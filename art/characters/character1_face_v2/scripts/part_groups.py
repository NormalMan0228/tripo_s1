"""Shape-stage part separation on the rigged face: PART_* vertex groups on WrapHead + an ID-colour review.
Parts: Scalp, Forehead/Brow, Nose, Cheeks, Lips, Chin/Jaw, Ears, LidUpper.L/R, LidLower.L/R, LashFlap.L/R,
EyeSocket, MouthBag, Neck; separate objects: Eye.L/R, Teeth, Tongue, Brow.L/R.
Usage: blender --background face_parts.blend --python part_groups.py -- <out.blend>"""
import bpy, sys, os, json
import numpy as np
out = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
w = bpy.data.objects["WrapHead"]; me = w.data; n = len(me.vertices)
C = json.loads(w["vertex_classes"])
G = {g.index: g.name for g in w.vertex_groups}
W = {}
for v in me.vertices:
    for g in v.groups:
        W.setdefault(G[g.group], np.zeros(n))[v.index] = g.weight
def grp(prefixes):
    acc = np.zeros(n)
    for k, a in W.items():
        if any(k.startswith(p) for p in prefixes): acc = np.maximum(acc, a)
    return acc
X = np.array([v.co[:] for v in me.vertices])
flap = np.zeros(n, bool)
fm = next((i for i, m in enumerate(me.materials) if m.name == "M_LashFlap"), None)
for p in me.polygons:
    if p.material_index == fm:
        for v in p.vertices: flap[v] = True
orig_n = n - int(flap.sum())
score = {
    "Scalp": W.get("scalp", np.zeros(n)), "Ears": W.get("ears", np.zeros(n)), "Lips": W.get("lips", np.zeros(n)),
    "Nose": grp(["DEF-nose"]), "Brow": grp(["DEF-brow", "DEF-forehead"]), "Cheeks": grp(["DEF-cheek"]),
    "Chin": grp(["DEF-chin", "DEF-jaw"]), "Neck": grp(["DEF-neck", "DEF-spine", "DEF-shoulder", "DEF-breast"]),
}
for s in ("L", "R"):
    score[f"LidUpper.{s}"] = grp([f"lid.T.{s}."]) * 1.6
    score[f"LidLower.{s}"] = grp([f"lid.B.{s}."]) * 1.6
names = list(score)
S = np.stack([score[k] for k in names], 1)
lab = np.where(S.max(1) > 0.05, S.argmax(1), -1)
part = {}
for i in range(n):
    part[i] = names[lab[i]] if lab[i] >= 0 else "Face"
# smooth region borders: majority vote over the 1-ring (soft parts only), a few passes
nbrs = [[] for _ in range(n)]
for e in me.edges:
    a_, b_ = e.vertices; nbrs[a_].append(b_); nbrs[b_].append(a_)
SOFT = {"Scalp", "Brow", "Nose", "Cheeks", "Chin", "Neck", "Face"}
for _ in range(int(os.environ.get("PART_SMOOTH", 4))):
    newp = dict(part)
    for i in range(n):
        if part[i] not in SOFT: continue
        labs = [part[j] for j in nbrs[i]] + [part[i]]
        labs = [l for l in labs if l in SOFT]
        if labs: newp[i] = max(set(labs), key=labs.count)
    part = newp
for i in C["socket"]: part[i] = "EyeSocket"
for i in C["bag"]: part[i] = "MouthBag"
for i in np.where(flap)[0]: part[int(i)] = "LashFlap." + ("L" if X[i, 0] > 0 else "R")
for g in [g for g in w.vertex_groups if g.name.startswith("PART_")]: w.vertex_groups.remove(g)
counts = {}
for nm in sorted(set(part.values())):
    g = w.vertex_groups.new(name="PART_" + nm)
    idx = [i for i, p in part.items() if p == nm]
    g.add(idx, 1.0, 'REPLACE'); counts[nm] = len(idx)
# ID colours (face corner colour attribute by polygon majority)
import colorsys, random
random.seed(4)
FIX = {"Scalp": (0.85, 0.75, 0.55), "Brow": (0.95, 0.55, 0.25), "Nose": (0.9, 0.3, 0.3), "Cheeks": (0.95, 0.6, 0.65),
       "Lips": (0.75, 0.15, 0.35), "Chin": (0.55, 0.75, 0.35), "Ears": (0.3, 0.7, 0.85), "Neck": (0.6, 0.6, 0.6),
       "Face": (0.9, 0.9, 0.9), "EyeSocket": (0.25, 0.25, 0.55), "MouthBag": (0.45, 0.1, 0.1),
       "LidUpper.L": (0.25, 0.45, 0.95), "LidUpper.R": (0.25, 0.45, 0.95), "LidLower.L": (0.55, 0.3, 0.9), "LidLower.R": (0.55, 0.3, 0.9)}
pal = {nm: FIX.get(nm, colorsys.hsv_to_rgb(k / len(counts), 0.55, 0.9)) for k, nm in enumerate(sorted(counts))}
pal["LashFlap.L"] = pal["LashFlap.R"] = (0.05, 0.05, 0.05)
ca = me.color_attributes.get("part_id") or me.color_attributes.new("part_id", 'FLOAT_COLOR', 'CORNER')
for p in me.polygons:
    vs = list(p.vertices); labs = [part[v] for v in vs]; nm = max(set(labs), key=labs.count)
    for li in p.loop_indices: ca.data[li].color = (*pal[nm], 1)
me.color_attributes.active_color = ca
w["parts"] = json.dumps(counts)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("PARTS", json.dumps(counts))
