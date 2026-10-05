"""Local surface normals, hair clearance, rooted lash cards and oral components."""
import bpy,bmesh,math,json,numpy as np
from pathlib import Path
from mathutils import Vector,kdtree
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v2';O.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend'))
sc=bpy.context.scene;head=bpy.data.objects['HEAD_P2_CLEANUP'];hair=bpy.data.objects['HAIR_HD_FITTED']
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def mat(name,color,rough=.55):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1);p=m.node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;return m
def meshobj(name,verts,faces,coll,material):
 m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update();o=bpy.data.objects.new(name,m);coll.objects.link(o);m.materials.append(material)
 for p in m.polygons:p.use_smooth=True
 return o
def tree(o):
 o.data.calc_loop_triangles();return BVHTree.FromPolygons([v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
surface=tree(head)
def xfront(y,z):
 p,n,i,d=surface.ray_cast(Vector((2,y,z)),Vector((-1,0,0)));return p.x if p else .19
# Open a narrow inspection slit through the existing closed lip contact line.
bm=bmesh.new();bm.from_mesh(head.data)
bm.verts.ensure_lookup_table();seen=set();groups=[]
for v in bm.verts:
 if v.index in seen:continue
 stack=[v];seen.add(v.index);g=[]
 while stack:
  a=stack.pop();g.append(a)
  for e in a.link_edges:
   b=e.other_vert(a)
   if b.index not in seen:seen.add(b.index);stack.append(b)
 groups.append(g)
groups.sort(key=len,reverse=True)
# Remove the generated loose internal fragments/teeth before building clean oral parts.
bmesh.ops.delete(bm,geom=[v for g in groups[3:] for v in g],context='VERTS')
nose_patches=0
for cy in []:  # Keep the generated nose silhouette; patch trial distorted it.
 fs=set(f for f in bm.faces if (c:=f.calc_center_median()).x>.23 and ((c.y-cy)/.024)**2+((c.z-.013)/.025)**2<1)
 es=set(e for f in fs for e in f.edges if sum(g in fs for g in e.link_faces)==1)
 adj={}
 for e in es:
  a,b=e.verts;adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
 if not adj or any(len(v)!=2 for v in adj.values()):continue
 remaining=set(adj);loops=[]
 while remaining:
  start=next(iter(remaining));loop=[start];prev=None
  while True:
   v=loop[-1];remaining.discard(v);nxt=next(w for w in adj[v] if w!=prev)
   if nxt==start:break
   prev=v;loop.append(nxt)
  loops.append(loop)
 loop=max(loops,key=len)
 if len(loop)<8:continue
 samples=np.array([v.co[:] for v in set(v for f in fs for v in f.verts)])
 y=(samples[:,1]-cy)/.024;z=(samples[:,2]-.013)/.025
 A=np.column_stack([np.ones(len(y)),y,z,y*y,y*z,z*z,y*y*y,y*y*z,y*z*z,z*z*z]);coef=np.linalg.lstsq(A,samples[:,0],rcond=None)[0]
 def fit(y,z):
  a=(y-cy)/.024;b=(z-.013)/.025;return float(np.dot(coef,[1,a,b,a*a,a*b,b*b,a*a*a,a*a*b,a*b*b,b*b*b]))
 boundary=[v.co.copy() for v in loop];center=sum(boundary,Vector())/len(boundary)
 if sum(a.y*b.z-b.y*a.z for a,b in zip(boundary,boundary[1:]+boundary[:1]))<0:loop.reverse();boundary.reverse()
 bmesh.ops.delete(bm,geom=list(fs),context='FACES_ONLY');previous=loop
 for j in range(1,7):
  t=j/7;ring=[]
  for c in boundary:
   q=c.lerp(center,t);q.x=fit(q.y,q.z)+(c.x-fit(c.y,c.z))*(1-t)**3;ring.append(bm.verts.new(q))
  for i in range(len(loop)):
   k=(i+1)%len(loop);bm.faces.new((previous[i],previous[k],ring[k],ring[i]))
  previous=ring
 center.x=fit(center.y,center.z);v=bm.verts.new(center)
 for i in range(len(loop)):bm.faces.new((previous[i],previous[(i+1)%len(loop)],v))
 nose_patches+=1
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
local_verts=[v for v in bm.verts if (v.co.x>.19 and abs(v.co.y)<.11 and -.05<v.co.z<.07) or (abs(v.co.y)>.245 and -.1<v.co.z<.23)]
bmesh.ops.remove_doubles(bm,verts=local_verts,dist=.0012)
repair_edges=[]
for e in bm.edges:
 c=(e.verts[0].co+e.verts[1].co)/2
 if e.is_boundary and ((c.x>.19 and abs(c.y)<.11 and -.05<c.z<.07) or (abs(c.y)>.245 and -.10<c.z<.23)):
  repair_edges.append(e)
if repair_edges:bmesh.ops.holes_fill(bm,edges=repair_edges,sides=128)
seam=-.058
fs=[f for f in bm.faces if (c:=f.calc_center_median()).x>.25 and abs(c.y)<.083 and abs(c.z-seam)<.023]
geom=set(fs)
for f in fs:geom.update(f.edges);geom.update(f.verts)
cut=bmesh.ops.bisect_plane(bm,geom=list(geom),dist=1e-6,plane_co=(0,0,seam),plane_no=(0,0,1))
edges=[e for e in cut['geom_cut'] if isinstance(e,bmesh.types.BMEdge) and all(v.co.x>.25 and abs(v.co.y)<.080 for v in e.verts)]
if edges:bmesh.ops.split_edges(bm,edges=edges)
for v in bm.verts:
 if abs(v.co.z-seam)<1e-5 and v.co.x>.25 and abs(v.co.y)<.083:
  center=sum(f.calc_center_median().z for f in v.link_faces)/max(1,len(v.link_faces));v.co.z+=(.00025 if center>=seam else -.00025)*(1-(abs(v.co.y)/.083)**2)
bm.to_mesh(head.data);bm.free();head.data.update()
# Repair winding and shading in affected regions using local surface orientation.
m=head.data;co=np.array([v.co[:] for v in m.vertices]);kd=kdtree.KDTree(len(co))
for i,c in enumerate(co):kd.insert(c,i)
kd.balance();normals=[];affected=[]
for i,c in enumerate(co):
 nose_lip=c[0]>.19 and abs(c[1])<.12 and -.17<c[2]<.07
 ear=abs(c[1])>.225 and -.1<c[2]<.23
 eye_front=False
 affected.append(nose_lip or ear or eye_front)
 if not affected[-1]:normals.append(m.vertices[i].normal[:]);continue
 pts=co[[j for _,j,d in kd.find_n(c,14)]];p=pts-pts.mean(0);_,vec=np.linalg.eigh(p.T@p);n=vec[:,0]
 out=np.array([1.,0.,0.]) if nose_lip or eye_front or c[0]>-.09 else np.array([-1.,.1*np.sign(c[1]),0.])
 if n@out<0:n=-n
 normals.append(n.tolist())
bm=bmesh.new();bm.from_mesh(m);bm.verts.ensure_lookup_table();flips=0
for f in bm.faces:
 if any(affected[v.index] for v in f.verts):
  target=sum((Vector(normals[v.index]) for v in f.verts),Vector())
  if f.normal.dot(target)<0:f.normal_flip();flips+=1
bm.to_mesh(m);bm.free();m.update();m.normals_split_custom_set_from_vertices(normals)
uv=m.uv_layers.get('Reference_Front_Preview')
for p in m.polygons:
 for li in p.loop_indices:
  c=m.vertices[m.loops[li].vertex_index].co;uv.data[li].uv=((284+(c.y+.31958)/.63916*742)/1312,1-(67+(.499756-c.z)/.864756*1005)/1199)
head.name='HEAD_P2_Local_Repair'
skin=head.data.materials[0];nd=skin.node_tree.nodes;lk=skin.node_tree.links;bs=nd['Principled BSDF'];previous=bs.inputs['Base Color'].links[0].from_socket
geo=nd.new('ShaderNodeNewGeometry');xyz=nd.new('ShaderNodeSeparateXYZ');lk.new(geo.outputs['Position'],xyz.inputs[0]);ab=nd.new('ShaderNodeMath');ab.operation='ABSOLUTE';lk.new(xyz.outputs['Y'],ab.inputs[0]);fade=nd.new('ShaderNodeMapRange');fade.inputs['From Min'].default_value=.235;fade.inputs['From Max'].default_value=.278;lk.new(ab.outputs[0],fade.inputs[0]);mx=nd.new('ShaderNodeMixRGB');mx.inputs[2].default_value=(.78,.49,.34,1);lk.new(fade.outputs[0],mx.inputs[0]);lk.new(previous,mx.inputs[1]);lk.new(mx.outputs[0],bs.inputs['Base Color'])
# Hair displacement is local and smoothly fades into unchanged locks.
hair_changed=0
for v in hair.data.vertices:
 c=v.co;y=abs(c.y);w=smooth(.08,.19,c.x)*(1-smooth(.29,.38,c.z))*smooth(-.23,-.10,c.z)*math.exp(-((y-.19)/.09)**2)
 if w>.001:
  side=1 if c.y>=0 else -1;c.y+=side*(.062 if side>0 else .038)*w;c.z+=.030*w*smooth(.10,.22,c.z);hair_changed+=1
 c.z+=.030*math.exp(-((c.y+.070)/.065)**2-((c.z-.19)/.075)**2)*smooth(.12,.24,c.x)*(1-smooth(-.02,.02,c.y))
hair.data.update()
# Lower-alpha dust is suppressed in shader; the source atlas remains unchanged.
cardsmat=bpy.data.materials['Brow_Lash_RGBA_Atlas'];nodes=cardsmat.node_tree.nodes;links=cardsmat.node_tree.links;p=nodes['Principled BSDF'];tex=next(n for n in nodes if n.type=='TEX_IMAGE')
threshold=nodes.new('ShaderNodeMapRange');threshold.clamp=True;threshold.inputs['From Min'].default_value=.13;threshold.inputs['From Max'].default_value=.8;links.new(tex.outputs['Alpha'],threshold.inputs['Value'])
attr=nodes.new('ShaderNodeVertexColor');attr.layer_name='EdgeFade';mul=nodes.new('ShaderNodeMath');mul.operation='MULTIPLY';links.new(threshold.outputs[0],mul.inputs[0]);links.new(attr.outputs['Color'],mul.inputs[1]);links.new(mul.outputs[0],p.inputs['Alpha'])
brow=bpy.data.objects['BROW_master_mirrored'];fade=brow.data.color_attributes.new(name='EdgeFade',type='FLOAT_COLOR',domain='CORNER')
for v in fade.data:v.color=(1,1,1,1)
atlas=tex.image;pix=np.array(atlas.pixels[:]).reshape(atlas.size[1],atlas.size[0],4)[::-1];alpha=pix[:,:,3]
coll=bpy.data.collections['03_UV_Brows_Lashes']
for name in ['LASH_UPPER_master_mirrored','LASH_LOWER_master_mirrored']:bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
def lash(upper):
 nx=32;ny=4;verts=[];uvs=[];fades=[];faces=[]
 xs=np.linspace(120,925,nx+1) if upper else np.linspace(205,1070,nx+1)
 roots=[]
 for x in xs:
  lo,hi=(450,900) if upper else (970,1200);ix=int(x)
  score=(alpha[lo:hi,max(0,ix-4):ix+5]>.85).sum(1);root=int(np.argmax(np.convolve(score,np.ones(7),mode='same')))+lo;roots.append(root)
 roots=np.convolve(np.pad(roots,(2,2),mode='edge'),np.ones(5)/5,mode='valid')
 for j in range(ny+1):
  t=j/ny
  for i,x in enumerate(xs):
   s=i/nx;y=.043+.165*s;arc=math.sin(math.pi*s)**.70
   zroot=(.108+.070*arc) if upper else (.098-.028*arc)
   rootx=xfront(y,zroot)+.0012
   length=((.020+.050*s) if upper else (.004+.006*s))*math.sin(math.pi*s)**.35
   z=zroot+(1 if upper else -1)*length*t
   vx=rootx+.009*t+.005*t*t
   verts.append((vx,y+.006*t*s,z));uvs.append((x/1254,1-(roots[i]-3+t*(190 if upper else 65))/1254));fades.append(min(1,s*12,(1-s)*12))
 for j in range(ny):
  for i in range(nx):
   a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
 o=meshobj('LASH_'+('UPPER' if upper else 'LOWER')+'_Rooted',verts,faces,coll,cardsmat);o.data.uv_layers.new(name='HairAtlas');o.data.color_attributes.new(name='EdgeFade',type='FLOAT_COLOR',domain='CORNER');uv=o.data.uv_layers['HairAtlas'];fade=o.data.color_attributes['EdgeFade']
 for p in o.data.polygons:
  for li in p.loop_indices:
   vi=o.data.loops[li].vertex_index;uv.data[li].uv=uvs[vi];fade.data[li].color=(fades[vi],)*3+(1,)
 mod=o.modifiers.new('Mirror_other_eye','MIRROR');mod.use_axis=(False,True,False);mod.use_mirror_merge=False
 return o
upper=lash(True);lower=lash(False)
# Physical mouth components, independent for later jaw/face rig binding.
oral=bpy.data.collections.new('04_Mouth_Interior');sc.collection.children.link(oral)
mucosa=mat('Oral_mucosa',(.12,.025,.03),.62);gum=mat('Gum_soft_rose',(.38,.10,.12),.5);ivory=mat('Teeth_ivory',(.8,.76,.64),.32);tonguemat=mat('Tongue_rose',(.43,.12,.15),.47)
ctrl=bpy.data.objects.new('MOUTH_INSPECTION_control',None);oral.objects.link(ctrl);ctrl['open']=0.;ctrl.id_properties_ui('open').update(min=0,max=1,description='Inspection only. 0 closed rest, 1 oral opening; not a full facial rig.')
def drive(key):
 d=key.driver_add('value').driver;d.expression='v';v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=ctrl;v.targets[0].data_path='["open"]'
head.shape_key_add(name='Basis');key=head.shape_key_add(name='Mouth_Open_Inspection')
for i,v in enumerate(key.data):
 c=co[i];w=smooth(.10,.24,c[0])*math.sqrt(max(0,1-(abs(c[1])/.085)**2))
 if c[2]<seam:weight=w*(1-smooth(.05,.15,seam-c[2]));v.co.z-=.028*weight;v.co.x-=.004*weight
 elif c[2]<seam+.026:v.co.z+=.002*w*(1-smooth(.005,.026,c[2]-seam))
drive(key)
n=64;rings=10;vs=[];opened=[];faces=[]
for j in range(rings+1):
 t=j/rings
 for i in range(n):
  a=2*math.pi*i/n;s=math.sin(a);y=.083*math.cos(a)*(1-.15*t)
  zr=seam
  z=(zr+.0007*s)*(1-smooth(0,.45,t))+(seam+.047*s)*smooth(0,.45,t)
  x=min(xfront(y,zr)-.012,.276-1.4*y*y)*(1-t)+.095*t
  vs.append((x,y,z));opened.append((x,y,z+(.002 if s>=0 else -.028)*abs(s)*(1-.5*t)))
for j in range(rings):
 for i in range(n):a=j*n+i;b=j*n+(i+1)%n;faces.append((a,a+n,b+n,b))
faces.append(tuple(range(rings*n,(rings+1)*n)))
bag=meshobj('ORAL_CAVITY_mucosa',vs,faces,oral,mucosa);bag.shape_key_add(name='Basis');key=bag.shape_key_add(name='Open_with_lips')
for v,c in zip(key.data,opened):v.co=c
drive(key)
def lower_follow(o):
 d=o.driver_add('location',2).driver;d.expression='-.020*v';v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=ctrl;v.targets[0].data_path='["open"]'
for up in [True,False]:
 verts=[];faces=[];segments=32
 for k in range(segments+1):
  a=-1.23+2.46*k/segments;x=.165+.081*math.cos(a);y=.078*math.sin(a);z=-.040 if up else -.095
  for dx,dz in [(-.009,-.009),(.009,-.009),(.009,.009),(-.009,.009)]:verts.append((x+dx,y,z+dz))
 for k in range(segments):
  for j in range(4):a=k*4+j;b=k*4+(j+1)%4;faces.append((a,b,b+4,a+4))
 faces.extend([(3,2,1,0),tuple(range(segments*4,segments*4+4))])
 obj=meshobj(('UPPER' if up else 'LOWER')+'_GUM',verts,faces,oral,gum)
 if not up:lower_follow(obj)
 teeth=[]
 for i in range(10):
  a=-1.12+2.24*i/9;x=.165+.081*math.cos(a);y=.078*math.sin(a);z=-.058 if up else -.077
  bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,z));o=bpy.context.object;o.name='Tooth';o.dimensions=(.019,.015,.024 if up else .020);o.rotation_euler[2]=-a
  bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(ivory)
  mod=o.modifiers.new('Rounded_enamel','BEVEL');mod.width=.004;mod.segments=3;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
  for p in o.data.polygons:p.use_smooth=True
  for c in list(o.users_collection):c.objects.unlink(o)
  oral.objects.link(o);teeth.append(o)
 bpy.ops.object.select_all(action='DESELECT')
 for o in teeth:o.select_set(True)
 bpy.context.view_layer.objects.active=teeth[0];bpy.ops.object.join();o=bpy.context.object;o.name=('UPPER' if up else 'LOWER')+'_TEETH_10'
 bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
 if not up:lower_follow(o)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=(.187,0,-.092));tongue=bpy.context.object;tongue.name='TONGUE';tongue.scale=(.051,.049,.009);bpy.ops.object.transform_apply(location=True,rotation=False,scale=True);tongue.data.materials.append(tonguemat)
for c in list(tongue.users_collection):c.objects.unlink(tongue)
oral.objects.link(tongue)
for p in tongue.data.polygons:p.use_smooth=True
lower_follow(tongue)
ctrl['open']=0.;sc.frame_set(1);bpy.context.view_layer.update()
sc.render.engine='CYCLES';sc.cycles.samples=32
head.hide_render=False;hair.hide_render=False
cam=sc.camera
def view(pos,target=(0,0,.08),scale=1.18):
 target=Vector(target);cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
view((3,0,.02))
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
text=bpy.data.texts.new('V2_README');text.write('Local refinement v2. Original v1 preserved.\nHair swept away from eyes. Rooted UV lash cards. Nose/lip/ear patch winding correction.\nMouth interior: pouch, gums, 20 teeth, tongue. Select MOUTH_INSPECTION_control, Custom Properties > open (0..1).\nThis control is an inspection morph, not a production facial rig. Neutral is closed.\nP2 topology still needs deformation retopology before final rigging. Head front projection is a preview material.\n')
sc['STATUS']='V2 local repairs and mouth construction; inspect opening before facial rigging.'
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(O/'explorer_b_hybrid_bust_v2.blend'))
for name,pos in [('front',(3,0,.02)),('angle',(3,-2,.15)),('side',(0,-3,.02))]:
 view(pos);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True;view((3,-.6,.02),(0,0,.02),.64);sc.render.filepath=str(O/'face_detail.png');bpy.ops.render.render(write_still=True)
ctrl['open']=1.;sc.frame_set(2);bpy.context.view_layer.update();view((3,-.2,0),(.20,0,-.055),.34);sc.render.filepath=str(O/'mouth_open.png');bpy.ops.render.render(write_still=True)
for o in sc.objects:
 if o.type=='MESH' and o not in list(oral.objects):o.hide_render=True
bag.hide_render=True;view((1,-.35,.5),(.18,0,-.06),.24);sc.render.filepath=str(O/'oral_cutaway.png');bpy.ops.render.render(write_still=True)
report={'source':'explorer_b_hybrid_bust_v1','nose_local_patches':nose_patches,'normal_reoriented_faces':flips,'hair_vertices_adjusted':hair_changed,'lip_seam_split_edges':len(edges),'head_vertices':len(head.data.vertices),'head_polygons':len(head.data.polygons),'oral_objects':[o.name for o in oral.objects],'api_credits':0,'full_facial_rig':False,'mouth_control':'MOUTH_INSPECTION_control[open]','remaining':['P2 deformation topology requires retopology validation.','Head color remains reference projection.','Inspection opening is not a complete production facial rig.']}
(O/'refinement-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
