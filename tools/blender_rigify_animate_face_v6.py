"""Generate a real Rigify control rig for the repaired Tripo face, then animate its controls."""
import bpy,addon_utils,math,json
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_animated_v6';bpy.ops.wm.open_mainfile(filepath=str(A/'face_repaired_workbench.blend'));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];ctrl=bpy.data.objects['FACE_CONTROLS'];addon_utils.enable('rigify',default_set=False,persistent=False);assert addon_utils.check('rigify')[1]
bpy.context.preferences.filepaths.save_version=0
arm=bpy.data.armatures.new('Explorer_Face_Metarig');meta=bpy.data.objects.new('Explorer_Face_Metarig',arm);sc.collection.objects.link(meta);bpy.ops.object.select_all(action='DESELECT');meta.select_set(True);bpy.context.view_layer.objects.active=meta;bpy.ops.object.mode_set(mode='EDIT')
def bone(name,a,b,parent=None):
 e=arm.edit_bones.new(name);e.head=a;e.tail=b
 if parent:e.parent=arm.edit_bones[parent]
 return e
bone('head',(.02,0,-.14),(.02,0,.18))
for side in ('L','R'):
 eye=bpy.data.objects['EYEBALL_'+side];p=eye.location.copy();bone('eye.'+side,p,p+Vector((.07,0,0)),'head');sign=1 if side=='L' else -1;bone('blink.'+side,(.34,sign*.12,.17),(.34,sign*.12,.205),'head')
bone('jaw',(.34,0,-.10),(.34,0,-.05),'head');bone('smile',(.34,0,-.015),(.34,0,.02),'head');bpy.ops.object.mode_set(mode='OBJECT')
collection=arm.collections.new('Face Controls');collection.rigify_ui_row=1
for b in arm.bones:collection.assign(b)
for pb in meta.pose.bones:
 pb.rigify_type='basic.super_copy';pb.rigify_parameters.make_control=True;pb.rigify_parameters.make_widget=True;pb.rigify_parameters.make_deform=pb.name in {'head','eye.L','eye.R'};pb.rigify_parameters.super_copy_widget_type='circle'
bpy.ops.object.mode_set(mode='POSE');bpy.ops.pose.rigify_generate();bpy.ops.object.mode_set(mode='OBJECT');rig=bpy.context.view_layer.objects.active;assert rig!=meta and rig.type=='ARMATURE';rig.name='Explorer_B_Rigify_Face_Rig';rig.show_in_front=True;meta.hide_render=True;meta.hide_set(True)
for col in bpy.data.collections:
 if col.name.startswith('WGTS'):col.hide_render=True;col.hide_viewport=True
beforeeye={side:bpy.data.objects['EYEBALL_'+side].matrix_world.copy() for side in ('L','R')}
for side in ('L','R'):
 eye=bpy.data.objects['EYEBALL_'+side];eye.parent=rig;eye.parent_type='BONE';eye.parent_bone='DEF-eye.'+side;eye.matrix_world=beforeeye[side]
# Skin, hair, brow, lashes and oral parts follow the generated head deformation bone.
rigged=[]
for o in list(sc.objects):
 if o.type!='MESH' or o.hide_render or o.hide_get() or o.name.startswith(('EYEBALL_','IRIS_','EYE_CATCHLIGHT_','WGT')):continue
 world=o.matrix_world.copy();o.parent=rig;o.matrix_world=world;g=o.vertex_groups.new(name='DEF-head');g.add(list(range(len(o.data.vertices))),1.,'REPLACE');mod=o.modifiers.new('Rigify_head_deform','ARMATURE');mod.object=rig;rigged.append(o.name)
bpy.context.view_layer.update();eyeerror=max((bpy.data.objects['EYEBALL_'+side].matrix_world.translation-beforeeye[side].translation).length for side in ('L','R'));assert eyeerror<1e-5,eyeerror
def property_driver(prop,bone_name,field):
 dr=ctrl.driver_add('["'+prop+'"]').driver;dr.expression='v';var=dr.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='pose.bones["'+bone_name+'"]["'+field+'"]'
for side in ('L','R'):
 pb=rig.pose.bones['blink.'+side];pb['blink']=0.;pb.id_properties_ui('blink').update(min=0,max=1,description='0 open, 1 closed; corrective arc keeps lids outside the eyeball');property_driver('blink_'+side,'blink.'+side,'blink')
pb=rig.pose.bones['jaw'];pb['mouth_open']=0.;pb.id_properties_ui('mouth_open').update(min=0,max=1,description='0 sealed smile, 1 original generated mouth interior');property_driver('mouth_open','jaw','mouth_open')
smile=head.shape_key_add(name='Smile_soft');basis=head.data.shape_keys.key_blocks[0]
for v,b in zip(smile.data,basis.data):
 c=b.co;w=math.exp(-((abs(c.y)-.084)/.034)**2-((c.z+.066)/.027)**2)*max(0,min(1,(c.x-.16)/.065));v.co.z+=.0025*w
sp=rig.pose.bones['smile'];sp['smile']=0.;sp.id_properties_ui('smile').update(min=0,max=1);dr=smile.driver_add('value').driver;dr.expression='v';var=dr.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='pose.bones["smile"]["smile"]'
sc.render.fps=30;sc.frame_start=1;sc.frame_end=360
def keyprop(pb,name,points):
 for frame,value in points:pb[name]=float(value);pb.keyframe_insert(data_path='["'+name+'"]',frame=frame)
blinks=[(1,0),(70,0),(74,1),(80,0),(172,0),(176,1),(182,0),(292,0),(296,1),(302,0),(360,0)]
for side in ('L','R'):keyprop(rig.pose.bones['blink.'+side],'blink',blinks)
keyprop(rig.pose.bones['jaw'],'mouth_open',[(1,0),(190,0),(213,.28),(239,.28),(267,0),(360,0)])
keyprop(sp,'smile',[(1,0),(120,.22),(190,.22),(270,.18),(360,0)])
for side in ('L','R'):
 pb=rig.pose.bones['eye.'+side];pb.rotation_mode='QUATERNION';rest=rig.data.bones[pb.name].matrix_local.to_quaternion()
 for frame,yaw,pitch in [(1,0,0),(37,0,0),(58,7,1),(104,7,1),(130,-7,-1),(159,-7,-1),(187,0,0),(270,0,0),(313,3,1),(338,0,0),(360,0,0)]:
  world=Quaternion(Vector((0,0,1)),math.radians(yaw))@Quaternion(Vector((0,1,0)),math.radians(-pitch));pb.rotation_quaternion=rest.inverted()@world@rest;pb.keyframe_insert(data_path='rotation_quaternion',frame=frame)
hp=rig.pose.bones['head'];hp.rotation_mode='QUATERNION';rest=rig.data.bones['head'].matrix_local.to_quaternion()
for frame,yaw,pitch in [(1,0,0),(90,-1,1.5),(180,1,-1),(270,.5,.8),(360,0,0)]:
 hp.rotation_quaternion=rest.inverted()@Quaternion(Vector((0,0,1)),math.radians(yaw))@Quaternion(Vector((0,1,0)),math.radians(pitch))@rest;hp.keyframe_insert(data_path='rotation_quaternion',frame=frame)
action=rig.animation_data.action;action.name='Explorer_B_Face_Demo_12s'
def curves(action):
 if hasattr(action,'fcurves'):return list(action.fcurves)
 return [f for layer in action.layers for strip in layer.strips for bag in strip.channelbags for f in bag.fcurves]
for fc in curves(action):
 for k in fc.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
sc.frame_set(1);bpy.context.view_layer.update();assert abs(ctrl['mouth_open'])<1e-7
for n,f in [('blink',74),('gaze_left',104),('mouth_open',226),('rest',1)]:sc.timeline_markers.new(n,frame=f)
notes=bpy.data.texts.new('V6_FACE_CONTROLS');notes.write('Actual Rigify-generated custom facial control rig on the repaired Tripo mesh. Space plays 12 seconds at 30 fps. Frame 1 is the default sealed gentle smile. Pose bones blink.L/R: blink slider. jaw: mouth_open slider. smile: smile slider. eye.L/R: rotate for gaze. head: rotate for head motion. Eyelid closure uses local shape keys with an arc corrective; no MPFB template target transfer is claimed. Original v5 is unchanged.\n')
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   space=area.spaces.active;space.shading.type='MATERIAL';space.region_3d.view_rotation=sc.camera.rotation_euler.to_quaternion();space.region_3d.view_location=(0,0,.04);space.region_3d.view_distance=1.65;space.region_3d.view_perspective='ORTHO';space.overlay.show_extras=False
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
report={'addon':'Rigify','actual_generated_rig':True,'rig_object':rig.name,'rig_bones':len(rig.data.bones),'rigged_objects':rigged,'eye_parent_rest_error':eyeerror,'animation':action.name,'fps':30,'frames':360,'duration_seconds':12,'interpolation':'Bezier Auto Clamped','mpfb_template_targets_transferred':False,'audio_lipsync':False,'new_Tripo_credits':0};(A/'rigify-report.json').write_text(json.dumps(report,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(A/'explorer_b_repaired_rigify_v6.blend'));print('RIGIFY_V6_READY',json.dumps(report))
