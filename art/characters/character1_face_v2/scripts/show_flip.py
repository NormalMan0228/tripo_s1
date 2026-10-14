import bpy, json, os, sys, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
pre = os.path.abspath(sys.argv[sys.argv.index("--")+1])
w = bpy.data.objects["WrapHead"]; b = bpy.data.objects["Body"]; me = w.data
C = json.loads(w["vertex_classes"]); inner = set(C["socket"]) | set(C["bag"])
T = BVHTree.FromPolygons([b.matrix_world @ v.co for v in b.data.vertices], [tuple(p.vertices) for p in b.data.polygons])
X = np.array([v.co[:] for v in me.vertices])
red = bpy.data.materials.new("red"); red.diffuse_color = (1, 0, 0, 1)
gry = bpy.data.materials.new("gry"); gry.diffuse_color = (0.8, 0.78, 0.76, 1)
blu = bpy.data.materials.new("blu"); blu.diffuse_color = (0.3, 0.5, 1, 1)
me.materials.clear(); me.materials.append(gry); me.materials.append(red); me.materials.append(blu)
for p in me.polygons:
    vs = list(p.vertices)
    if any(v in inner for v in vs): p.material_index = 2; continue
    P = X[vs]; cen = P.mean(0); nrm = np.cross(P[1] - P[0], P[2] - P[0])
    loc, tn, idx, d = T.find_nearest(Vector(cen))
    p.material_index = 1 if np.dot(nrm, np.array(tn)) < 0 else 0
if me.shape_keys:
    for kb in me.shape_keys.key_blocks[1:]: kb.value = 0
sc = bpy.context.scene
for o in sc.objects: o.hide_render = o is not w
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 700
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
wm = w.modifiers.new("wf", "WIREFRAME"); wm.thickness = 0.0005; wm.use_replace = False; wm.use_even_offset = False; wm.material_offset = 0
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
for name, (t, d, s) in {"eyeL": ((0.11, -0.2, 0.63), (0.2, -1, 0.05), 0.24), "eyeLside": ((0.11, -0.15, 0.63), (0.9, -0.4, 0.1), 0.26), "mouth": ((0, -0.2, 0.46), (0.3, -1, 0.1), 0.3)}.items():
    dv = Vector(d).normalized(); cd.ortho_scale = s
    cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{pre}_{name}.png"; bpy.ops.render.render(write_still=True)
