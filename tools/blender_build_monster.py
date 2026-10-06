"""Blender (headless) step of tools/build_monsters.py: merge Tripo clips into ONE game GLB per monster.

blender -b --factory-startup --python tools/blender_build_monster.py -- <config.json>

* base mesh + skin from the Tripo rig GLB; bones renamed tripo::X -> tripo_X (':' is a NodePath separator
  in Godot).
* every Tripo retarget GLB contributes its single clip (re-sampled at 30 fps, optionally cropped,
  re-timed or closed into a loop); clips Tripo cannot provide (quadruped idle/run/attack/hurt, and death
  for everyone) are keyframed here procedurally on the Tripo skeleton.
* the creature is turned to face glTF +Z (Godot's forward for this game), scaled to its in-game height,
  feet on y=0, centred on the origin.
* textures: base colour + normal map <=1024 px, ORM dropped (matte), plus a 512 px emission map cut from
  the base colour (bright saturated pixels in the variant's glow hue: eyes, embers, ice, spores).
* exports GLB with all actions and writes a JSON report (clips, lengths, size, facing, emission cover).
"""
import bpy
import json
import math
import sys
from mathutils import Vector, Quaternion, Matrix

CFG = json.load(open(sys.argv[sys.argv.index('--') + 1], encoding='utf-8'))
FPS = 30
REPORT = {'id': CFG['id'], 'clips': {}, 'warnings': []}


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ import
def import_glb(path):
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.type == 'MESH' and o.name.startswith('Icosphere'):  # importer's bone display shape
            new.remove(o)
            bpy.data.objects.remove(o, do_unlink=True)
    return new, [a for a in bpy.data.actions if a not in acts_before]


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
objs, acts = import_glb(CFG['base'])
ARM = next(o for o in objs if o.type == 'ARMATURE')
MESHES = [o for o in objs if o.type == 'MESH']
for a in acts:
    bpy.data.actions.remove(a)
if ARM.animation_data:
    ARM.animation_data.action = None
for bone in ARM.data.bones:
    bone.name = bone.name.replace('::', '_')
BONES = {b.name: b for b in ARM.data.bones}
ROOT = next(b for b in ARM.data.bones if b.parent is None)
UP = Vector((0, 0, 1))


def head(name):
    return BONES[name].head_local.copy()


# ------------------------------------------------------------------ facing (armature space)
if CFG['rig'] == 'biped':
    left, right = head('L_Thigh'), head('R_Thigh')
else:
    lefts = [b.head_local for b in ARM.data.bones if b.name.endswith('_Left_Limb_0')]
    rights = [b.head_local for b in ARM.data.bones if b.name.endswith('_Right_Limb_0')]
    left = sum(lefts, Vector()) / max(1, len(lefts))
    right = sum(rights, Vector()) / max(1, len(rights))
F = (left - right).cross(UP)
F.z = 0
F.normalize()
if CFG['rig'] == 'quadruped':
    fronts = [b.head_local for b in ARM.data.bones if b.name.startswith('tripo_0_') and b.name.endswith('_Limb_0')]
    backs = [b.head_local for b in ARM.data.bones if b.name.startswith('tripo_1_') and b.name.endswith('_Limb_0')]
    if fronts and backs:
        check = (sum(fronts, Vector()) / len(fronts) - sum(backs, Vector()) / len(backs))
        REPORT['facing_check_front_minus_hind_dot'] = round(check.dot(F), 4)
        if check.dot(F) < 0:
            REPORT['warnings'].append('front/hind limb labels disagree with left/right facing')
if CFG.get('flip_facing'):
    F = -F
RAW_F = F.copy()
_axis = 0 if abs(F.x) >= abs(F.y) else 1
F = Vector((0, 0, 0))
F[_axis] = math.copysign(1.0, RAW_F[_axis])  # Tripo outputs are axis aligned: snap the estimate
REPORT['facing_estimate_skew_degrees'] = round(math.degrees(RAW_F.angle(F)), 2)
S = F.cross(UP)  # creature's right side


def mesh_points():
    """Rest-pose vertices in armature space."""
    inv = ARM.matrix_world.inverted()
    pts = []
    for m in MESHES:
        mw = inv @ m.matrix_world
        pts.extend(mw @ v.co for v in m.data.vertices)
    return pts


POINTS = mesh_points()
ZMIN = min(p.z for p in POINTS)
ZMAX = max(p.z for p in POINTS)
HEIGHT = ZMAX - ZMIN
LENGTH = max(p.dot(F) for p in POINTS) - min(p.dot(F) for p in POINTS)


# ------------------------------------------------------------------ pose helpers
CHANNELS = {}  # bone -> list of (path, size)
for pb in ARM.pose.bones:
    pb.rotation_mode = 'QUATERNION'
    CHANNELS[pb.name] = [('pose.bones["%s"].location' % pb.name, 3), ('pose.bones["%s"].rotation_quaternion' % pb.name, 4),
                         ('pose.bones["%s"].scale' % pb.name, 3)]


def rest_pose():
    pose = {}
    for name in CHANNELS:
        pose[name] = (Vector((0, 0, 0)), Quaternion((1, 0, 0, 0)), Vector((1, 1, 1)))
    return pose


class Source:
    """A Tripo clip: evaluate its fcurves (old bone names) at a time in seconds."""
    def __init__(self, path):
        objs, acts = import_glb(path)
        self.action = acts[0]
        self.name = self.action.name
        self.action.name = 'tripo_src_' + self.name  # keep game clip names free
        self.start, self.end = self.action.frame_range
        self.src_fps = scene.render.fps / scene.render.fps_base  # importer maps seconds to scene frames
        self.duration = (self.end - self.start) / self.src_fps
        self.curves = {}
        for fc in self.action.fcurves:
            bone = fc.data_path.split('"')[1].replace('::', '_') if '"' in fc.data_path else None
            prop = fc.data_path.rsplit('.', 1)[-1]
            self.curves.setdefault(bone, {}).setdefault(prop, {})[fc.array_index] = fc
        for o in objs:
            bpy.data.objects.remove(o, do_unlink=True)

    def pose(self, t):
        frame = self.start + max(0.0, min(t, self.duration)) * self.src_fps
        pose = rest_pose()
        for bone, props in self.curves.items():
            if bone not in pose:
                continue
            loc, rot, scl = pose[bone]
            if 'location' in props:
                loc = Vector([props['location'][i].evaluate(frame) if i in props['location'] else 0 for i in range(3)])
            if 'rotation_quaternion' in props:
                rot = Quaternion([props['rotation_quaternion'][i].evaluate(frame) if i in props['rotation_quaternion']
                                  else (1 if i == 0 else 0) for i in range(4)]).normalized()
            if 'scale' in props:
                scl = Vector([props['scale'][i].evaluate(frame) if i in props['scale'] else 1 for i in range(3)])
            pose[bone] = (loc, rot, scl)
        return pose


def blend(a, b, w):
    out = {}
    for name in a:
        la, ra, sa = a[name]
        lb, rb, sb = b[name]
        if ra.dot(rb) < 0:
            rb = -rb
        out[name] = (la.lerp(lb, w), ra.slerp(rb, w), sa.lerp(sb, w))
    return out


def offset(pose, bone, rot_axis=None, angle=0.0, move=None):
    """Apply an armature-space rotation (about the bone head) and/or translation to one bone."""
    if bone not in pose:
        return
    loc, rot, scl = pose[bone]
    rest = BONES[bone].matrix_local
    if rot_axis is not None and abs(angle) > 1e-6:
        b = rest.to_quaternion()
        rot = rot @ (b.inverted() @ Quaternion(rot_axis, angle) @ b)
    if move is not None:
        loc = loc + rest.to_3x3().inverted() @ move
    pose[bone] = (loc, rot, scl)


def write_action(name, poses, loop):
    act = bpy.data.actions.new(name)
    for bone, channels in CHANNELS.items():
        for path, size in channels:
            kind = 1 if path.endswith('rotation_quaternion') else (0 if path.endswith('location') else 2)
            for index in range(size):
                values = []
                for frame, pose in enumerate(poses):
                    values.extend((float(frame), pose[bone][kind][index]))
                fc = act.fcurves.new(path, index=index, action_group=bone)
                fc.keyframe_points.add(len(poses))
                fc.keyframe_points.foreach_set('co', values)
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
                fc.update()
    if not ARM.animation_data:
        ARM.animation_data_create()
    ARM.animation_data.action = act
    if hasattr(ARM.animation_data, 'action_slot') and ARM.animation_data.action_slot is None and len(act.slots):
        ARM.animation_data.action_slot = act.slots[0]
    act.use_fake_user = True
    REPORT['clips'][name] = {'seconds': round((len(poses) - 1) / FPS, 3), 'frames': len(poses), 'loop': loop}
    return act


def frames(seconds):
    return [i / FPS for i in range(int(round(seconds * FPS)) + 1)]


# ------------------------------------------------------------------ clip recipes
def clip_from_source(src, start=0.0, end=None, speed=1.0, close_loop=0.0, return_after=0.0, lean=0.0, bob=0.0):
    end = src.duration if end is None else min(end, src.duration)
    span = (end - start) / speed
    poses = []
    for t in frames(span):
        poses.append(src.pose(start + t * speed))
    first, last = poses[0], poses[-1]
    if close_loop > 0:  # ease the tail back into the first frame for a seamless loop
        n = int(close_loop * FPS)
        for i in range(n):
            w = smooth((i + 1) / n)
            poses[len(poses) - n + i] = blend(poses[len(poses) - n + i], first, w)
    if return_after > 0:  # one-shot: ease from the last frame back to the clip's rest frame
        target = src.pose(0.0)
        for t in frames(return_after)[1:]:
            poses.append(blend(last, target, smooth(t / return_after)))
    if lean or bob:
        cycles = max(1, round(span / 0.5))
        for i, pose in enumerate(poses):
            phase = i / max(1, len(poses) - 1) * cycles * 2 * math.pi
            offset(pose, ROOT.name, S, -lean, Vector((0, 0, bob * HEIGHT * (0.5 + 0.5 * math.cos(phase)))))
    return poses


def head_bone():
    for name in ('tripo_Head_0', 'Head'):
        if name in BONES and (BONES[name].head_local - ROOT.head_local).dot(F) > -0.05 * LENGTH:
            return name
    return None


def tail_bones():
    out = []
    for b in ROOT.children:
        if 'Limb' in b.name or 'Spine' in b.name or 'Head' in b.name:
            continue
        if (b.tail_local - b.head_local).normalized().dot(F) < -0.4:
            out.append(b.name)
    return out


HEAD = head_bone()
TAILS = tail_bones() if CFG['rig'] == 'quadruped' and CFG.get('tail', True) else []
REPORT['bones'] = {'root': ROOT.name, 'head': HEAD, 'tail': TAILS, 'count': len(BONES)}


def quad_idle(seconds=2.4):
    poses = []
    for t in frames(seconds):
        p = rest_pose()
        a = 2 * math.pi * t / seconds
        offset(p, ROOT.name, S, 0.012 * math.sin(2 * a), Vector((0, 0, 0.012 * HEIGHT * math.sin(2 * a))))
        if HEAD:
            offset(p, HEAD, UP, 0.12 * math.sin(a))
            offset(p, HEAD, S, 0.05 * math.sin(2 * a + 0.6))
        for name in TAILS:
            offset(p, name, UP, 0.22 * math.sin(2 * a))
        poses.append(p)
    return poses


def quad_attack(windup, lunge=0.18, toss=False):
    """Crouch back during the server wind-up, then a lunge (bite) or head toss (gore) at the strike."""
    total = windup + 0.75
    poses = []
    for t in frames(total):
        p = rest_pose()
        if t < windup:
            w = smooth(t / windup)
            back, pitch, head_pitch = -0.07 * w, 0.10 * w, 0.12 * w
            if toss:
                pitch, head_pitch = -0.10 * w, -0.14 * w
                back += 0.015 * math.sin(t * 22) * w  # pawing rock
        elif t < windup + 0.18:
            w = smooth((t - windup) / 0.18)
            back = -0.07 + (lunge + 0.07) * w
            pitch = 0.10 - 0.24 * w if not toss else -0.10 + 0.32 * w
            head_pitch = 0.12 - 0.40 * w if not toss else -0.14 + 0.5 * w
        else:
            w = smooth((t - windup - 0.18) / 0.5)
            back = lunge * (1 - w)
            pitch = (-0.14 if not toss else 0.22) * (1 - w)
            head_pitch = (-0.28 if not toss else 0.36) * (1 - w)
        offset(p, ROOT.name, S, pitch, F * back * LENGTH + Vector((0, 0, 0.02 * HEIGHT * max(0.0, -back))))
        if HEAD:
            offset(p, HEAD, S, head_pitch)
        for name in TAILS:
            offset(p, name, S, 0.35 * smooth(min(1.0, t / windup)) * (1 if t < windup + 0.3 else 0.5))
        poses.append(p)
    return poses


def quad_hurt():
    poses = []
    for t in frames(0.5):
        p = rest_pose()
        w = math.sin(math.pi * min(1.0, t / 0.5)) * (1 - 0.3 * t)
        offset(p, ROOT.name, S, 0.16 * w, -F * 0.06 * LENGTH * w)
        offset(p, ROOT.name, F, 0.08 * w)
        if HEAD:
            offset(p, HEAD, S, 0.22 * w)
        poses.append(p)
    return poses


def pivot_lift(axis, angle, pose_points=POINTS):
    """Height to lift so a body rotated about the root head does not sink below the ground."""
    pivot = ROOT.head_local
    q = Quaternion(axis, angle)
    low = min((q @ (v - pivot)).z + pivot.z for v in pose_points[::7])
    return max(0.0, ZMIN - low)


def death(base_pose, flinch_pose=None):
    """Flinch, then topple (quadrupeds roll onto their side, bipeds fall onto their back) and settle."""
    if CFG['rig'] == 'quadruped':
        axis, final = F, 1.45
    else:
        axis, final = S, 1.4
    lift = pivot_lift(axis, final)
    poses = []
    for t in frames(1.4):
        if t < 0.22:
            w = smooth(t / 0.22)
            p = blend(base_pose, flinch_pose, w) if flinch_pose else {k: v for k, v in base_pose.items()}
            p = {k: (v[0].copy(), v[1].copy(), v[2].copy()) for k, v in p.items()}
            offset(p, ROOT.name, S, 0.12 * w if CFG['rig'] == 'quadruped' else -0.06 * w)
        else:
            k = (t - 0.22) / 0.62
            w = smooth(k) if k < 1 else 1.0
            if 0.84 <= t < 1.1:
                w = 1.0 + 0.05 * math.sin((t - 0.84) / 0.26 * math.pi)
            src = flinch_pose or base_pose
            p = {k2: (v[0].copy(), v[1].copy(), v[2].copy()) for k2, v in src.items()}
            offset(p, ROOT.name, axis, final * w, Vector((0, 0, lift * min(1.0, w))))
            if HEAD:
                offset(p, HEAD, S, 0.25 * min(1.0, w) * (1 if CFG['rig'] == 'quadruped' else -1))
        poses.append(p)
    return poses


# ------------------------------------------------------------------ build clips
sources = {name: Source(path) for name, path in CFG['clips'].items()}
REPORT['tripo_clips'] = {name: {'tripo_name': s.name, 'seconds': round(s.duration, 3)} for name, s in sources.items()}
rig = CFG['rig']
windup = CFG['windup']
if rig == 'quadruped':
    walk = sources['walk']
    write_action('walk', clip_from_source(walk), True)
    write_action('run', clip_from_source(walk, speed=CFG.get('run_speed', 1.75), lean=0.05, bob=0.025), True)
    write_action('idle', quad_idle(), True)
    write_action('attack', quad_attack(windup, toss=CFG['species'] == 'boar'), False)
    write_action('hurt', quad_hurt(), False)
    flinch = rest_pose()
    offset(flinch, ROOT.name, S, 0.15)
    write_action('death', death(rest_pose(), flinch), False)
else:
    idle = sources['idle']
    write_action('idle', clip_from_source(idle, 0.0, min(idle.duration, CFG.get('idle_seconds', 4.0)), close_loop=0.6), True)
    write_action('walk', clip_from_source(sources['walk']), True)
    if 'run' in sources:
        write_action('run', clip_from_source(sources['run']), True)
    else:
        write_action('run', clip_from_source(sources['walk'], speed=1.45, lean=0.06), True)
    impact = CFG['attack_impact']
    start = max(0.0, impact - windup)
    write_action('attack', clip_from_source(sources['attack'], start, impact + CFG.get('attack_follow', 0.8),
                                            return_after=0.35), False)
    write_action('hurt', clip_from_source(sources['hurt'], 0.0, CFG.get('hurt_seconds', 0.5), return_after=0.4), False)
    write_action('death', death(idle.pose(0.0), sources['hurt'].pose(0.45)), False)
    for extra in CFG.get('extras', []):
        write_action(extra, clip_from_source(sources[extra], return_after=0.3), False)
REPORT['attack_impact_seconds'] = round(min(windup, CFG.get('attack_impact', windup)), 3)
ARM.animation_data.action = bpy.data.actions.get('idle')

# ------------------------------------------------------------------ orientation, scale, ground
angle = math.atan2(-1.0, 0.0) - math.atan2(F.y, F.x)
# Tripo generations are axis aligned; a skewed left/right estimate (odd rigs) is snapped to the axis.
snapped = round(angle / (math.pi / 2)) * (math.pi / 2)
if abs(angle - snapped) > math.radians(12):
    REPORT['warnings'].append('facing snapped from %.1f degrees' % math.degrees(angle))
angle = snapped
REPORT['facing'] = {'armature_forward': [round(v, 3) for v in F], 'turned_degrees': round(math.degrees(angle), 2),
                    'gltf_forward': '+Z'}
scale = CFG['height'] / HEIGHT
turn = Matrix.Rotation(angle, 4, 'Z')
base = ARM.matrix_world.copy()
world_pts = [base @ p for p in POINTS[::5]]
moved = [turn @ (p * scale) for p in world_pts]
cx = (max(p.x for p in moved) + min(p.x for p in moved)) / 2
cy = (max(p.y for p in moved) + min(p.y for p in moved)) / 2
cz = min(p.z for p in moved)
ARM.matrix_world = Matrix.Translation((-cx, -cy, -cz)) @ turn @ Matrix.Scale(scale, 4) @ base
REPORT['scale'] = {'height_m': CFG['height'], 'source_height': round(HEIGHT, 4), 'uniform_scale': round(scale, 5),
                   'length_m': round(LENGTH * scale, 3)}

# ------------------------------------------------------------------ materials and textures
import numpy as np
HUES = {'forest': [(0.07, 0.21)], 'quarry': [(0.0, 0.13), (0.95, 1.0)], 'frost': [(0.45, 0.62)]}


def emission_from(base_img, variant):
    w, h = base_img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    base_img.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[:, :, :3]
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    v = mx
    s = np.where(mx > 1e-5, (mx - mn) / np.maximum(mx, 1e-5), 0)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    d = np.maximum(mx - mn, 1e-5)
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    in_hue = np.zeros_like(v, dtype=bool)
    for lo, hi in HUES[variant]:
        in_hue |= (hue >= lo) & (hue <= hi)
    sat_min = 0.3 if variant == 'frost' else 0.45
    chosen = None
    for v_min in (0.72, 0.78, 0.84, 0.9, 0.95):
        mask = in_hue & (v > v_min) & (s > sat_min)
        cover = float(mask.mean())
        chosen = (v_min, mask, cover)
        if cover <= CFG.get('max_emission_cover', 0.06):
            break
    v_min, mask, cover = chosen
    soft = np.clip((v - v_min) / 0.12, 0, 1) * mask
    out = np.zeros((h, w, 4), dtype=np.float32)
    out[:, :, :3] = rgb * soft[:, :, None] * 1.15
    out[:, :, 3] = 1
    img = bpy.data.images.new(CFG['id'] + '_emission', w, h)
    img.pixels.foreach_set(out.ravel())
    if w > 512:
        img.scale(512, 512)
    img.pack()
    REPORT['emission'] = {'cover': round(cover, 4), 'value_threshold': v_min, 'hues': HUES[variant]}
    return img


for mesh in MESHES:
    for slot in mesh.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
        base_img = None
        for n in list(nodes):
            if n.type == 'TEX_IMAGE' and n.image:
                img = n.image
                if max(img.size) > 1024:
                    img.scale(1024, 1024)
                if img.name.startswith('Color') or any(l.to_socket == bsdf.inputs['Base Color'] for l in n.outputs[0].links):
                    base_img = img
        for socket_name in ('Metallic', 'Roughness'):
            for link in list(bsdf.inputs[socket_name].links):
                links.remove(link)
        for n in list(nodes):
            if n.type == 'TEX_IMAGE' and n.image and n.image.name.startswith('ORM'):
                nodes.remove(n)
        bsdf.inputs['Metallic'].default_value = 0.0
        bsdf.inputs['Roughness'].default_value = 0.82
        if base_img is not None:
            emit = nodes.new('ShaderNodeTexImage')
            emit.image = emission_from(base_img, CFG['variant'])
            uv = next((l.from_node for n in nodes if n.type == 'TEX_IMAGE' and n.image == base_img
                       for l in n.inputs['Vector'].links), None)
            if uv is not None:
                links.new(uv.outputs[0], emit.inputs['Vector'])
            links.new(emit.outputs['Color'], bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = 1.0
        mat.name = CFG['id'] + '_material'
for mesh in MESHES:
    mesh.name = CFG['id'] + '_mesh'
    REPORT['triangles'] = REPORT.get('triangles', 0) + sum(len(p.vertices) - 2 for p in mesh.data.polygons)
ARM.name = CFG['id']

# ------------------------------------------------------------------ export
for a in list(bpy.data.actions):
    if a.name not in REPORT['clips']:
        bpy.data.actions.remove(a)
bpy.ops.export_scene.gltf(
    filepath=CFG['out'], export_format='GLB', export_animations=True, export_animation_mode='ACTIONS',
    export_skins=True, export_morph=False, export_image_format='JPEG', export_jpeg_quality=88,
    export_yup=True, export_apply=False, export_optimize_animation_size=False, export_anim_single_armature=True,
    export_reset_pose_bones=True, export_def_bones=False, export_cameras=False, export_lights=False,
    export_extras=False, export_tangents=False)
REPORT['clip_order'] = list(REPORT['clips'])
with open(CFG['report'], 'w', encoding='utf-8') as handle:
    json.dump(REPORT, handle, ensure_ascii=False, indent=2)
print('BUILD_OK', CFG['id'])
