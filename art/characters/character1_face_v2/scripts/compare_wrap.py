"""Side-by-side clay renders of target vs wrap + deviation heat map (wrap verts -> target surface, mm).
Usage: blender --background wrapped_X.blend --python compare_wrap.py -- <out_prefix>"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
pre = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
sc = bpy.context.scene
w = bpy.data.objects["WrapHead"]; b = bpy.data.objects["Body"]
eyes = [bpy.data.objects["Eye.L"], bpy.data.objects["Eye.R"]]
C = json.loads(w["vertex_classes"]); inner = set(C["socket"]) | set(C["bag"])
gco = [b.matrix_world @ v.co for v in b.data.vertices]
T = BVHTree.FromPolygons(gco, [tuple(p.vertices) for p in b.data.polygons])
X = np.array([v.co[:] for v in w.data.vertices])
d = np.array([T.find_nearest(Vector(p))[3] for p in X]) * 1000
d[list(inner)] = 0
col = w.data.color_attributes.new("dev", 'FLOAT_COLOR', 'POINT')
for i, v in enumerate(d):
    t = min(v / 2.0, 1.0)                     # 0 mm green -> 2 mm+ red
    col.data[i].color = (t, 1 - t, 0.15, 1)
w.data.color_attributes.active_color = col
surf = np.array([i not in inner for i in range(len(X))])
print("DEV mm mean %.3f p95 %.3f max %.3f" % (d[surf].mean(), np.percentile(d[surf], 95), d[surf].max()))
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 700
sh = sc.display.shading; sh.light = 'STUDIO'
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
V = {"front": ((0, -0.2, 0.55), (0, -1, 0), 0.7), "q34": ((0, -0.1, 0.55), (0.7, -0.7, 0.05), 0.8),
     "eye": ((0.11, -0.2, 0.63), (0.2, -1, 0.05), 0.25), "mouth": ((0, -0.2, 0.45), (0.25, -1, 0), 0.25)}
for mode in ("tgt", "wrap", "dev"):
    for o in sc.objects:
        if o.type == 'MESH':
            o.hide_render = not ((mode == "tgt" and (o is b or o in eyes)) or (mode != "tgt" and (o is w or o in eyes)))
    sh.color_type = 'VERTEX' if mode == "dev" else 'SINGLE'; sh.single_color = (0.8, 0.78, 0.76)
    for name, (t, dd, s) in V.items():
        dv = Vector(dd).normalized(); cd.ortho_scale = s
        cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = f"{pre}_{mode}_{name}.png"; bpy.ops.render.render(write_still=True)
