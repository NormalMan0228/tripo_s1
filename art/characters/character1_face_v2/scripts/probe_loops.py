import bpy, bmesh, sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from loop_tools import ring_around
ob = bpy.data.objects["TemplateHead"]; co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
F = json.load(open(sys.argv[sys.argv.index("--")+1]))
bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
for k in ("eye_L",):
    c = F[k]["center"]
    rings = ring_around(bm, co, c, max_r=0.04)
    print(k, "rings", len(rings))
    for r, lp in rings[:14]:
        P = co[lp]; print("  meanR %.4f n %d  ymin %.4f ymax %.4f" % (r, len(lp), P[:,1].min(), P[:,1].max()))
mc = [0.0, -0.10, F["mouth"]["lip_z"]]
rings = ring_around(bm, co, mc, max_r=0.05)
print("mouth rings", len(rings))
for r, lp in rings[:16]:
    P = co[lp]; print("  meanR %.4f n %d  ymin %.4f ymax %.4f zrange %.4f" % (r, len(lp), P[:,1].min(), P[:,1].max(), P[:,2].max()-P[:,2].min()))
