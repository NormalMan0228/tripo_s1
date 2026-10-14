"""T14 · rig points (Rigify face joints) for any head from dense landmarks, through a human template.

template mode (once): place the 92 face joints of the Rigify human metarig on the CC0 MPFB head template:
  similarity + thin-plate spline from the metarig's own joint layout to the template through 29 semantic pairs
  (eye corners and lid midpoints from MediaPipe eye contours, brows, nose tip, mouth corners, lip centres, chin,
  crown), joints snapped to the surface, exactly symmetric. The template's jaw pivot is solved from its jawOpen
  shape (least-squares rotation about the left-right axis). Writes data/rig_template.json with the joints and
  the template's dense MediaPipe points.
head mode: dense MediaPipe points of the head <-> the same point numbers on the template (about 300 pairs):
  similarity, then a regularised thin-plate spline carries every template joint onto the head; joints are snapped
  to the surface; lid rings go onto the head's own eye contour (MediaPipe or depth rim), lip joints onto its lip
  line, ear loops onto the ears found in a side height map; the jaw pivot is carried like the joints; left/right
  averaged. Writes <out>.json (head/tail per joint, residuals) and renders
  front + 3/4 overlays on the textured head.
Usage:
  blender -b tpl_face.blend -P rig_points.py -- template <tpl_dense.json> <tpl_landmarks.json> <metarig.json> <mpfb_head.blend>
  blender -b <head_tex.blend> -P rig_points.py -- head <dense.json> <landmarks.json> <out.json>
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facelib import tps_fit, tps_apply, recentred_rim, lids

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, 'data')
a = sys.argv[sys.argv.index('--') + 1:]; MODE = a[0]
# MediaPipe numbers used semantically
EYE_R = {'outer': 33, 'inner': 133, 'up': [246, 161, 160, 159, 158, 157, 173], 'lo': [7, 163, 144, 145, 153, 154, 155]}
EYE_L = {'outer': 263, 'inner': 362, 'up': [466, 388, 387, 386, 385, 384, 398], 'lo': [249, 390, 373, 374, 380, 381, 382]}
LIP = {'corner_R': 78, 'corner_L': 308, 'up_c': 13, 'lo_c': 14}

face = bpy.data.objects['face']
eyes = bpy.data.objects.get('eyes')
def rest(o):
    if o.data.shape_keys: return np.array([tuple(p.co) for p in o.data.shape_keys.key_blocks[0].data])
    return np.array([tuple(v.co) for v in o.data.vertices])
X = rest(face); F = [list(p.vertices) for p in face.data.polygons]
bvh_face = BVHTree.FromPolygons([tuple(p) for p in X], F)
if eyes:
    E = rest(eyes); FE = [[i + len(X) for i in p.vertices] for p in eyes.data.polygons]
    bvh_all = BVHTree.FromPolygons([tuple(p) for p in np.r_[X, E]], F + FE)
else:
    bvh_all = bvh_face
def snap(p): h = bvh_face.find_nearest(Vector(p)); return np.array(h[0]) if h[0] is not None else np.asarray(p)
def dense_pts(js):
    d = json.load(open(js)); return {int(k): np.array(v) for k, v in d.items() if not k.startswith('_')}
def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); A0, B0 = A - ma, B - mb
    U, D, Vt = np.linalg.svd(B0.T @ A0 / len(A)); Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ Sg @ Vt; s = np.trace(np.diag(D) @ Sg) / (A0 ** 2).sum(1).mean(); return s, R, mb - s * R @ ma
def symmetrise(J):
    out = {}
    for n, (h, t) in J.items():
        m = n.replace('.L', '.R') if '.L' in n else (n.replace('.R', '.L') if '.R' in n else None)
        if m and m in J:
            hm, tm = J[m]; mir = np.array([-1, 1, 1])
            out[n] = ((h + hm * mir) / 2, (t + tm * mir) / 2)
        else:
            h2, t2 = h.copy(), t.copy(); h2[0] = 0; t2[0] = 0; out[n] = (h2, t2)
    return out
SKIN = ('brow', 'lid', 'lip', 'cheek', 'forehead', 'temple', 'jaw.', 'chin', 'ear', 'nose')

def find_ear(LT, sgn):
    """The ear on one side (sgn +1 = left, +x): a side height map (rays from the side, one per (y, z) cell behind the
    outer eye corner, between mouth and well above the brow) minus its grey opening by a square of 0.35 x face height: the
    skull and jaw stay, narrow bumps remain. The ear is the strongest connected bump higher than 3.5 % of the face
    height. Returns its box (y, z), outer x, base x and its outer surface points, or None."""
    top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]
    eye = LT[13] if sgn > 0 else LT[7]
    z_lo = min(LT[20][2], LT[22][2]) - 0.1 * fh if 20 in LT and 22 in LT else LT[24][2]
    cell = fh / 80
    ys = eye[1] + (np.arange(int(1.2 * fh / cell)) + 0.5) * cell; zs = z_lo + (np.arange(int((top + 0.6 * fh - z_lo) / cell)) + 0.5) * cell
    ny, nz = len(ys), len(zs)
    H = np.full((nz, ny), np.nan); HP = np.full((nz, ny, 3), np.nan)
    for i, z in enumerate(zs):                           # side rays: works on any mesh density
        for j, y in enumerate(ys):
            h = bvh_face.ray_cast(Vector((sgn * 1.0, y, z)), Vector((-sgn, 0, 0)))
            if h[0] is not None and sgn * h[0].x > 0.3 * abs(eye[0]): H[i, j] = sgn * h[0].x; HP[i, j] = tuple(h[0])
    if np.isfinite(H).sum() < 50: return None
    H[~np.isfinite(H)] = np.nanmin(H)
    k = max(3, int(0.35 * fh / cell))
    def run(A, f, axis):
        Ap = np.pad(A, [(k // 2, k // 2) if ax == axis else (0, 0) for ax in range(2)], mode='edge')
        return f(np.stack([np.take(Ap, range(i, i + A.shape[axis]), axis=axis) for i in range(k)]), 0)
    Op = run(run(run(run(H, np.min, 0), np.min, 1), np.max, 0), np.max, 1)
    Rz = H - Op; mask = Rz > 0.035 * fh
    lab = np.zeros(mask.shape, int); best = None; n = 0
    for s0 in zip(*np.nonzero(mask)):
        if lab[s0]: continue
        n += 1; st = [s0]; lab[s0] = n; cells = []
        while st:
            c = st.pop(); cells.append(c)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (c[0] + d[0], c[1] + d[1])
                if 0 <= q[0] < nz and 0 <= q[1] < ny and mask[q] and not lab[q]: lab[q] = n; st.append(q)
        C = np.array(cells)
        if len(C) < 30 or C[:, 0].min() == 0: continue          # specks, and bumps cut by the bottom (shoulders, collars)
        sc = Rz[C[:, 0], C[:, 1]].sum()
        if best is None or sc > best[0]: best = (sc, n, C)
    if best is None: return None
    C = best[2]; zz = zs[C[:, 0]]; yy = ys[C[:, 1]]
    V = HP[C[:, 0], C[:, 1]]; V = V[np.isfinite(V).all(1)]
    return {'y': (np.percentile(yy, 2), np.percentile(yy, 98)), 'z': (np.percentile(zz, 2), np.percentile(zz, 98)),
            'x_max': float(H[C[:, 0], C[:, 1]].max()), 'x_base': float(np.median(Op[C[:, 0], C[:, 1]])), 'verts': V, 'fh': fh}

def coincident(H, T, names):
    """joint ends that share one point in the metarig (a mouth corner is the end of 4 bones): lists of [bone, 'h'|'t']"""
    ends = [(n, e, np.asarray(H[n] if e == 'h' else T[n])) for n in names for e in 'ht']; out = []; used = set()
    for i, (n, e, p) in enumerate(ends):
        if i in used: continue
        g = [[n, e]] + [[m, f] for j, (m, f, q) in enumerate(ends) if j > i and j not in used and np.linalg.norm(q - p) < 1e-5 and not used.add(j)]
        if len(g) > 1: out.append(g)
    return out
def sync(J, groups, fixed):
    """after some joint ends were set on their own (lids, lips ...), every end that shared their point follows"""
    for g in groups:
        src = next((m for m in g if tuple(m) in fixed), None)
        if src is None: continue
        v = np.array(J[src[0]][0 if src[1] == 'h' else 1])
        for n, e in g:
            h, t = J[n]; J[n] = (v.copy(), t) if e == 'h' else (h, v.copy())

EAR_NAMES = ['ear.%s', 'ear.%s.001', 'ear.%s.002', 'ear.%s.003', 'ear.%s.004']
def place_ear(J, LT, loop):
    """ear loop (5 joints, root first) from the metarig's loop normalised to its box: u front->back, v bottom->top,
    t base->outer; mapped into the detected ear box, outer points snapped to the ear's own vertices, the root to the
    surface. Returns per-side info."""
    out = {}
    for s_, sgn in (('L', 1), ('R', -1)):
        e = find_ear(LT, sgn)
        if e is None or len(e['verts']) < 10: out[s_] = None; continue
        V = e['verts']; pts = []
        for k, (u, v, t) in enumerate(loop):
            p = np.array([sgn * (e['x_base'] + t * (e['x_max'] - e['x_base'])), e['y'][0] + u * (e['y'][1] - e['y'][0]), e['z'][0] + v * (e['z'][1] - e['z'][0])])
            pts.append(snap(p) if k == 0 else V[np.argmin(np.linalg.norm(V - p, axis=1))])
        for k, nm in enumerate(EAR_NAMES): J[nm % s_] = (pts[k], pts[(k + 1) % 5])
        out[s_] = {'height_mm': round(float(np.ptp(e['z'])) * 1000, 1), 'out_mm': round((e['x_max'] - e['x_base']) * 1000, 1),
                   'height_rel': round(float(np.ptp(e['z']) / e['fh']), 2), 'verts': int(len(V))}
    return out

def eye_ring(get, side):
    """8 lid joints in metarig order: outer, upper 3, inner, lower 3 (lower listed inner->outer)"""
    S = EYE_R if side == 'R' else EYE_L
    up = [get(i) for i in S['up']]; lo = [get(i) for i in S['lo']]
    return [get(S['outer']), up[1], up[3], up[5], get(S['inner']), lo[5], lo[3], lo[1]]

if MODE == 'template':
    TD, TLM, META, MPFB = a[1], a[2], a[3], a[4]
    P = dense_pts(TD); LT = {int(k): np.array(v) for k, v in json.load(open(TLM)).items() if not k.startswith('_')}
    # semantic points the filter dropped (unsteady lip corners etc.) come from the unfiltered medians, mirrored
    RAW = {int(k): np.array(v) for k, v in json.load(open(TD))['_raw'].items()}
    for k, v in RAW.items():
        if k not in P: P[k] = snap(v)
    meta = json.load(open(META))['bones']; faceb = json.load(open(META))['face']
    H = {n: np.array(b['head']) for n, b in meta.items()}; T = {n: np.array(b['tail']) for n, b in meta.items()}
    pairs = []
    for s_, S in (('L', EYE_L), ('R', EYE_R)):
        ring = eye_ring(lambda i: P[i], s_)
        names = ['lid.T.%s', 'lid.T.%s.001', 'lid.T.%s.002', 'lid.T.%s.003', 'lid.B.%s', 'lid.B.%s.001', 'lid.B.%s.002', 'lid.B.%s.003']
        for k, nm in enumerate(names): pairs.append((H[nm % s_], ring[k]))
    for s_, ids in (('L', (6, 5, 4)), ('R', (1, 2, 3))):
        for nm, i in zip(('brow.T.%s.001', 'brow.T.%s.002', 'brow.T.%s.003'), ids): pairs.append((H[nm % s_], LT[i]))
    pairs += [(H['nose.002'], LT[16]), (T['lip.T.L.001'], P[LIP['corner_L']]), (T['lip.T.R.001'], P[LIP['corner_R']]),
              (H['lip.T.L'], snap(P[LIP['up_c']] + [0, 0, 0.004])), (H['lip.B.L'], snap(P[LIP['lo_c']] - [0, 0, 0.004])),
              (H['chin'], LT[24]), (T['spine.006'], LT[31])]
    M = np.array([p[0] for p in pairs]); Y = np.array([p[1] for p in pairs])
    s, R, t = umeyama(M, Y); sim = lambda Q: s * np.asarray(Q) @ R.T + t
    tps = tps_fit(sim(M), Y, lam=1e-9)
    J = {}
    for n in faceb:
        h, tl = tps_apply(tps, sim([H[n], T[n]]))
        if n.startswith(SKIN): h, tl = snap(h), snap(tl)
        J[n] = (h, tl)
    for s_ in 'LR':                                         # lid rings exactly on the contour
        ring = eye_ring(lambda i: P[i], s_)
        names = ['lid.T.%s', 'lid.T.%s.001', 'lid.T.%s.002', 'lid.T.%s.003', 'lid.B.%s', 'lid.B.%s.001', 'lid.B.%s.002', 'lid.B.%s.003']
        for k, nm in enumerate(names): J[nm % s_] = (ring[k], ring[(k + 1) % 8])
    loop = []
    E_ = [H['ear.L'], H['ear.L.001'], H['ear.L.002'], H['ear.L.003'], H['ear.L.004']]
    lo_, hi_ = np.min(E_, 0), np.max(E_, 0)
    for p in E_: q = (p - lo_) / (hi_ - lo_); loop.append([float(q[1]), float(q[2]), float(q[0])])
    ear_info = place_ear(J, LT, loop)
    # jaw pivot from the template's jawOpen (rotation about +X): D_y = -a z + b, D_z = a y - c
    with bpy.data.libraries.load(MPFB) as (src, dst): dst.objects = ['head']
    kb = dst.objects[0].data.shape_keys.key_blocks; B0 = np.array([tuple(q.co) for q in kb['Basis'].data])
    D = np.array([tuple(q.co) for q in kb['jawOpen'].data]) - B0
    mv = np.linalg.norm(D, axis=1) > 0.6 * np.linalg.norm(D, axis=1).max()
    Aq = np.zeros((2 * mv.sum(), 3)); rq = np.zeros(2 * mv.sum())
    Aq[0::2, 0] = -B0[mv, 2]; Aq[0::2, 1] = 1; rq[0::2] = D[mv, 1]
    Aq[1::2, 0] = B0[mv, 1]; Aq[1::2, 2] = -1; rq[1::2] = D[mv, 2]
    (aa, bb, cc), *_ = np.linalg.lstsq(Aq, rq, rcond=None)
    pivot = np.array([0.0, cc / aa, bb / aa])
    J['jaw'] = (pivot, LT[24].copy())
    J = symmetrise(J)
    json.dump({'joints': {n: [h.tolist(), t.tolist()] for n, (h, t) in J.items()}, 'dense': {str(k): v.tolist() for k, v in P.items()},
               'pivot': pivot.tolist(), 'jaw_angle_deg': math.degrees(aa), 'ear_loop': loop, 'ears': ear_info,
               'coincident': coincident(H, T, faceb)},
              open(os.path.join(DATA, 'rig_template.json'), 'w'))
    print('TEMPLATE joints', len(J), 'pairs', len(pairs), 'pivot', np.round(pivot, 4).tolist(), 'ears', ear_info)

else:
    DJ, LMJ, OUT = a[1], a[2], os.path.abspath(a[3])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    TPL = json.load(open(os.path.join(DATA, 'rig_template.json')))
    TP = {int(k): np.array(v) for k, v in TPL['dense'].items()}; TJ = {n: (np.array(h), np.array(t)) for n, (h, t) in TPL['joints'].items()}
    P = dense_pts(DJ); LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
    common = sorted(set(TP) & set(P))
    A_ = np.array([TP[k] for k in common]); B_ = np.array([P[k] for k in common])
    s, R, t = umeyama(A_, B_); sim = lambda Q: s * np.asarray(Q) @ R.T + t
    res_sim = np.linalg.norm(sim(A_) - B_, axis=1)
    LAM = float(os.environ.get('RP_LAM', '1e-4'))
    tps = tps_fit(sim(A_), B_, lam=LAM)
    res_tps = np.linalg.norm(tps_apply(tps, sim(A_)) - B_, axis=1)
    J = {}
    for n, (h, tl) in TJ.items():
        h2, t2 = tps_apply(tps, sim([h, tl]))
        if n.startswith(SKIN): h2, t2 = snap(h2), snap(t2)
        J[n] = (h2, t2)
    info = {'common_points': len(common), 'similarity_scale': round(float(s), 4),
            'residual_mm': {'similarity_p50': round(float(np.median(res_sim) * 1000), 2), 'tps_p50': round(float(np.median(res_tps) * 1000), 2),
                            'tps_p95': round(float(np.percentile(res_tps, 95) * 1000), 2)}}
    # lid rings: two candidates per eye, the better one wins
    #   MediaPipe eye contour (unfiltered medians, made symmetric): right on human-like eyes, but on big cartoon
    #     eyes MediaPipe draws a human-size eye inside the real one
    #   depth rim (first depth maximum around the eye): right on cartoon eyes, can wander on sculpted human lids
    # A ring is usable when it is convex-ish (area / hull area > 0.85) and wider than tall (aspect 1.2-6); a depth
    # rim also has to stay under the brow and contain (with a 20 % margin) most of the MediaPipe eye. One source for both eyes:
    # MediaPipe when its eye is narrow (aspect >= 2.6, human-like); else the depth rim when clearly bigger than the
    # MediaPipe eye (area x1.6, a cartoon eye); else whichever is usable; else the ring carried from the template.
    RAW = {int(k): np.array(v) for k, v in json.load(open(DJ)).get('_raw', {}).items()}
    PT = json.load(open(os.path.join(DATA, 'mp_mirror_pairs.json')))
    partner = {}
    for i_, j_ in PT['pairs']: partner[i_] = j_; partner[j_] = i_
    def raw_sym(i):
        j = partner.get(i)
        if i not in RAW: return None
        if j is None or j not in RAW: return snap(RAW[i])
        return snap((RAW[i] + RAW[j] * np.array([-1, 1, 1])) / 2)
    def ring_quality(ring):
        Q = np.array(ring)[:, [0, 2]]; c = Q.mean(0)
        area = 0.5 * abs(np.dot(Q[:, 0], np.roll(Q[:, 1], 1)) - np.dot(Q[:, 1], np.roll(Q[:, 0], 1)))
        ang = np.arctan2(Q[:, 1] - c[1], Q[:, 0] - c[0]); H_ = Q[np.argsort(ang)]
        hull = 0.5 * abs(np.dot(H_[:, 0], np.roll(H_[:, 1], 1)) - np.dot(H_[:, 1], np.roll(H_[:, 0], 1)))
        w = np.ptp(Q[:, 0]); h = np.ptp(Q[:, 1])
        ok = hull > 0 and area / hull > 0.85 and 1.2 < w / max(h, 1e-6) < 6
        return bool(ok), float(area), round(float(area / hull) if hull else 0, 2), round(float(w / max(h, 1e-6)), 2)
    names = ['lid.T.%s', 'lid.T.%s.001', 'lid.T.%s.002', 'lid.T.%s.003', 'lid.B.%s', 'lid.B.%s.001', 'lid.B.%s.002', 'lid.B.%s.003']
    def inside(poly, pts):
        P2 = np.array(poly)[:, [0, 2]]; res = []
        for x, z in np.array(pts)[:, [0, 2]]:
            c = False; j = len(P2) - 1
            for i in range(len(P2)):
                if (P2[i, 1] > z) != (P2[j, 1] > z) and x < (P2[j, 0] - P2[i, 0]) * (z - P2[i, 1]) / (P2[j, 1] - P2[i, 1] + 1e-12) + P2[i, 0]: c = not c
                j = i
            res.append(c)
        return np.array(res)
    cands, quals = {}, {}
    for s_, ids in (('R', (7, 9)), ('L', (13, 11))):
        cand = {}
        try:
            mp_ring = eye_ring(lambda i: raw_sym(i), s_)
            if all(r is not None for r in mp_ring): cand['mediapipe'] = mp_ring
        except Exception: pass
        try:
            cx = np.mean([LT[k][0] for k in ids]); cz = np.mean([LT[k][2] for k in ids])
            L = lids(recentred_rim(bvh_all, cx, cz, 'margin'), np.linspace(0, 1, 5))
            cand['depth'] = [L['up'][0], L['up'][1], L['up'][2], L['up'][3], L['up'][4], L['lo'][3], L['lo'][2], L['lo'][1]]
        except Exception: pass
        q = {k: list(ring_quality(v)) for k, v in cand.items()}
        if 'depth' in q:
            brow_z = J['brow.T.%s.002' % s_][0][2]
            below = max(p[2] for p in cand['depth']) < brow_z
            ok = q['depth'][0] and below
            q['depth'] += [bool(below)]
            if 'mediapipe' in cand:                          # a real big eye contains the MediaPipe eye
                Dr = np.array(cand['depth']); Dr = Dr.mean(0) + 1.2 * (Dr - Dr.mean(0))      # 20 % margin: rings of equal size touch
                cont = float(inside(Dr, cand['mediapipe']).mean()); ok = ok and cont >= 0.6
                q['depth'] += [round(cont, 2)]
            q['depth'][0] = bool(ok)
        cands[s_], quals[s_] = cand, q
    # one source for both eyes
    both = lambda k: all(k in quals[s_] and quals[s_][k][0] for s_ in 'RL')
    ratio = np.mean([quals[s_]['depth'][1] / max(quals[s_]['mediapipe'][1], 1e-12) for s_ in 'RL']) if both('depth') and all('mediapipe' in quals[s_] for s_ in 'RL') else 0
    mp_aspect = np.mean([quals[s_]['mediapipe'][3] for s_ in 'RL']) if all('mediapipe' in quals[s_] for s_ in 'RL') else 0
    if both('mediapipe') and mp_aspect >= 2.6: pick = 'mediapipe'          # narrow human-like eye: trust MediaPipe
    elif both('depth') and (ratio > 1.6 or not both('mediapipe')): pick = 'depth'
    elif both('mediapipe'): pick = 'mediapipe'
    elif both('depth'): pick = 'depth'
    else: pick = 'template'
    choice = {'pick': pick, 'depth_to_mediapipe_area': round(float(ratio), 2), 'mediapipe_aspect': round(float(mp_aspect), 2)}
    fixed = set()
    for s_ in 'RL':
        if pick != 'template':
            ring = cands[s_][pick]
            for k, nm in enumerate(names): J[nm % s_] = (ring[k], ring[(k + 1) % 8]); fixed |= {(nm % s_, 'h'), (nm % s_, 't')}
        choice[s_] = {k: {'usable': v[0], 'convex': v[2], 'aspect': v[3], 'area_mm2': round(float(v[1]) * 1e6, 1), **({'under_brow': v[4]} if len(v) > 4 else {}),
                          **({'contains_mediapipe': v[5]} if len(v) > 5 else {})} for k, v in quals[s_].items()}
    info['lid_rings'] = choice
    # the whole eye contour for the eye cut (rig_original EYE_RIMS): MediaPipe's 16 contour points, symmetric,
    # 4 samples per segment, shot onto the surface from the front. Only when MediaPipe won; the depth rim is what
    # rig_original finds by itself.
    FULL = {'R': [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7],
            'L': [263, 466, 388, 387, 386, 385, 384, 398, 362, 382, 381, 380, 374, 373, 390, 249]}
    if pick == 'mediapipe':
        rims_out = {}
        for s_ in 'RL':
            Q = [raw_sym(i) for i in FULL[s_]]
            if any(q is None for q in Q): rims_out = None; break
            ring = []
            for k in range(len(Q)):
                for t_ in (0, 0.25, 0.5, 0.75):
                    p = Q[k] + t_ * (Q[(k + 1) % len(Q)] - Q[k])
                    h = bvh_face.ray_cast(Vector((p[0], -2.0, p[2])), Vector((0, 1, 0)))
                    ring.append([float(c) for c in (h[0] if h[0] is not None else p)])
            rims_out[s_] = ring
        if rims_out: info['eye_rims'] = rims_out
    info['lid_candidates'] = {s_: {k: [list(map(float, p)) for p in v] for k, v in cands[s_].items()} for s_ in 'RL'}
    # lip corners / centres from the head's inner lip line when detected
    if all(k in P for k in LIP.values()):
        for s_, k in (('L', LIP['corner_L']), ('R', LIP['corner_R'])):
            for nm in ('lip.T.%s.001', 'lip.B.%s.001'):
                h, _ = J[nm % s_]; J[nm % s_] = (h, P[k]); fixed.add((nm % s_, 't'))
        J['lip.T.L'] = (snap(P[LIP['up_c']] + [0, 0, 0.0035]), J['lip.T.L'][1]); J['lip.T.R'] = (J['lip.T.L'][0].copy(), J['lip.T.R'][1])
        J['lip.B.L'] = (snap(P[LIP['lo_c']] - [0, 0, 0.0035]), J['lip.B.L'][1]); J['lip.B.R'] = (J['lip.B.L'][0].copy(), J['lip.B.R'][1])
        fixed |= {('lip.T.L', 'h'), ('lip.B.L', 'h')}
        info['lips_from_inner_line'] = True
    info['ears'] = place_ear(J, LT, TPL['ear_loop'])          # ears: the face points stop short of them
    # the jaw pivot sits deep in the head, far from every face point: the spline's extrapolation there is not to be
    # trusted (it pulled the pivot 4 cm forward), the similarity is (character1: within 1.3 cm of its solved pivot)
    piv = sim([TPL['pivot']])[0]
    J['jaw'] = (piv, J['jaw'][1]); info['jaw_pivot'] = np.round(piv, 4).tolist()
    sync(J, TPL['coincident'], fixed)                       # e.g. a moved mouth corner takes chin.L / cheek.B.L along
    J = symmetrise(J)
    # order sanity (front view heights): brows above lids above nose tip above lips above chin
    z = lambda n: J[n][0][2]
    info['order_ok'] = bool(z('brow.T.L.002') > z('lid.T.L.002') > z('nose.002') > z('lip.T.L') > z('lip.B.L') > z('chin'))
    json.dump({'joints': {n: [h.tolist(), t.tolist()] for n, (h, t) in J.items()}, 'info': info}, open(OUT, 'w'))
    # overlay renders (EEVEE, textured)
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try: sc.render.engine = eng; break
        except TypeError: pass
    sc.render.resolution_x = sc.render.resolution_y = 900; sc.view_settings.view_transform = 'Standard'
    if not sc.world: sc.world = bpy.data.worlds.new('w')
    sc.world.use_nodes = True; bg = sc.world.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1); bg.inputs[1].default_value = 0.6
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 1.4; so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (0.6, 0.1, -0.2)
    top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]; size = 2.0 * fh; cz = (top + LT[24][2]) / 2 + 0.05 * fh
    cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.ortho_scale = size; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
    figs = {}
    for vn, d in (('front', (0, -1, 0)), ('34', (0.7, -0.71, 0))):
        d = Vector(d).normalized(); co.location = Vector((0, 0, cz)) + d * 2; co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        png = os.path.splitext(OUT)[0] + f'_{vn}.png'; sc.render.filepath = png; bpy.ops.render.render(write_still=True)
        bpy.context.view_layer.update(); Mi = co.matrix_world.inverted()
        def to2d(p):
            q = Mi @ Vector(p); return [0.5 + q.x / size, 0.5 - q.y / size, -q.z]
        figs[vn] = {n: [to2d(h), to2d(t)] for n, (h, t) in J.items()}
    json.dump(figs, open(os.path.splitext(OUT)[0] + '_fig.json', 'w'))
    print('RIGPOINTS', json.dumps(info))
