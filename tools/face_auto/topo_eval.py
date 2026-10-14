"""M1 · topology evaluation of a candidate head mesh: quad share, holes, poles, symmetry, shape error and the edge loops
around the eyes and the mouth (can the eyes / lips be cut out along loops that already exist?).

1. The candidate is imported (.fbx/.glb/.gltf/.obj/.blend; in a .blend the object 'head' or 'orig' if present, else all
   meshes) and joined; vertices split for normals/UVs are welded (1e-6 of the size); only the largest connected piece
   (the head skin) is evaluated, the other pieces are listed.
   --align: candidates from another generator come in their own frame/scale: a similarity (scale+rotation+translation)
   is fitted to the reference by trimmed ICP from 24 axis-aligned starts, then point-to-plane refinement; the transform
   and aligned_head.obj (Y-up, imports back into this frame) are written. .obj inputs use Blender's default Y-up import.
2. Counts: faces, quads/tris/ngons %, vertices, non-manifold (>2 faces) and wire edges, boundary loops (holes) with
   lengths, poles (interior valence != 4, boundary valence != 3) in total and within 15 mm of each eye / lip contour.
3. Symmetry: mirrored vertices -> distance to the candidate surface, and the share of vertices with an exact mirror
   partner (< 0.01 mm). Shape: area-sampled surface distance candidate<->reference both ways, all and face region
   (within 10 mm of the dense MediaPipe points).
4. Loop fit, per feature: eye rims (eyes_meta 'raw'), outer lip contour (MediaPipe 61..291..146) and the lip seam
   (mean of the inner upper/lower lip lines 78..308, an open line). Targets are projected onto the candidate surface.
   - true_loop: closed edge loops that Blender's loop select would give (straight through valence-4 vertices; boundary
     loops count too) that wind once around the feature within 12 mm; best = lowest mean deviation; concentric = how
     many of them stay within 10 mm (nested rings available for cutting).
   - path: the best closed edge path around the feature in the edge graph (Dijkstra on a two-layer cover, cost =
     length * (1 + (d / 0.75 mm)^2)); for the seam an open path corner to corner. 'straight' = share of its vertices
     where it goes straight through like an edge loop (1.0 = it IS an edge loop, ~0 = zig-zag through triangles).
     The cycle must advance along the target's arc length (edges may not jump > 20 % of it), so it cannot cut across
     the eye opening or the lips.
   - coverage: share of the target length that has a mesh edge within 1 mm and 20 deg of its tangent.
   fits = mean deviation <= 1 mm and both one-sided maxima <= 2 mm. shape_within_5mm = reference vertices within 5 mm
   of the target -> candidate surface (is the eye / lip shape itself still there?).
   Limits: a path always exists on a dense mesh, so path deviation alone says little without 'straight'; the target
   contours themselves carry ~1 mm landmark noise; the lip seam of a closed mouth can only be an open line.
5. Renders (Workbench clay + wireframe-modifier copy): wire_front/eye/mouth/34.png with target contours (green), best
   path (orange) and best true loop (magenta). Writes <out_dir>/topo_qa.json.
Usage: blender -b --factory-startup -P topo_eval.py -- <mesh .fbx/.glb/.obj/.blend> <reference .fbx/.blend>
       <landmarks.json> <eyes_meta.json> <dense.json> <out_dir> [--align] [--quadify] [--no-render]
  --quadify: join triangle pairs back into quads first (a .glb is always triangulated; use it for quad meshes
             delivered as glTF, never for a genuinely triangulated mesh). quads before/after are reported.
"""
import bpy, bmesh, sys, os, json, time, heapq, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

T0 = time.time()
argv = sys.argv[sys.argv.index('--') + 1:]
ALIGN, RENDER, QUADIFY = '--align' in argv, '--no-render' not in argv, '--quadify' in argv
argv = [x for x in argv if not x.startswith('--')]
CAND, REF, LMJ, EMJ, DNJ, OUT = argv[:6]
OUT = os.path.abspath(OUT); os.makedirs(OUT, exist_ok=True)
MM = 1000.0
OUT_LIP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
SEAM_UP = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
SEAM_LO = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- loading / mesh arrays
def load(path, prefer=('head', 'orig')):
    before = set(bpy.data.objects); ext = os.path.splitext(path)[1].lower()
    if ext == '.fbx': bpy.ops.import_scene.fbx(filepath=path)
    elif ext in ('.glb', '.gltf'): bpy.ops.import_scene.gltf(filepath=path)
    elif ext == '.obj': bpy.ops.wm.obj_import(filepath=path)
    elif ext == '.blend':
        with bpy.data.libraries.load(path) as (src, dst): dst.objects = list(src.objects)
        for o in dst.objects:
            if o: sc.collection.objects.link(o)
    else: raise SystemExit('unknown mesh type ' + path)
    ms = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    pick = [o for o in ms if o.name.split('.')[0] in prefer]
    if pick: ms = sorted(pick, key=lambda o: prefer.index(o.name.split('.')[0]))[:1]
    dg = bpy.context.evaluated_depsgraph_get(); Vs, Ls, Ss, off = [], [], [], 0
    for o in ms:
        me = o.evaluated_get(dg).to_mesh(); n = len(me.vertices)
        co = np.empty(n * 3); me.vertices.foreach_get('co', co); M = np.array(o.matrix_world)
        Vs.append(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
        lt = np.empty(len(me.polygons), int); me.polygons.foreach_get('loop_total', lt)
        lv = np.empty(len(me.loops), int); me.loops.foreach_get('vertex_index', lv)
        Ls.append(lv + off); Ss.append(lt); off += n
        o.evaluated_get(dg).to_mesh_clear()
    names = [o.name for o in ms]
    for o in [o for o in bpy.data.objects if o not in before]: bpy.data.objects.remove(o, do_unlink=True)
    # weld vertices split for normals/UVs (glTF/FBX exports) so the topology is the real one; drop collapsed corners
    V, lv, lt = np.vstack(Vs), np.concatenate(Ls), np.concatenate(Ss); q = 1e-6 * np.linalg.norm(np.ptp(V, 0))
    _, first, inv = np.unique(np.round(V / q).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    lv = inv.ravel()[lv]; V = V[first]; pid = np.repeat(np.arange(len(lt)), lt)
    ls = np.concatenate([[0], np.cumsum(lt)[:-1]]); nxt = np.arange(len(lv)) + 1; nxt[ls + lt - 1] = ls
    k = lv != lv[nxt]; lt = np.bincount(pid[k], minlength=len(lt)); k &= (lt >= 3)[pid]
    lv, lt = lv[k], lt[lt >= 3]
    return V, lv, lt, names

class Topo:
    """Polygon mesh as arrays: V, corner verts lv, poly sizes lt; edges, corner->edge, edge face counts."""
    def __init__(s, V, lv, lt):
        s.V, s.lv, s.lt = V, lv, lt
        s.ls = np.concatenate([[0], np.cumsum(lt)[:-1]]); nl = len(lv)
        s.lp = np.repeat(np.arange(len(lt)), lt)
        nxt = np.arange(nl) + 1; nxt[s.ls + lt - 1] = s.ls; s.nxt = nxt
        prv = np.arange(nl) - 1; prv[s.ls] = s.ls + lt - 1; s.prv = prv
        pr = np.sort(np.stack([lv, lv[nxt]], 1), 1)
        s.E, s.le = np.unique(pr, axis=0, return_inverse=True); s.le = s.le.ravel()
        s.efc = np.bincount(s.le, minlength=len(s.E))
        s.val = np.bincount(s.E.ravel(), minlength=len(V))
        s.bnd_v = np.zeros(len(V), bool); s.bnd_v[s.E[s.efc == 1].ravel()] = True
        s.elen = np.linalg.norm(V[s.E[:, 0]] - V[s.E[:, 1]], axis=1)
    def polys(s): return [x.tolist() for x in np.split(s.lv, s.ls[1:])]
    def tris(s):
        k = s.lt - 2; p = np.repeat(np.arange(len(s.lt)), k); j = np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k)
        a = s.ls[p]; return np.stack([s.lv[a], s.lv[a + j + 1], s.lv[a + j + 2]], 1)
    def bvh(s): return BVHTree.FromPolygons(s.V.tolist(), s.polys(), all_triangles=False)

def mk_mesh(name, V_, lv_, lt_):
    me = bpy.data.meshes.new(name); me.vertices.add(len(V_)); me.vertices.foreach_set('co', V_.ravel().astype(np.float32))
    me.loops.add(len(lv_)); me.loops.foreach_set('vertex_index', lv_.astype(np.int32))
    me.polygons.add(len(lt_)); me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(lt_)[:-1]]).astype(np.int32))
    me.polygons.foreach_set('loop_total', lt_.astype(np.int32)); me.update(calc_edges=True); me.validate()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); return o

def quadify(V_, lv_, lt_):
    o = mk_mesh('tmp', V_, lv_, lt_); bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.join_triangles(bm, faces=list(bm.faces), angle_face_threshold=math.radians(40), angle_shape_threshold=math.radians(40))
    bm.to_mesh(o.data); bm.free(); me = o.data; n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co)
    lt2 = np.empty(len(me.polygons), int); me.polygons.foreach_get('loop_total', lt2)
    lv2 = np.empty(len(me.loops), int); me.loops.foreach_get('vertex_index', lv2)
    bpy.data.objects.remove(o, do_unlink=True); return co.reshape(-1, 3).astype(float), lv2, lt2

def components(T):
    lab = np.arange(len(T.V)); a, b = T.E[:, 0], T.E[:, 1]
    while True:
        m = np.minimum(lab[a], lab[b]); old = lab.copy()
        np.minimum.at(lab, a, m); np.minimum.at(lab, b, m); lab = lab[lab]
        if np.array_equal(lab, old): return lab

def sub_mesh(V, lv, lt, keep_poly):
    ls = np.concatenate([[0], np.cumsum(lt)[:-1]]); cm = np.repeat(keep_poly, lt)
    lv2, lt2 = lv[cm], lt[keep_poly]; used = np.unique(lv2); remap = -np.ones(len(V), int); remap[used] = np.arange(len(used))
    return V[used], remap[lv2], lt2

def samples(T, n, rng):
    tr = T.tris(); A, B, C = T.V[tr[:, 0]], T.V[tr[:, 1]], T.V[tr[:, 2]]
    ar = 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1); i = rng.choice(len(tr), n, p=ar / ar.sum())
    u, v = rng.random(n), rng.random(n); f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    return A[i] + (B[i] - A[i]) * u[:, None] + (C[i] - A[i]) * v[:, None]

def nearest(bvh, P):
    out = np.empty((len(P), 3)); nrm = np.empty((len(P), 3)); d = np.empty(len(P))
    for k, p in enumerate(P):
        loc, n, _, dd = bvh.find_nearest(Vector(p))
        if loc is None: out[k] = p; nrm[k] = 0; d[k] = 1e9
        else: out[k] = loc; nrm[k] = n; d[k] = dd
    return out, nrm, d

def st(x):
    x = np.asarray(x) * MM
    return {'p50': round(float(np.median(x)), 2), 'p95': round(float(np.percentile(x, 95)), 2), 'max': round(float(x.max()), 2)} if len(x) else None

# ---------------------------------------------------------------- inputs
rng = np.random.default_rng(0)
Vr, lvr, ltr, rnames = load(REF, prefer=('orig', 'head'))
TR = Topo(Vr, lvr, ltr); bvh_r = TR.bvh()
Vc, lvc, ltc, cnames = load(CAND)
quad_in = round(100 * float((ltc == 4).mean()), 2)
if QUADIFY: Vc, lvc, ltc = quadify(Vc, lvc, ltc)
TA = Topo(Vc, lvc, ltc); lab = components(TA); plab = lab[lvc[TA.ls]]
ul, cnt = np.unique(plab, return_counts=True); main = ul[np.argmax(cnt)]
pieces = []
for u_, c_ in sorted(zip(ul, cnt), key=lambda x: -x[1]):
    if u_ == main: continue
    vv = np.unique(lvc[np.repeat(plab == u_, ltc)])
    pieces.append({'faces': int(c_), 'centre_mm': (Vc[vv].mean(0) * MM).round(1).tolist(), 'size_mm': ((Vc[vv].max(0) - Vc[vv].min(0)) * MM).round(1).tolist()})
V, lv, lt = sub_mesh(Vc, lvc, ltc, plab == main)
qa = {'candidate': os.path.abspath(CAND), 'reference': os.path.abspath(REF), 'objects': cnames, 'pieces_total': len(ul),
      'other_pieces': pieces[:12], 'quads_pct_as_loaded': quad_in, 'quadified': QUADIFY}

# ---------------------------------------------------------------- similarity alignment (trimmed ICP with scale)
def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); A0, B0 = A - ma, B - mb
    U, D, Vt = np.linalg.svd(B0.T @ A0 / len(A)); dm = np.array([1, 1, np.sign(np.linalg.det(U @ Vt))])
    R = U @ np.diag(dm) @ Vt; s = (D * dm).sum() / (A0 ** 2).sum(1).mean(); return s, R, mb - s * R @ ma

def icp(X, s, R, t, iters, keep=0.85):
    for _ in range(iters):
        Y = s * X @ R.T + t; Q, _, d = nearest(bvh_r, Y); k = d <= np.percentile(d, keep * 100)
        s, R, t = umeyama(X[k], Q[k])
    Y = s * X @ R.T + t; _, _, d = nearest(bvh_r, Y); d = np.sort(d)[:int(len(d) * keep)]
    return s, R, t, float(np.sqrt((d ** 2).mean()))

def icp_plane(X, s, R, t, iters, keep=0.85):
    """point-to-plane refinement with scale (point-to-point slides slowly around a round head)."""
    for _ in range(iters):
        Y = s * X @ R.T + t; Q, N, d = nearest(bvh_r, Y); k = d <= np.percentile(d, keep * 100)
        Y, Q, N = Y[k], Q[k], N[k]; c = Y.mean(0); Yc = Y - c
        A = np.hstack([np.cross(Yc, N), N, (N * Yc).sum(1, keepdims=True)]); b = (N * (Q - Y)).sum(1)
        x = np.linalg.lstsq(A, b, rcond=None)[0]; w, tau, sg = x[:3], x[3:6], x[6]; wn = float(np.linalg.norm(w))
        Ru = np.array(Matrix.Rotation(wn, 3, Vector(w / wn))) if wn > 1e-12 else np.eye(3)
        s, R, t = (1 + sg) * s, Ru @ R, (1 + sg) * Ru @ (t - c) + c + tau
        if wn < 1e-7 and np.linalg.norm(tau) < 1e-8 and abs(sg) < 1e-7: break
    Y = s * X @ R.T + t; _, _, d = nearest(bvh_r, Y); d = np.sort(d)[:int(len(d) * keep)]
    return s, R, t, float(np.sqrt((d ** 2).mean()))

if ALIGN:
    T_ = Topo(V, lv, lt); X = samples(T_, 2500, rng); Y = samples(TR, 2500, rng)
    cx, cy = X.mean(0), Y.mean(0); s0 = np.sqrt(((Y - cy) ** 2).sum(1).mean() / ((X - cx) ** 2).sum(1).mean())
    rots = []
    import itertools
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            R0 = np.zeros((3, 3)); R0[range(3), perm] = sg
            if np.linalg.det(R0) > 0: rots.append(R0)
    trials = sorted([icp(X, s0, R0, cy - s0 * R0 @ cx, 6) + (i,) for i, R0 in enumerate(rots)], key=lambda r: r[3])
    s, R, t, rms = icp(X, *trials[0][:3], 10)[:4]
    X = samples(T_, 6000, rng); s, R, t, rms = icp_plane(X, s, R, t, 40)
    V = s * V @ R.T + t
    M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t
    qa['align'] = {'scale': round(float(s), 6), 'matrix': M.round(7).tolist(), 'trimmed_rms_mm': round(rms * MM, 2),
                   'start_rotation': int(trials[0][4]), 'runner_up_rms_mm': round(trials[1][3] * MM, 2)}
    with open(os.path.join(OUT, 'aligned_head.obj'), 'w') as f:
        f.write(''.join('v %.6f %.6f %.6f\n' % (p[0], p[2], -p[1]) for p in V))   # OBJ is Y-up
        f.write(''.join('f ' + ' '.join(str(i + 1) for i in pl) + '\n' for pl in np.split(lv, np.cumsum(lt)[:-1])))

T = Topo(V, lv, lt); bvh_c = T.bvh()
nv, nf = len(V), len(lt)
qa['counts'] = {'faces': int(nf), 'verts': int(nv), 'quads_pct': round(100 * float((lt == 4).mean()), 2),
                'tris_pct': round(100 * float((lt == 3).mean()), 2), 'ngons_pct': round(100 * float((lt > 4).mean()), 2),
                'edge_mm': st(T.elen)}
qa['manifold'] = {'nonmanifold_edges': int((T.efc > 2).sum()), 'wire_edges': int((T.efc == 0).sum()),
                  'boundary_edges': int((T.efc == 1).sum())}
# boundary loops
be = np.where(T.efc == 1)[0]; badj = {}
for e in be:
    for v in T.E[e]: badj.setdefault(int(v), []).append(int(e))
seen, holes = set(), []
for e0 in be:
    if e0 in seen: continue
    L, e, v = 0.0, int(e0), int(T.E[e0][0]); chain, cv = [], [int(T.E[e0][0])]
    while e not in seen:
        seen.add(e); chain.append(e); L += T.elen[e]; v = int(T.E[e][1] if T.E[e][0] == v else T.E[e][0]); cv.append(v)
        nx = [x for x in badj[v] if x not in seen]
        if not nx: break
        e = nx[0]
    holes.append({'edges': len(chain), 'length_mm': round(L * MM, 1), 'closed': cv[-1] == cv[0], 'verts': cv[:-1] if cv[-1] == cv[0] else cv})
holes.sort(key=lambda h: -h['length_mm'])
qa['holes'] = {'count': len(holes), 'closed': sum(h['closed'] for h in holes), 'loops': [{k: h[k] for k in ('edges', 'length_mm', 'closed')} for h in holes[:10]]}
pole = np.where(T.bnd_v, T.val != 3, T.val != 4) & (T.val > 0)
qa['poles'] = {'total': int(pole.sum()), 'interior': int((pole & ~T.bnd_v).sum()), 'pct_verts': round(100 * float(pole.mean()), 2)}

# symmetry
kd = KDTree(nv)
for i, p in enumerate(V): kd.insert(p, i)
kd.balance()
Vm = V * [-1, 1, 1]; gap = np.array([kd.find(p)[2] for p in Vm])
_, _, dm = nearest(bvh_c, Vm)
qa['symmetry'] = {'mirror_to_surface_mm': st(dm), 'exact_pair_pct': round(100 * float((gap < 1e-5).mean()), 2),
                  'pair_within_0.1mm_pct': round(100 * float((gap < 1e-4).mean()), 2),
                  'pair_gap_mm': st(gap)}

# surface distance (face region = within 10 mm of the dense MediaPipe points)
dense = json.load(open(DNJ)); D = {int(k): np.array(v) for k, v in dense.items() if k.isdigit()}
lmk = json.load(open(LMJ)); LM = np.array([v for k, v in lmk.items() if not k.startswith('_')])
kdf = KDTree(len(D) + len(LM))
for i, p in enumerate(list(D.values()) + list(LM)): kdf.insert(p, i)
kdf.balance()
face_mask = lambda P: np.array([kdf.find(p)[2] < 0.010 for p in P])
Pc = samples(T, 30000, rng); Pr = samples(TR, 30000, rng)
_, _, d_cr = nearest(bvh_r, Pc); _, _, d_rc = nearest(bvh_c, Pr); fc, fr = face_mask(Pc), face_mask(Pr)
qa['surface'] = {'cand_to_ref_mm': st(d_cr), 'ref_to_cand_mm': st(d_rc),
                 'face_cand_to_ref_mm': st(d_cr[fc]), 'face_ref_to_cand_mm': st(d_rc[fr])}
# outward orientation of the candidate normals (for lifting overlay lines)
cen = V.mean(0); tr_ = T.tris(); fn = np.cross(V[tr_[:, 1]] - V[tr_[:, 0]], V[tr_[:, 2]] - V[tr_[:, 0]])
orient = 1.0 if (fn * (V[tr_].mean(1) - cen)).sum() >= 0 else -1.0
qa['manifold']['normals_outward'] = orient > 0

# ---------------------------------------------------------------- contours
def resample(C, closed, step=0.0005):
    P = np.vstack([C, C[:1]]) if closed else C; seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)]); n = max(int(s[-1] / step), 8)
    q = np.linspace(0, s[-1], n, endpoint=not closed)
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)

def poly_near(P, C, closed):
    """distance of points P to polyline C and the arc-length parameter (0..1) of the nearest point."""
    A = C if closed else C[:-1]; B = np.roll(C, -1, 0) if closed else C[1:]; AB = B - A; L2 = np.maximum((AB ** 2).sum(1), 1e-18)
    sl = np.sqrt(L2); cum = np.concatenate([[0], np.cumsum(sl)]); out, par = np.empty(len(P)), np.empty(len(P))
    for i in range(0, len(P), 1500):
        Q = P[i:i + 1500, None, :] - A[None]; u = np.clip((Q * AB).sum(2) / L2, 0, 1)
        dd = np.linalg.norm(Q - u[..., None] * AB, axis=2); j = dd.argmin(1); r = np.arange(len(j))
        out[i:i + 1500] = dd[r, j]; par[i:i + 1500] = (cum[j] + u[r, j] * sl[j]) / cum[-1]
    return out, par % 1.0
poly_dist = lambda P, C, closed: poly_near(P, C, closed)[0]

em = json.load(open(EMJ))
def eye_rim(sd):
    C = np.array(em[sd]['raw'], float)
    if np.linalg.norm(C[0] - C[-1]) < 1e-6: C = C[:-1]
    return C
seam = np.array([0.5 * (D[a] + D[b]) for a, b in zip(SEAM_UP, SEAM_LO) if a in D and b in D])
lipo = np.array([D[i] for i in OUT_LIP if i in D])
targets = {'eye_L': (eye_rim('L'), True), 'eye_R': (eye_rim('R'), True), 'lip_outer': (lipo, True), 'lip_seam': (seam, False)}
proj = {}
for k, (C, cl) in targets.items():
    Cs = resample(C, cl); Q, _, d = nearest(bvh_c, Cs); proj[k] = (Q, cl, d)

# ---------------------------------------------------------------- loop machinery (only near the features)
near = np.zeros(nv, bool); dnear = {}
for k, (Q, cl, _) in proj.items():
    lo, hi = Q.min(0) - 0.016, Q.max(0) + 0.016; box = np.all((V > lo) & (V < hi), 1)
    d = np.full(nv, 1e9); d[box] = poly_dist(V[box], Q, cl); dnear[k] = d; near |= d < 0.016
eid = {(int(a), int(b)): i for i, (a, b) in enumerate(T.E)}
ekey = lambda a, b: eid[(a, b) if a < b else (b, a)]
vedges, adjf = {}, {}
for c in np.where(near[lv])[0]:
    v = int(lv[c]); e1, e2 = int(T.le[c]), int(T.le[T.prv[c]])
    vedges.setdefault(v, set()).update((e1, e2)); adjf.setdefault((v, e1), set()).add(e2); adjf.setdefault((v, e2), set()).add(e1)
opp = {}
for v, es in vedges.items():
    if len(es) != 4 or T.bnd_v[v] or T.val[v] != 4: continue
    for e in es:
        o = es - {e} - adjf.get((v, e), set())
        if len(o) == 1: opp[(v, e)] = o.pop()
other = lambda e, v: int(T.E[e][1] if T.E[e][0] == v else T.E[e][0])

def plane_angle(Q):
    c = Q.mean(0); U = np.linalg.svd(Q - c)[2]; ax, ay = U[0], U[1]
    return lambda P: (np.arctan2((P - c) @ ay, (P - c) @ ax) / (2 * np.pi)) % 1.0

def winding(t):
    dt = (np.diff(np.concatenate([t, t[:1]])) + 0.5) % 1.0 - 0.5
    return float(dt.sum()), float(np.abs(dt).max())

def dev(Pv, Q, cl):
    """deviation of a vertex chain (verts + edge midpoints) from target Q, and target -> chain."""
    P = np.vstack([Pv, 0.5 * (Pv + np.roll(Pv, -1, 0))[:len(Pv) - (0 if cl else 1)]])
    a = poly_dist(P, Q, cl); b = poly_dist(Q, Pv, cl)
    return {'mean_mm': round(float(a.mean() * MM), 2), 'max_mm': round(float(a.max() * MM), 2),
            'target_to_loop_mean_mm': round(float(b.mean() * MM), 2), 'target_to_loop_max_mm': round(float(b.max() * MM), 2)}

def fits(r): return bool(r['mean_mm'] <= 1.0 and r['max_mm'] <= 2.0 and r['target_to_loop_max_mm'] <= 2.0)

def straight_share(vs, cl):
    es = [ekey(vs[i], vs[(i + 1) % len(vs)]) for i in range(len(vs) if cl else len(vs) - 1)]
    rng_ = range(len(es)) if cl else range(len(es) - 1)
    ok = [opp.get((vs[(i + 1) % len(vs)], es[i])) == es[(i + 1) % len(es)] for i in rng_]
    return round(float(np.mean(ok)) if ok else 0.0, 3)

def true_loops(k):
    Q, cl, _ = proj[k]; d = dnear[k]; ang = plane_angle(Q); band = d < 0.012
    starts = np.where(band[T.E[:, 0]] & band[T.E[:, 1]])[0].tolist(); seen, loops = set(), []
    for h in holes:   # boundary loops are existing loops too
        vs = h['verts']
        if h['closed'] and len(vs) > 2 and band[vs].all(): loops.append((vs, 'boundary'))
    for e0 in starts:
        if e0 in seen: continue
        a, b = int(T.E[e0][0]), int(T.E[e0][1]); vs, es, e, v, closed = [a, b], [e0], e0, b, False
        while len(es) < 2000:
            e2 = opp.get((v, e))
            if e2 is None: break
            if e2 == e0: closed = True; break
            v = other(e2, v)
            if not band[v]: break
            es.append(e2); vs.append(v); e = e2
        seen.update(es)
        if closed and vs[-1] == a: loops.append((vs[:-1], 'loop'))
    res = []
    for vs, kind in loops:
        w, jmp = winding(ang(V[vs]))
        if abs(abs(w) - 1) > 0.2 or jmp > 0.25: continue
        r = dev(V[vs], Q, cl); r.update(edges=len(vs), kind=kind, within_10mm=bool(d[vs].max() <= 0.010)); res.append((r, vs))
    res.sort(key=lambda x: x[0]['mean_mm'])
    return res

def dijkstra(adj, src, dst):
    dist, prev, h = {src: 0.0}, {}, [(0.0, src)]
    while h:
        du, u = heapq.heappop(h)
        if u == dst: break
        if du > dist[u]: continue
        for v, w in adj.get(u, ()):
            nd = du + w
            if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = u; heapq.heappush(h, (nd, v))
    if dst not in dist: return None, 1e18
    p = [dst]
    while p[-1] != src: p.append(prev[p[-1]])
    return p[::-1], dist[dst]

SIG = 0.00075
def best_path(k):
    Q, cl, _ = proj[k]; d = dnear[k]; Rb = max(0.006, 3 * float(np.median(T.elen)))
    band = d < Rb; es = np.where(band[T.E[:, 0]] & band[T.E[:, 1]])[0].tolist()
    w = lambda e: T.elen[e] * (1 + ((d[T.E[e][0]] + d[T.E[e][1]]) / 2 / SIG) ** 2)
    adj = {}
    if cl:
        t = np.zeros(nv); bi = np.where(band)[0]; t[bi] = poly_near(V[bi], Q, True)[1]   # arc-length param: no shortcuts
        for e in es:
            a, b = map(int, T.E[e]); dt = (t[b] - t[a] + 0.5) % 1.0 - 0.5
            if abs(dt) > 0.2: continue
            c = int((t[b] < t[a] and dt > 0) or (t[b] > t[a] and dt < 0)); we = w(e)   # crosses the start point
            for l in (0, 1):
                adj.setdefault(2 * a + l, []).append((2 * b + (l ^ c), we)); adj.setdefault(2 * b + (l ^ c), []).append((2 * a + l, we))
        src = sorted([int(v) for v in bi if t[v] < 0.04 or t[v] > 0.96], key=lambda v: d[v])[:6]
        best = (None, 1e18)
        for s_ in src:
            p, c_ = dijkstra(adj, 2 * s_, 2 * s_ + 1)
            if p and c_ < best[1]: best = (p, c_)
        if best[0] is None: return None, None
        vs = [x // 2 for x in best[0]][:-1]
    else:
        for e in es:
            a, b = map(int, T.E[e]); we = w(e); adj.setdefault(a, []).append((b, we)); adj.setdefault(b, []).append((a, we))
        bi = np.where(band)[0]
        if not len(bi): return None, None
        ends = [int(bi[np.argmin(np.linalg.norm(V[bi] - Q[j], axis=1))]) for j in (0, -1)]
        vs, _ = dijkstra(adj, ends[0], ends[1])
        if vs is None: return None, None
    if vs is None or len(vs) < 3: return None, None          # degenerate path (e.g. both ends on one vertex)
    r = dev(V[vs], Q, cl); r.update(edges=len(vs) - (0 if cl else 1), straight=straight_share(vs, cl)); r['fits'] = fits(r)
    return r, vs

def coverage(k):
    Q, cl, _ = proj[k]; Qn = np.vstack([Q, Q[:1]]) if cl else Q
    S = resample(Qn, False, 0.00025); tg = np.gradient(S, axis=0); tg /= np.linalg.norm(tg, axis=1, keepdims=True) + 1e-12
    band = dnear[k] < 0.004; es = np.where(band[T.E[:, 0]] & band[T.E[:, 1]])[0]
    if not len(es): return 0.0
    A, B = V[T.E[es, 0]], V[T.E[es, 1]]; Mid = 0.5 * (A + B); r = 0.001 + T.elen[es].max() / 2
    kde = KDTree(len(es))
    for i, p in enumerate(Mid): kde.insert(p, i)
    kde.balance(); cos20 = math.cos(math.radians(20)); hit = 0
    for p, g in zip(S, tg):
        ids = [i for _, i, _ in kde.find_range(p, r)]
        if not ids: continue
        a, b = A[ids], B[ids]; ab = b - a; u = np.clip(((p - a) * ab).sum(1) / np.maximum((ab ** 2).sum(1), 1e-18), 0, 1)
        dd = np.linalg.norm(p - (a + u[:, None] * ab), axis=1); cs = np.abs((ab * g).sum(1)) / (np.linalg.norm(ab, axis=1) + 1e-12)
        hit += bool(np.any((dd <= 0.001) & (cs >= cos20)))
    return round(hit / len(S), 3)

feat, draw = {}, {}
for k in targets:
    Q, cl, pd = proj[k]; d = dnear[k]
    fr = {'target_points': len(Q), 'target_length_mm': round(float(np.linalg.norm(np.diff(np.vstack([Q, Q[:1]]) if cl else Q, axis=0), axis=1).sum() * MM), 1),
          'target_projection_shift_mm': st(pd), 'edge_mm_near': st(T.elen[(d[T.E[:, 0]] < 0.006)]) if (d < 0.006).any() else None,
          'poles_within_15mm': int((pole & (d < 0.015)).sum())}
    rb = np.all((Vr > Q.min(0) - 0.006) & (Vr < Q.max(0) + 0.006), 1); rv = Vr[rb][poly_dist(Vr[rb], Q, cl) < 0.005]
    fr['shape_within_5mm'] = st(nearest(bvh_c, rv)[2]) if len(rv) else None   # reference surface near the feature -> candidate
    pr, pv = best_path(k); fr['path'] = pr
    if cl:
        tl = true_loops(k)
        fr['true_loop'] = dict(tl[0][0], exists=True, fits=fits(tl[0][0])) if tl else {'exists': False, 'fits': False}
        fr['concentric_loops_10mm'] = int(sum(r['within_10mm'] for r, _ in tl))
        draw[k] = (pv, tl[0][1] if tl else None)
    else: draw[k] = (pv, None)
    fr['coverage_1mm_20deg'] = coverage(k)
    feat[k] = fr
qa['features'] = feat
def F(k, *p):
    x = feat[k]
    for q in p: x = (x or {}).get(q)
    return x
qa['summary'] = {
    'faces': int(nf), 'quads_pct': qa['counts']['quads_pct'], 'holes': len(holes), 'nonmanifold': qa['manifold']['nonmanifold_edges'],
    'symmetric_exact_pct': qa['symmetry']['exact_pair_pct'], 'surface_p95_mm': qa['surface']['cand_to_ref_mm']['p95'],
    'face_surface_p95_mm': (qa['surface']['face_cand_to_ref_mm'] or {}).get('p95'),
    **{f'{k}_loop': (F(k, 'true_loop', 'exists'), F(k, 'true_loop', 'mean_mm'), F(k, 'concentric_loops_10mm')) for k in ('eye_L', 'eye_R', 'lip_outer')},
    **{f'{k}_path': (F(k, 'path', 'mean_mm'), F(k, 'path', 'straight')) for k in targets},
    'poles_near': {k: feat[k]['poles_within_15mm'] for k in targets}}
qa['seconds_metrics'] = round(time.time() - T0, 1)

# ---------------------------------------------------------------- renders
def render():
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 800
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_cavity = False; sh.show_object_outline = False
    sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.93, 0.93, 0.93)
    sc.view_settings.view_transform = 'Standard'
    clay = mk_mesh('clay', V, lv, lt); clay.color = (0.62, 0.62, 0.64, 1)
    clay.data.polygons.foreach_set('use_smooth', np.ones(nf, bool))
    wire = clay.copy(); wire.data = clay.data; wire.name = 'wire'; sc.collection.objects.link(wire)
    wm = wire.modifiers.new('wf', 'WIREFRAME'); wm.use_replace = True; wm.use_even_offset = False; wire.color = (0.04, 0.04, 0.06, 1)
    cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.clip_end = 10; co = bpy.data.objects.new('c', cam)
    sc.collection.objects.link(co); sc.camera = co
    lines = []
    def line(pts, cl, col, rad, lift):
        _, n, _ = nearest(bvh_c, pts); n = n * orient
        cu = bpy.data.curves.new('ln', 'CURVE'); cu.dimensions = '3D'; sp = cu.splines.new('POLY'); P = pts + n * lift
        sp.points.add(len(P) - 1); sp.points.foreach_set('co', np.hstack([P, np.ones((len(P), 1))]).ravel().astype(np.float32))
        sp.use_cyclic_u = cl; cu.bevel_depth = rad; cu.bevel_resolution = 1
        o = bpy.data.objects.new('ln', cu); o.color = (*col, 1); sc.collection.objects.link(o); lines.append(o)
    def shot(fn, centre, dirv, size):
        px = size / 800.0; wm.thickness = 1.1 * px
        for o in lines: bpy.data.objects.remove(o, do_unlink=True)
        lines.clear(); base = 0.6 * px + 0.00008 + 0.03 * float(np.median(T.elen))  # coarse quads are not planar
        for k, (Q, cl, _) in proj.items():
            line(Q, cl, (0.05, 0.75, 0.15), 1.3 * px, base + 1.5 * px)
            pv, lp = draw[k]
            if pv: line(V[pv], cl, (1.0, 0.5, 0.0), 0.9 * px, base + 2.5 * px)
            if lp: line(V[lp], True, (0.9, 0.05, 0.75), 1.2 * px, base + 3.5 * px)
        d = Vector(dirv).normalized(); cam.ortho_scale = size
        co.location = Vector(centre) - d * 1.5; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, fn); bpy.ops.render.render(write_still=True)
    lo, hi = V.min(0), V.max(0); chin = D[152][2] if 152 in D else min(p[2] for p in D.values())
    H = (hi[2] - chin) * 1.3; hc = np.array([0.0, (lo[1] + hi[1]) / 2, hi[2] - 0.47 * H])
    shot('wire_front.png', hc, (0, 1, 0), H)
    Q = proj['eye_L'][0]; ext = (Q.max(0) - Q.min(0)).max()
    shot('wire_eye.png', Q.mean(0), (-math.sin(0.26), math.cos(0.26), 0), ext * 2.4)
    Q = np.vstack([proj['lip_outer'][0], proj['lip_seam'][0]]); ext = (Q.max(0) - Q.min(0))[0]
    shot('wire_mouth.png', Q.mean(0), (0, 1, 0), ext * 2.0)
    shot('wire_34.png', hc, (-math.sin(0.65), math.cos(0.65), 0), H)

if RENDER: render()
qa['seconds_total'] = round(time.time() - T0, 1)
json.dump(qa, open(os.path.join(OUT, 'topo_qa.json'), 'w'), indent=1)
print('TOPO_QA', json.dumps(qa['summary']))
