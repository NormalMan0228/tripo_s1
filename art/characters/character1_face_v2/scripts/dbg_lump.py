import bpy, json, numpy as np
w = bpy.data.objects["WrapHead"]; t = bpy.data.objects["TemplateHead"]
C = json.loads(w["vertex_classes"]); bag = set(C["bag"]); sock = set(C["socket"])
X = np.array([v.co[:] for v in w.data.vertices]); T0 = np.array([t.matrix_world @ v.co for v in t.data.vertices])
# lump: in front of chin, below the lip seam, abs x small
sel = np.where((np.abs(X[:,0]) < 0.06) & (X[:,2] > 0.36) & (X[:,2] < 0.43) & (X[:,1] < -0.20))[0]
print("lump candidates", len(sel), "in bag", sum(i in bag for i in sel), "in socket", sum(i in sock for i in sel))
print("template pos of those (y range, z range):", T0[sel,1].min().round(3), T0[sel,1].max().round(3), T0[sel,2].min().round(3), T0[sel,2].max().round(3))
print("bag template y range", T0[list(bag),1].min().round(3), T0[list(bag),1].max().round(3), "z", T0[list(bag),2].min().round(3), T0[list(bag),2].max().round(3))
print("wrapped bag y range", X[list(bag),1].min().round(3), X[list(bag),1].max().round(3), "z", X[list(bag),2].min().round(3), X[list(bag),2].max().round(3))
