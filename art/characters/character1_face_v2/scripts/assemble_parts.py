"""Assemble secondary parts on the lid-rigged face (face_lids.blend) -> face_parts.blend

* Teeth + tongue: MakeHuman (CC0) assets from the template file, mapped with the same seam-relative transform
  as the mouth bag; their own viseme/jaw shape keys are mapped too (same names as the face keys).
* Upper / lower lash cards rooted on the lid margin rings (hair_tex textures), brows as hair cards placed from
  the original character1 brow silhouette relative to the eye. All cards get every face key through a surface
  frame binding to WrapHead, so blinks/expressions carry them.
Usage: blender --background face_lids.blend --python assemble_parts.py -- <mpfb_template.blend> <template_head.blend> <v1_brows.json> <out.blend>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "character1_face_v1", "scripts"))
import hair_tex as HT

a = sys.argv[sys.argv.index("--") + 1:]
MPFB, TMPL, BROWS, OUT = a[0], a[1], a[2], os.path.abspath(a[3])
rep = {}
w = bpy.data.objects["WrapHead"]; me = w.data
coll = w.users_collection[0]
KB = me.shape_keys.key_blocks
KEYS = [k.name for k in KB[1:]]
X = np.array([v.co[:] for v in KB[0].data]); n = len(X)
KX = {k: np.array([v.co[:] for v in KB[k].data]) for k in KEYS}
F = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), "target_features.json")))
C = json.loads(w["vertex_classes"])

# ---------------------------------------------------------------- template head (similarity frame) for the mouth transform
with bpy.data.libraries.load(TMPL, link=False) as (df, dt):
    dt.objects = ["TemplateHead"]
th = dt.objects[0]
T0 = np.array([th.matrix_world @ v.co for v in th.data.vertices])
seam = list(w["lip_seam"])
# similarity template -> wrap from all surface verts (least squares)
def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); Ac, Bc = A - ma, B - mb
    U, S, Vt = np.linalg.svd(Bc.T @ Ac / len(A)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / (Ac ** 2).sum() * len(A)
    return s, R, mb - s * R @ ma
mouth_ring = np.array([i for i in range(len(T0)) if np.linalg.norm(T0[i] - T0[seam].mean(0)) < 0.04])
s_, R_, t_ = umeyama(T0[mouth_ring], X[mouth_ring])
def sim(P): return (s_ * (R_ @ np.asarray(P).T)).T + t_
X0s = sim(T0); seam_a = np.array(seam)
kx = np.ptp(X[seam_a, 0]) / max(np.ptp(X0s[seam_a, 0]), 1e-9)
DEPTH_K = float(os.environ.get("BAG_DEPTH_K", 0.8))
def mouth_map(P, base_X):
    Ps = sim(P); out = np.zeros_like(Ps)
    for i, p in enumerate(Ps):
        j = seam_a[np.argmin(np.linalg.norm(X0s[seam_a] - p, axis=1))]
        off = p - X0s[j]; off[0] *= kx; off[1:] *= DEPTH_K
        out[i] = base_X[j] + off
    return out
rep["mouth_sim_scale"] = float(s_); rep["mouth_kx"] = float(kx)

# ---------------------------------------------------------------- teeth + tongue
with bpy.data.libraries.load(MPFB, link=False) as (df, dt):
    dt.objects = ["Template_Face_Body.teeth_base", "Template_Face_Body.tongue01"]
TEETH_SHIFT = 0.0
# affine template->wrap from lip-region surface vertices (no bag), then keep the teeth behind the lip skin
bag_set = set(C["bag"])
mr = np.array([i for i in mouth_ring if i not in bag_set])
Ah = np.c_[T0[mr], np.ones(len(mr))]
AFF = np.linalg.lstsq(Ah, X[mr], rcond=None)[0]            # (4,3)
# symmetrise: no x-shear / x-translation (the face is symmetric about x = 0)
AFF[1:3, 0] = 0; AFF[0, 1:] = 0; AFF[3, 0] = 0
def aff(P): return np.c_[P, np.ones(len(P))] @ AFF
Lin = AFF[:3].T
for src, name in zip(dt.objects, ("Teeth", "Tongue")):
    ob = src.copy(); ob.data = src.data.copy(); ob.name = name; ob.data.name = name
    coll.objects.link(ob); ob.parent = None; ob.modifiers.clear()
    mw = src.matrix_world
    kb = ob.data.shape_keys.key_blocks
    basis = np.array([mw @ v.co for v in kb[0].data])
    nb = aff(basis)
    keys_new = {k.name: aff(np.array([mw @ v.co for v in k.data])) for k in kb[1:]}
    if name == "Teeth":
        skin_polys = [tuple(p.vertices) for p in me.polygons if not any(v in bag_set for v in p.vertices)]
        TB = BVHTree.FromPolygons([tuple(p) for p in X], skin_polys)
        pen = 0.0
        for p in nb:
            h = TB.ray_cast(Vector((p[0], -2, p[2])), Vector((0, 1, 0)), 5)
            if h[0] is not None and p[1] < h[0].y + 0.002:
                pen = max(pen, h[0].y + 0.002 - p[1])
        TEETH_SHIFT = pen
        rep["teeth_pushback_mm"] = round(pen * 1000, 2)
    sh_ = np.array([0, TEETH_SHIFT, 0])
    nb = nb + sh_; keys_new = {k_: v_ + sh_ for k_, v_ in keys_new.items()}
    ob.shape_key_clear(); ob.matrix_world = Matrix()
    ob.data.vertices.foreach_set("co", nb.ravel())
    ob.shape_key_add(name="Basis", from_mix=False)
    for kname in KEYS:
        ob.shape_key_add(name=kname, from_mix=False).data.foreach_set("co", np.asarray(keys_new.get(kname, nb)).ravel())
    rep[f"{name}_mapped_keys"] = sum(1 for k in KEYS if k in keys_new)

# ---------------------------------------------------------------- surface-frame binding to WrapHead (all keys)
me.calc_loop_triangles()
tris = np.array([t.vertices[:] for t in me.loop_triangles])
T_tri = BVHTree.FromPolygons([tuple(p) for p in X], [tuple(t) for t in tris])
def vnormals(co):
    fn = np.cross(co[tris[:, 1]] - co[tris[:, 0]], co[tris[:, 2]] - co[tris[:, 0]])
    vn = np.zeros_like(co)
    for k in range(3): np.add.at(vn, tris[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1), 1e-12)[:, None]
def frame(co, vn, ti, bc):
    v0, v1, v2 = co[tris[ti, 0]], co[tris[ti, 1]], co[tris[ti, 2]]
    q = bc[:, 0:1] * v0 + bc[:, 1:2] * v1 + bc[:, 2:3] * v2
    nr = bc[:, 0:1] * vn[tris[ti, 0]] + bc[:, 1:2] * vn[tris[ti, 1]] + bc[:, 2:3] * vn[tris[ti, 2]]
    nr /= np.maximum(np.linalg.norm(nr, axis=1), 1e-12)[:, None]
    e1 = v1 - v0; e1 -= (e1 * nr).sum(1)[:, None] * nr; e1 /= np.maximum(np.linalg.norm(e1, axis=1), 1e-12)[:, None]
    return q, e1, np.cross(nr, e1), nr
VN = {k: vnormals(KX[k]) for k in KEYS}; VN0 = vnormals(X)
def bind_keys(ob, anchor_pts=None):
    """anchor_pts: optional per-vertex point used to pick the binding triangle (e.g. strand root)."""
    pc = np.array([v.co[:] for v in ob.data.vertices])
    look = pc if anchor_pts is None else anchor_pts
    ti = np.zeros(len(pc), int); bc = np.zeros((len(pc), 3))
    for i, p in enumerate(look):
        loc, nor, idx, d = T_tri.find_nearest(Vector(p))
        A_, B_, C_ = [Vector(X[j]) for j in tris[idx]]
        v0, v1, v2 = B_ - A_, C_ - A_, loc - A_
        d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
        den = d00 * d11 - d01 * d01; bv = (d11 * d20 - d01 * d21) / den; bw = (d00 * d21 - d01 * d20) / den
        ti[i] = idx; bc[i] = (1 - bv - bw, bv, bw)
    q, e1, e2, nn = frame(X, VN0, ti, bc); o = pc - q
    loc_off = np.c_[(o * e1).sum(1), (o * e2).sum(1), (o * nn).sum(1)]
    if ob.data.shape_keys: ob.shape_key_clear()
    ob.shape_key_add(name="Basis", from_mix=False)
    for k in KEYS:
        q2, f1, f2, fn = frame(KX[k], VN[k], ti, bc)
        ob.shape_key_add(name=k, from_mix=False).data.foreach_set("co", (q2 + loc_off[:, :1] * f1 + loc_off[:, 1:2] * f2 + loc_off[:, 2:3] * fn).ravel())

# ---------------------------------------------------------------- lash cards from the margin rings
def make_mesh(name, verts, faces, uvs, mat):
    m = bpy.data.meshes.new(name); m.from_pydata([tuple(v) for v in verts], [], faces)
    ul = m.uv_layers.new(name="UVMap")
    for p in m.polygons:
        p.use_smooth = True
        for li in p.loop_indices: ul.data[li].uv = uvs[m.loops[li].vertex_index]
    m.materials.append(mat); o = bpy.data.objects.new(name, m); coll.objects.link(o); return o
def grid_faces(nr, nc, flip):
    f = []
    for j in range(nr - 1):
        for i in range(nc - 1):
            a_ = j * nc + i
            f.append((a_, a_ + 1, a_ + nc + 1, a_ + nc) if not flip else (a_, a_ + nc, a_ + nc + 1, a_ + 1))
    return f
def resample(P, k):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]; s /= s[-1]
    t = np.linspace(0, 1, k); return np.stack([np.interp(t, s, P[:, i]) for i in range(3)], -1)
M_LASH = HT.hair_material(bpy, "M_LashUpper", HT.to_blender_image(bpy, "T_lash_upper", HT.lash_texture()), roughness=0.5)
M_LOW = HT.hair_material(bpy, "M_LashLower", HT.to_blender_image(bpy, "T_lash_lower", HT.lower_lash_texture()), roughness=0.5)
nbrs = [[] for _ in range(n)]
for e in me.edges:
    i, j = e.vertices; nbrs[i].append(j); nbrs[j].append(i)
sock = set(C["socket"])
for side in (("L", "R") if not os.environ.get("SKIP_LASH") else ()):
    sx = 1 if side == "L" else -1
    c = np.array(F[f"eye_{side}"]["center"]); R = F[f"eye_{side}"]["radius"]
    margin = list(w[f"eye_margin_{side}"]); mp = X[margin]
    i_in, i_out = int(np.argmin(np.abs(mp[:, 0]))), int(np.argmax(np.abs(mp[:, 0])))
    order = margin[i_in:] + margin[:i_in]; k_out = order.index(margin[i_out])
    h1, h2 = order[:k_out + 1], order[k_out:] + [order[0]]
    upper, lower = (h1, h2) if X[h1, 2].mean() > X[h2, 2].mean() else (h2, h1)
    # ring-1 vertex for each margin vertex: outward neighbour that is not socket / margin
    ms = set(margin)
    def ring_next(idx):
        out = []
        for v in idx:
            cand = [u for u in nbrs[v] if u not in ms and u not in sock]
            out.append(min(cand, key=lambda u: np.linalg.norm(X[u] - X[v])) if cand else v)
        return out
    for part, idx, M, nprot, L0, L1, up in (("Lash", upper, M_LASH, 5, 0.010, 0.020, True), ("LashLower", lower, M_LOW, 4, 0.004, 0.008, False)):
        if X[idx[0], 0] * sx > X[idx[-1], 0] * sx:
            idx = idx[::-1]                                     # inner -> outer
        r1 = ring_next(idx); r2 = ring_next(r1)
        NC = 70
        rows = [resample(X[idx], NC), resample(X[r1], NC), resample(X[r2], NC)]
        # visible edge: front silhouette of the opening (target feature), dropped onto the face; band grows away from the eye
        op = np.array(F[f"eye_{side}"]["opening"])
        half = op[op[:, 2] >= np.interp(op[:, 0], np.sort(op[:, 0]), op[np.argsort(op[:, 0]), 2]) - 1] if False else op
        mx = X[idx]; xs = np.linspace(mx[:, 0].min(), mx[:, 0].max(), NC)
        if sx < 0: xs = xs[::-1]
        def edge_z(x_, upper_side):
            sel = op[np.abs(op[:, 0] - x_) < 0.006]
            if not len(sel): return None
            return sel[:, 2].max() if upper_side else sel[:, 2].min()
        BW = float(os.environ.get("LASH_BAND", 0.0045)) if up else 0.0018
        drop = []
        for off in (0.0, BW * 0.5, BW):
            rw = []
            for x_ in xs:
                ez = edge_z(x_, up)
                if ez is None: ez = np.interp(x_, np.sort(mx[:, 0]), mx[np.argsort(mx[:, 0]), 2])
                z_ = ez + (off if up else -off) - (0.0008 if up else -0.0008)
                h = T_tri.ray_cast(Vector((x_, -2, z_)), Vector((0, 1, 0)), 5)
                y_ = (h[0].y if h[0] is not None else c[1] - R) - 0.0006
                rw.append((x_, y_, z_))
            drop.append(np.array(rw))
        rows = [drop[0], drop[1], drop[2]]
        # lift the band slightly off the skin
        for k_, rw in enumerate(rows):
            nr = rw - c; nr /= np.linalg.norm(nr, axis=1)[:, None]; rows[k_] = rw + nr * 0.0006
        base = rows[1]; tang = rows[2] - rows[0]; tang /= np.linalg.norm(tang, axis=1)[:, None]
        nrm = base - c; nrm /= np.linalg.norm(nrm, axis=1)[:, None]
        u_ = np.linspace(0, 1, NC)
        L = (L0 + (L1 - L0) * u_ ** 1.4) * (0.4 + 0.6 * np.clip(u_ * 5, 0, 1))
        d = 0.55 * nrm + (0.5 if up else -0.5) * np.array([0, 0, 1.0]) + 0.15 * np.array([sx, 0, 0])
        d = d / np.linalg.norm(d, axis=1)[:, None] if d.ndim == 2 else np.tile(d / np.linalg.norm(d), (NC, 1))
        tip_rows = [rows[0] + d * (L * f)[:, None] + (np.array([0, 0, 1.0]) if up else np.array([0, 0, -1.0])) * (L * 0.3 * f * f)[:, None]
                    for f in np.linspace(1 / nprot, 1, nprot)]
        allrows = [rows[2], rows[1], rows[0]] + tip_rows if up else [rows[0]] + tip_rows
        V = np.concatenate(allrows)
        nr_ = len(allrows)
        root_v = 0.36 if up else 0.16
        vs = ([0.0, root_v * 0.5, root_v] if up else [root_v * 0.5]) + list(np.linspace(root_v, 1, nprot + 1)[1:])
        uvs = [(u_[i], vs[j]) for j in range(nr_) for i in range(NC)]
        ob = make_mesh(f"{part}.{side}", V, grid_faces(nr_, NC, (sx > 0) == up), uvs, M)
        # non-blink keys: surface binding at the root; blink keys: driven by the lid rig of this half
        roots = np.concatenate([rows[0]] * nr_)
        bind_keys(ob, anchor_pts=roots)
        LB = json.loads(w["lid_bones"])[side]
        part_tag = "T" if up else "B"
        bones = [b for b in LB if b["name"].startswith(f"lid.{part_tag}.")]
        # weights of the nearest margin vertex of this half, per card column (rows share their column weights)
        gidx = {g.name: g.index for g in w.vertex_groups}
        def vweights(vi):
            out = np.zeros(len(bones))
            for gg in me.vertices[vi].groups:
                for bi, b in enumerate(bones):
                    if gg.group == gidx.get(b["name"]): out[bi] = gg.weight
            return out
        mv = np.array(idx)
        col_w = []
        for i in range(NC):
            j = mv[np.argmin(np.abs(X[mv, 0] - rows[0][i, 0]))]
            ww_ = vweights(j); col_w.append(ww_ / max(ww_.sum(), 1e-9))
        col_ang = np.array([sum(wk * b["ang"] for wk, b in zip(ww_, bones)) for ww_ in col_w])
        col_ang = np.convolve(np.pad(col_ang, 3, mode="edge"), np.ones(7) / 7, "valid")
        pc = np.array([v.co[:] for v in ob.data.vertices])
        colidx = np.arange(len(pc)) % NC
        cc_ = np.array(LB[0]["center"])
        kbs = ob.data.shape_keys.key_blocks
        for L_ in ("Left", "Right"):
            if (L_ == "Left") != (side == "L"): continue
            for suf, amt in (("_25", 0.25), ("_50", 0.5), ("_75", 0.75), ("", 1.0)):
                ang = -col_ang[colidx] * amt
                d_ = pc - cc_; ca, sa = np.cos(ang), np.sin(ang)
                P = pc.copy()
                P[:, 1] = cc_[1] + d_[:, 1] * ca - d_[:, 2] * sa
                P[:, 2] = cc_[2] + d_[:, 1] * sa + d_[:, 2] * ca
                # keep each lash column just above the (smoothed, lifted) lid surface of this key
                KXk = KX[f"eyeBlink{L_}{suf}"]
                from mathutils.kdtree import KDTree
                kdk = KDTree(n)
                for vi_, pv_ in enumerate(KXk): kdk.insert(pv_, vi_)
                kdk.balance()
                for i in range(NC):
                    sel = np.where(colidx == i)[0]
                    root = P[sel[0]]
                    near_ = [KXk[j] for _, j, _ in kdk.find_n(Vector(root), 6)]
                    r_lid = max(np.linalg.norm(np.array(q) - cc_) for q in near_)
                    r_root = np.linalg.norm(root - cc_)
                    lift = max(0.0, r_lid + 0.0008 - r_root)
                    if lift > 0:
                        dd = P[sel] - cc_; rr = np.linalg.norm(dd, axis=1)
                        P[sel] = cc_ + dd * ((rr + lift) / rr)[:, None]
                kbs[f"eyeBlink{L_}{suf}"].data.foreach_set("co", P.ravel())
        rep[f"{part}.{side}"] = len(V)

# ---------------------------------------------------------------- brows from the v1 silhouette, placed relative to the eye
BR = json.load(open(BROWS))
M_BROW = HT.hair_material(bpy, "M_BrowHair", HT.to_blender_image(bpy, "T_brow", HT.brow_texture(base=tuple(BR["rgb"]))), roughness=0.6)
for side in ("L", "R"):
    c = np.array(F[f"eye_{side}"]["center"]); R = F[f"eye_{side}"]["radius"]
    sx = 1 if side == "L" else -1
    rel = np.array(BR[side])               # rows of (u_outward/R, z_bottom/R, z_top/R) along the brow
    U = c[0] + sx * rel[:, 0] * R; Zb = c[2] + rel[:, 1] * R; Zt = c[2] + rel[:, 2] * R
    NR, NC = 8, len(rel)
    V, uvs = [], []
    for j in range(NR):
        t = j / (NR - 1)
        for i in range(NC):
            x_, z_ = U[i], Zb[i] + t * (Zt[i] - Zb[i])
            h = T_tri.ray_cast(Vector((x_, -2, z_)), Vector((0, 1, 0)), 5)
            y_ = (h[0].y if h[0] is not None else c[1] - R) - 0.0007
            V.append((x_, y_, z_)); uvs.append((i / (NC - 1), t))
    ob = make_mesh(f"Brow.{side}", np.array(V), grid_faces(NR, NC, sx < 0), uvs, M_BROW)
    bind_keys(ob)
    rep[f"Brow.{side}"] = len(V)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("PARTS", json.dumps(rep))
