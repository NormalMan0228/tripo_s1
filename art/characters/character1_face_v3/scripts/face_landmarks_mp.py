"""CC-free face landmarks for wrap_anime_head.py: front render -> MediaPipe Face Landmarker -> rays onto the mesh.

Writes the subset of the Headshot 35-point scheme the wrap needs (brows 1-6, eye corners/lids 7-14, nose tip 16,
mouth corners 20/22, chin 24, crown 31, inner lips 34/35) as JSON {"1": [x, y, z], ...} in the mesh's own units.
MediaPipe assumes human-size eyes, so its lid points sit too close to the eye centre on big cartoon eyes; the wrap
only uses them as hints and finds the real lid rim from depth.
Usage: blender -b --factory-startup -P face_landmarks_mp.py -- <head.fbx> <out.json>
Needs .tools/landmark-venv (mediapipe) and .tools/landmark-models/face_landmarker.task.
"""
import bpy, sys, os, json, subprocess, tempfile
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], a[1]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 4))
PY = os.path.join(ROOT, ".tools", "landmark-venv", "Scripts", "python.exe")
MODEL = os.path.join(ROOT, ".tools", "landmark-models", "face_landmarker.task")
# MediaPipe face-mesh index for each Headshot point (person's right = image left = -X)
MP = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 8: 159, 9: 133, 10: 145,
      11: 362, 12: 386, 13: 263, 14: 374, 16: 1, 20: 61, 22: 291, 24: 152, 34: 13, 35: 14}
DETECT = r'''
import sys, json, numpy as np, mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
from PIL import Image
img, model, out = sys.argv[1:4]
det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
    base_options=mpt.BaseOptions(model_asset_path=model), num_faces=1,
    min_face_detection_confidence=0.2, min_face_presence_confidence=0.2))
im = Image.open(img).convert('RGB')
res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(im)))
json.dump([[p.x, p.y] for p in res.face_landmarks[0]] if res.face_landmarks else [], open(out, 'w'))
'''

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC) if SRC.lower().endswith('.fbx') else bpy.ops.import_scene.gltf(filepath=SRC)
ob = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
V = np.array([tuple(ob.matrix_world @ v.co) for v in ob.data.vertices])
bvh = BVHTree.FromPolygons([Vector(v) for v in V], [list(p.vertices) for p in ob.data.polygons])
lo, hi = V.min(0), V.max(0)
# frame the face: the upper 70 % of the mesh height, square, centred on x = 0
size = (hi[2] - lo[2]) * 0.62; cz = hi[2] - size * 0.55; cx = 0.5 * (lo[0] + hi[0])
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 1024
sc.display.shading.light = 'STUDIO'; sc.display.shading.show_cavity = True
sc.world = bpy.data.worlds.new('w')
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.ortho_scale = size
co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
co.location = Vector((cx, lo[1] - 1.0, cz)); co.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
tmp = tempfile.mkdtemp()
png, js, det = os.path.join(tmp, 'front.png'), os.path.join(tmp, 'mp.json'), os.path.join(tmp, 'detect.py')
sc.render.filepath = png; bpy.ops.render.render(write_still=True)
open(det, 'w').write(DETECT)
subprocess.run([PY, '-I', det, png, MODEL, js], check=True, capture_output=True)
L = json.load(open(js))
if not L: raise SystemExit('LANDMARKS: no face found')

def to3d(u, v):
    x = cx + (u - 0.5) * size; z = cz - (v - 0.5) * size
    loc = bvh.ray_cast(Vector((x, lo[1] - 1.0, z)), Vector((0, 1, 0)))[0]
    return [x, loc.y if loc else float(lo[1]), z]
pts = {str(k): to3d(*L[i]) for k, i in MP.items()}
mid = V[np.abs(V[:, 0] - cx) < (hi[0] - lo[0]) * 0.01]
pts['31'] = mid[np.argmax(mid[:, 2])].tolist()
# symmetrise left/right pairs and put midline points on x = cx (Tripo heads are close to symmetric)
pairs = [(1, 6), (2, 5), (3, 4), (7, 13), (8, 12), (9, 11), (10, 14), (20, 22)]
for p, q in pairs:
    P, Q = np.array(pts[str(p)]), np.array(pts[str(q)])
    avg = (P + Q * [-1, 1, 1] + [2 * cx, 0, 0]) / 2
    pts[str(p)] = avg.tolist(); pts[str(q)] = (avg * [-1, 1, 1] + [2 * cx, 0, 0]).tolist()
for k in (16, 24, 34, 35):
    pts[str(k)][0] = cx
    loc = bvh.ray_cast(Vector((cx, lo[1] - 1.0, pts[str(k)][2])), Vector((0, 1, 0)))[0]
    if loc: pts[str(k)][1] = loc.y
json.dump(pts, open(OUT, 'w'), indent=1)
print('LANDMARKS', len(pts), OUT)
