"""V2a continuation: local profile sculpt and fitted, relaxed eyelids."""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];SRC=R/'art/characters/explorer_b_face_rig_manual_v2a/explorer_face_lower_lip_v2a.blend'
OUT=R/'art/characters/explorer_b_face_rig_manual_v2b';OUT.mkdir(exist_ok=True)
sha=hashlib.sha256(SRC.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(SRC))
sc=bpy.context.scene;sc.frame_set(1);rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];head=bpy.data.objects['01_Face_skin_neck']
sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.cycles.samples=20
cam=sc.camera
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name):
 hidden=[]
 if name.startswith(('profile','eye-side','eye-front')):
  for o in sc.objects:
   if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
 sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 for o in hidden:o.hide_render=False
camera((.18,0,-.15),(0,-4,0),.75);render('profile-before')
camera((.18,-.149,.07),(1.3,-4,.08),.38);render('eye-side-before')
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
orig=[v.co.copy() for v in head.data.shape_keys.key_blocks['jawOpen'].data]
delta=[]
for p in orig:
 x,y,z=p;front=smooth(.10,.24,x);width=math.exp(-(y/.105)**4)
 # Restore lower-lip support and bring the chin toward the upper-lip profile.
 lip=.022*math.exp(-((z+.219)/.025)**2)
 support=.032*math.exp(-((z+.262)/.038)**2)
 chin=.037*math.exp(-((z+.302)/.043)**2)
 dx=(lip+support+chin)*front*width*(1-smooth(-.17,-.135,z))*smooth(-.39,-.34,z)
 delta.append(Vector((dx,0,0)))
for k in head.data.shape_keys.key_blocks:
 for p,d in zip(k.data,delta):p.co+=d
for v,p in zip(head.data.vertices,head.data.shape_keys.key_blocks['Basis'].data):v.co=p.co
head.data.update()

# Fit a smaller globe; the previous broad annulus covered an oversized globe at the sides.
old_r=Vector((.108,.097,.101));new_r=Vector((.095,.083,.085));centers={}
for side,sign in [('L',1),('R',-1)]:
 old_c=Vector((.133,.149*sign,.063));c=Vector((.146,.149*sign,.061));centers[side]=c
 for name in ['Eye_white.'+side,'Iris_pupil.'+side]:
  ob=bpy.data.objects[name]
  for v in ob.data.vertices:
   rel=v.co-old_c;v.co=c+Vector(tuple(rel[i]*new_r[i]/old_r[i] for i in range(3)))
  ob.data.update()
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for side,c in centers.items():
 b=rig.data.edit_bones['eye.'+side];b.head=c;b.tail=c+Vector((0,.06,0))
bpy.ops.object.mode_set(mode='OBJECT')
head.data.calc_loop_triangles();skin=BVHTree.FromPolygons([v.co for v in head.data.vertices],[t.vertices[:] for t in head.data.loop_triangles],all_triangles=True)
for side,c in centers.items():
 ob=bpy.data.objects['Eyelids.'+side];r=new_r;segments=64;nr=8
 def edge(a,blink):
  u=math.cos(a);s=math.sin(a);y=c.y+.077*u
  seam=c.z-.004+.004*u*u
  z=c.z+(.035 if s>=0 else .040)*s+.003*u*(1 if side=='L' else -1)
  z=z*(1-blink)+seam*blink
  inside=max(0,1-((y-c.y)/r.y)**2-((z-c.z)/r.z)**2)
  x=c.x+r.x*math.sqrt(inside)+.0018
  return Vector((x,y,z))
 def coords(blink):
  points=[]
  for j in range(nr+1):
   t=j/nr
   for i in range(segments):
    a=2*math.pi*i/segments;p=edge(a,blink)
    oy=c.y+.104*math.cos(a);oz=c.z+.105*math.sin(a)
    hit=skin.ray_cast(Vector((1,oy,oz)),Vector((-1,0,0)),2)[0]
    outer=Vector((hit.x-.0007 if hit else c.x,oy,oz))
    # Smoothly fit into the skin; no abrupt last-ring drop or max-clamped membrane.
    q=p.lerp(outer,t)
    inside=1-((q.y-c.y)/r.y)**2-((q.z-c.z)/r.z)**2
    if inside>0 and t<.75:
     sx=c.x+r.x*math.sqrt(inside)+.0018
     q.x=max(q.x,sx*(1-t*t)+q.x*t*t)
    points.append(q)
  return points
 for k in ob.data.shape_keys.key_blocks:
  amount=0 if k.name=='Basis' else int(k.name.split('_')[-1])/100
  for p,q in zip(k.data,coords(amount)):p.co=q
 for v,p in zip(ob.data.vertices,ob.data.shape_keys.key_blocks['Basis'].data):v.co=p.co
 ob.data.update()
 # Replace the stretched AI lash strip with a thin tapered rim following the lid.
 lname='08_Upper_lash_candidate_posY' if side=='L' else '07_Upper_lash_candidate_negY'
 oldlash=bpy.data.objects[lname];mat=oldlash.data.materials[0]
 oldlash.name='SOURCE_original_lash_'+side;oldlash.hide_render=True;oldlash.hide_set(True)
 def lashcoords(amount):
  points=[]
  for j in range(49):
   a=math.pi*j/48;p=edge(a,amount)+Vector((.001,0,.001))
   thick=.0003+.0020*math.sin(a)**.5
   for xx,zz in [(1,0),(0,1),(-1,0),(0,-1)]:points.append(p+Vector((.0008*xx,0,thick*zz)))
  return points
 lf=[]
 for j in range(48):
  for k in range(4):lf.append((j*4+k,(j+1)*4+k,(j+1)*4+(k+1)%4,j*4+(k+1)%4))
 lf.extend([(3,2,1,0),(192,193,194,195)])
 mesh=bpy.data.meshes.new(lname+'_fitted');mesh.from_pydata(lashcoords(0),[],lf);mesh.materials.append(mat)
 lash=bpy.data.objects.new(lname,mesh);sc.collection.objects.link(lash)
 for p in mesh.polygons:p.use_smooth=True
 vg=lash.vertex_groups.new(name='head');vg.add(list(range(len(mesh.vertices))),1,'REPLACE');mod=lash.modifiers.new('Face rig','ARMATURE');mod.object=rig
 lash.shape_key_add(name='Basis')
 for sample in range(1,5):
  key=lash.shape_key_add(name='Blink_'+str(sample*25))
  for p,q in zip(key.data,lashcoords(sample/4)):p.co=q
  d=key.driver_add('value').driver;d.expression='max(0,1-abs(4*v-'+str(sample)+'))'
  var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='["blink_'+side+'"]'
sc.frame_set(2);sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
camera((.18,0,-.15),(0,-4,0),.75);render('profile-after')
camera((.18,-.149,.07),(1.3,-4,.08),.38);render('eye-side-after')
camera((.18,-.149,.07),(4,-1.2,0),.38);render('eye-front-after')
camera((.10,0,0),(4,-.35,.12),1.30);render('front-after')
sc.frame_set(18);render('blink-after');sc.frame_set(98);render('jaw-after');sc.frame_set(1)
camera((.1,0,0),(3,-3,.1),1.25);render('angle-after')
camera((.1,0,0),(4,-.35,.12),1.3)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.1,0,0);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.65;s.region_3d.view_perspective='ORTHO'
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,'maximum_profile_depth_correction':max(d.x for d in delta),'eye_radius_before':list(old_r),'eye_radius_after':list(new_r),'neutral_upper_lid_height':.035,'topology_of_head_preserved':True,'inspection_views_hair_hidden_only_for_render':True,'old_lashes_archived_hidden':True}
assert report['source_unchanged']
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_profile_eye_v2b.blend'))
(OUT/'profile-eye-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PROFILE_EYE_V2B_SAVED',flush=True)
