import bpy,json,math,os
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
R=Path(__file__).resolve().parents[1];OLD=R/'art/characters/npc_cast_idle_v10';OUT=R/'art/characters/npc_cast_idle_v11';OUT.mkdir(exist_ok=True)
ns={'__file__':str(R/'tools/blender_npc_video_idle_v10.py')};exec((R/'tools/blender_npc_video_idle_v10.py').read_text().split('\nreports={}')[0],ns)
def helpers(rig,mesh,h):
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
 for side,sign in [('L',1),('R',-1)]:
  upper=rig.data.edit_bones['UpperArm.'+side];upper.head.y=sign*.105*h;rig.data.edit_bones['Shoulder.'+side].tail=upper.head
  fore=rig.data.edit_bones['Forearm.'+side]
  for name,parent in [('ForeTwist.',fore),('ElbowSupport.',upper)]:
   b=rig.data.edit_bones.new(name+side);b.head=fore.head;b.tail=fore.tail;b.roll=fore.roll;b.parent=parent;b.use_deform=True
  rig.data.edit_bones['Hand.'+side].parent=rig.data.edit_bones['ForeTwist.'+side]
 bpy.ops.object.mode_set(mode='OBJECT')
 for side in ['L','R']:
  twist=mesh.vertex_groups.new(name='ForeTwist.'+side);support=mesh.vertex_groups.new(name='ElbowSupport.'+side)
  upper=mesh.vertex_groups['UpperArm.'+side];fore=mesh.vertex_groups['Forearm.'+side];bone=rig.data.bones['Forearm.'+side];axis=(bone.tail_local-bone.head_local).normalized();length=bone.length
  for v in mesh.data.vertices:
   w={g.group:g.weight for g in v.groups};u=w.get(upper.index,0);f=w.get(fore.index,0);amount=u+f
   if amount<.65:continue
   p=(v.co-bone.head_local).dot(axis);blend=ns['smooth']((p/length-.12)/.72)
   fore.add([v.index],f*(1-blend),'REPLACE');twist.add([v.index],f*blend,'REPLACE')
   if (v.co-bone.head_local).length<.085*h:
    s=.72*(1-ns['smooth'](abs(p)/(.06*h)))
    for vg in [upper,fore,twist]:
     value=next((g.weight for g in v.groups if g.group==vg.index),0);vg.add([v.index],value*(1-s),'REPLACE')
    support.add([v.index],amount*s,'REPLACE')
  for v in mesh.data.vertices:
   groups=sorted([(g.group,g.weight) for g in v.groups if g.weight>1e-8],key=lambda a:a[1],reverse=True);keep=groups[:4];total=sum(w for i,w in keep)
   for i in [g.group for g in v.groups]:mesh.vertex_groups[i].remove([v.index])
   for i,w in keep:mesh.vertex_groups[i].add([v.index],w/total,'REPLACE')
def align_wrist(rig,side):
 bpy.context.view_layer.update();pb=rig.pose.bones['Hand.'+side];fore=rig.pose.bones['Forearm.'+side];a=(pb.tail-pb.head).normalized();b=(fore.tail-fore.head).normalized();angle=a.angle(b)
 if angle>math.radians(18):
  delta=a.rotation_difference(b);q=Quaternion().slerp(delta,1-math.radians(18)/angle)@pb.matrix.to_quaternion();pb.matrix=Matrix.Translation(pb.head)@q.to_matrix().to_4x4();pb.location=(0,0,0)
def finger_pose(rig,side,key,amount):
 for b in rig.pose.bones:
  if not b.name.startswith('Digit') or not b.name.endswith('.'+side):continue
  d=(b.bone.tail_local-b.bone.head_local).normalized();normal=Vector((0,-1 if side=='L' else 1,0));axis=d.cross(normal).normalized();prox='.1.' in b.name
  degrees=(18 if prox else 12)+amount*({'sora':18,'moru':25,'naru':34,'haeru':17}[key] if prox else {'sora':15,'moru':20,'naru':25,'haeru':12}[key])
  b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion(b.bone.matrix_local.to_quaternion().inverted()@axis,math.radians(degrees))
reports={}
for key,h in [('sora',1.65),('moru',1.65),('naru',1.55),('haeru',1.85)]:
 D=OUT/key;D.mkdir(exist_ok=True)
 if os.environ.get('NPC_REBUILD') and key not in os.environ['NPC_REBUILD'].split(','):
  reports[key]=json.loads((D/'verification.json').read_text());continue
 bpy.ops.wm.open_mainfile(filepath=str(OLD/key/(key+'_rigged_idle.blend')));scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in scene.objects if o.type=='MESH');rig.animation_data_clear()
 with bpy.data.libraries.load(str(R/'art/characters/npc_cast_idle_v9'/key/(key+'_rigged_idle.blend')),link=False) as (src,dst):dst.objects=[key+'_BodyRig']
 neutral=dst.objects[0];base={b.name:(b.rotation_quaternion.copy(),b.location.copy()) for b in neutral.pose.bones};bpy.data.objects.remove(neutral,do_unlink=True)
 helpers(rig,mesh,h);rig.animation_data_create();action=bpy.data.actions.new('Idle_'+key.capitalize()+'_ReferencePose');rig.animation_data.action=action;prev_q={}
 for frame in range(1,602,2):
  t=(frame-1)/30;cycle=math.pi*t/10
  for b in rig.pose.bones:
   b.rotation_mode='QUATERNION';b.rotation_quaternion=base.get(b.name,(Quaternion(),Vector()))[0];b.location=base.get(b.name,(Quaternion(),Vector()))[1]
  ns['ns']['rotation'](rig.pose.bones['Head'],*ns['timeline'](t,ns['HEAD'][key]));ns['ns']['rotation'](rig.pose.bones['Chest'],0,.35*math.sin(cycle*5),0);ns['ns']['rotation'](rig.pose.bones['Spine'],.7*math.sin(cycle),0,0)
  active={}
  if key=='sora':active['R']=(ns['hold'](t,3,6,8,11),(.105*h,-.045*h,.775*h),(.16*h,-.19*h,.60*h))
  elif key=='moru':
   for side,sign in [('L',1),('R',-1)]:active[side]=(1.,(.014*h,sign*.095*h,.495*h),(.09*h,sign*.19*h,.595*h))
  elif key=='naru':active['R']=(ns['hold'](t,10,12,16,19),(.108*h,-.065*h,.581*h),(.12*h,-.18*h,.535*h))
  else:
   for side,sign in [('L',1),('R',-1)]:active[side]=(1.,((.075 if side=='L' else .085)*h,-sign*.075*h,(.700 if side=='L' else .715)*h),(.06*h,sign*.17*h,.625*h))
  bpy.context.view_layer.update()
  for side in ['L','R']:
   amount=active.get(side,(0,None,None))[0]
   if side in active:ns['ns']['solve_limb'](rig,'UpperArm.'+side,'Forearm.'+side,active[side][1],active[side][2],amount)
   support=rig.pose.bones['ElbowSupport.'+side];support.rotation_quaternion=Quaternion().slerp(rig.pose.bones['Forearm.'+side].rotation_quaternion,.5)
   sign=1 if side=='L' else -1;roll=-sign*({'sora':-70,'moru':10,'naru':-70,'haeru':-65}[key])*amount
   rig.pose.bones['ForeTwist.'+side].rotation_quaternion=Quaternion(Vector((0,1,0)),math.radians(roll));rig.pose.bones['Hand.'+side].rotation_quaternion=Quaternion();align_wrist(rig,side);finger_pose(rig,side,key,amount)
  for b in rig.pose.bones:
   if b.name in prev_q and b.rotation_quaternion.dot(prev_q[b.name])<0:b.rotation_quaternion.negate()
   prev_q[b.name]=b.rotation_quaternion.copy();b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name);b.keyframe_insert(data_path='location',frame=frame,group=b.name)
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for p in fc.keyframe_points:p.interpolation='BEZIER';p.handle_left_type='AUTO_CLAMPED';p.handle_right_type='AUTO_CLAMPED'
     fc.modifiers.new('CYCLES')
 action.use_fake_user=True;action['duration_seconds']=20;action['loop']=True
 first=None;prev=None;step=0;foot=0;wrist=0;ids=np.array([v.index for v in mesh.data.vertices if v.co.z<.12])
 for frame in range(1,602):
  scene.frame_set(frame);bpy.context.view_layer.update()
  for side in ['L','R']:
   a=rig.pose.bones['Forearm.'+side];b=rig.pose.bones['Hand.'+side];wrist=max(wrist,math.degrees((a.tail-a.head).angle(b.tail-b.head)))
  e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();p=np.array([v.co[:] for v in m.vertices]);e.to_mesh_clear();assert np.isfinite(p).all()
  if first is None:first=p.copy()
  if prev is not None:
   delta=float(np.linalg.norm(p-prev,axis=1).max());step=max(step,delta)
   if delta>.02:print('LARGE_STEP',key,frame,delta,flush=True)
  foot=max(foot,float(np.linalg.norm(p[ids]-first[ids],axis=1).max()));prev=p
 gap=float(np.linalg.norm(p-first,axis=1).max());print('REFERENCE_AUDIT',key,gap,step,wrist,foot,flush=True);assert gap<1e-5 and step<.035 and foot<1e-5 and wrist<24
 scene.frame_set(1);scene.frame_start=1;scene.frame_end=600;scene.render.fps=30
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.wm.save_as_mainfile(filepath=str(D/(key+'_rigged_idle.blend')))
 bpy.ops.export_scene.gltf(filepath=str(D/(key+'_rigged_idle.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=False,export_force_sampling=True,export_sampling_interpolation_fallback='LINEAR',export_morph=False)
 report=json.loads((OLD/key/'verification.json').read_text());report['clip']=action.name;report.pop('export_audit',None);report.pop('visual_review',None);report['audit'].update(bones=len(rig.data.bones),loop_gap_m=gap,max_adjacent_frame_step_m=step,planted_boot_displacement_m=foot,max_wrist_axis_bend_degrees=wrist)
 report['reference_correction']={'forearm_twist_bones':2,'elbow_support_bones':2,'wrist':'Hand follows forearm; bend limited to 18 degrees at key poses','finger_curl':'Anatomical rest finger planes; no arbitrary local-X rotation','shoulder_pivots':'0.105 times height from center','pocket_pose':'Moru fingertips tucked behind front trouser surface'}
 (D/'verification.json').write_text(json.dumps(report,indent=2));reports[key]=report
(OUT/'verification.json').write_text(json.dumps(reports,indent=2))




