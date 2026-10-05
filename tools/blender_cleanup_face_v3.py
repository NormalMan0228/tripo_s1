"""Local, reversible face cleanup; atlas and original open pose remain intact."""
import bpy,bmesh,json,math,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly'
bpy.ops.wm.open_mainfile(filepath=str(O/'component_probe.blend'));sc=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0
parts=sorted([a for a in sc.objects if a.name.startswith('PART_')],key=lambda a:int(a.name.split('_')[1]));head=parts[0];head.name='FACE_skin_eyelids_lashes'
for a in parts:a.hide_render=False;a.hide_set(False)
def mat(name,color,rough=.45):
 m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=rough;b.inputs['Specular IOR Level'].default_value=.25;return m
enamel=mat('Teeth_clean_ivory_enamel',(.83,.79,.70),.29);gum=mat('Gums_warm_pink',(.26,.055,.065),.48);tongue=mat('Tongue_mucosal_pink',(.35,.075,.095),.43);lash=mat('Lashes_clean_dark_brown',(.010,.004,.002),.55)
for i,a in enumerate(parts):
 if i in (1,2,5) or 8<=i<=29:
  a.data.materials.clear();a.data.materials.append(gum if i in (1,2) else tongue if i==5 else enamel);a.name=('GUMS_lower' if i==1 else 'GUMS_upper' if i==2 else 'TONGUE' if i==5 else 'TOOTH_%02d'%i)
 if i in (6,7):a.name='BROW_'+('R' if i==6 else 'L')
for i,patch_i,side in [(3,31,'L'),(4,30,'R')]:
 eye=parts[i];patch=parts[patch_i];bpy.ops.object.select_all(action='DESELECT');eye.select_set(True);patch.select_set(True);bpy.context.view_layer.objects.active=eye;bpy.ops.object.join();eye.name='EYEBALL_'+side
 center=Vector([(min(v.co[j] for v in eye.data.vertices)+max(v.co[j] for v in eye.data.vertices))/2 for j in range(3)])
 eye.data.transform(Matrix.Translation(-center));eye.location=center;eye['rotation_pivot']='center of globe; catchlight patch joined, UV retained';eye['separate_from_face']=True
 # Smooth the original sphere without touching the facial eye opening.
 mod=eye.modifiers.new('Smooth_globe','SUBSURF');mod.levels=1;mod.render_levels=1
# Correct the actual lash ribbon faces, using the existing atlas to locate them.
base=head.data.materials[0];image=next(n.image for n in base.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'Color' in n.image.name)
w,h=image.size;pix=np.array(image.pixels[:],dtype=np.float32).reshape(h,w,4);uv=head.data.uv_layers.active.data
seeds=set();centers=[];sample=[]
for p in head.data.polygons:
 c=p.center.copy();centers.append(c);cols=[]
 for li in p.loop_indices:
  u,v=uv[li].uv;cols.append(pix[min(h-1,max(0,int(v*h))),min(w-1,max(0,int(u*w))),:3])
 rgb=np.mean(cols,axis=0);sample.append(rgb.tolist())
 if c.x>.11 and .060<abs(c.y)<.275 and .105<c.z<.207 and max(rgb)<.20 and np.mean(rgb)<.11:seeds.add(p.index)
adj=[set() for p in head.data.polygons];edgefaces={}
for p in head.data.polygons:
 for k in p.edge_keys:edgefaces.setdefault(k,[]).append(p.index)
for ids in edgefaces.values():
 for a in ids:adj[a].update(ids)
# One narrow boundary ring removes peach contamination along lash edges.
mask=set(seeds)
for i in seeds:
 for j in adj[i]:
  c=centers[j]
  if c.x>.13 and .066<abs(c.y)<.274 and .107<c.z<.205 and (c-centers[i]).length<.0045:mask.add(j)
head.data.materials.append(lash);lash_index=len(head.data.materials)-1
for p in head.data.polygons:
 if p.index in mask:p.material_index=lash_index
# Mouth gap from the SKIN surface; teeth and tongue cannot contaminate rays.
opened=[v.co.copy() for v in head.data.vertices];head.data.calc_loop_triangles();surface=BVHTree.FromPolygons(opened,[t.vertices for t in head.data.loop_triangles],all_triangles=True)
def sx(y,z):
 p,*_=surface.ray_cast(Vector((1,y,z)),Vector((-1,0,0)));return p.x if p else -.4
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
ys=np.linspace(-.107,.107,215);upper=[];lower=[];topx=[];botx=[]
for y in ys:
 cut=min(max(sx(y,z) for z in np.linspace(-.145,-.12,51)),max(sx(y,z) for z in np.linspace(-.059,-.035,49)))-.017
 zz=np.linspace(-.14,-.054,345);blocks=[];gap=[]
 for z in zz:
  if sx(y,z)<cut:gap.append(z)
  elif gap:blocks.append(gap);gap=[]
 if gap:blocks.append(gap)
 valid=[g for g in blocks if min(g)<-.070 and max(g)>-.11];gap=min(valid,key=lambda g:min(abs(z+.085) for z in g)) if valid else []
 if gap:a=max(gap)+.00025;b=min(gap)-.00025
 else:a=b=-.070
 upper.append(a);lower.append(b);topx.append(sx(y,a));botx.append(sx(y,b))
for arr in [upper,lower,topx,botx]:
 for _ in range(8):
  old=arr.copy()
  for i in range(1,len(arr)-1):arr[i]=old[i]*.5+(old[i-1]+old[i+1])*.25
def profile(a,y):return float(np.interp(y,ys,a))
closed=[]
for c in opened:
 x,y,z=c;q=c.copy()
 if abs(y)<.118 and -.255<z<-.028:
  a=profile(upper,y);b=profile(lower,y);gap=max(0,a-b);seam=a-.32*gap
  edge=1-smooth(.102,.118,abs(y));depth=smooth(.08,.24,x)
  if z<(a+b)/2:
   weight=smooth(-.235,-.146,z)*depth*edge;q.z+=(seam-b+.00008)*weight
   shift=max(0,min(.025,profile(topx,y)-.003-profile(botx,y))) if gap>.001 else 0;q.x+=shift*math.exp(-((z-b)/.028)**4)*depth*edge
  else:
   weight=(1-smooth(a+.010,a+.040,z))*depth*edge;q.z+=(seam-a-.00008)*weight;q.x-=.004*weight
  # Gentle upturned commissures, broad cheek falloff; closed midline retained.
  q.z+=.006*math.exp(-((abs(y)-.108)/.029)**2-((z+.076)/.037)**2)*depth
 closed.append(q)
adjv=[set() for _ in opened]
for e in head.data.edges:a,b=e.vertices;adjv[a].add(b);adjv[b].add(a)
delta=[b-a for a,b in zip(opened,closed)]
for _ in range(5):
 old=[p.copy() for p in delta]
 for i,c in enumerate(opened):
  if abs(c.y)>.125 or c.x<.14 or not -.24<c.z<-.032 or not adjv[i]:continue
  a=profile(upper,c.y);b=profile(lower,c.y)
  if min(abs(c.z-a),abs(c.z-b))<.007:continue
  avg=sum((old[k] for k in adjv[i]),Vector())/len(adjv[i]);delta[i]=old[i].lerp(avg,.4)
ctrl=bpy.data.objects.new('FACE_CONTROLS',None);head.users_collection[0].objects.link(ctrl);ctrl.location=(.45,0,-.2);ctrl.empty_display_size=.025;ctrl['mouth_open']=0.;ctrl.id_properties_ui('mouth_open').update(min=0,max=1,description='0: closed gentle smile. 1: exact original open-mouth geometry. Full facial rig pending.')
def morph(a,original,rest):
 for v,c in zip(a.data.vertices,rest):v.co=c
 a.shape_key_add(name='Basis_closed_smile');key=a.shape_key_add(name='Mouth_open_original')
 for v,c in zip(key.data,original):v.co=c
 dr=key.driver_add('value').driver;dr.expression='op';var=dr.variables.new();var.name='op';var.type='SINGLE_PROP';var.targets[0].id=ctrl;var.targets[0].data_path='["mouth_open"]'
morph(head,opened,[a+b for a,b in zip(opened,delta)])
for i in [1,5,9,17,19,20,21,23,24,26,27,28,29]:
 a=parts[i];original=[v.co.copy() for v in a.data.vertices];pivot=Vector((-.09,0,-.03));rest=[pivot+Matrix.Rotation(-.09,3,'Y')@(c-pivot) for c in original];morph(a,original,rest)
sc.cycles.samples=24;cam=sc.camera;sc.render.resolution_x=900;sc.render.resolution_y=1000
def view(pos,target=Vector((0,0,.03)),scale=1.14):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(n,pos,target=Vector((0,0,.03)),scale=1.14):
 view(pos,target,scale);sc.render.filepath=str(O/(n+'.png'));bpy.ops.render.render(write_still=True)
ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();view((3,0,0))
notes=bpy.data.texts.get('READ_ME');notes.clear();notes.write('New hair generated separately. Face edited locally: separated EYEBALL_L/R with central pivots, dark lash ribbon material repair, ivory teeth / pink gums / tongue. Default closed gentle smile. FACE_CONTROLS mouth_open=1 recovers original open geometry. Original hidden source retained. No full facial rig yet.\n')
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   sp=a.spaces.active;sp.shading.type='MATERIAL';sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_location=(0,0,.05);sp.region_3d.view_distance=1.5;sp.region_3d.view_perspective='ORTHO';sp.overlay.show_extras=False
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
bpy.ops.wm.save_as_mainfile(filepath=str(O/'face_local_cleanup.blend'))
render('face_rest_front',(3,0,0));render('face_rest_side',(0,-3,0));render('mouth_closed',(3,-.1,0),Vector((.26,0,-.085)),.34);render('eyes_clean',(3,0,0),Vector((.17,0,.15)),.55)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();render('mouth_open',(3,-.6,0),Vector((.23,0,-.085)),.38)
(O/'face-cleanup-report.json').write_text(json.dumps({'eyes_separate':True,'eyes':['EYEBALL_L','EYEBALL_R'],'eyeball_patches_joined':True,'teeth_clean_material_count':22,'gums_material':'Gums_warm_pink','lashes_seed_faces':len(seeds),'lashes_repaired_faces':len(mask),'default_mouth_open':0,'original_open_preserved':True,'center_aperture':profile(upper,0)-profile(lower,0),'profiles':{'y':ys.tolist(),'upper':upper,'lower':lower},'facial_rig':False},indent=2),encoding='utf-8')
print('FACE_CLEANUP_READY',len(mask),profile(upper,0),profile(lower,0))
