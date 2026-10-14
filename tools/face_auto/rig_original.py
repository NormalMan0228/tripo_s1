"""Rig the ORIGINAL head as it is: the rest shape is never changed, only cut and given expressions.

Allowed changes (user rule): cut without moving vertices, add new parts, add expressions.
 1. cut the eyeballs off the lids along the lid rim, and the upper lip off the lower lip along the lip seam
    (faces are split along the smooth rim / seam first: new vertices on original edges, no vertex moves)
 2. add a mouth cavity behind the lips (new part)
 3. expressions on the original vertices:
      blink_L / blink_R  lid skin rotates about the eyeball centre until the upper margin meets the lower one
      jaw_open           rotation about the jaw pivot; pivot and weights borrowed from a fitted template
      viseme_aa/I/U/E/O  template viseme motion carried onto the original vertices by closest point
 4. QA: basis vs original surface (must be 0), original vertices all kept, blink gap, lid vertices inside the eyeball
With EYE_RIMS=<rig_points head json> the eye cut follows the contour rig_points chose (T14), when it has one.
Usage: blender -b --factory-startup -P rig_original.py -- <head.fbx> <landmarks.json> <donor_fit.blend> <out_dir>
The donor is face_fit.py's fit.blend (template fitted to this head); only its weights/pivot/motion are used.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

sys.path.append(os.path.dirname(__file__))
from facelib import *

a = sys.argv[sys.argv.index("--") + 1:]
SRC, LMJ, DONOR, OUT = a[:4]
os.makedirs(OUT, exist_ok=True)
TS = np.linspace(0, 1, 11)[1:-1]
qa = {}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
src = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
src.data.transform(src.matrix_world); src.matrix_world = Matrix()
V0 = np.array([tuple(v.co) for v in src.data.vertices]); F0 = [list(p.vertices) for p in src.data.polygons]
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
bvh0 = bvh_of(V0, F0)

# ------------------------------------------------------------------ rims, seam
rims = {}
for side, ids in {'R': (7, 8, 9, 10), 'L': (13, 12, 11, 14)}.items():
    cx, cz = np.mean([LT[k][0] for k in ids]), np.mean([LT[k][2] for k in ids])
    rims[side] = lids(recentred_rim(bvh0, cx, cz, 'margin'), TS)
# T14: on human-like eyes the depth rim can leak into the lid creases; rig_points then hands over MediaPipe's eye
# contour (symmetric, on the surface) and the cut follows that instead
ER = os.environ.get('EYE_RIMS')
if ER and os.path.exists(ER):
    er = json.load(open(ER)).get('info', {}).get('eye_rims')
    if er:
        for side in 'RL': rims[side] = lids(np.array(er[side]), TS)
        qa['eye_rims_from'] = 'rig_points (MediaPipe contour)'
seam = seam_curve(bvh0, LT[20][0], LT[22][0], LT[20][2], (LT[34][2] + LT[35][2]) / 2, LT[22][2], n=61)

# ------------------------------------------------------------------ cuts (no vertex moves)
# The cut lines are smooth curves: the rim polygon around each eye, and the lip seam z = s(x). Faces they cross are
# first split along them (new vertices on the original edges, linear along each edge, so the surface does not
# change and no original vertex moves); then the mesh opens along those new edges. Opening only along existing
# edges gave a zigzag slit on dense triangle meshes.
def smooth_ring(R, n=3):
    for _ in range(n): R = (np.roll(R, 1, 0) + 2 * R + np.roll(R, -1, 0)) / 4
    return R
for s in 'RL': rims[s] = lids(smooth_ring(rims[s]['raw']), TS)
seam[:, 2] = np.convolve(np.pad(seam[:, 2], 3, mode='edge'), np.ones(7) / 7, mode='valid')
def ring_sdf(R, P):
    """signed distance in the front plane (x, z) to the closed rim polygon, negative inside"""
    A = R[:, [0, 2]]; B = np.roll(A, -1, 0); Q = P[:, [0, 2]]; d = np.full(len(Q), np.inf)
    for a_, b_ in zip(A, B):
        ab = b_ - a_; t = np.clip((Q - a_) @ ab / (ab @ ab + 1e-18), 0, 1)
        d = np.minimum(d, np.linalg.norm(Q - (a_ + t[:, None] * ab), axis=1))
    return np.where(inside2d(R, P), -d, d)
seam_f = lambda P: P[:, 2] - np.interp(P[:, 0], seam[:, 0], seam[:, 2])
def split_along(bm, faces, fval):
    """split the given faces along the zero line of fval; returns how many faces were split"""
    vl = list({v for f in faces for v in f.verts}); fv = dict(zip(vl, fval(np.array([tuple(v.co) for v in vl]))))
    zero = {v for v in vl if abs(fv[v]) < 1e-9}
    for e in list({e for f in faces for e in f.edges}):
        a_, b_ = e.verts; fa, fb = fv[a_], fv[b_]
        if fa * fb < 0:
            _, nv = bmesh.utils.edge_split(e, a_, fa / (fa - fb)); zero.add(nv)
    n = 0
    for f in faces:
        zv = [v for v in f.verts if v in zero]
        if len(zv) == 2 and not any(e.other_vert(zv[0]) is zv[1] for e in zv[0].link_edges):
            bmesh.utils.face_split(f, zv[0], zv[1]); n += 1
    return n
bm = bmesh.new(); bm.from_mesh(src.data); bm.faces.ensure_lookup_table()
Fc0 = np.array([V0[f].mean(0) for f in F0])
xl, xr = seam[0, 0], seam[-1, 0]
zs0 = np.interp(Fc0[:, 0], seam[:, 0], seam[:, 2]); ys0 = np.interp(Fc0[:, 0], seam[:, 0], seam[:, 1])
todo = []
for s in 'RL':
    R = rims[s]['raw']; near = (np.abs(ring_sdf(R, Fc0)) < 0.004) & (Fc0[:, 1] < R[:, 1].mean() + 0.006)
    todo.append(('eye_' + s, [bm.faces[i] for i in np.nonzero(near)[0]], lambda P, R=R: ring_sdf(R, P)))
lipband0 = (Fc0[:, 0] > xl) & (Fc0[:, 0] < xr) & (np.abs(Fc0[:, 2] - zs0) < 0.006) & (Fc0[:, 1] < ys0 + 0.006)
todo.append(('lips', [bm.faces[i] for i in np.nonzero(lipband0)[0]], seam_f))
qa['split_faces'] = {k: split_along(bm, fs_, fn) for k, fs_, fn in todo}
bm.verts.index_update(); bm.faces.index_update(); bm.faces.ensure_lookup_table()
Fc = np.array([np.mean([tuple(v.co) for v in f.verts], 0) for f in bm.faces])
eye_face = np.zeros(len(Fc), bool); eye_side = np.full(len(Fc), '', object)
for s in 'RL':
    R = rims[s]['raw']; m = inside2d(R, Fc) & (Fc[:, 1] < R[:, 1].mean() + 0.006)
    eye_face |= m; eye_side[m] = s
# lip seam: faces in the lip band split into upper/lower by the seam curve; their shared edges get cut
zs = np.interp(Fc[:, 0], seam[:, 0], seam[:, 2]); ys = np.interp(Fc[:, 0], seam[:, 0], seam[:, 1])
band = (Fc[:, 0] > xl) & (Fc[:, 0] < xr) & (np.abs(Fc[:, 2] - zs) < 0.006) & (Fc[:, 1] < ys + 0.006) & ~eye_face
upper = band & (Fc[:, 2] > zs)
cut_edges = set()
for e in bm.edges:
    lf = [f.index for f in e.link_faces]
    if len(lf) != 2: continue
    a_, b_ = lf
    if eye_face[a_] != eye_face[b_]: cut_edges.add(e)
    elif band[a_] and band[b_] and upper[a_] != upper[b_]: cut_edges.add(e)
bmesh.ops.split_edges(bm, edges=list(cut_edges))
qa['cut_edges'] = len(cut_edges)
bm.to_mesh(src.data); bm.free(); src.data.update()

# separate eyeballs into their own object (still the original geometry)
def separate(ob, face_mask, name):
    bm_ = bmesh.new(); bm_.from_mesh(ob.data); bm_.faces.ensure_lookup_table()
    keep = [f for f in bm_.faces if face_mask[f.index]]
    other = bmesh.new()
    vmap = {}
    for f in keep:
        vs = []
        for v in f.verts:
            if v not in vmap: vmap[v] = other.verts.new(v.co)
            vs.append(vmap[v])
        other.faces.new(vs)
    bmesh.ops.delete(bm_, geom=keep, context='FACES_ONLY')
    bmesh.ops.delete(bm_, geom=[v for v in bm_.verts if not v.link_faces], context='VERTS')
    bm_.to_mesh(ob.data); bm_.free()
    m = bpy.data.meshes.new(name); other.to_mesh(m); other.free()
    o = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(o); return o
# face indices survive split_edges (it only adds vertices), so the masks still line up
eyes_ob = separate(src, eye_face, 'eyes')
src.name = 'face'
X = np.array([tuple(v.co) for v in src.data.vertices]); XF = [list(p.vertices) for p in src.data.polygons]
E = np.array([tuple(v.co) for v in eyes_ob.data.vertices]); EF = [list(p.vertices) for p in eyes_ob.data.polygons]
nb = neighbours(len(X), XF)
# rest-shape check: every vertex of the rig lies on the original surface (cut vertices sit on original edges), and
# every original vertex is still there
def surf_dist(P): return np.array([bvh0.find_nearest(Vector(p))[3] for p in P])
qa['rest_max_offset_mm'] = float(max(surf_dist(X).max(), surf_dist(E).max()) * 1000)
qa['original_verts_kept_mm'] = float(dist_to(np.r_[X, E], V0).max() * 1000)

# ------------------------------------------------------------------ eyes
eyes = {}
bvhE = bvh_of(E, EF)
for s in 'RL':
    P = E[(E[:, 0] < 0) if s == 'R' else (E[:, 0] > 0)]
    C, r = sphere_fit(P); A = rims[s]['inner'] - rims[s]['outer']; A /= np.linalg.norm(A)
    eyes[s] = {'C': C, 'r': r, 'A': A, 'up_path': rims[s]['up_path'], 'lo_path': rims[s]['lo_path'], 'reach': 0.5}
    qa['eye_' + s] = {'radius_mm': r * 1000}

def outside_eyes(P, ids):
    """Push lid vertices that ended up inside the real eyeball surface back out along the eye radius."""
    for i in ids:
        for s, e in eyes.items():
            d = P[i] - e['C']; L = np.linalg.norm(d)
            if L > 2 * e['r'] or L < 1e-6: continue
            hit = bvhE.ray_cast(Vector(e['C'] + d / L * 3 * e['r']), Vector(-d / L))[0]   # from outside, inward
            if hit is None: continue
            surf = np.linalg.norm(np.array(hit) - e['C'])
            if L < surf + 0.0003: P[i] = e['C'] + d / L * (surf + 0.0003)
    return P

def relax(P, moved, pin, rounds=4):
    ids = np.nonzero(moved & ~pin)[0]
    for _ in range(rounds):
        for f_ in (0.5, -0.53):
            avg = np.array([P[nb[i]].mean(0) for i in ids]); P[ids] += f_ * (avg - P[ids])
    return P

keys = {}
# lid margins = the open edge the eye cut left in the skin, split into upper/lower by the corner-to-corner axis
bmb = bmesh.new(); bmb.from_mesh(src.data)
bverts = np.array(sorted({v.index for e in bmb.edges if e.is_boundary for v in e.verts})); bmb.free()
deg = max(len(n) for n in nb); NB = np.full((len(X), deg), -1)
for i, n in enumerate(nb): NB[i, :len(n)] = n
def harmonic(D, free, iters=500):
    """Jacobi on the mesh graph: free vertices take their neighbours' mean displacement; others stay fixed."""
    idx = np.nonzero(free)[0]; nbi = NB[idx]; msk = nbi >= 0; cnt = msk.sum(1)[:, None]
    for _ in range(iters):
        Dn = np.where(msk[..., None], D[np.where(msk, nbi, 0)], 0.0)
        D[idx] = Dn.sum(1) / np.maximum(cnt, 1)
    return D
for s, nm in (('L', 'blink_L'), ('R', 'blink_R')):
    e = eyes[s]; Rr = rims[s]['raw']
    marg = bverts[dist_to(Rr, X[bverts]) < 0.003]
    mid = (rims[s]['outer'] + rims[s]['inner']) / 2; up_dir = np.cross(e['A'], [0, -1, 0]); up_dir *= np.sign(up_dir[2]) / np.linalg.norm(up_dir)
    is_up = (X[marg] - mid) @ up_dir > 0
    e2 = dict(e); e2['up_path'] = X[marg[is_up]]; e2['lo_path'] = X[marg[~is_up]]
    P_rot = blink_field(X, e2)                                   # where the rotation model sends every lid vertex
    region = (np.linalg.norm(P_rot - X, axis=1) > 1e-6); region[marg] = True
    D = np.zeros_like(X); D[marg] = P_rot[marg] - X[marg]       # margins: exact closed position
    free = region.copy(); free[marg] = False                     # outside the region displacement stays 0
    D = harmonic(D, free)
    P = X + D; P = outside_eyes(P, np.nonzero(region)[0]); keys[nm] = P
    qa['lid_region_verts_' + s] = int(region.sum()); qa['margin_verts_' + s] = {'upper': int(is_up.sum()), 'lower': int((~is_up).sum())}

# ------------------------------------------------------------------ jaw + visemes from the donor template
with bpy.data.libraries.load(DONOR) as (fs, to): to.objects = ['head', 'target']
dh, dt = to.objects
DH = np.array([tuple(v.co) for v in dh.data.vertices]); DHF = [list(p.vertices) for p in dh.data.polygons]
DT = np.array([tuple(v.co) for v in dt.data.vertices])
# donor lives in template space; its 'target' is this head (same vertex order as the FBX import) -> similarity back
if len(DT) == len(V0):
    sc = float(np.linalg.norm(DT - DT.mean(0)) / np.linalg.norm(V0 - V0.mean(0))); tr = DT.mean(0) - sc * V0.mean(0)
else:
    raise SystemExit('donor target does not match this head')
toT = lambda P: (P - tr) / sc
DHt = toT(DH); DK = {k.name: toT(np.array([tuple(d.co) for d in k.data])) for k in dh.data.shape_keys.key_blocks[1:]}
bvhD = bvh_of(DHt, DHF)
tri = []
for f in DHF:
    for i in range(1, len(f) - 1): tri.append([f[0], f[i], f[i + 1]])
tri = np.array(tri); bvhDT = bvh_of(DHt, tri.tolist())
# upper / lower lip by which side's faces a vertex belongs to (after the cut the two lip edges share positions,
# so position alone cannot tell them apart)
FcX = np.array([X[f].mean(0) for f in XF])
zsX = np.interp(FcX[:, 0], seam[:, 0], seam[:, 2]); ysX = np.interp(FcX[:, 0], seam[:, 0], seam[:, 1])
bandX = (FcX[:, 0] > xl) & (FcX[:, 0] < xr) & (np.abs(FcX[:, 2] - zsX) < 0.006) & (FcX[:, 1] < ysX + 0.006)
up_v = np.zeros(len(X), bool); lo_v = np.zeros(len(X), bool)
for f, b, z, zs_ in zip(XF, bandX, FcX[:, 2], zsX):
    if b: (up_v if z > zs_ else lo_v)[f] = True
# lip edge vertices look up the donor slightly on their own side, so upper and lower lips get their own motion
Q = X.copy(); Q[up_v & ~lo_v, 2] += 0.0012; Q[lo_v & ~up_v, 2] -= 0.0012
def carry(delta_v):
    """Donor per-vertex field -> original vertices by closest point (barycentric)."""
    out = np.zeros((len(X),) + delta_v.shape[1:])
    for i, p in enumerate(Q):
        loc, n, t, d = bvhDT.find_nearest(Vector(p))
        if loc is None or d > 0.01: continue
        a_, b_, c_ = DHt[tri[t]]; v0, v1, v2 = b_ - a_, c_ - a_, np.array(loc) - a_
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01 + 1e-18; v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
        out[i] = (1 - v - w) * delta_v[tri[t, 0]] + v * delta_v[tri[t, 1]] + w * delta_v[tri[t, 2]]
    return out
# jaw weights from the template's jawOpen motion; lower lip / upper lip decided by the cut, not by the weights
dj = np.linalg.norm(DK['mpfb_jawOpen'] - DHt, axis=1); wj = np.clip(dj / np.percentile(dj[dj > 1e-6], 98), 0, 1)
w = carry(wj[:, None])[:, 0]
w[up_v & ~lo_v] = 0.0
w[lo_v & ~up_v] = np.maximum(w[lo_v & ~up_v], 0.85)
# the neck under the jaw does not turn with it: fade the weight out below and behind the chin
chin = LT[24]
neck = (X[:, 1] > chin[1] + 0.008) & (X[:, 2] < chin[2] + 0.004)
w = np.where(neck, w * (1 - smoothstep(chin[2] + 0.004 - X[:, 2], 0.0, 0.02)) * (1 - smoothstep(X[:, 1] - chin[1], 0.03, 0.06)), w)
qa['lip_verts'] = {'upper': int((up_v & ~lo_v).sum()), 'lower': int((lo_v & ~up_v).sum())}
dbg = json.load(open(os.path.join(os.path.dirname(DONOR), 'fit_debug.json')))
J = toT(np.array(dbg['jaw_pivot'])[None])[0]
def rot_x(P, piv, ang):
    c, s_ = np.cos(ang), np.sin(ang); d = P - piv
    return piv + np.c_[d[:, 0], d[:, 1] * c - d[:, 2] * s_, d[:, 1] * s_ + d[:, 2] * c]
ANG = math.radians(16)
jaw = X.copy(); m = w > 1e-3
for i in np.nonzero(m)[0]: jaw[i] = rot_x(X[i:i + 1], J, ANG * w[i])[0]
keys['jaw_open'] = jaw
for k in ('viseme_aa', 'viseme_I', 'viseme_U', 'viseme_E', 'viseme_O'):
    dk = 'mpfb_' + k
    if dk in DK: keys[k] = X + carry(DK[dk] - DHt)
qa['jaw_pivot'] = J.tolist(); qa['jaw_weighted_verts'] = int(m.sum())

# ------------------------------------------------------------------ mouth cavity (new part)
mc = seam[len(seam) // 2]; half = (seam[-1, 0] - seam[0, 0]) / 2
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(mc[0], mc[1] + half * 1.0, mc[2] - half * 0.1), segments=24, ring_count=12)
cav = bpy.context.active_object; cav.name = 'mouth_cavity'; cav.scale = (half * 1.0, half * 0.92, half * 0.72)
bpy.ops.object.transform_apply(scale=True); cav.data.flip_normals()

# ------------------------------------------------------------------ QA + write
def gap(s, P):
    e = eyes[s]; marg = bverts[dist_to(rims[s]['raw'], X[bverts]) < 0.003]
    mid = (rims[s]['outer'] + rims[s]['inner']) / 2; up_dir = np.cross(e['A'], [0, -1, 0]); up_dir *= np.sign(up_dir[2]) / np.linalg.norm(up_dir)
    up = marg[(X[marg] - mid) @ up_dir > 0]; lo_ = marg[(X[marg] - mid) @ up_dir <= 0]
    su, sl = X[up] @ e['A'], X[lo_] @ e['A']; span = su.max() - su.min(); mid_ = np.abs(su - (su.max() + su.min()) / 2) < 0.35 * span
    pair = [lo_[int(np.argmin(np.abs(sl - v)))] for v in su[mid_]]
    return float(np.max(np.linalg.norm(P[up[mid_]] - P[pair], axis=1)) * 1000)
for s, nm in (('L', 'blink_L'), ('R', 'blink_R')):
    qa['blink_gap_mm_' + s] = {'open': gap(s, X), 'closed': gap(s, keys[nm])}
src.shape_key_add(name='Basis')
for nm, P in keys.items():
    kb = src.shape_key_add(name=nm)
    for d, p in zip(kb.data, P): d.co = Vector(p)
for p_ in src.data.polygons: p_.use_smooth = True
json.dump(qa, open(os.path.join(OUT, 'qa.json'), 'w'), indent=1)
json.dump({s: {'C': eyes[s]['C'].tolist(), 'r': float(eyes[s]['r']), 'A': eyes[s]['A'].tolist(),
               'up_path': rims[s]['up_path'].tolist(), 'lo_path': rims[s]['lo_path'].tolist(), 'raw': rims[s]['raw'].tolist()}
           for s in 'RL'}, open(os.path.join(OUT, 'eyes_meta.json'), 'w'))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'rig.blend'))
print('QA', json.dumps(qa))
