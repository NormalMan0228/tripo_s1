"""Build refs_source.blend: character1 neutral head prepared for brow/lash-free Tripo reference renders.

From character1_face_v1/04_rig.blend: brow-free skin texture, no normal map on the skin, skin geometry under the
brows relaxed (Tripo carved a brow relief into the skin), shape keys removed, hair cards / lids hidden.
Usage: blender --background 04_rig.blend --python make_ref_source.py -- <skin_tex.png> <out.blend>
"""
import bpy, bmesh, sys, os
import numpy as np
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index("--") + 1:]
tex, out = os.path.abspath(a[0]), os.path.abspath(a[1])
skin = bpy.data.objects["Skin"]
mat = skin.data.materials[0]
for nd in mat.node_tree.nodes:
    if nd.type == 'TEX_IMAGE' and nd.image and "basecolor" in nd.image.name:
        nd.image = bpy.data.images.load(tex)
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
for l in list(bsdf.inputs["Normal"].links):
    mat.node_tree.links.remove(l)

skin.shape_key_clear()
co = np.array([v.co[:] for v in skin.data.vertices])
brow = []
for n in ("Brow.L", "Brow.R"):
    ob = bpy.data.objects[n]
    brow += [tuple(ob.matrix_world @ v.co) for v in ob.data.vertices]
brow = np.array(brow)
kd = KDTree(len(brow))
for i, p in enumerate(brow):
    kd.insert(p, i)
kd.balance()
d = np.array([kd.find(p)[2] for p in co])
# fill the small Tripo holes first (refs only), then membrane-smooth the brow recess with a fixed rim
bm = bmesh.new(); bm.from_mesh(skin.data)
edges = [e for e in bm.edges if e.is_boundary]
loops_small = bmesh.ops.holes_fill(bm, edges=edges, sides=10)
bm.to_mesh(skin.data); bm.free()
co = np.array([v.co[:] for v in skin.data.vertices])
d = np.array([kd.find(p)[2] for p in co])
free = d < float(os.environ.get("BROW_R", 0.010))
bm = bmesh.new(); bm.from_mesh(skin.data); bm.verts.ensure_lookup_table()
nb = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
bm.free()
cur = co.copy()
for _ in range(int(os.environ.get('RELAX_ITERS', 300))):
    avg = np.array([cur[n].mean(0) if n else cur[i] for i, n in enumerate(nb)])
    cur[free] = avg[free]
print("relaxed verts", int(free.sum()), "max move", float(np.linalg.norm(cur - co, axis=1).max()))
for v, p in zip(skin.data.vertices, cur):
    v.co = p
skin.data.update()
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name not in ("Skin", "Eye.L", "Eye.R", "Ear.L", "Ear.R"):
        o.hide_render = True; o.hide_viewport = True
bpy.ops.wm.save_as_mainfile(filepath=out)
