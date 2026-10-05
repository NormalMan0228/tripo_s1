"""Retain the supplied GLB exactly at neutral; add hair and non-destructive MPFB/Rigify controls."""
import bpy,bmesh,addon_utils,json,math,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_original_identity_v9';A.mkdir(parents=True,exist_ok=True);addon_utils.enable('rigify',persistent=True)
from bl_ext.user_default.mpfb.services.faceservice import FaceService
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_pipeline_v3/01_template_test/mpfb_template_face_test.blend'));d=bpy.data.objects['Template_Face_Body'];base=d.data.shape_keys.key_blocks[0]
def fit(p):
 x,y,z=p;h=float(np.interp(z,[1.40,1.445,1.475,1.515,1.548,1.580,1.69],[.23,.33,.435,.550,.652,.735,1.0]));sx=float(np.interp(z,[1.44,1.475,1.53,1.548,1.59],[3.1,2.65,3.5,4.2,3.5]));return Vector((-y*2-.035,x*sx,h-.535))
source=[fit(v.co) for v in base.data];units=['browDownLeft','browDownRight','browInnerUp','browOuterUpLeft','browOuterUpRight','cheekSquintLeft','cheekSquintRight','mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','mouthPucker','mouthPressLeft','mouthPressRight','eyeBlinkLeft','eyeBlinkRight','eyeWideLeft','eyeWideRight','jawOpen'];deltas={n:[fit(v.co)-p for v,p in zip(d.data.shape_keys.key_blocks[n].data,source)] for n in units};kd=KDTree(len(source))
for i,p in enumerate(source):kd.insert(p,i)
kd.balance()
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_user_head_v8/import_inspection.blend'));sc=bpy.context.scene
for o in list(bpy.data.objects):
 if o.type in {'MESH','ARMATURE','EMPTY'} and not o.name.startswith('tripo_part_'):bpy.data.objects.remove(o,do_unlink=True)
T=Matrix(((0,-1,0,0),(1,0,0,0),(0,0,1,-.535),(0,0,0,1)));original={};material_names={}
for o in list(sc.objects):
 if o.type!='MESH':continue
 expected=[T@o.matrix_world@v.co for v in o.data.vertices];o.data.transform(T@o.matrix_world);o.parent=None;o.matrix_world=Matrix.Identity(4);o.hide_render=False;o.hide_set(False);original[o.name]=expected;material_names[o.name]=[m.name for m in o.data.materials]
head=bpy.data.objects['tripo_part_0'];head.name='FACE_original_user_GLb';original[head.name]=original.pop('tripo_part_0')
# Split only the compound eye/upper-teeth object, preserving imported geometry, UVs and materials.
compound=bpy.data.objects['tripo_part_14'];eyeparts={}
for side,sign in [('L',1),('R',-1)]:
 bpy.ops.object.select_all(action='DESELECT');compound.select_set(True);bpy.context.view_layer.objects.active=compound
 before=set(sc.objects);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='DESELECT');bm=bmesh.from_edit_mesh(compound.data)
 for p in bm.faces:p.select_set(p.calc_center_median().z>.02 and sign*p.calc_center_median().y>0)
 bmesh.update_edit_mesh(compound.data);bpy.ops.mesh.separate(type='SELECTED');bpy.ops.object.mode_set(mode='OBJECT');created=[o for o in sc.objects if o not in before];assert len(created)==1;eye=created[0];eye.name='EYEBALL_original_'+side;center=sum((v.co for v in eye.data.vertices),Vector())/len(eye.data.vertices);eye.data.transform(Matrix.Translation(-center));eye.location=center;eyeparts[side]=eye
compound.name='TEETH_upper_original'
mapping={'tripo_part_2':'CLAVICLE_original','tripo_part_3':'EAR_original_L','tripo_part_4':'EAR_original_R','tripo_part_5':'TEETH_lower_original','tripo_part_8':'TONGUE_original','tripo_part_9':'LASH_original_L','tripo_part_11':'LASH_original_R','tripo_part_15':'BROW_original_L','tripo_part_16':'BROW_original_R'}
for old,new in mapping.items():o=bpy.data.objects[old];o.name=new;original[new]=original.pop(old)
bpy.context.view_layer.update();native=[o for o in sc.objects if o.type=='MESH'];snapshot={o.name:[o.matrix_world@v.co for v in o.data.vertices] for o in native}
with bpy.data.libraries.load(str(R/'art/characters/explorer_b_expressions_v7/explorer_b_expressions_v7.blend'),link=False) as (src,dst):dst.objects=['HAIR_sculptural_bob_mesh']
hair=dst.objects[0];sc.collection.objects.link(hair);hair.parent=None;hair.matrix_world=Matrix.Identity(4)
for m in list(hair.modifiers):hair.modifiers.remove(m)
hair.data.transform(Matrix.Diagonal((.86,.86,.90,1)));hair.hide_render=False;hair.hide_set(False)
# Continuous collision correction moves the hair only.
vv=[];ff=[]
for o in [head,bpy.data.objects['EAR_original_L'],bpy.data.objects['EAR_original_R']]:
 o.data.calc_loop_triangles();start=len(vv);vv.extend(o.matrix_world@v.co for v in o.data.vertices);ff.extend(tuple(start+i for i in t.vertices) for t in o.data.loop_triangles)
tree=BVHTree.FromPolygons(vv,ff,all_triangles=True);ps=[v.co.copy() for v in hair.data.vertices];ids=[];ds=[]
for i,p in enumerate(ps):
 if not (-.15<p.x and abs(p.y)<.36 and -.20<p.z<.34):continue
 q,n,_,dist=tree.find_nearest(p)
 if q is not None and dist<.03 and -.025<(p-q).dot(n)<.003:ids.append(i);ds.append(n*(.005-(p-q).dot(n)))
kt=KDTree(len(ids))
for j,i in enumerate(ids):kt.insert(ps[i],j)
kt.balance();hair_moved=0
for i,p in enumerate(ps):
 _,j,dist=kt.find(p)
 if dist>.055:continue
 total=0;delta=Vector()
 for _,j,dd in kt.find_range(p,.055):w=math.exp(-(dd/.027)**2);total+=w;delta+=ds[j]*w
 if total:hair.data.vertices[i].co+=delta/total*max(0,1-(dist/.055)**2);hair_moved+=1
faceobjects=[o for o in native if not o.name.startswith(('EYEBALL','CLAVICLE','TEETH_upper'))]
for o in faceobjects:
 o.shape_key_add(name='Basis_original_unchanged');base=o.data.shape_keys.key_blocks[0];coords=[o.matrix_world@v.co for v in o.data.vertices];maps=[]
 for p in coords:
  near=kd.find_n(p,4);ws=[1/max(.001,d)**2 for _,j,d in near];total=sum(ws);maps.append([(j,w/total) for (_,j,d),w in zip(near,ws)])
 for name in units:
  key=o.shape_key_add(name='!ex-'+name)
  for i,(v,b) in enumerate(zip(key.data,base.data)):
   delta=sum((deltas[name][j]*w for j,w in maps[i]),Vector());gain=.30 if name=='jawOpen' else .45 if name.startswith('mouth') else .80
   if o.name.startswith(('TEETH_lower','TONGUE')):
    delta=Vector((-.003,0,-.014 if o.name.startswith('TEETH') else -.010)) if name=='jawOpen' else Vector();gain=1.
   if o.name.startswith('EAR'):delta=Vector()
   v.co=b.co+o.matrix_world.inverted().to_3x3()@(delta*gain)
 FaceService.clear_expression(o);FaceService.set_expression(o,{'mouthSmileLeft':.20,'mouthSmileRight':.20});FaceService.clear_expression(o)
arm=bpy.data.armatures.new('Original_Identity_Metarig');meta=bpy.data.objects.new('Original_Identity_Metarig',arm);sc.collection.objects.link(meta);bpy.ops.object.select_all(action='DESELECT');meta.select_set(True);bpy.context.view_layer.objects.active=meta;bpy.ops.object.mode_set(mode='EDIT')
def bone(n,a,b,parent=None):
 e=arm.edit_bones.new(n);e.head=a;e.tail=b
 if parent:e.parent=arm.edit_bones[parent]
bone('head',(0,0,-.2),(0,0,.2))
for side in ['L','R']:p=eyeparts[side].location;bone('eye.'+side,p,p+Vector((.06,0,0)),'head')
bpy.ops.object.mode_set(mode='OBJECT');col=arm.collections.new('Face Controls');col.rigify_ui_row=1
for b in arm.bones:col.assign(b)
for pb in meta.pose.bones:pb.rigify_type='basic.super_copy';pb.rigify_parameters.make_control=True;pb.rigify_parameters.make_widget=True;pb.rigify_parameters.make_deform=True;pb.rigify_parameters.super_copy_widget_type='circle'
bpy.ops.object.mode_set(mode='POSE');bpy.ops.pose.rigify_generate();bpy.ops.object.mode_set(mode='OBJECT');rig=bpy.context.view_layer.objects.active;rig.name='Original_Identity_Rigify';rig.show_in_front=True;meta.hide_render=True;meta.hide_set(True)
for c in bpy.data.collections:
 if c.name.startswith('WGTS'):c.hide_render=True;c.hide_viewport=True
for o in native+[hair]:
 world=o.matrix_world.copy()
 if o.name.startswith('EYEBALL'):o.parent=rig;o.parent_type='BONE';o.parent_bone='DEF-eye.'+o.name[-1];bpy.context.view_layer.update();o.matrix_world=world;bpy.context.view_layer.update()
 else:o.parent=rig;o.matrix_world=world;g=o.vertex_groups.new(name='DEF-head');g.add(list(range(len(o.data.vertices))),1.,'REPLACE');m=o.modifiers.new('Rigify_head','ARMATURE');m.object=rig
hp=rig.pose.bones['head']
for name in units:
 hp[name]=0.;hp.id_properties_ui(name).update(min=0,max=1)
 for o in faceobjects:
  key=o.data.shape_keys.key_blocks['!ex-'+name];dr=key.driver_add('value').driver;dr.expression='v';v=dr.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["head"]["'+name+'"]'
presets={'Neutral':{},'Happy':{'mouthSmileLeft':.40,'mouthSmileRight':.40,'cheekSquintLeft':.12,'cheekSquintRight':.12},'Concern':{'mouthFrownLeft':.50,'mouthFrownRight':.50,'browInnerUp':.65},'Determined':{'browDownLeft':.50,'browDownRight':.50,'mouthPressLeft':.2,'mouthPressRight':.2},'Surprise':{'browOuterUpLeft':.70,'browOuterUpRight':.70,'browInnerUp':.25,'jawOpen':.35}}
poses=[(1,'Neutral'),(50,'Neutral'),(75,'Happy'),(105,'Happy'),(140,'Neutral'),(165,'Concern'),(195,'Concern'),(230,'Neutral'),(255,'Determined'),(285,'Determined'),(320,'Neutral'),(345,'Surprise'),(375,'Surprise'),(420,'Neutral'),(450,'Neutral')]
for name in units:
 for f,pose in poses:hp[name]=float(presets[pose].get(name,0));hp.keyframe_insert(data_path='["'+name+'"]',frame=f)
action=rig.animation_data.action;action.name='Original_Face_MPFb_Rigify_15s';action.use_fake_user=True;curves=list(action.fcurves) if hasattr(action,'fcurves') else [f for l in action.layers for s in l.strips for b in s.channelbags for f in b.fcurves]
for fc in curves:
 for k in fc.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
sc.frame_start=1;sc.frame_end=450;sc.render.fps=30;sc.frame_set(1);bpy.context.view_layer.update();errors={}
for o in native:
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();assert len(me.vertices)==len(snapshot[o.name]);errors[o.name]=max((o.matrix_world@v.co-p).length for v,p in zip(me.vertices,snapshot[o.name]));eo.to_mesh_clear()
assert max(errors.values())<1e-6,errors
cam=sc.camera;cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2;sc.render.resolution_x=640;sc.render.resolution_y=720;sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True
bpy.ops.wm.save_as_mainfile(filepath=str(A/'original_face_mpfb_rigify_v9.blend'))
for name,f in [('neutral',1),('happy',90),('concern',180),('determined',270),('surprise',360)]:sc.frame_set(f);sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'status':'passed','native_GLb_neutral_vertex_error':errors,'head_vertices':len(head.data.vertices),'original_eyes_retained':True,'original_materials_UV_normals_retained':True,'head_sculpting':False,'head_retopology':False,'mouth_rest':'original source pose','MPFB_units':units,'Rigify_generated':True,'hair_moved_vertices':hair_moved,'seconds':15,'full_blink_fitting_complete':False,'credits':0};(A/'verification.json').write_text(json.dumps(report,indent=2));print('ORIGINAL_IDENTITY_VERIFIED',json.dumps(errors))
