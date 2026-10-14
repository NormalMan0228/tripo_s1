"""Close the open mouth of the clean symmetric head (open/clean.blend) into a neutral closed-lip shape.

Body: harmonic jaw weight (chin/lower lip = 1, upper lip/upper face/back/neck = 0) -> rotation about the jaw
pivot (X axis) with the angle that minimises the front-visible mouth opening -> iterative lip seal
(front rays measure the remaining slit per column; lower rim moves up 70 %, upper rim down 30 %, harmonic falloff).
MouthLower / TeethLower / Tongue rotate rigidly with the jaw; TeethUpper stays.
Writes open/closed.blend + open/closed_report.json.  Symmetry is preserved (all operations are x-symmetric).
Usage: blender --background open/clean.blend --python close_mouth.py -- <out_dir>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
PIVOT = np.array([0.0, float(os.environ.get("PIV_Y", -0.03)), float(os.environ.get("PIV_Z", 0.53))])
rep = {"pivot": PIVOT.tolist()}
body = bpy.data.objects["Body"]
X0 = np.array([v.co[:] for v in body.data.vertices]); n = len(X0)
E = np.array([e.vertices[:] for e in body.data.edges])
polys = [tuple(p.vertices) for p in body.data.polygons]
x, y, z = X0.T


def front_hits(X, xs, zs):
    T = BVHTree.FromPolygons([tuple(p) for p in X], polys)
    D = np.full((len(zs), len(xs)), np.nan); F = np.full(D.shape, -1)
    for i, zz in enumerate(zs):
        for j, xx in enumerate(xs):
            h = T.ray_cast(Vector((xx, -2, zz)), Vector((0, 1, 0)), 5)
            if h[0] is not None: D[i, j] = h[0].y; F[i, j] = h[2]
    return D, F


# ---- measure opening of the source
XS = np.arange(-0.12, 0.1201, 0.002); ZS = np.arange(0.28, 0.52, 0.002)
D0, F0 = front_hits(X0, XS, ZS)
DEEP = -0.18
op = (D0 > DEEP) | np.isnan(D0)
op &= (ZS[:, None] > 0.335) & (ZS[:, None] < 0.50)
j0 = np.argmin(np.abs(XS)); rows = np.where(op[:, j0])[0]
z_lo0, z_hi0 = float(ZS[rows.min()]), float(ZS[rows.max()])
z_mid = 0.5 * (z_lo0 + z_hi0)
# corner: outermost column that is still open somewhere in the upper half of the mouth (z_mid .. z_hi0)
band = (ZS >= z_mid) & (ZS <= z_hi0 + 0.004)
cols = np.where(op[band].any(0))[0]
corner = float(np.max(np.abs(XS[cols])))
rep.update(corner_x=corner, mid_open=[z_lo0, z_hi0])

# ---- jaw weights (harmonic)
ax = np.abs(x)
front = y < -0.12
up_lip = front & (z > z_hi0 - 0.004) & (ax < corner * 0.85)
lo_lip = front & (z < z_lo0 + 0.004) & (z > z_lo0 - 0.10) & (ax < corner * 0.85)
fix0 = (z > 0.56) | (y > 0.06) | (z < 0.20) | up_lip
inside = (y > -0.25) & (y < 0.0) & (ax < corner * 1.1) & (z > 0.30) & (z < 0.50)
fix0 |= inside & (z > z_mid + 0.01)                       # palate / upper interior
fix1 = (lo_lip | (inside & (z < z_mid - 0.01)) | ((z < z_lo0) & (z > 0.25) & (y < -0.05) & (ax < 0.10))) & ~fix0
fixed = np.where(fix0 | fix1)[0]; vals = fix1[fixed].astype(float)
wE = 1.0 / np.maximum(np.linalg.norm(X0[E[:, 0]] - X0[E[:, 1]], axis=1), 1e-6)
deg = np.zeros(n); np.add.at(deg, E[:, 0], wE); np.add.at(deg, E[:, 1], wE); deg = np.maximum(deg, 1e-12)
w = np.clip(0.5 - (z - z_mid) / 0.1, 0, 1)
w[fixed] = vals
free = np.ones(n, bool); free[fixed] = False
for _ in range(6000):
    acc = np.zeros(n); np.add.at(acc, E[:, 0], wE * w[E[:, 1]]); np.add.at(acc, E[:, 1], wE * w[E[:, 0]])
    w[free] = 0.3 * w[free] + 0.7 * (acc / deg)[free]
w = np.clip(w, 0, 1)
w = 0.5 * (w + w)                                      # (symmetric by construction)


def rot(P, th):
    R = np.array(Matrix.Rotation(th, 3, 'X'))
    return (P - PIVOT) @ R.T + PIVOT


def lbs(th):
    return X0 * (1 - w[:, None]) + rot(X0, th) * w[:, None]


def opening(X):
    D, _ = front_hits(X, XS[::2], ZS[::2])
    o = (D > DEEP) | np.isnan(D)
    o &= (ZS[::2][:, None] > 0.33) & (ZS[::2][:, None] < 0.49) & (np.abs(XS[::2])[None] < corner)
    return int(o.sum())


best = None
for deg_ in np.arange(8, 34.1, 1.0):
    th = -math.radians(deg_)              # negative X rotation lifts the chin (front is -Y)
    s = opening(lbs(th))
    if best is None or s < best[0]: best = (s, deg_)
    if s == 0: break
th = -math.radians(best[1])
# make sure the direction is right: compare with +angle once
if opening(lbs(-th)) < best[0]:
    th = -th
rep["jaw_close_deg"] = math.degrees(th); rep["opening_after_rot"] = best[0]
X = lbs(th)

# ---- lip seal (closed loop)
SH = float(os.environ.get("SEAL_LOWER_SHARE", 0.7)); PRESS = 0.0008
FX = np.arange(-corner, corner + 1e-9, 0.002); FZ = np.arange(0.36, 0.50, 0.0006)
for it in range(10):
    T = BVHTree.FromPolygons([tuple(p) for p in X], polys)
    gaps = []
    lo_rim, up_rim = {}, {}
    for xx in FX:
        hz = []
        for zz in FZ:
            h = T.ray_cast(Vector((xx, -2, zz)), Vector((0, 1, 0)), 5)
            hz.append(h)
        deep = [k for k, h in enumerate(hz) if h[0] is None or h[0].y > DEEP]
        if not deep:
            gaps.append(0.0); continue
        k0, k1 = min(deep), max(deep)
        g = FZ[k1] - FZ[k0] + (FZ[1] - FZ[0])
        gaps.append(g)
        if k0 > 0 and hz[k0 - 1][0] is not None:
            for vi in polys[hz[k0 - 1][2]]: lo_rim[vi] = max(lo_rim.get(vi, 0), g)
        if k1 + 1 < len(FZ) and hz[k1 + 1][0] is not None:
            for vi in polys[hz[k1 + 1][2]]: up_rim[vi] = max(up_rim.get(vi, 0), g)
    gaps = np.array(gaps)
    rep.setdefault("seal_log_mm", []).append(round(float(gaps.max()) * 1000, 2))
    if gaps.max() < 0.0007: break
    # targets from the column gap profile, smoothed along x and faded at the corners
    gs = np.convolve(np.pad(gaps, 3, mode="edge"), np.ones(7) / 7, "valid")
    fade = np.clip((corner - np.abs(FX)) / (0.25 * corner), 0, 1)
    gs = gs * fade
    fixv = {}
    for vi in lo_rim: fixv[vi] = SH * float(np.interp(X[vi, 0], FX, gs)) + PRESS * fade[np.argmin(np.abs(FX - X[vi, 0]))]
    for vi in up_rim: fixv[vi] = fixv.get(vi, 0) - (1 - SH) * float(np.interp(X[vi, 0], FX, gs)) - PRESS * fade[np.argmin(np.abs(FX - X[vi, 0]))]
    # symmetric targets: average with mirror partners (nearest vertex at -x)
    dz = np.zeros(n); known = np.zeros(n, bool)
    for vi, d in fixv.items(): dz[vi] = d; known[vi] = True
    far = np.linalg.norm((X - np.array([0, -0.28, 0.44]))[:, [0, 2]], axis=1) > 0.06
    far |= X[:, 1] > -0.15
    known_all = known | far
    for _ in range(1500):
        acc = np.zeros(n); np.add.at(acc, E[:, 0], wE * dz[E[:, 1]]); np.add.at(acc, E[:, 1], wE * dz[E[:, 0]])
        dz[~known_all] = (acc / deg)[~known_all]
    X[:, 2] += dz
# enforce exact symmetry (mirror +X half onto -X by nearest partner in the source)
from mathutils.kdtree import KDTree
kd = KDTree(n)
for i, p in enumerate(X0): kd.insert(p, i)
kd.balance()
mir = np.array([kd.find((-p[0], p[1], p[2]))[1] for p in X0])
Xs = X.copy()
Xs[:, 0] = 0.5 * (X[:, 0] - X[mir, 0]); Xs[:, 1:] = 0.5 * (X[:, 1:] + X[mir, 1:])
X = Xs
body.data.vertices.foreach_set("co", X.ravel()); body.data.update()
vg = body.vertex_groups.get("jaw") or body.vertex_groups.new(name="jaw")
for i in range(n): vg.add([i], float(w[i]), 'REPLACE')
body["jaw_pivot"] = PIVOT.tolist(); body["jaw_close_deg"] = rep["jaw_close_deg"]
for nm in ("MouthLower", "TeethLower", "Tongue"):
    o = bpy.data.objects.get(nm)
    if o:
        P = np.array([v.co[:] for v in o.data.vertices]); o.data.vertices.foreach_set("co", rot(P, th).ravel()); o.data.update()
# metrics: teeth/tongue poking through the closed lips (front rays hit them before the skin)
T = BVHTree.FromPolygons([tuple(p) for p in X], polys)
pk = {}
for nm in ("TeethUpper", "TeethLower", "Tongue", "MouthLower"):
    P = np.array([v.co[:] for v in bpy.data.objects[nm].data.vertices]); c = 0
    for p in P[::3]:
        h = T.ray_cast(Vector((p[0], -2, p[2])), Vector((0, 1, 0)), 5)
        if h[0] is None or h[0].y > p[1]: c += 1
    pk[nm] = c
rep["visible_inner_verts(1/3 sample)"] = pk
rep["move_upper_face_max_mm"] = float(np.linalg.norm(X - X0, axis=1)[z > 0.56].max() * 1000)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "closed.blend"))
json.dump(rep, open(os.path.join(OUT, "closed_report.json"), "w"), indent=1)
print("CLOSED", json.dumps(rep))
