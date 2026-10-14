import bpy, bmesh, sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from loop_tools import ring_around
o = bpy.data.objects["Body"]; co = np.array([v.co[:] for v in o.data.vertices])
bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
c = np.array(bpy.data.objects["Eye.L"].location)
rings = ring_around(bm, co, c, max_r=0.16)
print("eye center", c.round(3), "rings", len(rings))
for r, lp in rings[:20]:
    P = co[lp]; d = np.linalg.norm(P - c, axis=1)
    print("  meanR2d %.4f n %d  dist3d %.4f-%.4f ymin %.3f" % (r, len(lp), d.min(), d.max(), P[:,1].min()))
bnd = [v.index for v in bm.verts if v.is_boundary and np.linalg.norm(co[v.index]-c) < 0.13]
print("boundary verts near eye", len(bnd), "valences", np.bincount([len(bm.verts[i].link_edges) for i in bnd]))
mc = np.array([0, -0.2, 0.45]); mr = ring_around(bm, co, mc, axis_idx=(0, 2), max_r=0.12)
print("mouth rings", len(mr), [(round(r, 3), len(l)) for r, l in mr[:12]])
