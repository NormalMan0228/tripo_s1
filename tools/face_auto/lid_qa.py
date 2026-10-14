"""Eyelid QA on a blend with lid rings (loop_organs / organ_eye attributes eye_ring, eye_u) and blink / look keys.
Per side (left measured; the heads are mirror-symmetric) and state (rest, blink t = 0.25 / 0.5 / 0.75 / 1.0 with the
eyeBlinkMid corrective at 4 t (1 - t), eyeLookUp / Down if present):
- canthi: the margin vertices nearest landmarks 13 (outer) / 11 (inner) of the base; ring corners: margin vertices with
  eye_u = 0 / 0.5; their distance (mm); corner motion (mm) per state;
- bumpiness of the margin ring K and the rings K-1 .. K-5 (outward), per lid (upper u in (0, 0.5), lower (0.5, 1)):
  vertices ordered by u, residual from a local quadratic fit along arc length (Gaussian weights, h = 1.5 mm; follows
  the lid's curvature, so only bumps remain): RMS / max (mm), and the RMS of the second difference of the residual;
- split points: the ring corners (eye_u 0 / 0.5) vs landmarks 13 / 11 (the canthi; on canthus_wedge bases 11 = the
  visible inner tip);
- closed lid (t = 1): contact: both margin lines sampled densely (400 points) against each other (max gap, length where
  they touch within 0.1 mm vs the closed line length and the rim's corner-to-corner length);
  meeting gap (upper margin vertices -> lower margin polyline, max mm), the meeting line's own
  bumpiness, and how far below the rest opening's middle it runs (share of the opening height at mid lid);
- eyeball clearance (lid rings -> sphere, min mm) and turned faces (normal > 90 deg from rest) in the lid area.
Writes <out.json> (numbers + polylines in the front view for figures).
Usage: blender -b <prev.blend> -P lid_qa.py -- <eyes.json> <landmarks.json> <out.json>
"""
import bpy, sys, json
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]
EJ, LMJ, OUT = a[0], a[1], a[2]
J = json.load(open(EJ)); K = int(J['rings']); E = J['eyes']['L']; C = np.array(E['C']); r = float(E['r'])
LM = {k: np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
face = bpy.data.objects['face']; me = face.data; kbs = me.shape_keys.key_blocks
X0 = np.array([tuple(d.co) for d in kbs[0].data]); N = len(X0)
ring = np.array([d.value for d in me.attributes['eye_ring'].data]); u = np.mod(np.array([d.value for d in me.attributes['eye_u'].data]), 1.0)
F = [list(p.vertices) for p in me.polygons]
MM = 1000.0


def key(name):
    kb = kbs.get(name)
    if kb is None: return None
    b = np.empty(N * 3); kb.data.foreach_get('co', b); return b.reshape(-1, 3) - X0


DB, DM = key('eyeBlinkLeft'), key('eyeBlinkMidLeft')
states = {'rest': X0}
for t in (0.25, 0.5, 0.75, 1.0):
    if DB is not None: states['b%.2f' % t] = X0 + t * DB + (4 * t * (1 - t) * DM if DM is not None else 0)
for nm in ('eyeLookUpLeft', 'eyeLookDownLeft'):
    d = key(nm)
    if d is not None: states[nm] = X0 + d

L = np.where(ring > 0)[0]; marg = np.where(ring == K)[0]
can = {'outer': int(marg[np.argmin(np.linalg.norm(X0[marg] - LM['13'], axis=1))]), 'inner': int(marg[np.argmin(np.linalg.norm(X0[marg] - LM['11'], axis=1))])}
cor = {'u0': int(marg[np.argmin(np.abs(np.mod(u[marg] + 0.5, 1.0) - 0.5))]), 'u05': int(marg[np.argmin(np.abs(u[marg] - 0.5))])}
# u = 0 is the +x (outer, left eye) corner
qa = {'K': K, 'canthus_vids': can, 'corner_vids': cor,
      'corner_to_canthus_mm': {'outer': round(float(np.linalg.norm(X0[cor['u0']] - X0[can['outer']]) * MM), 3),
                               'inner': round(float(np.linalg.norm(X0[cor['u05']] - X0[can['inner']]) * MM), 3)},
      'canthus_to_landmark_mm': {'outer': round(float(np.linalg.norm(X0[can['outer']] - LM['13']) * MM), 3), 'inner': round(float(np.linalg.norm(X0[can['inner']] - LM['11']) * MM), 3)},
      'split_to_canthus_landmark_mm': {'outer': round(float(np.linalg.norm(X0[cor['u0']] - LM['13']) * MM), 3), 'inner': round(float(np.linalg.norm(X0[cor['u05']] - LM['11']) * MM), 3)}}


def lsmooth(P, s, h):
    """local quadratic regression along arc length (Gaussian weights, bandwidth h): follows curvature without shrinking"""
    out = np.empty_like(P)
    for i in range(len(P)):
        d = s - s[i]; w = np.exp(-0.5 * (d / h) ** 2); A = np.c_[np.ones_like(d), d, d * d] * np.sqrt(w)[:, None]
        out[i] = np.linalg.lstsq(A, P * np.sqrt(w)[:, None], rcond=None)[0][0]
    return out


def bump(ids, X):
    """residual of a lid path (ordered ids, corners included) from a local quadratic fit along arc length (h 1.5 mm)"""
    P = X[ids]; s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if len(P) < 5: return None
    S = lsmooth(P, s, 0.0015); Rz = P - S; Rz[0] = Rz[-1] = 0
    d2 = Rz[:-2] - 2 * Rz[1:-1] + Rz[2:]
    return {'rms': float(np.sqrt((Rz ** 2).sum(1).mean()) * MM), 'max': float(np.linalg.norm(Rz, axis=1).max() * MM),
            'd2_rms': float(np.sqrt((d2 ** 2).sum(1).mean()) * MM)}


def lid_paths(k_):
    """vertices of ring k (left), upper / lower lid ordered by u from the outer corner, corners (u nearest 0 / 0.5) shared"""
    ids = np.where(ring == k_)[0]; uu = u[ids]
    up = ids[(uu > 0) & (uu < 0.5)]; lo = ids[uu > 0.5]
    c0 = ids[np.argmin(np.minimum(uu, 1 - uu))]; c5 = ids[np.argmin(np.abs(uu - 0.5))]
    up = [c0] + list(up[np.argsort(u[up])]) + [c5]; lo = [c0] + list(lo[np.argsort(-u[lo])]) + [c5]
    return [int(i) for i in dict.fromkeys(up)], [int(i) for i in dict.fromkeys(lo)]


rings_chk = [k for k in range(K, max(K - 6, 0), -1)]
paths = {k: lid_paths(k) for k in rings_chk}
D0 = X0 - C
def turned(X):
    """faces of the left lid rings whose normal turned > 90 deg: count, and how many lie in the tuck rings (> K)"""
    cnt = tk = 0
    for f in F:
        if not all(ring[v] > 0 for v in f): continue
        P0, P1 = X0[f], X[f]
        n0 = sum(np.cross(P0[i], P0[(i + 1) % len(f)]) for i in range(len(f))); n1 = sum(np.cross(P1[i], P1[(i + 1) % len(f)]) for i in range(len(f)))
        if n0 @ n1 < 0:
            cnt += 1; tk += int(max(ring[v] for v in f) > K)
    return [cnt, tk]
st = {}
for nm, X in states.items():
    b = {}
    for k in rings_chk:
        up, lo = paths[k]; bu, bl = bump(up, X), bump(lo, X)
        b[str(K - k)] = {'upper': {kk: round(v, 3) for kk, v in bu.items()} if bu else None, 'lower': {kk: round(v, 3) for kk, v in bl.items()} if bl else None}
    g = np.linalg.norm(X[L] - C, axis=1) - r
    st[nm] = {'corner_motion_mm': {kk: round(float(np.linalg.norm(X[v] - X0[v]) * MM), 3) for kk, v in can.items()},
              'bump_by_ring_from_margin': b, 'eyeball_clear_min_mm': round(float(g.min() * MM), 3), 'turned_faces': turned(X) if nm != 'rest' else [0, 0],
              'bump_rings0_5_mean_rms': round(float(np.mean([x[h]['rms'] for x in b.values() for h in ('upper', 'lower') if x[h]])), 3),
              'bump_rings0_5_max': round(float(np.max([x[h]['max'] for x in b.values() for h in ('upper', 'lower') if x[h]])), 3)}
qa['states'] = st
# closed lid: meeting line
if 'b1.00' in states:
    X = states['b1.00']; up, lo = paths[K]
    PU, PL = X[up], X[lo]
    def segd(P, Q):
        A_, B_ = Q[:-1], Q[1:]; AB = B_ - A_; ll = np.maximum((AB * AB).sum(1), 1e-18)
        t_ = np.clip(((P[:, None] - A_[None]) * AB[None]).sum(2) / ll[None], 0, 1)
        return np.linalg.norm(P[:, None] - (A_[None] + t_[..., None] * AB[None]), axis=2).min(1)
    def dense(Pl, n=400):
        s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pl, axis=0), axis=1))]; t_ = np.linspace(0, s_[-1], n)
        return np.stack([np.interp(t_, s_, Pl[:, j]) for j in range(3)], 1), s_[-1]
    DU, lu = dense(PU); DL, ll_ = dense(PL); gu = segd(DU, PL); gl = segd(DL, PU)
    rim0 = float(np.r_[0, np.cumsum(np.linalg.norm(np.diff(X0[up], axis=0), axis=1))][-1])
    qa['contact'] = {'gap_sampled_max_mm': round(float(max(gu.max(), gl.max()) * MM), 3), 'contact_len_mm': round(float((gu <= 0.0001).mean() * lu * MM), 2),
                     'closed_line_len_mm': round(float(lu * MM), 2), 'contact_share': round(float((gu <= 0.0001).mean()), 3),
                     'rim_corner_to_corner_mm': round(float(np.linalg.norm(X0[up[0]] - X0[up[-1]]) * MM), 2), 'upper_rim_len_rest_mm': round(rim0 * MM, 2)}
    qa['closed'] = {'meet_gap_max_mm': round(float(max(segd(PU, PL).max(), segd(PL, PU).max()) * MM), 3),
                    'meeting_line_bump': {kk: round(v, 3) for kk, v in bump(up, X).items()}}
    # where the line runs: at mid lid, share of the rest opening height (0 = lower lid, 1 = upper lid), front view (z)
    U0, L0 = X0[up][:, [0, 2]], X0[lo][:, [0, 2]]; xm = (X0[can['outer'], 0] + X0[can['inner'], 0]) / 2
    zu = np.interp(xm, *zip(*sorted(zip(U0[:, 0], U0[:, 1])))); zl = np.interp(xm, *zip(*sorted(zip(L0[:, 0], L0[:, 1]))))
    zc = np.interp(xm, *zip(*sorted(zip(PU[:, 0], PU[:, 2]))))
    qa['closed']['line_height_share_mid'] = round(float((zc - zl) / max(zu - zl, 1e-9)), 3)
# polylines for figures (front view x, z in mm): rings at rest and closed, canthi, corners
fig = {}
for nm in [s for s in ('rest', 'b0.50', 'b1.00') if s in states]:
    X = states[nm]; fig[nm] = {str(K - k): [(X[p][:, [0, 2]] * MM).round(3).tolist() for p in paths[k]] for k in rings_chk}
for nm in [s_ for s_ in ('rest', 'b1.00') if s_ in states]:
    X = states[nm]; res = {}
    for k in rings_chk:
        for h_, p in zip(('u', 'l'), paths[k]):
            P = X[p]; s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; res[f'{K - k}{h_}'] = (np.linalg.norm(P - lsmooth(P, s_, 0.0015), axis=1) * MM).round(3).tolist()
    fig[nm + '_res'] = res
fig['canthi'] = {kk: (X0[v][[0, 2]] * MM).round(3).tolist() for kk, v in can.items()}; fig['corners'] = {kk: (X0[v][[0, 2]] * MM).round(3).tolist() for kk, v in cor.items()}
qa['_fig'] = fig
json.dump(qa, open(OUT, 'w'))
print('LIDQA', json.dumps({k: v for k, v in qa.items() if k != '_fig' and k != 'states'}), json.dumps({s: {kk: v[kk] for kk in ('corner_motion_mm', 'bump_rings0_5_mean_rms', 'bump_rings0_5_max', 'eyeball_clear_min_mm', 'turned_faces')} for s, v in st.items()}))
