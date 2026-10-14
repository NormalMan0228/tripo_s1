"""TRACK P · clean bases from the Tripo Smart Mesh P2 heads (new clean originals with natural edge loops).

prep   <p2.fbx> <old_sym_dir> <topo_qa.json> <out_dir>
  1. The FBX is imported, split vertices welded (1e-6 of the size), connected pieces found; head piece = largest.
  2. Skin = the largest patch of the head piece joined across manifold edges only. Lash strips, a second eyeball,
     a brow, mouth linings and small bumps that Tripo fused on through 3-face edges fall off as extra pieces.
  3. Alignment to our frame (metres, +x = character left, face toward -y, z up), similarity own -> ours:
     a. two starts: topo_eval's trimmed-ICP matrix and an upright start (Tripo's own frame is face -y, z up:
        identity rotation, crown / nose / centre matched to the old landmarks); a start must stay upright and put
        skin within 15 mm of the old nose tip; the better face fit wins (f09: topo_eval's start was back to front);
     b. face-box trimmed point-to-plane ICP with scale against the OLD symmetric head (box from old landmarks);
     c. the skin's own mirror plane (mirrored skin registered onto itself) is turned onto x = 0 (yaw, roll, x
        only); scale, pitch, y, z refined again on the face with the plane held (2 rounds);
     d. P2 heads carry a centre edge loop ~0.1 mm off that plane: the loop's plane is turned onto x = 0 and its
        residual (< 0.2 mm) zeroed, so sym_mirror cuts along the existing loop instead of leaving a sliver strip.
  4. Pieces classified against the old landmarks / eyes: eye (sphere-like, round from the front, at the old eye),
     mouth (in the mouth box with skin in front of it), lid (elongated, along the old rim), brow, else other.
  5. Small skin holes: 3-vertex slivers welded as T-junctions, slits < 0.8 mm wide zipped (vertices merged), the rest
     of the loops < 12 vertices and the gaps left by fused 'other' bits filled. Kept: body opening, eye openings,
     nostrils and other loops of 12+ vertices.
  6. Preliminary landmarks / eyes_meta (as in finish, without MediaPipe) for sym_mirror.
  Writes <out>/_work/head_skin.fbx (skin, our frame), pieces.blend (classified pieces), landmarks_pre.json,
  eyes_meta_pre.json, prep_qa.json.
finish <out_dir> <old_sym_dir> <old_rig_points.json> <ref_front.png>     (after sym_mirror.py wrote <out>/base.blend)
  7. Pieces symmetrised and saved into base.blend: +x pieces follow the skin's symmetrisation move (eyeballs and
     mouth parts rigidly) and are mirrored; -x pieces without a +x partner are mirrored over; centre pieces get
     sym_mirror's half-average. Objects p2_eyes, p2_brows, p2_lids, p2_mouth ('other' pieces are dropped).
  8. Eye margin of the +x eye: the skin's eye-opening hole if it has one (f09); else the skin passes into a socket
     pocket behind the eyeball, and the margin is the closed edge path on the skin nearest the curve where the skin
     goes under the eyeball (an existing edge loop if one fits within 0.3 mm of the best path). eyes_meta: C, r =
     robust sphere fit of the +x eyeball, raw / up_path / lo_path from that loop (outer -> inner), margin_vids
     (vertex ids in 'orig'), skin_eyeball_crossing; the right eye mirrored.
  9. landmarks.json: eye points 7-14 from the margin (corners = facelib.lids, lid points = arc middle); brows, nose
     tip, chin and the mouth corners' extent from MediaPipe on clay front renders of this head (the method that
     made the old landmarks) with geometric fallbacks; lip line = the most recessed front line between the lips
     ('_lip_seam', corner to corner), 34 = 35 = its centre; crown = top of the centre line. Exactly symmetric.
  10. rig_points.json: every old T14 joint through similarity + thin-plate spline (old -> new landmarks 1-6, 16,
     20, 22, 24, 31, seam centre, eye rims, eyeball centres, and the ear joints after the old ear is registered
     onto the new ear by ICP); skin joints snapped onto orig; eye joints on the new eyeball centres; symmetric.
  11. likeness.jpg (01_front.png | grey front render | 50 % overlay, similarity from MediaPipe on the image to our
     landmarks), check_eye_mouth.jpg, _work/sheet_front.png / sheet_34.png, finish_qa.json.
sheet  <P_dir> <out.jpg> <head names...>: 4-head sheet of the sheet views.
Usage: blender -b --factory-startup -P p2_base.py -- prep <p2.fbx> <old_sym_dir> <topo_qa.json> <out_dir>
       blender -b --factory-startup -P sym_mirror.py -- <out>/_work/head_skin.fbx <out>/_work/landmarks_pre.json <out>/_work/eyes_meta_pre.json <out>
       blender -b --factory-startup -P p2_base.py -- finish <out_dir> <old_sym_dir> <old_rig_points.json> <ref_front.png>
       blender -b --factory-startup -P p2_base.py -- sheet <P_dir> <out.jpg> <head names...>
"""
import bpy, bmesh, sys, os, json, math, time, subprocess, tempfile, itertools
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.append(HERE)
from facelib import lids, sphere_fit, tps_fit, tps_apply

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MP_PY = os.path.join(ROOT, '.tools', 'landmark-venv', 'Scripts', 'python.exe')
MP_MODEL = os.path.join(ROOT, '.tools', 'landmark-models', 'face_landmarker.task')
MP_DETECT = os.path.join(HERE, 'mp_detect.py')
MP = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 8: 159, 9: 133, 10: 145,
      11: 362, 12: 386, 13: 263, 14: 374, 16: 1, 20: 61, 22: 291, 24: 152, 34: 13, 35: 14}
PAIRS = [(1, 6), (2, 5), (3, 4), (7, 13), (8, 12), (9, 11), (10, 14), (20, 22)]     # (right -x, left +x)
CENTRE = (16, 24, 31, 34, 35)
MX = np.array([-1.0, 1.0, 1.0]); MM = 1000.0
argv = sys.argv[sys.argv.index('--') + 1:]; MODE = argv[0]
T0 = time.time()


# ------------------------------------------------------------------ mesh arrays
def load_fbx(path):
    before = set(bpy.data.objects); bpy.ops.import_scene.fbx(filepath=path)
    ms = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    dg = bpy.context.evaluated_depsgraph_get(); Vs, Ls, Ss, off = [], [], [], 0
    for o in ms:
        me = o.evaluated_get(dg).to_mesh(); n = len(me.vertices)
        co = np.empty(n * 3); me.vertices.foreach_get('co', co); M = np.array(o.matrix_world)
        Vs.append(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
        lt = np.empty(len(me.polygons), int); me.polygons.foreach_get('loop_total', lt)
        lv = np.empty(len(me.loops), int); me.loops.foreach_get('vertex_index', lv)
        Ls.append(lv + off); Ss.append(lt); off += n
        o.evaluated_get(dg).to_mesh_clear()
    for o in [o for o in bpy.data.objects if o not in before]: bpy.data.objects.remove(o, do_unlink=True)
    V, lv, lt = np.vstack(Vs), np.concatenate(Ls), np.concatenate(Ss); q = 1e-6 * np.linalg.norm(np.ptp(V, 0))
    _, first, inv = np.unique(np.round(V / q).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    lv = inv.ravel()[lv]; V = V[first]; pid = np.repeat(np.arange(len(lt)), lt)
    ls = np.concatenate([[0], np.cumsum(lt)[:-1]]); nxt = np.arange(len(lv)) + 1; nxt[ls + lt - 1] = ls
    k = lv != lv[nxt]; lt = np.bincount(pid[k], minlength=len(lt)); k &= (lt >= 3)[pid]
    return V, lv[k], lt[lt >= 3]


def obj_arrays(o, world=True):
    me = o.data; n = len(me.vertices); co = np.empty(n * 3); me.vertices.foreach_get('co', co); V = co.reshape(-1, 3)
    if world: M = np.array(o.matrix_world); V = V @ M[:3, :3].T + M[:3, 3]
    lt = np.empty(len(me.polygons), int); me.polygons.foreach_get('loop_total', lt)
    lv = np.empty(len(me.loops), int); me.loops.foreach_get('vertex_index', lv)
    return V, lv, lt


def edges_of(lv, lt):
    ls = np.concatenate([[0], np.cumsum(lt)[:-1]]); nxt = np.arange(len(lv)) + 1; nxt[ls + lt - 1] = ls
    pr = np.sort(np.stack([lv, lv[nxt]], 1), 1); E, le = np.unique(pr, axis=0, return_inverse=True); le = le.ravel()
    return ls, E, le, np.bincount(le, minlength=len(E))


def label_prop(n, a, b):
    lab = np.arange(n)
    if not len(a): return lab
    while True:
        m = np.minimum(lab[a], lab[b]); old = lab.copy(); np.minimum.at(lab, a, m); np.minimum.at(lab, b, m); lab = lab[lab]
        if np.array_equal(lab, old): return lab


def sub_mesh(V, lv, lt, keep_poly):
    cm = np.repeat(keep_poly, lt); lv2, lt2 = lv[cm], lt[keep_poly]
    used = np.unique(lv2); remap = -np.ones(len(V), int); remap[used] = np.arange(len(used))
    return V[used], remap[lv2], lt2


def polys(lv, lt): return [x.tolist() for x in np.split(lv, np.cumsum(lt)[:-1])]


def bvh_of(V, lv, lt): return BVHTree.FromPolygons(V.tolist(), polys(lv, lt), all_triangles=False)


def tris(lv, lt):
    ls = np.concatenate([[0], np.cumsum(lt)[:-1]]); k = lt - 2; p = np.repeat(np.arange(len(lt)), k)
    j = np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k); a = ls[p]
    return np.stack([lv[a], lv[a + j + 1], lv[a + j + 2]], 1)


def samples(V, lv, lt, n, rng):
    tr = tris(lv, lt); A, B, C = V[tr[:, 0]], V[tr[:, 1]], V[tr[:, 2]]
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


def mk_obj(name, V, lv, lt, coll=None, smooth=True):
    me = bpy.data.meshes.new(name); me.vertices.add(len(V)); me.vertices.foreach_set('co', np.asarray(V, float).ravel().astype(np.float32))
    me.loops.add(len(lv)); me.loops.foreach_set('vertex_index', np.asarray(lv).astype(np.int32))
    me.polygons.add(len(lt)); me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(lt)[:-1]]).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.asarray(lt).astype(np.int32)); me.update(calc_edges=True); me.validate()
    if smooth: me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    o = bpy.data.objects.new(name, me); (coll or bpy.context.scene.collection).objects.link(o); return o


def st(x):
    x = np.asarray(x) * MM
    return {'p50': round(float(np.median(x)), 2), 'p95': round(float(np.percentile(x, 95)), 2), 'max': round(float(x.max()), 2)} if len(x) else None


def boundary_loops(V, lv, lt):
    """closed boundary loops walked through the face fans (a vertex where the boundary touches itself is passed
    once per fan, so pinched holes come out as separate loops). Returns [vertex index list] and the count of
    boundary edges that could not be walked (non-manifold)."""
    me = bpy.data.meshes.new('_b'); me.vertices.add(len(V)); me.vertices.foreach_set('co', V.ravel().astype(np.float32))
    me.loops.add(len(lv)); me.loops.foreach_set('vertex_index', lv.astype(np.int32)); me.polygons.add(len(lt))
    me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(lt)[:-1]]).astype(np.int32))
    me.polygons.foreach_set('loop_total', lt.astype(np.int32)); me.update(calc_edges=True)
    bm = bmesh.new(); bm.from_mesh(me); bm.edges.ensure_lookup_table(); seen = set(); out = []; bad = 0
    for e in bm.edges:
        if not e.is_boundary or e.index in seen: continue
        if len(e.link_loops) != 1: bad += 1; continue
        l = e.link_loops[0]; start = l; chain = []; ok = True
        while True:
            seen.add(l.edge.index); chain.append(l.vert.index); n = l.link_loop_next; guard = 0
            while not n.edge.is_boundary:
                if len(n.edge.link_loops) != 2: ok = False; break
                n = n.link_loop_radial_next.link_loop_next; guard += 1
                if guard > 64: ok = False; break
            if not ok: break
            l = n
            if l == start or len(chain) > 200000: break
        if ok and l == start: out.append(chain)
        else: bad += 1
    bm.free(); bpy.data.meshes.remove(me)
    return out, bad


def loop_info(V, L):
    P = V[L]; c = np.vstack([P, P[:1]])
    return {'verts': len(L), 'length_mm': round(float(np.linalg.norm(np.diff(c, axis=0), axis=1).sum() * MM), 1),
            'centre_mm': (P.mean(0) * MM).round(1).tolist(), 'size_mm': (np.ptp(P, 0) * MM).round(1).tolist()}


def load_old(sym_dir):
    LT = {int(k): np.array(v) for k, v in json.load(open(os.path.join(sym_dir, 'landmarks.json'))).items() if not k.startswith('_')}
    EM = json.load(open(os.path.join(sym_dir, 'eyes_meta.json')))
    with bpy.data.libraries.load(os.path.join(sym_dir, 'base.blend')) as (src, dst): dst.objects = [n for n in src.objects if n == 'orig']
    o = dst.objects[0]; V, lv, lt = obj_arrays(o); bpy.data.objects.remove(o, do_unlink=True)
    return LT, EM, V, lv, lt


def face_box(LT):
    brow = (LT[2][2] + LT[5][2]) / 2; chin = LT[24][2]; H = brow - chin
    return {'zlo': chin - 0.12 * H, 'zhi': brow + 0.35 * H, 'xmax': abs(LT[13][0]) + 0.22 * H,
            'ymax': (LT[13][1] + LT[7][1]) / 2 + 0.25 * H, 'H': H}


def in_box(P, B): return (P[:, 2] > B['zlo']) & (P[:, 2] < B['zhi']) & (np.abs(P[:, 0]) < B['xmax']) & (P[:, 1] < B['ymax'])


def apply(G, P): return P @ G[:3, :3].T + G[:3, 3]


def rot(axis, ang): return np.array(Matrix.Rotation(ang, 3, Vector(axis))) if abs(ang) > 1e-15 else np.eye(3)


def icp_face(Xs, G, bvh_ref, B, iters, mode='sim', keep=0.85):
    """point-to-plane ICP of samples Xs (own frame) under G onto the reference, face box only.
    mode 'sim': rotation + translation + scale; 'pitch': rotation about x, y/z translation, scale (mirror plane kept)."""
    for _ in range(iters):
        Y = apply(G, Xs); sel = in_box(Y, B); Y = Y[sel]
        if len(Y) < 100: return G, 1e9, np.array([1e9])
        Q, N, d = nearest(bvh_ref, Y); k = d <= np.percentile(d, keep * 100); Y, Q, N = Y[k], Q[k], N[k]
        c = Y.mean(0); Yc = Y - c; b = (N * (Q - Y)).sum(1)
        if mode == 'sim':
            A = np.hstack([np.cross(Yc, N), N, (N * Yc).sum(1, keepdims=True)])
            x = np.linalg.lstsq(A, b, rcond=None)[0]; w, tau, sg = x[:3], x[3:6], x[6]
        else:
            A = np.stack([np.cross(Yc, N)[:, 0], N[:, 1], N[:, 2], (N * Yc).sum(1)], 1)
            x = np.linalg.lstsq(A, b, rcond=None)[0]; w, tau, sg = np.array([x[0], 0, 0]), np.array([0, x[1], x[2]]), x[3]
        wn = float(np.linalg.norm(w)); Ru = rot(w / wn, wn) if wn > 1e-12 else np.eye(3)
        D = np.eye(4); D[:3, :3] = (1 + sg) * Ru; D[:3, 3] = c + tau - (1 + sg) * Ru @ c
        G = D @ G
        if wn < 1e-7 and np.linalg.norm(tau) < 1e-8 and abs(sg) < 1e-7: break
    Y = apply(G, Xs); Y = Y[in_box(Y, B)]
    if len(Y) < 100: return G, 1e9, np.array([1e9])
    _, _, d = nearest(bvh_ref, Y); ds = np.sort(d)[:int(len(d) * keep)]
    return G, float(np.sqrt((ds ** 2).mean())), d


def mirror_plane(Y, bvh_self, iters=30, keep=0.8):
    """the mirror plane of a near-symmetric surface: the x-mirrored samples are registered (rigid, point-to-plane)
    onto the surface; R*S is then a reflection whose -1 eigenvector is the plane normal."""
    R = np.eye(3); t = np.zeros(3); Z0 = Y * MX
    for _ in range(iters):
        Z = Z0 @ R.T + t; Q, N, d = nearest(bvh_self, Z); k = d <= np.percentile(d, keep * 100)
        Z, Q, N = Z[k], Q[k], N[k]; c = Z.mean(0); Zc = Z - c
        A = np.hstack([np.cross(Zc, N), N]); b = (N * (Q - Z)).sum(1); x = np.linalg.lstsq(A, b, rcond=None)[0]
        w, tau = x[:3], x[3:]; wn = float(np.linalg.norm(w)); Ru = rot(w / wn, wn) if wn > 1e-12 else np.eye(3)
        R = Ru @ R; t = Ru @ (t - c) + c + tau
        if wn < 1e-8 and np.linalg.norm(tau) < 1e-9: break
    A_ = R @ np.diag(MX); ev, evec = np.linalg.eigh((A_ + A_.T) / 2); n = evec[:, 0]
    if n[0] < 0: n = -n
    d_ = float(n @ t) / 2
    Z = Z0 @ R.T + t; _, _, dd = nearest(bvh_self, Z)
    return n, d_, float(np.sqrt((np.sort(dd)[:int(len(dd) * keep)] ** 2).mean()))


def plane_to_x(n, d, cen):
    """rigid map taking plane n.p = d onto x = 0 with the least rotation (about n x X: yaw / roll only)."""
    x = np.array([1.0, 0, 0]); ax = np.cross(n, x); s = np.linalg.norm(ax); ang = math.atan2(s, n @ x)
    Rq = rot(ax / s, ang) if s > 1e-12 else np.eye(3)
    c = cen - (n @ cen - d) * n; G = np.eye(4); G[:3, :3] = Rq; G[:3, 3] = np.array([0, c[1], c[2]]) - Rq @ c
    return G, math.degrees(ang)


# ------------------------------------------------------------------ renders
def render_setup(res=900):
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = res
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_cavity = False; sh.show_object_outline = False
    if not sc.world: sc.world = bpy.data.worlds.new('w')
    sc.world.color = (0.93, 0.93, 0.93); sc.view_settings.view_transform = 'Standard'; sc.render.film_transparent = False
    cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.clip_end = 20; co = bpy.data.objects.new('cam', cam)
    sc.collection.objects.link(co); sc.camera = co
    return sc, co


def wire_copy(o, col=(0.05, 0.05, 0.07, 1)):
    w = o.copy(); w.data = o.data; w.name = o.name + '_wire'; bpy.context.scene.collection.objects.link(w)
    m = w.modifiers.new('wf', 'WIREFRAME'); m.use_replace = True; m.use_even_offset = False; w.color = col
    return w, m


def curve_obj(P, closed, col, rad, name='ln'):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; sp = cu.splines.new('POLY')
    sp.points.add(len(P) - 1); sp.points.foreach_set('co', np.hstack([P, np.ones((len(P), 1))]).ravel().astype(np.float32))
    sp.use_cyclic_u = closed; cu.bevel_depth = rad; cu.bevel_resolution = 2
    o = bpy.data.objects.new(name, cu); o.color = (*col, 1); bpy.context.scene.collection.objects.link(o); return o


def shoot(sc, co, path, centre, dirv, size):
    d = Vector(dirv).normalized(); co.data.ortho_scale = size
    co.location = Vector(tuple(centre)) - d * 3.0; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ edge loops (ported from topo_eval.py)
class Topo:
    def __init__(s, V, lv, lt):
        s.V, s.lv, s.lt = V, lv, lt
        s.ls = np.concatenate([[0], np.cumsum(lt)[:-1]]); nl = len(lv); s.lp = np.repeat(np.arange(len(lt)), lt)
        nxt = np.arange(nl) + 1; nxt[s.ls + lt - 1] = s.ls; s.nxt = nxt
        prv = np.arange(nl) - 1; prv[s.ls] = s.ls + lt - 1; s.prv = prv
        pr = np.sort(np.stack([lv, lv[nxt]], 1), 1); s.E, s.le = np.unique(pr, axis=0, return_inverse=True); s.le = s.le.ravel()
        s.efc = np.bincount(s.le, minlength=len(s.E)); s.val = np.bincount(s.E.ravel(), minlength=len(V))
        s.bnd_v = np.zeros(len(V), bool); s.bnd_v[s.E[s.efc == 1].ravel()] = True
        s.elen = np.linalg.norm(V[s.E[:, 0]] - V[s.E[:, 1]], axis=1)
        s.eid = {(int(a), int(b)): i for i, (a, b) in enumerate(s.E)}
    def ekey(s, a, b): return s.eid[(a, b) if a < b else (b, a)]
    def other(s, e, v): return int(s.E[e][1] if s.E[e][0] == v else s.E[e][0])
    def opp_map(s, near):
        vedges, adjf = {}, {}
        for c in np.where(near[s.lv])[0]:
            v = int(s.lv[c]); e1, e2 = int(s.le[c]), int(s.le[s.prv[c]])
            vedges.setdefault(v, set()).update((e1, e2)); adjf.setdefault((v, e1), set()).add(e2); adjf.setdefault((v, e2), set()).add(e1)
        opp = {}
        for v, es in vedges.items():
            if len(es) != 4 or s.bnd_v[v] or s.val[v] != 4: continue
            for e in es:
                o = es - {e} - adjf.get((v, e), set())
                if len(o) == 1: opp[(v, e)] = o.pop()
        return opp


def poly_near(P, C, closed):
    """distance of points P to polyline C and the arc-length parameter (0..1) of the nearest point."""
    A = C if closed else C[:-1]; Bq = np.roll(C, -1, 0) if closed else C[1:]; AB = Bq - A; L2 = np.maximum((AB ** 2).sum(1), 1e-18)
    sl = np.sqrt(L2); cum = np.concatenate([[0], np.cumsum(sl)]); out, par = np.empty(len(P)), np.empty(len(P))
    for i in range(0, len(P), 1500):
        Q = P[i:i + 1500, None, :] - A[None]; u = np.clip((Q * AB).sum(2) / L2, 0, 1)
        dd = np.linalg.norm(Q - u[..., None] * AB, axis=2); j = dd.argmin(1); r = np.arange(len(j))
        out[i:i + 1500] = dd[r, j]; par[i:i + 1500] = (cum[j] + u[r, j] * sl[j]) / cum[-1]
    return out, par % 1.0


def resample_closed(C, step):
    P = np.vstack([C, C[:1]]); seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
    n = max(int(s[-1] / step), 8); q = np.linspace(0, s[-1], n, endpoint=False)
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)


def plane_angle(Q):
    c = Q.mean(0); U = np.linalg.svd(Q - c)[2]; ax, ay = U[0], U[1]
    return lambda P: (np.arctan2((P - c) @ ay, (P - c) @ ax) / (2 * np.pi)) % 1.0


def winding(t):
    dt = (np.diff(np.concatenate([t, t[:1]])) + 0.5) % 1.0 - 0.5
    return float(dt.sum()), float(np.abs(dt).max())


def loop_dev(Pv, Q):
    P = np.vstack([Pv, 0.5 * (Pv + np.roll(Pv, -1, 0))]); a = poly_near(P, Q, True)[0]; b = poly_near(Q, Pv, True)[0]
    return {'mean_mm': round(float(a.mean() * MM), 2), 'max_mm': round(float(a.max() * MM), 2),
            'target_to_loop_max_mm': round(float(b.max() * MM), 2)}


def match_loop(T, Q, band_r=0.004):
    """the mesh edge loop that best follows the closed target curve Q: true edge loops (straight through valence-4
    vertices) in a band around Q, else the cheapest closed edge path that advances along Q (deviation-weighted).
    Returns (vertex list, info)."""
    V = T.V; lo, hi = Q.min(0) - 0.02, Q.max(0) + 0.02; box = np.all((V > lo) & (V < hi), 1)
    d = np.full(len(V), 1e9); d[box] = poly_near(V[box], Q, True)[0]
    band = d < band_r; opp = T.opp_map(d < 0.012); ang = plane_angle(Q)
    res = []
    starts = np.where(band[T.E[:, 0]] & band[T.E[:, 1]])[0].tolist(); seen = set()
    for e0 in starts:
        if e0 in seen: continue
        a, b = int(T.E[e0][0]), int(T.E[e0][1]); vs, es, e, v, closed = [a, b], [e0], e0, b, False
        while len(es) < 3000:
            e2 = opp.get((v, e))
            if e2 is None: break
            if e2 == e0: closed = True; break
            v = T.other(e2, v)
            if not band[v]: break
            es.append(e2); vs.append(v); e = e2
        seen.update(es)
        if closed and vs[-1] == a:
            vs = vs[:-1]; w, jmp = winding(ang(V[vs]))
            if abs(abs(w) - 1) < 0.2 and jmp < 0.25: r = loop_dev(V[vs], Q); r['kind'] = 'edge_loop'; r['straight'] = 1.0; res.append((r, vs))
    # cheapest closed path (two-layer cover so the cycle goes once around; edges may not jump > 20 % of the arc)
    SIG = 0.00075; Rb = max(0.006, 3 * float(np.median(T.elen))); band2 = d < Rb
    es = np.where(band2[T.E[:, 0]] & band2[T.E[:, 1]])[0]; bi = np.where(band2)[0]
    t = np.zeros(len(V)); t[bi] = poly_near(V[bi], Q, True)[1]; adj = {}
    for e in es:
        a, b = map(int, T.E[e]); dt = (t[b] - t[a] + 0.5) % 1.0 - 0.5
        if abs(dt) > 0.2: continue
        c = int((t[b] < t[a] and dt > 0) or (t[b] > t[a] and dt < 0)); we = T.elen[e] * (1 + ((d[a] + d[b]) / 2 / SIG) ** 2)
        for l in (0, 1):
            adj.setdefault(2 * a + l, []).append((2 * b + (l ^ c), we)); adj.setdefault(2 * b + (l ^ c), []).append((2 * a + l, we))
    import heapq
    def dijkstra(src, dst):
        dist, prev, h = {src: 0.0}, {}, [(0.0, src)]
        while h:
            du, u = heapq.heappop(h)
            if u == dst: break
            if du > dist[u]: continue
            for v_, w_ in adj.get(u, ()):
                nd = du + w_
                if nd < dist.get(v_, 1e18): dist[v_] = nd; prev[v_] = u; heapq.heappush(h, (nd, v_))
        if dst not in dist: return None, 1e18
        p = [dst]
        while p[-1] != src: p.append(prev[p[-1]])
        return p[::-1], dist[dst]
    src = sorted([int(v) for v in bi if t[v] < 0.04 or t[v] > 0.96], key=lambda v: d[v])[:6]; best = (None, 1e18)
    for s_ in src:
        p, c_ = dijkstra(2 * s_, 2 * s_ + 1)
        if p and c_ < best[1]: best = (p, c_)
    if best[0] is not None:
        vs = [x // 2 for x in best[0]][:-1]
        if len(vs) >= 3:
            ok = []
            for i in range(len(vs)):
                e_in = T.ekey(vs[i - 1], vs[i]); e_out = T.ekey(vs[i], vs[(i + 1) % len(vs)]); ok.append(opp.get((vs[i], e_in)) == e_out)
            r = loop_dev(V[vs], Q); r['kind'] = 'path'; r['straight'] = round(float(np.mean(ok)), 3); res.append((r, vs))
    if not res: return None, {'kind': 'none'}
    loops_ = sorted([x for x in res if x[0]['kind'] == 'edge_loop'], key=lambda x: x[0]['mean_mm'])
    paths = [x for x in res if x[0]['kind'] == 'path']
    pick = loops_[0] if loops_ and (not paths or loops_[0][0]['mean_mm'] <= paths[0][0]['mean_mm'] + 0.3) else (paths[0] if paths else loops_[0])
    info = dict(pick[0]); info['edge_loops_in_band'] = len(loops_); info['verts'] = len(pick[1])
    return pick[1], info


def eyeball_cut(T, Ve, lve, lte, C, r):
    """closed curve where the skin passes under the eyeball surface (skin edges crossing the eyeball, signed by the
    eyeball's outward normal), the longest loop in front of the eyeball centre."""
    V = T.V; bvh_e = bvh_of(Ve, lve, lte); reg = np.linalg.norm(V - C, axis=1) < 2.2 * r
    sd = np.full(len(V), 1.0)
    for i in np.where(reg)[0]:
        q, n, _, dd = bvh_e.find_nearest(Vector(V[i])); q = np.array(q); n = np.array(n)
        if (q - C) @ n < 0: n = -n
        sd[i] = dd if (V[i] - q) @ n >= 0 else -dd
    sd[sd == 0] = 1e-12
    E = T.E; s0, s1 = sd[E[:, 0]], sd[E[:, 1]]; cr = (np.sign(s0) != np.sign(s1)) & reg[E[:, 0]] & reg[E[:, 1]]
    tt = np.where(cr, s0 / np.where(cr, s0 - s1, 1), 0); P = V[E[:, 0]] + tt[:, None] * (V[E[:, 1]] - V[E[:, 0]])
    fe = {}
    for c_ in np.where(cr[T.le])[0]: fe.setdefault(int(T.lp[c_]), []).append(int(T.le[c_]))
    link = {}
    for f, es in fe.items():
        es = list(dict.fromkeys(es))
        if len(es) % 2:                                           # a vertex on the eyeball surface: drop the most degenerate
            es.remove(min(es, key=lambda e: min(abs(sd[E[e, 0]]), abs(sd[E[e, 1]]))))
        for k in range(0, len(es) - 1, 2): link.setdefault(es[k], []).append(es[k + 1]); link.setdefault(es[k + 1], []).append(es[k])
    seen, curves = set(), []
    for e0 in link:
        if e0 in seen: continue
        chain = [e0]; seen.add(e0); prev, cur = None, e0
        while True:
            nx = [x for x in link[cur] if x != prev and x not in seen]
            if not nx: break
            prev, cur = cur, nx[0]; chain.append(cur); seen.add(cur)
        closed = e0 in link.get(chain[-1], []) and len(chain) > 3
        if closed: curves.append(P[chain])
    global CUT_DBG
    CUT_DBG = {'crossing_edges': int(cr.sum()), 'faces_by_count': np.bincount([len(set(v)) for v in fe.values()]).tolist(),
               'link_deg': np.bincount([len(v) for v in link.values()]).tolist(), 'efc_cross': np.bincount(T.efc[cr]).tolist(), 'closed_curves': len(curves), 'front': [round(float(c[:, 1].mean() - C[1]) * MM, 1) for c in curves],
               'lengths': [len(c) for c in curves], 'open_chains': len(link) - sum(len(c) for c in curves)}
    curves = [c for c in curves if c[:, 1].mean() < C[1]]
    curves.sort(key=lambda c: -np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1).sum())
    return (curves[0] if curves else None), sd


def robust_sphere(P):
    c, r = sphere_fit(P)
    for _ in range(3):
        res = np.abs(np.linalg.norm(P - c, axis=1) - r); k = res <= np.percentile(res, 80); c, r = sphere_fit(P[k])
    return c, r, float(np.abs(np.linalg.norm(P - c, axis=1) - r).mean())


def hit_y(bvh, x, z):
    h = bvh.ray_cast(Vector((x, -3.0, z)), Vector((0, 1, 0)))
    return None if h[0] is None else h[0].y


def lip_seam(bvh, z0, xmax, step=0.0005):
    """closed-mouth lip line from the front: per x the most recessed point (largest y) near the previous one, and
    the crease contrast (its depth below the lips 3 mm above and below)."""
    out = []; zc = z0; win = 0.006
    for x in np.arange(0.0, xmax, step):
        best = None
        for z in np.arange(zc - win, zc + win + 1e-9, 0.0002):
            y = hit_y(bvh, x, z)
            if y is not None and (best is None or y > best[0]): best = (y, z)
        if best is None: break
        y, z = best; ya, yb = hit_y(bvh, x, z + 0.003), hit_y(bvh, x, z - 0.003)
        con = y - 0.5 * ((ya if ya is not None else y) + (yb if yb is not None else y))
        out.append([x, y, z, con]); zc = z; win = 0.0015
    return np.array(out)


def seam_corner(seam, x_old):
    """mouth corner = where the lip crease fades: first sample beyond 0.4 x_old whose contrast drops under 15 % of
    the median contrast of the inner half (at least 0.3 mm); the corner is the sample before it."""
    inner = seam[seam[:, 0] < 0.5 * x_old]; tau = max(0.0003, 0.15 * float(np.median(inner[:, 3])))
    below = np.where(seam[:, 3] < tau)[0]; below = below[seam[below, 0] > 0.4 * x_old]
    return ((below[0] - 1) if len(below) else len(seam) - 1), tau, inner


def vertex_normals(V, lv, lt):
    tr = tris(lv, lt); fn = np.cross(V[tr[:, 1]] - V[tr[:, 0]], V[tr[:, 2]] - V[tr[:, 0]]); N = np.zeros_like(V)
    for j in range(3): np.add.at(N, tr[:, j], fn)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-15)


def build_points(Vs, lvs, lts, eyeball, LTo, EMo, opts, sym_tol):
    """landmarks (35-point numbering) and eyes_meta on a head skin from the left (+x) features, mirrored.
    eyeball = (V, lv, lt) of the +x eyeball piece or None. sym_tol: |x| below which a vertex counts as centre line.
    opts: 'mp' = {k: 3D} MediaPipe points shot onto this skin from a clay front render (the method that made the old
    landmarks), used for the brows, nose tip, chin and the mouth corners' extent when they agree within 12 mm (chin
    15 mm) with the fallbacks: old point snapped onto the skin (brows, chin onto the centre profile), most forward
    centre point (nose tip), end of the lip crease (mouth corner)."""
    T = Topo(Vs, lvs, lts); bvh = bvh_of(Vs, lvs, lts); info = {}
    N = vertex_normals(Vs, lvs, lts)
    if np.mean(((Vs - Vs.mean(0)) * N).sum(1) > 0) < 0.5: N = -N
    snap = lambda p: np.array(bvh.find_nearest(Vector(p))[0])
    CL = np.array(EMo['L']['C']); r_old = float(EMo['L']['r'])
    # ---- left eye: hole loop if the skin has one, else the edge loop at the skin / eyeball crossing
    if eyeball is not None: C, r, sres = robust_sphere(eyeball[0]); info['eyeball_sphere'] = {'r_mm': round(r * MM, 2), 'res_mm': round(sres * MM, 2)}
    else: C, r = CL.copy(), r_old; info['eyeball_sphere'] = None
    loops, _ = boundary_loops(Vs, lvs, lts); holes = []; inner_holes = []
    for L in loops:
        P = Vs[L]
        if len(L) >= 12 and np.linalg.norm(P.mean(0) - CL) < 1.6 * r_old + 0.01 and np.ptp(P[:, 0]) > 0.6 * r_old and P[:, 0].min() > 0:
            deep = float(np.mean(np.linalg.norm(P - C, axis=1) < 0.85 * r)) if eyeball is not None else 0.0
            (inner_holes if deep > 0.5 else holes).append(L)
    info['eye_holes_L'] = {'opening': [len(L) for L in holes], 'inside_eyeball': [len(L) for L in inner_holes]}
    cut = None
    if holes:
        L = max(holes, key=lambda L: np.ptp(Vs[L][:, 0]) * np.ptp(Vs[L][:, 2])); margin = Vs[L]
        info['margin'] = {'kind': 'hole', 'verts': len(L)}; vids = list(L)
    else:
        cut, sd = eyeball_cut(T, *eyeball, C, r) if eyeball is not None else (None, None)
        if cut is None: raise SystemExit('no eye margin found ' + json.dumps(globals().get('CUT_DBG')))
        Q = resample_closed(cut, 0.0005); vids, mi = match_loop(T, Q)
        margin = Vs[vids]; mi['signed_offset_mm'] = round(float(np.mean(sd[vids]) * MM), 2)
        info['margin'] = mi; info['margin']['cut_length_mm'] = round(float(np.linalg.norm(np.diff(np.vstack([cut, cut[:1]]), axis=0), axis=1).sum() * MM), 1)
    lid = lids(margin, np.linspace(0, 1, 5))
    def arcmid(P):
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; return np.array([np.interp(s[-1] / 2, s, P[:, j]) for j in range(3)])
    A = lid['inner'] - lid['outer']; A /= np.linalg.norm(A)
    def rs(P, n=48):
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; t = np.linspace(0, s[-1], n)
        return np.c_[[np.interp(t, s, P[:, j]) for j in range(3)]].T
    up, lo = rs(lid['up_path']), rs(lid['lo_path']); raw = np.r_[up, lo[::-1][1:-1]]
    EO = {}
    for s_, f in (('L', np.ones(3)), ('R', MX)):
        EO[s_] = {'C': (C * f).tolist(), 'r': float(r), 'A': (A * f).tolist(), 'up_path': (up * f).tolist(), 'lo_path': (lo * f).tolist(),
                  'raw': (raw * f).tolist(), 'margin_kind': info['margin']['kind']}
        if cut is not None: EO[s_]['skin_eyeball_crossing'] = (cut * f).tolist()
    # ---- landmarks: left side computed, right mirrored, centre on x = 0
    LN = {}; src = {}; mp = opts.get('mp') or {}
    LN[13], LN[11] = lid['outer'], lid['inner']; LN[12], LN[14] = arcmid(lid['up_path']), arcmid(lid['lo_path'])
    cv = np.where(np.abs(Vs[:, 0]) < sym_tol)[0]; CV, CN = Vs[cv], N[cv]
    z0 = (LTo[34][2] + LTo[35][2]) / 2; seam = lip_seam(bvh, z0, abs(LTo[22][0]) * 1.6)
    jc, tau, inner = seam_corner(seam, abs(LTo[22][0]))
    G_ = {k: snap(LTo[k]) for k in (4, 5, 6)}                     # geometric definitions (fallbacks)
    P_ = CV[np.abs(CV[:, 2] - LTo[16][2]) < 0.02]; G_[16] = P_[np.argmin(P_[:, 1])]       # nose tip: most forward
    ex = np.array([bvh.ray_cast(Vector(tuple(p + n * 2e-4)), Vector(tuple(n)), 0.3)[0] is None for p, n in zip(CV, CN)])
    CVx = CV[ex & (CN[:, 1] < 0.2)]; G_[24] = CVx[np.argmin(np.linalg.norm(CVx - LTo[24], axis=1))]    # old chin onto the profile
    G_[22] = seam[jc, :3]
    mpL = {}
    for a, b in ((3, 4), (2, 5), (1, 6), (20, 22)):
        if a in mp and b in mp: mpL[b] = (np.array(mp[b]) + np.array(mp[a]) * MX) / 2
    for k in (16, 24):
        if k in mp: mpL[k] = np.array(mp[k])
    def use(k, cand, how):
        if cand is not None and G_[k] is not None and np.linalg.norm(cand - G_[k]) < (0.015 if k == 24 else 0.012): LN[k] = cand; src[k] = how
        elif G_[k] is not None: LN[k] = G_[k]; src[k] = 'geometry'
        else: LN[k] = cand; src[k] = how
    for k in (4, 5, 6): use(k, snap(mpL[k]) if k in mpL else None, 'mediapipe')
    c16 = None
    if 16 in mpL:
        y = hit_y(bvh, 0.0, mpL[16][2]); c16 = None if y is None else np.array([0.0, y, mpL[16][2]])
    use(16, c16, 'mediapipe')
    c24 = None
    if 24 in mpL:
        k_ = (np.abs(CV[:, 2] - mpL[24][2]) < 0.003) & (CN[:, 1] < 0.1) & (CV[:, 1] < seam[0, 1] + 0.03)
        if k_.any(): c24 = CV[k_][np.argmin(CV[k_][:, 1])]
    use(24, c24, 'mediapipe')
    c22 = None; jcorner = jc
    if 22 in mpL:
        lim = min(len(seam), jc + 9); d_ = np.linalg.norm(seam[:lim][:, [0, 2]] - mpL[22][[0, 2]], axis=1); jcorner = int(np.argmin(d_)); c22 = seam[jcorner, :3]
    use(22, c22, 'mediapipe x on the lip line')
    if src[22] == 'geometry': jcorner = jc
    c0 = seam[0, :3].copy(); c0[0] = 0.0; LN[34] = c0; LN[35] = c0.copy()
    LN[31] = CV[np.argmax(CV[:, 2])]
    info['lip'] = {'crease_end_x_mm': round(float(seam[jc, 0] * MM), 1), 'corner_x_mm': round(float(LN[22][0] * MM), 1),
                   'crease_tau_mm': round(tau * MM, 2), 'crease_centre_mm': round(float(inner[:, 3].max() * MM), 2)}
    info['mediapipe_vs_geometry_mm'] = {str(k): round(float(np.linalg.norm(mpL[k] - G_[k]) * MM), 1) for k in mpL if G_.get(k) is not None}
    info['point_source'] = {str(k): v for k, v in src.items()}
    seamL = seam[:jcorner + 1, :3]
    for a, b in PAIRS: LN[a] = LN[b] * MX
    for k in CENTRE: LN[k] = np.array(LN[k], float); LN[k][0] = 0.0
    out = {'_source': 'p2_base', '_lip_seam': np.r_[(seamL[::-1] * MX)[:-1], seamL].tolist()}
    for k in sorted(LN): out[str(k)] = np.asarray(LN[k], float).tolist()
    info['landmark_shift_from_old_mm'] = {str(k): round(float(np.linalg.norm(LN[k] - LTo[k]) * MM), 1) for k in sorted(LN)}
    return out, EO, info, vids


# ================================================================== prep
if MODE == 'prep':
    FBX, OLD, TQA, OUT = argv[1], argv[2], argv[3], os.path.abspath(argv[4])
    WK = os.path.join(OUT, '_work'); os.makedirs(WK, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = np.random.default_rng(0); qa = {'fbx': os.path.abspath(FBX)}
    LT, EM, Vo, lvo, lto = load_old(OLD); bvh_old = bvh_of(Vo, lvo, lto); B = face_box(LT)
    V, lv, lt = load_fbx(FBX)
    ls, E, le, efc = edges_of(lv, lt)
    vlab = label_prop(len(V), E[:, 0], E[:, 1]); plab = vlab[lv[ls]]
    ul, cnt = np.unique(plab, return_counts=True); head = ul[np.argmax(cnt)]
    # ---- skin = largest patch of the head piece joined across manifold edges
    lp = np.repeat(np.arange(len(lt)), lt); m2 = efc[le] == 2
    cs = np.where(m2)[0]; cs = cs[np.argsort(le[cs], kind='stable')]
    flab = label_prop(len(lt), lp[cs[0::2]], lp[cs[1::2]])
    hf = plab == head; fl_u, fl_c = np.unique(flab[hf], return_counts=True); skin_l = fl_u[np.argmax(fl_c)]
    skin_f = hf & (flab == skin_l)
    qa['head_piece_faces'] = int(hf.sum()); qa['skin_faces'] = int(skin_f.sum())
    qa['fused_patches'] = [int(c) for u, c in sorted(zip(fl_u, fl_c), key=lambda x: -x[1]) if u != skin_l]
    Vs, lvs, lts = sub_mesh(V, lv, lt, skin_f)
    _, Es, les, efcs = edges_of(lvs, lts)
    qa['skin_nonmanifold_edges'] = int((efcs > 2).sum())
    # ---- alignment
    M0 = np.array(json.load(open(TQA))['align']['matrix'])
    Xs = samples(Vs, lvs, lts, 12000, rng)
    s0 = float(np.cbrt(abs(np.linalg.det(M0[:3, :3]))))
    G1 = np.eye(4); G1[:3, :3] *= s0                                        # upright start (Tripo frame: face -y, z up)
    Y = apply(G1, Vs); top = Y[:, 2].max(); G1[2, 3] = LT[31][2] - top
    Y = apply(G1, Vs); band = (Y[:, 2] > LT[24][2]) & (Y[:, 2] < (LT[2][2] + LT[5][2]) / 2)
    G1[0, 3] = -np.median(Y[band, 0]); G1[1, 3] = LT[16][1] - Y[band, 1].min()
    starts = []
    for nm, G in (('topo_eval', M0), ('upright', G1)):
        n_in = int(in_box(apply(G, Xs), B).sum())
        G, rms, _ = icp_face(Xs, G, bvh_old, B, 25)
        # the face must look toward -y: the old nose tip has new skin in front of / at it, facing -y
        loc, nrm, _, dn = bvh_of(apply(G, Vs), lvs, lts).find_nearest(Vector(LT[16]))
        Rn = G[:3, :3] / np.cbrt(abs(np.linalg.det(G[:3, :3])))                # Tripo's own frame is upright already
        ok = loc is not None and dn < 0.015 and min(Rn[0, 0], Rn[1, 1], Rn[2, 2]) > 0.7
        starts.append((rms if ok else 1e9, nm, G, n_in, round(dn * MM, 1) if loc else None))
    starts.sort(key=lambda s: s[0])
    qa['align_starts'] = [{'start': s[1], 'face_rms_mm': round(s[0] * MM, 2), 'box_pts_at_start': s[3], 'nose_gap_mm': s[4]} for s in starts]
    rms, nm, G = starts[0][:3]; qa['align_start_used'] = nm; qa['face_rms_after_sim_mm'] = round(rms * MM, 2)
    if rms > 0.05: raise SystemExit('ALIGN failed ' + json.dumps(qa['align_starts']))
    # mirror plane -> x = 0 (2 rounds), then scale / pitch / y / z on the face with the plane held
    hb = None; plane_log = []
    for it in range(3):
        Yv = apply(G, Vs); bvh_self = bvh_of(Yv, lvs, lts)
        Yh = apply(G, Xs); keep_h = Yh[:, 2] > LT[24][2] - 0.25 * B['H']      # head, not shoulders / collar
        n, d, mrms = mirror_plane(Yh[keep_h][::3], bvh_self)
        C, ang = plane_to_x(n, d, Yh[keep_h].mean(0))
        plane_log.append({'normal': n.round(5).tolist(), 'offset_mm': round(d * MM, 2), 'turn_deg': round(ang, 3), 'mirror_rms_mm': round(mrms * MM, 2)})
        if it == 2: break
        G = C @ G
        G, rms, _ = icp_face(Xs, G, bvh_old, B, 20, mode='pitch')
    qa['mirror_plane'] = plane_log
    G, rms, dface = icp_face(Xs, G, bvh_old, B, 1, mode='pitch')
    s_fin = float(np.cbrt(abs(np.linalg.det(G[:3, :3]))))
    qa['align'] = {'matrix': G.round(8).tolist(), 'scale': round(s_fin, 6), 'face_trimmed_rms_mm': round(rms * MM, 2),
                   'face_dist_mm': st(dface), 'topo_eval_rms_mm': json.load(open(TQA))['align']['trimmed_rms_mm']}
    V = apply(G, V); Vs = apply(G, Vs)
    # old -> new both ways on the face (shape difference)
    Pn = samples(Vs, lvs, lts, 20000, rng); Pn = Pn[in_box(Pn, B)]; bvh_new = bvh_of(Vs, lvs, lts)
    Po = samples(Vo, lvo, lto, 20000, rng); Po = Po[in_box(Po, B)]
    qa['face_surface_mm'] = {'new_to_old': st(nearest(bvh_old, Pn)[2]), 'old_to_new': st(nearest(bvh_new, Po)[2])}
    # orientation: share of skin faces facing away from the head centre
    tr = tris(lvs, lts); fn = np.cross(Vs[tr[:, 1]] - Vs[tr[:, 0]], Vs[tr[:, 2]] - Vs[tr[:, 0]])
    cen = Vs.mean(0); outw = ((Vs[tr].mean(1) - cen) * fn).sum(1) > 0
    qa['skin_outward_share'] = round(float(outw.mean()), 3)
    if outw.mean() < 0.4:
        lvs = np.concatenate([x[::-1] for x in np.split(lvs, np.cumsum(lts)[:-1])]); qa['skin_flipped'] = True
    # ---- pieces: other connected pieces + fused patches (each split into connected parts)
    pieces = []
    for u in ul:
        if u == head: continue
        pieces.append(sub_mesh(V, lv, lt, plab == u) + (False, None))
    for u in fl_u:
        if u == skin_l: continue
        fp = hf & (flab == u); Pv, Pl, Pt = sub_mesh(V, lv, lt, fp)
        ids = np.unique(lv[np.repeat(fp, lt)])                     # original vertex ids (sub_mesh keeps their order)
        _, Ep, _, _ = edges_of(Pl, Pt); lab2 = label_prop(len(Pv), Ep[:, 0], Ep[:, 1])
        pl2 = lab2[Pl[np.concatenate([[0], np.cumsum(Pt)[:-1]])]]
        for w in np.unique(pl2):
            sv, sl_, st_ = sub_mesh(Pv, Pl, Pt, pl2 == w); used = np.unique(Pl[np.repeat(pl2 == w, Pt)])
            pieces.append((sv, sl_, st_, True, set(ids[used].tolist())))
    bvh_new = bvh_of(Vs, lvs, lts)
    eyeC = {s: np.array(EM[s]['C']) for s in 'LR'}; r_old = float(EM['L']['r'])
    def side_of(c): return 'L' if c[0] > 0.004 else ('R' if c[0] < -0.004 else 'C')
    PI = []
    for k, pc in enumerate(pieces):
        Pv, Pl, Pt, fused = pc[:4]; c = Pv.mean(0); size = np.ptp(Pv, 0)
        sc_, sr = sphere_fit(Pv); sres = float(np.abs(np.linalg.norm(Pv - sc_, axis=1) - sr).mean())
        side = side_of(c); info = {'faces': int(len(Pt)), 'verts': len(Pv), 'fused': bool(fused), 'side': side,
                                   'centre_mm': (c * MM).round(1).tolist(), 'size_mm': (size * MM).round(1).tolist()}
        eye_s = 'L' if c[0] > 0 else 'R'; Ce = eyeC[eye_s]; dxz = float(np.linalg.norm((c - Ce)[[0, 2]]))
        rim = np.array(EM[eye_s]['raw']); sub = Pv[::max(1, len(Pv) // 3000)]
        drim = float(np.min(np.linalg.norm(sub[:, None] - rim[None], axis=2), 1).mean())
        mouth_box = (abs(c[0]) < abs(LT[22][0]) + 0.012) and (LT[24][2] - 0.005 < c[2] < LT[16][2]) and (c[1] > LT[34][1] - 0.004)
        front = bvh_new.ray_cast(Vector(tuple(c)), Vector((0, -1, 0)))
        behind_lips = front[0] is not None and front[3] < 0.08
        brow_d = min(np.min(np.linalg.norm(np.array([LT[i] for i in ids_]) - c, axis=1)) for ids_ in ((1, 2, 3), (4, 5, 6)))
        xz = size[0] / max(size[2], 1e-6)
        if sres < 0.06 * sr and 0.45 * r_old < sr < 1.8 * r_old and dxz < 0.8 * r_old and 0.6 < xz < 1.7: cls = 'eye'
        elif mouth_box and behind_lips: cls = 'mouth'
        elif drim < 0.009 and xz > 1.6 and size.max() < 3.0 * r_old: cls = 'lid'
        elif brow_d < 0.03 and c[2] > Ce[2] and xz > 1.5: cls = 'brow'
        else: cls = 'other'
        info.update({'class': cls, 'sphere_r_mm': round(sr * MM, 2), 'sphere_res_mm': round(sres * MM, 2),
                     'eye_offset_xz_mm': round(dxz * MM, 1), 'to_old_rim_mm': round(drim * MM, 1), 'to_brow_mm': round(brow_d * MM, 1)})
        PI.append(info)
    qa['pieces'] = PI
    # ---- small holes: filled (missing quads, slits, gaps left where a fused 'other' bit sat); kept: the body
    # opening (largest), eye openings and every other loop of 12+ vertices (nostrils, features)
    loops, bad = boundary_loops(Vs, lvs, lts)
    used_s = np.unique(lv[np.repeat(skin_f, lt)])                  # skin vertex k = original vertex used_s[k]
    other_ids = set()
    for pc, info in zip(pieces, PI):
        if pc[3] and info['class'] == 'other': other_ids |= pc[4]
    big = max(range(len(loops)), key=lambda i: len(loops[i])) if loops else -1
    fill, keep = [], []
    for i, L in enumerate(loops):
        P = Vs[L]; near_eye = min(np.linalg.norm(P.mean(0) - eyeC[s]) for s in 'LR') < 1.6 * r_old + 0.01
        touches_other = bool(other_ids & set(used_s[L].tolist()))
        if i == big or (len(L) >= 12 and not touches_other) or (near_eye and len(L) >= 12): keep.append(i)
        else: fill.append(i)
    qa['holes_filled'] = [loop_info(Vs, loops[i]) for i in fill]
    if fill:
        me = bpy.data.meshes.new('_f'); o = mk_obj('_f', Vs, lvs, lts); bm = bmesh.new(); bm.from_mesh(o.data)
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); new_faces = []; welded = 0
        for i in [i for i in fill if len(loops[i]) == 3]:       # sliver triangle hole = a T-junction: weld it shut
            L = loops[i]; P = Vs[L]
            if 0.5 * np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0])) > 2e-8: continue
            ang = [np.degrees(np.arccos(np.clip(np.dot(P[k - 1] - P[k], P[(k + 1) % 3] - P[k]) / (np.linalg.norm(P[k - 1] - P[k]) * np.linalg.norm(P[(k + 1) % 3] - P[k]) + 1e-15), -1, 1))) for k in range(3)]
            k = int(np.argmax(ang)); a_, c_, b_ = L[k - 1], L[k], L[(k + 1) % 3]
            e = bm.edges.get((bm.verts[a_], bm.verts[b_]))
            if e is None: continue
            AB = Vs[b_] - Vs[a_]; fac = float(np.clip(np.dot(Vs[c_] - Vs[a_], AB) / (AB @ AB), 0.01, 0.99))
            vc = bm.verts[c_]; ne, nv = bmesh.utils.edge_split(e, bm.verts[a_], fac)
            bmesh.ops.weld_verts(bm, targetmap={nv: vc}); welded += 1; fill = [j for j in fill if j != i]
            bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
        qa['sliver_holes_welded'] = welded
        # thin slits (cracks under 0.8 mm wide): zipped shut, the two sides' vertices merged (a fill would leave
        # sliver faces that shade as dark marks)
        key = lambda p: tuple(np.round(np.asarray(p) * 1e6).astype(np.int64))
        fill_pos = {key(Vs[v]) for i in fill for v in loops[i]}; zipped = 0
        refs = {i: list({bm.verts[v] for v in loops[i]}) for i in fill}
        for i in fill:
            L = loops[i]; P = Vs[L]; c = P.mean(0)
            ext = np.ptp((P - c) @ np.linalg.svd(P - c)[2][:2].T, 0)
            if len(L) >= 4 and ext.min() < 0.0008 and ext.max() > 3 * ext.min():
                vs_ = [v for v in refs[i] if v.is_valid]
                bmesh.ops.remove_doubles(bm, verts=vs_, dist=min(0.001, 1.3 * ext.min() + 1e-5)); zipped += 1
        qa['slits_zipped'] = zipped
        bm.to_mesh(o.data); bm.free(); Vs, lvs, lts = obj_arrays(o, world=False); bpy.data.objects.remove(o, do_unlink=True)
        # the rest of the marked holes (found again by position): filled, n-gons triangulated
        kdf = KDTree(len(fill_pos))
        for j_, q_ in enumerate(fill_pos): kdf.insert(np.array(q_) * 1e-6, j_)
        kdf.balance(); loops2, _ = boundary_loops(Vs, lvs, lts)
        fill2 = [L for L in loops2 if all(kdf.find(Vs[v])[2] < 5e-6 for v in L)]
        o = mk_obj('_f', Vs, lvs, lts); bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); new_faces = []
        for L in fill2:
            es = [bm.edges.get((bm.verts[L[j]], bm.verts[L[(j + 1) % len(L)]])) for j in range(len(L)) if L[j] != L[(j + 1) % len(L)]]
            es = list(dict.fromkeys(e for e in es if e is not None))
            if len(es) >= 3: r_ = bmesh.ops.holes_fill(bm, edges=es, sides=0); new_faces += r_['faces']
        qa['holes_filled_after_zip'] = len(fill2)
        big_f = [f for f in new_faces if len(f.verts) > 4]
        if big_f: bmesh.ops.triangulate(bm, faces=big_f, quad_method='BEAUTY', ngon_method='BEAUTY')
        bm.to_mesh(o.data); bm.free(); Vs, lvs, lts = obj_arrays(o, world=False); bpy.data.objects.remove(o, do_unlink=True)
        bvh_new = bvh_of(Vs, lvs, lts)
    # ---- P2 heads carry a centre edge loop ~0.1 mm off the fitted mirror plane: turn that loop onto x = 0 (and set
    # its vertices' tiny residual to 0), so sym_mirror cuts along the existing loop instead of leaving a sliver strip
    near = np.abs(Vs[:, 0]) < 0.0004
    if near.sum() >= 20:
        xm = float(np.abs(Vs[near][:, 0]).mean()); A_ = np.c_[np.ones(near.sum()), Vs[near][:, 1], Vs[near][:, 2]]; cf = np.linalg.lstsq(A_, Vs[near][:, 0], rcond=None)[0]
        nrm = np.array([1.0, -cf[1], -cf[2]]); ln_ = np.linalg.norm(nrm); Cc, ang_c = plane_to_x(nrm / ln_, cf[0] / ln_, Vs[near].mean(0))
        Vs = apply(Cc, Vs); pieces = [(apply(Cc, pc[0]),) + tuple(pc[1:]) for pc in pieces]; G = Cc @ G
        resid = np.abs(Vs[near][:, 0]).max(); Vs[near, 0] = 0.0; bvh_new = bvh_of(Vs, lvs, lts)
        qa['centre_loop'] = {'verts': int(near.sum()), 'turn_deg': round(ang_c, 4), 'mean_offset_before_mm': round(xm * MM, 3), 'residual_snapped_max_mm': round(float(resid * MM), 4)}
        qa['align']['matrix_final'] = G.round(8).tolist()
    T_ = Topo(Vs, lvs, lts)
    qa['skin_after'] = {'faces': int(len(lts)), 'verts': int(len(Vs)), 'quads_pct': round(100 * float((lts == 4).mean()), 2),
                        'nonmanifold_edges': int((T_.efc > 2).sum()), 'boundary_loops': [loop_info(Vs, L) for L in boundary_loops(Vs, lvs, lts)[0]]}
    nm_e = np.where(T_.efc > 2)[0]
    qa['skin_after']['nonmanifold_at_mm'] = [((Vs[T_.E[e, 0]] + Vs[T_.E[e, 1]]) / 2 * MM).round(1).tolist() for e in nm_e[:30]]
    # ---- preliminary landmarks / eyes_meta (sym_mirror averages them; finish redoes them on the symmetric head)
    eyeL = [pc for pc, info in zip(pieces, PI) if info['class'] == 'eye' and info['side'] == 'L']
    eyeball = max(eyeL, key=lambda pc: len(pc[2]))[:3] if eyeL else None
    LN, EO, pinfo, _ = build_points(Vs, lvs, lts, eyeball, LT, EM, {}, 0.0004)
    qa['points_pre'] = pinfo
    json.dump(LN, open(os.path.join(WK, 'landmarks_pre.json'), 'w'), indent=1)
    json.dump(EO, open(os.path.join(WK, 'eyes_meta_pre.json'), 'w'))
    # ---- save: skin FBX for sym_mirror, all pieces in a .blend (our frame, before symmetrisation)
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    sk = mk_obj('head', Vs, lvs, lts)
    bpy.ops.object.select_all(action='DESELECT'); sk.select_set(True); bpy.context.view_layer.objects.active = sk
    bpy.ops.export_scene.fbx(filepath=os.path.join(WK, 'head_skin.fbx'), use_selection=True, object_types={'MESH'},
                             mesh_smooth_type='OFF', add_leaf_bones=False, bake_anim=False)
    sk.name = 'skin_pre'
    for k, (pc, info) in enumerate(zip(pieces, PI)):
        o = mk_obj('%s_%s_%02d' % (info['class'], info['side'], k), *pc[:3]); o['class'] = info['class']; o['fused'] = info['fused']; o['side'] = info['side']
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WK, 'pieces.blend'), compress=True)
    # FBX round trip check (sym_mirror imports it)
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.fbx(filepath=os.path.join(WK, 'head_skin.fbx'))
    o = [o for o in bpy.data.objects if o.type == 'MESH'][0]; Vr = obj_arrays(o)[0]
    qa['fbx_roundtrip_max_mm'] = round(float(np.abs(Vr - Vs).max() * MM), 5) if len(Vr) == len(Vs) else 'vertex count changed %d -> %d' % (len(Vs), len(Vr))
    qa['seconds'] = round(time.time() - T0, 1)
    json.dump(qa, open(os.path.join(WK, 'prep_qa.json'), 'w'), indent=1)
    print('PREP', json.dumps({k: qa[k] for k in ('align_start_used', 'skin_faces', 'fbx_roundtrip_max_mm')}), json.dumps(qa['align']['face_trimmed_rms_mm']),
          json.dumps(pinfo['margin']))


# ================================================================== finish
def mirror_mesh(V, lv, lt):
    return V * MX, np.concatenate([x[::-1] for x in np.split(lv, np.cumsum(lt)[:-1])]), lt.copy()


def join_meshes(items):
    Vs_, Ls_, Ts_, off = [], [], [], 0
    for V, lv, lt in items: Vs_.append(V); Ls_.append(lv + off); Ts_.append(lt); off += len(V)
    return np.vstack(Vs_), np.concatenate(Ls_), np.concatenate(Ts_)


def sym_piece(V, lv, lt):
    """sym_mirror.py's symmetrisation on one centre piece: +x half averaged with the mirrored other side, mirrored."""
    o = mk_obj('_sp', V, lv, lt); bvh0 = bvh_of(V, lv, lt); bm = bmesh.new(); bm.from_mesh(o.data); CUT = 5e-5
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=CUT, plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
    for v in bm.verts:
        p = np.array(v.co)
        if abs(p[0]) < CUT: v.co.x = 0.0; continue
        loc = bvh0.find_nearest(Vector(tuple(p * MX)))[0]
        if loc is None: continue
        n = (p + np.array(loc) * MX) / 2; n[0] = max(n[0], min(p[0], 2 * CUT)); v.co = Vector(tuple(n))
    bmesh.ops.dissolve_degenerate(bm, dist=CUT, edges=bm.edges[:])
    for v in bm.verts:
        if v.co.x < CUT: v.co.x = 0.0
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis='X', merge_dist=1e-6)
    bmesh.ops.reverse_faces(bm, faces=[f for f in bm.faces if f.calc_center_median().x < 0])
    bm.to_mesh(o.data); bm.free(); out = obj_arrays(o, world=False); bpy.data.objects.remove(o, do_unlink=True)
    return out


def load_img_px(path):
    im = bpy.data.images.load(path, check_existing=False); w, h = im.size
    px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px); a = px.reshape(h, w, 4)[::-1].copy()
    bpy.data.images.remove(im); return a


def save_img_px(arr, path, quality=88):
    h, w = arr.shape[:2]; rgba = np.ones((h, w, 4), np.float32); rgba[..., :3] = np.clip(arr[..., :3], 0, 1)
    im = bpy.data.images.new('_out', w, h, alpha=False); im.pixels.foreach_set(rgba[::-1].ravel())
    im.filepath_raw = path; im.file_format = 'JPEG' if path.lower().endswith('.jpg') else 'PNG'
    bpy.context.scene.render.image_settings.quality = quality; im.save(); bpy.data.images.remove(im)


def resize_px(a, w, h):
    ys = np.clip(((np.arange(h) + 0.5) * a.shape[0] / h).astype(int), 0, a.shape[0] - 1)
    xs = np.clip(((np.arange(w) + 0.5) * a.shape[1] / w).astype(int), 0, a.shape[1] - 1)
    return a[ys][:, xs]


def mark(a, pts, col, r=4):
    for u, v in pts:
        u, v = int(round(u)), int(round(v))
        if 0 <= u < a.shape[1] and 0 <= v < a.shape[0]: a[max(0, v - r):v + r + 1, max(0, u - r):u + r + 1, :3] = col
    return a


def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); A0, B0 = A - ma, B - mb
    U, Dg, Vt = np.linalg.svd(B0.T @ A0 / len(A)); Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ Sg @ Vt; s = np.trace(np.diag(Dg) @ Sg) / (A0 ** 2).sum(1).mean(); return s, R, mb - s * R @ ma


def mp_head_points(sc, co, vis, bvh_skin, LTo, wk):
    """MediaPipe Face Landmarker on clay front renders of the new head (cavity shading, brows / lashes dark), the
    framing with the widest eye spacing wins (as face_landmarks_mp.py); points shot onto the skin from the front."""
    for o in bpy.data.objects:
        if o.type == 'MESH': o.hide_render = o not in vis
    col = {'p2_eyes': (0.92, 0.92, 0.92, 1), 'p2_brows': (0.25, 0.18, 0.14, 1), 'p2_lids': (0.12, 0.1, 0.1, 1), 'p2_mouth': (0.6, 0.3, 0.3, 1)}
    for o in vis: o.color = col.get(o.name, (0.75, 0.75, 0.77, 1))
    sh = sc.display.shading; sh.show_cavity = True; sc.render.resolution_x = sc.render.resolution_y = 1024
    top = (LTo[2][2] + LTo[5][2]) / 2; fh = top - LTo[24][2]; zc = (top + LTo[24][2]) / 2 + 0.05 * fh; best = None
    for k, f in enumerate((2.1, 2.6, 3.2)):
        size = f * fh; png = os.path.join(wk, 'mp_front%d.png' % k); shoot(sc, co, png, (0, 0, zc), (0, 1, 0), size)
        js = png + '.json'; subprocess.run([MP_PY, '-I', MP_DETECT, png, MP_MODEL, js], check=True, capture_output=True); L = json.load(open(js))
        if len(L) < 468: continue
        eye = abs(L[33][0] - L[263][0]) * size
        if best is None or eye > best[0]: best = (eye, L, size)
    sh.show_cavity = False
    if best is None: return {}
    _, L, size = best; out = {}
    for k, i in MP.items():
        u, v = L[i][:2]; x = (u - 0.5) * size; z = zc - (v - 0.5) * size
        h = bvh_skin.ray_cast(Vector((x, -3.0, z)), Vector((0, 1, 0)))
        if h[0] is not None: out[k] = np.array(h[0])
    return out


if MODE == 'finish':
    OUT, OLD, RIGJ, REFPNG = os.path.abspath(argv[1]), argv[2], argv[3], argv[4]
    WK = os.path.join(OUT, '_work'); qa = {}
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, 'base.blend')); bpy.context.preferences.filepaths.save_version = 0
    for o in [o for o in bpy.data.objects if o.name not in ('orig', 'noface')]: bpy.data.objects.remove(o, do_unlink=True)
    orig = bpy.data.objects['orig']; X, lvx, ltx = obj_arrays(orig)
    LJ0 = json.load(open(os.path.join(OUT, 'landmarks.json')))
    if LJ0.get('_source') != 'p2_base finish':                      # keep sym_mirror's own averaged files
        import shutil
        for f in ('landmarks.json', 'eyes_meta.json'): shutil.copy(os.path.join(OUT, f), os.path.join(WK, f.replace('.json', '_symmirror.json')))
    LTo, EMo, Vo, lvo, lto = load_old(OLD)
    before = set(bpy.data.objects); bpy.ops.import_scene.fbx(filepath=os.path.join(WK, 'head_skin.fbx'))
    o = [o for o in bpy.data.objects if o not in before and o.type == 'MESH'][0]; V0, lv0, lt0 = obj_arrays(o)
    for o in [o for o in bpy.data.objects if o not in before]: bpy.data.objects.remove(o, do_unlink=True)
    bvh0 = bvh_of(V0, lv0, lt0)
    def sym_disp(P):                                              # the skin's symmetrisation move at the nearest skin point
        out = np.empty_like(P)
        for i, p in enumerate(P):
            q = np.array(bvh0.find_nearest(Vector(p))[0]); m = np.array(bvh0.find_nearest(Vector(q * MX))[0]) * MX
            out[i] = (q + m) / 2 - q
        return out
    # ---- pieces: +x kept and mirrored, -x pieces without a +x partner mirrored over, centre pieces averaged
    with bpy.data.libraries.load(os.path.join(WK, 'pieces.blend')) as (src, dst): dst.objects = [n for n in src.objects if not n.startswith('skin_pre')]
    PC = []
    for o in dst.objects:
        V_, l_, t_ = obj_arrays(o); PC.append({'cls': o.get('class', 'other'), 'V': V_, 'lv': l_, 'lt': t_, 'c': V_.mean(0), 'name': o.name})
    for o in dst.objects: bpy.data.objects.remove(o, do_unlink=True)
    NAMES = {'eye': 'p2_eyes', 'brow': 'p2_brows', 'lid': 'p2_lids', 'mouth': 'p2_mouth'}; pieces_out = {}; qa['pieces'] = {}; eyeL = None
    for cls, oname in NAMES.items():
        it = [p for p in PC if p['cls'] == cls]
        Ls = [p for p in it if p['c'][0] > 0.004]; Rs = [p for p in it if p['c'][0] < -0.004]; Cs = [p for p in it if abs(p['c'][0]) <= 0.004]
        lefts = list(Ls); unpaired_R = []
        inside = lambda c, q: bool(np.all(c > q['V'].min(0) - 0.001) and np.all(c < q['V'].max(0) + 0.001))
        for p in Rs:                       # eyes: only the +x eyeball; skip crumbs and parts already inside a +x piece
            mc = p['c'] * MX
            if cls == 'eye' or len(p['lt']) < 20 or any(inside(mc, q) for q in Ls): continue
            if not any(np.linalg.norm(q['c'] - mc) < 0.003 and 0.6 < len(q['lt']) / len(p['lt']) < 1.6 for q in Ls):
                V_, l_, t_ = mirror_mesh(p['V'], p['lv'], p['lt']); lefts.append({'V': V_, 'lv': l_, 'lt': t_, 'c': mc}); unpaired_R.append(len(p['lt']))
        items = []
        for p in sorted(lefts, key=lambda p: -len(p['lt'])):
            if cls in ('eye', 'mouth'): V_ = p['V'] + sym_disp(p['V'][::max(1, len(p['V']) // 400)]).mean(0)
            else: V_ = p['V'] + sym_disp(p['V'])
            items.append((V_, p['lv'], p['lt'])); items.append(mirror_mesh(V_, p['lv'], p['lt']))
        for p in Cs: items.append(sym_piece(p['V'], p['lv'], p['lt']))
        qa['pieces'][oname] = {'left_pieces': len(Ls), 'right_only_mirrored': unpaired_R, 'centre_pieces': len(Cs),
                               'faces': int(sum(len(i[2]) for i in items))}
        if items:
            Vj, lj, tj = join_meshes(items); pieces_out[oname] = mk_obj(oname, Vj, lj, tj)
            if cls == 'eye': eyeL = items[0]
    qa['pieces_other_dropped_faces'] = sorted([int(len(p['lt'])) for p in PC if p['cls'] == 'other'], reverse=True)
    for o in bpy.data.objects: o.select_set(False)
    bpy.data.objects['noface'].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'base.blend'), compress=True)
    # ---- final skin: holes per side, eye margins, landmarks, eyes_meta
    loops, bad = boundary_loops(X, lvx, ltx); hl = {'L': [], 'R': [], 'C': []}
    for L in loops:
        c = X[L].mean(0); hl['L' if c[0] > 1e-4 else ('R' if c[0] < -1e-4 else 'C')].append(loop_info(X, L))
    qa['hole_loops'] = {s: {'count': len(v), 'verts': [h['verts'] for h in v], 'loops': v} for s, v in hl.items()}
    qa['hole_loops']['unwalkable_edges'] = bad
    T = Topo(X, lvx, ltx)
    kd = KDTree(len(X))
    for i, p in enumerate(X): kd.insert(p, i)
    kd.balance(); gap = np.array([kd.find(p * MX)[2] for p in X])
    qa['mesh'] = {'faces': int(len(ltx)), 'verts': int(len(X)), 'quads_pct': round(100 * float((ltx == 4).mean()), 2),
                  'tris_pct': round(100 * float((ltx == 3).mean()), 2), 'ngons': int((ltx > 4).sum()), 'nonmanifold_edges': int((T.efc > 2).sum()),
                  'exact_mirror_pct': round(100 * float((gap < 1e-7).mean()), 2)}
    sc, co = render_setup(1024)
    mp3 = mp_head_points(sc, co, [orig] + list(pieces_out.values()), bvh_of(X, lvx, ltx), LTo, WK)
    qa['mediapipe_on_new_head'] = {str(k): (np.round(v * MM, 1)).tolist() for k, v in mp3.items()}
    LN, EO, pinfo, vids = build_points(X, lvx, ltx, eyeL, LTo, EMo, {'mp': mp3}, 1e-7)
    vR = [kd.find(X[i] * MX)[1] for i in vids]
    EO['L']['margin_vids'] = [int(i) for i in vids]; EO['R']['margin_vids'] = [int(i) for i in vR]
    LN['_source'] = 'p2_base finish'
    json.dump(LN, open(os.path.join(OUT, 'landmarks.json'), 'w'), indent=1)
    json.dump(EO, open(os.path.join(OUT, 'eyes_meta.json'), 'w'))
    qa['points'] = pinfo
    LNa = {int(k): np.array(v) for k, v in LN.items() if not k.startswith('_')}
    fh = lambda L: (L[2][2] + L[5][2]) / 2 - L[24][2]
    qa['proportions_mm'] = {'note': '[new, old]', 'brow_to_chin': [round(fh(LNa) * MM, 1), round(fh(LTo) * MM, 1)],
                            'crown_to_chin': [round((LNa[31][2] - LNa[24][2]) * MM, 1), round((LTo[31][2] - LTo[24][2]) * MM, 1)],
                            'outer_eye_corners': [round((LNa[13][0] - LNa[7][0]) * MM, 1), round((LTo[13][0] - LTo[7][0]) * MM, 1)],
                            'mouth_width': [round((LNa[22][0] - LNa[20][0]) * MM, 1), round((LTo[22][0] - LTo[20][0]) * MM, 1)],
                            'nose_tip_to_chin': [round((LNa[16][2] - LNa[24][2]) * MM, 1), round((LTo[16][2] - LTo[24][2]) * MM, 1)],
                            'eyeball_r': [round(EO['L']['r'] * MM, 1), round(EMo['L']['r'] * MM, 1)]}
    # ---- rig points: old T14 joints through a thin-plate spline old -> new (non-eye landmarks, eye centres, rims)
    RP = json.load(open(RIGJ)); J = RP['joints']
    ts = np.linspace(0, 1, 7)
    def rim_pts(E):
        out = []
        for s_ in 'LR':
            l_ = lids(np.array(E[s_]['raw']), ts); out += list(l_['up']) + list(l_['lo'][1:-1]) + [np.array(E[s_]['C'])]
        return out
    keys = [k for k in (1, 2, 3, 4, 5, 6, 16, 20, 22, 24, 31) if k in LTo and k in LNa]
    S_ = np.array([LTo[k] for k in keys] + [(LTo[34] + LTo[35]) / 2] + rim_pts(EMo))
    D_ = np.array([LNa[k] for k in keys] + [(LNa[34] + LNa[35]) / 2] + rim_pts(EO))
    s_, R_, t_ = umeyama(S_, D_); sim = lambda Q: s_ * np.asarray(Q) @ R_.T + t_
    tps = tps_fit(sim(S_), D_, lam=1e-6)
    bvhX = bvh_of(X, lvx, ltx); snap = lambda p: np.array(bvhX.find_nearest(Vector(p))[0])
    # ears lie far from the face points: the old ear (head surface around the old ear joints) is carried by the
    # spline, then registered rigidly onto the new ear (trimmed point-to-plane ICP); its joints become extra pairs
    ear_n = [n for n in J if n.startswith('ear.L')]
    if ear_n:
        EJ = np.unique(np.round(np.array([J[n][k] for n in ear_n for k in (0, 1)]), 7), axis=0); ce = EJ.mean(0)
        reg = Vo[(np.linalg.norm(Vo - ce, axis=1) < 0.03) & (Vo[:, 0] > ce[0] - 0.012)]
        Y0 = tps_apply(tps, sim(reg))
        zone = (X[:, 2] > LNa[20][2]) & (X[:, 2] < LNa[13][2] + 0.01) & (X[:, 1] > LNa[13][1])        # ear zone: most lateral point
        pe_new = X[zone][np.argmax(X[zone][:, 0])]; pe_old = Y0[np.argmax(Y0[:, 0])]
        R_e, t_e = np.eye(3), pe_new - pe_old; c0 = Y0.mean(0) + t_e
        fc = np.add.reduceat(X[lvx], np.r_[0, np.cumsum(ltx)[:-1]]) / ltx[:, None]          # face centres
        keepf = (np.linalg.norm(fc - c0, axis=1) < 0.035) & (fc[:, 0] > 0.5 * c0[0])
        bvhE = bvh_of(*sub_mesh(X, lvx, ltx, keepf))                                         # only the new ear's surroundings
        for _ in range(40):
            Y = Y0 @ R_e.T + t_e; Q, Nq, dq = nearest(bvhE, Y); kk = dq <= np.percentile(dq, 80); Y, Q, Nq = Y[kk], Q[kk], Nq[kk]
            c = Y.mean(0); Yc = Y - c; A = np.hstack([np.cross(Yc, Nq), Nq]); b = (Nq * (Q - Y)).sum(1); x = np.linalg.lstsq(A, b, rcond=None)[0]
            w, tau = x[:3], x[3:]; wn = float(np.linalg.norm(w)); Ru = rot(w / wn, wn) if wn > 1e-12 else np.eye(3)
            R_e = Ru @ R_e; t_e = Ru @ (t_e - c) + c + tau
        Y = Y0 @ R_e.T + t_e; dq = nearest(bvhX, Y)[2]
        ear_dst = tps_apply(tps, sim(EJ)) @ R_e.T + t_e; mv = float(np.linalg.norm(ear_dst - (tps_apply(tps, sim(EJ)) + pe_new - pe_old), axis=1).mean())
        qa['ear_tip_offset_mm'] = round(float(np.linalg.norm(pe_new - pe_old) * MM), 1)
        ang_e = math.degrees(math.acos(np.clip((np.trace(R_e) - 1) / 2, -1, 1))); ok_e = mv < 0.02 and ang_e < 25
        qa['ear_registration'] = {'points': int(len(reg)), 'rms_mm': round(float(np.sqrt((np.sort(dq)[:int(0.8 * len(dq))] ** 2).mean()) * MM), 2),
                                  'moved_mm': round(mv * MM, 1), 'turn_deg': round(ang_e, 1), 'used': bool(ok_e)}
        if ok_e:
            S_ = np.r_[S_, EJ, EJ * MX]; D_ = np.r_[D_, ear_dst, ear_dst * MX]
            s_, R_, t_ = umeyama(S_, D_); tps = tps_fit(sim(S_), D_, lam=1e-6)
    skin_prefix = ('brow', 'lid', 'lip', 'cheek', 'forehead', 'temple', 'jaw.', 'chin', 'ear', 'nose')
    NJ = {}
    for n, (h, t) in J.items():
        hh, tt = tps_apply(tps, sim(np.array([h, t])))
        if n.startswith(skin_prefix): hh, tt = snap(hh), snap(tt)
        NJ[n] = [hh, tt]
    for s_e in 'LR':
        if 'eye.%s' % s_e in NJ:
            C = np.array(EO[s_e]['C']); d = np.array(J['eye.%s' % s_e][1]) - np.array(J['eye.%s' % s_e][0]); NJ['eye.%s' % s_e] = [C, C + d]
    for n in list(NJ):
        if n.endswith('.L') or '.L.' in n:
            m = n.replace('.L', '.R')
            if m in NJ:
                for k in (0, 1):
                    avg = (NJ[n][k] + NJ[m][k] * MX) / 2; NJ[n][k] = avg; NJ[m][k] = avg * MX
        elif '.R' not in n:
            NJ[n] = [NJ[n][0].copy(), NJ[n][1].copy()]; NJ[n][0][0] = 0.0; NJ[n][1][0] = 0.0
    res = np.linalg.norm(tps_apply(tps, sim(S_)) - D_, axis=1)
    move = np.array([np.linalg.norm(NJ[n][0] - np.array(J[n][0])) for n in J])
    rp_out = {'joints': {n: [NJ[n][0].tolist(), NJ[n][1].tolist()] for n in J},
              'info': {'from': os.path.abspath(RIGJ), 'method': 'similarity + thin-plate spline old -> new: landmarks 1-6, 16, 20, 22, 24, 31, lip seam centre, eye rims (7+5 per eye), eyeball centres and the ear joints (old ear registered onto the new ear by ICP); skin joints snapped onto orig; eye joints on the new eyeball centres; .L/.R averaged, centre bones on x = 0',
                       'pairs': int(len(S_)), 'similarity_scale': round(float(s_), 4), 'tps_residual_mm_max': round(float(res.max() * MM), 3),
                       'joint_move_mm': {'p50': round(float(np.median(move) * MM), 1), 'max': round(float(move.max() * MM), 1)},
                       'jaw_pivot': NJ['jaw'][0].tolist()}}
    json.dump(rp_out, open(os.path.join(OUT, 'rig_points.json'), 'w'), indent=1)
    qa['rig_points'] = rp_out['info']
    # ---- renders
    sc.render.resolution_x = sc.render.resolution_y = 800; objs = [orig] + list(pieces_out.values())
    for o in bpy.data.objects:
        if o.type == 'MESH': o.hide_render = o not in objs
    PCOL = {'p2_eyes': (0.42, 0.5, 0.95, 1), 'p2_brows': (0.85, 0.45, 0.6, 1), 'p2_lids': (0.95, 0.8, 0.3, 1), 'p2_mouth': (0.9, 0.35, 0.3, 1)}
    # likeness: front grey on the reference front image, similarity from MediaPipe points on the image to our landmarks
    js = os.path.join(tempfile.mkdtemp(), 'f.json')
    subprocess.run([MP_PY, '-I', MP_DETECT, REFPNG, MP_MODEL, js], check=True, capture_output=True); mp = json.load(open(js))
    ref = load_img_px(REFPNG); Hh, Ww = ref.shape[:2]
    if mp:
        ids = [k for k in MP if k in LNa]
        def simfit(L):
            src = np.array([[L[k][0], L[k][2]] for k in ids]); dst = np.array([[mp[MP[k]][0] * Ww, mp[MP[k]][1] * Hh] for k in ids])
            M = np.zeros((2 * len(src), 3)); rhs = np.zeros(2 * len(src)); M[0::2, 0] = src[:, 0]; M[0::2, 1] = 1; rhs[0::2] = dst[:, 0]
            M[1::2, 0] = -src[:, 1]; M[1::2, 2] = 1; rhs[1::2] = dst[:, 1]; (s1, tx, ty), *_ = np.linalg.lstsq(M, rhs, rcond=None)
            r_ = np.linalg.norm(np.c_[s1 * src[:, 0] + tx, -s1 * src[:, 1] + ty] - dst, axis=1)
            return s1, tx, ty, r_, dst
        s1, tx, ty, rn, dst = simfit(LNa); so, txo, tyo, ro, _ = simfit(LTo); ne = np.array([k not in range(7, 15) for k in ids])
        ids_all = ids; ids = [k for k in ids_all if k not in range(7, 15)]                # the same fit without the eye points
        rn_ne = simfit(LNa)[3]; ro_ne = simfit(LTo)[3]; sn_ne = simfit(LNa)[0]; so_ne = simfit(LTo)[0]; ids = ids_all
        qa['likeness'] = {'mediapipe_points': len(ids), 'fit_residual_mm': {'new': round(float(rn.mean() / s1 * MM), 2), 'old': round(float(ro.mean() / so * MM), 2)},
                          'fit_residual_without_eye_points_mm': {'new': round(float(rn_ne.mean() / sn_ne * MM), 2), 'old': round(float(ro_ne.mean() / so_ne * MM), 2),
                                                                 'note': 'similarity fitted and measured on brows, nose tip, mouth, chin only'},
                          'per_point_new_mm': {str(k): round(float(r / s1 * MM), 1) for k, r in zip(ids, rn)},
                          'per_point_old_mm': {str(k): round(float(r / so * MM), 1) for k, r in zip(ids, ro)}, 'scale_px_per_m': round(float(s1), 1)}
        zt, zb = LNa[31][2] + 0.02, LNa[24][2] - 0.06; size = zt - zb; zc = (zt + zb) / 2
        u0, v0 = s1 * (-size / 2) + tx, -s1 * zt + ty; spx = s1 * size
        for o in objs: o.color = (0.75, 0.75, 0.77, 1)
        sc.render.film_transparent = True
        shoot(sc, co, os.path.join(WK, 'likeness_render.png'), (0, 0, zc), (0, 1, 0), size)
        rend = load_img_px(os.path.join(WK, 'likeness_render.png')); sc.render.film_transparent = False
        n_ = rend.shape[0]
        uu = np.clip((u0 + (np.arange(n_) + 0.5) * spx / n_).astype(int), 0, Ww - 1); vv = np.clip((v0 + (np.arange(n_) + 0.5) * spx / n_).astype(int), 0, Hh - 1)
        crop = ref[vv][:, uu, :3]; al = rend[..., 3:4]
        grey = rend[..., :3] * al + (1 - al) * 1.0; blend = crop * (1 - 0.5 * al) + rend[..., :3] * 0.5 * al
        pm = (dst - [u0, v0]) * n_ / spx
        po = np.c_[s1 * np.array([LNa[k][0] for k in ids]) + tx - u0, -s1 * np.array([LNa[k][2] for k in ids]) + ty - v0] * n_ / spx
        blend = mark(mark(blend.copy(), pm, (0.1, 0.85, 0.2), 4), po, (0.95, 0.1, 0.1), 3)
        save_img_px(np.concatenate([crop, grey, blend], 1), os.path.join(OUT, 'likeness.jpg'))
    else:
        qa['likeness'] = {'mediapipe_points': 0}
    # sheet views: grey + wire, pieces coloured
    for o in objs: o.color = PCOL.get(o.name, (0.72, 0.72, 0.74, 1))
    wires = [wire_copy(o, (0.08, 0.08, 0.1, 1)) for o in objs]
    zt, zb = LNa[31][2] + 0.015, LNa[24][2] - 0.07; size = zt - zb; zc = (zt + zb) / 2
    for w, m in wires: m.thickness = size / 800 * 0.9
    for nm, d in (('front', (0, 1, 0)), ('34', (-0.7, 0.7, 0))):
        cyh = float(X[X[:, 2] > LNa[24][2], 1].mean())
        shoot(sc, co, os.path.join(WK, 'sheet_%s.png' % nm), (0, cyh, zc), d, size * (1.0 if nm == 'front' else 1.05))
    # check views: eye and mouth close-ups: margin (magenta), skin/eyeball crossing (green), lip seam (orange), landmarks (red)
    for w, m in wires: m.thickness = 0.00012
    curve_obj(np.array(EO['L']['raw']), True, (0.9, 0.1, 0.8), 0.00035)
    if 'skin_eyeball_crossing' in EO['L']: curve_obj(np.array(EO['L']['skin_eyeball_crossing']), True, (0.1, 0.75, 0.2), 0.00022)
    curve_obj(np.array(LN['_lip_seam']), False, (1.0, 0.5, 0.0), 0.00035)
    for k, p in LNa.items():
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0009, location=tuple(p), segments=10, ring_count=6); bpy.context.active_object.color = (0.95, 0.1, 0.1, 1)
    ec = np.mean(np.array(EO['L']['raw']), 0); mc = (LNa[20] + LNa[22]) / 2; mw = LNa[22][0] * 2; chk = []
    for nm, c, d, s in (('eye_front', ec, (0, 1, 0), 0.065), ('eye_34', ec, (-0.5, 0.86, 0), 0.065),
                        ('mouth_front', mc, (0, 1, 0), mw * 1.7), ('mouth_34', mc + np.array([mw * 0.2, 0, 0]), (-0.6, 0.8, 0), mw * 1.7)):
        p = os.path.join(WK, 'check_%s.png' % nm); shoot(sc, co, p, c, d, s); chk.append(load_img_px(p)[..., :3])
    save_img_px(np.concatenate([np.concatenate(chk[:2], 1), np.concatenate(chk[2:], 1)], 0), os.path.join(OUT, 'check_eye_mouth.jpg'))
    qa['seconds'] = round(time.time() - T0, 1)
    json.dump(qa, open(os.path.join(OUT, 'finish_qa.json'), 'w'), indent=1)
    print('FINISH', json.dumps({'holes': {s: qa['hole_loops'][s]['verts'] for s in 'LRC'}, 'margin': pinfo['margin'], 'likeness': qa['likeness'].get('fit_residual_mm'),
                                'pieces': {k: v['faces'] for k, v in qa['pieces'].items()}}))


# ================================================================== sheet (4 heads)
if MODE == 'sheet':
    PD, OUTJ, names = argv[1], argv[2], argv[3:]
    bpy.ops.wm.read_factory_settings(use_empty=True); cols = []
    for n in names:
        a_ = load_img_px(os.path.join(PD, n, '_work', 'sheet_front.png'))[..., :3]; b_ = load_img_px(os.path.join(PD, n, '_work', 'sheet_34.png'))[..., :3]
        cols.append(np.concatenate([resize_px(a_, 600, 600), resize_px(b_, 600, 600)], 0))
    save_img_px(np.concatenate(cols, 1), OUTJ)
    print('SHEET', OUTJ)
