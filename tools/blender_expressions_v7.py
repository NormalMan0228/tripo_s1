"""Keep approved v6 identity; clear hair collisions and add controllable expressions."""
import bpy,math,json,numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_expressions_v7';A.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_face_animated_v6/explorer_b_repaired_rigify_v6.blend'));bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update();head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];rig=bpy.data.objects['Explorer_B_Rigify_Face_Rig'];hp=rig.pose.bones['head']
eo=head.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();tree=BVHTree.FromPolygons([head.matrix_world@v.co for v in me.vertices],[tuple(t.vertices) for t in me.loop_triangles],all_triangles=True);eo.to_mesh_clear()
# Only clear front-facing hair near facial skin: the scalp and back hair keep their volume.
world=[hair.matrix_world@v.co for v in hair.data.vertices];deltas=[Vector() for _ in world];collisions=[]
for i,p in enumerate(world):
 if not (.08<p.x and -.19<p.z<.32 and abs(p.y)<.29):continue
 q,n,_,dist=tree.find_nearest(p)
 if q is None or dist>.04 or q.x<.11 or not (-.17<q.z<.28):continue
 signed=(p-q).dot(n)
 if signed<.0025:
  if signed>-.035:deltas[i]=n*(.005-signed);collisions.append(i)
from mathutils.kdtree import KDTree
kt=KDTree(len(collisions))
for j,i in enumerate(collisions):kt.insert(world[i],j)
kt.balance();active=set();source_deltas=[d.copy() for d in deltas];collision_set=set(collisions)
for i,p in enumerate(world):
 nearest=kt.find(p)
 if nearest[2]>.055:continue
 samples=kt.find_range(p,.055);weighted=Vector();total=0.
 for _,j,d in samples:
  w=math.exp(-(d/.027)**2);weighted+=source_deltas[collisions[j]]*w;total+=w
 if total:
  blend=max(0,1-(nearest[2]/.055)**2);new=weighted/total*blend
  if i in collision_set:new=new.lerp(source_deltas[i],.5)
  deltas[i]=new;active.add(i)
inv=hair.matrix_world.inverted().to_3x3()
for i in active:hair.data.vertices[i].co+=inv@deltas[i]
maxmove=max(d.length for d in deltas);assert maxmove<.059

def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def drive(key,prop):
 dr=key.driver_add('value').driver;dr.expression='v';v=dr.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["head"]["'+prop+'"]'
props=['happy','concern','determined','surprise']
for prop in props:hp[prop]=0.;hp.id_properties_ui(prop).update(min=0,max=1,description='Expression blend, 0 neutral / 1 full')
basis=head.data.shape_keys.key_blocks[0]
for prop in props:
 key=head.shape_key_add(name='Expression_'+prop)
 for v,b in zip(key.data,basis.data):
  c=b.co;y=abs(c.y);z=c.z;front=smooth(.13,.23,c.x)
  mouth=math.exp(-((y-.079)/.04)**2)*smooth(-.125,-.095,z)*(1-smooth(-.040,-.017,z))*front
  cheek=math.exp(-((y-.155)/.050)**2-((z-.008)/.060)**2)*front
  forehead=math.exp(-((y-.135)/.080)**2-((z-.210)/.029)**2)*front
  if prop=='happy':v.co.z+=.007*mouth+.0015*cheek;v.co.x+=.0015*cheek
  elif prop=='concern':v.co.z-=.010*mouth;v.co.z+=.0020*forehead*(1-smooth(.08,.2,y))
  elif prop=='determined':v.co.z-=.005*mouth;v.co.z-=.0020*forehead*(1-smooth(.08,.2,y))
  elif prop=='surprise':v.co.z+=.0035*forehead-.010*mouth
 drive(key,prop)
for side in ['L','R']:
 o=bpy.data.objects['BROW_'+side];base=o.shape_key_add(name='Basis') if not o.data.shape_keys else o.data.shape_keys.key_blocks[0]
 for prop in props:
  k=o.shape_key_add(name='Expression_'+prop)
  for v,b in zip(k.data,base.data):
   p=o.matrix_world@b.co;y=abs(p.y);inner=1-smooth(.09,.20,y)
   dz={'happy':.002,'concern':.009*inner-.002,'determined':-.007*inner+.001,'surprise':.011}[prop]
   v.co+=o.matrix_world.inverted().to_3x3()@Vector((0,0,dz))
  drive(k,prop)
# Keep v6 demonstration as a reusable action and create the new expression showcase.
rig.animation_data.action.use_fake_user=True;rig.animation_data.action=None
for pb in rig.pose.bones:pb.rotation_quaternion=(1,0,0,0);pb.rotation_euler=(0,0,0)
def keyprop(pb,name,points):
 for frame,value in points:pb[name]=float(value);pb.keyframe_insert(data_path='["'+name+'"]',frame=frame)
poses=[(1,'neutral'),(55,'neutral'),(85,'happy'),(145,'happy'),(175,'neutral'),(205,'curious'),(265,'curious'),(295,'neutral'),(325,'concern'),(385,'concern'),(415,'neutral'),(445,'determined'),(505,'determined'),(535,'neutral'),(565,'surprise'),(625,'surprise'),(665,'neutral'),(720,'neutral')]
for prop in props:keyprop(hp,prop,[(f,1. if p==prop else 0.) for f,p in poses])
keyprop(rig.pose.bones['jaw'],'mouth_open',[(f,.48 if p=='surprise' else 0.) for f,p in poses]);keyprop(rig.pose.bones['smile'],'smile',[(1,0),(720,0)])
for side in ['L','R']:
 pb=rig.pose.bones['blink.'+side];points={f:(.15 if p=='happy' else .10 if p=='determined' else 0.) for f,p in poses}
 for f in [43,163,283,403,523,677]:points.update({f:0.,f+4:1.,f+10:0.})
 keyprop(pb,'blink',sorted(points.items()))
 # Curious pose uses a gentle head tilt and an offset gaze within the verified range.
 pb=rig.pose.bones['eye.'+side];pb.rotation_mode='QUATERNION';rest=rig.data.bones[pb.name].matrix_local.to_quaternion()
 for f,p in poses:
  q=Quaternion(Vector((0,0,1)),math.radians(4 if p=='curious' else 0));pb.rotation_quaternion=rest.inverted()@q@rest;pb.keyframe_insert(data_path='rotation_quaternion',frame=f)
rest=rig.data.bones['head'].matrix_local.to_quaternion();hp.rotation_mode='QUATERNION'
for f,p in poses:
 q=Quaternion(Vector((1,0,0)),math.radians(5 if p=='curious' else 0));hp.rotation_quaternion=rest.inverted()@q@rest;hp.keyframe_insert(data_path='rotation_quaternion',frame=f)
action=rig.animation_data.action;action.name='Explorer_B_Expressions_24s';action.use_fake_user=True
curves=list(action.fcurves) if hasattr(action,'fcurves') else [f for l in action.layers for s in l.strips for b in s.channelbags for f in b.fcurves]
for fc in curves:
 for k in fc.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
sc.timeline_markers.clear()
for frame,name in [(1,'Neutral'),(100,'Happy'),(220,'Curious'),(340,'Concern'),(460,'Determined'),(580,'Surprise'),(720,'Neutral')]:sc.timeline_markers.new(name,frame=frame)
sc.frame_start=1;sc.frame_end=720;sc.render.fps=30;sc.frame_set(1);bpy.context.view_layer.update()
cam=sc.camera;target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
note=bpy.data.texts.new('V7_EXPRESSION_CONTROLS');note.write('Space: 24 second expression showcase. Head control custom properties: happy, concern, determined, surprise. jaw mouth_open, blink.L/R blink, eyes rotation remain editable. Curious is head tilt plus gaze. Previous v6 action is retained.\n')
sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=576;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.eevee.taa_render_samples=32
for name,frame in [('neutral',1),('happy',100),('curious',220),('concern',340),('determined',460),('surprise',580),('blink',47)]:
 sc.frame_set(frame);bpy.context.view_layer.update();sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(A/'explorer_b_expressions_v7.blend'))
report={'source':'approved v6','hair_vertices_adjusted':len(active),'direct_hair_collisions_corrected':len(collisions),'maximum_hair_shift':maxmove,'hair_topology_unchanged':True,'expressions':props+['curious','neutral'],'addon':'existing Rigify rig','frames':720,'fps':30,'seconds':24,'previous_action_preserved':True,'credits':0};(A/'report.json').write_text(json.dumps(report,indent=2));print('EXPRESSIONS_V7',json.dumps(report))
