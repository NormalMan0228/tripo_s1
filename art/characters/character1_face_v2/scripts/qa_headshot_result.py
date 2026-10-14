"""QA of a Headshot / wrap result against our clean source head.

* imports the result FBX, picks the body/head mesh (largest mesh with 'Body' or 'Head' in its name, else the largest)
* registers it to the source head: bbox scale/centre first, then similarity ICP on the upper face (eyes/nose/forehead)
* distances source->result per region (face front, lids, lips, ears, cranium) and result symmetry
* heat-map renders (front, 3/4) of the source coloured by distance to the result
Usage: blender --background head_a_full.blend --python qa_headshot_result.py -- <result.fbx> <out_prefix>
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index("--") + 1:]
RES, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
head = bpy.data.objects["Head"]
S = np.array([v.co[:] for v in head.data.vertices])
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=RES)
new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
cand = [o for o in new if "body" in o.name.lower() or "head" in o.name.lower()] or new
res = max(cand, key=lambda o: len(o.data.vertices))
dg = bpy.context.evaluated_depsgraph_get()
ev = res.evaluated_get(dg); rm = ev.to_mesh()
T = np.array([res.matrix_world @ v.co for v in rm.vertices]); TF = [tuple(p.vertices) for p in rm.polygons]
rep = {"result_object": res.name, "result_verts": len(T), "result_faces": len(TF)}
# keep only the result's head part (above its neck) when a full body comes back: use the top 30 % of its height
h = T[:, 2].max() - T[:, 2].min()
if h > 3 * (S[:, 2].max() - S[:, 2].min()):
    keep = T[:, 2] > T[:, 2].max() - 0.16 * h
    rep["full_body_cropped"] = True
else:
    keep = np.ones(len(T), bool)
# initial similarity from the cranium cap: sphere fit to the top of each head (scale = radius ratio, centre match)
def sphere(P):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1); x = np.linalg.lstsq(A, b, rcond=None)[0]
    return x[:3], math.sqrt(max(x[3] + x[:3] @ x[:3], 1e-12))
cs, rs = sphere(S[S[:, 2] > S[:, 2].max() - 0.15])
TK = T[keep]; band = 0.05 * (TK[:, 2].max() - TK[:, 2].min())
for _ in range(4):
    ct, rt = sphere(TK[TK[:, 2] > TK[:, 2].max() - band])
    band = 0.15 * rt / rs
s0 = rs / rt
M = np.eye(4); M[:3, :3] *= s0; M[:3, 3] = cs - s0 * ct
rep["init_scale"] = s0


def apply(M, P):
    return P @ M[:3, :3].T + M[:3, 3]


# similarity ICP on the upper face of the source (forehead, eyes, nose)
up = S[(S[:, 2] > 0.48) & (S[:, 1] < -0.05) & (np.abs(S[:, 0]) < 0.22)]
up = up[np.random.default_rng(0).choice(len(up), min(20000, len(up)), replace=False)]
for it in range(40):
    TT = apply(M, T)
    bvh = BVHTree.FromPolygons([tuple(p) for p in TT], TF)
    Q = np.array([bvh.find_nearest(Vector(p))[0] for p in up])
    d = np.linalg.norm(Q - up, axis=1); k = d < np.percentile(d, 85)
    A, B = Q[k], up[k]; ca, cb = A.mean(0), B.mean(0)
    U, sg, Vt = np.linalg.svd((A - ca).T @ (B - cb)); D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T; sc = (sg * np.diag(D)).sum() / ((A - ca) ** 2).sum()
    Mi = np.eye(4); Mi[:3, :3] = sc * R; Mi[:3, 3] = cb - sc * R @ ca
    M = Mi @ M
TT = apply(M, T)
bvh = BVHTree.FromPolygons([tuple(p) for p in TT], TF)
dist = np.array([(bvh.find_nearest(Vector(p))[0] - Vector(p)).length for p in S])
regions = {
    "face_front": (S[:, 1] < -0.12) & (S[:, 2] > 0.33) & (S[:, 2] < 0.75),
    "lids": np.zeros(len(S), bool), "lips": np.zeros(len(S), bool),
    "ears": (np.abs(S[:, 0]) > 0.24) & (S[:, 2] > 0.45) & (S[:, 2] < 0.75),
    "cranium": S[:, 2] > 0.8, "neck": (S[:, 2] < 0.33) & (S[:, 2] > 0.1)}
ce = np.array(head["eye_centre_L"]); R_ = float(head["eye_R"])
for c in (ce, ce * [-1, 1, 1]):
    r = np.linalg.norm(S - c, axis=1); regions["lids"] |= (r < R_ * 1.35) & (S[:, 1] < c[1])
zc = float(head.get("lip_line_z_centre", 0.453))
regions["lips"] = (np.abs(S[:, 0]) < 0.11) & (np.abs(S[:, 2] - zc) < 0.035) & (S[:, 1] < -0.18)
U_MM = float(os.environ.get("UNIT_MM", 370.47))     # mm per model unit (bust height 1 = 37 cm export scale)
rep["dist_mm"] = {k: {"median": round(float(np.median(dist[m])) * U_MM, 2), "p95": round(float(np.percentile(dist[m], 95)) * U_MM, 2)}
                  for k, m in regions.items() if m.any()}
kd = KDTree(len(TT))
for i, p in enumerate(TT): kd.insert(p, i)
kd.balance()
sub = TT[keep][::max(1, int(keep.sum() / 20000))]
rep["result_symmetry_mm_p95"] = round(float(np.percentile([kd.find((-p[0], p[1], p[2]))[2] for p in sub], 95)) * U_MM, 2)
# heat map on the source
me = head.data
ca_ = me.color_attributes.get("qa_dist") or me.color_attributes.new("qa_dist", 'FLOAT_COLOR', 'POINT')
t = np.clip(dist * U_MM / 3.0, 0, 1)                    # 0 mm blue .. 3 mm+ red
col = np.c_[t, 1 - np.abs(t - 0.5) * 2, 1 - t, np.ones(len(t))]
ca_.data.foreach_set("color", col.ravel()); me.color_attributes.active_color = ca_
for o in bpy.data.objects:
    if o.type == 'MESH' and o is not head: o.hide_render = True
sc_ = bpy.context.scene; sc_.render.engine = 'BLENDER_WORKBENCH'; sc_.render.resolution_x = sc_.render.resolution_y = 700
sh = sc_.display.shading; sh.light = 'STUDIO'; sh.color_type = 'VERTEX'
cd = bpy.data.cameras.new("qa"); cd.type = 'ORTHO'; cd.ortho_scale = 0.62; cam = bpy.data.objects.new("qa", cd); sc_.collection.objects.link(cam); sc_.camera = cam
for k, d in (("front", Vector((0, -1, 0))), ("q34", Vector((0.62, -0.78, 0)).normalized())):
    tgt = Vector((0, 0, 0.58)); cam.location = tgt + d * 3; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc_.render.filepath = f"{OUT}_heat_{k}.png"; bpy.ops.render.render(write_still=True)
json.dump(rep, open(OUT + "_report.json", "w"), indent=1)
print("QA", json.dumps(rep))
