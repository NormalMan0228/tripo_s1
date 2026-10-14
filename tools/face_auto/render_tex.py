"""EEVEE renders of a textured face asset for texture QA (same light / camera framing as m1 render_m1.py, any size).
views: face (front), 34 (three-quarter), eyes (front close-up of both eyes), eyeL (left eye close-up), mouth,
       side, back (from behind and above: back seam), under (from below: neck ring / chin).
combos: shape-key sums like 'rest', 'jawOpen', 'eyeBlinkLeft+eyeBlinkRight', 'eyeLookInLeft+eyeLookOutRight'.
Usage: blender -b <asset.blend> -P render_tex.py -- <out_dir> <landmarks.json> <view,view> <combo,combo> [--res 768]
Files: <out_dir>/<view>_<combo>.png
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0]); LMJ = a[1]; VIEWS = a[2].split(','); COMBOS = a[3].split(',')
RES = int(a[a.index('--res') + 1]) if '--res' in a else 768
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try: sc.render.engine = eng; break
    except TypeError: pass
sc.render.resolution_x = sc.render.resolution_y = RES; sc.view_settings.view_transform = 'Standard'
if not sc.world: sc.world = bpy.data.worlds.new('w')
sc.world.use_nodes = True; bgn = sc.world.node_tree.nodes['Background']; bgn.inputs[0].default_value = (0.62, 0.62, 0.64, 1); bgn.inputs[1].default_value = 0.55
sun = bpy.data.lights.new('sun_q', 'SUN'); sun.energy = 1.6; so = bpy.data.objects.new('sun_q', sun); sc.collection.objects.link(so); so.rotation_euler = (0.75, 0.25, -0.35)
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]; cz = (top + LT[24][2]) / 2 - 0.02 * fh
mz = (LT[20][2] + LT[22][2]) / 2; ez = (LT[8][2] + LT[12][2]) / 2
xL = (LT[11][0] + LT[13][0]) / 2 if abs(LT[13][0]) > 0 else 0.03
cam = bpy.data.cameras.new('cq'); cam.type = 'ORTHO'; co = bpy.data.objects.new('cq', cam); sc.collection.objects.link(co); sc.camera = co
SPEC = {'face': ((0, -1, 0), 1.75 * fh, (0, cz)), '34': ((0.7, -0.7, 0), 1.9 * fh, (0, cz)),
        'eyes': ((0, -1, 0), 0.75 * fh, (0, ez)), 'eyeL': ((0, -1, 0), 0.32 * fh, (xL, ez)),
        'mouth': ((0, -1, 0), 0.62 * fh, (0, mz - 0.05 * fh)), 'side': ((1, 0, 0), 1.9 * fh, (0, cz)),
        'back': ((0.25, 1, 0.35), 2.0 * fh, (0, cz)), 'under': ((0.3, -0.6, -0.75), 1.9 * fh, (0, cz))}
for view in VIEWS:
    d, size, (xc, zc) = SPEC[view]
    d = Vector(d).normalized(); co.location = Vector((xc, 0, zc)) + d * 2; cam.ortho_scale = size
    co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    for combo in COMBOS:
        vals = {}
        for part in combo.split('+'):
            k, _, v = part.partition(':'); vals[k] = float(v) if v else 1.0
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.data.shape_keys:
                for kb in o.data.shape_keys.key_blocks: kb.value = vals.get(kb.name, 0.0)
        bpy.context.view_layer.update()
        sc.render.filepath = os.path.join(OUT, f'{view}_{combo.replace("+", "_").replace(":", "")}.png')
        bpy.ops.render.render(write_still=True)
print('RENDERED', len(VIEWS) * len(COMBOS))
