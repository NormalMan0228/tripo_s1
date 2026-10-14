"""Target ear region by thickness: side-of-head vertices whose inward normal ray exits the mesh within EAR_T.
(Tripo segmentation of this head did not register to the P2 surface within 13 mm, so it is not used for ears.)
Writes target_ears.json {"L": verts idx, "R": ..., "landmarks": {...}}.
Usage: blender --background target.blend --python target_ears.py -- <out.json>
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
EAR_T = float(os.environ.get("EAR_T", 0.022))
body = bpy.data.objects["Body"]
co = np.array([body.matrix_world @ v.co for v in body.data.vertices])
N = np.array([v.normal[:] for v in body.data.vertices])
T = BVHTree.FromPolygons([tuple(p) for p in co], [tuple(p.vertices) for p in body.data.polygons])
thin = np.zeros(len(co), bool)
for i in np.where((np.abs(co[:, 0]) > 0.2) & (co[:, 2] > 0.45) & (co[:, 2] < 0.75) & (co[:, 1] > -0.1))[0]:
    h = T.ray_cast(Vector(co[i]) - Vector(N[i]) * 1e-4, Vector(-N[i]), EAR_T)
    if h[0] is not None:
        thin[i] = True
adj = [[] for _ in co]
for e in body.data.edges:
    a, b = e.vertices; adj[a].append(b); adj[b].append(a)
X_ROOT = float(os.environ.get("EAR_XROOT", 0.245))
R = co[thin]
region = (np.abs(co[:, 0]) > X_ROOT) & (co[:, 2] > R[:, 2].min() - 0.05) & (co[:, 2] < R[:, 2].max() + 0.015)     & (co[:, 1] > R[:, 1].min() - 0.06) & (co[:, 1] < R[:, 1].max() + 0.02)
grow = thin.copy(); st = list(np.where(thin)[0])
while st:
    v = st.pop()
    for w in adj[v]:
        if not grow[w] and region[w]:
            grow[w] = True; st.append(w)
res = {}
for s, sx in (("L", 1), ("R", -1)):
    cand = set(np.where(grow & (sx * co[:, 0] > 0))[0].tolist())
    best, seen = [], set()
    for s0 in cand:
        if s0 in seen: continue
        comp, st = [], [s0]
        while st:
            v = st.pop()
            if v in seen or v not in cand: continue
            seen.add(v); comp.append(v); st += adj[v]
        if len(comp) > len(best): best = comp
    res[s] = sorted(best)
    P = co[best]
    print("ear", s, len(best), P.min(0).round(3), P.max(0).round(3))
lm = {}
for s in ("L", "R"):
    P = co[res[s]]
    lm[f"ear_top_{s}"] = P[np.argmax(P[:, 2])].tolist(); lm[f"ear_low_{s}"] = P[np.argmin(P[:, 2])].tolist()
    lm[f"ear_back_{s}"] = P[np.argmax(P[:, 1])].tolist(); lm[f"ear_front_{s}"] = P[np.argmin(P[:, 1])].tolist()
    lm[f"ear_out_{s}"] = P[np.argmax(np.abs(P[:, 0]))].tolist()
res["landmarks"] = lm
json.dump(res, open(OUT, "w"))
