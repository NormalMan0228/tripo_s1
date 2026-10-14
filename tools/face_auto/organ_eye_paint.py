"""겹침생성 · eyeball paint that survives eye turns: each eyeball gets its own image, the parts the lids hide at rest
are painted as sclera and the iris is completed.

project_texture.py front-projects the reference photo onto the whole eyeball ('ref_uv'), so the parts hidden under the
lids carry lid, lash and skin paint (and the back half carries the eye again), which every eyeLook key or eye-bone turn
shows. This step gives each eyeball a Lambert azimuthal UV map about the head's forward axis (front at the tile centre,
back pole on its rim; image = two tiles, the character's right eye on the left as in the front view) and paints a new
image texel by texel (texels are rasterised from the eyeball's own triangles, so a texel knows its 3D point and the
photo point that ref_uv gave it):
- a texel the camera sees through the opening at rest (rays from the front against face + eyes) and more than band x r
  inside the opening's edge is 'trusted' and keeps its photo colour (same ref_uv interpolation: the rest look stays);
- sclera colour S = median of the bright, unsaturated trusted pixels; sclera-like = near S, as bright, no more saturated;
- iris, in photo space: rays out of the pupil (darkest spot of the opening, nearer its middle) end where trusted sclera
  starts (a ray that leaves the trusted part first, under a lid, gives nothing; early ends at highlights are dropped);
  a circle, or an axis-aligned ellipse where the border allows it, is fitted to the ends (trimmed); an eye with less
  border takes the other eye's radii and fits only its centre;
- every other texel inside that ellipse (+4 %: the limbal edge) is completed - hidden, in the edge band, or lash / lid
  paint (much darker than, or far from, the iris' ring colour taken along clean rays): the photo mirrored about the
  ellipse's horizontal axis where that is trusted and close to the ring colour, else the ring colour at that radius;
- outside it every texel, seen or hidden, takes one smooth sclera field: the trusted sclera-like texels spread over
  an image pyramid and blurred (the photo's lid shadows and lash / skin paint would turn with the eye; no seam where
  the seen part ends); S where none was seen.
The image is saved as <out>_eyes.png and packed; the eye material's image and UV map nodes switch to it ('eye_uv',
also the active UV map); 'ref_uv' stays. A rerun on its own output reads the photo again (mesh property
'eye_paint_source').
QA (<out>_eyepaint.json): tile size, mm per texel, S, iris ellipse (photo px) with border points and fit residual, the
iris centre at rest as azimuth / elevation about C and its radius as a turn angle (organ_eye_look_keys iris= reads
both), texel counts (seen, trusted, iris completed by mirror / by ring colour, lid paint on the iris, sclera) and how
many seen texels changed colour; ok = an iris was found on both eyes.
Usage: blender -b <tex_lid.blend> -P organ_eye_paint.py -- <eyes.json from organ_eye> <out.blend> [tile=1024 band=0.05]
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
EJ, OUT = a[0], os.path.abspath(a[1])
OPT = {'tile': 1024, 'band': 0.05}; OPT.update({k: float(v) for k, v in (s.split('=') for s in a[2:])})
T = int(OPT['tile']); J = json.load(open(EJ)); E = J['eyes']; K = J['rings']
face = bpy.data.objects['face']; eyes = bpy.data.objects['eyes']; me = eyes.data
def rest(o):
    d = o.data.shape_keys.key_blocks[0].data if o.data.shape_keys else o.data.vertices
    b = np.empty(len(d) * 3); d.foreach_get('co', b); return b.reshape(-1, 3)
X = rest(face); Xe = rest(eyes); ring = np.array([d.value for d in face.data.attributes['eye_ring'].data])
tex = next(n for m in me.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == 'TEX_IMAGE'); im = tex.image
if im.name == 'eye_paint': im = bpy.data.images.load(me['eye_paint_source'], check_existing=True)     # a rerun on our own output
me['eye_paint_source'] = bpy.path.abspath(im.filepath); Wp, Hp = im.size
px = np.empty(Wp * Hp * 4, np.float32); im.pixels.foreach_get(px); IM = px.reshape(Hp, Wp, 4)[:, :, :3]     # rows bottom-up, like UV v
def sample(q):                                          # bilinear, photo pixels (x right, y up)
    u = np.clip(q[:, 0] - 0.5, 0, Wp - 1.001); v = np.clip(q[:, 1] - 0.5, 0, Hp - 1.001); u0, v0 = u.astype(int), v.astype(int)
    fu, fv = (u - u0)[:, None], (v - v0)[:, None]
    return IM[v0, u0] * (1 - fu) * (1 - fv) + IM[v0, u0 + 1] * fu * (1 - fv) + IM[v0 + 1, u0] * (1 - fu) * fv + IM[v0 + 1, u0 + 1] * fu * fv
lum = lambda c: c @ np.array([0.3, 0.59, 0.11])
sat = lambda c: (c.max(-1) - c.min(-1)) / np.maximum(c.max(-1), 1e-6)
RU = np.empty(len(me.loops) * 2); me.uv_layers['ref_uv'].data.foreach_get('uv', RU); RU = RU.reshape(-1, 2) * [Wp, Hp]
LV = np.empty(len(me.loops), int); me.loops.foreach_get('vertex_index', LV)
me.calc_loop_triangles(); LT = np.array([tuple(t.loops) for t in me.loop_triangles])
Cs = {s: np.array(E[s]['C']) for s in 'LR'}
side = np.where(np.linalg.norm(Xe - Cs['L'], axis=1) < np.linalg.norm(Xe - Cs['R'], axis=1), 'L', 'R')

# ---- UVs: Lambert azimuthal about -y per eyeball (rho = 0.5 sin(theta / 2): the front gets the most texels)
def lam(P, C):
    d = (P - C) / np.linalg.norm(P - C, axis=1, keepdims=True); th = np.arccos(np.clip(-d[:, 1], -1, 1)); ph = np.arctan2(d[:, 2], d[:, 0])
    return np.c_[0.5 + 0.5 * np.sin(th / 2) * np.cos(ph), 0.5 + 0.5 * np.sin(th / 2) * np.sin(ph)], th
TILE = {'R': 0, 'L': 1}
UVt = np.zeros((len(LV), 2)); TH = np.zeros(len(LV))
for s in 'LR':
    k = side[LV] == s; UVt[k], TH[k] = lam(Xe[LV[k]], Cs[s])
back = np.zeros(len(LV), bool)                          # polygons round the back pole wrap across the tile: point them at sclera
for p in me.polygons:
    li = list(p.loop_indices)
    if TH[li].max() > math.radians(150): back[li] = True
UVt[back] = 0.02
uvl = me.uv_layers.get('eye_uv') or me.uv_layers.new(name='eye_uv')
uvl.data.foreach_set('uv', np.c_[(UVt[:, 0] + np.array([TILE[s] for s in side[LV]])) / 2, UVt[:, 1]].ravel())
me.uv_layers.active = uvl; uvl.active_render = True

FP = [list(p.vertices) for p in face.data.polygons]
bvhE = BVHTree.FromPolygons([tuple(v) for v in Xe], [list(p.vertices) for p in me.polygons])
dil = lambda m: m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
ero = lambda m: m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
def flood(m, R):
    while True:
        R2 = R | (dil(R) & m)
        if (R2 == R).all(): return R
        R = R2
qa = {'tile': T, 'eyes': {}}; EY = {}
for s, sg in (('L', 1), ('R', -1)):
    C, r = Cs[s], float(E[s]['r']); q = qa['eyes'][s] = {'mm_per_texel': round(4 * r / T * 1000, 4)}
    # rasterise this eyeball's triangles: per texel its 3D point (on the flat facet) and photo point
    Pimg = np.full((T, T, 3), np.nan); Qimg = np.zeros((T, T, 2)); cov = np.zeros((T, T), bool)
    for t in LT[(side[LV[LT[:, 0]]] == s) & ~back[LT].any(1)]:
        c = UVt[t] * T; lo = np.maximum(np.floor(c.min(0)).astype(int), 0); hi = np.minimum(np.ceil(c.max(0)).astype(int), T - 1)
        gx, gy = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1)); gx, gy = gx.ravel(), gy.ravel(); cx, cy = gx + 0.5, gy + 0.5
        (x0, y0), (x1, y1), (x2, y2) = c; den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12: continue
        b0 = ((y1 - y2) * (cx - x2) + (x2 - x1) * (cy - y2)) / den; b1 = ((y2 - y0) * (cx - x2) + (x0 - x2) * (cy - y2)) / den; b2 = 1 - b0 - b1
        k = (b0 >= -1e-6) & (b1 >= -1e-6) & (b2 >= -1e-6); Bc = np.c_[b0, b1, b2][k]
        Pimg[gy[k], gx[k]] = Bc @ Xe[LV[t]]; Qimg[gy[k], gx[k]] = Bc @ RU[t]; cov[gy[k], gx[k]] = True
    # what the camera sees at rest: a grid of rays from the front over the opening (eyeball before face)
    mg = X[(np.sign(ring) == sg) & (np.abs(ring) >= K - 1)]; h = 3.2 * r / T
    xs = np.arange(mg[:, 0].min() - 0.001, mg[:, 0].max() + 0.001, h); zs = np.arange(mg[:, 2].min() - 0.001, mg[:, 2].max() + 0.001, h)
    near = np.linalg.norm(X - C, axis=1) < 2.5 * r; bvhF = BVHTree.FromPolygons([tuple(v) for v in X], [f for f in FP if near[f].all()])
    Vg = np.zeros((len(zs), len(xs)), bool); y0 = float(X[:, 1].min()) - 0.05; up = Vector((0, 1, 0))
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            o = Vector((x, y0, z)); he = bvhE.ray_cast(o, up)
            if he[0] is not None: hf = bvhF.ray_cast(o, up); Vg[j, i] = hf[0] is None or he[3] < hf[3]
    P = np.where(cov[..., None], Pimg, C); gi = np.floor((P[..., 0] - xs[0]) / h).astype(int); gj = np.floor((P[..., 2] - zs[0]) / h).astype(int)
    inb = cov & (gi >= 0) & (gi < len(xs)) & (gj >= 0) & (gj < len(zs)) & (P[..., 1] < C[1])
    vis = np.zeros_like(cov); vis[inb] = Vg[gj[inb], gi[inb]]
    tru = vis.copy()                                     # trusted: more than band x r inside the opening's edge
    for _ in range(int(math.ceil(OPT['band'] * T / 4))): tru = ero(tru)
    col = np.zeros((T, T, 3)); col[cov] = sample(Qimg[cov])
    # ---- photo space: trusted pixels, sclera colour, pupil
    Qt = Qimg[tru]; u0, v0 = np.floor(Qt.min(0)).astype(int) - 6; u1, v1 = np.ceil(Qt.max(0)).astype(int) + 6
    PT = np.zeros((v1 - v0, u1 - u0), bool); PT[(Qt[:, 1] - v0).astype(int), (Qt[:, 0] - u0).astype(int)] = True
    PT = ero(dil(PT)); Cc = IM[v0:v1, u0:u1]; Lc, Sc = lum(Cc), sat(Cc)
    pale = PT & (Sc < 0.2); S = np.median(Cc[pale & (Lc >= np.percentile(Lc[pale], 60))], 0) if pale.sum() > 50 else np.median(Cc[PT & (Lc >= np.percentile(Lc[PT], 80))], 0)
    # sclera-like: near S and no more saturated (skin can be as bright as a shaded realistic sclera, never as grey)
    sl = lambda c, S=S: (np.abs(c - S).max(-1) < 0.2) & (lum(c) > 0.75 * lum(S)) & (sat(c) < sat(S) + 0.06)
    yy, xx = np.nonzero(PT); W_ = float(np.ptp(xx))
    dn2 = ((np.arange(PT.shape[1])[None] - xx.mean()) / (W_ / 2)) ** 2 + ((np.arange(PT.shape[0])[:, None] - yy.mean()) / (np.ptp(yy) / 2)) ** 2
    blur = sum(np.roll(np.roll(np.where(PT, Lc, 9.0), dy, 0), dx, 1) for dy in range(-2, 3) for dx in range(-2, 3)) / 25
    seed = np.unravel_index(np.argmin(np.where(ero(ero(ero(PT))), blur + 0.3 * lum(S) * dn2, 9.0)), Lc.shape)   # the pupil: dark, nearer the middle
    disk = np.hypot(np.arange(PT.shape[1])[None] - seed[1], np.arange(PT.shape[0])[:, None] - seed[0]) < 0.15 * W_
    pup = np.zeros_like(PT); pup[seed] = True; pup = flood(PT & disk & (Lc < blur[seed] + 0.08), pup)
    py_, px_ = np.nonzero(pup); c0 = np.array([px_.mean(), py_.mean()])
    # each ray out of the pupil: the iris ends where trusted sclera starts (6 px of it); a ray that leaves the trusted
    # region first (lid, lashes, the photo's own lid line) gives no point
    rr = np.arange(2.0, float(max(PT.shape)), 0.5); run = 12; U, V = [], []
    for ph in np.radians(np.arange(0, 360, 2.0)):
        x = np.rint(c0[0] + rr * math.cos(ph)).astype(int); y = np.rint(c0[1] + rr * math.sin(ph)).astype(int)
        ok_ = (x >= 0) & (x < PT.shape[1]) & (y >= 0) & (y < PT.shape[0]); n_ = int(np.argmin(ok_)) if not ok_.all() else len(rr)
        t_ = PT[y[:n_], x[:n_]]; stop = int(np.argmin(t_)) if not t_.all() else n_
        if stop <= run: continue
        win = np.convolve(sl(Cc[y[:stop], x[:stop]]).astype(int), np.ones(run, int), 'valid'); j = np.nonzero(win == run)[0]
        if len(j): U.append(c0[0] + rr[j[0]] * math.cos(ph)); V.append(c0[1] + rr[j[0]] * math.sin(ph))
    U, V = np.array(U), np.array(V); rp = np.hypot(U - c0[0], V - c0[1]) if len(U) else np.zeros(0)
    far = rp >= 0.8 * np.percentile(rp, 75) if len(U) else rp > 0; U, V = U[far], V[far]      # highlights end rays early: drop them
    q.update({'sclera_rgb': [round(float(x), 3) for x in S], 'pupil_px': int(pup.sum()), 'border_pts': len(U)})
    EY[s] = dict(C=C, Pimg=Pimg, Qimg=Qimg, cov=cov, vis=vis, tru=tru, col=col, P=P, u0=u0, v0=v0, PT=PT, Cc=Cc, S=S, sl=sl, c0=c0, U=U, V=V, W=W_)

# ---- iris ellipse per eye (photo px, crop coordinates): a circle (a human iris from the front), an ellipse when the
# border allows it; an eye whose border is weaker borrows the other eye's radii and fits only its centre
def trim(fit, U, V):                                     # fit -> (cx, cy, rx, ry); drop far points, refit
    k = np.ones(len(U), bool); e = rs = None
    for _ in range(4):
        if k.sum() < 12: return None, k, None
        e = fit(U, V, k)
        if e is None: return None, k, None
        rs = np.abs(np.hypot((U - e[0]) / e[2], (V - e[1]) / e[3]) - 1); k = rs < max(2.5 * np.median(rs[k]), 0.02)
    return e, k, rs
def circle(U, V, k):                                     # u^2 + v^2 + D u + E v + F = 0
    D_, E_, F_ = np.linalg.lstsq(np.c_[U, V, np.ones(len(U))][k], -(U ** 2 + V ** 2)[k], rcond=None)[0]; r2 = D_ * D_ / 4 + E_ * E_ / 4 - F_
    return (-D_ / 2, -E_ / 2, math.sqrt(r2), math.sqrt(r2)) if r2 > 0 else None
def ellipse(U, V, k):                                    # A u^2 + B v^2 + C u + D v = 1 about the mean (axis-aligned)
    mu, mv = U[k].mean(), V[k].mean(); A_, B_, C_, D_ = np.linalg.lstsq(np.c_[(U - mu) ** 2, (V - mv) ** 2, U - mu, V - mv][k], np.ones(k.sum()), rcond=None)[0]
    F_ = 1 + C_ ** 2 / (4 * A_) + D_ ** 2 / (4 * B_) if A_ > 0 and B_ > 0 else -1
    return (mu - C_ / (2 * A_), mv - D_ / (2 * B_), math.sqrt(F_ / A_), math.sqrt(F_ / B_)) if F_ > 0 else None
def centre_only(rx, ry):                                 # given radii: a unit circle in scaled coordinates, its centre only
    def f(U, V, k):
        e = circle(U / rx, V / ry, k); return (e[0] * rx, e[1] * ry, rx, ry) if e else None
    return f
def support(e, k, U, V, c0, W):                          # 30-degree sectors with border points; 0 if not plausible
    if e is None: return 0
    ang = np.degrees(np.arctan2((V[k] - e[1]) / e[3], (U[k] - e[0]) / e[2])); cu = (U[k] - e[0]) / e[2]
    ok = (cu < -0.5).any() and (cu > 0.5).any() and 0.7 < e[3] / e[2] < 1.5 and np.hypot(*((c0 - e[:2]) / e[2:])) < 0.5 and 0.1 * W < e[2] < 0.6 * W
    return len(np.unique((ang // 30).astype(int))) if ok and np.median(np.abs(np.hypot((U[k] - e[0]) / e[2], (V[k] - e[1]) / e[3]) - 1)) < 0.03 else 0
FIT = {}
for s, d in EY.items():
    U, V = d['U'], d['V']; best = (0, None, None, None)
    if len(U) >= 12:
        for fit, need in ((circle, 3), (ellipse, 6)):
            e, k, rs = trim(fit, U, V); sp = support(e, k, U, V, d['c0'], d['W'])
            if sp >= need and (best[1] is None or np.median(rs[k]) < 0.8 * np.median(best[3][best[2]])): best = (sp, e, k, rs)
    FIT[s] = best
for s, o in (('L', 'R'), ('R', 'L')):                    # the weaker eye takes the stronger one's iris size
    if FIT[o][1] is not None and FIT[o][0] >= FIT[s][0] + 2:
        d = EY[s]; e, k, rs = trim(centre_only(*FIT[o][1][2:]), d['U'], d['V']) if len(d['U']) >= 12 else (None, None, None)
        sp = support(e, k, d['U'], d['V'], d['c0'], d['W']) if e else 0
        if sp >= 2: FIT[s] = (sp, e, k, rs); qa['eyes'][s]['radii_from'] = o

def pushpull(c, w):                                     # hole filling over an image pyramid (known texels w = True keep c)
    if min(w.shape) <= 1 or w.all(): return c
    H_, W2 = w.shape; cs = (c * w[..., None]).reshape(H_ // 2, 2, W2 // 2, 2, 3).sum((1, 3)); ws = w.reshape(H_ // 2, 2, W2 // 2, 2).sum((1, 3))
    co = pushpull(np.where(ws[..., None] > 0, cs / np.maximum(ws, 1)[..., None], 0.0), ws > 0)
    up = np.repeat(np.repeat(co, 2, 0), 2, 1); up = sum(np.roll(np.roll(up, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
    return np.where(w[..., None], c, up)
def blur(c, k):                                         # three box passes per axis (about a Gaussian), edges clamped
    for ax in (0, 1):
        for _ in range(3):
            pad = np.concatenate([np.repeat(c.take([0], ax), k + 1, ax), c, np.repeat(c.take([-1], ax), k, ax)], ax); cs = np.cumsum(pad, ax)
            c = (cs.take(range(2 * k + 1, cs.shape[ax]), ax) - cs.take(range(0, cs.shape[ax] - 2 * k - 1), ax)) / (2 * k + 1)
    return c
OUTIMG = np.zeros((T, 2 * T, 3), np.float32)
for s, d in EY.items():
    q = qa['eyes'][s]; C, Pimg, Qimg, cov, vis, tru, col, P, PT, S, sl = (d[k] for k in ('C', 'Pimg', 'Qimg', 'cov', 'vis', 'tru', 'col', 'P', 'PT', 'S', 'sl'))
    u0, v0 = d['u0'], d['v0']; sp, ell, keep, res = FIT[s]
    if os.environ.get('EYEPAINT_DEBUG'):
        np.savez(os.environ['EYEPAINT_DEBUG'] + s, Cc=d['Cc'], PT=PT, U=d['U'], V=d['V'], keep=keep if keep is not None else np.zeros(len(d['U']), bool),
                 ell=np.array(ell if ell else [0, 0, 0, 0]), S=S, c0=d['c0'])
    Qc = Qimg - [u0, v0]; out = np.where(cov[..., None], col, S); inI = np.zeros_like(cov); n_mir = n_ring = n_lid = 0
    if ell:
        cx_, cy_, rx_, ry_ = ell; rho = np.hypot((Qc[..., 0] - cx_) / rx_, (Qc[..., 1] - cy_) / ry_); inI = cov & (P[..., 1] < C[1]) & (rho < 1.04)   # with the limbal edge
        # ring colours from clean radial lines only: directions where a ray reached sclera (no lid on the way)
        tI = tru & inI; bins = np.minimum((rho * 32).astype(int), 31); prof = np.full((32, 3), np.nan)
        phi = np.degrees(np.arctan2((Qc[..., 1] - cy_) / ry_, (Qc[..., 0] - cx_) / rx_)).astype(int) % 360
        pk = np.degrees(np.arctan2((d['V'][keep] - cy_) / ry_, (d['U'][keep] - cx_) / rx_)).astype(int) % 360
        cb = np.zeros(360, bool); cb[(pk[:, None] + np.arange(-8, 9)[None]).ravel() % 360] = True; clean = tI & cb[phi]
        for b in range(32):
            m = (clean if (clean & (bins == b)).sum() >= 5 else tI) & (bins == b)
            if m.sum() >= 5: prof[b] = np.median(col[m], 0)
        ok = ~np.isnan(prof[:, 0]); prof = np.array([np.interp(np.arange(32), np.nonzero(ok)[0], prof[ok, c]) for c in range(3)]).T if ok.any() else np.tile(S, (32, 1))
        pr = prof[bins]                                  # a trusted iris texel far off its ring colour (and not a highlight) is lid paint
        bad = tI & (rho > 0.35) & ((lum(col) < lum(pr) - 0.15) | (np.abs(col - pr).max(-1) > 0.3) | (sat(col) > sat(pr) + 0.25)) & ~(lum(col) > lum(pr) + 0.2)   # lashes, lid skin, waterline
        f = inI & (~tru | bad); n_lid = int(bad.sum())
        Qm = Qc[f].copy(); Qm[:, 1] = 2 * cy_ - Qm[:, 1]; ring_c = pr[f]
        mi, mj = np.rint(Qm[:, 0]).astype(int), np.rint(Qm[:, 1]).astype(int); in_ = (mi >= 0) & (mi < PT.shape[1]) & (mj >= 0) & (mj < PT.shape[0])
        okm = in_.copy(); okm[in_] = PT[mj[in_], mi[in_]]
        cm = sample(Qm + [u0, v0]); okm &= (lum(cm) < lum(ring_c) + 0.2) & (np.abs(cm - ring_c).max(-1) < 0.22)   # no highlight / lid paint twice
        out[f] = np.where(okm[:, None], cm, ring_c); n_mir, n_ring = int(okm.sum()), int((~okm).sum())
        ctr = np.argmin(np.where(inI, rho, 9).ravel()); dd = Pimg.reshape(-1, 3)[ctr] - C
        q.update({'iris_ellipse_px': [round(x + o, 1) for x, o in zip(ell, (u0, v0, 0, 0))], 'iris_support_sectors': sp, 'iris_fit_resid': round(float(np.median(res[keep])), 4),
                  'iris_rest_azel': [round(math.degrees(math.atan2(dd[0], -dd[1])), 2), round(math.degrees(math.asin(dd[2] / np.linalg.norm(dd))), 2)]})
        rim = inI | (cov & (P[..., 1] < C[1]) & (rho < 1.03)); rim &= rho > 0.97; gc = dd / np.linalg.norm(dd)        # iris radius as a turn angle
        if rim.any(): vr = Pimg[rim] - C; q['iris_radius_deg'] = round(float(np.degrees(np.median(np.arccos(np.clip(vr @ gc / np.linalg.norm(vr, axis=1), -1, 1))))), 2)
    # outside the iris: one smooth sclera field for the seen and the hidden part alike (the photo's lid shadows and the
    # edge between seen and filled texels would turn with the eye): trusted sclera texels spread over an image pyramid,
    # then blurred
    keepS = cov & ~inI & tru & sl(col)
    field = blur(pushpull(np.where(keepS[..., None], col, 0.0), keepS), T // 48) if keepS.any() else np.broadcast_to(S, out.shape)
    out[~inI] = field[~inI]
    q.update({'texels': int(cov.sum()), 'seen': int(vis.sum()), 'trusted': int(tru.sum()), 'iris_mirror': n_mir, 'iris_ring': n_ring, 'iris_lidpaint': n_lid,
              'sclera_texels': int((cov & ~inI).sum()), 'seen_changed': int((vis & (np.abs(out - col).max(-1) > 0.02)).sum())})
    OUTIMG[:, TILE[s] * T:(TILE[s] + 1) * T] = out
OUTIMG[np.isnan(OUTIMG)] = 0
img = bpy.data.images.get('eye_paint') or bpy.data.images.new('eye_paint', 2 * T, T, alpha=False)
if tuple(img.size) != (2 * T, T): img.scale(2 * T, T)
img.pixels.foreach_set(np.concatenate([OUTIMG, np.ones((T, 2 * T, 1), np.float32)], 2).ravel())
png = os.path.splitext(OUT)[0] + '_eyes.png'; img.filepath_raw = png; img.file_format = 'PNG'; img.save(); img.pack()
for m in me.materials:
    if not (m and m.use_nodes): continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE': n.image = img
        if n.type == 'UVMAP': n.uv_map = 'eye_uv'
qa['ok'] = all('iris_ellipse_px' in e for e in qa['eyes'].values())
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(qa, open(os.path.splitext(OUT)[0] + '_eyepaint.json', 'w'), indent=1)
print('EYEPAINT', json.dumps(qa))
