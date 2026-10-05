"""Body rigs and individual eight-second idle clips; static source files stay intact."""
import bpy, bmesh, math, json, hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector, Quaternion
from mathutils.kdtree import KDTree

R=Path(__file__).resolve().parents[1]
SOURCE=R/'art/characters/npc_cast_closed_v2'
OUT=R/'art/characters/npc_cast_idle_v3'
OUT.mkdir(parents=True,exist_ok=True)
PARAMS={
 'sora':dict(height=1.65,hip=.485,shoulder=.715,neck=.77,head=.79,elbow=.59,wrist=.48,arm=10,title='Idle_Sora_Calm',phase=.0,sway=.75,look=1.8),
 'moru':dict(height=1.65,hip=.49,shoulder=.725,neck=.785,head=.81,elbow=.59,wrist=.48,arm=12,title='Idle_Moru_Energetic',phase=.8,sway=1.6,look=2.2),
 'naru':dict(height=1.55,hip=.46,shoulder=.665,neck=.72,head=.745,elbow=.535,wrist=.435,arm=6,title='Idle_Naru_Curious',phase=1.7,sway=1.0,look=5.0),
 'haeru':dict(height=1.85,hip=.51,shoulder=.755,neck=.815,head=.835,elbow=.61,wrist=.475,arm=8,title='Idle_Haeru_Relaxed',phase=2.6,sway=.65,look=1.8),
}

def smooth(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)

def make_rig(key,p):
 h=p['height'];data=bpy.data.armatures.new(key+'_Skeleton');rig=bpy.data.objects.new(key+'_BodyRig',data)
 bpy.context.scene.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True)
 bpy.ops.object.mode_set(mode='EDIT')
 def bone(name,a,b,parent=None,deform=True):
  v=data.edit_bones.new(name);v.head=Vector(a)*h;v.tail=Vector(b)*h;v.use_deform=deform
  if parent:v.parent=data.edit_bones[parent]
  v.align_roll(Vector((1,0,0)));return v
 hip=p['hip'];neck=p['neck'];shoulder=p['shoulder'];cx=-.018
 bone('Root',(0,0,0),(0,0,.07),deform=False)
 bone('Hips',(cx,0,hip),(cx,0,hip+.065),'Root')
 bone('Spine',(cx,0,hip+.065),(cx,0,shoulder-.08),'Hips')
 bone('Chest',(cx,0,shoulder-.08),(cx,0,neck-.025),'Spine')
 bone('Neck',(cx,0,neck-.025),(cx,0,p['head']),'Chest')
 bone('Head',(cx,0,p['head']),(cx,0,.96),'Neck')
 for side,sgn in [('L',1),('R',-1)]:
  shoulderpt=(cx,.112*sgn,shoulder);elbow=(cx,.168*sgn,p['elbow']);wrist=(cx,.218*sgn,p['wrist'])
  bone('Shoulder.'+side,(cx,.028*sgn,shoulder),shoulderpt,'Chest')
  bone('UpperArm.'+side,shoulderpt,elbow,'Shoulder.'+side)
  bone('Forearm.'+side,elbow,wrist,'UpperArm.'+side)
  bone('Hand.'+side,wrist,(cx,.242*sgn,p['wrist']-.045),'Forearm.'+side)
  hippt=(cx,.075*sgn,hip);knee=(cx+.012,.09*sgn,.285);ankle=(cx,.103*sgn,.065)
  bone('Thigh.'+side,hippt,knee,'Hips')
  bone('Calf.'+side,knee,ankle,'Thigh.'+side)
  bone('Foot.'+side,ankle,(.065,.103*sgn,.022),'Calf.'+side)
  bone('Toe.'+side,(.065,.103*sgn,.022),(.1,.103*sgn,.022),'Foot.'+side)
 bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True;data.display_type='OCTAHEDRAL'
 return rig

def bind(obj,rig,p):
 # Weld only a temporary binding proxy, so UV seams and source vertices are unchanged.
 proxy=bpy.data.objects.new('BIND_PROXY',obj.data.copy());bpy.context.scene.collection.objects.link(proxy)
 bm=bmesh.new();bm.from_mesh(proxy.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bm.to_mesh(proxy.data);bm.free()
 bpy.ops.object.select_all(action='DESELECT');proxy.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
 try:bpy.ops.object.parent_set(type='ARMATURE_AUTO')
 except RuntimeError:pass
 kd=KDTree(len(proxy.data.vertices))
 for v in proxy.data.vertices:kd.insert(v.co,v.index)
 kd.balance()
 names=[b.name for b in rig.data.bones if b.use_deform]
 groups={n:obj.vertex_groups.new(name=n) for n in names}
 h=p['height'];fallback=0;fixed_head=0
 for v in obj.data.vertices:
  _,i,_=kd.find(v.co)
  weights={proxy.vertex_groups[g.group].name:g.weight for g in proxy.data.vertices[i].groups if g.weight>1e-6 and proxy.vertex_groups[g.group].name in groups}
  z=v.co.z/h
  if not weights:
   fallback+=1
   # Local, anatomy-specific candidates prevent one limb leaking into the other.
   side='L' if v.co.y>0 else 'R'
   if z<p['hip']-.05:candidates=['Hips','Thigh.'+side,'Calf.'+side,'Foot.'+side,'Toe.'+side]
   elif abs(v.co.y)/h>.14 and z<p['shoulder']+.02:candidates=['Shoulder.'+side,'UpperArm.'+side,'Forearm.'+side,'Hand.'+side]
   else:candidates=['Hips','Spine','Chest','Neck','Head']
   for n in candidates:
    b=rig.data.bones[n];a=b.head_local;t=b.tail_local;d=t-a
    u=max(0,min(1,(v.co-a).dot(d)/d.length_squared));distance=(v.co-a.lerp(t,u)).length
    weights[n]=1/max(distance,.012*h)**6
  # The upper face, eyes, ears and crown follow Head rigidly, with a neck transition.
  blend=smooth(p['head']-.045,p['head']+.012,z)
  if blend>0:
   total=sum(weights.values());weights={n:w/total*(1-blend) for n,w in weights.items()};weights['Head']=weights.get('Head',0)+blend;fixed_head+=1
  # Boots are stationary in the idle clips; discard torso/arm spill into feet.
  if z<.09:
   side='L' if v.co.y>0 else 'R';weights={'Foot.'+side:1.}
  weights=dict(sorted(weights.items(),key=lambda a:a[1],reverse=True)[:4]);total=sum(weights.values())
  for n,w in weights.items():groups[n].add([v.index],w/total,'REPLACE')
 obj.parent=rig;modifier=obj.modifiers.new('Body skin deformation','ARMATURE');modifier.object=rig
 proxy_data=proxy.data;bpy.data.objects.remove(proxy,do_unlink=True);bpy.data.meshes.remove(proxy_data)
 return {'method':'Bone heat on welded temporary proxy, anatomical fallback, rigid upper head, planted boots','fallback_vertices':fallback,'head_corrected_vertices':fixed_head,'max_influences':4}

def rotation(pb,x=0,y=0,z=0):
 rest=pb.bone.matrix_local.to_quaternion();q=Quaternion()
 for axis,angle in [(Vector((1,0,0)),x),(Vector((0,1,0)),y),(Vector((0,0,1)),z)]:
  q=q @ Quaternion(rest.inverted()@axis,math.radians(angle))
 pb.rotation_mode='QUATERNION';pb.rotation_quaternion=q

def animate(rig,p):
 rig.animation_data_create();action=bpy.data.actions.new(p['title']);rig.animation_data.action=action
 for frame in range(1,242,3):
  t=2*math.pi*(frame-1)/240;phase=p['phase'];breath=math.sin(2*t+phase);sway=math.sin(t+phase);look=math.sin(t-phase)
  rotation(rig.pose.bones['Spine'],x=p['sway']*sway,y=.55*breath)
  rotation(rig.pose.bones['Chest'],x=-.35*p['sway']*sway,y=-.25*breath,z=.45*math.sin(t+phase))
  rotation(rig.pose.bones['Neck'],y=.25*math.sin(2*t-phase))
  rotation(rig.pose.bones['Head'],x=.45*math.sin(t+.4),y=.7*math.sin(2*t+phase),z=p['look']*look)
  for side,sgn in [('L',1),('R',-1)]:
   rotation(rig.pose.bones['Shoulder.'+side],y=.25*breath)
   rotation(rig.pose.bones['UpperArm.'+side],x=-sgn*(p['arm']+.55*math.sin(t+phase+sgn*.5)),y=.6*math.sin(t+sgn))
   rotation(rig.pose.bones['Forearm.'+side],y=1.4+.35*math.sin(2*t+sgn+phase))
   rotation(rig.pose.bones['Hand.'+side],x=.5*math.sin(t+sgn),y=-.6)
  for pb in rig.pose.bones:
   pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for curve in bag.fcurves:
     for key in curve.keyframe_points:key.interpolation='BEZIER';key.handle_left_type='AUTO';key.handle_right_type='AUTO'
     curve.modifiers.new('CYCLES')
 action.use_fake_user=True;action['duration_seconds']=8;action['loop']=True
 return action

def validate(obj,rig):
 first=None;last=None;prev=None;peak_step=0;peak_displacement=0;feet_move=0
 foot_indices=np.array([v.index for v in obj.data.vertices if v.co.z<.12])
 for frame in range(1,242):
  bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
  p=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',p);p=p.reshape(-1,3);evaluated.to_mesh_clear()
  assert np.isfinite(p).all()
  if first is None:first=p.copy()
  else:peak_step=max(peak_step,float(np.linalg.norm(p-prev,axis=1).max()))
  peak_displacement=max(peak_displacement,float(np.linalg.norm(p-first,axis=1).max()))
  feet_move=max(feet_move,float(np.linalg.norm(p[foot_indices]-first[foot_indices],axis=1).max()))
  prev=p.copy();last=p
 gap=float(np.linalg.norm(last-first,axis=1).max());assert gap<1e-5 and peak_step<.015 and peak_displacement>.005 and feet_move<1e-5
 missing=sum(not v.groups for v in obj.data.vertices);assert missing==0
 return {'frames_checked':241,'loop_gap_m':gap,'max_adjacent_frame_step_m':peak_step,'max_motion_m':peak_displacement,'planted_boot_displacement_m':feet_move,'unweighted_vertices':missing,'bones':len(rig.data.bones)}

reports={}
for key,p in PARAMS.items():
 O=OUT/key;O.mkdir(exist_ok=True);bpy.ops.wm.read_factory_settings(use_empty=True)
 source=SOURCE/key/(key+'_static.glb');bpy.ops.import_scene.gltf(filepath=str(source));scene=bpy.context.scene
 obj=next(o for o in scene.objects if o.type=='MESH');obj.name=key+'_SkinnedMesh'
 # Normalize the glTF import transform without changing world-space geometry.
 bpy.context.view_layer.update();obj.data.transform(obj.matrix_world);obj.matrix_world.identity();obj.parent=None
 for o in list(scene.objects):
  if o.type=='EMPTY':bpy.data.objects.remove(o,do_unlink=True)
 original=np.array([v.co for v in obj.data.vertices]);rig=make_rig(key,p);binding=bind(obj,rig,p);action=animate(rig,p)
 scene.render.fps=30;scene.frame_start=1;scene.frame_end=240;scene.frame_set(1)
 audit=validate(obj,rig);assert np.array_equal(original,np.array([v.co for v in obj.data.vertices]))
 for im in bpy.data.images:
  if im.has_data and not im.packed_file:im.pack()
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':
    s=area.spaces.active;s.shading.type='MATERIAL';s.region_3d.view_location=(0,0,p['height']*.5);s.region_3d.view_distance=p['height']*1.6;s.region_3d.view_rotation=Vector((-1,0,0)).to_track_quat('-Z','Y');s.region_3d.view_perspective='ORTHO'
 scene.frame_set(1);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);obj.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(O/(key+'_rigged_idle.blend')))
 bpy.ops.export_scene.gltf(filepath=str(O/(key+'_rigged_idle.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=False,export_force_sampling=True,export_sampling_interpolation_fallback='LINEAR',export_morph=False)
 reports[key]={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_geometry_and_uv_unchanged':True,'body_rig':True,'face_rig':False,'individual_finger_rig':False,'clip':p['title'],'duration_seconds':8,'fps':30,'binding':binding,'audit':audit,'vertices':len(obj.data.vertices),'triangles':sum(len(f.vertices)-2 for f in obj.data.polygons)}
 (O/'verification.json').write_text(json.dumps(reports[key],indent=2))
 print('NPC_RIG_IDLE_EXPORTED',key,json.dumps(audit),flush=True)
(OUT/'verification.json').write_text(json.dumps(reports,indent=2))
