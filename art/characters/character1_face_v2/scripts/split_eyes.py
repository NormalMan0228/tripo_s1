"""Cut the fused eyeballs out of the open-mouth P2 Body: iterative sphere fit per eye, faces lying on the sphere
(largest connected set) become Eye.L / Eye.R; the lid edge stays on the Body.
Usage: blender --background open/parts.blend --python split_eyes.py -- <out.blend>
"""
import bpy, bmesh, sys, os, json
import numpy as np
out = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
TOL = float(os.environ.get("EYE_TOL", 0.0025))
body = bpy.data.objects["Body"]; me = body.data
co = np.array([v.co[:] for v in me.vertices])
def fit(P):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = s[:3]; return c, float(np.sqrt(s[3] + c @ c))
rep = {}
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
eye_faces = {}
for side, sx in (("L", 1), ("R", -1)):
    c, r = np.array([sx * 0.115, -0.13, 0.626]), 0.086
    for it in range(12):
        d = np.linalg.norm(co - c, axis=1)
        sel = np.abs(d - r) < (0.012 if it < 4 else 0.004)
        sel &= (sx * co[:, 0] > 0.02)
        c, r = fit(co[sel])
    d = np.linalg.norm(co - c, axis=1)
    on = np.abs(d - r) < TOL
    cand = set(f.index for f in bm.faces if all(on[v.index] for v in f.verts))
    # largest connected set
    best, seen = [], set()
    for f0 in cand:
        if f0 in seen: continue
        comp, st = [], [f0]
        while st:
            fi = st.pop()
            if fi in seen or fi not in cand: continue
            seen.add(fi); comp.append(fi)
            for e in bm.faces[fi].edges:
                for g in e.link_faces:
                    if g.index in cand and g.index not in seen: st.append(g.index)
        if len(comp) > len(best): best = comp
    eye_faces[side] = best
    rep[side] = dict(center=c.round(4).tolist(), radius=round(r, 4), faces=len(best))
bm.free()
# separate via edit-mode selection
for side in ("L", "R"):
    bpy.context.view_layer.objects.active = body
    for o in bpy.data.objects: o.select_set(o is body)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
    fs = set(eye_faces[side])
    for p in body.data.polygons: p.select = p.index in fs
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
    new = [o for o in bpy.context.selected_objects if o is not body][0]
    new.name = f"Eye.{side}"; new.data.name = f"Eye.{side}"
    # recompute face indices of the remaining body for the next side
    if side == "L":
        co = np.array([v.co[:] for v in body.data.vertices])
        bm = bmesh.new(); bm.from_mesh(body.data); bm.faces.ensure_lookup_table()
        c = np.array(rep["R"]["center"]); r = rep["R"]["radius"]
        on = np.abs(np.linalg.norm(co - c, axis=1) - r) < TOL
        cand = set(f.index for f in bm.faces if all(on[v.index] for v in f.verts))
        best, seen = [], set()
        for f0 in cand:
            if f0 in seen: continue
            comp, st = [], [f0]
            while st:
                fi = st.pop()
                if fi in seen or fi not in cand: continue
                seen.add(fi); comp.append(fi)
                for e in bm.faces[fi].edges:
                    for g in e.link_faces:
                        if g.index in cand and g.index not in seen: st.append(g.index)
            if len(comp) > len(best): best = comp
        eye_faces["R"] = best; bm.free()
bpy.ops.wm.save_as_mainfile(filepath=out)
print("EYES", json.dumps(rep))
