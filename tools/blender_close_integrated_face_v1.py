"""Closed-mouth rest while preserving the approved original open Tripo pose."""
import bpy,bmesh,json,math,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1';OUT=O/'assembly'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_b_integrated_face_haircards_open.blend'));sc=bpy.context.scene;head=bpy.data.objects['FACE_Tripo_integrated_0']
bm=bmesh.new();bm.from_mesh(head.data);bm.verts.ensure_lookup_table();seen=set();groups=[]
for v in bm.verts:
 if v.index in seen:continue
 seen.add(v.index);stack=[v];g=[]
 while stack:
  v=stack.pop();g.append(v.index)
  for e in v.link_edges:
   a=e.other_vert(v)
   if a.index not in seen:seen.add(a.index);stack.append(a)
 groups.append(g)
groups.sort(key=len,reverse=True);skin_ids=set(groups[0]);bm.free()
opened=[v.co.copy() for v in head.data.vertices];head.data.calc_loop_triangles()
surface=BVHTree.FromPolygons(opened,[tuple(t.vertices) for t in head.data.loop_triangles if all(i in skin_ids for i in t.vertices)],all_triangles=True)
def sx(y,z):
 p,*_=surface.ray_cast(Vector((1,y,z)),Vector((-1,0,0)));return p.x if p else -.4
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
ys=np.linspace(-.093,.093,187);upper=[];lower=[];topx=[];botx=[]
for y in ys:
 xbot=max(sx(y,z) for z in np.linspace(-.16,-.105,111));xtop=max(sx(y,z) for z in np.linspace(-.064,-.035,59))
 cut=min(xbot,xtop)-.017
 zz=np.linspace(-.145,-.054,365);blocks=[];gap=[]
 for z in zz:
  if sx(y,z)<cut:gap.append(z)
  elif gap:blocks.append(gap);gap=[]
 if gap:blocks.append(gap)
 # Select the mouth cavity interval, not an unrelated recessed chin sample.
 valid=[g for g in blocks if min(g)<-.069 and max(g)>-.112]
 gap=min(valid,key=lambda g:min(abs(z+.087) for z in g)) if valid else []
 if gap:a=max(gap)+.00025;b=min(gap)-.00025
 else:a=b=-.069
 upper.append(a);lower.append(b);topx.append(sx(y,a));botx.append(sx(y,b))
for arr in [upper,lower,topx,botx]:
 for _ in range(8):
  old=arr.copy()
  for i in range(1,len(arr)-1):arr[i]=old[i]*.5+(old[i-1]+old[i+1])*.25
def profile(a,y):return float(np.interp(y,ys,a))
closed=[]
for i,c in enumerate(opened):
 x,y,z=c;q=c.copy()
 if i in skin_ids and abs(y)<.105 and -.275<z<-.025:
  a=profile(upper,y);b=profile(lower,y);gap=max(0,a-b);seam=a-.32*gap
  edge=1-smooth(.089,.105,abs(y));depth=smooth(.06,.22,x)
  if z<(a+b)/2:
   w=smooth(-.26,-.148,z)*depth*edge
   q.z+=(seam-b+.0001)*w
   shift=max(0,min(.028,profile(topx,y)-.003-profile(botx,y))) if gap>.001 else 0
   q.x+=shift*math.exp(-((z-b)/.028)**4)*depth*edge
  else:
   w=(1-smooth(a+.010,a+.040,z))*depth*edge
   q.z+=(seam-a-.0001)*w
   q.x-=.004*w
 elif i not in skin_ids and z<-.085:
  pivot=Vector((-.09,0,-.03));q=pivot+Matrix.Rotation(-.072,3,'Y')@(c-pivot)
 closed.append(q)
# Relax displacement only; preserve original skin detail, UVs, lids and lashes.
adj=[set() for _ in opened]
for e in head.data.edges:
 a,b=e.vertices;adj[a].add(b);adj[b].add(a)
delta=[b-a for a,b in zip(opened,closed)]
for _ in range(5):
 old=[p.copy() for p in delta]
 for i,c in enumerate(opened):
  if i not in skin_ids or abs(c.y)>.11 or c.x<.14 or not -.255<c.z<-.032 or not adj[i]:continue
  a=profile(upper,c.y);b=profile(lower,c.y)
  if min(abs(c.z-a),abs(c.z-b))<.007:continue
  avg=sum((old[k] for k in adj[i]),Vector())/len(adj[i]);delta[i]=old[i].lerp(avg,.4)
closed=[a+b for a,b in zip(opened,delta)]
for v,c in zip(head.data.vertices,closed):v.co=c
head.shape_key_add(name='Basis_closed_rest');key=head.shape_key_add(name='Mouth_open_Tripo_original')
for v,c in zip(key.data,opened):v.co=c
ctrl=bpy.data.objects.new('FACE_CONTROLS',None);sc.collection.children['01_Integrated_face'].objects.link(ctrl);ctrl.location=(.45,0,-.2);ctrl.empty_display_size=.03
ctrl['mouth_open']=0.;ctrl.id_properties_ui('mouth_open').update(min=0,max=1,description='0 closed rest; 1 original generated oral inspection pose. Full facial rig pending.')
dr=key.driver_add('value').driver;dr.expression='op';var=dr.variables.new();var.name='op';var.type='SINGLE_PROP';var.targets[0].id=ctrl;var.targets[0].data_path='["mouth_open"]'
head['mouth_rest']='Closed rest with unchanged original generated open pose as a driven shape key'
for im in bpy.data.images:
 if im.users==0:bpy.data.images.remove(im)
sc.frame_set(1);bpy.context.view_layer.update();cam=sc.camera
def view(pos,target=Vector((0,0,0)),scale=1.18):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
view((3,0,0))
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.region_3d.view_location=(0,0,.08);sp.region_3d.view_distance=1.5;sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_perspective='ORTHO';sp.shading.type='MATERIAL';sp.overlay.show_extras=False
notes=bpy.data.texts.get('READ_ME');notes.clear();notes.write('Approved Tripo P2 face: eyelids, eyebrows and eyelashes included. Separate four-view HD hair is preserved hidden. Visible hair: sampled editable guides, UV strand cards and scalp undercoat. Native Blender albedo atlas is packed. FACE_CONTROLS mouth_open 0 closed / 1 original Tripo open mouth. Static prototype; no blink/gaze/face rig yet.\n')
blend=OUT/'explorer_b_integrated_face_haircards_v1.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for n,pos in [('rest_front',(3,0,0)),('rest_angle',(3,-2,0)),('rest_side',(0,-3,0))]:
 view(pos);sc.render.filepath=str(OUT/(n+'.png'));bpy.ops.render.render(write_still=True)
for val,n in [(0.,'mouth_closed'),(1.,'mouth_open')]:
 ctrl['mouth_open']=val;ctrl.update_tag();sc.frame_set(1+int(val*100));bpy.context.view_layer.update();view((3,-.1,0),Vector((.23,0,-.10)),.34);sc.render.filepath=str(OUT/(n+'.png'));bpy.ops.render.render(write_still=True)
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();view((3,0,0));bpy.ops.wm.save_as_mainfile(filepath=str(blend))
(OUT/'mouth-rest-report.json').write_text(json.dumps({'original_open_pose_preserved':True,'shape_key':key.name,'default':0,'control':'FACE_CONTROLS["mouth_open"]','center_original_aperture':profile(upper,0)-profile(lower,0),'skin_vertices':len(skin_ids),'all_vertices':len(opened),'unchanged_eye_lid_lash_vertices':sum(c.z>.05 and c==p for c,p in zip(opened,closed)),'aperture_profiles':{'y':ys.tolist(),'upper':upper,'lower':lower},'full_face_rig':False},indent=2),encoding='utf-8')
print('REST_SAVED',str(blend))
