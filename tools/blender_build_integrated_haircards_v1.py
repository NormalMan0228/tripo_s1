"""Rebuild the approved HD form as editable guides, UV ribbons and a scalp base."""
import bpy,math,json,random,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1';OUT=O/'assembly';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(O/'hair/fitted_form.blend'));sc=bpy.context.scene
head=bpy.data.objects['FACE_Tripo_integrated_0'];hd=bpy.data.objects['HAIR_Tripo_HD_form_guide']
def tree(o):
 o.data.calc_loop_triangles();return BVHTree.FromPolygons([v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
skin=tree(head);center=Vector((-.045,0,.205))
def ray(bt,d):
 p,n,idx,dist=bt.ray_cast(center+d*2,-d,3)
 if p is None or (p-center).dot(d)<.03:return None
 return p
def direction(phi,theta):return Vector((math.cos(phi)*math.sin(theta),math.sin(phi)*math.sin(theta),math.cos(theta)))
# Correct the guide's scalp fit. The immutable GLB remains on disk.
for v in hd.data.vertices:
 q=v.co-center
 if q.length<.01:continue
 d=q.normalized();p=ray(skin,d)
 if p is not None and v.co.z>.07 and q.length<(p-center).length+.014:
  v.co=center+d*((p-center).length+.014)
hd.data.update();form=tree(hd)
for p in hd.data.polygons:p.use_smooth=True
hd['source']='hair/model.glb; separate approved four-view Tripo HD task'
hd['role']='Hidden dense form reference, excluded from game export'
hd.hide_render=True;hd.hide_set(True);hd.hide_select=True
cardscol=bpy.data.collections.new('03_Hair_cards_GAME');sc.collection.children.link(cardscol)
guidescol=bpy.data.collections.new('92_Editable_hair_guides');sc.collection.children.link(guidescol)
def mesh(name,vs,fs,material):
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update();ob=bpy.data.objects.new(name,me);cardscol.objects.link(ob);me.materials.append(material)
 for f in me.polygons:f.use_smooth=True
 return ob
mat=bpy.data.materials.new('Hair_cards_strand_RGBA');mat.use_nodes=True;mat.surface_render_method='DITHERED';mat.use_transparency_overlap=True
bs=mat.node_tree.nodes['Principled BSDF'];bs.inputs['Roughness'].default_value=.72;bs.inputs['Sheen Weight'].default_value=.05;bs.inputs['Specular IOR Level'].default_value=.15
im=bpy.data.images.load(str(O/'haircards/strand_atlas_rgba.png'));im.pack();tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im;tex.extension='CLIP'
mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color']);mat.node_tree.links.new(tex.outputs['Alpha'],bs.inputs['Alpha'])
base=bpy.data.materials.new('Scalp_base_chocolate');base.use_nodes=True;bs=base.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.045,.021,.010,1);bs.inputs['Roughness'].default_value=.76;bs.inputs['Specular IOR Level'].default_value=.12
# Small continuous undercoat prevents scalp holes between transparent strands.
vs=[];fs=[];N=72;M=14
for j in range(M+1):
 for i in range(N):
  phi=2*math.pi*i/N;front=(1+math.cos(phi))/2
  stop=2.14-(1.02-.30*max(0,-math.sin(phi)))*front**2;theta=.018+(stop-.018)*j/M;d=direction(phi,theta);p=ray(skin,d)
  if p is None:p=center+d*.3
  vs.append(tuple(p+d*.005))
for j in range(M):
 for i in range(N):
  k=j*N+i;l=j*N+(i+1)%N;fs.append((k,l,l+N,k+N))
cap=mesh('HAIR_scalp_undercoat',vs,[tuple(reversed(f)) for f in fs],base)
cap['outward_normals_verified']=True
# Rebuild a continuous low-poly outer support from surface samples. Direct
# decimation of many overlapping HD locks tears the silhouette at intersections.
bvs=[];bfs=[];BN=96;BM=28
for i in range(BN):
 phi=-math.pi+2*math.pi*i/BN;front=max(0,math.cos(phi));end=2.58-.88*front**3;line=[]
 for j in range(49):
  theta=.04+(end-.04)*j/48;d=direction(phi,theta);p=ray(form,d)
  if p is None:
   if len(line)>12:break
   p=ray(skin,d)
   if p is None:continue
   p+=d*.014
  if abs(phi)<.95 and p.z<(.27+.12*(phi+.95)/1.9):break
  s=ray(skin,d);rad=(p-center).length
  if p.z>.08 and s is not None and s.z>.06:rad=max(rad,(s-center).length+.011)
  line.append(center+d*(rad-.002))
 if len(line)<2:raise RuntimeError('Insufficient bob surface samples')
 for j in range(BM+1):
  t=j/BM*(len(line)-1);k=min(len(line)-2,int(t));bvs.append(line[k].lerp(line[k+1],t-k))
for i in range(BN):
 for j in range(BM):
  a=i*(BM+1)+j;b=((i+1)%BN)*(BM+1)+j;bfs.append((a,b,b+1,a+1))
for _ in range(3):
 old=[p.copy() for p in bvs]
 for i in range(BN):
  for j in range(1,BM):
   k=i*(BM+1)+j;avg=(old[k-1]+old[k+1]+old[((i-1)%BN)*(BM+1)+j]+old[((i+1)%BN)*(BM+1)+j])/4
   bvs[k]=old[k].lerp(avg,.23)
bob=mesh('HAIR_bob_lowpoly_undercoat',[tuple(p) for p in bvs],[tuple(reversed(f)) for f in bfs],base)
bob['role']='Continuous low-poly bob silhouette supporting UV cards; sampled from fitted HD outer surface'
bob['source_triangle_count']=len(hd.data.polygons)
bob['outward_normals_verified']=True
rng=random.Random(2026100522);verts=[];faces=[];uvs=[];records=[]
def guide(phi_end,layer,index,bang=False):
 front=max(0,math.cos(phi_end))
 end=2.58-.88*front**3
 if bang:end=1.48+(.12 if phi_end<0 else -.05)
 points=[]
 for j in range(33):
  t=j/32;theta=.055+(end-.055)*t
  phi=phi_end+(.16)*(1-t)**2
  if bang or front>.7:phi=1.05*(1-t)**1.4+phi_end*(1-(1-t)**1.4)
  d=direction(phi,theta);p=ray(form,d)
  if p is None:
   if len(points)>10:break
   p=ray(skin,d)
   if p is None:continue
   p+=d*.017
  # Keep front fringe above the eye opening.
  if abs(phi_end)<.9 and p.z<(.25+.13*(phi_end+.9)/1.8):break
  s=ray(skin,d)
  radius=(p-center).length
  if s is not None and p.z>.08 and s.z>.06:radius=max(radius,(s-center).length+.010)
  p=center+d*(radius+.002+layer*.009)
  points.append(p)
 if len(points)<10:return
 # Smooth ray samples without shrinking them beneath the scalp.
 for _ in range(3):
  a=[p.copy() for p in points]
  for j in range(1,len(a)-1):points[j]=a[j]*.5+(a[j-1]+a[j+1])*.25
 width=(.047 if not bang else .039)*(1+rng.uniform(-.14,.14))
 start=len(verts);lengths=[0.]
 for a,b in zip(points,points[1:]):lengths.append(lengths[-1]+(b-a).length)
 total=lengths[-1];tile=index%6
 for j,p in enumerate(points):
  t=lengths[j]/total;tan=(points[min(j+1,len(points)-1)]-points[max(0,j-1)]).normalized();normal=(p-center).normalized();across=tan.cross(normal).normalized()
  if across.length<.1:across=Vector((0,1,0))
  taper=1-.60*max(0,(t-.60)/.40)**1.8
  for k in range(3):
   a=k/2;co=p+across*((a-.5)*width*taper)+normal*(.0018*(1-(2*a-1)**2))
   d=(co-center).normalized();s=ray(skin,d)
   if s is not None and co.z>.08 and s.z>.06 and (co-center).length<(s-center).length+.007:co=center+d*((s-center).length+.007)
   verts.append(tuple(co));uvs.append(((tile+a)/6,.9375-(.9375-.05)*t))
 for j in range(len(points)-1):
  for k in range(2):
   a=start+j*3+k;faces.append((a,a+1,a+4,a+3))
 cu=bpy.data.curves.new('Guide_%03d'%index,'CURVE');cu.dimensions='3D';sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
 for v,p in zip(sp.points,points):v.co=(*p,1)
 ob=bpy.data.objects.new('Hair_guide_%03d'%index,cu);guidescol.objects.link(ob);ob.hide_render=True;ob.hide_set(True)
 ob['ribbon_width']=width;ob['atlas_tile']=tile;ob['origin']='radial samples of fitted Tripo HD form, scalp clearance and relaxed continuity'
 records.append({'guide':ob.name,'samples':len(points),'width':width,'layer':layer,'bang':bang})
for layer in range(2):
 for i in range(108):
  phi=-math.pi+2*math.pi*(i+.4*layer)/108
  guide(phi,layer,len(records))
for i in range(38):guide(-.90+1.80*i/37,2,len(records),True)
hair=mesh('HAIR_UV_strand_cards',verts,faces,mat);uv=hair.data.uv_layers.new(name='StrandAtlas')
for f in hair.data.polygons:
 for li in f.loop_indices:uv.data[li].uv=uvs[hair.data.loops[li].vertex_index]
hair['construction']='Separate HD hair -> fitted form -> editable sampled curves -> tapered quad cards. Native Blender; no paid Hair Tool.'
hair['atlas']='Native Blender rendered original strand bundles; 6 tiles, RGBA'
hair['guide_count']=len(records);hair['full_hair_rig']=False
guidescol.hide_render=True
sc.cycles.samples=32;sc.render.resolution_x=900;sc.render.resolution_y=1000
cam=sc.camera
def view(pos,target=Vector((0,0,0)),scale=1.18):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
view((3,0,0))
bpy.ops.object.select_all(action='DESELECT');head.hide_set(False);head.select_set(True);bpy.context.view_layer.objects.active=head
blend=OUT/'explorer_b_integrated_face_haircards_open.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for n,p in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:
 view(p);sc.render.filepath=str(OUT/(n+'.png'));bpy.ops.render.render(write_still=True)
report={'guide_count':len(records),'cards_vertices':len(verts),'cards_quads':len(faces),'cards_triangles':len(faces)*2,'scalp_quads':len(cap.data.polygons),'bob_support_faces':len(bob.data.polygons),'dense_reference_triangles':len(hd.data.polygons),'atlas':str(im.filepath),'full_face_rig':False,'guides':records}
(OUT/'haircard-build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('HAIRCARD_SUMMARY',json.dumps({k:v for k,v in report.items() if k!='guides'}))
