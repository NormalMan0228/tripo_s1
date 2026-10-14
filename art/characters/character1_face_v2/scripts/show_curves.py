"""Overlay feature polylines (from a features json) on a render. Usage:
blender --background X.blend --python show_curves.py -- <features.json> <out_prefix> <key[,key...]> [views]"""
import bpy, sys, os, json
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
F = json.load(open(a[0])); pre = os.path.abspath(a[1]); keys = a[2].split(","); views = a[3].split(",") if len(a) > 3 else ["front", "eyeL", "mouth"]
sc = bpy.context.scene
cols = [(1, 0.1, 0.1, 1), (0.1, 0.5, 1, 1), (0.1, 0.9, 0.2, 1), (1, 0.8, 0.1, 1), (0.9, 0.2, 0.9, 1)]
for k, col in zip(keys, cols):
    v = F
    for part in k.split("."):
        v = v[part]
    pts = v if isinstance(v[0], (list, tuple)) else [v]
    cu = bpy.data.curves.new(k, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.0012
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1] - 0.002, p[2], 1)
    if len(pts) == 1:
        cu.bevel_depth = 0.004; sp.points.add(1); sp.points[1].co = (pts[0][0] + 1e-4, pts[0][1] - 0.002, pts[0][2], 1)
    ob = bpy.data.objects.new(k, cu); sc.collection.objects.link(ob)
    m = bpy.data.materials.new(k); m.diffuse_color = col; cu.materials.append(m)
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 800
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'
for o in sc.objects:
    if o.type == 'MESH':
        for s in o.material_slots:
            if s.material: s.material.diffuse_color = (0.8, 0.78, 0.76, 1)
CAMS = {"front": ((0, -0.2, 0.55), (0, -1, 0), 0.6), "eyeL": ((0.11, -0.2, 0.63), (0.15, -1, 0.05), 0.25),
        "mouth": ((0, -0.2, 0.45), (0.1, -1, 0), 0.3), "q34": ((0, -0.1, 0.55), (0.7, -0.7, 0.05), 0.7),
        "side": ((0, -0.1, 0.55), (1, 0, 0), 0.7)}
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
for name in views:
    t, d, s = CAMS[name]; dv = Vector(d).normalized(); cd.ortho_scale = s
    cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{pre}_{name}.png"; bpy.ops.render.render(write_still=True)
