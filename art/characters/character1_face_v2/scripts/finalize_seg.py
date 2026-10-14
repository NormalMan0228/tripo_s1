"""Final face part labels on the closed quad head from a mask-guided Tripo segmentation (transferred by transfer_seg.py).

1. name every Tripo part by the majority of our geometric labels (L/R collapsed; lips split upper/lower per part by lip line)
2. paired regions split L/R at the midline
3. fragment merge: label components smaller than MINF faces (or < 10 % of the label's main component) join the
   neighbouring label they share most edges with
4. exact symmetry: -X faces copy the mirrored +X label (L<->R swapped)
5. chin below the jaw edge -> neck; soft-region boundaries smoothed (indicators diffused SMOOTH_IT times, argmax over soft
   labels) while crease-based parts (lids, lips, ears, mouth interior) stay as Tripo cut them; then 3+4 again
6. output: material slot per label, int face attribute 'part', hard vertex groups P_<label>, soft normalised W_<label>
   (crease parts sharp, soft regions broadly blended)
Usage: blender --background open/closed.blend --python finalize_seg.py -- <transfer.blend> <labels.npz> <out.blend>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index("--") + 1:]
XFER, LAB, OUT = [os.path.abspath(x) for x in a[:3]]
MINF = int(os.environ.get("MINF", 40)); SMOOTH_IT = int(os.environ.get("SMOOTH_IT", 14)); CHIN_MIN_Z = float(os.environ.get("CHIN_MIN_Z", 0.325)); SOFT_IT = int(os.environ.get("SOFT_IT", 40))
body = bpy.data.objects["Body"]; me = body.data
nF = len(me.polygons)
with bpy.data.libraries.load(XFER) as (df, dt): dt.meshes = ["Body"]
xm = dt.meshes[0]
assert len(xm.polygons) == nF
pid = np.array([int(xm.materials[p.material_index].name[4:7]) for p in xm.polygons])
gl = np.load(LAB)["l"][:nF]
FC = np.array([p.center[:] for p in me.polygons]); FA = np.array([p.area for p in me.polygons])
FV = [tuple(p.vertices) for p in me.polygons]
rep = {}

COLL = {"brow_L": "brow", "brow_R": "brow", "cheek_L": "cheek", "cheek_R": "cheek", "jaw_L": "jaw", "jaw_R": "jaw",
        "lid_up_L": "lid_up", "lid_up_R": "lid_up", "lid_lo_L": "lid_lo", "lid_lo_R": "lid_lo", "ear_L": "ear", "ear_R": "ear",
        "lip_up": "lips", "lip_lo": "lips", "philtrum": "nose", "forehead": "scalp", "skin": "skin"}
PAIRED = {"brow", "cheek", "jaw", "lid_up", "lid_lo", "ear"}
# lip line (closed mouth): z of the deepest front valley near x=0, from the labels' lip faces
names = {}
for p in np.unique(pid):
    m = pid == p
    g = np.array([COLL.get(x, x) for x in gl[m]])
    u, c = np.unique(g, return_counts=True); nm = str(u[np.argmax(c)])
    cz = float(np.average(FC[m, 2], weights=FA[m])); cy = float(np.average(FC[m, 1], weights=FA[m]))
    if nm == "skin" and cz < 0.5 and cy < -0.05: nm = "jaw"          # Tripo's lower-face side region
    if nm == "lips":
        up = sum(1 for x in gl[m] if x == "lip_up"); lo = sum(1 for x in gl[m] if x == "lip_lo")
        nm = "lip_up" if up >= lo else "lip_lo"
    names[int(p)] = nm
lab = np.array([names[int(p)] for p in pid], dtype=object)
rep["part_names"] = {str(k): v for k, v in sorted(names.items())}


def split_lr(lab):
    out = lab.copy()
    for i, l in enumerate(lab):
        base = l[:-2] if l[-2:] in ("_L", "_R") else l
        if base in PAIRED: out[i] = f"{base}_{'L' if FC[i, 0] > 0 else 'R'}"
    return out


# face adjacency via edges
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
adj = [[g.index for e in f.edges for g in e.link_faces if g.index != f.index] for f in bm.faces]
bm.free()


def components(lab):
    comp = -np.ones(nF, int); comps = []
    for s in range(nF):
        if comp[s] >= 0: continue
        st = [s]; comp[s] = len(comps); mem = []
        while st:
            f = st.pop(); mem.append(f)
            for g in adj[f]:
                if comp[g] < 0 and lab[g] == lab[s]: comp[g] = len(comps); st.append(g)
        comps.append(mem)
    return comps


def merge_fragments(lab):
    for _ in range(20):
        comps = components(lab); changed = 0
        biggest = {}
        for c in comps: biggest[lab[c[0]]] = max(biggest.get(lab[c[0]], 0), len(c))
        for c in sorted(comps, key=len):
            l = lab[c[0]]
            if len(c) >= MINF and len(c) >= 0.1 * biggest[l]: continue
            if len(c) == biggest[l] and len(c) >= 8: continue          # a small but whole label stays
            cs = set(c); cnt = {}
            for f in c:
                for g in adj[f]:
                    if g not in cs: cnt[lab[g]] = cnt.get(lab[g], 0) + 1
            if not cnt: continue
            nl = max(cnt, key=cnt.get)
            if nl != l:
                for f in c: lab[f] = nl
                changed += 1
        if not changed: break
    return lab


kd = KDTree(nF)
for i, c in enumerate(FC): kd.insert(c, i)
kd.balance()
mir = np.empty(nF, int); md = np.empty(nF)
for i, c in enumerate(FC):
    _, j, d = kd.find((-c[0], c[1], c[2])); mir[i] = j; md[i] = d
rep["mirror_face_dist_max_mm"] = round(float(md.max()) * 1000, 4)


def swap(l):
    return l[:-2] + ("_R" if l.endswith("_L") else "_L") if l[-2:] in ("_L", "_R") else l


def symmetrize(lab):
    out = lab.copy()
    for i in range(nF):
        if FC[i, 0] < -1e-6: out[i] = swap(lab[mir[i]])
    return out


def vert_indicators(lab, labels):
    nV = len(me.vertices); H = np.zeros((nV, len(labels))); deg = np.zeros(nV)
    li = {l: k for k, l in enumerate(labels)}
    for f, vs in enumerate(FV):
        for v in vs: H[v, li[lab[f]]] += 1; deg[v] += 1
    return H / np.maximum(deg, 1)[:, None]


E = np.array([e.vertices[:] for e in me.edges])


def diffuse(H, it):
    nV = len(H); dg = np.zeros(nV); np.add.at(dg, E[:, 0], 1); np.add.at(dg, E[:, 1], 1)
    for _ in range(it):
        acc = np.zeros_like(H); np.add.at(acc, E[:, 0], H[E[:, 1]]); np.add.at(acc, E[:, 1], H[E[:, 0]])
        H = 0.5 * H + 0.5 * acc / np.maximum(dg, 1)[:, None]
    return H


def boundary_len(lab):
    bm = bmesh.new(); bm.from_mesh(me); s = 0.0
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) == 2 and lab[lf[0].index] != lab[lf[1].index]: s += e.calc_length()
    bm.free(); return s


lab = split_lr(lab)
rep["boundary_len_raw_m"] = round(boundary_len(lab), 3)
rep["components_raw"] = len(components(lab))
lab = merge_fragments(lab); lab = symmetrize(lab)
# chin below the front jaw edge is neck (Tripo's chin part ran down the throat)
lab[(lab == "chin") & (FC[:, 2] < CHIN_MIN_Z)] = "neck"
# crease-based parts (Tripo boundaries follow real geometry) stay fixed; soft region boundaries are smoothed strongly
HARD = lambda l: l.startswith(("lid_", "lip_", "ear_")) or l == "mouth_in"
labels = sorted(set(lab)); soft = np.array([not HARD(l) for l in labels])
hard_face = np.array([HARD(l) for l in lab])
H = diffuse(vert_indicators(lab, labels), SMOOTH_IT)
for f, vs in enumerate(FV):
    if hard_face[f]: continue
    sc_ = H[list(vs)].mean(0) * soft
    lab[f] = labels[int(np.argmax(sc_))]
lab = merge_fragments(lab); lab = symmetrize(lab)
labels = sorted(set(lab))
rep["boundary_len_final_m"] = round(boundary_len(lab), 3)
comps = components(lab)
rep["components_final"] = len(comps)
rep["components_per_label"] = {l: sum(1 for c in comps if lab[c[0]] == l) for l in labels}
rep["faces_per_label"] = {l: int((lab == l).sum()) for l in labels}
rep["symmetry_face_agreement"] = float(np.mean([lab[i] == swap(lab[mir[i]]) for i in range(nF)]))

PAL = {"scalp": (0.85, 0.72, 0.62), "skin": (0.95, 0.80, 0.70), "neck": (0.55, 0.75, 0.85), "nose": (0.95, 0.55, 0.55),
       "brow_L": (0.55, 0.40, 0.25), "brow_R": (0.45, 0.32, 0.20), "cheek_L": (0.95, 0.65, 0.45), "cheek_R": (0.90, 0.58, 0.40),
       "jaw_L": (0.70, 0.60, 0.85), "jaw_R": (0.62, 0.52, 0.78), "chin": (0.80, 0.45, 0.75), "lip_up": (0.85, 0.15, 0.30),
       "lip_lo": (0.95, 0.35, 0.45), "mouth_in": (0.45, 0.08, 0.12), "lid_up_L": (0.20, 0.70, 0.30), "lid_up_R": (0.15, 0.58, 0.25),
       "lid_lo_L": (0.55, 0.85, 0.45), "lid_lo_R": (0.45, 0.75, 0.38), "ear_L": (0.95, 0.75, 0.20), "ear_R": (0.85, 0.65, 0.15)}
me.materials.clear()
for l in labels:
    m = bpy.data.materials.get(f"P_{l}") or bpy.data.materials.new(f"P_{l}")
    m.diffuse_color = (*PAL.get(l, (0.5, 0.5, 0.5)), 1); me.materials.append(m)
li = {l: k for k, l in enumerate(labels)}
me.polygons.foreach_set("material_index", [li[l] for l in lab])
attr = me.attributes.get("part") or me.attributes.new("part", 'INT', 'FACE')
attr.data.foreach_set("value", [li[l] for l in lab])
body["part_labels"] = json.dumps(labels)
for vg in [g for g in body.vertex_groups if g.name.startswith(("P_", "W_", "SEG_"))]: body.vertex_groups.remove(vg)
for l in labels:
    vg = body.vertex_groups.new(name=f"P_{l}")
    vg.add(sorted({v for f, vs in enumerate(FV) if lab[f] == l for v in vs}), 1.0, 'REPLACE')
# soft weights: crease parts keep a sharp falloff (2 its), soft regions blend widely (SOFT_IT its) inside the remaining mass
H0 = vert_indicators(lab, labels); hard = np.array([HARD(l) for l in labels])
Wh = diffuse(H0, 2) * hard; Ws = diffuse(H0, SOFT_IT) * ~hard
rest = np.clip(1 - Wh.sum(1, keepdims=True), 0, 1)
W = Wh + rest * Ws / np.maximum(Ws.sum(1, keepdims=True), 1e-9)
W = W / np.maximum(W.sum(1, keepdims=True), 1e-9)
for k, l in enumerate(labels):
    vg = body.vertex_groups.new(name=f"W_{l}")
    for v in np.where(W[:, k] > 0.01)[0]: vg.add([int(v)], float(W[v, k]), 'REPLACE')
for nm, col in (("Eye.L", (0.95, 0.95, 0.95)), ("Eye.R", (0.95, 0.95, 0.95)), ("TeethUpper", (1, 1, 0.9)), ("TeethLower", (0.9, 0.9, 0.8)),
                ("Tongue", (0.9, 0.3, 0.35)), ("MouthLower", (0.6, 0.2, 0.25))):
    o = bpy.data.objects.get(nm)
    if o:
        m = bpy.data.materials.get(f"O_{nm}") or bpy.data.materials.new(f"O_{nm}"); m.diffuse_color = (*col, 1)
        o.data.materials.clear(); o.data.materials.append(m)
bpy.context.scene.display.shading.color_type = 'MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("FINAL", json.dumps({k: rep[k] for k in rep if k != "part_names"}))
