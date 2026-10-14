"""M1 · eye organs (v2): ring-topology eyelids built into a featureless head (after organ_mouth.py or on its own),
plus a separate eyeball object.

Per eye, everything is laid out in a ray chart from the eyeball centre (organ_lib.Chart), so big cartoon eyes that
wrap round the side of the head are handled like small human eyes:
1. eye opening = the lid margin of the original head (rig_original's eyes_meta rim: MediaPipe contour on human-like
   eyes, depth rim on big cartoon eyes), smoothed; corners at the ends of its long axis; M points, the corners at
   u = 0 and u = 0.5 (u < 0.5 upper lid, over the top)
2. hole = an egg round the opening: the opening plus a band (outer side 3-7 mm, nose side 2.5-5 mm, under 3-8 mm,
   above 55 % of the way to the brow); cut exactly along it (organ_lib.cut_level: curve vertices on the surface)
3. rings: K rings on straight chart lines from the hole curve to the margin point at the same angle; the hole
   boundary is zipped to ring 1 by angle (no folded triangles, any boundary vertex count); behind the margin two
   rings tuck under the lid along the eyeball (lid thickness)
4. depth along each ray: SHAPE=orig blends the featureless surface into the original's lid surface over the skin
   rings; SHAPE=proc blends into a shell 0.6 mm over the eyeball; lids never go inside the eyeball
5. eyeball: a UV sphere (centre and radius from rig_original), pole along the eye axis
Vertex groups eye_L_upper / eye_L_lower / eye_L_skin / eye_L_margin_upper / eye_L_margin_lower (and _R); point
attributes eye_ring (+-k, sign = side) and eye_u. Writes <out.blend> and <out>_eyes.json (centre, radius, axis).
Usage: blender -b <head.blend> -P organ_eye.py -- <eyes_meta.json> <landmarks.json> <out.blend> [orig|proc|tripo]
(tripo: the blend holds donor_eye_L / donor_eye_R from organ_donor.py)
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facelib import lids
from organ_lib import Chart, egg, star, cut_level, contour2d, zipper, bridge_rings

a = sys.argv[sys.argv.index('--') + 1:]
EMJ, LMJ, OUT = a[0], a[1], os.path.abspath(a[2]); SHAPE = a[3] if len(a) > 3 else 'orig'
N = bpy.data.objects.get('face') or bpy.data.objects['noface']; O = bpy.data.objects['orig']
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
EM = json.load(open(EMJ))
XO = np.array([tuple(v.co) for v in O.data.vertices])
bvhO = BVHTree.FromPolygons([tuple(p) for p in XO], [list(p.vertices) for p in O.data.polygons])
bvhD = {}
if SHAPE == 'tripo':                                       # Tripo eye parts placed by organ_donor.py: their lids are the shape
    for s_ in 'LR':
        Do = bpy.data.objects.get('donor_eye_' + s_)
        if Do is None: continue
        XD = np.array([tuple(Do.matrix_world @ v.co) for v in Do.data.vertices])
        bvhD[s_] = BVHTree.FromPolygons([tuple(p) for p in XD], [list(p.vertices) for p in Do.data.polygons])
XN = np.array([tuple(v.co) for v in N.data.vertices])
bvhN0 = BVHTree.FromPolygons([tuple(p) for p in XN], [list(p.vertices) for p in N.data.polygons])   # before any hole
M, K_SKIN, K_LID = 64, 5, 6; K = K_SKIN + K_LID
smooth = lambda x: x * x * (3 - 2 * x)
def sphere_t(ch, UV, C, R):
    """distance along each chart ray to where it leaves the sphere (C, R)"""
    D = ch.dirs(UV); q = ch.Q - C; b = D @ q; c = q @ q - R * R
    return -b + np.sqrt(np.maximum(b * b - c, 0))
def smooth_ring(R, n=4):
    for _ in range(n): R = (np.roll(R, 1, 0) + 2 * R + np.roll(R, -1, 0)) / 4
    return R

GN = ('upper', 'lower', 'skin', 'margin_upper', 'margin_lower')
for s in 'LR':
    for nm in GN:
        if not N.vertex_groups.get(f'eye_{s}_{nm}'): N.vertex_groups.new(name=f'eye_{s}_{nm}')
gidx = {g.name: g.index for g in N.vertex_groups}
bm = bmesh.new(); bm.from_mesh(N.data)
L_ring = bm.verts.layers.int.get('eye_ring') or bm.verts.layers.int.new('eye_ring')
L_u = bm.verts.layers.float.get('eye_u') or bm.verts.layers.float.new('eye_u')
L_def = bm.verts.layers.deform.verify()
info = {'shape': SHAPE, 'ring_verts': M, 'rings': K, 'eyes': {}}
balls = []
for s, sgn, brow_ids in (('L', 1, (4, 5, 6)), ('R', -1, (1, 2, 3))):
    C = np.array(EM[s]['C']); r = float(EM[s]['r'])
    rim3 = smooth_ring(np.array(EM[s]['raw'])); cen3 = rim3.mean(0)
    axis_n = (cen3 - C) / np.linalg.norm(cen3 - C)
    Q = C - axis_n * r * float(os.environ.get("EYE_Q_BACK", "2.0"))   # two radii behind the eyeball centre: steep enough for wrapped eyes, no fold at the nose wall
    focal = float(np.linalg.norm(cen3 - Q)); ch = Chart(Q, axis_n, focal)
    # ---- 1. margin in the chart, corners at u = 0 (+u side) and u = 0.5
    Lr = lids(rim3, np.linspace(0, 1, 5))
    upUV = np.c_[ch.uv(Lr['up_path']), Lr['up_path']]; loUV = np.c_[ch.uv(Lr['lo_path']), Lr['lo_path']]   # outer -> inner
    if upUV[0, 0] < upUV[-1, 0]: upUV, loUV = upUV[::-1], loUV[::-1]        # from the +u corner to the -u corner
    t = np.arange(M) / M; MU3 = contour2d(upUV, loUV)(t); MUV, M3 = MU3[:, :2], MU3[:, 2:]
    c0 = MUV.mean(0)
    w = float(np.linalg.norm(MUV[0] - MUV[M // 2])); top, bot = MUV[:, 1].max(), MUV[:, 1].min(); h = top - bot
    brow_v = float(ch.uv(np.mean([LT[k] for k in brow_ids], 0))[0, 1])
    b_out, b_in = np.clip(0.30 * w, 0.003, 0.007), np.clip(0.20 * w, 0.0025, 0.005)
    inner3 = Lr['inner']; b_in = min(b_in, 0.3 * abs(inner3[0]))          # keep the nose side off the nose bridge
    b_top = max(0.002, 0.55 * (brow_v - top)); b_bot = np.clip(0.6 * h, 0.003, 0.008)
    ea_pos = MUV[:, 0].max() - c0[0] + (b_out if sgn > 0 else b_in)          # L eye: outer corner at +x = +u
    ea_neg = c0[0] - MUV[:, 0].min() + (b_in if sgn > 0 else b_out)
    eb_pos, eb_neg = top - c0[1] + b_top, c0[1] - bot + b_bot
    f0, rho0 = egg(c0, ea_pos, ea_neg, eb_pos, eb_neg)
    # where the chart squeezes the surface (rays grazing the side of the nose), the egg would reach far over it:
    # per angle, shrink the radius until the surface point lies within 1.3 band + 1.5 mm of the margin in 3D
    phs = np.linspace(-np.pi, np.pi, 96, endpoint=False)
    phm = np.arctan2(MUV[:, 1] - c0[1], MUV[:, 0] - c0[0]); o = np.argsort(phm)
    per = lambda y: np.interp(np.mod(phs - phm[o][0], 2 * np.pi) + phm[o][0], np.r_[phm[o], phm[o][0] + 2 * np.pi], np.r_[y[o], y[o][0]])
    rM = per(np.hypot(*(MUV - c0).T)); M3s = np.c_[per(M3[:, 0]), per(M3[:, 1]), per(M3[:, 2])]
    r0 = rho0(phs); rr = r0.copy(); shrunk = 0
    for i, ph in enumerate(phs):
        dc = np.array([math.cos(ph), math.sin(ph)]); lim = 1.3 * (r0[i] - rM[i]) + 0.0015
        def gap(rad):
            uv = c0 + rad * dc; d = ch.cast(bvhN0, uv)[0]
            return np.inf if not np.isfinite(d) else float(np.linalg.norm(ch.point(uv, [d])[0] - M3s[i]))
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
    # ---- 2. hole
    bnd, BUV, cinfo = cut_level(bm, ch, f, 0.0002 / min(ea_pos, ea_neg, eb_pos, eb_neg))
    # ---- 3. rings on chart lines from the hole curve to the margin
    phM = np.arctan2(MUV[:, 1] - c0[1], MUV[:, 0] - c0[0])
    EUV = c0 + rho(phM)[:, None] * np.c_[np.cos(phM), np.sin(phM)]
    # depth along each chart ray: grid D[k, i] (row 0 = hole curve on the head, row K = margin on the original)
    dE = ch.cast(bvhN0, EUV); dM = np.linalg.norm(M3 - ch.Q, axis=1); dE = np.where(np.isfinite(dE), dE, dM)
    tol = max(0.004, 0.25 * w); D = np.zeros((K + 1, M)); D[0] = dE; P2s = [EUV]
    for k in range(1, K + 1):
        P2 = EUV + (k / K) * (MUV - EUV); dlin = dE + (k / K) * (dM - dE); P2s.append(P2)
        dN = ch.cast_near(bvhN0, P2, dlin); dO = ch.cast_near(bvhD.get(s, bvhO), P2, dlin)
        dN = np.where(np.isfinite(dN) & (np.abs(dN - dlin) < tol), dN, dlin)      # a far hit (nose wall) is not this surface
        dO = np.where(np.isfinite(dO) & (np.abs(dO - dlin) < tol), dO, dN)
        if SHAPE in ('orig', 'tripo'):
            wt = smooth(min(1.0, (k - 1) / K_SKIN)); D[k] = (1 - wt) * dN + wt * dO   # ring 1 stays on the head surface
        else:
            wt = smooth((k - 1) / (K - 1)); D[k] = (1 - wt) * dN + wt * sphere_t(ch, P2, C, r + 0.0006)
    # smooth the grid (Tripo lids are lumpy): the margin row along u only, the inner rows over both directions;
    # row 0 and ring 1 stay on the head surface
    for _ in range(2): D[K] = (np.roll(D[K], 1) + 2 * D[K] + np.roll(D[K], -1)) / 4
    for _ in range(6):
        D[2:K] = (D[1:K - 1] + D[3:K + 1] + np.roll(D[2:K], 1, 1) + np.roll(D[2:K], -1, 1) + 4 * D[2:K]) / 8
    rings3 = []
    for k in range(1, K + 1):
        d = np.maximum(D[k], sphere_t(ch, P2s[k], C, r + 0.0004)); rings3.append(ch.point(P2s[k], d))
    # lid thickness: two rings tucking under the lid along the eyeball
    marg = rings3[-1]; dm = (marg - C) / np.linalg.norm(marg - C, axis=1, keepdims=True)
    tout = marg - cen3; tout -= dm * np.sum(tout * dm, 1, keepdims=True); tout /= np.linalg.norm(tout, axis=1, keepdims=True)
    for rad, arc_mm in ((r + 0.0005, 0.8), (r + 0.0003, 2.5)):
        al = arc_mm / 1000 / r
        rings3.append(C + rad * (dm * math.cos(al) + tout * math.sin(al)))
    newv = [[bm.verts.new(tuple(p)) for p in R] for R in rings3]
    phB = np.arctan2(BUV[:, 1] - c0[1], BUV[:, 0] - c0[0])
    faces = zipper(bm, bnd, phB, newv[0], phM) + bridge_rings(bm, newv)
    bm.normal_update()
    # orientation: the zip triangles must agree with the head faces across the hole boundary
    agree = []
    for fc in faces[:len(bnd) + M]:
        for e in fc.edges:
            other = [g for g in e.link_faces if g is not fc]
            if other and all(v in set(bnd) for v in e.verts): agree.append(fc.normal.dot(other[0].normal))
    flipped = bool(np.median(agree) < 0) if agree else False
    if flipped:
        for fc in faces: fc.normal_flip()
    for fc in faces: fc.smooth = True
    # ---- groups and attributes
    for k, R in enumerate(newv, start=1):
        for i, v in enumerate(R):
            v[L_ring] = k * sgn; v[L_u] = float(t[i]); corner = i in (0, M // 2); up = t[i] < 0.5
            if k <= 2: v[L_def][gidx[f'eye_{s}_skin']] = 1.0
            elif corner: v[L_def][gidx[f'eye_{s}_upper']] = 0.5; v[L_def][gidx[f'eye_{s}_lower']] = 0.5
            else: v[L_def][gidx[f'eye_{s}_upper' if up else f'eye_{s}_lower']] = 1.0
            if k >= K and not corner: v[L_def][gidx[f'eye_{s}_margin_upper' if up else f'eye_{s}_margin_lower']] = 1.0
    # ---- 5. eyeball
    bm2 = bmesh.new(); bmesh.ops.create_uvsphere(bm2, u_segments=32, v_segments=16, radius=r)
    rot = Vector((0, 0, 1)).rotation_difference(Vector(tuple(ch.n))).to_matrix().to_4x4()
    bmesh.ops.transform(bm2, matrix=rot, verts=bm2.verts); bmesh.ops.translate(bm2, verts=bm2.verts, vec=Vector(tuple(C)))
    m2 = bpy.data.meshes.new('eye_' + s); bm2.to_mesh(m2); bm2.free()
    for p in m2.polygons: p.use_smooth = True
    eo = bpy.data.objects.new('eye_' + s, m2); bpy.context.scene.collection.objects.link(eo); balls.append(eo)
    lid = np.vstack(rings3)
    info['eyes'][s] = {'C': C.tolist(), 'r': r, 'axis': EM[s]['A'], 'view': ch.n.tolist(), 'width_mm': round(w * 1000, 1),
                       'height_mm': round(h * 1000, 1), 'half_axes_mm': [round(x * 1000, 1) for x in (ea_pos, ea_neg, eb_pos, eb_neg)],
                       'hole_boundary_verts': len(bnd), 'cut': cinfo, 'flipped': flipped, 'shrunk_angles': shrunk,
                       'lid_min_gap_mm': round(float((np.linalg.norm(lid - C, axis=1) - r).min() * 1000), 2),
                       'margin_gap_mm': round(float(np.median(np.linalg.norm(marg - C, axis=1) - r) * 1000), 2)}
    print('EYE', s, json.dumps(info['eyes'][s]))
bm.to_mesh(N.data); bm.free(); N.data.update()
bpy.ops.object.select_all(action='DESELECT')
for eo in balls: eo.select_set(True)
bpy.context.view_layer.objects.active = balls[0]; bpy.ops.object.join(); bpy.context.view_layer.objects.active.name = 'eyes'
N.name = 'face'
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(info, open(os.path.splitext(OUT)[0] + '_eyes.json', 'w'), indent=1)
print('EYES', json.dumps({s: {k: v for k, v in e.items() if k in ('width_mm', 'hole_boundary_verts', 'cut', 'lid_min_gap_mm')} for s, e in info['eyes'].items()}))
