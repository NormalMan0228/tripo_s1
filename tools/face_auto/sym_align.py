"""Stand a prepared head up straight by its own facial symmetry (Tripo heads can come out turned a few degrees).

MediaPipe (478 points) on a front render, shot back onto the mesh; data/mp_mirror_pairs.json lists which points
are left/right partners (found on symmetric heads). The symmetry plane: its normal is the main direction of the
partner differences, it passes through the mean of their midpoints and of the centre-line points. The head is
rotated so that normal becomes +X and shifted so the plane is x = 0. Two rounds (the detection improves once the
face looks straight at the camera). The mesh shape is not changed, only placed (rotation + translation).
Writes <out.fbx> and <out>_landmarks.json (the input landmarks moved the same way), <out>_sym.json.
Usage: blender -b --factory-startup -P sym_align.py -- <prepared.fbx> <landmarks.json> <out.fbx>
"""
import bpy, sys, os, json, math, subprocess, tempfile
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
SRC, LMJ, OUT = a[0], a[1], os.path.abspath(a[2])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PY = os.path.join(ROOT, '.tools', 'landmark-venv', 'Scripts', 'python.exe')
MODEL = os.path.join(ROOT, '.tools', 'landmark-models', 'face_landmarker.task')
DETECT = os.path.join(HERE, 'mp_detect.py')
PAIRS = json.load(open(os.path.join(HERE, 'data', 'mp_mirror_pairs.json')))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
ob = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
ob.data.transform(ob.matrix_world); ob.matrix_world = Matrix()
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
extra = {k: v for k, v in json.load(open(LMJ)).items() if k.startswith('_')}
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 1024
sc.display.shading.light = 'STUDIO'; sc.display.shading.show_cavity = True
if not sc.world: sc.world = bpy.data.worlds.new('w')
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
tmp = tempfile.mkdtemp(); log = []

def detect3d():
    X = np.array([tuple(v.co) for v in ob.data.vertices]); F = [list(p.vertices) for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons([tuple(p) for p in X], F)
    top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]
    size = 2.1 * fh; cz = (top + LT[24][2]) / 2 + 0.05 * fh; cx = (LT[7][0] + LT[13][0]) / 2
    cam.ortho_scale = size; co.location = Vector((cx, -2, cz)); co.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
    png = os.path.join(tmp, f'v{len(log)}.png'); sc.render.filepath = png; bpy.ops.render.render(write_still=True)
    subprocess.run([PY, '-I', DETECT, png, MODEL, png + '.json'], check=True, capture_output=True)
    pts = json.load(open(png + '.json'))
    P = np.full((len(pts), 3), np.nan)
    for i, (u, v) in enumerate(pts):
        h = bvh.ray_cast(Vector((cx + (u - 0.5) * size, -2, cz + (0.5 - v) * size)), Vector((0, 1, 0)))
        if h[0] is not None: P[i] = tuple(h[0])
    return P

for rnd in range(2):
    P = detect3d()
    if not np.isfinite(P).any(): break
    pr = [(i, j) for i, j in PAIRS['pairs'] if i < len(P) and j < len(P) and np.isfinite(P[i]).all() and np.isfinite(P[j]).all()]
    D = np.array([P[i] - P[j] for i, j in pr]); Mid = np.array([(P[i] + P[j]) / 2 for i, j in pr])
    C = np.array([P[k] for k in PAIRS['centre'] if k < len(P) and np.isfinite(P[k]).all()])
    # left/right orientation is arbitrary per pair: align the differences before the principal direction
    s0 = np.sign(D[:, 0]); s0[s0 == 0] = 1; D = D * s0[:, None]
    n = np.linalg.svd(D - 0 * D.mean(0), full_matrices=False)[2][0]; n = n if n[0] > 0 else -n
    c = np.r_[Mid, C].mean(0)
    gap_before = float(np.median(np.abs((np.r_[Mid, C] - c) @ n)) * 1000)
    # rotation n -> +X (smallest), then shift the plane to x = 0
    R = Vector(tuple(n)).rotation_difference(Vector((1, 0, 0))).to_matrix().to_4x4()
    T = Matrix.Translation(Vector((-(R @ Vector(tuple(c))).x, 0, 0))) @ R
    ob.data.transform(T)
    for k in LT: LT[k] = np.array(T @ Vector(tuple(LT[k])))
    ang = math.degrees(math.acos(max(-1, min(1, n[0]))))
    yaw = math.degrees(math.atan2(n[1], n[0])); roll = math.degrees(math.atan2(n[2], n[0]))
    log.append({'round': rnd, 'pairs': len(pr), 'tilt_deg': round(ang, 2), 'yaw_deg': round(yaw, 2), 'roll_deg': round(roll, 2),
                'plane_spread_mm': round(gap_before, 2), 'shift_mm': round(float(c @ n) * 1000, 2)})
# check: mirror gap of the partner points after alignment
P = detect3d()
pr = [(i, j) for i, j in PAIRS['pairs'] if np.isfinite(P[i]).all() and np.isfinite(P[j]).all()]
gap = np.array([np.linalg.norm(P[i] - P[j] * np.array([-1, 1, 1])) for i, j in pr]) * 1000
res = {'rounds': log, 'mirror_gap_after_mm': {'median': round(float(np.median(gap)), 2), 'p95': round(float(np.percentile(gap, 95)), 2)}}
for o in list(bpy.data.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, apply_unit_scale=True, bake_space_transform=False, add_leaf_bones=False)
json.dump({**{str(k): v.tolist() for k, v in LT.items()}, **extra}, open(os.path.splitext(OUT)[0] + '_landmarks.json', 'w'))
json.dump(res, open(os.path.splitext(OUT)[0] + '_sym.json', 'w'), indent=1)
print('SYM', json.dumps(res))
