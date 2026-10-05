import bpy,addon_utils,json,math,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';addon_utils.enable('bl_ext.user_default.mpfb',persistent=True)
from bl_ext.user_default.mpfb.services.faceservice import FaceService,ARKIT_FACEUNITS
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_pipeline_v3/01_template_test/mpfb_template_face_test.blend'));donor=bpy.data.objects['Template_Face_Body'];db=donor.data.shape_keys.key_blocks[0];raw=[v.co.copy() for v in db.data]
def fit(p):
 x,y,z=p;h=float(np.interp(z,[1.40,1.445,1.475,1.515,1.548,1.580,1.69],[.23,.33,.435,.550,.652,.735,1.0]));sx=float(np.interp(z,[1.44,1.475,1.53,1.548,1.59],[3.1,2.65,3.5,4.2,3.5]));return Vector((-y*2-.035,x*sx,h-.535))
mapped=[fit(p) for p in raw];deltas={}
selected=['browDownLeft','browDownRight','browInnerUp','browOuterUpLeft','browOuterUpRight','cheekSquintLeft','cheekSquintRight','mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','mouthPucker','mouthPressLeft','mouthPressRight','eyeBlinkLeft','eyeBlinkRight','eyeWideLeft','eyeWideRight','jawOpen']
for name in selected:
 k=donor.data.shape_keys.key_blocks.get(name);assert k,name;deltas[name]=[fit(v.co)-p for v,p in zip(k.data,mapped)]
kd=KDTree(len(mapped))
for i,p in enumerate(mapped):kd.insert(p,i)
kd.balance()
bpy.ops.wm.open_mainfile(filepath=str(A/'import_inspection.blend'));sc=bpy.context.scene
# Keep only the new import and the studio lights/camera.
for o in list(bpy.data.objects):
 if o.type in {'MESH','ARMATURE','EMPTY'} and not o.name.startswith('tripo_part_'):bpy.data.objects.remove(o,do_unlink=True)
parts=[o for o in sc.objects if o.type=='MESH'];T=Matrix(((0,-1,0,0),(1,0,0,0),(0,0,1,-.535),(0,0,0,1)))
for o in parts:
 o.data.transform(T@o.matrix_world);o.parent=None;o.matrix_world=Matrix.Identity(4);o.hide_render=False;o.hide_set(False)
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=.00008);bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT')
head=bpy.data.objects['tripo_part_0'];head.name='FACE_user_head';bpy.ops.object.select_all(action='DESELECT');compound=bpy.data.objects['tripo_part_14'];compound.select_set(True);bpy.context.view_layer.objects.active=compound;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
compoundparts=[o for o in sc.objects if o.name.startswith('tripo_part_14')];eyeobjs={};upper=[]
for o in compoundparts:
 c=sum((v.co for v in o.data.vertices),Vector())/len(o.data.vertices)
 if c.z>.02:eyeobjs.setdefault('L' if c.y>0 else 'R',[]).append(o)
 else:upper.append(o)
for side,objs in eyeobjs.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join();o=objs[0];o.name='EYEBALL_'+side
 c=sum((v.co for v in o.data.vertices),Vector())/len(o.data.vertices);o.data.transform(Matrix.Translation(-c));o.location=c
for i,o in enumerate(upper):o.name='TEETH_upper_'+str(i)
names={'tripo_part_2':'CLAVICLE','tripo_part_3':'EAR_L','tripo_part_4':'EAR_R','tripo_part_5':'TEETH_GUMS_lower','tripo_part_8':'TONGUE','tripo_part_9':'LASH_upper_L','tripo_part_11':'LASH_upper_R','tripo_part_15':'BROW_L','tripo_part_16':'BROW_R'}
for old,new in names.items():bpy.data.objects[old].name=new
for n in ['17','18','19','20','35','37']:bpy.data.objects['tripo_part_'+n].name='LID_SKIN_'+n
for side in ['L','R']:bpy.data.objects.remove(bpy.data.objects['EYEBALL_'+side],do_unlink=True)
eye_names=['EYEBALL_'+s for s in ['L','R']]+['IRIS_PUPIL_'+s for s in ['L','R']]+['EYE_CATCHLIGHT_'+s+'_'+k for s in ['L','R'] for k in ['main','small']]
with bpy.data.libraries.load(str(R/'art/characters/explorer_b_expressions_v7/explorer_b_expressions_v7.blend'),link=False) as (src,dst):dst.objects=eye_names
for o in dst.objects:
 sc.collection.objects.link(o)
 if o.parent and o.parent.type=='ARMATURE' and o.parent.name not in sc.objects:sc.collection.objects.link(o.parent);o.parent.hide_render=True
bpy.context.view_layer.update()
added={o.name.split('.')[0]:o for o in dst.objects};centers={s:added['EYEBALL_'+s].matrix_world.translation.copy() for s in ['L','R']};worlds={o:o.matrix_world.copy() for o in dst.objects}
for o in dst.objects:
 name=o.name.split('.')[0];side='L' if '_L' in name else 'R';sgn=1 if side=='L' else -1;C=Matrix.Translation(Vector((.15,sgn*.141,.116)))@Matrix.Scale(.66,4)@Matrix.Translation(-centers[side]);o.parent=None;o.parent_type='OBJECT';o.parent_bone='';o.matrix_world=C@worlds[o];o.name=name;o.hide_render=False;o.hide_set(False)
for side in ['L','R']:
 for prefix in ['IRIS_PUPIL_','EYE_CATCHLIGHT_']:
  for o in list(sc.objects):
   if o.name.startswith(prefix+side):world=o.matrix_world.copy();o.parent=bpy.data.objects['EYEBALL_'+side];o.matrix_world=world
with bpy.data.libraries.load(str(R/'art/characters/explorer_b_expressions_v7/explorer_b_expressions_v7.blend'),link=False) as (src,dst):dst.objects=['HAIR_sculptural_bob_mesh']
hair=dst.objects[0];sc.collection.objects.link(hair);hair.parent=None;hair.matrix_world=Matrix.Identity(4)
for m in list(hair.modifiers):hair.modifiers.remove(m)
hair.data.transform(Matrix.Diagonal((.86,.86,.90,1)));hair.hide_render=False;hair.hide_set(False)
for mat in hair.data.materials:
 if mat:mat.name='Hair_reused_v8_'+mat.name
dark=bpy.data.materials.new('Solid_lash_dark_v8');dark.use_nodes=True;bs=dark.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.007,.003,.002,1);bs.inputs['Roughness'].default_value=.48
for side in ['L','R']:o=bpy.data.objects['LASH_upper_'+side];o.data.materials.clear();o.data.materials.append(dark)
for o in sc.objects:
 if o.type!='MESH' or o==hair:continue
 for p in o.data.polygons:p.use_smooth=True
 for m in o.data.materials:
  if not m or m==dark or not m.use_nodes:continue
  bs=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
  if not bs:continue
  for field,val in [('Metallic',0.),('Roughness',.48 if not o.name.startswith('EYEBALL') else .20)]:
   for l in list(bs.inputs[field].links):m.node_tree.links.remove(l)
   bs.inputs[field].default_value=val
  for l in list(bs.inputs['Normal'].links):m.node_tree.links.remove(l)
# Preserve the original open-mouth shape, with a fitted sealed resting mouth.
head.data.calc_loop_triangles();original=[v.co.copy() for v in head.data.vertices];tree=BVHTree.FromPolygons(original,[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True);profiles=[]
for y in np.linspace(-.105,.105,101):
 gaps=[]
 for z in np.linspace(-.17,-.035,300):
  hit,*_=tree.ray_cast(Vector((1,y,z)),Vector((-1,0,0)))
  if hit is not None and hit.x<.20:gaps.append(float(z))
 profiles.append((float(y),max(gaps) if gaps else -.076,min(gaps) if gaps else -.086))
ys=[p[0] for p in profiles];tops=[p[1] for p in profiles];bots=[p[2] for p in profiles]
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
for o in list(sc.objects):
 if o.type!='MESH' or o==hair or o.name.startswith('EYEBALL'):continue
 orig=[v.co.copy() for v in o.data.vertices];o.shape_key_add(name='Basis_closed_smile');opening=o.shape_key_add(name='Mouth_open_original')
 for v,p in zip(opening.data,orig):v.co=p
 basis=o.data.shape_keys.key_blocks[0]
 if o==head:
  for v,p in zip(basis.data,orig):
   if not (p.x>.115 and abs(p.y)<.155 and -.26<p.z<-.02):continue
   w=smooth(.115,.16,p.x)*(1-smooth(.10,.19,abs(p.y)));z=float(np.interp(p.z,[-.30,-.23,-.17,-.135,-.10,-.075,-.04,0,.10],[-.30,-.21,-.135,-.107,-.105,-.075,-.04,0,.10]));v.co.z+=(z-p.z)*w
 elif o.name.startswith(('TEETH_','TONGUE')):
  for v in basis.data:
   v.co.x-=.035
   if o.name in {'TEETH_GUMS_lower','TONGUE'}:v.co.z+=.03
 # MPFB faceunit offsets are spatially retargeted to the new head, not copied by vertex index.
 if o.name.startswith(('FACE_','BROW_','LID_SKIN','LASH_','EAR_')):
  maps=[]
  for p in orig:
   near=kd.find_n(p,4);weights=[1/max(.001,d)**2 for _,i,d in near];total=sum(weights);maps.append([(i,w/total) for (_,i,d),w in zip(near,weights)])
  for name in selected:
   if name in {'jawOpen','eyeBlinkLeft','eyeBlinkRight'}:continue
   key=o.shape_key_add(name='!ex-'+name)
   for i,(v,b) in enumerate(zip(key.data,basis.data)):
    delta=sum((deltas[name][j]*w for j,w in maps[i]),Vector());gain=.55 if 'mouth' in name else .9;delta*=gain
    if delta.length>.025:delta*=.025/delta.length
    v.co=b.co+delta
  FaceService.set_expression(o,{'mouthSmileLeft':.1,'mouthSmileRight':.1});FaceService.clear_expression(o)
sc.render.engine='BLENDER_EEVEE_NEXT';sc.eevee.taa_render_samples=32;sc.render.resolution_x=640;sc.render.resolution_y=720;cam=sc.camera;target=Vector((0,0,.0));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2
for name,vec in [('assembled_front',(3,0,0)),('assembled_angle',(3,-2,0)),('assembled_side',(0,-3,0))]:
 cam.location=target+Vector(vec);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
cam.location=Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();bpy.ops.wm.save_as_mainfile(filepath=str(A/'assembled_workbench.blend'));(A/'mpfb-retarget.json').write_text(json.dumps({'source':'installed MPFB Faceunits 01 on tested MPFB template','source_units':selected,'transferred_units':[n for n in selected if n not in {'jawOpen','eyeBlinkLeft','eyeBlinkRight'}],'method':'landmark-scaled cage + four nearest donor vertex weighted offsets; local jaw/blink fitting required','FaceService_set_expression_called':True,'original_glb_preserved':True,'credits':0},indent=2));print('V8_ASSEMBLED')
