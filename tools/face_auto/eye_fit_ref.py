"""Eye openings of the Track P bases fitted to the REFERENCE IMAGE eye contour (method 1: P2 head, cut along loops),
with our own eyeball (sphere) instead of the P2 eyeball piece.

detect <ref_front.png> <out_dir> [mp|image|auto] [--trim]   (art-venv python: numpy, OpenCV; MediaPipe via mp_detect.py)
  1. MediaPipe Face Landmarker on the front image (478 points, iris 468-477).
  2. Per eye, two contours in image pixels (upper / lower lid, outer -> inner corner, 41 samples each):
     - mp: the 16 MediaPipe eye-contour points, a Catmull-Rom curve through them (inner corner = canthus tip;
       --trim cuts the lids where the white of the eye ends before the pink caruncle: blunt inner end, not used);
     - image: visible eyeball = sclera (saturation < 58, value > 135, grown from white seeds; bright skin patches and
       iris highlights dropped) + iris (ellipse fitted to the iris / sclera border). Lid points = sclera border pixels
       away from the iris; corners = the sclera's ends along its long axis (outer = farther from the nose); each lid
       o(t) = sum c_k phi_k(t) over the corner chord (sqrt(t(1-t)) terms for rounded ends, t(1-t) terms for pointed
       ones; robust least squares with a small ridge, so a lid is bridged smoothly where the iris touches it).
     auto, per head: mp when MediaPipe's eyes are human-like (mean aspect >= 2.45), else image (cartoon eyes:
     MediaPipe draws a human-size eye inside the big painted one; f11 2.2, f09 2.1 vs f02 2.9, f06 2.8).
  3. Iris: MediaPipe iris points (mp) or the fitted ellipse (image): centre and radii in pixels.
  Writes <out>/eye_contour.json and eye_contour.jpg (green = chosen, blue = the other method, red = iris, yellow = corners).
fit <P_dir> <eye_contour.json> <out_dir> [options]            (Blender)
  1. Front map image <-> head (x, z) as project_texture.py's front_uv (similarity + thin-plate spline, lam 50), fitted
     on the NON-EYE landmarks (1-6, 16, 20, 22, 24, 34, 35): the head's eye points come from the P2 margin being
     replaced. Inverse by Newton. Both eyes' contours go to the head frame, the right one is mirrored onto the left,
     the two are averaged (symmetric target, 48 samples per lid).
  2. Margin = eyes_meta margin_vids (closed edge path in 'orig'; f09: the hole loop). Dents (the path running round
     2-3 sides of one outer face) are cut short (the face goes to the cut side). Corners = ends along eyes_meta A.
     In-plane targets: every margin vertex goes to its nearest point on its target lid (a move across the lid); only
     over the end 30 % of each lid path it also slides along, so the corners land on the target corners; spacing kept
     >= 40 % of even ('--param arc': same share of arc length everywhere). '--inner axis': both lids end at the P2 inner
     corner's position along the eye axis and meet on their own midline (the P2 caruncle fold stays skin; f02, f06);
     '--inner p2': same, but they meet at the P2 corner point itself.
  3. Depth and eyeball ('--ball fit', default): each margin vertex keeps its own depth (y) at its new (x, z); our eyeball
     sphere is fitted in the middle of the band under these points (Gauss-Newton, priors: centre toward (iris x, P2 C y,
     iris z) with weight --prior-xz on x, z (default 0.01; per head 0.2-1 so the rest gaze is <= 5 deg off straight
     ahead), radius toward the P2 eyeball, 0.01 per point); only margin vertices outside the band --band lo hi (default
     0.6 0.85 mm) above the sphere move in depth, onto it (loop_organs shrinks the ball below a 0.6 mm margin gap). iris_dir = from C through the reference iris centre lifted onto
     the sphere (the rest gaze); iris radii from the reference iris (ellipse / MediaPipe iris). '--ball p2': the P2
     eyeball sphere, margin lifted onto r + 0.65 mm (much larger depth moves, not used).
  4. Field: each margin vertex turns about C onto its target direction (rotation vector) and changes its distance to C;
     both are smoothed along the margin (Gaussian, sigma 5 mm of arc) and given to every skin vertex outside the
     margin from the nearest margin point, times 1 - smoothstep(g / R), g = geodesic distance from the margin,
     R = max(2.5 median edge lengths, 2.5 x local margin move) -> the lid rim slides over the eyeball as a whole
     and keeps its shape; '--rim 1': ring 1 takes the mean move of its margin neighbours exactly, ring 2 half of its
     ring-1 neighbours' (no flips where the margin move changes fast at a corner). The pocket inside the margin (cut away
     by loop_organs) follows with 2 R. Then: faces turned
     > 78 deg are untangled (Laplacian, margin fixed), the skin within 3 mm of each corner is smoothed (8 half steps),
     outer skin in front of C is kept >= 0.47 mm (3 rings next to the margin) / 0.32 mm off the sphere (loop_organs'
     floors, so its eyeball shrink is 0). Left side computed, right side = exact mirror image through the mirror
     vertex pairs. Options not used by default: --arap N (as-rigid-as-possible refinement: lumps at f06's outer corner),
     --recut mm (re-cut through skin where the target is that far outside the margin), --rmax mm (falloff cap: flips).
     Per-head options of the P2 bases: clean/P2/run_p2.sh.
  5. Writes <out>/base.blend ('orig' and 'noface' edited alike, p2_eyes removed, p2_lids hidden), landmarks.json (eye
     points 7-14 from the new margin), eyes_meta.json (C, r, A, up_path / lo_path / raw (48 samples), margin_vids,
     margin_kind, iris_dir, iris_centre, iris_radius_deg, iris_radii_deg / _mm, eye_fit), rig_points.json (eye joints
     on C, lid joints snapped onto the new skin), eye_fit_qa.json (front / 3D distances before / after, opening
     width / height, moves, flips, stretch, clearances) and _work/eye_fit_uv.json (contours in image pixels + map).
views <base.blend> <eyes_meta.json> <out_prefix> <cx> <cz> <size> [--ball]   (Blender) grey + wire close-ups (front, 3/4)
overlay <eye_fit_uv.json> <out.jpg> [label]       (art-venv) reference eyes with reference (green) / old (red) / new (cyan)
sheet <title> <new_base_dir> <test_dir> <old_test_dir> <out.jpg>   (art-venv) verification sheet, see sheet_main.
"""
import sys, os, json, math, subprocess, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MP_PY = os.path.join(ROOT, '.tools', 'landmark-venv', 'Scripts', 'python.exe')
MP_MODEL = os.path.join(ROOT, '.tools', 'landmark-models', 'face_landmarker.task')
MP_DETECT = os.path.join(HERE, 'mp_detect.py')
# MediaPipe eye contours, outer corner -> upper lid -> inner corner -> lower lid; 'L' = character's left (+x, image right)
MP_EYE = {'L': {'outer': 263, 'up': [466, 388, 387, 386, 385, 384, 398], 'inner': 362, 'lo': [249, 390, 373, 374, 380, 381, 382],
                'iris': [473, 474, 475, 476, 477]},
          'R': {'outer': 33, 'up': [246, 161, 160, 159, 158, 157, 173], 'inner': 133, 'lo': [7, 163, 144, 145, 153, 154, 155],
                'iris': [468, 469, 470, 471, 472]}}
MP35 = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 8: 159, 9: 133, 10: 145,
        11: 362, 12: 386, 13: 263, 14: 374, 16: 1, 20: 61, 22: 291, 24: 152, 34: 13, 35: 14}
NONEYE = (1, 2, 3, 4, 5, 6, 16, 20, 22, 24, 34, 35)
MM = 1000.0


def arclen(P):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]


def resample_open(P, n):
    s = arclen(P); t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, j]) for j in range(P.shape[1])], 1)


def smooth_open(P, n, k=3):
    """smooth curve through the points of an open polyline (ends kept): Catmull-Rom by arc length, n samples"""
    P = np.asarray(P, float); s = arclen(P); s = s / s[-1]
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]]); sq = np.r_[-s[1], s, 2 - s[-2]]
    t = np.linspace(0, 1, n); out = np.empty((n, P.shape[1]))
    for i, tt in enumerate(t):
        j = min(max(np.searchsorted(sq, tt) - 1, 1), len(Q) - 3)
        p0, p1, p2, p3 = Q[j - 1], Q[j], Q[j + 1], Q[j + 2]; u = (tt - sq[j]) / max(sq[j + 1] - sq[j], 1e-12)
        out[i] = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
    return out


# ====================================================================== detect (image side)
def detect_main(argv):
    import cv2
    REF, OUT = argv[0], os.path.abspath(argv[1]); KIND = argv[2] if len(argv) > 2 and not argv[2].startswith('--') else 'auto'
    TRIM = '--trim' in argv
    os.makedirs(OUT, exist_ok=True)
    js = os.path.join(tempfile.mkdtemp(), 'mp.json')
    subprocess.run([MP_PY, '-I', MP_DETECT, REF, MP_MODEL, js], check=True, capture_output=True)
    im = cv2.imread(REF); H, W = im.shape[:2]
    mp = np.array(json.load(open(js))) * [W, H]
    if not len(mp): raise SystemExit('MediaPipe found no face on ' + REF)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    fw = abs(mp[454, 0] - mp[234, 0])                                     # face width (px)
    res = {'image': os.path.abspath(REF), 'size': [W, H], 'face_width_px': float(fw),
           'mp35': {str(k): mp[v].tolist() for k, v in MP35.items()}, 'eyes': {}}
    draw = im.copy()
    for s in 'LR':
        m = MP_EYE[s]
        mp_up = np.vstack([mp[m['outer']], mp[m['up']], mp[m['inner']]]); mp_lo = np.vstack([mp[m['outer']], mp[m['lo']], mp[m['inner']]])
        mp_up_s, mp_lo_s = smooth_open(mp_up, 41), smooth_open(mp_lo, 41)
        ic = mp[m['iris'][0]]; ir = float(np.mean(np.linalg.norm(mp[m['iris'][1:]] - ic, axis=1)))
        e_mp = {'up': mp_up_s.tolist(), 'lo': mp_lo_s.tolist(), 'outer': mp[m['outer']].tolist(), 'inner': mp[m['inner']].tolist(),
                'iris_c': ic.tolist(), 'iris_r': [ir, ir], 'iris_ang': 0.0}
        car = trim_caruncle(lab, hsv, mp_up_s, mp_lo_s) if TRIM else None
        if car is not None:
            k_, cpt = car; e_mp['caruncle_trim'] = {'mp_inner': e_mp['inner'], 'kept_share': round(k_ / 40.0, 3)}
            up_t = np.vstack([mp_up_s[:int(k_) + 1], cpt]); lo_t = np.vstack([mp_lo_s[:int(k_) + 1], cpt])
            e_mp['up'] = resample_open(up_t, 41).tolist(); e_mp['lo'] = resample_open(lo_t, 41).tolist(); e_mp['inner'] = cpt.tolist()
        e_im, dbg = image_eye(hsv, mp, s, fw)
        info = {'mp': e_mp, 'image': e_im, 'debug': dbg}
        # choice
        h_mp = float(np.ptp(np.r_[mp_up_s, mp_lo_s][:, 1])); w_mp = float(abs(mp_up_s[0, 0] - mp_up_s[-1, 0]))
        aspect_mp = w_mp / max(h_mp, 1e-6); info['mp_aspect'] = round(aspect_mp, 2)
        if e_im is not None:
            info['mp_vs_image_px'] = contour_dev(e_mp, e_im)
            h_im = float(np.ptp(np.r_[np.array(e_im['up']), np.array(e_im['lo'])][:, 1])); info['height_px'] = {'mp': round(h_mp, 1), 'image': round(h_im, 1)}
        res['eyes'][s] = info
    # method per head (both eyes alike): MediaPipe when its eyes are human-like (aspect >= 2.45) or the image method
    # failed; else the image contour (cartoon eyes: MediaPipe draws a human eye inside the big one)
    asp = np.mean([res['eyes'][s]['mp_aspect'] for s in 'LR']); img_ok = all(res['eyes'][s]['image'] is not None for s in 'LR')
    pick = KIND if KIND != 'auto' else ('mp' if asp >= 2.45 or not img_ok else 'image')
    if pick == 'image' and not img_ok: raise SystemExit('image method failed: ' + json.dumps({s: res['eyes'][s]['debug'] for s in 'LR'}))
    res['method'] = pick; res['mp_aspect_mean'] = round(float(asp), 2)
    for s in 'LR':
        info = res['eyes'][s]; info['method'] = pick; info['chosen'] = info[pick]
        for nm, col, wd in (('mp', (255, 120, 0), 3), ('image', (255, 120, 0), 3)):
            e = info[nm]
            if e is None: continue
            c = (0, 230, 0) if nm == pick else col
            for k in ('up', 'lo'):
                cv2.polylines(draw, [np.round(np.array(e[k])).astype(np.int32)], False, c, 3 if nm == pick else 2, cv2.LINE_AA)
            if nm == pick:
                cv2.ellipse(draw, (tuple(np.round(e['iris_c']).astype(int).tolist()), tuple(int(2 * r) for r in e['iris_r']), e['iris_ang']), (0, 0, 255), 2, cv2.LINE_AA)
                for k in ('outer', 'inner'): cv2.circle(draw, tuple(np.round(e[k]).astype(int).tolist()), 7, (0, 230, 255), -1)
    json.dump(res, open(os.path.join(OUT, 'eye_contour.json'), 'w'), indent=1)
    # overlay: both eyes, cropped
    allp = np.vstack([np.array(res['eyes'][s]['chosen'][k]) for s in 'LR' for k in ('up', 'lo')])
    c = allp.mean(0); hw = 0.62 * np.ptp(allp[:, 0]); hh = 0.42 * hw
    x0, x1, y0, y1 = int(c[0] - hw), int(c[0] + hw), int(c[1] - hh), int(c[1] + hh)
    crop = draw[max(y0, 0):y1, max(x0, 0):x1]; crop = cv2.resize(crop, (1600, int(1600 * crop.shape[0] / crop.shape[1])), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(OUT, 'eye_contour.jpg'), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print('DETECT', json.dumps({s: {'method': res['eyes'][s]['method'], 'mp_aspect': res['eyes'][s]['mp_aspect'],
                                    'mp_vs_image_px': res['eyes'][s].get('mp_vs_image_px')} for s in 'LR'}))


def trim_caruncle(lab, hsv, up, lo):
    """MediaPipe's inner eye corner is the canthus tip, past the pink caruncle; the eyeball (and the P2 margin) ends where
    the white of the eye ends. Along the midline between the lids (41 samples outer -> inner, 9 x 9 px medians), the
    eyeball ends at the last sclera sample (Lab a < 138, saturation < 60) before the caruncle (a >= 138) seen from the
    inner corner. Returns (index of the last kept sample, new inner corner = midline point half a step further) or None."""
    mid = (up + lo) / 2; n = len(mid); a = np.empty(n); sat = np.empty(n)
    for k, (x, y) in enumerate(np.round(mid).astype(int)):
        a[k] = np.median(lab[y - 4:y + 5, x - 4:x + 5, 1]); sat[k] = np.median(hsv[y - 4:y + 5, x - 4:x + 5, 1])
    scl = (a < 138) & (sat < 60)
    for k in range(n - 2, n // 2, -1):
        if scl[k] and scl[k - 1]:
            if k >= n - 3: return None                                    # no caruncle seen
            return k, (mid[k] + mid[k + 1]) / 2
    return None


def contour_dev(a, b):
    A = np.r_[np.array(a['up']), np.array(a['lo'])]; B = np.r_[np.array(b['up']), np.array(b['lo'])]
    d = np.min(np.linalg.norm(A[:, None] - B[None], axis=2), 1)
    return {'mean': round(float(d.mean()), 1), 'max': round(float(d.max()), 1)}


def image_eye(hsv, mp, s, fw):
    """visible eyeball of one eye from the image colours (see the module docstring). Returns (contour dict | None, debug)."""
    import cv2
    m = MP_EYE[s]; ring = mp[[m['outer'], m['inner']] + m['up'] + m['lo']]; ic = ring.mean(0)
    ew = float(np.ptp(ring[:, 0])); hw = int(1.0 * ew + 0.04 * fw); hh = int(0.8 * hw)
    x0, y0 = max(int(ic[0] - hw), 0), max(int(ic[1] - hh), 0); Hs, Ss, Vs = (hsv[y0:y0 + 2 * hh, x0:x0 + 2 * hw, k] for k in range(3))
    dbg = {'window': [x0, y0, 2 * hw, 2 * hh]}
    seed = (Ss < 28) & (Vs > 175)
    grow = (Ss < 58) & (Vs > 135)
    n, lab, st, _ = cv2.connectedComponentsWithStats(grow.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 0.0005 * hw * hh and seed[lab == i].sum() > 0.25 * st[i, cv2.CC_STAT_AREA]: keep[i] = True
    W_ = keep[lab]
    # the eye: components near the MediaPipe iris centre (within 0.11 face widths), the skin's bright patches dropped
    n, lab, st, cen = cv2.connectedComponentsWithStats(W_.astype(np.uint8), 8)
    cc = ic - [x0, y0]; comps = [i for i in range(1, n) if np.linalg.norm(cen[i] - cc) < 0.9 * ew and st[i, cv2.CC_STAT_AREA] > 0.002 * hw * hh]
    if not comps: return None, dict(dbg, fail='no sclera near the iris')
    W_ = np.isin(lab, comps)
    # iris: non-white pixels enclosed by the sclera hull; ellipse through its border with the sclera
    pts = np.argwhere(W_)[:, ::-1].astype(np.int32); hull = cv2.convexHull(pts)
    Hm = np.zeros(W_.shape, np.uint8); cv2.fillConvexPoly(Hm, hull, 1); Hm = Hm.astype(bool)
    I_ = Hm & ~W_
    n, lab, st, cen = cv2.connectedComponentsWithStats(I_.astype(np.uint8), 8)
    if n < 2: return None, dict(dbg, fail='no iris blob')
    ib = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])); IB = lab == ib
    ker = np.ones((3, 3), np.uint8)
    border = IB & cv2.dilate(W_.astype(np.uint8), ker, iterations=2).astype(bool)          # iris pixels touching sclera
    hull_edge = ~cv2.erode(Hm.astype(np.uint8), ker, iterations=4).astype(bool)
    bp = np.argwhere(border & ~hull_edge)[:, ::-1].astype(np.float32)
    if len(bp) < 20: return None, dict(dbg, fail='iris border too short')
    (ex, ey), (ea, eb), eang = cv2.fitEllipse(bp)
    for _ in range(2):                                       # drop border points far off the ellipse (lid corners of the blob)
        dd = ellipse_dist(bp, (ex, ey), (ea / 2, eb / 2), eang); k = dd < max(2.0, np.percentile(dd, 80))
        (ex, ey), (ea, eb), eang = cv2.fitEllipse(bp[k])
    dbg['iris_border_pts'] = int(len(bp))
    # lid points: sclera border pixels away from the iris ellipse
    Wb = W_ & ~cv2.erode(W_.astype(np.uint8), ker).astype(bool)
    ell = np.zeros(W_.shape, np.uint8); cv2.ellipse(ell, ((ex, ey), (ea * 1.06 + 6, eb * 1.06 + 6), eang), 1, -1)
    lp = np.argwhere(Wb & ~ell.astype(bool))[:, ::-1].astype(float)
    if len(lp) < 30: return None, dict(dbg, fail='few lid points')
    # corners: ends of the sclera along its long axis (PCA of sclera + iris pixels)
    A_ = np.r_[np.argwhere(W_)[:, ::-1], np.argwhere(IB)[:, ::-1]].astype(float); c0 = A_.mean(0)
    ev = np.linalg.eigh(np.cov((A_ - c0).T))[1][:, -1]
    if ev[0] < 0: ev = -ev
    tW = (np.argwhere(W_)[:, ::-1] - c0) @ ev; PW = np.argwhere(W_)[:, ::-1].astype(float)
    pa, pb = PW[np.argmin(tW)], PW[np.argmax(tW)]            # image-left, image-right end
    # corner = mean of the few extreme pixels (a pointed corner is one pixel wide)
    for nm in ('a', 'b'):
        t_ = tW if nm == 'b' else -tW; sel = t_ >= t_.max() - 2.0; p_ = PW[sel].mean(0)
        if nm == 'a': pa = p_
        else: pb = p_
    # outer = farther from the face centre line (x of nose tip 1)
    xc = mp[1, 0] - x0
    outer, inner = (pa, pb) if abs(pa[0] - xc) > abs(pb[0] - xc) else (pb, pa)
    ax = inner - outer; L = np.linalg.norm(ax); ax /= L; nrm = np.array([ax[1], -ax[0]])        # image: up = -y
    if nrm[1] > 0: nrm = -nrm
    t = (lp - outer) @ ax; o = (lp - outer) @ nrm
    # lid points split by the chord; each lid o(t) (offset from the chord, t along it) fitted with corners fixed
    up = np.c_[t, o][(o > 0) & (t > -2) & (t < L + 2)]; lo = np.c_[t, o][(o < 0) & (t > -2) & (t < L + 2)]
    dbg['lid_pts'] = {'up': int(len(up)), 'lo': int(len(lo))}
    def basis(tt):
        tt = np.clip(tt, 0, 1); q = np.sqrt(tt * (1 - tt)); p = tt * (1 - tt); c = tt - 0.5
        return np.stack([q, p, p * c, p * c * c, q * c, p * c ** 3], 1)
    def fit_lid(P):
        """o(t) = sum c_k phi_k(t): sqrt(t(1-t)) terms allow rounded ends, t(1-t) terms pointed ones; o = 0 at the
        corners; robust (Cauchy) least squares with a small ridge so gaps (iris touching the lid) are bridged smoothly"""
        if len(P) < 8: return None
        tt = P[:, 0] / L; A = basis(tt); w = np.ones(len(P)); lam = 1e-3 * len(P)
        for _ in range(5):
            Aw = A * w[:, None]; c = np.linalg.solve(Aw.T @ A + lam * np.eye(A.shape[1]), Aw.T @ P[:, 1]); r = P[:, 1] - A @ c
            w = 1 / (1 + (r / max(1.5, 2.5 * np.median(np.abs(r)))) ** 2)
        ts = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, 41)); os_ = basis(ts) @ c       # denser near the corners
        return np.c_[ts * L, os_], float(np.median(np.abs(r))), coverage_gap(tt)
    fu, fl = fit_lid(up), fit_lid(lo)
    to_img = lambda Q: outer + np.outer(Q[:, 0], ax) + np.outer(Q[:, 1], nrm) + [x0, y0]
    dbg.update(lid_fit_res_px={'up': round(fu[1], 2), 'lo': round(fl[1], 2)}, lid_gap_frac={'up': round(fu[2], 2), 'lo': round(fl[2], 2)},
               sclera_px=int(W_.sum()), iris_blob_px=int(IB.sum()))
    e = {'up': to_img(fu[0]).tolist(), 'lo': to_img(fl[0]).tolist(), 'outer': (outer + [x0, y0]).tolist(), 'inner': (inner + [x0, y0]).tolist(),
         'iris_c': [float(ex + x0), float(ey + y0)], 'iris_r': [float(ea / 2), float(eb / 2)], 'iris_ang': float(eang),
         'lid_pts_up': to_img(up[::max(1, len(up) // 150)]).tolist(), 'lid_pts_lo': to_img(lo[::max(1, len(lo) // 150)]).tolist()}
    return e, dbg


def overlay_main(argv):
    """overlay <eye_fit_uv.json> <out.jpg> [label]: the reference eyes with the image contour (green), the P2 margin
    before (red) and after the fit (cyan, if present), shot through the front map; iris centre (yellow)."""
    import cv2
    U = json.load(open(argv[0])); im = cv2.imread(U['img']); lab = argv[2] if len(argv) > 2 else ''
    for k, col, wd in (('target', (0, 220, 0), 4), ('target_mirror', (0, 220, 0), 4), ('old', (40, 40, 255), 3), ('old_mirror', (40, 40, 255), 3),
                       ('new', (255, 220, 0), 3), ('new_mirror', (255, 220, 0), 3)):
        if k in U: cv2.polylines(im, [np.round(np.array(U[k])).astype(np.int32)], True, col, wd, cv2.LINE_AA)
    for k in ('iris_c', 'iris_c_mirror'):
        if k in U: cv2.circle(im, tuple(np.round(U[k]).astype(int).tolist()), 8, (0, 230, 255), -1)
    allp = np.vstack([np.array(U['target']), np.array(U['target_mirror'])]); c = allp.mean(0); hw = 0.62 * np.ptp(allp[:, 0]); hh = 0.40 * hw
    y0_, x0_ = max(int(c[1] - hh), 0), max(int(c[0] - hw), 0)
    crop = im[y0_:int(c[1] + hh), x0_:int(c[0] + hw)].copy()
    if 'render' in U and os.path.exists(U['render']['path']):       # the head's front render warped into the image (50 %)
        LT = {int(k): np.array(v) for k, v in U['map']['LT'].items()}; mp35 = {int(k): np.array(v) for k, v in U['map']['mp35'].items()}
        FM = FrontMap(LT, mp35); R_ = cv2.imread(U['render']['path']); res = R_.shape[0]; sz = U['render']['size']; cx, cz = U['render']['centre_xz']
        vv, uu = np.mgrid[0:crop.shape[0]:2, 0:crop.shape[1]:2]; XZ = FM.inv(np.c_[uu.ravel() + x0_, vv.ravel() + y0_])
        j = np.clip(((XZ[:, 0] - cx + sz / 2) / sz * res).astype(int), 0, res - 1); i = np.clip(((cz + sz / 2 - XZ[:, 1]) / sz * res).astype(int), 0, res - 1)
        warp = R_[i, j].reshape(vv.shape + (3,)); warp = cv2.resize(warp, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_LINEAR)
        crop = (0.5 * crop + 0.5 * warp).astype(np.uint8)
    crop = cv2.resize(crop, (1600, int(1600 * crop.shape[0] / crop.shape[1])), interpolation=cv2.INTER_AREA)
    if lab: cv2.putText(crop, lab, (14, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.imwrite(argv[1], crop, [cv2.IMWRITE_JPEG_QUALITY, 88])


def sheet_main(argv):
    """sheet <title> <new_base_dir> <test_dir> <old_test_dir> <out.jpg>   (art-venv python)
    row 1: reference eye (same frame as the base renders; green = image contour, cyan = fitted margin) | old P2 base |
           new base with our eyeball (<new_base_dir>/_work/v_*_front.png, v_frame.json from views);
    row 2: after loop_organs + organ_blink_keys (preview_loop pv/): rest | blink 0.5 (+ Mid corrective) | blink 1.0;
    row 3: old P chain rest (<old_test_dir>/pv) | new 3/4 rest | new 3/4 blink 1.0."""
    import cv2
    TITLE, N, TD, OD, OUTJ = argv[:5]; S_ = 600
    U = json.load(open(os.path.join(N, '_work', 'eye_fit_uv.json'))); fr = json.load(open(os.path.join(N, '_work', 'v_frame.json')))
    LT = {int(k): np.array(v) for k, v in U['map']['LT'].items()}; mp35 = {int(k): np.array(v) for k, v in U['map']['mp35'].items()}
    FM = FrontMap(LT, mp35); im = cv2.imread(U['img'])
    for k, col in (('target', (0, 220, 0)), ('new', (255, 220, 0))):
        cv2.polylines(im, [np.round(np.array(U[k])).astype(np.int32)], True, col, 3, cv2.LINE_AA)
    cx, cz, sz = fr['cx'], fr['cz'], fr['size']
    g = np.linspace(-0.5, 0.5, 300); GX, GZ = np.meshgrid(cx + g * sz, cz - g * sz); UV = FM.fwd(np.c_[GX.ravel(), GZ.ravel()]).reshape(300, 300, 2).astype(np.float32)
    ref = cv2.remap(im, UV[..., 0], UV[..., 1], cv2.INTER_LINEAR)
    def rd(p):
        a = cv2.imread(p) if os.path.exists(p) else None
        return np.full((S_, S_, 3), 255, np.uint8) if a is None else cv2.resize(a, (S_, int(S_ * a.shape[0] / a.shape[1])))
    def lab(a, t):
        a = a.copy(); cv2.putText(a, t, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (20, 20, 200), 2, cv2.LINE_AA); return a
    pad = lambda a: np.vstack([a, np.full((max(0, S_ - a.shape[0]), S_, 3), 255, np.uint8)])[:S_]
    rows = [[lab(cv2.resize(ref, (S_, S_)), 'reference (green: contour, cyan: new margin)'), lab(rd(os.path.join(N, '_work', 'v_old_front.png')), 'P2 base (old)'),
             lab(rd(os.path.join(N, '_work', 'v_new_front.png')), 'P2 eye-fit base (new), our eyeball')],
            [lab(rd(os.path.join(TD, 'pv', 'eye_front_rest.png')), 'new: loop_organs rest'), lab(rd(os.path.join(TD, 'pv', 'eye_front_b05.png')), 'new: blink 0.5'),
             lab(rd(os.path.join(TD, 'pv', 'eye_front_b10.png')), 'new: blink 1.0')],
            [lab(rd(os.path.join(OD, 'pv', 'eye_front_rest.png')), 'old P chain: rest'), lab(rd(os.path.join(TD, 'pv', 'eye_34_rest.png')), 'new: 3/4 rest'),
             lab(rd(os.path.join(TD, 'pv', 'eye_34_b10.png')), 'new: 3/4 blink 1.0')]]
    def hrow(r):
        h = max(c.shape[0] for c in r); return np.hstack([np.vstack([c, np.full((h - c.shape[0], S_, 3), 255, np.uint8)]) for c in r])
    body = np.vstack([hrow(r) for r in rows]); head = np.full((44, body.shape[1], 3), 255, np.uint8)
    cv2.putText(head, TITLE, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.imwrite(OUTJ, np.vstack([head, body]), [cv2.IMWRITE_JPEG_QUALITY, 86])


def coverage_gap(t):
    t = np.sort(np.r_[0, t, 1]); return float(np.diff(t).max())


def ellipse_dist(P, c, ax, ang):
    a = math.radians(ang); R = np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])
    Q = (P - c) @ R.T; r = np.sqrt((Q[:, 0] / ax[0]) ** 2 + (Q[:, 1] / ax[1]) ** 2)
    return np.abs(r - 1) * min(ax)


# ====================================================================== fit (Blender)
def tps2(Xs, Ys, lam):
    """2D thin-plate spline Xs -> Ys (project_texture.py)"""
    n = len(Xs); r = np.linalg.norm(Xs[:, None] - Xs[None], axis=2); K = r * r * np.log(np.maximum(r, 1e-9))
    P_ = np.c_[np.ones(n), Xs]; Lm = np.zeros((n + 3, n + 3)); Lm[:n, :n] = K + lam * np.eye(n); Lm[:n, n:] = P_; Lm[n:, :n] = P_.T
    W_ = np.linalg.solve(Lm, np.r_[Ys, np.zeros((3, 2))])
    def f(Q):
        r = np.linalg.norm(Q[:, None] - Xs[None], axis=2); K = r * r * np.log(np.maximum(r, 1e-9))
        return K @ W_[:n] + W_[n] + Q @ W_[n + 1:]
    return f


class FrontMap:
    """front image <-> head (x, z), project_texture.py's front_uv (similarity x' = s x + tx, y' = -s z + ty, then a
    thin-plate spline in pixels, lam 50, faded into the similarity away from the landmarks), fitted on the NON-EYE
    landmarks only (brows 1-6, nose tip 16, mouth corners 20 / 22, chin 24, lip line 34 / 35): the eye points of the
    head come from the P2 margin we are replacing, MediaPipe's eye points miss cartoon eyes. Inverse by Newton."""
    def __init__(s, LT, mp35):
        ids = [k for k in NONEYE if k in LT and k in mp35]
        src = np.array([[LT[k][0], LT[k][2]] for k in ids], float); dst = np.array([mp35[k] for k in ids], float); s.ids = ids
        M = np.zeros((2 * len(src), 3)); rhs = np.zeros(2 * len(src))
        M[0::2, 0] = src[:, 0]; M[0::2, 1] = 1; rhs[0::2] = dst[:, 0]; M[1::2, 0] = -src[:, 1]; M[1::2, 2] = 1; rhs[1::2] = dst[:, 1]
        (s.s, s.tx, s.ty), *_ = np.linalg.lstsq(M, rhs, rcond=None)
        s.SP = s.sim(src); s.tps = tps2(s.SP, dst, 50.0); s.span = np.ptp(dst[:, 0])
        s.res_sim_mm = np.linalg.norm(s.SP - dst, axis=1) / s.s * MM
        s.res_mm = np.linalg.norm(s.fwd(src) - dst, axis=1) / s.s * MM
    def sim(s, Q): return np.c_[s.s * Q[:, 0] + s.tx, -s.s * Q[:, 1] + s.ty]
    def fwd(s, P):
        P = np.asarray(P, float); Q = s.sim(P[:, [0, 2]] if P.shape[1] == 3 else P); T_ = s.tps(Q)
        dmin = np.min(np.linalg.norm(Q[:, None] - s.SP[None], axis=2), 1)
        w = np.clip(1 - (dmin - 0.15 * s.span) / (0.35 * s.span), 0, 1)[:, None]
        return Q + w * (T_ - Q)
    def inv(s, UV):
        UV = np.asarray(UV, float); X = np.c_[(UV[:, 0] - s.tx) / s.s, -(UV[:, 1] - s.ty) / s.s]; h = 1e-5
        for _ in range(12):
            Fv = s.fwd(X) - UV; Jx = (s.fwd(X + [h, 0]) - s.fwd(X - [h, 0])) / (2 * h); Jz = (s.fwd(X + [0, h]) - s.fwd(X - [0, h])) / (2 * h)
            det = Jx[:, 0] * Jz[:, 1] - Jz[:, 0] * Jx[:, 1]
            dx = (Fv[:, 0] * Jz[:, 1] - Jz[:, 0] * Fv[:, 1]) / det; dz = (Jx[:, 0] * Fv[:, 1] - Fv[:, 0] * Jx[:, 1]) / det
            X = X - np.c_[dx, dz]
            if np.abs(Fv).max() < 1e-3: break
        return X


def inside2(P, poly):
    """points P (n, 2) inside the closed polygon poly (m, 2) (even-odd rule)"""
    P = np.asarray(P, float); A = poly; B = np.roll(poly, -1, 0); x, y = P[:, 0][:, None], P[:, 1][:, None]
    c = ((A[None, :, 1] > y) != (B[None, :, 1] > y)) & (x < (B[None, :, 0] - A[None, :, 0]) * (y - A[None, :, 1]) / (B[None, :, 1] - A[None, :, 1] + 1e-30) + A[None, :, 0])
    return c.sum(1) % 2 == 1


def closed_dist(P, C):
    """distance of points P to the closed polyline C (2D or 3D)"""
    A = C; B = np.roll(C, -1, 0); AB = B - A; ll = np.maximum((AB * AB).sum(1), 1e-18)
    t = np.clip(((P[:, None] - A[None]) * AB[None]).sum(2) / ll[None], 0, 1)
    return np.linalg.norm(P[:, None] - (A[None] + t[..., None] * AB[None]), axis=2).min(1)


def opening_size(up, lo, outer, inner):
    """width = corner to corner; height = largest gap between the lids measured across the corner chord (2D x, z)"""
    ax = inner - outer; w = float(np.linalg.norm(ax)); ax = ax / w; nr = np.array([-ax[1], ax[0]])
    tu, ou = (up - outer) @ ax, (up - outer) @ nr; tl, ol = (lo - outer) @ ax, (lo - outer) @ nr
    tt = np.linspace(0.02 * w, 0.98 * w, 60); su, sl = np.argsort(tu), np.argsort(tl)
    gu = np.interp(tt, tu[su], ou[su]); gl = np.interp(tt, tl[sl], ol[sl])
    return w, float(np.abs(gu - gl).max())


PCOL = {'orig': (0.75, 0.75, 0.77, 1), 'p2_eyes': (0.42, 0.5, 0.95, 1), 'p2_brows': (0.55, 0.3, 0.15, 1), 'p2_lids': (0.15, 0.1, 0.08, 1),
        'p2_mouth': (0.9, 0.35, 0.3, 1), 'eyes': (0.95, 0.95, 0.97, 1)}


def front_render(path, centre, size, res, objs=None, wire=False, film_transparent=False, direction=(0, 1, 0)):
    """orthographic workbench render looking along direction (default +y: the face front), object colours PCOL"""
    import bpy
    from mathutils import Vector
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = res
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_cavity = False; sh.show_object_outline = False
    if not sc.world: sc.world = bpy.data.worlds.new('w')
    sc.world.color = (0.93, 0.93, 0.93); sc.view_settings.view_transform = 'Standard'; sc.render.film_transparent = film_transparent
    co = bpy.data.objects.get('_cam')
    if co is None:
        cam = bpy.data.cameras.new('_cam'); cam.type = 'ORTHO'; cam.clip_end = 20; co = bpy.data.objects.new('_cam', cam); sc.collection.objects.link(co)
    sc.camera = co
    for o in bpy.data.objects:
        if o.type in ('MESH', 'CURVE'):
            show = (o.name in PCOL and o.name != 'noface') if objs is None else (o.name in objs)
            o.hide_render = not show
            if o.type == 'MESH' and o.name in PCOL: o.color = PCOL[o.name]
    d = Vector(direction).normalized(); co.data.ortho_scale = size
    co.location = Vector(tuple(centre)) - d * 3.0; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)


def fit_main(argv):
    """fit <P_dir> <eye_contour.json> <out_dir> [--gap mm] [--sigma mm] [--falloff k] [--qblend w] [--iris-centre p2|image]
    [--arap N] [--recut mm] [--anchor share] [--corner-smooth mm] [--dry]: see the module docstring"""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.kdtree import KDTree
    sys.path.append(HERE)
    from facelib import lids
    PDIR, CJP, OUT = os.path.abspath(argv[0]), argv[1], os.path.abspath(argv[2]); opt = argv[3:]
    GAP = float(opt[opt.index('--gap') + 1]) / MM if '--gap' in opt else 0.00065
    ICEN = opt[opt.index('--iris-centre') + 1] if '--iris-centre' in opt else 'p2'
    KSTR = float(opt[opt.index('--falloff') + 1]) if '--falloff' in opt else 2.5
    PARAM = opt[opt.index('--param') + 1] if '--param' in opt else 'ends'
    ENDS = float(opt[opt.index('--ends') + 1]) if '--ends' in opt else 0.3
    BALL = opt[opt.index('--ball') + 1] if '--ball' in opt else 'fit'
    PRIOR = float(opt[opt.index('--prior') + 1]) if '--prior' in opt else 0.01
    RMAX = float(opt[opt.index('--rmax') + 1]) / MM if '--rmax' in opt else 1.0
    CPRI = opt[opt.index('--centre-prior') + 1] if '--centre-prior' in opt else 'iris'
    PRIOR_XZ = float(opt[opt.index('--prior-xz') + 1]) if '--prior-xz' in opt else PRIOR
    RIMW = float(opt[opt.index('--rim') + 1]) if '--rim' in opt else 0.0
    GAP_FIT, GAP_LO, GAP_HI = 0.0007, 0.0006, 0.00085
    if '--band' in opt:
        GAP_LO, GAP_HI = float(opt[opt.index('--band') + 1]) / MM, float(opt[opt.index('--band') + 2]) / MM; GAP_FIT = (GAP_LO + GAP_HI) / 2
    CAP = '--skin-cap' in opt
    NREL = int(opt[opt.index('--relax') + 1]) if '--relax' in opt else 0
    SIGF = float(opt[opt.index('--sigma') + 1]) / MM if '--sigma' in opt else 0.005
    NARAP = int(opt[opt.index('--arap') + 1]) if '--arap' in opt else 0
    AW = opt[opt.index('--arap-weights') + 1] if '--arap-weights' in opt else 'cotan'
    CSM = float(opt[opt.index('--corner-smooth') + 1]) / MM if '--corner-smooth' in opt else 0.003
    GROW = float(opt[opt.index('--recut') + 1]) / MM if '--recut' in opt else 0.0
    INNER = opt[opt.index('--inner') + 1] if '--inner' in opt else 'full'
    DRY = '--dry' in opt
    os.makedirs(OUT, exist_ok=True); qa = {'ball': BALL, 'param': PARAM, 'ends': ENDS, 'falloff_k': KSTR, 'sigma_mm': SIGF * MM, 'prior': PRIOR}
    bpy.ops.wm.open_mainfile(filepath=os.path.join(PDIR, 'base.blend')); bpy.context.preferences.filepaths.save_version = 0
    ob = bpy.data.objects['orig']; nf = bpy.data.objects.get('noface')
    for o in (ob, nf):
        if o is not None and np.abs(np.array(o.matrix_world) - np.eye(4)).max() > 1e-9: raise SystemExit(o.name + ' has a transform')
    me = ob.data; n = len(me.vertices); X0 = np.empty(n * 3); me.vertices.foreach_get('co', X0); X0 = X0.reshape(-1, 3)
    if nf is not None:
        Xn = np.empty(n * 3); nf.data.vertices.foreach_get('co', Xn)
        if len(nf.data.vertices) != n or np.abs(Xn.reshape(-1, 3) - X0).max() > 1e-9: raise SystemExit('orig and noface differ')
    F = [list(p.vertices) for p in me.polygons]
    LJ = json.load(open(os.path.join(PDIR, 'landmarks.json'))); EM = json.load(open(os.path.join(PDIR, 'eyes_meta.json')))
    LT = {int(k): np.array(v, float) for k, v in LJ.items() if not k.startswith('_')}
    CJ = json.load(open(CJP)); mp35 = {int(k): np.array(v) for k, v in CJ['mp35'].items()}
    # ---- 1. front map; image contour -> head frame, symmetrised
    FM = FrontMap(LT, mp35)
    qa['front_map'] = {'points': FM.ids, 'px_per_mm': round(FM.s / MM, 3), 'similarity_res_mm': np.round(FM.res_sim_mm, 2).tolist(),
                       'tps_res_mm_max': round(float(FM.res_mm.max()), 3), 'contour_method': CJ['method']}
    NQ = 48; tgt = {}
    for s in 'LR':
        e = CJ['eyes'][s]['chosen']; f = np.array([1.0, 1.0]) if s == 'L' else np.array([-1.0, 1.0])
        up = FM.inv(np.array(e['up'])) * f; lo = FM.inv(np.array(e['lo'])) * f
        ic = FM.inv(np.array([e['iris_c']]))[0] * f
        a_ = math.radians(e['iris_ang']); th = np.linspace(0, 2 * np.pi, 72, endpoint=False)
        EP = np.array(e['iris_c']) + np.c_[e['iris_r'][0] * np.cos(th), e['iris_r'][1] * np.sin(th)] @ np.array([[math.cos(a_), math.sin(a_)], [-math.sin(a_), math.cos(a_)]])
        EPm = FM.inv(EP) * f
        tgt[s] = {'up': resample_open(up, NQ), 'lo': resample_open(lo, NQ), 'iris_c': ic, 'iris_rx': float(np.ptp(EPm[:, 0]) / 2), 'iris_rz': float(np.ptp(EPm[:, 1]) / 2)}
    T_up = (tgt['L']['up'] + tgt['R']['up']) / 2; T_lo = (tgt['L']['lo'] + tgt['R']['lo']) / 2
    T_up[0] = T_lo[0] = (T_up[0] + T_lo[0]) / 2; T_up[-1] = T_lo[-1] = (T_up[-1] + T_lo[-1]) / 2
    T_ic = (tgt['L']['iris_c'] + tgt['R']['iris_c']) / 2
    T_irx = (tgt['L']['iris_rx'] + tgt['R']['iris_rx']) / 2; T_irz = (tgt['L']['iris_rz'] + tgt['R']['iris_rz']) / 2
    qa['image_lr_asymmetry_mm'] = {'contour_mean': round(float(np.r_[np.linalg.norm(tgt['L']['up'] - tgt['R']['up'], axis=1), np.linalg.norm(tgt['L']['lo'] - tgt['R']['lo'], axis=1)].mean() * MM), 2),
                                   'iris_centre': round(float(np.linalg.norm(tgt['L']['iris_c'] - tgt['R']['iris_c']) * MM), 2)}
    T_closed = np.r_[T_up, T_lo[::-1][1:-1]]
    # ---- 2. current margin; outer skin vs pocket (flood over faces, both eyes' cycles block)
    part = mirror_part(X0)
    nbr = [[] for _ in range(n)]; E2F = {}
    for fi, f in enumerate(F):
        for k in range(len(f)):
            a_, b_ = f[k], f[(k + 1) % len(f)]; e = (min(a_, b_), max(a_, b_)); E2F.setdefault(e, []).append(fi)
    for (a_, b_) in E2F: nbr[a_].append(b_); nbr[b_].append(a_)
    ekey = lambda a_, b_: (min(a_, b_), max(a_, b_))
    def split(vids):
        vR = [int(part[v]) for v in vids]
        cyc_e = {ekey(c[i], c[(i + 1) % len(c)]) for c in (vids, vR) for i in range(len(c))}
        if not all(e in E2F for e in cyc_e): raise SystemExit('margin_vids is not an edge cycle')
        fadj = [[] for _ in F]
        for e, fs in E2F.items():
            if e in cyc_e or len(fs) != 2: continue
            fadj[fs[0]].append(fs[1]); fadj[fs[1]].append(fs[0])
        e0 = next((e for e in cyc_e if X0[e[0], 0] > 0 and len(E2F[e]) == 2), None)          # None: the margin is a hole
        pocket_f = set()
        if e0 is not None:
            comps = []
            for f0 in E2F[e0]:
                seen = {f0}; st_ = [f0]
                while st_:
                    f = st_.pop()
                    for g in fadj[f]:
                        if g not in seen: seen.add(g); st_.append(g)
                comps.append(seen)
            pocket_f = set() if comps[0] == comps[1] else min(comps, key=len)
            if len(pocket_f) > 0.25 * len(F): raise SystemExit('pocket flood leaks')
        pocket_v = {v for f in pocket_f for v in F[f]} - set(vids) - set(vR)
        outer_v = {v for fi, f in enumerate(F) if fi not in pocket_f for v in f}
        return vR, pocket_f, pocket_v, outer_v
    vids = [int(v) for v in EM['L']['margin_vids']]; vR, pocket_f, pocket_v, outer_v = split(vids)
    # re-cut where the reference opening reaches well outside the P2 margin (front view): there the opening grows over
    # existing skin (P2 canthus folds), so the cut follows existing edges out to the target instead of dragging the
    # margin over the skin. Cheapest closed edge walk that winds once round the target: old margin edges, plus edges of
    # the outer skin in the growth zone (front view: inside the target, outside the old margin, next to a growth arc);
    # cost = length * (1 + (front distance to the target / 0.6 mm)^2)
    recut = {'growth_arcs_pts': 0}
    O2 = X0[vids][:, [0, 2]]; outd = np.where(inside2(T_closed, O2), 0.0, closed_dist(T_closed, O2))
    grow = outd > GROW
    if grow.any() and GROW > 0:
        recut['growth_arcs_pts'] = int(grow.sum()); recut['growth_max_mm'] = round(float(outd.max() * MM), 2)
        L2 = np.array([v for v in outer_v if X0[v, 0] > 1e-6 and v not in set(vids)], int); P2_ = X0[L2][:, [0, 2]]
        dT = closed_dist(P2_, T_closed); A_ = T_closed; jn = np.argmin(np.linalg.norm(P2_[:, None] - A_[None], axis=2), 1)
        zone = set(L2[(inside2(P2_, T_closed) | (dT < 0.0003)) & ~inside2(P2_, O2) & (outd[jn] > 0.5 * GROW) & (dT < 0.0025)].tolist())
        nodes = zone | set(vids); cen2 = T_closed.mean(0)
        th = {v: math.atan2(X0[v, 2] - cen2[1], X0[v, 0] - cen2[0]) for v in nodes}
        # seam: half-line from the centre through the old margin vertex farthest from any growth
        far_i = int(np.argmax(closed_dist(O2, T_closed[grow]) if grow.sum() > 1 else np.linalg.norm(O2 - T_closed[grow][0], axis=1)))
        th0 = th[vids[far_i]]; rel = lambda v: (th[v] - th0) % (2 * np.pi)
        medge = {ekey(vids[i], vids[(i + 1) % len(vids)]) for i in range(len(vids))}
        adj = {}
        for (a_, b_), fs in E2F.items():
            if a_ not in nodes or b_ not in nodes: continue
            if (a_, b_) not in medge and a_ not in zone and b_ not in zone: continue
            mid = (X0[a_] + X0[b_])[[0, 2]] / 2; d_ = float(closed_dist(mid[None], T_closed)[0])
            w_ = float(np.linalg.norm(X0[a_] - X0[b_])) * (1 + (d_ / 0.0006) ** 2)
            ra, rb = rel(a_), rel(b_); cross = abs(ra - rb) > np.pi          # the edge crosses the seam
            for l in (0, 1):
                adj.setdefault((a_, l), []).append(((b_, l ^ int(cross)), w_)); adj.setdefault((b_, l), []).append(((a_, l ^ int(cross)), w_))
        import heapq
        src = vids[far_i]; dist = {(src, 0): 0.0}; prev = {}; h = [(0.0, (src, 0))]
        while h:
            d_, u = heapq.heappop(h)
            if u == (src, 1): break
            if d_ > dist.get(u, 1e18): continue
            for v_, w_ in adj.get(u, ()):
                if d_ + w_ < dist.get(v_, 1e18): dist[v_] = d_ + w_; prev[v_] = u; heapq.heappush(h, (d_ + w_, v_))
        if (src, 1) in prev:
            p_ = [(src, 1)]
            while p_[-1] != (src, 0): p_.append(prev[p_[-1]])
            cyc = [v for v, _ in p_[::-1]][:-1]
            if len(set(cyc)) == len(cyc) and len(cyc) >= 6:
                try:
                    vR2, pf2, pv2, ov2 = split(cyc)
                    if pocket_f and not pocket_f <= pf2: raise SystemExit('re-cut does not contain the old pocket')
                    recut.update(verts_old=len(vids), verts_new=len(cyc), new_skin_verts_on_cut=len(set(cyc) - set(vids)), cut_faces_added=len(pf2) - len(pocket_f))
                    vids, vR, pocket_f, pocket_v, outer_v = cyc, vR2, pf2, pv2, ov2
                except SystemExit as ex:
                    recut['rejected'] = str(ex)
            else: recut['rejected'] = 'walk not simple'
        else: recut['rejected'] = 'no closed walk'
    qa['recut'] = recut
    # dents of the edge path (it runs round two or three sides of one outer-skin face) are cut short: the face goes to
    # the pocket side. Placed on a smooth curve, a dent's middle vertices would squash that face flat
    fset = {frozenset(f): fi for fi, f in enumerate(F)}; short = 0
    if pocket_f:
        changed = True
        while changed:
            changed = False; m_ = len(vids)
            for i in range(m_):
                for k in (2, 3):
                    seq = [vids[(i + j) % m_] for j in range(k + 1)]
                    fi = fset.get(frozenset(seq))
                    if fi is not None and len(F[fi]) == k + 1 and fi not in pocket_f and ekey(seq[0], seq[-1]) in E2F:
                        drop = set(seq[1:-1]); vids = [v for v in vids if v not in drop]; short += 1; changed = True; break
                if changed: break
            if changed: vR, pocket_f, pocket_v, outer_v = split(vids)
    qa['margin_path'] = {'verts_before': len(EM['L']['margin_vids']), 'verts': len(vids), 'dents_cut': short, 'pocket_faces': len(pocket_f)}
    Pm = X0[vids]
    C0 = np.array(EM['L']['C']); r0 = float(EM['L']['r']); A0 = np.array(EM['L']['A']); A0 /= np.linalg.norm(A0)
    Am = (Pm - C0) @ A0; ia, ib = int(np.argmin(Am)), int(np.argmax(Am))
    io, ii = (ia, ib) if abs(Pm[ia, 0]) > abs(Pm[ib, 0]) else (ib, ia)                # outer = farther from the midline
    nv = len(vids); p1 = [(io + k) % nv for k in range((ii - io) % nv + 1)]; p2 = [(io - k) % nv for k in range((io - ii) % nv + 1)]
    upi, loi = (p1, p2) if Pm[p1, 2].mean() > Pm[p2, 2].mean() else (p2, p1)
    old_xz = Pm[:, [0, 2]]
    # inner corner ('--inner p2'): MediaPipe's inner corner is the canthus tip past the caruncle. Where P2 modelled the
    # caruncle as a skin fold (f06), pushing the margin into that fold folds it over; then both target lids end at the
    # P2 corner's position along the eye axis and run into the P2 corner point over their last 25 % (smoothstep):
    # pointed corner, the fold stays skin (the caruncle). Default 'full': the reference corner.
    T_up_ref, T_lo_ref, T_closed_ref = T_up.copy(), T_lo.copy(), T_closed.copy(); anch = {'mode': INNER}
    axv = (T_up[-1] - T_up[0]) / np.linalg.norm(T_up[-1] - T_up[0]); anch['tip_beyond_p2_corner_mm'] = round(float((T_up[-1] - old_xz[ii]) @ axv) * MM, 2)
    if INNER in ('p2', 'axis'):
        K = old_xz[ii]; tc = float((K - T_up[0]) @ axv); out_ = []
        for Tc in (T_up, T_lo):
            t_ = (Tc - T_up[0]) @ axv; k_ = int(np.argmax(t_ >= tc)) if (t_ >= tc).any() else len(Tc) - 1
            if 0 < k_ < len(Tc):
                f_ = (tc - t_[k_ - 1]) / max(t_[k_] - t_[k_ - 1], 1e-12); e_ = Tc[k_ - 1] + f_ * (Tc[k_] - Tc[k_ - 1]); Tt = np.vstack([Tc[:k_], e_])
            else: Tt = Tc.copy()
            out_.append(resample_open(Tt, len(Tc)))
        if INNER == 'axis': K = (out_[0][-1] + out_[1][-1]) / 2            # pointed corner on the reference's own midline
        for j_, Tt in enumerate(out_):
            q_ = arclen(Tt) / arclen(Tt)[-1]; w_ = np.clip((q_ - 0.75) / 0.25, 0, 1); w_ = w_ * w_ * (3 - 2 * w_); out_[j_] = Tt + w_[:, None] * (K - Tt[-1])
        T_up, T_lo = out_; T_closed = np.r_[T_up, T_lo[::-1][1:-1]]
    qa['inner_corner_anchor'] = anch
    # ---- 3. eyeball: P2 fit, centre (x, z) on the reference iris
    PE = bpy.data.objects.get('p2_eyes'); p2i = {}
    if PE is not None:
        XP = np.array([tuple(v.co) for v in PE.data.vertices]); XP = XP[XP[:, 0] > 0]
        dP = np.linalg.norm(XP - C0, axis=1) - r0; fr = (XP - C0)[:, 1] < 0
        bul = fr & (dP > 0.35 * dP[fr].max()); apex_dir = ((XP[bul] - C0) / np.linalg.norm(XP[bul] - C0, axis=1, keepdims=True)).mean(0)
        apex_dir /= np.linalg.norm(apex_dir); apex = C0 + apex_dir * (r0 + dP[bul].mean())
        p2i = {'cornea_bulge_mm': round(float(dP[fr].max() * MM), 2), 'apex_xz_mm': (apex[[0, 2]] * MM).round(2).tolist(),
               'apex_dir': apex_dir.round(4).tolist(), 'C_xz_mm': (C0[[0, 2]] * MM).round(2).tolist(),
               'image_iris_minus_apex_xz_mm': ((T_ic - apex[[0, 2]]) * MM).round(2).tolist(),
               'image_iris_minus_C_xz_mm': ((T_ic - C0[[0, 2]]) * MM).round(2).tolist()}
    qa['p2_eyeball'] = p2i; qa['iris_image_xz_mm'] = (T_ic * MM).round(2).tolist(); qa['iris_image_radii_mm'] = [round(T_irx * MM, 2), round(T_irz * MM, 2)]
    # ---- comparisons (front view)
    w_old, h_old = opening_size(Pm[upi][:, [0, 2]], Pm[loi][:, [0, 2]], Pm[io, [0, 2]], Pm[ii, [0, 2]])
    w_new, h_new = opening_size(T_up_ref, T_lo_ref, T_up_ref[0], T_up_ref[-1])
    d_old_to_t = closed_dist(old_xz, T_closed_ref); d_t_to_old = closed_dist(T_closed_ref, old_xz)
    qa['front_before'] = {'margin_to_reference_mean_mm': round(float(d_old_to_t.mean() * MM), 2), 'margin_to_reference_max_mm': round(float(d_old_to_t.max() * MM), 2),
                          'reference_to_margin_max_mm': round(float(d_t_to_old.max() * MM), 2),
                          'width_mm': [round(w_old * MM, 2), round(w_new * MM, 2)], 'height_mm': [round(h_old * MM, 2), round(h_new * MM, 2)],
                          'note': 'width / height: [current P2 margin, reference contour]',
                          'corner_shift_mm': {'outer': round(float(np.linalg.norm(Pm[io, [0, 2]] - T_up_ref[0]) * MM), 2), 'inner': round(float(np.linalg.norm(Pm[ii, [0, 2]] - T_up_ref[-1]) * MM), 2)},
                          'centroid_shift_xz_mm': ((T_closed_ref.mean(0) - old_xz.mean(0)) * MM).round(2).tolist()}
    gm = np.linalg.norm(Pm - C0, axis=1) - r0
    qa['margin_gap_to_p2_sphere_mm'] = {'min': round(float(gm.min() * MM), 2), 'median': round(float(np.median(gm) * MM), 2), 'max': round(float(gm.max() * MM), 2)}
    uvj = {'target': FM.fwd(T_closed).tolist(), 'target_mirror': FM.fwd(T_closed * [-1, 1]).tolist(), 'reference': FM.fwd(T_closed_ref).tolist(), 'old': FM.fwd(old_xz).tolist(), 'old_mirror': FM.fwd(old_xz * [-1, 1]).tolist(),
           'iris_c': FM.fwd(T_ic[None])[0].tolist(), 'img': CJ['image'], 'contour_img': {s: CJ['eyes'][s]['chosen'] for s in 'LR'}}
    uvj['map'] = {'LT': {str(k): v.tolist() for k, v in LT.items()}, 'mp35': CJ['mp35']}
    if DRY:
        # front render of the eye region (head grey, brows / lids / eyeball pieces coloured) for a warped overlay
        cen = T_closed.mean(0); size = 2 * (abs(cen[0]) + 1.2 * float(np.ptp(T_closed[:, 0])))
        pth = os.path.join(OUT, 'front_render.png'); front_render(pth, (0.0, 0.0, cen[1]), size, 1600)
        uvj['render'] = {'path': pth, 'centre_xz': [0.0, float(cen[1])], 'size': size}
        json.dump(qa, open(os.path.join(OUT, 'eye_fit_qa.json'), 'w'), indent=1); json.dump(uvj, open(os.path.join(OUT, 'eye_fit_uv.json'), 'w'))
        print('EYEFIT_DRY', json.dumps({k: qa[k] for k in ('front_before', 'p2_eyeball', 'margin_gap_to_p2_sphere_mm', 'image_lr_asymmetry_mm', 'iris_image_radii_mm')}))
        return
    # ---- 4. in-plane margin targets: each vertex goes to the target lid at its nearest point (pure across-lid move);
    # only near the corners (the end ENDS share of each lid path) it slides along the lid so the corners land on the
    # target corners ('--param arc': same share of arc length everywhere)
    arc01 = lambda P: arclen(P) / max(arclen(P)[-1], 1e-12)
    def at(Tc, q):
        sT = arc01(Tc); return np.c_[np.interp(q, sT, Tc[:, 0]), np.interp(q, sT, Tc[:, 1])]
    ss_ = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
    def qpar(Pp, Tc):
        sa = arc01(Pp)
        if PARAM == 'arc': return sa
        sT = arc01(Tc); A_ = Tc[:-1]; B_ = Tc[1:]; AB = B_ - A_; ll = np.maximum((AB * AB).sum(1), 1e-18)
        t = np.clip(((Pp[:, None] - A_[None]) * AB[None]).sum(2) / ll[None], 0, 1)
        dd = np.linalg.norm(Pp[:, None] - (A_[None] + t[..., None] * AB[None]), axis=2); j = dd.argmin(1)
        qn = np.maximum.accumulate(sT[j] + t[np.arange(len(Pp)), j] * (sT[j + 1] - sT[j]))
        q = qn - qn[0] * (1 - ss_(sa / ENDS)) + (1 - qn[-1]) * ss_((sa - 1 + ENDS) / ENDS)
        q = np.clip(np.maximum.accumulate(q), 0, 1); q[0], q[-1] = 0.0, 1.0
        u_ = np.linspace(0, 1, len(q)); dmin = 0.4 / max(len(q) - 1, 1)          # no two margin vertices closer than 40 %
        for lam in np.linspace(0.15, 1.0, 18):                                  # of the even spacing: blend toward even
            qq = (1 - lam) * q + lam * u_
            if np.diff(qq).min() >= dmin * min(1.0, lam / 0.5) or lam >= 1.0: return qq
        return u_
    Txz = np.zeros((nv, 2)); Txz[upi] = at(T_up, qpar(Pm[upi][:, [0, 2]], T_up)); Txz[loi] = at(T_lo, qpar(Pm[loi][:, [0, 2]], T_lo))
    # ---- 3b. our eyeball. 'fit' (default): the margin keeps its own depth (y) at its new (x, z); the sphere is fitted
    # to these points at GAP_FIT (0.7 mm) under them, pulled toward the P2 eyeball sphere (C0, r0) by priors (centre and
    # radius, weight PRIOR per point), radius capped so the untouched skin round the eye keeps loop_organs' floors
    # (0.45 mm within 3 mm of the margin, 0.3 mm elsewhere); then only margin vertices outside the band GAP_LO..GAP_HI
    # (0.6..0.85 mm) above the sphere move in depth, onto the band. 'p2': P2 sphere, margin lifted onto r + 0.65 mm.
    Pin = np.c_[Txz[:, 0], Pm[:, 1], Txz[:, 1]]
    if BALL == 'fit':
        Cp = np.array([T_ic[0], C0[1], T_ic[1]]) if CPRI == 'iris' else C0.copy()   # prior centre: behind the reference iris
        Cc, Rc = Cp.copy(), r0 + GAP_FIT; npt = len(Pin)
        for _ in range(30):
            d_ = Pin - Cc; L_ = np.linalg.norm(d_, axis=1); res = L_ - Rc
            J = np.c_[-d_ / L_[:, None], -np.ones(npt)]
            wc = np.sqrt(np.array([PRIOR_XZ, PRIOR, PRIOR_XZ]) * npt)                 # centre (x, z) toward the iris axis
            Jp = np.r_[J, np.c_[np.diag(wc), np.zeros(3)], [np.r_[np.zeros(3), np.sqrt(PRIOR * npt)]]]
            rp = np.r_[res, wc * (Cc - Cp), [np.sqrt(PRIOR * npt) * (Rc - r0 - GAP_FIT)]]
            dx = np.linalg.lstsq(Jp, -rp, rcond=None)[0]; Cc = Cc + dx[:3]; Rc = Rc + dx[3]
            if np.abs(dx).max() < 1e-9: break
        C = Cc; r = Rc - GAP_FIT
        nearS = np.array([v for v in outer_v if X0[v, 0] > 1e-6 and v not in set(vids)], int)
        dS = np.linalg.norm(X0[nearS] - C, axis=1); fw = (X0[nearS] - C)[:, 1] < 0; kS = fw & (dS < r + 0.004)
        dM = np.min(np.linalg.norm(X0[nearS][kS][:, None] - Pin[None], axis=2), 1)
        floorS = np.where(dM < 0.003, 0.00047, 0.00032); r_cap = float((dS[kS] - floorS).min()) if kS.any() else r
        qa['sphere_fit'] = {'r_fit_mm': round(r * MM, 3), 'r_cap_by_skin_mm': round(r_cap * MM, 3), 'rms_mm': round(float(np.sqrt(np.mean((np.linalg.norm(Pin - C, axis=1) - Rc) ** 2))) * MM, 3)}
        if CAP: r = min(r, r_cap)
        gap0 = np.linalg.norm(Pin - C, axis=1) - r; gt = np.clip(gap0, GAP_LO, GAP_HI)
        def lift_g(xz, R_):
            h2 = R_ ** 2 - (xz[:, 0] - C[0]) ** 2 - (xz[:, 1] - C[2]) ** 2
            return np.c_[xz[:, 0], C[1] - np.sqrt(np.maximum(h2, 0)), xz[:, 1]], h2
        T3, h2 = lift_g(Txz, r + gt)
        keep = np.abs(gt - gap0) < 1e-12; T3[keep] = Pin[keep]
        if (h2[~keep] < (0.15 * r) ** 2).any(): raise SystemExit('target margin reaches the eyeball silhouette (front lift ill-posed)')
    else:
        C, r = C0.copy(), r0
        h2 = (r + GAP) ** 2 - (Txz[:, 0] - C[0]) ** 2 - (Txz[:, 1] - C[2]) ** 2
        T3 = np.c_[Txz[:, 0], C[1] - np.sqrt(np.maximum(h2, 0)), Txz[:, 1]]
        if (h2 < (0.15 * r) ** 2).any(): raise SystemExit('target margin reaches the eyeball silhouette (front lift ill-posed)')
    def lift(xz, R_):
        h2_ = R_ ** 2 - (xz[:, 0] - C[0]) ** 2 - (xz[:, 1] - C[2]) ** 2
        return np.c_[xz[:, 0], C[1] - np.sqrt(np.maximum(h2_, 0)), xz[:, 1]], h2_
    qa['eyeball_before_after'] = {'C_mm': [(C0 * MM).round(2).tolist(), (C * MM).round(2).tolist()], 'r_mm': [round(r0 * MM, 2), round(r * MM, 2)],
                                  'front_point_mm': [((C0 - [0, r0, 0]) * MM).round(2).tolist(), ((C - [0, r, 0]) * MM).round(2).tolist()]}
    dmv = T3 - Pm; inpl = np.linalg.norm(dmv[:, [0, 2]], axis=1)
    tang = np.zeros(nv)                                                      # in-plane part along the margin
    for i in range(nv):
        tg = Pm[(i + 1) % nv, [0, 2]] - Pm[i - 1, [0, 2]]; tg /= max(np.linalg.norm(tg), 1e-12); tang[i] = abs(dmv[i, [0, 2]] @ tg)
    qa['margin_move_split_mm'] = {'in_plane_mean': round(float(inpl.mean() * MM), 2), 'in_plane_max': round(float(inpl.max() * MM), 2),
                                  'across_lid_mean': round(float(np.sqrt(np.maximum(inpl ** 2 - tang ** 2, 0)).mean() * MM), 2),
                                  'along_lid_mean': round(float(tang.mean() * MM), 2), 'along_lid_max': round(float(tang.max() * MM), 2),
                                  'depth_mean': round(float(np.abs(dmv[:, 1]).mean() * MM), 2), 'depth_max': round(float(np.abs(dmv[:, 1]).max() * MM), 2),
                                  'depth_moved_verts': int((np.abs(dmv[:, 1]) > 1e-6).sum()),
                                  'note': 'in-plane = front view (x, z); along-lid = corner slides; depth = y'}
    # ---- 5. geodesic distance and BFS rings from the margin over the outer skin
    mset = set(vids)
    def dijkstra(src, allowed, lim):
        import heapq
        dist = {v: 0.0 for v in src}; h = [(0.0, v) for v in src]
        while h:
            d_, v = heapq.heappop(h)
            if d_ > dist[v] or d_ > lim: continue
            for w_ in nbr[v]:
                if w_ not in allowed: continue
                nd = d_ + float(np.linalg.norm(X0[v] - X0[w_]))
                if nd < dist.get(w_, 1e18): dist[w_] = nd; heapq.heappush(h, (nd, w_))
        return dist
    left = {v for v in range(n) if X0[v, 0] > 1e-6}
    g_out = dijkstra(vids, (outer_v & left) | mset, 0.03); g_in = dijkstra(vids, (pocket_v & left) | mset, 0.03)
    ring = {v: 0 for v in vids}; fr_ = list(vids)
    for k in range(1, 9):
        nx_ = []
        for v in fr_:
            for w_ in nbr[v]:
                if w_ in outer_v and w_ in left and w_ not in ring: ring[w_] = k; nx_.append(w_)
        fr_ = nx_
    el = np.array([np.linalg.norm(X0[a_] - X0[b_]) for a_ in vids for b_ in nbr[a_] if b_ in outer_v and b_ not in mset])
    Lmed = float(np.median(el))
    # ---- 6. displacement field: rotation about C + radial change, from the margin outward with falloff
    d0 = Pm - C; rho0 = np.linalg.norm(d0, axis=1); dt = T3 - C; rho1 = np.linalg.norm(dt, axis=1)
    u0, u1 = d0 / rho0[:, None], dt / rho1[:, None]
    ax_ = np.cross(u0, u1); sn = np.linalg.norm(ax_, axis=1); cs = (u0 * u1).sum(1); ang = np.arctan2(sn, cs)
    OM = np.where(sn[:, None] > 1e-12, ax_ / np.maximum(sn, 1e-12)[:, None] * ang[:, None], 0.0); DR = rho1 - rho0
    Dmag = np.linalg.norm(T3 - Pm, axis=1)
    lab_ = np.array(['lo'] * nv, dtype=object); lab_[upi] = 'up'; lab_[io] = 'OUT'; lab_[ii] = 'IN'
    qa['margin_moves_dbg'] = [[int(i), lab_[i], round(float(np.linalg.norm(T3[i, [0, 2]] - Pm[i, [0, 2]]) * MM), 2), round(float((T3[i, 1] - Pm[i, 1]) * MM), 2),
                               round(float((np.linalg.norm(Pm[i] - C) - r) * MM), 2)] for i in range(nv)]
    s_m = arclen(np.vstack([Pm, Pm[:1]])); Ltot = s_m[-1]; s_m = s_m[:-1]
    def psmooth(vals, sig):                                       # Gaussian along the closed margin (arc length)
        dd = np.abs(s_m[:, None] - s_m[None]); dd = np.minimum(dd, Ltot - dd); W_ = np.exp(-0.5 * (dd / sig) ** 2)
        return (W_ / W_.sum(1, keepdims=True)) @ vals
    OMs, DRs, Dms = psmooth(OM, SIGF), psmooth(DR, SIGF), psmooth(Dmag, SIGF)
    Rmin = 2.5 * Lmed
    Rfall = np.minimum(np.maximum(Rmin, KSTR * Dms), max(RMAX, Rmin))
    def field_at(P):
        """nearest point on the (old) margin polyline: index pair and blend -> smoothed rotation, radial change, falloff radius"""
        A_ = Pm; B_ = np.roll(Pm, -1, 0); AB = B_ - A_; ll = np.maximum((AB * AB).sum(1), 1e-18)
        t = np.clip(((P[:, None] - A_[None]) * AB[None]).sum(2) / ll[None], 0, 1)
        dd = np.linalg.norm(P[:, None] - (A_[None] + t[..., None] * AB[None]), axis=2); j = dd.argmin(1); tt = t[np.arange(len(P)), j][:, None]
        j2 = (j + 1) % nv
        return OMs[j] * (1 - tt) + OMs[j2] * tt, DRs[j] * (1 - tt[:, 0]) + DRs[j2] * tt[:, 0], Rfall[j] * (1 - tt[:, 0]) + Rfall[j2] * tt[:, 0]
    def rotate(Vv, om):
        th = np.linalg.norm(om, axis=1); k_ = om / np.maximum(th, 1e-15)[:, None]; c_, s_ = np.cos(th)[:, None], np.sin(th)[:, None]
        return Vv * c_ + np.cross(k_, Vv) * s_ + k_ * (k_ * Vv).sum(1, keepdims=True) * (1 - c_)
    X1 = X0.copy(); X1[vids] = T3
    smooth01 = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
    for dist_, mult, kind in ((g_out, 1.0, 'outer'), (g_in, 2.0, 'pocket')):
        ids = np.array([v for v in dist_ if v not in mset], int)
        if not len(ids): continue
        om, dr, Rf = field_at(X0[ids]); g = np.array([dist_[v] for v in ids])
        w = 1 - smooth01(g / (mult * Rf))
        if kind == 'pocket': w = w * smooth01(X0[ids, 0] / 0.004)              # pockets joined behind the nose: fade to x = 0
        k_ = w > 1e-4; ids, om, dr, w = ids[k_], om[k_], dr[k_], w[k_]
        d_ = X0[ids] - C; rho = np.linalg.norm(d_, axis=1)
        X1[ids] = C + rotate(d_, om * w[:, None]) * ((rho + w * dr) / rho)[:, None]
    # ARAP: the field above is the start; as-rigid-as-possible over the moved region (left side, x > 0), margin vertices on
    # their targets, the ring of unmoved vertices around fixed, cotangent weights (polygons fanned into triangles):
    # every neighbourhood keeps its shape and turns as a whole (the lid rim and canthus folds move as units)
    REG = sorted(v for v in range(n) if X0[v, 0] > 1e-6 and v not in mset and np.linalg.norm(X1[v] - X0[v]) > 1e-7)
    if NARAP and REG:
        regs = set(REG); bnd = sorted({w_ for v in REG for w_ in nbr[v]} - regs - mset)
        W_ = {}
        for f in F:
            if not any(v in regs for v in f): continue
            for k in range(1, len(f) - 1):
                tri = (f[0], f[k], f[k + 1])
                for j in range(3):
                    a_, b_, o_ = tri[j], tri[(j + 1) % 3], tri[(j + 2) % 3]
                    u_, v_ = X0[a_] - X0[o_], X0[b_] - X0[o_]; ct = float(u_ @ v_) / max(float(np.linalg.norm(np.cross(u_, v_))), 1e-18)
                    e = ekey(a_, b_); W_[e] = W_.get(e, 0.0) + 0.5 * ct
        wm = float(np.median([abs(x) for x in W_.values()]))
        for e in W_: W_[e] = 1.0 if AW == 'uniform' else float(np.clip(W_[e], 0.1 * wm, 4.0 * wm))
        nbW = {}
        for (a_, b_), w_ in W_.items(): nbW.setdefault(a_, []).append((b_, w_)); nbW.setdefault(b_, []).append((a_, w_))
        idx = {v: i for i, v in enumerate(REG)}; nf_ = len(REG); Lm = np.zeros((nf_, nf_))
        for v in REG:
            for u_, w_ in nbW[v]:
                Lm[idx[v], idx[v]] += w_
                if u_ in idx: Lm[idx[v], idx[u_]] -= w_
        Lc = np.linalg.cholesky(Lm)
        rot_set = REG + sorted(mset) + bnd
        COL = np.array([v for v in REG if v in outer_v], int); FLR = np.array([0.0005 if ring.get(v, 99) <= 3 else 0.00035 for v in COL])
        for _ in range(NARAP):
            Rr = {}
            for v in rot_set:
                Sm = np.zeros((3, 3))
                for u_, w_ in nbW.get(v, []): Sm += w_ * np.outer(X0[v] - X0[u_], X1[v] - X1[u_])
                U_, _s, Vt = np.linalg.svd(Sm); Rv = Vt.T @ U_.T
                if np.linalg.det(Rv) < 0: Vt[2] *= -1; Rv = Vt.T @ U_.T
                Rr[v] = Rv
            rhs = np.zeros((nf_, 3))
            for v in REG:
                for u_, w_ in nbW[v]:
                    Ru = Rr.get(u_, np.eye(3)); rhs[idx[v]] += 0.5 * w_ * ((Rr[v] + Ru) @ (X0[v] - X0[u_]))
                    if u_ not in idx: rhs[idx[v]] += w_ * X1[u_]
            X1[REG] = np.linalg.solve(Lc.T, np.linalg.solve(Lc, rhs))
            # the eyeball: outer skin in front of the centre stays outside the sphere by the clearance floor
            dC = X1[COL] - C; rC = np.linalg.norm(dC, axis=1); inn = (rC < r + FLR) & (dC[:, 1] < 0)
            X1[COL[inn]] = C + dC[inn] / rC[inn, None] * (r + FLR[inn])[:, None]
        qa['arap'] = {'iterations': NARAP, 'free_verts': nf_, 'fixed_ring': len(bnd)}
    # untangle: faces of the outer skin (left) whose normal turned > 78 deg from the original: their vertices and one
    # ring around (margin fixed) go to the mean of their neighbours, then back to their distance from C; repeated
    # until none is left (tight canthus folds where a corner slides into them)
    # the rim next to the margin keeps its shape where the margin move changes fast along it (corners): ring 1 takes the
    # mean move of its margin neighbours (weight RIMW), ring 2 the mean of its ring-1 neighbours (half that)
    if RIMW > 0:
        Dm = {v: T3[k] - Pm[k] for k, v in enumerate(vids)}; Dl = {}
        r1 = [v for v in ring if ring[v] == 1]; r2 = [v for v in ring if ring[v] == 2]
        for v in r1:
            nb_ = [Dm[w_] for w_ in nbr[v] if w_ in Dm]
            if nb_: Dl[v] = np.mean(nb_, 0)
        for v in r2:
            nb_ = [Dl[w_] for w_ in nbr[v] if w_ in Dl]
            if nb_: Dl[v] = np.mean(nb_, 0)
        for v, d_ in Dl.items():
            w_ = RIMW if ring[v] == 1 else 0.5 * RIMW; X1[v] = (1 - w_) * X1[v] + w_ * (X0[v] + d_)
    def fn_(Xv, fids):
        P_ = [Xv[F[fi]] for fi in fids]
        return np.array([sum(np.cross(p[k], p[(k + 1) % len(p)]) for k in range(len(p))) for p in P_])
    untangled = set()
    def untangle():
        chk = [fi for fi, f in enumerate(F) if fi not in pocket_f and all(X0[v, 0] > 1e-6 for v in f) and any(np.linalg.norm(X1[v] - X0[v]) > 1e-7 for v in f)]
        N0c = fn_(X0, chk); N0c /= np.linalg.norm(N0c, axis=1, keepdims=True); rounds = 0
        for rounds in range(80):
            N1c = fn_(X1, chk); N1c /= np.maximum(np.linalg.norm(N1c, axis=1, keepdims=True), 1e-18)
            bad = [fi for fi, d_ in zip(chk, (N0c * N1c).sum(1)) if d_ < 0.2]
            if not bad: break
            vs = {v for fi in bad for v in F[fi]}; vs |= {w_ for v in vs for w_ in nbr[v] if w_ in outer_v}
            vs = [v for v in vs if v not in mset and X0[v, 0] > 1e-6]; untangled.update(vs)
            rt = np.maximum(np.linalg.norm(X1[vs] - C, axis=1), r + np.array([0.00047 if ring.get(v, 99) <= 3 else 0.00032 for v in vs]))
            avg = np.array([X1[nbr[v]].mean(0) for v in vs])
            X1[vs] = C + (avg - C) / np.linalg.norm(avg - C, axis=1)[:, None] * rt[:, None]
        return rounds
    rounds = untangle()
    qa['untangle'] = {'rounds': rounds, 'verts': len(untangled)}
    # corners: the lid rim rings bunch where a corner slid along the margin; the outer skin within CSM of either corner
    # (geodesic, margin fixed) is smoothed (Laplacian, 8 half steps) and kept off the eyeball
    if CSM > 0:
        for cv_ in (vids[io], vids[ii]):
            gd = dijkstra([cv_], (outer_v & left) | {cv_}, CSM)
            sv = [v for v in gd if v not in mset and gd[v] < CSM]
            if not sv: continue
            wv = (1 - smooth01(np.array([gd[v] for v in sv]) / CSM))[:, None]
            for _ in range(8):
                avg = np.array([X1[nbr[v]].mean(0) for v in sv]); X1[sv] = X1[sv] + 0.5 * wv * (avg - X1[sv])
            dC = X1[sv] - C; rC = np.linalg.norm(dC, axis=1); fl = np.array([0.0005 if ring.get(v, 99) <= 3 else 0.00035 for v in sv])
            inn = (rC < r + fl) & (dC[:, 1] < 0); idx_ = np.array(sv)[inn]
            X1[idx_] = C + dC[inn] / rC[inn, None] * (r + fl[inn])[:, None]
    # clearance floor of the outer skin near the eyeball (loop_organs: margin 0.6, 3 rings 0.45, any 0.3 mm)
    near = np.array([v for v in outer_v & left if v not in mset and np.linalg.norm(X1[v] - C) < r + 0.004 and (X1[v] - C)[1] < 0], int)
    floor = np.array([0.00047 if ring.get(v, 99) <= 3 else 0.00032 for v in near])
    gap_ = np.linalg.norm(X1[near] - C, axis=1) - r; bad = gap_ < floor; pushed = int(bad.sum())
    if bad.any():
        d_ = X1[near[bad]] - C; X1[near[bad]] = C + d_ / np.linalg.norm(d_, axis=1)[:, None] * (r + floor[bad])[:, None]
    rounds2 = untangle(); qa['untangle']['rounds_after_smoothing'] = rounds2; qa['untangle']['verts'] = len(untangled)
    # mirror: the right side is the exact mirror image of the left
    movedL = np.where((np.linalg.norm(X1 - X0, axis=1) > 0) & (X0[:, 0] > 1e-6))[0]
    if (np.abs(X0[movedL, 0]) < 1e-6).any(): raise SystemExit('a centre-line vertex would move')
    X1[part[movedL]] = X1[movedL] * [-1, 1, 1]
    if os.environ.get('EYEFIT_DBG'):
        np.savez(os.environ['EYEFIT_DBG'], X0=X0, X1=X1, vids=np.array(vids), T3=T3, Tc=T_closed, C=C,
                 Fv=np.array([v for f in F for v in f]), Fn=np.array([len(f) for f in F]), pocket=np.array(sorted(pocket_f)))
    # ---- 7. checks
    mv = np.linalg.norm(X1 - X0, axis=1); moved = np.where(mv > 1e-6)[0]; movedLs = moved[X0[moved, 0] > 0]
    def fnormals(Xv, fids):
        out = []
        for fi in fids:
            f = F[fi]; P_ = Xv[f]; nn = np.zeros(3)
            for k in range(len(f)): nn += np.cross(P_[k], P_[(k + 1) % len(f)])
            out.append(nn / max(np.linalg.norm(nn), 1e-18))
        return np.array(out)
    vset = set(moved.tolist()); faces_m = [fi for fi, f in enumerate(F) if any(v in vset for v in f)]
    n0, n1 = fnormals(X0, faces_m), fnormals(X1, faces_m); dots = (n0 * n1).sum(1)
    pf_sets = {frozenset(F[fi]) for fi in pocket_f}                          # faces whose mirror image is a pocket face
    mirror_pf = {fi for fi, f in enumerate(F) if frozenset(int(part[v]) for v in f) in pf_sets}
    isp = np.array([(fi in pocket_f) or (fi in mirror_pf) for fi in faces_m])
    def elen_ratio(fids):
        rr = []
        for fi in fids:
            f = F[fi]
            for k in range(len(f)):
                a_, b_ = f[k], f[(k + 1) % len(f)]; l0 = np.linalg.norm(X0[a_] - X0[b_]); l1 = np.linalg.norm(X1[a_] - X1[b_]); rr.append(l1 / max(l0, 1e-12))
        return np.array(rr) if rr else np.ones(1)
    out_f = [fi for fi, p_ in zip(faces_m, isp) if not p_]; er = elen_ratio(out_f)
    qa['flip_dbg'] = [{'x_mm': round(float(X0[F[fi]][:, 0].mean() * MM), 1), 'in_pocket': fi in pocket_f, 'margin_verts': sum(v in mset for v in F[fi]),
                       'all_left': bool(all(X0[v, 0] > 1e-6 for v in F[fi])), 'verts': F[fi]} for fi, d_, p_ in zip(faces_m, dots, isp) if d_ < 0 and not p_]
    gm_new = np.linalg.norm(X1[vids] - C, axis=1) - r
    nearN = np.array([v for v in outer_v & left if v not in mset and np.linalg.norm(X1[v] - C) < r + 0.004 and (X1[v] - C)[1] < 0], int)
    gapN = np.linalg.norm(X1[nearN] - C, axis=1) - r
    gr3 = np.array([gg for v, gg in zip(nearN, gapN) if ring.get(v, 99) <= 3])
    allS = np.array([v for v in outer_v if X0[v, 0] > 1e-6 and v not in mset], int)
    gapAll = np.linalg.norm(X1[allS] - C, axis=1) - r                      # whole sphere, any skin (not only the front)
    ringsL = [ring.get(int(v), -1) for v in movedLs if int(v) in outer_v and mv[v] > 5e-5]
    qa['edit'] = {'moved_verts_total': int(len(moved)), 'moved_verts_left': int(len(movedLs)),
                  'moved_outer_skin_left': int(sum(1 for v in movedLs if v in outer_v and v not in mset)), 'moved_pocket_left': int(sum(1 for v in movedLs if v in pocket_v)),
                  'margin_verts': nv, 'max_move_mm': round(float(mv.max() * MM), 3), 'margin_move_mm': {'mean': round(float(Dmag.mean() * MM), 2), 'max': round(float(Dmag.max() * MM), 2)},
                  'outer_skin_move_mm_max': round(float(max([mv[v] for v in movedLs if v in outer_v and v not in mset] or [0]) * MM), 3),
                  'rings_moved_over_0.05mm': int(max(ringsL)) if ringsL else 0, 'falloff_R_mm': {'min': round(float(Rfall.min() * MM), 2), 'max': round(float(Rfall.max() * MM), 2)},
                  'edge_med_mm': round(Lmed * MM, 3), 'flipped_faces_outer': int(((dots < 0) & ~isp).sum()), 'flipped_faces_pocket': int(((dots < 0) & isp).sum()),
                  'normal_turn_deg_max_outer': round(float(np.degrees(np.arccos(np.clip(dots[~isp], -1, 1))).max()) if (~isp).any() else 0.0, 1),
                  'edge_stretch_outer': {'min': round(float(er.min()), 3), 'max': round(float(er.max()), 3)},
                  'margin_gap_mm': {'min': round(float(gm_new.min() * MM), 3), 'max': round(float(gm_new.max() * MM), 3)},
                  'skin_clearance_mm': {'near_min': round(float(gapN.min() * MM), 3) if len(gapN) else None, 'rings1_3_min': round(float(gr3.min() * MM), 3) if len(gr3) else None,
                                        'pushed_to_floor': pushed, 'whole_sphere_any_skin_min': round(float(gapAll.min() * MM), 3)},
                  'pocket_faces_left': len(pocket_f), 'mirror_gap_max_mm': None}
    fl_ = [fi for fi, d_, p_ in zip(faces_m, dots, isp) if d_ < 0.3 and not p_ and X0[F[fi][0], 0] > 0]
    qa['edit']['turned_faces_left_dbg'] = [{'rings': [ring.get(v, -1) for v in F[fi]], 'near_corner_mm': round(float(min(np.linalg.norm(X0[F[fi]].mean(0) - Pm[io]), np.linalg.norm(X0[F[fi]].mean(0) - Pm[ii])) * MM), 1),
                                            'which': 'outer' if np.linalg.norm(X0[F[fi]].mean(0) - Pm[io]) < np.linalg.norm(X0[F[fi]].mean(0) - Pm[ii]) else 'inner',
                                            'dot': round(float(d_), 2), 'z_rel_mm': round(float((X0[F[fi]].mean(0)[2] - Pm[:, 2].mean()) * MM), 1)} for fi, d_ in zip(faces_m, dots) if fi in fl_][:12]
    kd = KDTree(n)
    for i, p in enumerate(X1): kd.insert(Vector(tuple(p)), i)
    kd.balance(); qa['edit']['mirror_gap_max_mm'] = round(float(max(kd.find(Vector((-p[0], p[1], p[2])))[2] for p in X1[moved]) * MM), 6)
    # front comparison after
    new_xz = X1[vids][:, [0, 2]]; d_new = closed_dist(new_xz, T_closed_ref); d_t_new = closed_dist(T_closed_ref, new_xz)
    w_n, h_n = opening_size(X1[vids][upi][:, [0, 2]], X1[vids][loi][:, [0, 2]], X1[vids][io, [0, 2]], X1[vids][ii, [0, 2]])
    dtg = closed_dist(new_xz, T_closed)
    qa['front_after'] = {'margin_to_reference_mean_mm': round(float(d_new.mean() * MM), 3), 'margin_to_reference_max_mm': round(float(d_new.max() * MM), 3),
                         'reference_to_margin_max_mm': round(float(d_t_new.max() * MM), 3), 'width_mm': round(w_n * MM, 2), 'height_mm': round(h_n * MM, 2),
                         'margin_to_target_max_mm': round(float(dtg.max() * MM), 3),
                         'note': 'target = reference contour, with the inner-corner anchor when used (see inner_corner_anchor)'}
    # 3D: margin gap to the new sphere before (P2 margin) / after, and the 3D move of the margin
    g_b = np.linalg.norm(Pm - C, axis=1) - r; g_a = np.linalg.norm(X1[vids] - C, axis=1) - r; m3 = np.linalg.norm(X1[vids] - Pm, axis=1)
    qa['3d'] = {'margin_gap_to_new_sphere_before_mm': [round(float(g_b.min() * MM), 2), round(float(g_b.max() * MM), 2)],
                'margin_gap_to_new_sphere_after_mm': [round(float(g_a.min() * MM), 3), round(float(g_a.max() * MM), 3)],
                'margin_move_3d_mm': {'mean': round(float(m3.mean() * MM), 2), 'max': round(float(m3.max() * MM), 2)}}
    # ---- 8. eyes_meta, landmarks, rig points
    Pn = X1[vids]; up_p = Pn[upi]; lo_p = Pn[loi]
    def rs48(P): return resample_open(P, 48)
    up48, lo48 = rs48(up_p), rs48(lo_p); raw = np.r_[up48, lo48[::-1][1:-1]]
    A1 = Pn[ii] - Pn[io]; A1 /= np.linalg.norm(A1)
    MXv = np.array([-1.0, 1, 1]); EO = {}
    ip, _ = lift(T_ic[None], r); iris_dir = (ip[0] - C) / np.linalg.norm(ip[0] - C); irx, irz = T_irx, T_irz      # rest gaze: through the reference iris
    ideg = [math.degrees(math.asin(min(irx / r, 1))), math.degrees(math.asin(min(irz / r, 1)))]
    for s, f in (('L', np.ones(3)), ('R', MXv)):
        EO[s] = {'C': (C * f).tolist(), 'r': float(r), 'A': (A1 * f).tolist(), 'up_path': (up48 * f).tolist(), 'lo_path': (lo48 * f).tolist(),
                 'raw': (raw * f).tolist(), 'margin_kind': 'path' if pocket_f else 'hole', 'margin_vids': vids if s == 'L' else vR,
                 'corner_vids': [vids[io], vids[ii]] if s == 'L' else [int(part[vids[io]]), int(part[vids[ii]])],
                 'iris_dir': (iris_dir * f).tolist(), 'iris_centre': ((C + iris_dir * r) * f).tolist(), 'iris_radius_deg': round(float(np.mean(ideg)), 3),
                 'iris_radii_deg': [round(ideg[0], 3), round(ideg[1], 3)], 'iris_radii_mm': [round(irx * MM, 3), round(irz * MM, 3)],
                 'eye_fit': {'source': 'eye_fit_ref.py', 'contour_method': CJ['method'], 'margin_gap_band_mm': [GAP_LO * MM, GAP_HI * MM], 'eyeball': 'ours (UV sphere at C, r; p2_eyes removed)',
                             'iris_note': 'iris_dir = rest gaze (unit, from C); iris_centre = front point of the sphere on that axis; radii: horizontal, vertical (front view of the reference iris, mm and degrees of arc on the sphere)'}}
    LN = dict(LJ)
    def arcmid(P):
        s_ = arclen(P); return np.array([np.interp(s_[-1] / 2, s_, P[:, j]) for j in range(3)])
    newL = {13: Pn[io], 11: Pn[ii], 12: arcmid(up_p), 14: arcmid(lo_p)}
    for k, p in newL.items(): LN[str(k)] = p.tolist()
    for a_, b_ in ((7, 13), (9, 11), (8, 12), (10, 14)): LN[str(a_)] = (newL[b_] * MXv).tolist()
    LN['_eye_fit'] = 'eye points 7-14 from the fitted margin (eye_fit_ref.py)'
    RP = json.load(open(os.path.join(PDIR, 'rig_points.json'))); J = RP['joints']
    bvh1 = BVHTree.FromPolygons([tuple(p) for p in X1], F); rp_moves = {}
    for nm in list(J):
        h_, t_ = np.array(J[nm][0]), np.array(J[nm][1])
        if nm in ('eye.L', 'eye.R'):
            f = np.ones(3) if nm.endswith('L') else MXv; d_ = t_ - h_; h2_ = C * f; J[nm] = [h2_.tolist(), (h2_ + d_).tolist()]; rp_moves[nm] = round(float(np.linalg.norm(h2_ - h_) * MM), 2)
        elif nm.startswith('lid.'):
            hh = np.array(bvh1.find_nearest(Vector(tuple(h_)))[0]); tt = np.array(bvh1.find_nearest(Vector(tuple(t_)))[0])
            J[nm] = [hh.tolist(), tt.tolist()]; rp_moves[nm] = round(float(np.linalg.norm(hh - h_) * MM), 2)
    RP['info']['eye_fit'] = {'moved_mm': rp_moves, 'note': 'eye joints on the new eyeball centre; lid joints snapped onto the fitted skin (rigify_fit re-places lid joints on the rings)'}
    # ---- 9. write
    for o in (ob, nf):
        if o is None: continue
        o.data.vertices.foreach_set('co', X1.ravel()); o.data.update()
    if PE is not None: bpy.data.objects.remove(PE, do_unlink=True)
    pl = bpy.data.objects.get('p2_lids')
    if pl is not None: pl.hide_render = True; pl.hide_viewport = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'base.blend'), compress=True)
    json.dump(LN, open(os.path.join(OUT, 'landmarks.json'), 'w'), indent=1)
    json.dump(EO, open(os.path.join(OUT, 'eyes_meta.json'), 'w'))
    json.dump(RP, open(os.path.join(OUT, 'rig_points.json'), 'w'), indent=1)
    uvj['new'] = FM.fwd(new_xz).tolist(); uvj['new_mirror'] = FM.fwd(new_xz * [-1, 1]).tolist(); uvj['iris_c_mirror'] = FM.fwd((T_ic * [-1, 1])[None])[0].tolist()
    os.makedirs(os.path.join(OUT, '_work'), exist_ok=True); json.dump(uvj, open(os.path.join(OUT, '_work', 'eye_fit_uv.json'), 'w'))
    json.dump(qa, open(os.path.join(OUT, 'eye_fit_qa.json'), 'w'), indent=1)
    print('EYEFIT', json.dumps({k: qa[k] for k in ('front_before', 'front_after', '3d', 'edit', 'eyeball_before_after')}))


def views_main(argv):
    """views <base.blend> <eyes_meta.json> <out_prefix> <cx> <cz> <size> [--ball] [--target target.json]
    grey + wire close-ups of the left eye (front, 3/4) of 'orig' (or 'face'): margin (magenta), eyeball: p2_eyes if present
    (blue), else with --ball our sphere at eyes_meta C, r (white); --target: a closed 3D curve (green)"""
    import bpy, bmesh
    from mathutils import Vector
    BL, EMJ, PRE = argv[0], argv[1], argv[2]; cx, cz, size = map(float, argv[3:6]); opt = argv[6:]
    bpy.ops.wm.open_mainfile(filepath=BL)
    EM = json.load(open(EMJ)); sk = bpy.data.objects.get('face') or bpy.data.objects.get('orig')
    keep = {sk.name, 'p2_eyes', 'eyes'}
    for o in list(bpy.data.objects):
        if o.type in ('MESH', 'CURVE') and o.name not in keep: o.hide_render = True
    PCOL[sk.name] = (0.74, 0.74, 0.76, 1)
    if '--ball' in opt and bpy.data.objects.get('p2_eyes') is None and bpy.data.objects.get('eyes') is None:
        bm = bmesh.new()
        for s_ in 'LR':
            b2 = bmesh.new(); bmesh.ops.create_uvsphere(b2, u_segments=48, v_segments=24, radius=float(EM[s_]['r']))
            bmesh.ops.translate(b2, verts=b2.verts, vec=Vector(tuple(EM[s_]['C']))); tm = bpy.data.meshes.new('t'); b2.to_mesh(tm); b2.free(); bm.from_mesh(tm)
        m_ = bpy.data.meshes.new('eyes'); bm.to_mesh(m_); bm.free()
        for p in m_.polygons: p.use_smooth = True
        eo = bpy.data.objects.new('eyes', m_); bpy.context.scene.collection.objects.link(eo)
    if '--iris' in opt and 'iris_dir' in EM['L']:                       # iris disc on the sphere along iris_dir (gaze check)
        PCOL['iris'] = (0.25, 0.13, 0.05, 1); bm = bmesh.new()
        for s_ in 'LR':
            e_ = EM[s_]; C_ = Vector(tuple(e_['C'])); d_ = Vector(tuple(e_['iris_dir'])).normalized(); rr = float(e_['r'])
            th = math.radians(float(e_['iris_radius_deg'])); b2 = bmesh.new()             # spherical cap 0.25 mm above the ball
            bmesh.ops.create_uvsphere(b2, u_segments=64, v_segments=64, radius=rr + 0.00025)
            bmesh.ops.delete(b2, geom=[v for v in b2.verts if v.co.normalized().z < math.cos(th)], context='VERTS')
            rq = Vector((0, 0, 1)).rotation_difference(d_).to_matrix().to_4x4(); bmesh.ops.transform(b2, matrix=rq, verts=b2.verts)
            bmesh.ops.translate(b2, verts=b2.verts, vec=C_); tm = bpy.data.meshes.new('t'); b2.to_mesh(tm); b2.free(); bm.from_mesh(tm)
        m_ = bpy.data.meshes.new('iris'); bm.to_mesh(m_); bm.free(); io_ = bpy.data.objects.new('iris', m_); bpy.context.scene.collection.objects.link(io_); keep.add('iris')
    objs = [o.name for o in bpy.data.objects if o.name in keep]
    for o in bpy.data.objects:
        if o.name in objs and o.name in PCOL: o.color = PCOL[o.name]
    if sk.name not in PCOL: sk.color = (0.74, 0.74, 0.76, 1)
    w = sk.copy(); w.data = sk.data; w.name = 'wire'; bpy.context.scene.collection.objects.link(w)
    for m in list(w.modifiers): w.modifiers.remove(m)
    md = w.modifiers.new('wf', 'WIREFRAME'); md.use_replace = True; md.thickness = size / 900 * 1.1; w.color = (0.08, 0.08, 0.1, 1); objs.append('wire')
    X = np.array([tuple(v.co) for v in sk.data.vertices]); mv = EM['L'].get('margin_vids') or []
    def curve(P, col, rad, nm):
        cu = bpy.data.curves.new(nm, 'CURVE'); cu.dimensions = '3D'; sp = cu.splines.new('POLY'); sp.points.add(len(P) - 1)
        sp.points.foreach_set('co', np.hstack([P, np.ones((len(P), 1))]).ravel().astype(np.float32)); sp.use_cyclic_u = True
        cu.bevel_depth = rad; cu.bevel_resolution = 2; o = bpy.data.objects.new(nm, cu); o.color = col; bpy.context.scene.collection.objects.link(o); objs.append(nm)
    if mv and sk.name == 'orig': curve(X[mv], (0.9, 0.1, 0.8, 1), size / 700, 'margin')
    if '--target' in opt:
        TP = np.array(json.load(open(opt[opt.index('--target') + 1]))); curve(TP, (0.1, 0.8, 0.2, 1), size / 1000, 'target')
    views = (('front', (0, 1, 0)), ('34', (-0.5, 0.86, 0))) if '--both' not in opt else (('front', (0, 1, 0)), ('34', (-0.6, 0.8, 0)), ('34r', (0.6, 0.8, 0)))
    for nm_, d in views:
        C_ = np.array([cx, float(np.array(EM['L']['C'])[1]), cz])
        front_render(PRE + '_%s.png' % nm_, tuple(C_), size, 900, objs=set(objs), direction=d)


def mirror_part(X):
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    kd = KDTree(len(X))
    for i, p in enumerate(X): kd.insert(Vector(tuple(p)), i)
    kd.balance(); part = np.empty(len(X), int); gap = 0.0
    for i, p in enumerate(X):
        _, j, d = kd.find(Vector((-p[0], p[1], p[2]))); part[i] = j; gap = max(gap, d)
    if gap > 1e-6: raise SystemExit('base is not exactly mirror-symmetric (%.3g mm)' % (gap * MM))
    return part


if __name__ == '__main__':
    if 'bpy' in sys.modules:
        a = sys.argv[sys.argv.index('--') + 1:]
        if a[0] == 'fit': fit_main(a[1:])
        elif a[0] == 'views': views_main(a[1:])
    else:
        a = sys.argv[1:]
        if a and a[0] == 'detect': detect_main(a[1:])
        elif a and a[0] == 'overlay': overlay_main(a[1:])
        elif a and a[0] == 'sheet': sheet_main(a[1:])
