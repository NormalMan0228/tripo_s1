"""Restore the original face and demonstrate finger / limb articulation only."""
import bpy,math,json,sys
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
ROOT=Path(__file__).resolve().parents[1]
# Reuse only the verified hand/IK construction, stopping before all facial edits.
source=(ROOT/'tools/blender_detail_rig.py').read_text(encoding='utf-8')
assert '# Add a restrained jaw deformation' in source, 'Hand construction boundary missing'
source=source.split('# Add a restrained jaw deformation')[0]
source=source.replace("artifacts/characters/explorer-b-detailed-v2","artifacts/characters/explorer-b-body-v3")
exec(compile(source,'hand_rig_construction','exec'),globals())
OUT=ROOT/'artifacts/characters/explorer-b-body-v3'
rig.name='Explorer_B_Body_Rig'
bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for b in list(rig.data.edit_bones):
    if b.name.startswith('Face_'):rig.data.edit_bones.remove(b)
bpy.ops.object.mode_set(mode='OBJECT')
assert body.data.shape_keys is None
# Load the original analytic two-bone pose helpers, without invoking its build/export.
old=(ROOT/'tools/blender_explorer_b.py').read_text(encoding='utf-8')
snippet=old[old.index("pb=rig.pose.bones;"):old.index("scene=bpy.context.scene;scene.render.fps=24")]
TAU=math.tau
exec(compile(snippet,'original_body_pose_helpers','exec'),globals())
base_pose=pose
scene=bpy.context.scene;scene.render.fps=24
face_indices=[v.index for v in body.data.vertices if v.co.z>.76]
face_rest=[list(body.data.vertices[i].co) for i in face_indices]

def fingers(side,amount,individual=None):
    for digit in paths:
        value=individual.get(digit,0) if individual is not None else amount
        for i,n in enumerate(finger_specs[(side,digit)][1]):
            # Moderate grasp avoids the former over-tight fist and thumb folding.
            b=pb[n];b.rotation_mode='QUATERNION'
            b.rotation_quaternion=Quaternion(Vector((1,0,0)),-math.radians(([16,25,18] if digit=='Thumb' else [28,42,28])[i])*value)

def body_pose(kind,t,duration):
    base_pose('scout',0)
    for b in pb:
        if b.name.startswith('CTRL_'):b.matrix_basis=Matrix.Identity(4)
    if kind=='hands':
        for side,sign in [('L',1),('R',-1)]:
            chain(side+'_Upperarm',side+'_Forearm',side+'_Hand',Vector((.11,sign*.15,.67)),(-.6,sign*.7,-.2))
            grip=envelope(t,.35,.85,1.45,2.0)
            if t<2:fingers(side,grip)
            else:
                values={digit:envelope(t,2+i*.22,2.2+i*.22,2.7+i*.22,3.0+i*.22) for i,digit in enumerate(paths)}
                fingers(side,0,values)
            rotate_inherited(side+'_Hand',rot((0,1,0),8*math.sin(math.tau*t/duration)))
    elif kind=='reach':
        reach=envelope(t,.35,1.15,2.4,3.6)
        for side,sign in [('L',1),('R',-1)]:
            wrist=Vector((.022,sign*.16,.507)).lerp(Vector((.135,sign*.095,.647)),reach)
            chain(side+'_Upperarm',side+'_Forearm',side+'_Hand',wrist,(-.7,sign*.7,-.25))
            fingers(side,envelope(t,1.05,1.55,2.15,2.85)*.8)
        rotate_inherited('Head',rot((0,1,0),4*reach))
    else:
        crouch=envelope(t,.35,1.15,1.65,2.45)
        step=envelope(t,3.0,3.65,4.25,5.5)
        m=pb['Hip'].matrix.copy();m.translation+=Vector((-.015*crouch,.019*step,-.075*crouch));pb['Hip'].matrix=m;update()
        rotate_inherited('Waist',rot((0,1,0),6*crouch))
        rotate_inherited('Spine01',rot((0,1,0),4*crouch))
        rotate_inherited('Head',rot((0,1,0),-6*crouch))
        for side,sign in [('L',1),('R',-1)]:
            target=heads[side+'_Foot'].copy()
            if side=='R':target+=Vector((.060*step,0,.065*step))
            end=chain(side+'_Thigh',side+'_Calf',side+'_Foot',target,(1,0,.05))
            pb[side+'_Foot'].matrix=Matrix.Translation(end)@rest[side+'_Foot'].to_3x3().to_4x4();update()
            wrist=Vector((.02+.045*crouch,sign*(.16+.025*step),.507-.045*crouch))
            chain(side+'_Upperarm',side+'_Forearm',side+'_Hand',wrist,(-.7,sign*.7,-.25))
            fingers(side,.12)
    update()

clips=[('Hands_Open_Grasp','hands',4),('Arms_Reach_Grip','reach',4),('Legs_Crouch_Step','legs',6)]
rig.animation_data_clear();rig.animation_data_create()
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
stats={}
for name,kind,duration in clips:
    rig.animation_data.action=None;previous={}
    for frame in range(duration*24+1):
        body_pose(kind,frame/24,duration)
        for b in pb:
            if b.name.startswith('CTRL_'):continue
            b.rotation_mode='QUATERNION';q=b.rotation_quaternion
            if b.name in previous and q.dot(previous[b.name])<0:q.negate()
            previous[b.name]=q.copy()
            b.keyframe_insert('location',frame=frame+1,group=b.name);b.keyframe_insert('rotation_quaternion',frame=frame+1,group=b.name)
    action=rig.animation_data.action;action.name=name;action.use_fake_user=True
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for k in fc.keyframe_points:k.interpolation='LINEAR'
    stats[name]={'duration_seconds':duration}
rig.animation_data.action=bpy.data.actions['Arms_Reach_Grip'];scene.frame_start=1;scene.frame_end=97;scene.frame_set(1)
rig.data.display_type='STICK';rig.show_in_front=True
for title in ['Body','Fingers','IK Controls']:
    collection=rig.data.collections.get(title) or rig.data.collections.new(title)
    for b in rig.data.bones:
        category='IK Controls' if b.name.startswith('CTRL_') else 'Fingers' if any(d in b.name for d in paths) else 'Body'
        if category==title:collection.assign(b)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer-b-body.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_anim_slide_to_zero=True,export_def_bones=True)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-body.blend'))
assert face_rest==[list(body.data.vertices[i].co) for i in face_indices]
report={'face':'Original B-v1 geometry, UV, texture and weights; no added eyes/lids/mouth, no face shape keys or face bones.','bones':len(rig.data.bones),'deform_bones':sum(b.use_deform for b in rig.data.bones),'finger_bones':30,'ik_controls':8,'clips':stats,'api_credits_spent':0,'external_face_tool_used':False}
(OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene.cycles.samples=14;scene.render.resolution_x=800;scene.render.resolution_y=800
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU'
cam=scene.camera
for name,action,frame,target,offset,scale in [('restored-face','Arms_Reach_Grip',1,(0,0,.823),(3,0,.1),.30),('reach','Arms_Reach_Grip',40,(0,0,.54),(3,-3,1.1),1.18),('crouch','Legs_Crouch_Step',33,(0,0,.48),(3,-3,1.1),1.18),('step','Legs_Crouch_Step',97,(0,0,.5),(3,-3,1.1),1.18),('hands','Hands_Open_Grasp',25,(.09,.17,.65),(2,-3,2),.24)]:
    rig.animation_data.action=bpy.data.actions[action];scene.frame_set(frame);target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
print('BODY_ONLY_V3_READY',json.dumps(report))
