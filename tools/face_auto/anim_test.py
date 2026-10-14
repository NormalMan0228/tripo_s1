"""Animation test clip for a baked face: keyframes the ARKit shape keys over a short scripted performance and renders it
(grey material, EEVEE, orthographic face camera from the landmarks) to an MP4 (FFMPEG, H.264) plus a contact sheet PNG.

The script reviews the expression set in motion rather than as single poses: eased transitions, overlaps (blink while
looking, smile + jaw while talking), the canthus-anchored blink at speed, the eyeballs and lids following the gaze, the
teeth / tongue / caruncle / brows riding along (every mesh with keys of the same names gets the same values).
Beats (seconds at 24 fps, default 12 s):
  0.0 neutral, 0.6 blink, 1.2 look left / right / up / down with lid follow, 3.0 double blink,
  3.6 talk: a viseme string ("hello, nice to meet you") from jawOpen / mouthFunnel / mouthPucker / mouthClose /
      mouthStretch / mouthSmile / mouthRollLower / tongue, 7.0 smile -> big smile + cheekSquint + blink,
  8.6 surprise (browInnerUp + browOuterUp + eyeWide + jawOpen), 9.8 frown (browDown + mouthFrown + noseSneer),
  10.8 back to neutral with a last blink.
Usage: blender -b <arkit_bp.blend> -P anim_test.py -- <out_dir> <landmarks.json> [view face|34] [seconds] [eyes_meta.json]
  env GRAY=0 keeps the file's materials; RES (default 540) square pixels.
Writes <out_dir>/anim_<view>.mp4, <out_dir>/anim_<view>_sheet.png (12 frames), <out_dir>/anim_keys.json (the curves).
"""
import bpy, sys, os, json, math
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0]); LMJ = a[1]; VIEW = a[2] if len(a) > 2 else 'face'; SEC = float(a[3]) if len(a) > 3 else 12.0
os.makedirs(OUT, exist_ok=True)
FPS = 24; NF = int(round(SEC * FPS)); RES = int(os.environ.get('RES', 540))
sc = bpy.context.scene; sc.frame_start, sc.frame_end = 1, NF; sc.render.fps = FPS

# ---- performance: list of (time_s, {key: value}) targets, eased between consecutive targets per key
def blink(t, d=0.22, s=1.0):
    return [(t, {'eyeBlinkLeft': 0, 'eyeBlinkRight': 0}), (t + d * 0.45, {'eyeBlinkLeft': s, 'eyeBlinkRight': s}),
            (t + d, {'eyeBlinkLeft': 0, 'eyeBlinkRight': 0})]
def look(t, l, r, hold=0.45, d=0.18):
    z = {k: 0 for k in ('eyeLookInLeft', 'eyeLookOutLeft', 'eyeLookInRight', 'eyeLookOutRight', 'eyeLookUpLeft', 'eyeLookUpRight',
                        'eyeLookDownLeft', 'eyeLookDownRight')}
    on = dict(z); on.update(l); on.update(r)
    return [(t, z), (t + d, on), (t + d + hold, on), (t + 2 * d + hold, z)]
VIS = {  # rough viseme shapes from ARKit keys
    'A': {'jawOpen': 0.55, 'mouthStretchLeft': 0.15, 'mouthStretchRight': 0.15},
    'E': {'jawOpen': 0.3, 'mouthStretchLeft': 0.45, 'mouthStretchRight': 0.45, 'mouthSmileLeft': 0.2, 'mouthSmileRight': 0.2},
    'I': {'jawOpen': 0.18, 'mouthSmileLeft': 0.35, 'mouthSmileRight': 0.35, 'mouthStretchLeft': 0.3, 'mouthStretchRight': 0.3},
    'O': {'jawOpen': 0.4, 'mouthFunnel': 0.7},
    'U': {'jawOpen': 0.15, 'mouthPucker': 0.8, 'mouthFunnel': 0.3},
    'M': {'mouthClose': 0.6, 'jawOpen': 0.08, 'mouthPressLeft': 0.3, 'mouthPressRight': 0.3},
    'F': {'jawOpen': 0.12, 'mouthRollLower': 0.6, 'mouthUpperUpLeft': 0.2, 'mouthUpperUpRight': 0.2},
    'L': {'jawOpen': 0.3, 'tongueOut': 0.25},
    'S': {'jawOpen': 0.08, 'mouthStretchLeft': 0.3, 'mouthStretchRight': 0.3},
    '_': {},
}
TALK = list('AELO_LAIS_MI_SU_MIS_U')                    # "hello, nice to meet you" as rough visemes, one per step
VK = sorted({k for v in VIS.values() for k in v})
def talk(t, step=0.16):
    ev = [(t, {k: 0 for k in VK})]
    for i, ch in enumerate(TALK):
        tgt = {k: 0 for k in VK}; tgt.update(VIS.get(ch, {})); ev.append((t + step * (i + 1), tgt))
    ev.append((t + step * (len(TALK) + 2), {k: 0 for k in VK}))
    return ev, t + step * (len(TALK) + 2)
EV = []
EV += blink(0.6)
EV += look(1.2, {'eyeLookOutLeft': 0.8}, {'eyeLookInRight': 0.8})
EV += look(1.9, {'eyeLookInLeft': 0.8}, {'eyeLookOutRight': 0.8})
EV += look(2.6, {'eyeLookUpLeft': 0.8}, {'eyeLookUpRight': 0.8}, hold=0.25)
EV += blink(3.15); EV += blink(3.45)
tv, tend = talk(3.8); EV += tv
S7 = max(7.0, tend + 0.2)
EV += [(S7, {'mouthSmileLeft': 0, 'mouthSmileRight': 0, 'cheekSquintLeft': 0, 'cheekSquintRight': 0}),
       (S7 + 0.4, {'mouthSmileLeft': 0.5, 'mouthSmileRight': 0.5}),
       (S7 + 0.9, {'mouthSmileLeft': 1.0, 'mouthSmileRight': 1.0, 'cheekSquintLeft': 0.6, 'cheekSquintRight': 0.6}),
       (S7 + 1.4, {'mouthSmileLeft': 1.0, 'mouthSmileRight': 1.0, 'cheekSquintLeft': 0.6, 'cheekSquintRight': 0.6}),
       (S7 + 1.7, {'mouthSmileLeft': 0, 'mouthSmileRight': 0, 'cheekSquintLeft': 0, 'cheekSquintRight': 0})]
EV += blink(S7 + 1.0, s=0.9)
S8 = S7 + 1.8
SUR = {'browInnerUp': 1, 'browOuterUpLeft': 0.9, 'browOuterUpRight': 0.9, 'eyeWideLeft': 0.8, 'eyeWideRight': 0.8, 'jawOpen': 0.45}
EV += [(S8, {k: 0 for k in SUR}), (S8 + 0.25, SUR), (S8 + 0.8, SUR), (S8 + 1.1, {k: 0 for k in SUR})]
S9 = S8 + 1.1
FR = {'browDownLeft': 0.9, 'browDownRight': 0.9, 'mouthFrownLeft': 0.8, 'mouthFrownRight': 0.8, 'noseSneerLeft': 0.5, 'noseSneerRight': 0.5}
EV += [(S9, {k: 0 for k in FR}), (S9 + 0.3, FR), (S9 + 0.8, FR), (S9 + 1.1, {k: 0 for k in FR})]
EV += blink(min(SEC - 0.5, S9 + 1.3))

# ---- keyframe every mesh that has the key (smooth Bezier = eased)
names = {}
for t, d in EV:
    for k, v in d.items(): names.setdefault(k, []).append((t, v))
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.data.shape_keys]
missing = sorted(k for k in names if not any(k in o.data.shape_keys.key_blocks for o in meshes))
for o in meshes:
    kbs = o.data.shape_keys.key_blocks
    for kb in kbs: kb.value = 0.0
    for k, pts in names.items():
        if k not in kbs: continue
        kb = kbs[k]; kb.slider_max = max(kb.slider_max, 1.0)
        for t, v in sorted(pts):
            kb.value = float(v); kb.keyframe_insert('value', frame=1 + t * FPS)
json.dump({'fps': FPS, 'frames': NF, 'keys': {k: sorted(v) for k, v in names.items()}, 'missing_keys': missing},
          open(os.path.join(OUT, 'anim_keys.json'), 'w'), indent=0)

# ---- look: grey, light, camera (same framing rule as render_m1.py)
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try: sc.render.engine = eng; break
    except TypeError: pass
sc.render.resolution_x = sc.render.resolution_y = RES; sc.view_settings.view_transform = 'Standard'
if not sc.world: sc.world = bpy.data.worlds.new('w')
sc.world.use_nodes = True; bgn = sc.world.node_tree.nodes['Background']; bgn.inputs[0].default_value = (0.62, 0.62, 0.64, 1); bgn.inputs[1].default_value = 0.55
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 1.6; so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (0.75, 0.25, -0.35)
IRIS = {}                                                        # side -> (rest gaze unit vector, iris radius deg)
if len(a) > 4 and os.path.exists(a[4]):                          # optional eyes json (eye_fit_ref eyes_meta.json)
    J4 = json.load(open(a[4])); E = J4.get('eyes', {k: v for k, v in J4.items() if k in ('L', 'R')})
    for sd, e in E.items():
        if 'iris_dir' in e: IRIS[sd] = (np.array(e['iris_dir'], float) / np.linalg.norm(e['iris_dir']), float(e.get('iris_radius_deg', 22)), np.array(e['C'], float))
if os.environ.get('GRAY', '1') != '0':
    cols = {'face': (0.55, 0.55, 0.57), 'eyes': (0.85, 0.85, 0.86), 'teeth_up': (0.9, 0.88, 0.8), 'teeth_lo': (0.9, 0.88, 0.8),
            'tongue': (0.62, 0.3, 0.32), 'caruncle': (0.75, 0.45, 0.47), 'p2_brows': (0.3, 0.24, 0.2)}
    for o in bpy.data.objects:
        if o.type != 'MESH': continue
        m = bpy.data.materials.new('g_' + o.name); m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value = (*cols.get(o.name, (0.55, 0.55, 0.57)), 1)
        bs.inputs['Roughness'].default_value = 0.2 if o.name == 'eyes' else 0.55
        o.data.materials.clear(); o.data.materials.append(m)
        if o.name == 'eyes':                                     # painted iris + pupil so the gaze reads in grey renders
            X = np.array([tuple(v.co) for v in o.data.vertices]); col = np.ones((len(X), 4), np.float32)
            Cs = {sd: v[2] for sd, v in IRIS.items()} if len(IRIS) == 2 else {'L': X[X[:, 0] > 0].mean(0), 'R': X[X[:, 0] < 0].mean(0)}
            near = np.array(list(Cs))[np.argmin(np.stack([np.linalg.norm(X - c, axis=1) for c in Cs.values()]), axis=0)]
            for sd in Cs:
                sel = near == sd
                if not sel.any(): continue
                C = Cs[sd]; g = IRIS.get(sd, (np.array([0, -1.0, 0]), 22.0, C))
                ang = np.degrees(np.arccos(np.clip(((X[sel] - C) / np.linalg.norm(X[sel] - C, axis=1)[:, None]) @ g[0], -1, 1)))
                c = np.tile([0.86, 0.86, 0.87, 1], (sel.sum(), 1)); c[ang < g[1]] = [0.32, 0.22, 0.14, 1]; c[ang < 0.42 * g[1]] = [0.03, 0.03, 0.03, 1]
                col[sel] = c
            at = o.data.color_attributes.new('irisc', 'FLOAT_COLOR', 'POINT'); at.data.foreach_set('color', col.ravel())
            nt = m.node_tree; an = nt.nodes.new('ShaderNodeAttribute'); an.attribute_name = 'irisc'
            nt.links.new(an.outputs['Color'], bs.inputs['Base Color'])
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]; cz = (top + LT[24][2]) / 2 - 0.02 * fh
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
d, size = {'face': ((0, -1, 0), 1.18 * fh), '34': ((0.7, -0.7, 0), 1.3 * fh)}[VIEW]; cz += 0.04 * fh
from mathutils import Vector
look_at = Vector((0.0, float(np.mean([LT[k][1] for k in LT])), cz)); dv = Vector(d).normalized()
co.location = look_at + dv * 1.0                                 # faces look toward -y: camera 1 m out along the view direction
co.rotation_euler = (look_at - co.location).to_track_quat('-Z', 'Y').to_euler(); cam.ortho_scale = size; cam.clip_end = 10
# ---- render: MP4 + sheet
sc.render.image_settings.file_format = 'FFMPEG'; sc.render.ffmpeg.format = 'MPEG4'; sc.render.ffmpeg.codec = 'H264'
sc.render.ffmpeg.constant_rate_factor = 'MEDIUM'; MP4 = sc.render.filepath = os.path.join(OUT, f'anim_{VIEW}.mp4')
bpy.ops.render.render(animation=True)
sc.render.image_settings.file_format = 'PNG'
fr = np.linspace(1, NF, 12).round().astype(int); tiles = []
for i, f in enumerate(fr):
    sc.frame_set(int(f)); p = os.path.join(OUT, f'_f{i:02d}.png'); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
im = [bpy.data.images.load(p) for p in tiles]; W = RES // 2
sheet = bpy.data.images.new('sheet', W * 6, W * 2); px = np.zeros((W * 2, W * 6, 4), np.float32)
for i, img in enumerate(im):
    a_ = np.array(img.pixels[:], np.float32).reshape(RES, RES, 4)[::2, ::2]
    r, c = 1 - i // 6, i % 6; px[r * W:(r + 1) * W, c * W:(c + 1) * W] = a_
sheet.pixels = px.ravel(); sheet.filepath_raw = os.path.join(OUT, f'anim_{VIEW}_sheet.png'); sheet.file_format = 'PNG'; sheet.save()
for p in tiles: os.remove(p)
print('ANIM', json.dumps({'frames': NF, 'view': VIEW, 'missing_keys': missing, 'mp4': MP4}))
