"""겹침생성 · ARKit eye-look keys: eyeLookUp/Down/In/Out Left/Right turn each eyeball about its centre, the lids follow
the vertical gaze a little, and corrective keys keep every blend of them a rigid turn.

The baked asset has no armature, so the 8 eyeLook keys are shape keys on 'eyes' (both eyeballs in one mesh): a key turns
only its own eyeball's vertices about its centre C (eyes.json), about the head's x axis (up / down) or z axis (in / out);
Left = the character's left eye (+x), In = toward the nose, Out = away from it. The ARKit sizes (up 25, down 30,
in / out 35 deg) are capped per head so the iris stays in view: a key turns at most so far that iris_seen (0.5) of the
iris disk (centre + two rings, 25 points) is still seen from the front through the lids and their follow (bisection;
the left eye decides, the right one is its mirror). The iris is where organ_eye_paint found the painted one
(iris=<..._eyepaint.json>: rest direction and radius, both eyes averaged and mirrored); without it only its centre is
tested, placed at the opening's centre (the painted iris can sit 10-25 deg off that, so tex_sym2 reruns this step on
the painted head).
Shape keys blend linearly and a turn does not: at weight 0.5 the eyeball shrinks (chords), and Up + In at 1 / 1 bulges
it out through the lids (3 mm on a big anime eye). So the eyeball also gets correctives, each meant to run with a fixed
weight rule (Fick gaze: the vertical turn first, then the horizontal one about the head's z axis):
  eyeLook<D>Mid<S>          4 t (1 - t)       t = eyeLook<D><S>   (turn by half the angle minus the half key)
  eyeLook<V><H><S>          a b               a = eyeLook<V><S> (V = Up / Down), b = eyeLook<H><S> (H = In / Out)
  eyeLook<V><H>Mid<H><S>    a 4 b (1 - b)
  eyeLook<V><H>Mid<V><S>    4 a (1 - a) b
With them a blend is the exact turn at a, b in {0, 0.5, 1} and stays on the eyeball's sphere in between (QA: radius
error on a 0.25 grid, linear vs corrected). In Blender drivers set them (simple expressions: no Python needed); each
mesh also carries the rules as the custom property 'corrective_keys' (JSON {key: [source key, or [a, b], expression]},
merged with organ_blink_keys' entries) for an exporter or a game runtime, which must set them next to the ARKit values
(a player that leaves them at 0 gets the plain linear keys).
Lid follow: vertical keys may also put a 'face' key of the same name: both lids of that eye turn with the gaze by
follow x the gaze angle at mid-lid (organ_lib.ring_blink: upper lid meet = 1, lower lid meet = 0, turned the same way),
shrunk (x 0.7 steps, none below 1.5 deg) until no lid triangle is squashed below 'squash' of its rest area.
Irregular-ring heads (loop_organs, eyes json 'irregular'): all four keys get a face key from organ_lib.lid_follow: every lid
vertex turns about the eyeball centre C (its gap over the eyeball, the tucks' too, unchanged), the upper lid by fu (0.6)
and the lower by fl (0.25) x the eyeball's elevation, both by fhu / fhl (0.15 / 0.1) x its azimuth for In / Out, times
sin(pi a) along the canthus chord (canthi fixed) and a geodesic falloff over the face (the lid rings span too little
elevation for a 15 deg raise); per key the shares are scaled down (x 0.9) per lid, over falloff reaches 0.7 / 1 / 1.3 /
1.8 x the eyeball radius, until no triangle flips and no visible skin triangle is squashed below squash2 (0.3). Each also
gets face eyeLook<D>Mid<S> (4 t (1 - t): the half turn, as the eyeball's) and eyeBlinkLook<D>Mid<S> (a 4 b (1 - b)) that
takes it out again at a full blink. QA adds apex_follow (lid apex turn / eyeball turn) and see-through rays (leak).
A closed eye should not follow the gaze, and two lid turns added linearly cut into the eyeball, so each follow gets two
face correctives (a = eyeBlink<S>, b = eyeLook<D><S>): eyeBlinkLook<D><S> (a b) takes the follow back out at a full
blink, eyeBlinkMidLook<D><S> (4 a (1 - a) b) pushes lid vertices straight out from C wherever eyeBlink t (with its Mid
corrective) + the follow at w (t, w on a grid) would come nearer the eyeball than organ_blink_keys' floor (0.2 mm, or
the rest gap - 0.1 mm) or than the blink alone; at a full blink the lids are the blink pose whatever the gaze.
Left and Right keys are exact mirrors, so sym_lock.py 'keys' pairs them unchanged. A rerun replaces all eyeLook* /
eyeBlink(Mid)Look* keys and their rules. Armature modifiers left without an armature (rigify_bake outputs before
2026-10-12 21:22: teeth_up) are removed with their DEF-* weights.
QA (<out>_looks.json): angle caps; per key the eyeball turn / centre drift / other-eye move, lid move, lid gap over
the floor, squash, flipped triangles, share of the iris seen from the front (left keys and gaze corners); gaze
grid per quadrant (radius error and distance to the true turn, linear vs corrected); lid clearance on the blink x look
grid (plain sum, follow taken out, with both correctives); eyeball rays seen from the front, open and closed eye.
Usage: blender -b <arkit_b0.blend | tex_eye.blend> -P organ_eye_look_keys.py -- <eyes.json from organ_eye> <out.blend>
       [iris=<tex_eye_eyepaint.json> up=25 down=30 in=35 out=35 follow=0.4 squash=0.4 iris_seen=0.5 fu=0.6 fl=0.25 fhu=0.15 fhl=0.1 squash2=0.3]
"""
import bpy, sys, os, json, math, itertools
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from organ_lib import ring_blink, ring_blink_irregular

a = sys.argv[sys.argv.index('--') + 1:]
EJ, OUT = a[0], os.path.abspath(a[1])
OPT = {'up': 25.0, 'down': 30.0, 'in': 35.0, 'out': 35.0, 'follow': 0.4, 'squash': 0.4, 'iris_seen': 0.5,
       'fu': 0.6, 'fl': 0.25, 'fhu': 0.15, 'fhl': 0.1, 'squash2': 0.3}       # irregular heads: follow shares (see lid_follow)
OPT.update({k: (v if k == 'iris' else float(v)) for k, v in (s.split('=', 1) for s in a[2:])})
IRIS = json.load(open(OPT['iris']))['eyes'] if 'iris' in OPT else None      # organ_eye_paint: where the painted iris sits
CLEAR, KNEE = 0.0002, 0.0001                            # organ_blink_keys' lid floor over the eyeball sphere
J = json.load(open(EJ)); E = J['eyes']; K = J['rings']; M = J['ring_verts']
face = bpy.data.objects['face']; eyes = bpy.data.objects['eyes']
if J.get('irregular'):                                  # loop_organs heads: BFS rings of the original mesh, u off any column grid
    from organ_lib import ring_blink_canthus, lid_coord, lid_follow, follow_field  # same lid motion as organ_blink_keys (canthi fixed)
    _EV = np.empty(len(face.data.edges) * 2, np.int64); face.data.edges.foreach_get('vertices', _EV); _EV = _EV.reshape(-1, 2); _HC = {}
    def ring_blink(X0, ring, u, sg, C, ax, t, K, M, **kw):
        if sg not in _HC: _HC[sg] = lid_coord(len(X0), _EV, ring, sg, K)
        return ring_blink_canthus(X0, ring, u, sg, C, ax, t, K, _HC[sg], **kw)
qa = {'opt': OPT, 'cleanup': [], 'keys': {}, 'gaze': {}, 'blink_look': {}}

for o in [o for o in bpy.data.objects if o.type == 'MESH']:     # Armature modifiers whose armature is gone
    dang = [m for m in o.modifiers if m.type == 'ARMATURE' and m.object is None]
    for m in dang: o.modifiers.remove(m)
    if dang:
        gs = [g for g in o.vertex_groups if g.name.startswith('DEF-')]
        for g in gs: o.vertex_groups.remove(g)
        qa['cleanup'].append({'object': o.name, 'modifiers': len(dang), 'groups': len(gs)})

def co(kb): b = np.empty(len(kb.data) * 3); kb.data.foreach_get('co', b); return b.reshape(-1, 3)
LOOK = ('eyeLook', 'eyeBlinkLook', 'eyeBlinkMidLook')
for o in (face, eyes):                                  # a rerun (iris=) starts clean: a follow may now be 0
    if not o.data.shape_keys: continue
    for kb in [kb for kb in o.data.shape_keys.key_blocks if kb.name.startswith(LOOK)]:
        try: kb.driver_remove('value')
        except TypeError: pass
        o.shape_key_remove(kb)
    if 'corrective_keys' in o.data:
        o.data['corrective_keys'] = json.dumps({k: v for k, v in json.loads(o.data['corrective_keys']).items() if not k.startswith(LOOK)})
def basis(o):
    if not o.data.shape_keys: o.shape_key_add(name='Basis')
    return co(o.data.shape_keys.key_blocks[0])
def put_key(o, name, P):
    kb = o.data.shape_keys.key_blocks.get(name) or o.shape_key_add(name=name, from_mix=False)
    kb.data.foreach_set('co', np.asarray(P, float).ravel()); kb.value = 0.0; return kb
CORR = {'eyes': {}, 'face': {}}
def corrective(o, name, P, srcs, expr):                 # key + driver (variables t, or a and b, = the source keys' values)
    kb = put_key(o, name, P)
    try: kb.driver_remove('value')
    except TypeError: pass
    d = kb.driver_add('value').driver; d.type = 'SCRIPTED'
    for vn, src in zip(('t',) if len(srcs) == 1 else ('a', 'b'), srcs):
        v = d.variables.new(); v.name = vn; v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'KEY'
        v.targets[0].id = o.data.shape_keys; v.targets[0].data_path = f'key_blocks["{src}"].value'
    d.expression = expr; CORR[o.name][name] = [srcs[0] if len(srcs) == 1 else list(srcs), expr.replace(' ', '')]

X = basis(face); Xe = basis(eyes)
ring = np.array([d.value for d in face.data.attributes['eye_ring'].data]); uu = np.array([d.value for d in face.data.attributes['eye_u'].data])
Cs = {s: np.array(E[s]['C']) for s in 'LR'}
side = np.where(np.linalg.norm(Xe - Cs['L'], axis=1) < np.linalg.norm(Xe - Cs['R'], axis=1), 'L', 'R')
face.data.calc_loop_triangles(); TRI = np.array([tuple(t.vertices) for t in face.data.loop_triangles])
def tarea(P): return np.cross(P[TRI[:, 1]] - P[TRI[:, 0]], P[TRI[:, 2]] - P[TRI[:, 0]])
A0 = np.linalg.norm(tarea(X), axis=1) + 1e-18; N0 = tarea(X) / A0[:, None]
def Rm(ax, deg):                                         # turn about the head's x or z axis
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]]) if ax == 'x' else np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def azel(V):                                            # head chart about C: azimuth (+ = +x) and elevation, degrees
    V = V / np.linalg.norm(V, axis=1, keepdims=True); return np.degrees(np.c_[np.arctan2(V[:, 0], -V[:, 1]), np.arcsin(np.clip(V[:, 2], -1, 1))])
def unit(az, el): az, el = math.radians(az), math.radians(el); return np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
def iris_dir(s, sg):                                    # rest iris: the painted one (both eyes averaged, mirrored), else the opening's centre
    if IRIS and all('iris_rest_azel' in IRIS[e] for e in 'LR'):
        (al, el_), (ar, er) = IRIS['L']['iris_rest_azel'], IRIS['R']['iris_rest_azel']; return unit(sg * (al - ar) / 2, (el_ + er) / 2)
    g = (X[ring == sg * K] - Cs[s]).mean(0); return g / np.linalg.norm(g)
RHO = float(np.mean([IRIS[e]['iris_radius_deg'] for e in 'LR'])) if IRIS and all('iris_radius_deg' in IRIS[e] for e in 'LR') else 0.0
def iris_pts(g):                                        # the iris disk: centre and two rings (unit directions from C)
    e1 = np.cross(g, [0, 0, 1.0]); e1 /= np.linalg.norm(e1); e2 = np.cross(g, e1); rho = math.radians(RHO)
    return np.array([g] + [math.cos(a) * g + math.sin(a) * (math.cos(b) * e1 + math.sin(b) * e2) for a in ((0.5 * rho, 0.9 * rho) if rho else ())
                           for b in np.radians(np.arange(0, 360, 30))])
# per key: (gaze rotation axis, sign of the angle for the LEFT eye, lid motion); the right eye mirrors (x axis: same, z: -)
DIRS = {'Up': ('x', -1, 'up'), 'Down': ('x', 1, 'down'), 'In': ('z', -1, None), 'Out': ('z', 1, None)}
m4 = lambda t: 4 * t * (1 - t)
floor = lambda g0: np.clip(np.minimum(CLEAR, g0 - KNEE), 0, None)

# ---- lid follow: a mid-lid turn in degrees as a share of the lid's own closing turn (ring_blink at t = 1)
def lid_turn(P0, P1, s, sg, cols):                      # largest turn of the margin about the corner axis, rad
    ax = np.array(E[s]['axis']); ax /= np.linalg.norm(ax); m = np.where((ring == sg * K) & np.isin(np.rint(uu * M).astype(int) % M, cols))[0]
    A = P0[m] - Cs[s]; B = P1[m] - Cs[s]; A -= np.outer(A @ ax, ax); B -= np.outer(B @ ax, ax)
    return float(np.max(np.arccos(np.clip((A * B).sum(1) / np.linalg.norm(A, axis=1) / np.linalg.norm(B, axis=1), -1, 1))))
DMID = {s: lid_turn(X, ring_blink(X, ring, uu, sg, Cs[s], np.array(E[s]['axis']), 1.0, K, M, meet=1.0), s, sg, list(range(1, M // 2)))
        for s, sg in (('L', 1), ('R', -1))}
def lids(s, sg, deg):                                   # both lids of one eye turn down (deg > 0) or up by deg at mid-lid
    C, ax, r = Cs[s], np.array(E[s]['axis']), float(E[s]['r'])
    t = math.radians(deg) / DMID[s]
    Pu = ring_blink(X, ring, uu, sg, C, ax, t, K, M, meet=1.0, r_eye=r if t > 0 else None)      # upper lid toward / away from the lower
    Pl = ring_blink(X, ring, uu, sg, C, ax, -t, K, M, meet=0.0, r_eye=r if t < 0 else None)    # lower lid the same way
    P = Pu + Pl - X
    d0 = np.linalg.norm(X - C, axis=1); d1 = np.linalg.norm(P - C, axis=1); fl = np.minimum(d0, r + 0.0003)
    push = (np.sign(ring) == sg) & (d1 < fl)            # never nearer the eyeball than at rest (or r + 0.3 mm)
    P[push] = C + (P[push] - C) * (fl[push] / d1[push])[:, None]
    ft = np.isin(TRI, np.where(np.abs(P - X).max(1) > 1e-7)[0]).any(1)
    return P, int(push.sum()), float(((tarea(P)[ft] * N0[ft]).sum(1) / A0[ft]).min()) if ft.any() else 1.0
def blink_keys(nm, s, sg):                              # eyeBlink and its Mid corrective (organ_blink_keys) as displacements
    kbs = face.data.shape_keys.key_blocks
    B = co(kbs['eyeBlink' + nm]) - X if kbs.get('eyeBlink' + nm) else ring_blink(X, ring, uu, sg, Cs[s], np.array(E[s]['axis']), 1.0, K, M, r_eye=float(E[s]['r'])) - X
    return B, (co(kbs['eyeBlinkMid' + nm]) - X if kbs.get('eyeBlinkMid' + nm) else np.zeros_like(X))

IRR = bool(J.get('irregular'))
REACHES = tuple(round(f_ * float(E['L']['r']), 5) for f_ in (0.7, 1.0, 1.3, 1.8)); _FF = {}    # falloff reach: x eyeball radius
def follow_pose(s, sg, d, th, su=1.0, sl=1.0, reach=0.014):   # irregular heads: lids turned about C with the gaze (organ_lib.lid_follow)
    if (sg, reach) not in _FF: _FF[(sg, reach)] = follow_field(X, ring, uu, sg, K, _EV, reach)
    vert = d in ('Up', 'Down'); g = (th if d == 'Up' else -th) if vert else (-th if d == 'In' else th) * sg     # eyeball el / az, deg
    eu, el_ = (OPT['fu'] * g * su, OPT['fl'] * g * sl) if vert else (0.0, 0.0)
    au, al = (0.0, 0.0) if vert else (OPT['fhu'] * g * su, OPT['fhl'] * g * sl)
    P = lid_follow(X, ring, uu, sg, Cs[s], K, _FF[(sg, reach)], eu, el_, au, al, rim=0.1 * float(E[s]['r']))
    ft = np.isin(TRI, np.where(np.abs(P - X).max(1) > 1e-9)[0]).any(1)
    q = (tarea(P) * N0).sum(1) / A0; skin = (np.abs(ring[TRI]) <= K).all(1) & ft
    return P, 0, float(q[skin].min()) if skin.any() else 1.0, int((q[ft] < 0).sum())
def follow_ok(d, su, sl, reach, th=None):               # visible skin squashed no more than squash2, no triangle flipped (tucks too)
    _, _, q_, nf_ = follow_pose('L', 1, d, OPT[d.lower()] if th is None else th, su, sl, reach); return q_ >= OPT['squash2'] and nf_ == 0
def follow_search(d):                                   # per lid the largest share (x 0.9 steps) at the reach that allows most
    best = None
    for reach in REACHES:
        sc = {}
        for lid_ in ('u', 'l'):
            x = 1.0
            while x > 0.15 and not follow_ok(d, x if lid_ == 'u' else 0.0, x if lid_ == 'l' else 0.0, reach): x *= 0.9
            sc[lid_] = x if x > 0.15 else 0.0
        su, sl = sc['u'], sc['l']
        while (su > 0 or sl > 0) and not follow_ok(d, su, sl, reach): su, sl = su * 0.9, sl * 0.9   # both together
        cand = (round(su, 3), round(sl, 3), reach)
        if best is None or su + 0.5 * sl > best[0] + 0.5 * best[1] + 1e-6: best = cand
    return best
def apex_follow(P, s, sg, d, th):                       # lid apex (margin vertex mid-chord) turn about C / eyeball turn
    C = Cs[s]; mk = np.where(ring == sg * K)[0]; um = np.mod(uu[mk], 1.0)
    io, ii = mk[np.argmin(np.minimum(um, 1 - um))], mk[np.argmin(np.abs(um - 0.5))]; e = X[ii] - X[io]; a_ = ((X[mk] - X[io]) @ e) / (e @ e)
    out = {}
    for nm_, sel in (('upper', (um > 0) & (um < 0.5)), ('lower', um > 0.5)):
        v = mk[sel][np.argmin(np.abs(a_[sel] - 0.5))]; A = azel((X[[v]] - C))[0]; B = azel((P[[v]] - C))[0]
        if d in ('Up', 'Down'): out[nm_] = round(float((B[1] - A[1]) / (th if d == 'Up' else -th)), 3)
        else: out[nm_] = round(float((B[0] - A[0]) / ((-th if d == 'In' else th) * sg)), 3)
    return out
# ---- eyeball rays from the front through the left eye's lids: those that reach the eyeball before the face
fsel = np.linalg.norm(X - Cs['L'], axis=1) < 2.5 * float(E['L']['r'])
FP = [list(p.vertices) for p in face.data.polygons if fsel[list(p.vertices)].all()]
bvh_eye = BVHTree.FromPolygons([tuple(v) for v in Xe], [list(p.vertices) for p in eyes.data.polygons])
mgL = X[ring == K]; gx = np.linspace(mgL[:, 0].min() - 0.002, mgL[:, 0].max() + 0.002, 160); gz = np.linspace(mgL[:, 2].min() - 0.002, mgL[:, 2].max() + 0.002, 100)
def seen(P):                                            # (the eyeball is a sphere: its turn does not change what the rays see)
    bf = BVHTree.FromPolygons([tuple(v) for v in P], FP); n = 0; y0 = float(P[:, 1].min()) - 0.05
    for x in gx:
        for z in gz:
            o = Vector((x, y0, z)); he = bvh_eye.ray_cast(o, Vector((0, 1, 0)))
            if he[0] is None: continue
            hf = bf.ray_cast(o, Vector((0, 1, 0))); n += hf[0] is None or he[3] < hf[3]
    return n
def iris_seen(P, G):                                    # share of iris points G (turned, left eye) seen from the front through face P
    bf = BVHTree.FromPolygons([tuple(v) for v in P], FP); y0 = float(P[:, 1].min()) - 0.05; Q = Cs['L'] + float(E['L']['r']) * G; n = 0
    for g, q in zip(G, Q):
        if g[1] < 0: h = bf.ray_cast(Vector((q[0], y0, q[2])), Vector((0, 1, 0))); n += h[0] is None or h[3] > q[1] - y0 - 1e-5
    return n / len(G)
_car = bpy.data.objects.get('caruncle')                 # the caruncle closes the inner corner's pocket (static under the looks)
bvh_car = BVHTree.FromPolygons([tuple(v.co) for v in _car.data.vertices], [list(p.vertices) for p in _car.data.polygons]) if _car else None
_fs4 = np.linalg.norm(X - Cs['L'], axis=1) < 4.5 * float(E['L']['r']); FP4 = [list(p.vertices) for p in face.data.polygons if _fs4[list(p.vertices)].any()]
def leak(P, dirs=((0, 1, 0), (-0.5, 0.86, 0))):         # rays (front, 3/4) over the left eye's opening box: 'miss' = see-through
    bf = BVHTree.FromPolygons([tuple(v) for v in P], FP4)  # (no face, eyeball or caruncle hit), 'inner' = a lid face seen from behind
    out = {'miss': [], 'inner': []}
    for dv in dirs:
        dv = np.array(dv, float); dv /= np.linalg.norm(dv); n = b = 0
        for x in gx[::2]:
            for z in gz[::2]:
                p0 = Vector(tuple(np.array([x, float(Cs['L'][1]), z]) - dv * 0.08)); vd = Vector(tuple(dv))
                hf = bf.ray_cast(p0, vd); he = bvh_eye.ray_cast(p0, vd); hc = bvh_car.ray_cast(p0, vd) if bvh_car else (None,) * 4
                if hf[0] is None and he[0] is None and hc[0] is None: n += 1; continue
                if hf[0] is not None and (he[0] is None or hf[3] < he[3]) and (hc[0] is None or hf[3] < hc[3]) and np.array(hf[1]) @ dv > 0: b += 1
        out['miss'].append(n); out['inner'].append(b)
    return out
BL = {s: blink_keys(nm, s, sg) for s, sg, nm in (('L', 1, 'Left'), ('R', -1, 'Right'))}
SEEN = {'rest': seen(X), 'blink': seen(X + BL['L'][0])}

# ---- angle caps: a key turns at most so far that 'iris_seen' of the iris disk (its centre when the paint is unknown) is
# still seen from the front through the lids and their follow (bisection); the left eye decides, the right is its mirror
G0 = iris_pts(iris_dir('L', 1)); ANG, FOL = {}, {}; VIS0 = iris_seen(X, G0); need = min(OPT['iris_seen'], 0.8 * VIS0)
lidpose = lambda lid, phi: lids('L', 1, phi if lid == 'down' else -phi)[0] if lid and phi > 0 else X
FSC = {}
for d, (ax, sgn, lid) in DIRS.items():
    if IRR:                                              # irregular heads: lids turn about C (lid_follow), all four keys
        FSC[d] = follow_search(d)
        fits = lambda th: iris_seen(follow_pose('L', 1, d, th, *FSC[d])[0], G0 @ Rm(ax, sgn * th).T) >= need
        lo, hi = 0.0, OPT[d.lower()]
        if fits(hi): lo = hi
        else:
            for _ in range(8): mid = round((lo + hi) / 2, 2); lo, hi = (mid, hi) if fits(mid) else (lo, mid)
        ANG[d] = lo; FOL[d] = FSC[d]; continue
    phi = OPT['follow'] * OPT[d.lower()] if lid else 0.0
    while phi >= 1.5 and lids('L', 1, phi if lid == 'down' else -phi)[2] < OPT['squash']: phi *= 0.7     # no squashed lid
    phi = phi if phi >= 1.5 else 0.0                     # a smaller follow is not seen
    fol = lambda th: round(min(phi, OPT['follow'] * th), 2)                      # tested exactly as the keys get them
    fits = lambda th: iris_seen(lidpose(lid, fol(th)), G0 @ Rm(ax, sgn * th).T) >= need
    lo, hi = 0.0, OPT[d.lower()]
    if fits(hi): lo = hi
    else:
        for _ in range(8): mid = round((lo + hi) / 2, 2); lo, hi = (mid, hi) if fits(mid) else (lo, mid)
    FOL[d] = fol(lo); ANG[d] = lo
qa.update({'angle_deg': ANG, 'lid_follow_deg': FOL, 'iris_rest_azel': [round(float(x), 2) for x in azel(G0[:1])[0]], 'iris_radius_deg': RHO,
           'iris_from': 'painted (organ_eye_paint)' if RHO else 'opening centre', 'iris_seen_rest': round(VIS0, 3), 'iris_seen_need': round(need, 3),
           'lid_full_turn_deg': round(math.degrees(DMID['L']), 1), 'seen_px': SEEN})
if IRR: qa.update(lid_follow_mode='lid_follow (turn about C)', lid_follow_scale_upper_lower_reach=FSC, follow_shares={k: OPT[k] for k in ('fu', 'fl', 'fhu', 'fhl')}, leak_rest=leak(X))

TT = np.round(np.arange(0.1, 1.001, 0.1), 2); WW = (0.25, 0.5, 0.75, 1.0); G5 = (0.0, 0.25, 0.5, 0.75, 1.0)
for s, sg, nm in (('L', 1, 'Left'), ('R', -1, 'Right')):
    C, r = Cs[s], float(E[s]['r']); sel = side == s; Y = Xe[sel]; r0 = np.linalg.norm(Y - C, axis=1)
    lidm = np.where((np.sign(ring) == sg) & (np.abs(ring) >= 2))[0]; li = np.where(np.sign(ring) == sg)[0]
    Bl, Ml = BL[s]; ANGS = {d: sgn * ANG[d] * (sg if ax == 'z' else 1) for d, (ax, sgn, lid) in DIRS.items()}
    def Rg(dw):                                          # Fick: the vertical turn first, then the horizontal one
        R = np.eye(3)
        for d, w in sorted(dw, key=lambda x: DIRS[x[0]][0] == 'z'): R = Rm(DIRS[d][0], ANGS[d] * w) @ R
        return R
    def pose(dw): P = Xe.copy(); P[sel] = (Y - C) @ Rg(dw).T + C; return P - Xe
    D = {d: pose([(d, 1.0)]) for d in DIRS}; Mid = {d: pose([(d, 0.5)]) - 0.5 * D[d] for d in DIRS}
    FL = {}
    for d, (ax, sgn, lid) in DIRS.items():
        name = 'eyeLook%s%s' % (d, nm); put_key(eyes, name, Xe + D[d])
        corrective(eyes, 'eyeLook%sMid%s' % (d, nm), Xe + Mid[d], [name], '4 * t * (1 - t)')
        R = {'eye_turn_deg': round(ANGS[d], 2), 'centre_drift_mm': round(float(np.linalg.norm(D[d][sel].mean(0)) * 1000), 4),
             'other_eye_max_mm': round(float(np.abs(D[d][~sel]).max() * 1000), 4),
             'mid_radius_err_mm': [round(float(x * 1000), 4) for x in (lambda e: (e.min(), e.max()))(np.concatenate(
                 [np.linalg.norm(Y + t * D[d][sel] + m4(t) * Mid[d][sel] - C, axis=1) - r0 for t in TT]))],
             'linear_radius_err_mm': round(float(min((np.linalg.norm(Y + t * D[d][sel] - C, axis=1) - r0).min() for t in TT) * 1000), 4)}
        Pf = X
        if (IRR and ANG[d] > 0) or (lid and FOL[d] > 0):
            if IRR: Pf, npush, q, _ = follow_pose(s, sg, d, ANG[d], *FSC[d])
            else: Pf, npush, q = lids(s, sg, FOL[d] if lid == 'down' else -FOL[d])
            put_key(face, name, Pf); Df = Pf - X; Mf = np.zeros_like(X)
            if IRR:                                      # the follow is a turn: half weight = the half turn (same rule as the eyeball's Mid key)
                Mf = follow_pose(s, sg, d, ANG[d] / 2, *FSC[d])[0] - X - 0.5 * Df
                corrective(face, 'eyeLook%sMid%s' % (d, nm), X + Mf, [name], '4 * t * (1 - t)')
                corrective(face, 'eyeBlinkLook%sMid%s' % (d, nm), X - Mf, ['eyeBlink' + nm, name], 'a * 4 * b * (1 - b)')   # full blink: out again
            if IRR and s == 'L': R.update(apex_follow=apex_follow(Pf, s, sg, d, ANG[d]), leak=leak(Pf), leak_half=leak(X + 0.5 * Df + Mf),
                                          leak_quarter=leak(X + 0.25 * Df + 0.75 * Mf), mid_max_mm=round(float(np.linalg.norm(Mf, axis=1).max() * 1000), 3))
            Dm = np.linalg.norm(Df, axis=1); act = np.where(Dm > 1e-6)[0]; ft = np.isin(TRI, act).any(1)
            g0l = np.linalg.norm(X[lidm] - C, axis=1) - r
            R.update({'lid_max_mm': round(float(Dm.max() * 1000), 2), 'lid_moved_verts': int(len(act)), 'squash_min': round(q, 3), 'pushed_out': npush,
                      'lid_gap_over_floor_min_mm': round(float(min((np.linalg.norm(X[lidm] + w * Df[lidm] + m4(w) * Mf[lidm] - C, axis=1) - r - floor(g0l)).min() for w in WW) * 1000), 4),
                      'lid_gap_min_mm': round(float((np.linalg.norm(Pf[lidm] - C, axis=1) - r).min() * 1000), 3),
                      'flipped_tris': int(((tarea(Pf)[ft] * N0[ft]).sum(1) < 0).sum())})
            # blink x look correctives: a full blink takes the follow back out (a b, a = eyeBlink, b = the look), and in
            # between (4 a (1 - a) b) lid vertices are pushed straight out from C where they would come nearer the eyeball
            # than the floor or than the blink alone, on the (t, w) grid; at t = 1 the pose is the blink alone
            Xl, Bs, Ms, Fs, MF = X[li], Bl[li], Ml[li], Df[li], Mf[li]; Dc = np.zeros_like(Fs)
            gap = lambda P: np.linalg.norm(P - C, axis=1) - r; fl = floor(gap(Xl))
            FLt = {t: np.minimum(fl, gap(Xl + t * Bs + m4(t) * Ms)) - 1e-7 for t in TT}     # or the blink alone, where nearer
            pz = lambda t, w, c1, c2: Xl + t * Bs + m4(t) * Ms + (1 - c1 * t) * (w * Fs + m4(w) * MF) + m4(t) * w * c2
            low = lambda c1, c2: min(float((gap(pz(t, w, c1, c2)) - FLt[t]).min()) for t in TT for w in WW)
            lin, cancel, it = low(0, 0 * Dc), low(1, 0 * Dc), 0
            for it in range(100):
                worst = 0.0
                for t in TT[TT < 1]:
                    for w in WW:
                        v = pz(t, w, 1, Dc) - C; n_ = np.linalg.norm(v, axis=1); de = FLt[t] - (n_ - r); mk = de > 0
                        if mk.any(): Dc[mk] += (de[mk] / (m4(t) * w * n_[mk]))[:, None] * v[mk]; worst = max(worst, float(de.max()))
                if worst < 1e-9: break
            cn, cm = 'eyeBlinkLook%s%s' % (d, nm), 'eyeBlinkMidLook%s%s' % (d, nm); Pm = X.copy(); Pm[li] += Dc
            corrective(face, cn, X - Df, ['eyeBlink' + nm, name], 'a * b'); corrective(face, cm, Pm, ['eyeBlink' + nm, name], '4 * a * (1 - a) * b')
            qa['blink_look'][cn] = {'gap_over_floor_min_mm_linear': round(lin * 1000, 4), 'follow_out_only': round(cancel * 1000, 4), 'with_correctives': round(low(1, Dc) * 1000, 4),
                                    'iters': it, 'push_max_mm': round(float(np.linalg.norm(Dc, axis=1).max() * 1000), 3)}
        if s == 'L': R['iris_seen'] = round(iris_seen(Pf, G0 @ Rg([(d, 1.0)]).T), 3)
        FL[d] = Pf; qa['keys'][name] = R
    for V, H in itertools.product(('Up', 'Down'), ('In', 'Out')):          # combination correctives, exact on the 0 / .5 / 1 grid
        base = lambda a_, b_: a_ * D[V] + b_ * D[H] + m4(a_) * Mid[V] + m4(b_) * Mid[H]
        K1 = pose([(V, 1.0), (H, 1.0)]) - base(1, 1)
        K2 = pose([(V, 1.0), (H, 0.5)]) - base(1, 0.5) - 0.5 * K1
        K3 = pose([(V, 0.5), (H, 1.0)]) - base(0.5, 1) - 0.5 * K1
        src = ['eyeLook%s%s' % (V, nm), 'eyeLook%s%s' % (H, nm)]
        corrective(eyes, 'eyeLook%s%s%s' % (V, H, nm), Xe + K1, src, 'a * b')
        corrective(eyes, 'eyeLook%s%sMid%s%s' % (V, H, H, nm), Xe + K2, src, '4 * a * b * (1 - b)')
        corrective(eyes, 'eyeLook%s%sMid%s%s' % (V, H, V, nm), Xe + K3, src, '4 * a * (1 - a) * b')
        if s != 'L': continue
        rows = {}
        for lab, full in (('linear', False), ('corrected', True)):
            rad, err = [], []
            for a_, b_ in itertools.product(G5, G5):
                P = base(a_, b_) + a_ * b_ * K1 + a_ * m4(b_) * K2 + m4(a_) * b_ * K3 if full else a_ * D[V] + b_ * D[H]
                rad.append(np.linalg.norm(Y + P[sel] - C, axis=1) - r0); err.append(np.linalg.norm(P[sel] - pose([(V, a_), (H, b_)])[sel], axis=1).max())
            rad = np.concatenate(rad); rows[lab] = {'radius_err_mm': [round(float(rad.min() * 1000), 4), round(float(rad.max() * 1000), 4)], 'to_true_turn_max_mm': round(float(max(err) * 1000), 4)}
        rows['iris_seen_at_1_1'] = round(iris_seen(FL[V], G0 @ Rg([(V, 1.0), (H, 1.0)]).T), 3)
        qa['gaze'][V + H] = rows
    qa['rest_lid_gap_min_mm_' + s] = round(float((np.linalg.norm(X[lidm] - C, axis=1) - r).min() * 1000), 3)

for o in (eyes, face):                                   # weight rules for exporters / runtimes, merged with the blink ones
    rules = json.loads(o.data['corrective_keys']) if 'corrective_keys' in o.data else {}
    rules.update(CORR[o.name])
    if rules: o.data['corrective_keys'] = json.dumps(rules)
qa['ok'] = bool(all(k['centre_drift_mm'] < 0.05 and k['other_eye_max_mm'] == 0 and k.get('iris_seen', 1) >= need - 0.01 and k.get('flipped_tris', 0) == 0
                    and k['mid_radius_err_mm'][1] <= 0.01 and k.get('lid_gap_over_floor_min_mm', 0) >= -1e-3 for k in qa['keys'].values())
                and all(g['corrected']['radius_err_mm'][1] <= 0.01 for g in qa['gaze'].values())
                and all(b['with_correctives'] >= -1e-3 for b in qa['blink_look'].values()))
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(qa, open(os.path.splitext(OUT)[0] + '_looks.json', 'w'), indent=1)
print('EYELOOK', json.dumps({k: qa[k] for k in ('angle_deg', 'lid_follow_deg', 'iris_from', 'iris_seen_rest', 'seen_px', 'cleanup', 'blink_look', 'ok')}))
for k, v in list(qa['keys'].items()) + list(qa['gaze'].items()): print('  ', k, v)
