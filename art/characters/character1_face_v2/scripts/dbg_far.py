import bpy, json, numpy as np
w = bpy.data.objects["WrapHead"]; t = bpy.data.objects["TemplateHead"]
X = np.array([v.co[:] for v in w.data.vertices]); T0 = np.array([t.matrix_world @ v.co for v in t.data.vertices])
far = np.where((np.abs(X[:, 0]) > 0.35) | (X[:, 1] < -0.4))[0]
print("template pos of far verts", T0[far].min(0).round(3), T0[far].max(0).round(3))
print("wrapped", X[far].min(0).round(3), X[far].max(0).round(3))
print("normals z of far (template):", np.round([t.data.vertices[i].normal.z for i in far[:10]], 2))
