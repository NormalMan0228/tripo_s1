"""Front / right / back / left renders of a model (grey clay, cavity), for review sheets.

  blender -b --factory-startup -P tools/body_gen/render_turn.py -- model.(fbx|glb) out_prefix [size]

Writes out_prefix_front.png, _right.png, _back.png, _left.png. The model is assumed to face -Y
(Blender's front view), as Tripo exports and the game GLBs do.
"""
import math
import sys

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
size = int(a[2]) if len(a) > 2 else 900
bpy.ops.wm.read_factory_settings(use_empty=True)
if src.lower().endswith('.fbx'):
    bpy.ops.import_scene.fbx(filepath=src)
else:
    bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
meshes = [o for o in sc.objects if o.type == 'MESH']
pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c = (lo + hi) / 2
H = max(hi - lo)
cam_data = bpy.data.cameras.new('cam')
cam_data.type = 'ORTHO'
cam_data.ortho_scale = 1.08 * H
cam_data.clip_end = 20 * H
cam = bpy.data.objects.new('cam', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'SINGLE'
sh.single_color = (0.78, 0.78, 0.76)
sh.show_cavity = True
sc.render.resolution_x = sc.render.resolution_y = size
w = bpy.data.worlds.new('w')
w.color = (0.93, 0.93, 0.94)
sc.world = w
sh.background_type = 'WORLD'
for name, d in (('front', (0, -1, 0)), ('right', (1, 0, 0)), ('back', (0, 1, 0)), ('left', (-1, 0, 0))):
    d = Vector(d)
    cam.location = c + d * 4 * H
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = '%s_%s.png' % (out, name)
    bpy.ops.render.render(write_still=True)
print('TURN', out, round(hi.z - lo.z, 3))
