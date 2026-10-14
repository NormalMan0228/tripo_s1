"""Cut a lip seam into the closed-mouth clean head: the lips stay where they are but become separable.

The lip line is the deepest front valley between the lips: per x column, front rays over z find the local depth maximum
between the two lip bulges (searched near the previous column's z, starting at the centre).  The seam is the cheapest
vertex path from corner to corner (Dijkstra; cost = edge length x (1 + K*frontness) + distance to the valley curve),
symmetrised, then split (edges duplicated) except at the two corner vertices.
Usage: blender --background head_clean.blend --python lip_seam.py -- <out.blend>
"""
import bpy, bmesh, sys, os, json, math, heapq
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
head = bpy.data.objects["Head"]; me = head.data
X = np.array([v.co[:] for v in me.vertices]); n = len(X)
T = BVHTree.FromPolygons([tuple(p) for p in X], [tuple(p.vertices) for p in me.polygons])
rep = {}
VALLEY = float(os.environ.get("VALLEY", 0.0008))


def depth(x, z):
    h = T.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)), 5)
    return h[0].y if h[0] is not None else np.nan


# centre column profile: lips are the two most-forward bulges below the nose; valley between them
ZS = np.arange(0.36, 0.52, 0.0005)
prof = np.array([depth(0.0, z) for z in ZS])
lips_band = (ZS > 0.40) & (ZS < 0.50)
# local maxima of depth (valleys) inside the band, take the one between the two forward-most bulges
cand = [i for i in range(2, len(ZS) - 2) if lips_band[i] and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]
        and prof[i] > min(prof[max(0, i - 30):i].min(), prof[i + 1:i + 31].min()) + 0.0015]
zc = float(ZS[max(cand, key=lambda i: prof[i] - 0.5 * (prof[max(0, i - 30):i].min() + prof[i + 1:i + 31].min()))])
rep["centre_valley_z"] = zc
line = {0.0: zc}
for sgn in (1, -1):
    z = zc; x = 0.0
    while True:
        x += sgn * 0.002
        zz = np.arange(z - 0.006, z + 0.006, 0.0004)
        dd = np.array([depth(x, q) for q in zz])
        if np.all(np.isnan(dd)): break
        i = int(np.nanargmax(dd))
        lo = np.nanmin(dd[:max(1, i - 3)]) if i > 3 else np.nan     # lower lip bulge
        hi = np.nanmin(dd[i + 4:]) if i + 4 < len(dd) else np.nan   # upper lip bulge
        if not (dd[i] - lo > VALLEY and dd[i] - hi > VALLEY) or abs(x) > 0.14: break   # a lip on both sides, else corner
        z = float(zz[i]); line[x] = z
xs = np.array(sorted(line)); zs = np.array([line[k] for k in xs])
corner = float(min(abs(xs.min()), abs(xs.max())))
rep["corner_x"] = corner; rep["valley_points"] = len(xs)
# symmetric valley curve
zsym = np.interp(np.abs(xs), np.abs(xs[xs >= 0]), zs[xs >= 0]) * 0.5 + np.interp(np.abs(xs), np.abs(xs[xs <= 0])[::-1], zs[xs <= 0][::-1]) * 0.5


def zline(x):
    return float(np.interp(abs(x), np.abs(xs[xs >= 0]), zsym[xs >= 0]))


# surface points on the valley curve
pts = []
for x in np.arange(-corner, corner + 1e-9, 0.002):
    z = zline(x); y = depth(x, z); pts.append((x, y, z))
pts = np.array(pts)
kd = KDTree(n)
for i, p in enumerate(X): kd.insert(p, i)
kd.balance()
v_start = kd.find(pts[0])[1]; v_end = kd.find(pts[-1])[1]
# Dijkstra restricted to the mouth region
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
region = (np.abs(X[:, 0]) < corner + 0.015) & (np.abs(X[:, 2] - zc) < 0.06) & (X[:, 1] < -0.06)
ptree = KDTree(len(pts))
for i, p in enumerate(pts): ptree.insert(p, i)
ptree.balance()
dcurve = np.array([ptree.find(p)[2] if region[i] else 1.0 for i, p in enumerate(X)])
front = np.nan_to_num(np.array([X[i, 1] for i in range(n)]))
yref = np.interp(X[:, 0], pts[:, 0], pts[:, 1])
K = 300.0
dist = {v_start: 0.0}; prev = {}; pq = [(0.0, v_start)]
while pq:
    d, u = heapq.heappop(pq)
    if u == v_end: break
    if d > dist.get(u, 1e9): continue
    for e in bm.verts[u].link_edges:
        w = e.other_vert(bm.verts[u]).index
        if not region[w]: continue
        L = e.calc_length()
        fr = max(0.0, yref[w] - X[w, 1])                     # in front of the valley floor -> expensive
        c = L * (1 + K * fr) + L * 40 * dcurve[w]
        nd = d + c
        if nd < dist.get(w, 1e9): dist[w] = nd; prev[w] = u; heapq.heappush(pq, (nd, w))
path = [v_end]
while path[-1] != v_start: path.append(prev[path[-1]])
path = path[::-1]
rep["seam_verts"] = len(path)
# symmetrise: keep the +X half of the path and mirror it (vertices are exactly mirrored in the symmetric mesh)
mir = {}
for i in path:
    mir[i] = kd.find((-X[i, 0], X[i, 1], X[i, 2]))[1]
half = [i for i in path if X[i, 0] >= -1e-7]
full = set(half) | {mir[i] for i in half}
# rebuild an ordered path through `full` by shortest path inside it
sub = {i: [e.other_vert(bm.verts[i]).index for e in bm.verts[i].link_edges if e.other_vert(bm.verts[i]).index in full] for i in full}
v_start = min(full, key=lambda i: X[i, 0]); v_end = max(full, key=lambda i: X[i, 0])
order = [v_start]; seen = {v_start}
while order[-1] != v_end:
    nx = [j for j in sub[order[-1]] if j not in seen]
    if not nx: break
    j = max(nx, key=lambda j: X[j, 0]); order.append(j); seen.add(j)
rep["seam_symmetric_ok"] = order[-1] == v_end
path = order if rep["seam_symmetric_ok"] else path
edges = []
for a_, b_ in zip(path[:-1], path[1:]):
    e = bm.edges.get((bm.verts[a_], bm.verts[b_]))
    if e: edges.append(e)
rep["seam_edges"] = len(edges)
rep["seam_y_range"] = [float(X[path, 1].min()), float(X[path, 1].max())]
bmesh.ops.split_edges(bm, edges=edges)
bm.to_mesh(me); bm.free(); me.update()
vg = head.vertex_groups.get("lip_seam") or head.vertex_groups.new(name="lip_seam")
# after the split the seam verts are duplicated: tag every vertex lying on the path positions
Xn = np.array([v.co[:] for v in me.vertices])
kd2 = KDTree(len(Xn))
for i, p in enumerate(Xn): kd2.insert(p, i)
kd2.balance()
tag = set()
for i in path:
    for (_, j, d) in kd2.find_range(X[i], 1e-7): tag.add(j)
vg.add(sorted(tag), 1.0, 'REPLACE')
bm = bmesh.new(); bm.from_mesh(me)
rep["boundary_edges"] = sum(1 for e in bm.edges if e.is_boundary)
rep["nonmanifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.free()
head["lip_line_z_centre"] = zc; head["mouth_corner_x"] = corner
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("SEAM", json.dumps(rep))
