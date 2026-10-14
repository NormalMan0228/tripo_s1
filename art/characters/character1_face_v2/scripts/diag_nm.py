import bpy, bmesh, numpy as np
o = bpy.data.objects["Body"]; bm = bmesh.new(); bm.from_mesh(o.data)
nm = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
P = np.array([((e.verts[0].co + e.verts[1].co) / 2)[:] for e in nm]); print("NM edges", len(nm)); print(np.round(P, 3)[:40].tolist())
bmesh.ops.split_edges(bm, edges=nm)
bm.verts.ensure_lookup_table()
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
for k, vs in sorted(g.items(), key=lambda t: -len(t[1]))[:15]:
    print("comp", len(vs), co[vs].mean(0).round(3).tolist(), co[vs].min(0).round(3).tolist(), co[vs].max(0).round(3).tolist())
