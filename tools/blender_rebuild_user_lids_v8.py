"""Replace faulty generated eye strips with a connected eyelid annulus and solid lashes."""
import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';A.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(A/'assembled_workbench.blend'));sc=bpy.context.scene;head=bpy.data.objects['FACE_user_head'];old=head.data;hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects.new('FACE_CONTROLS',None);sc.collection.objects.link(ctrl);bpy.context.preferences.filepaths.save_version=0
for obj in list(sc.objects):
 if obj.name.startswith(('LASH_upper_','LID_SKIN')):bpy.data.objects.remove(obj,do_unlink=True)

def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
oldkeys={k.name:[v.co.copy() for v in k.data] for k in old.shape_keys.key_blocks};basis=oldkeys['Basis_closed_smile'];opened=oldkeys['Mouth_open_original'];probe=json.loads((A/'eye-patch-probe.json').read_text());removed=set(i for d in probe.values() for i in d['removed_faces']);retained=[p for p in old.polygons if p.index not in removed];used=sorted({i for p in retained for i in p.vertices});mapping={i:j for j,i in enumerate(used)}
vertices=[basis[i].copy() for i in used];openverts=[opened[i].copy() for i in used];faces=[];uv0=[];uv1=[];materials=[]
for p in retained:
 faces.append(tuple(mapping[i] for i in p.vertices));coords=[tuple(old.uv_layers.active.data[i].uv) for i in p.loop_indices];uv0.append(coords);uv1.append(coords);materials.append(0)
image=next(n.image for n in old.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image);iw,ih=image.size;pixels=np.array(image.pixels[:],dtype=np.float32).reshape(ih,iw,4);vertexuv={}
# Match the two skin materials using the same physically plausible, matte response.
skin_shader=old.materials[0].node_tree.nodes.get('Principled BSDF')
for name,value in [('Roughness',.5),('Metallic',0.),('Specular IOR Level',.3)]:
 for link in list(skin_shader.inputs[name].links):old.materials[0].node_tree.links.remove(link)
 skin_shader.inputs[name].default_value=value
for link in list(skin_shader.inputs['Normal'].links):old.materials[0].node_tree.links.remove(link)
for p in retained:
 for li in p.loop_indices:vertexuv.setdefault(old.loops[li].vertex_index,[]).append(tuple(old.uv_layers.active.data[li].uv))
def sample_color(i):
 cols=[pixels[min(ih-1,max(0,int(v*ih))),min(iw-1,max(0,int(u*iw))),:3] for u,v in vertexuv[i]];valid=[c for c in cols if c[0]>.25 and c[1]>.11 and c[0]>c[2]*1.1];return np.mean(valid or cols,axis=0)
def tree_for(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();tree=BVHTree.FromPolygons([o.matrix_world@v.co for v in me.vertices],[t.vertices for t in me.loop_triangles],all_triangles=True);eo.to_mesh_clear();return tree
eye_data={};skinmats=[];N=128;K=8;new_start=len(vertices);misses=[]
old.calc_loop_triangles();alltris=[tuple(t.vertices) for t in old.loop_triangles];source_tree=BVHTree.FromPolygons(basis,alltris,all_triangles=True);skin_tree=source_tree
for sign in [-1,1]:
 side='R' if sign==-1 else 'L';face_start=len(faces);d=probe[str(sign)];ids=d['border_groups'][0]['verts'];remove=set(d['removed_faces']);edgefaces={}
 for p in old.polygons:
  for e in p.edge_keys:edgefaces.setdefault(e,[]).append(p.index)
 adj={}
 for (a,b),ps in edgefaces.items():
  if any(p in remove for p in ps) and any(p not in remove for p in ps):adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
 start=max(ids,key=lambda i:sign*basis[i].y);ordered=[start];prev=None;cur=start
 while True:
  nxt=next(i for i in adj[cur] if i!=prev)
  if nxt==start:break
  ordered.append(nxt);prev,cur=cur,nxt
 assert len(ordered)==len(ids)
 area=sum(sign*basis[a].y*basis[b].z-sign*basis[b].y*basis[a].z for a,b in zip(ordered,ordered[1:]+ordered[:1]))
 if area<0:ordered=[ordered[0]]+list(reversed(ordered[1:]))
 lengths=[math.hypot((sign*(basis[b].y-basis[a].y))/.094,(basis[b].z-basis[a].z)/.061) for a,b in zip(ordered,ordered[1:]+ordered[:1])];angles=np.array([0]+list(np.cumsum(lengths)[:-1]))/sum(lengths)*2*math.pi;outs=[basis[i] for i in ordered];colors=np.array([sample_color(i) for i in ordered])
 for _ in range(14):colors=colors*.5+(np.roll(colors,1,axis=0)+np.roll(colors,-1,axis=0))*.25
 ext_angles=np.concatenate(([angles[-1]-2*math.pi],angles,[angles[0]+2*math.pi]));extouts=[outs[-1]]+outs+[outs[0]];extcolors=np.concatenate(([colors[-1]],colors,[colors[0]]));eye=tree_for(bpy.data.objects['EYEBALL_'+side]);sideids=[];blinkpoints={}
 def boundary(theta):
  j=int(np.searchsorted(ext_angles,theta)-1);f=(theta-ext_angles[j])/(ext_angles[j+1]-ext_angles[j]);return extouts[j].lerp(extouts[j+1],float(f))
 def aperture(theta,blink=False,sign=sign,eye=eye):
  u=math.cos(theta);s=math.sin(theta);y=sign*(.141+.056*u);mid=.109+.008*(u+1)/2;upper=mid+.042*abs(s)**.9;lower=mid-.046*abs(s)**.9;z=(lower+.23*(upper-lower)+(-.0004 if s>=0 else .0004)) if blink else (upper if s>=0 else lower);p,*_=eye.ray_cast(Vector((1,y,z)),Vector((-1,0,0)))
  if p is None:misses.append([side,theta,y,z]);p=Vector((.19,y,z))
  p.x+=.003;return p
 # A dedicated cylindrical eye-skin texture is sampled from the unchanged outer skin edge.
 texarr=np.zeros((128,1024,4),dtype=np.float32)
 for j in range(1024):
  theta=2*math.pi*j/1024;rgb=np.array([np.interp(theta,ext_angles,extcolors[:,c]) for c in range(3)])
  for k in range(128):
   t=1-k/127;texarr[k,j,:3]=rgb*(1-.015*t);texarr[k,j,3]=1
 tex=bpy.data.images.new('Clean_eyelid_skin_'+side,width=1024,height=128);tex.colorspace_settings.name=image.colorspace_settings.name;tex.pixels.foreach_set(texarr.ravel());tex.filepath_raw=str(A/('eyelid_skin_'+side+'.png'));tex.file_format='PNG';tex.save();tex.pack()
 mat=bpy.data.materials.new('Clean_eyelid_skin_'+side);mat.use_nodes=True;bs=mat.node_tree.nodes['Principled BSDF'];bs.inputs['Roughness'].default_value=.50;bs.inputs['Specular IOR Level'].default_value=.30;node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=tex;uvnode=mat.node_tree.nodes.new('ShaderNodeUVMap');uvnode.uv_map='Eye_patch_UV';mat.node_tree.links.new(uvnode.outputs[0],node.inputs['Vector']);mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color']);skinmats.append(mat);mi=1+len(skinmats)-1
 rings=[]
 for k in range(1,K+1):
  t=k/K;ring=[]
  for j in range(N):
   theta=2*math.pi*j/N;outer=boundary(theta);inner=aperture(theta);p=outer.lerp(inner,t);globe,*_=eye.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)))
   if globe is not None:p.x=max(p.x,globe.x+.003)
   if k==K:p=inner.copy()
   idx=len(vertices);vertices.append(p);openverts.append(p.copy());ring.append(idx);sideids.append(idx);closed=outer.lerp(aperture(theta,True),t);cg,*_=eye.ray_cast(Vector((1,closed.y,closed.z)),Vector((-1,0,0)))
   if cg is not None:closed.x=max(closed.x,cg.x+.003)
   if k==K:closed=aperture(theta,True)
   blinkpoints[idx]=closed
  rings.append(ring)
 # Zipper the existing outer border to the first regular ring, sharing the original vertices.
 a=0;b=0;outerring=[mapping[i] for i in ordered];first=rings[0]
 while a<len(ordered) or b<N:
  nexta=float(angles[(a+1)%len(ordered)])+(2*math.pi if a+1>=len(ordered) else 0) if a<len(ordered) else 1e10;nextb=2*math.pi*(b+1)/N if b<N else 1e10
  if nexta<nextb:
   aa=a%len(ordered);ab=(a+1)%len(ordered);bb=b%N;faces.append((outerring[aa],outerring[ab],first[bb]));uv1.append([(float(angles[aa]/(2*math.pi))+(1 if a>=len(ordered) else 0),1),(float(angles[ab]/(2*math.pi))+(1 if a+1>=len(ordered) else 0),1),(b/N,1-1/K)]);a+=1
  else:
   aa=a%len(ordered);bb=b%N;bc=(b+1)%N;faces.append((outerring[aa],first[bc],first[bb]));uv1.append([(float(angles[aa]/(2*math.pi))+(1 if a>=len(ordered) else 0),1),((b+1)/N,1-1/K),(b/N,1-1/K)]);b+=1
  uv0.append([(0,0)]*3);materials.append(mi)
 for k in range(K-1):
  for j in range(N):
   nj=(j+1)%N;faces.append((rings[k][j],rings[k][nj],rings[k+1][nj],rings[k+1][j]));uv0.append([(0,0)]*4);uv1.append([(j/N,1-(k+1)/K),((j+1)/N,1-(k+1)/K),((j+1)/N,1-(k+2)/K),(j/N,1-(k+2)/K)]);materials.append(mi)
 if sign<0:
  for i in range(face_start,len(faces)):faces[i]=tuple(reversed(faces[i]));uv0[i]=list(reversed(uv0[i]));uv1[i]=list(reversed(uv1[i]))
 eye_data[side]={'rings':rings,'outer_ids':outerring,'blink_points':blinkpoints,'aperture':aperture,'eye_tree':eye,'sign':sign,'boundary':boundary}
assert not misses,misses[:8]
# Fair the new annulus against its exact outer boundary and globe-conforming inner margin.
# Do not ray-project onto the old generated strips: they contain overlapping torn surfaces.
neighbors=[set() for _ in vertices]
for face in faces:
 for a,b in zip(face,face[1:]+face[:1]):neighbors[a].add(b);neighbors[b].add(a)
seam_reference=[p.copy() for p in vertices]
for side,d in eye_data.items():
 movable=set(i for ring in d['rings'][:-1] for i in ring);eye=d['eye_tree']
 closedcoords={i:d['blink_points'][i].copy() for ring in d['rings'] for i in ring}
 for _ in range(60):
  prev=[v.copy() for v in vertices];prevc={i:c.copy() for i,c in closedcoords.items()}
  for i in movable:
   vertices[i]=prev[i].lerp(sum((prev[j] for j in neighbors[i]),Vector())/len(neighbors[i]),.45)
   pts=[prevc[j] if j in prevc else prev[j] for j in neighbors[i]];closedcoords[i]=prevc[i].lerp(sum(pts,Vector())/len(pts),.45)
   for p in [vertices[i],closedcoords[i]]:
    hit,*_=eye.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)))
    if hit is not None:p.x=max(p.x,hit.x+.003)
 for i,c in closedcoords.items():d['blink_points'][i]=c
 for ring in d['rings']:
  for i in ring:openverts[i]=vertices[i].copy()
# Blend the seam into two neighboring original skin rings, instead of freezing a jagged cut.
for side,d in eye_data.items():
 depths={i:0 for i in d['outer_ids']};front=set(depths)
 for depth in range(1,4):
  nxt={j for i in front for j in neighbors[i] if j not in depths};depths.update({j:depth for j in nxt});front=nxt
 fixed=set(d['rings'][-1]);affected=set(depths)-fixed;closed=[p.copy() for p in vertices]
 for i,c in d['blink_points'].items():closed[i]=c.copy()
 for _ in range(18):
  prev=[p.copy() for p in vertices];pc=[p.copy() for p in closed]
  for i in affected:
   w=.32/(1+depths[i]*.45);vertices[i]=prev[i].lerp(sum((prev[j] for j in neighbors[i]),Vector())/len(neighbors[i]),w);closed[i]=pc[i].lerp(sum((pc[j] for j in neighbors[i]),Vector())/len(neighbors[i]),w)
   for p in [vertices[i],closed[i]]:
    hit,*_=d['eye_tree'].ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)))
    if hit is not None:p.x=max(p.x,hit.x+.003)
   if i<new_start:
    ref=seam_reference[i]
    for p in [vertices[i],closed[i]]:p.y=ref.y;p.z=ref.z;p.x=max(ref.x-.006,min(ref.x+.006,p.x))
 for i in affected:openverts[i]=vertices[i].copy();d['blink_points'][i]=closed[i].copy()
mouthchanged=0
me=bpy.data.meshes.new('Face_clean_connected_lids_v6');me.from_pydata(vertices,[],faces);me.materials.append(old.materials[0]);[me.materials.append(m) for m in skinmats];u0=me.uv_layers.new(name='Original_Tripo_UV');u1=me.uv_layers.new(name='Eye_patch_UV')
for p,c0,c1,mi in zip(me.polygons,uv0,uv1,materials):
 p.material_index=mi;p.use_smooth=True
 for li,a,b in zip(p.loop_indices,c0,c1):u0.data[li].uv=a;u1.data[li].uv=b
head.data=me;head.shape_key_add(name='Basis_closed_smile');op=head.shape_key_add(name='Mouth_open_original')
for v,c in zip(op.data,openverts):v.co=c
def driver(key,prop,expression='v'):
 dr=key.driver_add('value').driver;dr.expression=expression;var=dr.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=ctrl;var.targets[0].data_path='["'+prop+'"]'
driver(op,'mouth_open')
for side,d in eye_data.items():
 key=head.shape_key_add(name='Blink_'+side)
 for idx,c in d['blink_points'].items():key.data[idx].co=c
 ctrl['blink_'+side]=0.;ctrl.id_properties_ui('blink_'+side).update(min=0,max=1);driver(key,'blink_'+side)
 correction=head.shape_key_add(name='Blink_arc_'+side)
 for idx,c in d['blink_points'].items():
  mid=vertices[idx].lerp(c,.5);hit,*_=d['eye_tree'].ray_cast(Vector((1,mid.y,mid.z)),Vector((-1,0,0)))
  if hit is not None:correction.data[idx].co.x+=max(0,hit.x+.003-mid.x)
 driver(correction,'blink_'+side,'4*v*(1-v)')

# Preserve retargeted MPFB face units on retained skin and interpolate them across the local eye patch.
from mathutils.kdtree import KDTree
kt=KDTree(len(basis))
for i,p in enumerate(basis):kt.insert(p,i)
kt.balance()
for name,coords in oldkeys.items():
 if not name.startswith('!ex-'):continue
 key=head.shape_key_add(name=name)
 for i,oldid in enumerate(used):key.data[i].co=vertices[i]+coords[oldid]-basis[oldid]
 for i in range(new_start,len(vertices)):
  near=kt.find_n(vertices[i],4);ws=[1/max(.001,d)**2 for _,j,d in near];total=sum(ws);delta=sum(((coords[j]-basis[j])*(w/total) for (_,j,d),w in zip(near,ws)),Vector());key.data[i].co=vertices[i]+delta
lash=bpy.data.materials.new('Solid_lashes_uniform_dark_v6');lash.use_nodes=True;bs=lash.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.008,.003,.0018,1);bs.inputs['Roughness'].default_value=.55;bs.inputs['Specular IOR Level'].default_value=.22
me.calc_loop_triangles();headtri=[tuple(t.vertices) for t in me.loop_triangles];headtree=BVHTree.FromPolygons(vertices,headtri,all_triangles=True)
for side,d in eye_data.items():
 sign=d['sign'];eye=d['eye_tree'];vv=[];cc=[];ff=[];T=80;closedhead=[v.co.copy() for v in head.data.shape_keys.key_blocks['Blink_'+side].data];closedtree=BVHTree.FromPolygons(closedhead,headtri,all_triangles=True)
 def lashcoords(theta,closed=False):
  inner=d['aperture'](theta,closed);s=math.sin(theta);width=(.003+.006*max(0,s)**.7)*smooth(.02,.22,theta)*(1-smooth(2.70,3.12,theta));root=inner.copy();top=inner.copy();top.z+=width*(.65 if closed else 1);hit,*_=eye.ray_cast(Vector((1,top.y,top.z)),Vector((-1,0,0)))
  if hit is not None:top.x=max(top.x,hit.x+.0034)
  tree=closedtree if closed else headtree
  for point in [root,top]:
   hit,*_=tree.ray_cast(Vector((1,point.y,point.z)),Vector((-1,0,0)))
   if hit is not None:point.x=hit.x+.00065
  return root,top
 # The complete thin volume uses the same pigment on front, back and all edges.
 for j in range(T+1):
  theta=math.pi*j/T;root,top=lashcoords(theta);cr,ct=lashcoords(theta,True)
  for p,q,dx in [(root,cr,.00035),(top,ct,.00035),(root,cr,-.00045),(top,ct,-.00045)]:p=p.copy();q=q.copy();p.x+=dx;q.x+=dx;vv.append(p);cc.append(q)
 for j in range(T):
  a=4*j;b=4*(j+1);ff.extend([(a,a+1,b+1,b),(a+2,b+2,b+3,a+3),(a+1,a+3,b+3,b+1),(a,b,b+2,a+2)])
 ff.extend([(0,2,3,1),(4*T,4*T+1,4*T+3,4*T+2)])
 # Small tapered outer flick, conforming to the eyelid surface in both poses.
 wing_rest=[];wing_closed=[]
 for closed in [False,True]:
  a=d['aperture'](0,closed);b=d['aperture'](.25,closed);tip=Vector((.16,sign*.228,.137));points=[];tree=closedtree if closed else headtree
  for p in [a,b,tip]:
   p=p.copy();hit,*_=tree.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)))
   if hit is not None:p.x=hit.x+.0007
   points.append(p)
  (wing_closed if closed else wing_rest).extend(points)
 start=len(vv)
 for delta in [.00035,-.00045]:
  for p,q in zip(wing_rest,wing_closed):p=p.copy();q=q.copy();p.x+=delta;q.x+=delta;vv.append(p);cc.append(q)
 ff.extend([(start,start+1,start+2),(start+3,start+5,start+4),(start,start+3,start+4,start+1),(start+1,start+4,start+5,start+2),(start+2,start+5,start+3,start)])
 ff=[tuple(reversed(f)) for f in ff] if sign<0 else ff;lm=bpy.data.meshes.new('Solid_lash_'+side);lm.from_pydata(vv,[],ff);lm.materials.append(lash);obj=bpy.data.objects.new('LASH_upper_'+side,lm);head.users_collection[0].objects.link(obj)
 for p in lm.polygons:p.use_smooth=True
 obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='Blink_'+side)
 for v,c in zip(key.data,cc):v.co=c
 driver(key,'blink_'+side)
 correction=obj.shape_key_add(name='Blink_arc_'+side)
 for idx,(p,c) in enumerate(zip(vv,cc)):
  mid=p.lerp(c,.5);hit,*_=eye.ray_cast(Vector((1,mid.y,mid.z)),Vector((-1,0,0)))
  if hit is not None:correction.data[idx].co.x+=max(0,hit.x+.0034-mid.x)
 driver(correction,'blink_'+side,'4*v*(1-v)')
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();sc.cycles.samples=20;sc.render.resolution_x=720;sc.render.resolution_y=800;cam=sc.camera
def render(n,pos,target,scale):
 cam.location=Vector(target)+Vector(pos);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True;render('eyes_rebuilt',(3,0,0),(.18,0,.145),.53);render('eye_angle_L',(3,-2,0),(.18,-.12,.145),.28);render('mouth_closed',(3,-.6,0),(.26,0,-.092),.34)
ctrl['blink_L']=ctrl['blink_R']=1.;ctrl.update_tag();sc.frame_set(2);bpy.context.view_layer.update();render('blink_closed',(3,0,0),(.18,0,.145),.53);ctrl['blink_L']=ctrl['blink_R']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();hair.hide_render=False
render('front',(3,0,0),(0,0,.04),1.23);target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
report={'head_vertices_before':len(old.vertices),'head_vertices_after':len(me.vertices),'replaced_eye_faces':len(removed),'new_skin_vertices':len(vertices)-new_start,'lash_vertices_total':660,'skin_and_lashes_separate':True,'mouth_corner_vertices_closed':mouthchanged,'eye_aperture_ray_misses':len(misses),'cost':0,'source_v5_preserved':True,'old_vertex_mapping':used};(A/'repair-report.json').write_text(json.dumps(report,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(A/'lids_repaired_workbench.blend'));print('REPAIR_V6',json.dumps({k:v for k,v in report.items() if k!='old_vertex_mapping'}))
