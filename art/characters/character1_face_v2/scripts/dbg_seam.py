import bpy, numpy as np
w = bpy.data.objects["WrapHead"]; t = bpy.data.objects["TemplateHead"]
seam = list(w["lip_seam"]); X = np.array([v.co[:] for v in w.data.vertices]); T0 = np.array([t.matrix_world @ v.co for v in t.data.vertices])
for k, i in enumerate(seam):
    print(k, i, "tmpl x %.4f z %.4f" % (T0[i, 0], T0[i, 2]), "wrap x %.4f y %.4f z %.4f" % tuple(X[i]))
