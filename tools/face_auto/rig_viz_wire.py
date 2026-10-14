"""겹침생성 · grey clay views of the final head with its wire mesh: the organ rings around the eye and mouth over the original head mesh.

A baked head (arkit_b.blend: face with ARKit shape keys, eyes, teeth_up / teeth_lo / tongue) is rendered with Workbench
in plain greys (skin, darker mouth cavity, lighter eyeballs and teeth, mid-grey tongue), soft studio light, ortho
camera. Workbench draws no viewport overlays, so the wire is real geometry: every mesh edge in the frame becomes a thin
flat quad facing the camera (constant 1.2 px wide in close-ups, 0.6 px in the whole-face views, ends overlapping so the lines join), pushed a few pixel widths
toward the camera so it wins the depth test against its own surface but stays hidden behind any nearer surface (the
other side of the lid, the far cheek in 3/4). Face edges are dark; eyeball, teeth and tongue edges a lighter grey. Lines
taper toward vertices of valence > 8 (fan poles of the mouth cap, eyeball poles) so converging spokes do not merge
into a dark blob. Output PNGs are 8-bit grey without dither (the scene is all grey), about a quarter of RGB size.
Posed shots set the shape key of that name on every object that has it (face, teeth_lo, tongue), the eyes stay as they
are, and the lines are built from the evaluated (posed) positions.
Frames: whole face from the brow/chin landmarks (2, 5, 24) and the head mesh; eye close-ups from the outer eye ring
(eye_ring = 1 on the left, rest and blink) and mouth close-ups from the outer mouth ring (mouth_ring = 1, rest and
jawOpen), both with a margin so the surrounding original head mesh shows. Fallbacks without ring attributes: the
eyeball from eyes.json / the left eyeball verts, the teeth and tongue for the mouth.
Writes grey_{front,34}.png, grey_{front,34}_wire.png, wire_eye_{front_rest,front_blink,34_rest,34_blink}.png,
wire_mouth_{front_rest,front_open,34_rest,34_open}.png (no text) and wire_qa.json (frames, edges drawn, dark-pixel share
of each image, how far the posed keys move face / teeth_lo / tongue, sharp folds (> 100 deg) near the outer organ
rings with the left and right eye counted apart, the L/R mirror check (positions vs triangulation: edges whose mirror
image is no edge), bare eyeball outside the original skin (surface samples: count, area, how far out; n/a without the
eye_ring attribute), timings).
Usage: blender -b <arkit_b.blend> -P rig_viz_wire.py -- <out_dir> <landmarks.json> [<eyes.json>]
"""
import bpy, sys, os, json, time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

T0 = time.time()
a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0]); os.makedirs(OUT, exist_ok=True)
LT = {int(k): np.array(v) for k, v in json.load(open(a[1])).items() if not k.startswith('_')}
JE = json.load(open(a[2])) if len(a) > 2 and os.path.exists(a[2]) else None
RES, RES_FULL, LINE_PX, LINE_FULL, VAL_FULL = 1400, 1600, 1.2, 0.6, 8.0   # long side of close-ups / whole face; line widths in px; pole taper
PARTS = ('face', 'eyes', 'teeth_up', 'teeth_lo', 'tongue')
sc = bpy.context.scene
for o in bpy.data.objects: o.hide_render = o.name not in PARTS
face = bpy.data.objects['face']; me = face.data; N = len(me.vertices)
attr = lambda n: np.array([d.value for d in me.attributes[n].data]) if n in me.attributes else None
ering, mring = attr('eye_ring'), attr('mouth_ring')

# ---- greys (sRGB); the cavity slot of the face gets a darker grey so the open mouth reads
GREY = {'skin': 0.70, 'cavity': 0.42, 'eyes': 0.88, 'teeth': 0.95, 'tongue': 0.56, 'line': 0.07, 'line_organ': 0.36}
def mat(n, g):
    m = bpy.data.materials.new('wv_' + n); m.diffuse_color = (g ** 2.2,) * 3 + (1.0,); m.roughness = 0.7; m.metallic = 0.0; return m
MS = {k: mat(k, g) for k, g in GREY.items()}
for i, m in enumerate(me.materials): me.materials[i] = MS['cavity'] if m and m.name.startswith('mouth_inner') else MS['skin']
if not len(me.materials): me.materials.append(MS['skin'])
for n, k in (('eyes', 'eyes'), ('teeth_up', 'teeth'), ('teeth_lo', 'teeth'), ('tongue', 'tongue')):
    o = bpy.data.objects.get(n)
    if not o: continue
    o.data.materials.clear(); o.data.materials.append(MS[k]); o.data.polygons.foreach_set('material_index', np.zeros(len(o.data.polygons), np.int32))
OBJ = {n: bpy.data.objects[n] for n in PARTS if n in bpy.data.objects}
EDGES, VS = {}, {}
for n, o in OBJ.items():
    e = np.empty(len(o.data.edges) * 2, np.int32); o.data.edges.foreach_get('vertices', e); EDGES[n] = e.reshape(-1, 2)
    VS[n] = np.minimum(1.0, VAL_FULL / np.maximum(np.bincount(e, minlength=len(o.data.vertices)), 1))   # full width up to valence 8

def setkeys(keys):
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]: kb.value = keys.get(kb.name, 0.0)
    bpy.context.view_layer.update()
def state(keys):
    """set the keys, return evaluated world vertex positions per part"""
    setkeys(keys); dg = bpy.context.evaluated_depsgraph_get(); S = {}
    for n, o in OBJ.items():
        oe = o.evaluated_get(dg); m = oe.to_mesh(); X = np.empty(len(m.vertices) * 3); m.vertices.foreach_get('co', X)
        Mw = np.array(o.matrix_world); S[n] = X.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]; oe.to_mesh_clear()
    return S
ST = {'rest': {}, 'blink': {'eyeBlinkLeft': 1.0}, 'open': {'jawOpen': 1.0}}
SS = {k: state(v) for k, v in ST.items()}

# ---- render setup: Workbench, soft studio light, light grey background
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_percentage = 100; sc.render.film_transparent = False
sc.display.render_aa = '16'; sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'BW'; sc.render.image_settings.compression = 15
sc.render.dither_intensity = 0.0                     # all-grey scene: 8-bit grey PNG, no dither noise -> ~1/4 the disk
sh = sc.display.shading; sh.light = 'STUDIO'; sh.studio_light = 'Default'; sh.color_type = 'MATERIAL'
sh.show_specular_highlight = False; sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.cavity_ridge_factor = 0.6; sh.cavity_valley_factor = 0.8
sh.show_shadows = False; sh.show_object_outline = False; sh.show_backface_culling = False; sh.show_xray = False
if not sc.world: sc.world = bpy.data.worlds.new('w')
sc.world.color = (0.93 ** 2.2,) * 3
cam = bpy.data.cameras.new('wv_cam'); cam.type = 'ORTHO'; co = bpy.data.objects.new('wv_cam', cam); sc.collection.objects.link(co); sc.camera = co
ALLX = np.vstack([X for S in SS.values() for X in S.values()])

def view(d):
    """unit direction toward the camera -> (d, image right, image up, rotation)"""
    d = np.array(d, float); d /= np.linalg.norm(d); q = Vector(tuple(-d)).to_track_quat('-Z', 'Y'); R = np.array(q.to_matrix())
    return d, R[:, 0], R[:, 1], q
def frame(P, d, m=1.3, amin=0.6, amax=1.4, res=RES):
    """ortho frame on points P seen from d: plane centre, ortho scale (longer side), resolution, window W x H"""
    d, r, u, q = view(d); U, V = P @ r, P @ u; lo, hi = np.array([U.min(), V.min()]), np.array([U.max(), V.max()])
    W, H = (hi - lo) * m; A = float(np.clip(H / W, amin, amax))
    if A <= 1: rs = (res, int(round(res * A / 2)) * 2); size = max(W, H / A); win = (size, size * rs[1] / rs[0])
    else: rs = (int(round(res / A / 2)) * 2, res); size = max(H, W * A); win = (size * rs[0] / rs[1], size)
    return {'d': d, 'r': r, 'u': u, 'q': q, 'c': (lo + hi) / 2, 'size': float(size), 'res': rs, 'win': win}

TMP = []
def lines(X, E, VS, F, m, px=LINE_PX, push=3.0):
    """edges -> camera-facing quads px wide, `push` widths toward the camera; only edges touching the frame window.
    VS: per-vertex width scale, so the many spokes of a fan pole taper to hairlines there instead of merging into a blob"""
    d, r, u = F['d'], F['r'], F['u']; w = px * F['size'] / max(F['res'])
    P = np.stack([X[E[:, 0]], X[E[:, 1]]], 1); U, V = P @ r - F['c'][0], P @ u - F['c'][1]
    k = ((np.abs(U) < F['win'][0] / 2 + w) & (np.abs(V) < F['win'][1] / 2 + w)).any(1); P, Ek = P[k], E[k]
    t = P[:, 1] - P[:, 0]; t -= np.outer(t @ d, d); L = np.linalg.norm(t, axis=1); k = L > 0.05 * w     # edges along the view: a dot
    P, t = P[k], t[k] / L[k, None]; s = VS[Ek[k]] * (w / 2); a0, a1 = s[:, :1], s[:, 1:]; n = np.cross(d, t)
    Q = np.stack([P[:, 0] - (t + n) * a0, P[:, 1] + (t - n) * a1, P[:, 1] + (t + n) * a1, P[:, 0] - (t - n) * a0], 1) + d * push * w
    if not len(Q): return 0
    nq = len(Q); mm = bpy.data.meshes.new('wv_lines'); mm.vertices.add(nq * 4); mm.vertices.foreach_set('co', Q.reshape(-1).astype(np.float32))
    mm.loops.add(nq * 4); mm.loops.foreach_set('vertex_index', np.arange(nq * 4, dtype=np.int32))
    mm.polygons.add(nq); mm.polygons.foreach_set('loop_start', np.arange(0, nq * 4, 4, dtype=np.int32)); mm.update()
    mm.materials.append(m); ob = bpy.data.objects.new('wv_lines', mm); sc.collection.objects.link(ob); TMP.append(ob); return int(nq)

QA = {'shots': {}, 'greys_srgb': GREY, 'line_px': LINE_PX}
def shoot(name, F, S=None, wire=False, px=LINE_PX):
    """render state S (keys already set) from frame F; wire: face edges dark, organ edges lighter and thinner"""
    t0 = time.time(); sc.render.resolution_x, sc.render.resolution_y = F['res']
    dmax = float((ALLX @ F['d']).max()); co.location = Vector(tuple(F['r'] * F['c'][0] + F['u'] * F['c'][1] + F['d'] * (dmax + 0.3)))
    co.rotation_euler = F['q'].to_euler(); cam.ortho_scale = F['size']; cam.clip_start = 0.05; cam.clip_end = float(np.ptp(ALLX @ F['d'])) + 0.8
    ne = {}
    if wire:
        for n in OBJ: ne[n] = lines(S[n], EDGES[n], VS[n], F, MS['line' if n == 'face' else 'line_organ'], px if n == 'face' else 0.9 * px)
    f = os.path.join(OUT, name); sc.render.filepath = f; bpy.ops.render.render(write_still=True)
    for ob in TMP: mm = ob.data; bpy.data.objects.remove(ob); bpy.data.meshes.remove(mm)
    TMP.clear(); im = bpy.data.images.load(f); pix = np.empty(len(im.pixels), np.float32); im.pixels.foreach_get(pix); bpy.data.images.remove(im)
    lum = pix.reshape(-1, 4)[:, :3].mean(1)
    QA['shots'][name] = {'res': list(F['res']), 'size_mm': round(1000 * F['size'], 1), 'edges_drawn': ne,
                         'dark_px_share': round(float((lum < 0.25).mean()), 4), 'sec': round(time.time() - t0, 2)}

# ---- whole face: brow (2, 5) to chin (24), down to a quarter face height below the chin
top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]
X0 = SS['rest']['face']; HEAD = X0[X0[:, 2] > LT[24][2] - 0.25 * fh]
setkeys(ST['rest'])
for v, d in (('front', (0, -1, 0)), ('34', (0.7, -0.7, 0))):
    F = frame(HEAD, d, 1.08, 0.8, 1.35, RES_FULL); shoot('grey_%s.png' % v, F); shoot('grey_%s_wire.png' % v, F, SS['rest'], True, LINE_FULL)

# ---- left eye: outer eye ring (rest + blink) with a margin
sgn = 1.0 if not JE else float(np.sign(JE['eyes']['L']['C'][0]) or 1.0)
if ering is not None and (ering * sgn == 1).any(): EP = np.vstack([SS[k]['face'][ering * sgn == 1] for k in ('rest', 'blink')]); em = 1.5
elif JE: C, rr = np.array(JE['eyes']['L']['C']), float(JE['eyes']['L']['r']); EP = C + np.array([[-2, 0, -1.2], [2, 0, 1.2]]) * rr; em = 1.2
else: Ey = SS['rest']['eyes']; EP = Ey[Ey[:, 0] * sgn > 0]; em = 2.2
for v, d in (('front', (0, -1, 0)), ('34', (0.7, -0.7, 0))):
    F = frame(EP, d, em)
    for k in ('rest', 'blink'):
        setkeys(ST[k]); shoot('wire_eye_%s_%s.png' % (v, k), F, SS[k], True)

# ---- mouth: outer mouth ring (rest + jawOpen) with a margin
if mring is not None and (mring == 1).any(): MP = np.vstack([SS[k]['face'][mring == 1] for k in ('rest', 'open')]); mm_ = 1.25
else: MP = np.vstack([SS[k][n] for k in ('rest', 'open') for n in ('teeth_up', 'teeth_lo', 'tongue') if n in SS[k]]); mm_ = 1.8
for v, d in (('front', (0, -1, 0)), ('34', (0.7, -0.7, 0))):
    F = frame(MP, d, mm_)
    for k in ('rest', 'open'):
        setkeys(ST[k]); shoot('wire_mouth_%s_%s.png' % (v, k), F, SS[k], True)
setkeys({})

# ---- QA: the posed keys really move things (face max move, and only near the left eye for the blink)
mv = lambda s, n: round(1000 * float(np.linalg.norm(SS[s][n] - SS['rest'][n], axis=1).max()), 2) if n in SS[s] else None
dB = np.linalg.norm(SS['blink']['face'] - X0, axis=1)
QA['pose'] = {'eyeBlinkLeft': {'face_max_mm': mv('blink', 'face'), 'right_side_max_mm': round(1000 * float(dB[X0[:, 0] * sgn < -0.005].max()), 3),
                               'eyes_max_mm': mv('blink', 'eyes')},
              'jawOpen': {n + '_max_mm': mv('open', n) for n in OBJ}}
QA['rings'] = {'eye_rings_left': int((ering * sgn).max()) if ering is not None else None, 'mouth_rings': int(mring.max()) if mring is not None else None}
# sharp folds in the rest head mesh (two face normals > 100 deg apart across an edge): seam pockets show up here, split by
# what they are near (the outer eye / mouth ring, inside an organ, elsewhere on the original head)
nP = len(me.polygons); PN = np.empty(nP * 3); me.polygons.foreach_get('normal', PN); PN = PN.reshape(-1, 3)
ls_ = np.empty(nP, np.int32); me.polygons.foreach_get('loop_start', ls_); lt_ = np.empty(nP, np.int32); me.polygons.foreach_get('loop_total', lt_)
lp = np.empty(len(me.loops), np.int64); lp[(ls_[:, None] + np.arange(lt_.max())[None])[np.arange(lt_.max())[None] < lt_[:, None]]] = np.repeat(np.arange(nP), lt_)
le = np.empty(len(me.loops), np.int32); me.loops.foreach_get('edge_index', le); o_ = np.argsort(le, kind='stable'); les, lps = le[o_], lp[o_]
st = np.where(np.r_[True, les[1:] != les[:-1]])[0]; cnt = np.diff(np.r_[st, len(les)]); st = st[cnt == 2]
fe = les[st][(PN[lps[st]] * PN[lps[st + 1]]).sum(1) < -0.17]; fe = fe[X0[EDGES['face'][fe]][:, :, 2].min(1) > LT[24][2] - 0.25 * fh]   # head, not the torso
FM = X0[EDGES['face'][fe]].mean(1)
def near(ids, P, r=0.004):
    return np.zeros(len(P), bool) if not len(ids) or not len(P) else np.linalg.norm(P[:, None] - X0[ids][None], axis=2).min(1) < r
e1 = np.where(np.abs(ering) == 1)[0] if ering is not None else np.array([], int); m1 = np.where(mring == 1)[0] if mring is not None else np.array([], int)
org = np.zeros(N, bool)
if ering is not None: org |= ering != 0
if mring is not None: org |= mring > 0
inO = org[EDGES['face'][fe]].all(1); nE, nM = near(e1, FM) & ~inO, near(m1, FM) & ~inO
# mirror check: sym_lock mirrors positions exactly, but the triangulation can still differ L/R; an edge whose mirror
# image is not an edge tells a topology cause (re-triangulate) apart from a position cause
from mathutils.kdtree import KDTree
kd = KDTree(N)
for i, p in enumerate(X0): kd.insert(p, i)
kd.balance(); MI = [kd.find((-p[0], p[1], p[2])) for p in X0]
pm = np.array([h[1] for h in MI]); pe = np.array([h[2] for h in MI]); EF = np.sort(EDGES['face'], 1)
noM = ~np.isin(np.sort(pm[EF], 1) @ np.array([N, 1], np.int64), EF @ np.array([N, 1], np.int64))
eL = FM[:, 0] * sgn > 0; nmF = noM[fe]
QA['mirror'] = {'verts_off_mirror_gt_0.01mm': int((pe > 1e-5).sum()), 'max_off_mirror_mm': round(1000 * float(pe.max()), 4),
                'edges_without_mirror_edge': int(noM.sum())}
QA['folds'] = {'head_edges_gt_100deg': int(len(fe)), 'inside_organs': int(inO.sum()) if org.any() else None,
               'near_outer_eye_ring_4mm': int(nE.sum()) if ering is not None else None,
               'near_outer_eye_ring_4mm_L': int((nE & eL).sum()) if ering is not None else None,
               'near_outer_eye_ring_4mm_R': int((nE & ~eL).sum()) if ering is not None else None,
               'near_outer_eye_ring_4mm_no_mirror_edge': int((nE & nmF).sum()) if ering is not None else None,
               'near_outer_mouth_ring_4mm': int(nM.sum()) if mring is not None else None, 'elsewhere': int((~inO & ~nE & ~nM).sum()),
               'near_ring_at_mm': [[round(1000 * float(x), 1) for x in p] for p in FM[nE | nM][:40]]}
# eyeball through the skin: points sampled over the eyeball surface (10 per triangle; the eyeball mesh is coarse, so its
# vertices alone miss a poke between them) that lie on the outer side of the original head surface (nearest face
# triangle has no organ-ring vertex) and whose outward ray (from the eyeball centre) leaves the head unhit.
# Without eye_ring the lid opening cannot be told from original skin, so every visible eyeball would count: skip.
if 'eyes' in OBJ and (ering is None or not (ering != 0).any()): QA['eyeball_through_skin'] = 'n/a (no eye_ring attribute)'
elif 'eyes' in OBJ:
    me.calc_loop_triangles(); TR = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', TR); TR = TR.reshape(-1, 3)
    bvh = BVHTree.FromPolygons(X0.tolist(), TR.tolist()); pc = Vector(tuple(LT[24] + np.array([0, -0.03, 0]))); q = bvh.find_nearest(pc)
    wind = 1.0 if (pc - q[0]).dot(q[1]) > 0 else -1.0              # a point in front of the chin must read as outside
    em_ = OBJ['eyes'].data; em_.calc_loop_triangles(); TE = np.empty(len(em_.loop_triangles) * 3, np.int32); em_.loop_triangles.foreach_get('vertices', TE)
    Ye = SS['rest']['eyes']; TE = TE.reshape(-1, 3); BCs = np.array([((i + 1 / 3) / 4, (j + 1 / 3) / 4) for i in range(4) for j in range(4 - i)])
    A_, B_, C_ = Ye[TE[:, 0]], Ye[TE[:, 1]], Ye[TE[:, 2]]; ar = np.linalg.norm(np.cross(B_ - A_, C_ - A_), axis=1) / 2 / len(BCs)
    SP = (A_[:, None] + BCs[None, :, :1] * (B_ - A_)[:, None] + BCs[None, :, 1:] * (C_ - A_)[:, None]).reshape(-1, 3); SA = np.repeat(ar, len(BCs))
    out = {}
    for sd, sg_ in (('L', sgn), ('R', -sgn)):
        k = SP[:, 0] * sg_ > 0; P_, A2 = SP[k], SA[k]; Ce = Ye[Ye[:, 0] * sg_ > 0].mean(0); dd, aa = [], []
        for p_, a_ in zip(P_, A2):
            h = bvh.find_nearest(Vector(tuple(p_)), 0.01)
            if h[0] is None or org[TR[h[2]]].any(): continue
            dv = wind * (Vector(tuple(p_)) - h[0]).dot(h[1]); nv = Vector(tuple(p_ - Ce)).normalized()
            if dv > 1e-4 and bvh.ray_cast(Vector(tuple(p_)) + nv * 1e-5, nv, 0.2)[0] is None: dd.append(dv); aa.append(a_)
        out[sd] = {'samples': int(k.sum()), 'outside_skin_gt_0.1mm': len(dd), 'area_mm2': round(1e6 * float(sum(aa)), 2),
                   'max_out_mm': round(1000 * float(max(dd)), 2) if dd else 0.0}
    QA['eyeball_through_skin'] = out
QA['total_sec'] = round(time.time() - T0, 1)
json.dump(QA, open(os.path.join(OUT, 'wire_qa.json'), 'w'), indent=1)
print('WIRE_QA', json.dumps({'pose': QA['pose'], 'rings': QA['rings'], 'folds': {k: v for k, v in QA['folds'].items() if k != 'near_ring_at_mm'},
                             'mirror': QA['mirror'], 'eyeball': QA.get('eyeball_through_skin'), 'total_sec': QA['total_sec']}))
print('WIRE_SHOTS', json.dumps({k: (v['edges_drawn'].get('face'), v['dark_px_share'], v['sec']) for k, v in QA['shots'].items()}))
