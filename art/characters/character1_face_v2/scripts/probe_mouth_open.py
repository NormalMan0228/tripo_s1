import bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
o = bpy.data.objects["Body"]; co = [v.co for v in o.data.vertices]
T = BVHTree.FromPolygons(co, [tuple(p.vertices) for p in o.data.polygons])
for x in (0.0, 0.03, 0.06, 0.08, 0.1):
    prev = None; out = []
    for z in np.arange(0.30, 0.52, 0.002):
        h = T.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)), 5)
        y = h[0].y if h[0] else None
        out.append((round(z, 3), None if y is None else round(y, 3)))
    deep = [z for z, y in out if y is not None and y > -0.17]
    print("x", x, "deep z range", (min(deep), max(deep)) if deep else None)
    if x == 0.0: print(out[::3])
ear = np.array([v.co[:] for v in o.data.vertices]); s = ear[(np.abs(ear[:,0]) > 0.26)]
print("ear z range", s[:,2].min().round(3), s[:,2].max().round(3), "y", s[:,1].min().round(3), s[:,1].max().round(3))
for n in ("TeethUpper","TeethLower","Tongue","MouthLower"):
    P = np.array([v.co[:] for v in bpy.data.objects[n].data.vertices]); print(n, P.min(0).round(3), P.max(0).round(3))
