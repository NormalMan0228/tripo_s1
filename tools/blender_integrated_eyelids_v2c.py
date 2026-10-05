"""Replace the eye-border patches with welded eyelid loops, restore visible lashes."""
import bpy,math,json,hashlib,collections
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];SRC=R/'art/characters/explorer_b_face_rig_manual_v2b/explorer_profile_eye_v2b.blend'
OUT=R/'art/characters/explorer_b_face_rig_manual_v2c';OUT.mkdir(exist_ok=True)
sha=hashlib.sha256(SRC.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(SRC))
sc=bpy.context.scene;sc.frame_set(1);rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];head=bpy.data.objects['01_Face_skin_neck']
old=head.data;faces=[list(p.vertices) for p in old.polygons];old_shapes={k.name:[v.co.copy() for v in k.data] for k in old.shape_keys.key_blocks};base=old_shapes['Basis']
topo=json.loads((R/'art/characters/explorer_b_face_rig_manual_v1/source-topology.json').read_text())
patches={};remove=set()
for hole in topo['objects'][0]['boundary_components']:
 if hole['n'] not in (32,33):continue
 side='L' if hole['center'][1]>0 else 'R';verts=set(hole['ids']);selected=set()
 sign=1 if side=='L' else -1
 for step in range(3):
  selected.update(i for i,f in enumerate(faces) if any(v in verts for v in f) and all(base[v].y*sign>.018 for v in f));verts.update(v for i in selected for v in faces[i])
 count=collections.Counter(tuple(sorted((a,b))) for i in selected for a,b in zip(faces[i],faces[i][1:]+faces[i][:1]));adj=collections.defaultdict(list)
 for (a,b),n in count.items():
  if n==1:adj[a].append(b);adj[b].append(a)
 todo=set(adj);components=[]
 while todo:
  stack=[todo.pop()];comp=[]
  while stack:
   a=stack.pop();comp.append(a)
   for b in adj[a]:
    if b in todo:todo.remove(b);stack.append(b)
  components.append(comp)
 outer=next(c for c in components if not(set(c)&set(hole['ids'])));assert all(len(adj[i])==2 for i in outer)
 loop=[min(outer)];prev=None
 while True:
  nxt=next(v for v in adj[loop[-1]] if v!=prev)
  if nxt==loop[0]:break
  prev=loop[-1];loop.append(nxt)
 if sum(base[a].y*base[b].z-base[b].y*base[a].z for a,b in zip(loop,loop[1:]+loop[:1]))<0:loop.reverse()
 patches[side]={'loop':loop,'removed':len(selected)};remove.update(selected)
allbase=[p.copy() for p in base];newfaces=[f for i,f in enumerate(faces) if i not in remove];info={};patch_samples={}
def edge(side,a,blink):
 sign=1 if side=='L' else -1;c=Vector((.146,.149*sign,.061));r=Vector((.095,.083,.085));u=math.cos(a);s=math.sin(a)
 y=c.y+.077*u;seam=c.z-.004+.004*u*u
 z=(c.z+(.035 if s>=0 else .040)*s+.003*u*sign)*(1-blink)+seam*blink
 x=c.x+r.x*math.sqrt(max(0,1-((y-c.y)/r.y)**2-((z-c.z)/r.z)**2))+.002
 return Vector((x,y,z))
for side,patch in patches.items():
 loop=patch['loop'];n=len(loop);cy=.149*(1 if side=='L' else -1)
 raw=np.unwrap([math.atan2((base[i].z-.061)/.1,(base[i].y-cy)/.1) for i in loop])
 angles=[]
 for i in range(n):angles.append(float(sum(raw[(i+d)%n]+math.floor((i+d)/n)*2*math.pi for d in range(-2,3))/5))
 assert min(angles[i+1]-angles[i] for i in range(n-1))>0
 def point(i,t,blink):
  outer=base[loop[i]];inner=edge(side,angles[i],blink);p=outer.lerp(inner,t)
  c=Vector((.146,cy,.061));inside=1-((p.y-c.y)/.083)**2-((p.z-c.z)/.085)**2
  if inside>0 and t>0:p.x=max(p.x,c.x+.095*math.sqrt(inside)+.002)
  return p
 prev=loop;patch_samples[side]={k:[] for k in range(5)}
 for j in range(1,11):
  t=j/10;ring=[]
  for i in range(n):
   idx=len(allbase);ring.append(idx);allbase.append(point(i,t,0));info[idx]=(side,loop[i],t)
   for k in range(5):patch_samples[side][k].append((idx,point(i,t,k/4)))
  for i in range(n):v=(i+1)%n;newfaces.append([prev[i],prev[v],ring[v],ring[i]])
  prev=ring
 patch['inner']=ring
# Close the source's four-vertex defect just below the right eye where it joins the patch.
source_edges=collections.Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
for hole in topo['objects'][0]['boundary_components']:
 if hole['n']==4 and abs(hole['center'][1])<.24 and 0<hole['center'][2]<.03:
  ids=set(hole['ids']);ha=collections.defaultdict(list)
  for (a,b),n in source_edges.items():
   if n==1 and a in ids and b in ids:ha[a].append(b);ha[b].append(a)
  loop=[min(ids)];prev=None
  while len(loop)<len(ids):
   nxt=next(i for i in ha[loop[-1]] if i!=prev);prev=loop[-1];loop.append(nxt)
  newfaces.append(loop)
used=sorted({i for f in newfaces for i in f});remap={i:j for j,i in enumerate(used)}
import heapq
neighbors=collections.defaultdict(set)
for f in newfaces:
 for a,b in zip(f,f[1:]+f[:1]):neighbors[a].add(b);neighbors[b].add(a)
seeds={i for p in patches.values() for i in p['loop']};distance={i:0. for i in seeds};queue=[(0.,i) for i in seeds];heapq.heapify(queue)
while queue:
 d,i=heapq.heappop(queue)
 if d!=distance[i] or d>.07:continue
 for j in neighbors[i]:
  nd=d+(allbase[i]-allbase[j]).length
  if nd<distance.get(j,1e9):distance[j]=nd;heapq.heappush(queue,(nd,j))
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
weights={i:(1-smooth(.012,.065,d)) for i,d in distance.items() if d<.065 and allbase[i].z>-.06}
for i in list(weights):
 if i in info:weights[i]*=1-smooth(.55,.80,info[i][2])
original_base=[p.copy() for p in allbase]
for repeat in range(48):
 for factor in (.48,-.42):
  updates={i:allbase[i]+(sum((allbase[j] for j in neighbors[i]),Vector())/len(neighbors[i])-allbase[i])*(factor*w) for i,w in weights.items()}
  for i,p in updates.items():allbase[i]=p
def outside_globe(p):
 q=p.copy();cy=.149*(1 if p.y>0 else -1)
 inside=1-((p.y-cy)/.083)**2-((p.z-.061)/.085)**2
 if inside>0 and p.x>.146:q.x=max(q.x,.146+.095*math.sqrt(inside)+.0035)
 return q
for i in set(weights)|set(info):allbase[i]=outside_globe(allbase[i])
correction={i:allbase[i]-original_base[i] for i in set(weights)|set(info)}
for side in patch_samples:
 for k in patch_samples[side]:patch_samples[side][k]=[(i,outside_globe(p+correction.get(i,Vector()))) for i,p in patch_samples[side][k]]
mesh=bpy.data.meshes.new('Face_skin_with_welded_eyelids');mesh.from_pydata([allbase[i] for i in used],[],[[remap[i] for i in f] for f in newfaces]);mesh.materials.append(old.materials[0]);mesh.update()
import bmesh
bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
for p in mesh.polygons:p.use_smooth=True
head.data=mesh
for vg in list(head.vertex_groups):head.vertex_groups.remove(vg)
vg=head.vertex_groups.new(name='head');vg.add(list(range(len(used))),1,'REPLACE')
head.shape_key_add(name='Basis')
def makekey(obj,name,coords,prop,expression='v'):
 k=obj.shape_key_add(name=name)
 for v,p in zip(k.data,coords):v.co=p
 d=k.driver_add('value').driver;d.expression=expression;var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='["'+prop+'"]'
for name,coords in old_shapes.items():
 if name=='Basis':continue
 result=[]
 for idx in used:
  if idx<len(base):result.append(coords[idx]+correction.get(idx,Vector()))
  else:
   side,outer,t=info[idx];result.append(allbase[idx]+(coords[outer]-base[outer])*(1-t)**2)
 makekey(head,name,result,'jaw_open' if name=='jawOpen' else name)
for side in patches:
 for k in range(1,5):
  coords=[allbase[i].copy() for i in used]
  for idx,p in patch_samples[side][k]:coords[remap[idx]]=p
  makekey(head,'IntegratedBlink_'+side+'_'+str(k*25),coords,'blink_'+side,'max(0,1-abs(4*v-'+str(k)+'))')
# Delete only redundant generated lid surfaces and last revision's thin lashes.
for side in ('L','R'):
 obj=bpy.data.objects.get('Eyelids.'+side)
 if obj:bpy.data.objects.remove(obj,do_unlink=True)
 lname='08_Upper_lash_candidate_posY' if side=='L' else '07_Upper_lash_candidate_negY'
 oldlash=bpy.data.objects[lname];mat=oldlash.data.materials[0];bpy.data.objects.remove(oldlash,do_unlink=True)
 def lashcoords(blink):
  pts=[]
  for j in range(65):
   a=math.pi*j/64;p=edge(side,a,blink)+Vector((.003,0,.002))
   width=.0007+.0052*math.sin(a)**.55
   for xx,zz in [(1,0),(0,1),(-1,0),(0,-1)]:pts.append(p+Vector((.0018*xx,0,width*zz)))
  # Short tapered outer-corner lash clusters, attached to the upper lash band.
  angles=[.17,.31,.46] if side=='L' else [math.pi-.17,math.pi-.31,math.pi-.46]
  sign=1 if side=='L' else -1
  for a in angles:
   p=edge(side,a,blink)+Vector((.0035,0,.004));tip=p+Vector((.009,sign*.005,.010*(1-.55*blink)))
   pts.extend([p+Vector((0,-.002,0)),p+Vector((.001,0,.003)),p+Vector((0,.002,0)),tip])
  return pts
 lf=[]
 for j in range(64):
  for k in range(4):lf.append((j*4+k,(j+1)*4+k,(j+1)*4+(k+1)%4,j*4+(k+1)%4))
 lf.extend([(3,2,1,0),(256,257,258,259)])
 for j in range(3):
  a=260+j*4;lf.extend([(a,a+1,a+3),(a+1,a+2,a+3),(a+2,a,a+3),(a+2,a+1,a)])
 m=bpy.data.meshes.new(lname+'_visible');m.from_pydata(lashcoords(0),[],lf);m.materials.append(mat)
 o=bpy.data.objects.new(lname,m);sc.collection.objects.link(o)
 for p in m.polygons:p.use_smooth=True
 v=o.vertex_groups.new(name='head');v.add(list(range(len(m.vertices))),1,'REPLACE');mod=o.modifiers.new('Face rig','ARMATURE');mod.object=rig;o.shape_key_add(name='Basis')
 for k in range(1,5):makekey(o,'Blink_'+str(k*25),lashcoords(k/4),'blink_'+side,'max(0,1-abs(4*v-'+str(k)+'))')
# True shared-vertex stitching check, rather than merely joining separate objects.
counts=collections.Counter(tuple(sorted((a,b))) for f in newfaces for a,b in zip(f,f[1:]+f[:1]))
welded={side:all(counts[tuple(sorted((a,b)))]==2 for a,b in zip(p['loop'],p['loop'][1:]+p['loop'][:1])) for side,p in patches.items()}
for s,p in patches.items():
 print('WELD_DIAGNOSTIC',s,len(p['loop']),[(a,b,counts[tuple(sorted((a,b)))]) for a,b in zip(p['loop'],p['loop'][1:]+p['loop'][:1]) if counts[tuple(sorted((a,b)))]!=2],flush=True)
assert all(welded.values()) and not any(bpy.data.objects.get('Eyelids.'+s) for s in ('L','R'))
cam=sc.camera;sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.cycles.samples=20
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name,hidehair=False):
 hidden=[]
 if hidehair:
  for o in sc.objects:
   if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
 sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 for o in hidden:o.hide_render=False
sc.frame_set(2);sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
camera((.18,-.149,.07),(1.3,-4,.08),.38);render('eye-side',True)
camera((.18,-.149,.07),(4,-1.2,0),.38);render('eye-front',True)
camera((.1,0,0),(4,-.35,.12),1.3);render('front')
sc.frame_set(18);render('blink');sc.frame_set(15);render('half-blink');sc.frame_set(1)
camera((.1,0,0),(3,-3,.1),1.25);render('angle');camera((.1,0,0),(4,-.35,.12),1.3)
sc['RIG_STATUS']='V2c: welded integrated eyelid patches; visible upper lashes with corner tips.'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.1,0,.02);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.45;s.region_3d.view_perspective='ORTHO'
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,'shared_boundary_edges':{s:len(p['loop']) for s,p in patches.items()},'all_shared_edges_have_two_faces':welded,'separate_eyelid_objects':0,'removed_original_eye_border_faces':len(remove),'head_vertices':len(mesh.vertices),'head_faces':len(mesh.polygons),'lashes':'Visible upper lash band and three short outer-corner clusters per eye','retained_source_mapping':{str(remap[i]):i for i in used if i<len(base)}}
assert report['source_unchanged']
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_integrated_eyes_v2c.blend'))
(OUT/'integrated-eye-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('INTEGRATED_EYES_SAVED',welded,flush=True)
