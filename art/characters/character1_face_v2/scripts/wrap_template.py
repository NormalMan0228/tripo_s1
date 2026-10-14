"""Wrap the template head topology (MakeHuman/MPFB, CC0) onto the Tripo target surface.

Design from the target, topology from the template:
 1. template lid-margin rings and lip-seam ring (quad edge loops) <-> target eye openings / lip line
 2. similarity alignment on landmarks, then a 3D thin-plate spline through dense correspondences
 3. iterative closest-point projection of the outer skin + tangential relaxation; margins/seam pinned;
    eye-socket and mouth-bag vertices follow by smoothing only (not projected)
Writes wrapped.blend (object WrapHead + target objects) and wrap_report.json.
Usage: blender --background template_head.blend --python wrap_template.py -- <template_features.json> <target.blend> <target_features.json> <out_dir> [tag]
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(__file__))
from loop_tools import ring_around

a = sys.argv[sys.argv.index("--") + 1:]
TF = json.load(open(a[0])); TGT_BLEND = a[1]; GF = json.load(open(a[2])); OUT = os.path.abspath(a[3])
TAG = a[4] if len(a) > 4 else "A"
P = dict(iters=int(os.environ.get("WRAP_ITERS", 40)), relax=float(os.environ.get("WRAP_RELAX", 0.5)))
report = {"params": P}

ob = bpy.data.objects["TemplateHead"]
me = ob.data
tco = np.array([ob.matrix_world @ v.co for v in me.vertices])
n = len(tco)
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
nbrs = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
edges = np.array([(e.verts[0].index, e.verts[1].index) for e in bm.edges])
boundary = np.array([v.is_boundary for v in bm.verts])

# ---------------------------------------------------------------- template rings
def pick_eye_rings(side):
    c = np.array(TF[f"eye_{side}"]["center"]); r = TF[f"eye_{side}"]["radius"]
    rings = ring_around(bm, tco, c, max_r=0.05)
    info = []
    for _, lp in rings:
        d = np.linalg.norm(tco[lp] - c, axis=1).mean()
        info.append((d, lp))
    front = [(d, lp) for d, lp in info if tco[lp][:, 1].min() < c[1] - 0.3 * r]
    margin = min([t for t in front if t[0] >= 0.97 * r], key=lambda t: t[0])[1]
    outer = sorted([t for t in front if t[0] > np.linalg.norm(tco[margin] - c, axis=1).mean() + 1e-5], key=lambda t: t[0])
    inner = [lp for d, lp in info if d < 0.97 * r]
    return c, r, margin, [lp for _, lp in outer], inner


def order_ring(lp, start_idx_fn, up_first=True):
    i0 = start_idx_fn(lp)
    lp = lp[i0:] + lp[:i0]
    if (tco[lp[1], 2] < tco[lp[0], 2]) == up_first or (tco[lp[2], 2] < tco[lp[0], 2]) == up_first:
        lp = [lp[0]] + lp[1:][::-1]
    return lp


T_EYE = {}
for side in ("L", "R"):
    c, r, margin, outer, inner = pick_eye_rings(side)
    margin = order_ring(margin, lambda lp: int(np.argmin(np.abs(tco[lp, 0]))))
    T_EYE[side] = dict(c=c, r=r, margin=margin, outer=outer, inner=inner)
    report[f"template_eye_{side}"] = dict(margin_n=len(margin), outer_rings=len(outer), inner_rings=len(inner))

lipz = TF["mouth"]["lip_z"]
mrings = ring_around(bm, tco, [0.0, -0.10, lipz], max_r=0.05)
front_m = [lp for _, lp in mrings if tco[lp][:, 1].min() < -0.155]
seam = min(front_m, key=lambda lp: np.ptp(tco[lp][:, 2]))
seam = order_ring(seam, lambda lp: int(np.argmin(tco[lp, 0])))      # start at the right corner (min x), along the upper lip
mouth_rings = sorted([(np.linalg.norm(tco[lp] - tco[seam].mean(0), axis=1).mean(), lp) for _, lp in mrings], key=lambda t: t[0])
report["template_seam_n"] = len(seam)

# ---------------------------------------------------------------- target objects
with bpy.data.libraries.load(TGT_BLEND, link=False) as (df, dt):
    dt.objects = ["Body", "Eye.L", "Eye.R"]
for o in dt.objects:
    bpy.context.scene.collection.objects.link(o)
body = bpy.data.objects["Body"]
gco = np.array([body.matrix_world @ v.co for v in body.data.vertices])
gpoly = [tuple(p.vertices) for p in body.data.polygons]
G_EYE = {s: (np.array(GF[f"eye_{s}"]["center"]), GF[f"eye_{s}"]["radius"]) for s in ("L", "R")}
# BVH of the visible skin: drop faces hidden inside the eyeballs
keep = []
LLN = np.array(GF["lip_line"])
def behind_lips(c):
    """face centroid inside the mouth slit: within the lip-line x range, near its z, behind it by > 0.8 mm"""
    if c[0] < LLN[:, 0].min() or c[0] > LLN[:, 0].max(): return False
    j = np.argmin(np.abs(LLN[:, 0] - c[0]))
    return abs(c[2] - LLN[j, 2]) < float(os.environ.get("MOUTH_DROP_Z", 0.006)) and c[1] > LLN[j, 1] + float(os.environ.get("MOUTH_DROP_Y", 9.0))
n_behind = 0
for p in body.data.polygons:
    c = np.mean([gco[i] for i in p.vertices], axis=0)
    if all(np.linalg.norm(c - G_EYE[s][0]) > G_EYE[s][1] * 1.0 for s in ("L", "R")):
        if behind_lips(c): n_behind += 1; continue
        keep.append(tuple(p.vertices))
report["target_faces_inside_mouth_dropped"] = n_behind
# projection target: Body with the deep smile-corner pockets softened (bake still uses the original surface)
MC_SOFT = float(os.environ.get("MC_SOFT_R", 0.03)); MC_SOFT_IT = int(os.environ.get("MC_SOFT_IT", 40))
gco_p = gco.copy()
if MC_SOFT_IT:
    ll_ = np.array(GF["lip_line"]); cpts = [ll_[0], ll_[-1]]
    gnb = [[] for _ in range(len(gco))]
    for e in body.data.edges:
        i_, j_ = e.vertices; gnb[i_].append(j_); gnb[j_].append(i_)
    dmin = np.min([np.linalg.norm(gco - c_, axis=1) for c_ in cpts], axis=0)
    wsoft = np.clip(1 - dmin / MC_SOFT, 0, 1) ** 2
    idx_s = np.where(wsoft > 0)[0]
    for _ in range(MC_SOFT_IT):
        avg = np.array([gco_p[gnb[i_]].mean(0) if gnb[i_] else gco_p[i_] for i_ in idx_s])
        gco_p[idx_s] += (avg - gco_p[idx_s]) * (0.5 * wsoft[idx_s])[:, None]
    report["mouth_corner_soft_verts"] = int(len(idx_s))
G_BVH = BVHTree.FromPolygons([tuple(p) for p in gco_p], keep)
G_BVH_ORIG = BVHTree.FromPolygons([tuple(p) for p in gco], keep)
G_BVH_ALL = BVHTree.FromPolygons([tuple(p) for p in gco], gpoly)


def resample_like(pts, tmpl_pts, blend=None):
    """Place len(tmpl_pts) points along polyline pts at the template's own (normalised) arc-length spacing,
    blended with uniform spacing (blend=1 -> fully template spacing)."""
    blend = float(os.environ.get("SPACING_BLEND", 0.85)) if blend is None else blend
    pts = np.asarray(pts, float); tp = np.asarray(tmpl_pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1); s_ = np.r_[0, np.cumsum(seg)]; s_ /= s_[-1]
    ts = np.linalg.norm(np.diff(tp, axis=0), axis=1); t_ = np.r_[0, np.cumsum(ts)]; t_ /= max(t_[-1], 1e-12)
    t_ = blend * t_ + (1 - blend) * np.linspace(0, 1, len(tp))
    return np.stack([np.interp(t_, s_, pts[:, i]) for i in range(3)], -1)


def resample(pts, k):
    pts = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]; s /= s[-1]
    t = np.linspace(0, 1, k)
    return np.stack([np.interp(t, s, pts[:, i]) for i in range(3)], -1)


def corner_split(lp_pts):
    """index of the outer corner (max |x|) in an eye ring that starts at the inner corner."""
    return int(np.argmax(np.abs(lp_pts[:, 0])))


# ---------------------------------------------------------------- correspondences
src, dst, wts = [], [], []
for side in ("L", "R"):
    m = T_EYE[side]["margin"]; tm = tco[m]
    k_out = corner_split(tm)
    op = np.array(GF[f"eye_{side}"].get(os.environ.get("EYE_PIN", "contact"), GF[f"eye_{side}"]["opening"])); op = np.vstack([op, op[:1]])
    g_out = int(np.argmax(np.abs(op[:, 0])))
    tm_closed = np.vstack([tm, tm[:1]])
    top = resample_like(op[:g_out + 1], tm_closed[:k_out + 1])
    bot = resample_like(op[g_out:], tm_closed[k_out:])
    tgt = np.vstack([top, bot[1:-1]])
    src += list(tm); dst += list(tgt); wts += [1.0] * len(m)
ll = np.array(GF["lip_line"])
k_left = int(np.argmax(tco[seam, 0]))                         # left corner index along the ordered seam
SEAM_OFF = float(os.environ.get('SEAM_OFF', 0.0)); SEAM_FWD = float(os.environ.get('SEAM_FWD', 0.0))
ts_ = tco[seam]; ts_c = np.vstack([ts_, ts_[:1]])
upper = resample_like(ll, ts_c[:k_left + 1], float(os.environ.get('LIP_SPACING_BLEND', 0.0))) + [0, 0, SEAM_OFF] - [0, SEAM_FWD, 0]
lower = resample_like(ll[::-1], ts_c[k_left:], float(os.environ.get('LIP_SPACING_BLEND', 0.0))) - [0, 0, SEAM_OFF] - [0, SEAM_FWD, 0]
src += list(tco[seam]); dst += list(np.vstack([upper, lower[1:-1]])); wts += [1.0] * len(seam)


def tvert(key):
    return tco[TF[key]] if isinstance(TF[key], int) else np.array(TF[key])


LM = [("nose_tip", "nose_tip"), ("chin", "chin"), ("head_top", "head_top"), ("head_back", "head_back")]
for tk, gk in LM:
    src.append(tvert(tk)); dst.append(np.array(GF[gk])); wts.append(1.0)
# ear labels + ear extremes (template 'ears' group vs thickness-segmented target ears), subnasale
gi_ear = ob.vertex_groups["ears"].index
t_ear = np.array([any(g.group == gi_ear and g.weight > 0.5 for g in v.groups) for v in me.vertices])
t_label = np.zeros(n, int); t_label[t_ear & (tco[:, 0] > 0)] = 1; t_label[t_ear & (tco[:, 0] < 0)] = 2
EARS = json.load(open(os.path.join(os.path.dirname(a[2]), "target_ears.json")))
LMP = json.load(open(os.path.join(os.path.dirname(a[2]), "landmarks_pair.json")))
EAR_AFFINE = {}
for s_, lab in (("L", 1), ("R", 2)):
    EP = tco[t_label == lab]
    TP = gco[EARS[s_]]
    sc_ = TP.std(0) / np.maximum(EP.std(0), 1e-9)
    EAR_AFFINE[lab] = (EP.mean(0), TP.mean(0), sc_)
    idx = np.where(t_label == lab)[0][::6]
    for i in idx:
        src.append(tco[i]); dst.append(TP.mean(0) + sc_ * (tco[i] - EP.mean(0))); wts.append(0.5)
src.append(np.array(LMP["template"]["subnasale"])); dst.append(np.array(LMP["target"]["subnasale"])); wts.append(1.0)
report["ear_template_verts"] = int(t_ear.sum())

src = np.array(src); dst = np.array(dst)
# similarity (Umeyama) from the sparse landmarks + ring centroids
def umeyama(X, Y):
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my
    U, S, Vt = np.linalg.svd(Yc.T @ Xc / len(X))
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / (Xc ** 2).sum() * len(X)
    return s, R, my - s * R @ mx
sim_src = np.array([tco[T_EYE["L"]["margin"]].mean(0), tco[T_EYE["R"]["margin"]].mean(0), tco[seam].mean(0),
                    tvert("nose_tip"), tvert("chin"), tvert("head_top")])
sim_dst = np.array([np.array(GF["eye_L"]["opening"]).mean(0), np.array(GF["eye_R"]["opening"]).mean(0), ll.mean(0),
                    np.array(GF["nose_tip"]), np.array(GF["chin"]), np.array(GF["head_top"])])
s, R, t = umeyama(sim_src, sim_dst)
report["similarity_scale"] = float(s)
X0 = (s * (R @ tco.T)).T + t
srcA = (s * (R @ src.T)).T + t

# neck ring: template boundary loop -> target cross-section at the matching relative height
bnd_idx = np.where(boundary)[0]
chin_t, top_t = X0[TF["chin"]][2], X0[TF["head_top"]][2]
neck_z = X0[bnd_idx, 2].mean()
c_neck = X0[bnd_idx].mean(0)
for i in bnd_idx:
    d = X0[i] - c_neck; d[2] = 0; dn = d / (np.linalg.norm(d) + 1e-9)
    o = Vector((c_neck[0], c_neck[1], X0[i, 2]))
    h = G_BVH_ALL.ray_cast(o + Vector(dn) * 0.6, Vector(-dn), 1.0)
    if h[0] is not None:
        srcA = np.vstack([srcA, X0[i]]); dst = np.vstack([dst, np.array(h[0])]); wts.append(0.5)

# ---------------------------------------------------------------- thin-plate spline (phi = r)
def tps(Xs, Ys, reg=1e-6):
    N = len(Xs)
    K = np.linalg.norm(Xs[:, None] - Xs[None], axis=2)
    Pm = np.c_[np.ones(N), Xs]
    A = np.zeros((N + 4, N + 4)); A[:N, :N] = K + reg * np.eye(N); A[:N, N:] = Pm; A[N:, :N] = Pm.T
    B = np.zeros((N + 4, 3)); B[:N] = Ys
    sol = np.linalg.solve(A, B)
    return lambda Q: np.linalg.norm(Q[:, None] - Xs[None], axis=2) @ sol[:N] + np.c_[np.ones(len(Q)), Q] @ sol[N:]
f = tps(srcA, dst)
X = f(X0)
report["tps_points"] = int(len(srcA))

# ---------------------------------------------------------------- vertex classes
pinned = np.zeros(n, bool)
for side in ("L", "R"):
    pinned[T_EYE[side]["margin"]] = True
pinned[seam] = True
pin_pos = {}
k = 0
for side in ("L", "R"):
    for i in T_EYE[side]["margin"]:
        pin_pos[i] = dst[k]; k += 1
for i in seam:
    pin_pos[i] = dst[k]; k += 1
def flood(seeds, stop):
    seen = set(seeds); st = list(seeds)
    while st:
        v = st.pop()
        for w in nbrs[v]:
            if w not in seen and not stop[w]:
                seen.add(w); st.append(w)
    return np.array(sorted(seen), int)


def smaller_side(ring):
    """Flood the off-ring neighbours with the ring as barrier; return the smaller enclosed region."""
    rs = set(ring)
    stop = np.zeros(n, bool); stop[list(rs)] = True
    cand = [w for v in ring for w in nbrs[v] if w not in rs]
    regions, used = [], set()
    for c0 in cand:
        if c0 in used:
            continue
        reg = flood([c0], stop)
        used.update(reg.tolist()); regions.append(reg)
    regions.sort(key=len)
    return regions[0] if len(regions) > 1 else np.array([], int), [len(r) for r in regions]


inner = np.zeros(n, bool)
socks = []
for side in ("L", "R"):
    sk, sizes = smaller_side(T_EYE[side]["margin"])
    socks.append(sk); report[f"socket_split_{side}"] = sizes
sock = np.concatenate(socks)
bag, sizes = smaller_side(seam); report["bag_split"] = sizes
inner[sock] = True; inner[bag] = True
# cavities of the template (nostrils, ear canal / concha, inner lips): a ray along the vertex normal hits the
# template itself within CAV_D -> do not project them; they ride along harmonically
T_BVH = BVHTree.FromPolygons([tuple(p) for p in tco], [tuple(p.vertices) for p in me.polygons])
tN = np.array([v.normal[:] for v in me.vertices])
CAV_D = float(os.environ.get("WRAP_CAV_D", 0.012))
cav = np.zeros(n, bool)
for i in range(n):
    if pinned[i] or inner[i]:
        continue
    h = T_BVH.ray_cast(Vector(tco[i]) + Vector(tN[i]) * 1e-4, Vector(tN[i]), CAV_D)
    if h[0] is not None:
        cav[i] = True
report["cavity_verts"] = int(cav.sum())
inner |= cav
inner[pinned] = False
surf = ~inner & ~pinned
report["classes"] = dict(pinned=int(pinned.sum()), socket=int(len(sock)), mouth_bag=int(len(bag)), surface=int(surf.sum()))

for i, p in pin_pos.items():
    X[i] = p

# ---------------------------------------------------------------- optional: export for NRICP (art-venv) / import result
STAGE = os.environ.get("WRAP_STAGE", "")
if STAGE == "export":
    gf = np.array([p for p in gpoly if len(p) == 3] + [(p[0], p[i], p[i + 1]) for p in gpoly if len(p) > 3 for i in range(1, len(p) - 1)])
    kp = np.array([all(np.linalg.norm(gco[list(t)].mean(0) - G_EYE[sd][0]) > G_EYE[sd][1] for sd in ("L", "R")) for t in gf])
    lm_idx = np.array(sorted(pin_pos)); lm_pos = np.array([pin_pos[i] for i in lm_idx])
    ear_set = {"L": set(EARS["L"]), "R": set(EARS["R"])}
    tf = gf[kp]
    f_label = np.array([1 if sum(v in ear_set["L"] for v in t) >= 2 else 2 if sum(v in ear_set["R"] for v in t) >= 2 else 0 for t in tf])
    np.savez(os.path.join(OUT, f"nricp_in_{TAG}.npz"), src=X, edges=edges, tgt_v=gco, tgt_f=tf, tgt_label=f_label,
             src_label=t_label, data_w=surf.astype(float), lm_idx=lm_idx, lm_pos=lm_pos, beta=np.array(10.0))
    print("EXPORTED"); raise SystemExit(0)
if STAGE == "import":
    X = np.load(os.path.join(OUT, f"nricp_out_{TAG}.npz"))["X"]
    if os.environ.get("EAR_KEEP"):
        ear_keep = t_label > 0
        surf = surf & ~ear_keep
        report["ears_kept_from_nricp"] = int(ear_keep.sum())
    P["iters"] = int(os.environ.get("WRAP_FINAL_ITERS", 6)); P["relax"] = float(os.environ.get("WRAP_FINAL_RELAX", 0.15))
# ---------------------------------------------------------------- projection + relaxation
deg = np.array([len(nb) for nb in nbrs])
def laplacian(Y):
    acc = np.zeros_like(Y)
    for i, nb in enumerate(nbrs):
        acc[i] = Y[nb].mean(0) - Y[i]
    return acc
def vnormals(Y):
    Nn = np.zeros_like(Y)
    for p in me.polygons:
        vs = list(p.vertices)
        fn = np.cross(Y[vs[1]] - Y[vs[0]], Y[vs[2]] - Y[vs[0]])
        Nn[vs] += fn
    return Nn / np.maximum(np.linalg.norm(Nn, axis=1), 1e-12)[:, None]
MODE = os.environ.get("WRAP_PROJ", "ray")
def project(i, Nn):
    p = Vector(X[i])
    if MODE == "ray":
        nrm = Vector(Nn[i])
        best = None
        for d in (nrm, -nrm):
            h = G_BVH.ray_cast(p, d, 0.03)
            if h[0] is not None and (best is None or h[3] < best[1]):
                best = (h[0], h[3])
        if best is not None:
            return np.array(best[0])
    loc = G_BVH.find_nearest(p)[0]
    return np.array(loc) if loc is not None else X[i]
for it in range(P["iters"]):
    Nn = vnormals(X)
    for i in np.where(surf)[0]:
        X[i] = project(i, Nn)
    L = laplacian(X); Nn = vnormals(X)
    Lt = L - (L * Nn).sum(1)[:, None] * Nn
    lam = P["relax"] * (1 - it / P["iters"]) ** 0.5
    X[surf] += lam * Lt[surf]
    X[inner] += float(os.environ.get("WRAP_INNER_SMOOTH", 0.0)) * L[inner]
    if not surf[boundary].all():
        pass
Nn = vnormals(X)
for i in np.where(surf)[0]:
    X[i] = project(i, Nn)
for i, p in pin_pos.items():
    X[i] = p
# lid zone untangle: the template's lid crease folds when pressed onto a smooth target lid
LID_RINGS = int(os.environ.get("LID_RINGS", 7)); UNT = int(os.environ.get("LID_UNTANGLE", 60))
if UNT:
    lidzone = np.zeros(n, bool)
    for side in ("L", "R"):
        dist = {v: 0 for v in T_EYE[side]["margin"]}; fr = list(T_EYE[side]["margin"])
        for k in range(1, LID_RINGS + 1):
            nx = []
            for v in fr:
                for u in nbrs[v]:
                    if u not in dist and surf[u]:
                        dist[u] = k; nx.append(u)
            fr = nx
        for v, k in dist.items():
            if k > 0: lidzone[v] = True
    zi = np.where(lidzone)[0]
    for it in range(UNT):
        Lu = np.array([X[nbrs[i]].mean(0) - X[i] for i in zi])
        X[zi] += 0.6 * Lu
        for i in zi:
            loc = G_BVH.find_nearest(Vector(X[i]))[0]
            if loc is not None: X[i] = np.array(loc)
    report["lid_untangle_verts"] = int(len(zi))
# mouth-corner untangle: release the two seam corner pins and relax a few rings around them
MC_R = int(os.environ.get("MC_RINGS", 3)); MC_IT = int(os.environ.get("MC_ITERS", 40))
if MC_IT:
    corners = [seam[int(np.argmin(X[seam, 0]))], seam[int(np.argmax(X[seam, 0]))]]
    zone = set(corners); fr = list(corners)
    for k in range(MC_R):
        nx = []
        for v in fr:
            for u in nbrs[v]:
                if u not in zone and (surf[u] or u in corners or pinned[u]):
                    zone.add(u); nx.append(u)
        fr = nx
    seam_set = set(seam)
    zi = [i for i in zone if (i not in seam_set) or i in corners]
    for it in range(MC_IT):
        for i in zi:
            X[i] = X[i] + 0.5 * (X[nbrs[i]].mean(0) - X[i])
            loc = G_BVH.find_nearest(Vector(X[i]))[0]
            if loc is not None: X[i] = np.array(loc)
    report["mouth_corner_relax_verts"] = len(zi)
# lip zone: tangential relaxation (cotangent-free, length-weighted) + projection onto the ORIGINAL target,
# seam pinned (corners included), N rings around the seam
LZ_R = int(os.environ.get("LIP_RINGS", 5)); LZ_IT = int(os.environ.get("LIP_ITERS", 0))
if LZ_IT:
    seam_set = set(seam)
    dist = {v: 0 for v in seam}; fr = list(seam)
    for k in range(1, LZ_R + 1):
        nx = []
        for v in fr:
            for u in nbrs[v]:
                if u not in dist and surf[u]:
                    dist[u] = k; nx.append(u)
        fr = nx
    zi = np.array([v for v, k in dist.items() if k > 0])
    wz = np.array([1.0 - 0.5 * (dist[v] - 1) / max(LZ_R - 1, 1) for v in zi])
    for it in range(LZ_IT):
        Nn = vnormals(X)
        for i, wi in zip(zi, wz):
            L = X[nbrs[i]].mean(0) - X[i]; nrm = Nn[i]
            X[i] = X[i] + 0.6 * wi * (L - L.dot(nrm) * nrm)
            loc = G_BVH_ORIG.find_nearest(Vector(X[i]))[0]
            if loc is not None: X[i] = np.array(loc)
    report["lip_zone_verts"] = int(len(zi))
# flip repair: surface faces whose normal opposes the target normal -> smooth their verts (+1 ring) and reproject
FR_IT = int(os.environ.get("FLIP_ITERS", 25))
polys_all = [list(p.vertices) for p in me.polygons]
for it in range(FR_IT):
    bad = set()
    for vs in polys_all:
        if not all(surf[v] or pinned[v] for v in vs): continue
        P_ = X[vs]; cen = P_.mean(0); nrm = np.cross(P_[1] - P_[0], P_[2] - P_[0])
        loc, tn, idx, d = G_BVH_ORIG.find_nearest(Vector(cen))
        if loc is not None and np.dot(nrm, np.array(tn)) < 0:
            bad.update(vs)
    if not bad: break
    zone = set(bad)
    for v in list(bad): zone.update(nbrs[v])
    for v in zone:
        if not surf[v]: continue
        X[v] = X[v] + 0.5 * (X[nbrs[v]].mean(0) - X[v])
        loc = G_BVH_ORIG.find_nearest(Vector(X[v]))[0]
        if loc is not None: X[v] = np.array(loc)
    report["flip_repair_last_bad"] = len(bad); report["flip_repair_iters"] = it + 1
# inner regions (eye socket, mouth bag): harmonic displacement from the surrounding final positions
disp = X - X0
fixed = ~inner
wE = 1.0 / np.maximum(np.linalg.norm(X0[edges[:, 0]] - X0[edges[:, 1]], axis=1), 1e-6)
d = disp.copy(); d[inner] = 0
degw = np.zeros(n); np.add.at(degw, edges[:, 0], wE); np.add.at(degw, edges[:, 1], wE)
for _ in range(3000):
    acc = np.zeros_like(d)
    np.add.at(acc, edges[:, 0], wE[:, None] * d[edges[:, 1]])
    np.add.at(acc, edges[:, 1], wE[:, None] * d[edges[:, 0]])
    d[inner] = acc[inner] / degw[inner, None]
X[inner] = X0[inner] + d[inner]
# mouth bag: procedural tube straight behind the final lip seam (ring k from the seam -> k*BAG_STEP deeper,
# shrinking toward the seam centroid); guaranteed to stay behind the lips
if len(bag):
    seam_a = np.array(seam); bag_set = set(bag.tolist())
    ring = {v: 0 for v in seam}; fr = list(seam)
    while fr:
        nx = []
        for v in fr:
            for u in nbrs[v]:
                if u in bag_set and u not in ring:
                    ring[u] = ring[v] + 1; nx.append(u)
        fr = nx
    near_seam = {}
    for i in bag:
        near_seam[i] = seam_a[np.argmin(np.linalg.norm(tco[seam_a] - tco[i], axis=1))]
    sc_ = X[seam_a].mean(0)
    kmax = max(ring.values()) if ring else 1
    # cavity ellipse: centre / radii from env (defaults sized for character1's Tripo oral cavity)
    ZC = float(os.environ.get("CAV_ZC", sc_[2])); AX = float(os.environ.get("CAV_AX", 0.085)); AZ = float(os.environ.get("CAV_AZ", 0.045))
    DEPTH = float(os.environ.get("CAV_DEPTH", 0.17))
    tsc = tco[seam_a].mean(0); tspan = np.ptp(tco[seam_a], axis=0) + 1e-9
    for i in bag:
        k = ring.get(i, kmax); j = near_seam[i]; t = k / kmax
        rel = tco[i] - tsc
        th = math.atan2(rel[2] / tspan[2], rel[0] / tspan[0])
        f = math.sin(math.pi * min(1.0, t * 1.15)) ** 0.6 if t < 0.999 else 0.0
        ell = np.array([AX * f * math.cos(th), 0.0, ZC + AZ * f * math.sin(th)])
        g = min(1.0, t / float(os.environ.get("CAV_BLEND", 0.4))); g = g * g * (3 - 2 * g)
        p_ = X[j] * (1 - g) + ell * g
        p_[1] = X[j, 1] * (1 - g) + (sc_[1] + DEPTH * t) * g if t > 0 else X[j, 1]
        X[i] = p_
    report["bag_rings"] = int(kmax)
# bag vertices must be hidden behind the wrap's own lip surface (front-ray test against non-bag faces)
if len(bag):
    bag_set = set(bag.tolist())
    skin_polys = [tuple(p.vertices) for p in me.polygons if not any(v in bag_set for v in p.vertices)]
    for rep_it in range(3):
        TW = BVHTree.FromPolygons([tuple(p) for p in X], skin_polys)
        moved = 0
        for i in bag:
            h = TW.ray_cast(Vector((X[i, 0], -2.0, X[i, 2])), Vector((0, 1, 0)), 5)
            if h[0] is not None and X[i, 1] < h[0].y + 0.0015:
                X[i, 1] = h[0].y + 0.0015; moved += 1
            elif h[0] is None:
                pass
        report[f"bag_pushed_{rep_it}"] = moved
    # bag verts left uncovered (no skin in front of them) are visible lip surface: snap them onto the target
    TW = BVHTree.FromPolygons([tuple(p) for p in X], skin_polys)
    snapped = 0
    for i in bag:
        h = TW.ray_cast(Vector((X[i, 0], -2.0, X[i, 2])), Vector((0, 1, 0)), 5)
        covered = h[0] is not None and h[0].y < X[i, 1]
        if not covered:
            g = G_BVH_ORIG.ray_cast(Vector((X[i, 0], -2.0, X[i, 2])), Vector((0, 1, 0)), 5)
            if g[0] is not None and g[0].y < X[i, 1] + 0.004:
                X[i] = np.array(g[0]) + np.array([0, 0.0003, 0]); snapped += 1
    report["bag_snapped_visible"] = snapped
# interior vertices must stay inside the skin (at least 2.5 mm)
for i in np.where(inner)[0]:
    loc, nor, idx, dist = G_BVH_ALL.find_nearest(Vector(X[i]))
    if loc is None:
        continue
    if (Vector(X[i]) - loc).dot(nor) > -0.0025 and i not in sock and (i not in set(bag.tolist()) or os.environ.get("BAG_CLAMP")):
        X[i] = np.array(loc - nor * 0.0025)
# eye socket hugs the eyeball: every socket vertex sits on the sphere (radius + SOCK_GAP), no cavity
SOCK_GAP = float(os.environ.get("SOCK_GAP", 0.0008))
for i in sock:
    side = "L" if X[i, 0] > 0 else "R"
    gc, gr = G_EYE[side]
    d = X[i] - gc; r = np.linalg.norm(d)
    if r > 1e-9:
        X[i] = gc + d / r * (gr + SOCK_GAP)
# relax the socket on the sphere (even spacing) and re-project
for _ in range(int(os.environ.get("SOCK_RELAX", 20))):
    for i in sock:
        side = "L" if X[i, 0] > 0 else "R"; gc, gr = G_EYE[side]
        q = 0.5 * X[i] + 0.5 * X[nbrs[i]].mean(0); d = q - gc
        X[i] = gc + d / np.linalg.norm(d) * (gr + SOCK_GAP)

# exact symmetry: mirror partners from the (symmetric) template topology, average each pair
from mathutils.kdtree import KDTree
kdT = KDTree(n)
for i, p in enumerate(tco): kdT.insert(p, i)
kdT.balance()
fm = [kdT.find((-p[0], p[1], p[2])) for p in tco]
mir = np.array([f[1] for f in fm]); okm = np.array([f[2] < 2e-4 for f in fm]) & okm_dummy if False else np.array([f[2] < 2e-4 for f in fm])
okm &= okm[mir]
Xs = X.copy()
# average the pair, except where the two sides disagree by > 3 cm (a broken vertex): copy the +X side
avg = okm.copy()
bad = okm & (np.linalg.norm(X - X[mir] * np.array([-1, 1, 1]), axis=1) > 0.03)
avg &= ~bad
Xs[avg, 0] = 0.5 * (X[avg, 0] - X[mir[avg], 0]); Xs[avg, 1:] = 0.5 * (X[avg, 1:] + X[mir[avg], 1:])
for i in np.where(bad)[0]:
    src_i = i if tco[i, 0] > 0 else mir[i]
    Xs[i] = X[src_i] * (np.array([1, 1, 1]) if src_i == i else np.array([-1, 1, 1]))
report["symmetrize_bad_pairs"] = int(bad.sum())
report["symmetrize_unpaired"] = int((~okm).sum())
_mv = np.linalg.norm(Xs - X, axis=1); _top = np.argsort(-_mv)[:8]
report["symmetrize_top"] = [[int(i), round(float(_mv[i]) * 1000, 1), np.round(X[i], 3).tolist(), np.round(X[mir[i]], 3).tolist(), "bag" if i in set(bag.tolist()) else ("sock" if i in set(sock.tolist()) else "surf")] for i in _top]
mid = np.abs(tco[:, 0]) < 1e-5; Xs[mid, 0] = 0.0
report["symmetrize_max_move_mm"] = float(np.linalg.norm(Xs - X, axis=1).max() * 1000)
X = Xs
# ---------------------------------------------------------------- metrics
dist = np.array([G_BVH.find_nearest(Vector(p))[3] for p in X[surf]])
report["fit_surface_dist_mm"] = dict(mean=float(dist.mean() * 1000), p95=float(np.percentile(dist, 95) * 1000), max=float(dist.max() * 1000))
el0 = np.linalg.norm(tco[edges[:, 0]] - tco[edges[:, 1]], axis=1) * s
el1 = np.linalg.norm(X[edges[:, 0]] - X[edges[:, 1]], axis=1)
ratio = el1 / np.maximum(el0, 1e-9)
report["edge_stretch"] = dict(p05=float(np.percentile(ratio, 5)), median=float(np.median(ratio)), p95=float(np.percentile(ratio, 95)))
# flipped faces vs template orientation (after similarity)
flip = 0
Nt = vnormals(X0); Nw = vnormals(X)
flip = int(((Nt * Nw).sum(1) < 0).sum())
report["normal_flips_vs_template"] = flip

wob = ob.copy(); wob.data = me.copy(); wob.name = "WrapHead"; wob.data.name = "WrapHead"
bpy.context.scene.collection.objects.link(wob)
if wob.data.shape_keys:
    wob.shape_key_clear()
for v, p in zip(wob.data.vertices, X):
    v.co = p
wob.matrix_world = wob.matrix_world.__class__()
wob["vertex_classes"] = json.dumps({"pinned": np.where(pinned)[0].tolist(), "socket": sock.tolist(), "bag": bag.tolist()})
wob["eye_margin_L"] = T_EYE["L"]["margin"]; wob["eye_margin_R"] = T_EYE["R"]["margin"]; wob["lip_seam"] = seam
wob["eye_rings_L"] = json.dumps(T_EYE["L"]["outer"]); wob["eye_rings_R"] = json.dumps(T_EYE["R"]["outer"])
ob.hide_render = True; ob.hide_viewport = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"wrapped_{TAG}.blend"))
json.dump(report, open(os.path.join(OUT, f"wrap_report_{TAG}.json"), "w"), indent=1)
print("WRAP", json.dumps(report))
