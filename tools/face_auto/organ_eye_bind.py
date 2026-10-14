"""겹침생성 · bind the eyeballs to the Rigify face rig: each eyeball turns about its own centre with the eye controls.

The 'eyes' mesh (both eyeballs, organ_eye.py) had no weights and no modifier, so moving the 'eyes' / 'eye.L' / 'eye.R'
target controls of 'face_rig' turned nothing. In the generated rig the bone that turns is MCH-eye.L/R: it damped-tracks
the eye.L/R control (which hangs under the common 'eyes' control), so it turns about its own head; ORG-eye.L/R is its
child with the same head. Neither is a deform bone, so a DEF-eye.L/R deform bone (same head, tail and roll as ORG-eye,
in the DEF collection) is parented to ORG-eye.L/R and every vertex of an eyeball gets weight 1 on its side's bone
(side = nearer eyeball centre); an Armature modifier binds 'eyes'.
rigify_fit puts the MCH-eye / ORG-eye heads on the eyeball centre C of eyes.json. If one is off by more than 0.01 mm it
is moved onto C on its own (head and tail together, so its direction stays), with any bone that copies its location
(MCH-eye.*.001, the lid-follow helper) moved by the same amount so the lids stay put at rest; master_eye (the lid
master) is left alone.
The weight names carry .L/.R, so sym_lock.py 'weights' swaps them on the mirrored eyeball.
QA (<out>_eyebind.json): pivot offset, rest offset of eyes and face (armature at rest moves nothing), and three control moves -
'eyes' up 25 deg, 'eyes' toward the character's left 20 deg, eye.L alone up 25 deg - with each eyeball's turn
(elevation / azimuth of its forward direction, + = up / character's left), centre drift, and the left/right mirror
error of the symmetric move.
Usage: blender -b <rigify_mw.blend> -P organ_eye_bind.py -- <eyes.json from organ_eye> <out.blend>
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index('--') + 1:]
EJ, OUT = a[0], os.path.abspath(a[1])
E = json.load(open(EJ))['eyes']; Cs = {s: np.array(E[s]['C']) for s in 'LR'}
rig = bpy.data.objects['face_rig']; eyes = bpy.data.objects['eyes']; me = eyes.data
assert rig.matrix_world.is_identity and eyes.matrix_world.is_identity, 'rig and eyes are expected in head space'
X = np.array([tuple(v.co) for v in me.vertices])
side = np.where(np.linalg.norm(X - Cs['L'], axis=1) < np.linalg.norm(X - Cs['R'], axis=1), 'L', 'R')
qa = {'verts': {s: int((side == s).sum()) for s in 'LR'}}

# ---- deform bones under ORG-eye, pivot on the eyeball centre
for o in bpy.context.view_layer.objects: o.select_set(False)
rig.hide_set(False); rig.hide_viewport = False; bpy.context.view_layer.objects.active = rig; rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones; dcol = rig.data.collections_all.get('DEF')
qa['pivot_offset_mm'] = {}; qa['pivot_moved'] = []
for s in 'LR':
    qa['pivot_offset_mm'][s] = round(float(np.linalg.norm(Cs[s] - np.array(eb['MCH-eye.' + s].head)) * 1000), 4)
    MODULAR = 'DEF-eye.' + s in eb and eb['DEF-eye.' + s].parent is not None and eb['DEF-eye.' + s].parent.name == 'MCH-eye.' + s
    if MODULAR:                                          # modular face: moving MCH-eye turns its damped track at rest (lids move)
        eb['DEF-eye.' + s].use_deform = True; continue
    for n in ('MCH-eye.' + s, 'ORG-eye.' + s):           # parent first: a child keeps its own offset from C
        off = Vector(tuple(Cs[s] - np.array(eb[n].head)))
        if off.length <= 1e-5: continue
        for b in [eb[n]] + [eb[c.name] for c in rig.pose.bones if c.name in eb and any(k.type == 'COPY_LOCATION' and k.subtarget == n for k in c.constraints)]:
            b.head += off; b.tail += off; qa['pivot_moved'].append([b.name, round(off.length * 1000, 4)])
    org = eb['ORG-eye.' + s]
    d = eb.get('DEF-eye.' + s) or eb.new('DEF-eye.' + s)
    d.head, d.tail, d.roll = org.head.copy(), org.tail.copy(), org.roll
    d.parent = org; d.use_connect = False; d.use_deform = True
    if dcol: dcol.assign(d)
bpy.ops.object.mode_set(mode='OBJECT')
qa['pivot_after_mm'] = {s: round(float(max(np.linalg.norm(Cs[s] - np.array(rig.data.bones[n + s].head_local)) for n in ('MCH-eye.', 'ORG-eye.', 'DEF-eye.')) * 1000), 4) for s in 'LR'}

# ---- weights + modifier
for g in [g for g in eyes.vertex_groups if g.name.startswith('DEF-eye')]: eyes.vertex_groups.remove(g)
for s in 'LR':
    g = eyes.vertex_groups.new(name='DEF-eye.' + s); g.add(np.where(side == s)[0].tolist(), 1.0, 'REPLACE')
for m in [m for m in eyes.modifiers if m.type == 'ARMATURE']: eyes.modifiers.remove(m)
md = eyes.modifiers.new('rig', 'ARMATURE'); md.object = rig

# ---- QA: move the target controls, measure each eyeball's turn about C
pb = rig.pose.bones
def evaluate(o):
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg)
    return np.array([tuple(v.co) for v in ev.data.vertices])
def reset():
    for b in pb: b.location = (0, 0, 0); b.rotation_quaternion = (1, 0, 0, 0); b.rotation_euler = (0, 0, 0); b.scale = (1, 1, 1)
    bpy.context.view_layer.update()
def move(name, d):                                      # world (= armature) space translation of a control
    b = pb[name]; b.matrix = Matrix.Translation(Vector(d)) @ b.matrix; bpy.context.view_layer.update()
def turn(P0, P1, C):                                     # Kabsch rotation about C, forward (-y) -> elevation / azimuth
    H = (P0 - C).T @ (P1 - C); U, _, Vt = np.linalg.svd(H); Dg = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ Dg @ U.T; g = R @ np.array([0, -1.0, 0])
    return {'elev_deg': round(math.degrees(math.asin(np.clip(g[2], -1, 1))), 2), 'azim_deg': round(math.degrees(math.atan2(g[0], -g[1])), 2),
            'turn_deg': round(math.degrees(math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))), 2),
            'centre_drift_mm': round(float(np.linalg.norm(P1.mean(0) - P0.mean(0)) * 1000), 4),
            'fit_resid_mm': round(float(np.abs((P0 - C) @ R.T + C - P1).max() * 1000), 4)}
kd = KDTree(len(X))
for i, p in enumerate(X): kd.insert(Vector(tuple(p)), i)
kd.balance()
mi = np.array([kd.find(Vector((-p[0], p[1], p[2])))[1] for p in X])
face = bpy.data.objects['face']
reset(); F0 = evaluate(face); P_rest = evaluate(eyes)
qa['rest_offset_mm'] = round(float(np.abs(P_rest - X).max() * 1000), 5)
FX = np.array([tuple(d.co) for d in (face.data.shape_keys.key_blocks[0].data if face.data.shape_keys else face.data.vertices)])
qa['face_rest_offset_mm'] = round(float(np.abs(F0 - FX).max() * 1000), 5)      # a moved pivot must not move the lids at rest
EYES = 'eyes' if 'eyes' in pb else 'eye_common'             # super_face / modular (dense) face: the common eye target
dist = float(abs(pb[EYES].bone.head_local[1] - Cs['L'][1]))
tests = {'eyes_up25': [(EYES, (0, 0, dist * math.tan(math.radians(25))))],
         'eyes_left20': [(EYES, (dist * math.tan(math.radians(20)), 0, 0))],
         'eyeL_up25': [('eye.L', (0, 0, dist * math.tan(math.radians(25))))]}
qa['poses'] = {}
for tn, moves in tests.items():
    reset()
    for n, d in moves: move(n, d)
    P = evaluate(eyes); r = {s: turn(X[side == s], P[side == s], Cs[s]) for s in 'LR'}
    if tn == 'eyes_up25':                                # symmetric move: right eyeball = mirror of the left one
        r['mirror_err_mm'] = round(float(np.linalg.norm(P[mi] * np.array([-1, 1, 1]) - P, axis=1).max() * 1000), 4)
    r['face_max_move_mm'] = round(float(np.linalg.norm(evaluate(face) - F0, axis=1).max() * 1000), 2)   # Rigify lids follow the eye
    qa['poses'][tn] = r
reset()
qa['ok'] = bool(max(qa['pivot_after_mm'].values()) < 0.05 and qa['rest_offset_mm'] < 0.01 and qa['face_rest_offset_mm'] < 0.01
                and all(qa['poses'][t][s]['centre_drift_mm'] < 0.05 for t in tests for s in 'LR')
                and qa['poses']['eyes_up25']['mirror_err_mm'] < 0.05)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(qa, open(os.path.splitext(OUT)[0] + '_eyebind.json', 'w'), indent=1)
print('EYEBIND', json.dumps(qa))
