"""Dense face landmarks on the head: all 478 MediaPipe points, measured from several renders, symmetrised.

1. EEVEE renders of the (textured) head: front, yaw +-10 deg, pitch +-5 deg (painted brows and lips help the detector)
2. MediaPipe Face Landmarker (478 points) on each render; every point is shot back onto the mesh (ray from the
   orthographic camera through the pixel), giving 3D points per view
3. per point: median over views, and its spread (mm) = how much the detector disagrees with itself
4. eye contour points are kept only when they lie on the depth-detected eye rims (median < 2 mm, human-like eyes);
   on cartoon eyes MediaPipe draws a human-size eye inside the big one, so they are dropped (irises always)
5. left/right partners come from a fixed MediaPipe partner table (by point number); each pair is averaged and put
   back on the surface, centre points get x = 0, so the set is exactly symmetric even on a slightly asymmetric face
Writes <out.json> {index: [x, y, z]}, with '_spread_mm', '_pairs', '_dropped' and per-view 2D data for figures.
Usage: blender -b <textured.blend> -P dense_landmarks.py -- <out.json> [max_spread_mm=3] [landmarks.json]
"""
import bpy, sys, os, json, math, subprocess, tempfile
import numpy as np
from mathutils import Vector, Euler
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
sys.path.append(os.path.dirname(__file__))
class flm:                                   # paths of the MediaPipe helper (face_landmarks_mp reads argv on import)
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    PY = os.path.join(ROOT, '.tools', 'landmark-venv', 'Scripts', 'python.exe')
    MODEL = os.path.join(ROOT, '.tools', 'landmark-models', 'face_landmarker.task')
    DETECT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mp_detect.py')
    MP = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 8: 159, 9: 133, 10: 145,
          11: 362, 12: 386, 13: 263, 14: 374, 16: 1, 20: 61, 22: 291, 24: 152, 34: 13, 35: 14}

a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0]); MAXS = float(a[1]) if len(a) > 1 else 3.0
LMJ = a[2] if len(a) > 2 else None                  # head_prepare landmarks: frame the face, check the eye points
os.makedirs(os.path.dirname(OUT), exist_ok=True)
EYE = {263, 249, 390, 373, 374, 380, 381, 382, 362, 466, 388, 387, 386, 385, 384, 398,
       33, 7, 163, 144, 145, 153, 154, 155, 133, 246, 161, 160, 159, 158, 157, 173} | set(range(468, 478))
sc = bpy.context.scene
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try: sc.render.engine = eng; break
    except TypeError: pass
sc.render.resolution_x = sc.render.resolution_y = 1024; sc.view_settings.view_transform = 'Standard'
if not sc.world: sc.world = bpy.data.worlds.new('w')
sc.world.use_nodes = True; bg = sc.world.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1); bg.inputs[1].default_value = 0.6
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 1.4; so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (0.6, 0.1, -0.2)
for o in bpy.data.objects:
    if o.type == 'MESH' and o.data.shape_keys:
        for kb in o.data.shape_keys.key_blocks: kb.value = 0
    if o.name in ('lid_L', 'lid_R'): o.hide_render = True
face = bpy.data.objects['face']; eyes = bpy.data.objects.get('eyes')          # eyes are optional (test heads)
X = np.array([tuple(v.co) for v in face.data.vertices])
E = np.array([tuple(v.co) for v in eyes.data.vertices]) if eyes else np.zeros((0, 3))
F = [list(p.vertices) for p in face.data.polygons] + ([[i + len(X) for i in p.vertices] for p in eyes.data.polygons] if eyes else [])
bvh = BVHTree.FromPolygons([tuple(p) for p in np.r_[X, E]], F)
lo, hi = X.min(0), X.max(0); h = hi[2] - lo[2]
centre = Vector((0, 0, hi[2] - 0.40 * h)); size = 0.62 * h
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')} if LMJ and os.path.exists(LMJ) else {}
if all(k in LT for k in (2, 5, 24, 16)):
    # frame the face itself (full-body heads are small in a whole-figure frame): brow-to-chin height x 2.1
    top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]
    centre = Vector((0, 0, (top + LT[24][2]) / 2 + 0.05 * fh)); size = 2.1 * fh
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.ortho_scale = size; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
views = [(0, 0), (10, 0), (-10, 0), (0, 5), (0, -5)]                    # (yaw, pitch) degrees
tmp = tempfile.mkdtemp(); per = []; view2d = []
for yaw, pitch in views:
    rot = Euler((math.radians(pitch), 0, math.radians(yaw)), 'XYZ').to_matrix()
    d = rot @ Vector((0, -1, 0)); co.location = centre + d * 2
    co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    png = os.path.join(tmp, f'v{yaw}_{pitch}.png'); sc.render.filepath = png; bpy.ops.render.render(write_still=True)
    js = png + '.json'
    subprocess.run([flm.PY, '-I', flm.DETECT, png, flm.MODEL, js], check=True, capture_output=True)
    pts = json.load(open(js))
    if len(pts) < 468: per.append(None); continue
    M = co.matrix_world; fwd = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
    P = np.full((len(pts), 3), np.nan)
    for i, (u, v) in enumerate(pts):
        o = M @ Vector(((u - 0.5) * size, (0.5 - v) * size, 0))
        hit = bvh.ray_cast(o, fwd)
        if hit[0] is not None: P[i] = tuple(hit[0])
    per.append(P); view2d.append({'yaw': yaw, 'pitch': pitch, 'png': png, 'pts': pts})
ok = [p for p in per if p is not None]
S = np.stack(ok)                                                         # views x 478 x 3
med = np.nanmedian(S, 0); spread = np.nanmax(np.linalg.norm(S - med, axis=2), 0) * 1000
eye_ok = False
if all(k in LT for k in (7, 9, 11, 13)):
    from facelib import recentred_rim
    rims = []
    for ids in ((7, 9), (11, 13)):
        cx = np.mean([LT[k][0] for k in ids]); cz = np.mean([LT[k][2] for k in ids])
        try: rims.append(recentred_rim(bvh, cx, cz, 'margin'))
        except Exception: pass
    contour = [i for i in EYE if i < 468 and np.isfinite(med[i]).all()]
    if rims and contour:
        R = np.concatenate(rims); kd2 = KDTree(len(R))
        for k2, p in enumerate(R): kd2.insert(Vector(p), k2)
        kd2.balance()
        dd = np.array([kd2.find(Vector(med[i]))[2] for i in contour]) * 1000
        eye_ok = bool(np.median(dd) < 2.0)
        eye_rim_mm = round(float(np.median(dd)), 2)
    else:
        eye_rim_mm = None
else:
    eye_rim_mm = None
DROP = (set(range(468, 478)) if eye_ok else EYE)
keep = np.array([(i not in DROP) and np.isfinite(med[i]).all() and spread[i] <= MAXS for i in range(len(med))])
dropped = {'eye_or_iris': int(sum(1 for i in range(len(med)) if i in DROP)), 'eye_points_on_rim': eye_ok, 'eye_to_rim_mm': eye_rim_mm,
           'unsteady': int(sum(1 for i in range(len(med)) if i not in DROP and np.isfinite(med[i]).all() and spread[i] > MAXS)),
           'missed_mesh': int(sum(1 for i in range(len(med)) if not np.isfinite(med[i]).all()))}
# mirror partners from the fixed MediaPipe partner table (data/mp_mirror_pairs.json, found on symmetric heads):
# by point number, so an asymmetric face still pairs correctly. Each pair is averaged (exact symmetry), then
# put back on the surface; centre-line points get x = 0. Points without a partner are dropped.
PT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'mp_mirror_pairs.json')))
partner = {}
for i, j in PT['pairs']: partner[i] = j; partner[j] = i
centre_set = set(PT['centre'])
idx = np.nonzero(keep)[0]; kset = set(int(i) for i in idx)
sym = {}; pairs = {}; asym = []
def on_surface(p):
    h = bvh.find_nearest(Vector(p)); return np.array(h[0]) if h[0] is not None else p
for i in idx:
    i = int(i)
    if i in centre_set:
        q = med[i].copy(); q[0] = 0.0; sym[i] = on_surface(q); continue
    j = partner.get(i)
    if j is None or j not in kset: continue
    if i in sym: continue
    avg = (med[i] + med[j] * np.array([-1, 1, 1])) / 2
    pi = on_surface(avg); sym[i] = pi; sym[j] = on_surface(pi * np.array([-1, 1, 1]))
    pairs[i] = j; asym.append(np.linalg.norm(med[i] - med[j] * np.array([-1, 1, 1])) * 1000)
asym = np.array(asym); centre_pts = sum(1 for i in sym if i in centre_set)
unpaired = [int(i) for i in idx if int(i) not in sym]
out = {str(i): p.tolist() for i, p in sym.items()}
out['_raw'] = {str(i): med[i].tolist() for i in range(len(med)) if np.isfinite(med[i]).all()}   # unfiltered medians
out['_spread_mm'] = {str(int(i)): round(float(spread[i]), 2) for i in range(len(med)) if np.isfinite(spread[i])}
out['_pairs'] = pairs; out['_dropped'] = dropped
out['_qa'] = {'views': len(ok), 'kept': sum(1 for k in out if not k.startswith('_')), 'pairs': len(pairs), 'centre': centre_pts, 'unpaired_dropped': len(unpaired),
              'spread_mm_median': round(float(np.median(spread[keep])), 2),
              'mirror_gap_before_mm': {'median': round(float(np.median(asym)), 2), 'p95': round(float(np.percentile(asym, 95)), 2)} if len(asym) else None}
out['_front2d'] = {'size': size, 'centre_z': centre.z, 'pts': view2d[0]['pts'] if view2d else []}
json.dump(out, open(OUT, 'w'))
sc.render.filepath = os.path.splitext(OUT)[0] + '_front.png'
co.location = centre + Vector((0, -2, 0)); co.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.render.render(write_still=True)
print('DENSE', json.dumps(out['_qa']), json.dumps(dropped))
