"""Clean high-res head (wrap input) from a Tripo HD candidate.

1. exact symmetry: symmetrize +X onto -X, decimate (symmetric) to ~TARGET faces, symmetrize again
2. denoise: weighted Taubin smoothing (non-shrinking); flat areas smoothed, creases (lids, lips, nostrils, ears) kept;
   a long masked Taubin run removes low-frequency lumps on the cranium (above the brows, back of head; ears excluded)
3. eyes: joint mirrored sphere fit of the fused eyeball caps (shared radius); the cap is flood-filled from its front over
   vertices near the ball with radial normals (stops at the lid groove) and removed, so Tripo's own lid margin and its
   inner wall stay; lid vertices inside R + GAP are pushed out; the margin loop is relaxed and laid on the ball at R + GAP;
   a short lining (RING rows) continues from the margin along the ball into the socket
4. final symmetrize; Eye.L / Eye.R UV spheres (origin = rotation centre)
Usage: blender --background <candidates.blend> --python hd_clean.py -- <object prefix> <out.blend>
   or: blender --background --python hd_clean.py -- <tripo.glb> <out.blend>
Writes <out>.blend and <out>_report.json.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
PREFIX, OUT = a[0], os.path.abspath(a[1])
TARGET = int(os.environ.get("TARGET", 400000))
CAP_TOL = float(os.environ.get("CAP_TOL", 0.0035))  # cap vertices: |r - R| below this ...
CAP_DOT = float(os.environ.get("CAP_DOT", 0.85))    # ... and normal close to radial
CLEAR = float(os.environ.get("CLEAR", 0.0012))      # plus everything inside R + CLEAR within the eye's front cone
CONE_DEG = float(os.environ.get("CONE_DEG", 80))
TRIM_DEG = float(os.environ.get("TRIM_DEG", 1.0))   # margin tongues deeper than this (deg) into the opening are trimmed
GAP = float(os.environ.get("GAP", 0.0003))          # lid margin / lining distance from the ball
RING = int(os.environ.get("RING", 0))   # 0: a sphere eyeball keeps the 0.3 mm margin gap at any rotation; RING_DEG = float(os.environ.get("RING_DEG", 4.0))
rep = {}

if PREFIX.lower().endswith(".glb"):          # import a Tripo GLB directly (same normalisation as import_candidates.py)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(PREFIX))
    ms = [o for o in bpy.data.objects if o.type == 'MESH']
    for o in ms:
        mw = o.matrix_world.copy(); o.parent = None; o.data.transform(mw); o.matrix_world = Matrix()
    P_ = np.concatenate([[v.co[:] for v in o.data.vertices] for o in ms]); mn, mx = P_.min(0), P_.max(0); sc_ = 1.0 / (mx[2] - mn[2])
    Tn = Matrix.Rotation(-math.pi / 2, 4, 'Z') @ Matrix.Translation((-(mn[0] + mx[0]) / 2 * sc_, -(mn[1] + mx[1]) / 2 * sc_, -mn[2] * sc_)) @ Matrix.Scale(sc_, 4)
    for o in ms: o.data.transform(Tn)
    P_ = np.concatenate([[v.co[:] for v in o.data.vertices] for o in ms]); mn, mx = P_.min(0), P_.max(0)
    for o in ms: o.data.transform(Matrix.Translation((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2])))
    src = max(ms, key=lambda o: len(o.data.vertices))
else:
    src = [o for o in bpy.data.objects if o.name.startswith(PREFIX) and o.type == 'MESH'][0]
me = src.data.copy(); me.transform(src.matrix_world)
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
head = bpy.data.objects.new("Head", me); bpy.context.scene.collection.objects.link(head)
bpy.context.view_layer.objects.active = head; head.select_set(True)
rep["faces_in"] = len(me.polygons)


def symmetrize():
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.symmetrize(direction='POSITIVE_X', threshold=1e-5)
    bpy.ops.mesh.remove_doubles(threshold=1e-6)
    bpy.ops.object.mode_set(mode='OBJECT')


def fix_defects(max_hole=16):
    bm = bmesh.new(); bm.from_mesh(me)
    bad = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
    faces = {f for e in bad for f in e.link_faces}
    n_bad = len(bad)
    if faces: bmesh.ops.delete(bm, geom=list(faces), context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=max_hole)
    bm.to_mesh(me); bm.free(); me.update()
    return n_bad


symmetrize(); rep["nonmanifold_fixed_1"] = fix_defects()
mod = head.modifiers.new("dec", 'DECIMATE'); mod.ratio = min(1.0, TARGET / len(me.polygons)); mod.use_symmetry = True; mod.symmetry_axis = 'X'
bpy.ops.object.modifier_apply(modifier="dec")
symmetrize(); rep["nonmanifold_fixed_2"] = fix_defects()
rep["faces_decimated"] = len(me.polygons)

# ---------------- denoise (weighted Taubin)
def arrays():
    X = np.array([v.co[:] for v in me.vertices]); E = np.array([e.vertices[:] for e in me.edges]); return X, E


X, E = arrays(); n = len(X)
deg = np.zeros(n); np.add.at(deg, E[:, 0], 1); np.add.at(deg, E[:, 1], 1); deg = np.maximum(deg, 1)


def lap(X):
    acc = np.zeros_like(X); np.add.at(acc, E[:, 0], X[E[:, 1]]); np.add.at(acc, E[:, 1], X[E[:, 0]])
    return acc / deg[:, None] - X


me.calc_normals() if hasattr(me, "calc_normals") else None
N = np.array([v.normal[:] for v in me.vertices])
el = np.linalg.norm(X[E[:, 0]] - X[E[:, 1]], axis=1); h = np.zeros(n); np.add.at(h, E[:, 0], el); np.add.at(h, E[:, 1], el); h /= deg
curv = np.abs((lap(X) * N).sum(1)) / np.maximum(h, 1e-9)          # ~ mean curvature * edge length (dimensionless)
H0 = float(os.environ.get("CURV_KEEP", 0.08))
w = np.clip(1 - curv / H0, 0, 1)
for _ in range(2):                                                # spread the protection a little
    acc = np.zeros(n); np.add.at(acc, E[:, 0], w[E[:, 1]]); np.add.at(acc, E[:, 1], w[E[:, 0]]); w = np.minimum(w, acc / deg + 0.25)
w = np.clip(w, 0, 1)
# isolated pits / spikes: high curvature with mostly flat surroundings (2-ring) -> fully smoothed
hi = (curv > H0).astype(float)
ring = hi.copy()
for _ in range(3):
    acc = np.zeros(n); np.add.at(acc, E[:, 0], ring[E[:, 1]]); np.add.at(acc, E[:, 1], ring[E[:, 0]]); ring = acc / deg
iso = (hi > 0) & (ring < float(os.environ.get("PIT_RING", 0.25)))
isom = iso.astype(float)
for _ in range(2):
    acc = np.zeros(n); np.add.at(acc, E[:, 0], isom[E[:, 1]]); np.add.at(acc, E[:, 1], isom[E[:, 0]]); isom = np.maximum(isom, (acc > 0).astype(float))
w = np.maximum(w, isom)
rep["isolated_pits_smoothed"] = int(iso.sum())
X0 = X.copy()
for _ in range(int(os.environ.get("TAUBIN_IT", 20))):
    X = X + 0.5 * w[:, None] * lap(X)
    X = X - 0.53 * w[:, None] * lap(X)
# cranium: low-frequency lumps (hair will cover it) -> long Taubin run masked to the skull above the brows / back of head
def smoothstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
yb = smoothstep(X0[:, 1], -0.10, 0.10)                               # 0 = front, 1 = back
mz = (1 - yb) * smoothstep(X0[:, 2], 0.80, 0.86) + yb * smoothstep(X0[:, 2], 0.55, 0.66)
ear = (np.abs(X0[:, 0]) > 0.20) & (X0[:, 2] < 0.80) & (X0[:, 2] > 0.45)
mz[ear] = 0
# smooth cranium: r(u) about a head centre fitted with a degree-CRANIUM_DEG polynomial in the unit direction u
# (same span as spherical harmonics up to that degree), weighted to a slightly wider region, blended in by mz
from itertools import combinations_with_replacement
DEG = int(os.environ.get("CRANIUM_DEG", 10))
c0 = np.array([0.0, 0.02, 0.62])
D = X - c0; rr = np.linalg.norm(D, axis=1); U = D / rr[:, None]
mfit = np.clip((1 - yb) * smoothstep(X0[:, 2], 0.74, 0.82) + yb * smoothstep(X0[:, 2], 0.48, 0.60), 0, 1); mfit[ear] = 0
fi = np.where(mfit > 0.05)[0]
fi = fi[np.random.default_rng(1).choice(len(fi), min(40000, len(fi)), replace=False)]
terms = [()] + [c for d in range(1, DEG + 1) for c in combinations_with_replacement(range(3), d)]
def basis(Uu):
    return np.stack([np.prod(Uu[:, list(t)], axis=1) if t else np.ones(len(Uu)) for t in terms], 1)
A = basis(U[fi]) * mfit[fi, None]
coef = np.linalg.lstsq(A, rr[fi] * mfit[fi], rcond=None)[0]
mi = np.where(mz > 1e-4)[0]
rfit = basis(U[mi]) @ coef
X[mi] = c0 + U[mi] * ((1 - mz[mi]) * rr[mi] + mz[mi] * rfit)[:, None]
rep["cranium_fit_terms"] = len(terms); rep["cranium_fit_move_mm_max"] = float(np.abs(rfit - rr[mi]).max() * 1000)
me.vertices.foreach_set("co", X.ravel()); me.update()
rep["denoise_move_mm"] = {"median": float(np.median(np.linalg.norm(X - X0, axis=1)) * 1000), "max": float(np.linalg.norm(X - X0, axis=1).max() * 1000)}
rep["denoise_protected_share"] = float((w < 0.5).mean())
mv = np.linalg.norm(X - X0, axis=1); rep["denoise_max_at"] = X0[int(np.argmax(mv))].round(3).tolist()
rep["denoise_move_p999_mm"] = float(np.percentile(mv, 99.9) * 1000)

# ---------------- eyes: joint mirrored sphere fit
rng = np.random.default_rng(0)


def fit4(Q):
    A = np.c_[2 * Q, np.ones(len(Q))]; b = (Q ** 2).sum(1); s = np.linalg.lstsq(A, b, rcond=None)[0]
    c = s[:3]; return c, math.sqrt(max(s[3] + c @ c, 0))


m = (X[:, 0] > 0.04) & (X[:, 0] < 0.26) & (X[:, 2] > 0.48) & (X[:, 2] < 0.75) & (X[:, 1] < -0.10)
Q = X[m]; best = None
for _ in range(4000):
    c, R = fit4(Q[rng.choice(len(Q), 4, replace=False)])
    if not (0.05 < R < 0.13): continue
    inl = np.abs(np.linalg.norm(Q - c, axis=1) - R) < 0.0012
    if best is None or inl.sum() > best[0]: best = (inl.sum(), c, R, inl)
_, c, R, inl = best
for _ in range(5):
    c, R = fit4(Q[inl]); inl = np.abs(np.linalg.norm(Q - c, axis=1) - R) < 0.0010
c[0] = abs(c[0])
res = np.linalg.norm(Q[inl] - c, axis=1) - R
rep["eye"] = {"centre_L": c.round(5).tolist(), "R": round(R, 5), "inliers": int(inl.sum()), "fit_rms_mm": float(np.sqrt((res ** 2).mean()) * 1000)}
EYES = {"L": c.copy(), "R": c * [-1, 1, 1]}

# eyeball cap = surface reached from the cap front over radial-normal vertices near the ball; stops at the lid groove
me.update(); Nn = np.array([v.normal[:] for v in me.vertices])
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
dele = set(); rep["eye_cap_verts"] = {}
for s_, ce in EYES.items():
    r = np.linalg.norm(X - ce, axis=1); radial = ((X - ce) * Nn).sum(1) / np.maximum(r, 1e-9)
    ok = (np.abs(r - R) < CAP_TOL) & (radial > CAP_DOT)
    front = ce + np.array([0, -R, 0])
    seed = int(np.argmin(np.linalg.norm(X - front, axis=1) + 10 * ~ok))
    seen = {seed}; st = [seed]
    while st:
        i = st.pop()
        for e in bm.verts[i].link_edges:
            j = e.other_vert(bm.verts[i]).index
            if j not in seen and ok[j]: seen.add(j); st.append(j)
    # Tripo's eye is a lens pocket: front cap on the sphere + back wall inside it. Also take everything inside the
    # ball (plus CLEAR shell) within the front cone of the eye.
    ax = np.array([0, -1.0, 0]); cosang = ((X - ce) @ ax) / np.maximum(r, 1e-9)
    inside = (r < R + CLEAR) & (cosang > math.cos(math.radians(CONE_DEG)))
    seen |= set(np.where(inside)[0].tolist())
    rep["eye_cap_verts"][s_] = len(seen)
    for i in seen:
        for f in bm.verts[i].link_faces: dele.add(f.index)
rep["eye_faces_removed"] = len(dele)
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in dele], context='FACES')
loose = [v for v in bm.verts if not v.link_faces]; bmesh.ops.delete(bm, geom=loose, context='VERTS')
# keep the main shell only (drop small islands left inside the sockets)
bm.verts.ensure_lookup_table()
comp = {}; cid = 0
for v in bm.verts:
    if v.index in comp: continue
    st = [v]; comp[v.index] = cid
    while st:
        u = st.pop()
        for e in u.link_edges:
            w_ = e.other_vert(u)
            if w_.index not in comp: comp[w_.index] = cid; st.append(w_)
    cid += 1
sizes = np.bincount(list(comp.values())); main = int(np.argmax(sizes))
bmesh.ops.delete(bm, geom=[v for v in bm.verts if comp[v.index] != main], context='VERTS')
rep["islands_dropped"] = int(cid - 1)
# small holes left by the cut (not the eye openings) are filled; dangling flaps (faces with >= 2 boundary edges) trimmed
for _ in range(3):
    flaps = [f for f in bm.faces if sum(1 for e in f.edges if e.is_boundary) >= 2]
    if not flaps: break
    bmesh.ops.delete(bm, geom=flaps, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=24)
# opening outline regularisation: in angular coords about the gaze axis (theta around, phi from axis) the margin
# phi(theta) must be smooth; tongues of lid hanging into the opening (phi below the rolling median) are trimmed
def angular(p, ce):
    d = np.asarray(p) - ce; r = np.linalg.norm(d, axis=-1)
    phi = np.degrees(np.arccos(np.clip(-d[..., 1] / np.maximum(r, 1e-12), -1, 1)))
    th = np.degrees(np.arctan2(d[..., 2], d[..., 0])); return th, phi, r
trimmed = 0
for _ in range(4):
    bm.verts.ensure_lookup_table()
    V = np.array([v.co[:] for v in bm.verts])
    bverts = np.array(sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts}))
    kill = set()
    for s_, ce in EYES.items():
        th, phi, r = angular(V, ce)
        bv = bverts[(r[bverts] < R + 0.01) & (phi[bverts] < 75)]
        if len(bv) < 20: continue
        o = np.argsort(th[bv]); tb, pb = th[bv][o], phi[bv][o]
        k = max(7, len(bv) // 9)
        ext = np.r_[pb[-k:], pb, pb[:k]]
        med = np.array([np.median(ext[i:i + 2 * k + 1]) for i in range(len(pb))])
        ref = np.interp(th, np.r_[tb - 360, tb, tb + 360], np.r_[med, med, med])
        bad = (phi < ref - TRIM_DEG) & (r < R + 0.004) & (phi < 75)
        kill |= set(np.where(bad)[0].tolist())
    if not kill: break
    faces = {f for i in kill for f in bm.verts[i].link_faces}
    trimmed += len(faces)
    bmesh.ops.delete(bm, geom=list(faces), context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for _ in range(2):
        flaps = [f for f in bm.faces if sum(1 for e in f.edges if e.is_boundary) >= 2]
        if flaps:
            bmesh.ops.delete(bm, geom=flaps, context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
rep["margin_tongue_faces_trimmed"] = trimmed
# anything of the lids inside the ball clearance is pushed out radially (keeps the HD lid shape elsewhere)
pushed = 0
for v in bm.verts:
    for s_, ce in EYES.items():
        d = v.co - Vector(ce)
        if d.length < R + GAP:
            v.co = Vector(ce) + d.normalized() * (R + GAP); pushed += 1
rep["lid_verts_pushed_out"] = pushed
# margin loops
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
bnd = [e for e in bm.edges if e.is_boundary]
loops = []; used = set()
for e0 in bnd:
    if e0.index in used: continue
    loop = [e0.verts[0]]; cur = e0.verts[1]; used.add(e0.index); prev = e0
    while cur is not loop[0]:
        loop.append(cur)
        nx = [e for e in cur.link_edges if e.is_boundary and e.index not in used]
        if not nx: break
        used.add(nx[0].index); cur = nx[0].other_vert(cur)
    loops.append(loop)
rep["boundary_loops"] = [len(l) for l in loops]
margins = {}
for l in loops:
    cen = np.mean([v.co[:] for v in l], 0)
    for s, ce in EYES.items():
        if np.linalg.norm(cen[[0, 2]] - ce[[0, 2]]) < R: margins[s] = l
assert set(margins) == {"L", "R"}, f"eye margin loops not found: {rep['boundary_loops']}"
# relax margin along the loop (few passes), then lay it on the ball at R + GAP
for s, l in margins.items():
    ce = Vector(EYES[s])
    P = np.array([v.co[:] for v in l])
    for _ in range(int(os.environ.get("MARGIN_RELAX", 6))):
        P = 0.5 * P + 0.25 * (np.roll(P, 1, 0) + np.roll(P, -1, 0))
    for v, p in zip(l, P):
        d = Vector(p) - ce; v.co = ce + d.normalized() * (R + GAP)
# lining: rings extruded from the margin, rotated about the eye centre toward the socket (along the ball surface)
for s, l in margins.items():
    ce = Vector(EYES[s])
    ring = l
    for k in range(RING):
        geom = bmesh.ops.extrude_edge_only(bm, edges=[e for e in {e for v in ring for e in v.link_edges if e.is_boundary}])
        nv = [g for g in geom["geom"] if isinstance(g, bmesh.types.BMVert)]
        # map new verts in loop order: nearest original ring vert
        new_ring = []
        for v in ring:
            cand_v = [e.other_vert(v) for e in v.link_edges if e.other_vert(v) in nv]
            new_ring.append(cand_v[0] if cand_v else v)
        for v_old, v in zip(ring, new_ring):
            d = v_old.co - ce
            # rotate toward the back of the eye: axis = d x forward
            fwd = Vector((0, -1, 0))
            axis = d.cross(fwd)
            if axis.length < 1e-9: continue
            rot = Matrix.Rotation(-math.radians(RING_DEG), 3, axis.normalized())
            v.co = ce + (rot @ d).normalized() * (R + GAP * (1 + 0.5 * (k + 1)))
        ring = new_ring
bm.normal_update()
bm.to_mesh(me); bm.free(); me.update()
symmetrize()

# ---------------- resolve remaining self-intersections by local Laplacian relaxation (2-ring around each pair)
def fix_intersections(max_iter=12):
    total = 0
    for it in range(max_iter):
        X = np.array([v.co[:] for v in me.vertices])
        T = BVHTree.FromPolygons([tuple(p) for p in X], [tuple(p.vertices) for p in me.polygons])
        polys = [set(p.vertices) for p in me.polygons]
        pairs = [(i, j) for i, j in T.overlap(T) if i < j and not (polys[i] & polys[j])]
        if it == 0: total = len(pairs)
        if not pairs: return total, it
        sel = set()
        for i, j in pairs: sel |= polys[i] | polys[j]
        E = np.array([e.vertices[:] for e in me.edges])
        for _ in range(2):
            m = np.isin(E, list(sel)).any(1); sel |= set(E[m].ravel().tolist())
        idx = np.array(sorted(sel)); mask = np.zeros(len(X), bool); mask[idx] = True
        deg = np.zeros(len(X)); np.add.at(deg, E[:, 0], 1); np.add.at(deg, E[:, 1], 1)
        bnd = set()
        for e in me.edges:
            pass
        for _ in range(4):
            acc = np.zeros_like(X); np.add.at(acc, E[:, 0], X[E[:, 1]]); np.add.at(acc, E[:, 1], X[E[:, 0]])
            avg = acc / np.maximum(deg, 1)[:, None]
            X[mask] = 0.4 * X[mask] + 0.6 * avg[mask]
        me.vertices.foreach_set("co", X.ravel()); me.update()
    return total, max_iter


rep["self_intersections_before_fix"], rep["intersection_fix_iters"] = fix_intersections()
symmetrize()

# ---------------- eyeballs
for s, ce in EYES.items():
    bm2 = bmesh.new(); bmesh.ops.create_uvsphere(bm2, u_segments=64, v_segments=32, radius=R)
    for v in bm2.verts: v.co = Matrix.Rotation(math.pi / 2, 3, 'X') @ v.co      # poles along Y (gaze axis)
    em = bpy.data.meshes.new(f"Eye.{s}"); bm2.to_mesh(em); bm2.free()
    eo = bpy.data.objects.new(f"Eye.{s}", em); bpy.context.scene.collection.objects.link(eo); eo.location = Vector(ce)
    for p in em.polygons: p.use_smooth = True
for p in me.polygons: p.use_smooth = True
head["eye_centre_L"] = EYES["L"].tolist(); head["eye_R"] = R

# ---------------- QA
X = np.array([v.co[:] for v in me.vertices]); n = len(X)
bm = bmesh.new(); bm.from_mesh(me)
rep["nonmanifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
rep["boundary_edges"] = sum(1 for e in bm.edges if e.is_boundary)
rep["loose_verts"] = sum(1 for v in bm.verts if not v.link_faces)
bm.free()
T = BVHTree.FromPolygons([tuple(p) for p in X], [tuple(p.vertices) for p in me.polygons])
pairs = T.overlap(T)
polys = [set(p.vertices) for p in me.polygons]
rep["self_intersections"] = sum(1 for i, j in pairs if i < j and not (polys[i] & polys[j]))
from mathutils.kdtree import KDTree
kd = KDTree(n)
for i, p in enumerate(X): kd.insert(p, i)
kd.balance()
mr = np.array([kd.find((-p[0], p[1], p[2]))[2] for p in X[::7]])
rep["mirror_residual_mm_max"] = float(mr.max() * 1000)
for s, ce in EYES.items():
    r = np.linalg.norm(X - ce, axis=1)
    rep[f"eye_{s}_min_clearance_mm"] = float((r.min() - R) * 1000)
rep["faces_out"] = len(me.polygons)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("HDCLEAN", json.dumps(rep))
