"""M1 · mouth organ (v2): a ring-topology mouth built into a featureless head (eyes/mouth removed, aligned to its
original head by align_noface.py). Same building blocks as organ_eye v2 (organ_lib: ray chart, level-set cut,
per-angle hole curve, zipper bridge, depth grid).

1. Lip contours: MediaPipe outer (61-291) and inner (78-308) lip lines measured on the original's renders
   (dense_landmarks), made symmetric; the closed-mouth seam is the mean of the inner upper and lower lines.
2. Ray chart from a point 1.5 mouth widths behind the lips (rays reach the corners where the face turns away).
3. Hole: an egg round the outer lip line (sides 0.45 half-width, halfway up to the nose and down to the chin),
   shrunk per angle where the surface point would lie too far from the lip line in 3D; cut exactly along it.
4. Rings, all with M points at the same parameter u (0 = +x corner, 0.25 top, 0.5 = -x corner, 0.75 bottom):
   rings 1..K_SKIN on chart lines from the hole curve to the outer lip line, rings K_SKIN+1..K from the outer lip
   line to the seam. The innermost ring is the slit: its upper half (u < 0.5) and lower half lie on the same seam
   line but are different vertices, joined only at the corners. The hole boundary is zipped to ring 1 by angle.
5. Depth along each ray: SHAPE=orig blends the featureless surface (ring 1) into the original's sculpted lips;
   SHAPE=proc keeps the featureless surface and adds a lip bulge. The depth grid is smoothed (lumpy Tripo lips).
6. Behind the slit: 2 inner-lip rings (lip thickness) and an oral cavity (4 rings + cap, material mouth_inner:
   palate above, floor below, out toward the cheeks), all with the same u, so the interior pairs left/right.
Vertex groups mouth_upper, mouth_lower, mouth_skin, mouth_bag, mouth_slit_upper, mouth_slit_lower; point
attributes mouth_ring, mouth_u. Writes <out.blend> and <out>_mouth.json.
Usage: blender -b <aligned.blend> -P organ_mouth.py -- <dense.json> <landmarks.json> <out.blend> [orig|proc|tripo]
(tripo: the blend must hold donor_mouth from organ_donor.py)
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from organ_lib import Chart, egg, star, cut_level, contour2d, zipper, bridge_rings

a = sys.argv[sys.argv.index('--') + 1:]
DJ, LMJ, OUT = a[0], a[1], os.path.abspath(a[2]); SHAPE = a[3] if len(a) > 3 else 'orig'
HERE = os.path.dirname(os.path.abspath(__file__))
N = bpy.data.objects.get('face') or bpy.data.objects['noface']; O = bpy.data.objects['orig']
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
D = json.load(open(DJ)); RAW = {int(k): np.array(v) for k, v in D['_raw'].items()}
PT = json.load(open(os.path.join(HERE, 'data', 'mp_mirror_pairs.json')))
partner = {}
for i, j in PT['pairs']: partner[i] = j; partner[j] = i
OU = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]; OL = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
IU = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]; IL = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
XO = np.array([tuple(v.co) for v in O.data.vertices])
bvhO = BVHTree.FromPolygons([tuple(p) for p in XO], [list(p.vertices) for p in O.data.polygons])
if SHAPE == 'tripo':                                       # Tripo mouth part placed by organ_donor.py: its lips are the shape
    Dn = bpy.data.objects['donor_mouth']; XD = np.array([tuple(Dn.matrix_world @ v.co) for v in Dn.data.vertices])
    bvhO = BVHTree.FromPolygons([tuple(p) for p in XD], [list(p.vertices) for p in Dn.data.polygons])
XN = np.array([tuple(v.co) for v in N.data.vertices])
bvhN0 = BVHTree.FromPolygons([tuple(p) for p in XN], [list(p.vertices) for p in N.data.polygons])
M, K_SKIN, K_LIP = 80, 6, 6; K = K_SKIN + K_LIP
smooth = lambda x: x * x * (3 - 2 * x)
def sym(i):
    """MediaPipe point i, left/right averaged with its partner (centre points x = 0)"""
    p = RAW[i].copy(); j = partner.get(i)
    if j is not None and j in RAW: p = (p + RAW[j] * np.array([-1, 1, 1])) / 2
    elif i in PT['centre']: p[0] = 0
    return p
def contour(ids):
    P = np.array([sym(i) for i in ids]); return P[np.argsort(-P[:, 0])]         # from +x (left) to -x
ou, ol, iu, il = contour(OU), contour(OL), contour(IU), contour(IL)
seam = (iu + il) / 2
corner = seam[0].copy(); seam[-1] = corner * np.array([-1, 1, 1])
ou[0] = ol[0] = seam[0]; ou[-1] = ol[-1] = seam[-1]                             # the lip lines meet at the corners
half_w = abs(corner[0])
info = {'shape': SHAPE, 'mouth_width_mm': round(2 * half_w * 1000, 1), 'ring_verts': M, 'rings': K}

# ---- chart from behind the lips
c3 = seam.mean(0); view = np.array([0.0, -1.0, 0.0]); depth = 3.0 * half_w
ch = Chart(c3 - view * depth, view, depth)
t = np.arange(M) / M
MO = contour2d(np.c_[ch.uv(ou), ou], np.c_[ch.uv(ol), ol])(t); OUV, O3 = MO[:, :2], MO[:, 2:]
MS = contour2d(np.c_[ch.uv(seam), seam], np.c_[ch.uv(seam), seam])(t); SUV, S3 = MS[:, :2], MS[:, 2:]
c0 = OUV.mean(0)
nose_b = sym(2) if 2 in RAW else LT[16]; chin = sym(152) if 152 in RAW else LT[24]
top, bot = OUV[:, 1].max(), OUV[:, 1].min()
nose_v, chin_v = float(ch.uv(nose_b)[0, 1]), float(ch.uv(chin)[0, 1])
b_side, b_top, b_bot = 0.45 * half_w, 0.5 * (nose_v - top), 0.5 * (bot - chin_v)
ea_pos = OUV[:, 0].max() - c0[0] + b_side; ea_neg = c0[0] - OUV[:, 0].min() + b_side
eb_pos, eb_neg = top - c0[1] + b_top, c0[1] - bot + b_bot
f0, rho0 = egg(c0, ea_pos, ea_neg, eb_pos, eb_neg)
# per angle: shrink where the surface point would lie further than 1.3 band + 1.5 mm from the lip line in 3D
phs = np.linspace(-np.pi, np.pi, 96, endpoint=False)
pho = np.arctan2(OUV[:, 1] - c0[1], OUV[:, 0] - c0[0]); o = np.argsort(pho)
per = lambda y: np.interp(np.mod(phs - pho[o][0], 2 * np.pi) + pho[o][0], np.r_[pho[o], pho[o][0] + 2 * np.pi], np.r_[y[o], y[o][0]])
rM = per(np.hypot(*(OUV - c0).T)); O3s = np.c_[per(O3[:, 0]), per(O3[:, 1]), per(O3[:, 2])]
r0 = rho0(phs); rr = r0.copy(); shrunk = 0
for i, ph in enumerate(phs):
    dc = np.array([math.cos(ph), math.sin(ph)]); lim = 1.3 * (r0[i] - rM[i]) + 0.0015
    def gap(rad):
        uv = c0 + rad * dc; d = ch.cast(bvhN0, uv)[0]
        return np.inf if not np.isfinite(d) else float(np.linalg.norm(ch.point(uv, [d])[0] - O3s[i]))
    if gap(r0[i]) > lim:
        lo_, hi_ = rM[i] + 0.35 * (r0[i] - rM[i]), r0[i]; shrunk += 1
        for _ in range(12):
            mid = (lo_ + hi_) / 2
            if gap(mid) > lim: hi_ = mid
            else: lo_ = mid
        rr[i] = lo_
sm = rr.copy()
for _ in range(3): sm = (np.roll(sm, 1) + 2 * sm + np.roll(sm, -1)) / 4
rr = np.minimum(rr, sm); f, rho = star(c0, phs, rr)
info['shrunk_angles'] = shrunk

# ---- hole
bm = bmesh.new(); bm.from_mesh(N.data)
L_ring = bm.verts.layers.int.get('mouth_ring') or bm.verts.layers.int.new('mouth_ring')   # layers before any new vertex
L_u = bm.verts.layers.float.get('mouth_u') or bm.verts.layers.float.new('mouth_u')
L_def = bm.verts.layers.deform.verify()
bnd, BUV, info['cut'] = cut_level(bm, ch, f, 0.0002 / min(ea_pos, ea_neg, eb_pos, eb_neg))
info['hole_boundary_verts'] = len(bnd)

# ---- rings: depth grid D[k, i] along the chart rays
EUV = c0 + rho(pho)[:, None] * np.c_[np.cos(pho), np.sin(pho)]
dE = ch.cast(bvhN0, EUV); dOl = np.linalg.norm(O3 - ch.Q, axis=1); dS = np.linalg.norm(S3 - ch.Q, axis=1)
dE = np.where(np.isfinite(dE), dE, dOl)
tol = max(0.004, 0.2 * half_w); Dg = np.zeros((K + 1, M)); Dg[0] = dE; P2s = [EUV]
lip_h = 0.10 * half_w
for k in range(1, K + 1):
    if k <= K_SKIN:
        s = k / K_SKIN; P2 = EUV + s * (OUV - EUV); dlin = dE + s * (dOl - dE)
    else:
        s = (k - K_SKIN) / K_LIP; P2 = OUV + s * (SUV - OUV); dlin = dOl + s * (dS - dOl)
    P2s.append(P2)
    dN = ch.cast_near(bvhN0, P2, dlin); dN = np.where(np.isfinite(dN) & (np.abs(dN - dlin) < tol), dN, dlin)
    if SHAPE in ('orig', 'tripo'):
        dO_ = ch.cast_near(bvhO, P2, dlin); dO_ = np.where(np.isfinite(dO_) & (np.abs(dO_ - dlin) < tol), dO_, dN)
        wt = smooth(min(1.0, (k - 1) / K_SKIN)); Dg[k] = (1 - wt) * dN + wt * dO_   # ring 1 stays on the head surface
    else:                                                     # lip profile: skin flat, vermilion bulges, the slit tucks in
        bulge = lip_h * math.sin(math.pi * min(1, max(0, (k - K_SKIN + 1) / (K_LIP + 1)))) if k >= K_SKIN - 1 else 0
        Dg[k] = dN + bulge - (0.002 if k == K else 0)
for _ in range(2): Dg[K] = (np.roll(Dg[K], 1) + 2 * Dg[K] + np.roll(Dg[K], -1)) / 4
for _ in range(4):
    Dg[2:K] = (Dg[1:K - 1] + Dg[3:K + 1] + np.roll(Dg[2:K], 1, 1) + np.roll(Dg[2:K], -1, 1) + 4 * Dg[2:K]) / 8
rings3 = [ch.point(P2s[k], Dg[k]) for k in range(1, K + 1)]
newv = [[bm.verts.new(tuple(p)) for p in R] for R in rings3]
faces = zipper(bm, bnd, np.arctan2(BUV[:, 1] - c0[1], BUV[:, 0] - c0[0]), newv[0], pho) + bridge_rings(bm, newv)
bm.normal_update()
bset = set(bnd); agree = []
for fc in faces:
    for e in fc.edges:
        other = [g for g in e.link_faces if g is not fc]
        if other and e.verts[0] in bset and e.verts[1] in bset: agree.append(fc.normal.dot(other[0].normal))
info['flipped'] = bool(np.median(agree) < 0) if agree else False
if info['flipped']:
    for fc in faces: fc.normal_flip()
# ---- inner lip roll + oral cavity, rings behind the slit with the same parameter u
#   roll: 2 rings 1.5 / 3.5 mm back, opening away from the seam (lip thickness, lip colour from the projection)
#   cavity: 4 rings 7 / 14 / 23 / 30 mm back; the upper half rises to a palate and the lower half drops to a floor
#   (height ~ sin(pi * fraction along the lip), so the corners stay on the seam); the sides go out toward the
#   cheeks, then in; a cap closes it. Sizes are for a 52 mm mouth and scale with it.
s_ = half_w / 0.026
slit = rings3[-1]; mc = slit.mean(0)
frac = np.where(t <= 0.5, t / 0.5, (t - 0.5) / 0.5); bell = np.sin(np.pi * frac)
sgnv = np.where((t > 0) & (t < 0.5), 1.0, np.where(t > 0.5, -1.0, 0.0))
PROF = [(0.0015, 0.0010, 1.00, 'roll'), (0.0035, 0.0022, 0.99, 'roll'),
        (0.0070, 0.0065, 1.03, 'bag'), (0.0140, 0.0110, 1.06, 'bag'), (0.0230, 0.0095, 0.85, 'bag'), (0.0300, 0.0050, 0.50, 'bag')]
prev = newv[-1]; roll_v, bag_rings, roll_f, bag_f = [], [], [], []
for dep, dz, sx, kind in PROF:
    Q = slit.copy(); Q[:, 0] = mc[0] + sx * (slit[:, 0] - mc[0]); Q[:, 1] = slit[:, 1] + dep * s_
    Q[:, 2] = slit[:, 2] + sgnv * dz * s_ * (bell ** 0.5 if kind == 'bag' else bell)
    cur = [bm.verts.new(tuple(q)) for q in Q]
    for i in range(M):
        j = (i + 1) % M; f_ = bm.faces.new((prev[i], prev[j], cur[j], cur[i])); (roll_f if kind == 'roll' else bag_f).append(f_)
    (roll_v if kind == 'roll' else bag_rings).append(cur); prev = cur
cap = bm.verts.new(tuple(mc + np.array([0, 0.034 * s_, 0])))
for i in range(M): bag_f.append(bm.faces.new((prev[i], prev[(i + 1) % M], cap)))
bag_v = sum(bag_rings, []) + [cap]
if info['flipped']:                                       # same winding as the lip rings they continue
    for fc in roll_f + bag_f: fc.normal_flip()
bm.normal_update()
info['interior'] = {'roll_rings': len(roll_v), 'cavity_rings': len(bag_rings), 'depth_mm': round(0.034 * s_ * 1000, 1)}
faces = faces + roll_f
for fc in faces + bag_f: fc.smooth = True
# ---- groups, attributes, material
GN = ('mouth_upper', 'mouth_lower', 'mouth_skin', 'mouth_bag', 'mouth_slit_upper', 'mouth_slit_lower')
for nm in GN:
    if not N.vertex_groups.get(nm): N.vertex_groups.new(name=nm)
gi = {g.name: g.index for g in N.vertex_groups}
for k, R in enumerate(newv, start=1):
    for i, v in enumerate(R):
        v[L_ring] = k; v[L_u] = float(t[i]); cor = i in (0, M // 2); up = t[i] < 0.5
        if k > K_SKIN:
            if cor: v[L_def][gi['mouth_upper']] = 0.5; v[L_def][gi['mouth_lower']] = 0.5
            else: v[L_def][gi['mouth_upper' if up else 'mouth_lower']] = 1.0
        else: v[L_def][gi['mouth_skin']] = 1.0
        if k == K and not cor: v[L_def][gi['mouth_slit_upper' if up else 'mouth_slit_lower']] = 1.0
for r_i, R in enumerate(roll_v):                         # inner lip roll: part of the lips
    for i, v in enumerate(R):
        v[L_ring] = K + 1 + r_i; v[L_u] = float(t[i]); cor = i in (0, M // 2); up = t[i] < 0.5
        if cor: v[L_def][gi['mouth_upper']] = 0.5; v[L_def][gi['mouth_lower']] = 0.5
        else: v[L_def][gi['mouth_upper' if up else 'mouth_lower']] = 1.0
for b_i, R in enumerate(bag_rings):
    for i, v in enumerate(R): v[L_ring] = K + 3 + b_i; v[L_u] = float(t[i]); v[L_def][gi['mouth_bag']] = 1.0
cap[L_ring] = K + 7; cap[L_u] = -1.0; cap[L_def][gi['mouth_bag']] = 1.0
me = N.data
if 'mouth_inner' not in [m.name for m in me.materials if m]:
    mi = bpy.data.materials.get('mouth_inner') or bpy.data.materials.new('mouth_inner'); mi.diffuse_color = (0.35, 0.08, 0.1, 1)
    if not me.materials: me.materials.append(bpy.data.materials.new('skin'))
    me.materials.append(mi)
mi_idx = [m.name for m in me.materials].index('mouth_inner')
for fc in bag_f: fc.material_index = mi_idx
bm.to_mesh(me); bm.free(); me.update()
N.name = 'face'
info['c0_mm'] = (c3 * 1000).round(1).tolist()
info['corner_mm'] = (corner * 1000).round(1).tolist()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(info, open(os.path.splitext(OUT)[0] + '_mouth.json', 'w'), indent=1)
print('MOUTH', json.dumps(info))
