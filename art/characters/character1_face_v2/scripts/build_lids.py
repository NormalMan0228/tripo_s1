"""Eyelid rig on the wrapped template topology (lids are part of the face mesh).

Per eye: upper lid split into N_UP column bones, lower lid into N_LO, all pivoting at the eye centre about the
world X axis. Weights = ring-distance falloff from the lid margin (socket side = 1, outer rings fade to 0 over
FALL_UP / FALL_LO rings) x column hat functions along the margin x x corner taper.
Close angles per bone: upper margin column -> closure line at CLOSE_K between the lower and upper margin
elevation, lower margin column -> same line. The skinned result is baked into shape keys with arc-correct
in-betweens (eyeBlink{L,R}_25/_50/_75/full); bones + weights are stored for the game rig.
Also assigns materials: eye socket (M_LidInner) and mouth bag (M_MouthInside).
Usage: blender --background face_keys.blend --python build_lids.py -- <out.blend> <report.json>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

a = sys.argv[sys.argv.index("--") + 1:]
OUT, REP = os.path.abspath(a[0]), os.path.abspath(a[1])
N_UP, N_LO = int(os.environ.get("N_UP", 5)), int(os.environ.get("N_LO", 3))
FALL_UP, FALL_LO = float(os.environ.get("FALL_UP", 7)), float(os.environ.get("FALL_LO", 4))
CLOSE_K = float(os.environ.get("CLOSE_K", 0.3))
OVERLAP = float(os.environ.get("OVERLAP", 0.02))
w = bpy.data.objects["WrapHead"]
me = w.data
X = np.array([v.co[:] for v in me.vertices]); n = len(X)
C = json.loads(w["vertex_classes"]); sock = set(C["socket"]); bag = set(C["bag"])
F = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), "target_features.json")))
nbrs = [[] for _ in range(n)]
for e in me.edges:
    i, j = e.vertices; nbrs[i].append(j); nbrs[j].append(i)
rep = {}


def alpha(P, c):
    d = np.atleast_2d(P) - c
    return np.arctan2(d[:, 2], -d[:, 1])


def rot_x(P, c, ang):
    d = P - c
    ca, sa = np.cos(ang), np.sin(ang)
    out = P.copy()
    out[:, 1] = c[1] + d[:, 1] * ca - d[:, 2] * sa
    out[:, 2] = c[2] + d[:, 1] * sa + d[:, 2] * ca
    return out


def bfs_dist(seeds, allowed):
    dist = np.full(n, np.inf); dist[list(seeds)] = 0; frontier = list(seeds)
    k = 0
    while frontier:
        k += 1; nxt = []
        for v in frontier:
            for u in nbrs[v]:
                if dist[u] == np.inf and allowed[u]:
                    dist[u] = k; nxt.append(u)
        frontier = nxt
    return dist


EYES = {}
all_bones = []
weights = {}           # bone -> (n,) weights
for side in ("L", "R"):
    c = np.array(F[f"eye_{side}"]["center"]); R = F[f"eye_{side}"]["radius"]
    margin = list(w[f"eye_margin_{side}"])
    m = X[margin]
    i_in = int(np.argmin(np.abs(m[:, 0]))); i_out = int(np.argmax(np.abs(m[:, 0])))
    # split margin ring into upper/lower halves between the corners
    order = margin[i_in:] + margin[:i_in]
    k_out = order.index(margin[i_out])
    h1, h2 = order[:k_out + 1], order[k_out:] + [order[0]]
    upper, lower = (h1, h2) if X[h1, 2].mean() > X[h2, 2].mean() else (h2, h1)
    ax = np.abs(X[margin, 0] - c[0])
    # elevation profiles along x (sorted)
    def prof(idx):
        P = X[idx]; o = np.argsort(P[:, 0]); return P[o, 0], alpha(P[o], c)
    ux, ua = prof(upper); lx, la = prof(lower)
    x0, x1 = X[margin, 0].min(), X[margin, 0].max()
    # ring distance from margin over the outer skin (not socket, not other eye / bag)
    allowed_out = np.array([i not in sock and i not in bag for i in range(n)])
    near = np.linalg.norm(X - c, axis=1) < R * 2.6
    d_out = bfs_dist(margin, allowed_out & near)
    side_up = np.zeros(n, bool)
    # assign upper/lower by nearest margin vertex (graph-free: euclidean)
    mu, ml = X[upper], X[lower]
    du = np.min(np.linalg.norm(X[:, None] - mu[None], axis=2), axis=1)
    dl = np.min(np.linalg.norm(X[:, None] - ml[None], axis=2), axis=1)
    side_up = du <= dl
    # socket verts of this eye
    sock_this = np.array([i in sock for i in range(n)]) & (np.linalg.norm(X - c, axis=1) < R * 1.6)

    def smooth_fall(d, D):
        t = np.clip(d / D, 0, 1)
        return 1 - t * t * (3 - 2 * t)

    base_w = np.zeros(n)
    fin = np.isfinite(d_out)
    PLAT_UP, PLAT_LO = float(os.environ.get("PLAT_UP", 3)), float(os.environ.get("PLAT_LO", 2))
    base_w[fin] = np.where(side_up[fin], smooth_fall(np.maximum(d_out[fin] - PLAT_UP, 0), FALL_UP),
                           smooth_fall(np.maximum(d_out[fin] - PLAT_LO, 0), FALL_LO))
    base_w[sock_this] = 1.0
    # corner taper by normalized x along the eye
    tx = np.clip((X[:, 0] - x0) / (x1 - x0), 0, 1)
    taper = np.sin(np.pi * np.clip(tx, 0, 1)) ** float(os.environ.get("TAPER_EXP", 0.35))
    taper[(X[:, 0] < x0 - 0.01) | (X[:, 0] > x1 + 0.01)] = 0
    # closure line
    gx = np.linspace(x0, x1, 41)
    ua_g, la_g = np.interp(gx, ux, ua), np.interp(gx, lx, la)
    close_g = la_g + CLOSE_K * (ua_g - la_g)
    bones = []
    for part, N, idxmask, fall in (("T", N_UP, side_up, FALL_UP), ("B", N_LO, ~side_up, FALL_LO)):
        centers = np.linspace(0, 1, N + 2)[1:-1]
        width = 1.0 / (N + 1)
        hats = [np.clip(1 - np.abs(tx - cc) / width, 0, 1) for cc in centers]
        hs = np.sum(hats, axis=0); hs[hs == 0] = 1
        for k, (cc, hat) in enumerate(zip(centers, hats)):
            bn = f"lid.{part}.{side}.{k}"
            wk = base_w * taper * idxmask * (hat / hs)
            # close angle at this column
            xk = x0 + cc * (x1 - x0)
            if part == "T":
                ang = float(np.interp(xk, gx, close_g - OVERLAP - ua_g))
            else:
                ang = float(np.interp(xk, gx, close_g + OVERLAP - la_g))
            bones.append(dict(name=bn, ang=ang, x=float(xk)))
            weights[bn] = wk
        rep[f"{side}_{part}_angles_deg"] = [round(math.degrees(b["ang"]), 1) for b in bones if b["name"].startswith(f"lid.{part}")]
    EYES[side] = dict(c=c, bones=bones)
    all_bones += bones


def skin(amount):
    """LBS of the lid bones at `amount` of their close angle (bones of both eyes)."""
    out = X.copy()
    total_w = np.zeros(n); acc = np.zeros_like(X)
    for side, E in EYES.items():
        for b in E["bones"]:
            wk = weights[b["name"]]
            if not wk.any(): continue
            P = rot_x(X, E["c"], -b["ang"] * amount)
            acc += wk[:, None] * P; total_w += wk
    m = total_w > 0
    out[m] = acc[m] / total_w[m, None] * np.minimum(total_w[m], 1)[:, None] + X[m] * (1 - np.minimum(total_w[m], 1))[:, None]
    return out


def skin_side(amount, side):
    keep = {k: v for k, v in EYES.items() if k == side}
    global EYES_BAK
    out = X.copy(); total_w = np.zeros(n); acc = np.zeros_like(X)
    E = EYES[side]
    for b in E["bones"]:
        wk = weights[b["name"]]
        P = rot_x(X, E["c"], -b["ang"] * amount)
        acc += wk[:, None] * P; total_w += wk
    m = total_w > 0
    tw = np.minimum(total_w[m], 1)
    out[m] = acc[m] / total_w[m, None] * tw[:, None] + X[m] * (1 - tw)[:, None]
    # lid thickness: moving outer-lid skin must stay outside the eyeball (margin starts on the sphere)
    R = F[f"eye_{side}"]["radius"] + float(os.environ.get("LID_GAP", 0.0025))
    c = E["c"]
    d = out - c; r = np.linalg.norm(d, axis=1)
    lift = np.clip(total_w * 3, 0, 1) * (1 - smoothstep_np(0.0, 0.15, -amount + 0.15)) * (~sock_mask)
    target = np.maximum(r, R)
    rn = r + (target - r) * lift
    out = c + d / np.maximum(r, 1e-9)[:, None] * rn[:, None]
    # smooth the moving lid skin (unfolds compressed rings into an even dome), then keep it off the eyeball
    sw = np.clip(total_w * 2, 0, 1) * (~sock_mask) * amount
    for _ in range(int(os.environ.get("LID_SMOOTH", 25))):
        avg = np.array([out[nb].mean(0) if nb else out[i] for i, nb in enumerate(nbrs)])
        out = out + (avg - out) * (0.5 * sw)[:, None]
        d = out - c; r = np.linalg.norm(d, axis=1)
        push = (sw > 0) & (r < R)
        out[push] = c + d[push] / r[push, None] * R
    return out


def smoothstep_np(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


sock_mask = np.array([i in sock for i in range(n)])
# replace the DT blink keys with arc-correct baked lid-rig keys
kb = me.shape_keys.key_blocks
for side, L in (("L", "Left"), ("R", "Right")):
    for suf, amt in (("_25", 0.25), ("_50", 0.5), ("_75", 0.75), ("", 1.0)):
        name = f"eyeBlink{L}{suf}"
        k = kb.get(name) or w.shape_key_add(name=name, from_mix=False)
        k.data.foreach_set("co", skin_side(amt, side).ravel())
# store weights as vertex groups and bone pivots for the game rig
for bn, wk in weights.items():
    g = w.vertex_groups.get(bn) or w.vertex_groups.new(name=bn)
    idx = np.where(wk > 1e-4)[0]
    for i in idx:
        g.add([int(i)], float(wk[i]), 'REPLACE')
w["lid_bones"] = json.dumps({side: [dict(b, center=list(E["c"])) for b in E["bones"]] for side, E in EYES.items()})

# materials for hidden interior regions
def mat(name, rgb, rough):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = 0.0
    return m
if not me.materials or me.materials[0] is None or me.materials[0].name != "M_FaceSkin" and "basecolor" not in str([n.name for n in (me.materials[0].node_tree.nodes if me.materials[0] and me.materials[0].node_tree else [])]):
    me.materials.clear(); me.materials.append(mat("M_FaceSkin", (0.8, 0.62, 0.52), 0.6))
me.materials.append(mat("M_LidInner", (0.55, 0.30, 0.24), 0.5))
me.materials.append(mat("M_MouthInside", (0.25, 0.05, 0.05), 0.4))
for p in me.polygons:
    vs = p.vertices
    if all(v in sock for v in vs): p.material_index = 1
    elif all(v in bag for v in vs): p.material_index = 2
rep["bones"] = len(all_bones)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(rep, open(REP, "w"), indent=1)
print("LIDS", json.dumps(rep))
