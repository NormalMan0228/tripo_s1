"""Colour the original head from its reference images (the Tripo head was generated without texture).

front  MediaPipe on the reference front image <-> the head's own landmarks (same detector, same point numbers):
       similarity + 2D thin-plate spline from (x, z) to image pixels, so eyes, brows and lips land on their paint
left / right  silhouette fit: head top and the most forward point (nose tip) give scale and offset
back   same scale as the front, centred on the silhouette
(left, right and back are optional: a head with only 01_front.png gets the front view, the rest the skin median)
Each vertex mixes the views by how much it faces each camera (normal weight squared); a view is skipped where
the vertex is hidden from that camera (ray test against face + eyes). Colours are taken at the REST shape and
stored per vertex ('ref_color'), so expressions carry them along. The eyeballs get a front-projected UV map
and the front image (iris detail is finer than the eyeball vertices). Mouth interior, teeth, tongue, lid
shells get plain materials (the lid shells take the skin colour sampled above the eyes).
Writes <out.blend> (EEVEE materials set up) and <out>_qa.json (fit residuals in pixels).
Usage: blender -b <arkit.blend> -P project_texture.py -- <ref_dir> <landmarks.json> <out.blend>
"""
import bpy, sys, os, json, subprocess, tempfile
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(__file__))
class flm:                                   # paths of the MediaPipe helper (face_landmarks_mp reads argv on import)
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    PY = os.path.join(ROOT, '.tools', 'landmark-venv', 'Scripts', 'python.exe')
    MODEL = os.path.join(ROOT, '.tools', 'landmark-models', 'face_landmarker.task')
    DETECT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mp_detect.py')
    MP = {1: 70, 2: 105, 3: 107, 4: 336, 5: 334, 6: 300, 7: 33, 8: 159, 9: 133, 10: 145,
          11: 362, 12: 386, 13: 263, 14: 374, 16: 1, 20: 61, 22: 291, 24: 152, 34: 13, 35: 14}

a = sys.argv[sys.argv.index('--') + 1:]
REF, LMJ, OUT = a[0], a[1], os.path.abspath(a[2])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
def load_img(path):
    im = bpy.data.images.load(path, check_existing=True); w, h = im.size
    px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[::-1, :, :3]                       # Blender stores rows bottom-up, linear
    return np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(np.maximum(rgb, 0), 1 / 2.4) - 0.055) if im.colorspace_settings.name != 'sRGB' else rgb
imgs = {k: load_img(os.path.join(REF, f))            # side and back views are optional (test heads have a front only)
        for k, f in (('front', '01_front.png'), ('left', '02_left.png'), ('back', '03_back.png'), ('right', '04_right.png'))
        if k == 'front' or os.path.exists(os.path.join(REF, f))}
Hh, Ww = imgs['front'].shape[:2]
face = bpy.data.objects['face']; eyes = bpy.data.objects['eyes']
def rest(o):
    if o.data.shape_keys: return np.array([tuple(p.co) for p in o.data.shape_keys.key_blocks[0].data])
    return np.array([tuple(v.co) for v in o.data.vertices])
X = rest(face); E = rest(eyes)
qa = {}

# ---- front: MediaPipe on the image, our landmarks on the mesh
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
js = os.path.join(tempfile.mkdtemp(), 'f.json')
subprocess.run([flm.PY, '-I', flm.DETECT, os.path.join(REF, '01_front.png'), flm.MODEL, js], check=True, capture_output=True)
mp = json.load(open(js))
ids = [k for k in flm.MP if k in LT]
src = np.array([[LT[k][0], LT[k][2]] for k in ids]); dst = np.array([[mp[flm.MP[k]][0] * Ww, mp[flm.MP[k]][1] * Hh] for k in ids])
# similarity x' = s*x + tx, y' = -s*z + ty (image v grows downward)
M = np.zeros((2 * len(src), 3)); rhs = np.zeros(2 * len(src))
M[0::2, 0] = src[:, 0]; M[0::2, 1] = 1; rhs[0::2] = dst[:, 0]
M[1::2, 0] = -src[:, 1]; M[1::2, 2] = 1; rhs[1::2] = dst[:, 1]
(s_, tx, ty), *_ = np.linalg.lstsq(M, rhs, rcond=None)
simf = lambda P: np.c_[s_ * P[:, 0] + tx, -s_ * P[:, 1] + ty]
res_sim = np.linalg.norm(simf(src) - dst, axis=1)
def tps2(Xs, Ys, lam):
    n = len(Xs); r = np.linalg.norm(Xs[:, None] - Xs[None], axis=2); K = r * r * np.log(np.maximum(r, 1e-9))
    P_ = np.c_[np.ones(n), Xs]; L = np.zeros((n + 3, n + 3)); L[:n, :n] = K + lam * np.eye(n); L[:n, n:] = P_; L[n:, :n] = P_.T
    W_ = np.linalg.solve(L, np.r_[Ys, np.zeros((3, 2))])
    def f(Q):
        r = np.linalg.norm(Q[:, None] - Xs[None], axis=2); K = r * r * np.log(np.maximum(r, 1e-9))
        return K @ W_[:n] + W_[n] + Q @ W_[n + 1:]
    return f
tps = tps2(simf(src), dst, lam=50.0)                       # smooth warp in pixels: features match, no wobble
SP = simf(src); span_ = np.ptp(dst[:, 0])
def front_uv(P):                                           # 3D points use (x, z)
    # the warp is trusted near the landmarks only: away from them (head top, sides, neck) it fades into the
    # similarity, otherwise the thin-plate spline's extrapolation sends the skull to the clothes or the backdrop
    Q = simf(P[:, [0, 2]] if P.shape[1] == 3 else P); T_ = tps(Q)
    dmin = np.min(np.linalg.norm(Q[:, None] - SP[None], axis=2), 1)
    w = np.clip(1 - (dmin - 0.15 * span_) / (0.35 * span_), 0, 1)[:, None]
    return Q + w * (T_ - Q)
qa['front'] = {'points': len(ids), 'similarity_residual_px': round(float(res_sim.mean()), 1), 'scale_px_per_m': round(float(s_), 1)}

# ---- sides and back from the silhouette
def mask(im):
    bg = np.median(np.r_[im[:8].reshape(-1, 3), im[:, :8].reshape(-1, 3)], 0)
    return np.abs(im - bg).max(2) > 0.06
def side_fit(name, sign):
    m = mask(imgs[name]); rows = np.nonzero(m.any(1))[0]; vtop = rows.min()
    # nose tip: most forward silhouette point in the band where the mesh nose is
    z_top = X[:, 2].max(); vn_est = vtop + (z_top - LT[16][2]) * s_
    band = [r for r in range(int(vn_est - 0.05 * Hh), int(vn_est + 0.05 * Hh)) if 0 <= r < Hh and m[r].any()]
    cols = [(np.nonzero(m[r])[0].min() if sign < 0 else np.nonzero(m[r])[0].max(), r) for r in band]
    u_n, v_n = min(cols) if sign < 0 else max(cols)
    s2 = (v_n - vtop) / (z_top - LT[16][2])
    # u = u_n + sign_u * s2 * (y - y_nose): in 'left' the face is on the image left and +y runs right
    return lambda P: np.c_[u_n + (1 if sign < 0 else -1) * s2 * (P[:, 1] - LT[16][1]), v_n - s2 * (P[:, 2] - LT[16][2])], s2
views_uv = {'front': front_uv}
if 'left' in imgs: views_uv['left'], sL = side_fit('left', -1); qa.setdefault('side_scale_vs_front', {})['left'] = round(float(sL / s_), 3)
if 'right' in imgs: views_uv['right'], sR = side_fit('right', +1); qa.setdefault('side_scale_vs_front', {})['right'] = round(float(sR / s_), 3)
if 'back' in imgs:
    mb = mask(imgs['back']); rb = np.nonzero(mb.any(1))[0]; cb = np.nonzero(mb[rb.min() + int(0.15 * Hh)])[0]
    uc = (cb.min() + cb.max()) / 2
    views_uv['back'] = lambda P: np.c_[uc - s_ * P[:, 0], rb.min() + (X[:, 2].max() - P[:, 2]) * s_]

# ---- visibility per view + normal weights
me = face.data
def vnormals(P, polys):
    n = np.zeros_like(P)
    for p in polys:
        v = list(p.vertices); a_, b_, c_ = P[v[0]], P[v[1]], P[v[2]]
        n[v] += np.cross(b_ - a_, c_ - a_)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
N = vnormals(X, me.polygons)
allP = np.r_[X, E]; allF = [list(p.vertices) for p in me.polygons] + [[i + len(X) for i in p.vertices] for p in eyes.data.polygons]
bvh = BVHTree.FromPolygons([tuple(p) for p in allP], allF)
dirs = {'front': np.array([0, -1, 0.]), 'left': np.array([1, 0, 0.]), 'right': np.array([-1, 0, 0.]), 'back': np.array([0, 1, 0.])}
views = {k: (dirs[k], f) for k, f in views_uv.items()}
def bg_mask(im):
    """background = flood fill from the image border through smooth colour (studio backdrops are gradients; the
    figure's edge is a step), on a ~256 px copy. Returns (mask, stride)."""
    st_ = max(1, im.shape[1] // 256); a_ = im[::st_, ::st_]
    m = np.zeros(a_.shape[:2], bool); m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = True
    m &= np.abs(a_ - np.median(a_[0], 0)).max(2) < 0.25
    for _ in range(600):
        g = m.copy()
        for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
            nb = np.roll(m, sh, axis=ax); diff = np.abs(a_ - np.roll(a_, sh, axis=ax)).max(2)
            g |= nb & (diff < 0.02)
        if (g == m).all(): break
        m = g
    for _ in range(6):                                   # and the figure's edge band (anti-aliasing, rim light)
        m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    mx_, mn_ = a_.max(2), a_.min(2)                     # plus bright neutral grey anywhere (backdrop glow, rim light)
    m |= ((mx_ - mn_) / np.maximum(mx_, 1e-6) < 0.06) & (mx_ > 0.5)
    return m, st_
def sample(im, uv):
    u = np.clip(uv[:, 0], 0, Ww - 1); v = np.clip(uv[:, 1], 0, Hh - 1)
    u0, v0 = np.floor(u).astype(int), np.floor(v).astype(int); u1, v1 = np.minimum(u0 + 1, Ww - 1), np.minimum(v0 + 1, Hh - 1)
    fu, fv = (u - u0)[:, None], (v - v0)[:, None]
    return im[v0, u0] * (1 - fu) * (1 - fv) + im[v0, u1] * fu * (1 - fv) + im[v1, u0] * (1 - fu) * fv + im[v1, u1] * fu * fv
col = np.zeros((len(X), 3)); wsum = np.zeros(len(X))
for name, (d, uvf) in views.items():
    w = np.clip(N @ d, 0, None) ** 2 * (N @ d > 0.3)                 # grazing samples smear the silhouette
    vis = np.ones(len(X), bool)
    for i in np.nonzero(w > 1e-3)[0]:
        hit = bvh.ray_cast(Vector(X[i] + N[i] * 2e-4 + d * 2e-4), Vector(d))
        if hit[0] is not None and hit[3] > 3e-4: vis[i] = False
    w = w * vis
    if name == 'front': w = w * 1.5                                  # the front image is the sharpest one
    c_ = sample(imgs[name], uvf(X))
    # pixels of the image background (the mesh silhouette is a little wider than the painted one) are no colour
    bm_, st_ = bg_mask(imgs[name]); uv_ = uvf(X)
    bu = np.clip((uv_[:, 0] / st_).astype(int), 0, bm_.shape[1] - 1); bv = np.clip((uv_[:, 1] / st_).astype(int), 0, bm_.shape[0] - 1)
    w = w * ~bm_[bv, bu]
    col += w[:, None] * c_; wsum += w
skin_zone = (N @ np.array([0, -1, 0]) > 0.8) & (X[:, 2] > LT[22][2]) & (X[:, 2] < LT[8][2]) & (np.abs(X[:, 0]) < abs(LT[13][0] - LT[7][0]) / 2)
fallback = np.median(sample(imgs['front'], front_uv(X[skin_zone])), 0)         # cheeks: skin (a bust's clothes face the camera too)
col = np.where(wsum[:, None] > 1e-6, col / np.maximum(wsum, 1e-6)[:, None], fallback)
qa['no_view_verts'] = int((wsum <= 1e-6).sum())
at = me.color_attributes.get('ref_color') or me.color_attributes.new('ref_color', 'FLOAT_COLOR', 'POINT')
# the painted eye whites are wider than the mesh's eye openings: skin next to an opening that took white/grey
# (low saturation) or iris/lash dark paint is refilled from the surrounding skin (diffusion over the mesh)
import bmesh
bm = bmesh.new(); bm.from_mesh(me)
opening = np.array(sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts}))
nbr = [[] for _ in range(len(X))]
for e in bm.edges: i, j = e.verts[0].index, e.verts[1].index; nbr[i].append(j); nbr[j].append(i)
bm.free()
if os.environ.get('PT_DEBUG'): np.savez(os.environ['PT_DEBUG'], X=X, col=col, wsum=wsum)
# vertices no view saw (or seen only at a grazing angle) take their colour by diffusion over the mesh from their
# neighbours (front-only heads: sides and back)
have = wsum > 0.02; fill = col.copy()
# the skull (above the ear lobes) fills only from the skull and face, not up the neck from a collar or hood
head_ = X[:, 2] > LT[24][2] + 0.3 * (X[:, 2].max() - LT[24][2])
for pass_ in (True, False):
    for _ in range(400):
        todo = np.nonzero(~have & (head_ if pass_ else True))[0]
        if not len(todo): break
        new_ = [(i, fill[[j for j in nbr[i] if have[j] and (head_[j] or not pass_)]].mean(0)) for i in todo
                if any(have[j] and (head_[j] or not pass_) for j in nbr[i])]
        if not new_: break
        for i, c in new_: fill[i] = c; have[i] = True
col = np.where((wsum > 0.02)[:, None], col, fill)
opening = opening[(X[opening, 1] < np.percentile(X[:, 1], 30)) & (X[opening, 2] > LT[16][2])]   # eye openings only
if not len(opening) and 'eye_ring' in face.data.attributes:     # big-skulled heads: the openings sit behind the front 30 %
    er_ = np.abs(np.array([d.value for d in face.data.attributes['eye_ring'].data])); opening = np.nonzero(er_ == er_.max() - 2)[0]
from mathutils.kdtree import KDTree
kd = KDTree(len(opening))
for k, i in enumerate(opening): kd.insert(Vector(X[i]), k)
kd.balance()
d_open = np.array([kd.find(Vector(p))[2] for p in X])
mx, mn = col.max(1), col.min(1); sat = (mx - mn) / np.maximum(mx, 1e-6)
bad = (d_open < 0.022) & ((sat < 0.25) | (mx < 0.35))
qa['eye_paint_refilled_verts'] = int(bad.sum())
idx = np.nonzero(bad)[0]
for _ in range(300):
    col[idx] = np.array([col[nbr[i]].mean(0) if nbr[i] else col[i] for i in idx])
lin = np.where(col <= 0.04045, col / 12.92, ((col + 0.055) / 1.055) ** 2.4)   # images are sRGB, attributes are linear
at.data.foreach_set('color', np.c_[lin, np.ones(len(lin))].ravel().tolist())
me.color_attributes.active_color = at

# ---- eyes: front-projected UVs + the front image
uv = eyes.data.uv_layers.get('ref_uv') or eyes.data.uv_layers.new(name='ref_uv')
EU = front_uv(E)
for loop in eyes.data.loops:
    p = EU[loop.vertex_index]; uv.data[loop.index].uv = (p[0] / Ww, 1 - p[1] / Hh)
eyes.data.uv_layers.active = uv

# ---- materials (EEVEE)
def principled(name, base=None, attr=None, image=None, uvmap=None, rough=0.55):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value = rough
    nt.links.new(bs.outputs[0], out.inputs[0])
    if attr:
        ca = nt.nodes.new('ShaderNodeVertexColor'); ca.layer_name = attr; nt.links.new(ca.outputs['Color'], bs.inputs['Base Color'])
    elif image:
        tx_ = nt.nodes.new('ShaderNodeTexImage'); tx_.image = bpy.data.images.load(image, check_existing=True)
        um = nt.nodes.new('ShaderNodeUVMap'); um.uv_map = uvmap; nt.links.new(um.outputs[0], tx_.inputs[0])
        nt.links.new(tx_.outputs['Color'], bs.inputs['Base Color'])
    else:
        bs.inputs['Base Color'].default_value = base
    return m
skin_m = principled('ref_skin', attr='ref_color')
inner_m = principled('ref_mouth', base=(0.32, 0.06, 0.08, 1), rough=0.4)
for i, m in enumerate(me.materials):
    me.materials[i] = inner_m if (m and m.name in ('mouth_inner', 'ref_mouth')) else skin_m
eyes.data.materials.clear(); eyes.data.materials.append(principled('ref_eye', image=os.path.join(REF, '01_front.png'), uvmap='ref_uv', rough=0.15))
# skin above the eyes for the lid shells
# lid shells take the cheek skin, a little darker (the skin just above the eye carries lashes, liner and brows,
# which on big cartoon eyes reach far up)
lid_s = fallback * 0.92
lid_c = tuple(np.where(lid_s <= 0.04045, lid_s / 12.92, ((lid_s + 0.055) / 1.055) ** 2.4)) + (1,)
for n, c in (('lid_L', lid_c), ('lid_R', lid_c), ('teeth_up', (0.95, 0.94, 0.9, 1)), ('teeth_lo', (0.95, 0.94, 0.9, 1)), ('tongue', (0.75, 0.32, 0.36, 1))):
    o = bpy.data.objects.get(n)
    if not o: continue
    gums = [i for i, m in enumerate(o.data.materials) if m and m.name.startswith('gums')]   # organ_teeth v2: slot 1 = gums
    o.data.materials.clear(); o.data.materials.append(principled('ref_' + n, base=c, rough=0.5))
    if gums: o.data.materials.append(principled('ref_gums', base=(0.62, 0.17, 0.19, 1), rough=0.45))
# figure data: where our landmarks, eye-opening edges and silhouette land on the front image
bm_edges = set()
import bmesh
bm = bmesh.new(); bm.from_mesh(me)
bnd = sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts}); bm.free()
bnd = [i for i in bnd if X[i, 1] < np.percentile(X[:, 1], 30)]
qa['_overlay'] = {'landmarks_img': dst.tolist(), 'landmarks_mesh': front_uv(src3 := np.array([LT[k] for k in ids])).tolist(),
                  'openings': front_uv(X[bnd]).tolist()}
json.dump(qa, open(os.path.splitext(OUT)[0] + '_qa.json', 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('TEXTURED', json.dumps({k: v for k, v in qa.items() if not k.startswith('_')}))
