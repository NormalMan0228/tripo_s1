"""Renders for one LOD of the rigged head: wire close-up (density), rest, jaw_open, viseme_aa, blink 100 %.
Usage: blender -b <lod.blend | rig_mouth.blend> -P render_lod.py -- <lid_pose.json> <out_dir> <prefix>
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector, Quaternion
a = sys.argv[sys.argv.index('--') + 1:]
POSE, OUT, PFX = a[0], os.path.abspath(a[1]), a[2]
os.makedirs(OUT, exist_ok=True)
pose = json.load(open(POSE))
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 600
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
if not sc.world: sc.world = bpy.data.worlds.new('w')
cols = {'material': (0.86, 0.72, 0.64, 1), 'mouth_inner': (0.35, 0.08, 0.1, 1), 'teeth_up': (0.97, 0.96, 0.9, 1),
        'teeth_lo': (0.97, 0.96, 0.9, 1), 'tongue': (0.78, 0.35, 0.4, 1), 'eye_white': (0.95, 0.95, 0.95, 1), 'wire': (0.08, 0.1, 0.16, 1)}
def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.diffuse_color = cols[name]; return m
for n in list(cols): mat(n)
eyes = bpy.data.objects['eyes']; eyes.data.materials.clear(); eyes.data.materials.append(mat('eye_white'))
face = bpy.data.objects['face']
keys = face.data.shape_keys.key_blocks
H = np.array([tuple(face.matrix_world @ v.co) for v in face.data.vertices])
lo, hi = H.min(0), H.max(0); cz = hi[2] - (hi[2] - lo[2]) * 0.40; size = (hi[2] - lo[2]) * 0.62
# wire copy: no shape keys, wireframe replaces the surface; drawn just in front of the shaded face
w = face.copy(); w.data = face.data.copy(); w.name = 'face_wire'; sc.collection.objects.link(w)
w.shape_key_clear(); w.data.materials.clear(); w.data.materials.append(mat('wire'))
m = w.modifiers.new('wf', 'WIREFRAME'); m.thickness = 0.00022; m.use_replace = True; m.offset = 1
w.location.y -= 0.0002
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
lidR = bpy.data.objects['lid_R']; P = np.array([tuple(lidR.matrix_world @ v.co) for v in lidR.data.vertices]); ec = P.mean(0)
arm = bpy.data.objects['lid_rig']
def blink(t):
    for s, p in pose.items():
        for k, al in enumerate(p['alpha_b']):
            pb = arm.pose.bones['lid_%s_%d' % (s, k)]; pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Quaternion((0, 1, 0), -al * t * p['sign'])
    bpy.context.view_layer.update()
def setkey(name):
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks: kb.value = 1.0 if kb.name == name else 0.0
def shot(tag, d, s_, c, wire=False):
    w.hide_render = not wire
    d = Vector(d).normalized(); co.location = Vector(c) + d * 2; cam.ortho_scale = s_
    co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, f'{PFX}_{tag}.png'); bpy.ops.render.render(write_still=True)
front = ((0, -1, 0), size, (0, 0, cz))
setkey(None); blink(0)
# close-up: right eye down to the mouth corner, where density matters
shot('wire', (0, -1, 0), size * 0.42, (ec[0] * 0.55, 0, ec[2] - size * 0.12), wire=True)
shot('rest', *front)
setkey('jaw_open'); shot('jaw', *front)
setkey('viseme_aa'); shot('aa', *front)
setkey(None); blink(1.0); shot('blink', *front); blink(0)
print('RENDERED', PFX)
