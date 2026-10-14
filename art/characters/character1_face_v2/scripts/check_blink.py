import bpy, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
w = bpy.data.objects["WrapHead"]; F = json.load(open(bpy.path.abspath("//target_features.json")))
kb = w.data.shape_keys.key_blocks
def keyco(name): return np.array([v.co[:] for v in kb[name].data])
X0 = keyco("Basis")
for side, L in (("L", "Left"), ("R", "Right")):
    c = np.array(F[f"eye_{side}"]["center"]); R = F[f"eye_{side}"]["radius"]
    eye = bpy.data.objects[f"Eye.{side}"]
    ev = [eye.matrix_world @ v.co for v in eye.data.vertices]
    Te = BVHTree.FromPolygons(ev, [tuple(p.vertices) for p in eye.data.polygons])
    er = np.linalg.norm(np.array(ev) - c, axis=1); print(side, "eye mesh radius min/max", er.min().round(4), er.max().round(4), "R", round(R, 4))
    for nm in (f"eyeBlink{L}_50", f"eyeBlink{L}"):
        X = keyco(nm)
        moved = np.linalg.norm(X - X0, axis=1) > 1e-5
        r = np.linalg.norm(X[moved] - c, axis=1)
        front = (X[moved] - c)[:, 1] < 0
        Tw = BVHTree.FromPolygons([tuple(p) for p in X], [tuple(p.vertices) for p in w.data.polygons])
        vis = tot = 0
        for i in range(-30, 31):
            for j in range(-30, 31):
                o = Vector((c[0] + i * R / 30, -2, c[2] + j * R / 30))
                he = Te.ray_cast(o, Vector((0, 1, 0)), 5)
                if he[0] is None: continue
                tot += 1; hw = Tw.ray_cast(o, Vector((0, 1, 0)), 5)
                if hw[0] is None or hw[3] > he[3]: vis += 1
        print(" ", nm, "moved", int(moved.sum()), "front r<R:", int((r[front] < R).sum()), "eye visible", round(vis / tot, 3))
