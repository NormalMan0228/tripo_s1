import bpy, json, numpy as np
w = bpy.data.objects["WrapHead"]; seam = list(w["lip_seam"]); X = np.array([v.co[:] for v in w.data.vertices])
print("seam bbox", X[seam].min(0).round(3), X[seam].max(0).round(3))
C = json.loads(w["vertex_classes"]); print("bag bbox", X[C["bag"]].min(0).round(3), X[C["bag"]].max(0).round(3))
for n in ("Teeth", "Tongue"):
    o = bpy.data.objects[n]; P = np.array([v.co[:] for v in o.data.vertices]); print(n, P.min(0).round(3), P.max(0).round(3))
