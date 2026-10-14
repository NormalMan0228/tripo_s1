"""Eyelid modification: lashes grown out of the lid itself.

The upper (and lower) half of each lid-margin edge loop is extruded into a thin flap that is part of the face
mesh, so the lash line is physically attached to the lid and follows every lid deformation:
  row 0 = margin (shared vertices), row 1 = lash root ridge (slightly raised, gives the lid a thick rim),
  rows 2..N = lash flap curling outward / up (down for the lower lid).
The flap vertices are rebuilt for EVERY shape key from their parent margin vertex's local frame in that key,
and copy the parent's deform weights. Flap faces get their own material slot (LashFlap) for shape review now
and an alpha strand texture later. Upper rim thickness: RIDGE.
Usage: blender --background face_lids.blend --python lash_flap.py -- <out.blend> <report.json>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
OUT, REP = os.path.abspath(a[0]), os.path.abspath(a[1])
P = dict(up_len=float(os.environ.get("UP_LEN", 0.016)), lo_len=float(os.environ.get("LO_LEN", 0.007)),
         rows_up=int(os.environ.get("ROWS_UP", 4)), rows_lo=int(os.environ.get("ROWS_LO", 3)),
         ridge=float(os.environ.get("RIDGE", 0.0012)), curl=float(os.environ.get("CURL", 0.9)),
         lift=float(os.environ.get("LIFT", 0.55)))
w = bpy.data.objects["WrapHead"]; me = w.data
F = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), "target_features.json")))
C = json.loads(w["vertex_classes"]); sock = set(C["socket"])
key_names = [k.name for k in me.shape_keys.key_blocks]
rep = {"params": P}

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
shape = {nm: bm.verts.layers.shape[nm] for nm in key_names}
deform = bm.verts.layers.deform.verify()
n0 = len(bm.verts)
V0 = list(bm.verts)          # stable references to the original vertices

flap_mat = len(me.materials)
m = bpy.data.materials.new("M_LashFlap"); m.use_nodes = True
b = m.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (0.02, 0.015, 0.013, 1)
b.inputs["Roughness"].default_value = 0.6; me.materials.append(m)

new_faces_all = []
for side in ("L", "R"):
    c = Vector(F[f"eye_{side}"]["center"]); sx = 1 if side == "L" else -1
    margin = list(w[f"eye_margin_{side}"])
    co = {i: V0[i].co.copy() for i in margin}
    i_in = min(margin, key=lambda i: abs(co[i].x)); i_out = max(margin, key=lambda i: abs(co[i].x))
    k_in, k_out = margin.index(i_in), margin.index(i_out)
    order = margin[k_in:] + margin[:k_in]; ko = order.index(i_out)
    h1, h2 = order[:ko + 1], order[ko:] + [order[0]]
    upper, lower = (h1, h2) if np.mean([co[i].z for i in h1]) > np.mean([co[i].z for i in h2]) else (h2, h1)
    for part, chain, L, rows, up in (("up", upper, P["up_len"], P["rows_up"], True), ("lo", lower, P["lo_len"], P["rows_lo"], False)):
        if co[chain[0]].x * sx > co[chain[-1]].x * sx:
            chain = chain[::-1]                                         # inner -> outer
        # root on the visible lid rim: walk outward ring by ring from each margin vertex and take the most
        # forward (min y) vertex within RIM_STEPS steps; ring index median-smoothed along the lid
        if os.environ.get("ROOT", "rim") == "rim":
            mset = set(margin)
            paths = []
            for i in chain:
                path, cur, used = [i], i, set(mset)
                for _ in range(int(os.environ.get("RIM_STEPS", 6))):
                    cand = [e.other_vert(V0[cur]).index for e in V0[cur].link_edges]
                    cand = [q for q in cand if q not in used and q not in sock and q < n0]
                    if not cand: break
                    # continue roughly perpendicular to the margin: farthest from the margin centroid in the lid plane
                    cur = max(cand, key=lambda q: (V0[q].co - c).length - 0.3 * abs(V0[q].co.x - V0[i].co.x))
                    used.add(cur); path.append(cur)
                paths.append(path)
            ks = [int(np.argmin([V0[q].co.y for q in pth])) for pth in paths]
            ks = [int(np.median(ks[max(0, j - 2):j + 3])) for j in range(len(ks))]
            newchain = []
            for pth, k in zip(paths, ks):
                q = pth[min(k, len(pth) - 1)]
                if not newchain or newchain[-1] != q: newchain.append(q)
            rep.setdefault("rim_steps", {})[f"{side}_{part}"] = ks
            chain = newchain
        nch = len(chain)
        u = np.linspace(0, 1, nch)
        prof = (0.35 + 0.65 * np.sin(np.pi * np.clip(u * 0.92 + 0.04, 0, 1)) ** 0.7) * (0.6 + 0.4 * u)   # longer toward the outer side
        ramp_in = np.clip(u / 0.18, 0, 1); ramp_in = ramp_in * ramp_in * (3 - 2 * ramp_in)
        ramp_out = np.clip((1 - u) / 0.10, 0, 1); ramp_out = ramp_out * ramp_out * (3 - 2 * ramp_out)
        prof = prof * (0.12 + 0.88 * ramp_in) * (0.25 + 0.75 * ramp_out)
        # root row: coincident duplicates of the margin (manifold face mesh; follows the margin in every key)
        prev = []
        for i in chain:
            nv = bm.verts.new(V0[i].co.copy())
            for gi, wv in V0[i][deform].items(): nv[deform][gi] = wv
            prev.append(nv)
        root_row = prev
        rings = [prev]
        for r in range(1, rows + 1):
            ring = []
            for j, pv in enumerate(prev):
                nv = bm.verts.new(pv.co.copy())
                for gi, wv in V0[chain[j]][deform].items(): nv[deform][gi] = wv
                ring.append(nv)
            for j in range(nch - 1):
                q = (prev[j], prev[j + 1], ring[j + 1], ring[j])
                f = bm.faces.new(q if (sx > 0) != up else q[::-1])
                f.material_index = flap_mat; f.smooth = True; new_faces_all.append(f)
            rings.append(ring); prev = ring
        # per-key placement from each parent margin vertex's frame
        for nm in key_names:
            lay = shape[nm]
            # lower lashes fold away while the lid closes (closed eye reads as one lash line)
            amt = 0.0
            if nm.startswith("eyeBlink") and (("Left" in nm) == (side == "L")):
                amt = {"_25": 0.25, "_50": 0.5, "_75": 0.75}.get(nm[-3:], 1.0)
            Lscale = (1 - amt) ** 1.5 if not up else 1.0
            pts = [V0[i][lay].copy() for i in chain]
            for j in range(nch):
                p0 = pts[j]
                t = (pts[min(j + 1, nch - 1)] - pts[max(j - 1, 0)]).normalized()      # along the lid edge
                rdir = (p0 - c).normalized()                                          # out of the eyeball
                updir = t.cross(rdir).normalized()
                if (updir.z < 0) == up: updir = -updir                               # toward the brow (upper) / cheek (lower)
                out_x = Vector((sx, 0, 0)) * (0.25 * u[j])
                Lj = L * prof[j] * Lscale
                for r in range(1, rows + 1):
                    f = r / rows
                    if r == 1:
                        pos = p0 + rdir * P["ridge"] + updir * P["ridge"] * 0.8           # root ridge = thick lid rim
                    else:
                        g = (r - 1) / (rows - 1)
                        dirv = (rdir * (1 - P["lift"]) + updir * P["lift"] + out_x).normalized()
                        curl = updir * (P["curl"] * Lj * g * g * 0.35)
                        pos = p0 + rdir * P["ridge"] + updir * P["ridge"] * 0.8 + dirv * (Lj * g) + curl
                    rings[r][j][lay] = pos
                    if nm == key_names[0]:
                        rings[r][j].co = pos
                root_row[j][lay] = p0 + rdir * 0.0002
                if nm == key_names[0]: root_row[j].co = p0 + rdir * 0.0002
    rep[f"{side}"] = dict(upper=len(upper), lower=len(lower))

bm.to_mesh(me); bm.free()
me.update()
rep["new_verts"] = len(me.vertices) - n0
rep["flap_faces"] = len(new_faces_all)
w["lash_flap_params"] = json.dumps(P)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(rep, open(REP, "w"), indent=1)
print("FLAP", json.dumps(rep))
