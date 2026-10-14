import bpy, bmesh, numpy as np
o = bpy.data.objects["Body"]
for x in bpy.data.objects: x.select_set(x is o)
bpy.context.view_layer.objects.active = o
bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bm.to_mesh(o.data); bm.free()
co = np.array([v.co[:] for v in o.data.vertices]); print("before x range", co[:,0].min().round(3), co[:,0].max().round(3), len(co))
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
r = bpy.ops.mesh.symmetrize(direction='POSITIVE_X', threshold=0.0008); bpy.ops.object.mode_set(mode='OBJECT')
print("sym", r)
bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
par = list(range(len(bm.verts)))
def f(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for e in bm.edges:
    a, b = f(e.verts[0].index), f(e.verts[1].index)
    if a != b: par[a] = b
g = {}
for v in bm.verts: g.setdefault(f(v.index), []).append(v.index)
co = np.array([v.co[:] for v in bm.verts])
for vs in sorted(g.values(), key=len, reverse=True)[:6]: print("comp", len(vs), co[vs].min(0).round(3), co[vs].max(0).round(3))
