"""Original Explorer B animation authoring. No imported clips or retargeting.

Blender 4.5: analytic two-bone posing, independently designed contact paths,
body counter-motion and gesture timing, baked to editable bone keyframes.
The Tripo rig supplies skin weights only. The authored axes are X-forward/Z-up.
"""
import bpy, math, json, sys
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion
OUT=Path(__file__).resolve().parents[1]/'artifacts/characters/explorer-b-v1'
TAU=math.tau
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'rig-original.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
rig.name='Explorer_B_OriginalMotion_Rig'
for o in list(bpy.context.scene.objects):
 if o.type=='MESH' and not any(m.type=='ARMATURE' for m in o.modifiers):bpy.data.objects.remove(o,do_unlink=True)
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
rig.animation_data_clear();rig.animation_data_create()
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
for o in meshes:
 o.name='Explorer_B_SkinnedMesh'
 for poly in o.data.polygons:poly.use_smooth=True
 for mod in o.modifiers:
  if mod.type=='ARMATURE':mod.use_deform_preserve_volume=False
 # Controlled cloth response; keep original base-color and normal maps.
 for m in o.data.materials:
  for node in m.node_tree.nodes:
   if node.type=='BSDF_PRINCIPLED':
    for inp in ('Metallic','Roughness'):
     for link in list(node.inputs[inp].links):m.node_tree.links.remove(link)
    node.inputs['Metallic'].default_value=0
    node.inputs['Roughness'].default_value=.78
    node.inputs['Specular IOR Level'].default_value=.22
pb=rig.pose.bones;rest={b.name:b.matrix_local.copy() for b in rig.data.bones}
heads={b.name:b.head_local.copy() for b in rig.data.bones}
def rot(axis,deg):return Quaternion(Vector(axis),math.radians(deg))
def update():bpy.context.view_layer.update()
def reset():
 for b in pb:b.rotation_mode='QUATERNION';b.matrix_basis=Matrix.Identity(4)
 update()
def rotate_inherited(name,q):
 b=pb[name];m=b.matrix.copy();b.matrix=Matrix.Translation(m.translation)@q.to_matrix().to_4x4()@m.to_3x3().to_4x4();update()
def place_segment(name,start,end,rest_end):
 direction=(end-start).normalized();old=(rest_end-heads[name]).normalized()
 q=old.rotation_difference(direction)
 pb[name].matrix=Matrix.Translation(start)@q.to_matrix().to_4x4()@rest[name].to_3x3().to_4x4();update()
def chain(upper,lower,endbone,target,pole):
 a=pb[upper].head.copy();l1=(heads[lower]-heads[upper]).length;l2=(heads[endbone]-heads[lower]).length
 v=target-a;distance=min(v.length,(l1+l2)*.995);direction=v.normalized()
 along=(l1*l1-l2*l2+distance*distance)/(2*distance)
 height=math.sqrt(max(0,l1*l1-along*along))
 bend=Vector(pole);bend=(bend-direction*bend.dot(direction)).normalized()
 knee=a+direction*along+bend*height;end=a+direction*distance
 place_segment(upper,a,knee,heads[lower]);place_segment(lower,knee,end,heads[endbone])
 return end
def smooth(a,b,t):
 t=max(0,min(1,(t-a)/(b-a)));return t*t*(3-2*t)
def envelope(t,a,b,c,d):return smooth(a,b,t)*(1-smooth(c,d,t))
def footpath(phase,stride,lift,stance):
 p=phase%1
 if p<stance:return stride/2-stride*p/stance,0,0
 u=(p-stance)/(1-stance)
 return -stride/2+stride*(u-math.sin(TAU*u)/TAU),lift*math.sin(math.pi*u)**1.3,-10*math.sin(math.pi*u)
def pose(kind,t):
 reset();hip=pb['Hip'];base=hip.matrix.copy();z=-.018;side=0;lean=0;yaw=0
 if kind=='scout':z+=.0025*math.sin(TAU*t/3);side=.007*math.sin(TAU*t/6)
 if kind in ('walk','run'):
  cycle=32/24 if kind=='walk' else 20/24;p=t/cycle
  z+= (.008 if kind=='walk' else .022)*math.cos(TAU*p*2)
  if kind=='run':z-=.018
  side=(.010 if kind=='walk' else .006)*math.sin(TAU*p)
  lean=4 if kind=='walk' else 12;yaw=(4 if kind=='walk' else 7)*math.sin(TAU*p)
 if kind=='summon':z-=.024*envelope(t,.15,.65,1.55,2.35);lean=-4*envelope(t,.3,.7,1.3,1.65)+6*envelope(t,1.4,1.75,2.0,2.6)
 base.translation+=Vector((0,side,z));hip.matrix=base;update()
 rotate_inherited('Waist',rot((0,1,0),lean*.4)@rot((0,0,1),yaw*.4))
 rotate_inherited('Spine01',rot((0,1,0),lean*.35))
 rotate_inherited('Spine02',rot((0,1,0),lean*.25)@rot((0,0,1),-yaw*.8))
 look=0;nod=0
 if kind=='scout':
  look=23*envelope(t,.6,1.45,2.0,2.8)-17*envelope(t,3.0,3.7,4.25,5.1)
  nod=3*envelope(t,1.3,1.8,2.1,2.7)
 if kind=='summon':nod=12*envelope(t,.3,.9,1.3,1.7)-8*envelope(t,1.55,1.9,2.2,2.9)
 rotate_inherited('NeckTwist01',rot((0,0,1),look*.25))
 rotate_inherited('Head',rot((0,0,1),look*.75)@rot((0,1,0),nod-lean*.35))
 for prefix,sign in [('L',1),('R',-1)]:
  foot=prefix+'_Foot';target=heads[foot].copy();pitch=0
  if kind in ('walk','run'):
   cycle=32/24 if kind=='walk' else 20/24
   x,h,pitch=footpath(t/cycle+(0 if prefix=='L' else .5),.21 if kind=='walk' else .33,.052 if kind=='walk' else .10,.62 if kind=='walk' else .42)
   target.x+=x;target.z+=h
  if kind=='summon':target.x+=sign*.025*envelope(t,.05,.45,2.8,3.6)
  end=chain(prefix+'_Thigh',prefix+'_Calf',foot,target,(1,0,.05))
  pb[foot].matrix=Matrix.Translation(end)@rot((0,1,0),pitch).to_matrix().to_4x4()@rest[foot].to_3x3().to_4x4();update()
  wrist=Vector((.022,sign*.16,.525+z))
  if kind=='scout':wrist.x+=.006*math.sin(TAU*t/3+(0 if sign==1 else .4));wrist.z+=.002*math.sin(TAU*t/3)
  if kind in ('walk','run'):
   p=TAU*t/(32/24 if kind=='walk' else 20/24)+(0 if sign==1 else math.pi)
   wrist.x+=-(.055 if kind=='walk' else .085)*math.cos(p)
   wrist.z+=(.008 if kind=='walk' else .06)+(.008 if kind=='walk' else .025)*math.sin(p)
  if kind=='summon':
   gather=envelope(t,.15,.9,1.35,2.05);release=envelope(t,1.3,1.8,2.2,3.05)
   wrist= wrist.lerp(Vector((.15,sign*.058,.665)),gather)
   wrist= wrist.lerp(Vector((.18,sign*.16,.69)),release)
   wrist.y+=sign*.018*math.sin(TAU*(t-.6))*gather
  end=chain(prefix+'_Upperarm',prefix+'_Forearm',prefix+'_Hand',wrist,(-.7,sign*.7,-.25))
  # Relaxed hand continues forearm; palm opens towards the imaginary object.
  if kind=='summon':rotate_inherited(prefix+'_Hand',rot((0,1,0),-18*envelope(t,.4,1.0,2.1,2.9)))
 update()

scene=bpy.context.scene;scene.render.fps=24
clips=[('B_Scout','scout',144),('B_TrailWalk','walk',32),('B_Dash','run',20),('B_ShapeSummon','summon',96)]
actions={};validation={}
for name,kind,frames in clips:
 rig.animation_data.action=None;previous={}
 for frame in range(frames+1):
  pose(kind,frame/24)
  for b in pb:
   q=b.rotation_quaternion
   if b.name in previous and q.dot(previous[b.name])<0:q.negate()
   previous[b.name]=q.copy()
   b.keyframe_insert('location',frame=frame+1,group=b.name)
   b.keyframe_insert('rotation_quaternion',frame=frame+1,group=b.name)
  if frame==0:rig.animation_data.action.name=name
 action=rig.animation_data.action;action.use_fake_user=True;actions[name]=action
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for k in fc.keyframe_points:k.interpolation='LINEAR'
 validation[name]={'seconds':frames/24,'frames':frames+1,'original_authored_motion':True,'loop':kind!='summon'}
rig.animation_data.action=actions['B_Scout'];scene.frame_start=1;scene.frame_end=145;scene.frame_set(1)

# Export just the skinned character and four new actions.
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer-b-custom.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_anim_slide_to_zero=True)

# Neutral review stage: lighting is sized for this one-metre source asset.
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 scene.cycles.device='GPU'
except:pass
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.20,.23,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
scene.view_settings.view_transform='AgX'
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.008));floor=bpy.context.object;floor.name='Review_Floor'
mat=bpy.data.materials.new('Stage_sage');mat.diffuse_color=(.12,.18,.17,1);floor.data.materials.append(mat)
target=Vector((0,0,.53))
for name,position,energy,size in [('Key',(2,-3,3),150,3),('Fill',(2,3,2),85,3),('Rim',(-2,1,2.5),180,2)]:
 bpy.ops.object.light_add(type='AREA',location=position);o=bpy.context.object;o.name=name;o.data.energy=energy;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(2.8,-4,1.8));cam=bpy.context.object;cam.name='Review_Camera';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.35;scene.camera=cam
for area in bpy.context.screen.areas if bpy.context.screen else []:
 if area.type=='VIEW_3D':
  area.spaces.active.region_3d.view_perspective='CAMERA'
  area.spaces.active.shading.type='MATERIAL'
  area.spaces.active.shading.use_scene_lights=True
  area.spaces.active.shading.use_scene_world=True
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-custom.blend'))
(OUT/'animation-manifest.json').write_text(json.dumps({'authoring':'Original scripted Blender keyframes; Tripo skin rig only. No Mixamo, mocap, stock motion or retarget endpoint.','source_height_m':1.0,'forward_axis':'+X','fps':24,'bones':len(pb),'clips':validation,'notes':['No individual finger or facial expression rig in this prototype.','In-place locomotion: movement must match stride speed when integrated.']},indent=2),encoding='utf-8')
for name,kind,n in clips:
 rig.animation_data.action=actions[name]
 for f in ([1,37,83] if kind=='scout' else [1,n//4+1,n//2+1]):
  scene.frame_set(f);scene.render.filepath=str(OUT/(name+'-'+str(f)+'.png'));bpy.ops.render.render(write_still=True)
print('EXPLORER_B_AUTHORING_COMPLETE')
