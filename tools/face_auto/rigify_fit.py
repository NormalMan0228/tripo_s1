"""T13 · Rigify face rig fitted to the ORIGINAL head from our automatic landmarks, generated and bound headless.

1. Human metarig, reduced to the spine (head/neck anchor) and the face (faces.super_face, 92 bones).
2. Correspondences metarig joint -> our point: eye corners and lid rims (depth rims, 8 per eye), upper brow
   (MediaPipe 1-6), nose tip, mouth corners, upper/lower lip centre, chin, crown.
3. Similarity (Umeyama) then a thin-plate spline through those pairs moves every face joint; then
   - lid chains sit exactly on the depth rims, lip chains on the lip edges (just above / below the seam),
   - skin joints are projected onto the face surface,
   - jaw: head at the solved jaw pivot, tail at the chin; eyes from the eyeball centres; teeth and tongue from our parts,
   - left/right are averaged so the rig is exactly symmetric.
4. rigify_generate, then automatic (heat) weights on the face mesh. The spine deform bones stay as a still anchor
   for neck and shoulders. Lower teeth and tongue follow DEF-jaw rigidly.
The mesh is not changed: the armature at rest leaves every vertex where it was (checked).
Writes <out>/rigify_fit.blend, <out>/fit_qa.json, <out>/joints.json (2D figure data).
With RIG_POINTS=<rig_points head json> (T14) the face joints come from that file instead of step 2-3.
Usage: blender -b <rig_mouth.blend> -P rigify_fit.py -- <landmarks.json> <eyes_meta.json> <rig_qa.json> <out_dir>
"""
import bpy, addon_utils, sys, os, json, time
import numpy as np
from mathutils import Vector, Matrix
sys.path.append(os.path.dirname(__file__))
from facelib import bvh_of, lids, tps_fit, tps_apply

a = sys.argv[sys.argv.index('--') + 1:]
LMJ, EYES, RQA, OUT = a[0], a[1], a[2], os.path.abspath(a[3])
os.makedirs(OUT, exist_ok=True)
addon_utils.enable('rigify', default_set=True)
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
eyes = json.load(open(EYES)); jaw_pivot = np.array(json.load(open(RQA))['jaw_pivot'])
face = bpy.data.objects['face']
X = np.array([tuple(v.co) for v in face.data.vertices]); XF = [list(p.vertices) for p in face.data.polygons]
bvh = bvh_of(X, XF)
qa = {}

# ---- metarig: spine + face only
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.armature_human_metarig_add()
meta = bpy.context.active_object; meta.name = 'metarig'
bpy.ops.object.mode_set(mode='EDIT')
eb = meta.data.edit_bones
def under_face(b):
    while b:
        if b.name == 'face': return True
        b = b.parent
    return False
for b in list(eb):
    if not (under_face(b) or b.name.startswith('spine')): eb.remove(b)
H = {b.name: np.array(b.head) for b in eb}; Tl = {b.name: np.array(b.tail) for b in eb}
_ends = [(n, e, H[n] if e == 'h' else Tl[n]) for n in H for e in 'ht']
GROUPS = []                                                  # joint ends sharing one point in the metarig
for i, (n, e, p) in enumerate(_ends):
    g = [(m, f) for m, f, q in _ends if np.linalg.norm(q - p) < 1e-5]
    if len(g) > 1 and g[0] == (n, e): GROUPS.append(g)

# ---- our points
ts = np.linspace(0, 1, 5)
rim = {s: lids(np.array(eyes[s]['raw']), ts) for s in 'RL'}
pairs = []
def P(m, t): pairs.append((m, t))
for s in 'LR':
    up, lo = rim[s]['up'], rim[s]['lo']                     # both run outer -> inner
    chT = ['lid.T.%s' % s, 'lid.T.%s.001' % s, 'lid.T.%s.002' % s, 'lid.T.%s.003' % s, 'lid.B.%s' % s]
    for k, n in enumerate(chT): P(H[n], up[k])
    chB = {1: 'lid.B.%s.003' % s, 2: 'lid.B.%s.002' % s, 3: 'lid.B.%s.001' % s}
    for k, n in chB.items(): P(H[n], lo[k])
for mid, ids in (('L', (6, 5, 4)), ('R', (1, 2, 3))):
    for n, i in zip(('brow.T.%s.001', 'brow.T.%s.002', 'brow.T.%s.003'), ids): P(H[n % mid], LT[i])
P(H['nose.002'], LT[16])
P(Tl['lip.T.L.001'], LT[22]); P(Tl['lip.T.R.001'], LT[20])
seam_c = (LT[34] + LT[35]) / 2
def on_surface(p):
    return np.array(bvh.find_nearest(Vector(p))[0])
P(H['lip.T.L'], on_surface(seam_c + [0, 0, 0.0035])); P(H['lip.B.L'], on_surface(seam_c - [0, 0, 0.0035]))
P(H['chin'], LT[24])
P(Tl['spine.006'], LT[31])
M = np.array([p[0] for p in pairs]); T = np.array([p[1] for p in pairs])
def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); A0, B0 = A - ma, B - mb
    U, D, Vt = np.linalg.svd(B0.T @ A0 / len(A)); Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ Sg @ Vt; s = np.trace(np.diag(D) @ Sg) / (A0 ** 2).sum(1).mean(); return s, R, mb - s * R @ ma
s, R, t = umeyama(M, T)
sim = lambda Q: s * np.asarray(Q) @ R.T + t
tps = tps_fit(sim(M), T, lam=1e-9)
qa['similarity_scale'] = float(s)
qa['pairs'] = len(pairs)
qa['similarity_residual_mm'] = round(float(np.linalg.norm(sim(M) - T, axis=1).mean() * 1000), 2)

face_bones = [b.name for b in eb if under_face(b)]
newH, newT = {}, {}
for b in eb:
    if b.name in face_bones:
        newH[b.name], newT[b.name] = tps_apply(tps, sim([H[b.name], Tl[b.name]]))
    else:
        newH[b.name], newT[b.name] = sim([H[b.name], Tl[b.name]])
# skin joints onto the surface
skin_prefix = ('brow', 'lid', 'lip', 'cheek', 'forehead', 'temple', 'jaw.', 'chin', 'ear', 'nose')
for n in face_bones:
    if n.startswith(skin_prefix):
        newH[n] = on_surface(newH[n]); newT[n] = on_surface(newT[n])
# T14: face joints from rig_points.py (about 300 dense MediaPipe pairs through the MPFB template, ears found on the
# head) instead of the 29-pair fit above; lids, eyes, jaw, teeth and tongue are still set below from our cuts/parts
RP = os.environ.get('RIG_POINTS')
if RP:
    rp = json.load(open(RP))['joints']
    for n in face_bones:
        if n in rp: newH[n], newT[n] = np.array(rp[n][0]), np.array(rp[n][1])
    qa['joints_from'] = 'rig_points (%d joints)' % sum(1 for n in face_bones if n in rp)
    # rig_points' pivot comes from the face points; the rig_qa pivot comes from the whole-head template fit, which
    # drifts on busts and full bodies (pivot at chin height -> the lower teeth swing forward out of the lip)
    jaw_pivot = np.array(rp['jaw'][0]); qa['jaw_pivot_from'] = 'rig_points'
else:
    qa['joints_from'] = '29-pair fit'
# lid chains exactly on the rims (connected chain: heads, last tail = first head)
for s_ in 'LR':
    up, lo = rim[s_]['up'], rim[s_]['lo']
    ring = [up[0], up[1], up[2], up[3], up[4], lo[3], lo[2], lo[1]]
    names = ['lid.T.%s' % s_, 'lid.T.%s.001' % s_, 'lid.T.%s.002' % s_, 'lid.T.%s.003' % s_,
             'lid.B.%s' % s_, 'lid.B.%s.001' % s_, 'lid.B.%s.002' % s_, 'lid.B.%s.003' % s_]
    for k, n in enumerate(names):
        newH[n] = ring[k]; newT[n] = ring[(k + 1) % 8]
    C = np.array(eyes[s_]['C']); r = eyes[s_]['r']
    newH['eye.%s' % s_] = C.copy(); newT['eye.%s' % s_] = C + np.array([0, -r, 0])
# jaw from the solved pivot to the chin; chin chain follows
newH['jaw'] = jaw_pivot.copy(); newT['jaw'] = LT[24].copy(); newH['chin'] = LT[24].copy()
# teeth and tongue from our parts
def obj_pts(n):
    o = bpy.data.objects.get(n); return None if o is None else np.array([tuple(o.matrix_world @ v.co) for v in o.data.vertices])
for n in ('teeth.T', 'teeth.B'):
    Pp = obj_pts('teeth_up' if n == 'teeth.T' else 'teeth_lo')
    if Pp is not None:
        f = Pp[np.argmin(Pp[:, 1])]; newH[n] = np.array([0, f[1], Pp[:, 2].mean()]); newT[n] = newH[n] + [0, np.ptp(Pp[:, 1]), 0]
Pt = obj_pts('tongue')
if Pt is not None:
    y0, y1 = Pt[:, 1].min(), Pt[:, 1].max(); zc = Pt[:, 2].max() - 0.002
    js = [np.array([0, y0 + (y1 - y0) * k / 3, zc]) for k in range(4)]
    for k, n in enumerate(('tongue', 'tongue.001', 'tongue.002')): newH[n], newT[n] = js[k], js[k + 1]
# exact symmetry: average each .L joint with the mirrored .R one; centre bones on x = 0
mir = np.array([-1, 1, 1])
for n in list(newH):
    if n.endswith('.L') or '.L.' in n:
        m = n.replace('.L', '.R')
        if m in newH:
            for D_ in (newH, newT):
                avg = (D_[n] + D_[m] * mir) / 2; D_[n] = avg; D_[m] = avg * mir
    elif not ('.R' in n):
        newH[n][0] = 0.0; newT[n][0] = 0.0
# ends that shared one point in the metarig share it again (the lid rings and jaw/chin were set on their own)
fixed = {(n, e) for s_ in 'LR' for n in ('lid.T.%s' % s_, 'lid.T.%s.001' % s_, 'lid.T.%s.002' % s_, 'lid.T.%s.003' % s_,
         'lid.B.%s' % s_, 'lid.B.%s.001' % s_, 'lid.B.%s.002' % s_, 'lid.B.%s.003' % s_) for e in 'ht'} | {('jaw', 't'), ('chin', 'h')}
for g in GROUPS:
    src = next((m for m in g if m in fixed), g[0])
    v = (newH if src[1] == 'h' else newT)[src[0]].copy()
    for n, e in g: (newH if e == 'h' else newT)[n] = v.copy()
# connected bones must share the joint: a child's head = its parent's tail
for b in eb:
    if b.use_connect and b.parent: newH[b.name] = newT[b.parent.name]
for b in eb:
    b.head = Vector(newH[b.name]); b.tail = Vector(newT[b.name])
bpy.ops.armature.select_all(action='SELECT')
bpy.ops.object.mode_set(mode='OBJECT')
qa['face_bones'] = len(face_bones)

# ---- dense face (RIG_DENSE, default on): more rig points. The fitted super_face metarig is upgraded to Rigify's
# modular face (skin chains take any number of bones); lid, lip, brow and cheek chains are split in two (deform
# bones 94 -> ~130). Lid joints then sit evenly (arc length) on the eye organ's margin ring, lip joints on a lip ring
# of the mouth organ (2 rings outside the slit), corners shared by upper and lower and set on the slit corner itself
# (RIG_LIP_CORNER; RIG_LIP_FRAC packs the lip joints); brow/cheek midpoints go onto the
# skin. jaw_master (the jaw hinge in this rig) goes to the solved pivot. Built on the left, mirrored to the right.
DENSE = os.environ.get('RIG_DENSE', '1') != '0' and 'eye_ring' in face.data.attributes and 'mouth_ring' in face.data.attributes
qa['dense'] = DENSE
if DENSE:
    meta.select_set(True); bpy.context.view_layer.objects.active = meta
    bpy.ops.object.mode_set(mode='POSE'); bpy.ops.pose.rigify_upgrade_face(); bpy.ops.object.mode_set(mode='EDIT')
    eb = meta.data.edit_bones
    def chain(root):
        seq = [eb[root]]
        while True:
            c = [x for x in seq[-1].children if x.use_connect]
            if not c: return seq
            seq.append(c[0])
    ROOTS = [r % s_ for s_ in 'LR' for r in ('lid.T.%s', 'lid.B.%s', 'lip.T.%s', 'lip.B.%s', 'brow.T.%s', 'brow.B.%s', 'cheek.T.%s', 'cheek.B.%s')]
    ROOTS = [r for r in ROOTS if r in eb]
    bpy.ops.armature.select_all(action='DESELECT')
    for r in ROOTS:
        for b in chain(r): b.select = b.select_head = b.select_tail = True
    bpy.ops.armature.subdivide(number_cuts=1)
    CH = {r: chain(r) for r in ROOTS}
    def move_pt(old, new):                                   # every bone end on the old point follows (glue, corners)
        old = Vector(tuple(old))
        for b in eb:
            for e in ('head', 'tail'):
                if (getattr(b, e) - old).length < 1e-6: setattr(b, e, Vector(tuple(new)))
    def arc_pts(P, n, fr=None):                              # n+1 points evenly by arc length along polyline P (or at fractions fr)
        s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        t_ = np.linspace(0, s_[-1], n + 1) if fr is None or len(fr) != n + 1 else np.asarray(fr) * s_[-1]
        return np.c_[[np.interp(t_, s_, P[:, j]) for j in range(3)]].T
    def ring_loop(attr, uattr, k):
        rg_ = np.array([d.value for d in face.data.attributes[attr].data]); u_ = np.array([d.value for d in face.data.attributes[uattr].data])
        ids = np.where(rg_ == k)[0]; return X[ids[np.argsort(u_[ids])]]
    def path(L, i0, i1, avoid):                              # the way round the closed loop from i0 to i1 not through avoid
        n = len(L); fw = [(i0 + j) % n for j in range((i1 - i0) % n + 1)]; bw = [(i0 - j) % n for j in range((i0 - i1) % n + 1)]
        return L[bw] if avoid in fw else L[fw]
    def place(root, P):                                      # chain joints onto points P (len = bones + 1)
        for k, b in enumerate(CH[root]):
            if k == 0: move_pt(b.head.copy(), P[0])
            move_pt(b.tail.copy(), P[k + 1])
    rg_e = np.array([d.value for d in face.data.attributes['eye_ring'].data]); KE = int(np.abs(rg_e).max()) - 2
    Le = ring_loop('eye_ring', 'eye_u', KE)                  # left eye margin ring (+x), closed, in u order
    oc, ic = np.array(eb['lid.T.L'].head), np.array(eb['lid.B.L'].head)          # outer / inner corner joints
    io, ii = int(np.argmin(np.linalg.norm(Le - oc, axis=1))), int(np.argmin(np.linalg.norm(Le - ic, axis=1)))
    lo_i = int(np.argmin(Le[:, 2]))                          # a lower-lid vertex: the upper path must avoid it
    place('lid.T.L', arc_pts(path(Le, io, ii, lo_i), len(CH['lid.T.L'])))
    hi_i = int(np.argmax(Le[:, 2]))
    place('lid.B.L', arc_pts(path(Le, ii, io, hi_i), len(CH['lid.B.L'])))
    rg_m = np.array([d.value for d in face.data.attributes['mouth_ring'].data]); KS = int(rg_m.max()) - 7
    Lm = ring_loop('mouth_ring', 'mouth_u', KS - 2)          # lip ring 2 outside the slit, closed, in u order
    u_m = np.array([d.value for d in face.data.attributes['mouth_u'].data]); im_ = np.where(rg_m == KS - 2)[0]; um = np.sort(u_m[im_])
    # lip centres by mouth_u (0.25 top, 0.75 bottom), not by height: cartoon mouth corners sit below the lip centres (f11)
    ic_ = int(np.argmax(Lm[:, 0])); up_c = int(np.argmin(np.abs(um - 0.25))); lo_c = int(np.argmin(np.abs(um - 0.75)))
    # lip joints by arc length from the centre to the corner; RIG_LIP_FRAC (comma list, bones + 1 values) packs them toward the corner
    LF = [float(v) for v in os.environ.get('RIG_LIP_FRAC', '').split(',') if v.strip()] or None
    pT_ = arc_pts(path(Lm, up_c, ic_, lo_c), len(CH['lip.T.L']), LF); pB_ = arc_pts(path(Lm, lo_c, ic_, up_c), len(CH['lip.B.L']), LF)
    qa['lip_joint_frac'] = LF or 'even'
    # the shared corner joint (lip_end, also the head of cheek.B and the tail of chin.L) exactly on the slit corner
    # (mouth_u = 0), not on the lip ring's outermost point 2 rings further out (P heads: 1.8-2.8 mm lateral of the
    # commissure, so the corner control pulled skin beside the corner); env RIG_LIP_CORNER=ring: the old placement
    if os.environ.get('RIG_LIP_CORNER', 'slit') == 'slit':
        sl_m = np.where(rg_m == KS)[0]; cs_ = X[sl_m[np.argmin(np.minimum(u_m[sl_m], 1 - u_m[sl_m]))]]
        qa['lip_corner_moved_mm'] = round(float(np.linalg.norm(pT_[-1] - cs_) * 1000), 2); pT_[-1] = cs_; pB_[-1] = cs_
    place('lip.T.L', pT_)
    place('lip.B.L', pB_)
    for r in [r for r in ROOTS if r.startswith(('brow', 'cheek')) and r.endswith('.L')]:
        for b in CH[r][:-1]: move_pt(b.tail.copy(), on_surface(np.array(b.tail)))
    # ---- mouth plus (2026-10-13, env RIG_MOUTH_PLUS=0: off): more rig points round the mouth
    #  - lips: the bone next to each corner is split again (5 bones per half lip), joints at arc fractions
    #    RIG_LIP_FRAC5 (default 0, .25, .5, .74, .885, 1): a control 11 % of the lip length from the corner keeps the
    #    upper lip up while the corner drops on jawOpen (the template's lip edge bends sharply there)
    #  - modiolus: the first cheek.B bone (corner -> cheek.B.002) is split; its joint goes 40 % of the way out
    #  - mentalis / marionette: chin.L (jaw side -> corner) is split; its joint goes onto the skin
    #  - nasolabial: a new 2-bone skin chain from the nose wing (end of nose.L) over the fold to the modiolus, typed
    #    like cheek.B (Rigify glues its ends to the nose and modiolus controls)
    MPLUS = os.environ.get('RIG_MOUTH_PLUS', '1') != '0'
    qa['mouth_plus'] = MPLUS
    if MPLUS:
        split = []
        MP_LIP, MP_MOD, MP_CHIN = (os.environ.get(k_, '1') != '0' for k_ in ('RIG_MP_LIP', 'RIG_MP_MODIOLUS', 'RIG_MP_CHIN'))
        for s_ in 'LR':
            if MP_LIP: split += [CH['lip.T.%s' % s_][-1], CH['lip.B.%s' % s_][-1]]
            if MP_MOD and 'cheek.B.%s' % s_ in CH: split.append(CH['cheek.B.%s' % s_][0])
            if MP_CHIN and 'chin.%s' % s_ in eb: split.append(eb['chin.%s' % s_])
        bpy.ops.armature.select_all(action='DESELECT')
        for b in split: b.select = b.select_head = b.select_tail = True
        bpy.ops.armature.subdivide(number_cuts=1)
        CH = {r: chain(r) for r in ROOTS}
        LF5 = [float(v) for v in os.environ.get('RIG_LIP_FRAC5', '0,0.25,0.5,0.74,0.885,1').split(',') if v.strip()] if MP_LIP else LF
        pT_ = arc_pts(path(Lm, up_c, ic_, lo_c), len(CH['lip.T.L']), LF5); pB_ = arc_pts(path(Lm, lo_c, ic_, up_c), len(CH['lip.B.L']), LF5)
        csn = np.array(CH['lip.T.L'][-1].tail); pT_[-1] = csn; pB_[-1] = csn
        place('lip.T.L', pT_); place('lip.B.L', pB_); qa['lip_joint_frac'] = LF5; qa['lip_bones_per_half'] = len(CH['lip.T.L'])
        cb = CH.get('cheek.B.L') if MP_MOD else None
        if cb is not None:
            pm = on_surface(csn + 0.4 * (np.array(cb[1].tail) - csn)); move_pt(cb[0].tail.copy(), pm); qa['modiolus_from_corner_mm'] = round(float(np.linalg.norm(pm - csn) * 1000), 1)
        if MP_CHIN and 'chin.L' in eb:
            move_pt(eb['chin.L'].tail.copy(), on_surface(np.array(eb['chin.L'].tail)))
        if os.environ.get('RIG_NASOLABIAL', '1') != '0' and 'nose.L' in eb and cb is not None:
            A_ = np.array(eb['nose.L'].tail); M_ = np.array(cb[0].tail); N_ = on_surface((A_ + M_) / 2)
            for s_, mx in (('L', 1.0), ('R', -1.0)):
                m3 = np.array([mx, 1, 1]); par = eb['cheek.B.%s' % s_].parent
                b1 = eb.new('nasolabial.%s' % s_); b1.head = Vector(tuple(A_ * m3)); b1.tail = Vector(tuple(N_ * m3)); b1.parent = par
                b2 = eb.new('nasolabial.%s.001' % s_); b2.head = Vector(tuple(N_ * m3)); b2.tail = Vector(tuple(M_ * m3)); b2.parent = b1; b2.use_connect = True
            qa['nasolabial'] = True
    # ---- tongue v3 (organ_teeth_v3: point attributes tongue_v 0 tip .. 1 back, tongue_top 1 dorsum / 0 underside;
    # env RIG_TONGUE4=0: off): a 4-bone chain on the tongue's mid-line (half way between dorsum and underside at x = 0,
    # at tongue_v 0, .25, .5, .75, 1), instead of 3 bones in a straight line 2 mm under the top (the root of the v3
    # tongue curves down, so the last bone ended outside it)
    tgo = bpy.data.objects.get('tongue')
    if os.environ.get('RIG_TONGUE4', '1') != '0' and tgo is not None and 'tongue_v' in tgo.data.attributes and 'tongue.002' in eb:
        TV = np.array([d.value for d in tgo.data.attributes['tongue_v'].data]); TX = np.array([tuple(tgo.matrix_world @ v.co) for v in tgo.data.vertices])
        jts = []
        for vv in (0.0, 0.25, 0.5, 0.75, 1.0):
            sel = (np.abs(TV - vv) < 0.07) & (np.abs(TX[:, 0]) < 0.25 * np.ptp(TX[:, 0]))
            if sel.sum() < 3: sel = np.argsort(np.abs(TV - vv))[:12]
            P_ = TX[sel]; jts.append(np.array([0.0, P_[:, 1].mean(), (P_[:, 2].max() + P_[:, 2].min()) / 2]))
        if 'tongue.003' not in eb:
            bpy.ops.armature.select_all(action='DESELECT'); t2 = eb['tongue.002']; t2.select = t2.select_head = t2.select_tail = True
            bpy.ops.armature.subdivide(number_cuts=1)
        tch = [eb['tongue']]
        while True:
            c_ = [x for x in tch[-1].children if x.use_connect and x.name.startswith('tongue')]
            if not c_: break
            tch.append(c_[0])
        if len(tch) == 4:
            for k_, bt_ in enumerate(tch): bt_.head = Vector(tuple(jts[k_])); bt_.tail = Vector(tuple(jts[k_ + 1]))
            qa['tongue_chain'] = [b_.name for b_ in tch]; qa['tongue_joints_mm'] = [(j_ * 1000).round(1).tolist() for j_ in jts]
    jm = eb.get('jaw_master')
    if jm is not None: jm.head = Vector(tuple(jaw_pivot)); jm.tail = Vector(tuple(LT[24]))
    # mirror: every right-side bone = mirror of its left twin; centre bones on x = 0
    twin = lambda n: n.replace('.L', '\0').replace('.R', '.L').replace('\0', '.R')
    for b in eb:
        if '.R' in b.name and twin(b.name) in eb:
            l_ = eb[twin(b.name)]; b.head = Vector((-l_.head.x, l_.head.y, l_.head.z)); b.tail = Vector((-l_.tail.x, l_.tail.y, l_.tail.z)); b.roll = -l_.roll
        elif '.L' not in b.name and '.R' not in b.name and abs(b.head.x) < 0.004 and abs(b.tail.x) < 0.004:
            b.head.x = 0.0; b.tail.x = 0.0
    newH = {b.name: np.array(b.head) for b in eb}; newT = {b.name: np.array(b.tail) for b in eb}
    bpy.ops.object.mode_set(mode='OBJECT')
    if qa.get('nasolabial'):                                 # the new chains take cheek.B's Rigify type and parameters
        for s_ in 'LR':
            src_, dst_ = meta.pose.bones['cheek.B.%s' % s_], meta.pose.bones['nasolabial.%s' % s_]
            dst_.rigify_type = src_.rigify_type
            for k_ in src_.rigify_parameters.bl_rna.properties.keys():
                if k_ in ('rna_type', 'name'): continue
                try: setattr(dst_.rigify_parameters, k_, getattr(src_.rigify_parameters, k_))
                except Exception: pass
            meta.pose.bones['nasolabial.%s.001' % s_].rigify_type = ''
    qa['dense_face_bones'] = sum(1 for b in meta.data.bones if under_face(b)); qa['dense_split_chains'] = len(ROOTS)
    qa['dense_lid_ring'] = KE; qa['dense_lip_ring'] = KS - 2
# 2D joint data for the figure
json.dump({n: [newH[n].tolist(), newT[n].tolist()] for n in newH}, open(os.path.join(OUT, 'joints.json'), 'w'))

# ---- generate
t0 = time.time()
bpy.ops.object.select_all(action='DESELECT'); meta.select_set(True); bpy.context.view_layer.objects.active = meta
bpy.ops.pose.rigify_generate()
rig = [o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name not in ('metarig', 'lid_rig')][0]
rig.name = 'face_rig'
qa['generate_s'] = round(time.time() - t0, 1); qa['rig_bones'] = len(rig.data.bones)
# Rigify puts jaw_master (and the MCH-jaw_master lip-follow chain, copies of it) at the jaw.L/R heads, beside the eyes;
# turning it swings the chin backward. The jaw hinges at the 'jaw' bone head (the solved joint, where DEF-jaw starts):
# the chain moves its heads there, each keeping its length share along the hinge -> chin line and jaw_master's roll.
rig['jaw_pivot'] = [float(c) for c in jaw_pivot]               # read by rigify_bake (the jaw turns about it)
for o in bpy.context.view_layer.objects: o.select_set(False)
rig.select_set(True); bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones
if not DENSE and 'jaw' in eb and 'jaw_master' in eb:      # (dense: jaw_master was put on the pivot in the metarig)
    jm = eb['jaw_master']; h0, L0 = jm.head.copy(), (jm.tail - jm.head).length; hinge = eb['jaw'].head.copy(); roll = jm.roll
    qa['jaw_master_moved_mm'] = round((hinge - h0).length * 1000, 1)
    for b in [jm] + [b for b in eb if b.name.startswith('MCH-jaw_master')]:
        f = (b.tail - b.head).length / L0
        b.head = hinge; b.tail = hinge + (jm.tail - hinge) * f if b is not jm else jm.tail; b.roll = roll
# the tongue rides on exactly what the lower teeth ride on: its root bones hang from DEF-jaw (teeth_lo is bound to
# DEF-jaw) instead of ORG-jaw_master (env RIG_TONGUE_JAW=0: off). (The jawOpen 'stalk' itself came from the bake
# pinning the tweak_tongue controls, fixed in rigify_bake.py.)
if os.environ.get('RIG_TONGUE_JAW', '1') != '0' and 'DEF-jaw' in eb:
    qa['tongue_reparented'] = []
    for b in eb:
        if 'tongue' in b.name and b.parent is not None and b.parent.name == 'ORG-jaw_master':
            b.use_connect = False; b.parent = eb['DEF-jaw']; qa['tongue_reparented'].append(b.name)
bpy.ops.object.mode_set(mode='OBJECT')

# ---- bind: heat weights on the face mesh (face + spine deform bones). Blender's heat solver fails on a 24 cm head
# ("failed to find solution"), so it runs on a 10x scaled copy and the groups are copied back by vertex index.
# It also fails on an exactly mirrored head (centre-line vertices and bones in one plane; f11 lost every weight):
# the copy's vertices are moved by ~0.02 mm noise, which only the weights see (sym_lock.py makes them symmetric again)
t0 = time.time()
X0 = np.array([tuple(v.co) for v in face.data.vertices])
for attempt, jit in enumerate((2e-5, 5e-5, 1e-4)):
    cp = face.copy(); cp.data = face.data.copy(); bpy.context.scene.collection.objects.link(cp)
    cp.shape_key_clear(); cp.modifiers.clear(); cp.vertex_groups.clear(); cp.parent = None
    cp.data.vertices.foreach_set('co', (X0 + np.random.default_rng(attempt + 1).normal(0, jit, X0.shape)).ravel()); cp.data.update()
    rc = rig.copy(); rc.data = rig.data.copy(); bpy.context.scene.collection.objects.link(rc)
    for b in rc.data.bones:                              # the skin never follows the tongue or the teeth
        if b.name.startswith(('DEF-tongue', 'DEF-teeth', 'DEF-eye.', 'DEF-eye_iris')): b.use_deform = False   # eyeballs are their own mesh
    cp.scale = (10, 10, 10); rc.scale = (10, 10, 10); bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects: o.select_set(False)
    cp.select_set(True); rc.select_set(True); bpy.context.view_layer.objects.active = rc
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    n_heat = sum(1 for v in cp.data.vertices if not v.groups)
    if n_heat < 0.01 * len(X0) or attempt == 2: break
    rcd = rc.data; bpy.data.objects.remove(cp); bpy.data.objects.remove(rc); bpy.data.armatures.remove(rcd)
qa['heat_attempts'] = attempt + 1; qa['heat_jitter_mm'] = jit * 1000; qa['heat_unweighted'] = n_heat
names = {g.index: g.name for g in cp.vertex_groups}
vg = {n: face.vertex_groups.new(name=n) for n in names.values()}
for v in cp.data.vertices:
    for g in v.groups:
        if g.weight > 1e-4: vg[names[g.group]].add([v.index], g.weight, 'REPLACE')
rcd = rc.data; bpy.data.objects.remove(cp); bpy.data.objects.remove(rc); bpy.data.armatures.remove(rcd)
md = face.modifiers.new('face_rig', 'ARMATURE'); md.object = rig
# heat weights have hard edges between neighbouring bones; smooth them over the mesh (the lip and eye cuts keep
# upper and lower apart, because smoothing only spreads along edges), then normalise
SMOOTH = int(os.environ.get('RIG_SMOOTH', '40'))
if SMOOTH:
    for o in bpy.context.view_layer.objects: o.select_set(False)
    face.select_set(True); bpy.context.view_layer.objects.active = face
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    bpy.ops.object.vertex_group_smooth(group_select_mode='BONE_DEFORM', factor=0.5, repeat=SMOOTH, expand=0.0)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM', lock_active=False)
    bpy.ops.object.mode_set(mode='OBJECT')
qa['weight_smooth_repeat'] = SMOOTH
# neck and shoulders belong to the still head bone: below the chin the face bones fade out over 45 mm (smoothing
# otherwise spreads the jaw down to the shoulders and jawOpen drags them)
chin_z = LT[24][2]; fade = np.clip((X[:, 2] - (chin_z - 0.050)) / 0.045, 0, 1); fade = fade * fade * (3 - 2 * fade)
head_g = face.vertex_groups.get('DEF-spine.006') or face.vertex_groups.new(name='DEF-spine.006')
face_idx = {g.index for g in face.vertex_groups if not g.name.startswith('DEF-spine')}
moved = 0
for v in face.data.vertices:
    m = fade[v.index]
    if m >= 1: continue
    take = 0.0
    for g in v.groups:
        if g.group in face_idx and g.weight > 0:
            take += g.weight * (1 - m); g.weight *= m
    if take > 0:
        head_g.add([v.index], take, 'ADD'); moved += 1
qa['neck_reweighted_verts'] = moved
qa['bind_s'] = round(time.time() - t0, 1)
n_unw = sum(1 for v in face.data.vertices if sum(g.weight for g in v.groups) < 1e-6)
qa['unweighted_verts'] = n_unw; qa['vertex_groups'] = len(face.vertex_groups)
# lower teeth ride on the jaw, upper teeth on the head; the tongue on the tongue bones (which follow the jaw)
for n in ('teeth_lo', 'teeth_up'):
    o = bpy.data.objects.get(n)
    if not o: continue
    g = o.vertex_groups.new(name='DEF-jaw' if n == 'teeth_lo' else 'DEF-spine.006')
    g.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
    md = o.modifiers.new('rig', 'ARMATURE'); md.object = rig
o = bpy.data.objects.get('tongue')
TCH = qa.get('tongue_chain')
if o and os.environ.get('RIG_TONGUE_STATIC', '1') != '0' and 'DEF-jaw' in rig.data.bones:
    # 2026-10-13 user: the tongue is not finished - it rides the jaw rigidly (100 % DEF-jaw, no bending; the tongue
    # chain stays in the rig, unused). env RIG_TONGUE_STATIC=0: the tongue_v-blended chain below
    gj = o.vertex_groups.new(name='DEF-jaw'); gj.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
    md = o.modifiers.new('rig', 'ARMATURE'); md.object = rig; qa['tongue_weights'] = 'static: DEF-jaw 1.0'
elif o and TCH and 'tongue_v' in o.data.attributes and all('DEF-' + n_ in rig.data.bones for n_ in TCH) and 'DEF-jaw' in rig.data.bones:
    # tongue v3: weights blended linearly between neighbouring chain bones along tongue_v (bone k centred at (k+.5)/4),
    # the underside behind the tip (tongue_top = 0) and the root (tongue_v > 0.85) partly on DEF-jaw, so the floor
    # attachment and the root stay anchored in tongueOut
    TV = np.array([d.value for d in o.data.attributes['tongue_v'].data])
    TT_ = np.array([d.value for d in o.data.attributes['tongue_top'].data]) if 'tongue_top' in o.data.attributes else np.ones(len(TV))
    gdef = [o.vertex_groups.new(name='DEF-' + n_) for n_ in TCH]; gj = o.vertex_groups.new(name='DEF-jaw')
    ss_ = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
    nb = len(TCH); c_ = (np.arange(nb) + 0.5) / nb
    # jaw share: root ramp over tongue_v 0.7 -> 1 (0.85 -> 1 kinked the root underside 30 deg in tongueOut), underside
    # 0.35 behind the tip; smoothed over the tongue mesh (12
    # passes): a hard dorsum / underside step folded the lateral margins over in tongueOut (dihedral up to 177 deg)
    AJ = np.maximum(ss_((TV - 0.7) / 0.3), 0.35 * ss_((TV - 0.15) / 0.3) * (1 - TT_))
    nbr_ = [[] for _ in range(len(TV))]
    for e_ in o.data.edges: a0_, a1_ = e_.vertices; nbr_[a0_].append(a1_); nbr_[a1_].append(a0_)
    for _ in range(12): AJ = np.array([0.5 * AJ[i] + 0.5 * AJ[nb_].mean() if nb_ else AJ[i] for i, nb_ in enumerate(nbr_)])
    WT = np.zeros((len(TV), nb + 1))
    for v in o.data.vertices:
        vv = float(TV[v.index]); w = np.zeros(nb)
        if vv <= c_[0]: w[0] = 1
        elif vv >= c_[-1]: w[-1] = 1
        else:
            k_ = int(np.searchsorted(c_, vv)) - 1; t_ = (vv - c_[k_]) / (c_[k_ + 1] - c_[k_]); w[k_], w[k_ + 1] = 1 - t_, t_
        a_ = float(AJ[v.index]); WT[v.index, :nb] = w * (1 - a_); WT[v.index, nb] = a_
    # the whole weight set smoothed over the mesh too (RIG_TONGUE_SMOOTH passes, default 12): the joints of a short tongue
    # (P f09) kinked in tongueOut (25.9 deg)
    for _ in range(int(os.environ.get('RIG_TONGUE_SMOOTH', '12'))): WT = np.array([0.5 * WT[i] + 0.5 * WT[nb_].mean(0) if nb_ else WT[i] for i, nb_ in enumerate(nbr_)])
    WT /= np.maximum(WT.sum(1, keepdims=True), 1e-9)
    for v in o.data.vertices:
        for k_ in range(nb):
            if WT[v.index, k_] > 1e-4: gdef[k_].add([v.index], float(WT[v.index, k_]), 'REPLACE')
        if WT[v.index, nb] > 1e-4: gj.add([v.index], float(WT[v.index, nb]), 'REPLACE')
    md = o.modifiers.new('rig', 'ARMATURE'); md.object = rig; qa['tongue_weights'] = 'tongue_v blend + jaw anchor'
elif o:
    segs = [(n, np.array(rig.data.bones[n].head_local), np.array(rig.data.bones[n].tail_local))
            for n in ('DEF-tongue', 'DEF-tongue.001', 'DEF-tongue.002') if n in rig.data.bones]
    groups = {n: o.vertex_groups.new(name=n) for n, _, _ in segs}
    for v in o.data.vertices:
        p = np.array(v.co)
        dist = []
        for n, h, t in segs:
            ab = t - h; u = np.clip((p - h) @ ab / (ab @ ab), 0, 1); dist.append(np.linalg.norm(h + u * ab - p))
        groups[segs[int(np.argmin(dist))][0]].add([v.index], 1.0, 'REPLACE')
    md = o.modifiers.new('rig', 'ARMATURE'); md.object = rig
# rest check: armature at rest must not move the face
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); ev = face.evaluated_get(dg)
E = np.array([tuple(v.co) for v in ev.data.vertices])
qa['rest_offset_mm'] = round(float(np.abs(E - X).max() * 1000), 4)
json.dump(qa, open(os.path.join(OUT, 'fit_qa.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'rigify_fit.blend'), compress=True)
print('FIT', json.dumps(qa))
