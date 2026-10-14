import bpy, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
w = bpy.data.objects["WrapHead"]; b = bpy.data.objects["Body"]
X = np.array([v.co[:] for v in w.data.vertices])
gco = [b.matrix_world @ v.co for v in b.data.vertices]
T = BVHTree.FromPolygons(gco, [tuple(p.vertices) for p in b.data.polygons])
# faces of the wrap whose centre is in front of the target surface by > 2 mm (front ray)
bad = []
for p in w.data.polygons:
    c = np.mean([X[i] for i in p.vertices], axis=0)
    h = T.ray_cast(Vector((c[0], -1, c[2])), Vector((0, 1, 0)), 2.0)
    if h[0] is not None and c[1] < h[0].y - 0.002:
        bad.append(p.index)
print("faces in front of target by >2mm:", len(bad))
vs = sorted({i for f in bad for i in w.data.polygons[f].vertices})
if vs:
    P = X[vs]; print("bbox", P.min(0).round(3), P.max(0).round(3))
    d = [T.find_nearest(Vector(X[i]))[3] for i in vs]
    print("their verts dist to target: max", round(max(d), 4), "mean", round(float(np.mean(d)), 4))
