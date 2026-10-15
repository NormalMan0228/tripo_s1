"""Turn one Tripo multi-clip FBX (Humanoid rig, Mixamo bone names) into the game GLB.

  blender -b --factory-startup -P tools/body_gen/build_game_monster.py -- <in.fbx> <out.glb> <config.json> <id> [report.json]

The config (art/characters/body_p2_v1/mon_v3/anim/game_build.json) gives, per monster: height_m,
clips {game clip name: text found in the Tripo action name, or {match, start, end} seconds for one
stage of a multi-stage motion}, loops, loop_min_seconds, attack_impact (optional seconds; otherwise
the frame where a hand reaches furthest forward), glow_hues (hue ranges for the emission map, e.g.
yellow eyes), cleanup (mesh_cleanup.py options, repeated on the rigged mesh) and recolor (shift one
colour family of the base texture, e.g. an NPC's hair, to an approved hue) and hover ({height, bob,
period, fall}: floating creatures fly at that height and fall out of the air when they die).

* every clip is re-sampled at 30 fps (the FBX is 24 fps) and quaternion signs are kept continuous;
  loop clips are cropped to the best-matching start/end pair (loop_min_seconds, default 45 % of
  the clip) and the remaining seam is blended over the last quarter, so they repeat without a pop;
* where the deformed mesh dips below the rest-pose floor (crouches, lying dead), the hips are
  raised by a smooth envelope of that depth (no per-frame judder);
* bones mixamorig:X -> mixamorig_X (':' is a NodePath separator in Godot);
* the creature is turned to face glTF +Z, scaled to height_m, feet on y=0, centred;
* base colour <= 1024 px, matte, plus a 512 px emission map cut from glow_hues;
* the report lists clip lengths, loop seam error, hips drift, lowest foot point per clip, impact time,
  and a no-pop check per clip (largest bone turn per frame, hips move per frame, loop seam jumps).
"""
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT, CFG_PATH, MID = argv[:4]
REPORT_PATH = argv[4] if len(argv) > 4 else OUT.rsplit('.', 1)[0] + '_report.json'
CFG = json.load(open(CFG_PATH, encoding='utf-8'))
M = CFG['monsters'][MID]
FPS = CFG.get('fps', 30)
TEX_MAX = CFG.get('texture_max', 1024)
REPORT = {'id': MID, 'source': SRC, 'clips': {}, 'warnings': []}


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC, automatic_bone_orientation=False)
scene = bpy.context.scene
SRC_FPS = scene.render.fps / scene.render.fps_base
ARM = next(o for o in scene.objects if o.type == 'ARMATURE')
MESHES = [o for o in scene.objects if o.type == 'MESH']
if M.get('cleanup'):
    # same debris/crack/fin/hole cleanup as mon_v3/clean/ (tools/body_gen/mesh_cleanup.py), on the rigged mesh
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mesh_cleanup
    REPORT['cleanup'] = {m.name: mesh_cleanup.clean_object(m, mesh_cleanup.parse(M['cleanup'])) for m in MESHES}
    REPORT['cleanup']['options'] = M['cleanup']
SOURCES = list(bpy.data.actions)
PB = list(ARM.pose.bones)
NAMES = [pb.name for pb in PB]
UP = Vector((0, 0, 1))


def bone(name):
    return next(pb for pb in PB if pb.name.split(':')[-1] == name)


# ------------------------------------------------------------------ rest-pose measurements (world space)
def rest_points():
    pts = []
    for m in MESHES:
        pts.extend(m.matrix_world @ v.co for v in m.data.vertices)
    return pts


ARM.data.pose_position = 'REST'
bpy.context.view_layer.update()
POINTS = rest_points()
ARM.data.pose_position = 'POSE'
ZMIN = min(p.z for p in POINTS)
HEIGHT = max(p.z for p in POINTS) - ZMIN
aw = ARM.matrix_world
left = aw @ ARM.data.bones[bone('LeftUpLeg').name].head_local
right = aw @ ARM.data.bones[bone('RightUpLeg').name].head_local
RAW_F = (left - right).cross(UP)
RAW_F.z = 0
RAW_F.normalize()
axis = 0 if abs(RAW_F.x) >= abs(RAW_F.y) else 1
F = Vector((0, 0, 0))
F[axis] = math.copysign(1.0, RAW_F[axis])
REPORT['facing_estimate_skew_degrees'] = round(math.degrees(RAW_F.angle(F)), 2)


# ------------------------------------------------------------------ sample every source clip
def find_source(pattern):
    hits = sorted((a for a in SOURCES if pattern.lower() in a.name.lower()), key=lambda a: a.name)
    if not hits:
        raise SystemExit('clip pattern %r matched %s' % (pattern, []))
    if len(hits) > 1:  # the same motion generated twice: both are the same prompt, keep one
        REPORT['warnings'].append('clip pattern %r matched %d actions, used %s' % (pattern, len(hits), hits[0].name))
    return hits[0]


def assign(act):
    if not ARM.animation_data:
        ARM.animation_data_create()
    ARM.animation_data.action = act
    if hasattr(ARM.animation_data, 'action_slot') and ARM.animation_data.action_slot is None and len(act.slots):
        ARM.animation_data.action_slot = act.slots[0]


HIPS, HANDS = bone('Hips'), [bone('LeftHand'), bone('RightHand')]
STRIKERS = HANDS + [bone('LeftToeBase'), bone('RightToeBase'), bone('Head')]  # what can land a blow
TOES = [bone('LeftToeBase'), bone('RightToeBase'), bone('LeftFoot'), bone('RightFoot')]


def lowest_point():
    """Lowest z of the deformed mesh (world space) at the current frame."""
    dg = bpy.context.evaluated_depsgraph_get()
    z = 1e9
    for m in MESHES:
        ev = m.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        mw = np.array(ev.matrix_world)
        z = min(z, float((co.reshape(-1, 3) @ mw[2, :3]).min() + mw[2, 3]))
        ev.to_mesh_clear()
    return z


def sample(act, t0=None, t1=None):
    """Local channels (loc, quat, scale) of every bone at 30 fps between t0 and t1 seconds of the
    action (default: all of it), plus world points for checks."""
    assign(act)
    start, end = act.frame_range
    if t1 is not None:
        end = min(end, start + t1 * SRC_FPS)
    if t0 is not None:
        start = start + t0 * SRC_FPS
    seconds = (end - start) / SRC_FPS
    n = int(round(seconds * FPS)) + 1
    loc = np.zeros((n, len(PB), 3))
    rot = np.zeros((n, len(PB), 4))
    scl = np.zeros((n, len(PB), 3))
    hips, hands, feet, low, toes = [], [], [], [], []
    for i in range(n):
        f = start + i / FPS * SRC_FPS
        scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        for j, pb in enumerate(PB):
            l, q, s = pb.matrix_basis.decompose()
            loc[i, j], rot[i, j], scl[i, j] = l, q, s
        w = ARM.matrix_world
        hips.append(w @ HIPS.head)
        hands.append([w @ h.tail for h in STRIKERS])
        feet.append(min((w @ t.tail).z for t in TOES))
        toes.append([w @ TOES[0].tail, w @ TOES[1].tail])
        low.append(lowest_point())
    # keep quaternion signs continuous so the exported curves never take the long way round
    for i in range(1, n):
        flip = (rot[i] * rot[i - 1]).sum(axis=1) < 0
        rot[i, flip] *= -1
    return {'loc': loc, 'rot': rot, 'scl': scl, 'hips': hips, 'hands': hands, 'feet': feet, 'low': low, 'toes': toes, 'n': n}


def ground_speed(c):
    """In-place walk/run: the foot on the ground slides backward under the body at the speed the
    creature would travel. Median backward speed (source units/s) of whichever toe is lower, on
    frames where it is within 4 % of the height of the floor; the game's WALK_REF/RUN_REF."""
    v = []
    t = c['toes']
    for i in range(1, len(t)):
        k = 0 if t[i][0].z <= t[i][1].z else 1
        if t[i][k].z - ZMIN > 0.04 * HEIGHT:
            continue
        v.append(-(t[i][k] - t[i - 1][k]).dot(F) * FPS)
    v = [x for x in v if x > 0]
    return float(np.median(v)) if v else 0.0


HIPS_INDEX = PB.index(HIPS)
HIPS_TO_LOCAL = (ARM.matrix_world.to_3x3() @ ARM.data.bones[HIPS.name].matrix_local.to_3x3()).inverted()


def smooth_envelope(x, loop, half=6, sigma=2.0):
    """Running max over +-half frames, then a Gaussian blur: never below x by much, and no
    frame-to-frame jumps (wraps around for loop clips)."""
    n = len(x)
    pad = half + int(3 * sigma) + 1
    if loop:
        xp = np.concatenate([x[-pad - 1:-1], x, x[1:pad + 1]])  # frame n-1 equals frame 0
    else:
        xp = np.concatenate([np.full(pad, x[0]), x, np.full(pad, x[-1])])
    env = np.array([xp[i - half:i + half + 1].max() for i in range(half, len(xp) - half)])
    env = np.concatenate([np.full(half, env[0]), env, np.full(half, env[-1])])
    k = np.exp(-0.5 * (np.arange(-3 * sigma, 3 * sigma + 1) / sigma) ** 2)
    sm = np.convolve(env, k / k.sum(), mode='same')
    return sm[pad:pad + n]


def lift_out_of_ground(c, loop):
    """Retargeted clips can push the body below the floor (crouches, lying dead). Raise the hips by
    how far the deformed mesh dips under the rest-pose floor - taken as a smooth envelope over time,
    because the lowest point hops between the feet and a per-frame lift makes the body judder.
    Frames above the floor (hops) are left alone. Returns the largest lift as a fraction of H."""
    raw = np.maximum(0.0, ZMIN - np.array(c['low']))
    if not raw.any():
        return 0.0
    lift = smooth_envelope(raw, loop)
    for i, dz in enumerate(lift):
        if dz > 0:
            c['loc'][i, HIPS_INDEX] += np.array(HIPS_TO_LOCAL @ Vector((0, 0, float(dz))))
    c['lift_residual'] = float((raw - lift).max())  # how far it can still sink at the worst frame
    return round(float(lift.max()) / HEIGHT, 4)


def add_hover(c, name, loop, hv):
    """Floating creatures (category 2: harpy, imp, gargoyle, frost wraith, lich): raise the hips by
    hv['height'] metres with a gentle bob of hv.get('bob', 0.06) m every hv.get('period', 2.0) s
    (loops use a whole number of bobs so the seam stays closed). Death starts in the air and falls:
    the lift eases to 0 over hv.get('fall', 0.7) s, after which the floor rules apply."""
    n = c['n']
    to_src = HEIGHT / M['height_m']  # metres -> source units
    h = hv['height'] * to_src
    bob = hv.get('bob', 0.06) * to_src
    seconds = (n - 1) / FPS
    if loop:
        cycles = max(1, round(seconds / hv.get('period', 2.0)))
        omega = 2 * math.pi * cycles / max(seconds, 1e-6)
    else:
        omega = 2 * math.pi / hv.get('period', 2.0)
    for i in range(n):
        t = i / FPS
        dz = h + bob * math.sin(omega * t)
        if name == 'death':
            dz *= 1 - smooth(t / hv.get('fall', 0.7))
        c['loc'][i, HIPS_INDEX] += np.array(HIPS_TO_LOCAL @ Vector((0, 0, dz)))
    return hv['height']


def close_loop(c):
    """Blend the last quarter toward the first pose (rotations by slerp) so frame n-1 == frame 0."""
    n = c['n']
    k = max(6, n // 4)
    seam_before = float(np.abs(c['rot'][-1] - c['rot'][0]).max())
    for j in range(len(PB)):
        q0 = Quaternion(c['rot'][0, j])
        qe = Quaternion(c['rot'][-1, j])
        corr = q0 @ qe.inverted()
        dl = c['loc'][0, j] - c['loc'][-1, j]
        ds = c['scl'][0, j] - c['scl'][-1, j]
        for i in range(n - k, n):
            w = smooth((i - (n - k - 1)) / k)
            q = Quaternion((1, 0, 0, 0)).slerp(corr, w) @ Quaternion(c['rot'][i, j])
            if q.dot(Quaternion(c['rot'][i - 1, j])) < 0:
                q.negate()
            c['rot'][i, j] = q
            c['loc'][i, j] += w * dl
            c['scl'][i, j] += w * ds
    return round(seam_before, 4)


def best_loop_window(c, min_frames):
    """AI clips rarely end where they start. Pick the frame pair (i, j), at least min_frames
    apart, whose poses and speeds match best (bone rotations, their change per frame and the hips
    position; longer windows win ties),
    and crop the clip to it. Returns (i, j, mismatch)."""
    q = c['rot']
    n = c['n']
    dots = np.abs(np.einsum('ibk,jbk->ijb', q, q))
    hips = c['loc'][:, HIPS_INDEX]
    d = (1 - dots).sum(axis=2) + 10 * ((hips[:, None, :] - hips[None, :, :]) ** 2).sum(axis=2) / HEIGHT ** 2
    # also match speed: the motion leaving frame i should look like the motion arriving at frame j
    v = np.zeros_like(q)
    v[:-1] = q[1:] * np.sign((q[1:] * q[:-1]).sum(axis=2, keepdims=True)) - q[:-1]
    vin = np.zeros_like(q)
    vin[1:] = v[:-1]
    d = d + 4 * ((v[:, None] - vin[None, :]) ** 2).sum(axis=(2, 3))
    best = None
    for i in range(0, n - min_frames):
        for j in range(i + min_frames, n):
            score = d[i, j] * (1.5 - 0.5 * (j - i) / (n - 1))
            if best is None or score < best[0]:
                best = (score, i, j)
    _, i, j = best
    for key in ('loc', 'rot', 'scl'):
        c[key] = c[key][i:j + 1].copy()
    for key in ('hips', 'hands', 'feet', 'low', 'toes'):
        c[key] = c[key][i:j + 1]
    c['n'] = j - i + 1
    return i, j, round(float(d[i, j]), 4)


def measure_low(c):
    """Lowest mesh point per frame for edited channels (pose set directly, no action)."""
    ARM.animation_data.action = None
    low = []
    for i in range(c['n']):
        for j, pb in enumerate(PB):
            pb.matrix_basis = Matrix.LocRotScale(Vector(c['loc'][i, j]), Quaternion(c['rot'][i, j]),
                                                 Vector(c['scl'][i, j]))
        bpy.context.view_layer.update()
        low.append(lowest_point())
    c['low'] = low


def despike(c, big=25.0):
    """Retargeting sometimes flips a bone for a single frame (a wrist or forearm turning 60+
    degrees and straight back). Where frame i is far from both neighbours but the neighbours are
    close to each other, replace it with their halfway pose. Real fast moves (a smash) turn the
    same way over several frames and are left alone. Returns the number of fixed bone-frames."""
    q = c['rot']
    fixed = 0
    for _ in range(3):
        n_fix = 0
        for i in range(1, len(q) - 1):
            for j in range(q.shape[1]):
                a = Quaternion(q[i - 1, j])
                b = Quaternion(q[i, j])
                d = Quaternion(q[i + 1, j])
                ab = math.degrees(a.rotation_difference(b).angle)
                bd = math.degrees(b.rotation_difference(d).angle)
                ad = math.degrees(a.rotation_difference(d).angle)
                ab, bd, ad = (min(x, 360 - x) for x in (ab, bd, ad))
                if ab > big and bd > big and ad < 0.5 * min(ab, bd):
                    m = a.slerp(d, 0.5)
                    if m.dot(b) < 0:
                        m.negate()
                    q[i, j] = m
                    c['loc'][i, j] = 0.5 * (c['loc'][i - 1, j] + c['loc'][i + 1, j])
                    n_fix += 1
        fixed += n_fix
        if not n_fix:
            break
    return fixed


def destep(c, thr=40.0, k=3):
    """A bone that turns more than thr degrees between two frames and stays there (a wrist or
    ankle flipping during retargeting) reads as a pop. Spread that turn over the k frames on each
    side with an eased slerp between the poses just outside the window. Returns how many turns
    were spread."""
    q = c['rot']
    n = len(q)
    count = 0
    for j in range(q.shape[1]):
        i = 0
        while i < n - 1:
            a_ = Quaternion(q[i, j])
            b_ = Quaternion(q[i + 1, j])
            ang = math.degrees(a_.rotation_difference(b_).angle)
            if min(ang, 360 - ang) > thr:
                a = max(0, i - k)
                b = min(n - 1, i + 1 + k)
                qa, qb = Quaternion(q[a, j]), Quaternion(q[b, j])
                for t in range(a + 1, b):
                    w = smooth((t - a) / (b - a))
                    m = qa.slerp(qb, w)
                    if m.dot(Quaternion(q[t - 1, j])) < 0:
                        m.negate()
                    q[t, j] = m
                count += 1
                i = b
            else:
                i += 1
    return count


def smoothness(c, loop):
    """No-pop check: largest bone rotation between consecutive frames (degrees), largest hips
    move per frame (fraction of height) and, for loops, the pose and speed jump across the seam."""
    q = c['rot']
    dots = np.clip(np.abs((q[1:] * q[:-1]).sum(axis=2)), 0, 1)
    step = np.degrees(2 * np.arccos(dots))  # (n-1, bones)
    hips = c['loc'][:, HIPS_INDEX]
    fi, bj = np.unravel_index(int(step.argmax()), step.shape)
    out = {'max_bone_deg_per_frame': round(float(step.max()), 2),
           'max_bone_turn_at': [NAMES[bj] if bj < len(NAMES) else bj, int(fi)],
           'max_hips_move_per_frame_ratio': round(float(np.linalg.norm(hips[1:] - hips[:-1], axis=1).max()) / HEIGHT, 4)}
    if loop and len(q) > 2:
        seam = np.degrees(2 * np.arccos(np.clip(np.abs((q[-1] * q[0]).sum(axis=1)), 0, 1)))
        out['seam_pose_deg'] = round(float(seam.max()), 2)
        # speed just before the seam vs just after it (frame n-1 equals frame 0, so compare n-2->n-1 with 0->1)
        out['seam_speed_jump_deg'] = round(float(np.abs(step[-1] - step[0]).max()), 2)
    return out


clips = {}
for name, spec in M['clips'].items():
    # spec: text found in the action name, or {"match": text, "start": s, "end": s} for one stage
    # of a Tripo multi-stage motion (several motions generated as one action)
    if isinstance(spec, str):
        spec = {'match': spec}
    src = find_source(spec['match'])
    c = sample(src, spec.get('start'), spec.get('end'))
    info = {'source': 'tripo:' + src.name.split('|', 1)[-1][:80], 'frames': c['n'],
            'window': [spec.get('start'), spec.get('end')],
            'seconds': round((c['n'] - 1) / FPS, 3), 'loop': name in M.get('loops', [])}
    info['despiked_frames'] = despike(c)
    info['smoothed_turns'] = destep(c)
    if name in ('walk', 'run'):
        info['ground_speed_mps'] = round(ground_speed(c) * M['height_m'] / HEIGHT, 3)
    if info['loop']:
        # loop: crop to the best-matching window, blend the remaining seam, then re-measure the floor
        min_frames = int(round(M.get('loop_min_seconds', {}).get(name, max(0.6, 0.45 * (c['n'] - 1) / FPS)) * FPS))
        i, j, mismatch = best_loop_window(c, min(min_frames, c['n'] - 2))
        info['loop_window_seconds'] = [round(i / FPS, 3), round(j / FPS, 3)]
        info['loop_window_mismatch'] = mismatch
        info['seam_quat_error_before'] = close_loop(c)
        measure_low(c)
        info['frames'] = c['n']
        info['seconds'] = round((c['n'] - 1) / FPS, 3)
    info['ground_lift_max_ratio'] = lift_out_of_ground(c, info['loop'])
    if M.get('hover'):
        info['hover_m'] = add_hover(c, name, info['loop'], M['hover'])
    info['ground_sink_left_ratio'] = round(c.get('lift_residual', 0.0) / HEIGHT, 4)
    info.update(smoothness(c, info['loop']))
    if info['max_bone_deg_per_frame'] > 30:
        REPORT['warnings'].append('%s: a bone turns %.0f degrees in one frame (pop?)' % (name, info['max_bone_deg_per_frame']))
    h = c['hips']
    drift = max(math.hypot(p.x - h[0].x, p.y - h[0].y) for p in h)
    info['hips_drift_ratio'] = round(drift / HEIGHT, 3)
    info['lowest_foot_ratio'] = round((min(c['feet']) - ZMIN) / HEIGHT, 3)
    if name != 'death' and drift / HEIGHT > 0.2:
        REPORT['warnings'].append('%s: hips move %.2f of the height' % (name, drift / HEIGHT))
    clips[name] = c
    REPORT['clips'][name] = info

# attack impact: a blow travels toward the foe (forward) and/or down (smash, stomp, slam). Score
# each frame by the fastest hand, foot or head on forward speed plus downward speed (hips included,
# for body slams), skip the first 0.25 s and the last 0.3 s, find the first strike within 80 % of
# the top score (the first hit of a combo) and take the moment that strike stops. Raising the arms
# for a wind-up scores nothing.
# An "attack_impact" value in the config overrides this after a visual check.
att = clips.get('attack')
if att:
    if 'attack_impact' in M:
        impact = M['attack_impact']
        REPORT['attack_impact_source'] = 'config'
    else:
        pts = [list(hs) + [hp] for hs, hp in zip(att['hands'], att['hips'])]
        score = []
        for i in range(len(pts) - 1):
            best = 0.0
            for k in range(len(pts[i])):
                v = (pts[i + 1][k] - pts[i][k]) * FPS
                best = max(best, max(0.0, v.dot(F)) + max(0.0, -v.z))
            score.append(best)
        a, b = int(0.25 * FPS), max(int(0.25 * FPS) + 1, len(score) - int(0.3 * FPS))
        top = max(score[a:b])
        idx = next(i for i in range(a, b) if score[i] >= 0.8 * top)
        # the blow lands where that strike stops: the first frame after its speed peak that drops
        # below half of it (full extension / contact)
        peak = idx
        while peak + 1 < len(score) and score[peak + 1] >= score[peak]:
            peak += 1
        end = peak
        while end + 1 < len(score) and score[end + 1] >= 0.5 * score[peak] and end - peak < int(0.4 * FPS):
            end += 1
        impact = (end + 1) / FPS
        REPORT['attack_impact_source'] = 'auto: end of the first fast forward/down strike (hands, feet, head, hips)'
    REPORT['attack_impact_seconds'] = round(impact, 3)
    if impact < 0.3 or impact > 1.6:
        REPORT['warnings'].append('attack impact at %.2f s - check' % impact)

# ------------------------------------------------------------------ rename bones, write game actions
for src in SOURCES:
    bpy.data.actions.remove(src)
for b in ARM.data.bones:
    b.name = b.name.replace(':', '_')
NAMES = [pb.name for pb in ARM.pose.bones]
for pb in ARM.pose.bones:
    pb.rotation_mode = 'QUATERNION'

for name, c in clips.items():
    act = bpy.data.actions.new(name)
    n = c['n']
    frames = np.arange(n, dtype=np.float64)
    for j, bname in enumerate(NAMES):
        for path, arr, size in (('location', c['loc'], 3), ('rotation_quaternion', c['rot'], 4), ('scale', c['scl'], 3)):
            for k in range(size):
                fc = act.fcurves.new('pose.bones["%s"].%s' % (bname, path), index=k, action_group=bname)
                fc.keyframe_points.add(n)
                fc.keyframe_points.foreach_set('co', np.column_stack([frames, arr[:, j, k]]).ravel())
                fc.keyframe_points.foreach_set('interpolation', [1] * n)  # LINEAR
                fc.update()
    act.use_fake_user = True
    assign(act)
scene.render.fps = FPS
scene.render.fps_base = 1
assign(bpy.data.actions['idle'])

# ------------------------------------------------------------------ orientation, scale, ground
angle = math.atan2(-1.0, 0.0) - math.atan2(F.y, F.x)  # Blender -Y becomes glTF +Z
angle = round(angle / (math.pi / 2)) * (math.pi / 2)
scale = M['height_m'] / HEIGHT
turn = Matrix.Rotation(angle, 4, 'Z')
moved = [turn @ (p * scale) for p in POINTS[::5]]
cx = (max(p.x for p in moved) + min(p.x for p in moved)) / 2
cy = (max(p.y for p in moved) + min(p.y for p in moved)) / 2
cz = min(p.z for p in moved)
ARM.matrix_world = Matrix.Translation((-cx, -cy, -cz)) @ turn @ Matrix.Scale(scale, 4) @ ARM.matrix_world
REPORT['facing'] = {'armature_forward': list(F), 'turned_degrees': round(math.degrees(angle), 1), 'gltf_forward': '+Z'}
REPORT['scale'] = {'height_m': M['height_m'], 'source_height': round(HEIGHT, 4), 'uniform_scale': round(scale, 5)}


# ------------------------------------------------------------------ material, emission
def emission_from(img, hues):
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[:, :, :3]
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    s = np.where(mx > 1e-5, (mx - mn) / np.maximum(mx, 1e-5), 0)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    d = np.maximum(mx - mn, 1e-5)
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    in_hue = np.zeros_like(mx, dtype=bool)
    for lo, hi in hues:
        in_hue |= (hue >= lo) & (hue <= hi)
    chosen = None
    for v_min in (0.72, 0.78, 0.84, 0.9, 0.95):
        mask = in_hue & (mx > v_min) & (s > 0.45)
        chosen = (v_min, mask, float(mask.mean()))
        if chosen[2] <= M.get('max_emission_cover', 0.01):
            break
    v_min, mask, cover = chosen
    soft = np.clip((mx - v_min) / 0.12, 0, 1) * mask
    out = np.zeros((h, w, 4), dtype=np.float32)
    out[:, :, :3] = rgb * soft[:, :, None] * 1.15
    out[:, :, 3] = 1
    em = bpy.data.images.new(MID + '_emission', w, h)
    em.pixels.foreach_set(out.ravel())
    if w > 512:
        em.scale(512, 512)
    em.pack()
    REPORT['emission'] = {'cover': round(cover, 5), 'value_threshold': v_min, 'hues': hues}
    return em


def recolor(img, rc):
    """Shift one colour family in the base texture (e.g. hair) to the approved hue: pixels whose
    hue is within rc['hue'] (and saturation within rc.get('sat', [0, 1]), value >= rc.get('val_min', 0))
    get hue rc['to_hue'] and saturation x rc.get('sat_scale', 1); value (shading) is kept."""
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    rgb = px[:, :3]
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    lo, hi = rc['hue']
    slo, shi = rc.get('sat', [0.0, 1.0])
    m = (hue >= lo) & (hue <= hi) & (sat >= slo) & (sat <= shi) & (mx >= rc.get('val_min', 0.0))
    hn = np.full(m.sum(), rc['to_hue'])
    sn = np.clip(sat[m] * rc.get('sat_scale', 1.0), 0, 1)
    vn = mx[m]
    i = np.floor(hn * 6).astype(int) % 6
    f = hn * 6 - np.floor(hn * 6)
    p_, q_, t_ = vn * (1 - sn), vn * (1 - f * sn), vn * (1 - (1 - f) * sn)
    out = np.select([(i == k)[:, None] for k in range(6)],
                    [np.stack(c, 1) for c in ((vn, t_, p_), (q_, vn, p_), (p_, vn, t_), (p_, q_, vn), (t_, p_, vn), (vn, p_, q_))])
    rgb[m] = out
    px[:, :3] = rgb
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return {'pixels': int(m.sum()), 'share': round(float(m.mean()), 4), 'rule': rc}


tex_sizes = []
for mesh in MESHES:
    for slot in mesh.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
        base = None
        for n in list(nodes):
            if n.type == 'TEX_IMAGE' and n.image:
                if any(l.to_socket == bsdf.inputs['Base Color'] for l in n.outputs[0].links):
                    if max(n.image.size) > TEX_MAX:
                        n.image.scale(TEX_MAX, TEX_MAX)
                    base = n
                else:
                    nodes.remove(n)  # roughness/metal maps: the game look is matte
        for sock in ('Metallic', 'Roughness', 'Specular IOR Level'):
            if sock in bsdf.inputs:
                for l in list(bsdf.inputs[sock].links):
                    links.remove(l)
        bsdf.inputs['Metallic'].default_value = 0.0
        bsdf.inputs['Roughness'].default_value = 0.82
        if base is not None and M.get('recolor'):
            REPORT['recolor'] = recolor(base.image, M['recolor'])
        if base is not None:
            tex_sizes.append(list(base.image.size))
            if M.get('glow_hues'):
                emit = nodes.new('ShaderNodeTexImage')
                emit.image = emission_from(base.image, M['glow_hues'])
                if base.inputs['Vector'].links:
                    links.new(base.inputs['Vector'].links[0].from_node.outputs[0], emit.inputs['Vector'])
                links.new(emit.outputs['Color'], bsdf.inputs['Emission Color'])
                bsdf.inputs['Emission Strength'].default_value = 1.0
        mat.name = MID + '_material'
for mesh in MESHES:
    mesh.name = MID + '_mesh'
    REPORT['triangles'] = REPORT.get('triangles', 0) + sum(len(p.vertices) - 2 for p in mesh.data.polygons)
REPORT['texture_sizes'] = tex_sizes
ARM.name = MID

bpy.ops.export_scene.gltf(
    filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='ACTIONS',
    export_skins=True, export_morph=False, export_image_format='JPEG', export_jpeg_quality=88,
    export_yup=True, export_apply=False, export_optimize_animation_size=False, export_anim_single_armature=True,
    export_reset_pose_bones=True, export_def_bones=False, export_cameras=False, export_lights=False,
    export_extras=False, export_tangents=False)
REPORT['clip_order'] = list(REPORT['clips'])
json.dump(REPORT, open(REPORT_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('BUILD_OK', MID, json.dumps(REPORT, ensure_ascii=False))
