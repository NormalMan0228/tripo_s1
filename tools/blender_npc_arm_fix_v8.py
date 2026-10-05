import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
R=Path(__file__).resolve().parents[1]
namespace={'__file__':str(R/'tools/blender_relaxed_stand_idle_v6.py')}
exec((R/'tools/blender_relaxed_stand_idle_v6.py').read_text().split('reports={}')[0],namespace)
OLD=R/'art/characters/npc_cast_idle_v7';OUT=R/'art/characters/npc_cast_idle_v8';OUT.mkdir(exist_ok=True)
old_standing=namespace['relaxed_standing'];solve=namespace['solve_limb']
def standing(rig,key):
 old_standing(rig,key)
 h={'sora':1.65,'moru':1.65,'naru':1.55,'haeru':1.85}[key]
 for side,sign in [('L',1),('R',-1)]:
  upper=rig.pose.bones['UpperArm.'+side];fore=rig.pose.bones['Forearm.'+side]
  a=upper.head.copy();length=upper.bone.length+fore.bone.length
  target=Vector((a.x+.02*h,sign*(.155 if key in ['sora','naru'] and side=='R' else .14)*h,0))
  target.z=a.z-math.sqrt((length*.985)**2-(target.x-a.x)**2-(target.y-a.y)**2)
  solve(rig,upper.name,fore.name,target,Vector((.20*h,sign*.15*h,.58*h)))
  # Wrist follows forearm: restoring the original world hand orientation created a kink.
  hand=rig.pose.bones['Hand.'+side];hand.rotation_quaternion=Quaternion();hand.location=(0,0,0)
  bpy.context.view_layer.update()
 return {b.name:b.rotation_quaternion.copy() for b in rig.pose.bones},rig.pose.bones['Hips'].location.copy()
namespace['relaxed_standing']=standing
def smooth(x):
 x=max(0,min(1,x));return x*x*(3-2*x)
def elbow_weights(mesh,rig):
 count=0
 for side in ['L','R']:
  u=mesh.vertex_groups['UpperArm.'+side];f=mesh.vertex_groups['Forearm.'+side]
  elbow=rig.data.bones['Forearm.'+side].head_local;axis=(rig.data.bones['Forearm.'+side].tail_local-rig.data.bones['UpperArm.'+side].head_local).normalized()
  width=(rig.data.bones['UpperArm.'+side].length+rig.data.bones['Forearm.'+side].length)*.18
  for v in mesh.data.vertices:
   current={g.group:g.weight for g in v.groups};total=current.get(u.index,0)+current.get(f.index,0)
   if total<.6 or (v.co-elbow).length>width*1.6:continue
   factor=smooth(.5+(v.co-elbow).dot(axis)/(width*2))
   u.add([v.index],total*(1-factor),'REPLACE');f.add([v.index],total*factor,'REPLACE');count+=1
 return count
def angle(rig,side):
 u=rig.pose.bones['UpperArm.'+side];f=rig.pose.bones['Forearm.'+side]
 return math.degrees((u.tail-u.head).angle(f.tail-f.head))
reports={}
for key in ['sora','moru','naru','haeru']:
 D=OUT/key;D.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(OLD/key/(key+'_rigged_idle.blend')))
 scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in scene.objects if o.type=='MESH')
 source_action=rig.animation_data.action
 digit_keys={}
 for layer in source_action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     if 'Digit' in fc.data_path:digit_keys[(fc.data_path,fc.array_index)]=[(k.co.x,k.co.y) for k in fc.keyframe_points]
 scene.frame_set(1);before={s:angle(rig,s) for s in ['L','R']};fixed=elbow_weights(mesh,rig)
 action=namespace['animate'](rig,key,0);action.name='Idle_'+key.capitalize()+'_SoftArms'
 # Remove large wrist/arm departures from the gesture and keep a small character-specific reach.
 scene.frame_set(1);base={b.name:b.rotation_quaternion.copy() for b in rig.pose.bones}
 for frame in range(1,242,2):
  scene.frame_set(frame)
  for side in ['L','R']:
   for segment in ['UpperArm','Forearm']:
    b=rig.pose.bones[segment+'.'+side];q=b.rotation_quaternion.copy();b.rotation_quaternion=base[b.name].slerp(q,.42 if key in ['sora','moru'] and side=='L' else .65);b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
   hand=rig.pose.bones['Hand.'+side];hand.rotation_quaternion=Quaternion();hand.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=hand.name)
  for (path,index),points in digit_keys.items():
   name=path.split('"')[1];rig.pose.bones[name].rotation_quaternion[index]=next(value for f,value in points if f==frame)
  for b in rig.pose.bones:
   if b.name.startswith('Digit'):b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for k in fc.keyframe_points:k.handle_left_type='AUTO_CLAMPED';k.handle_right_type='AUTO_CLAMPED'
     if not fc.modifiers:fc.modifiers.new('CYCLES')
 first=None;prev=None;maxstep=0;footmove=0;angles=[]
 feet=np.array([v.index for v in mesh.data.vertices if v.co.z<.12])
 for frame in range(1,242):
  scene.frame_set(frame);bpy.context.view_layer.update();angles.append({s:angle(rig,s) for s in ['L','R']})
  e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();p=np.array([v.co[:] for v in m.vertices]);e.to_mesh_clear();assert np.isfinite(p).all()
  if first is None:first=p.copy()
  if prev is not None:maxstep=max(maxstep,float(np.linalg.norm(p-prev,axis=1).max()))
  footmove=max(footmove,float(np.linalg.norm(p[feet]-first[feet],axis=1).max()));prev=p
 gap=float(np.linalg.norm(p-first,axis=1).max());assert gap<1e-5 and maxstep<.026 and footmove<1e-5
 assert max(abs(sum(g.weight for g in v.groups)-1) for v in mesh.data.vertices)<1e-4
 scene.frame_set(1);scene.frame_start=1;scene.frame_end=240
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(D/(key+'_rigged_idle.blend')))
 bpy.ops.export_scene.gltf(filepath=str(D/(key+'_rigged_idle.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=False,export_force_sampling=True,export_sampling_interpolation_fallback='LINEAR',export_morph=False)
 report=json.loads((OLD/key/'verification.json').read_text());report['clip']=action.name;report.pop('export_audit',None)
 report['arm_correction']={'previous_rest_elbow_degrees':before,'rest_elbow_degrees':angles[0],'maximum_elbow_degrees':{s:max(a[s] for a in angles) for s in ['L','R']},'elbow_blend_vertices':fixed,'wrist':'Identity relative to forearm; no world-space orientation reset','gesture_arm_blend':.42,'source_mesh_unchanged':True}
 report['audit'].update(loop_gap_m=gap,max_adjacent_frame_step_m=maxstep,planted_boot_displacement_m=footmove)
 (D/'verification.json').write_text(json.dumps(report,indent=2));reports[key]=report;print('ARM_FIX',key,report['arm_correction'],flush=True)
(OUT/'verification.json').write_text(json.dumps(reports,indent=2))
