"""M1 · Tripo organ parts as shape donors for the ring organs (organ_eye / organ_mouth with SHAPE=tripo).

The Tripo eye and mouth parts are single fused patches (lids + eyeball + lashes, lips + teeth), so their topology
cannot be rigged. Their shape can: this script places each part on the head so that its opening matches the
original's, and the ring builders then read the depth of their rings from the part instead of the original head.

Eye part (one per style, used for both eyes, mirrored when that fits better):
1. front ray grid over the part; a sphere fitted to the hits round the centre = the eyeball
2. hits on that sphere, connected to the centre = the eye opening; its x extremes = the corners
   (split part from Tripo 'Generate in Parts': whole parts grown from the centre part over neighbours that lie on or
   inside the sphere, of any size - an anime sclera comes in ~50 fragments; lids, lashes and skin lie outside it;
   an opening that is not eye-like falls back to the old rule without the sphere, then to the image)
3. the eyeball itself is removed (the rig has its own eyeball); lids, skin and lashes stay
4. frame: corners midpoint, corner line, up; scale along the corner line by the corner distance, up by the
   opening height, depth like the corner line; mirror chosen by the overlap with the original's opening
   (env DONOR_DEPTH=fit, experimental: depth scale and shift fitted so the opening outline lies at the depth of the
   original's margin; the json reports outline_off_mm, how far the outline sits in front of that margin, either way)
Mouth part (open lips with teeth):
1. front ray grid; the deep region round the centre = the mouth opening; its x extremes = the corners
2. frame from the corners to the original's mouth corners (seam ends), one scale
Writes objects donor_eye_L, donor_eye_R, donor_mouth into <out.blend> (+ <out>_donor.json).
The Tripo parts are fused (the lids run smoothly into the eyeball) and untextured, so the eye opening is found in
the part's own front image (white sclera + the iris it encloses, inside the part silhouette) and carried onto the
part by matching the image silhouette to the part's front silhouette.
Usage: blender -b <aligned.blend> -P organ_donor.py -- <eye.glb> <mouth.glb> <eyes_meta.json> <dense.json> <out.blend> <eye_image.png>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facelib import lids, inside2d

a = sys.argv[sys.argv.index('--') + 1:]
EYE_GLB, MOUTH_GLB, EMJ, DJ, OUT = a[0], a[1], a[2], a[3], os.path.abspath(a[4]); EYE_IMG = a[5]
HERE = os.path.dirname(os.path.abspath(__file__))
EM = json.load(open(EMJ)); D = json.load(open(DJ)); RAW = {int(k): np.array(v) for k, v in D['_raw'].items()}
PT = json.load(open(os.path.join(HERE, 'data', 'mp_mirror_pairs.json')))
partner = {}
for i, j in PT['pairs']: partner[i] = j; partner[j] = i
info = {}

def load_part(fn):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=fn)
    new = [o for o in bpy.data.objects if o not in before]
    ms = [o for o in new if o.type == 'MESH']
    V, F, PI, off = [], [], [], 0
    for k, o in enumerate(ms):
        X = np.array([tuple(o.matrix_world @ v.co) for v in o.data.vertices]); V.append(X)
        F += [[i + off for i in p.vertices] for p in o.data.polygons]; PI += [k] * len(o.data.polygons); off += len(X)
    for o in new: bpy.data.objects.remove(o)
    bm = bmesh.new(); L_part = bm.faces.layers.int.new('part')
    vs = [bm.verts.new(tuple(p)) for p in np.vstack(V)]
    for f, k in zip(F, PI):
        try: bm.faces.new([vs[i] for i in f])[L_part] = k
        except ValueError: pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return bm

def front_grid(bm, n=220):
    bm.verts.ensure_lookup_table(); X = np.array([tuple(v.co) for v in bm.verts])
    lo, hi = X.min(0), X.max(0); bvh = BVHTree.FromBMesh(bm)
    xs = np.linspace(lo[0], hi[0], n); zs = np.linspace(lo[2], hi[2], n)
    H = np.full((n, n, 3), np.nan); Pg = np.full((n, n), -1, int)
    bm.faces.ensure_lookup_table(); Lp = bm.faces.layers.int.get('part')
    for i, z in enumerate(zs):
        for j, x in enumerate(xs):
            h = bvh.ray_cast(Vector((x, lo[1] - 1.0, z)), Vector((0, 1, 0)))
            if h[0] is not None:
                H[i, j] = tuple(h[0])
                if Lp is not None: Pg[i, j] = bm.faces[h[2]][Lp]
    front_grid.parts = Pg
    return xs, zs, H, X

def component(mask, i0, j0):
    out = np.zeros_like(mask); st = [(i0, j0)]
    while st:
        i, j = st.pop()
        if 0 <= i < mask.shape[0] and 0 <= j < mask.shape[1] and mask[i, j] and not out[i, j]:
            out[i, j] = True; st += [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)]
    return out

def fill_holes(mask):
    outside = component(~mask, 0, 0); return ~outside

def outline(mask, xs, zs):
    """boundary cells of a star-shaped mask as a polygon ordered by angle (x, z)"""
    b = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
    ii, jj = np.nonzero(b); P = np.c_[xs[jj], zs[ii]]; c = P.mean(0)
    return P[np.argsort(np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0]))]

def depth_at(H, xs, zs, p):
    i, j = int(np.argmin(np.abs(zs - p[1]))), int(np.argmin(np.abs(xs - p[0])))
    for r in range(0, 12):
        blk = H[max(0, i - r):i + r + 1, max(0, j - r):j + r + 1, 1]
        if np.isfinite(blk).any(): return float(np.nanmin(blk))
    return float('nan')

def sphere_fit(P):
    A = np.c_[2 * P, np.ones(len(P))]; s = np.linalg.lstsq(A, (P ** 2).sum(1), rcond=None)[0]
    C = s[:3]; return C, math.sqrt(max(s[3] + C @ C, 1e-12))

def raster_iou(A, B, n=160):
    lo = np.minimum(A.min(0), B.min(0)); hi = np.maximum(A.max(0), B.max(0))
    g = np.stack(np.meshgrid(np.linspace(lo[0], hi[0], n), np.linspace(lo[1], hi[1], n)), -1).reshape(-1, 2)
    to3 = lambda Q: np.c_[Q[:, 0], np.zeros(len(Q)), Q[:, 1]]
    ia, ib = inside2d(to3(A), to3(g)), inside2d(to3(B), to3(g))
    return (ia & ib).sum() / max(1, (ia | ib).sum())

def place(bm, M4, name):
    me = bpy.data.meshes.new(name); bm2 = bm.copy()
    for v in bm2.verts: v.co = Vector(tuple((M4 @ np.r_[np.array(v.co), 1.0])[:3]))
    bm2.normal_update(); bm2.to_mesh(me); bm2.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); o.hide_render = True
    return o

def frame(origin, ex, up):
    ex = ex / np.linalg.norm(ex); ez = up - ex * (up @ ex); ez /= np.linalg.norm(ez); ey = np.cross(ez, ex)
    return origin, np.c_[ex, ey, ez]                     # columns: corner line, depth (into the head), up

# ------------------------------------------------------------------ eye
bm = load_part(EYE_GLB); xs, zs, H, X = front_grid(bm)
size = max(np.ptp(X[:, 0]), np.ptp(X[:, 2])); ok = ~np.isnan(H[..., 0])
cx, cz = (X[:, 0].min() + X[:, 0].max()) / 2, (X[:, 2].min() + X[:, 2].max()) / 2
gx, gz = np.meshgrid(xs, zs)
# split part (Tripo 'Generate in Parts'): start from the part under the centre (pupil / iris) and add neighbouring
# parts that belong to the eyeball. The eyeball parts (iris, pupil, highlights, sclera - on a fragmented part the
# sclera comes in dozens of small pieces) lie on one sphere or inside it (a recessed anime iris); lids, lashes and
# skin lie outside it, and where a lid joins the eyeball smoothly (upper lid running into the sclera) only the sphere
# tells them apart. Sphere: centre on the iris axis, fitted to the hits left and right of the iris (sclera in every
# style, lids cover the top and bottom), then refitted to the sclera parts taken. A neighbour joins when its hits
# lie on / inside the sphere, it does not step out of the sphere at the shared edge (lid margin), it is level with
# or behind the edge and it does not touch the part border. The cells showing those parts are the opening.
# If the opening is not eye-like (round, or shrunk by a refit) the old rule runs without the sphere, then the image.
Pg = front_grid.parts; nparts = int(Pg.max()) + 1; eye_parts = None
# TOL_RES sits midway in the gap seen on the 4 test styles: highest part taken +0.123 R (realistic caruncle), lowest
# part that must stay out +0.166 R (semi lower lid)
TOL_RES, TOL_STEP, TOL_SMALL = 0.145, 0.015, 0.05       # relative to the eyeball radius
def axis_sphere(P, xc, zc):
    """sphere with its centre on the line x = xc, z = zc: |P - C|^2 = R^2 is linear in yC and R^2 - yC^2"""
    A = np.c_[2 * P[:, 1], np.ones(len(P))]; b = (P[:, 0] - xc) ** 2 + (P[:, 2] - zc) ** 2 + P[:, 1] ** 2
    yC, k = np.linalg.lstsq(A, b, rcond=None)[0]; return np.array([xc, yC, zc]), math.sqrt(max(k + yC * yC, 1e-12))
def trimmed_axis_sphere(P, xc, zc, keep_pct, n):
    keep = np.ones(len(P), bool)
    for _ in range(n):
        C, R = axis_sphere(P[keep], xc, zc); res = np.abs(np.linalg.norm(P - C, axis=1) - R); keep = res <= np.percentile(res, keep_pct)
    return C, R
if nparts > 3:
    ic, jc = np.argmin(np.abs(zs - cz)), np.argmin(np.abs(xs - cx))
    if Pg[ic, jc] < 0:
        ii_, jj_ = np.nonzero(Pg >= 0); k = np.argmin((ii_ - ic) ** 2 + (jj_ - jc) ** 2); ic, jc = ii_[k], jj_[k]
    c0 = int(Pg[ic, jc]); Yg = H[..., 1]
    okc = Pg >= 0
    edge_c = okc & ~(np.roll(okc, 1, 0) & np.roll(okc, -1, 0) & np.roll(okc, 1, 1) & np.roll(okc, -1, 1))
    eq, ec = np.unique(Pg[edge_c], return_counts=True); touches = {int(q) for q, c in zip(eq, ec) if c >= 3}   # lids, skin
    hq, hc = np.unique(Pg[okc], return_counts=True); small = {int(q) for q, c in zip(hq, hc) if c < 0.003 * okc.sum()}   # lashes
    gi_, gj_ = np.nonzero(Pg == c0); ci_, cj_ = gi_.mean(), gj_.mean(); ri_ = math.sqrt(len(gi_) / math.pi)
    xc_, zc_ = np.interp(cj_, np.arange(len(xs)), xs), np.interp(ci_, np.arange(len(zs)), zs)
    I_, J_ = np.mgrid[:Pg.shape[0], :Pg.shape[1]]
    # left and right of the iris, only on parts that are neither border parts (skin, lid) nor lash strands: the band
    # then ends at the corners, and the first sphere is within a few % of the final one
    band = okc & ~np.isin(Pg, list(touches | small | {c0})) & (np.abs(I_ - ci_) < 0.5 * ri_) & (np.abs(J_ - cj_) > 1.15 * ri_)
    def edge_steps(Hp, inside, parts):
        """per part of `parts`: (depth step, step out of the sphere) across its edge with the `inside` cells"""
        st = {}
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nbq = np.roll(np.roll(Pg, di, 0), dj, 1); m = inside & np.isin(nbq, parts)
            dy = np.roll(np.roll(Yg, di, 0), dj, 1)[m] - Yg[m]; dr = np.roll(np.roll(Hp, di, 0), dj, 1)[m] - Hp[m]
            for q, a_, b_ in zip(nbq[m].tolist(), dy.tolist(), dr.tolist()): st.setdefault(q, []).append((a_, b_))
        return st
    def grow(Ce, Re):
        """eyeball parts for the sphere (Ce, Re), refitted to the sclera parts taken; None: old rule without sphere"""
        hist, prev, areas = [], None, []
        for it in range(6):
            Hr = (np.linalg.norm(H - Ce, axis=2) - Re) / Re if Ce is not None else np.zeros(Pg.shape)
            med = {int(q): float(np.median(Hr[Pg == q])) for q in hq}; Hp = np.maximum(Hr, 0)
            def joins(q, st):
                if q in touches or len(st) < 2: return False
                dy, dr = np.median(np.array(st), 0)
                if Ce is None: return q not in small and dy > -0.01 * size               # no sphere: level with or behind the edge
                return med[q] < (TOL_SMALL if q in small else TOL_RES) and dr < TOL_STEP and dy > -0.01 * size
            ban = set()
            for _ in range(8):
                take = {c0}
                for _ in range(200):
                    rest = [int(q) for q in hq if q not in take and q not in ban]
                    new = {q for q, st in edge_steps(Hp, np.isin(Pg, list(take)), rest).items() if joins(q, st)}
                    if not new: break
                    take |= new
                if Ce is None: break
                # every part must also pass against all the others: a lid margin can slip in over a short edge before
                # the rest of its edge (where it steps out of the sphere) is taken
                bad = {q for q in take - {c0} if not joins(q, edge_steps(Hp, np.isin(Pg, list(take - {q})), [q]).get(q, []))}
                if not bad: break
                ban |= bad
            op = fill_holes(np.isin(Pg, list(take)))
            # a part seen only inside the opening and on the sphere is eyeball whatever its depth step (a highlight)
            enc = {int(q) for q in hq if q not in take and abs(med[q]) < TOL_SMALL and op[Pg == q].all()} if Ce is not None else set()
            if enc: take |= enc; op = fill_holes(np.isin(Pg, list(take)))
            hist.append(len(take)); areas.append(int(op.sum()))
            if Ce is None: break
            S = np.isin(Pg, [q for q in take if abs(med[q]) < 0.05])            # sclera parts (not the iris recess)
            if S.sum() < 50: break
            C1, R1 = trimmed_axis_sphere(H[S], xc_, zc_, 80, 4)
            if take == prev and abs(R1 - Re) < 0.003 * Re: break
            prev, Ce, Re = take, C1, R1
        oi, oj = np.nonzero(op)
        # an eye opening is wider than tall (a take that collapsed onto the iris is round), and no refit may shrink it much
        good = np.ptp(xs[oj]) > 1.4 * np.ptp(zs[oi]) and areas[-1] >= 0.7 * max(areas)
        return take, op, good, {'passes': hist, 'areas': areas, 'dropped': len(ban), 'sphere_r_rel': None if Re is None else round(float(Re / size), 4)}
    C0, R0 = trimmed_axis_sphere(H[band], xc_, zc_, 60, 10) if band.sum() >= 30 else (None, None)
    take, opening, good, gst = grow(C0, R0); method = 'sphere' if R0 is not None else 'no_sphere'
    if not good and R0 is not None:
        take, opening, good, gst = grow(None, None); method = 'no_sphere'
    info['eye_parts'] = {'parts': nparts, 'method': method if good else 'image', 'eyeball_parts': len(take), 'border_parts': len(touches),
                         'sphere_r0_rel': None if R0 is None else round(float(R0 / size), 4), **gst}
    if good: ball = np.isin(Pg, list(take)); eye_parts = take
if eye_parts is None:
    # eye opening from the part's front image: inside the part silhouette (not the border-connected background), the
    # bright unsaturated pixels (sclera) connected to the centre, holes filled (iris, pupil)
    img = bpy.data.images.load(EYE_IMG); iw, ih = img.size
    px = np.array(img.pixels[:]).reshape(ih, iw, 4)[::-1, :, :3][::2, ::2]   # top row first, half size
    mx_, mn_ = px.max(2), px.min(2); sat = (mx_ - mn_) / np.maximum(mx_, 1e-6)
    bgc = np.median(np.r_[px[0], px[-1], px[:, 0], px[:, -1]], 0)
    bgm = component(np.linalg.norm(px - bgc, axis=2) < 0.06, 0, 0)            # background: flood from the corner
    sil_i = ~bgm
    ii, jj = np.nonzero(sil_i)
    # pupil: the darkest blob near the image centre; along its row the iris ends where the sclera starts (bright, grey)
    ci, cj = int(ii.mean()), int(jj.mean())
    dark = sil_i & (mx_ < max(0.18, np.percentile(mx_[sil_i], 3) + 0.05))
    di, dj = np.nonzero(dark); k = np.argmin((di - ci) ** 2 + (dj - cj) ** 2)
    pup = component(dark, di[k], dj[k]); pi_, pj_ = np.argwhere(pup).mean(0).astype(int)
    def scl_edge(sign):
        row = mx_[pi_]; srow = sat[pi_]; j = pj_
        lim = int(0.45 * (jj.max() - jj.min()))
        for t in range(3, lim):
            j = pj_ + sign * t
            if not sil_i[pi_, j]: break
            if row[j] > 0.55 and srow[j] < 0.35: return j
        seg = row[pj_ + sign * 3: pj_ + sign * lim: sign]; return pj_ + sign * (3 + int(np.argmax(seg)))
    jR, jL = scl_edge(1), scl_edge(-1)
    seeds = [(pi_, min(jR + 3, px.shape[1] - 1)), (pi_, max(jL - 3, 0))]
    scol = np.mean([px[a_ - 2:a_ + 3, b_ - 2:b_ + 3].reshape(-1, 3).mean(0) for a_, b_ in seeds], 0)
    # scans from the pupil: pixels are 'eye' (sclera or iris) until they turn skin-like or dark (lid line, lashes).
    # skin colour = median of the silhouette band 6-20 px inside its edge; sclera colour = just outside the iris edges
    inner = sil_i.copy()
    for _ in range(6): inner &= np.roll(inner, 1, 0) & np.roll(inner, -1, 0) & np.roll(inner, 1, 1) & np.roll(inner, -1, 1)
    band = inner.copy()
    for _ in range(14): band &= np.roll(band, 1, 0) & np.roll(band, -1, 0) & np.roll(band, 1, 1) & np.roll(band, -1, 1)
    skin = np.median(px[inner & ~band], 0)
    scl = np.mean([px[a_ - 2:a_ + 3, b_ - 2:b_ + 3].reshape(-1, 3).mean(0) for a_, b_ in seeds], 0)
    irc = px[pi_, int((pj_ + jR) / 2)]
    def is_eye(i, j):
        if math.hypot(i - pi_, j - (jR + jL) / 2) < 0.95 * (jR - jL) / 2: return True       # inside the iris (pupil is dark)
        c = px[i, j]; dk = np.linalg.norm(c - skin)
        return (np.linalg.norm(c - scl) < dk or np.linalg.norm(c - irc) < dk) and mx_[i, j] > 0.25 and sil_i[i, j]
    ir0 = (jR - jL) / 2.0
    def run(i, j, di, dj, lim):
        n = 0
        while 0 <= i + di * (n + 1) < px.shape[0] and 0 <= j + dj * (n + 1) < px.shape[1] and n < lim and is_eye(i + di * (n + 1), j + dj * (n + 1)): n += 1
        return n
    lim = int(3.5 * ir0) + 10
    up = run(pi_, pj_, -1, 0, lim); dn = run(pi_, pj_, 1, 0, lim)
    rows = range(int(pi_ - 0.35 * ir0), int(pi_ + 0.36 * ir0) + 1, max(1, int(ir0 / 12)))
    ext_r = max((j0_ + run(i_, j0_, 0, 1, lim), i_) for i_ in rows for j0_ in [jR])
    ext_l = min((j0_ - run(i_, j0_, 0, -1, lim), i_) for i_ in rows for j0_ in [jL])
    # opening: two half-ellipses (upper from the corners over the top point, lower under the bottom point)
    cxo = (ext_r[0] + ext_l[0]) / 2; half = (ext_r[0] - ext_l[0]) / 2; zc_ = (ext_r[1] + ext_l[1]) / 2
    th = np.linspace(0, 2 * np.pi, 120, endpoint=False)
    yy_ = np.where(np.sin(th) > 0, -(pi_ - up - zc_) * 0 - (zc_ - (pi_ - up)), (pi_ + dn) - zc_)
    Hl = np.c_[zc_ + np.where(np.sin(th) > 0, -(zc_ - (pi_ - up)), (pi_ + dn) - zc_) * np.abs(np.sin(th)), cxo + half * np.cos(th)]
    grown = np.zeros_like(sil_i)
    ir_ = (jR - jL) / 2.0
    gi, gj = np.mgrid[:px.shape[0], :px.shape[1]]
    iris_disc = np.hypot(gi - pi_, gj - (jR + jL) / 2) < ir_
    P2 = np.argwhere(grown | iris_disc).astype(float)
    def hull(Pt):
        Pt = Pt[np.lexsort((Pt[:, 1], Pt[:, 0]))]; cr = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo_, up_ = [], []
        for p_ in Pt:
            while len(lo_) >= 2 and cr(lo_[-2], lo_[-1], p_) <= 0: lo_.pop()
            lo_.append(p_)
        for p_ in Pt[::-1]:
            while len(up_) >= 2 and cr(up_[-2], up_[-1], p_) <= 0: up_.pop()
            up_.append(p_)
        return np.array(lo_[:-1] + up_[:-1])
    # image -> part mapping (silhouette boxes); seeds in the part grid: the iris centre and the sclera just outside it
    i0b, i1b, j0b, j1b = ii.min(), ii.max(), jj.min(), jj.max()
    okx = np.nonzero(ok.any(0))[0]; okz = np.nonzero(ok.any(1))[0]
    x0p, x1p, z0p, z1p = xs[okx.min()], xs[okx.max()], zs[okz.min()], zs[okz.max()]
    to_part = lambda I, J: np.c_[x0p + (np.asarray(J) - j0b) / max(1, j1b - j0b) * (x1p - x0p), z1p - (np.asarray(I) - i0b) / max(1, i1b - i0b) * (z1p - z0p)]
    cell = lambda P: (int(np.clip(np.searchsorted(zs, P[1]), 0, len(zs) - 1)), int(np.clip(np.searchsorted(xs, P[0]), 0, len(xs) - 1)))
    irisP = to_part([pi_], [(jR + jL) / 2])[0]; sclR = to_part([pi_], [jR + 0.25 * (jR - jL)])[0]; sclL = to_part([pi_], [jL - 0.25 * (jR - jL)])[0]
    irad = 0.5 * (jR - jL) / max(1, j1b - j0b) * (x1p - x0p)
    # lid margin = crease in the part's front depth map (large |Laplacian|); flood from the sclera seeds without crossing it
    Yf = np.where(ok, H[..., 1], np.nanmax(H[..., 1]) + 0.2 * size)
    Lp = np.abs(np.roll(Yf, 1, 0) + np.roll(Yf, -1, 0) + np.roll(Yf, 1, 1) + np.roll(Yf, -1, 1) - 4 * Yf)
    gx, gz = np.meshgrid(xs, zs)
    near_eye = np.hypot(gx - irisP[0], gz - irisP[1]) < 4 * irad
    crease = Lp > np.percentile(Lp[ok & near_eye], 88)
    iris_g = np.hypot(gx - irisP[0], gz - irisP[1]) < 1.05 * irad
    free = ok & ~crease
    ball = np.zeros_like(ok)
    for sd in (sclR, sclL):
        c_ = cell(sd)
        if free[c_]: ball |= component(free & ~iris_g, *c_)
    ball = fill_holes(ball | iris_g) & ok
    opening = ball
if os.environ.get('DONOR_DEBUG'): np.savez(os.environ['DONOR_DEBUG'], Y=H[..., 1], ball=ball, opening=opening, xs=xs, zs=zs)
Co, ro = sphere_fit(H[ball])
poly = outline(opening, xs, zs)
k1, k2 = int(np.argmax(poly[:, 0])), int(np.argmin(poly[:, 0]))
cor_o = [poly[k1], poly[k2]]; h_o = np.ptp(poly[:, 1])
if os.environ.get('DONOR_DEBUG'): np.savez(os.environ['DONOR_DEBUG'], Y=H[..., 1], ball=ball, opening=opening, xs=xs, zs=zs, Co=Co, ro=ro)
# remove the eyeball (on or inside the fitted sphere)
d = np.array([(Vector(tuple(v.co)) - Vector(tuple(Co))).length for v in bm.verts])
if eye_parts is not None:
    Lp = bm.faces.layers.int.get('part'); cnt = {}
    for f in bm.faces: cnt[f[Lp]] = cnt.get(f[Lp], 0) + 1
    # small parts that hardly show in the front grid are lash strands (~1 cell per 20 faces); small surface patches
    # (a fragmented lid shows like any surface, ~0.2 cells per face) stay
    vis = {int(q): int(c) for q, c in zip(*np.unique(Pg[Pg >= 0], return_counts=True))}; dens = (Pg >= 0).sum() / len(bm.faces)
    tiny = {q for q, c in cnt.items() if c < 0.004 * len(bm.faces) and vis.get(q, 0) < 0.6 * dens * c}
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[Lp] in eye_parts or f[Lp] in tiny], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    info['eye_parts']['removed_tiny'] = len(tiny)
else:
    Vx = np.array([tuple(v.co) for v in bm.verts]); in_open = inside2d(np.c_[poly[:, 0], np.zeros(len(poly)), poly[:, 1]], Vx)
    bmesh.ops.delete(bm, geom=[v for v, dd, io in zip(bm.verts, d, in_open) if abs(dd - ro) < 0.015 * size or (io and dd < ro)], context='VERTS')
yc = (depth_at(H, xs, zs, cor_o[0]) + depth_at(H, xs, zs, cor_o[1])) / 2   # depth of the corners
info['eye_part'] = {'size': float(size), 'eyeball_r_rel': float(ro / size), 'opening_w_rel': float(np.linalg.norm(cor_o[0] - cor_o[1]) / size), 'opening_h_rel': float(h_o / size)}
for s in 'LR':
    rim3 = np.array(EM[s]['raw']); Lr = lids(rim3, np.linspace(0, 1, 5))
    A3, B3 = (Lr['outer'], Lr['inner']) if Lr['outer'][0] > Lr['inner'][0] else (Lr['inner'], Lr['outer'])   # +x corner, -x corner
    org_t = (A3 + B3) / 2; C = np.array(EM[s]['C'])
    view = (rim3.mean(0) - C); view /= np.linalg.norm(view)
    ex_t = A3 - B3; up_t = np.array([0, 0, 1.0]) - view * view[2]
    _, R_t = frame(org_t, ex_t, up_t)
    if R_t[:, 1] @ view > 0: R_t[:, 1] *= -1                           # depth column points into the head
    w_t = np.linalg.norm(B3 - A3); P_t = (rim3 - org_t) @ R_t; h_t = np.ptp(P_t[:, 2])
    best = None
    for mirror in (False, True):
        mx = -1.0 if mirror else 1.0
        a_o, b_o = (cor_o[0], cor_o[1])                                  # +x then -x in the part
        if mirror: a_o, b_o = b_o * np.array([-1, 1]), a_o * np.array([-1, 1])
        po = poly * np.array([mx, 1])
        mid = (a_o + b_o) / 2; ex_o = a_o - b_o; ang_o = math.atan2(ex_o[1], ex_o[0])
        c_, s_ = math.cos(-ang_o), math.sin(-ang_o)
        q = (po - mid) @ np.array([[c_, -s_], [s_, c_]]).T                # part opening in its corner frame
        sx, sz = w_t / np.linalg.norm(b_o - a_o), h_t / max(np.ptp(q[:, 1]), 1e-9)
        iou = raster_iou(q * [sx, sz], P_t[:, [0, 2]])
        if best is None or iou > best[0]: best = (iou, mirror, mid, ang_o, sx, sz, q)
    iou, mirror, mid, ang_o, sx, sz, q = best
    mx = -1.0 if mirror else 1.0
    # part -> corner frame: mirror x, move mid to 0 (x, z) and the opening plane to 0 (y), rotate by -ang about y
    T1 = np.eye(4); T1[0, 0] = mx
    T2 = np.eye(4); T2[:3, 3] = [-mid[0], -yc, -mid[1]]
    c_, s_ = math.cos(-ang_o), math.sin(-ang_o); T3 = np.eye(4); T3[0, 0], T3[0, 2], T3[2, 0], T3[2, 2] = c_, -s_, s_, c_
    sy = (sx * sz) ** 0.5
    # depth of the opening outline (lids meet the eyeball) vs the original's margin, matched by angle round the opening:
    # fit margin depth = a * outline depth + b. DONOR_DEPTH=fit uses it (depth scale a, shift b); by default the
    # corners sit at the corner depth and the depth scale is sqrt(sx sz) (the fit is only reported)
    qd = q * [sx, sz]; dpt = np.array([depth_at(H, xs, zs, p_) for p_ in poly]) - yc
    angd = np.arctan2(*(qd - qd.mean(0)).T[::-1]); angt = np.arctan2(*(P_t[:, [0, 2]] - P_t[:, [0, 2]].mean(0)).T[::-1])
    dm_ = dpt[np.argmin(np.abs(np.angle(np.exp(1j * (angt[:, None] - angd[None, :])))), axis=1)]
    ok_ = np.isfinite(dm_); a_fit, b_fit = np.linalg.lstsq(np.c_[dm_[ok_], np.ones(ok_.sum())], P_t[ok_, 1], rcond=None)[0]
    a_fit = float(np.clip(a_fit, 0.5 * sy, 2.0 * sy)); b_fit = float(np.median(P_t[ok_, 1] - a_fit * dm_[ok_]))
    off_now = float(np.median(P_t[ok_, 1] - sy * dm_[ok_]))           # + : the outline sits in front of the margin
    fit_depth = os.environ.get('DONOR_DEPTH', 'corner') == 'fit'
    if fit_depth: sy = a_fit
    S = np.diag([sx, sy, sz, 1.0])
    # corner frame: x along the corner line (+x side), y = depth (the part's +y is into the part = into the head), z up
    Rt = np.eye(4); Rt[:3, :3] = R_t; Rt[:3, 3] = org_t
    Tb = np.eye(4); Tb[1, 3] = b_fit if fit_depth else 0.0
    M4 = Rt @ Tb @ S @ T3 @ T2 @ T1
    if mirror:                                                             # mirroring flips the winding
        bm_m = bm.copy(); bmesh.ops.reverse_faces(bm_m, faces=bm_m.faces); place(bm_m, M4, 'donor_eye_' + s); bm_m.free()
    else: place(bm, M4, 'donor_eye_' + s)
    info['eye_' + s] = {'mirror': mirror, 'iou': round(float(iou), 3), 'scale_x': round(float(sx), 4), 'scale_z': round(float(sz), 4),
                        'depth': 'fit' if fit_depth else 'corner', 'scale_y': round(float(sy), 4), 'depth_fit_scale': round(a_fit, 4),
                        'outline_off_mm': round(off_now * 1000, 2), 'depth_shift_mm': round(b_fit * 1000 if fit_depth else 0.0, 2)}
bm.free()

# ------------------------------------------------------------------ mouth
def sym(i):
    p = RAW[i].copy(); j = partner.get(i)
    if j is not None and j in RAW: p = (p + RAW[j] * np.array([-1, 1, 1])) / 2
    elif i in PT['centre']: p[0] = 0
    return p
IU = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]; IL = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
seam = (np.array([sym(i) for i in IU]) + np.array([sym(i) for i in IL])) / 2; seam = seam[np.argsort(-seam[:, 0])]
A3 = seam[0].copy(); B3 = A3 * np.array([-1, 1, 1]); org_t = (A3 + B3) / 2
bm = load_part(MOUTH_GLB); xs, zs, H, X = front_grid(bm)
size = max(np.ptp(X[:, 0]), np.ptp(X[:, 2])); ok = ~np.isnan(H[..., 0])
Y = np.where(ok, H[..., 1], np.nan); front = np.nanpercentile(Y, 10)
cx, cz = (X[:, 0].min() + X[:, 0].max()) / 2, (X[:, 2].min() + X[:, 2].max()) / 2
gx, gz = np.meshgrid(xs, zs); rr_ = np.hypot(gx - cx, gz - cz)
ring_ = ok & (rr_ > 0.3 * size)                                            # skin and outer lips: fit a smooth surface
Aq = lambda x, z: np.c_[np.ones_like(x), x, z, x * x, z * z, x * z]
coef = np.linalg.lstsq(Aq(gx[ring_], gz[ring_]), Y[ring_], rcond=None)[0]
resid = Y - (Aq(gx.ravel(), gz.ravel()) @ coef).reshape(Y.shape)
deep = ok & (resid > 0.04 * size)
i0, j0 = np.argmin(np.abs(zs - cz)), np.argmin(np.abs(xs - cx))
if not deep[i0, j0]:                                                       # nearest deep cell to the centre
    ii, jj = np.nonzero(deep); k = np.argmin((ii - i0) ** 2 + (jj - j0) ** 2); i0, j0 = ii[k], jj[k]
opening = fill_holes(component(deep, i0, j0)); poly = outline(opening, xs, zs)
k1, k2 = int(np.argmax(poly[:, 0])), int(np.argmin(poly[:, 0])); a_o, b_o = poly[k1], poly[k2]
mid = (a_o + b_o) / 2; ang_o = math.atan2(a_o[1] - b_o[1], a_o[0] - b_o[0])
yc = (depth_at(H, xs, zs, a_o) + depth_at(H, xs, zs, b_o)) / 2              # depth of the corners
_, R_t = frame(org_t, A3 - B3, np.array([0, 0, 1.0]))
if R_t[:, 1] @ np.array([0, -1.0, 0]) > 0: R_t[:, 1] *= -1
s_ = np.linalg.norm(B3 - A3) / np.linalg.norm(b_o - a_o)
T2 = np.eye(4); T2[:3, 3] = [-mid[0], -yc, -mid[1]]
c_, sn = math.cos(-ang_o), math.sin(-ang_o); T3 = np.eye(4); T3[0, 0], T3[0, 2], T3[2, 0], T3[2, 2] = c_, -sn, sn, c_
S = np.diag([s_, s_, s_, 1.0])
Rt = np.eye(4); Rt[:3, :3] = R_t; Rt[:3, 3] = org_t
M4 = Rt @ S @ T3 @ T2
# close the open part: per column of the opening, the upper lip comes down and the lower lip up by half the gap,
# fading out over 2.5 gap heights; then the inside (teeth, tongue: far behind the smooth lip surface) goes
cols = np.nonzero(opening.any(0))[0]
zt = np.array([zs[np.nonzero(opening[:, j])[0].max()] for j in cols]); zb = np.array([zs[np.nonzero(opening[:, j])[0].min()] for j in cols])
xc, zc, hh = xs[cols], (zt + zb) / 2, (zt - zb) / 2; Hm = hh.max()
for v in bm.verts:
    x, y, z = v.co; zc_ = np.interp(x, xc, zc, left=zc[0], right=zc[-1]); h_ = np.interp(x, xc, hh, left=0.0, right=0.0)
    dz_rel = abs(z - zc_); w = float(np.clip(1 - (dz_rel - 2.0 * Hm) / (3.0 * Hm), 0, 1)) if dz_rel > 2.0 * Hm else 1.0
    v.co.z = z - np.sign(z - zc_) * min(h_, dz_rel) * w
fit = lambda x, z: float(Aq(np.array([x]), np.array([z]))[0] @ coef)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y - fit(v.co.x, v.co.z) > 0.035 * size], context='VERTS')
bm.verts.ensure_lookup_table()
o = place(bm, M4, 'donor_mouth')
info['mouth'] = {'size': float(size), 'opening_w_rel': float(np.linalg.norm(b_o - a_o) / size), 'opening_h_rel': float(np.ptp(poly[:, 1]) / size), 'scale': round(float(s_), 4)}
bm.free()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(info, open(os.path.splitext(OUT)[0] + '_donor.json', 'w'), indent=1)
print('DONOR', json.dumps(info))
