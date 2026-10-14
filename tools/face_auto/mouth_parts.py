"""T2 · mouth interior as added parts: no original vertex moves.

The lip cut left a slit in the skin (one boundary loop: upper-lip edge + lower-lip edge). From that loop we add
  ring 1  lip inner wall (3 mm straight back from each edge vertex)
  ring 2  mouth bag wall (pulled toward the mouth centre and 22 mm back)
  cap     back of the bag (fan to one centre vertex)
and separate parts: upper teeth, lower teeth, tongue.
Expressions: every added vertex copies the motion of the lip-edge vertex it grew from. For jaw_open that motion is
read back as a rotation about the jaw pivot and re-applied as rotation, so the bag swings with the jaw instead of
sliding. Lower teeth and tongue turn with the lower lip's centre; upper teeth stay.
QA: original vertices unchanged; at rest nothing new is visible from the front; with the jaw open the front rays
through the mouth hit the new interior, not the inside of the head shell.
Usage: blender -b <rig_lids.blend> -P mouth_parts.py -- <rig_qa.json> <out_dir>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
RIGQA, OUT = a[0], a[1]
os.makedirs(OUT, exist_ok=True)
J = np.array(json.load(open(RIGQA))['jaw_pivot'])
face = bpy.data.objects['face']; me = face.data
qa = {}
if 'mouth_cavity' in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects['mouth_cavity'])
kb = me.shape_keys.key_blocks
for k in [k.name for k in kb if k.name in ('blink_L', 'blink_R')]: face.shape_key_remove(kb[k])   # lids are parts now (T1)
kb = me.shape_keys.key_blocks
keys = [k.name for k in kb[1:]]
N0 = len(me.vertices)
X = np.array([tuple(v.co) for v in me.vertices])
K = {k: np.array([tuple(d.co) for d in kb[k].data]) for k in keys}

# ------------------------------------------------------------------ the mouth slit (boundary loop near the mouth)
bm = bmesh.new(); bm.from_mesh(me)
bnd = [e for e in bm.edges if e.is_boundary]
adj = {}
for e in bnd:
    u, v = e.verts[0].index, e.verts[1].index; adj.setdefault(u, []).append(v); adj.setdefault(v, []).append(u)
loops, seen = [], set()
for s0 in adj:
    if s0 in seen: continue
    cyc = [s0]; seen.add(s0); prev, cur = None, s0
    while True:
        nx = [n for n in adj[cur] if n != prev and n not in seen]
        if not nx: break
        prev, cur = cur, nx[0]; cyc.append(cur); seen.add(cur)
    loops.append(cyc)
bm.free()
moving = np.linalg.norm(K['jaw_open'] - X, axis=1) > 1e-6
def score(L):
    P = X[L]; c = P.mean(0)
    return abs(c[0]) * 10 + (0 if moving[L].any() and (~moving[L]).any() else 1)   # midline and half moves with the jaw
loop = np.array(min((L for L in loops if len(L) > 20), key=score))
P = X[loop]; c = P.mean(0); half = (P[:, 0].max() - P[:, 0].min()) / 2
qa['slit_verts'] = int(len(loop)); qa['mouth_width_mm'] = float(half * 2000)

# per-edge-vertex motion: jaw as an angle about the pivot (x axis), visemes as translation
def angle_about_J(p0, p1):
    a0 = math.atan2(p0[2] - J[2], p0[1] - J[1]); a1 = math.atan2(p1[2] - J[2], p1[1] - J[1]); return a1 - a0
theta = np.array([angle_about_J(X[i], K['jaw_open'][i]) for i in loop])
def rot_x(Q, ang):
    d = Q - J; c_, s_ = np.cos(ang), np.sin(ang)
    return J + np.c_[d[:, 0], d[:, 1] * c_ - d[:, 2] * s_, d[:, 1] * s_ + d[:, 2] * c_]

# ------------------------------------------------------------------ geometry
back = np.array([0, 1.0, 0])
ring1 = P + back * 0.003
ring2 = c + (P - c) * np.array([0.85, 0.0, 0.9]) + back * 0.022
cap = c + back * 0.026
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
mat_i = len(me.materials)
m_in = bpy.data.materials.new('mouth_inner'); m_in.diffuse_color = (0.35, 0.08, 0.1, 1); me.materials.append(m_in)
n = len(loop); ev = [bm.verts[int(i)] for i in loop]
r1 = [bm.verts.new(p) for p in ring1]; r2 = [bm.verts.new(p) for p in ring2]; cv = bm.verts.new(cap)
for i in range(n):
    j = (i + 1) % n
    for quad in ((ev[i], ev[j], r1[j], r1[i]), (r1[i], r1[j], r2[j], r2[i])):
        try: f = bm.faces.new(quad); f.material_index = mat_i
        except ValueError: pass
    try: f = bm.faces.new((r2[i], r2[j], cv)); f.material_index = mat_i
    except ValueError: pass
bm.normal_update(); bm.to_mesh(me); bm.free(); me.update()
new_ids = np.arange(N0, len(me.vertices))
for p_ in me.polygons: p_.use_smooth = True
# make the new walls face into the mouth (towards the bag centre)
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
mid = Vector(c + back * 0.012)
for f in bm.faces:
    if f.material_index == mat_i and f.normal.dot(f.calc_center_median() - mid) > 0: f.normal_flip()
bm.to_mesh(me); bm.free(); me.update()

# shape keys for the new vertices: copy the edge vertex's motion
kb = me.shape_keys.key_blocks
basis = kb[0].data
for i in range(n): basis[N0 + i].co = Vector(ring1[i]); basis[N0 + n + i].co = Vector(ring2[i])
basis[N0 + 2 * n].co = Vector(cap)
for k in keys:
    data = kb[k].data
    for i in range(n):
        if k == 'jaw_open':
            p1 = rot_x(ring1[i:i + 1], theta[i])[0]; p2 = rot_x(ring2[i:i + 1], theta[i] * 0.85)[0]
        else:
            d = K[k][loop[i]] - X[loop[i]]; p1 = ring1[i] + d; p2 = ring2[i] + d * 0.6
        data[N0 + i].co = Vector(p1); data[N0 + n + i].co = Vector(p2)
    if k == 'jaw_open': data[N0 + 2 * n].co = Vector(rot_x(cap[None], theta.max() * 0.45)[0])
    else: data[N0 + 2 * n].co = Vector(cap + np.mean([K[k][i] - X[i] for i in loop], axis=0) * 0.3)

# ------------------------------------------------------------------ teeth and tongue (separate parts)
mv = theta > 0.5 * theta.max() if theta.max() > 0 else theta < 0.5 * theta.min()
lower_mid = loop[mv][np.argsort(np.abs(P[mv, 0]))[:6]]                          # lower-lip centre vertices (they move)
th_low = float(np.mean([angle_about_J(X[i], K['jaw_open'][i]) for i in lower_mid]))
zseam = c[2]
def arc_band(name, z0, z1, depth, col):
    us = np.linspace(-1, 1, 25); vs = []; fs = []
    for u in us:
        x = u * half * 0.78; y = c[1] + depth + (u * u) * half * 0.55
        vs += [(x, y, z0), (x, y, z1), (x, y + 0.0025, z1), (x, y + 0.0025, z0)]
    for i in range(len(us) - 1):
        a0, b0 = 4 * i, 4 * (i + 1)
        for q in range(4): fs.append([a0 + q, a0 + (q + 1) % 4, b0 + (q + 1) % 4, b0 + q])
    m = bpy.data.meshes.new(name); m.from_pydata(vs, [], fs); m.update()
    o = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(o); o.color = col
    mt = bpy.data.materials.new(name); mt.diffuse_color = col; m.materials.append(mt); return o
teeth_up = arc_band('teeth_up', zseam - 0.0025, zseam + 0.004, 0.005, (0.97, 0.96, 0.9, 1))
teeth_lo = arc_band('teeth_lo', zseam - 0.004, zseam + 0.0018, 0.0056, (0.97, 0.96, 0.9, 1))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(c[0], c[1] + 0.014, zseam - 0.0055), segments=20, ring_count=10)
tongue = bpy.context.active_object; tongue.name = 'tongue'; tongue.scale = (half * 0.62, 0.011, 0.0035)
bpy.ops.object.transform_apply(scale=True); tongue.color = (0.78, 0.35, 0.4, 1)
mt = bpy.data.materials.new('tongue'); mt.diffuse_color = (0.78, 0.35, 0.4, 1); tongue.data.materials.append(mt)
lip_d = {k: np.mean([K[k][i] - X[i] for i in lower_mid], axis=0) for k in keys}
for o, follows in ((teeth_lo, True), (tongue, True), (teeth_up, False)):
    o.shape_key_add(name='Basis'); V = np.array([tuple(v.co) for v in o.data.vertices])
    for k in keys:
        sk = o.shape_key_add(name=k)
        if not follows: Q = V
        elif k == 'jaw_open': Q = rot_x(V, th_low)
        else: Q = V + lip_d[k] * 0.8
        for d, q in zip(sk.data, Q): d.co = Vector(q)
qa['jaw_angle_lower_lip_deg'] = math.degrees(th_low)

# ------------------------------------------------------------------ QA
Xn = np.array([tuple(v.co) for v in me.vertices])
qa['original_max_offset_mm'] = float(np.abs(Xn[:N0] - X).max() * 1000)
def set_key(k):
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for b in o.data.shape_keys.key_blocks[1:]: b.value = 1.0 if b.name == k else 0.0
    bpy.context.view_layer.update()
def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); m = ev.to_mesh()
    V = [o.matrix_world @ v.co for v in m.vertices]; F = [list(p.vertices) for p in m.polygons]; mats = [p.material_index for p in m.polygons]
    ev.to_mesh_clear(); return V, F, mats
def mouth_rays(k):
    """Front rays over the mouth box: what do they hit first?  skin / interior(new) / head shell from inside / nothing."""
    set_key(k); V, F, mats = evaluated(face)
    bv = BVHTree.FromPolygons(V, F); others = []
    for o in (teeth_up, teeth_lo, tongue):
        Vo, Fo, _ = evaluated(o); others.append(BVHTree.FromPolygons(Vo, Fo))
    res = {'skin': 0, 'interior': 0, 'shell_inside': 0}
    for x in np.linspace(c[0] - half * 0.8, c[0] + half * 0.8, 17):
        for z in np.linspace(zseam - 0.012, zseam + 0.006, 13):
            org = Vector((x, c[1] - 0.3, z)); d = Vector((0, 1, 0))
            loc, nrm, fi, dist = bv.ray_cast(org, d)
            best = (dist if loc else 9, 'face', fi, nrm)
            for b in others:
                l2, n2, f2, d2 = b.ray_cast(org, d)
                if l2 and d2 < best[0]: best = (d2, 'part', f2, n2)
            if best[0] == 9: continue
            if best[1] == 'part' or mats[best[2]] == mat_i: res['interior'] += 1
            elif best[3].y > 0: res['shell_inside'] += 1          # back face of the skin = looking inside the head
            else: res['skin'] += 1
    return res
for k in ('', 'jaw_open', 'viseme_aa', 'viseme_O'):
    if k and k not in keys: continue
    qa['rays_' + (k or 'rest')] = mouth_rays(k)
set_key('')
json.dump(qa, open(os.path.join(OUT, 'qa_mouth.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'rig_mouth.blend'))
print('QA', json.dumps(qa))
