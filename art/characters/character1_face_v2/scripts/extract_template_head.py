"""Extract the MakeHuman/MPFB template head-neck (skin only, helpers removed) with its shape keys.

Output template_head.blend with object TemplateHead: modifiers applied except armature/subsurf (none kept),
'body' vertex group only, cut below the clavicles, all 98 face shape keys kept, UVs kept.
Also writes template_landmarks.json: eye-hole loops, mouth loops, key vertex ids.
Usage: blender --background mpfb_template_face_test.blend --python extract_template_head.py -- <out_dir> [cut_z]
"""
import bpy, bmesh, sys, os, json
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(a[0]); cut_z = float(a[1]) if len(a) > 1 else 1.33
src = bpy.data.objects["Template_Face_Body"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "TemplateHead"; ob.data.name = "TemplateHead"
bpy.context.scene.collection.objects.link(ob)
ob.modifiers.clear(); ob.parent = None; ob.matrix_world = src.matrix_world.copy()
ob.animation_data_clear()
if ob.data.shape_keys:
    for kb in ob.data.shape_keys.key_blocks:
        kb.value = 0.0
    if ob.data.shape_keys.animation_data:
        ob.data.shape_keys.animation_data_clear()

gi = ob.vertex_groups["body"].index
keep = np.zeros(len(ob.data.vertices), bool)
for v in ob.data.vertices:
    for g in v.groups:
        if g.group == gi and g.weight > 0.5:
            keep[v.index] = True
co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
keep &= co[:, 2] > cut_z

bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep[v.index]], context='VERTS')
# drop dangling pieces (keep the largest connected component)
bm.verts.ensure_lookup_table()
parent = list(range(len(bm.verts)))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
for e in bm.edges:
    a1, b1 = find(e.verts[0].index), find(e.verts[1].index)
    if a1 != b1: parent[a1] = b1
roots = [find(v.index) for v in bm.verts]
big = max(set(roots), key=roots.count)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if roots[v.index] != big], context='VERTS')
bm.to_mesh(ob.data); bm.free()
for g in list(ob.vertex_groups):
    if not (g.name in ('ears', 'lips', 'scalp') or g.name.startswith('DEF-')):
        ob.vertex_groups.remove(g)
bpy.data.objects.remove(src)
for o in list(bpy.data.objects):
    if o is not ob:
        bpy.data.objects.remove(o)

# landmarks: boundary loops
me = ob.data
bm = bmesh.new(); bm.from_mesh(me)
adj = {}
for e in bm.edges:
    if e.is_boundary:
        u, w = e.verts[0].index, e.verts[1].index
        adj.setdefault(u, []).append(w); adj.setdefault(w, []).append(u)
bm.free()
co = np.array([ob.matrix_world @ v.co for v in me.vertices])
seen, loops = set(), []
for s in adj:
    if s in seen: continue
    order = [s]; seen.add(s); prev, cur = None, s
    while True:
        nxt = [w for w in adj[cur] if w != prev and w not in seen]
        if not nxt: break
        prev, cur = cur, nxt[0]; order.append(cur); seen.add(cur)
    loops.append(order)
info = []
for l in loops:
    c = co[l].mean(0)
    info.append(dict(n=len(l), centroid=c.round(4).tolist(), verts=l))
info.sort(key=lambda d: -d["n"])
for d in info:
    print("loop", d["n"], d["centroid"])
json.dump({"loops": info, "verts": len(me.vertices), "faces": len(me.polygons),
           "keys": [k.name for k in me.shape_keys.key_blocks] if me.shape_keys else []},
          open(os.path.join(out, "template_landmarks.json"), "w"))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "template_head.blend"))
print("TEMPLATE", len(me.vertices), len(me.polygons))
