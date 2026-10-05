import bpy,json,math,struct,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10';author=A/'original_preserved_face_rig_v10.blend';runtime=A/'game_export_scene_v10.blend';bpy.ops.wm.open_mainfile(filepath=str(author));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];hp=rig.pose.bones['head'];native=[o for o in sc.objects if o.type=='MESH' and o.data.shape_keys and not o.hide_render];updated={}
def smooth(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
trees={};brow_points={}
for side in ['L','R']:
 o=bpy.data.objects['EYEBALL_original_'+side];o.data.calc_loop_triangles();trees[side]=BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
 brow_points[side]=[v.co.copy() for v in bpy.data.objects['BROW_original_'+side].data.vertices]
Y=[.058,.072,.085,.105,.13,.155,.18,.202,.218];U=[.084,.102,.13,.15,.159,.166,.178,.178,.145];B=[.083,.067,.051,.047,.046,.05,.065,.082,.10]
def blink(p,side):
 x,y,z=p;q=p.copy();sgn=1 if side=='L' else -1
 if sgn*y<.055 or sgn*y>.237 or x<.075 or z<.008 or z>.26:return q
 a=float(np.interp(abs(y),Y,U));b=float(np.interp(abs(y),Y,B));near=[p.z for p in brow_points[side] if abs(abs(p.y)-abs(y))<.012];fixed=min(a+.035,min(near)-.003) if near else a+.035;a=min(a,fixed-.012);seam=b+.22*(a-b);w=smooth(.075,.115,x)*(1-smooth(.224,.237,abs(y)))
 q.z+=(float(np.interp(z,[.008,b-.04,b,a,fixed,.32],[.008,b-.04,seam-.0001,seam+.0001,fixed,.32]))-z)*w
 hit,*_=trees[side].ray_cast(Vector((1,q.y,q.z)),Vector((-1,0,0)))
 if hit is not None and q.x<hit.x+.004:q.x+=(hit.x+.004-q.x)*w
 return q
for o in native:
 keys=o.data.shape_keys.key_blocks;base=keys[0]
 for side,label in [('L','Left'),('R','Right')]:
  if o.name.startswith(('EYEBALL','TEETH','TONGUE','CLAVICLE','EAR')):continue
  key=keys['!ex-eyeBlink'+label]
  for v,b in zip(key.data,base.data):v.co=b.co if o.name.startswith('BROW') else blink(b.co,side)
  for n,gain in [('eyeSquint',.32),('eyeWide',-.10)]:
   for v,b,k in zip(keys['!ex-'+n+label].data,base.data,key.data):v.co=b.co+(k.co-b.co)*gain
 for n in ['browInnerUp','browOuterUpLeft','browOuterUpRight','browDownLeft','browDownRight']:
  key=keys['!ex-'+n];sgn=1 if n.endswith('Left') else -1 if n.endswith('Right') else 0
  for v,b in zip(key.data,base.data):
   p=b.co;x,y,z=p;d=(v.co-p)*.5
   if o.name.startswith(('FACE','BROW')):
    w=math.exp(-((z-.205)/.055)**4)*smooth(.12,.18,x)*(1-smooth(.23,.27,abs(y)))
    if sgn:w*=smooth(-.015,.025,sgn*y)
    if n=='browInnerUp':d.z+=.016*(1-smooth(.075,.16,abs(y)))*w
    elif n.startswith('browOuter'):d.z+=.014*smooth(.09,.17,abs(y))*w
    else:d.z-=.011*w;d.y-=math.copysign(.0025*w,y)
   v.co=p+d
 for n in ['eyeBlinkLeft','eyeBlinkRight','eyeSquintLeft','eyeSquintRight','eyeWideLeft','eyeWideRight','browInnerUp','browOuterUpLeft','browOuterUpRight','browDownLeft','browDownRight']:
  key=keys['!ex-'+n];updated.setdefault(o.name,{})[n]=[(v.co-b.co).copy() for v,b in zip(key.data,base.data)]
def activate(n,f):
 a=bpy.data.actions[n];rig.animation_data.action=a;rig.animation_data.action_slot=a.slots[0];sc.frame_set(f);bpy.context.view_layer.update()
def skin_tree():
 vv=[];tt=[]
 for o in sc.objects:
  if o.type!='MESH' or o.hide_render or not (o.name.startswith(('FACE','LASH','tripo_part_','BROW'))):continue
  eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();start=len(vv);vv.extend(eo.matrix_world@v.co for v in me.vertices);tt.extend(tuple(start+i for i in t.vertices) for t in me.loop_triangles);eo.to_mesh_clear()
 return BVHTree.FromPolygons(vv,tt,all_triangles=True)
def coverage():
 skin=skin_tree();rows={}
 for side in ['L','R']:
  tree=trees[side];visible=0;total=0
  for y in np.linspace(.065,.199,44)*(1 if side=='L' else -1):
   for z in np.linspace(.038,.167,44):
    eye,*_=tree.ray_cast(Vector((1,y,z)),Vector((-1,0,0)))
    if eye is None:continue
    total+=1;hit,*_=skin.ray_cast(Vector((1,y,z)),Vector((-1,0,0)))
    if hit is None or hit.x<eye.x-.0002:visible+=1
  rows[side]={'sampled_eye_points':total,'visible_points':visible}
 return rows
activate('Blink',5);checks=coverage();print('CLOSED_EYE_COVERAGE',checks,flush=True)
cam=sc.camera
def render(n,target=Vector(),scale=1.2):
 cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
render('Blink');render('blink_detail',Vector((.2,.13,.11)),.27)
for n,f in [('Concern',31),('Determined',31),('Happy',31),('Surprise',31),('WinkLeft',8),('WinkRight',8)]:activate(n,f);render(n)
activate('IdleClosed',1);cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2;bpy.ops.wm.save_as_mainfile(filepath=str(author))
bpy.ops.wm.open_mainfile(filepath=str(runtime));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify']
for name,units in updated.items():
 o=bpy.data.objects[name];keys=o.data.shape_keys.key_blocks
 for n,delta in units.items():
  key=keys.get(n)
  if key:
   for v,b,d in zip(key.data,keys[0].data,delta):v.co=b.co+d
activate('IdleClosed',1);bpy.ops.wm.save_as_mainfile(filepath=str(runtime));bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if o==rig or (o.type=='MESH' and not o.hide_render and not o.name.startswith('WGT')):o.select_set(True)
bpy.context.view_layer.objects.active=rig
opts={'filepath':str(A/'character_face_clips_v10.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIONS','export_anim_single_armature':True,'export_morph_animation':True,'export_bake_animation':True,'export_frame_range':False,'export_anim_slide_to_zero':True,'export_merge_animation':'ACTION','export_morph_normal':True};available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());bpy.ops.export_scene.gltf(**{k:v for k,v in opts.items() if k in available});report=json.loads((A/'rig-verification.json').read_text());report['closed_eye_coverage']=checks;report['brow_landmark_corrections']=True;(A/'rig-verification.json').write_text(json.dumps(report,indent=2));print('V10_POLISHED')
