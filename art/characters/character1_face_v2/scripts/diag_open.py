import bpy, bmesh, json, numpy as np
from mathutils.kdtree import KDTree
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    nm = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
    bnd = [e for e in bm.edges if e.is_boundary]
    adj = {}
    for e in bnd:
        a, b = e.verts[0].index, e.verts[1].index; adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    seen, loops = set(), []
    for s in adj:
        if s in seen: continue
        st, comp = [s], []
        while st:
            v = st.pop()
            if v in seen: continue
            seen.add(v); comp.append(v); st += adj[v]
        P = np.array([bm.verts[i].co[:] for i in comp]); loops.append((len(comp), P.mean(0).round(3).tolist()))
    co = np.array([v.co[:] for v in bm.verts])
    kd = KDTree(len(co))
    for i, p in enumerate(co): kd.insert(p, i)
    kd.balance()
    mir = [kd.find((-p[0], p[1], p[2]))[2] for p in co[::5]]
    print("OBJ", o.name, "v", len(co), "nonmanifold", len(nm), "boundary loops", len(loops), sorted(loops, key=lambda t: -t[0])[:10], "mirror err mm mean %.2f p95 %.2f" % (np.mean(mir) * 1000, np.percentile(mir, 95) * 1000))
    bm.free()
