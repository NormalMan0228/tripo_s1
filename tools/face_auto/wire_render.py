"""Wireframe-on-shaded renders: fitted template next to the target. Usage: blender -b fit.blend -P wire_render.py -- <out_png_prefix>"""
import bpy, sys, os
from mathutils import Vector
import numpy as np
OUT = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 720
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'SINGLE'; sc.display.shading.single_color = (0.82, 0.74, 0.68)
if not sc.world: sc.world = bpy.data.worlds.new('w')
head = bpy.data.objects['head']
for o in bpy.data.objects:
    if o.type == 'MESH' and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0
H = np.array([tuple(head.matrix_world @ v.co) for v in head.data.vertices]); lo, hi = H.min(0), H.max(0)
cz = hi[2] - (hi[2] - lo[2]) * 0.42; size = (hi[2] - lo[2]) * 0.62
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.ortho_scale = size; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
co.location = Vector((0, -2, cz)); co.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
def shot(name, show):
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.hide_render = o.name not in show
            o.modifiers.clear() if False else None
    sc.render.filepath = OUT + name + '.png'; bpy.ops.render.render(write_still=True)
# wireframe via modifier on a copy so the shaded surface stays underneath
for nm in ('head', 'target'):
    o = bpy.data.objects.get(nm)
    if not o: continue
    w = o.copy(); w.data = o.data.copy(); w.name = nm + '_wire'; sc.collection.objects.link(w)
    if w.data.shape_keys:
        w.active_shape_key_index = 0
        for kb in list(w.data.shape_keys.key_blocks)[::-1]: w.shape_key_remove(kb)
    m = w.modifiers.new('wf', 'WIREFRAME'); m.thickness = 0.00035; m.use_replace = True
    w.color = (0.1, 0.1, 0.12, 1)
sc.display.shading.color_type = 'OBJECT'
for o in bpy.data.objects:
    if o.type == 'MESH' and not o.name.endswith('_wire'): o.color = (0.82, 0.74, 0.68, 1)
shot('fitted_wire', {'head', 'head_wire', 'eye_L', 'eye_R'})
shot('target_wire', {'target', 'target_wire'})
