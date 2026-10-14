"""Assemble the t2 face: wrapped face (lids rigged) + Tripo parts from open/closed.blend.

* mouth bag of the wrap reshaped to the Tripo oral cavity (projection onto cavity surface + relax, seam fixed)
* TeethUpper / TeethLower / Tongue / MouthLower copied in; lower parts get a 'jaw' group and jawOpen-family keys
  built by rotating about the jaw pivot by the angle the face key opens the chin
* Eye.L / Eye.R from the closed file (clean spheres)
* PART_* vertex groups on the face
Usage: blender --background t2/face_lids.blend --python assemble_t2.py -- <closed.blend> <out.blend>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], os.path.abspath(a[1])
rep = {}
w = bpy.data.objects["WrapHead"]; me = w.data
C = json.loads(w["vertex_classes"]); bag = np.array(C["bag"]); sock = set(C["socket"])
seam = list(w["lip_seam"])
KB = me.shape_keys.key_blocks; KEYS = [k.name for k in KB[1:]]
X = np.array([v.co[:] for v in KB[0].data]); n = len(X)
nbrs = [[] for _ in range(n)]
for e in me.edges:
    i, j = e.vertices; nbrs[i].append(j); nbrs[j].append(i)
for o in list(bpy.data.objects):
    if o.name in ("Body", "Eye.L", "Eye.R", "TemplateHead"): bpy.data.objects.remove(o)
with bpy.data.libraries.load(SRC, link=False) as (df, dt):
    dt.objects = ["Body", "TeethUpper", "TeethLower", "Tongue", "MouthLower", "Eye.L", "Eye.R"]
src = {o.name: o for o in dt.objects}
coll = w.users_collection[0]
for nm in ("TeethUpper", "TeethLower", "Tongue", "MouthLower", "Eye.L", "Eye.R"):
    coll.objects.link(src[nm])
tb = src["Body"]
pivot = np.array(tb["jaw_pivot"])
# ---- cavity surface: target body faces behind the lip seam + MouthLower
tco = np.array([tb.matrix_world @ v.co for v in tb.data.vertices])
seam_y = X[seam, 1].max()
cav_polys = [tuple(p.vertices) for p in tb.data.polygons if tco[list(p.vertices)].mean(0)[1] > seam_y + 0.004
             and abs(tco[list(p.vertices)].mean(0)[0]) < 0.13 and 0.30 < tco[list(p.vertices)].mean(0)[2] < 0.52]
ml = src["MouthLower"]; mco = np.array([ml.matrix_world @ v.co for v in ml.data.vertices])
verts = list(map(tuple, tco)) + list(map(tuple, mco)); off = len(tco)
cav_polys += [tuple(i + off for i in p.vertices) for p in ml.data.polygons]
CAV = BVHTree.FromPolygons(verts, cav_polys)
bag_set = set(bag.tolist())
ring = {v: 0 for v in seam}; fr = list(seam)
while fr:
    nx = []
    for v in fr:
        for u in nbrs[v]:
            if u in bag_set and u not in ring: ring[u] = ring[v] + 1; nx.append(u)
    fr = nx
B0 = X.copy()
for it in range(int(os.environ.get("CAV_IT", 30))):
    for i in bag:
        if ring.get(i, 99) == 0: continue
        loc = CAV.find_nearest(Vector(X[i]))[0]
        if loc is not None:
            t = min(1.0, ring.get(i, 99) / 2.0)            # first rings blend from the lips into the cavity
            X[i] = X[i] * (1 - 0.5 * t) + np.array(loc) * 0.5 * t
    for i in bag:
        if ring.get(i, 99) == 0: continue
        X[i] = 0.5 * X[i] + 0.5 * X[nbrs[i]].mean(0)
disp = X - B0
rep["bag_cavity_move_mm"] = float(np.linalg.norm(disp[bag], axis=1).max() * 1000)
for k in KB:
    P = np.array([v.co[:] for v in k.data]); P[bag] += disp[bag]; k.data.foreach_set("co", P.ravel())
me.vertices.foreach_set("co", np.array([v.co[:] for v in KB[0].data]).ravel())
# ---- jaw angle per key: rotation that best matches the chin motion of each face key
gi = w.vertex_groups.get("DEF-jaw")
chin = [i for i in range(n) if X[i, 2] < 0.41 and X[i, 1] < -0.2 and abs(X[i, 0]) < 0.04]
def fit_angle(P):
    d0 = X[chin] - pivot; d1 = P[chin] - pivot
    a0 = np.arctan2(d0[:, 2], -d0[:, 1]); a1 = np.arctan2(d1[:, 2], -d1[:, 1])
    return float(np.median(a1 - a0))
lower = ["TeethLower", "Tongue", "MouthLower"]
# lower dentition: open the jaw back until the lower teeth no longer intersect the upper teeth (+ small gap)
for nm in ("TeethUpper",) + tuple(lower) + ("Eye.L", "Eye.R"):
    o = src[nm]; o.data.transform(o.matrix_basis); o.matrix_basis = Matrix()
def bvh_of(o, P=None):
    P = np.array([v.co[:] for v in o.data.vertices]) if P is None else P
    return BVHTree.FromPolygons([tuple(p) for p in P], [tuple(p.vertices) for p in o.data.polygons])
TU = bvh_of(src["TeethUpper"]); PL = {nm: np.array([v.co[:] for v in src[nm].data.vertices]) for nm in lower}
def rotP(P, th):
    R = np.array(Matrix.Rotation(th, 3, 'X')); return (P - pivot) @ R.T + pivot
open_deg = 0.0
for dg in np.arange(0, 25.01, 0.5):
    P = rotP(PL["TeethLower"], math.radians(dg))
    if not TU.overlap(bvh_of(src["TeethLower"], P)):
        open_deg = dg + float(os.environ.get("TEETH_GAP_DEG", 1.0)); break
for nm in lower:
    src[nm].data.vertices.foreach_set("co", rotP(PL[nm], math.radians(open_deg)).ravel()); src[nm].data.update()
rep["teeth_reopen_deg"] = open_deg
for nm in ("TeethUpper",) + tuple(lower):
    o = src[nm]
    P0 = np.array([v.co[:] for v in o.data.vertices])
    if o.data.shape_keys: o.shape_key_clear()
    o.shape_key_add(name="Basis", from_mix=False)
    angs = {}
    for k in KEYS:
        P = P0
        if nm in lower:
            th = fit_angle(np.array([v.co[:] for v in KB[k].data]))
            if abs(th) > 1e-3:
                R = np.array(Matrix.Rotation(-th, 3, 'X')); P = (P0 - pivot) @ R.T + pivot
                angs[k] = round(math.degrees(th), 2)
        o.shape_key_add(name=k, from_mix=False).data.foreach_set("co", P.ravel())
    if nm == "TeethLower": rep["jaw_key_angles_deg"] = {k: v for k, v in angs.items() if abs(v) > 0.5}
for nm in ("Eye.L", "Eye.R"):
    o = src[nm]; o["center"] = list(np.array([v.co[:] for v in o.data.vertices]).mean(0))
bpy.data.objects.remove(tb)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("ASSEMBLED", json.dumps(rep)[:600])
