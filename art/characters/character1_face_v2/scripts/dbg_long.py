import bpy, json, numpy as np
w = bpy.data.objects["WrapHead"]; C = json.loads(w["vertex_classes"])
X = np.array([v.co[:] for v in w.data.vertices])
E = np.array([e.vertices[:] for e in w.data.edges])
L = np.linalg.norm(X[E[:, 0]] - X[E[:, 1]], axis=1)
o = np.argsort(-L)[:12]
cls = {}
for k in ("bag", "socket", "pinned"):
    for i in C[k]: cls[i] = k
for j in o:
    a, b = E[j]; print(round(float(L[j]), 3), a, b, cls.get(a, "surf"), cls.get(b, "surf"), X[a].round(3), X[b].round(3))
