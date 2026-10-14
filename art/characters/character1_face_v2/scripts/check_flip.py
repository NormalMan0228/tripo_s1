import bpy, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
w = bpy.data.objects["WrapHead"]; b = bpy.data.objects["Body"]; me = w.data
C = json.loads(w["vertex_classes"]); inner = set(C["socket"]) | set(C["bag"])
T = BVHTree.FromPolygons([b.matrix_world @ v.co for v in b.data.vertices], [tuple(p.vertices) for p in b.data.polygons])
X = np.array([v.co[:] for v in me.shape_keys.key_blocks["Basis"].data])
flip = []; tot = 0
for p in me.polygons:
    vs = list(p.vertices)
    if any(v in inner for v in vs): continue
    P = X[vs]; cen = P.mean(0); nrm = np.cross(P[1] - P[0], P[2] - P[0]); nrm /= np.linalg.norm(nrm) + 1e-12
    loc, tn, idx, d = T.find_nearest(Vector(cen))
    tot += 1
    if np.dot(nrm, np.array(tn)) < 0: flip.append(p.index)
print("surface faces", tot, "flipped vs target", len(flip))
if flip:
    cen = np.array([X[list(me.polygons[f].vertices)].mean(0) for f in flip])
    for lab, m in (("eyeL", np.linalg.norm(cen - np.array([0.115, -0.13, 0.63]), axis=1) < 0.12), ("eyeR", np.linalg.norm(cen - np.array([-0.115, -0.13, 0.63]), axis=1) < 0.12), ("mouth", np.linalg.norm(cen - np.array([0, -0.25, 0.45]), axis=1) < 0.1)):
        print(" ", lab, int(m.sum()))
