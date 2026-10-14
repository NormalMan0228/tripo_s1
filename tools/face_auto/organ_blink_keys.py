"""겹침생성 · eyeBlinkLeft / eyeBlinkRight shape keys for ring eyelids (organ_eye.py), from organ_lib.ring_blink, and
a lid clearance pass over the other keys.
Blink: lid columns turn about the eye's corner axis so the upper and lower margins meet; the head does not move.
rigify_bake.py leaves eyeBlink to a separate lid rig (T1), which M1 heads do not have, so the keys come from here.
A shape key blends linearly: at weight t the lid sits on the chord between rest and closed, and the chord of a lid
turning about the eyeball centre cuts into the eyeball (0.3 mm on a human eye, 2 mm on big anime eyes at t = 0.5).
So each side also gets an in-between corrective eyeBlinkMidLeft / eyeBlinkMidRight, meant to be added with weight
4 t (1 - t) whenever eyeBlink is t: least-squares fit of ring_blink(t) minus the chord over t = 0.05 .. 0.95, then
pushed out until the lid keeps the clearance floor at every one of those t (the parabola alone dipped to 0.18 mm).
In Blender a driver on the corrective's value does that (simple expression: works with Python auto-run off); the
mesh also carries the rule as the custom property 'corrective_keys' (JSON {key: [source key, expression]}) for an
exporter / game runtime, which must set it next to eyeBlink (ARKit-only players leave it at 0 and get the plain
linear key). The names end in Left / Right so sym_lock.py keys pairs them.
Other keys: the baked bones know nothing of the eyeball, so eyeSquint / cheekSquint / noseSneer ... push lid-ring
vertices into it. Every key that moves a lid ring keeps the floor alone (weight 0.5 and 1); every key that does not
open the eye (lid delta against the blink's, cos >= -0.2: squint, cheekSquint, smile, brow down ...) also keeps it on
top of the blink path (t = 0.25 .. 1, with the corrective), and the six of them that come nearest also in pairs and
triples (smile + squint + blink). Only vertices that would break the floor move, straight away from the eyeball
centre, the push shared by the keys that pushed inward. Keys that open the eye (eyeWide, brow up: cos < -0.2) are not
fitted to the closed lid: that would lift them off the open eye by as much; QA names the worst such conflict.
Floor = ring_blink's: 0.2 mm off the eyeball sphere (C, r), or the rest gap minus 0.1 mm where the rest is nearer.
QA: BLINKKEYS (lid-ring distance to the sphere, mm, t grid 0.05: linear key alone and with the corrective);
LIDKEYS (per side: keys, keys held with the blink, the combined six, opening keys, constraints, min over the floor
before / after, largest change per key, the worst opening key on the closed lid = not covered).
Irregular lid rings (eyes json 'irregular': true, from loop_organs.py: BFS rings of the original mesh) close with
organ_lib.ring_blink_irregular (turn and radius scale as smooth functions of u from the margin vertices); the rest is
the same.
Irregular rings default to organ_lib.ring_blink_canthus (canthi fixed, meeting line at --meet 0.62, skin falloff on the
harmonic lid coordinate organ_lib.lid_coord instead of the BFS ring index), then organ_lib.corner_zip (where the margin
runs far above the eyeball, e.g. a canthus_wedge inner corner: the lids zip shut linearly onto one meeting curve up to
the tip), wedge_close (bases whose eyes json still has a separate canthus_tip), lid_seal at t = 1 (upper and lower margin
lines meet edge to edge) and lid_untangle (folds relaxed); --legacy keeps ring_blink_irregular. The skin turn's corner fade
(ring_blink_canthus corner_fade) is picked per eye from 0.06 / 0.12 / 0.2 by the fewest lid faces turned > 90 deg when
closed (f09: 18 -> 5 at 0.2; the other test heads keep 0.06); BLINKKEYS reports it.
Usage: blender -b <arkit.blend> -P organ_blink_keys.py -- <eyes.json from organ_eye / loop_organs> <out.blend> [--no-mid] [--legacy] [--meet 0.62]
"""
import bpy, sys, os, json, itertools
import numpy as np
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from organ_lib import ring_blink, ring_blink_irregular, ring_blink_canthus, lid_coord, wedge_close, lid_untangle, corner_zip, lid_seal

a = sys.argv[sys.argv.index('--') + 1:]
EJ, OUT, MID = a[0], os.path.abspath(a[1]), '--no-mid' not in a[2:]
LEGACY = '--legacy' in a[2:]                       # irregular rings: ring_blink_irregular (ring-index falloff, meet 0.8)
MEET = float(a[a.index('--meet') + 1]) if '--meet' in a else 0.62
CLEAR, KNEE = 0.0002, 0.0001
J = json.load(open(EJ)); E = J['eyes']; K = J['rings']; M = J['ring_verts']; IRR = bool(J.get('irregular'))
face = bpy.data.objects['face']; me = face.data
if not me.shape_keys: face.shape_key_add(name='Basis')
X0 = np.array([tuple(d.co) for d in me.shape_keys.key_blocks[0].data]); N = len(X0)
ring = np.array([d.value for d in me.attributes['eye_ring'].data]); u = np.array([d.value for d in me.attributes['eye_u'].data])

def co(kb): b = np.empty(N * 3); kb.data.foreach_get('co', b); return b.reshape(-1, 3)
def key(name, P):
    kb = me.shape_keys.key_blocks.get(name) or face.shape_key_add(name=name, from_mix=False)
    kb.data.foreach_set('co', P.ravel()); kb.value = 0.0; return kb

def drive(kb, src):                                    # value = 4 t (1 - t), t = the eyeBlink key (simple expression: no Python needed)
    try: kb.driver_remove('value')
    except TypeError: pass
    d = kb.driver_add('value').driver; d.type = 'SCRIPTED'; v = d.variables.new(); v.name = 't'; v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'KEY'; v.targets[0].id = me.shape_keys; v.targets[0].data_path = f'key_blocks["{src}"].value'
    d.expression = '4 * t * (1 - t)'

floor = lambda g0: np.clip(np.minimum(CLEAR, g0 - KNEE), 0, None)     # ring_blink's floor above the sphere
TT = np.round(np.arange(0.05, 0.951, 0.05), 2); B4 = 4 * TT * (1 - TT); TQ = np.round(np.arange(0.05, 1.001, 0.05), 2)
out, BL, corr = {}, {}, {}
CFS, CFQ = {1: 0.06, -1: 0.06}, {}; FACES = [list(p.vertices) for p in me.polygons]
for s, sg, name in (('L', 1, 'eyeBlinkLeft'), ('R', -1, 'eyeBlinkRight')):
    C, ax, r = np.array(E[s]['C']), np.array(E[s]['axis']), float(E[s]['r'])
    if IRR and not LEGACY:
        EV = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get('vertices', EV)
        HC = lid_coord(N, EV.reshape(-1, 2), ring, sg, K)
        TIP = E[s].get('canthus_tip'); VIEW = E[s].get('view')
        FV = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', FV)
        FN = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', FN)
        PROT = [int(np.argmin(np.linalg.norm(X0 - np.array(TIP), axis=1)))] if TIP is not None else []
        SMZ = 40 if E[s].get('canthus_wedge') else 0             # canthus-wedge bases: fair the zip sheet's seam (crease)
        def rb(t, sg=sg, C=C, ax=ax, r=r, HC=HC, TIP=TIP, VIEW=VIEW, FV=FV, FN=FN, PROT=PROT, CF=None):
            CF = CFS[sg] if CF is None else CF
            P_ = ring_blink_canthus(X0, ring, u, sg, C, ax, t, K, HC, meet=MEET, r_eye=r, clear=CLEAR, knee=KNEE, corner_fade=CF)
            P_ = corner_zip(P_, X0, ring, u, sg, K, C, r, t, EV.reshape(-1, 2), meet=MEET, smooth=SMZ)   # wedge part of the margin: zip
            P_ = wedge_close(P_, X0, ring, u, sg, K, TIP, VIEW, t, C=C, r_eye=r, clear=CLEAR, edges=EV.reshape(-1, 2))
            if t <= 0: return P_
            if t >= 0.999: P_ = lid_seal(P_, ring, u, sg, K, EV.reshape(-1, 2))                # closed: the lines meet edge to edge
            return lid_untangle(P_, X0, FV, FN, ring, sg, K, C=C, r_eye=r, clear=CLEAR, protect=PROT)[0]
    elif IRR: rb = lambda t: ring_blink_irregular(X0, ring, u, sg, C, ax, t, K, r_eye=r, clear=CLEAR, knee=KNEE)
    else: rb = lambda t: ring_blink(X0, ring, u, sg, C, ax, t, K, M, r_eye=r, clear=CLEAR, knee=KNEE)
    if IRR and not LEGACY:                             # corner fade of the skin turn: of 0.06 / 0.12 / 0.2 (u from the canthi) the one
        LF = [f for f in FACES if all(np.sign(ring[v]) == sg and ring[v] != 0 for v in f)]   # leaving the fewest lid faces turned
        nrm_ = lambda Q, f: sum(np.cross(Q[f][i], Q[f][(i + 1) % len(f)]) for i in range(len(f)))   # > 90 deg when closed (lid_qa's count)
        N0_ = [nrm_(X0, f) for f in LF]; trn = {}
        for cf_ in (0.06, 0.12, 0.2):
            Pc = rb(1.0, CF=cf_); trn[cf_] = sum(1 for f, n0 in zip(LF, N0_) if n0 @ nrm_(Pc, f) < 0)
        CFS[sg] = min(trn, key=lambda c_: (trn[c_], c_)); CFQ[name] = {'corner_fade': CFS[sg], 'turned_closed_by_fade': {str(c_): v for c_, v in trn.items()}}
    P = rb(1.0); key(name, P); li = np.where(np.sign(ring) == sg)[0]; X, Pl = X0[li], P[li]
    gap = lambda Y: np.linalg.norm(Y - C, axis=1) - r; fl = floor(gap(X)) + 2e-6
    q = {'moved_verts': int((np.linalg.norm(P - X0, axis=1) > 1e-5).sum()), 'max_mm': round(float(np.linalg.norm(P - X0, axis=1).max() * 1000), 2)}
    Dm = np.zeros_like(X); mid = name.replace('eyeBlink', 'eyeBlinkMid')
    if MID:
        Ea = np.array([rb(t)[li] - (X + t * (Pl - X)) for t in TT])              # arc minus chord
        Dm = np.einsum('t,tij->ij', B4, Ea) / (B4 @ B4); it = 0
        for it in range(60):                                                     # out to the floor at every t of the grid
            worst = 0.0
            for t, b in zip(TT, B4):
                d = X + t * (Pl - X) + b * Dm - C; n_ = np.linalg.norm(d, axis=1); de = fl - (n_ - r); m_ = de > 0
                if m_.any(): Dm[m_] += (de[m_] / (b * n_[m_]))[:, None] * d[m_]; worst = max(worst, float(de.max()))
            if worst < 1e-9: break
        F = X0.copy(); F[li] += Dm; drive(key(mid, F), name); corr[mid] = [name, '4*t*(1-t)']
        fit = np.array([np.linalg.norm(b * Dm - e, axis=1).max() for b, e in zip(B4, Ea)])
        q.update(mid_key=mid, mid_max_mm=round(float(np.linalg.norm(Dm, axis=1).max() * 1000), 2), mid_iters=it,
                 mid_path_err_mm=round(float(fit.max() * 1000), 3))
    elif me.shape_keys.key_blocks.get(mid): face.shape_key_remove(me.shape_keys.key_blocks[mid])
    gl = {t: gap(X + t * (Pl - X)) * 1000 for t in TQ}; gm = {t: gap(X + t * (Pl - X) + 4 * t * (1 - t) * Dm) * 1000 for t in TQ}
    lo = lambda G_: [round(float(min(g.min() for g in G_.values())), 3), float(min(G_, key=lambda t: G_[t].min()))]
    q.update(linear_min_mm_at_t=lo(gl), with_mid_min_mm_at_t=lo(gm), with_mid_lt_0_2mm=max(int((g < CLEAR * 1000 - 1e-3).sum()) for g in gm.values()))
    for t in (0.25, 0.5, 0.75, 1.0): q[f't{t}'] = {'linear_min_mm': round(float(gl[t].min()), 3), 'with_mid_min_mm': round(float(gm[t].min()), 3)}
    q.update(CFQ.get(name, {})); out[name] = q; BL[s] = (li, C, r, Pl - X, Dm, fl - 2e-6)
if corr: me['corrective_keys'] = json.dumps(corr)
elif 'corrective_keys' in me: del me['corrective_keys']
print('BLINKKEYS', json.dumps(out))

# ---- the other keys on the lid rings keep the floor (alone; the squint family also on the blink path and together)
kbs = me.shape_keys.key_blocks; names = [kb.name for kb in kbs[1:] if not kb.name.startswith('eyeBlink')]
lids = np.where(ring != 0)[0]; Dk = {n: (co(kbs[n]) - X0)[lids] for n in names}; pos = {v: i for i, v in enumerate(lids)}
lq, changed = {}, set()
for s, (li, C, r, Bl, Ml, fl) in BL.items():
    rows = np.array([pos[v] for v in li]); X = X0[li]
    D = {n: Dk[n][rows].copy() for n in names if np.linalg.norm(Dk[n][rows], axis=1).max() > 5e-5}
    nb = np.sqrt((Bl * Bl).sum())
    cosb = {n: float((d * Bl).sum() / max(np.sqrt((d * d).sum()) * nb, 1e-12)) for n, d in D.items()}
    bases = [X] + [X + t * Bl + 4 * t * (1 - t) * Ml for t in ((0.25, 0.5, 0.75, 1.0) if MID else (1.0,))]
    gap = lambda Y: np.linalg.norm(Y - C, axis=1) - r
    A = [n for n in D if cosb[n] >= -0.2]                                   # may be held during a blink
    A6 = sorted(A, key=lambda n: min(gap(X + D[n]).min(), gap(bases[-1] + D[n]).min()))[:6]
    cons = [(X, ((n, w),)) for n in D for w in (0.5, 1.0)] + [(Bs, ((n, 1.0),)) for n in A for Bs in bases[1:]]
    cons += [(Bs, tuple((n, 1.0) for n in S)) for k in (2, 3) for S in itertools.combinations(A6, k) for Bs in bases]
    lowest = lambda: min((float((gap(Bs + sum(w * D[n] for n, w in S)) - fl).min()) for Bs, S in cons), default=0.0)   # no lid keys: 0
    before = lowest(); D0 = {n: d.copy() for n, d in D.items()}; it = 0
    for it in range(80):
        worst = 0.0
        for Bs, S in cons:
            d = Bs + sum(w * D[n] for n, w in S) - C; n_ = np.linalg.norm(d, axis=1); de = fl - (n_ - r); m_ = de > 1e-9
            if not m_.any(): continue
            nh = d[m_] / n_[m_][:, None]; cin = np.array([np.clip(-(w * D[n][m_] * nh).sum(1), 0, None) for n, w in S])
            sh = np.where(cin.sum(0) > 1e-12, cin / np.maximum(cin.sum(0), 1e-12), 1.0 / len(S))    # pushed back by the keys that pushed in
            for (n, w), f in zip(S, sh): D[n][m_] += (de[m_] * f / w)[:, None] * nh
            worst = max(worst, float(de.max()))
        if worst < 1e-8: break
    ch = {n: float(np.linalg.norm(D[n] - D0[n], axis=1).max()) for n in D}
    for n, c in ch.items():
        if c > 1e-9: Dk[n][rows] = D[n]; changed.add(n)
    nc = min(((float(gap(X + Bl + D[n]).min()) * 1000, n) for n in D if cosb[n] < -0.2), default=(None, None))
    lq[s] = {'keys': len(D), 'with_blink': len(A), 'combined': A6, 'opening': [n for n in D if cosb[n] < -0.2], 'constraints': len(cons), 'iters': it, 'min_over_floor_mm_before': round(before * 1000, 3),
             'after': round(lowest() * 1000, 3), 'changed_mm': {n: round(c * 1000, 3) for n, c in sorted(ch.items(), key=lambda x: -x[1])[:8] if c > 1e-7},
             'not_covered_closed_plus': [nc[1], None if nc[0] is None else round(nc[0], 3)]}
for n in changed:
    P = co(kbs[n]); P[lids] = X0[lids] + Dk[n]; kbs[n].data.foreach_set('co', P.ravel())
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('LIDKEYS', json.dumps(lq))
