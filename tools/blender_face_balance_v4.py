"""Rest-expression correction, centered lively eyes and complete lash pigmentation."""
import bpy,bmesh,math,json,colorsys,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];OLD=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly';A=R/'art/characters/explorer_b_face_balance_v4/assembly';A.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(OLD/'explorer_b_young_bob_closed_smile_v3.blend'));sc=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0
head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS'];basis=head.data.shape_keys.key_blocks[0];opened=head.data.shape_keys.key_blocks['Mouth_open_original']
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
for v,b,k in zip(head.data.vertices,basis.data,opened.data):
 c=b.co.copy();source=k.co
 # Soften only the front central chin, with a broad continuous falloff.
 chin=math.exp(-(c.y/.087)**4)*smooth(.10,.22,c.x)*(1-smooth(-.205,-.137,c.z));c.z+=.011*chin;c.x-=.002*chin
 # Relax the overly raised commissures, preserving central lip closure.
 mouth=math.exp(-((abs(source.y)-.105)/.032)**2-((source.z+.078)/.046)**2)*smooth(.14,.24,source.x)
 c.z-=.007*mouth;b.co=c;v.co=c
# Keep tooth and gum objects in the cavity in closed rest, restore them at open=1.
for o in sc.objects:
 if o.name.startswith(('TOOTH_','GUMS_')):
  if not o.data.shape_keys:
   coords=[v.co.copy() for v in o.data.vertices];o.shape_key_add(name='Basis_closed_smile');key=o.shape_key_add(name='Mouth_open_original')
   for v,c in zip(key.data,coords):v.co=c
   dr=key.driver_add('value').driver;dr.expression='op';var=dr.variables.new();var.name='op';var.type='SINGLE_PROP';var.targets[0].id=ctrl;var.targets[0].data_path='["mouth_open"]'
  for v,b in zip(o.data.vertices,o.data.shape_keys.key_blocks[0].data):b.co.x-=.017;v.co=b.co
# Lash wings get fully dark pigment through a smooth vertex color correction.
attr=head.data.attributes['Lash_color_repair'];tint=head.data.color_attributes['Lash_tint']
for v,a in zip(head.data.vertices,attr.data):
 x,y,z=v.co;wing=smooth(.205,.224,abs(y))*(1-smooth(.25,.259,abs(y)))*smooth(.147,.162,x)*smooth(.119,.128,z)*(1-smooth(.156,.164,z));a.value=max(a.value,min(1,a.value*1.55),wing)
for loop,c in zip(head.data.loops,tint.data):
 f=attr.data[loop.vertex_index].value;c.color=(1-f+f*.018,1-f+f*.012,1-f+f*.008,1)
# Retain the original generated eye shapes as hidden references.
sourcecol=bpy.data.collections.new('93_Original_v3_eyes');sc.collection.children.link(sourcecol)
def material(name,color,rough=.4,coat=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=rough;b.inputs['Coat Weight'].default_value=coat;b.inputs['Coat Roughness'].default_value=.14;return m
sclera=material('Sclera_soft_ivory',(.84,.87,.85),.27,.25);pupil=material('Pupil_deep_clean_black',(.003,.002,.0015),.22,.35);iris=material('Iris_warm_brown_radial_detail',(.12,.055,.016),.29,.35);glint=material('Eye_soft_catchlight',(.92,.97,1),.22)
gb=glint.node_tree.nodes['Principled BSDF'];gb.inputs['Emission Color'].default_value=(.9,.95,1,1);gb.inputs['Emission Strength'].default_value=.15
# A dedicated UV iris texture uses a single non-overlapping rectangular chart.
nt=iris.node_tree;bs=nt.nodes['Principled BSDF'];uv=nt.nodes.new('ShaderNodeTexCoord');mapping=nt.nodes.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY';mapping.inputs[1].default_value=(9,150,1);nt.links.new(uv.outputs['UV'],mapping.inputs[0]);noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1.;noise.inputs['Detail'].default_value=3.;noise.inputs['Roughness'].default_value=.68;nt.links.new(mapping.outputs[0],noise.inputs['Vector']);ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.20;ramp.color_ramp.elements[0].color=(.024,.009,.0025,1);ramp.color_ramp.elements[1].position=.8;ramp.color_ramp.elements[1].color=(.24,.115,.025,1);nt.links.new(noise.outputs['Fac'],ramp.inputs[0]);nt.links.new(ramp.outputs[0],bs.inputs['Base Color'])
separate=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(uv.outputs['UV'],separate.inputs[0]);edge=nt.nodes.new('ShaderNodeMapRange');edge.inputs['From Min'].default_value=.85;edge.inputs['From Max'].default_value=1.;edge.inputs['To Min'].default_value=0.;edge.inputs['To Max'].default_value=1.;nt.links.new(separate.outputs['X'],edge.inputs['Value']);mix=nt.nodes.new('ShaderNodeMixRGB');mix.inputs[2].default_value=(.016,.006,.002,1);nt.links.new(edge.outputs[0],mix.inputs[0]);nt.links.new(ramp.outputs[0],mix.inputs[1]);nt.links.new(mix.outputs[0],bs.inputs['Base Color'])
irises=[];eyes=[]
for side in ('L','R'):
 eye=bpy.data.objects['EYEBALL_'+side];eyes.append(eye);copy=eye.copy();copy.data=eye.data.copy();sourcecol.objects.link(copy);copy.name='SOURCE_v3_eye_'+side;copy.hide_render=True;copy.hide_set(True);copy.hide_select=True
 # Remove only the old disconnected white catchlight patches from the globe.
 bm=bmesh.new();bm.from_mesh(eye.data);seen=set();groups=[]
 for v in bm.verts:
  if v in seen:continue
  stack=[v];seen.add(v);g=[]
  while stack:
   a=stack.pop();g.append(a)
   for e in a.link_edges:
    b=e.other_vert(a)
    if b not in seen:seen.add(b);stack.append(b)
  groups.append(g)
 bmesh.ops.delete(bm,geom=[v for g in groups if len(g)<100 for v in g],context='VERTS');bm.to_mesh(eye.data);bm.free();eye.data.materials.clear();eye.data.materials.append(sclera)
 for p in eye.data.polygons:p.material_index=0;p.use_smooth=True
 bpy.context.view_layer.update();evaleye=eye.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaleye.to_mesh();mesh.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[t.vertices for t in mesh.loop_triangles],all_triangles=True);evaleye.to_mesh_clear()
 sign=1 if eye.location.y>0 else -1;cy=sign*.004;cz=.002;radius=.057;N=96;M=18;verts=[];faces=[];uvfaces=[]
 def surface(y,z,offset=.0007):
  p,*_=tree.ray_cast(Vector((.3,y,z)),Vector((-1,0,0)));return p.x+offset if p else math.sqrt(max(.001,.091**2-y*y-z*z))+offset
 for j in range(M+1):
  rr=radius*j/M
  for i in range(N+1):
   angle=2*math.pi*i/N;y=cy+rr*math.cos(angle);z=cz+rr*math.sin(angle);verts.append((surface(y,z),y,z))
 for j in range(M):
  for i in range(N):
   a=j*(N+1)+i;b=a+N+1;faces.append((a,a+1,b+1,b));uvfaces.append(((j/M,i/N),(j/M,(i+1)/N),((j+1)/M,(i+1)/N),((j+1)/M,i/N)))
 me=bpy.data.meshes.new('Iris_cap_'+side);me.from_pydata(verts,[],faces);me.materials.append(iris);me.materials.append(pupil);u=me.uv_layers.new(name='Iris_radial_UV')
 for p,coords in zip(me.polygons,uvfaces):
  p.use_smooth=True;p.material_index=1 if p.index//N<7 else 0
  for li,value in zip(p.loop_indices,coords):u.data[li].uv=value
 cap=bpy.data.objects.new('IRIS_PUPIL_'+side,me);eye.users_collection[0].objects.link(cap);cap.parent=eye;cap.matrix_parent_inverse=Matrix.Identity(4);irises.append(cap)
 # Small paired highlights read consistently in render and material preview.
 for n,yoff,zoff,rr in [('main',.014,.024,.0065),('small',-.018,-.013,.0027)]:
  y=cy+yoff;z=cz+zoff;x=surface(y,z,.00115);bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=1);o=bpy.context.object;o.name='EYE_CATCHLIGHT_'+side+'_'+n;o.parent=eye;o.location=(x,y,z);o.scale=(.00075,rr*.78,rr);o.data.materials.append(glint)
  for p in o.data.polygons:p.use_smooth=True
 eye['rest_gaze']='Centered straight-forward iris, 0.004 outward offset correcting prior converged gaze';eye['appearance']='Clean ivory sclera, radial brown iris, black pupil, subtle coat and two small highlights'
# Bake only the NEW iris UV map. The skin atlas is never baked or altered.
bpy.ops.object.select_all(action='DESELECT');cap=irises[0];cap.select_set(True);bpy.context.view_layer.objects.active=cap;image=bpy.data.images.new('Warm_brown_iris_v4',width=1024,height=1024);image.colorspace_settings.name='sRGB';node=nt.nodes.new('ShaderNodeTexImage');node.image=image
for n in nt.nodes:n.select=False
node.select=True;nt.nodes.active=node;sc.cycles.samples=8;sc.render.bake.use_clear=True;sc.render.bake.margin=4;sc.render.bake.use_pass_direct=False;sc.render.bake.use_pass_indirect=False;sc.render.bake.use_pass_color=True;bpy.ops.object.bake(type='DIFFUSE');image.filepath_raw=str(A/'warm_brown_iris_v4.png');image.file_format='PNG';image.save();image.pack();nt.links.new(node.outputs['Color'],bs.inputs['Base Color'])
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();sc.cycles.samples=32;cam=sc.camera
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0))]:render(n,pos)
hair.hide_render=True;render('eyes_detail',(3,0,0),Vector((.18,0,.145)),.52);render('mouth_closed',(3,-.6,0),Vector((.26,0,-.092)),.34)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();render('mouth_open',(3,-.6,0),Vector((.23,0,-.085)),.38)
hair.hide_render=False;ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
notes=bpy.data.texts['READ_ME'];notes.clear();notes.write('v4 local Blender correction, no Tripo spend. Straight-forward centered eyes with new clean sclera, brown radial iris and small catchlights; old v3 eyes preserved hidden. Chin center softened. Mouth corners relaxed and teeth/gums recessed in rest. Original open skin and oral geometry preserved at mouth_open=1. Lash pigment strengthened; original skin UV unchanged. Full facial rig pending.\n')
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head;bpy.ops.wm.save_as_mainfile(filepath=str(A/'explorer_b_balanced_face_v4.blend'));print('V4_PROBE_SAVED')
