"""Render a mesh with selected vertex rings highlighted (red points via a vertex colour attribute) and wireframe.
Usage: blender --background X.blend --python show_rings.py -- <object> <features.json> <out_prefix> [keys...]"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
obn, feats, pre = a[0], json.load(open(a[1])), os.path.abspath(a[2])
keys = a[3:] or ["eye_L", "eye_R", "mouth"]
ob = bpy.data.objects[obn]
sc = bpy.context.scene
for o in sc.objects:
    if o.type == 'MESH' and o is not ob:
        o.hide_render = True
me = ob.data
col = me.color_attributes.new("ring_dbg", 'FLOAT_COLOR', 'POINT')
for i in range(len(me.vertices)):
    col.data[i].color = (0.75, 0.72, 0.7, 1)
palette = [(1, 0.1, 0.1, 1), (0.1, 0.4, 1, 1), (0.1, 0.8, 0.2, 1), (1, 0.8, 0.1, 1)]
for k, c in zip(keys, palette):
    for v in feats[k]["ring"]:
        col.data[v].color = c
me.color_attributes.active_color = col
wm = ob.modifiers.new("wf", 'WIREFRAME'); wm.thickness = float(os.environ.get("WIRE", 0.0004)); wm.use_replace = False
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 900
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'VERTEX'
co = np.array([ob.matrix_world @ v.co for v in me.vertices])
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
views = json.loads(os.environ.get("VIEWS", "null")) or {
    "eye": [feats["eye_L"]["ring_centroid"], [0.25, -1, 0], 0.07],
    "mouth": [feats["mouth"]["ring_centroid"], [0.2, -1, 0.1], 0.09],
    "mouthsec": [feats["mouth"]["ring_centroid"], [1, -0.2, 0], 0.1]}
for name, (t, d, s) in views.items():
    dv = Vector(d).normalized(); cd.ortho_scale = s
    cam.location = Vector(t) + dv * 1.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{pre}_{name}.png"; bpy.ops.render.render(write_still=True)
