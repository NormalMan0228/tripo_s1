"""Fair the eyelid edge loops of a P2 eye-fit base at rest (small loop edits only).
Rings = BFS rings of the outer skin from the margin (eyes_meta margin_vids), as loop_organs builds them.
1. Margin (ring 0): only its depth (y) is faired along the closed path (Taubin lambda 0.5 / mu -0.53, the canthi held),
   so it stays on the reference contour in the front view; its gap above the eyeball stays inside the band it had.
2. Rings 1..R (default 6): each vertex is faired along its own ring (Taubin over its same-ring mesh neighbours: bumps
   along the loop go, spacing evens out), weight 1 on rings 1-4 fading to 0 at ring R + 1; displacement capped at
   CAP (0.5 mm), rising smoothly to CAPC (1.0 mm) within CRAD (10 mm) of the canthi (stair-steps of the canthus folds); kept >= 0.47 mm (rings 1-3) / 0.32 mm off the eyeball sphere (eyes_meta C, r); a step that would turn
   a face by more than 60 deg is undone for its vertices.
2b. Canthus regions (within CRAD of a canthus, where the BFS rings are not concentric: folds, stair-steps): the outer skin
   is also faired as a surface (Taubin over all mesh neighbours, weight 1 at the canthus -> 0 at CRAD), same cap.
3. Left side computed, right side = exact mirror image; 'orig' and 'noface' alike; eyes_meta raw / up_path / lo_path
   and landmarks 12 / 14 refreshed from the faired margin (the canthi do not move); eyes_meta corner_vids (canthus
   vertices, outer / inner: loop_organs puts the lid-ring corners there) and canthus_tip (the visible inner tip of the
   eye = the reference's inner corner, apex of P2's caruncle wedge; organ_lib.wedge_close closes the wedge onto it);
   rig_points.json: the lid chains' end joints (lid.T.<s> head / lid.B.<s>.003 tail = outer, lid.B.<s> head /
   lid.T.<s>.003 tail = inner) exactly on the canthus vertices.
QA (lid_fair_qa.json): bumpiness per ring before / after (residual from a local quadratic fit along the ring, h 1.5 mm:
RMS / max mm), max displacement, moved vertices, turned faces, clearance.
Usage: blender -b --factory-startup -P lid_fair.py -- <base_dir> [--rings 6] [--iters 12] [--cap 0.5]
       (edits <base_dir>/base.blend, eyes_meta.json, landmarks.json in place; the caller keeps a copy)
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index('--') + 1:]; D = os.path.abspath(a[0]); opt = a[1:]
RR = int(opt[opt.index('--rings') + 1]) if '--rings' in opt else 6
IT = int(opt[opt.index('--iters') + 1]) if '--iters' in opt else 60
CAP = float(opt[opt.index('--cap') + 1]) / 1000 if '--cap' in opt else 0.0005
CAPC = float(opt[opt.index('--cap-canthus') + 1]) / 1000 if '--cap-canthus' in opt else 0.001
CRAD = float(opt[opt.index('--canthus-radius') + 1]) / 1000 if '--canthus-radius' in opt else 0.010
MM = 1000.0; MX = np.array([-1.0, 1, 1])
bpy.ops.wm.open_mainfile(filepath=os.path.join(D, 'base.blend')); bpy.context.preferences.filepaths.save_version = 0
ob = bpy.data.objects['orig']; nf = bpy.data.objects.get('noface')
X0 = np.array([tuple(v.co) for v in ob.data.vertices]); n = len(X0); F = [list(p.vertices) for p in ob.data.polygons]
EM = json.load(open(os.path.join(D, 'eyes_meta.json'))); LJ = json.load(open(os.path.join(D, 'landmarks.json')))
C = np.array(EM['L']['C']); r = float(EM['L']['r']); vids = [int(v) for v in EM['L']['margin_vids']]; vR = [int(v) for v in EM['R']['margin_vids']]
kd = KDTree(n)
for i, p in enumerate(X0): kd.insert(Vector(tuple(p)), i)
kd.balance(); part = np.array([kd.find(Vector((-p[0], p[1], p[2])))[1] for p in X0])
nbr = [[] for _ in range(n)]; E2F = {}
for fi, f in enumerate(F):
    for k in range(len(f)):
        a_, b_ = f[k], f[(k + 1) % len(f)]; E2F.setdefault((min(a_, b_), max(a_, b_)), []).append(fi)
for (a_, b_) in E2F: nbr[a_].append(b_); nbr[b_].append(a_)
# outer skin vs pocket (both eyes' margins block the face flood), as eye_fit_ref.py
cyc = {(min(c[i], c[(i + 1) % len(c)]), max(c[i], c[(i + 1) % len(c)])) for c in (vids, vR) for i in range(len(c))}
fadj = [[] for _ in F]
for e, fs in E2F.items():
    if e in cyc or len(fs) != 2: continue
    fadj[fs[0]].append(fs[1]); fadj[fs[1]].append(fs[0])
e0 = next((e for e in cyc if X0[e[0], 0] > 0 and len(E2F[e]) == 2), None); pocket_f = set()
if e0 is not None:
    comps = []
    for f0 in E2F[e0]:
        seen = {f0}; st = [f0]
        while st:
            f = st.pop()
            for g in fadj[f]:
                if g not in seen: seen.add(g); st.append(g)
        comps.append(seen)
    pocket_f = set() if comps[0] == comps[1] else min(comps, key=len)
outer_v = {v for fi, f in enumerate(F) if fi not in pocket_f for v in f}
mset = set(vids); left = X0[:, 0] > 1e-6
ring = {v: 0 for v in vids}; fr = list(vids)
for k in range(1, RR + 2):
    nx = []
    for v in fr:
        for w in nbr[v]:
            if w in outer_v and left[w] and w not in ring: ring[w] = k; nx.append(w)
    fr = nx
# canthi = the margin vertices at landmarks 13 (outer) / 11 (inner) (eye_fit_ref puts them on the margin's ends); they stay put
A = np.array(EM['L']['A']); A /= np.linalg.norm(A)
c_out = vids[int(np.argmin(np.linalg.norm(X0[vids] - np.array(LJ['13']), axis=1)))]; c_in = vids[int(np.argmin(np.linalg.norm(X0[vids] - np.array(LJ['11']), axis=1)))]
cant = {c_out, c_in}; Am = np.array([(1.0 if v == c_in else (-1.0 if v == c_out else 0.0)) for v in vids])


def lsmooth(P, s, h):
    out = np.empty_like(P)
    for i in range(len(P)):
        d = s - s[i]; w = np.exp(-0.5 * (d / h) ** 2); Am_ = np.c_[np.ones_like(d), d, d * d] * np.sqrt(w)[:, None]
        out[i] = np.linalg.lstsq(Am_, P * np.sqrt(w)[:, None], rcond=None)[0][0]
    return out


def ring_paths(X, k):
    """vertices of ring k ordered round the eye by the angle about the margin centre in the eye's front chart"""
    ids = np.array([v for v, kk in ring.items() if kk == k]); cen = X[vids].mean(0)
    view = cen - C; view /= np.linalg.norm(view); e1 = A - view * (A @ view); e1 /= np.linalg.norm(e1); e2 = np.cross(view, e1)
    ang = np.arctan2((X[ids] - cen) @ e2, (X[ids] - cen) @ e1); return ids[np.argsort(ang)]


def bumps(X):
    out = {}
    for k in range(0, RR + 1):
        ids = ring_paths(X, k); P = X[ids]; P = np.vstack([P[-3:], P, P[:3]])
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; R = np.linalg.norm(P - lsmooth(P, s, 0.0015), axis=1)[3:-3]
        out[str(k)] = {'rms': round(float(np.sqrt((R ** 2).mean()) * MM), 3), 'max': round(float(R.max() * MM), 3)}
    return out


qa = {'rings': RR, 'iters': IT, 'cap_mm': CAP * MM, 'bump_before': bumps(X0)}
X1 = X0.copy()
# ---- 1. margin depth along the closed path
m = np.array(vids); gm0 = np.linalg.norm(X0[m] - C, axis=1) - r; glo, ghi = float(gm0.min()), float(gm0.max())
hold = np.array([v in cant for v in vids])
y = X1[m, 1].copy()
for it in range(IT):
    for lam in (0.5, -0.53):
        L_ = 0.5 * (np.roll(y, 1) + np.roll(y, -1)) - y; y = np.where(hold, y, y + lam * L_)
X1[m, 1] = X0[m, 1] + np.clip(y - X0[m, 1], -CAP, CAP)                 # capped like the rings
d_ = X1[m] - C; g_ = np.linalg.norm(d_, axis=1) - r; bad = (g_ < glo) | (g_ > ghi)
if bad.any():                                                         # back into the band along y (front view unchanged)
    gt = np.clip(g_, glo, ghi); h2 = (r + gt) ** 2 - (X1[m, 0] - C[0]) ** 2 - (X1[m, 2] - C[2]) ** 2
    X1[m[bad], 1] = C[1] - np.sqrt(np.maximum(h2[bad], 0))
# ---- 2. rings 1..R along their own ring
rv = np.array([v for v, k in ring.items() if 1 <= k <= RR], int)
same = [[w for w in nbr[v] if ring.get(w, -1) == ring[v]] for v in rv]
wk = np.array([1.0 if ring[v] <= 4 else max(0.0, 1 - (ring[v] - 4) / (RR - 3)) for v in rv])
ok = np.array([len(s_) >= 2 for s_ in same]); wk = wk * ok
for it in range(IT):
    for lam in (0.5, -0.53):
        L_ = np.array([X1[s_].mean(0) - X1[v] if len(s_) else np.zeros(3) for v, s_ in zip(rv, same)])
        X1[rv] = X1[rv] + (lam * wk)[:, None] * L_
# displacement cap: CAP (0.5 mm) on the lids, rising to CAPC (1.0 mm) toward the canthi (within CRAD = 10 mm), where the
# stair-steps and bunched loops of the P2 canthus folds sit
dcan = np.min(np.linalg.norm(X0[rv][:, None] - X0[list(cant)][None], axis=2), 1); xq = np.clip(dcan / CRAD, 0, 1)
capv = CAP + (CAPC - CAP) * (1 - xq * xq * (3 - 2 * xq))
dv = X1[rv] - X0[rv]; dn = np.linalg.norm(dv, axis=1); sc = np.minimum(1.0, capv / np.maximum(dn, 1e-12)); X1[rv] = X0[rv] + dv * sc[:, None]
# ---- 2b. canthus regions: the BFS rings are not concentric there (folds, stair-steps), so the outer skin within CRAD of
# a canthus is also faired as a surface (Taubin over all its mesh neighbours, weight 1 at the canthus -> 0 at CRAD), same cap
cv_ = np.array([v for v in outer_v if left[v] and v not in mset and np.min(np.linalg.norm(X0[v] - X0[list(cant)], axis=1)) < CRAD], int)
if len(cv_):
    wc = 1 - np.clip(np.min(np.linalg.norm(X0[cv_][:, None] - X0[list(cant)][None], axis=2), 1) / CRAD, 0, 1); wc = wc * wc * (3 - 2 * wc)
    nbc = [[w for w in nbr[v] if w in outer_v] for v in cv_]
    for it in range(IT // 2):
        for lam in (0.5, -0.53):
            L_ = np.array([X1[b].mean(0) - X1[v] for v, b in zip(cv_, nbc)]); X1[cv_] = X1[cv_] + (lam * wc)[:, None] * L_
    allm = np.union1d(rv, cv_); dv = X1[allm] - X0[allm]; dn = np.linalg.norm(dv, axis=1)
    dcan2 = np.min(np.linalg.norm(X0[allm][:, None] - X0[list(cant)][None], axis=2), 1); xq2 = np.clip(dcan2 / CRAD, 0, 1)
    cap2 = CAP + (CAPC - CAP) * (1 - xq2 * xq2 * (3 - 2 * xq2)); X1[allm] = X0[allm] + dv * np.minimum(1.0, cap2 / np.maximum(dn, 1e-12))[:, None]
    rv = allm; ring.update({int(v): ring.get(int(v), RR + 1) for v in cv_})
fl = np.array([0.00047 if ring[v] <= 3 else 0.00032 for v in rv]); dC = X1[rv] - C; rC = np.linalg.norm(dC, axis=1)
inn = (rC < r + fl) & (dC[:, 1] < 0); X1[rv[inn]] = C + dC[inn] / rC[inn, None] * (r + fl[inn])[:, None]
# ---- turned faces: undo the vertices of faces turned > 60 deg
def fnorm(X, fl_):
    out = []
    for fi in fl_:
        f = F[fi]; P = X[f]; nn = sum(np.cross(P[k], P[(k + 1) % len(f)]) for k in range(len(f))); out.append(nn / max(np.linalg.norm(nn), 1e-18))
    return np.array(out)
mv = set(np.where(np.linalg.norm(X1 - X0, axis=1) > 1e-9)[0].tolist())
fm = [fi for fi, f in enumerate(F) if any(v in mv for v in f)]; undone = 0
for _ in range(5):
    dots = (fnorm(X0, fm) * fnorm(X1, fm)).sum(1); badf = [fi for fi, d_ in zip(fm, dots) if d_ < 0.5]
    if not badf: break
    vs = {v for fi in badf for v in F[fi] if v in mv and v not in mset}; undone += len(vs)
    for v in vs: X1[v] = 0.5 * (X1[v] + X0[v])
dots = (fnorm(X0, fm) * fnorm(X1, fm)).sum(1)
# ---- mirror, write
movedL = np.where((np.linalg.norm(X1 - X0, axis=1) > 0) & left)[0]
X1[part[movedL]] = X1[movedL] * MX
disp = np.linalg.norm(X1 - X0, axis=1)
gall = np.linalg.norm(X1[rv] - C, axis=1) - r
qa.update(bump_after=bumps(X1), max_disp_mm=round(float(disp.max() * MM), 3), moved_verts_left=int(len(movedL)),
          margin_depth_change_mm={'mean': round(float(np.abs(X1[m, 1] - X0[m, 1]).mean() * MM), 3), 'max': round(float(np.abs(X1[m, 1] - X0[m, 1]).max() * MM), 3)},
          margin_gap_mm=[round(float((np.linalg.norm(X1[m] - C, axis=1) - r).min() * MM), 3), round(float((np.linalg.norm(X1[m] - C, axis=1) - r).max() * MM), 3)],
          ring_clear_min_mm=round(float(gall.min() * MM), 3), faces_turned_gt60=int((dots < 0.5).sum()), faces_flipped=int((dots < 0).sum()), undone_verts=undone,
          canthus_move_mm=round(float(max(disp[v] for v in cant) * MM), 6))
for o in (ob, nf):
    if o is not None: o.data.vertices.foreach_set('co', X1.ravel()); o.data.update()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D, 'base.blend'), compress=True)
# eyes_meta / landmarks from the faired margin: same paths, new positions
def rs48(P):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; t = np.linspace(0, s[-1], 48)
    return np.stack([np.interp(t, s, P[:, j]) for j in range(3)], 1)
io_, ii_ = vids.index(c_out), vids.index(c_in)
nv = len(vids); p1 = [(io_ + k) % nv for k in range((ii_ - io_) % nv + 1)]; p2 = [(io_ - k) % nv for k in range((io_ - ii_) % nv + 1)]
Pn = X1[vids]; upi, loi = (p1, p2) if Pn[p1, 2].mean() > Pn[p2, 2].mean() else (p2, p1)
up48, lo48 = rs48(Pn[upi]), rs48(Pn[loi]); raw = np.r_[up48, lo48[::-1][1:-1]]
for s_, f in (('L', np.ones(3)), ('R', MX)):
    EM[s_]['up_path'] = (up48 * f).tolist(); EM[s_]['lo_path'] = (lo48 * f).tolist(); EM[s_]['raw'] = (raw * f).tolist()
    EM[s_]['lid_fair'] = {'source': 'lid_fair.py', 'rings': RR, 'iters': IT, 'cap_mm': CAP * MM}
# canthus vertices (corner_vids: outer, inner; loop_organs puts the ring corners there) and the visible inner tip of the
# eye (canthus_tip: the reference's inner corner, before eye_fit_ref's '--inner axis' cut; the apex of P2's caruncle
# wedge, where the closing lids end; None when it is the margin corner itself)
cvL = [vids[io_], vids[ii_]]; tipP = None
UVJ = os.path.join(D, '_work', 'eye_fit_uv.json')
if os.path.exists(UVJ):
    sys.path.append(os.path.dirname(os.path.abspath(__file__))); from eye_fit_ref import FrontMap
    U = json.load(open(UVJ)); FMp = FrontMap({int(k): np.array(v) for k, v in U['map']['LT'].items()}, {int(k): np.array(v) for k, v in U['map']['mp35'].items()})
    tipxz = FMp.inv(np.array(U['reference'])[47:48])[0]; Kc = X1[cvL[1]]
    cand = np.where((np.linalg.norm(X1[:, [0, 2]] - tipxz, axis=1) < 0.0012) & (np.abs(X1[:, 1] - Kc[1]) < 0.012) & left)[0]
    if len(cand):
        tv = int(cand[np.argmin(np.abs(X1[cand, 1] - Kc[1]))])
        if np.linalg.norm(X1[tv] - Kc) > 0.001: tipP = X1[tv]
for s_, f in (('L', np.ones(3)), ('R', MX)):
    EM[s_]['corner_vids'] = cvL if s_ == 'L' else [int(part[v]) for v in cvL]
    EM[s_]['canthus_tip'] = None if tipP is None else (tipP * f).tolist()
qa['canthus_tip_mm'] = None if tipP is None else (tipP * MM).round(2).tolist()
json.dump(EM, open(os.path.join(D, 'eyes_meta.json'), 'w'))
def arcmid(P):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; return np.array([np.interp(s[-1] / 2, s, P[:, j]) for j in range(3)])
LJ['12'] = arcmid(Pn[upi]).tolist(); LJ['14'] = arcmid(Pn[loi]).tolist(); LJ['8'] = (np.array(LJ['12']) * MX).tolist(); LJ['10'] = (np.array(LJ['14']) * MX).tolist()
json.dump(LJ, open(os.path.join(D, 'landmarks.json'), 'w'), indent=1)
qa['_rings'] = {nm: {str(k): (X[ring_paths(X, k)][:, [0, 2]] * MM).round(3).tolist() for k in range(0, RR + 1)} for nm, X in (('before', X0), ('after', X1))}
# rig points: the lid chains end exactly on the canthus vertices (rigify_fit places the chain joints along the margin
# ring between lid.T.<s> head (outer corner) and lid.B.<s> head (inner corner))
RPJ = os.path.join(D, 'rig_points.json')
if os.path.exists(RPJ):
    RP = json.load(open(RPJ)); J = RP['joints']; mvj = {}
    for s_, f in (('L', np.ones(3)), ('R', MX)):
        oc, ic = (X1[c_out] * f).tolist(), (X1[c_in] * f).tolist()
        for nm, k_, P_ in (('lid.T.%s' % s_, 0, oc), ('lid.B.%s.003' % s_, 1, oc), ('lid.B.%s' % s_, 0, ic), ('lid.T.%s.003' % s_, 1, ic)):
            if nm in J: mvj[nm + ('.head' if k_ == 0 else '.tail')] = round(float(np.linalg.norm(np.array(J[nm][k_]) - P_) * MM), 3); J[nm][k_] = P_
    RP['info']['lid_corners'] = {'note': 'lid chain ends on the canthus vertices (lid_fair.py)', 'moved_mm': mvj}
    json.dump(RP, open(RPJ, 'w'), indent=1); qa['rig_lid_corner_moves_mm'] = mvj
json.dump(qa, open(os.path.join(D, 'lid_fair_qa.json'), 'w'), indent=1)
print('LIDFAIR', json.dumps({k: qa[k] for k in ('max_disp_mm', 'moved_verts_left', 'margin_depth_change_mm', 'margin_gap_mm', 'ring_clear_min_mm', 'faces_turned_gt60', 'faces_flipped', 'undone_verts', 'canthus_move_mm')}),
      json.dumps({'before': {k: v['rms'] for k, v in qa['bump_before'].items()}, 'after': {k: v['rms'] for k, v in qa['bump_after'].items()}}))
