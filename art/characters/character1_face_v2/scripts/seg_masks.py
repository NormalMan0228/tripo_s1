"""Part-colour masks for Tripo Segmentation v2 ref_image experiments.

Labels the faces of the head (Body + separate parts) by geometric rules, then renders a flat, un-antialiased
front orthographic mask with the same framing as the generation references (ortho 1.08, centre z 0.5, 1024 px).
Variants: full (lids/lips/mouth split) and coarse (face / eyes / ears / mouth parts / neck).
Usage: blender --background <head.blend> --python seg_masks.py -- <out_dir> <prefix>
Writes <prefix>_mask_full.png, <prefix>_mask_coarse.png, <prefix>_labels.json and a colour legend.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
OUT, PRE = os.path.abspath(a[0]), a[1]
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.data.transform(o.matrix_basis); o.matrix_basis = o.matrix_basis.__class__()
PAL = {  # label -> RGB 0..1 (well separated hues)
    "skin": (0.20, 0.35, 1.00), "scalp": (0.20, 0.35, 1.00), "neck": (0.0, 0.85, 0.85),
    "ear_L": (1.0, 0.6, 0.0), "ear_R": (0.85, 0.45, 0.0),
    "eye_L": (1.0, 1.0, 0.0), "eye_R": (0.85, 0.85, 0.0),
    "lid_up_L": (0.0, 0.8, 0.0), "lid_up_R": (0.0, 0.6, 0.0), "lid_lo_L": (0.55, 1.0, 0.55), "lid_lo_R": (0.4, 0.8, 0.4),
    "lips": (1.0, 0.0, 0.9), "mouth_in": (0.5, 0.0, 0.2), "teeth_up": (1.0, 1.0, 1.0), "teeth_lo": (0.75, 0.75, 0.75),
    "tongue": (1.0, 0.0, 0.0), "gum_lo": (0.6, 0.2, 0.0),
    # rig-region variant
    "forehead": (0.55, 0.3, 1.0), "brow_L": (0.0, 0.45, 0.25), "brow_R": (0.0, 0.3, 0.45), "nose": (1.0, 0.45, 0.6),
    "cheek_L": (0.3, 0.75, 1.0), "cheek_R": (0.6, 0.9, 1.0), "lip_up": (1.0, 0.0, 0.9), "lip_lo": (0.7, 0.0, 1.0),
    "philtrum": (0.95, 0.75, 0.5), "chin": (0.5, 0.5, 0.0), "jaw_L": (0.2, 0.2, 0.6), "jaw_R": (0.35, 0.35, 0.75)}
COARSE = {"lid_up_L": "skin", "lid_up_R": "skin", "lid_lo_L": "skin", "lid_lo_R": "skin", "lips": "skin",
          "mouth_in": "mouth_in", "gum_lo": "mouth_in", "teeth_lo": "teeth_up", "eye_R": "eye_L", "ear_R": "ear_L",
          "lid_dummy": "skin"}
body = bpy.data.objects["Body"]
co = np.array([v.co[:] for v in body.data.vertices])
eyes = {}
for s in ("L", "R"):
    e = bpy.data.objects[f"Eye.{s}"]; P = np.array([v.co[:] for v in e.data.vertices])
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1); sol = np.linalg.lstsq(A, b, rcond=None)[0]
    c = sol[:3]; eyes[s] = (c, float(np.sqrt(sol[3] + c @ c)))
# mouth opening contour from front rays (deep hits)
T = BVHTree.FromPolygons([tuple(p) for p in co], [tuple(p.vertices) for p in body.data.polygons])
XS = np.arange(-0.13, 0.1301, 0.002); ZS = np.arange(0.30, 0.52, 0.002)
D = np.full((len(ZS), len(XS)), np.nan)
for i, z in enumerate(ZS):
    for j, x in enumerate(XS):
        h = T.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)), 5)
        if h[0] is not None: D[i, j] = h[0].y
lip_front = np.nanmin(D[(ZS > 0.36) & (ZS < 0.47)][:, np.abs(XS) < 0.02])
deep = ((D > -0.18) | np.isnan(D)) & (np.abs(XS)[None] < 0.11) & (ZS[:, None] < 0.49)
# keep only the deep region connected to the mouth centre (rays under the chin are also "deep")
j0 = int(np.argmin(np.abs(XS))); comp = np.zeros_like(deep)
st = [(i, j0) for i in range(len(ZS)) if deep[i, j0] and 0.36 < ZS[i] < 0.48]
for ij in st: comp[ij] = True
while st:
    i, j = st.pop()
    for a_, b_ in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
        if 0 <= a_ < len(ZS) and 0 <= b_ < len(XS) and deep[a_, b_] and not comp[a_, b_] and ZS[a_] > 0.335:
            comp[a_, b_] = True; st.append((a_, b_))
open_pts = np.array([(XS[j], ZS[i]) for i in range(len(ZS)) for j in range(len(XS)) if comp[i, j]]).reshape(-1, 2)
closed_mouth = len(open_pts) < 20
if closed_mouth:   # closed lips: use the depth valley line as the "opening"
    open_pts = np.array([(XS[j], ZS[i]) for j in range(len(XS)) if abs(XS[j]) < 0.09
                         for i in [int(np.nanargmax(np.where((ZS > 0.425) & (ZS < 0.46), D[:, j], -9)))]])
LINE = open_pts[np.argsort(open_pts[:, 0])] if closed_mouth else None
if closed_mouth:   # robust smooth lip line: symmetric quadratic fit on the inner 2/3, z = a + b x^2
    inner = np.abs(LINE[:, 0]) < 0.06
    cf = np.polyfit(LINE[inner, 0] ** 2, LINE[inner, 1], 1)
    LINE = np.c_[LINE[:, 0], np.polyval(cf, LINE[:, 0] ** 2)]
LIP_C = float(np.abs(open_pts[:, 0]).max()) + 0.008 if closed_mouth else 0.0
if closed_mouth: print("LINE", np.round(LINE[::5], 3).tolist())
def dist_to_open(p):
    d = np.sqrt((open_pts[:, 0] - p[0]) ** 2 + (open_pts[:, 1] - p[2]) ** 2)
    return d.min()
lab_v = []
for p in co:
    lab = "skin"
    if p[2] > 0.80: lab = "scalp"
    if p[2] < 0.29: lab = "neck"
    if abs(p[0]) > 0.245 and 0.46 < p[2] < 0.70 and p[1] > -0.09: lab = "ear_L" if p[0] > 0 else "ear_R"
    for s, (c, R) in eyes.items():
        d = p - c; r = np.linalg.norm(d)
        if r < R * 1.32 and d[1] < 0.2 * R:
            alpha = math.atan2(d[2], -d[1])
            lab = f"lid_up_{s}" if d[2] > -0.15 * R else f"lid_lo_{s}"
    if abs(p[0]) < 0.13 and 0.31 < p[2] < 0.53:
        dm = dist_to_open(p)
        h = T.ray_cast(Vector((p[0], -2, p[2])), Vector((0, 1, 0)), 5)
        depth = (p[1] - h[0].y) if h[0] is not None else 0.0     # how far behind the visible surface
        if closed_mouth:     # lens-shaped lip band around the lip line, upper 22 mm / lower 32 mm at the centre
            t = abs(p[0]) / LIP_C
            if t < 1:
                zl = float(np.interp(p[0], LINE[:, 0], LINE[:, 1])); k = math.sqrt(1 - t * t)
                if zl - 0.032 * k < p[2] < zl + 0.022 * k:
                    lab = "lips" if depth < 0.01 else "mouth_in"
                elif depth > 0.01 and p[1] > lip_front + 0.01 and abs(p[2] - zl) < 0.05:
                    lab = "mouth_in"
        else:
            if (depth > 0.003 or dm < 0.004) and dm < 0.03:
                if p[1] > lip_front + 0.01: lab = "mouth_in"
            elif dm < 0.016 and depth <= 0.003 and abs(p[0]) < np.abs(open_pts[:, 0]).max() + 0.006: lab = "lips"
    lab_v.append(lab)
lab_v = np.array(lab_v, dtype=object)
RIG = "--rig" in sys.argv
if RIG:
    ec = {k: v[0] for k, v in eyes.items()}; ER = eyes["L"][1]
    zl0 = float(np.interp(0.0, LINE[:, 0], LINE[:, 1])) if closed_mouth else float(open_pts[:, 1].mean())
    for i, p in enumerate(co):
        l = lab_v[i]
        if l not in ("skin", "lips"): continue
        x, y, z = p; ax = abs(x); side = "L" if x > 0 else "R"
        if y > -0.05: continue                                      # back of head stays skin/scalp
        if l == "lips":
            lab_v[i] = "lip_up" if z > (float(np.interp(x, LINE[:, 0], LINE[:, 1])) if closed_mouth else zl0) else "lip_lo"; continue
        c = ec[side]
        if abs(x - c[0]) < ER * 1.7 and c[2] + ER * 1.0 < z < c[2] + ER * 2.1: lab_v[i] = f"brow_{side}"
        elif z > c[2] + ER * 1.0 and z <= 0.80: lab_v[i] = "forehead"
        elif ax < 0.05 - 0.15 * max(0.0, z - 0.52) and 0.47 < z < 0.62 and y < -0.24: lab_v[i] = "nose"
        elif ax < 0.075 and zl0 + 0.02 < z <= 0.49: lab_v[i] = "philtrum"
        elif ax < 0.07 and z < zl0 - 0.035 and z > 0.29: lab_v[i] = "chin"
        elif z < zl0 - 0.0 and z > 0.29: lab_v[i] = f"jaw_{side}"
        elif 0.40 <= z <= c[2] + ER * 1.0: lab_v[i] = f"cheek_{side}"
# face labels by majority, smoothing 2 passes
bm = bmesh.new(); bm.from_mesh(body.data); bm.faces.ensure_lookup_table()
flab = []
for f in bm.faces:
    ls = [lab_v[v.index] for v in f.verts]; flab.append(max(set(ls), key=ls.count))
for _ in range(2):
    new = []
    for f in bm.faces:
        nb = [flab[g.index] for e in f.edges for g in e.link_faces if g is not f] + [flab[f.index]] * 2
        new.append(max(set(nb), key=nb.count))
    flab = new
bm.free()
OBJLAB = {"Eye.L": "eye_L", "Eye.R": "eye_R", "TeethUpper": "teeth_up", "TeethLower": "teeth_lo", "Tongue": "tongue", "MouthLower": "gum_lo"}
counts = {}
for l in flab: counts[l] = counts.get(l, 0) + 1


def render(mode):
    mats = {}
    def m(label):
        lab = COARSE.get(label, label) if mode == "coarse" else label
        if lab not in mats:
            mt = bpy.data.materials.new(f"seg_{mode}_{lab}"); mt.diffuse_color = (*PAL[lab], 1); mats[lab] = mt
        return mats[lab]
    me = body.data
    me.materials.clear()
    order = sorted(set(flab))
    for l in order: me.materials.append(m(l))
    idx = {l: i for i, l in enumerate(order)}
    for p, l in zip(me.polygons, flab): p.material_index = idx[l]
    for o in bpy.data.objects:
        if o.type == 'MESH' and o is not body:
            if o.name in OBJLAB:
                o.data.materials.clear(); o.data.materials.append(m(OBJLAB[o.name])); o.hide_render = False
            else:
                o.hide_render = True
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
    sc.display.render_aa = 'OFF'
    sc.view_settings.view_transform = 'Standard'
    if sc.world: sc.world.color = (0, 0, 0)
    sc.render.film_transparent = False
    sc.render.resolution_x = sc.render.resolution_y = 1024
    cam = bpy.data.objects.get("seg_cam")
    if cam is None:
        cd = bpy.data.cameras.new("seg_cam"); cd.type = 'ORTHO'; cd.ortho_scale = 1.08
        cam = bpy.data.objects.new("seg_cam", cd); sc.collection.objects.link(cam)
        cam.location = (0, -2.5, 0.5); cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, f"{PRE}_mask_{'rig' if RIG else mode}.png")
    bpy.ops.render.render(write_still=True)


if RIG:
    pass
render("full")
if not RIG: render("coarse")
# face centres + labels (Body and separate parts) for scoring segmentation outputs
FC, FL = [], []
for pg, l in zip(body.data.polygons, flab): FC.append(list(pg.center)); FL.append(l)
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name in OBJLAB:
        for pg in o.data.polygons: FC.append(list(pg.center)); FL.append(OBJLAB[o.name])
np.savez_compressed(os.path.join(OUT, f"{PRE}_facelabels.npz"), c=np.array(FC, np.float32), l=np.array(FL))
json.dump({"lip_front": float(lip_front), "n_open_pts": len(open_pts), "face_label_counts": counts, "closed_mouth": bool(closed_mouth), "palette": PAL, "coarse_map": COARSE}, open(os.path.join(OUT, f"{PRE}_labels.json"), "w"), indent=1)
print("MASKS", PRE, json.dumps(counts))
