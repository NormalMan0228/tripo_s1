"""겹침생성 · full left/right symmetrisation of an original head (user decision 2026-10-12).

1. The head is cut at x = 0 and the left half (+x) is kept; the cut makes the centre-line vertices.
2. Each kept vertex moves to the average of itself and the mirrored right surface (nearest point on the original
   to its mirror image, mirrored back), so the result is the left/right mean shape, not one side copied.
3. That half is mirrored and welded on x = 0: the head is now exactly symmetric, vertex for vertex.
4. Inputs that come in pairs are averaged the same way: the 35-point landmarks (partners found by mirror distance,
   centre points put on x = 0) and the eye rims / eyeball centres (eyes_meta.json).
The change is half the original asymmetry; it is measured and written to sym_qa.json.
Writes <out_dir>/base.blend (objects 'orig' and 'noface', the same symmetric head: the 겹침생성 base),
<out_dir>/landmarks.json, <out_dir>/eyes_meta.json, <out_dir>/sym_qa.json.
Usage: blender -b --factory-startup -P sym_mirror.py -- <orig.fbx> <landmarks.json> <eyes_meta.json> <out_dir>
"""
import bpy, bmesh, sys, os, json
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facelib import lids

a = sys.argv[sys.argv.index('--') + 1:]
FBX, LMJ, EMJ, OUT = a[0], a[1], a[2], os.path.abspath(a[3])
os.makedirs(OUT, exist_ok=True)
MX = np.array([-1.0, 1.0, 1.0])
bpy.ops.wm.read_factory_settings(use_empty=True)
before = set(bpy.data.objects); bpy.ops.import_scene.fbx(filepath=FBX)
ms = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
for o in ms: o.data.transform(o.matrix_world); o.matrix_world = Matrix()
if len(ms) > 1:
    bpy.ops.object.select_all(action='DESELECT')
    for o in ms: o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]; bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active if len(ms) > 1 else ms[0]
for x in [x for x in bpy.data.objects if x.type != 'MESH']: bpy.data.objects.remove(x)
X0 = np.array([tuple(v.co) for v in ob.data.vertices]); F0 = [list(p.vertices) for p in ob.data.polygons]
bvh0 = BVHTree.FromPolygons([tuple(p) for p in X0], F0)
qa = {'verts_in': len(X0)}

bm = bmesh.new(); bm.from_mesh(ob.data)
# vertices within 0.05 mm of the plane count as on it: a cut that close to a vertex leaves sliver faces, and Rigify's
# bone heat weighting fails on those (f02, f11, f09 lost all weights)
CUT = 5e-5
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=CUT, plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
bm.verts.ensure_lookup_table()
moved = []
for v in bm.verts:
    p = np.array(v.co)
    if abs(p[0]) < CUT: v.co.x = 0.0; continue
    q = np.array(bvh0.find_nearest(Vector(tuple(p * MX)))[0]) * MX
    n = (p + q) / 2
    n[0] = max(n[0], min(p[0], 2 * CUT))                   # the average must not fold a vertex onto the plane
    moved.append(np.linalg.norm(n - p)); v.co = Vector(tuple(n))
# edges under CUT join; only plane vertices can be that close to each other across x (the rest stay >= CUT)
bmesh.ops.dissolve_degenerate(bm, dist=CUT, edges=bm.edges[:])
for v in bm.verts:
    if v.co.x < CUT: v.co.x = 0.0
centre = [v for v in bm.verts if abs(v.co.x) < 1e-9]
res = bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis='X', merge_dist=1e-6)
# mirroring keeps the vertex order, so the copied half faces inward: turn it back (texture projection, culling).
# Picked by position, not from the op's output: faces welded onto the centre line are missing from res['geom'],
# which left a 1-face strip down the middle wound the wrong way (2,800-3,800 faces per head, a seam in the texture)
bmesh.ops.reverse_faces(bm, faces=[f for f in bm.faces if f.calc_center_median().x < 0])
bm.normal_update()
me = bpy.data.meshes.new('orig'); bm.to_mesh(me); bm.free()
Xs = np.array([tuple(v.co) for v in me.vertices])
o2 = bpy.data.objects.new('orig', me); bpy.context.scene.collection.objects.link(o2)
bpy.data.objects.remove(ob)
for p in me.polygons: p.use_smooth = True
# QA: how far the symmetric surface is from the original, both ways
bvhS = BVHTree.FromPolygons([tuple(p) for p in Xs], [list(p.vertices) for p in me.polygons])
d0 = np.array([bvhS.find_nearest(Vector(tuple(p)))[3] for p in X0]) * 1000
mirror_gap = np.array([bvhS.find_nearest(Vector(tuple(p * MX)))[3] for p in Xs[::7]]) * 1000
fr = X0[:, 1] < np.median(X0[:, 1]); top = X0[:, 2].max(); face = fr & (X0[:, 2] > top - 0.6 * (top - X0[:, 2].min()))
st = lambda d: {'p50': round(float(np.median(d)), 2), 'p95': round(float(np.percentile(d, 95)), 2), 'max': round(float(d.max()), 2)}
Pc = np.array([tuple(p.center) for p in me.polygons]); Nc = np.array([tuple(p.normal) for p in me.polygons])
outw = ((Pc - Xs.mean(0)) * Nc).sum(1) > 0                 # share of faces pointing away from the head centre
qa['tiny_faces'] = int(sum(1 for p in me.polygons if p.area < 1e-9))   # slivers (bone heat fails on them); want 0
E2 = {}                                                    # winding: a manifold edge must run opposite ways in its 2 faces
for p in me.polygons:
    vs = list(p.vertices)
    for i in range(len(vs)): E2.setdefault((vs[i], vs[(i + 1) % len(vs)]), []).append(p.index)
qa['winding_conflicts'] = int(sum(1 for e, f in E2.items() if len(f) == 2 and e[::-1] not in E2))   # manifold edges run the same way by both faces; want 0
qa.update({'verts_out': len(Xs), 'centre_verts': len(centre), 'change_mm_all': st(d0), 'change_mm_face': st(d0[face]),
           'mirror_gap_after_mm': st(mirror_gap),
           'outward_faces': {'+x': round(float(outw[Pc[:, 0] > 0].mean()), 3), '-x': round(float(outw[Pc[:, 0] < 0].mean()), 3)}})
n2 = o2.copy(); n2.data = me.copy(); n2.name = 'noface'; bpy.context.scene.collection.objects.link(n2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'base.blend'), compress=True)

# ---- landmarks: partners by mirror distance, pairs averaged, centre points on x = 0
LJ = json.load(open(LMJ)); LT = {k: np.array(v) for k, v in LJ.items() if not k.startswith('_')}
ks = list(LT); out = {k: v for k, v in LJ.items() if k.startswith('_')}; done = set(); pairs = []
for k in ks:
    if k in done: continue
    p = LT[k]; best = min((np.linalg.norm(LT[j] * MX - p), j) for j in ks if j != k)
    if abs(p[0]) < 0.004 or best[0] > max(0.006, 0.5 * abs(2 * p[0])):
        q = p.copy(); q[0] = 0.0; out[k] = q.tolist(); done.add(k); continue
    j = best[1]; m = (p + LT[j] * MX) / 2
    out[k] = m.tolist(); out[j] = (m * MX).tolist(); done |= {k, j}; pairs.append((k, j))
json.dump(out, open(os.path.join(OUT, 'landmarks.json'), 'w'), indent=1)
qa['landmark_pairs'] = len(pairs)

# ---- eye rims: lids resampled (outer -> inner) and averaged with the mirrored other eye
EM = json.load(open(EMJ))
def resample(P, n=48):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; t = np.linspace(0, s[-1], n)
    return np.c_[[np.interp(t, s, P[:, j]) for j in range(3)]].T
L = {s: lids(np.array(EM[s]['raw']), np.linspace(0, 1, 5)) for s in 'LR'}
up = (resample(L['L']['up_path']) + resample(L['R']['up_path']) * MX) / 2
lo = (resample(L['L']['lo_path']) + resample(L['R']['lo_path']) * MX) / 2
C = (np.array(EM['L']['C']) + np.array(EM['R']['C']) * MX) / 2; r = (EM['L']['r'] + EM['R']['r']) / 2
A = np.array(EM['L']['A']) + np.array(EM['R']['A']) * MX; A /= np.linalg.norm(A)
raw = np.r_[up, lo[::-1][1:-1]]
EO = {}
for s, f in (('L', np.ones(3)), ('R', MX)):
    EO[s] = {'C': (C * f).tolist(), 'r': float(r), 'A': (A * f).tolist(), 'up_path': (up * f).tolist(), 'lo_path': (lo * f).tolist(), 'raw': (raw * f).tolist()}
json.dump(EO, open(os.path.join(OUT, 'eyes_meta.json'), 'w'))
qa['eye_centre_change_mm'] = round(float(np.linalg.norm(C - np.array(EM['L']['C'])) * 1000), 2)
json.dump(qa, open(os.path.join(OUT, 'sym_qa.json'), 'w'), indent=1)
print('SYMQA', json.dumps(qa))
