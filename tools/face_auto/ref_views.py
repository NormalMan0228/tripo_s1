"""Reference views <-> 3D for the image-texture bakers (bake_ref_texture.py, eye_iris_texture.py). Plain numpy,
runs in .tools/art-venv (no bpy). The mapping is the one project_texture.py uses (kept identical on purpose):
  front  MediaPipe on 01_front.png <-> the head's own landmarks: similarity + 2D thin-plate spline from (x, z) to
         image pixels; the spline is trusted near the landmarks and fades into the similarity away from them
  left / right  silhouette fit (head top + most forward point = nose tip give scale and offset)
  back   front scale, centred on the silhouette
plus: background masks (flood fill from the border through smooth colour), MediaPipe eye / lip polygons and the
inverse of the front map, and a triangle rasteriser (z-buffer per view, barycentric raster in UV space).
"""
import os, json, subprocess, tempfile
import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MP_PY = os.path.join(ROOT, '.tools', 'landmark-venv', 'Scripts', 'python.exe')
MP_MODEL = os.path.join(ROOT, '.tools', 'landmark-models', 'face_landmarker.task')
MP_DETECT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mp_detect.py')
MP = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 8: 159, 9: 133, 10: 145,
      11: 362, 12: 386, 13: 263, 14: 374, 16: 1, 20: 61, 22: 291, 24: 152, 34: 13, 35: 14}
# MediaPipe contours: eye openings (subject right = image left first) and lips
MP_EYE = {'R': [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
          'L': [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]}
MP_IRIS = {'R': [468, 469, 470, 471, 472], 'L': [473, 474, 475, 476, 477]}     # centre first (image-left eye = 468)
MP_LIP_IN = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191]
MP_LIP_OUT = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
MP_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149,
           150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
MP_BROW = {'R': [70, 63, 105, 66, 107, 55, 65, 52, 53, 46], 'L': [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]}
DIRS = {'front': np.array([0, -1, 0.]), 'left': np.array([1, 0, 0.]), 'right': np.array([-1, 0, 0.]), 'back': np.array([0, 1, 0.])}
FILES = (('front', '01_front.png'), ('left', '02_left.png'), ('back', '03_back.png'), ('right', '04_right.png'))


def load_rgb(path):
    return np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0


def save_rgb(path, a, alpha=None):
    a8 = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    if alpha is not None: a8 = np.dstack([a8, (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)])
    Image.fromarray(a8).save(path)


def srgb_to_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def mp_detect(img, cache):
    if not os.path.exists(cache):
        subprocess.run([MP_PY, '-I', MP_DETECT, img, MP_MODEL, cache], check=True, capture_output=True)
    return json.load(open(cache))


def sample(im, uv):
    """bilinear sample, uv in pixels (N, 2)"""
    H, W = im.shape[:2]
    u = np.clip(uv[:, 0] - 0.5, 0, W - 1.001); v = np.clip(uv[:, 1] - 0.5, 0, H - 1.001)
    u0, v0 = np.floor(u).astype(np.int64), np.floor(v).astype(np.int64)
    fu, fv = (u - u0)[:, None], (v - v0)[:, None]
    return (im[v0, u0] * (1 - fu) * (1 - fv) + im[v0, u0 + 1] * fu * (1 - fv) +
            im[v0 + 1, u0] * (1 - fu) * fv + im[v0 + 1, u0 + 1] * fu * fv)


def bg_mask(im):
    """background = flood fill from the image border through smooth colour + the figure's edge band + bright
    neutral grey (backdrop glow). Returns (mask, stride) on a ~256 px copy (as project_texture)."""
    st_ = max(1, im.shape[1] // 256); a_ = im[::st_, ::st_]
    m = np.zeros(a_.shape[:2], bool); m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = True
    m &= np.abs(a_ - np.median(a_[0], 0)).max(2) < 0.25
    for _ in range(600):
        g = m.copy()
        for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
            nb = np.roll(m, sh, axis=ax); diff = np.abs(a_ - np.roll(a_, sh, axis=ax)).max(2)
            g |= nb & (diff < 0.02)
        if (g == m).all(): break
        m = g
    for _ in range(6):
        m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    near = m.copy()                                      # bright neutral grey (backdrop glow, rim light) counts only
    for _ in range(10):                                  # next to the backdrop: a grey shirt is not background
        near = near | np.roll(near, 1, 0) | np.roll(near, -1, 0) | np.roll(near, 1, 1) | np.roll(near, -1, 1)
    mx_, mn_ = a_.max(2), a_.min(2)
    m |= ((mx_ - mn_) / np.maximum(mx_, 1e-6) < 0.06) & (mx_ > 0.5) & near
    return m, st_


def tps2(Xs, Ys, lam):
    n = len(Xs); r = np.linalg.norm(Xs[:, None] - Xs[None], axis=2); K = r * r * np.log(np.maximum(r, 1e-9))
    P_ = np.c_[np.ones(n), Xs]; L = np.zeros((n + 3, n + 3)); L[:n, :n] = K + lam * np.eye(n); L[:n, n:] = P_; L[n:, :n] = P_.T
    W_ = np.linalg.solve(L, np.r_[Ys, np.zeros((3, 2))])
    def f(Q):
        out = np.empty((len(Q), 2))
        for s in range(0, len(Q), 200000):
            q = Q[s:s + 200000]; r = np.linalg.norm(q[:, None] - Xs[None], axis=2); K = r * r * np.log(np.maximum(r, 1e-9))
            out[s:s + 200000] = K @ W_[:n] + W_[n] + q @ W_[n + 1:]
        return out
    return f


def point_in_poly(pts, poly):
    """even-odd rule, pts (N, 2), poly (M, 2)"""
    x, y = pts[:, 0], pts[:, 1]; ins = np.zeros(len(pts), bool); j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        c = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / np.where(yj - yi == 0, 1e-12, yj - yi) + xi)
        ins ^= c; j = i
    return ins


def eye_margins(V, eye_ring):
    """lid margin ring (|eye_ring| == max - 2, the visible opening edge) per eye as (x, z); L = the +x eye"""
    Km = int(np.abs(eye_ring).max()) - 2; spos = np.sign(np.median(V[eye_ring > 0, 0])); out = {}
    for sg in (1, -1):
        m = (np.abs(eye_ring) == Km) & (np.sign(eye_ring) == sg)
        out['L' if sg * spos > 0 else 'R'] = V[m][:, [0, 2]] if m.sum() >= 8 else None
    return out


class Views:
    def __init__(self, ref_dir, LT, X, cache_dir, front_only=False):
        self.LT = LT; self.X = X; self.qa = {}
        self.imgs = {k: load_rgb(os.path.join(ref_dir, f)) for k, f in FILES
                     if k == 'front' or (not front_only and os.path.exists(os.path.join(ref_dir, f)))}
        self.H, self.W = self.imgs['front'].shape[:2]
        os.makedirs(cache_dir, exist_ok=True)
        mp = mp_detect(os.path.join(ref_dir, '01_front.png'), os.path.join(cache_dir, 'mp_front.json'))
        self.mp = np.array(mp) * [self.W, self.H] if mp else None
        ids = [k for k in MP if k in LT]
        src = np.array([[LT[k][0], LT[k][2]] for k in ids]); dst = self.mp[[MP[k] for k in ids]]
        M = np.zeros((2 * len(src), 3)); rhs = np.zeros(2 * len(src))
        M[0::2, 0] = src[:, 0]; M[0::2, 1] = 1; rhs[0::2] = dst[:, 0]
        M[1::2, 0] = -src[:, 1]; M[1::2, 2] = 1; rhs[1::2] = dst[:, 1]
        (s_, tx, ty), *_ = np.linalg.lstsq(M, rhs, rcond=None)
        self.s_ = s_
        self.simf = lambda P: np.c_[s_ * P[:, 0] + tx, -s_ * P[:, 1] + ty]
        self.tps = tps2(self.simf(src), dst, lam=50.0)
        self.SP = self.simf(src); self.span_ = np.ptp(dst[:, 0])
        self._pairs = (ids, src, dst)
        self.qa['front'] = {'points': len(ids), 'similarity_residual_px': round(float(np.linalg.norm(self.simf(src) - dst, axis=1).mean()), 1),
                            'scale_px_per_mm': round(float(s_ / 1000), 2)}
        self.uvf = {'front': self.front_uv}
        if 'left' in self.imgs:
            self.uvf['left'], sL = self.side_fit('left', -1); self.qa.setdefault('side_scale_vs_front', {})['left'] = round(float(sL / s_), 3)
        if 'right' in self.imgs:
            self.uvf['right'], sR = self.side_fit('right', +1); self.qa.setdefault('side_scale_vs_front', {})['right'] = round(float(sR / s_), 3)
        if 'back' in self.imgs:
            mb = self.mask(self.imgs['back']); rb = np.nonzero(mb.any(1))[0]; cb = np.nonzero(mb[rb.min() + int(0.15 * self.H)])[0]
            uc = (cb.min() + cb.max()) / 2; ztop = X[:, 2].max(); r0 = rb.min()
            self.uvf['back'] = lambda P: np.c_[uc - s_ * P[:, 0], r0 + (ztop - P[:, 2]) * s_]
        self._bg = {}

    def fit_eye_margins(self, margins):
        """refit the front spline with the lid margins: margins = {'L'|'R': (n, 2) mesh margin (x, z)}; each
        MediaPipe eye contour point is paired with the margin point at the same angle around the opening
        (angles normalised by the opening's width / height, so corners meet corners). The eye landmarks 7-14
        are dropped (the contour replaces them). Returns the mean move of the contour points in pixels."""
        ids, src, dst = self._pairs
        keep = [i for i, k in enumerate(ids) if k not in (7, 8, 9, 10, 11, 12, 13, 14)]
        S2, D2 = [src[keep]], [dst[keep]]
        for s_, M in margins.items():
            if M is None or len(M) < 8: continue
            C = self.mp[MP_EYE[s_]]; cc = C.mean(0); ce = np.ptp(C, 0) / 2
            pc = np.c_[(C[:, 0] - cc[0]) / ce[0], -(C[:, 1] - cc[1]) / ce[1]]       # image v down -> z up
            mc = (M.min(0) + M.max(0)) / 2; me = np.ptp(M, 0) / 2
            am = np.arctan2((M[:, 1] - mc[1]) / me[1], (M[:, 0] - mc[0]) / me[0]); o_ = np.argsort(am)
            am, Mo = am[o_], M[o_]
            ai = np.arctan2(pc[:, 1], pc[:, 0])
            mx = np.interp(ai, np.r_[am - 2 * np.pi, am, am + 2 * np.pi], np.tile(Mo[:, 0], 3))
            mz = np.interp(ai, np.r_[am - 2 * np.pi, am, am + 2 * np.pi], np.tile(Mo[:, 1], 3))
            S2.append(np.c_[mx, mz]); D2.append(C)
        S2, D2 = np.concatenate(S2), np.concatenate(D2)
        before = self.front_uv(S2[len(keep):]) if len(S2) > len(keep) else np.zeros((0, 2))
        self.tps = tps2(self.simf(S2), D2, lam=50.0); self.SP = self.simf(S2)
        mv = float(np.linalg.norm(before - D2[len(keep):], axis=1).mean()) if len(before) else 0.0
        self.qa['eye_margin_fit'] = {'pairs': int(len(S2) - len(keep)), 'contour_vs_margin_px_before': round(mv, 1)}
        return mv

    def front_uv(self, P):
        Q = self.simf(P[:, [0, 2]] if P.shape[1] == 3 else P); T_ = self.tps(Q)
        dmin = np.full(len(Q), np.inf)
        for k in range(len(self.SP)): dmin = np.minimum(dmin, np.linalg.norm(Q - self.SP[k], axis=1))
        w = np.clip(1 - (dmin - 0.15 * self.span_) / (0.35 * self.span_), 0, 1)[:, None]
        return Q + w * (T_ - Q)

    def front_inv(self, uv, iters=30):
        """image pixels -> (x, z) on the head (Newton with a numeric Jacobian)"""
        uv = np.atleast_2d(uv).astype(float)
        s_ = self.s_; Q0 = self.simf(np.zeros((1, 2)))[0]
        xz = np.c_[(uv[:, 0] - Q0[0]) / s_, -(uv[:, 1] - Q0[1]) / s_]
        h = 1e-5
        for _ in range(iters):
            f0 = self.front_uv(xz) - uv
            fx = (self.front_uv(xz + [h, 0]) - uv - f0) / h; fz = (self.front_uv(xz + [0, h]) - uv - f0) / h
            J = np.stack([fx, fz], 2)
            xz = xz - np.linalg.solve(J, f0[:, :, None])[:, :, 0]
            if np.abs(f0).max() < 1e-3: break
        return xz

    @staticmethod
    def mask(im):
        bg = np.median(np.r_[im[:8].reshape(-1, 3), im[:, :8].reshape(-1, 3)], 0)
        return np.abs(im - bg).max(2) > 0.06

    def side_fit(self, name, sign):
        LT, X, H = self.LT, self.X, self.H
        m = self.mask(self.imgs[name]); rows = np.nonzero(m.any(1))[0]; vtop = rows.min()
        z_top = X[:, 2].max(); vn_est = vtop + (z_top - LT[16][2]) * self.s_
        band = [r for r in range(int(vn_est - 0.05 * H), int(vn_est + 0.05 * H)) if 0 <= r < H and m[r].any()]
        cols = [(np.nonzero(m[r])[0].min() if sign < 0 else np.nonzero(m[r])[0].max(), r) for r in band]
        u_n, v_n = min(cols) if sign < 0 else max(cols)
        s2 = (v_n - vtop) / (z_top - LT[16][2])
        return (lambda P: np.c_[u_n + (1 if sign < 0 else -1) * s2 * (P[:, 1] - LT[16][1]), v_n - s2 * (P[:, 2] - LT[16][2])]), s2

    def bg(self, name):
        if name not in self._bg: self._bg[name] = bg_mask(self.imgs[name])
        return self._bg[name]

    def is_bg(self, name, uv):
        m, st = self.bg(name)
        bu = np.clip((uv[:, 0] / st).astype(int), 0, m.shape[1] - 1); bv = np.clip((uv[:, 1] / st).astype(int), 0, m.shape[0] - 1)
        return m[bv, bu]

    def bg_soft(self, name, uv):
        """background share 0..1, bilinear on the (slightly blurred) low-res mask: no blocky stair steps"""
        if ('soft', name) not in self._bg:
            import cv2
            m, st = self.bg(name); self._bg[('soft', name)] = (cv2.GaussianBlur(m.astype(np.float32), (0, 0), 0.7), st)
        m, st = self._bg[('soft', name)]
        return sample(m[:, :, None], uv / st)[:, 0]

    def depth(self, name, P):
        return -(P @ DIRS[name])                                  # larger = farther from that camera

    def poly(self, ids):
        return self.mp[ids] if self.mp is not None else None


# ------------------------------------------------------------------ rasterisers
def raster_depth(P2, D, H, W, step=1):
    """z-buffer of triangles: P2 (m, 3, 2) pixel coords, D (m, 3) depth. Returns (H//step, W//step) min depth."""
    Hs, Ws = (H + step - 1) // step, (W + step - 1) // step
    Z = np.full((Hs, Ws), np.inf, np.float32)
    P2 = P2 / step
    x0 = np.floor(P2[:, :, 0].min(1)).astype(int); x1 = np.ceil(P2[:, :, 0].max(1)).astype(int)
    y0 = np.floor(P2[:, :, 1].min(1)).astype(int); y1 = np.ceil(P2[:, :, 1].max(1)).astype(int)
    for t in range(len(P2)):
        a0, a1 = max(x0[t], 0), min(x1[t], Ws - 1); b0, b1 = max(y0[t], 0), min(y1[t], Hs - 1)
        if a0 > a1 or b0 > b1: continue
        (ax, ay), (bx, by), (cx, cy) = P2[t]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        xs, ys = np.meshgrid(np.arange(a0, a1 + 1) + 0.5, np.arange(b0, b1 + 1) + 0.5)
        l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        l2 = 1 - l0 - l1
        ins = (l0 >= -1e-3) & (l1 >= -1e-3) & (l2 >= -1e-3)
        if not ins.any(): continue
        d = l0 * D[t, 0] + l1 * D[t, 1] + l2 * D[t, 2]
        sub = Z[b0:b1 + 1, a0:a1 + 1]
        np.minimum(sub, np.where(ins, d, np.inf), out=sub)
    return Z


def raster_uv(TUV, S):
    """texels (centres) covered by uv triangles. Returns flat texel index, triangle id, barycentrics (n, 3)."""
    P2 = np.c_[TUV[:, :, 0].reshape(-1) * S, (1 - TUV[:, :, 1].reshape(-1)) * S].reshape(-1, 3, 2)
    x0 = np.floor(P2[:, :, 0].min(1)).astype(int); x1 = np.ceil(P2[:, :, 0].max(1)).astype(int)
    y0 = np.floor(P2[:, :, 1].min(1)).astype(int); y1 = np.ceil(P2[:, :, 1].max(1)).astype(int)
    owner = np.full(S * S, -1, np.int32)
    out_i, out_t, out_b = [], [], []
    for t in range(len(P2)):
        a0, a1 = max(x0[t], 0), min(x1[t], S - 1); b0, b1 = max(y0[t], 0), min(y1[t], S - 1)
        if a0 > a1 or b0 > b1: continue
        (ax, ay), (bx, by), (cx, cy) = P2[t]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-14: continue
        xs, ys = np.meshgrid(np.arange(a0, a1 + 1) + 0.5, np.arange(b0, b1 + 1) + 0.5)
        l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        l2 = 1 - l0 - l1
        ins = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not ins.any(): continue
        idx = (ys[ins].astype(int)) * S + xs[ins].astype(int)
        new = owner[idx] < 0
        if not new.any(): continue
        idx = idx[new]; owner[idx] = t
        out_i.append(idx); out_t.append(np.full(len(idx), t, np.int32))
        out_b.append(np.c_[l0[ins][new], l1[ins][new], l2[ins][new]].astype(np.float32))
    if not out_i: return np.zeros(0, int), np.zeros(0, np.int32), np.zeros((0, 3), np.float32)
    return np.concatenate(out_i), np.concatenate(out_t), np.concatenate(out_b)


def dilate_fill(img, mask, iters):
    """push island colours outward (texture padding); img (S, S, 3) float, mask bool (filled texels)"""
    import cv2
    img = img.copy(); m = mask.astype(np.float32); k = np.ones((3, 3), np.float32)
    for _ in range(iters):
        num = cv2.filter2D(img * m[:, :, None], -1, k, borderType=cv2.BORDER_CONSTANT)
        den = cv2.filter2D(m, -1, k, borderType=cv2.BORDER_CONSTANT)
        grow = (m == 0) & (den > 0)
        if not grow.any(): break
        img[grow] = num[grow] / den[grow][:, None]; m[grow] = 1
    return img, m > 0
