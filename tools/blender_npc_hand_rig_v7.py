import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path(__file__).resolve().parents[1];OLD=R/'art/characters/npc_cast_idle_v6';OUT=R/'art/characters/npc_cast_idle_v7';OUT.mkdir(exist_ok=True)
def components(mesh,ids,cut):
 pos={i:tuple(round(v,4) for v in mesh.data.vertices[i].co) for i in ids}
 remain={v for v in pos.values() if v[2]<cut};adj={v:set() for v in remain}
 for e in mesh.data.edges:
  a,b=e.vertices
  if a in pos and b in pos and pos[a] in remain and pos[b] in remain:adj[pos[a]].add(pos[b]);adj[pos[b]].add(pos[a])
 groups=[]
 while remain:
  stack=[remain.pop()];part=[]
  while stack:
   a=stack.pop();part.append(a)
   for b in adj[a]:
    if b in remain:remain.remove(b);stack.append(b)
  if len(part)>8:groups.append(np.array(part))
 return sorted(groups,key=lambda p:p[:,0].mean())
def add_digits(rig,mesh):
 fittings=[]
 for side,sign in [('L',1),('R',-1)]:
  gi=mesh.vertex_groups['Hand.'+side].index
  ids=[v.index for v in mesh.data.vertices if any(g.group==gi and g.weight>.45 for g in v.groups)]
  cloud=np.array([mesh.data.vertices[i].co[:] for i in ids]);lo,hi=cloud[:,2].min(),cloud[:,2].max();cut=lo+.5*(hi-lo)
  groups=components(mesh,ids,cut)
  if not 3<=len(groups)<=5:
   for fraction in [.4,.35,.3,.25,.55,.6]:
    candidate_cut=lo+fraction*(hi-lo);candidate=components(mesh,ids,candidate_cut)
    if 3<=len(candidate)<=5:groups=candidate;cut=candidate_cut;break
  if not 1<=len(groups)<=5:raise RuntimeError(('Unsupported hand segmentation',side,len(groups)))
  for number,part in enumerate(groups,1):
   tip=part[part[:,2]<np.quantile(part[:,2],.22)].mean(0)
   base=part[part[:,2]>np.quantile(part[:,2],.75)].mean(0);base[2]=cut+.08*(hi-lo)
   # Extend each observed digit toward its knuckle; do not invent missing mesh fingers.
   joint=base+(tip-base)*.53
   fittings.append((side,number,Vector(base),Vector(joint),Vector(tip),part,ids,gi,sign))
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
 for side,n,base,joint,tip,*_ in fittings:
  parent=rig.data.edit_bones['Hand.'+side]
  for j,(a,b) in enumerate([(base,joint),(joint,tip)],1):
   eb=rig.data.edit_bones.new(f'Digit{n}.{j}.{side}');eb.head=a;eb.tail=b;eb.parent=parent;eb.use_connect=j==2;parent=eb
 bpy.ops.object.mode_set(mode='OBJECT')
 # Smooth assignment by nearest observed digit axis. Palm retains the existing wrist weights.
 for side in ['L','R']:
  fits=[f for f in fittings if f[0]==side];gi=fits[0][7];ids=fits[0][6]
  vg={f[1]:[mesh.vertex_groups.new(name=f'Digit{f[1]}.{j}.{side}') for j in [1,2]] for f in fits}
  for i in ids:
   v=mesh.data.vertices[i];p=v.co;choices=[]
   for f in fits:
    a,b=f[2],f[4];d=b-a;t=max(0,min(1,(p-a).dot(d)/d.length_squared));choices.append(((p-(a+d*t)).length,t,f))
   dist,t,f=min(choices,key=lambda q:q[0]);radius=.018 if len(ids)>700 else .014
   influence=min(1,max(0,t/.27))*min(1,max(0,(radius*1.4-dist)/(radius*.5)))
   if influence<.001:continue
   oldweight=next(g.weight for g in v.groups if g.group==gi);weight=oldweight*influence
   mesh.vertex_groups['Hand.'+side].add([i],oldweight-weight,'REPLACE')
   distal=max(0,min(1,(t-.40)/.23));vg[f[1]][0].add([i],weight*(1-distal),'REPLACE');vg[f[1]][1].add([i],weight*distal,'REPLACE')
 return fittings
reports={}
for key in ['sora','moru','naru','haeru']:
 D=OUT/key;D.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(OLD/key/(key+'_rigged_idle.blend')))
 s=bpy.context.scene;rig=next(o for o in s.objects if o.type=='ARMATURE');mesh=next(o for o in s.objects if o.type=='MESH');fits=add_digits(rig,mesh)
 action=rig.animation_data.action;action.name='Idle_'+key.capitalize()+'_RelaxedHands'
 s.frame_set(1);neutral_wrist=rig.pose.bones['Hand.L'].rotation_quaternion.copy()
 for frame in range(1,242,2):
  s.frame_set(frame);sec=(frame-1)/30;gesture=math.sin(math.pi*max(0,min(1,(sec-.2)/5.2)))**2 if key in ['sora','moru'] else 0
  if key=='moru':
   wrist=rig.pose.bones['Hand.L'];wrist.rotation_quaternion=neutral_wrist.slerp(wrist.rotation_quaternion,.35);wrist.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=wrist.name)
  for side,n,base,joint,tip,part,ids,gi,sign in fits:
   axis=(tip-base).cross(Vector((0,-sign,0))).normalized()
   for j,degrees in [(1,18+3*(n%3)),(2,14+3*(n%2))]:
    pb=rig.pose.bones[f'Digit{n}.{j}.{side}'];rest=pb.bone.matrix_local.to_quaternion();pb.rotation_mode='QUATERNION'
    supported=len([f for f in fits if f[0]==side]);degrees=degrees if supported>1 else degrees*.35
    angle=degrees*(1-.55*gesture if side=='L' else 1)+1.5*math.sin(4*math.pi*sec/8)
    pb.rotation_quaternion=Quaternion(rest.inverted()@axis,math.radians(angle));pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for curve in bag.fcurves:
     if 'Digit' in curve.data_path:
      for p in curve.keyframe_points:p.interpolation='BEZIER';p.handle_left_type='AUTO_CLAMPED';p.handle_right_type='AUTO_CLAMPED'
      curve.modifiers.new('CYCLES')
 first=None;previous=None;step=0;gap=0
 for frame in range(1,242):
  s.frame_set(frame);e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();coords=np.array([v.co[:] for v in m.vertices]);e.to_mesh_clear();assert np.isfinite(coords).all()
  if first is None:first=coords.copy()
  if previous is not None:step=max(step,float(np.linalg.norm(coords-previous,axis=1).max()))
  previous=coords
 gap=float(np.linalg.norm(coords-first,axis=1).max());assert gap<1e-5 and step<.026
 assert max(abs(sum(g.weight for g in v.groups)-1) for v in mesh.data.vertices)<1e-4
 s.frame_set(1);s.frame_start=1;s.frame_end=240
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(D/(key+'_rigged_idle.blend')))
 bpy.ops.export_scene.gltf(filepath=str(D/(key+'_rigged_idle.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=False,export_force_sampling=True,export_sampling_interpolation_fallback='LINEAR',export_morph=False)
 report=json.loads((OLD/key/'verification.json').read_text());report['clip']=action.name;report['audit']['bones']=len(rig.data.bones);report['audit']['max_adjacent_frame_step_m']=step;report['audit']['loop_gap_m']=gap
 report['hand_rig']={'digit_chains_per_hand':{side:len([f for f in fits if f[0]==side]) for side in ['L','R']},'joints_per_chain':2,'source_mesh_and_uv_unchanged':True,'weights_normalized':True,'note':'Chains follow separated source digit geometry; merged generated fingers are not reconstructed.'}
 report.pop('export_audit',None);reports[key]=report;(D/'verification.json').write_text(json.dumps(report,indent=2));print('HAND_RIG_READY',key,report['hand_rig'],flush=True)
(OUT/'verification.json').write_text(json.dumps(reports,indent=2))
