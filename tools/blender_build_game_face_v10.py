"""Preserved source Basis + fitted facial controls + separate game Actions and a closed-rest runtime copy."""
import bpy,json,math,hashlib,struct,numpy as np
from pathlib import Path
from mathutils import Vector
from bl_ext.user_default.mpfb.services.faceservice import FaceService
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10';bpy.ops.wm.open_mainfile(filepath=str(A/'face_fitting_workbench.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];hp=rig.pose.bones['head'];native=[o for o in sc.objects if o.type=='MESH' and not o.hide_render and not o.name.startswith(('WGT','HAIR'))];head=bpy.data.objects['FACE_original_user_GLb'];rig.animation_data_clear()
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
units=['jawOpen','jawLeft','jawRight','jawForward','eyeBlinkLeft','eyeBlinkRight','eyeWideLeft','eyeWideRight','eyeSquintLeft','eyeSquintRight','browDownLeft','browDownRight','browInnerUp','browOuterUpLeft','browOuterUpRight','cheekSquintLeft','cheekSquintRight','cheekPuff','noseSneerLeft','noseSneerRight','mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','mouthPucker','mouthFunnel','mouthPressLeft','mouthPressRight','mouthStretchLeft','mouthStretchRight','mouthDimpleLeft','mouthDimpleRight','mouthUpperUpLeft','mouthUpperUpRight','mouthLowerDownLeft','mouthLowerDownRight']
controls=units+['gazeYaw','gazePitch'];raw={o.name:[v.co.copy() for v in o.data.shape_keys.key_blocks[0].data] for o in native};closed={o.name:[v.co.copy() for v in o.data.shape_keys.key_blocks['RestClosed'].data] for o in native};source_hash=hashlib.sha256((R/'art/characters/explorer_b_user_head_v8/source_user_head.glb').read_bytes()).hexdigest()
def smooth(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
def local_delta(o,p,n):
 x,y,z=p;d=Vector();side=1 if n.endswith('Left') else -1 if n.endswith('Right') else 0
 s=(smooth(-.018,.022,side*y) if side else 1.);front=smooth(.09,.19,x)
 if o.name.startswith(('EYEBALL','EAR','CLAVICLE')):return d
 if n.startswith('jaw'):
  w=front*(1-smooth(-.085,-.03,z))*(1-smooth(.12,.22,abs(y)))
  if n=='jawLeft':d.y=.010*w
  elif n=='jawRight':d.y=-.010*w
  elif n=='jawForward':d.x=.010*w
  if o.name.startswith(('TEETH_lower','TONGUE')):d=Vector((.01 if n=='jawForward' else 0,.01 if n=='jawLeft' else -.01 if n=='jawRight' else 0,0))
  if o.name.startswith('TEETH_upper'):d=Vector()
  return d
 if o.name.startswith(('TEETH','TONGUE')):return d
 if n.startswith('mouth'):
  w=front*math.exp(-((z+.095)/.040)**4)*(1-smooth(.10,.15,abs(y)));corner=smooth(.018,.075,abs(y));g=w*s
  if 'Smile' in n:d.z=.007*corner*g;d.y=math.copysign(.0025*corner*g,y)
  elif 'Frown' in n:d.z=-.007*corner*g
  elif n in ['mouthPucker','mouthFunnel']:d.x=(.014 if n=='mouthPucker' else .009)*w;d.y=-y*(.19 if n=='mouthPucker' else .12)*w
  elif 'Press' in n:d.z=-(z-(-.095+.006*min(1,(abs(y)/.105)**2)))*.24*g;d.x=-.002*g
  elif 'Stretch' in n:d.y=math.copysign(.006*corner*g,y)
  elif 'Dimple' in n:d.x=-.005*corner*g;d.z=.002*corner*g
  elif 'UpperUp' in n:d.z=.007*g*smooth(-.096,-.089,z)
  elif 'LowerDown' in n:d.z=-.007*g*(1-smooth(-.100,-.093,z))
 elif n.startswith('cheek'):
  w=front*math.exp(-((z-.02)/.055)**2-((abs(y)-.155)/.080)**2)*s
  if 'Puff' in n:d.x=.009*w;d.y=math.copysign(.004*w,y)
  else:d.z=.004*w;d.x=.003*w
 elif n.startswith('noseSneer'):
  w=math.exp(-((z+.015)/.027)**2-((abs(y)-.035)/.035)**2)*smooth(.22,.28,x)*s;d.z=.004*w
 return d
for o in native:
 o.data.shape_keys.animation_data_clear();keys=o.data.shape_keys.key_blocks
 for name in units:
  key=keys.get('!ex-'+name) or o.shape_key_add(name='!ex-'+name);key.value=0.
  if name.startswith('eyeBlink'):continue
  if name.startswith('brow'):
   for v,b in zip(key.data,raw[o.name]):
    delta=v.co-b
    # Preserve MPFB donor brow units; restrict their falloff to the brow region.
    if not o.name.startswith(('BROW','FACE')):delta=Vector()
    else:delta*=smooth(.10,.16,b.z)
    if delta.length>.012:delta*=.012/delta.length
    v.co=b+delta
  elif name.startswith(('eyeWide','eyeSquint')):
   blink=keys['!ex-eyeBlink'+('Left' if name.endswith('Left') else 'Right')]
   for v,b,bl in zip(key.data,raw[o.name],blink.data):
    delta=(bl.co-b)*(.32 if name.startswith('eyeSquint') else -.10);v.co=b+delta
  else:
   for v,b,p in zip(key.data,raw[o.name],closed[o.name]):v.co=b+local_delta(o,p,name)
 for name in units:
  key=keys['!ex-'+name];dr=key.driver_add('value').driver;dr.expression='v';v=dr.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["head"]["'+name+'"]'
  if name.startswith(('eyeWide','eyeSquint')):
   vv=dr.variables.new();vv.name='blink';vv.type='SINGLE_PROP';vv.targets[0].id=rig;vv.targets[0].data_path='pose.bones["head"]["eyeBlink'+('Left' if name.endswith('Left') else 'Right')+'"]';dr.expression='v*(1-blink)'
 key=keys['RestClosed'];dr=key.driver_add('value').driver;dr.expression='1-op';v=dr.variables.new();v.name='op';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["head"]["jawOpen"]'
for name in controls:hp[name]=0.;hp.id_properties_ui(name).update(min=-1 if name.startswith('gaze') else 0,max=1,description='Original source opens at jawOpen=1; closed rest at 0' if name=='jawOpen' else name)
for side in ['L','R']:
 pb=rig.pose.bones['eye.'+side];pb.rotation_mode='XYZ'
 for index,prop,gain in [(2,'gazeYaw',.085),(0,'gazePitch',.05)]:
  dr=pb.driver_add('rotation_euler',index).driver;dr.expression=str(gain)+'*g';v=dr.variables.new();v.name='g';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["head"]["'+prop+'"]'
presets={'IdleClosed':{},'Smile':{'mouthSmileLeft':.50,'mouthSmileRight':.50},'Happy':{'mouthSmileLeft':.75,'mouthSmileRight':.75,'cheekSquintLeft':.45,'cheekSquintRight':.45,'browOuterUpLeft':.18,'browOuterUpRight':.18},'Concern':{'browInnerUp':.70,'mouthFrownLeft':.55,'mouthFrownRight':.55,'eyeSquintLeft':.12,'eyeSquintRight':.12},'Determined':{'browDownLeft':.55,'browDownRight':.55,'mouthPressLeft':.40,'mouthPressRight':.40,'eyeSquintLeft':.35,'eyeSquintRight':.35},'Surprise':{'browOuterUpLeft':.70,'browOuterUpRight':.70,'browInnerUp':.2,'jawOpen':.70,'eyeWideLeft':.40,'eyeWideRight':.40},'Pucker':{'mouthPucker':.80}}
specs=[]
for name,pose in presets.items():
 length=90 if name in ['IdleClosed','Smile','Pucker','Surprise'] else 120;frames=[(1,{}),(16,{}),(31,pose),(length-30,pose),(length,{})];specs.append((name,length,frames,'face',name=='IdleClosed'))
specs.extend([('TalkOpen',60,[(1,{}),(12,{'jawOpen':.60}),(24,{'jawOpen':.1}),(39,{'jawOpen':.9}),(60,{})],'face',False),('Blink',15,[(1,{}),(3,{'eyeBlinkLeft':.20,'eyeBlinkRight':.20}),(5,{'eyeBlinkLeft':1.,'eyeBlinkRight':1.}),(6,{'eyeBlinkLeft':1.,'eyeBlinkRight':1.}),(9,{'eyeBlinkLeft':.15,'eyeBlinkRight':.15}),(12,{}),(15,{})],'blink',False),('WinkLeft',45,[(1,{}),(8,{'eyeBlinkLeft':1.}),(24,{'eyeBlinkLeft':1.}),(38,{}),(45,{})],'blink',False),('WinkRight',45,[(1,{}),(8,{'eyeBlinkRight':1.}),(24,{'eyeBlinkRight':1.}),(38,{}),(45,{})],'blink',False),('LookAround',120,[(1,{}),(25,{'gazeYaw':.80,'gazePitch':.20}),(50,{}),(80,{'gazeYaw':-.80,'gazePitch':-.10}),(105,{}),(120,{})],'gaze',False)])
def curves(a):return list(a.fcurves) if hasattr(a,'fcurves') else [f for l in a.layers for s in l.strips for b in s.channelbags for f in b.fcurves]
clips=[]
for name,length,frames,layer,loop in specs:
 rig.animation_data_create();rig.animation_data.action=None
 for prop in controls:
  for f,pose in frames:hp[prop]=float(pose.get(prop,0));hp.keyframe_insert(data_path='["'+prop+'"]',frame=f)
 action=rig.animation_data.action;action.name=name;action.use_fake_user=True;action.use_frame_range=True;action.frame_start=1;action.frame_end=length
 for fc in curves(action):
  for k in fc.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
 track=rig.animation_data.nla_tracks.new();track.name=name;track.mute=True;strip=track.strips.new(name,1,action);strip.action_frame_start=1;strip.action_frame_end=length
 clips.append({'name':name,'frames':length,'fps':30,'duration_seconds':(length-1)/30,'layer':layer,'loop':loop,'peak_frame':31 if layer=='face' and name!='TalkOpen' else 5 if layer=='blink' else 25 if layer=='gaze' else 39})
def action(name):
 a=bpy.data.actions[name];rig.animation_data.action=a;rig.animation_data.action_slot=a.slots[0]
action('IdleClosed');sc.frame_start=1;sc.frame_end=90;sc.render.fps=30;sc.frame_set(1);bpy.context.view_layer.update()
# Two independent oracles: source mesh and Basis are unchanged; resetting the pose recovers the original.
errors={}
for o in native:errors[o.name]=max((v.co-p).length for v,p in zip(o.data.shape_keys.key_blocks[0].data,raw[o.name]));assert errors[o.name]==0
rig.animation_data.action=None
for prop in controls:hp[prop]=1. if prop=='jawOpen' else 0.
rig.update_tag();bpy.context.view_layer.update();restore={}
for o in native:
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();restore[o.name]=max((v.co-p).length for v,p in zip(me.vertices,raw[o.name]));eo.to_mesh_clear()
assert max(restore.values())<1e-6,restore
action('IdleClosed');sc.frame_set(1);bpy.context.view_layer.update()
note=bpy.data.texts.get('ORIGINAL_FACE_RESTORATION');note.clear();note.write('V10: ORIGINAL SOURCE BASIS, UV, MATERIALS AND TOPOLOGY PRESERVED. Closed neutral is a reversible RestClosed shape key. jawOpen=0 closed, jawOpen=1 original source open. 36 facial controls plus 2 gaze controls on Rigify head. MPFB donor brow targets retained, native eye/lip fitting added. Individual Actions IdleClosed/Smile/Happy/Concern/Determined/Surprise/Pucker/TalkOpen/Blink/WinkLeft/WinkRight/LookAround. Choose an Action in the Dope Sheet Action Editor; all start at 1. Blink range 1-15, wink 1-45, talk 1-60, others 1-90/120. No phoneme/audio lipsync. Runtime copy bakes the closed default, renames morph targets and reduces only the hair.\n')
author=A/'original_preserved_face_rig_v10.blend';bpy.ops.wm.save_as_mainfile(filepath=str(author));sc.render.engine='CYCLES';sc.cycles.samples=24;cam=sc.camera;cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2
for c in clips:
 action(c['name']);sc.frame_set(c['peak_frame']);bpy.context.view_layer.update();sc.render.filepath=str(A/(c['name']+'.png'));bpy.ops.render.render(write_still=True)
action('IdleClosed');sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(author))
report={'source_sha256':source_hash,'source_basis_error':errors,'original_open_recovery_error':restore,'original_head_vertices':len(head.data.vertices),'original_UV_materials_topology_preserved':True,'closed_rest_is_separate_shape_key':True,'units':units,'gaze_controls':['gazeYaw','gazePitch'],'clips':clips,'addons':['MPFB','Rigify'],'MPFB_role':'retargeted donor brow units and FaceService naming; native customized lip and lid targets','credits':0}
# Rebase only a separate runtime copy. Author file above retains the untouched original Basis.
for o in native:
 keys=o.data.shape_keys.key_blocks;oldraw=raw[o.name];newbase=closed[o.name];o.data.shape_keys.animation_data_clear()
 for key in keys:
  if key.name=='RestClosed':continue
  if key==keys[0]:
   for v,p in zip(key.data,newbase):v.co=p
  elif key.name=='!ex-jawOpen':
   for v,p in zip(key.data,oldraw):v.co=p
  else:
   for v,p,b in zip(key.data,newbase,oldraw):v.co+=p-b
 o.shape_key_remove(keys['RestClosed']);keys[0].name='Basis_game_closed_rest'
 for key in list(keys)[1:]:
  if max((v.co-b.co).length for v,b in zip(key.data,keys[0].data))<1e-8:o.shape_key_remove(key);continue
  name=key.name.removeprefix('!ex-');key.name=name;dr=key.driver_add('value').driver;dr.expression='v';v=dr.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["head"]["'+name+'"]'
  if name.startswith(('eyeWide','eyeSquint')):
   vv=dr.variables.new();vv.name='blink';vv.type='SINGLE_PROP';vv.targets[0].id=rig;vv.targets[0].data_path='pose.bones["head"]["eyeBlink'+('Left' if name.endswith('Left') else 'Right')+'"]';dr.expression='v*(1-blink)'
hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];bpy.ops.object.select_all(action='DESELECT');hair.select_set(True);bpy.context.view_layer.objects.active=hair;deci=hair.modifiers.new('Runtime_hair_reduction','DECIMATE');deci.ratio=.065;bpy.ops.object.modifier_apply(modifier=deci.name);hair.data.calc_loop_triangles();report['runtime_hair_triangles']=len(hair.data.loop_triangles)
action('IdleClosed');sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(A/'game_export_scene_v10.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in native+[hair,rig]:o.select_set(True)
bpy.context.view_layer.objects.active=rig;options={'filepath':str(A/'character_face_clips_v10.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIONS','export_anim_single_armature':True,'export_morph_animation':True,'export_bake_animation':True,'export_frame_range':False,'export_anim_slide_to_zero':True,'export_merge_animation':'ACTION','export_morph_normal':True};available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());bpy.ops.export_scene.gltf(**{k:v for k,v in options.items() if k in available})
buf=(A/'character_face_clips_v10.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);names=[a['name'] for a in g['animations']];assert set(names)=={c['name'] for c in clips},names;assert g['skins'];assert all('bufferView' in i for i in g['images']);report['GLB_clips']=names;report['status']='exported_awaiting_engine_validation';(A/'rig-verification.json').write_text(json.dumps(report,indent=2));(A/'expression-clips.json').write_text(json.dumps(clips,indent=2));print('V10_INDEPENDENT_CLIPS_EXPORTED',names)
