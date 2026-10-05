"""Replace only the damaged oral patch, preserving the head/chin and existing eye rig."""
import bpy, math, json, hashlib, collections
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];OUT=R/'art/characters/explorer_b_face_rig_manual_v3';OUT.mkdir(exist_ok=True)
SRC=R/'art/characters/explorer_b_face_rig_manual_v2/explorer_manual_face_rig_v2.blend'
sha=hashlib.sha256(SRC.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1)
head=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
oldmesh=head.data;oldkeys=oldmesh.shape_keys.key_blocks
co=[p.co.copy() for p in oldkeys['jawOpen'].data];faces=[list(p.vertices) for p in oldmesh.polygons]
kept=[];removed=[]
for f in faces:
 c=sum((co[i] for i in f),Vector())/len(f)
 ((removed if (c.y/.145)**2+((c.z+.164)/.087)**2<1 and c.x>-.018 else kept)).append(f)
counts=collections.Counter(tuple(sorted((a,b))) for f in removed for a,b in zip(f,f[1:]+f[:1]))
adj=collections.defaultdict(list)
for (a,b),n in counts.items():
 if n==1:adj[a].append(b);adj[b].append(a)
todo=set(adj);components=[]
while todo:
 stack=[todo.pop()];c=[]
 while stack:
  a=stack.pop();c.append(a)
  for b in adj[a]:
   if b in todo:todo.remove(b);stack.append(b)
 components.append(c)
outer=max(components,key=len);assert len(outer)==84 and all(len(adj[i])==2 for i in outer)
loop=[min(outer)];prev=None
while True:
 nxt=next(n for n in adj[loop[-1]] if n!=prev)
 if nxt==loop[0]:break
 prev=loop[-1];loop.append(nxt)
assert len(loop)==len(outer)
# Counterclockwise yz boundary produces outward +X surface normals.
signed=sum(co[a].y*co[b].z-co[b].y*co[a].z for a,b in zip(loop,loop[1:]+loop[:1]))
if signed<0:loop.reverse()
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def mix(a,b,t):return a*(1-t)+b*t
import numpy as np
rawangles=np.unwrap([math.atan2((co[i].z+.164)/.087,co[i].y/.145) for i in loop])
angles=[]
for i in range(len(loop)):
 vals=[]
 for d in range(-4,5):
  j=i+d;cycle=math.floor(j/len(loop));vals.append(rawangles[j%len(loop)]+cycle*2*math.pi)
 angles.append(float(sum(vals)/len(vals)))
print('ANGLE_SPACING',min(angles[i+1]-angles[i] for i in range(len(angles)-1)), 'MODIFIERS',[(m.name,m.type) for m in head.modifiers],flush=True)
# Retain original unaffected coordinates. All new patch vertices have explicit closed/open states.
base=[p.copy() for p in co];opened=[p.copy() for p in co]
surface_faces=list(kept);mats=[0]*len(kept);ring_prev=loop
patch_indices=[];patch_meta={}
nr=14
def rim(theta,jaw):
 y=.092*math.cos(theta);sin=math.sin(theta)
 seam=-.153+.005*math.cos(theta)**2
 z=seam+(.00010+.035*jaw)*sin
 x=.326-4.5*y*y-.012*jaw*max(0,-sin)
 return Vector((x,y,z))
def point(i,t,jaw):
 theta=angles[i];outer=co[loop[i]];inner=rim(theta,jaw)
 # Smooth radial density and thin rounded lip volume near the opening.
 theta_o=math.atan2((outer.z+.164)/.087,outer.y/.145)
 clean_outer=Vector((outer.x,.145*math.cos(theta),-.164+.087*math.sin(theta)))
 q=clean_outer.lerp(inner,t)
 q+= (outer-clean_outer)*(1-t)**4
 # A smooth cheek/lip profile instead of propagating noisy boundary depths inward.
 depth=.326-4.5*q.y*q.y
 depth-=.64*max(0,-.173-q.z)
 depth+=.16*max(0,q.z+.130)
 q.x=depth+(outer.x-(.326-4.5*outer.y*outer.y-.64*max(0,-.173-outer.z)+.16*max(0,outer.z+.130)))*(1-t)**4
 sin=math.sin(theta)
 bump=.009 if sin>=0 else .008
 q.x+=bump*math.exp(-((t-.83)/.13)**2)*abs(sin)**.7
 # Soften the transition below the lower lip; no downward lobe.
 if sin<0:q.x+=.009*math.sin(math.pi*t)*(-sin)
 # Gentle paired philtrum columns above upper lip; shallow, not carved grooves.
 if sin>0:
  phil=math.exp(-((q.z+.105)/.024)**2)*(math.exp(-((q.y-.014)/.012)**2)+math.exp(-((q.y+.014)/.012)**2))
  q.x+=.0014*phil*math.sin(math.pi*t)
 return q
for j in range(1,nr+1):
 ring=[];t=j/nr
 for i in range(len(loop)):
  idx=len(base);ring.append(idx);base.append(point(i,t,0));opened.append(point(i,t,1));patch_indices.append(idx);patch_meta[idx]=(angles[i],t)
 for i in range(len(loop)):
  n=(i+1)%len(loop);surface_faces.append([ring_prev[i],ring_prev[n],ring[n],ring[i]]);mats.append(0)
 ring_prev=ring
# A separate-depth oral pouch, continuously joined to the inner lip rim.
for j in range(1,9):
 t=j/8;ring=[]
 for i,theta in enumerate(angles):
  vals=[]
  for jaw in (0,1):
   edge=rim(theta,jaw);depth=.21*t
   y=mix(edge.y,.082*math.cos(theta),t)
   # The cavity retains volume behind closed lips.
   z=mix(edge.z,-.153+.050*math.sin(theta),smooth(0,.65,t))
   vals.append(Vector((edge.x-depth,y,z)))
  idx=len(base);ring.append(idx);base.append(vals[0]);opened.append(vals[1]);patch_indices.append(idx);patch_meta[idx]=(theta,1+j/8)
 for i in range(len(loop)):
  n=(i+1)%len(loop);surface_faces.append([ring_prev[i],ring_prev[n],ring[n],ring[i]]);mats.append(1)
 ring_prev=ring
surface_faces.append(list(reversed(ring_prev)));mats.append(1)
# Drop removed-mouth orphan vertices and maintain a source-index mapping.
used=sorted({i for f in surface_faces for i in f});remap={old:new for new,old in enumerate(used)}
# Relax the shared junction across both the retained skin and new loops.
# This removes the radial folds created by the irregular original cut boundary.
import heapq
neighbors=collections.defaultdict(set)
for f in surface_faces:
 for a,b in zip(f,f[1:]+f[:1]):neighbors[a].add(b);neighbors[b].add(a)
dist={i:0. for i in loop};heap=[(0.,i) for i in loop];heapq.heapify(heap)
while heap:
 d,i=heapq.heappop(heap)
 if d!=dist[i] or d>.060:continue
 for j in neighbors[i]:
  nd=d+(base[i]-base[j]).length
  if nd<dist.get(j,1e9):dist[j]=nd;heapq.heappush(heap,(nd,j))
weights={i:(1-smooth(.005,.050,d))*smooth(-.265,-.245,base[i].z)*(1-smooth(-.090,-.073,base[i].z)) for i,d in dist.items() if d<.050}
for coords in (base,opened):
 for repeat in range(36):
  for factor in (.48,-.45):
   updates={}
   for i,w in weights.items():
    mean=sum((coords[j] for j in neighbors[i]),Vector())/len(neighbors[i])
    updates[i]=coords[i]+(mean-coords[i])*(factor*w)
   for i,p in updates.items():coords[i]=p
newmesh=bpy.data.meshes.new('Face_with_local_lip_loops_v3')
newmesh.from_pydata([base[i] for i in used],[],[[remap[i] for i in f] for f in surface_faces]);newmesh.update()
skin=oldmesh.materials[0];newmesh.materials.append(skin)
def material(name,color,rough=.5):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough
 return m
mucosa=material('Mouth mucosa muted warm rose',(.31,.085,.08),.5);newmesh.materials.append(mucosa)
for p,mi in zip(newmesh.polygons,mats):p.material_index=mi;p.use_smooth=True
# All original upper-face expression offsets survive. Mouth expressions use the new lip loops.
old_deltas={k.name:[v.co-oldkeys['Basis'].data[i].co for i,v in enumerate(k.data)] for k in oldkeys if k.name not in ('Basis','jawOpen')}
head.data=newmesh
for vg in list(head.vertex_groups):head.vertex_groups.remove(vg)
vg=head.vertex_groups.new(name='head');vg.add(list(range(len(used))),1,'REPLACE')
head.shape_key_add(name='Basis')
def driven_key(name,coords,prop):
 k=head.shape_key_add(name=name)
 for p,c in zip(k.data,coords):p.co=c
 d=k.driver_add('value').driver;d.expression='v';v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='["'+prop+'"]'
 return k
driven_key('jawOpen',[opened[i] for i in used],'jaw_open')
for name in ('smile','frown','pucker','brow_up','brow_frown'):
 target=[]
 for idx in used:
  p=base[idx].copy()
  if idx<len(co):
   if name.startswith('brow'):p+=old_deltas[name][idx]
   elif name=='smile' or name=='frown':
    w=math.exp(-((abs(p.y)-.105)/.06)**2-((p.z+.15)/.055)**2)*smooth(.15,.26,p.x)
    p.z+=(.008 if name=='smile' else -.008)*w
  else:
   theta,t=patch_meta[idx];y=p.y
   if name=='smile':p.z+=.008*(abs(y)/.10)**2*min(1,t*2);p.y*=1+.035*min(1,t*2)
   elif name=='frown':p.z-=.008*(abs(y)/.10)**2*min(1,t*2)
   elif name=='pucker':p.y*=1-.15*min(1,t);p.x+=.012*min(1,t)
  if idx<len(co) and co[idx].z<=-.265:p=base[idx].copy()
  target.append(p)
 driven_key(name,target,name)
# Paint oral lining and gums, preserve ivory crowns.
gum=material('Gum muted coral',(.38,.115,.105),.5);gum_counts={}
for name,upper in [('02_Upper_dental_candidate',True),('03_Lower_dental_candidate',False)]:
 obj=bpy.data.objects[name];obj.data.materials.append(gum);gi=len(obj.data.materials)-1;n=0
 for p in obj.data.polygons:
  if (upper and p.center.z>-.103) or (not upper and p.center.z<-.218):p.material_index=gi;n+=1
 gum_counts[name]=n
tongue=bpy.data.objects['06_Tongue_candidate'];tongue.data.materials.clear();tongue.data.materials.append(material('Tongue soft rose',(.40,.135,.13),.5))
for p in tongue.data.polygons:p.material_index=0
sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.cycles.samples=24
cam=sc.camera
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
camera((.10,0,0),(4,-.35,.12),1.30)
for name,frame in [('neutral',1),('jaw-open',98),('smile',124)]:
 sc.frame_set(frame);rig.update_tag();bpy.context.view_layer.update();sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
sc.frame_set(1);camera((.2,0,-.15),(4,0,0),.52)
sc.render.filepath=str(OUT/'mouth-closeup.png');bpy.ops.render.render(write_still=True)
camera((.13,0,-.12),(3,-3,.02),.85)
sc.render.filepath=str(OUT/'mouth-angle.png');bpy.ops.render.render(write_still=True)
sc.frame_set(98);camera((.2,0,-.15),(4,0,0),.52)
sc.render.filepath=str(OUT/'mouth-open-closeup.png');bpy.ops.render.render(write_still=True)
camera((.1,0,0),(4,-.35,.12),1.30);sc.frame_set(1)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.1,0,0);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.65;s.region_3d.view_perspective='ORTHO';s.shading.color_type='MATERIAL'
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,
 'removed_old_oral_faces':len(removed),'outer_boundary_vertices':len(loop),'new_lip_radial_rings':nr,
 'oral_material_faces':mats.count(1),'gum_faces':gum_counts,
 'chin_anchor_max_error':max((base[i]-co[i]).length for i in used if i<len(co) and co[i].z<=-.265),
 'method':'Localized oral patch with shared original boundary, thin lip volumes, volumetric mucosa pouch, closed/open morphs.',
 'source_indices_for_retained_vertices':{str(remap[i]):i for i in used if i<len(co)}}
assert report['source_unchanged'] and report['chin_anchor_max_error']<1e-7
sc['RIG_STATUS']='V3 local oral retopology, closed mouth rest, thin lower lip, soft philtrum, mucosa/gum materials.'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_manual_face_rig_v3.blend'))
(OUT/'mouth-refinement-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('MOUTH_PATCH_SAVED',len(used),len(surface_faces),flush=True)
