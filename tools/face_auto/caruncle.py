"""Caruncle: a low, lens-shaped pink mound filling the inner corner of the eye opening (after loop_organs on a
canthus_wedge base; heads without a caruncle wedge, e.g. cartoon / anime eyes, get none).

canthus_wedge.py re-routed the margin through P2's caruncle wedge to the visible inner tip; loop_organs cut the wedge
away, so the opening's inner end is a narrow angle between the upper and lower lid rims, deep in front of the eyeball.
Here (left built, right mirrored), in the frame tip -> outer corner (x) / up / view:
  - length LEN_F (14 %; ~16 % with the sloped end) of the opening width; across, a share W(x) of the opening height there: 0.9 at the tip (the
    nasal part fills the corner angle, its borders tucked just inside / behind the rims = continuous with the canthus
    skin, no seam), 0.42 at the crown (x 40-60 %), then a rounded lateral end (teardrop outline);
  - depth behind the rims' plane: crown 0.45 mm (0 at the tip), borders 0.18 mm under the crown (a flat lens), the
    lateral 40 % sloping back to 2.2 mm (into the pocket toward the plica);
  - closed pillow (a flat back sheet shares the border): no free rim from any side.
Object 'caruncle', material 'caruncle' (pink), smooth. Shape keys eyeBlinkLeft / eyeBlinkRight collapse it onto the
lids' meeting curve (meet 0.62) 2 mm behind it: partly covered at 0.5, hidden at 1 (same key names as the face;
caruncle_qa.py counts what is visible). Re-running replaces an existing 'caruncle'.
Writes <out.blend> and eyes json 'caruncle' (object, faces_per_eye, material, sizes) for the texture (None when none).
Usage: blender -b <loop.blend> -P caruncle.py -- <eyes.json (loop_organs)> <out.blend>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
a = sys.argv[sys.argv.index('--') + 1:]; EJ, OUT = a[0], os.path.abspath(a[1])
J = json.load(open(EJ)); K = int(J['rings']); E = J['eyes']['L']
C = np.array(E['C']); r = float(E['r']); view = np.array(E['view']); view /= np.linalg.norm(view)
face = bpy.data.objects['face']; me = face.data
X = np.array([tuple(v.co) for v in me.vertices])
ring = np.array([d.value for d in me.attributes['eye_ring'].data]); u = np.mod(np.array([d.value for d in me.attributes['eye_u'].data]), 1.0)
mk = np.where(ring == K)[0]; um = u[mk]
tip_i = mk[np.argmin(np.abs(um - 0.5))]; out_i = mk[np.argmin(np.minimum(um, 1 - um))]; tip = X[tip_i]
chord = float(np.linalg.norm(X[out_i] - tip))
if not E.get('canthus_wedge'):                              # cartoon / anime heads (no P2 caruncle wedge): no caruncle
    J['caruncle'] = None; json.dump(J, open(EJ, 'w'), indent=1)
    print('CARUNCLE', json.dumps({'built': False, 'reason': 'no canthus wedge (inner corner on the eyeball)'})); bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True); sys.exit(0)
Dz = float(E['canthus_wedge']['p2_corner_mm']) / 1000 + 0.001
for o_ in [o_ for o_ in bpy.data.objects if o_.name.startswith('caruncle')]:   # re-run: replace
    m_ = o_.data; bpy.data.objects.remove(o_)
    if m_.users == 0: bpy.data.meshes.remove(m_)
NS, NC = 14, 10
LEN_F, W_TIP, W_CROWN, D_CROWN, EL, D_END, D_BACK = 0.14, 0.9, 0.42, 0.00045, 0.00018, 0.0022, 0.0004
ax = X[out_i] - tip; chord = float(np.linalg.norm(ax)); ax /= chord
up = np.cross(view, ax); up /= np.linalg.norm(up)
if up[2] < 0: up = -up


def line(sel):                                              # a zone line (margin vertices near the tip) by x along the axis
    ids = mk[sel]; ids = ids[np.linalg.norm(X[ids] - tip, axis=1) < Dz]
    P = np.r_[tip[None], X[ids]]; x = (P - tip) @ ax; o = np.argsort(x); P, x = P[o], x[o]
    keep = np.r_[True, np.diff(x) > 1e-7]; return P[keep], x[keep]


PU, xU = line((um > 0) & (um < 0.5)); PL, xL = line(um > 0.5)
if len(PU) < 3 or len(PL) < 3:
    print('CARUNCLE', json.dumps({'built': False, 'reason': 'inner zone too short'})); bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True); sys.exit(0)
at = lambda P, xs, x: np.array([np.interp(x, xs, P[:, j]) for j in range(3)])
Lc = min(LEN_F * chord, 0.9 * xU[-1], 0.9 * xL[-1])


def sm(a_, b_, x):
    t_ = float(np.clip((x - a_) / (b_ - a_), 0, 1)); return t_ * t_ * (3 - 2 * t_)


def wshare(s_):                                             # share of the opening height across (teardrop outline)
    if s_ <= 0.15: return W_TIP
    if s_ <= 0.6: return W_TIP + (W_CROWN - W_TIP) * sm(0.15, 0.4, s_)
    return W_CROWN * math.sqrt(max(0.0, 1 - ((s_ - 0.6) / 0.4) ** 2))


def depth(s_, e):                                           # behind the rims' plane; e = 0 mid-line .. 1 border
    dc = D_CROWN * min(s_ / 0.25, 1.0) + max(0.0, (s_ - 0.6) / 0.4) ** 2 * (D_END - D_CROWN)
    return dc + EL * e * e                                  # flat lens across: the borders EL (0.18 mm) under the crown


S = np.linspace(0.0, 1.0, NS + 1); G = lambda i, j: i * (NC + 1) + j
Vf = []; Vb = []
for i, s_ in enumerate(S):
    x = s_ * Lc; U_, L_ = at(PU, xU, x), at(PL, xL, x); mid = (U_ + L_) / 2; w = wshare(s_)
    for j in range(NC + 1):
        c = (j / NC - 0.5) * w; e = abs(2 * j / NC - 1)
        p = mid + c * (U_ - L_)
        pf = p - view * depth(s_, e); pb = p - view * (depth(s_, 1.0) + D_BACK * (1 - e * e) * math.sin(math.pi * s_))
        for pt in (pf, pb):
            if np.linalg.norm(pt - C) < r + 0.0002: pt[:] = C + (pt - C) / np.linalg.norm(pt - C) * (r + 0.0002)
        Vf.append(pf); Vb.append(pb)
Vf = np.array(Vf); Vb = np.array(Vb); Vf[:NC + 1] = tip; Vb[:NC + 1] = tip
# one vertex list: front grid, then the back grid's interior columns (j = 1 .. NC-1; its border columns are the front's)
bidx = {}; V = list(Vf)
for i in range(NS + 1):
    for j in range(1, NC):
        bidx[(i, j)] = len(V); V.append(Vb[G(i, j)])
B_ = lambda i, j: G(i, j) if j in (0, NC) else bidx[(i, j)]
V = np.array(V)
fn = lambda f: np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
Ff = [[G(i, j), G(i, j + 1), G(i + 1, j + 1), G(i + 1, j)] for i in range(NS) for j in range(NC)]
if np.mean([fn(f) @ view for f in Ff[NC:]]) < 0: Ff = [f[::-1] for f in Ff]
Fb = [[B_(i, j), B_(i + 1, j), B_(i + 1, j + 1), B_(i, j + 1)] for i in range(NS) for j in range(NC)]
if np.mean([fn(f) @ view for f in Fb[NC:]]) > 0: Fb = [f[::-1] for f in Fb]
Fc = Ff + Fb
nl = len(V); VV = np.r_[V, V * [-1, 1, 1]]; FF = Fc + [[x_ + nl for x_ in f[::-1]] for f in Fc]
m2 = bpy.data.meshes.new('caruncle'); m2.from_pydata(VV.tolist(), [], FF); m2.update()
bm = bmesh.new(); bm.from_mesh(m2); bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7); bm.to_mesh(m2); bm.free(); m2.update()
for p in m2.polygons: p.use_smooth = True
VV = np.array([tuple(v.co) for v in m2.vertices])


def closed(p):                                              # closed: onto the lids' meeting curve, 2 mm behind it
    x = float(np.clip((p - tip) @ ax, 0, Lc)); s_ = x / Lc; U_, L_ = at(PU, xU, x), at(PL, xL, x); Mq = U_ + 0.62 * (L_ - U_)
    q = Mq - view * (0.002 * min(s_ / 0.12, 1.0))
    if np.linalg.norm(q - C) < r - 0.0005: q = C + (q - C) / np.linalg.norm(q - C) * (r - 0.0005)
    return q if s_ > 1e-6 else tip


o_tmp = bpy.data.objects.new('_tmp', m2)
o_tmp.shape_key_add(name='Basis')
for nm, sg in (('eyeBlinkLeft', 1.0), ('eyeBlinkRight', -1.0)):    # per side (x sign); the blink keys of the face
    kb = o_tmp.shape_key_add(name=nm, from_mix=False); co = VV.copy()
    for k_, p in enumerate(VV):
        if p[0] * sg > 1e-9: co[k_] = closed(p * [sg, 1, 1]) * [sg, 1, 1]
    kb.data.foreach_set('co', co.ravel())
bpy.data.objects.remove(o_tmp)
mat = bpy.data.materials.get('caruncle') or bpy.data.materials.new('caruncle'); mat.diffuse_color = (0.86, 0.55, 0.55, 1); m2.materials.append(mat)
o = bpy.data.objects.new('caruncle', m2); bpy.context.scene.collection.objects.link(o)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
info = {'object': 'caruncle', 'faces_per_eye': len(Fc), 'material': 'caruncle', 'length_mm': round(Lc * 1000, 2), 'length_share_of_opening': LEN_F,
        'height_share_tip_crown': [W_TIP, W_CROWN], 'depth_behind_rims_mm': {'crown': D_CROWN * 1000, 'border_under_crown': EL * 1000, 'lateral_end': D_END * 1000},
        'closed_pillow': True, 'keys': ['eyeBlinkLeft', 'eyeBlinkRight'], 'zone_mm': round(Dz * 1000, 2),
        'note': 'caruncle.py: lens mound filling the inner corner (nasal part continuous with the canthus tip and rims); paint pink, crown lighter, lateral end toward the plica'}
J['caruncle'] = info; json.dump(J, open(EJ, 'w'), indent=1)
print('CARUNCLE', json.dumps(info))
