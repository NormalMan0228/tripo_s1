"""Measure the same anatomical landmarks on two heads (template and target) with identical front-ray rules.

Landmarks (character left = +X): subnasale, alar_L/R, ear_top_L/R, ear_low_L/R, ear_back_L/R, ear_front_L/R.
Usage: blender --background template_head.blend --python head_landmarks.py -- <template_features.json> <target.blend> <target_features.json> <out.json>
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
TF = json.load(open(a[0])); TGT = a[1]; GF = json.load(open(a[2])); OUT = os.path.abspath(a[3])


def mesh_np(ob):
    return np.array([ob.matrix_world @ v.co for v in ob.data.vertices]), [tuple(p.vertices) for p in ob.data.polygons]


tob = bpy.data.objects["TemplateHead"]
with bpy.data.libraries.load(TGT, link=False) as (df, dt):
    dt.objects = ["Body"]
gob = dt.objects[0]; bpy.context.scene.collection.objects.link(gob)


def measure(co, polys, nose_tip, seam_z, eye_c, label):
    T = BVHTree.FromPolygons([tuple(p) for p in co], polys)
    def front(x, z):
        h = T.ray_cast(Vector((x, -5, z)), Vector((0, 1, 0)), 10)
        return None if h[0] is None else np.array(h[0])
    out = {}
    # subnasale: deepest midline point between nose tip and lip seam
    zs = np.linspace(nose_tip[2], seam_z, 60)[1:-1]
    pts = [front(0.0, z) for z in zs]
    pts = [p for p in pts if p is not None]
    out["subnasale"] = max(pts, key=lambda p: p[1]).tolist()
    # alar: at the height just above subnasale, scanning outward: the nose ends where depth jumps backward
    z_al = out["subnasale"][2] + 0.25 * (nose_tip[2] - out["subnasale"][2])
    half_w = abs(eye_c[0])
    for sx, k in ((1, "alar_L"), (-1, "alar_R")):
        prev = None; best = None; best_jump = 0
        for x in np.linspace(0, half_w * 1.1, 120):
            p = front(sx * x, z_al)
            if p is None: continue
            if prev is not None and p[1] - prev[1] > best_jump:
                best_jump = p[1] - prev[1]; best = prev
            prev = p
        out[k] = best.tolist()
    # ears: region beyond the side of the head at eye..mouth height
    eye_z = eye_c[2]
    for sx, s in ((1, "L"), (-1, "R")):
        side = co[(sx * co[:, 0] > 0)]
        band = side[(side[:, 2] > seam_z - 0.1 * abs(eye_z - seam_z)) & (side[:, 2] < eye_z + 0.8 * abs(eye_z - seam_z))]
        xmax = np.abs(band[:, 0]).max()
        ear = band[np.abs(band[:, 0]) > xmax - 0.32 * abs(eye_c[0])]
        out[f"ear_top_{s}"] = ear[np.argmax(ear[:, 2])].tolist()
        out[f"ear_low_{s}"] = ear[np.argmin(ear[:, 2])].tolist()
        out[f"ear_back_{s}"] = ear[np.argmax(ear[:, 1])].tolist()
        out[f"ear_front_{s}"] = ear[np.argmin(ear[:, 1])].tolist()
        out[f"ear_out_{s}"] = ear[np.argmax(np.abs(ear[:, 0]))].tolist()
    print(label, {k: np.round(v, 3).tolist() for k, v in out.items()})
    return out


tco, tp = mesh_np(tob)
t_nose = tco[TF["nose_tip"]]
t_eye = np.array(TF["eye_L"]["center"])
res = {"template": measure(tco, tp, t_nose, TF["mouth"]["lip_z"], t_eye, "T"),
       "target": measure(*mesh_np(gob), np.array(GF["nose_tip"]), float(np.mean([p[2] for p in GF["lip_line"]])), np.array(GF["eye_L"]["center"]), "G")}
json.dump(res, open(OUT, "w"), indent=1)
