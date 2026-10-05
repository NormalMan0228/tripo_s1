"""Normalize Tripo motion, align gait phases and export reusable Godot character.

Video references guide review and timing; this does not claim video-to-mocap.
No grafted parts, invented facial geometry, or player-runtime Blender dependency.
"""
import bpy, json, math, statistics
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/production-lab-20261003'
DEST=ROOT/'labs/production_lab/assets';DEST.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'tripo/body/rig-original.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
rig.animation_data_clear();rig.animation_data_create();rig.name='Explorer_B_Production_Rig'
for o in meshes:
 o.name='Explorer_B_Cohesive_Surface'
 for p in o.data.polygons:p.use_smooth=True
 for mod in o.modifiers:
  if mod.type=='ARMATURE':mod.use_deform_preserve_volume=False
 for mat in o.data.materials:
  for n in mat.node_tree.nodes:
   if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=.35
   if n.type=='BSDF_PRINCIPLED':
    for slot in ['Metallic','Roughness']:
     for link in list(n.inputs[slot].links):mat.node_tree.links.remove(link)
    n.inputs['Metallic'].default_value=0;n.inputs['Roughness'].default_value=.78
    n.inputs['Specular IOR Level'].default_value=.24
scene=bpy.context.scene;scene.render.fps=60
audit={};actions={};gaits={}

def pose_at(action,t):
 rig.animation_data.action=action
 if action.slots:rig.animation_data.action_slot=action.slots[0]
 scene.frame_set(math.floor(t),subframe=t%1);bpy.context.view_layer.update()
 return {b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in rig.pose.bones}

for kind,subdir in [('idle','idle'),('walk','walk'),('run','motion')]:
 before=set(bpy.data.objects);existing=set(bpy.data.actions)
 bpy.ops.import_scene.gltf(filepath=str(OUT/f'tripo/{subdir}/preset-original.glb'))
 imported=[o for o in bpy.data.objects if o not in before]
 source_rig=next(o for o in imported if o.type=='ARMATURE')
 source_actions=[a for a in bpy.data.actions if a not in existing]
 source_action=next((a for a in source_actions if a.name.startswith(kind)),source_actions[0])
 # All sources derive from the same Tripo skin. Refuse incompatible skeletons.
 if [b.name for b in source_rig.data.bones]!=[b.name for b in rig.data.bones]:raise RuntimeError('incompatible_rig')
 source_rig.animation_data.action=None
 srcfps=60;start,end=source_action.frame_range;duration=(end-start)/srcfps
 frames=max(24,round(duration*60));duration=frames/60
 samples=[];positions=[];root_positions=[]
 for i in range(frames+1):
  t=start+(end-start)*i/frames
  for b in rig.pose.bones:b.rotation_mode='QUATERNION'
  pose_at(source_action,t)
  root_positions.append(rig.pose.bones['Root'].head.copy())
  positions.append({n:rig.pose.bones[n].head.copy() for n in ['Hip','L_Foot','R_Foot']})
  # The provider stores travel on Hip in this skin, not necessarily on Root.
  rig.pose.bones['Root'].matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
  hip=rig.pose.bones['Hip'];m=hip.matrix.copy()
  m.translation.x=rig.data.bones['Hip'].head_local.x
  m.translation.y=rig.data.bones['Hip'].head_local.y + .004*math.sin(2*math.pi*i/frames)
  hip.matrix=m;bpy.context.view_layer.update()
  samples.append({b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in rig.pose.bones})
 raw_drift=positions[-1]['Hip']-positions[0]['Hip']
 for o in imported:bpy.data.objects.remove(o,do_unlink=True)
 # Distribute endpoint mismatch smoothly, then circularly align left heel strike.
 first,last=samples[0],samples[-1]
 max_source_gap=0.0
 for n in first:
  max_source_gap=max(max_source_gap,first[n][1].rotation_difference(last[n][1]).angle)
  qfix=last[n][1].rotation_difference(first[n][1])
  delta=first[n][0]-last[n][0]
  for i in range(frames+1):
   w=i/frames;w=w*w*(3-2*w)
   loc,q,scale=samples[i][n]
   fixed=q@Quaternion((1,0,0,0)).slerp(qfix,w)
   samples[i][n]=(loc+delta*w,fixed,scale.lerp(first[n][2],w))
 samples[-1]={n:tuple(v.copy() for v in values) for n,values in samples[0].items()}
 phase_index=0
 if kind!='idle':
  floor=min(p['L_Foot'].z-r.z for p,r in zip(positions,root_positions))
  candidates=[i for i,p in enumerate(positions[:-1]) if p['L_Foot'].z-root_positions[i].z<floor+.045]
  phase_index=max(candidates or list(range(frames)),key=lambda i:positions[i]['L_Foot'].x-positions[i]['Hip'].x)
  samples=samples[phase_index:-1]+samples[:phase_index]+[samples[phase_index]]
 rig.animation_data.action=None;previous={}
 for i,sample in enumerate(samples):
  for bone in rig.pose.bones:
   loc,q,scale=sample[bone.name];bone.location=loc;bone.rotation_quaternion=q;bone.scale=scale
   if bone.name in previous and q.dot(previous[bone.name])<0:bone.rotation_quaternion.negate()
   previous[bone.name]=bone.rotation_quaternion.copy()
   bone.keyframe_insert('location',frame=i+1,group=bone.name)
   bone.keyframe_insert('rotation_quaternion',frame=i+1,group=bone.name)
   bone.keyframe_insert('scale',frame=i+1,group=bone.name)
  if i==0:rig.animation_data.action.name=kind
 action=rig.animation_data.action;action.use_fake_user=True;actions[kind]=action
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for k in fc.keyframe_points:k.interpolation='LINEAR'
 audit[kind]={'seconds':duration,'frames':frames+1,'source_root_drift_m':list(raw_drift),
              'source_max_loop_rotation_gap_deg':math.degrees(max_source_gap),'phase_shift_frames':phase_index,
              'normalized_root_drift_m':0,'normalized_loop_endpoint_gap':0}
 if kind!='idle':
  # Contact phase is measured on the normalized clip. World travel stays in motor.
  pts=[];right_pts=[]
  for i in range(frames):
   scene.frame_set(i+1);bpy.context.view_layer.update()
   pts.append(rig.pose.bones['L_Foot'].head.copy())
   right_pts.append(rig.pose.bones['R_Foot'].head.copy())
  floor=min(p.z for p in pts)
  mask=[p.z<floor+.035 for p in pts]
  right_floor=min(p.z for p in right_pts)
  right_mask=[p.z<right_floor+.035 for p in right_pts]
  span=max(p.x for p in pts)-min(p.x for p in pts)
  reference_speed=abs(raw_drift.x)/duration*1.7
  if reference_speed<.1:reference_speed=span/max(.2,sum(mask)/frames)/duration*1.7
  slopes=[-(pts[(i+1)%frames].x-pts[i].x)*frames*1.7 for i in range(frames-1)
          if mask[i] and mask[i+1] and pts[i+1].x<pts[i].x]
  contact_distance=statistics.median(slopes) if slopes else reference_speed*duration
  contact_distance=max(.5,min(3.2,contact_distance))
  gaits[kind]={'cycle_seconds':duration,'reference_speed_mps':reference_speed,
               'raw_root_cycle_distance_m':reference_speed*duration,
               'cycle_distance_m':contact_distance,'stance_fraction':sum(mask)/frames,
               'foot_span_m':span*1.7,'left_contact_mask':mask,'right_contact_mask':right_mask}
 for a in source_actions:
  if a!=action:bpy.data.actions.remove(a)
for kind,action in actions.items():action.name=kind
rig.animation_data.action=actions['idle'];scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(DEST/'explorer_b.glb'),export_format='GLB',use_selection=True,
 export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_anim_slide_to_zero=True,
 export_def_bones=True)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_b_reusable.blend'))
manifest={'source':'Tripo P2-20260801 detailed PBR, 40000 face limit',
 'rig':'v1.0-20240301 biped Tripo; 41 bones','clips_source':'Tripo preset; root and loop normalization in Blender',
 'video_reference':'Seedance 2.0, PixVerse V6, Kling V3 comparison; review reference, not automatic mocap',
 'no_grafted_parts':True,'bones':len(rig.data.bones),'height_scale':1.7,'forward_axis':'+X',
 'vertices':sum(len(o.data.vertices) for o in meshes),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),
 'individual_finger_animation':False,'facial_morphs':False,'clips':audit,'gaits':gaits,
 'review_status':'Requires Godot contact, transition and visual validation'}
(DEST/'motion_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(OUT/'motion-audit.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('REUSABLE_CHARACTER_READY',json.dumps({k:v for k,v in manifest.items() if k!='gaits'}))
