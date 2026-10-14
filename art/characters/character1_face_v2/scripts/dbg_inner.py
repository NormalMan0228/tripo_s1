import bpy, json, numpy as np
w = bpy.data.objects["WrapHead"]; C = json.loads(w["vertex_classes"])
X = np.array([v.co[:] for v in w.data.vertices])
for k in ("bag", "socket", "pinned"):
    P = X[C[k]]; print(k, len(P), P.min(0).round(3), P.max(0).round(3))
far = np.where((np.abs(X[:, 0]) > 0.35) | (X[:, 1] < -0.4))[0]
print("far verts", len(far), far[:20], "in bag", len(set(far) & set(C["bag"])))
