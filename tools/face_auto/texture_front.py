"""Colour a prepared head from the single front image it was generated from (test heads without texture).

Alignment, image pixels <- head (x, z):
  1. MediaPipe on the image and the head's own landmarks (<name>_landmarks.json from head_prepare): similarity
     on the stable points (eye corners, nose tip, mouth corners, chin, brows); accepted when the mean residual is
     under 2.5 % of the eye span
  2. otherwise the head silhouette: top of the head and the head width at the widest row of the top 18 % of the
     figure (works for busts and full bodies)
Every vertex facing the camera and not hidden takes the image colour; the rest is filled by diffusion over the
mesh from its coloured neighbours. Stored as linear 'ref_color'; an EEVEE material shows it.
Writes <out.blend> (object 'face') and <out>_tex.json (method, residual).
Usage: blender -b --factory-startup -P texture_front.py -- <prepared.fbx> <landmarks.json> <front.png> <out.blend>
"""
import bpy, bmesh, sys, os, json, subprocess, tempfile
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
SRC, LMJ, IMG, OUT = a[0], a[1], a[2], os.path.abspath(a[3])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PY = os.path.join(ROOT, '.tools', 'landmark-venv', 'Scripts', 'python.exe')
MODEL = os.path.join(ROOT, '.tools', 'landmark-models', 'face_landmarker.task')
DETECT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mp_detect.py')
MP = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 9: 133, 11: 362, 13: 263, 16: 1, 20: 61, 22: 291, 24: 152}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
ob = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]; ob.name = 'face'
ob.data.transform(ob.matrix_world); ob.matrix_world.identity()
me = ob.data
X = np.array([tuple(v.co) for v in me.vertices]); F = [list(p.vertices) for p in me.polygons]
im = bpy.data.images.load(IMG); W, H = im.size
px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px); img = px.reshape(H, W, 4)[::-1, :, :3]
info = {}

# ---- alignment
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')} if os.path.exists(LMJ) else {}
js = os.path.join(tempfile.mkdtemp(), 'f.json')
subprocess.run([PY, '-I', DETECT, IMG, MODEL, js], check=True, capture_output=True)
mp = json.load(open(js))
fit = None
if mp and LT:
    ids = [k for k in MP if k in LT]
    src = np.array([[LT[k][0], LT[k][2]] for k in ids]); dst = np.array([[mp[MP[k]][0] * W, mp[MP[k]][1] * H] for k in ids])
    M = np.zeros((2 * len(src), 3)); r = np.zeros(2 * len(src))
    M[0::2, 0] = src[:, 0]; M[0::2, 1] = 1; r[0::2] = dst[:, 0]
    M[1::2, 0] = -src[:, 1]; M[1::2, 2] = 1; r[1::2] = dst[:, 1]
    (s_, tx, ty), *_ = np.linalg.lstsq(M, r, rcond=None)
    res = np.linalg.norm(np.c_[s_ * src[:, 0] + tx, -s_ * src[:, 1] + ty] - dst, axis=1).mean()
    span = abs(dst[ids.index(13), 0] - dst[ids.index(7), 0]) if 13 in ids and 7 in ids else W * 0.2
    info['landmark_fit'] = {'points': len(ids), 'residual_px': round(float(res), 1), 'eye_span_px': round(float(span), 1)}
    if s_ > 0 and res < 0.025 * span * 4:
        fit = (s_, tx, ty); info['method'] = 'landmarks'
if fit is None:
    bg = np.median(np.r_[img[:6].reshape(-1, 3), img[:, :6].reshape(-1, 3)], 0)
    m = np.abs(img - bg).max(2) > 0.06
    rows = np.nonzero(m.any(1))[0]; vtop, vbot = rows.min(), rows.max()
    band = range(vtop, vtop + int(0.18 * (vbot - vtop)))
    wimg = max((np.nonzero(m[r])[0].ptp() for r in band if m[r].any()), default=1)
    z_top = X[:, 2].max(); hz = X[:, 2] > z_top - 0.18 * np.ptp(X[:, 2])
    zs = np.linspace(z_top - 0.18 * np.ptp(X[:, 2]), z_top, 40)
    wmesh = max(np.ptp(X[np.abs(X[:, 2] - z) < 0.002, 0]) if (np.abs(X[:, 2] - z) < 0.002).sum() > 3 else 0 for z in zs)
    s_ = wimg / max(wmesh, 1e-6)
    cols = np.nonzero(m[vtop + int(0.1 * (vbot - vtop))])[0]
    tx = (cols.min() + cols.max()) / 2; ty = vtop + s_ * z_top
    fit = (s_, tx, ty); info['method'] = 'silhouette'
s_, tx, ty = fit
uv = lambda P: np.c_[s_ * P[:, 0] + tx, -s_ * P[:, 2] + ty]

# ---- colours: front-facing and visible vertices sample the image, the rest diffuse from neighbours
n = np.zeros_like(X)
for f in F:
    a_, b_, c_ = X[f[0]], X[f[1]], X[f[2]]; n[f] += np.cross(b_ - a_, c_ - a_)
n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
bvh = BVHTree.FromPolygons([tuple(p) for p in X], F)
facing = -n[:, 1] > 0.15
vis = facing.copy()
for i in np.nonzero(facing)[0]:
    h = bvh.ray_cast(Vector(X[i] + n[i] * 2e-4 + np.array([0, -2e-4, 0])), Vector((0, -1, 0)))
    if h[0] is not None and h[3] > 3e-4: vis[i] = False
UV = uv(X); inside = (UV[:, 0] >= 0) & (UV[:, 0] < W - 1) & (UV[:, 1] >= 0) & (UV[:, 1] < H - 1)
known = vis & inside
col = np.zeros((len(X), 3))
u, v = UV[known, 0], UV[known, 1]
u0, v0 = np.floor(u).astype(int), np.floor(v).astype(int); fu, fv = (u - u0)[:, None], (v - v0)[:, None]
col[known] = img[v0, u0] * (1 - fu) * (1 - fv) + img[v0, u0 + 1] * fu * (1 - fv) + img[v0 + 1, u0] * (1 - fu) * fv + img[v0 + 1, u0 + 1] * fu * fv
# blend weight toward grazing angles so silhouettes do not smear background colour
w = np.clip((-n[:, 1] - 0.15) / 0.35, 0, 1)
bm = bmesh.new(); bm.from_mesh(me); nbr = [[] for _ in range(len(X))]
for e in bm.edges: i, j = e.verts[0].index, e.verts[1].index; nbr[i].append(j); nbr[j].append(i)
bm.free()
fill = col.copy(); have = known.copy()
for _ in range(400):
    todo = np.nonzero(~have)[0]
    if not len(todo): break
    new = [(i, fill[[j for j in nbr[i] if have[j]]].mean(0)) for i in todo if any(have[j] for j in nbr[i])]
    for i, c in new: fill[i] = c; have[i] = True
skin = np.median(col[known & (w > 0.9)], 0) if (known & (w > 0.9)).any() else np.array([0.8, 0.7, 0.6])
fill[~have] = skin
col = np.where(known[:, None], w[:, None] * col + (1 - w[:, None]) * fill, fill)
lin = np.where(col <= 0.04045, col / 12.92, ((col + 0.055) / 1.055) ** 2.4)
at = me.color_attributes.new('ref_color', 'FLOAT_COLOR', 'POINT'); at.data.foreach_set('color', np.c_[lin, np.ones(len(lin))].ravel().tolist())
me.color_attributes.active_color = at
mat = bpy.data.materials.new('ref_skin'); mat.use_nodes = True; nt = mat.node_tree
bs = nt.nodes['Principled BSDF']; bs.inputs['Roughness'].default_value = 0.55
vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'ref_color'; nt.links.new(vc.outputs['Color'], bs.inputs['Base Color'])
me.materials.clear(); me.materials.append(mat)
info['coloured_from_image'] = round(float(known.mean()), 3)
json.dump(info, open(os.path.splitext(OUT)[0] + '_tex.json', 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('TEXFRONT', json.dumps(info))
