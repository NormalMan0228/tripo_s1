"""Renders for the eyelid-part rig: blink 0 / 50 / 100 %, natural (skin-coloured lids) and debug (blue lids).
Usage: blender -b <rig_lids.blend> -P render_lids.py -- <lid_pose.json> <out_dir> <prefix> [views=front,eye,34]
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector, Quaternion
a = sys.argv[sys.argv.index('--') + 1:]
POSE, OUT, PFX = a[0], a[1], a[2]
VIEWS = a[3].split(',') if len(a) > 3 else ['front', 'eye', '34']
os.makedirs(OUT, exist_ok=True)
pose = json.load(open(POSE))
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 560
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'OBJECT'
if not sc.world: sc.world = bpy.data.worlds.new('w')
skin = (0.86, 0.72, 0.64, 1)
col = {'face': skin, 'eyes': (0.95, 0.95, 0.95, 1), 'mouth_cavity': (0.35, 0.08, 0.1, 1)}
for o in bpy.data.objects:
    if o.type == 'MESH': o.color = col.get(o.name, skin)
face = bpy.data.objects['face']
if face.data.shape_keys:
    for k in face.data.shape_keys.key_blocks: k.value = 0
H = np.array([tuple(face.matrix_world @ v.co) for v in face.data.vertices])
lo, hi = H.min(0), H.max(0); cz = hi[2] - (hi[2] - lo[2]) * 0.40; size = (hi[2] - lo[2]) * 0.62
eyeC = np.mean([np.array(json.load(open(os.path.join(os.path.dirname(POSE), '..', 'rig_' + PFX, 'eyes_meta.json')))[s]['C'])
                for s in 'RL'], axis=0) if False else None
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
lidR = bpy.data.objects['lid_R']; P = np.array([tuple(lidR.matrix_world @ v.co) for v in lidR.data.vertices]); ec = P.mean(0)
views = {'front': ((0, -1, 0), size, (0, 0, cz)), '34': ((0.7, -0.7, 0.05), size, (0, 0, cz)), 'side': ((1, 0, 0), size, (0, (lo[1] + hi[1]) / 2, cz)),
         'eye': ((0.2, -1, 0.05), size * 0.36, (ec[0], 0, ec[2] - size * 0.03))}
arm = bpy.data.objects['lid_rig']
def blink(t):
    for s, p in pose.items():
        for k, al in enumerate(p['alpha_b']):
            pb = arm.pose.bones['lid_%s_%d' % (s, k)]; pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Quaternion((0, 1, 0), -al * t * p['sign'])
    bpy.context.view_layer.update()
for mode in ('skin', 'debug'):
    for n in ('lid_L', 'lid_R'): bpy.data.objects[n].color = skin if mode == 'skin' else (0.3, 0.5, 0.95, 1)
    for t in (0.0, 0.5, 1.0):
        blink(t)
        for v in VIEWS:
            d, s_, c = views[v]; d = Vector(d).normalized(); co.location = Vector(c) + d * 2; cam.ortho_scale = s_
            co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = os.path.join(OUT, f'{PFX}_{mode}_b{int(t*100)}_{v}.png'); bpy.ops.render.render(write_still=True)
blink(0.0)
print('RENDERED')
