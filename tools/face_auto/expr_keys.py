"""T7 · expression keys on the original from an aligned expression scan (no change to the rest shape).

blink: per eye, in polar coordinates about the eyeball axis (centre C, axis A):
  1. the scan's closed lid is sampled as radius R_s(s, phi) by rays toward the axis;
  2. the lid line = the crease (lowest radius) between the original's upper and lower rim, per position s;
  3. both margins of the original's eye opening rotate onto that line (upper 0.3 mm in front);
  4. the rest of the lid region follows by harmonic interpolation, then takes the scan's radius at its new angle
     (weighted down toward the region edge), and is kept 0.4 mm outside the eyeball.
aa: the lower face follows the scan:
  1. the existing jaw_open key is scaled to the strength that best fits the scan's chin;
  2. the inner lip contour of the scan's open mouth (from front depth) is the target of the upper and lower lip edges;
  3. other lower-face skin snaps to the scan surface, harmonically smoothed, fading to zero at the region edge;
  4. the mouth interior (ring, bag) copies its nearest lip edge, teeth and tongue take the scaled jaw key.
Writes <out>/<name>.blend (rig with the new key on 'face' and parts), <out>/<name>_qa.json.
Usage: blender -b <rig_mouth.blend> -P expr_keys.py -- <aligned.blend> <eyes_meta.json> <landmarks.json> <blink|aa> <out_dir> <name>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
sys.path.append(os.path.dirname(__file__))
from facelib import bvh_of, hit_y, smoothstep, dist_to

a = sys.argv[sys.argv.index('--') + 1:]
ALIGNED, EYES, LMJ, MODE, OUT, NAME = a[:6]
OUT = os.path.abspath(OUT); os.makedirs(OUT, exist_ok=True)
with bpy.data.libraries.load(ALIGNED) as (src, dst): dst.objects = ['scan']
scan = dst.objects[0]
SV = np.array([tuple(v.co) for v in scan.data.vertices]); SF = [list(p.vertices) for p in scan.data.polygons]
bvh_s = bvh_of(SV, SF)
face = bpy.data.objects['face']; me = face.data
X = np.array([tuple(v.co) for v in me.vertices]); XF = [list(p.vertices) for p in me.polygons]
inner_m = {i for i, m in enumerate(me.materials) if m and m.name == 'mouth_inner'}
skin_v = np.zeros(len(X), bool); inner_v = np.zeros(len(X), bool)
for p in me.polygons:
    (inner_v if p.material_index in inner_m else skin_v)[list(p.vertices)] = True
nb = [set() for _ in range(len(X))]
for f in XF:
    for i in range(len(f)):
        nb[f[i]].add(f[i - 1]); nb[f[i - 1]].add(f[i])
deg = max(len(n) for n in nb); NB = np.full((len(X), deg), -1)
for i, n in enumerate(nb): NB[i, :len(n)] = sorted(n)
def harmonic(D, free, iters=400):
    idx = np.nonzero(free)[0]; nbi = NB[idx]; msk = nbi >= 0; cnt = msk.sum(1)[:, None]
    for _ in range(iters):
        Dn = np.where(msk[..., None], D[np.where(msk, nbi, 0)], 0.0)
        D[idx] = Dn.sum(1) / np.maximum(cnt, 1)
    return D
eyes = json.load(open(EYES))
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
qa = {'mode': MODE}
key = X.copy()

def add_key(ob, name, P):
    if not ob.data.shape_keys: ob.shape_key_add(name='Basis')
    kb = ob.data.shape_keys.key_blocks.get(name) or ob.shape_key_add(name=name, from_mix=False)
    kb.data.foreach_set('co', np.asarray(P, dtype=np.float64).ravel()); return kb

if MODE == 'blink':
    bm = bmesh.new(); bm.from_mesh(me)
    bverts = np.array(sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts})); bm.free()
    for s in 'RL':
        e = eyes[s]; C, A, r = np.array(e['C']), np.array(e['A']), e['r']
        fwd = np.array([0, -1, 0.0]); fwd = fwd - A * (fwd @ A); fwd /= np.linalg.norm(fwd)
        up = np.cross(A, fwd); up = -up if up[2] < 0 else up
        def polar(Q):
            d = Q - C; return d @ A, np.arctan2(d @ up, d @ fwd), np.hypot(d @ up, d @ fwd)
        raw = np.array(e['raw'])
        marg = bverts[dist_to([Vector(p) for p in raw], [Vector(p) for p in X[bverts]]) < 0.003]
        sm, pm, rm = polar(X[marg])
        # split margins by the corner-to-corner chord: corners are the extreme s
        o = np.argsort(sm); s_lo_c, s_hi_c = sm[o[0]], sm[o[-1]]
        p_c = np.interp(sm, [s_lo_c, s_hi_c], [pm[o[0]], pm[o[-1]]])
        is_up = pm > p_c
        su, pu = sm[is_up], pm[is_up]; sl, pl = sm[~is_up], pm[~is_up]
        ou, ol = np.argsort(su), np.argsort(sl)
        phi_up = lambda q: np.interp(q, su[ou], pu[ou]); phi_lo = lambda q: np.interp(q, sl[ol], pl[ol])
        # 1. scan radius grid
        S_ = np.linspace(s_lo_c - 0.002, s_hi_c + 0.002, 45)
        PH = np.linspace(min(pl.min(), pu.min()) - 0.5, max(pl.max(), pu.max()) + 0.6, 160)
        RS = np.full((len(S_), len(PH)), np.nan)
        for i, sv in enumerate(S_):
            base = C + sv * A
            for j, ph in enumerate(PH):
                d = math.cos(ph) * fwd + math.sin(ph) * up
                hit = bvh_s.ray_cast(Vector(base + d * r * 3), Vector(-d))[0]
                if hit is not None: RS[i, j] = np.linalg.norm(np.array(hit) - base)
        def rs_at(q, ph):
            i = np.clip(np.interp(q, S_, np.arange(len(S_))), 0, len(S_) - 1.001); j = np.clip(np.interp(ph, PH, np.arange(len(PH))), 0, len(PH) - 1.001)
            i0, j0 = np.floor(i).astype(int), np.floor(j).astype(int); fi, fj = i - i0, j - j0
            g = lambda a_, b_: RS[a_, b_]
            v = (g(i0, j0) * (1 - fi) * (1 - fj) + g(i0 + 1, j0) * fi * (1 - fj) + g(i0, j0 + 1) * (1 - fi) * fj + g(i0 + 1, j0 + 1) * fi * fj)
            return v
        # 2. lid line: deepest crease between the rims; reported as a share of the opening (0 = lower rim, 1 = upper)
        line_s, line_p, depth = [], [], []
        for i, sv in enumerate(S_):
            if sv < s_lo_c + 0.08 * (s_hi_c - s_lo_c) or sv > s_hi_c - 0.08 * (s_hi_c - s_lo_c): continue
            a0, a1 = phi_lo(sv), phi_up(sv); lo_b, hi_b = a0 + 0.02 * (a1 - a0), a1 - 0.05 * (a1 - a0)
            m = (PH > lo_b) & (PH < hi_b) & ~np.isnan(RS[i])
            if m.sum() < 5: continue
            row = RS[i, m]; ph = PH[m]; k = int(np.argmin(row))
            depth.append(float(min(row[:k + 1].max(), row[k:].max()) - row[k]) * 1000)
            line_s.append(sv); line_p.append(ph[k])
        line_s, line_p, depth = np.array(line_s), np.array(line_p), np.array(depth)
        good = depth > 0.15
        share = (line_p - phi_lo(line_s)) / np.maximum(phi_up(line_s) - phi_lo(line_s), 1e-6)
        SHARE = float(np.median(share[good])) if good.sum() >= 5 else 0.1   # no clear crease: meet near the lower rim
        qa['lid_line_' + s] = {'samples': int(len(line_s)), 'with_crease': int(good.sum()),
                               'crease_depth_mm_median': round(float(np.median(depth)), 3) if len(depth) else 0,
                               'meet_share_used': round(SHARE, 3)}
        meet = lambda q: phi_lo(q) + SHARE * (phi_up(q) - phi_lo(q))
        # measurement: how far the scan's closed lid sits in front of the eyeball, over the opening
        Sg, Pg = np.meshgrid(S_, PH, indexing='ij')
        inside = (Sg > s_lo_c + 0.1 * (s_hi_c - s_lo_c)) & (Sg < s_hi_c - 0.1 * (s_hi_c - s_lo_c)) & (Pg > phi_lo(Sg)) & (Pg < phi_up(Sg)) & ~np.isnan(RS)
        off = (np.sqrt(Sg[inside] ** 2 + RS[inside] ** 2) - r) * 1000
        imid = int(np.argmin(np.abs(S_ - (s_lo_c + s_hi_c) / 2)))
        qa['closed_lid_offset_mm_' + s] = {'p05': round(float(np.percentile(off, 5)), 2), 'p50': round(float(np.median(off)), 2),
                                            'p95': round(float(np.percentile(off, 95)), 2)}
        qa['profile_' + s] = {'phi': PH.tolist(), 'offset_mm': ((np.sqrt(S_[imid] ** 2 + RS[imid] ** 2) - r) * 1000).tolist(),
                              'phi_lo': float(phi_lo(S_[imid])), 'phi_up': float(phi_up(S_[imid])),
                              'orig_offset_mm': None}
        # 3. every lid vertex turns about the eye axis (as in the procedural blink), so the mapping in (s, phi)
        #    stays one-to-one; its radius comes from the scan's closed lid, weighted down toward the region edge
        q, ph, rd = polar(X); dist = np.linalg.norm(X - C, axis=1)
        reach = 0.5
        pu_all, pl_all = phi_up(q), phi_lo(q)
        is_upper = ph >= (pu_all + pl_all) / 2
        w = np.where(is_upper, 1 - smoothstep(ph - pu_all, 0, reach), 1 - smoothstep(pl_all - ph, 0, reach * 0.6))
        # full motion between the corners (margins meet exactly there), fade only beyond the corners
        side = 1 - smoothstep(np.maximum(s_lo_c - q, q - s_hi_c), 0, 0.004)
        w = w * side * (1 - smoothstep(dist, 1.15 * r, 1.45 * r)) * skin_v
        region = w > 1e-4; region[marg] = True; w[marg] = 1.0
        target = np.where(is_upper, meet(q) - pu_all, meet(q) - pl_all)
        nph = ph + target * w
        rs2 = rs_at(q, nph); front = np.where(is_upper, 0.0003, 0.0)
        nr = np.where(np.isnan(rs2), rd, rd + (rs2 + front - rd) * w)
        nr = np.maximum(nr, np.sqrt(np.maximum((r + 0.0004) ** 2 - q ** 2, 0)) * (w > 0) )
        P = C + np.outer(q, A) + np.outer(np.sin(nph) * nr, up) + np.outer(np.cos(nph) * nr, fwd)
        key[region] = P[region]
        # QA: closed gap between margins, eyeball clearance, distance to the scan
        gu = key[marg[is_up]]; gl = key[marg[~is_up]]
        gap = dist_to([Vector(p) for p in gl], [Vector(p) for p in gu]) * 1000
        clear = (np.linalg.norm(key[region] - C, axis=1) - r) * 1000
        ds = np.array([bvh_s.find_nearest(Vector(p))[3] for p in key[region]]) * 1000
        qa['blink_' + s] = {'region_verts': int(region.sum()), 'margin_up': int(is_up.sum()), 'margin_lo': int((~is_up).sum()),
                           'closed_gap_mm': {'p50': round(float(np.median(gap)), 3), 'max': round(float(gap.max()), 3)},
                           'eyeball_clearance_mm_min': round(float(clear.min()), 3),
                           'to_scan_mm': {'p50': round(float(np.median(ds)), 3), 'p95': round(float(np.percentile(ds, 95)), 3)}}
    add_key(face, 'blink_scan', key)
    qa['rest_offset_mm'] = 0.0
else:
    kb = me.shape_keys.key_blocks
    DJ = np.array([tuple(p.co) for p in kb['jaw_open'].data]) - X
    # lip edges: skin vertices on an edge shared with the mouth interior; lower ones are the ones the jaw carries
    edge_v = np.nonzero(skin_v & inner_v)[0]
    dj_e = np.linalg.norm(DJ[edge_v], axis=1); lower_e = dj_e > 0.35 * dj_e.max()
    d_edge = dist_to([Vector(p) for p in X[edge_v]], [Vector(p) for p in X]) * 1000
    # 1. jaw strength that best fits the scan's chin (strong-jaw skin away from the lips)
    jm = np.linalg.norm(DJ, axis=1); chin = skin_v & (jm > 0.5 * jm.max()) & (d_edge > 8)
    ts = np.arange(0.0, 3.01, 0.05)
    cost = [np.median([bvh_s.find_nearest(Vector(p))[3] for p in (X[chin] + t_ * DJ[chin])[::4]]) for t_ in ts]
    T_JAW = float(ts[int(np.argmin(cost))]); qa['jaw_strength'] = T_JAW
    qa['chin_fit_mm'] = {'t=1': round(float(cost[20]) * 1000, 2), 'best': round(float(min(cost)) * 1000, 2)}
    Q = X + T_JAW * DJ
    # 2. the scan's inner lip contour from front depth
    xl, xr = LT[20][0], LT[22][0]; zc = (LT[34][2] + LT[35][2]) / 2
    xs = np.arange(xl - 0.012, xr + 0.012, 0.0004); zs = np.arange(zc - 0.04, zc + 0.015, 0.0004)
    Dp = np.array([[hit_y(bvh_s, x, z) or np.nan for x in xs] for z in zs])
    box = (np.abs(xs[None, :]) < 0.6 * (xr - xl)) & (np.abs(zs[:, None] - zc) < 0.02)
    # the opening = where the scan is much deeper than the original's closed mouth at the same spot
    bvh_o = bvh_of(X, XF)
    D0 = np.array([[hit_y(bvh_o, x, z) or np.nan for x in xs] for z in zs])
    deep = (np.nan_to_num(Dp - D0, nan=-9) > 0.006) & (np.abs(xs[None, :]) < (xr - xl))
    # connected component of the deep region around the mouth centre
    from collections import deque
    i0 = int(np.argmin(np.abs(zs - (zc - 0.006)))); j0 = int(np.argmin(np.abs(xs)))
    if not deep[i0, j0]:
        cand = np.argwhere(deep & box); i0, j0 = cand[np.argmin(np.abs(cand[:, 1] - j0) + np.abs(cand[:, 0] - i0))]
    seen = np.zeros_like(deep); dq = deque([(i0, j0)]); seen[i0, j0] = True
    while dq:
        i, j = dq.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a_, b_ = i + di, j + dj
            if 0 <= a_ < len(zs) and 0 <= b_ < len(xs) and deep[a_, b_] and not seen[a_, b_]:
                seen[a_, b_] = True; dq.append((a_, b_))
    cols = np.nonzero(seen.any(0))[0]
    cx = xs[cols]; ztop = np.array([zs[np.nonzero(seen[:, c])[0].max()] for c in cols]); zbot = np.array([zs[np.nonzero(seen[:, c])[0].min()] for c in cols])
    sm5 = lambda v: np.convolve(np.pad(v, 3, mode='edge'), np.ones(7) / 7, mode='valid')
    ztop, zbot = sm5(ztop), sm5(zbot)                              # the 0.4 mm depth grid is stair-stepped
    sxl, sxr = cx.min(), cx.max()
    qa['scan_mouth'] = {'width_mm': round((sxr - sxl) * 1000, 1), 'open_height_mm_centre': round(float(np.interp(0, cx, ztop - zbot)) * 1000, 1),
                        'orig_width_mm': round((xr - xl) * 1000, 1)}
    # 3. lip edge targets: same relative position between the corners, on the lip just outside the opening
    D = T_JAW * DJ
    ex = X[edge_v, 0]; u = (ex - xl) / (xr - xl); tx = sxl + u * (sxr - sxl)
    for k, vi in enumerate(edge_v):
        if lower_e[k]: z = np.interp(tx[k], cx, zbot) - 0.0003; y = hit_y(bvh_s, tx[k], z - 0.0005)
        else: z = np.interp(tx[k], cx, ztop) + 0.0003; y = hit_y(bvh_s, tx[k], z + 0.0005)
        if y is None: continue
        D[vi] = np.array([tx[k], y, z]) - X[vi]
    # 4. lower-face skin away from the lips snaps to the scan; near the lips harmonic; fade to the scaled jaw key
    mc = np.array([0, X[edge_v, 1].mean(), zc]); dm = np.linalg.norm(X - mc, axis=1)
    # weight: whole lower face, fading out toward the cheeks, below the nose (12 mm ramp) and away from the nose itself
    w = (1 - smoothstep(dm, 0.035, 0.055)) * smoothstep(LT[16][2] - 0.004 - X[:, 2], 0, 0.012)         * smoothstep(np.linalg.norm(X - LT[16], axis=1), 0.012, 0.022) * skin_v
    snap = (w > 0) & (d_edge > 4)
    for vi in np.nonzero(snap)[0]:
        hit = bvh_s.find_nearest(Vector(Q[vi]))[0]
        D[vi] = w[vi] * (np.array(hit) - X[vi]) + (1 - w[vi]) * D[vi]
    band = skin_v & (d_edge <= 4) & (d_edge > 0.01) & (w > 0)
    D = harmonic(D, band, iters=300)
    # closest points jump between neighbours (and the two heads differ by ~1 mm): smooth the displacement over the
    # region with the lip edges held, so the key follows the scan's overall shape without its noise
    reg_free = (w > 0) & skin_v & ~np.isin(np.arange(len(X)), edge_v)
    idx = np.nonzero(reg_free)[0]; nbi = NB[idx]; msk = nbi >= 0; cnt = msk.sum(1)[:, None]
    for _ in range(int(os.environ.get('AA_SMOOTH', '300'))):
        Dn = np.where(msk[..., None], D[np.where(msk, nbi, 0)], 0.0).sum(1) / np.maximum(cnt, 1)
        D[idx] = 0.5 * D[idx] + 0.5 * Dn
    # smooth the lip edge targets along the edge too (lower and upper separately)
    for grp in (lower_e, ~lower_e):
        ids = edge_v[grp]; o_ = np.argsort(X[ids, 0]); ids = ids[o_]
        Dg = D[ids].copy(); D[ids] = np.array([Dg[max(0, i - 2):i + 3].mean(0) for i in range(len(ids))])
    # 5. mouth interior follows the matching lip edge's correction; teeth and tongue take the scaled jaw key
    corr = D[edge_v] - T_JAW * DJ[edge_v]
    from mathutils.kdtree import KDTree
    kd = KDTree(len(edge_v))
    for k, vi in enumerate(edge_v): kd.insert(Vector(X[vi]), k)
    kd.balance()
    for vi in np.nonzero(inner_v & ~skin_v)[0]:
        near = kd.find_n(Vector(X[vi]), 8)
        best = min(near, key=lambda h: np.linalg.norm(DJ[edge_v[h[1]]] - DJ[vi]))
        D[vi] = T_JAW * DJ[vi] + corr[best[1]]
    key = X + D
    for nm in ('teeth_lo', 'tongue', 'teeth_up'):
        ob = bpy.data.objects.get(nm)
        if not ob: continue
        B0 = np.array([tuple(v.co) for v in ob.data.vertices]); J = np.array([tuple(p.co) for p in ob.data.shape_keys.key_blocks['jaw_open'].data])
        add_key(ob, 'aa_scan', B0 + T_JAW * (J - B0))
    add_key(face, 'aa_scan', key)
    reg = (w > 0.5) & skin_v
    ds = np.array([bvh_s.find_nearest(Vector(p))[3] for p in key[reg]]) * 1000
    qa['to_scan_mm_lower_face'] = {'p50': round(float(np.median(ds)), 3), 'p95': round(float(np.percentile(ds, 95)), 3)}
    ce = np.abs(X[edge_v, 0]) < 0.004
    qa['open_height_mm_centre_keyed'] = round(float(key[edge_v[ce & ~lower_e], 2].mean() - key[edge_v[ce & lower_e], 2].mean()) * 1000, 1)
    qa['rest_offset_mm'] = 0.0

# folds: faces the key turns over relative to rest
T = np.array([f[:3] for f in XF if len(f) == 3])
def tn(P):
    n = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]); return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-14)
moved = np.linalg.norm(key - X, axis=1) > 1e-7
mt = moved[T].any(1)
flip = ((tn(key) * tn(X)).sum(1) < 0) & mt
qa['flipped_faces'] = int(flip.sum()); qa['moved_faces'] = int(mt.sum())
json.dump(qa, open(os.path.join(OUT, NAME + '_qa.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + '.blend'), compress=True)
print('KEYS', json.dumps(qa))
