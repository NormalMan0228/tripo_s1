"""Extend the eye margin of a P2 eye-fit base through the caruncle wedge to the visible inner canthus tip.

eye_fit_ref.py '--inner axis' ended the lids at P2's inner corner Kc; medial of it P2 modelled the caruncle as a flat
triangular skin pocket (the wedge) whose apex is the visible inner tip of the eye (eyes_meta canthus_tip, lid_fair.py).
The user's rule: the rim splits into an upper and a lower line exactly at the two anchors (inner tip, outer canthus), and
when closed the lines meet edge to edge up to both anchors. So the margin is re-routed:
1. Reference lid curves (eye_fit_uv.json 'reference': the image contour before the axis cut) in the head frame (x, z)
   through eye_fit_ref.FrontMap; their parts medial of the current margin are the wedge's upper / lower edges.
2. Upper wedge path: cheapest edge path on the outer skin of the left side from the tip vertex to an upper-margin vertex
   at 60-85 % of the upper lid's arc (before eye_fit_ref's axis bend), cost = length * (1 + (front distance to the
   reference upper curve / 0.35 mm)^2) * (3 if hidden from the front) * (1 + (recess behind the smoothed skin / 0.4 mm)^2)
   * (1 + ((0.55 - facing the front)_+ / 0.15)^2) (the path goes round the caruncle pocket and its folded walls, so the
   whole pocket is cut away); lower wedge path the same with the lower
   curve and lower-margin vertices (60-90 %).
3. New margin cycle = upper margin (outer corner -> U0) + upper wedge path (U0 -> tip) + lower wedge path (tip -> L0) +
   lower margin (L0 -> outer corner); the skipped margin part and the wedge interior fall on the cut side (checked:
   the flood of the cut side must not leak). Right side = mirror image.
4. eyes_meta: margin_vids, corner_vids (outer, tip), A (outer -> tip), up_path / lo_path / raw, canthus_tip (now the
   margin corner itself), wedge = {upper / lower path vids, interior vids}; landmarks 9 / 11 = the tip, 8 / 10 / 12 / 14
   from the new paths; rig_points lid chain corners on the tip.
5. The wedge paths (extended laterally over the old margin down to 45 % of each lid, so the junction has no kink) are
   snapped onto the reference curves (front view; depth linear along the wedge part, kept on the old margin) and
   the outer skin within 2.5 mm follows with a smooth falloff, then the skin within 6.5 mm (full weight to 2.6 mm) is
   faired (Taubin, 60 rounds: P2's upper-lid fold over the wedge flattens)
   (small loop edit; mirror exact; flips counted).
QA: canthus_wedge_qa.json (path lengths, front deviation from the reference curves, cut-side faces).
Run after eye_fit_ref.py fit (needs _work/eye_fit_uv.json), before lid_fair.py. The tip: the reference's inner corner
-> nearest vertex in the front view (within 1.2 mm) at the margin corner's depth, moved onto the reference corner.
Usage: blender -b --factory-startup -P canthus_wedge.py -- <base_dir>      (tip = margin corner, e.g. f09 / f11: no change)
"""
import bpy, sys, os, json, heapq
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from eye_fit_ref import FrontMap, resample_open

a = sys.argv[sys.argv.index('--') + 1:]; D = os.path.abspath(a[0])
MM = 1000.0; MX = np.array([-1.0, 1, 1]); SIG = 0.00035
EM = json.load(open(os.path.join(D, 'eyes_meta.json'))); LJ = json.load(open(os.path.join(D, 'landmarks.json')))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D, 'base.blend')); bpy.context.preferences.filepaths.save_version = 0
ob = bpy.data.objects['orig']; X = np.array([tuple(v.co) for v in ob.data.vertices]); n = len(X); F = [list(p.vertices) for p in ob.data.polygons]
kd = KDTree(n)
for i, p in enumerate(X): kd.insert(Vector(tuple(p)), i)
kd.balance(); part = np.array([kd.find(Vector((-p[0], p[1], p[2])))[1] for p in X])
nbr = [[] for _ in range(n)]; E2F = {}
for fi, f in enumerate(F):
    for k in range(len(f)):
        a_, b_ = f[k], f[(k + 1) % len(f)]; E2F.setdefault((min(a_, b_), max(a_, b_)), []).append(fi)
for (a_, b_) in E2F: nbr[a_].append(b_); nbr[b_].append(a_)
ek = lambda a_, b_: (min(a_, b_), max(a_, b_))
vids = [int(v) for v in EM['L']['margin_vids']]
c_out = vids[int(np.argmin(np.linalg.norm(X[vids] - np.array(LJ['13']), axis=1)))]; c_in = vids[int(np.argmin(np.linalg.norm(X[vids] - np.array(LJ['11']), axis=1)))]
# the visible inner tip of the eye: the reference's inner corner (before eye_fit_ref's '--inner axis' cut) -> the vertex
# near it in the front view (within 1.2 mm) nearest the margin's inner corner in depth (the wedge apex)
U = json.load(open(os.path.join(D, '_work', 'eye_fit_uv.json')))
FM = FrontMap({int(k): np.array(v) for k, v in U['map']['LT'].items()}, {int(k): np.array(v) for k, v in U['map']['mp35'].items()})
R = FM.inv(np.array(U['reference'])); up_ref = R[:48]; lo_ref = np.r_[R[:1], R[48:][::-1], R[47:48]]
tipxz = up_ref[-1]; Kc = X[c_in]
cand = np.where((np.linalg.norm(X[:, [0, 2]] - tipxz, axis=1) < 0.0012) & (np.abs(X[:, 1] - Kc[1]) < 0.012) & (X[:, 0] > 1e-6))[0]
tv = int(cand[np.argmin(np.abs(X[cand, 1] - Kc[1]))]) if len(cand) else c_in
if np.linalg.norm(X[tv] - Kc) < 0.001:
    print('WEDGE', json.dumps({'changed': False, 'reason': 'the inner tip is the margin corner (no caruncle wedge)'})); sys.exit(0)


def split(cyc):
    """faces on the cut side of the cycle pair (left cycle + its mirror), as eye_fit_ref.split"""
    cR = [int(part[v]) for v in cyc]
    ce = {ek(c[i], c[(i + 1) % len(c)]) for c in (cyc, cR) for i in range(len(c))}
    if not all(e in E2F for e in ce): return None
    fadj = [[] for _ in F]
    for e, fs in E2F.items():
        if e in ce or len(fs) != 2: continue
        fadj[fs[0]].append(fs[1]); fadj[fs[1]].append(fs[0])
    e0 = next((e for e in ce if X[e[0], 0] > 0 and len(E2F[e]) == 2), None)
    if e0 is None: return set()
    comps = []
    for f0 in E2F[e0]:
        seen = {f0}; st = [f0]
        while st:
            f = st.pop()
            for g in fadj[f]:
                if g not in seen: seen.add(g); st.append(g)
        comps.append(seen)
    return set() if comps[0] == comps[1] else min(comps, key=len)


pocket0 = split(vids); outer_v = {v for fi, f in enumerate(F) if fi not in pocket0 for v in f}
# upper / lower margin paths (outer corner -> inner corner)
nv = len(vids); io, ii = vids.index(c_out), vids.index(c_in)
p1 = [vids[(io + k) % nv] for k in range((ii - io) % nv + 1)]; p2 = [vids[(io - k) % nv] for k in range((io - ii) % nv + 1)]
upm, lom = (p1, p2) if X[p1, 2].mean() > X[p2, 2].mean() else (p2, p1)
# front-visible vertices of the left outer skin
bvh = BVHTree.FromPolygons([tuple(p) for p in X], F)
def visible(v):
    p = X[v]; h = bvh.ray_cast(Vector((p[0], p[1] - 0.2, p[2])), Vector((0, 1, 0)))
    return h[0] is not None and (np.array(h[0]) - p) @ np.array([0, 1, 0]) > -0.0003
box = np.where((X[:, 0] > 1e-6) & (np.linalg.norm(X[:, [0, 2]] - X[c_in][[0, 2]], axis=1) < 0.015))[0]
vis = {int(v) for v in box if v in outer_v}                  # outer skin of the left side near the corner
seen = {v for v in vis if visible(v)}                        # front-visible ones are cheaper (the rim, not the overhang's underside)
# recess: how far a vertex lies behind the smoothed skin (the caruncle wedge is a pocket): paths go round the pocket so
# that the whole pocket falls on the cut side
vl = sorted(vis | set(vids)); pos = {v: i for i, v in enumerate(vl)}; Xs = X[vl].copy()
nb_l = [[pos[w] for w in nbr[v] if w in pos] for v in vl]
for _ in range(40):
    Xs = np.array([Xs[b].mean(0) if b else Xs[i] for i, b in enumerate(nb_l)]) * 0.5 + Xs * 0.5
recess = {v: float(X[v, 1] - Xs[pos[v], 1]) for v in vl}
VN = np.zeros_like(X)                                         # vertex normals (outward): steep / folded pocket walls face away
for f in F:
    P_ = X[f]; nn = sum(np.cross(P_[k], P_[(k + 1) % len(f)]) for k in range(len(f)))
    for v in f: VN[v] += nn
VN /= np.maximum(np.linalg.norm(VN, axis=1, keepdims=True), 1e-18)
if np.mean(((X - X.mean(0)) * VN).sum(1) > 0) < 0.5: VN = -VN
facing = {v: float(-VN[v, 1]) for v in vl}                    # 1 = faces the front camera
vis = (vis - set(vids)) | {tv}


def segdist(P, Q):
    A_, B_ = Q[:-1], Q[1:]; AB = B_ - A_; ll = np.maximum((AB * AB).sum(1), 1e-18)
    t = np.clip(((P[:, None] - A_[None]) * AB[None]).sum(2) / ll[None], 0, 1)
    return np.linalg.norm(P[:, None] - (A_[None] + t[..., None] * AB[None]), axis=2).min(1)


def wedge_path(ref, targets, avoid, t0=None):
    t0 = tv if t0 is None else t0
    nodes = vis | set(targets) | {t0}; d = {v: float(segdist(X[[v]][:, [0, 2]], ref)[0]) for v in nodes}
    dist = {t0: 0.0}; prev = {}; h = [(0.0, t0)]; tg = set(targets)
    while h:
        du, v = heapq.heappop(h)
        if du > dist[v]: continue
        if v in tg:
            p = [v]
            while p[-1] != t0: p.append(prev[p[-1]])
            return p[::-1], du
        for w in nbr[v]:
            if w not in nodes or w in avoid: continue
            c = float(np.linalg.norm(X[v] - X[w])) * (1 + ((d[v] + d[w]) / 2 / SIG) ** 2) * (1.0 if w in seen else 3.0)                 * (1 + (max(recess.get(w, 0.0), 0.0) / 0.0004) ** 2) * (1 + (max(0.55 - facing.get(w, 1.0), 0.0) / 0.15) ** 2)
            if du + c < dist.get(w, 1e18): dist[w] = du + c; prev[w] = v; heapq.heappush(h, (du + c, w))
    return None, None


def share(path, lo_, hi_):                               # margin vertices at a share of arc length (outer 0 -> inner 1)
    P = X[path]; s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; q = s_ / s_[-1]
    return [v for v, qq in zip(path, q) if lo_ <= qq <= hi_]
up_t = share(upm, 0.6, 0.85); lo_t = share(lom, 0.6, 0.9)                 # before eye_fit_ref's axis bend (last 25 %)


def snap_pred(path, ref):                                  # front-view move each path vertex would get from snap() (mm)
    P = X[path]; s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; q = s_ / max(s_[-1], 1e-12)
    e0 = P[-1][[0, 2]]; j0 = int(np.argmin(np.linalg.norm(ref - e0, axis=1)))
    sub = np.vstack([e0[None], ref[j0 + 1:], tipxz[None]])[::-1]
    ss = np.r_[0, np.cumsum(np.linalg.norm(np.diff(sub, axis=0), axis=1))]; ss /= ss[-1]
    Q = np.c_[np.interp(q, ss, sub[:, 0]), np.interp(q, ss, sub[:, 1])]
    return np.linalg.norm(Q - P[:, [0, 2]], axis=1) * MM


# the tip vertex: of the candidates near the reference tip, the one whose wedge paths need the smallest snap (a path
# that detours round the pocket would be folded back onto the reference curve -> flipped faces); ties -> deepest
tv_depth = tv; tip_scores = []
for c in sorted(set(cand.tolist()) | {tv}):
    a_, _ = wedge_path(up_ref, up_t, set(lom) - {c_in}, c)
    b_, _ = wedge_path(lo_ref, lo_t, (set(upm) - {c_in}) | set(a_[1:-1]), c) if a_ else (None, None)
    if a_ is None or b_ is None: continue
    sc = max(snap_pred(a_, up_ref).max(), snap_pred(b_, lo_ref).max())
    tip_scores.append((round(float(sc), 2), round(float(abs(X[c, 1] - Kc[1]) * MM), 2), int(c)))
tip_scores.sort()
if tip_scores and tip_scores[0][2] != tv and tip_scores[0][0] < [t for t in tip_scores if t[2] == tv][0][0] - 0.5: tv = tip_scores[0][2]
pu, cu = wedge_path(up_ref, up_t, set(lom) - {c_in})
pl, cl = wedge_path(lo_ref, lo_t, set(upm) - {c_in} | set(pu[1:-1]) if pu else set())
qa = {'tip_vertex': tv, 'tip_vertex_depth_rule': tv_depth, 'tip_scores_mm': tip_scores[:8], 'tip_to_P2_corner_mm': round(float(np.linalg.norm(X[tv] - X[c_in]) * MM), 2), 'skin_verts': len(vis), 'visible_verts': len(seen)}
if pu is None or pl is None: raise SystemExit('no wedge path ' + json.dumps(qa))
U0, L0 = pu[-1], pl[-1]                                  # where the wedge paths leave the old margin
new_up = upm[:upm.index(U0) + 1] + pu[::-1][1:]          # outer -> U0 -> ... -> tip
new_lo = lom[:lom.index(L0) + 1] + pl[::-1][1:]          # outer -> L0 -> ... -> tip
cyc = new_up + new_lo[::-1][1:-1]
if len(set(cyc)) != len(cyc): raise SystemExit('wedge cycle not simple ' + json.dumps(qa))
pocket = split(cyc)
if pocket is None: raise SystemExit('wedge cycle is not an edge cycle')
# dents (the cycle runs round 2-3 sides of one face kept on the skin side) are cut short: the face goes to the cut side
# (snapped onto smooth curves, a dent's middle vertices would flip that face); the tip and the outer corner stay
fset = {frozenset(f): fi for fi, f in enumerate(F)}; dents = 0; changed = True
while changed:
    changed = False; m_ = len(cyc)
    for i in range(m_):
        for k in (3, 2):
            seq = [cyc[(i + j) % m_] for j in range(k + 1)]; fi = fset.get(frozenset(seq))
            if fi is None or len(F[fi]) != k + 1 or fi in pocket or (min(seq[0], seq[-1]), max(seq[0], seq[-1])) not in E2F: continue
            drop = set(seq[1:-1])
            if tv in drop or c_out in drop: continue
            cyc = [v for v in cyc if v not in drop]; pu = [v for v in pu if v not in drop]; pl = [v for v in pl if v not in drop]
            new_up = [v for v in new_up if v not in drop]; new_lo = [v for v in new_lo if v not in drop]
            dents += 1; changed = True; pocket = split(cyc); break
        if changed: break
qa['dents_cut'] = dents
qa.update(upper_path_verts=len(pu), lower_path_verts=len(pl), margin_verts=[len(vids), len(cyc)],
          cut_faces=[len(pocket0), len(pocket)], wedge_faces=len(pocket) - len(pocket0),
          upper_front_dev_mm=round(float(segdist(X[pu][:, [0, 2]], up_ref).max() * MM), 3),
          lower_front_dev_mm=round(float(segdist(X[pl][:, [0, 2]], lo_ref).max() * MM), 3),
          U0_L0_to_P2_corner_mm=[round(float(np.linalg.norm(X[U0] - X[c_in]) * MM), 2), round(float(np.linalg.norm(X[L0] - X[c_in]) * MM), 2)])
if len(pocket) > len(pocket0) + 400 or len(pocket) < len(pocket0): raise SystemExit('wedge cut leaks / shrinks ' + json.dumps(qa))
wedge_in = sorted({v for fi in pocket - pocket0 for v in F[fi]} - set(cyc))
# ---- the wedge paths onto the reference curves: interior path vertices go to the reference curve (front view) at their
# share of arc length between the path ends (U0 / L0 fixed on the old margin, the tip fixed), depth blended linearly
# between the ends; the outer skin within RW (2.5 mm, geodesic) follows with a smooth falloff; small loop edit only
X0 = X.copy(); RW = 0.0025; FR, FIT = 2.6, 60              # skin fairing reach (x RW) and rounds
def snap(path, ref):
    P = X[path]; s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; q = s_ / s_[-1]
    e0 = P[-1][[0, 2]]; j0 = int(np.argmin(np.linalg.norm(ref - e0, axis=1)))       # the ref point nearest the margin end
    sub = np.vstack([ref[j0:], X[tv][None, [0, 2]]]) if j0 < len(ref) - 1 else np.vstack([ref[-1:], X[tv][None, [0, 2]]])
    sub = np.vstack([e0[None], sub[1:]]); sub = sub[::-1]                              # tip -> margin end
    ss = np.r_[0, np.cumsum(np.linalg.norm(np.diff(sub, axis=0), axis=1))]; ss /= ss[-1]
    for k_ in range(1, len(path) - 1):
        xz = np.array([np.interp(q[k_], ss, sub[:, 0]), np.interp(q[k_], ss, sub[:, 1])])
        y = (1 - q[k_]) * X[path[0], 1] + q[k_] * X0[path[-1], 1]
        X[path[k_]] = [xz[0], y, xz[1]]
X[tv] = [tipxz[0], X0[tv, 1], tipxz[1]]                  # the tip onto the reference corner (front view), depth kept
def ext(mpath, P0):                                        # old margin vertices lateral of the junction, down to share 0.45
    P = X[mpath]; s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; q = s_ / s_[-1]
    j = mpath.index(P0); return [v for v, qq in zip(mpath[:j][::-1], q[:j][::-1]) if qq >= 0.45]
eu, el = ext(upm, U0), ext(lom, L0)
snap(pu + eu, up_ref); snap(pl + el, lo_ref)               # the junction smoothed: the chain is re-spread along the curve
for v in eu + el: X[v, 1] = X0[v, 1]                       # old margin keeps its depth
moved = {v: X[v] - X0[v] for v in set(pu) | set(pl) | set(eu) | set(el) if np.linalg.norm(X[v] - X0[v]) > 1e-9}
outer_new = {v for fi, f in enumerate(F) if fi not in pocket for v in f}
mset = set(cyc)
if moved:
    src = list(moved); dist = {v: 0.0 for v in src}; own = {v: v for v in src}; h = [(0.0, v) for v in src]
    while h:
        du, v = heapq.heappop(h)
        if du > dist[v] or du > FR * RW: continue
        for w in nbr[v]:
            if w in mset or w not in outer_new or X0[w, 0] <= 1e-6: continue
            nd = du + float(np.linalg.norm(X0[v] - X0[w]))
            if nd < dist.get(w, 1e18): dist[w] = nd; own[w] = own[v]; heapq.heappush(h, (nd, w))
    for w, dw in dist.items():
        if w in moved: continue
        x_ = min(dw / RW, 1.0); X[w] = X0[w] + moved[own[w]] * (1 - x_ * x_ * (3 - 2 * x_))
    # the skin dragged with the wedge paths is faired (Taubin over its mesh neighbours, weight 1 near the paths -> 0 at
    # 1.6 RW): the snap leaves sharp creases where neighbouring path vertices moved differently
    reg = [w for w, dw in dist.items() if w not in mset and dw < FR * RW]
    if reg:
        wv = np.array([1 - max(dist[w] / (FR * RW) - 0.4, 0.0) / 0.6 for w in reg]); wv = wv * wv * (3 - 2 * wv)
        nbs = [[x for x in nbr[w] if x in outer_new] for w in reg]
        for _ in range(FIT):
            for lam in (0.5, -0.53):
                L_ = np.array([X[b].mean(0) - X[w] if b else np.zeros(3) for w, b in zip(reg, nbs)]); X[reg] = X[reg] + (lam * wv)[:, None] * L_
def fnorm(Xv, f):
    P_ = Xv[f]; nn = sum(np.cross(P_[k], P_[(k + 1) % len(f)]) for k in range(len(f))); return nn / max(np.linalg.norm(nn), 1e-18)
chg = np.where(np.linalg.norm(X - X0, axis=1) > 1e-9)[0]; cs = set(chg.tolist())
flipped = lambda: [fi for fi, f in enumerate(F) if fi not in pocket and X0[f, 0].min() > -1e-9 and any(v in cs for v in f) and fnorm(X0, f) @ fnorm(X, f) < 0.2]
flips0 = len(flipped()); untangle_rounds = 0
for untangle_rounds in range(80):                          # folds left by the snap: their vertices (and one ring) relaxed
    bad = flipped()
    if not bad: break
    vs = {v for fi in bad for v in F[fi]}; vs |= {w for v in list(vs) for w in nbr[v] if w in outer_new}
    vm = [v for v in vs if v in mset and v != tv and v != c_out]                  # margin vertices: depth only (front shape kept)
    vs = [v for v in vs if v not in mset and v != tv and X0[v, 0] > 1e-6]
    if not vs and not vm: break
    if vs: X[vs] = np.array([X[[w for w in nbr[v] if w in outer_new]].mean(0) for v in vs])
    if vm: X[vm, 1] = np.array([X[[w for w in nbr[v] if w in outer_new]][:, 1].mean() for v in vm])
    cs |= set(vs) | set(vm)
chg = np.array(sorted(cs), int)
flips = sum(1 for fi, f in enumerate(F) if fi not in pocket and X0[f, 0].min() > -1e-9 and any(v in cs for v in f) and fnorm(X0, f) @ fnorm(X, f) < 0)
qa['snap_flips_before_untangle'] = flips0; qa['snap_untangle_rounds'] = untangle_rounds
qa['snap_flip_dbg'] = [{'n': len(F[fi]), 'margin': sum(v in mset for v in F[fi]), 'tip': int(tv in F[fi]), 'tip_mm': round(float(np.linalg.norm(X0[F[fi]].mean(0) - X0[tv]) * MM), 1),
                        'area0_mm2': round(float(np.linalg.norm(sum(np.cross(X0[F[fi]][k], X0[F[fi]][(k + 1) % len(F[fi])]) for k in range(len(F[fi])))) / 2 * 1e6), 3),
                        'dot': round(float(fnorm(X0, F[fi]) @ fnorm(X, F[fi])), 2), 'in_pu_pl': sum(v in set(pu) | set(pl) for v in F[fi]),
                        'verts': [[int(v), 'U%d' % pu.index(v) if v in pu else ('L%d' % pl.index(v) if v in pl else ('M' if v in mset else 'S'))] for v in F[fi]],
                        'xz0': (X0[F[fi]][:, [0, 2]] * MM).round(2).tolist(), 'xz': (X[F[fi]][:, [0, 2]] * MM).round(2).tolist()} for fi in flipped()]
X[part[chg]] = X[chg] * MX
qa.update(snap_moved_verts_left=int(len(chg)), snap_max_mm=round(float(np.linalg.norm(X - X0, axis=1).max() * MM), 3), snap_flips=int(flips),
          upper_front_dev_after_mm=round(float(segdist(X[pu][:, [0, 2]], up_ref).max() * MM), 3), lower_front_dev_after_mm=round(float(segdist(X[pl][:, [0, 2]], lo_ref).max() * MM), 3))
for o in (ob, bpy.data.objects.get('noface')):
    if o is not None: o.data.vertices.foreach_set('co', X.ravel()); o.data.update()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D, 'base.blend'), compress=True)
# ---- eyes_meta, landmarks, rig points
def rs48(P):
    return resample_open(P, 48)
up48, lo48 = rs48(X[new_up]), rs48(X[new_lo]); raw = np.r_[up48, lo48[::-1][1:-1]]
A = X[tv] - X[c_out]; A /= np.linalg.norm(A)
for s, f in (('L', np.ones(3)), ('R', MX)):
    mp = (lambda v: v) if s == 'L' else (lambda v: int(part[v]))
    EM[s].update(margin_vids=[mp(v) for v in cyc], corner_vids=[mp(c_out), mp(tv)], A=(A * f).tolist(), up_path=(up48 * f).tolist(),
                 lo_path=(lo48 * f).tolist(), raw=(raw * f).tolist(), canthus_tip=(X[tv] * f).tolist(), margin_kind='path',
                 wedge={'upper_vids': [mp(v) for v in pu], 'lower_vids': [mp(v) for v in pl], 'interior_vids': [mp(v) for v in wedge_in],
                        'P2_corner_vid': mp(c_in), 'p2_corner_mm': round(float(np.linalg.norm(X[tv] - X[c_in]) * MM), 3),
                        'note': 'canthus_wedge.py: margin re-routed through the P2 caruncle wedge to the tip'})
json.dump(EM, open(os.path.join(D, 'eyes_meta.json'), 'w'))
def arcmid(P):
    s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; return np.array([np.interp(s_[-1] / 2, s_, P[:, j]) for j in range(3)])
LJ['11'] = X[tv].tolist(); LJ['9'] = (X[tv] * MX).tolist()
LJ['12'] = arcmid(X[new_up]).tolist(); LJ['14'] = arcmid(X[new_lo]).tolist(); LJ['8'] = (np.array(LJ['12']) * MX).tolist(); LJ['10'] = (np.array(LJ['14']) * MX).tolist()
LJ['_canthus_wedge'] = 'eye points 9 / 11 = visible inner canthus tip (canthus_wedge.py)'
json.dump(LJ, open(os.path.join(D, 'landmarks.json'), 'w'), indent=1)
RPJ = os.path.join(D, 'rig_points.json')
if os.path.exists(RPJ):
    RP = json.load(open(RPJ)); J = RP['joints']
    for s, f in (('L', np.ones(3)), ('R', MX)):
        for nm, k_ in (('lid.B.%s' % s, 0), ('lid.T.%s.003' % s, 1)):
            if nm in J: J[nm][k_] = (X[tv] * f).tolist()
    RP['info']['lid_corners_wedge'] = 'inner lid chain ends on the canthus tip (canthus_wedge.py)'
    json.dump(RP, open(RPJ, 'w'), indent=1)
ids = sorted({v for v in box})
qa['_fig'] = {'edges': [[int(a_), int(b_)] for (a_, b_) in E2F if a_ in vis and b_ in vis], 'X': {str(v): (X[v][[0, 2]] * MM).round(3).tolist() for v in set(ids) | vis},
              'old_margin': (X[vids][:, [0, 2]] * MM).round(3).tolist(), 'new_margin': (X[cyc][:, [0, 2]] * MM).round(3).tolist(),
              'up_ref': (up_ref * MM).round(3).tolist(), 'lo_ref': (lo_ref * MM).round(3).tolist(), 'tip': (X[tv][[0, 2]] * MM).tolist(), 'Kc': (X[c_in][[0, 2]] * MM).tolist(),
              'X0': {str(v): (X0[v][[0, 2]] * MM).round(3).tolist() for v in vl}, 'recess': {str(v): round(r_ * MM, 3) for v, r_ in recess.items()},
              'pu': [int(v) for v in pu], 'pl': [int(v) for v in pl], 'pocket_v': sorted({int(v) for fi in pocket for v in F[fi] if X0[v, 0] > 0 and str(v) in {str(w) for w in vl}})}
json.dump(qa, open(os.path.join(D, 'canthus_wedge_qa.json'), 'w'), indent=1)
print('WEDGE', json.dumps(qa))
