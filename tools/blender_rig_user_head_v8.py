import bpy,addon_utils,json,math,numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(A/'lids_repaired_workbench.blend'));addon_utils.enable('rigify',persistent=True)
from bl_ext.user_default.mpfb.services.faceservice import FaceService
sc=bpy.context.scene;head=bpy.data.objects['FACE_user_head'];meshes=[o for o in sc.objects if o.type=='MESH'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh']
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
# Finish the sealed resting lip contact while retaining the original open pose.
keys=head.data.shape_keys.key_blocks;basis=keys[0]
def bvh(o,coords=None):
 o.data.calc_loop_triangles();return BVHTree.FromPolygons(coords or [o.matrix_world@v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
# Fit hair in surface-normal direction, keeping the overall bob silhouette.
skin=bvh(head,[p.co for p in basis.data]);moved=0;inv=hair.matrix_world.inverted().to_3x3()
for v in hair.data.vertices:
 p=hair.matrix_world@v.co
 if not (p.x>.06 and abs(p.y)<.32 and -.20<p.z<.33):continue
 q,n,_,dist=skin.find_nearest(p)
 if q is None or dist>.025 or q.x<.10:continue
 signed=(p-q).dot(n)
 if -.022<signed<.003:v.co+=inv@(n*(.004-signed));moved+=1
arm=bpy.data.armatures.new('New_Head_Metarig');meta=bpy.data.objects.new('New_Head_Metarig',arm);sc.collection.objects.link(meta);bpy.ops.object.select_all(action='DESELECT');meta.select_set(True);bpy.context.view_layer.objects.active=meta;bpy.ops.object.mode_set(mode='EDIT')
def bone(n,a,b,parent=None):
 e=arm.edit_bones.new(n);e.head=a;e.tail=b
 if parent:e.parent=arm.edit_bones[parent]
bone('head',(0,0,-.20),(0,0,.20))
for side in ['L','R']:
 eye=bpy.data.objects['EYEBALL_'+side];p=eye.location;bone('eye.'+side,p,p+Vector((.06,0,0)),'head');sgn=1 if side=='L' else -1;bone('blink.'+side,(.35,sgn*.14,.17),(.35,sgn*.14,.20),'head')
bone('jaw',(.35,0,-.16),(.35,0,-.10),'head');bpy.ops.object.mode_set(mode='OBJECT');col=arm.collections.new('Face Controls');col.rigify_ui_row=1
for b in arm.bones:col.assign(b)
for pb in meta.pose.bones:pb.rigify_type='basic.super_copy';pb.rigify_parameters.make_control=True;pb.rigify_parameters.make_widget=True;pb.rigify_parameters.make_deform=pb.name=='head' or pb.name.startswith('eye.');pb.rigify_parameters.super_copy_widget_type='circle'
bpy.ops.object.mode_set(mode='POSE');bpy.ops.pose.rigify_generate();bpy.ops.object.mode_set(mode='OBJECT');rig=bpy.context.view_layer.objects.active;rig.name='User_Head_Rigify_Face';rig.show_in_front=True;meta.hide_render=True;meta.hide_set(True)
for c in bpy.data.collections:
 if c.name.startswith('WGTS'):c.hide_render=True;c.hide_viewport=True
for o in meshes:
 if o.name.startswith(('IRIS_','EYE_CATCHLIGHT_')):continue
 world=o.matrix_world.copy()
 if o.name.startswith('EYEBALL_'):o.parent=rig;o.parent_type='BONE';o.parent_bone='DEF-eye.'+o.name[-1];o.matrix_world=world
 else:
  o.parent=rig;o.matrix_world=world;g=o.vertex_groups.get('DEF-head') or o.vertex_groups.new(name='DEF-head');g.add(list(range(len(o.data.vertices))),1.,'REPLACE');m=o.modifiers.new('Rigify_head','ARMATURE');m.object=rig
presets={'Neutral':{},'Happy':{'mouthSmileLeft':.32,'mouthSmileRight':.32,'cheekSquintLeft':.12,'cheekSquintRight':.12},'Concern':{'mouthFrownLeft':.45,'mouthFrownRight':.45,'browInnerUp':.65},'Determined':{'browDownLeft':.50,'browDownRight':.50,'mouthPressLeft':.20,'mouthPressRight':.20},'Surprise':{'browOuterUpLeft':.70,'browOuterUpRight':.70,'browInnerUp':.25,'eyeWideLeft':.1,'eyeWideRight':.1}}
faceobjects=[o for o in meshes if o.data.shape_keys and any(k.name.startswith('!ex-') for k in o.data.shape_keys.key_blocks)];applied={}
for name,expression in presets.items():
 for o in faceobjects:FaceService.clear_expression(o);FaceService.set_expression(o,expression)
 applied[name]=FaceService.read_current_expression(head)
for o in faceobjects:FaceService.clear_expression(o)
props=sorted({k.name[4:] for o in faceobjects for k in o.data.shape_keys.key_blocks if k.name.startswith('!ex-')});hp=rig.pose.bones['head']
for p in props:hp[p]=0.;hp.id_properties_ui(p).update(min=0,max=1)
jaw=rig.pose.bones['jaw'];jaw['jawOpen']=0.;jaw.id_properties_ui('jawOpen').update(min=0,max=1)
for side in ['L','R']:pb=rig.pose.bones['blink.'+side];pb['blink']=0.;pb.id_properties_ui('blink').update(min=0,max=1)
def drive(k,pb,prop,expr='v'):
 k.driver_remove('value');d=k.driver_add('value').driver;d.expression=expr;v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["'+pb+'"]["'+prop+'"]'
for o in meshes:
 if not o.data.shape_keys:continue
 for k in o.data.shape_keys.key_blocks:
  if k.name=='Mouth_open_original':drive(k,'jaw','jawOpen')
  elif k.name.startswith('!ex-eyeBlink'):side='L' if k.name.endswith('Left') else 'R';drive(k,'blink.'+side,'blink')
  elif k.name in {'Blink_L','Blink_R'}:drive(k,'blink.'+k.name[-1],'blink')
  elif k.name.startswith('Blink_arc_'):side=k.name[-1];drive(k,'blink.'+side,'blink','4*v*(1-v)')
  elif k.name.startswith('!ex-'):drive(k,'head',k.name[4:])
poses=[(1,'Neutral'),(55,'Neutral'),(80,'Happy'),(110,'Happy'),(155,'Neutral'),(180,'Concern'),(210,'Concern'),(255,'Neutral'),(280,'Determined'),(310,'Determined'),(355,'Neutral'),(380,'Surprise'),(410,'Surprise'),(470,'Neutral'),(540,'Neutral')]
for p in props:
 for f,name in poses:hp[p]=float(applied[name].get(p,0));hp.keyframe_insert(data_path='["'+p+'"]',frame=f)
for f,name in poses:jaw['jawOpen']=float(.7 if name=='Surprise' else 0.);jaw.keyframe_insert(data_path='["jawOpen"]',frame=f)
for side in ['L','R']:
 pb=rig.pose.bones['blink.'+side]
 for f,v in [(1,0),(43,0),(47,1),(53,0),(143,0),(147,1),(153,0),(243,0),(247,1),(253,0),(343,0),(347,1),(353,0),(463,0),(467,1),(473,0),(540,0)]:pb['blink']=float(v);pb.keyframe_insert(data_path='["blink"]',frame=f)
 pb=rig.pose.bones['eye.'+side];pb.rotation_mode='QUATERNION';rest=rig.data.bones[pb.name].matrix_local.to_quaternion()
 for f,angle in [(1,0),(120,3),(200,0),(320,-3),(420,0),(540,0)]:pb.rotation_quaternion=rest.inverted()@Quaternion(Vector((0,0,1)),math.radians(angle))@rest;pb.keyframe_insert(data_path='rotation_quaternion',frame=f)
action=rig.animation_data.action;action.name='MPFB_Rigify_New_Head_18s';action.use_fake_user=True;curves=list(action.fcurves) if hasattr(action,'fcurves') else [fc for l in action.layers for s in l.strips for b in s.channelbags for fc in b.fcurves]
for fc in curves:
 for k in fc.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
sc.frame_start=1;sc.frame_end=540;sc.render.fps=30;sc.timeline_markers.clear()
for f,n in [(1,'Neutral'),(95,'Happy'),(195,'Concern'),(295,'Determined'),(395,'Surprise')]:sc.timeline_markers.new(n,frame=f)
cam=sc.camera;cam.location=(3,0,0);cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.20
for n,f in [('neutral',1),('happy',95),('concern',195),('determined',295),('surprise',395),('blink_half',45),('blink_closed',47)]:
 sc.frame_set(f);bpy.context.view_layer.update();sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(A/'user_head_mpfb_rigify_v8.blend'));(A/'rig-report.json').write_text(json.dumps({'Rigify_generated':True,'rig':rig.name,'bone_count':len(rig.data.bones),'MPFB_FaceService_presets_evaluated':True,'MPFB_retarget_units':props,'presets':presets,'blink':'locally fitted eyelid closure and arc corrective for generated globes','jaw':'original open-mouth pose restored from sealed basis','hair_adjusted_vertices':moved,'duration':18,'new_Tripo_credits':0},indent=2));print('V8_RIG_READY')
