"""T13 · ARKit expressions from the fitted Rigify face rig: pose library (authored once) -> shape keys on the original.

Every pose is a list of control moves written in head space (mm, +x = character's left, -y = forward, +z = up) and
in degrees for the jaw, so it does not depend on bone rolls and works for any head the fitter rigs. _L poses are
mirrored to _R automatically. Each pose is applied to the generated rig, the face (and lower teeth / tongue) is
evaluated and stored as a shape key, then the rig returns to rest. Keys relative to another pose (mouthClose is
"jawOpen + lips closed" minus jawOpen) are supported.
Not baked here: eyeBlink (T1 lid parts, bones) and eyeLook (eyeball bones) - 10 of the 52.
QA per key: largest move, left/right agreement of mirrored pairs, faces the key turns over.
Writes <out>/arkit.blend (face with the keys, rig removed for export), <out>/arkit_rig.blend (rig kept),
<out>/bake_qa.json.
Usage: blender -b <rigify_fit.blend> -P rigify_bake.py -- <out_dir> [--mpfb <mpfb_head.blend> <fit.blend>] [--k 1.0] [--style <styles/x.json>]
  --style (2026-10-14): per-appearance pose file written by hand (tools/face_auto/styles, build_styles.py). Each key in it
  replaces the MPFB pose: the jaw turns by jaw_deg (positive opens) and every listed control moves by d (x, y, z in
  units of this head's half mouth width; head space: +x character's left, -y forward, +z up) from its base position.
  base 'jaw' = rest with the jaw turned (lower-face controls follow the jaw as the rig does), 'mpfb' = the MPFB pose.
  env BAKE_STYLE_SUFFIX (e.g. '_s'): store the style keys under that suffix next to the MPFB ones (for comparison);
  env BAKE_ONLY=key,key: bake only those keys (fast trials).
  --mpfb: pose library read from the CC0 MPFB ARKit template (default when given); without it the hand-written library
  binding (2026-10-13): no sideways shift for mirror-symmetric heads (BAKE_SYM_X), mouth frame carried onto the
  template's lips (BAKE_MOUTH_ALIGN), mouthClose sealed (BAKE_SEAL); QA in bake_qa.json 'bind', 'mouthClose_seal'
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0])
MPFB = (a[a.index('--mpfb') + 1], a[a.index('--mpfb') + 2]) if '--mpfb' in a else None
STYLE = a[a.index('--style') + 1] if '--style' in a else None          # appearance template pose file (styles/*.json)
K = float(a[a.index('--k') + 1]) if '--k' in a else 1.0       # expression strength (1 = template size)
K_JAW = float(a[a.index('--k-jaw') + 1]) if '--k-jaw' in a else 0.7      # jaw keys: the template's human jaw drop is too
K_UP = float(a[a.index('--k-upper') + 1]) if '--k-upper' in a else 1.5   # big for this head; brows/eyes/cheeks/nose read
def k_for(names):                                                        # better a little stronger on a cartoon face
    n = names[0]
    if n.startswith('jaw') or n == 'mouthClose': return K * K_JAW
    if n.startswith(('brow', 'eye', 'cheek', 'nose')): return K * K_UP
    return K
os.makedirs(OUT, exist_ok=True)
rig = bpy.data.objects['face_rig']; face = bpy.data.objects['face']
pb = rig.pose.bones
mm = 0.001

# control groups found by position (inner/outer order does not depend on names)
def ctl(n): return pb.get(n)
def side_chain(prefix, s):
    bs = [b for b in pb if b.name.startswith(prefix + '.' + s) and not b.name.startswith(('ORG', 'DEF', 'MCH'))]
    return sorted(bs, key=lambda b: abs(b.bone.head_local.x))           # inner first
BROW_T = {s: side_chain('brow.T', s) for s in 'LR'}; BROW_B = {s: side_chain('brow.B', s) for s in 'LR'}
LID_T = {s: [ctl('lid.T.%s.%03d' % (s, k)) for k in (1, 2, 3)] for s in 'LR'}
LID_B = {s: [ctl('lid.B.%s.%03d' % (s, k)) for k in (1, 2, 3)] for s in 'LR'}

def T(*names_or_bones, d=(0, 0, 0)):
    return [('T', n, np.array(d, float)) for n in names_or_bones]
def S(s, name):  # side name helper: 'lips.L'
    return name.replace('$', s)

def pose_L(name, s):
    """moves for the character's side s ('L'); x is mirrored for 'R' by the caller."""
    o = 'R' if s == 'L' else 'L'
    bt, bb = BROW_T[s], BROW_B[s]
    P = {
        'mouthSmile':     T(S(s, 'lips.$'), d=(3, 3, 5)) + T(S(s, 'cheek.B.$.001'), d=(1, 0, 2)) + T(S(s, 'cheek.T.$.001'), d=(0, 0, 1.5))
                          + T(S(s, 'lip.T.$.001'), d=(1, 1, 1.5)) + T(S(s, 'lip.B.$.001'), d=(1, 1, 2)),
        'mouthFrown':     T(S(s, 'lips.$'), d=(1, 0, -5)) + T(S(s, 'lip.B.$.001'), d=(0, 0, -1.5)),
        'mouthDimple':    T(S(s, 'lips.$'), d=(2, 4, 0)),
        'mouthStretch':   T(S(s, 'lips.$'), d=(5, 1, -2)) + T(S(s, 'lip.B.$.001'), d=(2, 0, -1.5)),
        'mouthPress':     T(S(s, 'lip.T.$.001'), d=(0, 1, -1)) + T(S(s, 'lip.B.$.001'), d=(0, 1, 1)) + T(S(s, 'lips.$'), d=(1, 1, 0)),
        'mouthLowerDown': T(S(s, 'lip.B.$.001'), d=(0, -0.5, -4)) + T('lip.B', d=(0, 0, -1)),
        'mouthUpperUp':   T(S(s, 'lip.T.$.001'), d=(0, -0.5, 4)) + T('lip.T', d=(0, 0, 1)),
        'browDown':       [('T', b, np.array((0, 1, -2.5))) for b in bt] + [('T', b, np.array((0, 0.5, -1.5))) for b in bb] + [('T', bt[0], np.array((-1, 0, -1)))],
        'browOuterUp':    [('T', bt[-1], np.array((0, 0, 5))), ('T', bt[len(bt) // 2], np.array((0, 0, 2.5))), ('T', bb[-1], np.array((0, 0, 3)))],
        'cheekSquint':    T(S(s, 'cheek.T.$.001'), d=(0, -1, 3)) + T(S(s, 'cheek.B.$.001'), d=(0, 0, 1.5)) + [('T', b, np.array((0, 0, 1))) for b in LID_B[s]],
        'noseSneer':      T(S(s, 'nose.$.001'), d=(0, -0.5, 3)) + T(S(s, 'cheek.T.$.001'), d=(0, 0, 1.5)) + [('T', bt[0], np.array((0, 0, -1)))],
        'eyeSquint':      [('T', b, np.array((0, 0, 2.5))) for b in LID_B[s]] + T(S(s, 'cheek.T.$.001'), d=(0, 0, 1)),
        'eyeWide':        [('T', b, np.array((0, 0, 2.5))) for b in LID_T[s]] + [('T', b, np.array((0, 0, 1))) for b in bb],
    }
    return P[name]

CENTRE = {
    'jawOpen':         [('R', 'jaw_master', 16.0)],
    'jawForward':      T('jaw_master', d=(0, -4, 0)),
    'jawLeft':         T('jaw_master', d=(4, 0, 0)),
    'jawRight':        T('jaw_master', d=(-4, 0, 0)),
    'mouthFunnel':     T('lips.L', d=(-4, -3, 0)) + T('lips.R', d=(4, -3, 0)) + T('lip.T', d=(0, -3, 2)) + T('lip.B', d=(0, -3, -2))
                       + T('cheek.B.L.001', d=(-1.5, -1, 0)) + T('cheek.B.R.001', d=(1.5, -1, 0))
                       + T('lip.T.L.001', d=(-2, -3, 1)) + T('lip.T.R.001', d=(2, -3, 1)) + T('lip.B.L.001', d=(-2, -3, -1)) + T('lip.B.R.001', d=(2, -3, -1)),
    'mouthPucker':     T('lips.L', d=(-6, -4, 0)) + T('lips.R', d=(6, -4, 0)) + T('lip.T', 'lip.B', d=(0, -4, 0))
                       + T('lip.T.L.001', 'lip.B.L.001', d=(-2.5, -4, 0)) + T('lip.T.R.001', 'lip.B.R.001', d=(2.5, -4, 0))
                       + T('cheek.B.L.001', d=(-2, -1, 0)) + T('cheek.B.R.001', d=(2, -1, 0)) + T('chin', d=(0, -1, 0.5)),
    'mouthLeft':       T('lips.L', 'lips.R', 'lip.T', 'lip.B', 'lip.T.L.001', 'lip.T.R.001', 'lip.B.L.001', 'lip.B.R.001', d=(5, 0, 0))
                       + T('cheek.B.L.001', 'cheek.B.R.001', 'chin', 'chin.L', 'chin.R', d=(2.5, 0, 0)),
    'mouthRight':      T('lips.L', 'lips.R', 'lip.T', 'lip.B', 'lip.T.L.001', 'lip.T.R.001', 'lip.B.L.001', 'lip.B.R.001', d=(-5, 0, 0))
                       + T('cheek.B.L.001', 'cheek.B.R.001', 'chin', 'chin.L', 'chin.R', d=(-2.5, 0, 0)),
    'mouthRollLower':  T('lip.B', 'lip.B.L.001', 'lip.B.R.001', d=(0, 3, 1.5)),
    'mouthRollUpper':  T('lip.T', 'lip.T.L.001', 'lip.T.R.001', d=(0, 3, -1.5)),
    'mouthShrugLower': T('lip.B', d=(0, -1.5, 2.5)) + T('lip.B.L.001', 'lip.B.R.001', d=(0, -1, 2)) + T('chin', d=(0, -1, 2)),
    'mouthShrugUpper': T('lip.T', d=(0, -1, 2.5)) + T('lip.T.L.001', 'lip.T.R.001', d=(0, -1, 2)),
    'cheekPuff':       T('cheek.B.L.001', d=(4, -2, 0)) + T('cheek.B.R.001', d=(-4, -2, 0)) + T('cheek.T.L.001', d=(2, -1, 0)) + T('cheek.T.R.001', d=(-2, -1, 0)),
    'browInnerUp':     [('T', BROW_T[s][0], np.array((0, -0.5, 5))) for s in 'LR'] + [('T', BROW_T[s][1], np.array((0, 0, 2.5))) for s in 'LR']
                       + [('T', BROW_B[s][0], np.array((0, 0, 3))) for s in 'LR'],
    # tongue only, measured on an open jaw (used together with jawOpen): forward and up over the lower lip
    'tongueOut':       [('R', 'jaw_master', 16.0)] + T('tongue_master' if 'tongue_master' in pb else 'tongue', d=(0, -24, 7)),   # modular face: 'tongue'
    # corrective: lips meet while the jaw is open; stored as (this pose - jawOpen 10 deg)
    'mouthClose':      [('R', 'jaw_master', 10.0)] + T('lip.B', 'lip.B.L.001', 'lip.B.R.001', d=(0, -1, 5)) + T('lip.T', 'lip.T.L.001', 'lip.T.R.001', d=(0, 0, -2))
                       + T('lips.L', 'lips.R', d=(0, 0, 1.5)),
}
RELATIVE = {'mouthClose': [('R', 'jaw_master', 10.0)], 'tongueOut': [('R', 'jaw_master', 16.0)]}
SIDED = ['mouthSmile', 'mouthFrown', 'mouthDimple', 'mouthStretch', 'mouthPress', 'mouthLowerDown', 'mouthUpperUp',
         'browDown', 'browOuterUp', 'cheekSquint', 'noseSneer', 'eyeSquint', 'eyeWide']

POSES = dict(CENTRE)
for nm in SIDED:
    POSES[nm + '_L'] = pose_L(nm, 'L')
    POSES[nm + '_R'] = pose_L(nm, 'R')   # built from the R controls; x of each move mirrored below
    POSES[nm + '_R'] = [(k, n, (d * np.array([-1, 1, 1]) if k == 'T' else d)) for k, n, d in POSES[nm + '_R']]

PAIRS = [(n + '_L', n + '_R') for n in SIDED]
if MPFB:
    # ---- pose library from the CC0 MPFB template (ARKit 52): its expression motion at each control's spot.
    # The template was fitted onto this head in face_fit (same vertex order as the template), so a control's
    # position maps to a point on the fitted template; the template key's displacement there (scaled back to
    # this head) is where the control goes. The jaw turns about the solved pivot by the angle that puts the chin
    # control where the template's chin goes.
    from mathutils.bvhtree import BVHTree
    TPL, FIT = MPFB
    with bpy.data.libraries.load(TPL) as (src, dst): dst.objects = ['head']
    tpl = dst.objects[0]
    with bpy.data.libraries.load(FIT) as (src, dst): dst.objects = ['head', 'target']
    fit_head, fit_target = dst.objects
    kbt = tpl.data.shape_keys.key_blocks; T0 = np.array([tuple(q.co) for q in kbt['Basis'].data])
    Fh = np.array([tuple(v.co) for v in fit_head.data.vertices]); assert len(Fh) == len(T0)
    fit_head.data.calc_loop_triangles(); TRI = np.array([tuple(t.vertices) for t in fit_head.data.loop_triangles])
    bvhF = BVHTree.FromPolygons([tuple(q) for q in Fh], TRI.tolist())
    Xf = np.array([tuple(v.co) for v in face.data.vertices]); Tg = np.array([tuple(v.co) for v in fit_target.data.vertices])
    Xb = Xf
    if os.environ.get('ORIG_BBOX'):                     # M1 heads: the template was fitted to the ORIGINAL head, whose extent
        bb = json.load(open(os.environ['ORIG_BBOX'])); Xb = np.array([bb['min'], bb['max']])   # differs from this mesh
    sc = float(np.ptp(Tg[:, 2]) / np.ptp(Xb[:, 2])); tr = (Tg.min(0) + Tg.max(0)) / 2 - sc * (Xb.min(0) + Xb.max(0)) / 2
    BINDQA = {'tr_x_mm': round(float(tr[0]) * 1000, 2)}
    # both heads mirror-symmetric about x = 0: no sideways shift (the old full-head bbox is not centred: f06 -9.3 mm,
    # so every left control bound 9 mm off its spot and left / right keys differed); env BAKE_SYM_X=0: old mapping
    if os.environ.get('BAKE_SYM_X', '1') != '0' and abs(Xf[:, 0].max() + Xf[:, 0].min()) < 5e-4 and abs(Fh[:, 0].max() + Fh[:, 0].min()) < 5e-4:
        tr[0] = 0.0; BINDQA['sym_x'] = True
    # mouth frame (env BAKE_MOUTH_ALIGN=0: off): the template fitted to the ORIGINAL head need not have its mouth where this
    # mesh has it (P f11: the slit maps 12 mm behind the template's lips, P f02 4 mm low), so lip controls bound to the
    # inner lip or to skin beside the corner (f11 corner: upper lip 'moved' 1 mm in jawOpen, lower 18 mm). Our slit centre
    # and corners are carried onto the template's: its seam centre (closest upper / lower lip pair on x = 0, upper / lower
    # read from the template's jawOpen) and its commissure (the densest vertex cluster beside the mouth, where MPFB's lip
    # loops fold into the corner; the same 14-18 template vertices on every fit): x scaled corner to corner, y / z
    # shifted (centre offset blended to the corner offset along the lip), faded out between 0.6 and 1.4 half mouth
    # widths from the mouth line, so cheeks / chin / nose bind as before.
    MA = None
    def _sd(p, a_, b_):
        ab = b_ - a_; t_ = float(np.clip((p - a_) @ ab / (ab @ ab), 0, 1)); return float(np.linalg.norm(a_ + t_ * ab - p))
    if os.environ.get('BAKE_MOUTH_ALIGN', '1') != '0' and 'mouth_ring' in face.data.attributes and 'jawOpen' in kbt and BINDQA.get('sym_x'):
        from mathutils.kdtree import KDTree as _KD
        rg_ = np.array([d.value for d in face.data.attributes['mouth_ring'].data]); u_ = np.array([d.value for d in face.data.attributes['mouth_u'].data])
        sl_ = np.where(rg_ == int(rg_.max()) - 7)[0]; cpi = int(sl_[np.argmin(np.minimum(u_[sl_], 1 - u_[sl_]))])
        upi = sl_[(u_[sl_] > 0) & (u_[sl_] < 0.5)]; loi = sl_[u_[sl_] > 0.5]
        Xs_ = (Xf[upi[np.argmin(np.abs(Xf[upi, 0]))]] + Xf[loi[np.argmin(np.abs(Xf[loi, 0]))]]) / 2; Xs_[0] = 0.0
        A_ = sc * Xf[cpi] + tr; B_ = sc * Xs_ + tr
        dropv = -(np.array([tuple(q.co) for q in kbt['jawOpen'].data]) - T0)[:, 2]; lowv = np.clip(dropv / dropv.max(), 0, 1)
        nr = (np.abs(Fh[:, 0]) < 1e-4) & (np.linalg.norm(Fh - B_, axis=1) < 0.03)
        Uc, Lc = np.where(nr & (lowv < 0.2))[0], np.where(nr & (lowv > 0.5))[0]
        if len(Uc) and len(Lc) and A_[0] > 0.005:
            _, iu, il = min((float(np.linalg.norm(Fh[i] - Fh[j])), i, j) for i in Uc for j in Lc)
            Ts = (Fh[iu] + Fh[il]) / 2; hw_ = float(A_[0])
            reg = np.where((Fh[:, 0] > 0.35 * hw_) & (Fh[:, 0] < 1.8 * hw_) & (np.abs(Fh[:, 2] - Ts[2]) < 0.7 * hw_) & (Fh[:, 1] < Ts[1] + hw_))[0]
            kdm = _KD(len(reg))
            for j, i in enumerate(reg): kdm.insert(Fh[i], j)
            kdm.balance(); rad = 0.065 * hw_
            dens = [len(kdm.find_range(Fh[i], rad)) for i in reg]; k0 = int(np.argmax(dens))
            cl = [int(reg[j]) for _, j, _ in kdm.find_range(Fh[reg[k0]], rad)]; Tc = Fh[cl].mean(0)
            MA = {'A': A_, 'B': B_, 'Ts': Ts, 'Tc': Tc, 'xs': float(Tc[0] / A_[0])}
            BINDQA['mouth_align'] = {'centre_shift_mm': ((Ts - B_) / sc * 1000).round(2).tolist(), 'corner_shift_mm': ((Tc - A_) / sc * 1000).round(2).tolist(),
                                     'x_scale': round(MA['xs'], 3), 'corner_cluster': len(cl), 'seam_pair_gap_mm': round(float(np.linalg.norm(Fh[iu] - Fh[il])) * 1000, 2)}
    def mouth_fix(q):
        if MA is None: return q
        A_, B_, Ts, Tc = MA['A'], MA['B'], MA['Ts'], MA['Tc']; Mx = np.array([1.0 if q[0] >= 0 else -1.0, 1, 1])
        lam = min(abs(q[0]) / A_[0], 1.0); new = q + (1 - lam) * (Ts - B_) + lam * (Tc * Mx - A_ * Mx); new[0] = q[0] * MA['xs']
        d_ = min(_sd(q, B_, A_), _sd(q, B_, A_ * np.array([-1.0, 1, 1]))); s_ = float(np.clip((d_ - 0.6 * A_[0]) / (0.8 * A_[0]), 0, 1))
        return q + (1 - s_ * s_ * (3 - 2 * s_)) * (new - q)
    EXCL = {'jaw_master', 'jaw', 'eyes', 'eye.L', 'eye.R', 'master_eye.L', 'master_eye.R', 'teeth.T', 'teeth.B', 'nose_master',
            'eye_common', 'eye_master.L', 'eye_master.R', 'jaw_master_mouth',             # modular (dense) face
            'root', 'torso', 'chest', 'hips', 'neck', 'head'}
    # tongue controls never take template targets (the 'tweak_tongue.*' ones did: pinned at rest they held the tongue up
    # while the jaw opened -> a 35 mm vertical 'stalk' in the mouth, or no motion at all)
    CTRL = [b for b in pb if not b.name.startswith(('ORG', 'DEF', 'MCH', 'tweak_spine', 'spine_fk', 'tongue', 'ear')) and 'tongue' not in b.name and b.name not in EXCL]
    # lip controls bind only to the matching template lip: on a closed mouth the nearest point of a lower-lip control
    # can be the template's upper lip (symmetric f09: jawOpen moved the chin 40 mm but the lips 3 mm). Upper/lower is
    # read from the template's own jawOpen: how far each triangle drops, as a share of the largest drop.
    SIDE_BVH = {}
    if 'jawOpen' in kbt:
        drop = -(np.array([tuple(q.co) for q in kbt['jawOpen'].data]) - T0)[:, 2]; low = np.clip(drop / drop.max(), 0, 1)[TRI].mean(1)
        for sd, m in ((1, low < 0.2), (-1, low > 0.5)):
            SIDE_BVH[sd] = (BVHTree.FromPolygons([tuple(q) for q in Fh], TRI[m].tolist()), np.where(m)[0])
    def bind_point(p, side):
        q = mouth_fix(sc * np.asarray(p) + tr) + np.array([0, 0, side * 0.0012 * sc])
        if side in SIDE_BVH:
            bv, idx = SIDE_BVH[side]; loc, nrm, ti, dist = bv.find_nearest(Vector(q)); ti = int(idx[ti])
        else: loc, nrm, ti, dist = bvhF.find_nearest(Vector(q))
        t = TRI[ti]; A_, B_, C_ = Fh[t]
        v0, v1, v2 = B_ - A_, C_ - A_, np.array(loc) - A_
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1; den = d00 * d11 - d01 * d01
        v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
        return t, np.array([1 - v - w, v, w]), dist / sc
    side_of = lambda n: 1 if n.startswith('lip.T') else (-1 if n.startswith('lip.B') else 0)
    # lip controls take the motion of their lip's EDGE (the slit point at the control's x, on its own lip), not of the
    # spot 2-6 mm off the slit where the control sits: the template's lip body and lip edge move differently (P f06
    # smile: point 4 mm above the seam +3.2 mm, 3 mm below it +7.7 mm, so the lower lip rose through the upper one);
    # edge to edge, upper and lower follow the template's lip line and cannot cross. env BAKE_LIP_EDGE=0: control spot
    LIPEDGE = None
    if os.environ.get('BAKE_LIP_EDGE', '1') != '0' and 'mouth_ring' in face.data.attributes:
        rg_ = np.array([d.value for d in face.data.attributes['mouth_ring'].data]); u_ = np.array([d.value for d in face.data.attributes['mouth_u'].data])
        sl_ = np.where(rg_ == int(rg_.max()) - 7)[0]; cr_ = [int(i) for i in sl_ if min(u_[i] % 0.5, 0.5 - u_[i] % 0.5) < 1e-9]
        LIPEDGE = {1: np.array(sorted([int(i) for i in sl_ if 0 < u_[i] < 0.5] + cr_, key=lambda i: Xf[i, 0])),
                   -1: np.array(sorted([int(i) for i in sl_ if u_[i] > 0.5] + cr_, key=lambda i: Xf[i, 0]))}
    def ctl_query(b):
        sd = side_of(b.name); h = np.array(b.bone.head_local)
        if LIPEDGE is None or sd == 0: return h
        ids = LIPEDGE[sd]; return np.array([np.interp(h[0], Xf[ids, 0], Xf[ids, j]) for j in range(3)])
    BIND = {b.name: (np.array(b.bone.head_local),) + bind_point(ctl_query(b), side_of(b.name)) for b in CTRL}
    if LIPEDGE is not None: BINDQA['lip_edge'] = True
    # the two lip chains meet at the centre control; where the template's lip line bends there (P f06 smile: upper edge
    # centre -1 mm, 13 mm out +5 mm per side) the rig made a sharp V. The centre control takes 75 % of its neighbours'
    # mean move (env BAKE_LIP_CENTRE_SMOOTH, default 0.75; 0 = off)
    CSM = float(os.environ.get('BAKE_LIP_CENTRE_SMOOTH', '0.75')); CENT_NB = {}
    if CSM > 0:
        for c_ in ('lip.T', 'lip.B'):
            if c_ not in BIND: continue
            ch_ = [n for n in BIND if n.startswith(c_ + '.') and abs(BIND[n][0][0]) > 1e-3]
            nl_ = [n for n in ch_ if BIND[n][0][0] > 0]; nr_ = [n for n in ch_ if BIND[n][0][0] < 0]
            if nl_ and nr_: CENT_NB[c_] = (min(nl_, key=lambda n: BIND[n][0][0]), max(nr_, key=lambda n: BIND[n][0][0]))
        BINDQA['centre_smooth'] = {k: list(v) for k, v in CENT_NB.items()}
    # chain smoothing (env BAKE_CHAIN_SMOOTH, default 0.5; 0 = off): the mouth-plus controls (the lip control next to each
    # corner, modiolus, mentalis side, nasolabial middle) sit between two controls of their skin chain; the template's
    # motion at such close spots is noisy (P f09: flips 32 -> 60-126 with them), so each takes this share of the mean
    # move of its two chain neighbours (the controls at the ends of its two deform bones)
    CHS = float(os.environ.get('BAKE_CHAIN_SMOOTH', '0.5')); CHAIN_NB = {}
    if CHS > 0:
        import re as _re
        _plus = lambda n_: bool(_re.match(r'(lip\.[TB]\.[LR]\.004|cheek\.B\.[LR]\.004|chin\.[LR]\.001|nasolabial\.[LR]\.001)$', n_))
        _ch = {n_: np.array(pb[n_].bone.head_local) for n_ in BIND}
        def _ctl_at(p_):
            best = min(_ch, key=lambda n_: np.linalg.norm(_ch[n_] - p_)); return best if np.linalg.norm(_ch[best] - p_) < 2e-4 else None
        for n_ in BIND:
            if not _plus(n_): continue
            nb_ = []
            for bd in rig.data.bones:
                if not (bd.use_deform and bd.name.startswith('DEF-')): continue
                h_, t_ = np.array(bd.head_local), np.array(bd.tail_local)
                if np.linalg.norm(h_ - _ch[n_]) < 2e-4: nb_.append(_ctl_at(t_))
                elif np.linalg.norm(t_ - _ch[n_]) < 2e-4: nb_.append(_ctl_at(h_))
            nb_ = [m_ for m_ in dict.fromkeys(nb_) if m_ and m_ != n_]
            if len(nb_) >= 2: CHAIN_NB[n_] = nb_
        BINDQA['chain_smooth'] = {k: v for k, v in CHAIN_NB.items()}
    chin_p = np.array(pb['chin'].bone.head_local); CHIN = bind_point(chin_p, 0)
    _ld = [v[3] * 1000 for n_, v in BIND.items() if n_.startswith('lip')]
    if _ld: BINDQA['lip_bind_mm'] = {'mean': round(float(np.mean(_ld)), 2), 'max': round(float(np.max(_ld)), 2), 'controls': len(_ld)}
    # Rigify puts jaw_master at the jaw.L/R heads (beside the eyes, 4 cm in front of the ear); the jaw itself (DEF-jaw)
    # hinges at the 'jaw' bone head, the joint solved from the template's jawOpen (rig_points). Turning about
    # jaw_master swung the chin back (f02: 25 mm back, 11 mm down at 15 deg) and the lower teeth into the cheek.
    # (rigify_fit stores the solved hinge on the rig; older rigs: the 'jaw' head of the super_face rig)
    J = np.array(rig['jaw_pivot'] if 'jaw_pivot' in rig else (pb['jaw'].bone.head_local if 'jaw' in pb else pb['jaw_master'].bone.head_local)); JPIV = Vector(J)
    def delta(name):
        Dk = np.array([tuple(q.co) for q in kbt[name].data]) - T0
        return Dk
    def at(Dk, bnd):
        t, w = bnd[0], bnd[1]; return (w[:, None] * Dk[t]).sum(0) / sc
    def moves_for(names, kk=None):
        Dk = sum(delta(n) for n in names); kk = k_for(names) if kk is None else kk
        mv = []
        dc = at(Dk, CHIN)
        if any(n.startswith('jaw') for n in names) or 'jawOpen' in names:
            if 'jawOpen' in names:
                y0, z0 = (chin_p - J)[1:]; y1, z1 = (chin_p + dc - J)[1:]
                mv.append(('RA', 'jaw_master', kk * math.atan2(y0 * z1 - z0 * y1, y0 * y1 + z0 * z1)))
            else:
                mv.append(('T', 'jaw_master', kk * dc / mm))
        dd = {n: kk * at(Dk, (t, w)) for n, (rest, t, w, dist) in BIND.items()}
        for c_, (nl_, nr_) in CENT_NB.items():                # centre lip control: half its own move, half its neighbours'
            dd[c_] = (1 - CSM) * dd[c_] + CSM * 0.5 * (dd[nl_] + dd[nr_])
        d0_ = dict(dd)
        for c_, nb_ in CHAIN_NB.items(): dd[c_] = (1 - CHS) * d0_[c_] + CHS * np.mean([d0_[m_] for m_ in nb_], 0)
        for n, (rest, t, w, dist) in BIND.items():
            mv.append(('A', n, rest + dd[n]))
        return mv
    ARKIT = [k.name for k in kbt if k.name[0].islower() and not k.name.startswith(('viseme', 'eyeBlink', 'eyeLook'))
             and '_' not in k.name]
    POSES = {}
    for n in ARKIT:
        POSES[n] = moves_for(['jawOpen', 'mouthClose'] if n == 'mouthClose' else [n], k_for(['mouthClose']) if n == 'mouthClose' else None)
    RELATIVE = {'mouthClose': moves_for(['jawOpen'], k_for(['mouthClose'])), 'tongueOut': [('R', 'jaw_master', 16.0)]}
    POSES['tongueOut'] = CENTRE['tongueOut']
    PAIRS = [(n, n.replace('Left', 'Right')) for n in POSES if n.endswith('Left')]
    if os.environ.get('DEBUG_BIND'):
        for n_, (rest_, t_, w_, dist_) in sorted(BIND.items()):
            if n_.startswith(os.environ['DEBUG_BIND']): print('BIND', n_, 'dist mm', round(dist_ * 1000, 2), 'jawOpen mm', np.round(at(delta('jawOpen'), (t_, w_)) * 1000, 2).tolist(), 'tpl pt', np.round((w_[:, None] * Fh[t_]).sum(0), 4).tolist())
    print('MPFB poses', len(POSES), 'controls', len(CTRL), 'scale', round(sc, 4), 'bind max mm', round(max(v[3] for v in BIND.values()) * 1000, 2))

# jaw opening direction: positive angle must move the chin down
def depth(b):
    d = 0
    while b.parent: d += 1; b = b.parent
    return d

def reset():
    for b in pb:
        b.location = (0, 0, 0); b.rotation_quaternion = (1, 0, 0, 0); b.rotation_euler = (0, 0, 0); b.scale = (1, 1, 1)
    bpy.context.view_layer.update()

JAW_SIGN = 1.0
PASSES = 25
if 'JPIV' not in globals(): JPIV = None              # jaw hinge for 'RA'/'R' moves of jaw_master (set from the template)
JINV = {}
def apply(moves):
    reset()
    bones = []
    for k, n, d in moves:
        b = pb[n] if isinstance(n, str) else n
        if b is None: continue
        bones.append((depth(b), k, b, d))
    for _, k, b, d in sorted(bones, key=lambda x: x[0]):
        cur = b.matrix.copy()
        if k == 'T':
            b.matrix = Matrix.Translation(Vector(d * mm)) @ cur
        elif k == 'A':                      # absolute target for the bone head (armature space, metres)
            b.matrix = Matrix.Translation(Vector(d) - cur.translation) @ cur
        elif k == 'RA':                     # rotation about the bone head (jaw_master: the jaw hinge) around X, radians, no sign fix
            p = JPIV.copy() if (JPIV is not None and b.name == 'jaw_master') else cur.translation.copy()
            b.matrix = Matrix.Translation(p) @ Matrix.Rotation(float(d), 4, 'X') @ Matrix.Translation(-p) @ cur
        else:
            p = JPIV.copy() if (JPIV is not None and b.name == 'jaw_master') else cur.translation.copy()
            Rm = Matrix.Rotation(math.radians(d) * JAW_SIGN, 4, 'X')
            b.matrix = Matrix.Translation(p) @ Rm @ Matrix.Translation(-p) @ cur
        bpy.context.view_layer.update()
    # absolute targets: Rigify face controls are partly driven by their neighbours (copy-location constraints),
    # so the head is solved through each control's own location channels with a measured response (Jacobian)
    # one control at a time, constraint drivers before the controls that copy them (Gauss-Seidel, damped)
    targets = [(b, np.asarray(d)) for _, k, b, d in sorted(bones, key=lambda x: (x[0], len(x[2].constraints))) if k == 'A']
    if not targets: return
    mods = [m for o in bpy.data.objects if o.type == 'MESH' for m in o.modifiers if m.type == 'ARMATURE']
    for m in mods: m.show_viewport = False                  # solve on the armature only (fast)
    best = (9.0, None); worse = 0
    for it in range(PASSES):
        worst = 0.0
        for b, d in targets:
            miss = d - np.array(b.head); worst = max(worst, float(np.linalg.norm(miss)))
            if np.linalg.norm(miss) > 2e-5:
                step = 0.8 * (JINV[b.name] @ miss); ls_ = np.linalg.norm(step)
                if ls_ > 0.003: step *= 0.003 / ls_                  # at most 3 mm per pass (constraints are not linear)
                b.location = Vector(np.array(b.location) + step)
                bpy.context.view_layer.update()
        if os.environ.get('DEBUG_POSE'): print('PASS', it, 'worst mm', round(worst * 1000, 2), sorted(((round(float(np.linalg.norm(d - np.array(b.head))) * 1000, 1), b.name, [c.subtarget for c in b.constraints]) for b, d in targets), reverse=True)[:3])
        if worst < best[0]:
            best = (worst, {b.name: tuple(b.location) for b, _ in targets}); worse = 0
        else:
            worse += 1
        if worst < 1e-4 or worse >= 2: break
    # keep the pass that came closest (a few neighbour pairs copy each other and slowly run away)
    for b, _ in targets: b.location = best[1][b.name]
    bpy.context.view_layer.update()
    for m in mods: m.show_viewport = True
    bpy.context.view_layer.update()

def evaluate(o):
    dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg)
    return np.array([tuple(v.co) for v in ev.data.vertices])

if MPFB:
    # each control's response to its own location channels (constraints included), measured at rest
    reset()
    for b in CTRL:
        h0 = np.array(b.head); Jm = np.zeros((3, 3))
        for i in range(3):
            loc = [0.0, 0.0, 0.0]; loc[i] = 1e-3; b.location = loc; bpy.context.view_layer.update()
            Jm[:, i] = (np.array(b.head) - h0) / 1e-3
        b.location = (0, 0, 0)
        # truncated: a control held on a sphere (modular-face lids: Limit Distance to the eye) has a near-zero normal
        # response, and the full inverse blew it up into 30 mm jumps
        JINV[b.name] = np.linalg.pinv(Jm, rcond=0.05)
    bpy.context.view_layer.update()
X = np.array([tuple(v.co) for v in face.data.vertices])
# judged on the chin bone, not the mesh: the mean move of all skinned vertices flipped on the symmetric f09 head
apply([('R', 'jaw_master', 10.0)])
if pb['chin'].head[2] - pb['chin'].bone.head_local[2] > 0: JAW_SIGN = -1.0
reset()
if STYLE:
    # appearance template: hand-written control moves (see usage); needs the MPFB block for CTRL / JINV / the jaw hinge
    assert MPFB, '--style needs --mpfb (controls, jaw hinge and the keys the style file does not list)'
    SJ = json.load(open(STYLE)); SUF = os.environ.get('BAKE_STYLE_SUFFIX', '')
    rgW = np.array([d.value for d in face.data.attributes['mouth_ring'].data]); slW = np.where(rgW == int(rgW.max()) - 7)[0]
    W_ = float(np.abs(X[slW, 0]).max())
    apply([('RA', 'jaw_master', 0.05)]); RA_SIGN = 1.0 if pb['chin'].head[2] < pb['chin'].bone.head_local[2] else -1.0; reset()
    def mpfb_angle(mv): return next((float(d) for k, n, d in mv if k == 'RA' and n == 'jaw_master'), 0.0)
    for key, spec in SJ['keys'].items():
        base = spec.get('base', 'jaw'); src = POSES.get(key, [])
        ang = RA_SIGN * math.radians(spec['jaw_deg']) if 'jaw_deg' in spec else (mpfb_angle(src) if base == 'mpfb' else 0.0)
        if base == 'mpfb':
            tgt = {n: np.array(d, float) for k, n, d in src if k == 'A'}
            if 'jaw_deg' in spec:                         # MPFB targets were made for its own jaw angle: re-base them
                apply([('RA', 'jaw_master', mpfb_angle(src))]); h0 = {b.name: np.array(b.head) for b in CTRL}
                apply([('RA', 'jaw_master', ang)]); h1 = {b.name: np.array(b.head) for b in CTRL}
                tgt = {n: v - h0[n] + h1[n] for n, v in tgt.items()}
        else:
            apply([('RA', 'jaw_master', ang)] if ang else []); tgt = {b.name: np.array(b.head) for b in CTRL}
        for n, d in spec.get('d', {}).items():
            if n in tgt: tgt[n] = tgt[n] + np.array(d, float) * W_
        POSES[key + SUF] = ([('RA', 'jaw_master', ang)] if ang else []) + [('A', n, v) for n, v in tgt.items()]
        if key in RELATIVE and SUF: RELATIVE[key + SUF] = RELATIVE[key]
    reset(); qa_style = {'file': os.path.basename(STYLE), 'style': SJ.get('style'), 'keys': list(SJ['keys']), 'half_mouth_mm': round(W_ * 1000, 2)}
    print('STYLE', json.dumps(qa_style))
if os.environ.get('BAKE_ONLY'):
    _only = os.environ['BAKE_ONLY'].split(',')
    POSES = {k: v for k, v in POSES.items() if k in _only}; PAIRS = [p_ for p_ in PAIRS if p_[0] in POSES and p_[1] in POSES]

parts = [o for o in (bpy.data.objects.get('teeth_lo'), bpy.data.objects.get('tongue')) if o]
P0 = {o.name: np.array([tuple(v.co) for v in o.data.vertices]) for o in parts}
def add_key(o, name, P):
    if not o.data.shape_keys: o.shape_key_add(name='Basis')
    kb = o.data.shape_keys.key_blocks.get(name) or o.shape_key_add(name=name, from_mix=False)
    kb.data.foreach_set('co', np.asarray(P, float).ravel())

# shape keys stay at 0 while evaluating (keys are added before the armature in the stack, value 0 = no effect)
if not face.data.shape_keys: face.shape_key_add(name='Basis')        # M1 heads come without keys
for kb in face.data.shape_keys.key_blocks: kb.value = 0
qa = {'jaw_sign': JAW_SIGN, 'keys': {}}
if STYLE: qa['style'] = qa_style
if MPFB: qa['bind'] = BINDQA; print('BIND', json.dumps(BINDQA))
reset(); Erest = evaluate(face)
qa['rest_offset_mm'] = round(float(np.abs(Erest - X).max() * 1000), 4)
T3 = np.array([p.vertices[:3] for p in face.data.polygons if len(p.vertices) == 3])
def tn(P):
    n = np.cross(P[T3[:, 1]] - P[T3[:, 0]], P[T3[:, 2]] - P[T3[:, 0]]); return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-14)
N0 = tn(X)
DISP = {}
if os.environ.get('DEBUG_POSE'):
    apply(POSES[os.environ['DEBUG_POSE']]); raise SystemExit
# mouthClose = lips sealed while the jaw is open. Rig and template meet only at the controls; between them (and at the
# corners, now that upper and lower lip weights are kept apart) the slit stayed 1-7 mm open on jawOpen + mouthClose.
# The posed mouthClose mesh is sealed before it is stored: each slit vertex moves half way to the other lip's edge at the
# same rest x (corners stay), the inner-lip roll rings with it, lip skin on the same side by 1 - smoothstep(d / 2 D1)
# of its distance d to the slit (D1 = max(0.15 half width, lip-joint ring distance), as organ_mouth_weights).
# env BAKE_SEAL=0: off
SEAL = None
if os.environ.get('BAKE_SEAL', '1') != '0' and 'mouth_ring' in face.data.attributes:
    rgS = np.array([d.value for d in face.data.attributes['mouth_ring'].data]); uS = np.array([d.value for d in face.data.attributes['mouth_u'].data])
    KS_ = int(rgS.max()) - 7; slS = np.where(rgS == KS_)[0]
    cS_ = [int(i) for i in slS if min(uS[i] % 0.5, 0.5 - uS[i] % 0.5) < 1e-9]
    UPs = np.array(sorted([int(i) for i in slS if 0 < uS[i] < 0.5] + cS_, key=lambda i: X[i, 0]))
    LOs = np.array(sorted([int(i) for i in slS if uS[i] > 0.5] + cS_, key=lambda i: X[i, 0]))
    xcS = float(np.abs(X[slS, 0]).max()); r2S = np.where(rgS == KS_ - 2)[0]
    kdS = KDTree(len(slS))
    for j, i in enumerate(slS): kdS.insert(Vector(X[i]), j)
    kdS.balance(); dS = np.array([kdS.find(Vector(p))[2] for p in X])
    D1S = max(float(np.median(dS[r2S])) if len(r2S) else 0.0, 0.15 * xcS)
    sideS = np.where((uS > 0) & (uS < 0.5), 1, np.where(uS > 0.5, -1, 0))
    fS = np.where((rgS >= KS_ + 1) & (rgS <= KS_ + 2), 1.0, np.where((rgS >= 1) & (rgS <= KS_), 1 - (lambda s_: s_ * s_ * (3 - 2 * s_))(np.clip(dS / (2 * D1S), 0, 1)), 0.0))
    fS[sideS == 0] = 0.0
    SEAL = (UPs, LOs, sideS, fS)
CSEAL = () if os.environ.get('BAKE_CORNER_SEAL', '1') == '0' else ('mouthSmile', 'mouthStretch', 'mouthDimple', 'mouthFrown', 'mouthPress',
                                                               'cheekPuff', 'cheekSquint', 'noseSneer', 'mouthLeft', 'mouthRight')
def seal(E, corner=False):
    """corner=True: only the outer part of the slit (0 at 55 % of the half width, full from 85 %) is closed"""
    UPs, LOs, sideS, fS = SEAL
    def at(ids, P, x): return np.c_[[np.interp(x, X[ids, 0], P[ids, j]) for j in range(3)]].T
    dU = (at(LOs, E, X[UPs, 0]) - E[UPs]) / 2; dL = (at(UPs, E, X[LOs, 0]) - E[LOs]) / 2
    if corner:
        cf = lambda x: (lambda s_: s_ * s_ * (3 - 2 * s_))(np.clip((np.abs(x) / xcS - 0.55) / 0.30, 0, 1))
        dU = dU * cf(X[UPs, 0])[:, None]; dL = dL * cf(X[LOs, 0])[:, None]
    gap0 = float(np.linalg.norm(at(LOs, E, X[UPs, 0]) - E[UPs], axis=1).max())
    out = E.copy(); m = fS > 0
    for sd, ids, dd in ((1, UPs, dU), (-1, LOs, dL)):
        v = np.where(m & (sideS == sd))[0]
        out[v] += fS[v, None] * np.c_[[np.interp(X[v, 0], X[ids, 0], dd[:, j]) for j in range(3)]].T
    gap1 = float(np.linalg.norm(at(LOs, out, X[UPs, 0]) - out[UPs], axis=1).max())
    return out, {'gap_before_mm': round(gap0 * 1000, 2), 'gap_after_mm': round(gap1 * 1000, 2), 'moved_verts': int(m.sum())}
# ---- correctives on the posed mesh (2026-10-13), before the seals:
# EDGE (env BAKE_EDGE_FIX=1: on; default off since the 5-bone lip chain of rigify_fit RIG_MOUTH_PLUS reaches the
#   template's corner opening on its own, and the fix overshot it): near the corners the rig reaches the template only at its controls; between the last
#   lip control and the corner the B-bones drag the upper lip down with the corner (jawOpen: corner opening 0.2 of the
#   centre, template 0.25-0.4). Slit vertices from 60 % of the half width outward take the template's lip-edge motion
#   (side-specific binding as the lip controls; weight 0 -> 1 between 60 and 80 %, back to 0 at the corner: the template's
#   lip edges and its corner cluster disagree within ~10 % of the corner, where the rig's corner controls rule),
#   carried into the lip skin / inner roll of the same side like the seal.
# RELAX (env BAKE_RELAX=0: off): wherever mouth-skin triangles turn over, the displacement of their vertices and
#   neighbours (2 rings round them) is smoothed (slit fixed) until none do (at most 40 rounds); BAKE_RELAX_CORNER=n first smooths the
#   skin within 0.3 half width of the corners n times (default 0).
# tongueOut (env BAKE_TONGUE_OUT=v2: the old key, tongue only, stored relative to jawOpen 16 deg): a key of its own like
# ARKit's - the jaw drops 9 deg so the lips part round the tongue, and the tongue control goes 34 mm forward and 3 up
# (for a 52 mm mouth, scaled with this one; the v3 tongue's root and floor stay on the jaw, so the tip needs the
# reach to pass the lips). The tongue alone then sticks out past the lips; with jawOpen added the jaw opens further.
if SEAL is not None and 'tongueOut' in POSES:
    if os.environ.get('BAKE_TONGUE_OUT', 'static') == 'static':     # 2026-10-13 user: tongue static for now - the key
        POSES['tongueOut'] = []; RELATIVE.pop('tongueOut', None); qa['tongueOut'] = 'empty key (tongue static, rides the jaw rigidly)'
    elif os.environ.get('BAKE_TONGUE_OUT', 'static') != 'v2':
        _tc = 'tongue_master' if 'tongue_master' in pb else 'tongue'
        POSES['tongueOut'] = [('R', 'jaw_master', 9.0)] + T(_tc, d=np.array((0, -34, 3)) * xcS / 0.026)
        RELATIVE.pop('tongueOut', None)

EDGEFIX = MPFB is not None and SEAL is not None and os.environ.get('BAKE_EDGE_FIX', '0') != '0'
RELAX = SEAL is not None and os.environ.get('BAKE_RELAX', '1') != '0'
if EDGEFIX:
    EB_ = {sd: [bind_point(X[i], sd) for i in ids] for sd, ids in ((1, UPs), (-1, LOs))}
    _ss = lambda s_: np.clip(s_, 0, 1) ** 2 * (3 - 2 * np.clip(s_, 0, 1))
    EW_ = {sd: _ss((np.abs(X[ids, 0]) / xcS - 0.6) / 0.2) * _ss((1 - np.abs(X[ids, 0]) / xcS) / 0.12) for sd, ids in ((1, UPs), (-1, LOs))}
def tnames(n):
    if not MPFB or n == 'tongueOut': return None
    if n == 'mouthClose': return ['jawOpen', 'mouthClose'], k_for(['mouthClose'])
    return ([n], k_for([n])) if n in kbt else None
def edge_fix(E, tn_):
    if not EDGEFIX or tn_ is None: return E, None
    names, kk = tn_; Dk = sum(delta(n_) for n_ in names); out = E.copy(); mx = 0.0
    for sd, ids in ((1, UPs), (-1, LOs)):
        Dt = np.array([kk * at(Dk, (bd[0], bd[1])) for bd in EB_[sd]]); dd = EW_[sd][:, None] * (Dt - (E[ids] - X[ids]))
        mx = max(mx, float(np.linalg.norm(dd, axis=1).max()))
        v = np.where((fS > 0) & (sideS == sd))[0]
        out[v] += fS[v, None] * np.c_[[np.interp(X[v, 0], X[ids, 0], dd[:, j]) for j in range(3)]].T
    return out, round(mx * 1000, 2)
if RELAX:
    face.data.calc_loop_triangles(); TL_ = np.array([tuple(t.vertices) for t in face.data.loop_triangles])
    SKT_ = TL_[(rgS[TL_].max(1) <= KS_) & (rgS[TL_] > 0).any(1)]
    nz_ = np.where((rgS >= 1) & (rgS <= KS_ + 2) & (rgS != KS_))[0]; inz_ = np.zeros(len(X), bool); inz_[nz_] = True
    NB_ = {int(i): [] for i in nz_}
    for e_ in face.data.edges:
        a_, b_ = e_.vertices
        if inz_[a_] and rgS[b_] >= 1: NB_[a_].append(b_)
        if inz_[b_] and rgS[a_] >= 1: NB_[b_].append(a_)
    cz_ = [i for i in nz_ if min(np.linalg.norm(X[i] - X[c_]) for c_ in cS_) < 0.3 * xcS]
    def sk_n(P): return np.cross(P[SKT_[:, 1]] - P[SKT_[:, 0]], P[SKT_[:, 2]] - P[SKT_[:, 0]])
    SKN0 = sk_n(X); SKOK = np.linalg.norm(SKN0, axis=1) > 1e-14
# LIPLINE (env BAKE_LIPLINE_SMOOTH = passes, default 3; 0 = off): the lip edges follow the template's lip line only at
#   the controls, and the template's own edge motion is noisy (P f09 funnel: ragged lips). The displacement along each
#   lip edge is smoothed (neighbours by rest x; fading out from 80 to 92 % of the half width, so the sharp turn into the
#   corner that opens it stays) and the change carried into the lip skin / roll of the
#   same side like the seal.
LLS = int(os.environ.get('BAKE_LIPLINE_SMOOTH', '3')) if SEAL is not None else 0
def lipline(E):
    if LLS <= 0: return E, None
    out = E.copy(); mx = 0.0
    for sd, ids in ((1, UPs), (-1, LOs)):
        D0 = E[ids] - X[ids]; D = D0.copy(); xs = X[ids, 0]
        a_ = np.clip((np.abs(xs) / xcS - 0.8) / 0.12, 0, 1); wl_ = 0.5 * (1 - a_ * a_ * (3 - 2 * a_))   # the corner turn is kept
        for _ in range(LLS):
            Dn = D.copy()
            for k in range(1, len(ids) - 1):
                if ids[k] in cS_: continue
                t = (xs[k] - xs[k - 1]) / max(xs[k + 1] - xs[k - 1], 1e-9)
                Dn[k] = (1 - wl_[k]) * D[k] + wl_[k] * (D[k - 1] + t * (D[k + 1] - D[k - 1]))
            D = Dn
        dd = D - D0; mx = max(mx, float(np.linalg.norm(dd, axis=1).max()))
        v = np.where((fS > 0) & (sideS == sd))[0]
        out[v] += fS[v, None] * np.c_[[np.interp(X[v, 0], xs, dd[:, j]) for j in range(3)]].T
    return out, round(mx * 1000, 2)
def relax(E):
    if not RELAX: return E, None
    D = E - X
    def smooth(ids, a_=0.5):
        Dn = D.copy()
        for i in ids:
            nb = NB_.get(int(i))
            if nb: Dn[i] = (1 - a_) * D[i] + a_ * D[nb].mean(0)
        return Dn
    for _ in range(int(os.environ.get('BAKE_RELAX_CORNER', '0'))): D = smooth(cz_)
    fl0 = int((SKOK & ((sk_n(X + D) * SKN0).sum(1) < 0)).sum()); it = 0
    for it in range(40):
        bad = SKOK & ((sk_n(X + D) * SKN0).sum(1) < 0)
        if not bad.any(): break
        vs = set(SKT_[bad].ravel().tolist())
        for _ in range(2): vs |= {w for v_ in list(vs) for w in NB_.get(v_, [])}
        D = smooth([v_ for v_ in vs if inz_[v_]])
    fl1 = int((SKOK & ((sk_n(X + D) * SKN0).sum(1) < 0)).sum())
    return X + D, {'flips_before': fl0, 'flips_after': fl1, 'rounds': it}
# CAP (env BAKE_LIP_STRETCH_CAP, default 1.35; 0 = off): a key whose lip skin (rings K-3 .. K+2, upper or lower lip)
#   grows by more than this in area is scaled down as a whole (face, lower teeth, tongue), so a small mouth on a big
#   head does not take the template's full-size motion (P f09 jawOpen: lip area +51 %, flips 112 -> 144)
LCAP = float(os.environ.get('BAKE_LIP_STRETCH_CAP', '1.35')) if SEAL is not None else 0.0
if LCAP > 0:
    face.data.calc_loop_triangles(); TLc_ = np.array([tuple(t.vertices) for t in face.data.loop_triangles])
    zc_ = (rgS >= KS_ - 3) & (rgS <= KS_ + 2)
    LZ_ = [TLc_[zc_[TLc_].all(1) & ((uS[TLc_] > 0) & (uS[TLc_] < 0.5)).all(1)], TLc_[zc_[TLc_].all(1) & (uS[TLc_] > 0.5).all(1)]]
    def _ar(P, T_): return float(np.linalg.norm(np.cross(P[T_[:, 1]] - P[T_[:, 0]], P[T_[:, 2]] - P[T_[:, 0]]), axis=1).sum())
    LA0_ = [_ar(X, T_) for T_ in LZ_]
def cap_scale(E):
    if LCAP <= 0: return 1.0
    st = lambda s_: max(_ar(X + s_ * (E - X), T_) / a0 for T_, a0 in zip(LZ_, LA0_))
    if st(1.0) <= LCAP: return 1.0
    lo_, hi_ = 0.0, 1.0
    for _ in range(12):
        md = (lo_ + hi_) / 2
        if st(md) <= LCAP: lo_ = md
        else: hi_ = md
    return lo_
# DENSE (env BAKE_DENSE_TPL = strength; default 0 = off since 2026-10-13: untested, left lip-row ridges on P f09 smile / funnel): the template's motion reaches the rig only at its controls;
#   between them heat weights carry it. Every face-skin vertex is bound to the template (as the controls: mouth frame,
#   upper / lower lip side) and the residual (template motion there - rig motion), smoothed over the mesh (8 passes), is
#   added with a mask: 0 within D1 of the lip slit and within 0.15 half mouth width of the lid margins (seals, caps and
#   the canthus blink keep them), up to 1 by 3 D1 / 0.45 half width. Jaw keys and mouthClose keep the rig (the teeth
#   ride the rig jaw).
DTS = float(os.environ.get('BAKE_DENSE_TPL', '0')) if (MPFB and SEAL is not None) else 0.0
if DTS > 0:
    _ss2 = lambda s_: np.clip(s_, 0, 1) ** 2 * (3 - 2 * np.clip(s_, 0, 1))
    erA = np.abs(np.array([d.value for d in face.data.attributes['eye_ring'].data])) if 'eye_ring' in face.data.attributes else np.zeros(len(X))
    KEm = int(erA.max()) - 2 if erA.max() > 2 else 0
    mvE = np.where(erA == KEm)[0] if KEm > 0 else np.array([], int)
    if len(mvE):
        kdE = KDTree(len(mvE))
        for j_, i_ in enumerate(mvE): kdE.insert(Vector(X[i_]), j_)
        kdE.balance(); dE = np.array([kdE.find(Vector(p_))[2] for p_ in X])
    else: dE = np.full(len(X), 1.0)
    MASK = _ss2((dS - D1S) / (2 * D1S)) * _ss2((dE - 0.15 * xcS) / (0.30 * xcS)) * DTS
    MASK[(rgS > KS_) | (erA > KEm)] = 0.0
    mvD = np.where(MASK > 1e-3)[0]
    sideD = np.where((rgS > 0) & (rgS <= KS_) & (uS > 0) & (uS < 0.5), 1, np.where((rgS > 0) & (rgS <= KS_) & (uS > 0.5), -1, 0))
    _bd = [bind_point(X[i_], int(sideD[i_])) for i_ in mvD]
    BT_ = np.array([bd_[0] for bd_ in _bd]); BW_ = np.array([bd_[1] for bd_ in _bd])
    ED_ = np.array([tuple(e_.vertices) for e_ in face.data.edges]); okE = (rgS[ED_] <= KS_).all(1); ED_ = ED_[okE]
    CNT_ = np.bincount(ED_.ravel(), minlength=len(X)).astype(float)
    BINDQA['dense_tpl'] = {'strength': DTS, 'verts': int(len(mvD)), 'full_mask_verts': int((MASK > 0.99 * DTS).sum())}
def dense_fix(E, tn_):
    if DTS <= 0 or tn_ is None: return E, None
    names, kk = tn_
    if names[0].startswith('jaw') or 'mouthClose' in names: return E, None
    Dk = sum(delta(n_) for n_ in names); DT = kk * (BW_[:, :, None] * Dk[BT_]).sum(1) / sc
    Rr = np.zeros_like(X); Rr[mvD] = X[mvD] + DT - E[mvD]
    for _ in range(8):
        acc = np.zeros_like(X); np.add.at(acc, ED_[:, 0], Rr[ED_[:, 1]]); np.add.at(acc, ED_[:, 1], Rr[ED_[:, 0]])
        Rr = np.where(CNT_[:, None] > 0, 0.5 * Rr + 0.5 * acc / np.maximum(CNT_[:, None], 1), Rr)
    out = E + MASK[:, None] * Rr
    return out, round(float(np.linalg.norm(MASK[:, None] * Rr, axis=1).max() * 1000), 2)
for name, moves in POSES.items():
    apply(moves); E = evaluate(face); Ep = {o.name: evaluate(o) for o in parts}
    E, ef_ = edge_fix(E, tnames(name))
    if ef_ is not None: qa.setdefault('edge_fix_max_mm', {})[name] = ef_
    if name != 'tongueOut' or name not in RELATIVE:
        E, ll_ = lipline(E)
        if ll_ is not None: qa.setdefault('lipline_max_mm', {})[name] = ll_
    if name == 'mouthClose' and SEAL is not None:
        E, qa['mouthClose_seal'] = seal(E)
    # closed-mouth keys: the slit stays shut at the corners (P f11 smile opened 1-2 mm red triangles there); the
    # middle may still part as the template does (env BAKE_CORNER_SEAL=0: off)
    elif SEAL is not None and CSEAL and name.startswith(CSEAL):
        E, qa.setdefault('corner_seal', {})[name] = seal(E, corner=True)
    E, dn_ = dense_fix(E, tnames(name))
    if dn_ is not None: qa.setdefault('dense_tpl_max_mm', {})[name] = dn_
    if name != 'tongueOut' or name not in RELATIVE:
        E, rl_ = relax(E)
        if rl_ is not None: qa.setdefault('relax', {})[name] = rl_
    if name not in RELATIVE:
        s_cap = cap_scale(E)
        if s_cap < 1.0:
            E = X + s_cap * (E - X); Ep = {n_: P0[n_] + s_cap * (Ep[n_] - P0[n_]) for n_ in Ep}; qa.setdefault('lip_stretch_cap', {})[name] = round(s_cap, 3)
    reach = [np.linalg.norm(np.array(pb[n].head) - d) for k, n, d in moves if k == 'A']
    if name in RELATIVE:
        apply(RELATIVE[name]); Er = evaluate(face); Epr = {o.name: evaluate(o) for o in parts}
        if name == 'mouthClose': Er = relax(lipline(edge_fix(Er, tnames('jawOpen'))[0])[0])[0]   # the jawOpen key as stored
        if name == 'mouthClose':
            s_cap = cap_scale(Er)
            if s_cap < 1.0:
                E = X + s_cap * (E - X); Er = X + s_cap * (Er - X)
                Ep = {n_: P0[n_] + s_cap * (Ep[n_] - P0[n_]) for n_ in Ep}; Epr = {n_: P0[n_] + s_cap * (Epr[n_] - P0[n_]) for n_ in Epr}
        E = X + (E - Er); Ep = {n: P0[n] + (Ep[n] - Epr[n]) for n in Ep}
    D = E - X; DISP[name] = D
    add_key(face, name, E)
    for o in parts:
        if np.abs(Ep[o.name] - P0[o.name]).max() > 1e-6: add_key(o, name, Ep[o.name])
    flips = int(((tn(E) * N0).sum(1) < 0).sum())
    qa['keys'][name] = {'max_mm': round(float(np.linalg.norm(D, axis=1).max() * 1000), 2),
                        'moved_verts': int((np.linalg.norm(D, axis=1) > 1e-4).sum()), 'flipped_faces': flips,
                        'control_miss_mm': round(float(max(reach) * 1000), 2) if reach else None}
reset()
# left/right agreement: displacement of _L at v vs mirrored displacement of _R at mirror(v)
kd = KDTree(len(X))
for i, p in enumerate(X): kd.insert(Vector(p), i)
kd.balance()
mi = np.array([kd.find(Vector((-p[0], p[1], p[2])))[1] for p in X])
for nl, nr in PAIRS:
    DL, DR = DISP[nl], DISP[nr][mi] * np.array([-1, 1, 1])
    act = np.linalg.norm(DL, axis=1) > 2e-4
    err = np.linalg.norm(DL - DR, axis=1)[act]; mx = np.linalg.norm(DL, axis=1).max()
    qa['keys'][nl]['mirror_err_p95_pct'] = round(float(np.percentile(err, 95) / mx * 100), 1) if act.any() else None
json.dump(qa, open(os.path.join(OUT, 'bake_qa.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'arkit_rig.blend'), compress=True)
# export variant: drop the Rigify rig and metarig, keep the T1 lid rig
for o in [o for o in bpy.data.objects if o.type == 'MESH']:            # every rigged mesh (teeth_up, eyes too), not only keyed ones
    for m in list(o.modifiers):
        if m.type == 'ARMATURE' and m.object and m.object.name == 'face_rig': o.modifiers.remove(m)
    o.vertex_groups.clear() if o is not face else None
for n in ('face_rig', 'metarig'):
    if n in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[n])
for o in [o for o in bpy.data.objects if o.name.startswith('WGT-')]: bpy.data.objects.remove(o)   # Rigify control shapes
for g in list(face.vertex_groups): face.vertex_groups.remove(g)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'arkit.blend'), compress=True)
print('BAKED', len(POSES), 'rest', qa['rest_offset_mm'], 'jaw_sign', JAW_SIGN)
for k, v in qa['keys'].items(): print('  ', k, v)
