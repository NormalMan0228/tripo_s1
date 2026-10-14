"""Face landmarks without Character Creator: front render -> MediaPipe Face Landmarker -> rays onto the mesh.

Writes the Headshot-style point subset the fitter needs (brows 1-6, eye corners/lids 7-14, nose tip 16, mouth
corners 20/22, chin 24, crown 31, inner lips 34/35) as JSON {"1": [x, y, z], ...}. The head must face -Y, Z up.
MediaPipe assumes human-size eyes, so on big cartoon eyes its lid points sit near the eye centre; the fitter only
uses them as a start point and finds the real lid rim from depth.
Usage: blender -b --factory-startup -P face_landmarks_mp.py -- <head.fbx|glb|blend> <out.json> [debug.png]
"""
import bpy, sys, os, json, subprocess, tempfile, shutil
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], a[1]
DEBUG = a[2] if len(a) > 2 else None
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PY = os.path.join(ROOT, ".tools", "landmark-venv", "Scripts", "python.exe")
MODEL = os.path.join(ROOT, ".tools", "landmark-models", "face_landmarker.task")
MP = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 8: 159, 9: 133, 10: 145,
      11: 362, 12: 386, 13: 263, 14: 374, 16: 1, 20: 61, 22: 291, 24: 152, 34: 13, 35: 14}
DETECT = os.path.join(os.path.dirname(__file__), "mp_detect.py")


def load(src):
    if src.lower().endswith('.blend'):
        bpy.ops.wm.open_mainfile(filepath=src)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        (bpy.ops.import_scene.fbx if src.lower().endswith('.fbx') else bpy.ops.import_scene.gltf)(filepath=src)
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for k in o.data.shape_keys.key_blocks: k.value = 0.0
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render]


def detect(png):
    js = png + '.json'
    subprocess.run([PY, '-I', DETECT, png, MODEL, js], check=True, capture_output=True)
    return json.load(open(js))


def front_landmarks(obs, out_png=None):
    V = np.vstack([np.array([tuple(o.matrix_world @ v.co) for v in o.data.vertices]) for o in obs])
    F, off = [], 0
    for o in obs:
        F += [[off + i for i in p.vertices] for p in o.data.polygons]; off += len(o.data.vertices)
    bvh = BVHTree.FromPolygons([Vector(v) for v in V], F)
    lo, hi = V.min(0), V.max(0); h, wdt = hi[2] - lo[2], hi[0] - lo[0]; cx = 0.5 * (lo[0] + hi[0])
    # a few framings; the real face is the detection with the widest eye spacing in world units
    framings = [(max(h, wdt) * 1.05, 0.5 * (lo[2] + hi[2])), (h * 0.62, hi[2] - h * 0.62 * 0.55), (h * 0.7, lo[2] + h * 0.45)]
    if h > 1.5 * wdt: framings = [(wdt * 1.1, hi[2] - wdt * 0.55)] + framings
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 1024
    sc.display.shading.light = 'STUDIO'; sc.display.shading.show_cavity = True
    if not sc.world: sc.world = bpy.data.worlds.new('w')
    cam = bpy.data.cameras.new('lmcam'); cam.type = 'ORTHO'
    co = bpy.data.objects.new('lmcam', cam); sc.collection.objects.link(co); sc.camera = co
    co.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
    tmp = tempfile.mkdtemp(); best = None
    for k, (size_, cz_) in enumerate(framings):
        cam.ortho_scale = size_; co.location = Vector((cx, lo[1] - 1.0, cz_))
        png = os.path.join(tmp, 'front%d.png' % k); sc.render.filepath = png; bpy.ops.render.render(write_still=True)
        L_ = detect(png)
        if not L_: continue
        eye = abs(L_[33][0] - L_[263][0]) * size_
        if best is None or eye > best[0]: best = (eye, L_, size_, cz_, png)
    bpy.data.objects.remove(co)
    if best is None: return None
    _, L, size, cz, png = best
    if out_png: shutil.copy(png, out_png)
    def to3d(u, v):
        x = cx + (u - 0.5) * size; z = cz - (v - 0.5) * size
        loc = bvh.ray_cast(Vector((x, lo[1] - 1.0, z)), Vector((0, 1, 0)))[0]
        return [x, loc.y if loc else float(lo[1]), z]
    pts = {str(k): to3d(*L[i][:2]) for k, i in MP.items()}
    mid = V[np.abs(V[:, 0] - cx) < (hi[0] - lo[0]) * 0.01]
    pts['31'] = mid[np.argmax(mid[:, 2])].tolist()
    for p, q in [(1, 6), (2, 5), (3, 4), (7, 13), (8, 12), (9, 11), (10, 14), (20, 22)]:
        P, Q = np.array(pts[str(p)]), np.array(pts[str(q)])
        avg = (P + Q * [-1, 1, 1] + [2 * cx, 0, 0]) / 2
        pts[str(p)] = avg.tolist(); pts[str(q)] = (avg * [-1, 1, 1] + [2 * cx, 0, 0]).tolist()
    for k in (16, 24, 34, 35):
        pts[str(k)][0] = cx
        loc = bvh.ray_cast(Vector((cx, lo[1] - 1.0, pts[str(k)][2])), Vector((0, 1, 0)))[0]
        if loc: pts[str(k)][1] = loc.y
    pts['_score'] = L[0][2] if len(L[0]) > 2 else 1.0
    return pts


if __name__ == "__main__":
    obs = load(SRC)
    pts = front_landmarks(obs, DEBUG)
    if pts is None: raise SystemExit('LANDMARKS: no face found')
    json.dump(pts, open(OUT, 'w'), indent=1)
    print('LANDMARKS', len(pts), OUT)
