"""Bake the reference views into image textures per part (texture step 2 of 3), replacing the per-vertex
'ref_color' of project_texture.py, which is blurry on 8-22k vertex heads.

skin   every texel of the skin UV (uv_parts.py) is a point of the REST surface (shape key 0, so expressions
       carry the paint along). It is projected into each reference view with the project_texture mapping
       (ref_views.py) and the views are mixed by how squarely the texel faces each camera. A view is skipped
       where the texel is hidden (z-buffer of face + eyes + brow pieces per view) or lands on the image
       background; the front view is skipped where it lands inside the painted eye openings or between the
       painted lips (MediaPipe contours), so no sclera / iris / mouth-line paint ends up on lids and lips; the
       lid rings take the front view only. The side and back views are gain-matched to the front on their
       overlap. Texels no view saw are filled from the nearest seen texels in 3D (seam-free; the skull fills
       from the skull only, lids from lid skin), then softened. Then the parts the reference cannot show:
         lid tuck rings      lid skin, darker (upper) / pinkish (lower, waterline)
         lid margin rows     toward the lash colour sampled at the painted upper lash line
         lid skin rings      eye-paint left-overs (whiter or much darker than the lid skin) re-filled
         inner lip roll      lip colour (sampled between the painted outer and inner lip contours), darker inward
         mouth cavity        dark red, darker with depth
       Island borders are padded (dilation) so mip-maps never bleed the background.
brows  'p2_brows' (when the asset has it): front-image crop under the brow box of uv_parts; lighter pixels are
       pulled to the brow colour (the brow piece is brow wherever it is).
Usage: python bake_ref_texture.py <uv_dir> <ref_dir> <landmarks.json> <out_dir> [--size 4096] [--margin-fit]
Writes <out_dir>/skin.png, brows.png (if any), bake_qa.json, dbg_views.jpg (view map: R front, G sides,
B back, grey filled), mp_front.json (MediaPipe cache).
"""
import sys, os, json, time
import numpy as np
import scipy.sparse as sps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_views as rv

t0 = time.time()
a = sys.argv[1:]
UVD, REF, LMJ, OUT = a[0], a[1], a[2], os.path.abspath(a[3])
S = int(a[a.index('--size') + 1]) if '--size' in a else 4096
os.makedirs(OUT, exist_ok=True)
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
sk = np.load(os.path.join(UVD, 'mesh_skin.npz'))
V, Nv, T, TUV, TM = sk['V'], sk['N'], sk['T'], sk['TUV'], sk['TM']
mat_names = list(sk['mat_names'])
CAV = next((i for i, m in enumerate(mat_names) if m in ('mouth_inner', 'ref_mouth')), -1)
views = rv.Views(REF, LT, V, OUT)
# --margin-fit: the photo's eye contour (MediaPipe, reliable on realistic / semi eyes) is pinned onto the mesh's
# lid margin ring, so lash lines and lid skin land on the lids, not on the cheek (bases from eye_fit_ref.py already
# match the photo contour and need no refit; cartoon eyes: MediaPipe's contour is not the painted one, skip)
if '--margin-fit' in a and 'eye_ring' in sk:
    views.fit_eye_margins(rv.eye_margins(V, sk['eye_ring']))
qa = {'views': views.qa, 'size': S}
lum = lambda c: c @ np.array([0.3, 0.59, 0.11], np.float32)
def sat(c): mx, mn = c.max(-1), c.min(-1); return (mx - mn) / np.maximum(mx, 1e-6)

# ---------------------------------------------------------------- texels
idx, tri, bary = rv.raster_uv(TUV, S)
TV = T[tri]
P = np.einsum('nk,nkd->nd', bary, V[TV]).astype(np.float64)
Nt = np.einsum('nk,nkd->nd', bary, Nv[TV]); Nt /= np.maximum(np.linalg.norm(Nt, axis=1, keepdims=True), 1e-9)
near = TV[np.arange(len(TV)), np.argmax(bary, 1)]                       # nearest vertex: ring ids are integers
er = sk['eye_ring'][near] if 'eye_ring' in sk else np.zeros(len(P), int)
# continuous ring coordinate (|ring| interpolated over the triangle): lid colour rules ramp over it, no stepped edges
kf = np.einsum('nk,nk->n', bary, np.abs(sk['eye_ring'][TV]).astype(np.float32)) if 'eye_ring' in sk else np.zeros(len(P), np.float32)
eu = sk['eye_u'][near] if 'eye_u' in sk else np.zeros(len(P))
mr = sk['mouth_ring'][near] if 'mouth_ring' in sk else np.zeros(len(P), int)
mrf = np.einsum('nk,nk->n', bary, sk['mouth_ring'][TV].astype(np.float32)) if 'mouth_ring' in sk else np.zeros(len(P))
cav = TM[tri] == CAV
NT = len(P); qa['texels'] = int(NT)
print('texels', NT, 'raster %.1fs' % (time.time() - t0)); sys.stdout.flush()

# ---------------------------------------------------------------- occluders: skin + eyes + brow pieces
occ_V = [V]; occ_T = [T]; off = len(V)
for nm in ('eyes', 'brows'):
    f = os.path.join(UVD, f'mesh_{nm}.npz')
    if os.path.exists(f):
        d = np.load(f); occ_V.append(d['V']); occ_T.append(d['T'] + off); off += len(d['V'])
OV = np.concatenate(occ_V); OT = np.concatenate(occ_T)
K = int(np.abs(sk['eye_ring']).max()) - 2 if 'eye_ring' in sk else 0
lid = (np.abs(er) >= 1)
mouth_zone = mr >= 1
# lids and lips take the front view only; the side views fade in over ~8 vertex rings around them (a hard switch
# leaves a stepped edge where the side paint differs a little)
eye_v = (np.abs(sk['eye_ring']) >= 1) if 'eye_ring' in sk else np.zeros(len(V), bool)
mouth_v = (sk['mouth_ring'] >= 1) if 'mouth_ring' in sk else np.zeros(len(V), bool)
ei = np.r_[T[:, 0], T[:, 1], T[:, 2], T[:, 1], T[:, 2], T[:, 0]]; ej = np.r_[T[:, 1], T[:, 2], T[:, 0], T[:, 0], T[:, 1], T[:, 2]]
Adj = sps.csr_matrix((np.ones(len(ei)), (ei, ej)), shape=(len(V), len(V))); Adj.data[:] = 1
Adj = sps.diags(1 / np.maximum(np.asarray(Adj.sum(1)).ravel(), 1)) @ Adj
def diffuse(z, n=8):
    f = z.astype(float)
    for _ in range(n): f = np.maximum(z, Adj @ f)
    return np.clip(np.einsum('nk,nk->n', bary, f[TV]), 0, 1)
fz_eye = diffuse(eye_v); fz_mouth = diffuse(mouth_v)
side_fade = 1 - np.maximum(fz_eye, fz_mouth)
side_fade[lid | mouth_zone] = 0

# MediaPipe polygons on the front image
poly_eye = {s: views.poly(rv.MP_EYE[s]) for s in ('L', 'R')}
poly_lin = views.poly(rv.MP_LIP_IN); poly_lout = views.poly(rv.MP_LIP_OUT)
def grow(poly, px):
    c = poly.mean(0); d = poly - c; n = np.linalg.norm(d, axis=1, keepdims=True)
    return c + d * (1 + px / np.maximum(n, 1e-6))
eye_w_px = np.mean([np.ptp(poly_eye[s][:, 0]) for s in poly_eye])

cols, ws = {}, {}
OFF = [(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
for name, uvf in views.uvf.items():
    tv = time.time()
    d = rv.DIRS[name]
    c = Nt @ d
    w = np.clip((c - 0.12) / 0.33, 0, 1) ** 2 * np.clip(c, 0, 1) ** 2
    if name == 'front': w = w * 1.5
    # visibility: z-buffer in the view's own pixels; soft = share of the 3x3 pixels around the texel that it is
    # not behind (anti-aliased occlusion edges, no stair steps where a nostril or lid hides the skin)
    oc = uvf(OV); od = views.depth(name, OV)
    Z = rv.raster_depth(oc[OT], od[OT], views.H, views.W, step=1)
    uv = np.empty((NT, 2))
    for s0 in range(0, NT, 1_000_000): uv[s0:s0 + 1_000_000] = uvf(P[s0:s0 + 1_000_000])
    dep = views.depth(name, P)
    vis = np.zeros(NT, np.float32)
    for dx, dy in OFF:
        zu = np.clip((uv[:, 0] + dx).astype(int), 0, Z.shape[1] - 1); zv = np.clip((uv[:, 1] + dy).astype(int), 0, Z.shape[0] - 1)
        vis += dep <= Z[zv, zu] + 0.0012
    vis /= len(OFF)
    w = w * vis * np.clip(1 - 1.5 * views.bg_soft(name, uv), 0, 1)
    if name == 'front':
        bad = np.zeros(NT, bool)
        for s in poly_eye: bad |= rv.point_in_poly(uv, grow(poly_eye[s], 0.03 * eye_w_px))
        bad |= rv.point_in_poly(uv, grow(poly_lin, 0.012 * eye_w_px))
        w = w * ~bad; qa['front_eye_mouth_masked'] = int((bad & (c > 0)).sum()); front_bad = bad
        near_eye = np.zeros(NT, bool)                                   # around the painted eye: liner wings, lashes
        for s in poly_eye:                                              # (wide sideways, short upward: not the brows)
            pe_ = poly_eye[s]; c__ = pe_.mean(0); near_eye |= rv.point_in_poly(uv, c__ + (pe_ - c__) * [1.6, 1.25])
        near_eye &= c > 0
        # inside the painted face oval the silhouette-fitted side maps are too loose (nose wings, lid corners):
        # side views ramp in from 70 % to 100 % of the oval
        oval = views.poly(rv.MP_OVAL); oc_ = oval.mean(0); core_mult = np.zeros(NT, np.float32)
        for f_ in (0.70, 0.775, 0.85, 0.925, 1.0):
            core_mult += ~rv.point_in_poly(uv, oc_ + (oval - oc_) * f_)
        core_mult /= 5.0
    else:
        # inside the face oval only where the FRONT camera sees the texel (the front map ignores depth: the back and
        # the sides of the skull project into the oval too and must keep their own photos)
        cfr = np.clip((Nt @ rv.DIRS['front'] - 0.1) / 0.25, 0, 1)
        core_eff = 1 - (1 - core_mult) * cfr
        w = w * side_fade ** 2 * ~front_bad * core_eff ** 2            # where the front sees eye paint, so do the sides
        # the front map is landmark-aligned, the side / back maps only silhouette-fitted: where the front sees the
        # texel well, it leads
        cf_ = Nt @ rv.DIRS['front']; t_ = np.clip((cf_ - 0.35) / 0.35, 0, 1)
        w = w * (1 - 0.85 * t_ * t_ * (3 - 2 * t_))
        if name in ('left', 'right'):                                   # the side fit (head top + nose) drifts on
            fh_ = (LT[2][2] + LT[5][2]) / 2 - LT[24][2]                 # the bust: fade out below the chin
            w = w * np.clip((P[:, 2] - (LT[24][2] - 0.45 * fh_)) / (0.35 * fh_), 0, 1)
    w = w * ~cav
    cols[name] = rv.sample(views.imgs[name], uv).astype(np.float32); ws[name] = w.astype(np.float32)
    print(name, 'visible %.2f' % (vis[c > 0.12] > 0.5).mean(), '%.1fs' % (time.time() - tv)); sys.stdout.flush()
    del uv, oc, Z

# gain-match side / back views to the front where both see the texel
gains = {}
for name, refs in (('left', ('front',)), ('right', ('front',)), ('back', ('left', 'right'))):   # back: to the matched sides
    if name not in cols: continue
    ov = np.zeros(NT, bool); rc = np.zeros((NT, 3), np.float32); rw = np.zeros(NT, np.float32)
    for r_ in refs:
        if r_ in cols: rc += ws[r_][:, None] * cols[r_]; rw += ws[r_]
    ov = (rw > 0.05) & (ws[name] > 0.05)
    if ov.sum() < 300: gains[name] = [1, 1, 1]; continue
    g = np.median(rc[ov] / rw[ov, None], 0) / np.maximum(np.median(cols[name][ov], 0), 1e-3)
    g = np.clip(g, 0.75, 1.33); cols[name] *= g; gains[name] = [round(float(x), 3) for x in g]
qa['view_gains'] = gains
wsum = sum(ws.values()); col = sum(ws[k][:, None] * cols[k] for k in cols) / np.maximum(wsum, 1e-9)[:, None]
# confidence: weak (grazing, half-hidden) texels lean on the fill below, so view edges fade instead of stepping
conf = np.clip(wsum / np.where(kf >= 1, 0.35, 0.12), 0, 1); conf = conf * conf * (3 - 2 * conf)
# (lid rings: a texel the photos only graze - rim, tuck, fold - leans on the neighbouring lid skin instead)
dom = np.stack([ws.get('front', np.zeros(NT)), ws.get('left', np.zeros(NT)) + ws.get('right', np.zeros(NT)), ws.get('back', np.zeros(NT))], 1)
del cols, ws

# ---------------------------------------------------------------- eye-paint left-overs on and around the lids
from scipy.spatial import cKDTree
def knn_fill(targets, sources, k=12):
    """colour of targets from the nearest confident texels in 3D (seam-free)"""
    if not len(targets) or not len(sources): return np.zeros((len(targets), 3), np.float32)
    if len(sources) > 400_000: sources = np.random.default_rng(1).choice(sources, 400_000, replace=False)
    tr = cKDTree(P[sources]); d, j = tr.query(P[targets], k=min(k, len(sources)))
    if d.ndim == 1: d, j = d[:, None], j[:, None]
    w = 1 / np.maximum(d, 1e-5) ** 2
    return (w[:, :, None] * col[sources][j]).sum(1) / w.sum(1)[:, None]
side = np.sign(er)
good = conf > 0.98
lid_skin = {}
for sg in (1, -1):
    ref = good & (side == sg) & np.isin(np.abs(er), (2, 3))
    lid_skin[sg] = np.median(col[ref], 0) if ref.sum() > 20 else np.median(col[good], 0)
qa['lid_skin'] = {('L' if sg > 0 else 'R'): [round(float(x), 3) for x in v] for sg, v in lid_skin.items()}
# painted eye colours (sclera = brightest third inside the openings, iris = inside the MediaPipe iris circles)
fr_ = views.imgs['front']; scl_px, iris_px = [], []
for s in ('L', 'R'):
    pe = poly_eye[s]; pc_ = pe.mean(0); pin_ = pc_ + (pe - pc_) * 0.9; ir_ = views.mp[rv.MP_IRIS[s]]
    ic_, iR = ir_[0], np.mean(np.linalg.norm(ir_[1:] - ir_[0], axis=1))
    xs, ys = np.meshgrid(np.arange(pe[:, 0].min(), pe[:, 0].max()) + 0.5, np.arange(pe[:, 1].min(), pe[:, 1].max()) + 0.5)
    q = np.c_[xs.ravel(), ys.ravel()]; q = q[rv.point_in_poly(q, pin_)]; dq = np.linalg.norm(q - ic_, axis=1)
    a_ = rv.sample(fr_, q[dq > 1.15 * iR]); scl_px.append(a_[lum(a_) >= np.percentile(lum(a_), 66)] if len(a_) > 10 else a_)
    iris_px.append(rv.sample(fr_, q[dq < 0.8 * iR]))
scl_c = np.median(np.concatenate(scl_px), 0); iris_c = np.median(np.concatenate(iris_px), 0)
qa['painted_sclera'] = [round(float(x), 3) for x in scl_c]; qa['painted_iris'] = [round(float(x), 3) for x in iris_c]
contam = np.zeros(NT, bool)
s_pos = np.sign(np.median(V[sk['eye_ring'] > 0, 0])) if 'eye_ring' in sk and (sk['eye_ring'] > 0).any() else 1.0
eye_side = np.where(side != 0, side, np.sign(P[:, 0]) * s_pos)        # texels around the rings: by side of the face
for sg in (1, -1):
    S_ = lid_skin[sg]; ls = float(lum(S_)); ss = float(sat(S_[None])[0])
    # colour test on the lid rings only (big painted cartoon eyes overrun the MediaPipe contour); skin around the
    # eye is judged by where its photo pixel lies (front_bad above), never by colour: pale under-eye skin is not
    # sclera
    ring = (np.abs(er) >= 4) & (np.abs(er) <= K)                     # rings 1-3 are the skin around the lids
    m = (conf > 0.05) & (eye_side == sg) & ring
    cm = col[m]; lc = lum(cm)
    # eye white: close to the painted sclera and greyer than skin; iris: close to the painted iris and dark
    s_lim = min(0.6 * ss, max(0.12, 2 * float(sat(scl_c[None])[0])))
    whiter = (np.linalg.norm(cm - scl_c, axis=1) < 0.11) & (sat(cm) < s_lim)
    darker = (np.linalg.norm(cm - iris_c, axis=1) < 0.14) & (lc < ls * 0.6) & (np.abs(er[m]) >= 1) & (np.abs(er[m]) < K - 1)
    contam[np.nonzero(m)[0][whiter | darker]] = True
    # dark paint (eyeliner wing, lash tips, iris rim) around the eye but off the lash rows -> neighbouring skin
    m2 = (conf > 0.05) & (eye_side == sg) & near_eye & (kf < K - 1.5) & (lum(col) < 0.45 * ls)
    contam |= m2; qa.setdefault('dark_paint_refilled', {})['L' if sg > 0 else 'R'] = int(m2.sum())
qa['eye_paint_refilled_texels'] = int(contam.sum())
conf[contam] = 0; good &= ~contam

# ---------------------------------------------------------------- fill (3D nearest confident texels), then mix
z_split = LT[24][2] + 0.45 * ((LT[2][2] + LT[5][2]) / 2 - LT[24][2])     # skull above ~ the nose
skull = P[:, 2] > z_split
need = (conf < 0.999) & ~cav; fillc = np.zeros((NT, 3), np.float32); done = np.zeros(NT, bool)
# dark paint (brows, lash lines, nostrils, lip line) never spreads into filled skin: sources are skin-bright
fl_ = lum(col); face_ref = good & (Nt @ rv.DIRS['front'] > 0.5) & (P[:, 2] > LT[24][2]) & (P[:, 2] < (LT[2][2] + LT[5][2]) / 2)
ref_l = float(np.median(fl_[face_ref])) if face_ref.sum() > 100 else float(np.median(fl_[good]))
good_fill = good & (fl_ > 0.72 * ref_l); qa['fill_dark_sources_dropped'] = int((good & ~good_fill).sum())
for sg in (1, -1):                                                       # lids from lid skin (not the lash rows)
    ls = float(lum(lid_skin[sg])); lg = lum(col)
    skin_like = good & (lg > 0.6 * ls) & (lg < 1.3 * ls)
    t_ = np.nonzero(need & (side == sg) & (np.abs(er) >= 1))[0]
    s_ = np.nonzero(skin_like & (side == sg) & (np.abs(er) >= 1) & (np.abs(er) <= K - 2))[0]
    fillc[t_] = knn_fill(t_, s_); done[t_] = True
    # skin around the eye (corners, below the lashes) from the surrounding skin (outside the rings, face-bright)
    t_ = np.nonzero(need & ~done & (eye_side == sg) & (er == 0) & (fz_eye > 0.02))[0]
    s_ = np.nonzero(good & (eye_side == sg) & (er == 0) & (fl_ > 0.75 * ref_l) & (fl_ < 1.3 * ref_l))[0]
    fillc[t_] = knn_fill(t_, s_); done[t_] = True
t_ = np.nonzero(need & ~done & skull)[0]; fillc[t_] = knn_fill(t_, np.nonzero(good_fill & skull)[0]); done[t_] = True
t_ = np.nonzero(need & ~done)[0]; fillc[t_] = knn_fill(t_, np.nonzero(good)[0])
nz = np.nonzero(need)[0]
col[nz] = conf[nz, None] * col[nz] + (1 - conf[nz, None]) * fillc[nz]
filled = need & (conf < 0.5)
qa['texels_seen'] = round(float((conf > 0.5).mean()), 3); qa['texels_filled'] = round(float(filled.mean()), 3)

# ---------------------------------------------------------------- what the reference cannot show
# image samples for lips and lashes
fr = views.imgs['front']
def img_pixels_in(poly, excl=None):
    x0, y0 = np.floor(poly.min(0)).astype(int); x1, y1 = np.ceil(poly.max(0)).astype(int)
    xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5); pts = np.c_[xs.ravel(), ys.ravel()]
    m = rv.point_in_poly(pts, poly)
    if excl is not None: m &= ~rv.point_in_poly(pts, excl)
    return rv.sample(fr, pts[m])
lip_px = img_pixels_in(poly_lout, grow(poly_lin, 0.02 * eye_w_px))
lipc = np.median(lip_px, 0) if len(lip_px) > 20 else np.array([0.62, 0.36, 0.36])
lash = []
for s in ('L', 'R'):                                                     # darkest paint along the upper lid contour
    pe = poly_eye[s]; up = pe[pe[:, 1] < np.median(pe[:, 1])]
    pts = np.concatenate([up + [dx, dy] for dx in np.linspace(-3, 3, 5) for dy in np.linspace(-0.08, 0.02, 6) * eye_w_px])
    smp = rv.sample(fr, pts); lash.append(smp[np.argsort(lum(smp))[:max(5, len(smp) // 8)]].mean(0))
lashc = np.mean(lash, 0)
qa['lip_colour'] = [round(float(x), 3) for x in lipc]; qa['lash_colour'] = [round(float(x), 3) for x in lashc]
# caruncle (pink inner-corner piece, if the asset has one): the photo's pink at the inner eye corners
car = []
for s, ci in (('R', 133), ('L', 362)):
    pe = poly_eye[s]; c_ = views.mp[ci]; rr_ = 0.14 * eye_w_px
    xs, ys = np.meshgrid(np.arange(c_[0] - rr_, c_[0] + rr_) + 0.5, np.arange(c_[1] - rr_, c_[1] + rr_) + 0.5)
    q = np.c_[xs.ravel(), ys.ravel()]; q = q[rv.point_in_poly(q, grow(pe, 0.03 * eye_w_px)) & (np.linalg.norm(q - c_, axis=1) < rr_)]
    if len(q):
        smp = rv.sample(fr, q); smp = smp[(sat(smp) > 0.2) & (lum(smp) > 0.3)]
        if len(smp) > 10: car.append(np.median(smp, 0))
carc = np.mean(car, 0) if car else np.array([0.78, 0.47, 0.47])
carc = 0.7 * carc + 0.3 * np.array([0.80, 0.45, 0.47])                    # keep it pink even on pale paintings
qa['caruncle_colour'] = [round(float(x), 3) for x in carc]
# lids, per lid column (64 bins of eye_u, as organ_lid_colors): the skin of rings 2-3 is the column's lid skin.
#   rings 4..K-2 (lid skin, partly tucked under the fold at rest and unrolled in a blink): paint that is far from
#   the column skin (sclera, iris, lash strokes) blends to it; rings K-1..K (margin): dark paint (lash line) kept,
#   anything else -> column skin a little darker, then toward the lash colour; tuck rings darker (below)
upper = eu < 0.5; NB = 64; cb = np.clip((eu * NB).astype(int), 0, NB - 1)
qa['lid_columns'] = {}
for sg in (1, -1):
    ka = np.abs(er); Sc = np.full((NB, 3), np.nan)
    cand = good & (side == sg) & np.isin(ka, (1, 2, 3))                 # skin-like samples only (big painted eyes
    if cand.sum() > 20:                                                 # reach over rings 2-3 on cartoon heads)
        med_ = np.median(col[cand], 0)
        for _ in range(2):
            cand &= np.linalg.norm(col - med_, axis=1) < 0.15
            if cand.sum() > 20: med_ = np.median(col[cand], 0)
    for c_ in range(NB):
        r_ = cand & (cb == c_)
        if r_.sum() > 5: Sc[c_] = np.median(col[r_], 0)
    ok_ = ~np.isnan(Sc[:, 0])
    if ok_.sum() < 4: Sc[:] = lid_skin[sg]
    else:
        g_ = np.nonzero(ok_)[0]
        for j in range(3): Sc[~ok_, j] = np.interp(np.nonzero(~ok_)[0], np.r_[g_ - NB, g_, g_ + NB], np.tile(Sc[g_, j], 3))
    for _ in range(8): Sc = (np.roll(Sc, 1, 0) + 2 * Sc + np.roll(Sc, -1, 0)) / 4
    fu_ = eu * NB - 0.5; c0_ = np.floor(fu_).astype(int); tw = (fu_ - c0_)[:, None]   # smooth along the lid
    S_t = Sc[c0_ % NB] * (1 - tw) + Sc[(c0_ + 1) % NB] * tw
    sel = (side == sg) & (kf >= 3); kk = kf[sel]; S_s = S_t[sel]; c0 = col[sel]
    d_ = np.linalg.norm(c0 - S_s, axis=1); t = np.clip((d_ - 0.08) / 0.08, 0, 1)[:, None]
    c1 = c0 * (1 - t) + S_s * t                                           # lid skin: off-colour paint -> column skin
    c1 = c0 + (c1 - c0) * np.clip(kk - 3, 0, 1)[:, None]
    lS = lum(S_s); td = np.clip((0.75 * lS - lum(c1)) / (0.3 * lS), 0, 1)[:, None]   # margin: dark paint = lash line
    cm_ = c1 * td + S_s * 0.92 * (1 - td)
    wu = np.clip(0.5 + 1.5 * np.sin(2 * np.pi * eu[sel]), 0, 1)                    # 1 on the upper lid, ramps at corners
    tl = ((0.2 + 0.35 * wu) * np.clip(kk - (K - 1), 0.6, 1.0))[:, None]
    cm_ = cm_ * (1 - tl) + lashc * tl
    wm = np.clip(kk - (K - 2), 0, 1)[:, None]
    c2 = c1 * (1 - wm) + cm_ * wm
    tuck = S_s * (wu[:, None] * 0.5 + (1 - wu[:, None]) * np.array([0.82, 0.62, 0.62]))
    wt = np.clip(kk - K, 0, 1)[:, None]                                    # tuck rings: darker / pinkish waterline
    col[sel] = c2 * (1 - wt) + tuck * wt
    qa['lid_columns']['L' if sg > 0 else 'R'] = {'columns_with_skin': int(ok_.sum()), 'lash_kept_texels': int((td[:, 0] > 0.5).sum())}
# lips: inner roll = lip colour, darker inward; the contact row keeps its paint
if CAV >= 0 and mouth_zone.any():
    cav_ring = int(mr[cav].min()) if cav.any() else int(mr.max()) + 1
    rings = range(1, cav_ring)
    zext = {r: np.ptp(P[mr == r, 2]) if (mr == r).sum() > 3 else 1.0 for r in rings}
    contact = min(zext, key=zext.get)
    m = (mr > contact) & ~cav
    tt = np.clip((mrf[m] - contact) / max(cav_ring - contact, 1), 0, 1)[:, None]
    col[m] = lipc * (0.92 - 0.3 * tt)
    m = cav
    tt = np.clip((mrf[m] - cav_ring) / max(mr.max() - cav_ring, 1), 0, 1)[:, None]
    col[m] = np.array([0.58, 0.22, 0.23]) * (1 - tt) + np.array([0.26, 0.07, 0.08]) * tt
    qa['mouth'] = {'contact_ring': int(contact), 'cavity_ring': cav_ring}

# ---------------------------------------------------------------- to the image, soften filled areas, pad
import cv2
img = np.zeros((S * S, 3), np.float32); img[idx] = col; img = img.reshape(S, S, 3)
cover = np.zeros(S * S, bool); cover[idx] = True; cover = cover.reshape(S, S)
cf = np.ones(S * S, np.float32); cf[idx] = np.where(cav, 1.0, conf); cf = cf.reshape(S, S)
sig = S / 1024.0
num = cv2.GaussianBlur(img * cover[:, :, None], (0, 0), 2.5 * sig); den = cv2.GaussianBlur(cover.astype(np.float32), (0, 0), 2.5 * sig)
soft = num / np.maximum(den, 1e-6)[:, :, None]
img = img * cf[:, :, None] + soft * (1 - cf[:, :, None])                # filled paint softened, seen paint kept
img, padded = rv.dilate_fill(img, cover, int(6 * sig))
img[~padded] = np.median(col[good], 0)
rv.save_rgb(os.path.join(OUT, 'skin.png'), img)
dbg = np.zeros((S * S, 3), np.float32); dd = dom / np.maximum(dom.sum(1, keepdims=True), 1e-9)
dbg[idx] = np.where(filled[:, None], 0.35, dd * 0.9); dbg[idx[cav]] = (0.5, 0.0, 0.3)
rv.save_rgb(os.path.join(OUT, 'dbg_views.png'), cv2.resize(dbg.reshape(S, S, 3), (1024, 1024), interpolation=cv2.INTER_AREA))

# ---------------------------------------------------------------- brows (P2 pieces)
fb = os.path.join(UVD, 'mesh_brows.npz')
if os.path.exists(fb):
    bx = np.load(fb)['brows_box']; BW, BH = 1024, 512
    xs, ys = np.meshgrid((np.arange(BW) + 0.5) / BW, 1 - (np.arange(BH) + 0.5) / BH)
    XZ = np.c_[bx[0] + xs.ravel() * (bx[1] - bx[0]), bx[2] + ys.ravel() * (bx[3] - bx[2])]
    bc = rv.sample(fr, views.front_uv(XZ)).reshape(BH, BW, 3)
    L_ = lum(bc); skin_l = np.percentile(L_, 85); dark = L_ < 0.8 * skin_l
    brow = np.median(bc[dark], 0) if dark.sum() > 50 else np.percentile(bc.reshape(-1, 3), 10, axis=0)
    t = np.clip((L_ - lum(brow)) / max(skin_l - float(lum(brow)), 1e-3), 0, 1)[:, :, None]
    out = bc * (1 - t) + brow * t                                         # light (skin) pixels -> brow colour
    out[-int(0.04 * BH) - 4:, :int(0.02 * BW) + 4] = brow                 # corner patch for edge / back faces (uv_parts)
    rv.save_rgb(os.path.join(OUT, 'brows.png'), out)
    qa['brows'] = {'colour': [round(float(x), 3) for x in brow], 'dark_fraction': round(float(dark.mean()), 3)}
qa['seconds'] = round(time.time() - t0, 1)
json.dump(qa, open(os.path.join(OUT, 'bake_qa.json'), 'w'), indent=1)
print('BAKED', json.dumps(qa))
