"""Shared steps of the organ builders (organ_mouth.py, organ_eye.py): an elliptical hole in the featureless head
with a clean boundary loop, and ring filling from that loop to an organ contour."""
import bmesh, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def cut_ellipse(bm, cx, cz, ea, eb, front_y):
    """Split the front faces the ellipse (front plane x, z) crosses along it, delete the faces inside, and return
    the hole's boundary loop as a list of BMVerts, starting at the vertex nearest +x and running upward
    (counter-clockwise seen from the front). The walk follows the actual hole edges, so a face the curve crossed
    twice (not split) only widens the hole a little instead of leaving a gap."""
    def f(P): return np.sqrt(((P[:, 0] - cx) / ea) ** 2 + ((P[:, 2] - cz) / eb) ** 2) - 1
    bm.faces.ensure_lookup_table()
    cen = lambda fc: np.array([tuple(fc.calc_center_median())])
    cand = [fc for fc in bm.faces if fc.calc_center_median().y < front_y and abs(f(cen(fc))[0]) < 0.25]
    vl = list({v for fc in cand for v in fc.verts}); fv = dict(zip(vl, f(np.array([tuple(v.co) for v in vl]))))
    zero = {v for v in vl if abs(fv[v]) < 1e-9}
    for e in list({e for fc in cand for e in fc.edges}):
        a_, b_ = e.verts; fa, fb = fv[a_], fv[b_]
        if fa * fb < 0: _, nv = bmesh.utils.edge_split(e, a_, fa / (fa - fb)); zero.add(nv)
    for fc in cand:
        zv = [v for v in fc.verts if v in zero]
        if len(zv) == 2 and not any(e.other_vert(zv[0]) is zv[1] for e in zv[0].link_edges): bmesh.utils.face_split(fc, zv[0], zv[1])
    inner = [fc for fc in bm.faces if fc.calc_center_median().y < front_y and f(cen(fc))[0] < 0]
    bmesh.ops.delete(bm, geom=inner, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    near = lambda v: abs(f(np.array([tuple(v.co)]))[0]) < 0.35 and v.co.y < front_y
    adj = {}
    for e in bm.edges:
        if e.is_boundary and near(e.verts[0]) and near(e.verts[1]):
            a0, b0 = e.verts; adj.setdefault(a0, []).append(b0); adj.setdefault(b0, []).append(a0)
    loops, seen = [], set()
    for v0 in adj:
        if v0 in seen: continue
        loop = [v0]; seen.add(v0); prev, cur = None, v0
        while True:
            nxt = [w for w in adj[cur] if w is not prev and w not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
        loops.append(loop)
    bnd = max(loops, key=len)
    i0 = int(np.argmax([v.co.x for v in bnd])); bnd = bnd[i0:] + bnd[:i0]
    if bnd[1].co.z < bnd[-1].co.z: bnd = [bnd[0]] + bnd[1:][::-1]
    return bnd, sorted([len(l) for l in loops], reverse=True)[:3]


def densify(bnd, n):
    """split the longest boundary edges (the new vertex lies on the original edge) until the loop has n vertices"""
    while len(bnd) < n:
        k = max(range(len(bnd)), key=lambda i: (bnd[i].co - bnd[(i + 1) % len(bnd)].co).length)
        e = next(e for e in bnd[k].link_edges if e.other_vert(bnd[k]) is bnd[(k + 1) % len(bnd)])
        _, nv = bmesh.utils.edge_split(e, bnd[k], 0.5); bnd.insert(k + 1, nv)
    return bnd


def loop_param(bnd, cx, cz, ea, eb):
    """parameter u in [0, 1) of each loop vertex: arc length along the loop (always increasing, so no two ring
    vertices share a contour point), shifted so the topmost point sits at u = 0.25 (the ellipse is symmetric, so
    the start (+x) and the far side (-x) then sit near 0 and 0.5)"""
    P = np.array([[v.co.x, v.co.z] for v in bnd])
    seg = np.linalg.norm(np.diff(np.r_[P, P[:1]], axis=0), axis=1); s = np.r_[0, np.cumsum(seg)[:-1]] / seg.sum()
    return s


def closed_contour(up, lo):
    """closed contour from the first corner over the top to the second corner and back under; up and lo both run
    corner1 -> corner2. Returns f(u) -> (x, z) with the second corner at u = 0.5"""
    P = np.r_[up, lo[::-1][1:]]
    seg = np.linalg.norm(np.diff(P[:, [0, 2]], axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]
    su = s[len(up) - 1] / s[-1]
    def f(u):
        t = np.where(u <= 0.5, u / 0.5 * su, su + (u - 0.5) / 0.5 * (1 - su)) * s[-1]
        return np.c_[np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 2])]
    return f


def surf_y(bvh, x, z):
    h = bvh.ray_cast(Vector((x, -2.0, z)), Vector((0, 1, 0))); return h[0].y if h[0] is not None else None


def bridge_rings(bm, rings_v):
    """quads between consecutive rings (same vertex count); returns the new faces"""
    out = []; M = len(rings_v[0])
    for k in range(len(rings_v) - 1):
        for i in range(M):
            j = (i + 1) % M
            try: out.append(bm.faces.new((rings_v[k][i], rings_v[k][j], rings_v[k + 1][j], rings_v[k + 1][i])))
            except ValueError: pass
    return out


# ---------------------------------------------------------------- v2: ray chart, level-set cut, zipper bridge
class Chart:
    """Chart of an organ seen from a point Q behind it (the eyeball centre): (u, v) = focal * (d.a, d.b) / (d.n),
    d = P - Q. A ray from Q meets a star-shaped patch exactly once, so the hole, the rings and their depth all work
    on big wrapped cartoon eyes, where a front (y) projection folds at the side of the head. u follows +x, v +z."""
    def __init__(self, Q, n, focal):
        self.Q = np.asarray(Q, float); n = np.asarray(n, float); self.n = n / np.linalg.norm(n); self.focal = float(focal)
        a = np.array([1.0, 0, 0]) - self.n * self.n[0]; self.a = a / np.linalg.norm(a); self.b = np.cross(self.n, self.a)

    def uv(self, P):
        d = np.atleast_2d(P) - self.Q; w = d @ self.n; ok = w > 1e-4 * self.focal
        out = self.focal * np.c_[d @ self.a, d @ self.b] / np.where(ok, w, 1.0)[:, None]; out[~ok] = np.nan
        return out

    def dirs(self, UV):
        UV = np.atleast_2d(UV) / self.focal; D = self.a * UV[:, :1] + self.b * UV[:, 1:2] + self.n
        return D / np.linalg.norm(D, axis=1, keepdims=True)

    def cast(self, bvh, UV):
        """distance from Q along each chart ray to the first surface hit (nan on a miss)"""
        out = []
        for d in self.dirs(UV):
            h = bvh.ray_cast(Vector(tuple(self.Q)), Vector(tuple(d)))
            out.append(h[3] if h[0] is not None else np.nan)
        return np.array(out)

    def cast_near(self, bvh, UV, expect, hits=4):
        """per ray: the surface hit (of the first `hits` along it) nearest to the expected distance"""
        out = []
        for d, e in zip(self.dirs(UV), np.atleast_1d(expect)):
            o = Vector(tuple(self.Q)); dv = Vector(tuple(d)); t0 = 0.0; best = np.nan
            for _ in range(hits):
                h = bvh.ray_cast(o + dv * t0, dv)
                if h[0] is None: break
                t = t0 + h[3]
                if not np.isfinite(best) or abs(t - e) < abs(best - e): best = t
                t0 = t + 1e-5
            out.append(best)
        return np.array(out)

    def point(self, UV, dist):
        return self.Q + self.dirs(UV) * np.asarray(dist)[:, None]


def egg(c0, ea_pos, ea_neg, eb_pos, eb_neg):
    """closed curve around c0 from four half-axes (+u, -u, +v, -v): f(UV) < 0 inside; rho(phi) = radius at angle phi"""
    def f(UV):
        UV = np.atleast_2d(UV); du, dv = UV[:, 0] - c0[0], UV[:, 1] - c0[1]
        ea = np.where(du > 0, ea_pos, ea_neg); eb = np.where(dv > 0, eb_pos, eb_neg)
        return np.sqrt((du / ea) ** 2 + (dv / eb) ** 2) - 1
    def rho(phi):
        c, s = np.cos(phi), np.sin(phi); ea = np.where(c > 0, ea_pos, ea_neg); eb = np.where(s > 0, eb_pos, eb_neg)
        return 1 / np.sqrt((c / ea) ** 2 + (s / eb) ** 2)
    return f, rho


def star(c0, phis, rhos):
    """closed curve around c0 given by its radius at sample angles (periodic linear interpolation); same interface
    as egg()"""
    o = np.argsort(phis); ph = np.asarray(phis)[o]; rh = np.asarray(rhos)[o]
    ph = np.r_[ph[-1] - 2 * np.pi, ph, ph[0] + 2 * np.pi]; rh = np.r_[rh[-1], rh, rh[0]]
    def rho(phi):
        return np.interp(np.mod(np.asarray(phi) - ph[0], 2 * np.pi) + ph[0], ph, rh)
    def f(UV):
        UV = np.atleast_2d(UV); d = UV - c0
        return np.hypot(d[:, 0], d[:, 1]) / rho(np.arctan2(d[:, 1], d[:, 0])) - 1
    return f, rho


def cut_level(bm, chart, f, tol_f):
    """Cut the hole {f < 0} out of the surface around the chart axis, exactly along f = 0.
    1. faces reached from the face on the chart axis through faces with min f < 0.5 (stays on this side of Q)
    2. vertices within tol_f of the curve become curve vertices (no sliver triangles); edges whose ends lie strictly
       on both sides are split where f = 0 (bisection on the edge, so the new vertex lies on the surface)
    3. faces that now have vertices strictly on both sides are split between curve vertices; the inside goes
    Returns (boundary loop counter-clockwise in the chart, its chart coordinates, info)."""
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    hit = bvh.ray_cast(Vector(tuple(chart.Q)), Vector(tuple(chart.n)))
    if hit[0] is None: raise RuntimeError('chart axis misses the surface')
    fv = {}
    def fval(v):
        if v not in fv:
            uv = chart.uv(np.array(v.co))
            fv[v] = float(f(uv)[0]) if np.isfinite(uv).all() else np.inf
        return fv[v]
    region, stack = set(), [bm.faces[hit[2]]]
    while stack:
        fc = stack.pop()
        if fc in region or min(fval(v) for v in fc.verts) > 0.5: continue
        region.add(fc)
        for e in fc.edges:
            for g in e.link_faces:
                if g not in region: stack.append(g)
    zero = set()
    for fc in region:
        for v in fc.verts:
            if abs(fval(v)) < tol_f: zero.add(v); fv[v] = 0.0
    n_split = 0
    for e in list({e for fc in region for e in fc.edges}):
        a_, b_ = e.verts; fa, fb = fval(a_), fval(b_)
        if fa * fb >= 0 or not (np.isfinite(fa) and np.isfinite(fb)): continue
        pa, pb = np.array(a_.co), np.array(b_.co); lo, hi = 0.0, 1.0
        for _ in range(24):
            mid = (lo + hi) / 2
            if np.sign(f(chart.uv(pa + (pb - pa) * mid))[0]) == np.sign(fa): lo = mid
            else: hi = mid
        _, nv = bmesh.utils.edge_split(e, a_, (lo + hi) / 2); zero.add(nv); fv[nv] = 0.0; n_split += 1
    sgn = lambda v: 0 if v in zero else (1 if fval(v) > 0 else -1)
    work = list(region); n_fsplit = 0
    while work:
        fc = work.pop()
        if not fc.is_valid: continue
        vs = list(fc.verts); s_ = [sgn(v) for v in vs]
        if not (1 in s_ and -1 in s_): continue
        L = len(vs); zs = [i for i in range(L) if s_[i] == 0]
        for k in range(len(zs)):
            i, j = zs[k], zs[(k + 1) % len(zs)]
            gap = (j - i) % L or L
            arc = [s_[m % L] for m in range(i + 1, i + gap)]
            if arc and len(set(arc)) == 1 and 1 < gap < L - 1:
                res = bmesh.utils.face_split(fc, vs[i], vs[j])
                work.append(fc)
                if res[0] is not None: work.append(res[0])
                n_fsplit += 1; break
    alive = [g for g in bm.faces if all(v in fv for v in g.verts)]
    def inside(g):
        s_ = [sgn(v) for v in g.verts]
        if -1 in s_ and 1 not in s_: return True
        if 1 in s_ and -1 not in s_: return False
        return f(chart.uv(np.array(g.calc_center_median())))[0] < 0          # all on the curve, or a split failed
    mixed = sum(1 for g in alive if 1 in [sgn(v) for v in g.verts] and -1 in [sgn(v) for v in g.verts])
    # delete only the inside piece around the chart axis (a fold elsewhere that the curve also encloses stays)
    ins = {g for g in alive if inside(g)}
    bm.faces.ensure_lookup_table(); seed = bm.faces[BVHTree.FromBMesh(bm).find_nearest(hit[0])[2]]
    comp, stack = set(), [seed] if seed in ins else []
    while stack:
        g = stack.pop()
        if g in comp: continue
        comp.add(g)
        for e in g.edges:
            for h in e.link_faces:
                if h in ins and h not in comp: stack.append(h)
    bmesh.ops.delete(bm, geom=list(comp), context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    adj = {}
    for e in bm.edges:
        if e.is_boundary and e.verts[0] in zero and e.verts[1] in zero:
            a0, b0 = e.verts; adj.setdefault(a0, []).append(b0); adj.setdefault(b0, []).append(a0)
    loops, seen = [], set()
    for v0 in adj:
        if v0 in seen: continue
        loop = [v0]; seen.add(v0); prev, cur = None, v0
        while True:
            nxt = [w for w in adj[cur] if w is not prev and w not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
        loops.append(loop)
    bnd = max(loops, key=len)
    UV = chart.uv(np.array([tuple(v.co) for v in bnd]))
    area = 0.5 * np.sum(UV[:, 0] * np.roll(UV[:, 1], -1) - np.roll(UV[:, 0], -1) * UV[:, 1])
    if area < 0: bnd = bnd[::-1]; UV = UV[::-1]
    info = {'region_faces': len(region), 'edge_splits': n_split, 'face_splits': n_fsplit, 'mixed_left': mixed,
            'inside_faces': len(ins), 'deleted': len(comp),
            'loops': sorted([len(l) for l in loops], reverse=True)[:4], 'bowtie_verts': sum(len(x) > 2 for x in adj.values())}
    return bnd, UV, info


def contour2d(up, lo):
    """closed 2D contour: corner1 -> over `up` -> corner2 -> back under `lo` (both run corner1 -> corner2).
    Returns g(t) -> (n, 2) with the corners at t = 0 and t = 0.5 (each lid gets half the parameter)."""
    def arc(P):
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; return s / s[-1]
    lo_r = lo[::-1]; su, sl = arc(up), arc(lo_r)
    def g(t):
        t = np.mod(np.asarray(t, float), 1.0); out = np.zeros((len(t), up.shape[1])); m = t <= 0.5
        for j in range(up.shape[1]):
            out[m, j] = np.interp(t[m] / 0.5, su, up[:, j]); out[~m, j] = np.interp((t[~m] - 0.5) / 0.5, sl, lo_r[:, j])
        return out
    return g


def zipper(bm, B, phB, R, phR):
    """triangles between an outer loop B and an inner ring R (both counter-clockwise), merged by angle around the
    chart centre: each step advances the loop whose next vertex comes first, so no triangle folds over"""
    phB = np.unwrap(phB)
    j0 = int(np.argmin(np.abs(np.angle(np.exp(1j * (np.asarray(phR) - phB[0]))))))
    R = R[j0:] + R[:j0]; phR = np.unwrap(np.r_[phR[j0:], phR[:j0]])
    phR = phR + 2 * np.pi * np.round((phB[0] - phR[0]) / (2 * np.pi))
    pb = np.r_[phB, phB[0] + 2 * np.pi]; pr = np.r_[phR, phR[0] + 2 * np.pi]
    nb, nr = len(B), len(R); i = j = 0; out = []
    while i < nb or j < nr:
        if j >= nr or (i < nb and pb[i + 1] <= pr[j + 1]):
            tri = (B[i % nb], B[(i + 1) % nb], R[j % nr]); i += 1
        else:
            tri = (B[i % nb], R[(j + 1) % nr], R[j % nr]); j += 1
        try: out.append(bm.faces.new(tri))
        except ValueError: pass
    return out


def rotate_about(P, C, ax, ang):
    d = P - C; ax = ax / np.linalg.norm(ax); c, s = np.cos(ang)[:, None], np.sin(ang)[:, None]
    return C + d * c + np.cross(ax, d) * s + ax * (d @ ax)[:, None] * (1 - c)


def ring_blink(X0, ring, u, sg, C, ax, t, K, M, meet=0.8, r_eye=None, clear=0.0002, knee=0.0001):
    """Eyelid closing on the ring topology of organ_eye (pure numpy, also used for the eyeBlink keys).
    Cylindrical coordinates about the corner axis through the eyeball centre: every lid column (same u) keeps its
    axial position and turns about the axis. The partner of an upper margin point is the lower margin point at the
    same axial position (interpolated), Delta apart in angle; the upper column turns meet * Delta * t and the lower
    (1 - meet) * Delta * t toward each other, and both blend their radius toward the meeting radius, so the margins
    meet along one curve and the corners stay put. Rings fade from the margin (weight 1, tucks included) to ring 2
    (weight 0); the skin rings 1-2 and the head do not move.
    With r_eye the closing lid also hugs the eyeball: a vertex g0 above the eyeball sphere at rest ends at most
    1.5 mm + 0.3 g0 above it (a lid slides over the eye, it does not sweep its rest bulge in front of it), and no
    moving vertex comes closer than `clear` to the sphere at any t (the meeting scale pulls the tuck rings in): a soft
    knee of width `knee` above that leaves every vertex with more room untouched (vertices nearer than clear + knee at
    rest keep their rest gap minus the knee, so t -> 0 still gives the rest pose)."""
    P = X0.copy(); m = np.sign(ring) == sg; k = np.abs(ring); ax = ax / np.linalg.norm(ax)
    col = np.rint(u * M).astype(int) % M
    D0 = X0 - C; A0 = D0 @ ax; R0 = D0 - np.outer(A0, ax)
    mk = np.where(m & (k == K))[0]; byc = {c: i for i, c in zip(mk, col[mk])}
    e1 = R0[mk].mean(0); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
    th = lambda R: np.arctan2(R @ e2, R @ e1)
    up_c = [c for c in range(0, M // 2 + 1) if c in byc]; lo_c = [c for c in [M // 2] + list(range(M // 2 + 1, M)) + [0] if c in byc]
    def curve(cs):
        ii = np.array([byc[c] for c in cs]); a_ = A0[ii]; o = np.argsort(a_)
        return a_[o], np.unwrap(th(R0[ii])[o]), np.linalg.norm(R0[ii], axis=1)[o]
    aU, tU, rU = curve(up_c); aL, tL, rL = curve(lo_c)
    shift = 2 * np.pi * np.round((np.median(tU) - np.median(tL)) / (2 * np.pi)); tL = tL + shift
    w = np.where(k >= K, 1.0, np.clip((k - 2) / (K - 2), 0, 1)); w = w * w * (3 - 2 * w)
    ang = np.zeros(len(P)); scl = np.ones(len(P)); dang, rme = {}, {}
    for c, i in byc.items():
        if c == 0 or c == M // 2: continue
        upper = c < M // 2; a_ = A0[i]; ti = np.arctan2(R0[i] @ e2, R0[i] @ e1); ri = np.linalg.norm(R0[i])
        if upper:
            to, ro = np.interp(a_, aL, tL), np.interp(a_, aL, rL); ti = ti + 2 * np.pi * np.round((to - ti) / (2 * np.pi))
            d_ang = meet * (to - ti); r_meet = ri + meet * (ro - ri)
        else:
            to, ro = np.interp(a_, aU, tU), np.interp(a_, aU, rU); ti = ti + 2 * np.pi * np.round((to - ti) / (2 * np.pi))
            d_ang = (1 - meet) * (to - ti); r_meet = ri + (1 - meet) * (ro - ri)
        dang[c] = d_ang; rme[c] = r_meet / ri
    # neighbouring columns of a lid turn alike (a jagged meeting line comes from margin noise)
    for half in (range(1, M // 2), range(M // 2 + 1, M)):
        cs = [c for c in half if c in dang]
        for _ in range(2):
            a_ = np.array([dang[c] for c in cs]); b_ = np.array([rme[c] for c in cs])
            a_[1:-1] = (a_[:-2] + 2 * a_[1:-1] + a_[2:]) / 4; b_[1:-1] = (b_[:-2] + 2 * b_[1:-1] + b_[2:]) / 4
            for c, x, y in zip(cs, a_, b_): dang[c] = x; rme[c] = y
    for c in dang:
        sel = m & (col == c)
        ang[sel] = dang[c] * t * w[sel]; scl[sel] = 1 + (rme[c] - 1) * t * w[sel]
    idx = m & (ang != 0)
    c_, s_ = np.cos(ang[idx])[:, None], np.sin(ang[idx])[:, None]; R = R0[idx]
    Rr = R * c_ + np.cross(ax, R) * s_                      # R is perpendicular to the axis
    rho = np.linalg.norm(R, axis=1) * scl[idx]
    if r_eye is not None:
        g0 = np.linalg.norm(D0[idx], axis=1) - r_eye; g1 = np.minimum(g0, 0.0015 + 0.3 * np.maximum(g0, 0))
        rho_t = np.sqrt(np.maximum((r_eye + g1) ** 2 - A0[idx] ** 2, 0))
        wt = (t * w[idx]) * (rho_t < rho)
        rho = rho + wt * (rho_t - rho)
        cl = np.clip(np.minimum(clear, g0 - knee), 0, None); A2 = A0[idx] ** 2
        x = np.sqrt(A2 + rho ** 2) - r_eye - cl; lo = x < knee                     # distance above the floor sphere
        xs = knee * np.exp(np.minimum(x, knee) / knee - 1)                          # C1 knee: x at knee, -> 0 deep inside
        rho = np.where(lo, np.sqrt(np.maximum((r_eye + cl + xs) ** 2 - A2, 0)), rho)
    Rn = Rr / np.maximum(np.linalg.norm(Rr, axis=1, keepdims=True), 1e-12)
    P[idx] = C + np.outer(A0[idx], ax) + Rn * rho[:, None]
    return P


def ring_blink_irregular(X0, ring, u, sg, C, ax, t, K, meet=0.8, r_eye=None, clear=0.0002, knee=0.0001, corner_fade=0.06,
                         tuck_room=0.0006):
    """ring_blink for irregular lid rings (loop_organs.py: BFS rings of the original mesh, any vertex count per ring,
    u not on a column grid). Cylindrical coordinates about the corner axis through the eyeball centre, as ring_blink.
    Closed margin: ONE meeting line for both lids, as a function of the axial position A: angle
    (1 - meet) * upper(A) + meet * lower(A) and gap above the eyeball (1 - meet) * gap_upper(A) + meet * gap_lower(A)
    (both lid curves interpolated at A, corners shared), smoothed along A, the gap then hugged like ring_blink
    (at most 1.5 mm + 0.3 rest gap, at least tuck_room = 0.6 mm where the rest gap allows, so the tuck rings, which
    only turn and keep their 0.5 / 0.3 mm gaps, stay under the margin). Every margin vertex goes exactly onto that line at
    its own A, so the upper and lower margins meet without a gap whatever their vertex counts.
    Other lid vertices turn by dang(u) * t * w(ring) and scale their radius by 1 + (rme(u) - 1) * t * w(ring): dang /
    rme are the margin vertices' values as periodic functions of u (0 turn and scale 1 at the corners u = 0 / 0.5;
    the tuck rings, which share their margin vertex's u, take the exact values; skin rings a version smoothed along
    each lid, 2 passes 1-2-1, faded to 0 within corner_fade of u of each corner: skin round a blunt canthus would
    otherwise shear across the corner line). w, the eyeball hug and the clearance floor (r_eye, clear, knee) as in
    ring_blink."""
    P = X0.copy(); m = np.sign(ring) == sg; k = np.abs(ring); ax = ax / np.linalg.norm(ax)
    D0 = X0 - C; A0 = D0 @ ax; R0 = D0 - np.outer(A0, ax); rad0 = np.linalg.norm(R0, axis=1)
    mk = np.where(m & (k == K))[0]; um = np.mod(u[mk], 1.0)
    e1 = R0[mk].mean(0); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
    th = np.arctan2(R0 @ e2, R0 @ e1)
    cor = (np.abs(um) < 1e-9) | (np.abs(um - 0.5) < 1e-9) | (np.abs(um - 1) < 1e-9)
    upm = (um < 0.5) & ~cor; lom = (um > 0.5) & ~cor
    rr = r_eye if r_eye is not None else float(np.median(np.linalg.norm(D0[mk], axis=1)))
    gm = np.linalg.norm(D0[mk], axis=1) - rr                  # margin rest gaps above the eyeball sphere
    def curve(sel):
        ii = np.where(sel)[0]; o = np.argsort(A0[mk[ii]]); ii = ii[o]
        return A0[mk[ii]], np.unwrap(th[mk[ii]]), gm[ii]
    aU, tU, gU = curve(upm | cor); aL, tL, gL = curve(lom | cor)
    tL = tL + 2 * np.pi * np.round((np.median(tU) - np.median(tL)) / (2 * np.pi))
    lo_a, hi_a = max(aU[0], aL[0]), min(aU[-1], aL[-1]); AG = np.linspace(lo_a, hi_a, 64)
    TM = (1 - meet) * np.interp(AG, aU, tU) + meet * np.interp(AG, aL, tL)
    GM = (1 - meet) * np.interp(AG, aU, gU) + meet * np.interp(AG, aL, gL)
    for _ in range(3):
        TM[1:-1] = (TM[:-2] + 2 * TM[1:-1] + TM[2:]) / 4; GM[1:-1] = (GM[:-2] + 2 * GM[1:-1] + GM[2:]) / 4
    if r_eye is not None:
        G1 = np.minimum(GM, 0.0015 + 0.3 * np.maximum(GM, 0)); GM = np.maximum(G1, np.minimum(tuck_room, GM))   # tucks stay under
    dang = np.zeros(len(mk)); rme = np.ones(len(mk))
    for q in np.where(~cor)[0]:
        i = mk[q]; a_ = A0[i]
        to = np.interp(a_, AG, TM); ti = th[i] + 2 * np.pi * np.round((to - th[i]) / (2 * np.pi))
        Rm = np.sqrt(max((rr + float(np.interp(a_, AG, GM))) ** 2 - a_ * a_, 1e-12))
        dang[q] = to - ti; rme[q] = Rm / rad0[i]
    ds, rs = dang.copy(), rme.copy()
    for half in (upm, lom):                                  # skin rings: neighbouring margin values alike
        qs = np.where(half)[0]; qs = qs[np.argsort(um[qs])]
        for _ in range(2):
            a_ = ds[qs]; b_ = rs[qs]
            a_[1:-1] = (a_[:-2] + 2 * a_[1:-1] + a_[2:]) / 4; b_[1:-1] = (b_[:-2] + 2 * b_[1:-1] + b_[2:]) / 4
            ds[qs] = a_; rs[qs] = b_
    def per(vals, scl0):
        ku = np.r_[um[~cor], 0.0, 0.5]; kv = np.r_[vals[~cor], scl0, scl0]; o = np.argsort(ku); ku, kv = ku[o], kv[o]
        KU = np.r_[ku[-1] - 1, ku, ku[0] + 1]; KV = np.r_[kv[-1], kv, kv[0]]
        return lambda x: np.interp(np.mod(x, 1.0), KU, KV)
    fd, fr, fds, frs = per(dang, 0.0), per(rme, 1.0), per(ds, 0.0), per(rs, 1.0)
    uu = np.mod(u, 1.0); inner = k >= K
    w = np.where(k >= K, 1.0, np.clip((k - 2) / (K - 2), 0, 1)); w = w * w * (3 - 2 * w)
    m_ = np.mod(uu, 0.5); cf = np.clip(np.minimum(m_, 0.5 - m_) / corner_fade, 0, 1); cf = cf * cf * (3 - 2 * cf)
    dv = np.where(inner, fd(uu), fds(uu) * cf); sv = np.where(inner, fr(uu), 1 + (frs(uu) - 1) * cf)
    sv = np.where(k > K, 1.0, sv)                            # tuck rings only turn: they keep their gap under the margin
    ang = np.where(m, dv * t * w, 0.0); scl = np.where(m, 1 + (sv - 1) * t * w, 1.0)
    idx = m & (ang != 0); marg = (k == K)[idx]
    c_, s_ = np.cos(ang[idx])[:, None], np.sin(ang[idx])[:, None]; R = R0[idx]
    Rr = R * c_ + np.cross(ax, R) * s_
    rho = rad0[idx] * scl[idx]
    if r_eye is not None:
        g0 = np.linalg.norm(D0[idx], axis=1) - r_eye; g1 = np.minimum(g0, 0.0015 + 0.3 * np.maximum(g0, 0))
        rho_t = np.sqrt(np.maximum((r_eye + g1) ** 2 - A0[idx] ** 2, 0))
        wt = (t * w[idx]) * (rho_t < rho) * ~marg                # the margin already sits on the hugged meeting line
        rho = rho + wt * (rho_t - rho)
        cl = np.clip(np.minimum(clear, g0 - knee), 0, None); A2 = A0[idx] ** 2
        x = np.sqrt(A2 + rho ** 2) - r_eye - cl; lo = x < knee
        xs = knee * np.exp(np.minimum(x, knee) / knee - 1)
        rho = np.where(lo, np.sqrt(np.maximum((r_eye + cl + xs) ** 2 - A2, 0)), rho)
    Rn = Rr / np.maximum(np.linalg.norm(Rr, axis=1, keepdims=True), 1e-12)
    P[idx] = C + np.outer(A0[idx], ax) + Rn * rho[:, None]
    return P


def lid_coord(n, edges, ring, sg, K, iters=400):
    """smooth lid coordinate h for ring_blink_canthus: 1 on the margin (ring K), 0 on rings <= 2 and off the lid, harmonic
    (uniform-weight Jacobi) on the skin rings 3 .. K-1 of side sg; tuck rings (> K) get 1. BFS ring indices bunch near the
    canthi and jump where a ring zig-zags; h has smooth level sets, so a falloff on h moves neighbouring skin alike."""
    k = np.abs(ring); side = np.sign(ring) == sg
    h = np.zeros(n); h[side & (k >= K)] = 1.0
    free = np.where(side & (k > 2) & (k < K))[0]
    if not len(free): return h
    nb = [[] for _ in range(n)]
    for a_, b_ in edges: nb[a_].append(b_); nb[b_].append(a_)
    lists = [[w for w in nb[v] if not (side[w] and k[w] > K)] for v in free]      # tucks do not pull the skin
    mx = max(len(l) for l in lists); NB = np.array([l + [l[0]] * (mx - len(l)) for l in lists]); cnt = np.array([len(l) for l in lists], float)
    msk = (np.arange(mx)[None, :] < cnt[:, None])
    h[free] = np.clip((k[free] - 2) / (K - 2), 0, 1)                                 # start: the ring ramp
    for _ in range(iters):
        h[free] = (h[NB] * msk).sum(1) / cnt
    return h


def ring_blink_canthus(X0, ring, u, sg, C, ax, t, K, h, meet=0.62, r_eye=None, clear=0.0002, knee=0.0001, corner_fade=0.06,
                       tuck_room=0.0006, W1=0.75, HUGA=0.25, BL0=0.6):
    """ring_blink_irregular anchored at the canthi with a smooth skin falloff (eye_fit P2 bases).
    The ring corners (eye_u = 0 / 0.5) are the canthus vertices (loop_organs takes eyes_meta corner_vids) and do not move.
    Margin: onto ONE meeting line from canthus to canthus as ring_blink_irregular, but at meet = 0.62 (the line runs a
    little below the middle of the opening; the upper lid makes ~60 % of the travel). Skin: turns by the margin's turn
    (smoothed along u, 0 at the canthi, corner_fade) times smoothstep(h), h = lid_coord (harmonic, 1 at the margin, 0 at
    ring 2) instead of the BFS ring index, so skin that the BFS rings bunch together (outer third of the upper lid, canthus
    folds) moves alike and the closed lid has no dents; the rim next to the margin (h >= W1 = 0.75) turns rigidly with it
    (a thin lower-lid rim strip sheared across would fold), skin with h > BL0 takes the margin's exact turn blended into the
    smoothed one. Eyeball hug only where the lid turns (|turn| / HUGA rad, smoothstep: a lower lid that barely moves keeps
    its roll). Tucks and clearance floor as ring_blink_irregular."""
    k = np.abs(ring); hh = np.where(k >= K, 1.0, np.clip(h, 0, 1))
    P = X0.copy(); m = np.sign(ring) == sg; ax = ax / np.linalg.norm(ax)
    D0 = X0 - C; A0 = D0 @ ax; R0 = D0 - np.outer(A0, ax); rad0 = np.linalg.norm(R0, axis=1)
    mk = np.where(m & (k == K))[0]; um = np.mod(u[mk], 1.0)
    e1 = R0[mk].mean(0); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
    th = np.arctan2(R0 @ e2, R0 @ e1)
    cor = (np.abs(um) < 1e-9) | (np.abs(um - 0.5) < 1e-9) | (np.abs(um - 1) < 1e-9)
    upm = (um < 0.5) & ~cor; lom = (um > 0.5) & ~cor
    rr = r_eye if r_eye is not None else float(np.median(np.linalg.norm(D0[mk], axis=1)))
    gm = np.linalg.norm(D0[mk], axis=1) - rr
    def curve(sel):
        ii = np.where(sel)[0]; o = np.argsort(A0[mk[ii]]); ii = ii[o]
        return A0[mk[ii]], np.unwrap(th[mk[ii]]), gm[ii]
    aU, tU, gU = curve(upm | cor); aL, tL, gL = curve(lom | cor)
    tL = tL + 2 * np.pi * np.round((np.median(tU) - np.median(tL)) / (2 * np.pi))
    lo_a, hi_a = max(aU[0], aL[0]), min(aU[-1], aL[-1]); AG = np.linspace(lo_a, hi_a, 64)
    TM = (1 - meet) * np.interp(AG, aU, tU) + meet * np.interp(AG, aL, tL)
    GM = (1 - meet) * np.interp(AG, aU, gU) + meet * np.interp(AG, aL, gL)
    for _ in range(3):
        TM[1:-1] = (TM[:-2] + 2 * TM[1:-1] + TM[2:]) / 4; GM[1:-1] = (GM[:-2] + 2 * GM[1:-1] + GM[2:]) / 4
    if r_eye is not None:
        G1 = np.minimum(GM, 0.0015 + 0.3 * np.maximum(GM, 0)); GM = np.maximum(G1, np.minimum(tuck_room, GM))
    dang = np.zeros(len(mk)); rme = np.ones(len(mk))
    for q in np.where(~cor)[0]:
        i = mk[q]; a_ = A0[i]
        to = np.interp(a_, AG, TM); ti = th[i] + 2 * np.pi * np.round((to - th[i]) / (2 * np.pi))
        Rm = np.sqrt(max((rr + float(np.interp(a_, AG, GM))) ** 2 - a_ * a_, 1e-12))
        dang[q] = to - ti; rme[q] = Rm / rad0[i]
    ds, rs = dang.copy(), rme.copy()
    for half in (upm, lom):                                  # skin: neighbouring margin values alike (4 passes 1-2-1)
        qs = np.where(half)[0]; qs = qs[np.argsort(um[qs])]
        for _ in range(4):
            a_ = ds[qs]; b_ = rs[qs]
            a_[1:-1] = (a_[:-2] + 2 * a_[1:-1] + a_[2:]) / 4; b_[1:-1] = (b_[:-2] + 2 * b_[1:-1] + b_[2:]) / 4
            ds[qs] = a_; rs[qs] = b_
    def per(vals, scl0):
        ku = np.r_[um[~cor], 0.0, 0.5]; kv = np.r_[vals[~cor], scl0, scl0]; o = np.argsort(ku); ku, kv = ku[o], kv[o]
        KU = np.r_[ku[-1] - 1, ku, ku[0] + 1]; KV = np.r_[kv[-1], kv, kv[0]]
        return lambda x: np.interp(np.mod(x, 1.0), KU, KV)
    fd, fr, fds, frs = per(dang, 0.0), per(rme, 1.0), per(ds, 0.0), per(rs, 1.0)
    uu = np.mod(u, 1.0); inner = k >= K
    hw = np.clip(hh / W1, 0, 1)                                 # the lid rim next to the margin (h >= W1) turns rigidly with it
    w = np.where(inner, 1.0, hw * hw * (3 - 2 * hw))
    m_ = np.mod(uu, 0.5); cf = np.clip(np.minimum(m_, 0.5 - m_) / corner_fade, 0, 1); cf = cf * cf * (3 - 2 * cf)
    # skin next to the margin turns like the margin itself (exact values), farther out like the smoothed, corner-faded
    # values: the blend follows h, so there is no shear between the margin and the first skin ring near the canthi
    bl = np.where(inner, 1.0, np.clip((hh - BL0) / (1 - BL0), 0, 1)) if BL0 < 1 else inner.astype(float); bl = bl * bl * (3 - 2 * bl)
    dv = bl * fd(uu) + (1 - bl) * fds(uu) * cf; sv = bl * fr(uu) + (1 - bl) * (1 + (frs(uu) - 1) * cf)
    sv = np.where(k > K, 1.0, sv)
    ang = np.where(m, dv * t * w, 0.0); scl = np.where(m, 1 + (sv - 1) * t * w, 1.0)
    idx = m & (ang != 0); marg = (k == K)[idx]
    c_, s_ = np.cos(ang[idx])[:, None], np.sin(ang[idx])[:, None]; R = R0[idx]
    Rr = R * c_ + np.cross(ax, R) * s_
    rho = rad0[idx] * scl[idx]
    if r_eye is not None:
        g0 = np.linalg.norm(D0[idx], axis=1) - r_eye; g1 = np.minimum(g0, 0.0015 + 0.3 * np.maximum(g0, 0))
        rho_t = np.sqrt(np.maximum((r_eye + g1) ** 2 - A0[idx] ** 2, 0))
        hugw = np.clip(np.abs(dv[idx]) / HUGA, 0, 1); hugw = hugw * hugw * (3 - 2 * hugw)   # only lids that travel hug the eye:
        wt = (t * w[idx]) * (rho_t < rho) * ~marg * hugw                                     # a lower lid barely turning keeps its roll
        rho = rho + wt * (rho_t - rho)
        cl = np.clip(np.minimum(clear, g0 - knee), 0, None); A2 = A0[idx] ** 2
        x = np.sqrt(A2 + rho ** 2) - r_eye - cl; lo = x < knee
        xs = knee * np.exp(np.minimum(x, knee) / knee - 1)
        rho = np.where(lo, np.sqrt(np.maximum((r_eye + cl + xs) ** 2 - A2, 0)), rho)
    Rn = Rr / np.maximum(np.linalg.norm(Rr, axis=1, keepdims=True), 1e-12)
    P[idx] = C + np.outer(A0[idx], ax) + Rn * rho[:, None]
    return P



def follow_field(X0, ring, u, sg, K, edges, reach=0.014):
    """Geodesic reach of the margin of side sg over the whole face (edges; vertices with x * sg > 0, the tucks and the
    margin itself): per vertex the distance to the nearest margin vertex and that vertex (its owner). Cache it per side
    for lid_follow."""
    import heapq
    k = np.abs(ring); m = np.sign(ring) == sg; side = m | (X0[:, 0] * sg > 1e-6)
    mk = np.where(m & (k == K))[0]
    nb = {}
    for a_, b_ in edges:
        if side[a_] and side[b_]: nb.setdefault(int(a_), []).append(int(b_)); nb.setdefault(int(b_), []).append(int(a_))
    dist = {int(v): 0.0 for v in mk}; own = {int(v): int(v) for v in mk}; h = [(0.0, int(v)) for v in mk]
    while h:
        du, v = heapq.heappop(h)
        if du > dist[v] or du > reach: continue
        for w_ in nb.get(v, ()):
            nd = du + float(np.linalg.norm(X0[v] - X0[w_]))
            if nd < dist.get(w_, 1e18): dist[w_] = nd; own[w_] = own[v]; heapq.heappush(h, (nd, w_))
    ids = np.array(sorted(dist), int)
    return {'ids': ids, 'dist': np.array([dist[v] for v in ids]), 'own': np.array([own[v] for v in ids], int), 'mk': mk, 'reach': reach}


def lid_follow(X0, ring, u, sg, C, K, FF, el_u, el_l, az_u=0.0, az_l=0.0, rim=0.0015, pw=1.0):
    """Lids following the gaze (eye-fit / loop_organs heads). Every vertex reached by FF = follow_field(...) turns about
    the eyeball centre C, so its distance to C (the lid's clearance over the eyeball, the tucks' too) is unchanged:
    elevation el (deg, + = up, about the head's x axis), then azimuth az (deg, about the head's z axis, + = toward +x),
    by the values of its owner margin vertex (upper lid: eye_u < 0.5) times
      p(a) = sin(pi a) ** pw   (a = share along the chord outer canthus -> inner canthus, 0 at both canthi: the skin's
                               own, the margin's and the tucks' that of their owner margin vertex)
      f(d) = 1 within `rim` (1.5 mm, geodesic) of the margin and on the tucks, then 1 - smoothstep out to FF['reach']
    (toward the canthi the upper and lower values blend into their mean by 1 - p: the corner moves as one piece)
    The upper lid skin spans little elevation about C up to the eye rings' edge (f02: 14 deg), so the falloff runs over
    the face out to the brow (14 mm), not over lid_coord: a 15 deg raise then compresses the skin about 2:1 at most
    instead of folding it. Returns the new positions."""
    k = np.abs(ring); ids, dist, own, mk = FF['ids'], FF['dist'], FF['own'], FF['mk']
    um = np.mod(u[mk], 1.0); i_out = mk[np.argmin(np.minimum(um, 1 - um))]; i_in = mk[np.argmin(np.abs(um - 0.5))]
    e = X0[i_in] - X0[i_out]; src = np.where(k[ids] >= K, own, ids)      # the skin by its own chord share (smooth), the margin / tucks by their owner's
    a = np.clip(((X0[src] - X0[i_out]) @ e) / float(e @ e), 0, 1); p = np.sin(np.pi * a) ** pw
    x = np.clip((dist - rim) / max(FF['reach'] - rim, 1e-9), 0, 1); f = 1 - x * x * (3 - 2 * x)
    f = np.where(k[ids] > K, 1.0, f)
    up = np.mod(u[own], 1.0) < 0.5
    # toward the canthi both lids take the mean turn (no squeeze of the narrow corner between them), mid-lid their own
    b = p
    el = np.radians(b * np.where(up, el_u, el_l) + (1 - b) * (el_u + el_l) / 2) * p * f
    az = np.radians(b * np.where(up, az_u, az_l) + (1 - b) * (az_u + az_l) / 2) * p * f
    P = X0.copy(); D = X0[ids] - C
    c, s_ = np.cos(-el), np.sin(-el)                                     # up = negative turn about +x (front is -y)
    y = c * D[:, 1] - s_ * D[:, 2]; z = s_ * D[:, 1] + c * D[:, 2]; D = np.c_[D[:, 0], y, z]
    c, s_ = np.cos(az), np.sin(az)                                       # toward +x = positive turn about +z
    x_ = c * D[:, 0] - s_ * D[:, 1]; y = s_ * D[:, 0] + c * D[:, 1]
    P[ids] = C + np.c_[x_, y, D[:, 2]]
    return P

def wedge_close(P, X0, ring, u, sg, K, tip, view, t, C=None, r_eye=None, clear=0.0002, reach=0.003, edges=None, smooth=8):
    """Close the caruncle wedge of an eye-fit base whose margin ends at the P2 inner corner Kc (u = 0.5) while the visible
    inner tip of the eye (where sleep crust collects) is the wedge apex `tip`, a few mm medial. Front chart (plane
    normal to `view`): e_a from Kc to the tip, e_n perpendicular (up). Lower wedge edge = the line Kc -> tip; upper edge =
    the rim line from the tip that touches the upper margin from above (largest slope n / (1 - a) seen from the tip),
    i.e. wedge height h(a) = H0 (1 - a) at a in [0, 1]. Skin of side sg (not the margin, not the tucks) with 0 <= a <= 1:
    inside the wedge (0 <= height <= h) it comes down by t * height (the upper edge lands on the lower one, the wedge
    narrows to a line ending at the tip), above it by t * h(a) * (1 - smoothstep(dist / reach)) (the lid above the wedge
    follows, reach 3 mm). This wedge field replaces the lid blink for that skin, blended in over a in [-0.6, 0] and faded
    out over [0.9, 1] (the tip stays); the margin and the tucks keep the lid blink.
    With r_eye the result keeps `clear` above the eyeball sphere. Returns the new positions (P is not modified)."""
    if tip is None: return P
    tip = np.asarray(tip, float); k = np.abs(ring); m = np.sign(ring) == sg
    mk = np.where(m & (k == K))[0]; um = np.mod(u[mk], 1.0)
    ic = mk[np.argmin(np.abs(um - 0.5))]; Kc = X0[ic]
    v = np.asarray(view, float); v = v / np.linalg.norm(v)
    ea = (tip - Kc) - v * ((tip - Kc) @ v); L = float(np.linalg.norm(ea))
    if L < 0.001: return P
    ea /= L; en = np.cross(v, ea)
    if en[2] < 0: en = -en
    a_ = ((X0 - Kc) @ ea) / L; n_ = (X0 - Kc) @ en
    # upper wedge edge: the rim line from the tip that touches the upper margin from above (largest slope n / (1 - a)
    # seen from the tip); the wedge height at a is then H0 (1 - a)
    upm = np.array([i for i in mk if 0 < np.mod(u[i], 1.0) < 0.5 and a_[i] < 0.95], int)
    H0 = float(max((n_[upm] / (1 - a_[upm])).max(), 0.0)) if len(upm) else 0.0
    if H0 <= 1e-5: return P
    ntip = float((tip - Kc) @ en)
    lo = a_ * ntip                                            # lower edge: straight from Kc to the tip
    h = H0 * np.clip(1 - a_, 0, None); ht = n_ - lo
    # skin (not margin, not tucks) above the closing line near the inner end: the wedge field (inside the wedge down by
    # its height above the line, above it down by h(a) with a 3 mm falloff) replaces the lid blink there, blended in over
    # a in [-0.6, 0] (the lid blink alone further out) and faded out over [0.9, 1] (the tip stays)
    sel = m & (k < K) & (k > 0) & (a_ > -0.6) & (a_ < 1.0) & (ht > 0) & ((a_ > 0) | (np.mod(u, 1.0) < 0.5))
    om = np.clip((a_ + 0.6) / 0.6, 0, 1); om = om * om * (3 - 2 * om)
    fa = np.clip((1.0 - a_) / 0.1, 0, 1); fa = fa * fa * (3 - 2 * fa)
    inside = ht <= h; dist = ht - h; fo = 1 - np.clip(dist / reach, 0, 1); fo = fo * fo * (3 - 2 * fo)
    down = np.where(inside, np.maximum(ht, 0), h * fo) * fa * t
    W_ = X0 - np.outer(down, en)
    Q = P.copy(); Q[sel] = (1 - om[sel])[:, None] * P[sel] + om[sel][:, None] * W_[sel]
    if edges is not None and smooth and sel.any():
        # the wedge skin is folded (P2 caruncle): its change against the lid blink is smoothed over the mesh (Jacobi,
        # half steps; margin, tucks and the tip held) so folded vertices do not crumple into slivers
        idx = np.where(sel)[0]; pos = -np.ones(len(X0), int); pos[idx] = np.arange(len(idx))
        e = np.asarray(edges); keep = sel[e[:, 0]] | sel[e[:, 1]]; e = e[keep]
        tipv = int(np.argmin(np.linalg.norm(X0 - tip, axis=1)))
        Dw = Q - P
        free = sel.copy(); free[tipv] = False
        for _ in range(smooth):
            acc = np.zeros_like(Dw); cnt = np.zeros(len(X0))
            np.add.at(acc, e[:, 0], Dw[e[:, 1]]); np.add.at(acc, e[:, 1], Dw[e[:, 0]]); np.add.at(cnt, e[:, 0], 1); np.add.at(cnt, e[:, 1], 1)
            f_ = free & (cnt > 0); Dw[f_] = 0.5 * Dw[f_] + 0.5 * acc[f_] / cnt[f_, None]
        Q[sel] = P[sel] + Dw[sel]
    if r_eye is not None and C is not None:
        d = Q[sel] - C; rr = np.linalg.norm(d, axis=1); lo_ = rr < r_eye + clear
        if lo_.any():
            idx = np.where(sel)[0][lo_]; Q[idx] = C + d[lo_] / rr[lo_, None] * (r_eye + clear)
    return Q


def lid_untangle(P, X0, fv, fn, ring, sg, K, C=None, r_eye=None, clear=0.0002, rounds=40, protect=(), grow=1):
    """Remove folds of a lid pose P: skin faces of side sg (all vertices on lid rings 1 .. K-1 or the margin) whose normal
    turned more than ~84 deg from rest get their vertices (and `grow` rings around; not the margin, not the tucks, not
    `protect`) relaxed: the displacement P - X0 of each such vertex moves halfway to the mean displacement of its
    neighbours (Jacobi), repeated until no fold is left (at most `rounds`). Displacements are smoothed, not positions,
    so the lid keeps its rest shape and only the fold is evened out. The eyeball floor (r_eye + clear) is kept.
    fv: flat face vertex indices, fn: vertex count per face. Returns (new P, rounds used, folds left)."""
    P = P.copy(); k = np.abs(ring); side = np.sign(ring) == sg
    starts = np.r_[0, np.cumsum(fn)[:-1]]; faces = [fv[s:s + c] for s, c in zip(starts, fn)]
    lidf = [f for f in faces if all(side[v] and 0 < k[v] <= K for v in f)]
    nb = {}
    for f in lidf:
        for i in range(len(f)):
            a_, b_ = int(f[i]), int(f[(i + 1) % len(f)]); nb.setdefault(a_, set()).add(b_); nb.setdefault(b_, set()).add(a_)
    fixed = set(np.where(side & (k >= K))[0].tolist()) | set(int(v) for v in protect)
    def normal(X, f):
        Q = X[f]; n = np.zeros(3)
        for i in range(len(f)): n += np.cross(Q[i], Q[(i + 1) % len(f)])
        return n / max(np.linalg.norm(n), 1e-18)
    N0 = [normal(X0, f) for f in lidf]
    left = 0; it = 0
    for it in range(rounds):
        bad = [f for f, n0 in zip(lidf, N0) if normal(P, f) @ n0 < 0.1]
        left = len(bad)
        if not bad: break
        vs = {int(v) for f in bad for v in f}
        for _ in range(grow): vs |= {w for v in list(vs) for w in nb.get(v, ())}
        vs = [v for v in vs if v not in fixed]
        if not vs: break
        D = P - X0
        newD = {v: 0.5 * D[v] + 0.5 * np.mean([D[w] for w in nb[v]], 0) for v in vs if v in nb}
        for v, d in newD.items(): P[v] = X0[v] + d
        if r_eye is not None and C is not None:
            d = P[vs] - C; rr = np.linalg.norm(d, axis=1); lo = rr < r_eye + clear
            if lo.any(): P[np.array(vs)[lo]] = C + d[lo] / rr[lo, None] * (r_eye + clear)
    return P, it, left


def corner_zip(P, X0, ring, u, sg, K, C, r_eye, t, edges, meet=0.62, g_lo=0.0015, g_w=0.002, decay=0.93, iters=150, reach=0.008, smooth=0):
    """Where the margin runs far above the eyeball (the caruncle wedge of the eye-fit bases: up to 8 mm above the sphere
    near the inner tip), ring_blink_canthus' eyeball hug would drag the closing lids deep into the head. There the lids
    close as a zip, linear in t (exact as a shape key):
    chord from the inner tip (u = 0.5) to the outer corner (u = 0), a = share along it; upper U(a) and lower L(a) margin
    lines; meeting point M(a) = U(a) + meet (L(a) - U(a)); every margin vertex's closed displacement Dm = M(a) - rest
    (both lines land on the same curve, so they meet edge to edge up to the tip). The skin's closed displacement Dz is
    the displacement of its nearest zone margin vertex (geodesic over the lid and face skin) times
    1 - smoothstep(g / reach), reach 8 mm: the skin round the inner corner moves with its edge as a sheet; the tucks fold short
    (30 % of their rest offset) behind their margin vertex. Zone weight: margin smoothstep((rest gap above the sphere - g_lo) / g_w) (0 on the
    eyeball part, 1 in the wedge), carried to the skin the same way. Result = (1 - W) P + W (rest + t Dz)."""
    k = np.abs(ring); m = np.sign(ring) == sg; mk = np.where(m & (k == K))[0]; um = np.mod(u[mk], 1.0)
    if t == 0 or not len(mk): return P
    i_in = mk[np.argmin(np.abs(um - 0.5))]; i_out = mk[np.argmin(np.minimum(um, 1 - um))]
    tip, oc = X0[i_in], X0[i_out]; e = oc - tip; L_ = float(np.linalg.norm(e)); e = e / L_
    a = ((X0 - tip) @ e) / L_
    g0 = np.linalg.norm(X0[mk] - C, axis=1) - r_eye; wz = np.clip((g0 - g_lo) / g_w, 0, 1); wz = wz * wz * (3 - 2 * wz)
    if wz.max() < 1e-6: return P
    up = mk[(um > 0) & (um < 0.5)]; lo = mk[um > 0.5]
    def line(ids):
        ids = np.r_[[i_in], ids, [i_out]]; o = np.argsort(a[ids]); ids = ids[o]
        return a[ids], X0[ids]
    aU, PU = line(up); aL, PL = line(lo)
    def at(aa, A_, P_): return np.stack([np.interp(aa, A_, P_[:, j]) for j in range(3)], 1)
    aa = a[mk]; Mp = at(aa, aU, PU) + meet * (at(aa, aL, PL) - at(aa, aU, PU))
    Dz = np.zeros_like(P); Dz[mk] = Mp - X0[mk]; Dz[i_in] = 0; Dz[i_out] = 0
    W = np.zeros(len(P)); W[mk] = wz
    # region: the lid skin and the face skin beyond the lid rings within `reach` (geodesic) of the zip zone's margin, on
    # this side; the harmonic extension runs over it with 0 on its outer edge, so the skin round the inner corner follows
    # the moving margin smoothly (no pinch at the lid rings' edge)
    ed = np.asarray(edges); side = (np.sign(ring) == sg) | ((ring == 0) & (X0[:, 0] * sg > 1e-6))
    keep = side[ed[:, 0]] & side[ed[:, 1]] & (k[ed[:, 0]] <= K) & (k[ed[:, 1]] <= K); ed = ed[keep]
    import heapq
    nb = {}
    for a_, b_ in ed: nb.setdefault(int(a_), []).append(int(b_)); nb.setdefault(int(b_), []).append(int(a_))
    # skin: the closed displacement of its lid's margin at the skin vertex's own chord share a (upper or lower lid by the
    # nearest zone margin vertex, geodesic) times 1 - smoothstep(g / reach): the lid skin above / below the wedge moves with its edge as a sheet and the
    # stretch spreads over `reach`, instead of piling up next to the edge
    zm = [int(v) for v, w_ in zip(mk, wz) if w_ > 0.02]; dist = {v: 0.0 for v in zm}; own = {v: v for v in zm}; h = [(0.0, v) for v in zm]
    while h:
        du, v = heapq.heappop(h)
        if du > dist[v] or du > reach: continue
        for w_ in nb.get(v, ()):
            if k[w_] >= K: continue
            nd = du + float(np.linalg.norm(X0[v] - X0[w_]))
            if nd < dist.get(w_, 1e18): dist[w_] = nd; own[w_] = own[v]; heapq.heappush(h, (nd, w_))
    sv = np.array([v for v, d_ in dist.items() if d_ > 0], int)
    if len(sv):
        g_ = np.array([dist[v] for v in sv]); o_ = np.array([own[v] for v in sv]); x_ = np.clip(g_ / reach, 0, 1); f_ = 1 - x_ * x_ * (3 - 2 * x_)
        Wm = np.zeros(len(P)); Wm[mk] = wz
        def lid_fn(ids):                                  # margin displacement / weight along a lid as functions of a
            ids = np.r_[[i_in], ids, [i_out]]; o = np.argsort(a[ids]); ids = ids[o]; return a[ids], Dz[ids], Wm[ids]
        LU_, LL_ = lid_fn(up), lid_fn(lo); upper = np.mod(u[o_], 1.0) < 0.5
        for sel_, (aa_, dd_, ww_) in ((upper, LU_), (~upper, LL_)):
            if not sel_.any(): continue
            q_ = np.clip(a[sv[sel_]], aa_[0], aa_[-1])
            Dz[sv[sel_]] = np.stack([np.interp(q_, aa_, dd_[:, j]) for j in range(3)], 1) * f_[sel_, None]
            W[sv[sel_]] = np.interp(q_, aa_, ww_) * f_[sel_]
    tk = np.where(m & (k > K))[0]
    if len(tk):
        # tuck walls of the zone: when closed they fold short (30 % of their rest offset) straight behind their margin
        # vertex (toward the eyeball centre), so no wall shows above the closed line
        jm = np.array([mk[np.argmin(np.abs(um - np.mod(u[v], 1.0)))] for v in tk]); W[tk] = W[jm]
        Mc = X0[jm] + Dz[jm]; back = C - Mc; back /= np.linalg.norm(back, axis=1, keepdims=True)
        Dz[tk] = Mc + 0.3 * (X0[tk] - X0[jm]) + back * (0.0004 * (k[tk] - K))[:, None] - X0[tk]
    Z = X0 + t * Dz
    Q = (1 - W)[:, None] * P + W[:, None] * Z
    if smooth > 0 and len(sv):
        # crease softening (canthus-wedge bases): the skin of the zip region (W > 0, outside the margin) takes the mean
        # displacement of its neighbours of the same lid `smooth` times (Jacobi, half steps); the margin, the tucks and
        # the region's outer edge keep theirs, and the tip's surroundings are eased out (none within 0.5 mm, full from
        # 2.5 mm; the skin row next to the margin from 3 to 5 mm: smoothed nearer, it folds under the closed line) ->
        # the seam between the zip sheet and the canthus rotation above the inner corner is faired
        R = np.array([v for v in sv if W[v] > 1e-4 and k[v] < K], int)
        if len(R):
            Dq = Q - X0; ri = {int(v): i for i, v in enumerate(R)}
            # upper / lower lid by the owning zone margin vertex; no averaging across the two (they meet round the tip)
            lab = {int(v): bool(up_) for v, up_ in zip(sv, np.mod(u[o_], 1.0) < 0.5)}
            lab.update({int(v): bool(uu_ < 0.5) for v, uu_ in zip(mk, um) if abs(uu_ - 0.5) > 1e-6 and min(uu_, 1 - uu_) > 1e-6})
            same = lambda a_, b_: lab.get(b_, lab[a_]) == lab[a_]
            ea = np.array([(ri[int(a_)], int(b_)) for a_, b_ in ed if int(a_) in ri and same(int(a_), int(b_))] +
                          [(ri[int(b_)], int(a_)) for a_, b_ in ed if int(b_) in ri and same(int(b_), int(a_))], int)
            cnt = np.bincount(ea[:, 0], minlength=len(R)).astype(float)
            ok_ = cnt > 0; dt_ = np.linalg.norm(X0[R] - tip, axis=1); r1 = k[R] == K - 1               # the row next to the margin: from 3 mm
            xt = np.clip(np.where(r1, (dt_ - 0.003) / 0.002, (dt_ - 0.0005) / 0.002), 0, 1); bw = 0.5 * xt * xt * (3 - 2 * xt)
            for _ in range(int(smooth)):
                acc = np.zeros((len(R), 3)); np.add.at(acc, ea[:, 0], Dq[ea[:, 1]])
                Dq[R[ok_]] = (1 - bw[ok_, None]) * Dq[R[ok_]] + bw[ok_, None] * acc[ok_] / cnt[ok_, None]
            Q[R] = X0[R] + Dq[R]
    zz = np.where(m & (W > 1e-6))[0]                          # keep the zone off the eyeball (tuck walls of the wedge)
    if len(zz):
        d = Q[zz] - C; rr = np.linalg.norm(d, axis=1); fl = np.where(k[zz] > K, 0.0003, 0.0002); lo_ = rr < r_eye + fl
        if lo_.any(): Q[zz[lo_]] = C + d[lo_] / rr[lo_, None] * (r_eye + fl[lo_])[:, None]
    return Q

def lid_seal(P, ring, u, sg, K, edges, rounds=6, iters=12):
    """Closed lids (t = 1): the upper and lower margin lines meet edge to edge. Each upper margin vertex and the lower line
    (and vice versa) move halfway toward each other's nearest point, a few rounds; the corners stay; tucks take their
    margin vertex's correction, the lid skin the correction diffused (Jacobi, iters steps, decay 0.8). Returns new P."""
    k = np.abs(ring); m = np.sign(ring) == sg; mk = np.where(m & (k == K))[0]; um = np.mod(u[mk], 1.0)
    cor = (np.abs(um) < 1e-9) | (np.abs(um - 0.5) < 1e-9) | (np.abs(um - 1) < 1e-9)
    i_c = mk[cor]; up = mk[(um > 0) & (um < 0.5)]; lo = mk[um > 0.5]
    o_u = up[np.argsort(um[(um > 0) & (um < 0.5)])]; o_l = lo[np.argsort(-um[um > 0.5])]
    c0 = mk[np.argmin(np.minimum(um, 1 - um))]; c5 = mk[np.argmin(np.abs(um - 0.5))]
    LU = np.r_[[c0], o_u, [c5]]; LL = np.r_[[c0], o_l, [c5]]
    Q = P.copy()
    def nearest_on(Pt, line):
        A_, B_ = Q[line[:-1]], Q[line[1:]]; AB = B_ - A_; ll = np.maximum((AB * AB).sum(1), 1e-18)
        tt = np.clip(((Pt[:, None] - A_[None]) * AB[None]).sum(2) / ll[None], 0, 1); R_ = A_[None] + tt[..., None] * AB[None]
        d = np.linalg.norm(Pt[:, None] - R_, axis=2); j = d.argmin(1); return R_[np.arange(len(Pt)), j]
    corr = np.zeros_like(P)
    for _ in range(rounds):
        nu = nearest_on(Q[o_u], LL); nl = nearest_on(Q[o_l], LU)
        du = 0.5 * (nu - Q[o_u]); dl = 0.5 * (nl - Q[o_l])
        Q[o_u] += du; Q[o_l] += dl; corr[o_u] += du; corr[o_l] += dl
    tk = np.where(m & (k > K))[0]
    if len(tk):
        jm = np.array([mk[np.argmin(np.abs(um - np.mod(u[v], 1.0)))] for v in tk]); corr[tk] = corr[jm]; Q[tk] = P[tk] + corr[tk]
    ed = np.asarray(edges); sk = m & (k > 0) & (k < K)
    keep = sk[ed[:, 0]] | sk[ed[:, 1]]; ed = ed[keep]; cs = corr.copy()
    for _ in range(iters):
        acc = np.zeros_like(P); cnt = np.zeros(len(P))
        np.add.at(acc, ed[:, 0], cs[ed[:, 1]]); np.add.at(acc, ed[:, 1], cs[ed[:, 0]]); np.add.at(cnt, ed[:, 0], 1); np.add.at(cnt, ed[:, 1], 1)
        f_ = sk & (cnt > 0); cs[f_] = 0.8 * acc[f_] / cnt[f_, None]
    Q[sk] = P[sk] + cs[sk]
    return Q
