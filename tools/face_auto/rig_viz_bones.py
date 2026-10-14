"""겹침생성 · where the face rig's bones are: coloured bone proxies over a faded head, rest and jaw-open, plus mouth/eye close-ups.

Armatures do not render, so every deform bone (DEF-* of 'face_rig') becomes a mesh proxy: a slim octahedron from head
to tail plus a small sphere at the head, sized from face height and coloured by region (from the bone name). The eye and
teeth ORG bones are not deform bones but mark where those organs are anchored, so they are drawn as rods without a joint
sphere. Tongue, teeth and eye proxies get a larger minimum size, because the tongue chain is only ~2 cm long, and in the
full views they also show at 60 % through the bones in front of them.
Workbench passes per view on transparent film (studio-lit head; flat-lit bones, so the PNG shows the exact palette
colours) are composited in numpy with the bones on top of the lightened head, like Blender's 'In Front'. Bones lying far
behind the visible surface (the other ear in 3/4, the far side in the side view) are hidden where the head covers them,
and the neck/head axis ('other') is drawn only in the side view, where it does not cross the face. Framing comes from
the head mesh and the bone bounding box. Close-ups (mouth side and 3/4, eye 3/4) fade the context bones, draw the
tongue/teeth/eye bones on top and ghost the inner organ meshes through the skin.
Pose test: jaw_master turns ~15 deg (sign chosen so the chin drops), the mesh deforms through its Armature modifier, the
proxies are redrawn over a faint ghost of the rest bones, and a black ball with a white rim, drawn last, marks the jaw
hinge (jaw_master head). QA adds weight mirror symmetry and the jaw deformation's left/right asymmetry.
Writes bones_{front,side,34,mouth_side,mouth_34,eye_34}.png, bones_jaw_{front,side,34,mouth_side}.png, bones_palette.json,
bones_qa.json.
Usage: blender -b <rigify_fit.blend> -P rig_viz_bones.py -- <out_dir> <landmarks.json> [jaw_deg=15]
"""
import bpy, bmesh, sys, os, json, shutil
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0]); LMJ = a[1]; JAW = float(a[2]) if len(a) > 2 else 15.0
TMP = os.path.join(OUT, '_passes'); os.makedirs(TMP, exist_ok=True)
sc = bpy.context.scene; arm = bpy.data.objects['face_rig']; face = bpy.data.objects['face']; me = face.data; MW = arm.matrix_world
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]

PAL = {'jaw': (230, 126, 34), 'lips': (215, 38, 61), 'lids': (0, 168, 181), 'brows': (123, 63, 191), 'cheeks': (224, 86, 160),
       'nose': (212, 176, 0), 'ears': (150, 100, 60), 'tongue': (140, 215, 40), 'teeth': (255, 238, 150), 'eye': (31, 95, 208),
       'forehead': (128, 128, 0), 'other': (80, 80, 80), 'jaw_pivot': (20, 20, 20)}
KEY = {'jaw': 'jaw', 'chin': 'jaw', 'lip': 'lips', 'lid': 'lids', 'brow': 'brows', 'cheek': 'cheeks', 'nose': 'nose', 'ear': 'ears',
       'tongue': 'tongue', 'teeth': 'teeth', 'eye': 'eye', 'forehead': 'forehead', 'temple': 'forehead'}
region = lambda n: KEY.get(n.split('-', 1)[-1].split('.')[0].split('_')[0], 'other')
flip = lambda n: '.'.join({'L': 'R', 'R': 'L'}.get(s, s) for s in n.split('.'))
side_of = lambda n: 'L' if 'L' in n.split('.') else 'R' if 'R' in n.split('.') else ''
DEF = [b.name for b in arm.data.bones if b.use_deform]
REF = [n for n in ('ORG-eye.L', 'ORG-eye.R', 'ORG-teeth.T', 'ORG-teeth.B') if n in arm.data.bones]   # anchors, not deform
INNER = ('tongue', 'teeth', 'eye')
HEAD_OBJ = [o for o in (face, *(bpy.data.objects.get(n) for n in ('eyes', 'teeth_up', 'teeth_lo', 'tongue'))) if o]; ORGANS = HEAD_OBJ[1:]
HEAD_COL = {'face': (0.80, 0.80, 0.81), 'eyes': (0.95, 0.95, 0.95), 'teeth_up': (0.93, 0.92, 0.86), 'teeth_lo': (0.93, 0.92, 0.86), 'tongue': (0.78, 0.55, 0.55)}
FAR, FAR_A, CTX_A, GHOST_A, ORG_A, XRAY_A = 0.6 * fh, 0.5, 0.3, 0.3, 0.5, 0.6    # depth for 'far'; opacities: far, context, rest ghost, organs, inner bones
# view -> (direction toward the camera, close-up kind); close-up kind -> (main regions, on-top regions, framed regions, near eye only, min frame/fh)
VIEWS = {'front': ((0, -1, 0), None), 'side': ((1, 0, 0), None), '34': ((0.7, -0.7, 0), None),
         'mouth_side': ((1, 0, 0), 'mouth'), 'mouth_34': ((0.7, -0.7, 0), 'mouth'), 'eye_34': ((0.7, -0.7, 0), 'eye')}
FOCUS = {'mouth': ({'lips', 'jaw'}, {'tongue', 'teeth'}, {'lips', 'tongue', 'teeth'}, False, 0.7), 'eye': ({'lids'}, {'eye'}, {'lids', 'eye'}, True, 0.5)}

# ---- render setup: Workbench, object colours, outline, transparent film
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.film_transparent = True; sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = sc.render.resolution_y = 1000; sc.render.resolution_percentage = 100; sc.render.image_settings.color_mode = 'RGBA'
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_object_outline = True; sh.object_outline_color = (0.12, 0.12, 0.12)
sh.show_xray = False; sh.show_shadows = False; sh.show_cavity = False
for o in HEAD_OBJ: o.color = (*HEAD_COL.get(o.name, (0.8, 0.8, 0.8)), 1.0)
cam = bpy.data.cameras.new('rv_cam'); cam.type = 'ORTHO'; co = bpy.data.objects.new('rv_cam', cam); sc.collection.objects.link(co); sc.camera = co

# ---- bones, head mesh, depth test
def bone_ends(names, posed):
    pbs = arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones if posed else None
    return {n: tuple(np.array(MW @ v) for v in ((pbs[n].head, pbs[n].tail) if posed else (arm.data.bones[n].head_local, arm.data.bones[n].tail_local)))
            for n in names}
def mesh_pos(o):
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get()); m = ev.to_mesh(); P = np.empty(len(m.vertices) * 3); m.vertices.foreach_get('co', P)
    ev.to_mesh_clear(); W = np.array(o.matrix_world); return P.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3]
POLYS = [tuple(p.vertices) for p in me.polygons]; BVH = {}
def far_set(E, X, view):
    """bones whose samples (10/50/90 %) mostly sit more than FAR behind the first head surface seen along the view"""
    if id(X) not in BVH: BVH[id(X)] = BVHTree.FromPolygons(X.tolist(), POLYS)
    bvh = BVH[id(X)]; d = np.array(Vector(VIEWS[view][0]).normalized()); out = set()
    for n, (h, t) in E.items():
        deep = 0
        for s in (0.1, 0.5, 0.9):
            p = h + (t - h) * s; hit = bvh.ray_cast(Vector(p + d), Vector(-d))
            deep += hit[0] is not None and 1.0 - hit[3] > FAR
        if deep >= 2: out.add(n)
    if abs(d[0]) < 1e-6: out |= {flip(n) for n in out} & set(E)     # mirror-symmetric view: a pair fades together
    return out

# ---- framing from the head mesh and bone bbox (projected on the camera axes); close-ups from their focus bones
def frame(view, Es, headpts):
    d, kind = VIEWS[view]; d = Vector(d).normalized(); q = (-d).to_track_quat('-Z', 'Y')
    r, u = np.array(q @ Vector((1, 0, 0))), np.array(q @ Vector((0, 1, 0))); names = [n for n in Es[0] if region(n) != 'other']
    R = np.stack([r, u]).T
    if kind is None:                                                  # whole head + all poses, room below the chin for the open jaw
        uv = np.vstack([headpts, LT[24] - [0, 0, 0.15 * fh]] + [np.array(E[n]) for E in Es for n in names]) @ R
        lo, hi = uv.min(0), uv.max(0); c = (lo + hi) / 2; s = float((hi - lo).max()) * 1.06
    else:                                                             # focus bones in both poses, at least smin * fh wide
        _, _, frg, near, smin = FOCUS[kind]; names = [n for n in names if region(n) in frg and (not near or side_of(n) == 'L')]
        uv = np.vstack([np.array(E[n]) for E in Es for n in names]) @ R; lo, hi = uv.min(0), uv.max(0); c = (lo + hi) / 2
        s = max(smin * fh, float((hi - lo).max()) * 1.35)
    return Vector(r * c[0] + u * c[1]) + d * 2, q.to_euler(), s
def aim(view): co.location, co.rotation_euler, cam.ortho_scale = FR[view]

# ---- bone proxies: one mesh per (region, layer), object colour = region colour
bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
ICO_V = np.array([v.co for v in bm.verts]); ICO_F = np.array([[v.index for v in f.verts] for f in bm.faces]); bm.free()
OCT_F = np.array([(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)])
proxies = {}
lin = lambda c: ((c / 255 + 0.055) / 1.055) ** 2.4          # flat-lit bones then show the exact palette sRGB
def build(E, lay, pivot=None):
    for o in sum(proxies.values(), []): m = o.data; bpy.data.objects.remove(o); bpy.data.meshes.remove(m)
    proxies.clear(); acc = {}
    for n, (h, t) in E.items():
        rg, lys, L = region(n), lay(n), np.linalg.norm(t - h)
        if not lys or L < 1e-6: continue
        y = (t - h) / L; up = np.array([0, 0, 1.0]) if abs(y[2]) < 0.9 else np.array([1.0, 0, 0])
        x = np.cross(y, up); x /= np.linalg.norm(x); z = np.cross(x, y)
        w, r = np.clip(0.1 * L, 0.005 * fh, 0.02 * fh), np.clip(0.15 * L, 0.007 * fh, 0.012 * fh)
        if rg in INNER: w, r = max(w, 0.011 * fh), max(r, 0.013 * fh)      # short inner chains must still read at full-face scale
        m = h + y * 0.1 * L; V = [np.array([h, m + x * w, m + z * w, m - x * w, m - z * w, t])]; F = [OCT_F]; S = [np.zeros(8, bool)]
        if n not in REF: V.append(h + ICO_V * r); F.append(ICO_F); S.append(np.ones(len(ICO_F), bool))   # joint sphere, like Blender's bones
        for ly in lys:
            A = acc.setdefault((rg, ly), [[], [], [], 0])
            for v, f, s in zip(V, F, S): A[0].append(v); A[1].append(f + A[3]); A[2].append(s); A[3] += len(v)
    if pivot is not None: acc[('jaw_pivot', 'pivot')] = [[pivot + ICO_V * 0.028 * fh], [ICO_F], [np.ones(len(ICO_F), bool)], 0]
    for (rg, ly), (V, F, S, _) in acc.items():
        me_ = bpy.data.meshes.new('rv_' + rg); me_.from_pydata(np.concatenate(V).tolist(), [], np.concatenate(F).tolist())
        me_.validate(); me_.polygons.foreach_set('use_smooth', np.concatenate(S)); me_.update()
        o = bpy.data.objects.new('rv_' + rg, me_); o.color = (*[lin(c) for c in PAL[rg]], 1.0); sc.collection.objects.link(o)
        proxies.setdefault(ly, []).append(o)

# ---- passes and numpy compositing (bpy images: raw byte values in, raw out; straight alpha)
def render(tag, show):
    for o in sc.objects: o.hide_render = o not in show
    if not show: return None
    p = os.path.join(TMP, tag + '.png'); sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(p, check_existing=False); px = np.empty(im.size[0] * im.size[1] * 4, np.float32); im.pixels.foreach_get(px)
    A = px.reshape(im.size[1], im.size[0], 4); bpy.data.images.remove(im); return A
def over(dst, src, k=1.0):
    if src is None: return
    k = np.asarray(k, np.float32); al = src[..., 3:4] * (k[..., None] if k.ndim else k); dst[..., :3] = src[..., :3] * al + dst[..., :3] * (1 - al)
def stack(*Ls):
    Ls = [x for x in Ls if x is not None]; O = Ls[0].copy() if Ls else None
    for s in Ls[1:]:
        sa, oa = s[..., 3:4], O[..., 3:4]; na = sa + oa * (1 - sa)
        O[..., :3] = (s[..., :3] * sa + O[..., :3] * oa * (1 - sa)) / np.maximum(na, 1e-6); O[..., 3:4] = na
    return O
def rim(P, px=4):
    """white halo around the pivot ball: its alpha dilated by px (on the ball's bbox only)"""
    al = P[..., 3]; ys, xs = np.nonzero(al > 0); R = np.ones_like(P); R[..., 3] = 0
    if not len(ys): return None
    y0, y1, x0, x1 = max(ys.min() - px - 1, 0), ys.max() + px + 2, max(xs.min() - px - 1, 0), xs.max() + px + 2; a_ = al[y0:y1, x0:x1]; d = a_.copy()
    for dy in range(-px, px + 1):
        for dx in range(-px, px + 1):
            if dx * dx + dy * dy <= px * px: d = np.maximum(d, np.roll(np.roll(a_, dy, 0), dx, 1))
    R[y0:y1, x0:x1, 3] = d; return R
def save(A, name):
    im = bpy.data.images.new(name, A.shape[1], A.shape[0], alpha=True); im.pixels.foreach_set(A.ravel().astype(np.float32))
    p = im.filepath_raw = os.path.join(OUT, name); im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im); return p
def pal_px(C):
    c8 = np.round(np.clip(C[..., :3], 0, 1) * 255).astype(np.int16)
    return {k: int((np.abs(c8 - np.array(v)).max(-1) <= 2).sum()) for k, v in PAL.items()}
def shot(view, name, E, X, ghost=None, pivot=None):
    far = far_set(E, X, view); kind = VIEWS[view][1]
    def lay(n):
        rg = region(n)
        if rg == 'other': return ('main',) if view == 'side' else ()     # the head/neck axis would cross the face elsewhere
        if n in far: return ('far',)
        if kind is None: return ('main', 'xray') if rg in INNER else ('main',)   # inner bones also show faintly through the bones in front
        mn, tp = FOCUS[kind][:2]; return ('top',) if rg in tp else ('main',) if rg in mn else ('ctx',)
    build(E, lay, pivot); bpy.context.view_layer.update(); aim(view)
    sh.light = 'STUDIO'; H = render(name + '_head', HEAD_OBJ); I = render(name + '_org', ORGANS) if kind else None
    sh.light = 'FLAT'; B = {k: render(name + '_' + k, proxies.get(k, [])) for k in ('far', 'ctx', 'main', 'xray', 'top', 'pivot')}
    Ha = H[..., 3].copy(); H[..., :3] = H[..., :3] * 0.62 + 0.38; H[..., 3] *= 0.9                 # light, slightly see-through head
    C = np.ones_like(H); C[..., :3] = 0.97; over(C, H)
    if I is not None: I[..., :3] = I[..., :3] * 0.85 + 0.1; over(C, I, ORG_A)                     # teeth/tongue/eyes ghosted through the skin
    over(C, ghost, GHOST_A); over(C, B['far'], FAR_A * (1 - Ha))                                   # far bones only where no head covers them
    over(C, B['ctx'], CTX_A); over(C, B['main']); over(C, B['xray'], XRAY_A); over(C, B['top'])
    if B['pivot'] is not None: over(C, rim(B['pivot'])); over(C, B['pivot'])                     # hinge marker last, never hidden
    save(C, name); PX[name] = pal_px(C); return stack(B['main'], B['top']), sorted(n for n in far if lay(n) == ('far',))

# ---- QA: counts, bone mirror pairs, centre line, weight mirror symmetry
qa = {'total_bones': len(arm.data.bones), 'deform_bones': len(DEF), 'per_region': {}, 'reference_bones': REF, 'face_height_mm': round(fh * 1000, 1)}
for n in DEF: qa['per_region'][region(n)] = qa['per_region'].get(region(n), 0) + 1
qa['per_region'] = {k: qa['per_region'].get(k, 0) for k in PAL if k != 'jaw_pivot'}
rest = bone_ends(DEF + REF, False); fx = np.array([-1, 1, 1]); mm = []
for n in DEF:
    if side_of(n) == 'L' and flip(n) in rest:
        (hl, tl), (hr, tr) = rest[n], rest[flip(n)]; mm.append((n, np.linalg.norm(hl * fx - hr) * 1000, np.linalg.norm(tl * fx - tr) * 1000))
worst = max(mm, key=lambda e: e[1]) if mm else ('', 0, 0)
cen = [n for n in DEF if not side_of(n)]; cx = {n: max(abs(rest[n][0][0]), abs(rest[n][1][0])) * 1000 for n in cen}
qa['mirror'] = {'pairs': len(mm), 'max_head_mismatch_mm': round(worst[1], 3), 'worst_pair': worst[0], 'max_tail_mismatch_mm': round(max((e[2] for e in mm), default=0), 3),
                'unpaired_side': sorted(n for n in DEF if side_of(n) and flip(n) not in rest), 'centre_bones': len(cen),
                'centre_max_abs_x_mm': round(max(cx.values(), default=0), 3), 'centre_off_axis': sorted(n for n in cen if cx[n] >= 0.5)}
# the mesh is neither vertex- nor exactly shape-symmetric (head p99 ~5 mm), so each head vertex is mirrored onto the surface
# (within 3 mm, facing the same way so the touching lips are not mixed up) and compared with the barycentric blend there
X0 = mesh_pos(face); me.calc_loop_triangles(); TRI = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', TRI)
TRI = TRI.reshape(-1, 3); bvt = BVHTree.FromPolygons(X0.tolist(), TRI.tolist()); TI = np.full(len(X0), -1); NP = np.zeros_like(X0)
N0 = np.empty(len(X0) * 3, np.float32); me.vertex_normals.foreach_get('vector', N0); N0 = N0.reshape(-1, 3) * fx; HEADV = X0[:, 2] > LT[24][2] - 0.1 * fh
for i in np.where(HEADV)[0]:
    hit = bvt.find_nearest(Vector(X0[i] * fx), 3e-3)
    if hit[0] is not None and hit[1].dot(Vector(N0[i])) > 0.5: NP[i], TI[i] = hit[0], hit[2]
OKM = TI >= 0; T3 = TRI[TI[OKM]]; A_, B_, C_ = X0[T3[:, 0]], X0[T3[:, 1]], X0[T3[:, 2]]; v0, v1, v2 = B_ - A_, C_ - A_, NP[OKM] - A_
d00, d01, d11, d20, d21 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1), (v2 * v0).sum(1), (v2 * v1).sum(1); den = np.maximum(d00 * d11 - d01 * d01, 1e-20)
BC = np.clip(np.stack([np.zeros(len(den)), (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den], 1), 0, 1); BC[:, 0] = np.clip(1 - BC[:, 1:].sum(1), 0, 1)
BC /= BC.sum(1, keepdims=True); mirror_at = lambda F: sum(BC[:, k, None] * F[T3[:, k]] for k in range(3))   # field F sampled at the mirror points
dgr = [g for g in face.vertex_groups if g.name in set(DEF)]; col = {g.index: k for k, g in enumerate(dgr)}; gn = [g.name for g in dgr]
W = np.zeros((len(X0), len(dgr)), np.float32)
for v in me.vertices:
    for e in v.groups:
        k = col.get(e.group)
        if k is not None: W[v.index, k] = e.weight
perm = [gn.index(flip(n)) if flip(n) in gn else k for k, n in enumerate(gn)]
dW = np.abs(W[OKM] - mirror_at(W)[:, perm]); dv = dW.max(1); wv = int(dv.argmax())
SD = np.linalg.norm(NP[OKM] - X0[OKM] * fx, axis=1) * 1000
qa['weight_mirror'] = {'deform_groups': len(gn), 'head_verts': int(HEADV.sum()), 'matched_verts': int(OKM.sum()),
                       'mirror_surface_dist_mm_p50_p99': [round(float(np.quantile(SD, q)), 2) for q in (0.5, 0.99)],
                       'max_weight_diff': round(float(dv.max()), 4), 'worst_group': gn[int(dW[wv].argmax())], 'worst_at_mm': [round(float(x) * 1000, 1) for x in X0[OKM][wv]],
                       'p99_weight_diff': round(float(np.quantile(dv, 0.99)), 4), 'p999_weight_diff': round(float(np.quantile(dv, 0.999)), 4),
                       'verts_diff_gt_0.1': int((dv > 0.1).sum())}

# ---- jaw pose: turn jaw_master about its local X; pick the sign that drops the chin (DEF-jaw tail)
ring = np.zeros(len(me.vertices), int)
if 'mouth_ring' in me.attributes: me.attributes['mouth_ring'].data.foreach_get('value', ring)
def lip_pick(group, lower):
    """front-most vertex of the lip at the centre line (|x| < 2 mm); vertex group if present, else rings below/above the slit"""
    cand = np.where((ring >= 1) & (ring <= 12) & (np.abs(X0[:, 0]) < 0.002))[0]; g = face.vertex_groups.get(group)
    if g is not None: sel = np.array([i for i in cand if any(e.group == g.index and e.weight > 0.5 for e in me.vertices[int(i)].groups)], int)
    else: zs = X0[(ring == 12) & (np.abs(X0[:, 0]) < 0.002), 2].mean(); sel = cand[(X0[cand, 2] < zs) == lower]
    return int(sel[np.argmin(X0[sel, 1])]) if len(sel) else None
LO, UP = lip_pick('mouth_lower', True), lip_pick('mouth_upper', False)
TL = bpy.data.objects.get('teeth_lo'); TL0 = mesh_pos(TL) if TL else None
pj = arm.pose.bones['jaw_master']; pj.rotation_mode = 'QUATERNION'; Q0 = pj.rotation_quaternion.copy(); tail0 = rest['DEF-jaw'][1]; sign_ok = False
for sgn in (1, -1):
    QJ = Quaternion((1, 0, 0), np.radians(JAW) * sgn); pj.rotation_quaternion = QJ; bpy.context.view_layer.update()
    if bone_ends(['DEF-jaw'], True)['DEF-jaw'][1][2] < tail0[2] - 1e-4: sign_ok = True; break
pbe = arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones
Mr = MW @ arm.data.bones['DEF-jaw'].matrix_local; Mp = MW @ pbe['DEF-jaw'].matrix
posed = bone_ends(DEF + REF, True); X1 = mesh_pos(face); piv = np.array(MW @ arm.data.bones['jaw_master'].head_local)
mv = lambda i: None if i is None else [round(float(x), 2) for x in (X1[i] - X0[i]) * 1000]
ln = lambda i: None if i is None else round(float(np.linalg.norm(X1[i] - X0[i]) * 1000), 2)
disp = {n: 1000 * max(np.linalg.norm(posed[n][0] - rest[n][0]), np.linalg.norm(posed[n][1] - rest[n][1])) for n in DEF}
D = X1 - X0; asym = np.linalg.norm(D[OKM] - mirror_at(D) * fx, axis=1) * 1000; av = int(asym.argmax())   # a centre-line pose must deform both sides alike
qa['jaw_pose'] = {'control': 'jaw_master', 'requested_deg': JAW, 'sign': sgn, 'sign_ok': sign_ok, 'pivot_mm': [round(float(x) * 1000, 1) for x in piv],
                  'DEF_jaw_rotation_deg': round(float(np.degrees((Mp @ Mr.inverted()).to_quaternion().angle)), 2),
                  'DEF_jaw_tail_move_mm': [round(float(x) * 1000, 2) for x in posed['DEF-jaw'][1] - tail0],
                  'lower_lip_centre_vertex': LO, 'lower_lip_centre_move_mm': mv(LO), 'lower_lip_centre_move_len_mm': ln(LO),
                  'upper_lip_centre_vertex': UP, 'upper_lip_centre_move_len_mm': ln(UP),
                  'teeth_lo_max_move_mm': round(float(np.linalg.norm(mesh_pos(TL) - TL0, axis=1).max() * 1000), 2) if TL else None,
                  'region_max_bone_move_mm': {rg: round(max((v for n, v in disp.items() if region(n) == rg), default=0), 2) for rg in qa['per_region'] if qa['per_region'][rg]},
                  'moved_threshold_mm': 2.0, 'moved_deform_bones': sorted(n for n in DEF if disp[n] > 2.0),
                  'deform_asym_max_mm': round(float(asym.max()), 3), 'deform_asym_at_mm': [round(float(x) * 1000, 1) for x in X0[OKM][av]],
                  'deform_asym_p99_mm': round(float(np.quantile(asym, 0.99)), 3), 'deform_asym_p999_mm': round(float(np.quantile(asym, 0.999)), 3)}
qa['jaw_pose']['n_moved_deform_bones'] = len(qa['jaw_pose']['moved_deform_bones'])
pj.rotation_quaternion = Q0; bpy.context.view_layer.update()

# ---- frames shared by rest and jaw shots (both poses inside), then rest views and jaw views
FR = {v: frame(v, [rest, posed], X0[X0[:, 2] > LT[24][2] + 0.1 * fh]) for v in VIEWS}     # skull/face above the jaw line, not the torso
qa['frames'] = {v: {'view_plane_centre_mm': [round(c * 1000, 1) for c in loc - Vector(VIEWS[v][0]).normalized() * 2], 'size_mm': round(s * 1000, 1)} for v, (loc, _, s) in FR.items()}
PX = {}; ghosts = {}; qa['hidden_far_bones'] = {}
for v in VIEWS: ghosts[v], qa['hidden_far_bones'][v] = shot(v, 'bones_%s.png' % v, rest, X0)
pj.rotation_quaternion = QJ; bpy.context.view_layer.update()
for v in ('front', 'side', '34', 'mouth_side'): shot(v, 'bones_jaw_%s.png' % v, posed, X1, ghosts[v], piv)
qa['palette_px'] = {k: {r: c for r, c in d.items() if r in INNER + ('jaw', 'lips', 'other', 'jaw_pivot')} for k, d in PX.items()}
json.dump({k: list(v) for k, v in PAL.items()} | {'_note': 'rgb 0-255; teeth/eye = ORG anchor bones (non-deform, rods without joint sphere); '
           'jaw_pivot = black ball with white rim at jaw_master head (jaw images); close-ups: faint bones = context, tongue/teeth/eye drawn on top, '
           'organ meshes ghosted through the skin; jaw images: faint bones = rest pose; far-side bones hidden behind the head; other = neck/head axis, side views only'},
          open(os.path.join(OUT, 'bones_palette.json'), 'w'), indent=1)
json.dump(qa, open(os.path.join(OUT, 'bones_qa.json'), 'w'), indent=1)
shutil.rmtree(TMP, ignore_errors=True)
print('RIGVIZ', json.dumps({k: qa[k] for k in ('deform_bones', 'mirror', 'weight_mirror')}))
print('RIGVIZ_JAW', json.dumps({k: v for k, v in qa['jaw_pose'].items() if k != 'moved_deform_bones'}))
print('RIGVIZ_PX', json.dumps(qa['palette_px']))
