"""Target (P2 Tripo head) features for wrapping: eyeball spheres, eye-opening contours, lip line, landmarks.

Separates the P2 object into Body / Eye.L / Eye.R (connected components), fits eye spheres, takes the eye-hole
boundary loops of the body as opening contours (ordered, starting at the inner corner, going over the top),
and finds the closed-lip line as the depth valley between the lips in front view.
Writes target.blend (Body, Eye.L, Eye.R) and target_features.json.
Usage: blender --background candidates.blend --python target_features.py -- <collection> <out_dir>
"""
import bpy, bmesh, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
coll, out = a[0], os.path.abspath(a[1])
if coll == "__existing__":
    keep = {"Body", "Eye.L", "Eye.R"}
    for o in list(bpy.data.objects):
        if o.name not in keep: bpy.data.objects.remove(o)
    for o in bpy.data.objects:
        o.data.transform(o.matrix_world); o.matrix_world = o.matrix_world.__class__()
    parts = [bpy.data.objects["Body"], bpy.data.objects["Eye.L"], bpy.data.objects["Eye.R"]]
    src = None
else:
    src = next(o for o in bpy.data.collections[coll].objects if o.type == 'MESH')
for o in (list(bpy.data.objects) if src else []):
    if o is not src:
        bpy.data.objects.remove(o)
if src:
    for c in list(bpy.data.collections):
        if c.name != coll:
            bpy.data.collections.remove(c)
    bpy.context.view_layer.objects.active = src; src.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE'); bpy.ops.object.mode_set(mode='OBJECT')
    parts = [o for o in bpy.data.objects if o.type == 'MESH']
    parts.sort(key=lambda o: -len(o.data.vertices))
body = parts[0]; body.name = "Body"
feats = {}


def sphere_fit(P):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = s[:3]
    return c, float(np.sqrt(s[3] + c @ c))


for o in parts[1:]:
    P = np.array([v.co[:] for v in o.data.vertices])
    c, r = sphere_fit(P)
    side = "L" if c[0] > 0 else "R"
    o.name = f"Eye.{side}"
    res = np.abs(np.linalg.norm(P - c, axis=1) - r)
    feats[f"eye_{side}"] = dict(center=c.tolist(), radius=r, fit_res_max=float(res.max()), verts=len(P))
    print("eye", side, np.round(c, 4), round(r, 4), "res", round(float(res.max()), 5))

# --- align: yaw so both eye centres share depth, centre the eye midpoint on x = 0
from mathutils import Matrix
cL, cR = np.array(feats["eye_L"]["center"]), np.array(feats["eye_R"]["center"])
d = cL - cR
yaw = -np.arctan2(d[1], d[0])
M = Matrix.Rotation(yaw, 4, 'Z')
mid = M @ Vector((cL + cR) / 2)
M = Matrix.Translation((-mid.x, 0, 0)) @ M
for o in parts:
    o.data.transform(M)
for side in ("L", "R"):
    feats[f"eye_{side}"]["center"] = list(M @ Vector(feats[f"eye_{side}"]["center"]))
feats["align"] = dict(yaw_deg=float(np.degrees(yaw)), x_shift=float(-mid.x))
print("align yaw deg", round(float(np.degrees(yaw)), 3), "x shift", round(float(-mid.x), 4))
co = np.array([v.co[:] for v in body.data.vertices])
bm = bmesh.new(); bm.from_mesh(body.data)
adj = {}
for e in bm.edges:
    if e.is_boundary:
        u, w = e.verts[0].index, e.verts[1].index
        adj.setdefault(u, []).append(w); adj.setdefault(w, []).append(u)
seen, loops = set(), []
for s in adj:
    if s in seen: continue
    order = [s]; seen.add(s); prev, cur = None, s
    while True:
        nxt = [w for w in adj[cur] if w != prev and w not in seen]
        if not nxt: break
        prev, cur = cur, nxt[0]; order.append(cur); seen.add(cur)
    loops.append(order)
bm.free()
print("boundary loops", [(len(l), np.round(co[l].mean(0), 3).tolist()) for l in sorted(loops, key=len, reverse=True)[:8]])


def order_eye_loop(loop, side):
    """Start at the inner corner (closest to the midline), continue over the top."""
    P = co[loop]
    i0 = int(np.argmin(np.abs(P[:, 0])))
    loop = loop[i0:] + loop[:i0]
    P = co[loop]
    # direction: second sample should be above the first ("over the top")
    if P[min(3, len(P) - 1), 2] < P[0, 2]:
        loop = [loop[0]] + loop[1:][::-1]
    return loop


Tb = BVHTree.FromPolygons([tuple(p) for p in co], [tuple(p.vertices) for p in body.data.polygons])
for side in ("L", "R"):
    eo = bpy.data.objects[f"Eye.{side}"]
    Te = BVHTree.FromPolygons([tuple(v.co) for v in eo.data.vertices], [tuple(p.vertices) for p in eo.data.polygons])
    c = np.array(feats[f"eye_{side}"]["center"]); r = feats[f"eye_{side}"]["radius"]
    sx = 1 if side == "L" else -1
    pts = []
    N = 180
    for k in range(N):
        th = np.pi - 2 * np.pi * k / N if side == "L" else 2 * np.pi * k / N   # start at the inner corner, go over the top
        dx, dz = np.cos(th), np.sin(th)
        last_eye = None
        for rr in np.arange(0.0, r * 1.6, r / 300):
            x, z = c[0] + dx * rr, c[2] + dz * rr
            he = Te.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)), 2.0)
            hs = Tb.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)), 2.0)
            eye_first = he[0] is not None and (hs[0] is None or he[3] < hs[3])
            if eye_first:
                last_eye = he[0]
            elif last_eye is not None:
                pts.append([x, hs[0].y if hs[0] is not None else last_eye.y, z]); break
    feats[f"eye_{side}"]["opening"] = pts
    feats[f"eye_{side}"]["opening_n"] = len(pts)
    print("opening", side, len(pts))
    # contact curve: skin surface crossing the eye sphere (radius + CONTACT_EPS), front hemisphere,
    # ordered by angle like the opening (inner corner first, over the top)
    eps = float(__import__("os").environ.get("CONTACT_EPS", 0.0008))
    d0 = np.linalg.norm(co - c, axis=1) - r
    nearf = (co[:, 1] < c[1] - 0.25 * r) & (d0 < 0.03)
    eps = max(eps, float(np.percentile(d0[nearf], 1)) + 0.0008) if nearf.any() else eps
    dd = d0 - eps
    cp = []
    for e in body.data.edges:
        i, j = e.vertices
        if dd[i] * dd[j] < 0:
            t = dd[i] / (dd[i] - dd[j]); p = co[i] + t * (co[j] - co[i])
            if p[1] < c[1] - 0.25 * r:
                cp.append(p)
    cp = np.array(cp)
    # keep the crossing ring nearest to the opening (largest component around the eye axis)
    ang = np.arctan2(cp[:, 2] - c[2], sx * (cp[:, 0] - c[0]))
    ang_o = np.arctan2(np.array(pts)[:, 2] - c[2], sx * (np.array(pts)[:, 0] - c[0]))
    bins = np.linspace(-np.pi, np.pi, 181)
    curve = []
    op = np.array(pts)
    for k in range(180):
        a0 = bins[k]; a1 = bins[k + 1]
        m = (ang >= a0) & (ang < a1)
        if not m.any(): continue
        # among crossings in this angular bin, the one closest (in front projection) to the opening point
        mo = (ang_o >= a0 - 0.05) & (ang_o < a1 + 0.05)
        ref = op[mo].mean(0) if mo.any() else c
        q = cp[m]; qq = q[np.argmin(np.linalg.norm((q - ref)[:, [0, 2]], axis=1))]
        curve.append((a0, qq))
    curve.sort(key=lambda t: t[0])
    cv = np.array([q for _, q in curve])
    # reorder to start at the inner corner (min |x|) and go over the top
    i0 = int(np.argmin(np.abs(cv[:, 0])))
    cv = np.vstack([cv[i0:], cv[:i0]])
    if cv[min(3, len(cv) - 1), 2] < cv[0, 2]:
        cv = np.vstack([cv[:1], cv[1:][::-1]])
    feats[f"eye_{side}"]["contact"] = cv.tolist()
    print("contact", side, len(cv), "mean depth behind opening mm", round(float((cv[:, 1].mean() - op[:, 1].mean()) * 1000), 2))

# lip line: depth valley between the lips (front rays), per x column across the mouth
T = Tb
nose = co[np.argmin(np.where(np.abs(co[:, 0]) < 0.01, co[:, 1], 9))]
chin_band = (np.abs(co[:, 0]) < 0.01) & (co[:, 2] < nose[2] - 0.05)
feats["nose_tip"] = nose.tolist()
zs = np.arange(nose[2] - 0.16, nose[2] - 0.02, 0.0008)
def depth_profile(x):
    ys = []
    for z in zs:
        h = T.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)), 2.0)[0]
        ys.append(h.y if h is not None else np.nan)
    return np.array(ys)
mid = depth_profile(0.0)
# the lip seam: deepest local valley between two lip bulges just below the nose
from numpy import nanargmax
cand = [(i, mid[i]) for i in range(3, len(zs) - 3)
        if mid[i] > mid[i - 3] and mid[i] > mid[i + 3] and mid[i] == np.nanmax(mid[i - 3:i + 4])]
cand.sort(key=lambda t: -(t[1] - min(mid[t[0] - 3], mid[t[0] + 3])))
seam_z0 = zs[cand[0][0]]
line = []
d0 = None
for x in np.arange(0.0, 0.20, 0.002):
    prof = depth_profile(x)
    zc = line[-1][1] if line else seam_z0
    win = np.abs(zs - zc) < (0.004 if line else 0.012)
    if not win.any(): break
    idx = np.where(win)[0]
    j = idx[np.nanargmax(prof[idx])]
    lo = np.nanmin(prof[np.abs(zs - zs[j]) < 0.01])
    depth = prof[j] - lo
    if d0 is None: d0 = depth
    if x > 0.03 and depth < 0.4 * d0:
        break
    line.append((x, zs[j], prof[j], depth))
line = np.array(line)
# the corner: first abrupt upward step (the valley jumps into the dimple / smile crease)
for i in range(3, len(line)):
    if line[i, 0] > 0.07 and line[i, 1] - line[i - 1, 1] > 0.0016:
        line = line[:i - 1]; break
# smooth z along x (moving median) to remove single-sample jumps
zsm = np.array([np.median(line[max(0, i - 2):i + 3, 1]) for i in range(len(line))])
line[:, 1] = zsm
# extend to the corner pocket: deepest front-ray hit just beyond the traced end, slightly above it
xe, ze = line[-1, 0], line[-1, 1]
best = None
for x in np.arange(xe, xe + 0.025, 0.001):
    for z in np.arange(ze - 0.002, ze + 0.014, 0.0005):
        h = T.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)), 2.0)[0]
        if h is not None and (best is None or h.y > best[2] + 0.0004):
            best = (x, z, h.y)
EXT = float(__import__("os").environ.get("LIP_EXT_FRAC", 1.0))
if best is not None:
    best = (xe + (best[0] - xe) * EXT, ze + (best[1] - ze) * EXT, best[2])
if best is not None and best[0] > xe + 0.002:
    n_add = max(2, int((best[0] - xe) / 0.002))
    ext = [(xe + (best[0] - xe) * t, ze + (best[1] - ze) * t * t, 0, 0) for t in np.linspace(0, 1, n_add + 1)[1:]]
    for xx, zz, _, _ in ext:
        h = T.ray_cast(Vector((xx, -1, zz)), Vector((0, 1, 0)), 2.0)[0]
        line = np.vstack([line, [xx, zz, h.y if h is not None else best[2], 0]])
corner_x = float(line[-1, 0])
L = np.concatenate([line[::-1] * [-1, 1, 1, 1], line[1:]])  # mirror to the right side
feats["lip_line"] = [[float(p[0]), float(p[2]), float(p[1])] for p in L]   # x, y, z
feats["mouth_corner_x"] = corner_x
feats["chin"] = co[np.argmin(np.where(chin_band & (co[:, 2] > seam_z0 - 0.14) & (co[:, 2] < seam_z0 - 0.035), co[:, 1], 9))].tolist()
feats["head_top"] = co[np.argmax(co[:, 2])].tolist()
feats["head_back"] = co[np.argmax(np.where(co[:, 2] > nose[2] + 0.05, co[:, 1], -9))].tolist()
ear_band = (co[:, 2] > nose[2] - 0.05) & (co[:, 2] < nose[2] + 0.12)
feats["ear_L"] = co[np.argmax(np.where(ear_band, co[:, 0], -9))].tolist()
feats["ear_R"] = co[np.argmin(np.where(ear_band, co[:, 0], 9))].tolist()
print("lip line pts", len(L), "corner x", round(corner_x, 4), "seam z", round(float(seam_z0), 4))
json.dump(feats, open(os.path.join(out, "target_features.json"), "w"))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "target.blend"))
