"""겹침생성 · cut-away views of the mouth and eye interiors (lip roll, oral cavity, teeth, tongue, lids on the eyeball).

A baked head (arkit_b.blend: face with ARKit shape keys, teeth_up / teeth_lo / tongue, eyes) is cut by a plane and
rendered with Workbench from the cut side. The camera's clip_start removes everything in front of the plane, so the
hollow surfaces behind it are seen from inside (pale colours), and the section itself is drawn as flat ribbons along
the plane/mesh intersection, one strong colour per part (skin, lip roll, cavity, upper / lower teeth, tongue, eyeball).
Every part is drawn in both windings with backface culling on, so the face's outer side (pale grey, e.g. the nose
beyond the eye cut) reads apart from the inside of the hollow head (beige). Expression views also carry the rest
section as a thin grey ghost line drawn under the current lines, so grey shows only where something moved.
Views: midline (x = 0) mouth close-ups at rest / mouthFunnel (shared frame on lips + teeth + tongue) and jawOpen (own
frame, with the dropped chin); a front X-ray of the open mouth (teeth and tongue over the opaque head, the parts hidden
behind skin faded and hatched); a cut through the left eyeball centre at rest / eyeBlinkLeft, plus tight lid insets
(about 1.2 r) for the lid-eyeball contact. The far eyeball is left out of the eye views: the hollow head has no wall
between the eyes, so it would show through as a halo. A shape key is set on every object that has it.
section_qa.json: lip and teeth gaps at the centre, teeth/tongue vertices outside the skin envelope (skin up to the lip
slit + a fan over the slit; ray parity, 3 directions) or inside the flesh (nearest face seen from its back, > 0.2 mm;
'n/a' while the cavity is a flat sheet < 1 mm high), cavity height/depth from the rings behind the slit, and upper-lid
distances to the eyeball: signed against the eyeball mesh (negative = inside) and against the ideal sphere.
Usage: blender -b <arkit_b.blend> -P rig_viz_section.py -- <out_dir> <landmarks.json> [<eyes.json>]   (env SV_LIGHT=STUDIO: shaded surfaces)
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0]); os.makedirs(OUT, exist_ok=True)
LT = {int(k): np.array(v) for k, v in json.load(open(a[1])).items() if not k.startswith('_')}
JE = json.load(open(a[2])) if len(a) > 2 and os.path.exists(a[2]) else None
EJ = JE['eyes'] if JE else None
sc = bpy.context.scene; RES = 800
PARTS = ('face', 'teeth_up', 'teeth_lo', 'tongue', 'eyes')
for o in bpy.data.objects: o.hide_render = o.name not in PARTS
face = bpy.data.objects['face']; me = face.data
attr = lambda n: np.array([d.value for d in me.attributes[n].data])
mring, mu, ering, eu = attr('mouth_ring'), attr('mouth_u'), attr('eye_ring'), attr('eye_u')
K = int(JE['rings']) if JE and 'rings' in JE else int(np.abs(ering).max()) - 2      # lid margin ring (organ_eye)
# colours (sRGB): pale surface seen beyond the cut, strong section line
COL = {'skin': ((0.93, 0.82, 0.73), (0.50, 0.28, 0.16)), 'roll': ((0.96, 0.66, 0.66), (0.85, 0.15, 0.25)),
       'cavity': ((0.74, 0.42, 0.52), (0.45, 0.02, 0.22)), 'teeth': ((0.98, 0.97, 0.90), (0.05, 0.50, 0.62)),
       'tongue': ((0.99, 0.70, 0.42), (0.85, 0.35, 0.00)), 'eye': ((0.80, 0.89, 1.00), (0.12, 0.30, 0.90)),
       'ghost': ((0.5, 0.5, 0.5), (0.42, 0.42, 0.45)), 'outer': ((0.86, 0.86, 0.87), (0.50, 0.28, 0.16)),
       'teeth_lo': ((0.94, 0.94, 0.85), (0.10, 0.55, 0.25))}             # lower teeth apart: incisors overlap at rest
def mat(name, c):
    m = bpy.data.materials.new(name); m.diffuse_color = (*[x ** 2.2 for x in c], 1.0); return m
MS = {k: mat('sv_' + k, v[0]) for k, v in COL.items()}; ML = {k: mat('sv_line_' + k, v[1]) for k, v in COL.items()}
# face slots: skin, cavity (mouth_inner*), and a new slot for the inner lip roll (rings behind the slit, skin material)
cav = next((i for i, m in enumerate(me.materials) if m and m.name.startswith('mouth_inner')), -1)
ls = np.array([p.loop_start for p in me.polygons]); lt = np.array([p.loop_total for p in me.polygons]); od = np.argsort(ls)
lv = np.empty(len(me.loops), int); me.loops.foreach_get('vertex_index', lv)
mi = np.empty(len(me.polygons), int); me.polygons.foreach_get('material_index', mi)
pmax = np.empty(len(ls), int); pmax[od] = np.maximum.reduceat(mring[lv], ls[od])
sk = np.zeros(len(mring), bool); sk[lv[np.repeat(mi[od], lt[od]) != cav]] = True       # vertex touches a skin-material face
for i in range(len(me.materials)): me.materials[i] = MS['cavity'] if i == cav else MS['skin']
me.materials.append(MS['roll']); ROLL = len(me.materials) - 1
X0 = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', X0); X0 = X0.reshape(-1, 3)
# slit = the ring whose upper (u 0.25) and lower (u 0.75) centre vertices touch at rest; only rings on skin-material
# faces count, so a cavity ring (e.g. the cap) that happens to be closed can never win
def centre(ids, t): return ids[np.argmin(np.abs(mu[ids] - t))]
real = [k for k in range(1, mring.max() + 1) if len(np.unique(np.round(mu[mring == k], 4))) >= 8]   # interior may share u
cand = [k for k in real if sk[mring == k].all()] or real
gapr = {k: np.linalg.norm(X0[centre(np.where(mring == k)[0], 0.25)] - X0[centre(np.where(mring == k)[0], 0.75)]) for k in cand}
SLIT = min(gapr, key=gapr.get)
mi[(mi != cav) & (pmax > SLIT)] = ROLL; me.polygons.foreach_set('material_index', mi); me.update()
SLOT = {i: ('cavity' if i == cav else 'roll' if i == ROLL else 'skin') for i in range(len(me.materials))}
for n, k in (('teeth_up', 'teeth'), ('teeth_lo', 'teeth_lo'), ('tongue', 'tongue'), ('eyes', 'eye')):
    o = bpy.data.objects.get(n)
    if not o: continue
    o.data.materials.clear(); o.data.materials.append(MS[k])
    for p in o.data.polygons: p.material_index = 0

def setkeys(keys):
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]: kb.value = keys.get(kb.name, 0.0)
    bpy.context.view_layer.update()
def state(keys):
    """set shape keys on every object, return evaluated world verts / triangles / per-triangle part"""
    setkeys(keys); dg = bpy.context.evaluated_depsgraph_get(); S = {'keys': keys}
    for n in PARTS:
        o = bpy.data.objects.get(n)
        if not o: continue
        oe = o.evaluated_get(dg); m = oe.to_mesh(); m.calc_loop_triangles()
        X = np.empty(len(m.vertices) * 3); m.vertices.foreach_get('co', X); X = X.reshape(-1, 3)
        Mw = np.array(o.matrix_world); X = X @ Mw[:3, :3].T + Mw[:3, 3]
        T = np.empty(len(m.loop_triangles) * 3, int); m.loop_triangles.foreach_get('vertices', T); T = T.reshape(-1, 3)
        tm = np.empty(len(m.loop_triangles), int); m.loop_triangles.foreach_get('material_index', tm)
        part = np.array([SLOT[i] for i in tm]) if n == 'face' else np.full(len(T), {'teeth_up': 'teeth', 'eyes': 'eye'}.get(n, n))
        S[n] = (X, T, part); oe.to_mesh_clear()
    return S

def cut(X, T, ax, c):
    """plane ax = c through triangles -> segments (n, 2, 3); zero-distance vertices count as below"""
    d = X[T][:, :, ax] - c; s = d > 0; m = s.any(1) & ~s.all(1)
    D, V = d[m], X[T[m]]; E = ((0, 1), (1, 2), (2, 0))
    cr = np.stack([s[m][:, i] != s[m][:, j] for i, j in E], 1)
    with np.errstate(divide='ignore', invalid='ignore'):
        P = np.stack([V[:, i] + (V[:, j] - V[:, i]) * (D[:, i] / (D[:, i] - D[:, j]))[:, None] for i, j in E], 1)
    o = np.argsort(~cr, 1, kind='stable')[:, :2]
    return P[np.arange(len(P))[:, None], o]

TMP = []
def temp_obj(V, F, m):
    mm = bpy.data.meshes.new('sv_tmp'); mm.from_pydata(V.tolist(), [], F.tolist()); mm.materials.append(m); mm.shade_smooth()
    ob = bpy.data.objects.new('sv_tmp', mm); sc.collection.objects.link(ob); TMP.append(ob)
WIND = 1.0                                                        # -1 if the face triangles wind inward (set from the rest state)
def solids(S, eye_side):
    """the parts as temp meshes in both windings; with backface culling the face's outer side and its inner side (the
    hollow seen through the cut) get different colours, the other parts look the same from both sides"""
    for n, (X, T, part) in ((n, v) for n, v in S.items() if n != 'keys'):
        if n == 'eyes' and eye_side: k = (X[T][:, :, 0] * eye_side > 0).all(1); T, part = T[k], part[k]
        for p in set(part.tolist()):
            u, inv = np.unique(T[part == p], return_inverse=True); F = inv.reshape(-1, 3)
            if n == 'face' and WIND < 0: F = F[:, ::-1]
            temp_obj(X[u], F, MS['outer' if (n, p) == ('face', 'skin') else p]); temp_obj(X[u], F[:, ::-1], MS[p])
def ribbon(segs, ax, c, side, w, off, m):
    """flat quads along the section, facing the camera, `off` in front of the plane (larger = nearer = on top)"""
    if not len(segs): return
    P0, P1 = segs[:, 0], segs[:, 1]; dv = P1 - P0; L = np.linalg.norm(dv, axis=1); k = L > 1e-9
    P0, P1, dv = P0[k], P1[k], dv[k] / L[k, None]; n = np.zeros(3); n[ax] = 1.0
    pv = np.cross(dv, n) * w / 2; ex = dv * w / 2             # ends overlap so neighbouring segments join
    Q = np.stack([P0 - ex - pv, P1 + ex - pv, P1 + ex + pv, P0 - ex + pv], 1); Q[..., ax] = c + side * off
    F = np.arange(len(Q) * 4).reshape(-1, 4); temp_obj(Q.reshape(-1, 3), np.vstack([F, F[:, ::-1]]), m)   # both windings: culling on

ORDER = ('eye', 'cavity', 'roll', 'skin', 'tongue', 'teeth_lo', 'teeth')      # later = nearer the camera = on top (lids over eyeball)
def sections(S, ax, c):
    out = {}
    for n, (X, T, part) in ((n, v) for n, v in S.items() if n != 'keys'):
        for p in set(part.tolist()): out.setdefault(p, []).append(cut(X, T[part == p], ax, c))
    return {p: np.concatenate(v) for p, v in out.items()}

sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_percentage = 100
sh = sc.display.shading; sh.light = os.environ.get('SV_LIGHT', 'FLAT'); sh.color_type = 'MATERIAL'; sh.show_backface_culling = False
sh.show_specular_highlight = False; sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.show_shadows = False; sh.show_object_outline = False
sc.display.render_aa = '16'; sc.view_settings.view_transform = 'Standard'; sc.render.film_transparent = False
if not sc.world: sc.world = bpy.data.worlds.new('w')
sc.world.color = (0.94 ** 2.2,) * 3
cam = bpy.data.cameras.new('sv'); cam.type = 'ORTHO'; co = bpy.data.objects.new('sv', cam); sc.collection.objects.link(co); sc.camera = co
DIST, CLIP = 0.5, 0.0003
GHOST_OFF, LINE_OFF = 0.00012, 0.00015                            # ghost under every current line; both behind the clip

def frame(P, m=1.18, amin=0.5, amax=1.3):
    """side-view frame on points P (image right = +y, up = +z): centre, ortho scale (longer side), resolution"""
    lo, hi = P.min(0), P.max(0); W, H = (hi[1] - lo[1]) * m, (hi[2] - lo[2]) * m; A = float(np.clip(H / W, amin, amax))
    res = (RES, int(round(RES * A / 2)) * 2) if A <= 1 else (int(round(RES / A / 2)) * 2, RES)
    return (lo + hi) / 2, max(W, H / A) if A <= 1 else max(H, W * A), res

def shoot(name, S, ax, c, side, ctr, size, ghost=None, res=(RES, RES), eye_side=0):
    """camera on the `side` of plane ax = c looking across it; clip_start drops everything in front of the plane.
    The parts are drawn from the state's own meshes; eye_side != 0 keeps only the eyeball on that side of x = 0
    (the other would show through the hollow head)"""
    sc.render.resolution_x, sc.render.resolution_y = res
    d = np.zeros(3); d[ax] = side; loc = np.array(ctr, float); loc[ax] = c + side * DIST
    co.location = Vector(loc); co.rotation_euler = Vector(tuple(-d)).to_track_quat('-Z', 'Y').to_euler()
    cam.ortho_scale = size; cam.clip_start = DIST - CLIP; cam.clip_end = DIST + 0.6
    w = size * 0.0055; orig = [bpy.data.objects[n] for n in PARTS if n in bpy.data.objects]
    if ghost:
        for p, g in ghost.items(): ribbon(g, ax, c, side, w * 0.45, GHOST_OFF, ML['ghost'])
    sec = sections(S, ax, c)
    for k, p in enumerate(ORDER):
        if p in sec: ribbon(sec[p], ax, c, side, w, LINE_OFF + 0.00001 * k, ML[p])
    solids(S, eye_side)
    for o in orig: o.hide_render = True
    sh.show_backface_culling = True; sc.render.filepath = os.path.join(OUT, name); bpy.ops.render.render(write_still=True)
    sh.show_backface_culling = False
    for o in orig: o.hide_render = False
    for ob in TMP: mm = ob.data; bpy.data.objects.remove(ob); bpy.data.meshes.remove(mm)
    TMP.clear(); return sec

def xray(name, S, ctr, size):
    """front view without a cut. Pass 0: the whole head; pass 1: the inner parts alone; pass 2: object colours (head
    black, inner white) = which inner pixels are seen directly. Hidden inner pixels are laid over faded and hatched."""
    sc.render.resolution_x = sc.render.resolution_y = RES
    loc = np.array(ctr, float); loc[1] -= DIST; co.location = Vector(loc); co.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
    cam.ortho_scale = size; cam.clip_start = 0.01; cam.clip_end = DIST + 0.6; setkeys(S['keys']); P = []
    head = [bpy.data.objects[n] for n in ('face', 'eyes') if n in bpy.data.objects]
    inner = [bpy.data.objects[n] for n in ('teeth_up', 'teeth_lo', 'tongue') if n in bpy.data.objects]
    for o in head: o.color = (0, 0, 0, 1)
    for o in inner: o.color = (1, 1, 1, 1)
    for i in range(3):
        for o in head: o.hide_render = i == 1
        sc.render.film_transparent = i == 1
        sh.color_type, sh.light, sh.show_cavity = ('OBJECT', 'FLAT', False) if i == 2 else ('MATERIAL', os.environ.get('SV_LIGHT', 'FLAT'), True)
        f = os.path.join(OUT, '_xr%d.png' % i); sc.render.filepath = f; bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(f); px = np.empty(len(im.pixels), np.float32); im.pixels.foreach_get(px)
        P.append(px.reshape(RES, RES, 4)); bpy.data.images.remove(im); os.remove(f)
    for o in head: o.hide_render = False
    sc.render.film_transparent = False; sh.color_type, sh.light, sh.show_cavity = 'MATERIAL', os.environ.get('SV_LIGHT', 'FLAT'), True
    A, B, V = P; mB = B[..., 3] > 0.5; vis = mB & (V[..., :3].mean(-1) > 0.5); hid = mB & ~vis
    yy, xx = np.mgrid[:RES, :RES]; hatch = (xx + yy) % 10 < 3                # diagonal hatch = behind skin
    O = A.copy(); O[hid, :3] = A[hid, :3] * 0.5 + B[hid, :3] * 0.5
    h2 = hid & hatch; O[h2, :3] = A[h2, :3] * 0.45 + B[h2, :3] * 0.55 * 0.55
    e = np.zeros_like(mB)                                                    # own outline: workbench's is too faint here
    for dy, dx in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)): e |= mB & ~np.roll(np.roll(mB, dy, 0), dx, 1)
    O[e & vis, :3] = B[e & vis, :3] * 0.45; O[e & hid, :3] = A[e & hid, :3] * 0.4 + B[e & hid, :3] * 0.45 * 0.6
    im = bpy.data.images.new('sv_xr', RES, RES); im.pixels.foreach_set(O.ravel())
    im.filepath_raw = os.path.join(OUT, name); im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
    return {'inner_px': int(mB.sum()), 'hidden_px': int(hid.sum())}

# ---- QA helpers
def env_bvh(S):
    """skin envelope: face triangles up to the slit ring + a fan closing the slit (the open mouth when the jaw drops)"""
    X, T, part = S['face']; keep = (mring[T].max(1) <= SLIT) & (part == 'skin')
    loop = np.where(mring == SLIT)[0]; loop = loop[np.argsort(mu[loop])]; ci = len(X)
    fan = np.stack([loop, np.roll(loop, -1), np.full(len(loop), ci)], 1)
    V = np.vstack([X, X[loop].mean(0)]); F = np.vstack([T[keep], fan])
    return BVHTree.FromPolygons([tuple(v) for v in V], F.tolist())
DIRS = [Vector(v).normalized() for v in ((0.013, 1, 0.021), (1, 0.017, 0.011), (-1, 0.019, -0.013))]
def inside(bvh, p):
    votes = 0
    for dv in DIRS:
        o, n = Vector(tuple(p)), 0
        for _ in range(64):
            h = bvh.ray_cast(o, dv, 2.0)
            if h[0] is None: break
            n += 1; o = h[0] + dv * 2e-5
        votes += n % 2
    return votes >= 2

def mouth_qa(S):
    X = S['face'][0]; sl = np.where(mring == SLIT)[0]; up, lo = centre(sl, 0.25), centre(sl, 0.75)
    r = {'lip_gap_mm': round(1000 * float(np.linalg.norm(X[up] - X[lo])), 2), 'lip_gap_z_mm': round(1000 * float(X[up, 2] - X[lo, 2]), 2)}
    if 'teeth_up' in S and 'teeth_lo' in S:
        def mid(Y):
            k = np.abs(Y[:, 0]) < 0.003
            return Y[k] if k.sum() >= 2 else Y[np.argsort(np.abs(Y[:, 0]))[:4]]
        r['teeth_gap_mm'] = round(1000 * float(mid(S['teeth_up'][0])[:, 2].min() - mid(S['teeth_lo'][0])[:, 2].max()), 2)
    # cavity from the rings behind the slit only (the slit itself would just repeat the lip gap)
    Xf, Tf, pf = S['face']; cm = np.where((mring > SLIT) & (np.abs(Xf[:, 0]) < 0.003))[0]; ch = None
    if len(cm): ch = 1000 * float(np.ptp(Xf[cm, 2])); r['cavity_mid_height_mm'] = round(ch, 2); r['cavity_mid_depth_mm'] = round(1000 * float(np.ptp(Xf[cm, 1])), 2)
    flat = ch is None or ch < 1.0                                    # flat sheet: which side of it is a coin flip
    env = env_bvh(S); allb = BVHTree.FromPolygons([tuple(v) for v in Xf], Tf.tolist())
    mc = Xf[np.where(mring == SLIT)[0]].mean(0)       # sanity: in front of the chin = out, 1 cm behind the slit = in
    r['envelope_check'] = bool(not inside(env, LT[24] + np.array([0, -0.03, 0])) and inside(env, mc + np.array([0, 0.01, 0])))
    # face winding: a point in front of the chin must read as outside (positive), else flip the sign
    q = allb.find_nearest(Vector(tuple(LT[24] + np.array([0, -0.03, 0])))); sg = 1.0 if (Vector(tuple(LT[24] + np.array([0, -0.03, 0]))) - q[0]).dot(q[1]) > 0 else -1.0
    for n in ('teeth_up', 'teeth_lo', 'tongue'):
        if n not in S: continue
        Y = S[n][0]; outv = sum(not inside(env, p) for p in Y); fl = 0
        for p in Y:
            q = allb.find_nearest(Vector(tuple(p)))
            if q[0] is not None and sg * (Vector(tuple(p)) - q[0]).dot(q[1]) < -0.0002: fl += 1
        r[n] = {'verts': len(Y), 'outside_skin': int(outv), 'in_flesh': 'n/a (flat sheet)' if flat else int(fl)}
    return r

def eye_qa(S, C, rad):
    """upper-lid rings of the left eye vs the eyeball: signed distance to the eyeball mesh (nearest face normal,
    negative = inside the rendered eyeball) and to the ideal sphere from eyes.json"""
    X = S['face'][0]; upl = np.where((ering > 0) & (eu > 1e-4) & (eu < 0.5 - 1e-4))[0]
    ds = np.linalg.norm(X[upl] - C, axis=1) - rad; rr = ering[upl]; mm_ = lambda v: round(1000 * float(v.min()), 3)
    r = {'margin_ring': K, 'upper_min_sphere_mm': mm_(ds), 'inside_sphere': int((ds < 0).sum()),
         'edge_min_sphere_mm': mm_(ds[rr >= K]), 'margin_ring_min_sphere_mm': mm_(ds[rr == K]) if (rr == K).any() else None}
    if 'eyes' in S:
        Xe, Te, _ = S['eyes']; Te = Te[(Xe[Te][:, :, 0] * np.sign(C[0]) > 0).all(1)]
        eb = BVHTree.FromPolygons([tuple(v) for v in Xe], Te.tolist()); vc = Vector(tuple(C))
        q = eb.find_nearest(vc); fo = -1.0 if (vc - q[0]).dot(q[1]) > 0 else 1.0     # normals point outward: the centre is behind them
        dm = np.empty(len(upl))
        for i, p in enumerate(X[upl]):
            h = eb.find_nearest(Vector(tuple(p))); dm[i] = fo * np.sign((Vector(tuple(p)) - h[0]).dot(h[1])) * h[3]
        r.update({'upper_min_mesh_signed_mm': mm_(dm), 'inside_mesh': int((dm < -1e-6).sum()), 'inside_mesh_gt_0.05mm': int((dm < -5e-5).sum()),
                  'inside_mesh_rings': sorted({int(k) for k in rr[dm < -1e-6]}), 'margin_ring_min_mesh_mm': mm_(dm[rr == K]) if (rr == K).any() else None,
                  'per_ring_min_mesh_mm': {int(k): mm_(dm[rr == k]) for k in np.unique(rr)}})
    r['per_ring_min_sphere_mm'] = {int(k): mm_(ds[rr == k]) for k in np.unique(rr)}
    return r

# ---- mouth: midline section
ST = {'rest': {}, 'jawOpen': {'jawOpen': 1.0}, 'funnel': {'mouthFunnel': 1.0}}
SS = {k: state(v) for k, v in ST.items()}
Xr, Tr, pr = SS['rest']['face']; pc = LT[24] + np.array([0, -0.03, 0]); q = BVHTree.FromPolygons([tuple(v) for v in Xr], Tr.tolist()).find_nearest(Vector(tuple(pc)))
WIND = 1.0 if (Vector(tuple(pc)) - q[0]).dot(q[1]) > 0 else -1.0   # a point in front of the chin sees the outer side
def mouth_pts(S, r0=1):
    X = S['face'][0]; return [X[(mring >= r0) & (np.abs(X[:, 0]) < 0.003)]] + [S[n][0] for n in ('teeth_up', 'teeth_lo', 'tongue') if n in S]
chin = np.argmin(np.linalg.norm(SS['rest']['face'][0] - LT[24], axis=1))       # chin vertex, followed into jawOpen
FR = {'closed': frame(np.vstack(mouth_pts(SS['rest'], SLIT // 2) + mouth_pts(SS['funnel'], SLIT // 2))),   # lips + teeth + tongue
      'jawOpen': frame(np.vstack(mouth_pts(SS['jawOpen']) + [SS['jawOpen']['face'][0][chin][None]]))}
QA = {'slit_ring': int(SLIT), 'margin_ring': K, 'colors_srgb': {k: {'surface': v[0], 'section': v[1]} for k, v in COL.items()}, 'mouth': {}, 'eye': {},
      'frames': {k: {'centre': [round(float(x), 4) for x in v[0]], 'size_mm': round(1000 * v[1], 1), 'res': list(v[2])} for k, v in FR.items()}}
c_, s_, r_ = FR['closed']; rest_sec = shoot('sec_mouth_rest.png', SS['rest'], 0, 0.0, 1, c_, s_, res=r_)
shoot('sec_mouth_funnel.png', SS['funnel'], 0, 0.0, 1, c_, s_, ghost=rest_sec, res=r_)
c_, s_, r_ = FR['jawOpen']; shoot('sec_mouth_jawOpen.png', SS['jawOpen'], 0, 0.0, 1, c_, s_, ghost=rest_sec, res=r_)
for k, S in SS.items(): QA['mouth'][k] = mouth_qa(S)
# ---- mouth: front X-ray, jaw open
S = SS['jawOpen']; Y = np.vstack([S[n][0] for n in ('teeth_up', 'teeth_lo', 'tongue') if n in S])
Q = np.vstack([S['face'][0][mring == SLIT], Y]); qlo, qhi = Q.min(0), Q.max(0)
QA['front_xray'] = xray('sec_mouth_front_open.png', S, (qlo + qhi) / 2, 1.35 * max(qhi[0] - qlo[0], qhi[2] - qlo[2]))
# ---- left eye: section through the eyeball centre
if EJ: C, rad = np.array(EJ['L']['C']), float(EJ['L']['r'])
else:
    E = SS['rest']['eyes'][0]; E = E[E[:, 0] > 0]; C = E.mean(0); rad = float(np.linalg.norm(E - C, axis=1).mean())
SE = {'rest': SS['rest'], 'blink': state({'eyeBlinkLeft': 1.0})}
sgn = 1 if C[0] > 0 else -1
ec = C + np.array([0, -0.35 * rad, 0.05 * rad])                     # lids sit in front of the eyeball
er_sec = shoot('sec_eye_rest.png', SE['rest'], 0, float(C[0]), 1, ec, 3.0 * rad, eye_side=sgn)
shoot('sec_eye_blink.png', SE['blink'], 0, float(C[0]), 1, ec, 3.0 * rad, ghost=er_sec, eye_side=sgn)
# lid inset: margin + tuck rings near the cut, rest and closed, framed at about 1.2 r so 0.3 mm gaps are ~10 px
lid = np.vstack([s['face'][0][(ering * sgn >= K) & (np.abs(s['face'][0][:, 0] - C[0]) < 0.25 * rad)] for s in SE.values()])
if len(lid) >= 4: lc = (lid.min(0) + lid.max(0)) / 2; ls_ = max(1.2 * rad, 1.25 * float(np.ptp(lid[:, 1:], 0).max()))
else: lc, ls_ = C + np.array([0, -0.8 * rad, 0]), 1.2 * rad
er_lid = shoot('sec_eye_rest_lid.png', SE['rest'], 0, float(C[0]), 1, lc, ls_, eye_side=sgn)
shoot('sec_eye_blink_lid.png', SE['blink'], 0, float(C[0]), 1, lc, ls_, ghost=er_lid, eye_side=sgn)
QA['eye'] = {'C': [round(float(x), 5) for x in C], 'r_mm': round(1000 * rad, 2), 'lid_inset_size_mm': round(1000 * ls_, 1),
             'rest': eye_qa(SE['rest'], C, rad), 'eyeBlinkLeft': eye_qa(SE['blink'], C, rad)}
json.dump(QA, open(os.path.join(OUT, 'section_qa.json'), 'w'), indent=1)
print('SECTION_QA', json.dumps({k: QA[k] for k in ('slit_ring', 'mouth', 'front_xray')}),
      json.dumps({k: {kk: vv for kk, vv in v.items() if not kk.startswith('per_ring')} for k, v in QA['eye'].items() if isinstance(v, dict)}))
