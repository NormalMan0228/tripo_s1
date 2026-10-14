"""Clean, symmetric, rig-ready parts from the open-mouth P2 head.

1. align: yaw/x-shift from the two eyeball fits so the face plane is x = 0
2. Body: remove non-manifold fin pieces and tiny islands, merge doubles, SYMMETRIZE from SIDE (+X default),
   fill small holes (gum sockets, ear canals, nicks); keep the bust cut and the eye openings
3. eye openings get an inner lid lining (lid thickness wrapping onto the eyeball) for blinking
4. eyeballs: clean UV spheres (fitted centre / radius, pupil axis -Y), mirrored pair
5. teeth / tongue: symmetrized (lower teeth rebuilt from the better side)
Writes open/clean.blend and open/clean_report.json.
Usage: blender --background open/parts_eyes.blend --python fix_open.py -- <out_dir>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
SIDE = os.environ.get("SIDE", "POSITIVE_X")           # half that is kept and mirrored
HOLE_MAX = int(os.environ.get("HOLE_MAX", 70))
rep = {"side": SIDE}
O = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}


def np_co(o): return np.array([v.co[:] for v in o.data.vertices])


def fit(P):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = s[:3]; return c, float(np.sqrt(s[3] + c @ c))


# ---------------------------------------------------------------- 1. align
cL, rL = fit(np_co(O["Eye.L"])); cR, rR = fit(np_co(O["Eye.R"]))
d = cL - cR; yaw = -math.atan2(d[1], d[0]); tilt = -math.atan2(d[2], math.hypot(d[0], d[1]))
M = Matrix.Rotation(tilt, 4, 'Y') @ Matrix.Rotation(yaw, 4, 'Z')
mid = M @ Vector((cL + cR) / 2)
M = Matrix.Translation((-mid.x, 0, 0)) @ M
for o in O.values():
    o.data.transform(M)
cL, cR = np.array(M @ Vector(cL)), np.array(M @ Vector(cR))
R_EYE = (rL + rR) / 2
c_eye = np.array([abs(cL[0]) / 2 + abs(cR[0]) / 2, (cL[1] + cR[1]) / 2, (cL[2] + cR[2]) / 2])
rep["align"] = dict(yaw_deg=math.degrees(yaw), tilt_deg=math.degrees(tilt), eye_center_L=c_eye.round(4).tolist(), eye_radius=round(R_EYE, 4))


def run_edit(o, fn):
    for x in bpy.data.objects: x.select_set(x is o)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    fn()
    bpy.ops.object.mode_set(mode='OBJECT')


def keep_largest(o, min_keep=None):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    par = list(range(len(bm.verts)))
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for e in bm.edges:
        a, b = f(e.verts[0].index), f(e.verts[1].index)
        if a != b: par[a] = b
    g = {}
    for v in bm.verts: g.setdefault(f(v.index), []).append(v)
    big = max(g.values(), key=len)
    kill = [v for vs in g.values() if vs is not big and (min_keep is None or len(vs) < min_keep) for v in vs]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bm.to_mesh(o.data); bm.free()
    return len(kill)


# ---------------------------------------------------------------- 2. body
body = O["Body"]
bm = bmesh.new(); bm.from_mesh(body.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
nm = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
bmesh.ops.split_edges(bm, edges=nm)
bm.to_mesh(body.data); bm.free()
rep["removed_fin_verts"] = keep_largest(body, min_keep=200)
# symmetrize (bisect at x=0, mirror the kept half, merge the seam)

# slivers left from the eye cut: body faces whose verts all hug an eyeball sphere
bm = bmesh.new(); bm.from_mesh(body.data)
kill = []
for f in bm.faces:
    for c in (cL, cR):
        if all(abs(np.linalg.norm(np.array(v.co) - c) - R_EYE) < float(os.environ.get("SLIVER_TOL", 0.009)) for v in f.verts):
            kill.append(f); break
bmesh.ops.delete(bm, geom=kill, context='FACES')
bm.to_mesh(body.data); bm.free()
rep["eye_sliver_faces_removed"] = len(kill)
rep["removed_after_sliver"] = keep_largest(body, min_keep=200)
# lid folds: relax (not delete) the skin around each eye opening; folded/inverted faces unfold, the lid rim
# (vertices hugging the eyeball) and the rest of the face stay put
FOLD_IT = int(os.environ.get("FOLD_ITERS", 0))
if FOLD_IT:
    bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
    wv = {}
    for v in bm.verts:
        p_ = np.array(v.co)
        for c in (cL, cR):
            d_ = p_ - c; r_ = np.linalg.norm(d_)
            if d_[1] < 0.01 and r_ < R_EYE * 1.5:
                # strongest just outside the lid band, fading to 0 at 1.5 R and at the rim
                w_ = np.clip((r_ - (R_EYE + 0.002)) / 0.006, 0, 1) * np.clip((R_EYE * 1.5 - r_) / (R_EYE * 0.25), 0, 1)
                if w_ > 0: wv[v] = max(wv.get(v, 0), w_)
    for _ in range(FOLD_IT):
        new = {}
        for v, w_ in wv.items():
            nb = [e.other_vert(v).co for e in v.link_edges]
            if nb and not v.is_boundary: new[v] = v.co.lerp(sum(nb, Vector()) / len(nb), 0.5 * w_)
        for v, q in new.items(): v.co = q
    bm.to_mesh(body.data); bm.free()
    rep["lid_relax_verts"] = len(wv)
# holes
def boundary_loops(o):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts[0].index, e.verts[1].index; adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    co = np.array([v.co[:] for v in bm.verts]); bm.free()
    seen, loops = set(), []
    for s in adj:
        if s in seen: continue
        order = [s]; seen.add(s); prev, cur = None, s
        while True:
            nx = [w for w in adj[cur] if w != prev and w not in seen]
            if not nx: break
            prev, cur = cur, nx[0]; order.append(cur); seen.add(cur)
        loops.append(order)
    return loops, co
loops, co = boundary_loops(body)
eye_loops, keep_loops, fill = [], [], []
for lp in loops:
    c = co[lp].mean(0)
    near_eye = min(np.linalg.norm(c - cL), np.linalg.norm(c - cR)) < R_EYE * 0.8
    if near_eye and len(lp) > 20: eye_loops.append(lp)
    elif co[lp][:, 2].min() < 0.02 or len(lp) > HOLE_MAX: keep_loops.append(lp)      # bust cut / large openings
    elif min(np.linalg.norm(c - cL), np.linalg.norm(c - cR)) < R_EYE * 1.35: keep_loops.append(lp)  # lid crevice: leave for the eye pass
    else: fill.append(lp)
rep["holes"] = dict(eye=[len(l) for l in eye_loops], kept=[len(l) for l in keep_loops], filled=len(fill),
                    filled_sizes=sorted([len(l) for l in fill], reverse=True)[:12])
# fill with Blender's own Fill Holes on exactly these boundary loops (consistent winding), then relax the patches
fs = set(i for l in fill for i in l)
for x in bpy.data.objects: x.select_set(x is body)
bpy.context.view_layer.objects.active = body
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='VERT'); bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')
for v in body.data.vertices: v.select = v.index in fs
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.fill_holes(sides=0)
bpy.ops.mesh.select_more()
bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=3)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

# ---------------------------------------------------------------- 3. inner lid lining for the eye openings
loops, co = boundary_loops(body)
eye_loops = [lp for lp in loops if min(np.linalg.norm(co[lp].mean(0) - cL), np.linalg.norm(co[lp].mean(0) - cR)) < R_EYE * 0.8 and len(lp) > 20]
GAP = float(os.environ.get("LID_GAP", 0.0015)); DEPTH = float(os.environ.get("LID_DEPTH", 0.006))
# smooth each eye-opening rim along itself (removes the jagged eye-cut edge); 1-2 rings follow
RIM_IT = int(os.environ.get("RIM_ITERS", 6))
bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
for lp in eye_loops:
    c = cL if co[lp].mean(0)[0] > 0 else cR
    vs = [bm.verts[i] for i in lp]; n_ = len(vs)
    orig = [v.co.copy() for v in vs]
    for _ in range(RIM_IT):
        new = [vs[j].co * 0.5 + (vs[j - 1].co + vs[(j + 1) % n_].co) * 0.25 for j in range(n_)]
        for v, q in zip(vs, new): v.co = q
    for v in vs:                                    # stay just outside the eyeball
        dv = np.array(v.co) - c; r = np.linalg.norm(dv)
        if r < R_EYE + GAP: v.co = Vector(c + dv / r * (R_EYE + GAP))
    rs = set(vs)
    for v, o0 in zip(vs, orig):
        dlt = v.co - o0
        for e in v.link_edges:
            u = e.other_vert(v)
            if u not in rs:
                u.co += dlt * 0.5
                for e2 in u.link_edges:
                    w2 = e2.other_vert(u)
                    if w2 not in rs and w2 is not v: w2.co += dlt * 0.15
bm.to_mesh(body.data); bm.free()
loops, co = boundary_loops(body)
eye_loops = [lp for lp in loops if min(np.linalg.norm(co[lp].mean(0) - cL), np.linalg.norm(co[lp].mean(0) - cR)) < R_EYE * 0.8 and len(lp) > 20]
bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
V0 = list(bm.verts)
lining = 0
for lp in (eye_loops if os.environ.get('LINING', '1') == '1' else []):
    c = cL if co[lp].mean(0)[0] > 0 else cR
    ring_prev = [V0[i] for i in lp]
    for k, (gap, back) in enumerate(((GAP, 0.0), (GAP, DEPTH * 0.5), (GAP * 0.7, DEPTH))):
        ring = []
        for v in ring_prev:
            p = np.array(V0[lp[ring_prev.index(v)]].co) if k == 0 else np.array(v.co)
            dvec = p - c; rr = np.linalg.norm(dvec)
            q = c + dvec / rr * (R_EYE + gap)
            # slide backward on the sphere (rotate the point away from the viewer around the eye centre)
            if back > 0:
                t = q - c; t[1] += back * 1.0; q = c + t / np.linalg.norm(t) * (R_EYE + gap)
            ring.append(bm.verts.new(Vector(q)))
        for j in range(len(lp)):
            a, b = ring_prev[j], ring_prev[(j + 1) % len(lp)]
            try:
                bm.faces.new((a, b, ring[(j + 1) % len(lp)], ring[j]))
            except ValueError:
                pass
        ring_prev = ring; lining += len(ring)
bm.normal_update()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(body.data); bm.free()
rep["lid_lining_verts"] = lining
run_edit(body, lambda: (bpy.ops.mesh.symmetrize(direction=SIDE, threshold=0.0008), bpy.ops.mesh.remove_doubles(threshold=1e-5)))
# components after symmetrize: Body = largest, sizeable interior pieces -> MouthLower, crumbs -> delete
bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
par = list(range(len(bm.verts)))
def f_(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for e in bm.edges:
    a, b = f_(e.verts[0].index), f_(e.verts[1].index)
    if a != b: par[a] = b
g = {}
for v in bm.verts: g.setdefault(f_(v.index), []).append(v.index)
comps = sorted(g.values(), key=len, reverse=True)
crumbs = [i for c in comps[1:] if len(c) < 60 for i in c]
bmesh.ops.delete(bm, geom=[bm.verts[i] for i in crumbs], context='VERTS')
bm.to_mesh(body.data); bm.free()
rep["post_sym_components"] = [len(c) for c in comps[:6]]
for x in bpy.data.objects: x.select_set(x is body)
bpy.context.view_layer.objects.active = body
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.separate(type='LOOSE'); bpy.ops.object.mode_set(mode='OBJECT')
pieces = sorted([o for o in bpy.context.selected_objects], key=lambda o: -len(o.data.vertices))
pieces[0].name = "Body"; pieces[0].data.name = "Body"; body = pieces[0]
if len(pieces) > 1:
    for x in bpy.data.objects: x.select_set(x in pieces[1:])
    bpy.context.view_layer.objects.active = pieces[1]
    bpy.ops.object.join()
    ml = bpy.context.view_layer.objects.active; ml.name = "MouthLower"; ml.data.name = "MouthLower"

# final: close any leftover small boundary loop (<= 16 verts) on the body (not the eye openings / bust cut)
loops, co = boundary_loops(body)
small = [lp for lp in loops if len(lp) <= 16]
fs = set(i for l in small for i in l)
for x in bpy.data.objects: x.select_set(x is body)
bpy.context.view_layer.objects.active = body
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='VERT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
for v in body.data.vertices: v.select = v.index in fs
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.fill_holes(sides=0); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
rep["final_small_holes_filled"] = len(small)
# ---------------------------------------------------------------- 4. clean eyeballs
for nm_ in ("Eye.L", "Eye.R"):
    bpy.data.objects.remove(O[nm_])
for side, sx in (("L", 1), ("R", -1)):
    me = bpy.data.meshes.new(f"Eye.{side}")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=28, radius=R_EYE - float(os.environ.get('EYE_SHRINK', 0.001)))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))   # poles on the Y axis
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(f"Eye.{side}", me); body.users_collection[0].objects.link(ob)
    ob.location = (sx * c_eye[0], c_eye[1], c_eye[2])
    ob["pupil_axis"] = "-Y"

# ---------------------------------------------------------------- 5. teeth / tongue
for nm_ in ("TeethUpper", "TeethLower", "Tongue"):
    o = bpy.data.objects.get(nm_)
    if not o: continue
    run_edit(o, lambda: (bpy.ops.mesh.remove_doubles(threshold=1e-5), bpy.ops.mesh.symmetrize(direction=SIDE, threshold=0.0005), bpy.ops.mesh.remove_doubles(threshold=1e-5)))
    rep[f"{nm_}_verts"] = len(o.data.vertices)

# metrics
def mirror_err(o):
    from mathutils.kdtree import KDTree
    P = np_co(o); kd = KDTree(len(P))
    for i, p in enumerate(P): kd.insert(p, i)
    kd.balance()
    e = [kd.find((-p[0], p[1], p[2]))[2] for p in P]
    return float(np.max(e))
for o in bpy.data.objects:
    if o.type == 'MESH':
        bm = bmesh.new(); bm.from_mesh(o.data)
        rep.setdefault("final", {})[o.name] = dict(verts=len(bm.verts), nonmanifold=sum((not e.is_manifold) and not e.is_boundary for e in bm.edges),
                                                    boundary_edges=sum(e.is_boundary for e in bm.edges), mirror_err_max_mm=round(mirror_err(o) * 1000, 3) if not o.name.startswith("Eye") else None)
        bm.free()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "clean.blend"))
json.dump(rep, open(os.path.join(OUT, "clean_report.json"), "w"), indent=1)
print("CLEAN", json.dumps(rep))
