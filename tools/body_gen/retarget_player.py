"""Turn a Tripo Mixamo-rigged character into a player GLB: rename the bones to the names the game
uses (player.gd / action_pose.gd look for R_Hand, Head, Spine02, R_Upperarm, R_Forearm) and copy the
current player clips (idle, walk, run, slash from game/assets/explorer.glb) onto it.

  blender -b --factory-startup -P tools/body_gen/retarget_player.py -- <character.glb|fbx> <out.glb> [source.glb]

Retargeting is done in world space per mapped bone: the source bone's rotation away from its rest
pose is applied to the target bone after the target rest is turned to point the same way as the
source rest (limbs only, so an A-pose and a T-pose rest give the same motion). Unmapped bones
(fingers, toe ends) follow their parents. The hips also take the source hip's movement, scaled by
the hip-height ratio.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion

a = sys.argv[sys.argv.index('--') + 1:]
src_char, out = a[0], a[1]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src_anim = a[2] if len(a) > 2 else os.path.join(ROOT, 'game', 'assets', 'explorer.glb')
CLIPS = ['idle', 'walk', 'run', 'slash']
# The source run leans and crouches hard; on longer-legged bodies that reads as sitting, so the
# body lean (hip and spine rotation away from rest) and the hip drop are scaled down per clip.
DAMP = {}
# run = the walk sampled 1.7x faster (the source run's high-knee
# crouch reads as sitting on adult proportions)
RUN_FROM_WALK = (1.7, 0.0)
DAMP_BONES = ('Hip', 'Waist', 'Spine01', 'Spine02')
# Mixamo base name -> (game bone name, source bone, align the rest direction)
MAP = {
    'Hips': ('Hip', 'Hip', False), 'Spine': ('Waist', 'Waist', False), 'Spine1': ('Spine01', 'Spine01', False),
    'Spine2': ('Spine02', 'Spine02', False), 'Neck': ('NeckTwist01', 'NeckTwist01', False), 'Head': ('Head', 'Head', False),
}
for side, s in (('Left', 'L'), ('Right', 'R')):
    MAP.update({
        side + 'Shoulder': (s + '_Clavicle', s + '_Clavicle', True), side + 'Arm': (s + '_Upperarm', s + '_Upperarm', True),
        side + 'ForeArm': (s + '_Forearm', s + '_Forearm', True), side + 'Hand': (s + '_Hand', s + '_Hand', True),
        side + 'UpLeg': (s + '_Thigh', s + '_Thigh', True), side + 'Leg': (s + '_Calf', s + '_Calf', True),
        side + 'Foot': (s + '_Foot', s + '_Foot', False), side + 'ToeBase': (s + '_ToeBase', s + '_ToeBase', False),
    })


def imp(path):
    before = set(bpy.data.objects)
    if path.lower().endswith('.fbx'):
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    else:
        bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    return [o for o in new if o.type == 'ARMATURE'][0], new


def rot(m):
    return m.to_3x3().normalized().to_quaternion()


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
T, t_objs = imp(src_char)
for b in T.data.bones:  # mixamorig:Hips / mixamorig_Hips / Hips -> game names
    base = b.name.split(':')[-1].replace('mixamorig_', '')
    if base in MAP:
        b.name = MAP[base][0]
if T.animation_data:
    T.animation_data.action = None
    for tr in list(T.animation_data.nla_tracks):
        T.animation_data.nla_tracks.remove(tr)
for act in list(bpy.data.actions):
    bpy.data.actions.remove(act)
S, s_objs = imp(src_anim)
acts = {act.name.split('|')[-1]: act for act in bpy.data.actions}
if S.animation_data:
    S.animation_data.action = None
    sc.frame_set(0)
if S.animation_data:  # the importer stacks every clip on NLA tracks; sample only the active action
    for tr in list(S.animation_data.nla_tracks):
        S.animation_data.nla_tracks.remove(tr)
pairs = [(MAP[k][0], MAP[k][1], MAP[k][2]) for k in MAP]
pairs = [p for p in pairs if p[0] in T.data.bones and p[1] in S.data.bones]
print('mapped', len(pairs), 'of', len(MAP))
Tmw, Smw = T.matrix_world.copy(), S.matrix_world.copy()  # import-time frames: clips that also move the armature object are read relative to it
Tq = rot(Tmw)
s_rest = {sb: rot(Smw @ S.data.bones[sb].matrix_local) for _, sb, _ in pairs}
align = {}
for tb, sb, al in pairs:
    if al:
        td = (Tmw.to_3x3() @ (T.data.bones[tb].tail_local - T.data.bones[tb].head_local)).normalized()
        sd = (Smw.to_3x3() @ (S.data.bones[sb].tail_local - S.data.bones[sb].head_local)).normalized()
        align[tb] = td.rotation_difference(sd)
    else:
        align[tb] = Quaternion()
src_of = {tb: sb for tb, sb, _ in pairs}
s_hip0 = Smw @ S.data.bones['Hip'].head_local
t_hip0 = Tmw @ T.data.bones['Hip'].head_local
ratio = (t_hip0.z - min((Tmw @ b.head_local).z for b in T.data.bones)) / max(1e-4, s_hip0.z - min((Smw @ b.head_local).z for b in S.data.bones))
order = []
def walk_bones(b):
    order.append(b)
    for c in b.children:
        walk_bones(c)
for b in T.data.bones:
    if b.parent is None:
        walk_bones(b)
for pb in T.pose.bones:
    pb.rotation_mode = 'QUATERNION'
T.animation_data_create()
made = []
made_acts = {}
for clip in CLIPS:
    if clip == 'run' and RUN_FROM_WALK:
        continue
    src = acts.get(clip)
    if not src:
        print('missing source clip', clip)
        continue
    S.animation_data.action = src
    f0, f1 = int(src.frame_range[0]), int(src.frame_range[1])
    act = bpy.data.actions.new(clip)
    T.animation_data.action = act
    step = RUN_FROM_WALK[0] if clip == 'run' and RUN_FROM_WALK else 1.0
    lean = Quaternion((1, 0, 0), math.radians(RUN_FROM_WALK[1])) if clip == 'run' and RUN_FROM_WALK and RUN_FROM_WALK[1] else None
    for k in range(int((f1 - f0) / step) + 1):
        t = f0 + k * step
        f = f0 + k
        sc.frame_set(int(t), subframe=t - int(t))
        P = {}
        fix = lean
        if clip in DAMP:  # stand the whole pose up by part of the hip's lean (legs included)
            Dh = rot(Smw @ S.pose.bones['Hip'].matrix) @ s_rest['Hip'].inverted()
            fix = Quaternion().slerp(Dh.inverted(), 1 - DAMP[clip])
        for b in order:
            rest = b.matrix_local
            base = P[b.parent.name] @ b.parent.matrix_local.inverted() @ rest if b.parent else rest.copy()
            M = base
            if b.name in src_of:
                sb = src_of[b.name]
                spb = S.pose.bones[sb]
                D = rot(Smw @ spb.matrix) @ s_rest[sb].inverted()
                if fix is not None:
                    D = fix @ D
                want = D @ align[b.name] @ rot(Tmw @ rest)
                R = (Tq.inverted() @ want).to_matrix().to_4x4()
                head = base.to_translation()
                if b.name == 'Hip':
                    disp = (Smw @ spb.head) - s_hip0
                    if clip in DAMP:
                        disp.z *= DAMP[clip]
                    head = Tmw.inverted() @ (t_hip0 + disp * ratio)
                M = Matrix.Translation(head) @ R
            P[b.name] = M
            pb = T.pose.bones[b.name]
            pb.matrix_basis = base.inverted() @ M
            pb.keyframe_insert('rotation_quaternion', frame=f, group=b.name)
            if b.name == 'Hip':
                pb.keyframe_insert('location', frame=f, group=b.name)
    act.use_fake_user = True
    made_acts[clip] = act
    made.append((clip, k + 1))
if RUN_FROM_WALK and 'walk' in made_acts:  # run = the retargeted walk played RUN_FROM_WALK[0] times faster
    run = made_acts['walk'].copy()
    run.name = 'run'
    w0 = made_acts['walk'].frame_range[0]
    for fc in run.fcurves:
        for kp in fc.keyframe_points:
            for pt in (kp.co, kp.handle_left, kp.handle_right):
                pt.x = w0 + (pt.x - w0) / RUN_FROM_WALK[0]
    made_acts['run'] = run
    made.append(('run', int(run.frame_range[1] - run.frame_range[0]) + 1))
print('clips', made)
for o in s_objs:
    bpy.data.objects.remove(o, do_unlink=True)
for act in [x for x in bpy.data.actions if x not in made_acts.values()]:
    bpy.data.actions.remove(act)
T.animation_data.action = None
for clip, _ in made:  # one NLA track per clip: the exporter writes each track as an animation of that name
    tr = T.animation_data.nla_tracks.new()
    tr.name = clip
    st = tr.strips.new(clip, int(made_acts[clip].frame_range[0]), made_acts[clip])
    st.name = clip
bpy.ops.object.select_all(action='DESELECT')
for o in t_objs:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out, use_selection=True, export_animations=True,
                          export_animation_mode='NLA_TRACKS', export_force_sampling=True)
print('WROTE', out)
