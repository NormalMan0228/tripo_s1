"""Turn the closed-mouth smile of the Headshot source FBX into a neutral closed mouth, keeping vertex/face order
(so a saved Headshot alignment .ini still maps), then render before/after clay views.

The lip line comes from the seam of head_a_full.blend (model units x METRES_PER_UNIT = FBX metres).
A smooth field flattens the seam curve to the centre height (corners down), pulls the corners in a little and
fades out vertically, sideways past the corners and towards the back of the head.

Usage: blender -b --factory-startup -P neutralize_smile.py -- <out_fbx> <render_dir> [droop_mm=0.5] [narrow=0.06] [corner_r_mm=7] [smooth_it=25]
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

a = sys.argv[sys.argv.index("--") + 1:]
OUT_FBX, RDIR = os.path.abspath(a[0]), os.path.abspath(a[1])
DROOP = float(a[2]) / 1000 if len(a) > 2 else 0.0005
NARROW = float(a[3]) if len(a) > 3 else 0.06
CORNER_R = float(a[4]) / 1000 if len(a) > 4 else 0.007      # corner smoothing radius
SMOOTH_IT = int(a[5]) if len(a) > 5 else 25
HD = os.path.join(os.path.dirname(__file__), "..", "hd")
SRC_FBX = os.path.join(HD, "export", "character1_head_headshot.fbx")
M_PER_UNIT = json.load(open(os.path.join(HD, "export", "export_report.json")))["metres_per_unit"]
os.makedirs(RDIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
# lip seam from the HD blend: boundary verts in the mouth band
with bpy.data.libraries.load(os.path.join(HD, "head_a_full.blend")) as (src, dst):
    dst.objects = ["Head"]
hd = dst.objects[0]
bm = bmesh.new(); bm.from_mesh(hd.data)
S = np.array([v.co[:] for v in bm.verts if v.is_boundary and abs(v.co.x) <= 0.0985
              and -0.2795 <= v.co.y <= -0.2210 and 0.40 <= v.co.z <= 0.50]) * M_PER_UNIT
bm.free(); bpy.data.objects.remove(hd)
order = np.argsort(np.abs(S[:, 0]))
sx, sz = np.abs(S[order, 0]), S[order, 2]
XC = sx.max()                                   # corner |x|
zs = lambda x: np.interp(np.minimum(np.abs(x), XC), sx, sz)
ZC = float(zs(0.0))

bpy.ops.import_scene.fbx(filepath=SRC_FBX)
o = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mw = o.matrix_world.copy(); inv = mw.inverted()
V = np.array([tuple(mw @ v.co) for v in o.data.vertices])
x, y, z = V[:, 0], V[:, 1], V[:, 2]
seam_y = np.interp(np.minimum(np.abs(x), XC), sx, S[order, 1])
t = np.minimum(np.abs(x), XC) / XC                      # 0 centre .. 1 corner
dz_line = (ZC - DROOP * t ** 2) - zs(x)                  # flatten the smile curve
dx_line = -np.sign(x) * NARROW * np.minimum(np.abs(x), XC) * t ** 2
SIG_Z, SIG_X, SIG_Y = 0.012, 0.012, 0.015
w = np.exp(-((z - zs(x)) / SIG_Z) ** 2)
w *= np.where(np.abs(x) <= XC, 1.0, np.exp(-((np.abs(x) - XC) / SIG_X) ** 2))
w *= np.clip(1 - (y - seam_y) / SIG_Y, 0, 1) ** 2         # front of the face only
D = np.zeros_like(V); D[:, 0] = dx_line * w; D[:, 2] = dz_line * w


def render(tag):
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.8, 0.8, 0.8)
    sh.show_cavity = True; sh.cavity_type = 'WORLD'
    sc.render.resolution_x = sc.render.resolution_y = 700; sc.view_settings.view_transform = 'Standard'
    cam = bpy.data.objects.get("Cam") or bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.type = 'ORTHO'
    for name, d, c, s in [("front", (0, -1, 0), (0, 0, 0.215), 0.30), ("q34", (0.6, -0.8, 0.05), (0, 0, 0.215), 0.30),
                          ("mouth", (0, -1, 0), (0, 0, 0.172), 0.11), ("mouthq", (0.6, -0.8, -0.05), (0, -0.05, 0.172), 0.12)]:
        d = Vector(d).normalized(); c = Vector(c)
        cam.location = c + d * 1.5; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.ortho_scale = s
        sc.render.filepath = os.path.join(RDIR, f"{tag}_{name}.png"); bpy.ops.render.render(write_still=True)


render("before")
NV = V + D
# topology-preserving clean-up: Laplacian smoothing of the sheared corner creases and of folded faces
# (face normal opposite to its neighbours) outside the lip-contact band, e.g. the inverted triangle on the chin
me = o.data
nbr = [[] for _ in range(len(V))]
for e in me.edges:
    i, j = e.vertices; nbr[i].append(j); nbr[j].append(i)
cz = ZC - DROOP
dist_c = np.hypot(np.abs(NV[:, 0]) - XC * (1 - NARROW), NV[:, 2] - cz)     # distance to the moved corners (x-z)
wsm = np.clip(1 - dist_c / CORNER_R, 0, 1) * (NV[:, 1] < -0.05)
P = np.array([p.vertices[:] for p in me.polygons if len(p.vertices) == 3] + [])
fn = np.cross(NV[P[:, 1]] - NV[P[:, 0]], NV[P[:, 2]] - NV[P[:, 0]])
fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-20
vn = np.zeros_like(NV); np.add.at(vn, P.ravel(), np.repeat(fn, 3, axis=0))
vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-20
flip = (np.einsum('ij,ij->i', fn, vn[P].mean(axis=1)) < -0.2)
cen = NV[P].mean(axis=1)
lipband = (np.abs(cen[:, 2] - ZC) < 0.006) & (cen[:, 1] < -0.09) & (np.abs(cen[:, 0]) < XC + 0.004)
bad_faces = np.where(flip & ~lipband)[0]
fix = np.zeros(len(V))
for f in bad_faces:
    for vi in P[f]: fix[vi] = 1; fix[nbr[vi]] = np.maximum(fix[nbr[vi]], 0.7)
wsm = np.maximum(wsm, fix)
idx = np.where(wsm > 0)[0]
for _ in range(SMOOTH_IT):
    avg = np.array([NV[nbr[i]].mean(axis=0) for i in idx])
    NV[idx] += (avg - NV[idx]) * (0.5 * wsm[idx])[:, None]
FIXED = {"folded_faces_fixed": [np.round(cen[f], 4).tolist() for f in bad_faces], "smoothed_verts": int((wsm > 0).sum())}
D = NV - V
for v, p in zip(o.data.vertices, NV): v.co = inv @ Vector(p)
o.data.update()
render("after")
for ob in bpy.data.objects: ob.select_set(ob == o)
bpy.context.view_layer.objects.active = o
bpy.ops.export_scene.fbx(filepath=OUT_FBX, use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
                         mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False, path_mode='STRIP')
mv = np.linalg.norm(D, axis=1)
print("NEUTRAL", json.dumps({"corner_x_m": float(XC), "centre_z_m": ZC, "corner_rise_mm": float((zs(XC) - ZC) * 1000),
                             "max_move_mm": float(mv.max() * 1000), "moved_verts": int((mv > 1e-4).sum()),
                             "verts": len(V), "polys": len(o.data.polygons), "fbx_bytes": os.path.getsize(OUT_FBX), **FIXED}))
