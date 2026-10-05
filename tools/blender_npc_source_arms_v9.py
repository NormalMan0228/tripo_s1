import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path(__file__).resolve().parents[1];OLD=R/'art/characters/npc_cast_idle_v8';OUT=R/'art/characters/npc_cast_idle_v9';OUT.mkdir(exist_ok=True)
def fit(rig,mesh,h):
 original=rig.data.pose_position;rig.data.pose_position='REST';names={g.index:g.name for g in mesh.vertex_groups};fitted={}
 for side,sign in [('L',1),('R',-1)]:
  ids=[v.index for v in mesh.data.vertices if sign*v.co.y>.13*h and -.12*h<v.co.x<.04*h and sum(g.weight for g in v.groups if names[g.group] in ['UpperArm.'+side,'Forearm.'+side,'Hand.'+side])>.65]
  cloud=np.array([mesh.data.vertices[i].co[:] for i in ids])
  def section(z,window=.018):
   p=cloud[np.abs(cloud[:,2]-z)<window*h]
   return Vector((float(np.median(p[:,0])),float(np.median(p[:,1])),z)) if len(p)>6 else None
  upper=rig.data.bones['UpperArm.'+side];fore=rig.data.bones['Forearm.'+side];hand=rig.data.bones['Hand.'+side]
  shoulder=section(upper.head_local.z-.02*h) or upper.head_local.copy();shoulder.z=upper.head_local.z
  elbow=section(fore.head_local.z) or fore.head_local.copy();wrist=section(hand.head_local.z) or hand.head_local.copy()
  palm=section(hand.tail_local.z) or hand.tail_local.copy();fitted[side]=(shoulder,elbow,wrist,palm)
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
 for side,(a,b,c,d) in fitted.items():
  rig.data.edit_bones['Shoulder.'+side].tail=a
  for name,start,end in [('UpperArm',a,b),('Forearm',b,c),('Hand',c,d)]:
   bone=rig.data.edit_bones[name+'.'+side];bone.head=start;bone.tail=end;bone.align_roll(Vector((1,0,0)))
 bpy.ops.object.mode_set(mode='OBJECT');rig.data.pose_position=original
 return {s:[list(p) for p in chain] for s,chain in fitted.items()}
reports={}
for key,h in [('sora',1.65),('moru',1.65),('naru',1.55),('haeru',1.85)]:
 D=OUT/key;D.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(OLD/key/(key+'_rigged_idle.blend')))
 scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in scene.objects if o.type=='MESH');source=np.array([v.co[:] for v in mesh.data.vertices]);fitting=fit(rig,mesh,h)
 action=rig.animation_data.action;action.name='Idle_'+key.capitalize()+'_SourceArms'
 for frame in range(1,242,2):
  scene.frame_set(frame);sec=(frame-1)/30;pulse=math.sin(math.pi*sec/8)**2
  for side,sign in [('L',1),('R',-1)]:
   for segment in ['Shoulder','UpperArm','Forearm','Hand']:
    pb=rig.pose.bones[segment+'.'+side];pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion();pb.location=(0,0,0)
    if segment=='UpperArm':
     # Lower the whole arm as one rigid chain. Forearm and wrist retain their source relationship.
     pb.rotation_quaternion=Quaternion(pb.bone.matrix_local.to_quaternion().inverted()@Vector((1,0,0)),math.radians(-sign*12))
    if side=='L' and key in ['sora','moru'] and segment in ['UpperArm','Forearm']:
     # Small FK gesture from the source silhouette, without a wrist target or arm IK.
     angle=math.radians((3 if segment=='UpperArm' else 5)*pulse)
     pb.rotation_quaternion=pb.rotation_quaternion@Quaternion(pb.bone.matrix_local.to_quaternion().inverted()@Vector((0,1,0)),angle)
    pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name);pb.keyframe_insert(data_path='location',frame=frame,group=pb.name)
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for p in fc.keyframe_points:p.handle_left_type='AUTO_CLAMPED';p.handle_right_type='AUTO_CLAMPED'
 # Test the rest binding directly: newly fitted bones must not alter source geometry.
 rig.data.pose_position='REST';bpy.context.view_layer.update();e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();rest=np.array([v.co[:] for v in m.vertices]);e.to_mesh_clear();rest_error=float(np.linalg.norm(rest-source,axis=1).max());assert rest_error<1e-5;rig.data.pose_position='POSE'
 first=None;prev=None;maxstep=0;footmotion=0;ids=np.array([v.index for v in mesh.data.vertices if v.co.z<.12]);arm_ids=np.array([v.index for v in mesh.data.vertices if abs(v.co.y)>.17*h and .4*h<v.co.z<.7*h])
 for frame in range(1,242):
  scene.frame_set(frame);bpy.context.view_layer.update();e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();p=np.array([v.co[:] for v in m.vertices]);e.to_mesh_clear();assert np.isfinite(p).all()
  if first is None:first=p.copy()
  if prev is not None:maxstep=max(maxstep,float(np.linalg.norm(p-prev,axis=1).max()))
  footmotion=max(footmotion,float(np.linalg.norm(p[ids]-first[ids],axis=1).max()));prev=p
 gap=float(np.linalg.norm(p-first,axis=1).max());assert gap<1e-5 and maxstep<.026 and footmotion<1e-5
 scene.frame_set(1);scene.frame_start=1;scene.frame_end=240
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(D/(key+'_rigged_idle.blend')))
 bpy.ops.export_scene.gltf(filepath=str(D/(key+'_rigged_idle.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=False,export_force_sampling=True,export_sampling_interpolation_fallback='LINEAR',export_morph=False)
 report=json.loads((OLD/key/'verification.json').read_text());report['clip']=action.name;report.pop('export_audit',None);report.pop('arm_correction',None)
 report['arm_correction']={'method':'Source elbow/wrist relationship restored; entire arm lowered rigidly at fitted shoulder; no arm IK or world-space wrist override','source_rest_vertex_error_m':rest_error,'fitted_arm_joints':fitting,'gesture_degrees':{'upper_arm':3,'forearm':5},'rest_upper_arm_lowering_degrees':12,'rest_forearm_and_wrist_pose_rotation_degrees':0}
 report['audit'].update(loop_gap_m=gap,max_adjacent_frame_step_m=maxstep,planted_boot_displacement_m=footmotion)
 (D/'verification.json').write_text(json.dumps(report,indent=2));reports[key]=report;print('SOURCE_ARMS_RESTORED',key,rest_error,flush=True)
(OUT/'verification.json').write_text(json.dumps(reports,indent=2))
