"""Helpers of loop_organs.py (cut along existing loops): mesh graph, the closed edge cycle that follows a lid rim,
the corner-to-corner lip seam path, BFS rings, loop parameters, strip triangulation between two polylines.
Nothing here moves a vertex of the input mesh: cycles and paths are made of existing edges, rings are sets of
existing vertices."""
import heapq, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree

YUP_TO_ZUP = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])     # (x, y, z) -> (x, -z, y): Y-up import -> our frame


def landmark_fit(X, faces, P):
    """median / max distance (m) from points P to the surface (X, faces)"""
    bvh = BVHTree.FromPolygons([tuple(p) for p in X], faces)
    d = np.array([bvh.find_nearest(Vector(tuple(p)))[3] for p in P])
    return float(np.median(d)), float(d.max())


def mirror_partners(X, tol=1e-6):
    """index of the vertex at the mirror image (x -> -x) of each vertex, and the gap"""
    kd = KDTree(len(X))
    for i, p in enumerate(X): kd.insert(Vector(tuple(p)), i)
    kd.balance()
    part = np.full(len(X), -1); gap = np.zeros(len(X))
    for i, p in enumerate(X):
        _, j, d = kd.find(Vector((-p[0], p[1], p[2]))); part[i] = j; gap[i] = d
    return part, gap


def polyline_dist(P, L, closed=True):
    """distance from each point of P (n, 3) to the polyline L (m, 3)"""
    A = L if closed else L[:-1]; B = np.roll(L, -1, 0) if closed else L[1:]
    AB = B - A; ll = np.maximum((AB * AB).sum(1), 1e-18)
    out = np.empty(len(P))
    for s in range(0, len(P), 2048):
        Q = P[s:s + 2048]; t = np.clip(((Q[:, None] - A[None]) * AB[None]).sum(2) / ll[None], 0, 1)
        out[s:s + 2048] = np.linalg.norm(Q[:, None] - (A[None] + t[..., None] * AB[None]), axis=2).min(1)
    return out


class Graph:
    """edge graph of a bmesh (indices valid until the next topology change)"""
    def __init__(self, bm):
        bm.verts.index_update(); bm.edges.index_update(); bm.faces.index_update()
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
        self.bm = bm; self.n = len(bm.verts)
        self.X = np.array([tuple(v.co) for v in bm.verts])
        self.ev = np.array([(e.verts[0].index, e.verts[1].index) for e in bm.edges], dtype=np.int64).reshape(-1, 2)
        self.ef = [frozenset(f.index for f in e.link_faces) for e in bm.edges]
        self.nbr = [[(e.other_vert(v).index, e.index) for e in v.link_edges] for v in bm.verts]
        self.val = np.array([len(v.link_edges) for v in bm.verts])
        self.elen = np.linalg.norm(self.X[self.ev[:, 0]] - self.X[self.ev[:, 1]], axis=1) if len(self.ev) else np.zeros(0)

    def straight(self, e_in, v, e_out):
        """an edge loop goes straight through a valence-4 vertex: in and out edge share no face"""
        return self.val[v] == 4 and not (self.ef[e_in] & self.ef[e_out])


def dijkstra_turn(G, sources, ecost, mask, turn_pen, cross=None, goal=None, max_cost=np.inf):
    """Shortest walk on directed-edge states (vertex, incoming edge[, sheet]): cost = sum of ecost[e] plus turn_pen
    at every vertex where the walk does not go straight along an edge loop (half of it at poles: valence != 4).
    cross[e] (0/1): the edge crosses a seam line; the state carries the parity, so a goal with sheet 1 is reached
    only by a walk that winds round once. goal(v, sheet) -> bool ends the search.
    Returns (cost, vertex list) of the best walk to a goal, or the dist / prev maps when goal is None."""
    dist, prev, h = {}, {}, []
    for s in sources:
        st = (s, -1, 0); dist[st] = 0.0; heapq.heappush(h, (0.0, s, -1, 0))
    while h:
        d, v, ein, sh = heapq.heappop(h)
        if d > dist.get((v, ein, sh), np.inf) or d > max_cost: continue
        if goal is not None and ein >= 0 and goal(v, sh):
            path = [v]; st = (v, ein, sh)
            while st in prev: st = prev[st]; path.append(st[0])
            return d, path[::-1]
        for w, e in G.nbr[v]:
            if e == ein or not mask[w]: continue
            c = ecost[e]
            if ein >= 0 and not G.straight(ein, v, e): c += turn_pen * (1.0 if G.val[v] == 4 else 0.5)
            sh2 = sh ^ (int(cross[e]) if cross is not None else 0); st2 = (w, e, sh2); nd = d + c
            if nd < dist.get(st2, np.inf):
                dist[st2] = nd; prev[st2] = (v, ein, sh); heapq.heappush(h, (nd, w, e, sh2))
    if goal is not None: return np.inf, None
    return dist, prev


def eye_cycle(G, mask, rim_d, theta, sigma, turn_pen):
    """Closed edge cycle round the eye: minimal sum over its edges of length * (1 + (rim distance / sigma)^2) plus
    the turn penalty (prefers real edge loops; turning at poles is cheaper). theta: angle of each vertex round the
    opening centre measured from a seam half-line; an edge whose endpoint angles differ by more than pi crosses it.
    A walk from a seam-edge endpoint back to itself with odd parity winds round the opening once.
    Returns (cost, vertex cycle without the repeated start)."""
    a, b = G.ev[:, 0], G.ev[:, 1]
    dm = (rim_d[a] + rim_d[b]) / 2
    ecost = G.elen * (1 + (dm / sigma) ** 2)
    ok = mask[a] & mask[b]
    cross = (np.abs(theta[a] - theta[b]) > np.pi) & ok
    seeds = sorted({int(v) for e in np.where(cross)[0] for v in G.ev[e]}, key=lambda v: rim_d[v])[:12]
    best = (np.inf, None)
    for s in seeds:
        c, path = dijkstra_turn(G, [s], ecost, mask, turn_pen, cross=cross, goal=lambda v, sh, s=s: v == s and sh == 1,
                                max_cost=best[0])
        if path is not None and c < best[0]: best = (c, path[:-1])
    return best


def simple_cycle(cyc):
    """drop the shorter lobe wherever the cycle visits a vertex twice"""
    cyc = list(cyc)
    while True:
        seen = {}; rep = None
        for i, v in enumerate(cyc):
            if v in seen: rep = (seen[v], i); break
            seen[v] = i
        if rep is None: return cyc
        i, j = rep; inner = cyc[i:j]; outer = cyc[:i] + cyc[j:]          # cyc[i] is cyc[j]: kept once in each
        cyc = inner if len(inner) >= len(outer) else outer


def boundary_loops(bm):
    """closed boundary edge loops as lists of BMVerts"""
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
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
    return loops


def flood_faces(seed, blocked):
    """faces reached from seed without crossing an edge in `blocked` (a set of BMEdges)"""
    comp, stack = set(), [seed]
    while stack:
        f = stack.pop()
        if f in comp: continue
        comp.add(f)
        for e in f.edges:
            if e in blocked: continue
            for g in e.link_faces:
                if g not in comp: stack.append(g)
    return comp


def bfs(G, seeds, mask, dmax):
    """topological distance (edges) from the seed vertices, over vertices in mask, up to dmax"""
    d = np.full(G.n, -1); fr = list(seeds)
    for s in fr: d[s] = 0
    k = 0
    while fr and k < dmax:
        k += 1; nf = []
        for v in fr:
            for w, _ in G.nbr[v]:
                if d[w] < 0 and mask[w]: d[w] = k; nf.append(w)
        fr = nf
    return d


def arc_param(P, closed=False):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.r_[P, P[:1]] if closed else P, axis=0), axis=1))]
    return s


def periodic_interp(x, xp, fp, period=1.0):
    """linear interpolation of a periodic function given at increasing knots xp in [0, period)"""
    xp = np.asarray(xp, float); fp = np.asarray(fp, float)
    X = np.r_[xp[-1] - period, xp, xp[0] + period]; F = np.r_[fp[-1], fp, fp[0]]
    return np.interp(np.mod(np.asarray(x, float) - X[1], period) + X[1], X, F)


def strip(bm, A, ua, B, ub):
    """triangles between two open polylines A (ua increasing) and B (ub increasing) that start and end together,
    merged by parameter (each step advances the side whose next vertex comes first). Returns the faces as vertex
    triples (A, A, B) / (A, B, B) in a fixed winding; the caller orients them."""
    i = j = 0; out = []
    while i < len(A) - 1 or j < len(B) - 1:
        if j >= len(B) - 1 or (i < len(A) - 1 and ua[i + 1] <= ub[j + 1]): out.append((A[i], A[i + 1], B[j])); i += 1
        else: out.append((A[i], B[j + 1], B[j])); j += 1
    return out


def winding_vs(face_verts, a, b):
    """+1 if the face loop runs a -> b, -1 if b -> a, 0 if a, b are not consecutive"""
    n = len(face_verts)
    for i in range(n):
        if face_verts[i] == a and face_verts[(i + 1) % n] == b: return 1
        if face_verts[i] == b and face_verts[(i + 1) % n] == a: return -1
    return 0


def sphere_fit(P):
    """least-squares sphere through points P: centre, radius"""
    A = np.c_[2 * P, np.ones(len(P))]; b = (P * P).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]; C = x[:3]; r = math.sqrt(max(x[3] + C @ C, 0))
    return C, r


def smoothstep(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


def edge_loop_walk(G, e0, v0):
    """vertices of the edge loop through edge e0 walked away from v0 (straight across valence-4 vertices).
    Returns (vertex list, closed?)"""
    a_, b_ = int(G.ev[e0, 0]), int(G.ev[e0, 1]); prev_v, cur = (a_, b_) if a_ == v0 else (b_, a_); e = e0
    out = [prev_v]; seen = {e0}
    while True:
        out.append(cur)
        if G.val[cur] != 4: return out, False
        nxt = [(w, f) for w, f in G.nbr[cur] if f != e and not (G.ef[f] & G.ef[e])]
        if len(nxt) != 1: return out, False
        w, f = nxt[0]
        if f == e0: return out[:-1], True
        if f in seen: return out, False
        seen.add(f); e = f; cur = w


def closed_loops_around(G, emask, theta):
    """closed edge loops (true quad loops) through the edges in emask that wind round the opening once
    (theta: vertex angle from a seam half-line, as eye_cycle). Returns a list of vertex cycles."""
    done, out = set(), []
    for e0 in np.where(emask)[0]:
        if e0 in done: continue
        cyc, closed = edge_loop_walk(G, int(e0), int(G.ev[e0, 0]))
        if not closed: done.add(int(e0)); continue
        es = {next(e for w_, e in G.nbr[cyc[i]] if w_ == cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))}
        done |= es
        th = theta[cyc]; cross = int(np.sum(np.abs(np.diff(np.r_[th, th[:1]])) > np.pi))
        if cross % 2 == 1 and len(set(cyc)) == len(cyc): out.append(list(cyc))
    return out


def inside_poly(P, Q):
    """points P (n, 2) inside the closed polygon Q (m, 2) (even-odd rule)"""
    x, y = P[:, :1], P[:, 1:2]; x1, y1 = Q[None, :, 0], Q[None, :, 1]; x2, y2 = np.roll(Q[:, 0], -1)[None], np.roll(Q[:, 1], -1)[None]
    c = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / np.where(y2 == y1, 1e-30, y2 - y1) + x1)
    return (c.sum(1) % 2) == 1


def bowtie_verts(bm):
    """vertices whose faces do not form one edge-connected fan (non-manifold 'bow-tie' vertices), as a bool array"""
    bm.verts.index_update(); out = np.zeros(len(bm.verts), bool)
    for v in bm.verts:
        fs = set(v.link_faces)
        if len(fs) < 2: continue
        seen, st = set(), [next(iter(fs))]
        while st:
            f = st.pop()
            if f in seen: continue
            seen.add(f)
            for e in f.edges:
                if v in e.verts:
                    for g in e.link_faces:
                        if g in fs and g not in seen: st.append(g)
        out[v.index] = len(seen) != len(fs)
    return out
