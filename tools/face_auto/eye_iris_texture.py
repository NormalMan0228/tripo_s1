"""Eyeball texture from the reference front image (texture step 2b): iris disk cut from the painting, sclera and
pupil kept clean, no lid / lash / skin paint on the eyeball.

Eyeball UV (uv_parts.py): per eye an azimuthal map about the forward axis (-y) through the eye centre C (radius
sin(theta/2), equal-area: the front of the eye gets ~1.6x the texels of an equidistant map), left eye in the left half, right eye in the right half of one 2:1 image. Works for any eyeball mesh
around C (P2 eyeball pieces, or a UV-sphere eyeball with C, r from eyes_eyes.json).
Per eye:
  1. iris in the image: MediaPipe iris (468-477) refined by the iris / sclera edge along 96 rays (circle fit on
     the edge points that lie inside the painted eye opening)
  2. iris on the eyeball: the image iris centre is taken back to the head (inverse front map) and shot along the
     view axis onto this eyeball mesh -> iris direction g; iris angular radius from the image radius
  3. the painted iris is unwrapped to polar (radius, angle); the part the painted lids cover (outside the eye
     opening) and, for realistic / semi styles, the catch-light, are refilled from the visible angles at the
     same radius (an iris is close to radially symmetric) -> a full iris disk with its own pupil and colours;
     painted catch-lights are removed on every style (the material's glossy coat makes the catch-lights)
  4. texel -> direction on the eyeball -> angle to g: inside the iris = polar iris, outside = sclera: the
     painted white (brightest visible sclera pixels), a slight shading toward the back, and for realistic /
     semi styles a soft limbal ring and a few faint vessels. Stylised eyes (cartoon, anime) keep their look.
Usage: python eye_iris_texture.py <uv_dir> <ref_dir> <landmarks.json> <out_dir> [--style realistic|semi|cartoon|anime] [--size 1024] [--margin-fit]
Writes <out_dir>/eyes.png (2*size x size), eyes_qa.json, dbg_iris.jpg (painted eye crop with the fitted circle +
the refilled iris). Option (not done): a fixed anime highlight as a view-space emission decal in the material.
"""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_views as rv

a = sys.argv[1:]
UVD, REF, LMJ, OUT = a[0], a[1], a[2], os.path.abspath(a[3])
STYLE = a[a.index('--style') + 1] if '--style' in a else 'realistic'
N = int(a[a.index('--size') + 1]) if '--size' in a else 1024
os.makedirs(OUT, exist_ok=True)
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
em = np.load(os.path.join(UVD, 'mesh_eyes.npz'))
EV, ET = em['V'], em['T']; info = json.loads(str(em['eye_info']))
_sk = np.load(os.path.join(UVD, 'mesh_skin.npz'))
views = rv.Views(REF, LT, _sk['V'], OUT, front_only=True)
if '--margin-fit' in a and 'eye_ring' in _sk: views.fit_eye_margins(rv.eye_margins(_sk['V'], _sk['eye_ring']))   # as the skin bake
fr = views.imgs['front']; mp = views.mp
lum = lambda c: c @ np.array([0.3, 0.59, 0.11], np.float32)
def sat(c): mx, mn = c.max(-1), c.min(-1); return (mx - mn) / np.maximum(mx, 1e-6)
REAL = STYLE in ('realistic', 'semi')
qa = {'style': STYLE}
fwd, ex, ez = np.array([0, -1.0, 0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0])
W2 = 2 * N
img = np.zeros((N, W2, 3), np.float32)
rng = np.random.default_rng(7)
dbg_tiles = []

for s in ('L', 'R'):
    e = info[s]; C = np.array(e['C']); side_u = e['u0']
    poly = views.poly(rv.MP_EYE[s]); ir = mp[rv.MP_IRIS[s]]
    c0 = ir[0]; R0 = float(np.mean(np.linalg.norm(ir[1:] - c0, axis=1)))
    eye_w = np.ptp(poly[:, 0])
    pc = poly.mean(0); pin = pc + (poly - pc) * 0.94                 # eroded opening (no lash / lid paint)
    # ---- 1. refine the circle on the iris / sclera edge
    ang = np.linspace(0, 2 * np.pi, 96, endpoint=False); rr = np.linspace(0.5, 1.8, 66) * R0
    pts = c0 + rr[None, :, None] * np.stack([np.cos(ang), np.sin(ang)], 1)[:, None, :]
    L_ = lum(rv.sample(fr, pts.reshape(-1, 2))).reshape(len(ang), len(rr))
    L_ = (L_[:, :-2] + L_[:, 1:-1] + L_[:, 2:]) / 3
    g_ = np.diff(L_, axis=1); k = np.argmax(g_, 1)
    edge = c0 + (rr[k + 1])[:, None] * np.stack([np.cos(ang), np.sin(ang)], 1)
    ok = (g_[np.arange(len(ang)), k] > 0.02) & rv.point_in_poly(edge, pin)
    c_img, R_img = c0, R0; how = 'mediapipe'
    if ok.sum() >= 10 and np.ptp(np.unwrap(ang[ok])) > np.pi / 2:
        A_ = np.c_[2 * edge[ok], np.ones(ok.sum())]; b_ = (edge[ok] ** 2).sum(1)
        (cx, cy, cc), *_ = np.linalg.lstsq(A_, b_, rcond=None); Rf = math.sqrt(max(cc + cx * cx + cy * cy, 1e-6))
        if 0.7 * R0 < Rf < 1.45 * R0 and np.hypot(cx - c0[0], cy - c0[1]) < 0.5 * R0:
            c_img, R_img = np.array([cx, cy]), Rf; how = 'edge fit'
    # ---- 3. polar iris with lid-covered part and highlight refilled
    NR, NA = 128, 384
    pr = np.linspace(0, 1.12, NR); pa = np.linspace(0, 2 * np.pi, NA, endpoint=False)
    PP = c_img + (pr[:, None, None] * R_img) * np.stack([np.cos(pa), np.sin(pa)], 1)[None]
    pol = rv.sample(fr, PP.reshape(-1, 2)).reshape(NR, NA, 3)
    # visible = inside the opening and not in the band the upper lid shades (the opening moved down by 0.18 R)
    vis = (rv.point_in_poly(PP.reshape(-1, 2), pin) & rv.point_in_poly(PP.reshape(-1, 2) - [0, 0.18 * R_img], pin)).reshape(NR, NA)
    # painted catch-lights (all styles): much brighter and greyer than their ring -> refilled from the same radius
    # (they would turn with the eyeball; the glossy coat of the eye material makes catch-lights that stay put)
    Lp = lum(pol); med = np.array([np.median(Lp[i][vis[i]]) if vis[i].any() else 0 for i in range(NR)])
    hl = (Lp > med[:, None] + (0.18 if REAL else 0.15)) & (sat(pol) < 0.35) & (pr[:, None] < 1.0)
    for _ in range(1 if REAL else 3):                                # stylised blobs have soft anti-aliased rims
        hl = hl | np.roll(hl, 1, 1) | np.roll(hl, -1, 1); hl[1:] |= hl[:-1]; hl[:-1] |= hl[1:]
    vis &= ~hl; qa.setdefault('highlight_cells', {})[s] = int(hl.sum())
    # hidden cells first copy the iris on the opposite side / a quarter turn away (keeps the radial fibres),
    # what is still missing is interpolated along the ring
    if REAL:                    # realistic / semi: the lower half (no lid shadow, no catch-light) mirrored to the top
        mir = (NA - np.arange(NA)) % NA; top = pa > np.pi
        pol[:, top] = pol[:, mir[top]]; vis[:, top] = vis[:, mir[top]]
    src_ok = vis.copy(); orig = pol.copy(); copy_ = np.full_like(pol, np.nan)
    for sh in (NA // 2, NA // 4, -NA // 4):
        take = np.isnan(copy_[..., 0]) & np.roll(src_ok, -sh, 1)
        copy_[take] = np.roll(orig, -sh, 1)[take]
        t2 = ~vis & take; pol[t2] = copy_[t2]; vis = vis | t2
    # feather: visible cells near the hidden part blend toward the copied iris, so no straight seam shows
    import cv2
    ww = cv2.GaussianBlur(np.tile(src_ok.astype(np.float32), (1, 3)), (0, 0), sigmaX=10, sigmaY=2)[:, NA:2 * NA]
    ww = np.clip(2 * ww - 1, 0, 1) * src_ok
    has = ~np.isnan(copy_[..., 0]) & src_ok
    pol[has] = ww[has, None] * orig[has] + (1 - ww[has, None]) * copy_[has]
    for i in range(NR):
        v = np.nonzero(vis[i])[0]
        if len(v) >= max(4, NA // 12):
            for ch in range(3):
                pol[i, :, ch] = np.interp(pa, np.r_[pa[v] - 2 * np.pi, pa[v], pa[v] + 2 * np.pi], np.tile(pol[i, v, ch], 3))
        else: vis[i] = False
    good = np.nonzero([vis[i].any() for i in range(NR)])[0]
    for i in range(NR):
        if not vis[i].any() and len(good): pol[i] = pol[good[np.argmin(np.abs(good - i))]]
    pol = (np.roll(pol, 1, 1) + 2 * pol + np.roll(pol, -1, 1)) / 4      # soften copy edges (radial detail kept)
    if REAL:                                                         # round pupil (catch-light holes, lid shadow)
        Lr = np.median(lum(pol), 1); iris_l = np.median(Lr[(pr > 0.55) & (pr < 0.85)])
        dark = np.nonzero(Lr < 0.5 * iris_l)[0]
        rp = pr[dark[np.nonzero(np.diff(np.r_[dark, 10 ** 6]) > 1)[0][0]]] if len(dark) and dark[0] <= 3 else 0.0
        if 0.12 < rp < 0.75:
            pc_ = np.median(pol[pr < 0.6 * rp].reshape(-1, 3), 0)
            for i in np.nonzero((pr > 0.9 * rp) & (pr < 1.5 * rp))[0]:      # dark spill outside the round pupil
                Li = lum(pol[i]); dk = Li < 0.6 * iris_l
                if dk.any() and (~dk).sum() > NA // 8: pol[i, dk] = np.median(pol[i, ~dk], 0)
            tp = np.clip((pr - 0.85 * rp) / (0.2 * rp), 0, 1)[:, None, None]; tp = tp * tp * (3 - 2 * tp)
            pol = pc_ * (1 - tp) + pol * tp
        qa.setdefault('pupil_r_rel', {})[s] = round(float(rp), 3)
    # ---- sclera colour: brightest visible painted white
    xs, ys = np.meshgrid(np.arange(int(pc[0] - eye_w), int(pc[0] + eye_w)) + 0.5, np.arange(int(pc[1] - eye_w / 2), int(pc[1] + eye_w / 2)) + 0.5)
    q = np.c_[xs.ravel(), ys.ravel()]; q = q[rv.point_in_poly(q, pin) & (np.linalg.norm(q - c_img, axis=1) > 1.15 * R_img)]
    if len(q) > 30:
        sc_px = rv.sample(fr, q); sc_px = sc_px[lum(sc_px) >= np.percentile(lum(sc_px), 70)]
        sclera = np.median(sc_px, 0)
    else: sclera = np.array([0.9, 0.88, 0.85], np.float32)
    white = np.array([0.93, 0.91, 0.88]) if REAL else np.array([0.97, 0.97, 0.97])
    sclera = 0.6 * sclera + 0.4 * white if REAL else 0.5 * sclera + 0.5 * white
    sclera = sclera * (0.95 / max(float(sclera.max()), 0.95)) if sclera.max() > 0.95 else sclera
    # ---- 2. iris on this eyeball
    xz = views.front_inv(c_img[None])[0]
    sel = np.nonzero(np.sign(EV[ET[:, 0], 0]) == np.sign(C[0]))[0]
    tri = EV[ET[sel]]; A2 = tri[:, :, [0, 2]]
    v0, v1 = A2[:, 1] - A2[:, 0], A2[:, 2] - A2[:, 0]; w_ = xz - A2[:, 0]
    den = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
    with np.errstate(all='ignore'):
        b1 = (w_[:, 0] * v1[:, 1] - w_[:, 1] * v1[:, 0]) / den; b2 = (v0[:, 0] * w_[:, 1] - v0[:, 1] * w_[:, 0]) / den
    inside = (b1 >= 0) & (b2 >= 0) & (b1 + b2 <= 1) & (np.abs(den) > 1e-14)
    if inside.any():
        yy = tri[inside, 0, 1] + b1[inside] * (tri[inside, 1, 1] - tri[inside, 0, 1]) + b2[inside] * (tri[inside, 2, 1] - tri[inside, 0, 1])
        Ph = np.array([xz[0], yy.min(), xz[1]]); hit = 'mesh'
    else:
        r_ = e['r']; dxz = np.hypot(xz[0] - C[0], xz[1] - C[2]); Ph = np.array([xz[0], C[1] - math.sqrt(max(r_ * r_ - dxz * dxz, 0)), xz[1]]); hit = 'sphere'
    g = (Ph - C) / np.linalg.norm(Ph - C); Rf3 = float(np.linalg.norm(Ph - C))
    ends = views.front_inv(np.array([c_img - [R_img, 0], c_img + [R_img, 0], c_img - [0, R_img], c_img + [0, R_img]]))
    r_iris = 0.25 * (np.linalg.norm(ends[0] - ends[1]) + np.linalg.norm(ends[2] - ends[3]))
    alpha = math.asin(min(r_iris / Rf3, 0.95))
    if 'iris_dir' in e and 'iris_radius_deg' in e:                   # eye-fit base (eyes_meta.json): use its iris
        g = np.array(e['iris_dir'], float); g /= np.linalg.norm(g); alpha = math.radians(float(e['iris_radius_deg']))
        Rf3 = float(e['r']); r_iris = Rf3 * math.sin(alpha); hit = 'eyes_meta'
    qa[s] = {'iris_img_px': [round(float(c_img[0]), 1), round(float(c_img[1]), 1)], 'iris_r_px': round(float(R_img), 1), 'fit': how,
             'iris_dir': [round(float(x), 3) for x in g], 'iris_r_mm': round(float(r_iris * 1000), 2), 'iris_deg': round(math.degrees(alpha), 1),
             'eyeball_front_r_mm': round(Rf3 * 1000, 2), 'hit': hit, 'sclera': [round(float(x), 3) for x in sclera],
             'pupil_lum': round(float(lum(pol[:10].reshape(-1, 3)).mean()), 3)}
    # ---- 4. texels of this half
    px, py = np.meshgrid(np.arange(N) + (0 if s == 'L' else N), np.arange(N))
    U = (px + 0.5) / W2; Vv = 1 - (py + 0.5) / N
    a_ = (U - side_u) / 0.25; b_ = (Vv - 0.5) / 0.5
    rho = np.minimum(np.hypot(a_, b_), 1.0); phi = np.arctan2(b_, a_)
    EA = e.get('map', 'equidistant') == 'equal_area'                 # uv radius = sin(theta / 2) (front gets more texels)
    th = 2 * np.arcsin(rho) if EA else rho * np.pi
    D = (np.cos(th)[..., None] * fwd + np.sin(th)[..., None] * (np.cos(phi)[..., None] * ex + np.sin(phi)[..., None] * ez))
    beta = np.arccos(np.clip(D @ g, -1, 1))
    e1 = ex - (ex @ g) * g; e1 /= np.linalg.norm(e1); e2 = ez - (ez @ g) * g - (ez @ e1) * e1; e2 /= np.linalg.norm(e2)
    psi = np.mod(np.arctan2(-(D @ e2), D @ e1), 2 * np.pi)
    ri = beta / alpha
    # polar lookup (bilinear, periodic in angle)
    fi = np.clip(ri / 1.12 * (NR - 1), 0, NR - 1.001); fj = psi / (2 * np.pi) * NA
    i0 = np.floor(fi).astype(int); j0 = np.floor(fj).astype(int) % NA; j1 = (j0 + 1) % NA; ti = (fi - i0)[..., None]; tj = (fj - np.floor(fj))[..., None]
    I = (pol[i0, j0] * (1 - ti) * (1 - tj) + pol[i0, j1] * (1 - ti) * tj + pol[i0 + 1, j0] * ti * (1 - tj) + pol[i0 + 1, j1] * ti * tj)
    if REAL: I = I * (1 - 0.35 * np.clip((ri - 0.82) / 0.18, 0, 1) ** 2)[..., None]      # limbal ring
    Sc = sclera * (1 - 0.10 * np.clip((beta - 0.6) / 0.9, 0, 1))[..., None]
    if REAL: Sc = Sc * (1 - 0.04 * np.clip((beta - 0.9) / 0.6, 0, 1))[..., None] + np.array([0.03, -0.01, -0.01]) * np.clip((beta - 0.9) / 0.6, 0, 1)[..., None]
    t = np.clip((ri - 1.0) / 0.07, 0, 1)[..., None]; t = t * t * (3 - 2 * t)
    half = I * (1 - t) + Sc * t
    if REAL:                                                       # faint vessels from the corners toward the iris
        import cv2
        vm = np.zeros((N, N), np.float32)
        for _ in range(int(rng.integers(10, 16))):
            ph0 = rng.uniform(0, 2 * np.pi)
            if abs(math.cos(ph0)) < 0.5: continue                    # mostly the left / right corners (visible white)
            bt = 1.35; pts = []; vel = 0.0
            while bt > alpha * 1.3:
                dd = math.cos(bt) * g + math.sin(bt) * (math.cos(ph0) * e1 + math.sin(ph0) * e2)
                th_ = math.acos(np.clip(dd @ fwd, -1, 1)); ph_ = math.atan2(dd @ ez, dd @ ex); rh = math.sin(th_ / 2) if EA else th_ / np.pi
                uu = side_u + 0.25 * rh * math.cos(ph_); vv = 0.5 + 0.5 * rh * math.sin(ph_)
                pts.append((uu * W2 - (0 if s == 'L' else N), (1 - vv) * N))
                bt -= 0.02; vel = 0.85 * vel + rng.normal(0, 0.012); ph0 += vel      # smooth wandering line
            if len(pts) > 2:
                cv2.polylines(vm, [np.round(np.array(pts) * 4).astype(np.int32)], False, float(rng.uniform(0.4, 1.0)), 1, cv2.LINE_AA, shift=2)
        vm = cv2.GaussianBlur(vm, (0, 0), 0.8) * np.clip((beta - alpha * 1.25) / 0.5, 0, 1)
        half = half * (1 - 0.3 * vm[..., None]) + np.array([0.72, 0.28, 0.27]) * (0.3 * vm[..., None])
    img[:, (0 if s == 'L' else N):(N if s == 'L' else W2)] = half
    # debug tile: painted eye crop with the fitted circle, refilled iris
    import cv2
    x0_, y0_ = int(c_img[0] - 2.2 * R_img), int(c_img[1] - 1.4 * R_img); sz = int(4.4 * R_img)
    crop = (np.clip(fr[max(y0_, 0):y0_ + int(2.8 * R_img), max(x0_, 0):x0_ + sz], 0, 1) * 255).astype(np.uint8).copy()
    cv2.circle(crop, (int(c_img[0] - x0_), int(c_img[1] - y0_)), int(R_img), (0, 255, 0), 1)
    cv2.polylines(crop, [np.round(pin - [x0_, y0_]).astype(np.int32)], True, (255, 0, 0), 1)
    crop = cv2.resize(crop, (440, 280))
    flat = np.zeros((280, 280, 3), np.float32); yy_, xx_ = np.mgrid[0:280, 0:280]
    rr_ = np.hypot(xx_ - 140, yy_ - 140) / 125.0; aa = np.mod(np.arctan2(yy_ - 140, xx_ - 140), 2 * np.pi)
    ii = np.clip(rr_ / 1.12 * (NR - 1), 0, NR - 1).astype(int); jj = (aa / (2 * np.pi) * NA).astype(int) % NA
    flat = (np.clip(pol[ii, jj], 0, 1) * 255).astype(np.uint8)
    dbg_tiles.append(np.concatenate([crop, flat], 1))

rv.save_rgb(os.path.join(OUT, 'eyes.png'), img)
rv.save_rgb(os.path.join(OUT, 'dbg_iris.png'), np.concatenate(dbg_tiles, 0).astype(np.float32) / 255)
json.dump(qa, open(os.path.join(OUT, 'eyes_qa.json'), 'w'), indent=1)
print('EYES', json.dumps(qa))
