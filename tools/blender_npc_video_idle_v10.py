import bpy,json,math,os
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
R=Path(__file__).resolve().parents[1];OLD=R/'art/characters/npc_cast_idle_v9';OUT=R/'art/characters/npc_cast_idle_v10';OUT.mkdir(exist_ok=True)
ns={'__file__':str(R/'tools/blender_relaxed_stand_idle_v6.py')};exec((R/'tools/blender_relaxed_stand_idle_v6.py').read_text().split('reports={}')[0],ns)
def smooth(u):
 u=max(0,min(1,u));return u*u*u*(u*(u*6-15)+10)
def hold(t,a,b,c,d):return smooth((t-a)/(b-a))*(1-smooth((t-c)/(d-c)))
def timeline(t,keys):
 for (a,p),(b,q) in zip(keys,keys[1:]):
  if a<=t<=b:
   u=smooth((t-a)/(b-a));return tuple(x+(y-x)*u for x,y in zip(p,q))
 return keys[0][1]
HEAD={
 'sora':[(0,(0,0,0)),(4,(0,0,0)),(6,(-6,2,-8)),(8,(-6,2,-8)),(10,(0,0,0)),(18,(0,0,0)),(20,(0,0,0))],
 'moru':[(0,(0,0,0)),(3,(0,0,0)),(5,(0,7,0)),(8,(0,7,0)),(10,(0,0,0)),(12,(0,3,-5)),(15,(0,3,-5)),(18,(0,0,0)),(20,(0,0,0))],
 'naru':[(0,(0,0,0)),(2,(0,2,0)),(4,(0,-2,3)),(8,(0,0,0)),(10,(0,0,-6)),(13,(0,6,-6)),(15,(0,6,-6)),(18,(0,0,0)),(20,(0,0,0))],
 'haeru':[(0,(0,0,0)),(5,(0,0,4)),(8,(0,0,4)),(10,(0,3,0)),(12,(0,3,0)),(15,(-11,-4,-10)),(17,(-11,-4,-10)),(20,(0,0,0))]}
def hand_pose(rig,side,direction,amount,neutral_world):
 pb=rig.pose.bones['Hand.'+side];fk=pb.rotation_quaternion.copy();head=pb.head.copy()
 rd=(pb.bone.tail_local-pb.bone.head_local).normalized();desired=Vector(direction).normalized()
 rn=Vector((0,1 if side=='L' else -1,0));rn=(rn-rd*rn.dot(rd)).normalized()
 normal=Vector((-1,0,0));normal=(normal-desired*normal.dot(desired)).normalized()
 rest_frame=Matrix((rd.cross(rn),rd,rn)).transposed();target_frame=Matrix((desired.cross(normal),desired,normal)).transposed()
 q=(target_frame@rest_frame.transposed()).to_quaternion()@pb.bone.matrix_local.to_quaternion()
 if q.dot(neutral_world)<0:q.negate()
 q=neutral_world.slerp(q,amount)
 pb.matrix=Matrix.Translation(head)@q.to_matrix().to_4x4();bpy.context.view_layer.update();pb.location=(0,0,0)
reports={}
for key,h in [('sora',1.65),('moru',1.65),('naru',1.55),('haeru',1.85)]:
 D=OUT/key;D.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(OLD/key/(key+'_rigged_idle.blend')))
 if os.environ.get('NPC_REBUILD') and key not in os.environ['NPC_REBUILD'].split(','):
  reports[key]=json.loads((D/'verification.json').read_text());continue
 scene=bpy.context.scene;scene.frame_set(1);rig=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in scene.objects if o.type=='MESH')
 bag_ids=set()
 arm_positions=set()
 if key=='naru':
  positions={v.index:tuple(round(x,5) for x in v.co) for v in mesh.data.vertices}
  for sign in [-1,1]:
   remain={p for p in positions.values() if sign*p[1]>.12*h and .30*h<p[2]<.76*h};adj={p:set() for p in remain};parts=[]
   for edge in mesh.data.edges:
    a,b=[positions[i] for i in edge.vertices]
    if a in remain and b in remain:adj[a].add(b);adj[b].add(a)
   while remain:
    stack=[remain.pop()];part=[]
    while stack:
     a=stack.pop();part.append(a)
     for b in adj[a]:
      if b in remain:remain.remove(b);stack.append(b)
    if part:parts.append(part)
   arm_positions.update(max(parts,key=lambda p:max(sign*v[1] for v in p)))
  tex=next(n.image for m in mesh.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'normal' not in n.image.name.lower());pixels=np.array(tex.pixels[:]).reshape(tex.size[1],tex.size[0],4);uv=mesh.data.uv_layers.active.data;bag_points=set()
  for loop in mesh.data.loops:
   v=mesh.data.vertices[loop.vertex_index]
   if not .36*h<v.co.z<.72*h or abs(v.co.y)>.20*h:continue
   coord=uv[loop.index].uv;r,g,b=pixels[min(tex.size[1]-1,int(coord.y*tex.size[1])),min(tex.size[0]-1,int(coord.x*tex.size[0])),:3]
   if .10<r<.65 and r>g*1.18 and g>b*1.15:bag_points.add(positions[v.index])
  allowed={p for p in positions.values() if .36*h<p[2]<.72*h and abs(p[1])<.20*h};adj={p:set() for p in allowed}
  for edge in mesh.data.edges:
   a,b=[positions[i] for i in edge.vertices]
   if a in allowed and b in allowed:adj[a].add(b);adj[b].add(a)
  for ring in range(4):bag_points.update(q for p in list(bag_points) for q in adj.get(p,()))
  bag_ids={i for i,p in positions.items() if p in bag_points}
 # Keep front accessories on the body, and prevent central torso vertices following folded arms.
 corrected=0
 for v in mesh.data.vertices:
  if key=='naru' and v.index in bag_ids:
   for group in list(v.groups):mesh.vertex_groups[group.group].remove([v.index])
   mesh.vertex_groups['Spine'].add([v.index],1.,'REPLACE');corrected+=1;continue
  if key=='naru':
   if tuple(round(x,5) for x in v.co) in arm_positions:continue
   remove=[g.group for g in v.groups if any(n in mesh.vertex_groups[g.group].name for n in ['Arm','Hand','Digit','Shoulder'])]
   amount=sum(g.weight for g in v.groups if g.group in remove)
   if amount>.001:
    for i in remove:mesh.vertex_groups[i].remove([v.index])
    vg=mesh.vertex_groups['Chest' if v.co.z>.61*h else 'Hips'];existing=next((g.weight for g in v.groups if g.group==vg.index),0);vg.add([v.index],existing+amount,'REPLACE');corrected+=1
   continue
  if v.index in bag_ids:
   for group in list(v.groups):mesh.vertex_groups[group.group].remove([v.index])
   mesh.vertex_groups['Chest' if v.co.z>.61*h else 'Hips'].add([v.index],1.,'REPLACE');corrected+=1;continue
  accessory=key=='naru' and v.co.x>.025*h and abs(v.co.y)<.165*h and .37*h<v.co.z<.72*h
  torso=abs(v.co.y)<.095*h and .50*h<v.co.z<.76*h
  if accessory or torso:
   remove=[g.group for g in v.groups if any(n in mesh.vertex_groups[g.group].name for n in ['Arm','Hand','Digit','Shoulder'])]
   amount=sum(g.weight for g in v.groups if g.group in remove)
   if amount>.001:
    for i in remove:mesh.vertex_groups[i].remove([v.index])
    vg=mesh.vertex_groups['Chest' if v.co.z>.61*h else 'Hips'];existing=next((g.weight for g in v.groups if g.group==vg.index),0);vg.add([v.index],existing+amount,'REPLACE');corrected+=1
 neutral_hands={side:rig.pose.bones['Hand.'+side].matrix.to_quaternion() for side in ['L','R']}
 base={b.name:(b.rotation_quaternion.copy(),b.location.copy()) for b in rig.pose.bones};rig.animation_data_clear();rig.animation_data_create();action=bpy.data.actions.new('Idle_'+key.capitalize()+'_VideoReference');rig.animation_data.action=action
 previous_quaternions={}
 for frame in range(1,602,2):
  t=(frame-1)/30;cycle=2*math.pi*t/20
  for b in rig.pose.bones:b.rotation_quaternion=base[b.name][0];b.location=base[b.name][1]
  ns['rotation'](rig.pose.bones['Head'],*timeline(t,HEAD[key]));rig.pose.bones['Head'].rotation_quaternion=base['Head'][0]@rig.pose.bones['Head'].rotation_quaternion
  breath=.45*math.sin(cycle*5);ns['rotation'](rig.pose.bones['Chest'],0,breath,0)
  tilt={'sora':.7,'moru':1.1,'naru':.8,'haeru':1.4}[key]*math.sin(cycle)
  ns['rotation'](rig.pose.bones['Spine'],tilt,0,0)
  active={}
  if key=='sora':
   amount=hold(t,4,6,8,10);active['R']=(amount,(.115*h,-.028*h,.738*h),(.20*h,-.26*h,.60*h),(-.1,.12,1))
  elif key=='moru':
   for side,sign in [('L',1),('R',-1)]:active[side]=(1.,(.058*h,sign*.125*h,.492*h),(.16*h,sign*.25*h,.585*h),(-.1,sign*.12,-1))
  elif key=='naru':
   amount=hold(t,10,12,16,19);active['R']=(amount,(.142*h,-.09*h,.592*h),(.21*h,-.25*h,.48*h),(-.05,1,.3))
  else:
   for side,sign in [('L',1),('R',-1)]:
    active[side]=(1.,((.095 if side=='L' else .11)*h,-sign*.035*h,(.670 if side=='L' else .650)*h),(.12*h,sign*.24*h,.575*h),(-.15,-sign,.7))
  bpy.context.view_layer.update()
  for side,(amount,target,pole,direction) in active.items():
   ns['solve_limb'](rig,'UpperArm.'+side,'Forearm.'+side,target,pole,amount);bpy.context.view_layer.update();hand_pose(rig,side,direction,amount,neutral_hands[side])
   for b in rig.pose.bones:
    if b.name.startswith('Digit') and b.name.endswith('.'+side):
     extra=(12 if key=='naru' else 4)*amount
     b.rotation_quaternion=base[b.name][0]@Quaternion(Vector((1,0,0)),math.radians(extra))
  for b in rig.pose.bones:
   if b.name in previous_quaternions and b.rotation_quaternion.dot(previous_quaternions[b.name])<0:b.rotation_quaternion.negate()
   previous_quaternions[b.name]=b.rotation_quaternion.copy()
   b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name);b.keyframe_insert(data_path='location',frame=frame,group=b.name)
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for p in fc.keyframe_points:p.interpolation='BEZIER';p.handle_left_type='AUTO_CLAMPED';p.handle_right_type='AUTO_CLAMPED'
     fc.modifiers.new('CYCLES')
 action.use_fake_user=True;action['duration_seconds']=20;action['loop']=True
 first=None;prev=None;maxstep=0;footmotion=0;peak=0;ids=np.array([v.index for v in mesh.data.vertices if v.co.z<.12])
 for frame in range(1,602):
  scene.frame_set(frame);bpy.context.view_layer.update();e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();p=np.array([v.co[:] for v in m.vertices]);e.to_mesh_clear();assert np.isfinite(p).all()
  if first is None:first=p.copy()
  if prev is not None:maxstep=max(maxstep,float(np.linalg.norm(p-prev,axis=1).max()))
  footmotion=max(footmotion,float(np.linalg.norm(p[ids]-first[ids],axis=1).max()));peak=max(peak,float(np.linalg.norm(p-first,axis=1).max()));prev=p
 gap=float(np.linalg.norm(p-first,axis=1).max());print('VIDEO_AUDIT',key,gap,maxstep,footmotion,flush=True);assert gap<1e-5 and maxstep<.035 and footmotion<1e-5
 scene.frame_set(1);scene.frame_start=1;scene.frame_end=600;scene.render.fps=30
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(D/(key+'_rigged_idle.blend')))
 bpy.ops.export_scene.gltf(filepath=str(D/(key+'_rigged_idle.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=False,export_force_sampling=True,export_sampling_interpolation_fallback='LINEAR',export_morph=False)
 report=json.loads((OLD/key/'verification.json').read_text());report['clip']=action.name;report['duration_seconds']=20;report.pop('export_audit',None);report.pop('visual_review',None)
 report['reference_animation']={'source':'reference/npc-idle-reference.mp4','method':'Manually authored skeletal poses from inspected video frames; not automatic motion capture','timeline_seconds':{'sora':'4–10: right hand toward chin; thinking head tilt','moru':'Hands at pocket openings; 3–10 down glance; 12–18 side glance','naru':'10–19: right hand toward bag strap; glance down','haeru':'Arms folded throughout; 13–20 slow head tilt and return'}[key],'loop_tail_adapted':True,'facial_animation':False}
 report['reference_animation']['body_attachment_weight_corrections']=corrected
 report['audit'].pop('head_motion_m',None);report['audit'].pop('hand_motion_m',None)
 report['audit'].update(frames_checked=601,loop_gap_m=gap,max_adjacent_frame_step_m=maxstep,planted_boot_displacement_m=footmotion,max_motion_m=peak)
 (D/'verification.json').write_text(json.dumps(report,indent=2));reports[key]=report;print('VIDEO_IDLE_READY',key,report['audit'],flush=True)
(OUT/'verification.json').write_text(json.dumps(reports,indent=2))
