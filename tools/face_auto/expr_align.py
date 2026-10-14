"""T7 · put an expression scan (a new Tripo head with eyes closed, or mouth open) on top of the rigged original.

Only rotation, translation and one uniform scale are solved (no bending), so the scan keeps its own shape. The fit
uses the parts of the face the expression should not move:
  blink  everything except a band around both eye openings
  aa     the skull above the brows, the ears and the nose (the jaw, lips and, in our "Ah" image, the brows move)
Start: landmark similarity (Umeyama) on the stable landmarks, then trimmed ICP (closest points, worst 20 % dropped).
Writes <out>/<name>_aligned.blend (object 'scan' in the original's space) and <out>/<name>_align.json
(transform, residual on the stable region = how much the two generations differ where nothing should move).
Usage: blender -b <rig_mouth.blend> -P expr_align.py -- <scan.fbx> <scan_landmarks.json> <orig_landmarks.json>
                                                        <eyes_meta.json> <blink|aa> <out_dir> <name>
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector, Matrix
sys.path.append(os.path.dirname(__file__))
from facelib import bvh_of, dist_to

a = sys.argv[sys.argv.index('--') + 1:]
SCAN, SLM, OLM, EYES, MODE, OUT, NAME = a[:7]
OUT = os.path.abspath(OUT); os.makedirs(OUT, exist_ok=True)
face = bpy.data.objects['face']
P0 = np.array([tuple(v.co) for v in face.data.vertices])
F0 = [list(p.vertices) for p in face.data.polygons]
inner = {i for i, m in enumerate(face.data.materials) if m and m.name == 'mouth_inner'}
skin_v = np.zeros(len(P0), bool)
for p in face.data.polygons:
    if p.material_index not in inner: skin_v[list(p.vertices)] = True
LO = {int(k): np.array(v) for k, v in json.load(open(OLM)).items() if not k.startswith('_')}
LS = {int(k): np.array(v) for k, v in json.load(open(SLM)).items() if not k.startswith('_')}
eyes = json.load(open(EYES))

old = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=SCAN)
new = [o for o in bpy.data.objects if o not in old and o.type == 'MESH']
scan = new[0]; scan.name = 'scan'
for o in bpy.data.objects:
    if o not in old and o is not scan: bpy.data.objects.remove(o)
scan.data.transform(scan.matrix_world); scan.matrix_world = Matrix()
S = np.array([tuple(v.co) for v in scan.data.vertices]); FS = [list(p.vertices) for p in scan.data.polygons]
bvh_s = bvh_of(S, FS)

# stable region on the original (skin only, every 6th vertex)
rims = np.concatenate([np.array(eyes[s]['raw']) for s in 'RL'])
d_rim = dist_to([Vector(p) for p in rims], [Vector(p) for p in P0]) * 1000
brow_z = max(LO[k][2] for k in (1, 2, 3, 4, 5, 6))
if MODE == 'blink':
    stable = skin_v & (d_rim > 14)
    lm_ids = [1, 2, 3, 4, 5, 6, 16, 20, 22, 24, 31]
else:
    xmax = np.abs(P0[np.abs(P0[:, 2] - LO[8][2]) < 0.01, 0]).max()
    stable = skin_v & ((P0[:, 2] > brow_z + 0.015) | (np.linalg.norm(P0 - LO[16], axis=1) < 0.016) | (np.abs(P0[:, 0]) > 0.86 * xmax))
    stable &= d_rim > 14
    lm_ids = [7, 9, 11, 13, 16, 31]
idx = np.nonzero(stable)[0][::6]
X = P0[idx]

def umeyama(A, B):
    """similarity s,R,t with s R A + t ~ B"""
    ma, mb = A.mean(0), B.mean(0); A0, B0 = A - ma, B - mb
    U, D, Vt = np.linalg.svd(B0.T @ A0 / len(A))
    Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ Sg @ Vt; s = np.trace(np.diag(D) @ Sg) / (A0 ** 2).sum(1).mean()
    return s, R, mb - s * R @ ma

ids = [k for k in lm_ids if k in LS and k in LO]
s, R, t = umeyama(np.array([LS[k] for k in ids]), np.array([LO[k] for k in ids]))
log = [{'start': 'landmarks', 'ids': ids, 'scale': round(float(s), 4)}]
for it in range(40):
    # closest point on the scan for every stable original point (in scan space), then map back
    Xs = ((X - t) @ R) / s
    Q = np.array([tuple(bvh_s.find_nearest(Vector(p))[0]) for p in Xs])
    d = np.linalg.norm(s * Q @ R.T + t - X, axis=1)
    keep = d <= np.percentile(d, 80)
    s2, R2, t2 = umeyama(Q[keep], X[keep])
    step = abs(s2 - s) + np.abs(R2 - R).max() + np.abs(t2 - t).max()
    s, R, t = s2, R2, t2
    if it % 5 == 0 or step < 1e-7:
        log.append({'it': it, 'rms_mm_kept': round(float(np.sqrt((d[keep] ** 2).mean()) * 1000), 3)})
    if step < 1e-7: break
# apply to the scan mesh
M = Matrix(((s * R).tolist()[0] + [t[0]], (s * R).tolist()[1] + [t[1]], (s * R).tolist()[2] + [t[2]], (0, 0, 0, 1)))
scan.data.transform(M)
S2 = np.array([tuple(v.co) for v in scan.data.vertices]); bvh2 = bvh_of(S2, FS)
dd = np.array([bvh2.find_nearest(Vector(p))[3] for p in P0[np.nonzero(stable)[0][::3]]]) * 1000
res = {'mode': MODE, 'scale': float(s), 'R': R.tolist(), 't': t.tolist(), 'iterations': log,
       'stable_residual_mm': {'mean': round(float(dd.mean()), 3), 'p50': round(float(np.median(dd)), 3),
                              'p95': round(float(np.percentile(dd, 95)), 3)},
       'stable_points': int(stable.sum())}
json.dump(res, open(os.path.join(OUT, NAME + '_align.json'), 'w'), indent=1)
for o in list(bpy.data.objects):
    if o.name not in ('scan', 'face'): bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + '_aligned.blend'), compress=True)
print('ALIGNED', NAME, json.dumps(res['stable_residual_mm']), 'scale', round(float(s), 4), log[-1])
