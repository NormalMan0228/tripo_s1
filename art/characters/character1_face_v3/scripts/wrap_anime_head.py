"""Wrap an anime template head (VRM/glTF, with expression shape keys) onto a Tripo head shape.

Template = clean topology + anime eyes/lids + blink and mouth shape keys (e.g. Seed-san, or a VRoid export).
           Anime heads have no eye holes: the skin dips into a pocket and flat eye cards float in front of it.
Target   = Tripo head prepared for Headshot (character1_v3_head_headshot.fbx) + its landmarks: the 35-point
           Headshot ini, or JSON from face_landmarks_mp.py (MediaPipe, no Character Creator needed).

Steps
 1. weld the template head (glTF splits vertices on UV seams)
 2. eye rims and lip seams on both heads from front-ray depth: target lid margin = first depth maximum
    walking out from the eye centre; template rim = where the pocket wall reaches the face; lip seam =
    deepest groove between the mouth corners. Plus brows, nose tip, chin, crown, back, ear top/bottom/back.
 3. scale+translate the target into template space, thin-plate-spline warp W (template -> target landmarks)
 4. pull the skin onto the target surface (smoothed displacement, faded out near eyes and mouth and off
    inside the eye pockets / mouth cavity, so the template keeps its own thin anime lids and lip slit)
 5. every shape key k becomes W(template_k) + skin offset, so a lid that closes in the template closes on
    the target rim too
Outputs: <out>/wrap.blend (head + scaled target for comparison), <out>/wrap_log.json
Usage: blender -b --factory-startup -P wrap_anime_head.py -- <template.glb> <head_mesh_name> <target.fbx> <align.ini|landmarks.json> <out_dir> [extra,parts]
"""
import bpy, sys, os, re, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index("--") + 1:]
TEMPLATE, HEAD, TARGET, INI, OUT = a[:5]
EXTRA = a[5].split(',') if len(a) > 5 and a[5] else []   # template parts that ride along (hair, hats …)
os.makedirs(OUT, exist_ok=True)
log = {}
TS = np.linspace(0, 1, 11)[1:-1]          # samples along each lid / the lip seam (corners added separately)
TSD = np.linspace(0, 1, 33)[1:-1]         # dense lid samples for the eye-region map


def hit_y(bvh, x, z):
    loc = bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))[0]
    return None if loc is None else loc.y


def rim_rays(bvh, cx, cz, mode):
    """Eye opening contour from front rays walking outward from the eye centre, one point per 4 degrees.
    margin: Tripo eye (eyeball recedes, then the lid rises) -> first depth maximum.
    pocket: anime eye (skin pocket behind the eye card) -> top of the pocket wall."""
    yc = hit_y(bvh, cx, cz); pts = []
    rs = np.arange(0.002, 0.045, 0.00025)
    for th in np.radians(np.arange(0, 360, 4)):
        d = (math.cos(th), math.sin(th))
        ys = np.array([hit_y(bvh, cx + r * d[0], cz + r * d[1]) or np.nan for r in rs])
        ok = None
        if mode == 'margin':
            for i in range(1, len(rs) - 16):
                if ys[i] >= ys[i - 1] and ys[i] >= ys[i + 1] and ys[i] - np.nanmin(ys[i + 1:i + 16]) > 0.0003:
                    ok = i; break
        else:
            for i in range(len(rs) - 1):
                if ys[i] < yc - 0.006:
                    while i + 1 < len(rs) and ys[i] - ys[i + 1] > 0.6 * (rs[1] - rs[0]): i += 1
                    ok = i; break
        if ok is not None:
            pts.append([cx + rs[ok] * d[0], ys[ok], cz + rs[ok] * d[1]])
    return np.array(pts)


def seam_curve(bvh, xl, xr, zl, zm, zr, n=31):
    """Lip seam = deepest groove per x; the point sits on the lip surface (mean of the hits just above/below)."""
    out = []
    for x in np.linspace(xl, xr, n):
        t = (x - xl) / (xr - xl); zc = zl + (zr - zl) * t
        zg = zm + (zc - zm) * (2 * t - 1) ** 2
        best = max(((hit_y(bvh, x, z) or -9, z) for z in np.arange(zg - 0.004, zg + 0.004, 0.0002)))
        z = best[1]; ys = [hit_y(bvh, x, z + dz) for dz in (-0.0006, 0.0006)]
        out.append([x, np.mean([y for y in ys if y is not None]), z])
    return np.array(out)


def split_idx(n, a_idx, b_idx):
    """Index lists of the two paths of a closed polyline between a and b (both inclusive)."""
    p1 = [a_idx]; i = a_idx
    while i != b_idx: i = (i + 1) % n; p1.append(i)
    p2 = [a_idx]; i = a_idx
    while i != b_idx: i = (i - 1) % n; p2.append(i)
    return p1, p2


def resample(path, ts):
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)]); s /= s[-1]
    return np.array([[np.interp(t, s, path[:, j]) for j in range(3)] for t in ts])


def lids(R, axis=False):
    """Split a rim contour into corners + upper/lower lid samples.
    axis=False: corners = farthest / nearest to the midline (anime template eyes, D-shaped).
    axis=True:  corners = the two ends of the contour's long axis (tilted almond Tripo eyes; no landmark hints
                needed, so rough MediaPipe eye corners are fine); outer = the end farther from the midline."""
    if axis:
        xz = R[:, [0, 2]]; c0 = xz.mean(0); ev = np.linalg.eigh(np.cov((xz - c0).T))[1][:, -1]
        t = (xz - c0) @ ev; e1, e2 = int(np.argmax(t)), int(np.argmin(t))
        io, ii = (e1, e2) if abs(R[e1, 0]) > abs(R[e2, 0]) else (e2, e1)
    else:
        ax = np.abs(R[:, 0]); io, ii = int(np.argmax(ax)), int(np.argmin(ax))
    p1, p2 = split_idx(len(R), io, ii)
    up, lo = (p1, p2) if R[p1][:, 2].mean() > R[p2][:, 2].mean() else (p2, p1)
    return {'outer': R[io], 'inner': R[ii], 'up': resample(R[up], TS), 'lo': resample(R[lo], TS), 'raw': R,
            'dense': np.vstack([R[io], R[ii], resample(R[up], TSD), resample(R[lo], TSD)])}


def rule_landmarks(V, nose_band, chin_y, ear_x, ear_z, mid_tol=0.004):
    """Same rules on both heads: nose tip, chin, crown, back-most point, ear top/bottom/back."""
    out = {}
    M = V[np.abs(V[:, 0]) < mid_tol]
    nb = M[(M[:, 2] > nose_band[0]) & (M[:, 2] < nose_band[1])]
    out['nose'] = nb[np.argmin(nb[:, 1])]
    fr = M[M[:, 1] < chin_y]
    out['chin'] = fr[np.argmin(fr[:, 2])]
    out['crown'] = M[np.argmax(M[:, 2])]
    out['back'] = M[np.argmax(M[:, 1])]
    for s_, sg in (('R', -1), ('L', 1)):
        E = V[((sg * V[:, 0]) > ear_x) & (V[:, 2] > ear_z[0]) & (V[:, 2] < ear_z[1])]
        out['ear_top_' + s_] = E[np.argmax(E[:, 2])]
        out['ear_bot_' + s_] = E[np.argmin(E[:, 2])]
        out['ear_back_' + s_] = E[np.argmax(E[:, 1])]
    return out

# ---------------------------------------------------------------- target (Tripo head)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=TARGET)
tgt = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
SV = np.array([tuple(tgt.matrix_world @ v.co) for v in tgt.data.vertices])
SP = [list(p.vertices) for p in tgt.data.polygons]
bvhS0 = BVHTree.FromPolygons([Vector(v) for v in SV], SP)
if INI.lower().endswith('.json'):          # face_landmarks_mp.py output (no Character Creator needed)
    LT = {int(k): np.array(v, float) for k, v in json.load(open(INI)).items()}
else:                                       # Headshot alignment ini: F = triangle index, B = barycentric
    tg = open(INI, encoding='utf-8-sig').read().split('[Target]')[1]
    F = {int(k): int(v) for k, v in re.findall(r'\nF(\d+) = (\d+)', tg)}
    B = {int(k): [float(x) for x in v.split()] for k, v in re.findall(r'\nB(\d+) = "([^"]+)"', tg)}
    LT = {k: sum(SV[SP[F[k]][i]] * B[k][i] for i in range(3)) for k in F}

tgt_rims = {}
for side, ids in {'R': (7, 8, 9, 10), 'L': (13, 12, 11, 14)}.items():
    cx, cz = np.mean([LT[k][0] for k in ids]), np.mean([LT[k][2] for k in ids])
    for _ in range(3):                      # re-centre on the found rim so a rough start point does not matter
        R_ = rim_rays(bvhS0, cx, cz, 'margin'); cx, cz = float(R_[:, 0].mean()), float(R_[:, 2].mean())
    tgt_rims[side] = lids(R_, axis=True)
zm = (LT[34][2] + LT[35][2]) / 2
tgt_seam = seam_curve(bvhS0, LT[20][0], LT[22][0], LT[20][2], zm, LT[22][2])
eyeT = np.mean([LT[k] for k in (7, 9, 11, 13)], axis=0)
tgt_rule = rule_landmarks(SV, (0, 1), 0, 0.100, (eyeT[2] - 0.06, eyeT[2] + 0.03))
tgt_rule.update({'nose': LT[16], 'chin': LT[24], 'crown': LT[31]})   # ini points are reliable for these
log['target_rim_points'] = {s: len(v['raw']) for s, v in tgt_rims.items()}

# ---------------------------------------------------------------- template (anime head)
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
bpy.ops.import_scene.gltf(filepath=TEMPLATE)
head = bpy.data.objects[HEAD]
for o in list(bpy.context.scene.objects):
    if o.type == 'MESH' and o != head and o.name not in EXTRA: bpy.data.objects.remove(o)
mw = head.matrix_world.copy(); mwi = mw.inverted()
me = head.data
N = len(me.vertices)
TV = np.array([tuple(mw @ v.co) for v in me.vertices])
keys = [k.name for k in me.shape_keys.key_blocks][1:] if me.shape_keys else []
KV = {k: np.array([tuple(mw @ Vector(d.co)) for d in me.shape_keys.key_blocks[k].data]) for k in keys}

kd = KDTree(N)
for i, p in enumerate(TV): kd.insert(p, i)
kd.balance()
rep = np.arange(N)
for i, p in enumerate(TV):
    if rep[i] != i: continue
    for _, j, _ in kd.find_range(p, 1e-6):
        if j > i and rep[j] == j: rep[j] = i
uids, wid = np.unique(rep, return_inverse=True)          # welded id per original vertex
M_ = len(uids); W0 = TV[uids]
faces = [[int(wid[v]) for v in p.vertices] for p in me.polygons]
fmat = [p.material_index for p in me.polygons]
skin = np.zeros(M_, bool); eyem = np.zeros(M_, bool)
for f, m in zip(faces, fmat):
    if m == 0: skin[f] = True
    elif m == 1: eyem[f] = True
adj = [set() for _ in range(M_)]
for f in faces:
    for i in range(len(f)):
        a_, b_ = f[i], f[(i + 1) % len(f)]; adj[a_].add(b_); adj[b_].add(a_)
bvhT = BVHTree.FromPolygons([Vector(v) for v in W0], [f for f, m in zip(faces, fmat) if m == 0])
# open edge of the head skin = where it meets the body's neck; it stays put so the head still fits the body
ecount = {}
for f, m in zip(faces, fmat):
    if m == 0:
        for i in range(len(f)):
            e = tuple(sorted((f[i], f[(i + 1) % len(f)]))); ecount[e] = ecount.get(e, 0) + 1
neck_ring = np.array(sorted({v for e, c in ecount.items() if c == 1 for v in e}))
log['neck_ring_verts'] = int(len(neck_ring))

tpl_rims = {}
for side, sg in (('R', -1), ('L', 1)):
    E = W0[eyem & (sg * W0[:, 0] > 0.015) & (W0[:, 2] > 1.38)]
    cx, cz = float(np.median(E[:, 0])), float(np.median(E[:, 2]))
    tpl_rims[side] = lids(rim_rays(bvhT, cx, cz, 'pocket'))
log['template_rim_points'] = {s: len(v['raw']) for s, v in tpl_rims.items()}
# slit corners from the welded lip line: skin vertices near the mouth with two coincident layers
tpl_seam = seam_curve(bvhT, -0.0222, 0.0222, 1.3440, 1.3440, 1.3440)
eyeTt = np.mean([tpl_rims[s][k] for s in 'RL' for k in ('outer', 'inner')], axis=0)
mouthTt = tpl_seam[len(tpl_seam) // 2]
tpl_rule = rule_landmarks(W0[skin], (mouthTt[2] + 0.008, eyeTt[2] - 0.008), -0.05, 0.085, (eyeTt[2] - 0.05, eyeTt[2] + 0.02))
def front_point(bvh, x, z): return np.array([x, hit_y(bvh, x, z), z])
tpl_brow = {1: front_point(bvhT, -0.0751, 1.4546), 2: front_point(bvhT, -0.0477, 1.4589), 3: front_point(bvhT, -0.0217, 1.4540)}
tpl_brow.update({6: tpl_brow[1] * [-1, 1, 1], 5: tpl_brow[2] * [-1, 1, 1], 4: tpl_brow[3] * [-1, 1, 1]})

# ---------------------------------------------------------------- correspondences (template -> target)
src, dst, tag = [], [], []
def add(p, q, t): src.append(np.asarray(p, float)); dst.append(np.asarray(q, float)); tag.append(t)
for s in 'RL':
    add(tpl_rims[s]['outer'], tgt_rims[s]['outer'], 'eye_outer_' + s); add(tpl_rims[s]['inner'], tgt_rims[s]['inner'], 'eye_inner_' + s)
    for p, q in zip(tpl_rims[s]['up'], tgt_rims[s]['up']): add(p, q, 'lid_up_' + s)
    for p, q in zip(tpl_rims[s]['lo'], tgt_rims[s]['lo']): add(p, q, 'lid_lo_' + s)
add(tpl_seam[0], tgt_seam[0], 'mouth_R'); add(tpl_seam[-1], tgt_seam[-1], 'mouth_L')
for p, q in zip(resample(tpl_seam, TS), resample(tgt_seam, TS)): add(p, q, 'lip_seam')
for k in (1, 2, 3, 4, 5, 6): add(tpl_brow[k], LT[k], 'brow%d' % k)
for k in tpl_rule: add(tpl_rule[k], tgt_rule[k], k)
src, dst = np.array(src), np.array(dst)

# scale + translation of the target into template space (no rotation: both face -Y, Z up)
use = [i for i, t in enumerate(tag) if t.startswith(('eye_', 'mouth_', 'nose', 'chin', 'crown'))]
A_, B_ = dst[use], src[use]
am, bm_ = A_.mean(0), B_.mean(0)
sc = float(((A_ - am) * (B_ - bm_)).sum() / ((A_ - am) ** 2).sum()); tr = bm_ - sc * am
dst_t = dst * sc + tr
SVt = SV * sc + tr
src = np.vstack([src, W0[neck_ring[::2]]]); dst_t = np.vstack([dst_t, W0[neck_ring[::2]]]); tag += ['neck'] * len(neck_ring[::2])
bvhS = BVHTree.FromPolygons([Vector(v) for v in SVt], SP)
log["target_to_template_scale"] = sc; log["target_to_template_translation"] = tr.tolist()
log['landmark_residual_mm_after_similarity'] = {t: round(float(np.linalg.norm(dst_t[i] - src[i]) * 1000), 1) for i, t in enumerate(tag) if not t.startswith(('lid_', 'lip_'))}
json.dump({'src': src.tolist(), 'dst': dst_t.tolist(), 'tag': tag,
           'tpl_rims': {s: v['raw'].tolist() for s, v in tpl_rims.items()},
           'tgt_rims': {s: (v['raw'] * sc + tr).tolist() for s, v in tgt_rims.items()},
           'tpl_seam': tpl_seam.tolist(), 'tgt_seam': (tgt_seam * sc + tr).tolist()}, open(os.path.join(OUT, 'landmarks.json'), 'w'))

# ---------------------------------------------------------------- thin-plate spline W
def tps_fit(X, Y, lam=1e-7):
    n = len(X); K = np.linalg.norm(X[:, None] - X[None], axis=2)
    P_ = np.hstack([np.ones((n, 1)), X])
    L = np.zeros((n + 4, n + 4)); L[:n, :n] = K + lam * np.eye(n); L[:n, n:] = P_; L[n:, :n] = P_.T
    rhs = np.zeros((n + 4, 3)); rhs[:n] = Y
    return X, np.linalg.solve(L, rhs)
def tps_apply(model, Q):
    X, Wt = model; out = np.empty_like(Q)
    for s0 in range(0, len(Q), 4000):
        q = Q[s0:s0 + 4000]; K = np.linalg.norm(q[:, None] - X[None], axis=2)
        out[s0:s0 + 4000] = K @ Wt[:len(X)] + Wt[len(X)] + q @ Wt[len(X) + 1:]
    return out
# eye rims follow the target only across the face (x, z); their depth comes from a fit without them, so the
# stacked eye cards and the lid skin keep the template's front-to-back order (the Tripo lid margin sits
# deep behind a thick lid band and would drag the rim back through the cards)
# the anime eye keeps its own drawn shape: each eye only gets a best-fit scale / tilt / position (2D
# similarity in the x-z plane) onto the target's eye opening, so the iris art is never squashed
def sim2_fit(A2, B2):
    ma, mb = A2.mean(0), B2.mean(0); a2, b2 = A2 - ma, B2 - mb
    U, S_, Vt = np.linalg.svd(b2.T @ a2); D_ = np.diag([1, np.sign(np.linalg.det(U @ Vt))])
    R2 = U @ D_ @ Vt; s2 = float((S_ * np.diag(D_)).sum() / (a2 ** 2).sum()); return s2, R2, mb - s2 * R2 @ ma
def sim2_apply(m, P2): s2, R2, t2 = m; return (s2 * (R2 @ P2.T)).T + t2
eye_sim = {}
for s_ in 'RL':
    eye_sim[s_] = sim2_fit(tpl_rims[s_]['dense'][:, [0, 2]], (tgt_rims[s_]['dense'] * sc + tr)[:, [0, 2]])
    log['eye_fit_' + s_] = {'scale': eye_sim[s_][0], 'tilt_deg': float(np.degrees(np.arctan2(eye_sim[s_][1][1, 0], eye_sim[s_][1][0, 0])))}
for i, t in enumerate(tag):
    if t.startswith(('lid_', 'eye_')):
        dst_t[i, [0, 2]] = sim2_apply(eye_sim[t[-1]], src[i][None, [0, 2]])[0]
eye_ids = [i for i, t in enumerate(tag) if t.startswith(('lid_', 'eye_'))]
other = [i for i in range(len(tag)) if i not in eye_ids]
pre = tps_apply(tps_fit(src[other], dst_t[other]), src[eye_ids])
log['eye_rim_depth_change_mm'] = float(np.abs(dst_t[eye_ids, 1] - pre[:, 1]).mean() * 1000)
dst_t[eye_ids, 1] = pre[:, 1]
model = tps_fit(src, dst_t)
Wb = tps_apply(model, W0)

# ---------------------------------------------------------------- pull skin onto the target surface
def dist_to(Pset, Q):
    k2 = KDTree(len(Pset))
    for i, p in enumerate(Pset): k2.insert(p, i)
    k2.balance(); return np.array([k2.find(q)[2] for q in Q])
def smoothstep(x, e0, e1):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)
def inside2d(poly, pts):
    """Point-in-polygon in the x-z plane."""
    x, z = pts[:, 0], pts[:, 2]; px, pz = poly[:, 0], poly[:, 2]; res = np.zeros(len(pts), bool)
    j = len(poly) - 1
    for i in range(len(poly)):
        c = ((pz[i] > z) != (pz[j] > z)) & (x < (px[j] - px[i]) * (z - pz[i]) / (pz[j] - pz[i] + 1e-12) + px[i])
        res ^= c; j = i
    return res
rim_pts = np.vstack([tpl_rims['R']['raw'], tpl_rims['L']['raw']])
d_eye = dist_to(rim_pts, W0); d_mouth = dist_to(tpl_seam, W0)
pocket = np.zeros(M_, bool)
for s in 'RL':
    R = tpl_rims[s]['raw']; pocket |= inside2d(R, W0) & (W0[:, 1] > R[:, 1].min() - 0.001)
front_y = np.array([hit_y(bvhT, p[0], p[2]) if abs(p[0]) < 0.05 and abs(p[2] - mouthTt[2]) < 0.025 else 9 for p in W0], float)
cavity = W0[:, 1] > front_y + 0.003
d_neck = dist_to(W0[neck_ring], W0)
wgt = skin * ~pocket * ~cavity * smoothstep(d_eye, 0.004, 0.011) * smoothstep(d_mouth, 0.002, 0.008) * smoothstep(d_neck, 0.004, 0.03)
log['masked'] = {'pocket': int(pocket.sum()), 'cavity': int(cavity.sum()), 'pulled': int((wgt > 0).sum())}
nbrs = [np.array(sorted(s)) for s in adj]
def lap(D, it):
    for _ in range(it):
        D = 0.5 * D + 0.5 * np.array([D[n].mean(0) if len(n) else D[i] for i, n in enumerate(nbrs)])
    return D
def vnormals(X):
    nrm = np.zeros_like(X)
    for f in faces:
        p0, p1, p2 = X[f[0]], X[f[1]], X[f[2]]; nrm[f] += np.cross(p1 - p0, p2 - p0)
    return nrm / (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12)
# far skin (away from eyes and mouth) is pulled onto the target; the offsets become one smooth field that
# moves every vertex, eye cards included, so the stacked anime eye layers keep their order
far = wgt > 0.999
fields = []
X = Wb.copy()
for it in range(3):
    nX = vnormals(X); ids, D = [], []
    for i in np.nonzero(far)[0]:
        loc, n, idx, dd = bvhS.find_nearest(Vector(X[i]))
        if loc is None or n.dot(Vector(nX[i])) < 0.2: continue
        ids.append(i); D.append(np.array(loc) - X[i])
    ids, D = np.array(ids), np.array(D)
    k_ = max(1, len(ids) // 700)
    sub = np.concatenate([ids[::k_], neck_ring]); Dsub = np.vstack([D[::k_], W0[neck_ring] - X[neck_ring]])   # neck seam stays
    field = tps_fit(X[sub], Dsub, lam=2e-5); fields.append(field)
    X = X + tps_apply(field, X)
    log['field_fit_%d' % it] = {'n': int(len(sub)), 'mean_mm': float(np.linalg.norm(D, axis=1).mean() * 1000)}
# no per-vertex snap afterwards: the template is much coarser than the Tripo surface, and snapping each
# vertex onto it copies the sculpt's small bumps; the smooth field already lands within ~0.3 mm on average
O = X - Wb
on = np.linalg.norm(O, axis=1)
log['skin_offset_mm'] = {'mean': float(on[skin].mean() * 1000), 'max': float(on.max() * 1000)}

# ---------------------------------------------------------------- eye regions: 2D map + template depth
# around each eye the skin pocket, lid skin and stacked eye cards move with one planar (x, z) map that puts
# the template rim on the target rim; depth stays the template's plus a smooth shift taken from the ring
# around the eye, so walls and cards cannot fold through the face. Blended into the general warp outside.
def tps2_fit(Xp, Y, lam=1e-9):
    n = len(Xp); r = np.linalg.norm(Xp[:, None] - Xp[None], axis=2); K = np.where(r > 0, r * r * np.log(r + 1e-30), 0)
    P_ = np.hstack([np.ones((n, 1)), Xp]); L = np.zeros((n + 3, n + 3))
    L[:n, :n] = K + lam * np.eye(n); L[:n, n:] = P_; L[n:, :n] = P_.T
    rhs = np.zeros((n + 3, Y.shape[1])); rhs[:n] = Y; return Xp, np.linalg.solve(L, rhs)
def tps2_apply(m, Q):
    Xp, Wt = m; r = np.linalg.norm(Q[:, None] - Xp[None], axis=2); K = np.where(r > 0, r * r * np.log(r + 1e-30), 0)
    return K @ Wt[:len(Xp)] + Wt[len(Xp)] + Q @ Wt[len(Xp) + 1:]
Xgen = X.copy()
eye_maps = {}; w_eye = np.zeros(M_)
for s_, sg in (('R', -1), ('L', 1)):
    side = sg * W0[:, 0] > 0.004
    dS = dist_to(tpl_rims[s_]['dense'], W0)
    flat = lambda P: P * [1, 0, 1]
    dS2 = dist_to(flat(tpl_rims[s_]['dense']), flat(W0))                      # distance seen from the front
    frontmost = np.array([abs(W0[i][1] - (hit_y(bvhT, W0[i][0], W0[i][2]) or 9)) < 0.0005 if side[i] and skin[i] and dS2[i] < 0.06 else False for i in range(M_)])
    hidden = np.array([W0[i][1] > (hit_y(bvhT, W0[i][0], W0[i][2]) or 9) + 0.001 if side[i] and dS2[i] < 0.03 else False for i in range(M_)])
    # everything an eye expression moves (the sliding upper lid reaches far above the rim) uses the eye map too
    moving = np.zeros(M_, bool)
    for k in keys:
        if k.startswith(('eye_', 'blink')) and 'brow' not in k: moving |= np.linalg.norm(KV[k][uids] - W0, axis=1) > 1e-4
    inside = side & (pocket | hidden | ~skin | moving) & (dS2 < 0.035)
    dIn = dist_to(flat(W0[inside]), flat(W0))
    w = np.where(inside, 1.0, 1 - smoothstep(dIn, 0.0, 0.010)) * side
    w_eye = np.maximum(w_eye, w)
    ring = np.nonzero(side & skin & ~inside & frontmost & (dIn > 0.010) & (dIn < 0.014))[0][::2]
    srcp = np.vstack([tpl_rims[s_]['dense'][:, [0, 2]], W0[ring][:, [0, 2]]])
    dstp = np.vstack([sim2_apply(eye_sim[s_], tpl_rims[s_]['dense'][:, [0, 2]]), Xgen[ring][:, [0, 2]]])
    fxz = tps2_fit(srcp, dstp)
    # depth shift: smooth fit to how far the general warp moved the visible skin around (not on) the rim
    fit = np.nonzero(side & skin & frontmost & ~pocket & (dS2 > 0.004) & (dS2 < 0.045))[0]
    fit = fit[::max(1, len(fit) // 350)]
    fdy = tps2_fit(W0[fit][:, [0, 2]], (Xgen[fit][:, 1] - W0[fit][:, 1])[:, None], lam=3e-6)
    eye_maps[s_] = (side, fxz, fdy)
    log['eye_ring_points_' + s_] = int(len(ring)); log['eye_region_verts_' + s_] = int(inside.sum())
def eye_region(P, Pgen):
    Q = Pgen.copy()
    for s_, (side, fxz, fdy) in eye_maps.items():
        ids = np.nonzero(side & (w_eye > 0))[0]
        xz = tps2_apply(fxz, P[ids][:, [0, 2]]); dy = tps2_apply(fdy, P[ids][:, [0, 2]])[:, 0]
        E = np.stack([xz[:, 0], P[ids][:, 1] + dy, xz[:, 1]], 1)
        w = w_eye[ids][:, None]; Q[ids] = w * E + (1 - w) * Pgen[ids]
    return Q
X = eye_region(W0, Xgen)

# ---------------------------------------------------------------- keep hidden card parts hidden
# lash / eye-white cards extend behind the lids; anything the template hides behind the skin (seen from the
# front) is pushed back behind the deformed skin by the same gap (up to 1.5 mm), per expression
tri = []
for f, m in zip(faces, fmat):
    if m == 0:
        for i in range(1, len(f) - 1): tri.append([f[0], f[i], f[i + 1]])
non = np.nonzero(~skin & (np.abs(W0[:, 2] - eyeTt[2]) < 0.05))[0]
def front_gap(P):
    bvh = BVHTree.FromPolygons([Vector(v) for v in P], tri)
    return np.array([(P[i][1] - (hit_y(bvh, P[i][0], P[i][2]) or 9)) for i in non])
def keep_hidden(Ptpl, Pdef):
    g0 = front_gap(Ptpl); g1 = front_gap(Pdef); Q = Pdef.copy()
    need = (g0 > 0) & (g0 < 0.02) & (g1 < np.minimum(g0, 0.0015))
    Q[non[need], 1] += np.minimum(g0[need], 0.0015) - g1[need]
    return Q, int(need.sum())
X, nfix = keep_hidden(W0, X); log['hidden_fix_basis'] = nfix

# ---------------------------------------------------------------- write basis + shape keys
def write(target_arr, arr_w):
    full = arr_w[wid]
    for i in range(N): target_arr[i].co = mwi @ Vector(full[i])
write(me.vertices, X)
if me.shape_keys:
    write(me.shape_keys.key_blocks[0].data, X)
    for k in keys:
        Tk = KV[k][uids]
        Xk = eye_region(Tk, tps_apply(model, Tk) + O)
        write(me.shape_keys.key_blocks[k].data, keep_hidden(Tk, Xk)[0])
me.update()
# the glTF import keeps the template's custom normals; on the new shape they shade as lumps, so drop them
bpy.context.view_layer.objects.active = head; head.select_set(True)
with bpy.context.temp_override(object=head, active_object=head, selected_objects=[head]):
    if me.has_custom_normals: bpy.ops.mesh.customdata_custom_splitnormals_clear()
for p_ in me.polygons: p_.use_smooth = True

# parts made for the template (hair, hats …) get the same space warp, so they fit the new head
def warp_space(P):
    Q = tps_apply(model, P)
    for f_ in fields: Q = Q + tps_apply(f_, Q)
    return Q
for name in EXTRA:
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != 'MESH': continue
    m_ = ob.matrix_world; mi_ = m_.inverted(); md = ob.data
    blocks = [md.vertices] + ([k.data for k in md.shape_keys.key_blocks] if md.shape_keys else [])
    for blk in blocks:
        P = np.array([tuple(m_ @ Vector(d.co)) for d in blk]); Q = warp_space(P)
        for d, q in zip(blk, Q): d.co = mi_ @ Vector(q)
    md.update()
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        if md.has_custom_normals: bpy.ops.mesh.customdata_custom_splitnormals_clear()
# bones that drive those parts (and the face) follow the same warp, so spring bones sit inside the new hair
arm = head.find_armature()
if arm is not None and EXTRA:
    bpy.context.view_layer.objects.active = arm
    with bpy.context.temp_override(object=arm, active_object=arm, selected_objects=[arm]):
        bpy.ops.object.mode_set(mode='EDIT')
        am = arm.matrix_world; ami = am.inverted(); top = float(W0[:, 2].min())
        for eb in arm.data.edit_bones:
            hd_, tl_ = am @ eb.head, am @ eb.tail
            if hd_.z < top - 0.01: continue          # body bones stay
            q = warp_space(np.array([tuple(hd_), tuple(tl_)]))
            eb.head, eb.tail = ami @ Vector(q[0]), ami @ Vector(q[1])
        bpy.ops.object.mode_set(mode='OBJECT')
log['extra_parts'] = EXTRA

# keep the target (scaled into template space) in the file for side-by-side checks
before = set(bpy.context.scene.objects)
bpy.ops.import_scene.fbx(filepath=TARGET)
t2 = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in before][0]
t2.matrix_world = Matrix.Translation(Vector(tr)) @ Matrix.Scale(sc, 4) @ t2.matrix_world
t2.name = 'target'; t2.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'wrap.blend'))
json.dump(log, open(os.path.join(OUT, 'wrap_log.json'), 'w'), indent=1)
print('WRAPLOG', json.dumps(log))
