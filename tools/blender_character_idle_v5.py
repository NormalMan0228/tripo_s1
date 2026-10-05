import bpy, math, json, hashlib
import numpy as np
from mathutils import Vector,Quaternion,Matrix
from pathlib import Path
R=Path(__file__).resolve().parents[1];OLD=R/'art/characters/npc_cast_idle_v3';OUT=R/'art/characters/npc_cast_idle_v5';OUT.mkdir(exist_ok=True)
descriptions={'sora':'Tailor: look down and inspect tunic with one hand, then settle','moru':'Energetic youth: lift one arm, small wrist gesture, then open shoulders','naru':'Curious explorer: lean forward and tilt while inspecting both sides, arms quiet','haeru':'Reserved adult: slow asymmetric shoulder release, look aside, single nod'}
def pose(**kw):return kw
# Independent pose stories; missing values return to that character's neutral pose.
# All tuples are rotations around world X, Y, Z in degrees, converted to bone space.
STORIES={
 'sora':[(0,{}),(1,{}),(2,pose(Head=(0,9,-4),Spine=(0,-2,0),**{'UpperArm.L':(9,-12,0),'Forearm.L':(-48,-24,0),'Hand.L':(0,0,8)})),(3,pose(Head=(0,11,-4),Spine=(0,-2,0),**{'UpperArm.L':(9,-12,0),'Forearm.L':(-48,-24,0),'Hand.L':(0,0,-7)})),(3.8,pose(Head=(0,9,-4),Spine=(0,-2,0),**{'UpperArm.L':(9,-12,0),'Forearm.L':(-48,-24,0),'Hand.L':(0,0,7)})),(5,{}),(6,pose(Head=(0,-3,5))),(7,{}),(8,{})],
 'moru':[(0,{}),(.8,pose(Head=(-5,0,-8))),(1.8,pose(Head=(-3,-2,-5),Chest=(0,-2,-4),**{'UpperArm.L':(30,-8,0),'Forearm.L':(-50,-16,0),'Hand.L':(0,0,10)})),(2.35,pose(Head=(-3,-2,-5),Chest=(0,-2,-4),**{'UpperArm.L':(30,-8,0),'Forearm.L':(-50,-16,0),'Hand.L':(0,0,-12)})),(2.9,pose(Head=(-3,-2,-5),Chest=(0,-2,-4),**{'UpperArm.L':(30,-8,0),'Forearm.L':(-50,-16,0),'Hand.L':(0,0,10)})),(4,{}),(5.4,pose(Head=(0,-5,0),Chest=(0,-3,0),**{'Shoulder.L':(7,0,0),'Shoulder.R':(-7,0,0),'UpperArm.L':(9,-9,0),'UpperArm.R':(-9,-9,0)})),(6.5,{}),(8,{})],
 'naru':[(0,{}),(.7,{}),(1.6,pose(Spine=(-3,-7,-4),Chest=(0,-2,-3),Neck=(-3,0,-3),Head=(-10,2,-19))),(2.8,pose(Spine=(-3,-7,-4),Chest=(0,-2,-3),Neck=(-3,0,-3),Head=(-12,4,-19))),(3.8,pose(Spine=(0,-4,0),Head=(0,0,0))),(4.8,pose(Spine=(2,-5,3),Chest=(0,-1,2),Neck=(2,0,2),Head=(10,1,18))),(5.8,pose(Spine=(2,-5,3),Chest=(0,-1,2),Neck=(2,0,2),Head=(8,-2,18))),(7,{}),(8,{})],
 'haeru':[(0,{}),(1.5,{}),(2.7,pose(Chest=(1,-2,0),Neck=(3,0,3),Head=(7,0,8),**{'Shoulder.R':(-11,-3,0),'UpperArm.R':(-1,-8,0),'Forearm.R':(4,-10,0)})),(3.7,pose(Chest=(1,-2,0),Neck=(3,0,3),Head=(7,0,8),**{'Shoulder.R':(-11,3,0),'UpperArm.R':(-1,-8,0),'Forearm.R':(4,-10,0)})),(5,pose(Head=(0,0,9))),(5.8,pose(Head=(0,7,7))),(6.6,pose(Head=(0,-2,4))),(7.5,{}),(8,{})]
}
def story_pose(key,seconds,neutral):
 keys=STORIES[key]
 for (a,pa),(b,pb) in zip(keys,keys[1:]):
  if a<=seconds<=b:
   u=(seconds-a)/(b-a);u=u*u*u*(u*(u*6-15)+10)
   return {name:tuple(x+(y-x)*u for x,y in zip(pa.get(name,value),pb.get(name,value))) for name,value in neutral.items()}
 return neutral.copy()
def pulse(t,a,b):
 if t<=a or t>=b:return 0.
 return math.sin(math.pi*(t-a)/(b-a))**2
def ramp(t,a,b):
 u=max(0,min(1,(t-a)/(b-a)));return u*u*u*(u*(u*6-15)+10)
def rotation(pb,x=0,y=0,z=0):
 rest=pb.bone.matrix_local.to_quaternion();q=Quaternion()
 for axis,angle in [(Vector((1,0,0)),x),(Vector((0,1,0)),y),(Vector((0,0,1)),z)]:q=q@Quaternion(rest.inverted()@axis,math.radians(angle))
 pb.rotation_mode='QUATERNION';pb.rotation_quaternion=q
def hand_controls(rig,key):
 if key not in ['sora','moru']:return None
 h={'sora':1.65,'moru':1.65}[key]
 target=bpy.data.objects.new(key+'_HandTarget',None);bpy.context.scene.collection.objects.link(target);target.parent=rig;target.location=(.125*h,.075*h,.535*h) if key=='sora' else (.13*h,.17*h,.725*h)
 pole=bpy.data.objects.new(key+'_ElbowPole',None);bpy.context.scene.collection.objects.link(pole);pole.parent=rig;pole.location=(.27*h,.30*h,.58*h)
 return (target,pole)
def solve_hand(rig,controls,amount):
 if amount<1e-7:return
 upper=rig.pose.bones['UpperArm.L'];fore=rig.pose.bones['Forearm.L'];fk_upper=upper.rotation_quaternion.copy();fk_fore=fore.rotation_quaternion.copy()
 bpy.context.view_layer.update();start=upper.head.copy();target=controls[0].location.copy();pole=controls[1].location.copy()
 length1=upper.bone.length;length2=fore.bone.length;axis=target-start;distance=min(axis.length,length1+length2-.0001);axis.normalize()
 bend=pole-start; bend-=axis*bend.dot(axis);bend.normalize()
 along=(length1*length1-length2*length2+distance*distance)/(2*distance);radius=math.sqrt(max(0,length1*length1-along*along));elbow=start+axis*along+bend*radius
 for pb,head,tail in [(upper,start,elbow),(fore,elbow,start+axis*distance)]:
  rest_direction=(pb.bone.tail_local-pb.bone.head_local).normalized();desired=(tail-head).normalized()
  world_rotation=rest_direction.rotation_difference(desired)@pb.bone.matrix_local.to_quaternion()
  pb.matrix=Matrix.Translation(head)@world_rotation.to_matrix().to_4x4();bpy.context.view_layer.update()
 ik_upper=upper.rotation_quaternion.copy();ik_fore=fore.rotation_quaternion.copy()
 upper.location=(0,0,0);fore.location=(0,0,0)
 upper.rotation_quaternion=fk_upper.slerp(ik_upper,amount);fore.rotation_quaternion=fk_fore.slerp(ik_fore,amount)
def animate(rig,key,arm):
 rig.animation_data_clear()
 for pb in rig.pose.bones:pb.rotation_quaternion=Quaternion();pb.location=(0,0,0)
 rig.animation_data_create();a=bpy.data.actions.new('Idle_'+key.capitalize()+'_Character');rig.animation_data.action=a
 gesture=hand_controls(rig,key)
 for frame in range(1,242,2):
  sec=(frame-1)/30;t=2*math.pi*sec/8
  neutral={b.name:(0,0,0) for b in rig.pose.bones}
  for side,sgn in [('L',1),('R',-1)]:
   neutral['UpperArm.'+side]=(-sgn*arm,0,0);neutral['Forearm.'+side]=(0,-4,0)
  values=story_pose(key,sec,neutral)
  breathing={'sora':.4,'moru':.6,'naru':.3,'haeru':.6}[key]*math.sin(2*t)
  values['Chest']=(values['Chest'][0],values['Chest'][1]+breathing,values['Chest'][2])
  for name,angles in values.items():rotation(rig.pose.bones[name],*angles)
  if gesture:
   if key=='sora':
    amount=ramp(sec,.3,2.3)*(1-ramp(sec,4.3,6.3))
   else:
    amount=pulse(sec,.2,5.4)
    rotation(rig.pose.bones['Hand.L'],x=-120*amount,z=12*math.sin(4*math.pi*max(0,min(1,(sec-1)/2)))*amount)
   solve_hand(rig,gesture,amount)
  for pb in rig.pose.bones:pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
 for layer in a.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for f in bag.fcurves:
     for k in f.keyframe_points:k.interpolation='BEZIER';k.handle_left_type='AUTO';k.handle_right_type='AUTO'
     f.modifiers.new('CYCLES')
 a.use_fake_user=True;a['duration_seconds']=8;a['loop']=True
 return a
def audit(mesh,key):
 first=None;prev=None;max_step=0;motion=0;foot_motion=0;head_motion=0;hand_motion=0
 ids=np.array([v.index for v in mesh.data.vertices if v.co.z<.12])
 h=max(v.co.z for v in mesh.data.vertices);head=np.array([v.index for v in mesh.data.vertices if v.co.z>h*.85],dtype=int);hand=np.array([v.index for v in mesh.data.vertices if abs(v.co.y)>h*.175 and h*.38<v.co.z<h*.52],dtype=int)
 for f in range(1,242):
  bpy.context.scene.frame_set(f);bpy.context.view_layer.update();e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();coords=np.empty(len(m.vertices)*3,dtype=np.float32);m.vertices.foreach_get('co',coords);e.to_mesh_clear();coords=coords.reshape(-1,3);assert np.isfinite(coords).all()
  if first is None:first=coords.copy()
  else:max_step=max(max_step,float(np.linalg.norm(coords-prev,axis=1).max()))
  dist=np.linalg.norm(coords-first,axis=1);motion=max(motion,float(dist.max()));head_motion=max(head_motion,float(dist[head].max()));hand_motion=max(hand_motion,float(dist[hand].max()));foot_motion=max(foot_motion,float(dist[ids].max()));prev=coords.copy()
 gap=float(np.linalg.norm(coords-first,axis=1).max());print('AUDIT_VALUES',key,gap,max_step,motion,foot_motion,flush=True);assert gap<1e-5 and max_step<.025 and motion>.06 and foot_motion<1e-5
 return {'frames_checked':241,'loop_gap_m':gap,'max_adjacent_frame_step_m':max_step,'max_motion_m':motion,'head_motion_m':head_motion,'hand_motion_m':hand_motion,'planted_boot_displacement_m':foot_motion,'unweighted_vertices':sum(not v.groups for v in mesh.data.vertices),'bones':22}
reports={}
for key,arm in [('sora',10),('moru',12),('naru',6),('haeru',8)]:
 O=OUT/key;O.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(OLD/key/(key+'_rigged_idle.blend')));scene=bpy.context.scene
 rig=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in scene.objects if o.type=='MESH');a=animate(rig,key,arm)
 scene.frame_start=1;scene.frame_end=240;scene.render.fps=30;check=audit(mesh,key);scene.frame_set(1)
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(O/(key+'_rigged_idle.blend')))
 bpy.ops.export_scene.gltf(filepath=str(O/(key+'_rigged_idle.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=False,export_force_sampling=True,export_sampling_interpolation_fallback='LINEAR',export_morph=False)
 report=json.loads((OLD/key/'verification.json').read_text());report.update(clip=a.name,audit=check,description=descriptions[key]);report.pop('export_audit',None);report.pop('visual_review',None);report['motion_amplitude_ratio_to_v3']=check['max_motion_m']/json.loads((OLD/key/'verification.json').read_text())['audit']['max_motion_m']
 (O/'verification.json').write_text(json.dumps(report,indent=2));reports[key]=report;print('VISIBLE_IDLE',key,json.dumps(check),flush=True)
(OUT/'verification.json').write_text(json.dumps(reports,indent=2))

