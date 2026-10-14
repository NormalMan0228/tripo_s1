"""T1 · eyelid parts: blink without moving a single original vertex.

A thin lid shell per eye sits on a sphere around the eyeball centre, tucked under the original upper-lid band
(hidden at rest). Blink = one bone per eye rotating the shell about the eye axis, so it slides out from under
the band, over the eyeball, and tucks under the lower lid. Bone rotation follows an arc, so mid-blink never cuts
into the eyeball (a shape key would interpolate on a chord).

Steps
 1. eye frame per side: centre C, axis A (outer->inner corner), up/forward from rig_original's eyes_meta.json
 2. per lateral slice s: angles of the upper/lower margin; eyeball surface radius over the travel (ray casts)
 3. shell = grid over s (corner to corner + pad) and angle (just above the upper margin up to the hidden top),
    radius = eyeball surface max along that slice + clearance
 4. closing angle alpha = largest upper-to-lower margin gap + overlap; top edge kept hidden after rotation
 5. armature with bones lid_L / lid_R (head at C, along A); shell weighted 100 % to its bone
 6. QA: shell hidden at rest (rays from the camera side), eyeball coverage when closed, shell never inside the
    eyeball at 0 / 50 / 100 %, original face untouched
Usage: blender -b <rig.blend> -P lid_parts.py -- <eyes_meta.json> <out_dir>
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
META, OUT = a[0], a[1]
os.makedirs(OUT, exist_ok=True)
meta = json.load(open(META))
face = bpy.data.objects['face']; eyes = bpy.data.objects['eyes']
qa = {}

def mesh_bvh(ob):
    V = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return BVHTree.FromPolygons(V, [list(p.vertices) for p in ob.data.polygons])
bF, bE = mesh_bvh(face), mesh_bvh(eyes)
Fv0 = np.array([tuple(v.co) for v in face.data.vertices])

CLEAR = 0.0008      # shell clearance above the eyeball surface (m)
TUCK = 0.05         # radians the shell edge tucks under the lower lid when closed
TUCK_REST = 0.11    # radians the shell's bottom edge hides above the upper margin at rest
PAD = -0.001        # lateral extent: stop 1 mm inside the corners (m)
NB = 9              # lid bones per eye along the eye axis (outer -> inner)

def frame(e):
    C, A = np.array(e['C']), np.array(e['A']); A /= np.linalg.norm(A)
    fwd = np.array([0, -1.0, 0]); fwd = fwd - A * (fwd @ A); fwd /= np.linalg.norm(fwd)
    up = np.cross(A, fwd)
    if up[2] < 0: up = -up
    return C, A, up, fwd

def polar(P, C, A, up, fwd):
    d = P - C; return d @ A, np.arctan2(d @ up, d @ fwd), np.sqrt((d @ up) ** 2 + (d @ fwd) ** 2)

def point(C, A, up, fwd, s, phi, rad):
    return C + A * s + up * (np.sin(phi) * rad) + fwd * (np.cos(phi) * rad)

def surf_radius(C, A, up, fwd, s, phi):
    """Distance from the axis to the eyeball surface along (s, phi), by casting from outside toward the axis."""
    far = point(C, A, up, fwd, s, phi, 0.08); near = point(C, A, up, fwd, s, phi, 0.0)
    d = Vector(near - far); L = d.length
    hit = bE.ray_cast(Vector(far), d.normalized(), L)[0]
    return None if hit is None else float(np.linalg.norm(np.array(hit) - near))

parts = {}
arm_data = bpy.data.armatures.new('lid_rig'); arm = bpy.data.objects.new('lid_rig', arm_data)
bpy.context.scene.collection.objects.link(arm)
for side in ('L', 'R'):
    e = meta[side]; C, A, up, fwd = frame(e)
    UP, LO = np.array(e['up_path']), np.array(e['lo_path'])
    su, pu, _ = polar(UP, C, A, up, fwd); sl, pl, _ = polar(LO, C, A, up, fwd)
    ou, ol = np.argsort(su), np.argsort(sl)
    s0, s1 = min(su.min(), sl.min()) - PAD, max(su.max(), sl.max()) + PAD
    S = np.linspace(s0, s1, 28)
    phi_up = np.interp(S, su[ou], pu[ou]); phi_lo = np.interp(S, sl[ol], pl[ol])
    gap = phi_up - phi_lo
    # each lateral slice turns only as far as it needs; the shell is as tall as its own turn plus tucks
    need = np.maximum(gap, 0) + TUCK_REST + TUCK
    # bone angles: each bone takes the largest need in its half-interval on both sides, so blends never undershoot
    sb = np.linspace(S[0], S[-1], NB); half = (sb[1] - sb[0]) / 2
    alpha_b = np.array([need[np.abs(S - x) <= half + 1e-9].max() for x in sb])
    alpha_s = np.interp(S, sb, alpha_b)                 # what each slice will actually turn (linear blend)
    Hs = alpha_s + TUCK_REST + TUCK
    R = []
    for i, s in enumerate(S):
        rs = [surf_radius(C, A, up, fwd, s, ph) for ph in np.linspace(phi_up[i] + TUCK_REST - alpha_s[i] - TUCK, phi_up[i] + TUCK_REST + Hs[i], 28)]
        rs = [x for x in rs if x is not None]
        R.append(max(rs) + CLEAR if rs else np.nan)
    R = np.array(R); good = ~np.isnan(R); R = np.interp(np.arange(len(R)), np.nonzero(good)[0], R[good])
    R = np.maximum(R, np.convolve(np.pad(R, 2, mode='edge'), np.ones(5) / 5, 'valid'))   # smooth, never below the surface
    NPHI = 18
    verts, faces, vs = [], [], []
    for i, s in enumerate(S):
        for j in range(NPHI):
            ph = (phi_up[i] + TUCK_REST) + Hs[i] * j / (NPHI - 1)
            verts.append(point(C, A, up, fwd, s, ph, R[i])); vs.append(s)
    for i in range(len(S) - 1):
        for j in range(NPHI - 1):
            v0 = i * NPHI + j; faces.append([v0, v0 + NPHI, v0 + NPHI + 1, v0 + 1])
    me = bpy.data.meshes.new('lid_' + side); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    ob = bpy.data.objects.new('lid_' + side, me); bpy.context.scene.collection.objects.link(ob)
    n0 = np.array(me.polygons[0].normal); c0 = np.array(me.polygons[0].center)
    if n0 @ (c0 - C) < 0: me.flip_normals()
    for p in me.polygons: p.use_smooth = True
    if face.data.materials: ob.data.materials.append(face.data.materials[0])
    # bone chain along the eye axis; vertices blend linearly between the two nearest bones
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
    for k in range(NB):
        b = arm_data.edit_bones.new('lid_%s_%d' % (side, k)); b.head = Vector(C + A * sb[k]); b.tail = Vector(C + A * (sb[k] + 0.01))
        b.align_roll(Vector(up))
    bpy.ops.object.mode_set(mode='OBJECT')
    vs = np.array(vs); t_ = np.clip((vs - sb[0]) / (sb[-1] - sb[0]) * (NB - 1), 0, NB - 1 - 1e-9)
    k0 = np.floor(t_).astype(int); f_ = t_ - k0
    groups = [ob.vertex_groups.new(name='lid_%s_%d' % (side, k)) for k in range(NB)]
    for vi in range(len(verts)):
        groups[k0[vi]].add([vi], 1 - f_[vi], 'ADD'); groups[k0[vi] + 1].add([vi], f_[vi], 'ADD')
    ob.parent = arm; mod = ob.modifiers.new('arm', 'ARMATURE'); mod.object = arm
    parts[side] = {'ob': ob, 'C': C, 'A': A, 'up': up, 'fwd': fwd, 'alpha_b': alpha_b, 'S': S, 'phi_up': phi_up, 'phi_lo': phi_lo, 'R': R}
    qa['eye_' + side] = {'close_angle_deg_per_bone': [round(math.degrees(x), 1) for x in alpha_b],
                         'radius_mm': [float(R.min() * 1000), float(R.max() * 1000)]}

def set_blink(t):
    """Pose every lid bone: t = 0 open, 1 closed. Bone local Y is the eye axis, so this rotates about it."""
    for side, p in parts.items():
        for k in range(NB):
            pb = arm.pose.bones['lid_%s_%d' % (side, k)]; pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Quaternion((0, 1, 0), -p['alpha_b'][k] * t * p.get('sign', 1))
    bpy.context.view_layer.update()

def world_verts(ob):
    dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); m = ev.to_mesh()
    P = np.array([tuple(ob.matrix_world @ v.co) for v in m.vertices]); ev.to_mesh_clear(); return P

# decide the rotation sign per eye: closing must lower the shell's bottom edge toward the lower lid
for side, p in parts.items():
    set_blink(0.0); P0 = world_verts(p['ob'])
    p['sign'] = 1; set_blink(0.3); P1 = world_verts(p['ob'])
    _, ph0, _ = polar(P0, p['C'], p['A'], p['up'], p['fwd']); _, ph1, _ = polar(P1, p['C'], p['A'], p['up'], p['fwd'])
    if ph1.mean() > ph0.mean(): p['sign'] = -1
set_blink(0.0)

# ------------------------------------------------------------------ QA
def visible_fraction(P, normal_from):
    """Share of shell vertices seen from the front camera direction (not hidden by the face skin)."""
    vis = 0
    for q in P:
        org = Vector((q[0], q[1] - 0.5, q[2])); d = Vector((0, 1, 0))
        hf = bF.ray_cast(org, d)[0]
        if hf is None or hf.y > q[1] - 0.0002: vis += 1
    return vis / len(P)
def coverage(side):
    """Front rays through the eye opening: share that hit the shell (or skin) before the eyeball."""
    p = parts[side]; P = world_verts(p['ob']); F_ = [list(f.vertices) for f in p['ob'].data.polygons]
    bS = BVHTree.FromPolygons([Vector(v) for v in P], F_)
    raw = np.array(meta[side]['raw']); c = raw.mean(0); pts = c + (raw - c) * 0.9
    xs = np.linspace(pts[:, 0].min(), pts[:, 0].max(), 22); zs = np.linspace(pts[:, 2].min(), pts[:, 2].max(), 14)
    from_poly = []
    for x in xs:
        for z in zs:
            # inside the rim polygon (x-z)
            inside = False; j = len(pts) - 1
            for i in range(len(pts)):
                if (pts[i, 2] > z) != (pts[j, 2] > z) and x < (pts[j, 0] - pts[i, 0]) * (z - pts[i, 2]) / (pts[j, 2] - pts[i, 2] + 1e-12) + pts[i, 0]: inside = not inside
                j = i
            if not inside: continue
            org = Vector((x, -1.0, z)); d = Vector((0, 1, 0))
            he = bE.ray_cast(org, d)[0]; hs = bS.ray_cast(org, d)[0]; hf = bF.ray_cast(org, d)[0]
            ye = he.y if he else 9; ys = hs.y if hs else 9; yf = hf.y if hf else 9
            from_poly.append(min(ys, yf) < ye)
    return float(np.mean(from_poly)) if from_poly else 0.0
def inside_eye(side):
    P = world_verts(parts[side]['ob']); bad = 0
    for q in P[::3]:
        r = surf_radius(*[parts[side][k] for k in ('C', 'A', 'up', 'fwd')], *polar(q[None], parts[side]['C'], parts[side]['A'], parts[side]['up'], parts[side]['fwd'])[:2])
        if r is not None:
            _, _, rad = polar(q[None], parts[side]['C'], parts[side]['A'], parts[side]['up'], parts[side]['fwd'])
            if rad[0] < r - 0.0001: bad += 1
    return bad
for t in (0.0, 0.5, 1.0):
    set_blink(t)
    for side in parts:
        key = 'blink_%d' % int(t * 100)
        qa.setdefault(key, {})[side] = {'shell_inside_eyeball_verts': inside_eye(side)}
        if t == 0.0: qa[key][side]['shell_visible_share'] = visible_fraction(world_verts(parts[side]['ob']), None)
        if t == 1.0: qa[key][side]['eye_covered_share'] = coverage(side)
set_blink(0.0)
qa['face_untouched_max_mm'] = float(np.abs(np.array([tuple(v.co) for v in face.data.vertices]) - Fv0).max() * 1000)
json.dump(qa, open(os.path.join(OUT, 'qa_lids.json'), 'w'), indent=1)
json.dump({s: {'sign': p['sign'], 'alpha_b': [float(x) for x in p['alpha_b']], 'bones': NB} for s, p in parts.items()}, open(os.path.join(OUT, 'lid_pose.json'), 'w'))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'rig_lids.blend'))
print('QA', json.dumps(qa))
