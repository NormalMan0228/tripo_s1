"""Blender-only assembly and Rigify authoring of the nine approved source GLBs.

Preserves input files; garments and body regions stay independently selectable.
Includes paired mirrors, a reconstructed hidden body, finger chains, skinning,
restrained face controls, and authored deformation review poses. No API calls.
"""
import bpy, bmesh, hashlib, json, math
from pathlib import Path
import numpy as np
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/characters/explorer_b_modular_v1/03_generated'
OUT=SOURCE.parent/'04_blender_assembly'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
scene.render.fps=30
scene.frame_start=1;scene.frame_end=121
report={'scope':'Blender only: nine source meshes assembled, locally fitted and rigged',
        'new_tripo_calls':0,'new_scenario_calls':0,'source_hashes':{},'parts':{},
        'limitations':['Initial facial controls retain original face surfaces; oral cavity, tongue and a complete eyelid system are not authored.',
                       'Dense generated meshes are cleaned and weighted; hand-authored production edge-loop retopology and lower-detail variants remain pending.',
                       'The reconstructed body and local neck bridge use a shared solid skin material. Production body UV unwrap and final skin texture authoring remain pending.',
                       'Clothing clearance and weights are reviewed with the included pose test; extreme gameplay poses require further fitting and corrective shapes.']}
collections={}
for name in ['01_Body','02_Clothing','03_Hair','04_Rig','05_Reference_Metarig','06_Studio']:
 c=bpy.data.collections.new(name);scene.collection.children.link(c);collections[name]=c

def move_collection(obj,name):
 for c in list(obj.users_collection):c.objects.unlink(obj)
 collections[name].objects.link(obj)

def activate(obj):
 if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj

def bounds(obj):
 points=[v.co for v in obj.data.vertices]
 return Vector([min(p[i] for p in points) for i in range(3)]),Vector([max(p[i] for p in points) for i in range(3)])

def vertex_normals(obj):
 normals=np.zeros((len(obj.data.vertices),3),dtype=np.float64)
 corner=np.empty(len(obj.data.loops)*3,dtype=np.float32)
 indices=np.empty(len(obj.data.loops),dtype=np.int32)
 obj.data.corner_normals.foreach_get('vector',corner)
 obj.data.loops.foreach_get('vertex_index',indices)
 np.add.at(normals,indices,corner.reshape(-1,3))
 normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
 return normals

def set_normals(obj,normals):
 normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
 obj.data.normals_split_custom_set_from_vertices(normals.tolist())

def import_part(key,name,collection):
 path=SOURCE/key/'model.glb'
 report['source_hashes'][key]=hashlib.sha256(path.read_bytes()).hexdigest()
 before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(path))
 imported=[o for o in bpy.data.objects if o not in before]
 obj=next(o for o in imported if o.type=='MESH')
 matrix=obj.matrix_world.copy()
 original_normals=vertex_normals(obj)
 for v in obj.data.vertices:v.co=matrix@v.co
 obj.parent=None;obj.matrix_world=Matrix.Identity(4);obj.name=name;obj.data.name=name+'_Mesh'
 move_collection(obj,collection)
 for other in imported:
  if other!=obj:bpy.data.objects.remove(other,do_unlink=True)
 activate(obj)
 if key in ['body','hand']:
  if obj.data.has_custom_normals:bpy.ops.mesh.customdata_custom_splitnormals_clear()
  bm=bmesh.new();bm.from_mesh(obj.data)
  bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-5)
  if key=='body':bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
  bm.to_mesh(obj.data);bm.free()
 else:
  set_normals(obj,original_normals@np.array(matrix.to_3x3().inverted()))
 for polygon in obj.data.polygons:polygon.use_smooth=True
 obj['source_component']=key;obj['source_glb']=path.relative_to(ROOT).as_posix()
 return obj

def transform_mesh(obj,matrix):
 normals=vertex_normals(obj) if obj.data.has_custom_normals else None
 for v in obj.data.vertices:v.co=matrix@v.co
 obj.data.update()
 if normals is not None:set_normals(obj,normals@np.array(matrix.to_3x3().inverted()))

def scale_move(obj,scale,location):
 transform_mesh(obj,Matrix.Translation(Vector(location))@Matrix.Diagonal((*scale,1)))

def copy_mirror(obj,name):
 result=obj.copy();result.data=obj.data.copy();result.name=name
 obj.users_collection[0].objects.link(result)
 normals=vertex_normals(result) if result.data.has_custom_normals else None
 for v in result.data.vertices:v.co.y=-v.co.y
 bm=bmesh.new();bm.from_mesh(result.data);bmesh.ops.reverse_faces(bm,faces=bm.faces);bm.to_mesh(result.data);bm.free()
 if normals is not None:
  normals[:,1]*=-1;set_normals(result,normals)
 result['mirror_source']=obj.name;result['mirror_plane']='Y = 0'
 return result

def material(name,color,rough=.65):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
 p.inputs['Roughness'].default_value=rough;p.inputs['Specular IOR Level'].default_value=.28
 return m

skin_material=material('Skin_Shared_Warm_Peach',(.64,.405,.285),.65)
body=import_part('body','Body','01_Body')
# Source has a separate protective shorts shell. The continuous body's surface
# is reconstructed beneath clothing, never a missing torso under a garment.
bm=bmesh.new();bm.from_mesh(body.data)
remaining=set(bm.verts);remove=[]
while remaining:
 first=remaining.pop();todo=[first];members=[first]
 while todo:
  current=todo.pop()
  for edge in current.link_edges:
   other=edge.other_vert(current)
   if other in remaining:remaining.remove(other);todo.append(other);members.append(other)
 lo=Vector([min(v.co[i] for v in members) for i in range(3)])
 hi=Vector([max(v.co[i] for v in members) for i in range(3)])
 if (lo.z>-.03 and hi.z<.22) or len(members)<10:remove.extend(members)
if remove:bmesh.ops.delete(bm,geom=remove,context='VERTS')
# Open neck, wrist and waist boundaries must be closed before voxel union.
# A signed-volume remesh of an open generated surface produces holes.
bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0)
bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
bm.to_mesh(body.data);bm.free()
scale_move(body,(1.30,1.30,1.30),(.0455,0,.69468))
body.data.materials.clear();body.data.materials.append(skin_material)
for p in body.data.polygons:p.material_index=0
activate(body)
# Voxel union removes waist discontinuities while keeping a full underlying skin.
body.data.remesh_voxel_size=.0035
body.data.use_remesh_preserve_volume=True
bpy.ops.object.voxel_remesh()
smooth=body.modifiers.new('Surface_Cleanup','SMOOTH');smooth.factor=.48;smooth.iterations=3
bpy.ops.object.modifier_apply(modifier=smooth.name)
# Exact Y-plane body symmetry before weights; preserve facial/hair asymmetry.
bm=bmesh.new();bm.from_mesh(body.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                      plane_co=(0,0,0),plane_no=(0,1,0),dist=.00001,clear_outer=True,clear_inner=False)
for v in bm.verts:
 if abs(v.co.y)<.00005:v.co.y=0
bm.to_mesh(body.data);bm.free()
mirror=body.modifiers.new('Exact_Body_Symmetry','MIRROR');mirror.use_axis=(False,True,False)
mirror.use_clip=True;mirror.use_mirror_merge=True;mirror.merge_threshold=.0001
bpy.ops.object.modifier_apply(modifier=mirror.name)
for p in body.data.polygons:p.use_smooth=True
body_core_vertices=len(body.data.vertices)

head=import_part('head','Head','01_Body')
scale_move(head,(.385,.385,.385),(0,0,1.486))
for v in head.data.vertices:
 local=(v.co-Vector((0,0,1.486)))/.385
 # Fit only the covered rear scalp; facial features stay unchanged.
 t=max(0,min(1,(local.z-.16)/.18))*max(0,min(1,(.13-local.x)/.32))
 t=t*t*(3-2*t)
 v.co.x=-.021+(v.co.x+.021)*(1-.28*t)
 v.co.y*=1-.10*t
 if v.co.z>1.548:v.co.z=1.548+(v.co.z-1.548)*(1-.12*t)
head.data.materials.append(skin_material)
for p in head.data.polygons:
 if sum(head.data.vertices[i].co.z for i in p.vertices)/len(p.vertices)<1.37:p.material_index=len(head.data.materials)-1
# Remove the generated neck stub and join at a measured shared boundary, while
# retaining independent Head and Body objects and source UV interpolation.
bm=bmesh.new();bm.from_mesh(head.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
 plane_co=(0,0,1.34),plane_no=(0,0,1),dist=.000001,clear_inner=True)
socket={tuple(round(c,7) for c in v.co):v.co.copy() for v in bm.verts if abs(v.co.z-1.34)<.00001}
bm.to_mesh(head.data);bm.free()
socket_points=sorted(socket.values(),key=lambda p:math.atan2(p.y,p.x+.021))
if len(socket_points)<16:raise RuntimeError('neck_socket_missing')
# Authored skin bridge, with the last ring exactly equal to the head boundary.
bm=bmesh.new();bm.from_mesh(body.data);rings=[];segments=len(socket_points)
for z,center_x,rx,ry in [(1.095,.008,.055,.146),(1.12,.006,.060,.143),
 (1.15,.002,.062,.133),(1.18,-.002,.062,.118),(1.21,-.007,.061,.095),
 (1.24,-.014,.052,.065),(1.27,-.020,.042,.038),(1.305,-.021,.041,.037)]:
 rings.append([bm.verts.new((center_x+rx*math.cos(math.atan2(p.y,p.x+.021)),
                           ry*math.sin(math.atan2(p.y,p.x+.021)),z)) for p in socket_points])
rings.append([bm.verts.new(p) for p in socket_points])
for a,b in zip(rings,rings[1:]):
 for i in range(segments):bm.faces.new((a[i],a[(i+1)%segments],b[(i+1)%segments],b[i]))
bm.to_mesh(body.data);bm.free()
for p in body.data.polygons:p.use_smooth=True
neck_attribute=body.data.attributes.new(name='authored_neck_bridge',type='INT',domain='POINT')
for i in range(body_core_vertices,len(body.data.vertices)):neck_attribute.data[i].value=1
report['neck_socket']={'z':1.34,'matched_boundary_vertices':segments,'shared_boundary_positions':True}
# Shared peach on all new exposed skin, preserve the generated face artwork.
hand=import_part('hand','Hand.R','01_Body')
hand_source=[v.co.copy() for v in hand.data.vertices]
hand.data.materials.clear();hand.data.materials.append(skin_material)
for p in hand.data.polygons:p.material_index=0
nail_material=material('Nails_Subtle_Warm_Pink',(.73,.49,.39),.48)
hand.data.materials.append(nail_material)
bm=bmesh.new();bm.from_mesh(hand.data);remaining=set(bm.verts)
while remaining:
 first=remaining.pop();todo=[first];members=[first]
 while todo:
  cur=todo.pop()
  for edge in cur.link_edges:
   other=edge.other_vert(cur)
   if other in remaining:remaining.remove(other);todo.append(other);members.append(other)
 if 100<len(members)<600:
  for f in set(f for v in members for f in v.link_faces):f.material_index=1
bm.to_mesh(hand.data);bm.free()

# End-socket centers are measured from the final body surface, not raw bounds.
arm_tip=[v.co for v in body.data.vertices[:body_core_vertices] if v.co.y<-.30 and .80<v.co.z<.94]
tip_direction=Vector((0,-.5,-.8660254))
tip_end=max(p.dot(tip_direction) for p in arm_tip)
tip_ring=[p for p in arm_tip if p.dot(tip_direction)>tip_end-.004]
wrist=sum(tip_ring,Vector())/len(tip_ring)-tip_direction*.008
hand_matrix=Matrix.Translation(wrist)@Matrix.Rotation(math.radians(150),4,'X')@Matrix.Diagonal((.24,.18,.18,1))@Matrix.Translation(Vector((-.0276013,-.0610624,.4969258)))
transform_mesh(hand,hand_matrix)
hand_L=copy_mirror(hand,'Hand.L')
hair=import_part('hair','Hair','03_Hair')
scale_move(hair,(.46,.43,.40),(0,0,1.529))
jacket=import_part('jacket','Jacket','02_Clothing')
scale_move(jacket,(.75,.68,.67),(.025,0,1.113))
shirt=import_part('shirt','Shirt','02_Clothing')
shirt_normals=vertex_normals(shirt);shirt_raw_z=np.array([v.co.z for v in shirt.data.vertices])
for v in shirt.data.vertices:
 v.co.x=v.co.x*.36+.014;v.co.y*=.43
 v.co.z=float(np.interp(v.co.z,[-.5,0,.2,.3,.5],[.88,1.06,1.175,1.215,1.24]))
shirt.data.update()
shirt_slopes=np.select([shirt_raw_z<0,shirt_raw_z<.2,shirt_raw_z<.3],[.36,.575,.4],default=.125)
shirt_normals[:,0]/=.36;shirt_normals[:,1]/=.43;shirt_normals[:,2]/=shirt_slopes
set_normals(shirt,shirt_normals)
pants=import_part('pants','Pants','02_Clothing')
scale_move(pants,(.73,.83,.68),(.020,0,.570))
belt=import_part('belt','Belt','02_Clothing')
scale_move(belt,(.27,.345,.255),(.017,0,.893))

boot=import_part('boots','Boot.R','02_Clothing')
points=np.array([tuple(v.co) for v in boot.data.vertices])
ankle=points[points[:,2]>.25,:2].mean(axis=0)
lower=points[points[:,2]<-.20,:2]
eigenvalues,eigenvectors=np.linalg.eigh(np.cov(lower.T))
direction=eigenvectors[:,np.argmax(eigenvalues)]
if np.dot(lower.mean(axis=0)-ankle,direction)<0:direction=-direction
rotation=Matrix.Rotation(-math.atan2(direction[1],direction[0]),4,'Z')
transform_mesh(boot,rotation)
lo,hi=bounds(boot);rotated_ankle=rotation@Vector((*ankle,0))
sx=.265/(hi.x-lo.x);sy=.142/(hi.y-lo.y);sz=.25/(hi.z-lo.z)
scale_move(boot,(sx,sy,sz),(-rotated_ankle.x*sx-.010,-rotated_ankle.y*sy-.126,-lo.z*sz))
boot_L=copy_mirror(boot,'Boot.L')

report['fit_corrections']={'method':'Preserve garment surfaces; non-destructive hidden-body mask prevents covered skin clipping.'}
# Fit each wrist ring with the source body socket radius, smoothing into the palm.
for side,obj in [('R',hand),('L',hand_L)]:
 source_wrist=Vector((wrist.x,wrist.y if side=='R' else -wrist.y,wrist.z))
 direction=(Vector((0,-1 if side=='R' else 1,-1.73))).normalized()
 transverse=Vector((0,-direction.z,direction.y))
 for v in obj.data.vertices:
  delta=v.co-source_wrist;t=delta.dot(direction)
  if t<.022:
   blend=1-max(0,min(1,t/.022));blend=blend*blend*(3-2*blend)
   cross=delta.dot(transverse)
   corrected=source_wrist+direction*(t-.040*blend)+Vector((delta.x,0,0))+transverse*cross*.75
   v.co=v.co.lerp(corrected,blend)

report['wrist_sockets']={}
for side,obj,sign in [('R',hand,-1),('L',hand_L,1)]:
 direction=Vector((0,sign*.5,-.8660254));transverse=Vector((0,-direction.z,direction.y))
 center=Vector((wrist.x,sign*abs(wrist.y),wrist.z))-direction*.015
 bm=bmesh.new();bm.from_mesh(body.data)
 selected=[v for v in bm.verts if v.co.y*sign>.275 and .76<v.co.z<1.07]
 geometry=list(selected)+list({e for v in selected for e in v.link_edges})+list({f for v in selected for f in v.link_faces})
 bmesh.ops.bisect_plane(bm,geom=geometry,plane_co=center,plane_no=direction,
                       dist=.000001,clear_outer=True)
 ring=[v for v in bm.verts if abs((v.co-center).dot(direction))<.00001 and (v.co-center).length<.06]
 if len(ring)<12:raise RuntimeError('body_wrist_boundary_'+side)
 xmin=min(v.co.x for v in ring);xmax=max(v.co.x for v in ring)
 pmin=min((v.co-center).dot(transverse) for v in ring);pmax=max((v.co-center).dot(transverse) for v in ring)
 center+=Vector(((xmin+xmax)/2-center.x,0,0))+transverse*((pmin+pmax)/2)
 rx=(xmax-xmin)/2;ry=(pmax-pmin)/2
 for v in ring:
  delta=v.co-center;angle=math.atan2(delta.dot(transverse)/ry,delta.x/rx)
  v.co=center+Vector((rx*math.cos(angle),0,0))+transverse*(ry*math.sin(angle))
 bm.to_mesh(body.data);bm.free()
 bm=bmesh.new();bm.from_mesh(obj.data)
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=center,
                       plane_no=direction,dist=.000001,clear_inner=True)
 ring=[v for v in bm.verts if abs((v.co-center).dot(direction))<.00001]
 if len(ring)<12:raise RuntimeError('hand_wrist_boundary_'+side)
 for v in bm.verts:
  delta=v.co-center;t=delta.dot(direction)
  if t<.012:
   angle=math.atan2(delta.dot(transverse)/ry,delta.x/rx)
   fitted=center+direction*t+Vector((rx*math.cos(angle),0,0))+transverse*(ry*math.sin(angle))
   v.co=v.co.lerp(fitted,max(0,1-t/.012))
 bm.to_mesh(obj.data);bm.free()
 report['wrist_sockets'][side]={'center':list(center),'radius_x_m':rx,'radius_transverse_m':ry,
                              'body_boundary_vertices':len([v for v in body.data.vertices if abs((v.co-center).dot(direction))<.00001 and (v.co-center).length<.06]),
                              'hand_boundary_vertices':len(ring),'shared_ellipse':True}

all_meshes=[body,head,hand,hand_L,hair,jacket,shirt,pants,boot,boot_L,belt]
for obj in all_meshes:
 for p in obj.data.polygons:p.use_smooth=True
 report['parts'][obj.name]={'source':obj.get('source_component'), 'vertices':len(obj.data.vertices),
                           'bounds':[list(p) for p in bounds(obj)],'independently_selectable':True}

# Built-in Rigify control rig; fit the metarig in metric +X-forward coordinates.
bpy.ops.preferences.addon_enable(module='rigify')
bpy.ops.object.armature_basic_human_metarig_add()
meta=bpy.context.object;meta.name='Explorer_B_Metarig';move_collection(meta,'05_Reference_Metarig')
activate(meta);bpy.ops.object.mode_set(mode='EDIT')
for name in ['breast.L','breast.R']:
 if name in meta.data.edit_bones:meta.data.edit_bones.remove(meta.data.edit_bones[name])
spine_points=[(0,0,.81),(.005,0,.925),(.006,0,1.05),(.004,0,1.145),(0,0,1.27),(.005,0,1.305),(.005,0,1.35),(.005,0,1.62)]
for i in range(7):
 name='spine' if i==0 else 'spine.%03d'%i
 b=meta.data.edit_bones[name];b.head=spine_points[i];b.tail=spine_points[i+1]
 b.align_roll(Vector((0,1,0)))
finger_paths={
 'thumb':[(-.15,-.24),(-.23,-.03),(-.26,.07),(-.264,.142)],
 'index':[(-.095,.015),(-.092,.205),(-.090,.340),(-.088,.434)],
 'middle':[(.038,.030),(.040,.246),(.041,.402),(.040,.495)],
 'ring':[(.145,.015),(.145,.208),(.146,.335),(.146,.427)],
 'pinky':[(.238,-.065),(.239,.053),(.240,.181),(.241,.290)]}
finger_world={}
for side,sign in [('R',-1),('L',1)]:
 def point(x,y,z):return Vector((x,abs(y)*sign,z))
 shoulder=point(-.020,.183,1.205)
 elbow=point(-.008,.273,1.055)
 wrist_side=Vector((wrist.x,abs(wrist.y)*sign,wrist.z))
 hand_end=wrist_side+Vector((0,sign*.048,-.079))
 specifications={
  'pelvis':(point(0,.012,.81),point(0,.122,.86)),
  'shoulder':(point(-.008,.055,1.22),shoulder),
  'upper_arm':(shoulder,elbow), 'forearm':(elbow,wrist_side),'hand':(wrist_side,hand_end),
  'thigh':(point(.005,.118,.80),point(-.048,.129,.445)),
  'shin':(point(-.048,.129,.445),point(-.010,.126,.095)),
  'foot':(point(-.010,.126,.095),point(.118,.126,.043)),
  'toe':(point(.118,.126,.043),point(.195,.126,.043)),
  'heel.02':(point(-.061,.086,.009),point(-.061,.165,.009))}
 for stem,(a,b) in specifications.items():
  bone=meta.data.edit_bones[stem+'.'+side];bone.head=a;bone.tail=b
  bone.align_roll(Vector((0,1,0)) if stem not in ['upper_arm','forearm','hand'] else Vector((1,0,0)))
 for digit,path in finger_paths.items():
  pts=[]
  for y,z in path:
   p=hand_matrix@Vector((-.038 if digit=='thumb' else .037,y,z))
   if side=='L':p.y=-p.y
   pts.append(p)
  names=[]
  for i in range(3):
   name=f'f_{digit}.{i+1:02d}.{side}'
   b=meta.data.edit_bones.new(name);b.head=pts[i];b.tail=pts[i+1]
   b.parent=meta.data.edit_bones['hand.'+side] if i==0 else meta.data.edit_bones[names[-1]]
   b.use_connect=i>0;b.align_roll(Vector((1,0,0)));names.append(name)
  finger_world[(side,digit)]=(pts,names)
jaw=meta.data.edit_bones.new('face_jaw');jaw.head=(.005,0,1.416);jaw.tail=(.110,0,1.389)
jaw.parent=meta.data.edit_bones['spine.006'];jaw.align_roll(Vector((0,1,0)))
bpy.ops.object.mode_set(mode='OBJECT')
for (side,digit),(pts,names) in finger_world.items():
 p=meta.pose.bones[names[0]];p.rigify_type='limbs.super_finger'
 p.rigify_parameters.primary_rotation_axis='-X'
 p.rigify_parameters.make_extra_ik_control=False
 for name in names:
  meta.data.collections['Arm.'+side+' (FK)'].assign(meta.data.bones[name])
p=meta.pose.bones['face_jaw'];p.rigify_type='basic.super_copy'
meta.data.collections['Torso'].assign(meta.data.bones['face_jaw'])
bpy.ops.pose.rigify_generate()
rig=bpy.context.object
if rig==meta:rig=next(o for o in scene.objects if o.type=='ARMATURE' and o!=meta)
rig.name='Explorer_B_Rig';move_collection(rig,'04_Rig');rig.show_in_front=False
meta.hide_render=True;meta.hide_set(True);meta.hide_select=True
for bone in rig.pose.bones:
 bone.rotation_mode='XYZ'
 if 'IK_FK' in bone:bone['IK_FK']=1.0
 for prop in ['IK_Stretch','stretch_length']:
  if prop in bone:bone[prop]=0 if prop=='IK_Stretch' else 1
def_bones=[b for b in rig.data.bones if b.use_deform and b.name.startswith('DEF-')]
bone_names=[b.name for b in def_bones]
report['rig']={'generator':'Blender built-in Rigify, fitted Basic Human + custom ten finger chains and jaw',
               'bones_total':len(rig.data.bones),'deform_bones':len(def_bones),
               'finger_deform_bones':[n for n in bone_names if n.startswith('DEF-f_')],
               'controls':[b.name for b in rig.pose.bones if not b.name.startswith(('DEF-','ORG-','MCH-'))]}

def bind(obj,weights):
 for vg in list(obj.vertex_groups):obj.vertex_groups.remove(vg)
 for name,values in weights.items():
  group=obj.vertex_groups.new(name=name)
  for index,value in enumerate(values):
   if value>1e-7:group.add([index],float(value),'REPLACE')
 modifier=obj.modifiers.new('Character_Skin','ARMATURE');modifier.object=rig;modifier.use_deform_preserve_volume=True
 obj.parent=rig

def smoothstep(a,b,x):
 t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)

def bone_weights(obj,candidates):
 coords=np.array([tuple(v.co) for v in obj.data.vertices],dtype=np.float64)
 names=[b.name for b in def_bones if candidates(b.name)]
 bones=[rig.data.bones[n] for n in names]
 distances=[]
 for bone in bones:
  a=np.array(bone.head_local);delta=np.array(bone.tail_local)-a
  t=np.clip(((coords-a)@delta)/max(np.dot(delta,delta),1e-12),0,1)
  distances.append(np.linalg.norm(coords-a-t[:,None]*delta,axis=1))
 d=np.stack(distances,axis=1)
 w=1/np.maximum(d,.007)**4
 nearest=np.argsort(d,axis=1)[:,:4]
 mask=np.zeros_like(w,dtype=bool);np.put_along_axis(mask,nearest,True,axis=1)
 w*=mask;w/=np.maximum(w.sum(axis=1,keepdims=True),1e-12)
 return {name:w[:,i] for i,name in enumerate(names)}

body_weights=bone_weights(body,lambda n:not n.startswith(('DEF-f_','DEF-hand','DEF-face','DEF-pelvis','DEF-shoulder')))
# Blend the end of each forearm into the same hand bone as the wrist ring.
body_coords=np.array([tuple(v.co) for v in body.data.vertices])
neck_vertices=np.array([d.value for d in body.data.attributes['authored_neck_bridge'].data],dtype=bool)
for side,sign in [('R',-1),('L',1)]:
 center=np.array((wrist.x,abs(wrist.y)*sign,wrist.z))
 influence=1-smoothstep(.018,.052,np.linalg.norm(body_coords-center,axis=1))
 socket=report['wrist_sockets'][side];socket_center=np.array(socket['center'])
 direction=np.array((0,sign*.5,-.8660254))
 boundary=(np.abs((body_coords-socket_center)@direction)<.00002)&(np.linalg.norm(body_coords-socket_center,axis=1)<.06)
 influence[boundary]=1
 for n in body_weights:body_weights[n]*=1-influence
 body_weights['DEF-hand.'+side]=influence
neck_blend=smoothstep(1.25,1.34,body_coords[:,2])*neck_vertices
for n in body_weights:body_weights[n]*=1-neck_blend
body_weights['DEF-spine.006']=body_weights.get('DEF-spine.006',np.zeros(len(body_coords)))+neck_blend
bind(body,body_weights)
# Full underlying body remains editable. Mask only the skin covered by clothes.
visible=body.vertex_groups.new(name='Visible_Skin_With_Outfit')
for v in body.data.vertices:
 x,y,z=v.co
 side_sign=-1 if y<0 else 1
 direction=Vector((0,side_sign*.5,-.8660254))
 center=Vector((wrist.x,side_sign*abs(wrist.y),wrist.z))
 if neck_vertices[v.index] or (abs(y)>.283 and .80<z<1.065):visible.add([v.index],1,'REPLACE')
mask=body.modifiers.new('Outfit_Hidden_Body','MASK');mask.vertex_group=visible.name;mask.threshold=.5
mask.show_viewport=False
body['outfit_mask_instructions']='Disable Outfit_Hidden_Body to edit the full underlying body. The body is not deleted.'

def normalize(values):
 total=sum(values.values());return {k:v/max(total,1e-12) for k,v in values.items()}

for side,obj in [('R',hand),('L',hand_L)]:
 weights=bone_weights(obj,lambda n:n.endswith('.'+side) and (n.startswith('DEF-f_') or n.startswith('DEF-hand')))
 sign=-1 if side=='R' else 1
 coords=np.array([tuple(v.co) for v in obj.data.vertices]);center=np.array(report['wrist_sockets'][side]['center'])
 distance=(coords-center)@np.array((0,sign*.5,-.8660254))
 wrist_blend=1-smoothstep(.020,.040,distance)
 for n in weights:weights[n]*=1-wrist_blend
 weights['DEF-hand.'+side]=weights.get('DEF-hand.'+side,np.zeros(len(coords)))+wrist_blend
 bind(obj,weights)

def rigid(obj,name):bind(obj,{name:np.ones(len(obj.data.vertices))})
rigid(hair,'DEF-spine.006');rigid(boot,'DEF-foot.R');rigid(boot_L,'DEF-foot.L');rigid(belt,'DEF-spine')
# Preserve the source face; neck receives matching body weights at its socket.
hw=bone_weights(head,lambda n:n.startswith('DEF-spine') or n=='DEF-face_jaw')
coords=np.array([tuple(v.co) for v in head.data.vertices])
head_weight=smoothstep(1.30,1.34,coords[:,2])
for n in hw:hw[n]*=1-head_weight
hw['DEF-spine.006']=hw.get('DEF-spine.006',np.zeros(len(coords)))+head_weight
local=(coords-np.array((0,0,1.486)))/.385
jaw_amount=.65*smoothstep(.04,.18,local[:,0])*(1-smoothstep(-.30,-.18,local[:,2]))*smoothstep(-.48,-.38,local[:,2])*smoothstep(.045,.075,coords[:,0])
for n in hw:hw[n]*=1-jaw_amount
hw['DEF-face_jaw']=hw.get('DEF-face_jaw',np.zeros(len(coords)))+jaw_amount
bind(head,hw)

for obj in [shirt,pants,jacket]:
 for name in bone_names:obj.vertex_groups.new(name=name)
 activate(obj)
 transfer=obj.modifiers.new('Body_Weight_Transfer','DATA_TRANSFER');transfer.object=body
 transfer.use_vert_data=True;transfer.data_types_verts={'VGROUP_WEIGHTS'};transfer.vert_mapping='POLYINTERP_NEAREST'
 bpy.ops.object.modifier_apply(modifier=transfer.name)
 modifier=obj.modifiers.new('Character_Skin','ARMATURE');modifier.object=rig;modifier.use_deform_preserve_volume=True
 obj.parent=rig
 # Equalized seam weights, normalized after the transfer.
 bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
 bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL',lock_active=False)
 bpy.ops.object.mode_set(mode='OBJECT')
mask.show_viewport=True
shirt_visible=shirt.vertex_groups.new(name='Visible_Shirt_Under_Jacket')
for v in shirt.data.vertices:
 if abs(v.co.y)<.118 and (v.co.z<1.205 or abs(v.co.y)<.052):shirt_visible.add([v.index],1,'REPLACE')
shirt_mask=shirt.modifiers.new('Jacket_Hidden_Shirt','MASK');shirt_mask.vertex_group=shirt_visible.name
shirt_mask.threshold=.5
shirt['outfit_mask_instructions']='Disable Jacket_Hidden_Shirt to see and edit the complete shirt.'

# Restrained facial morphs operate on original vertices and original UVs.
head.shape_key_add(name='Basis')
for name in ['Smile','BrowRaise','BrowConcern']:
 key=head.shape_key_add(name=name)
 for original,vertex in zip(head.data.vertices,key.data):
  p=original.co;local=(p-Vector((0,0,1.486)))/.385
  front=float(smoothstep(.04,.20,local.x))
  if name=='Smile':
   influence=math.exp(-((abs(local.y)-.11)/.055)**2-((local.z+.255)/.055)**2)*front
   vertex.co.z+=.003*influence;vertex.co.y+=math.copysign(.0018*influence,p.y)
  else:
   influence=math.exp(-((abs(local.y)-.18)/.10)**2-((local.z-.12)/.048)**2)*front
   vertex.co.z+=(.006 if name=='BrowRaise' else .004*(1-abs(local.y)/.28))*influence
 rig[name]=0.0;rig.id_properties_ui(name).update(min=0,max=1,description='Restrained original-face expression')
 driver=key.driver_add('value').driver;driver.type='SCRIPTED'
 variable=driver.variables.new();variable.name='value';variable.targets[0].id=rig
 variable.targets[0].data_path='["'+name+'"]';driver.expression='min(max(value,0),1)'
head['facial_scope']='Original face retained: gentle smile and brows, small jaw bone. No replacement face geometry or claimed complete eyelid rig.'

# Actual authored pose tests, not external animation presets.
def reset_pose():
 for b in rig.pose.bones:b.location=(0,0,0);b.rotation_euler=(0,0,0);b.scale=(1,1,1)
 for name in ['Smile','BrowRaise','BrowConcern']:rig[name]=0

reset_pose();rig.animation_data_create()
for frame in range(1,122):
 t=(frame-1)/120;amount=math.sin(math.pi*t)**2
 reset_pose()
 for side,sign in [('R',-1),('L',1)]:
  upper=rig.pose.bones.get('upper_arm_fk.'+side)
  lower=rig.pose.bones.get('forearm_fk.'+side)
  if upper:upper.rotation_euler.x=math.radians(28 if side=='R' else -15)*amount
  if lower:lower.rotation_euler.x=math.radians(52 if side=='R' else 18)*amount
  for digit in finger_paths:
   for i,angle in enumerate([32,42,22]):
    b=rig.pose.bones.get(f'f_{digit}.{i+1:02d}.{side}')
    if b:b.rotation_euler.x=-math.radians(angle if digit!='thumb' else angle*.50)*amount
  thigh=rig.pose.bones.get('thigh_fk.'+side);shin=rig.pose.bones.get('shin_fk.'+side)
  if thigh:thigh.rotation_euler.x=math.radians(sign*10)*amount
  if shin:shin.rotation_euler.x=math.radians(16)*amount
 if 'head' in rig.pose.bones:rig.pose.bones['head'].rotation_euler.y=math.radians(12)*amount
 rig['Smile']=.55*amount;rig['BrowRaise']=.25*amount
 for name in ['Smile','BrowRaise','BrowConcern']:rig.keyframe_insert(data_path='["'+name+'"]',frame=frame)
 for b in rig.pose.bones:
  if b.name.startswith(('DEF-','MCH-','ORG-')):continue
  b.keyframe_insert('location',frame=frame);b.keyframe_insert('rotation_euler',frame=frame)
  b.keyframe_insert('scale',frame=frame)
 if frame==1:rig.animation_data.action.name='Rig_Proof_Pose_Return'
action=rig.animation_data.action;action.use_fake_user=True
for layer in action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for curve in bag.fcurves:
    for key in curve.keyframe_points:key.interpolation='LINEAR'
scene.frame_set(1);bpy.context.view_layer.update()

report['weight_validation']={}
for obj in all_meshes:
 totals=[sum(g.weight for g in v.groups if obj.vertex_groups[g.group].name in bone_names) for v in obj.data.vertices]
 report['weight_validation'][obj.name]={'vertices':len(totals),'unweighted_vertices':sum(x<.99 for x in totals),
                                      'maximum_normalization_error':max(abs(x-1) for x in totals),
                                      'armature_modifiers':sum(m.type=='ARMATURE' for m in obj.modifiers)}
 if any(x<.99 for x in totals):raise RuntimeError('unweighted_vertices_'+obj.name)
report['symmetry']={'body_and_pairs_mirror_plane':'Y = 0','left_hand_derived_from_right':True,'left_boot_derived_from_right':True}
report['actions']=[{'name':action.name,'frames':121,'fps':30,'duration_seconds':4,'purpose':'rig deformation review, not final gameplay locomotion'}]

# Soft studio, with cameras for neutral full body and source-preserving close-ups.
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
try:
 preferences=bpy.context.preferences.addons['cycles'].preferences;preferences.compute_device_type='CUDA';preferences.get_devices()
 for device in preferences.devices:device.use=device.type=='CUDA'
 if any(d.type=='CUDA' for d in preferences.devices):scene.cycles.device='GPU'
except Exception:scene.cycles.device='CPU'
scene.render.resolution_x=1000;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
world=bpy.data.worlds.new('Character Studio');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.85,.87,.90,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.45;scene.world=world
for name,position,power,size in [('Key',(3,-4,5),900,4),('Fill',(2,3,2.5),550,3),('Rim',(-3,1,4),750,3)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.size=size
 light=bpy.data.objects.new(name,data);collections['06_Studio'].objects.link(light)
 light.location=position;light.rotation_euler=(Vector((0,0,.9))-light.location).to_track_quat('-Z','Y').to_euler();light.hide_select=True
camera=bpy.data.objects.new('Review_Camera',bpy.data.cameras.new('Review_Camera'))
collections['06_Studio'].objects.link(camera);scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=1.96
camera.location=(4,-2.2,1.25);camera.rotation_euler=(Vector((0,0,.87))-camera.location).to_track_quat('-Z','Y').to_euler();camera.hide_select=True
collections['06_Studio'].hide_viewport=True
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.shading.type='MATERIAL';area.spaces.active.overlay.show_floor=False
   area.spaces.active.region_3d.view_location=(0,0,.9)
   area.spaces.active.region_3d.view_distance=2.6
   area.spaces.active.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
   area.spaces.active.region_3d.view_perspective='ORTHO'
activate(head)
instructions=bpy.data.texts.new('START_HERE_조작안내')
instructions.write('최신 부품 조립 및 리깅 테스트\n\nObject Mode: 신체·머리·손·헤어·의상을 각각 선택하고 수정할 수 있습니다.\nExplorer_B_Rig 선택 후 Ctrl+Tab: Pose Mode. 몸·팔·다리·손가락 컨트롤을 선택하여 회전합니다.\nIK_FK 속성 1은 FK, 0은 IK입니다. 손·발 IK 컨트롤도 포함됩니다.\nTimeline 1~121: Blender에서 직접 만든 변형 검증 동작. 1프레임은 기본 자세입니다.\nRig의 Custom Properties: Smile, BrowRaise, BrowConcern.\n원본 GLB는 03_generated 폴더에 보존됩니다.\n전문 토폴로지, 상세 눈꺼풀·구강 리깅, 제작용 걷기 애니메이션은 후속 작업입니다.\n')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_b_assembled_rigged.blend'))
(OUT/'assembly-rig-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ASSEMBLY_RIG_READY',json.dumps({'parts':len(all_meshes),'bones':len(rig.data.bones),'deform_bones':len(def_bones),'api_credits':0}),flush=True)
