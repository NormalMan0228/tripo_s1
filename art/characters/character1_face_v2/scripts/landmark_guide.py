"""Facial landmarks on the clean head (for Headshot alignment points / wrap correspondences) + a numbered guide render.

Landmarks come from the geometry: eye margin loops (corners, lid midpoints), lip seam (mouth corners), front-most
points (nose tip, lip midpoints, chin), nose width at the nostril line, ear extremes, glabella.
Writes <out>.json (model-space positions + nearest vertex index) and <out>.png (front + 3/4 views with numbers).
Usage: blender --background head_a_full.blend --python landmark_guide.py -- <out_prefix>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
head = bpy.data.objects["Head"]; me = head.data
X = np.array([v.co[:] for v in me.vertices]); n = len(X)
ce = np.array(head["eye_centre_L"]); R = float(head["eye_R"])
L = {}
from mathutils.bvhtree import BVHTree
HT = BVHTree.FromPolygons([tuple(p) for p in X], [tuple(p.vertices) for p in me.polygons])
KD = KDTree(n)
for i, p in enumerate(X): KD.insert(p, i)
KD.balance()
# eye margins: boundary loops near each eye centre (lip seam loops are excluded by distance)
bm = bmesh.new(); bm.from_mesh(me)
bverts = np.array(sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts})); bm.free()
for side, c in (("L", ce), ("R", ce * [-1, 1, 1])):
    m = bverts[np.linalg.norm(X[bverts] - c, axis=1) < R * 1.6]
    P = X[m]
    inner = m[np.argmin(np.abs(P[:, 0]))]; outer = m[np.argmax(np.abs(P[:, 0]))]
    mid_x = 0.5 * (X[inner, 0] + X[outer, 0])
    near = m[np.abs(X[m, 0] - mid_x) < R * 0.25]
    L[f"eye_inner_{side}"] = int(inner); L[f"eye_outer_{side}"] = int(outer)
    # visible lid edges: scan front rays at the eye's middle x; the lid edge is the last head hit before the ball shows
    def front_hit(x, z):
        h = HT.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)), 5)
        yh = h[0].y if h[0] is not None else 9.0
        dx, dz = x - c[0], z - c[2]; r2 = R * R - dx * dx - dz * dz
        ys = c[1] - math.sqrt(r2) if r2 > 0 else 9.0
        return yh, ys, h
    for nm, zs in (("upper", np.arange(c[2] + R, c[2] - 0.2 * R, -0.0005)), ("lower", np.arange(c[2] - R, c[2] + 0.2 * R, 0.0005))):
        prev = None
        for z in zs:
            yh, ys, h = front_hit(mid_x, z)
            if ys < yh - 1e-5 and prev is not None: break
            prev = h
        L[f"lid_{nm}_{side}"] = int(KD.find(prev[0])[1])
# lip seam
vg = head.vertex_groups.get("lip_seam")
seam = np.array([v.index for v in me.vertices for g in v.groups if vg and g.group == vg.index])
L["mouth_corner_L"] = int(seam[np.argmax(X[seam, 0])]); L["mouth_corner_R"] = int(seam[np.argmin(X[seam, 0])])
zc = float(np.median(X[seam[np.abs(X[seam, 0]) < 0.01], 2]))
mid = np.abs(X[:, 0]) < 0.004
up = np.where(mid & (X[:, 2] > zc) & (X[:, 2] < zc + 0.03))[0]; L["lip_upper_mid"] = int(up[np.argmin(X[up, 1])])
lo = np.where(mid & (X[:, 2] < zc) & (X[:, 2] > zc - 0.04))[0]; L["lip_lower_mid"] = int(lo[np.argmin(X[lo, 1])])
nz = np.where(mid & (X[:, 2] > zc + 0.03) & (X[:, 2] < ce[2]))[0]; L["nose_tip"] = int(nz[np.argmin(X[nz, 1])])
# nostril line: nose width at the alar level (just above subnasale), front part only
zt = X[L["nose_tip"], 2]
al = np.where((np.abs(X[:, 2] - (zt - 0.012)) < 0.004) & (X[:, 1] < X[L["nose_tip"], 1] + 0.05) & (np.abs(X[:, 0]) < 0.06))[0]
L["alar_L"] = int(al[np.argmax(X[al, 0])]); L["alar_R"] = int(al[np.argmin(X[al, 0])])
ch = np.where(mid & (X[:, 2] > 0.25) & (X[:, 2] < zc - 0.04) & (X[:, 1] < -0.2))[0]
L["chin"] = int(ch[np.argmin(X[ch, 2] + 0.5 * X[ch, 1])])
gl = np.where(mid & (np.abs(X[:, 2] - (ce[2] + R * 1.1)) < 0.004))[0]; L["glabella"] = int(gl[np.argmin(X[gl, 1])])
for side, sg in (("L", 1), ("R", -1)):
    # ear = the part sticking out beyond the skull side: |x| beyond the head-side envelope at that height
    band = (X[:, 2] > 0.45) & (X[:, 2] < 0.75) & (X[:, 1] > -0.03) & (sg * X[:, 0] > 0.22)
    skull = np.where(band & (X[:, 1] > 0.12))[0]                      # behind the ear: skull side width per height
    zb = np.round(X[skull, 2] / 0.01).astype(int); wmax = {}
    for zi, xx in zip(zb, np.abs(X[skull, 0])): wmax[zi] = max(wmax.get(zi, 0), xx)
    env = np.array([wmax.get(int(round(z / 0.01)), 0.25) for z in X[:, 2]])
    ear = np.where(band & (np.abs(X[:, 0]) > env + 0.012))[0]
    L[f"ear_top_{side}"] = int(ear[np.argmax(X[ear, 2])]); L[f"ear_bottom_{side}"] = int(ear[np.argmin(X[ear, 2])])
    L[f"ear_outer_{side}"] = int(ear[np.argmax(sg * X[ear, 0])])
KO = {"eye_inner": "안쪽 눈꼬리", "eye_outer": "바깥 눈꼬리", "lid_upper": "윗눈꺼풀 중앙", "lid_lower": "아랫눈꺼풀 중앙",
      "mouth_corner": "입꼬리", "lip_upper_mid": "윗입술 중앙", "lip_lower_mid": "아랫입술 중앙", "nose_tip": "코끝", "alar": "콧볼",
      "chin": "턱끝", "glabella": "미간", "ear_top": "귀 위", "ear_bottom": "귓불 아래", "ear_outer": "귀 바깥"}
names = list(L)
json.dump({k: {"vertex": v, "pos": X[v].round(5).tolist()} for k, v in L.items()}, open(OUT + ".json", "w"), indent=1, ensure_ascii=False)
# render: front + 3/4 clay, project landmark positions to pixels
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 900
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.82, 0.8, 0.78); sh.show_cavity = True
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name not in ("Head", "Eye.L", "Eye.R"): o.hide_render = True
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = 0.62; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
from bpy_extras.object_utils import world_to_camera_view
shots = {}
for k, d in (("front", Vector((0, -1, 0))), ("q34", Vector((0.62, -0.78, 0.0)).normalized())):
    tgt = Vector((0, 0, 0.58)); cam.location = tgt + d * 3; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    sc.render.filepath = f"{OUT}_{k}.png"; bpy.ops.render.render(write_still=True)
    pix = []
    for nm in names:
        p = Vector(X[L[nm]].tolist()); co = world_to_camera_view(sc, cam, p)
        vis = (p - cam.location).normalized().dot(-d) > 0
        pix.append((co.x * 900, (1 - co.y) * 900, bool((Vector(X[L[nm]].tolist()) - tgt).dot(d) > -0.05)))
    shots[k] = pix
json.dump({"names": names, "ko": KO, "shots": shots}, open(OUT + "_pix.json", "w"), ensure_ascii=False)
print("LANDMARKS", len(names))
