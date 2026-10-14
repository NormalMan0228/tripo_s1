"""Shared geometry helpers for the face pipeline (run inside Blender's Python)."""
import math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


def bvh_of(V, F):
    return BVHTree.FromPolygons([Vector(v) for v in V], [list(f) for f in F])


def hit_y(bvh, x, z, y0=-2.0):
    loc = bvh.ray_cast(Vector((x, y0, z)), Vector((0, 1, 0)))[0]
    return None if loc is None else loc.y


def rim_rays(bvh, cx, cz, mode, step_deg=4):
    """Eye opening contour from front rays walking outward from (cx, cz).
    margin: sculpted eye (eyeball recedes toward the lid, then the lid rises) -> first depth maximum.
    pocket: open socket / anime pocket (the ray falls into the socket) -> top of the wall where depth jumps forward."""
    yc = hit_y(bvh, cx, cz)
    if yc is None: yc = 9.0
    pts = []
    rs = np.arange(0.002, 0.045, 0.00025)
    for th in np.radians(np.arange(0, 360, step_deg)):
        d = (math.cos(th), math.sin(th))
        ys = np.array([hit_y(bvh, cx + r * d[0], cz + r * d[1]) or np.nan for r in rs])
        ok = None
        if mode == 'margin':
            for i in range(1, len(rs) - 16):
                if ys[i] >= ys[i - 1] and ys[i] >= ys[i + 1] and ys[i] - np.nanmin(ys[i + 1:i + 16]) > 0.0003:
                    ok = i; break
        else:
            for i in range(len(rs) - 1):
                if ys[i] < min(yc, np.nanmax(ys[:i + 1])) - 0.004:
                    while i + 1 < len(rs) and ys[i] - ys[i + 1] > 0.6 * (rs[1] - rs[0]): i += 1
                    ok = i; break
        if ok is not None:
            pts.append([cx + rs[ok] * d[0], ys[ok], cz + rs[ok] * d[1]])
    return np.array(pts)


def recentred_rim(bvh, cx, cz, mode, rounds=3):
    R = None
    for _ in range(rounds):
        R = rim_rays(bvh, cx, cz, mode); cx, cz = float(R[:, 0].mean()), float(R[:, 2].mean())
    return R


def resample(path, ts):
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)]); s /= s[-1]
    return np.array([[np.interp(t, s, path[:, j]) for j in range(3)] for t in ts])


def split_idx(n, a_idx, b_idx):
    p1 = [a_idx]; i = a_idx
    while i != b_idx: i = (i + 1) % n; p1.append(i)
    p2 = [a_idx]; i = a_idx
    while i != b_idx: i = (i - 1) % n; p2.append(i)
    return p1, p2


def lids(R, ts):
    """Corners = ends of the contour's long axis (outer = farther from the midline); upper/lower lid samples."""
    xz = R[:, [0, 2]]; c0 = xz.mean(0); ev = np.linalg.eigh(np.cov((xz - c0).T))[1][:, -1]
    t = (xz - c0) @ ev; e1, e2 = int(np.argmax(t)), int(np.argmin(t))
    io, ii = (e1, e2) if abs(R[e1, 0]) > abs(R[e2, 0]) else (e2, e1)
    p1, p2 = split_idx(len(R), io, ii)
    up, lo = (p1, p2) if R[p1][:, 2].mean() > R[p2][:, 2].mean() else (p2, p1)
    return {'outer': R[io], 'inner': R[ii], 'up': resample(R[up], ts), 'lo': resample(R[lo], ts), 'raw': R,
            'up_path': R[up], 'lo_path': R[lo]}


def seam_curve(bvh, xl, xr, zl, zm, zr, n=31):
    out = []
    for x in np.linspace(xl, xr, n):
        t = (x - xl) / (xr - xl); zc = zl + (zr - zl) * t
        zg = zm + (zc - zm) * (2 * t - 1) ** 2
        best = max(((hit_y(bvh, x, z) or -9, z) for z in np.arange(zg - 0.004, zg + 0.004, 0.0002)))
        z = best[1]; ys = [hit_y(bvh, x, z + dz) for dz in (-0.0006, 0.0006)]
        ys = [y for y in ys if y is not None]
        out.append([x, np.mean(ys) if ys else best[0], z])
    return np.array(out)


def tps_fit(X, Y, lam=1e-7):
    n = len(X); K = np.linalg.norm(X[:, None] - X[None], axis=2)
    P_ = np.hstack([np.ones((n, 1)), X])
    L = np.zeros((n + 4, n + 4)); L[:n, :n] = K + lam * np.eye(n); L[:n, n:] = P_; L[n:, :n] = P_.T
    rhs = np.zeros((n + 4, Y.shape[1])); rhs[:n] = Y
    return X, np.linalg.solve(L, rhs)


def tps_apply(model, Q):
    X, Wt = model; out = np.empty((len(Q), Wt.shape[1]))
    for s0 in range(0, len(Q), 4000):
        q = Q[s0:s0 + 4000]; K = np.linalg.norm(q[:, None] - X[None], axis=2)
        out[s0:s0 + 4000] = K @ Wt[:len(X)] + Wt[len(X)] + q @ Wt[len(X) + 1:]
    return out


def dist_to(Pset, Q):
    k2 = KDTree(len(Pset))
    for i, p in enumerate(Pset): k2.insert(p, i)
    k2.balance(); return np.array([k2.find(q)[2] for q in Q])


def smoothstep(x, e0, e1):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)


def inside2d(poly, pts):
    x, z = pts[:, 0], pts[:, 2]; px, pz = poly[:, 0], poly[:, 2]; res = np.zeros(len(pts), bool)
    j = len(poly) - 1
    for i in range(len(poly)):
        c = ((pz[i] > z) != (pz[j] > z)) & (x < (px[j] - px[i]) * (z - pz[i]) / (pz[j] - pz[i] + 1e-12) + px[i])
        res ^= c; j = i
    return res


def neighbours(nverts, faces):
    adj = [set() for _ in range(nverts)]
    for f in faces:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]; adj[a].add(b); adj[b].add(a)
    return [np.array(sorted(s)) for s in adj]


def laplace(D, nbrs, it, keep=0.5):
    for _ in range(it):
        D = keep * D + (1 - keep) * np.array([D[n].mean(0) if len(n) else D[i] for i, n in enumerate(nbrs)])
    return D


def vnormals(X, faces):
    nrm = np.zeros_like(X)
    for f in faces:
        nrm[f] += np.cross(X[f[1]] - X[f[0]], X[f[2]] - X[f[0]])
    return nrm / (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12)


def sphere_fit(P):
    A = np.hstack([2 * P, np.ones((len(P), 1))]); b = (P ** 2).sum(1)
    c, *_ = np.linalg.lstsq(A, b, rcond=None); ctr = c[:3]; r = math.sqrt(max(c[3] + ctr @ ctr, 1e-12))
    return ctr, r


def mirror_x(P, mirror):
    """Exact left/right symmetry using the template's mirror vertex pairs."""
    Q = P[mirror] * [-1, 1, 1]
    return (P + Q) / 2


def blink_field(P, eye, close=1.0, lower_share=0.1):
    """Procedural blink for one eye. eye: dict(center C, axis A (outer->inner unit), up_path, lo_path (world rims),
    eyeball radius r, angular reach). Every vertex in the lid region rotates about the axis through C, so it slides over the eyeball
    sphere and the upper margin lands on the lower margin whatever the eye size or tilt."""
    C, A = eye['C'], eye['A']
    fwd = np.array([0, -1, 0.0]); fwd = fwd - A * (fwd @ A); fwd /= np.linalg.norm(fwd)
    up = np.cross(A, fwd)                                  # completes the frame (points roughly +Z for both eyes)
    if up[2] < 0: up = -up
    def polar(Q):
        d = Q - C; s = d @ A; u = d @ up; f = d @ fwd
        return s, np.arctan2(u, f), np.sqrt(u * u + f * f)
    su, pu, ru = polar(eye['up_path']); sl, pl, rl = polar(eye['lo_path'])
    ou, ol = np.argsort(su), np.argsort(sl)
    s_all, phi, rad = polar(P)
    phi_up = np.interp(s_all, su[ou], pu[ou]); phi_lo = np.interp(s_all, sl[ol], pl[ol])
    meet = phi_lo + (phi_up - phi_lo) * lower_share
    span = max(su.max() - su.min(), 1e-6); edge = np.clip(1 - np.abs((s_all - (su.max() + su.min()) / 2) / (0.5 * span)), 0, 1)
    side_w = smoothstep(edge, 0.0, 0.25)                  # fade toward and beyond the corners
    reach = eye['reach']                                   # radians above/below the margin that still move
    w_up = np.where(phi >= phi_up - 0.02, 1 - smoothstep(phi - phi_up, 0.0, reach), 0.0)
    w_lo = np.where(phi <= phi_lo + 0.02, 1 - smoothstep(phi_lo - phi, 0.0, reach * 0.6), 0.0)
    dist = np.linalg.norm(P - C, axis=1)
    near = 1 - smoothstep(dist, 1.15 * eye['r'], 1.45 * eye['r'])   # lid skin hugs the eyeball; brow and nose do not move
    dphi = np.where(w_up > 0, (meet - phi_up) * w_up, (meet - phi_lo) * w_lo) * side_w * near * close
    newphi = phi + dphi
    # the closing upper lid must land just in front of the lower lid, not slide under it: lift the upper lid's
    # radius by the difference between the two margins (fading out with the same weight)
    r_up = np.interp(s_all, su[ou], ru[ou]); r_lo = np.interp(s_all, sl[ol], rl[ol])
    lift = np.where(w_up > 0, np.maximum(r_lo + 0.0004 - r_up, 0) * w_up * side_w * near * close, 0.0)
    rad = rad + lift
    u = np.sin(newphi) * rad; f = np.cos(newphi) * rad
    out = C + np.outer(s_all, A) + np.outer(u, up) + np.outer(f, fwd)
    moved = (np.abs(dphi) > 1e-9) | (lift > 1e-9)
    Q = P.copy(); Q[moved] = out[moved]
    return Q
