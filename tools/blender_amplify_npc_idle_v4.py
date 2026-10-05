import bpy, math, json, hashlib
import numpy as np
from mathutils import Vector,Quaternion
from pathlib import Path
R=Path(__file__).resolve().parents[1];OLD=R/'art/characters/npc_cast_idle_v3';OUT=R/'art/characters/npc_cast_idle_v4';OUT.mkdir(exist_ok=True)
descriptions={'sora':'Calm glance and nod with relaxed arm motion','moru':'Energetic shoulder lift and forearm gesture','naru':'Curious left-right looking with torso follow-through','haeru':'Relaxed head tilt and shoulder stretch'}
def pulse(t,a,b):
 if t<=a or t>=b:return 0.
 return math.sin(math.pi*(t-a)/(b-a))**2
def rotation(pb,x=0,y=0,z=0):
 rest=pb.bone.matrix_local.to_quaternion();q=Quaternion()
 for axis,angle in [(Vector((1,0,0)),x),(Vector((0,1,0)),y),(Vector((0,0,1)),z)]:q=q@Quaternion(rest.inverted()@axis,math.radians(angle))
 pb.rotation_mode='QUATERNION';pb.rotation_quaternion=q
def animate(rig,key,arm):
 rig.animation_data_clear()
 for pb in rig.pose.bones:pb.rotation_quaternion=Quaternion();pb.location=(0,0,0)
 rig.animation_data_create();a=bpy.data.actions.new('Idle_'+key.capitalize()+'_Visible');rig.animation_data.action=a
 for frame in range(1,242,2):
  sec=(frame-1)/30;t=2*math.pi*sec/8;breath=math.sin(2*t);shift=math.sin(t)
  if key=='sora':
   g=pulse(sec,1,5);roll=2.8*shift;turn=11*g;nod=3.5*math.sin(2*t)+5*pulse(sec,4.2,6.5);tilt=2*shift;lift=3*g;elbow=5*g;fore=3*math.sin(t+.4)
  elif key=='moru':
   g=pulse(sec,.8,3.8);roll=4.0*shift;turn=-9*pulse(sec,3.5,6.8);nod=2.8*math.sin(2*t);tilt=3*shift;lift=11*g;elbow=19*g;fore=5*math.sin(t+.6)
  elif key=='naru':
   left=pulse(sec,.4,3.4);right=pulse(sec,3.7,7.6);g=left+right;roll=3.2*shift;turn=-16*left+15*right;nod=3*math.sin(2*t);tilt=4.5*shift;lift=4*g;elbow=7*right;fore=3.5*math.sin(t)
  else:
   g=pulse(sec,2,6.6);roll=2.8*shift;turn=10*g;nod=3*math.sin(2*t);tilt=6*g;lift=7*g;elbow=10*g;fore=3.5*math.sin(t+.8)
  rotation(rig.pose.bones['Spine'],x=roll,y=1.6*breath)
  rotation(rig.pose.bones['Chest'],x=-.25*roll,y=-.6*breath,z=.18*turn)
  rotation(rig.pose.bones['Neck'],x=.25*tilt,y=.25*nod,z=.12*turn)
  rotation(rig.pose.bones['Head'],x=tilt,y=nod,z=turn)
  for side,sgn in [('L',1),('R',-1)]:
   amount=1 if side=='L' else .65
   rotation(rig.pose.bones['Shoulder.'+side],x=sgn*lift*.22,y=1.1*breath)
   rotation(rig.pose.bones['UpperArm.'+side],x=-sgn*(arm-lift*amount+1.8*math.sin(t+sgn*.5)),y=-fore)
   rotation(rig.pose.bones['Forearm.'+side],y=-4-elbow*amount-2*math.sin(2*t+sgn))
   rotation(rig.pose.bones['Hand.'+side],x=2*math.sin(t+sgn),y=-1.2)
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
 gap=float(np.linalg.norm(coords-first,axis=1).max());assert gap<1e-5 and max_step<.025 and motion>.06 and foot_motion<1e-5
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
