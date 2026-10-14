"""Find the template's eye-opening (lid margin) loops and lip-seam loop as ordered vertex rings.

Eye: eyeball sphere fitted to the helper-l/r-eye vertices of the original template. Lid margin = the skin
edge loop whose vertices are nearest the eyeball sphere while facing forward; traced as the boundary of the
region of skin faces lying on/inside the sphere's front cap.
Mouth: faces behind the lip line form the mouth bag; the seam loop is the boundary between front-facing lip
faces and the bag (traced the same way using a depth threshold behind the lips).
Writes template_features.json (indices refer to TemplateHead in template_head.blend).
Usage: blender --background template_head.blend --python template_features.py -- <mpfb_template.blend> <out.json>
"""
import bpy, bmesh, sys, os, json
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
src_path, out = a[0], os.path.abspath(a[1])
ob = bpy.data.objects["TemplateHead"]
co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])

with bpy.data.libraries.load(src_path, link=False) as (df, dt):
    dt.objects = ["Template_Face_Body"]
src = dt.objects[0]
gidx = {g.name: g.index for g in src.vertex_groups}
sco = np.array([src.matrix_world @ v.co for v in src.data.vertices])


def group_pts(name):
    gi = gidx[name]
    return sco[[v.index for v in src.data.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)]]


def sphere_fit(P):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = s[:3]
    return c, float(np.sqrt(s[3] + c @ c))


bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
mw = ob.matrix_world


def boundary_ring(face_mask):
    """Ordered vertex ring on the boundary of a face set (largest loop)."""
    adj = {}
    for e in bm.edges:
        fl = [f.index for f in e.link_faces]
        ins = sum(face_mask[i] for i in fl)
        if len(fl) == 2 and ins == 1:
            u, w = e.verts[0].index, e.verts[1].index
            adj.setdefault(u, []).append(w); adj.setdefault(w, []).append(u)
    seen, loops = set(), []
    for s in adj:
        if s in seen: continue
        order = [s]; seen.add(s); prev, cur = None, s
        while True:
            nxt = [w for w in adj[cur] if w != prev and w not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; order.append(cur); seen.add(cur)
        loops.append(order)
    return max(loops, key=len) if loops else []


fc = np.array([np.mean([co[v.index] for v in f.verts], axis=0) for f in bm.faces])
bm.normal_update()
fold = {}
for e in bm.edges:
    if len(e.link_faces) == 2:
        n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
        fold[e.index] = float(np.degrees(n1.angle(n2, 0.0)))


def fold_ring(center, radius_xz, thr, plane_axes=(0, 2)):
    """Largest closed cycle of sharp-fold edges near `center` (distance measured in the front plane)."""
    c2 = np.array(center)[list(plane_axes)]
    edges = []
    for e in bm.edges:
        if fold.get(e.index, 0) < thr:
            continue
        m = (co[e.verts[0].index] + co[e.verts[1].index]) / 2
        if np.linalg.norm(m[list(plane_axes)] - c2) < radius_xz and m[1] < center[1] + radius_xz:
            edges.append((e.verts[0].index, e.verts[1].index))
    adj = {}
    for u, w in edges:
        adj.setdefault(u, []).append(w); adj.setdefault(w, []).append(u)
    seen, best = set(), []
    for s0 in adj:
        if s0 in seen: continue
        comp, st = [], [s0]
        while st:
            x = st.pop()
            if x in seen: continue
            seen.add(x); comp.append(x); st += adj[x]
        if len(comp) > len(best): best = comp
    # order the ring by angle around its centroid in the front plane
    if not best: return []
    P = co[best][:, list(plane_axes)]; cc = P.mean(0)
    ang = np.arctan2(P[:, 1] - cc[1], P[:, 0] - cc[0])
    return [best[i] for i in np.argsort(ang)]


res = {}
for side, grp in (("L", "helper-l-eye"), ("R", "helper-r-eye")):
    c, r = sphere_fit(group_pts(grp))
    ring = fold_ring(c, r * 1.3, float(__import__("os").environ.get("EYE_THR", 50)))
    res[f"eye_{side}"] = dict(center=c.tolist(), radius=r, ring=ring, n=len(ring),
                              ring_centroid=co[ring].mean(0).tolist() if ring else None)
    print("eye", side, "center", np.round(c, 4), "r", round(r, 4), "ring", len(ring))
up = group_pts("helper-upper-teeth"); lo = group_pts("helper-lower-teeth")
lipz = float((up[:, 2].min() + lo[:, 2].max()) / 2)
mc = np.array([0.0, min(up[:, 1].min(), lo[:, 1].min()), lipz])
ring = fold_ring(mc, 0.035, float(__import__("os").environ.get("MOUTH_THR", 50)))
res["mouth"] = dict(ring=ring, n=len(ring), lip_z=lipz, ring_centroid=co[ring].mean(0).tolist() if ring else None)
print("mouth ring", len(ring), "lip z", round(lipz, 4))
res["nose_tip"] = int(np.argmin(np.where(np.abs(co[:, 0]) < 0.004, co[:, 1], 9)))
res["chin"] = int(np.argmin(np.where((np.abs(co[:, 0]) < 0.004) & (co[:, 2] < lipz - 0.03) & (co[:, 2] > lipz - 0.09), co[:, 1], 9)))
res["head_top"] = int(np.argmax(co[:, 2]))
res["head_back"] = int(np.argmax(np.where(co[:, 2] > lipz + 0.08, co[:, 1], -9)))
res["ear_L"] = int(np.argmax(np.where(co[:, 2] > lipz, co[:, 0], -9)))
res["ear_R"] = int(np.argmin(np.where(co[:, 2] > lipz, co[:, 0], 9)))
bm.free()
json.dump(res, open(out, "w"))
print("FEATURES", {k: (v if isinstance(v, int) else v.get("n")) for k, v in res.items()})
