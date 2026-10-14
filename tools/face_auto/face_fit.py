"""Fit the universal MPFB head template to any prepared head and build expressions for that face.

Stages
 1. landmarks + eye rims (depth rays) + lip seam on both heads; scale/translate the target into template space
 2. thin-plate-spline warp from the correspondences, then non-rigid ICP over the whole skin (smoothed,
    mirrored every step) so the template takes the target's shape; exact left/right symmetry at the end
 3. eyeballs: sphere fitted to the target's eye surface (falls back to the warped template eye)
 4. expressions computed on THIS face, not copied:
      blink_L / blink_R : lid skin rotates about the eyeball centre until the upper margin meets the lower one
      jaw_open          : rotation about a pivot solved from MPFB's jawOpen motion, with jawOpen's weights
    plus MPFB keys carried over by the same warp for comparison (prefix mpfb_)
 5. QA numbers (fit error, symmetry, blink gap, lid/eyeball penetration) -> qa.json
Usage: blender -b --factory-startup -P face_fit.py -- <template_dir> <target.fbx> <target_landmarks.json> <out_dir>
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

sys.path.append(os.path.dirname(__file__))
from facelib import *

a = sys.argv[sys.argv.index("--") + 1:]
TPL, TARGET, TLM, OUT = a[:4]
os.makedirs(OUT, exist_ok=True)
TS = np.linspace(0, 1, 11)[1:-1]
log = {}

# ------------------------------------------------------------------ load template, then the target into it
bpy.ops.wm.open_mainfile(filepath=os.path.join(TPL, 'mpfb_head.blend'))
meta = json.load(open(os.path.join(TPL, 'mpfb_head.json')))
LTt = {int(k): np.array(v) for k, v in json.load(open(os.path.join(TPL, 'mpfb_head_landmarks.json'))).items() if not k.startswith('_')}
head = bpy.data.objects['head']; hm = head.data
parts = {n: bpy.data.objects[n] for n in ('eye_L', 'eye_R', 'teeth_up', 'teeth_lo', 'tongue', 'lash_L', 'lash_R') if n in bpy.data.objects}
H = np.array([tuple(v.co) for v in hm.vertices]); HF = [list(p.vertices) for p in hm.polygons]
mirror = np.array(meta['mirror'])
keys = [k.name for k in hm.shape_keys.key_blocks[1:]]
K = {k: np.array([tuple(d.co) for d in hm.shape_keys.key_blocks[k].data]) for k in keys}
PV = {n: np.array([tuple(v.co) for v in o.data.vertices]) for n, o in parts.items()}
PK = {n: {k.name: np.array([tuple(d.co) for d in k.data]) for k in o.data.shape_keys.key_blocks[1:]} if o.data.shape_keys else {} for n, o in parts.items()}

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=TARGET)
tgt = [o for o in bpy.data.objects if o not in before and o.type == 'MESH'][0]
SV = np.array([tuple(tgt.matrix_world @ v.co) for v in tgt.data.vertices]); SF = [list(p.vertices) for p in tgt.data.polygons]
LT = {int(k): np.array(v) for k, v in json.load(open(TLM)).items() if not k.startswith('_')}
bvhS0 = bvh_of(SV, SF); bvhH = bvh_of(H, HF)

# ------------------------------------------------------------------ eye rims, lip seams, landmarks
def rims(bvh, L, mode):
    out = {}
    for side, ids in {'R': (7, 8, 9, 10), 'L': (13, 12, 11, 14)}.items():
        cx, cz = np.mean([L[k][0] for k in ids]), np.mean([L[k][2] for k in ids])
        out[side] = lids(recentred_rim(bvh, cx, cz, mode), TS)
    return out
tgt_rims = rims(bvhS0, LT, 'margin')
tpl_rims = rims(bvhH, LTt, 'pocket')
def seam(bvh, L): return seam_curve(bvh, L[20][0], L[22][0], L[20][2], (L[34][2] + L[35][2]) / 2, L[22][2])
tgt_seam, tpl_seam = seam(bvhS0, LT), seam(bvhH, LTt)
def midline_rules(V):
    M = V[np.abs(V[:, 0]) < 0.004]; return {'crown': M[np.argmax(M[:, 2])], 'back': M[np.argmax(M[:, 1])]}
tgt_rule, tpl_rule = midline_rules(SV), midline_rules(H)

src, dst, tag = [], [], []
def add(p, q, t): src.append(np.asarray(p, float)); dst.append(np.asarray(q, float)); tag.append(t)
for s in 'RL':
    add(tpl_rims[s]['outer'], tgt_rims[s]['outer'], 'eye_outer'); add(tpl_rims[s]['inner'], tgt_rims[s]['inner'], 'eye_inner')
    for p, q in zip(tpl_rims[s]['up'], tgt_rims[s]['up']): add(p, q, 'lid')
    for p, q in zip(tpl_rims[s]['lo'], tgt_rims[s]['lo']): add(p, q, 'lid')
add(tpl_seam[0], tgt_seam[0], 'mouth'); add(tpl_seam[-1], tgt_seam[-1], 'mouth')
for p, q in zip(resample(tpl_seam, TS), resample(tgt_seam, TS)): add(p, q, 'seam')
for k in (1, 2, 3, 4, 5, 6): add(LTt[k], LT[k], 'brow')
add(LTt[16], LT[16], 'nose'); add(LTt[24], LT[24], 'chin')
for k in tpl_rule: add(tpl_rule[k], tgt_rule[k], k)
src, dst = np.array(src), np.array(dst)
use = [i for i, t in enumerate(tag) if t in ('eye_outer', 'eye_inner', 'mouth', 'nose', 'chin', 'crown')]
A_, B_ = dst[use], src[use]; am, bm_ = A_.mean(0), B_.mean(0)
sc = float(((A_ - am) * (B_ - bm_)).sum() / ((A_ - am) ** 2).sum()); tr = bm_ - sc * am
dst_t = dst * sc + tr; SVt = SV * sc + tr; bvhS = bvh_of(SVt, SF)
# the Tripo eye is fused to the lids: template skin must never snap onto that eyeball surface
SFc = np.array([SVt[f].mean(0) for f in SF])
eye_faces = np.zeros(len(SF), bool)
for s in 'RL':
    R = tgt_rims[s]['raw'] * sc + tr
    eye_faces |= inside2d(R, SFc) & (SFc[:, 1] < R[:, 1].mean() + 0.006)
bvhSkin = bvh_of(SVt, [f for f, e in zip(SF, eye_faces) if not e])
log['target_eye_faces_excluded'] = int(eye_faces.sum())
for s in 'RL':
    for k in ('outer', 'inner', 'up', 'lo', 'raw', 'up_path', 'lo_path'): tgt_rims[s][k] = tgt_rims[s][k] * sc + tr
tgt_seam_t = tgt_seam * sc + tr
log['scale_target_to_template'] = sc

# ------------------------------------------------------------------ warp + non-rigid ICP (symmetric)
model = tps_fit(src, dst_t, lam=1e-6)
Wb = tps_apply(model, H); X = Wb.copy()
pocket = np.zeros(len(H), bool)
for s in 'RL':
    R = tpl_rims[s]['raw']; pocket |= inside2d(R, H) & (H[:, 1] > R[:, 1].min() - 0.001)
front_y = np.array([(hit_y(bvhH, p[0], p[2]) or 9) if abs(p[0]) < 0.04 and abs(p[2] - tpl_seam[15][2]) < 0.025 else 9 for p in H])
cavity = H[:, 1] > front_y + 0.003
d_rim = dist_to(np.vstack([tpl_rims['R']['raw'], tpl_rims['L']['raw']]), H); d_seam = dist_to(tpl_seam, H)
active = ~pocket & ~cavity & (d_rim > 0.003) & (d_seam > 0.002)
nbrs = neighbours(len(H), HF)
for it in range(24):
    nX = vnormals(X, HF); D = np.zeros_like(X)
    for i in np.nonzero(active)[0]:
        loc, n, idx, d = bvhSkin.find_nearest(Vector(X[i]))
        if loc is None or d > 0.02 or n.dot(Vector(nX[i])) < 0.3: continue
        D[i] = np.array(loc) - X[i]
    D = laplace(D, nbrs, max(2, 12 - it // 2))
    D = (D + D[mirror] * [-1, 1, 1]) / 2
    X += 0.7 * D
X = mirror_x(X, mirror)
err = [bvhSkin.find_nearest(Vector(X[i]))[3] for i in np.nonzero(active)[0]]
log['fit_error_mm'] = {'mean': float(np.mean(err) * 1000), 'p95': float(np.percentile(err, 95) * 1000)}

# ------------------------------------------------------------------ eyelids: every margin vertex onto the target rim
# margin = template skin vertices on the edge of the eye socket (next to a socket vertex). Each one is pinned to the
# target rim at the same arc position (corners matched); the lid skin around it follows by harmonic interpolation
# of the displacement, so a human-size lid can stretch to a big cartoon eye without tearing.
margins = {}
for s in 'RL':
    side = (H[:, 0] < 0) if s == 'R' else (H[:, 0] > 0)
    R = tpl_rims[s]['raw']; pk = side & inside2d(R, H) & (H[:, 1] > R[:, 1].min() - 0.001)
    # one clean row: for each rim ray point (already ordered around the eye) the nearest non-socket vertex, seen
    # from the front; duplicates dropped, order kept
    cand = np.nonzero(side & ~pk)[0]; M = []
    for q in R:
        j = int(cand[np.argmin(((H[cand][:, [0, 2]] - q[[0, 2]]) ** 2).sum(1) + 4 * (H[cand][:, 1] - q[1]) ** 2)])
        if not M or (j != M[-1] and j not in M): M.append(j)
    M = np.array(M)
    L = lids(H[M], TS)                                   # corners/paths on the template margin itself
    io = int(np.argmin(np.linalg.norm(H[M] - L['outer'], axis=1))); ii = int(np.argmin(np.linalg.norm(H[M] - L['inner'], axis=1)))
    p1, p2 = split_idx(len(M), io, ii)
    up, lo_ = (p1, p2) if H[M[p1]][:, 2].mean() > H[M[p2]][:, 2].mean() else (p2, p1)
    goal = {}
    for path, tpath in ((up, tgt_rims[s]['up_path']), (lo_, tgt_rims[s]['lo_path'])):
        P = H[M[path]]; seg = np.linalg.norm(np.diff(P, axis=0), axis=1); t = np.concatenate([[0], np.cumsum(seg)]); t /= t[-1]
        Q = resample(tpath, t)
        for j, q in zip(path, Q): goal[int(M[j])] = q
    region = side & (pk | (dist_to(H[M] * [1, 0, 1], H * [1, 0, 1]) < 0.012))
    fixed = {i: X[i] for i in np.nonzero(~region)[0] if region[nbrs[i]].any()}
    fixed.update(goal)
    free = [i for i in np.nonzero(region)[0] if i not in fixed]
    D = np.zeros_like(X)
    for i, q in goal.items(): D[i] = q - X[i]
    for _ in range(600):
        for i in free: D[i] = D[nbrs[i]].mean(0)
    X[np.nonzero(region)[0]] += D[np.nonzero(region)[0]]
    margins[s] = {'all': M, 'up': M[up], 'lo': M[lo_], 'pocket': pk}
    log['margin_verts_' + s] = int(len(M))
X = mirror_x(X, mirror)

# smooth space warp (template space -> fitted) for eyes, teeth, tongue, lashes and pivots
sub = np.arange(0, len(H), max(1, len(H) // 900))
field = tps_fit(H[sub], (X - H)[sub], lam=1e-5)
def warp(P): return P + tps_apply(field, P)

# ------------------------------------------------------------------ eyeballs
eyes = {}
for s, nm in (('R', 'eye_R'), ('L', 'eye_L')):
    C0, r0 = sphere_fit(PV[nm])
    R = tgt_rims[s]['raw']; c = R.mean(0); inner = c + (R - c) * 0.7
    pts = []
    for u in np.linspace(0, 1, 9):
        for v in np.linspace(0, 1, 9):
            x = inner[:, 0].min() + u * (inner[:, 0].max() - inner[:, 0].min()); z = inner[:, 2].min() + v * (inner[:, 2].max() - inner[:, 2].min())
            if inside2d(inner, np.array([[x, 0, z]]))[0]:
                y = hit_y(bvhS, x, z)
                if y is not None: pts.append([x, y, z])
    width_ratio = np.linalg.norm(tgt_rims[s]['outer'] - tgt_rims[s]['inner']) / np.linalg.norm(tpl_rims[s]['outer'] - tpl_rims[s]['inner'])
    Cw = warp(C0[None])[0]; rw = r0 * width_ratio
    Ct, rt = sphere_fit(np.array(pts)) if len(pts) > 12 else (Cw, 0)
    ok = 0.7 * rw < rt < 2.2 * rw and np.linalg.norm(Ct - Cw) < rw
    C, r = (Ct, rt) if ok else (Cw, rw)
    eyes[s] = {'C': C, 'r': r, 'C0': C0, 'r0': r0, 'from_target': bool(ok)}
    log['eye_' + s] = {'radius_mm': r * 1000, 'from_target_surface': bool(ok), 'width_ratio': float(width_ratio)}
newPV = {}
for n, P in PV.items():
    if n.startswith('eye_'):
        e = eyes[n[-1]]; newPV[n] = e['C'] + (P - e['C0']) * (e['r'] / e['r0'])
    else:
        newPV[n] = warp(P)
# lid skin must stay outside the eyeball
for s, e in eyes.items():
    sk = margins[s]['pocket']; d = np.linalg.norm(X - e['C'], axis=1)
    bad = (d < e['r'] + 0.0004) & ~pocket & ~sk & (np.abs(X[:, 0] - e['C'][0]) < 2 * e['r'])
    X[bad] = e['C'] + (X[bad] - e['C']) / d[bad, None] * (e['r'] + 0.0004)
    # socket lining: onto a shell just inside the eyeball, so it never shows or folds over the lid
    X[sk] = e['C'] + (X[sk] - e['C']) / np.linalg.norm(X[sk] - e['C'], axis=1)[:, None] * (0.97 * e['r'])
    # relax the stretched lid skin (margin pinned), keeping it on or outside the eyeball
    lid = (~sk) & (np.linalg.norm(X - e['C'], axis=1) < 1.5 * e['r']) & (np.abs(X[:, 0] - e['C'][0]) < 2 * e['r'])
    pin = set(margins[s]['all'].tolist()); ids = [i for i in np.nonzero(lid)[0] if i not in pin]
    for _ in range(8):
        for f_ in (0.5, -0.53):
            avg = np.array([X[nbrs[i]].mean(0) for i in ids]); X[ids] += f_ * (avg - X[ids])
        d = np.linalg.norm(X - e['C'], axis=1); bad = lid & (d < e['r'] + 0.0004)
        X[bad] = e['C'] + (X[bad] - e['C']) / d[bad, None] * (e['r'] + 0.0004)
X = mirror_x(X, mirror)

# ------------------------------------------------------------------ expressions computed on this face
eye_defs = {}
for s in 'RL':
    R = tgt_rims[s]; A = R['inner'] - R['outer']; A /= np.linalg.norm(A)
    eye_defs[s] = {'C': eyes[s]['C'], 'A': A, 'up_path': X[margins[s]['up']], 'lo_path': X[margins[s]['lo']],
                   'reach': 0.45, 'r': eyes[s]['r']}
new_keys = {}
def relax_key(Pk, s, rounds=6):
    """Corrective pass on a computed expression: Taubin-smooth only the vertices it moved (plus one ring), then keep
    them on or outside the eyeball, so the closing line has no spikes."""
    e = eyes[s]; moved = np.linalg.norm(Pk - X, axis=1) > 1e-5
    ring = moved.copy()
    for i in np.nonzero(moved)[0]: ring[nbrs[i]] = True
    ids = np.nonzero(ring & ~margins[s]['pocket'])[0]; ids = ids[~np.isin(ids, margins[s]['all'])]   # margins stay where the blink put them
    for _ in range(rounds):
        for f_ in (0.5, -0.53):
            avg = np.array([Pk[nbrs[i]].mean(0) for i in ids]); Pk[ids] += f_ * (avg - Pk[ids])
        d = np.linalg.norm(Pk[ids] - e['C'], axis=1); bad = d < e['r'] + 0.0004
        Pk[ids[bad]] = e['C'] + (Pk[ids[bad]] - e['C']) / d[bad, None] * (e['r'] + 0.0004)
    return Pk
for s, nm in (('L', 'blink_L'), ('R', 'blink_R')):
    new_keys[nm] = {'head': relax_key(blink_field(X, eye_defs[s]), s)}
    for ln in ('lash_' + s,):
        if ln in newPV: new_keys[nm][ln] = blink_field(newPV[ln], eye_defs[s])
# jaw: pivot and weights from MPFB's own jawOpen motion, rotation recomputed on the fitted shape
dj = K['jawOpen'] - H; mag = np.linalg.norm(dj, axis=1); w = np.clip(mag / np.percentile(mag[mag > 1e-6], 98), 0, 1)
sel = w > 0.8
Ay = np.c_[-H[sel, 2], np.ones(sel.sum()), np.zeros(sel.sum())]; Az = np.c_[H[sel, 1], np.zeros(sel.sum()), -np.ones(sel.sum())]
sol, *_ = np.linalg.lstsq(np.vstack([Ay, Az]), np.concatenate([dj[sel, 1], dj[sel, 2]]), rcond=None)
th = sol[0]; Jz, Jy = sol[1] / th, sol[2] / th
J = warp(np.array([[0.0, Jy, Jz]]))[0]
log['jaw_pivot_template'] = [0.0, float(Jy), float(Jz)]; log['jaw_angle_mpfb_deg'] = float(np.degrees(th))
def rot_x(P, piv, ang):
    c, s_ = np.cos(ang), np.sin(ang); d = P - piv
    return piv + np.c_[d[:, 0], d[:, 1] * c - d[:, 2] * s_, d[:, 1] * s_ + d[:, 2] * c]
ANG = math.radians(18)
jaw = X.copy()
for i in np.nonzero(w > 1e-3)[0]: jaw[i] = rot_x(X[i:i + 1], J, ANG * w[i])[0]
new_keys['jaw_open'] = {'head': jaw}
for n in ('teeth_lo', 'tongue'):
    if n in newPV: new_keys['jaw_open'][n] = rot_x(newPV[n], J, ANG)
# MPFB keys carried by the warp (what every "copy the template's expression" pipeline does)
off = X - Wb
for k in ('eyeBlinkLeft', 'eyeBlinkRight', 'jawOpen', 'viseme_aa', 'viseme_I', 'viseme_U', 'viseme_E', 'viseme_O', 'mouthSmileLeft', 'mouthSmileRight'):
    if k not in K: continue
    new_keys['mpfb_' + k] = {'head': mirror_x(tps_apply(model, K[k]) + off, mirror) if k[-4:] not in ('Left', 'ight') else tps_apply(model, K[k]) + off}
    for n in PK:
        if k in PK[n]:
            new_keys['mpfb_' + k][n] = (PK[n][k] - PV[n]) * (eyes[n[-1]]['r'] / eyes[n[-1]]['r0'] if n.startswith('eye_') else 1) + newPV[n]

# ------------------------------------------------------------------ QA
def blink_gap(s, Pk):
    """Largest distance between the upper and lower lid margins (paired along the eye axis, corners excluded)."""
    A = eye_defs[s]['A']; up, lo_ = margins[s]['up'], margins[s]['lo']
    su, sl = X[up] @ A, X[lo_] @ A; span = su.max() - su.min(); mid = np.abs(su - (su.max() + su.min()) / 2) < 0.4 * span
    pair = [lo_[int(np.argmin(np.abs(sl - v)))] for v in su[mid]]
    return float(np.max(np.linalg.norm(Pk[up[mid]] - Pk[pair], axis=1)) * 1000)
def inside_eye(Pk, s):
    e = eyes[s]; d = np.linalg.norm(Pk - e['C'], axis=1); return int(((d < e['r'] - 0.0003) & ~pocket & ~margins[s]['pocket']).sum())
qa = {}
for s, nm, mk in (('L', 'blink_L', 'mpfb_eyeBlinkLeft'), ('R', 'blink_R', 'mpfb_eyeBlinkRight')):
    qa['blink_gap_mm_' + s] = {'procedural': blink_gap(s, new_keys[nm]['head']), 'mpfb_copied': blink_gap(s, new_keys[mk]['head']) if mk in new_keys else None,
                               'open': blink_gap(s, X)}
    qa['lid_inside_eyeball_' + s] = {'neutral': inside_eye(X, s), 'procedural_blink': inside_eye(new_keys[nm]['head'], s),
                                     'mpfb_blink': inside_eye(new_keys[mk]['head'], s) if mk in new_keys else None}
qa['symmetry_max_mm'] = float(np.max(np.linalg.norm(X - X[mirror] * [-1, 1, 1], axis=1)) * 1000)
qa.update(log)

# ------------------------------------------------------------------ write
def set_obj(ob, P, keyset):
    if ob.data.shape_keys:
        ob.active_shape_key_index = 0
        for kb_ in list(ob.data.shape_keys.key_blocks)[::-1]: ob.shape_key_remove(kb_)
    for v, p in zip(ob.data.vertices, P): v.co = Vector(p)
    if keyset:
        ob.shape_key_add(name='Basis')
        for nm, Pk in keyset.items():
            kb_ = ob.shape_key_add(name=nm)
            for d, p in zip(kb_.data, Pk): d.co = Vector(p)
    ob.data.update()
set_obj(head, X, {nm: v['head'] for nm, v in new_keys.items()})
for n, ob in parts.items():
    set_obj(ob, newPV[n], {nm: v[n] for nm, v in new_keys.items() if n in v})
tgt.data.transform(Matrix.Translation(Vector(tr)) @ Matrix.Scale(sc, 4)); tgt.name = 'target'; tgt.hide_render = True
json.dump(qa, open(os.path.join(OUT, 'qa.json'), 'w'), indent=1)
json.dump({'tgt_rims': {s: tgt_rims[s]['raw'].tolist() for s in 'RL'}, 'tpl_rims': {s: tpl_rims[s]['raw'].tolist() for s in 'RL'},
           'src': src.tolist(), 'dst': dst_t.tolist(), 'tag': tag, 'eyes': {s: {'C': e['C'].tolist(), 'r': e['r']} for s, e in eyes.items()},
           'jaw_pivot': J.tolist()}, open(os.path.join(OUT, 'fit_debug.json'), 'w'))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'fit.blend'))
print('QA', json.dumps(qa))
