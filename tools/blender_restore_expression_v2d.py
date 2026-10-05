"""Restore archived original lashes, reopen the integrated eye silhouette, close neutral mouth locally."""
import bpy,math,json,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];SRC=R/'art/characters/explorer_b_face_rig_manual_v2c/explorer_integrated_eyes_v2c.blend'
OUT=R/'art/characters/explorer_b_face_rig_manual_v2d';OUT.mkdir(exist_ok=True)
sha=hashlib.sha256(SRC.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1)
head=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];keys=head.data.shape_keys.key_blocks
base=[p.co.copy() for p in keys['Basis'].data]
report0=json.loads((SRC.parent/'integrated-eye-report.json').read_text());retained={int(i):j for i,j in report0['retained_source_mapping'].items()}
added=sorted(set(range(len(base)))-set(retained));patch={};offset=0
for side,n in report0['shared_boundary_edges'].items():
 for j in range(10):
  for i in range(n):patch[added[offset+j*n+i]]=(side,(j+1)/10)
 offset+=10*n
assert offset==len(added)
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def protect(p):
 q=p.copy();cy=.149*(1 if p.y>0 else -1);inside=1-((p.y-cy)/.083)**2-((p.z-.061)/.085)**2
 if inside>0 and p.x>.146:q.x=max(q.x,.156+.095*math.sqrt(inside)+.004)
 return q
for key in keys:
 for idx,(side,t) in patch.items():
  p=key.data[idx].co.copy();cy=.149*(1 if side=='L' else -1)
  z0=base[idx].z;upper=max(0,(z0-.061)/.035);lower=max(0,(.061-z0)/.04)
  blink=0
  if key.name.startswith('IntegratedBlink_'+side+'_'):blink=int(key.name.split('_')[-1])/100
  p.z+=(.018*min(1,upper)-.003*min(1,lower))*t*t*(1-blink)
  p.x+=.010*t
  key.data[idx].co=protect(p)
 # Smoothly advance the bordering skin instead of leaving a deep socket.
 for idx in retained:
  p=key.data[idx].co.copy();cy=.149*(1 if p.y>0 else -1)
  w=math.exp(-((p.y-cy)/.11)**4-((p.z-.07)/.115)**4)*smooth(.12,.20,p.x)
  if -.045<p.z<.23:
   p.x+=.006*w;key.data[idx].co=p
for side in ('L','R'):
 c=Vector((.146,.149*(1 if side=='L' else -1),.061));newc=c+Vector((.010,0,0))
 white=bpy.data.objects['Eye_white.'+side]
 for v in white.data.vertices:v.co.x+=.010
 iris=bpy.data.objects['Iris_pupil.'+side]
 for v in iris.data.vertices:
  y=(v.co.y-c.y)*1.15;z=(v.co.z-c.z)*1.15
  v.co=newc+Vector((.096*math.sqrt(max(0,1-(y/.084)**2-(z/.086)**2)),y,z))
 white.data.update();iris.data.update()
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for side in ('L','R'):
 b=rig.data.edit_bones['eye.'+side];b.head.x+=.010;b.tail.x+=.010
bpy.ops.object.mode_set(mode='OBJECT')

# Restore the actual archived AI lash geometry, not a newly drawn substitute.
restored={}
for side in ('L','R'):
 lname='08_Upper_lash_candidate_posY' if side=='L' else '07_Upper_lash_candidate_negY'
 substitute=bpy.data.objects.get(lname)
 if substitute:bpy.data.objects.remove(substitute,do_unlink=True)
 obj=bpy.data.objects['SOURCE_original_lash_'+side];original=[p.co.copy() for p in obj.data.shape_keys.key_blocks['Basis'].data]
 restored[side]={'vertices':len(original),'polygons':len(obj.data.polygons),'source':'SOURCE_original_lash_'+side}
 obj.shape_key_clear();obj.name=lname;obj.hide_render=False;obj.hide_viewport=False;obj.hide_set(False)
 for v,p in zip(obj.data.vertices,original):v.co=p+Vector((.010,0,0))
 obj.shape_key_add(name='Basis');neutral=[v.co.copy() for v in obj.data.vertices]
 for k in range(1,5):
  amount=k/4;key=obj.shape_key_add(name='Blink_'+str(k*25));cy=.149*(1 if side=='L' else -1)
  for v,p in zip(key.data,neutral):
   u=max(-1,min(1,(p.y-cy)/.080));s=math.sqrt(max(0,1-u*u));seam=.057+.004*u*u
   opening=.061+.053*s+.003*u*(1 if side=='L' else -1)
   q=p.copy();q.z+=(seam-opening)*amount
   inside=1-((q.y-cy)/.083)**2-((q.z-.061)/.085)**2
   if inside>0:q.x=max(q.x,.156+.095*math.sqrt(inside)+.005)
   v.co=q
  d=key.driver_add('value').driver;d.expression='max(0,1-abs(4*v-'+str(k)+'))';var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='["blink_'+side+'"]'
 obj.data.update()

# Measure the actual neutral mouth gap by frontal rays. Close locally around its rims.
mouthbase=[p.co.copy() for p in keys['Basis'].data];head.data.calc_loop_triangles()
bvh=BVHTree.FromPolygons(mouthbase,[t.vertices[:] for t in head.data.loop_triangles],all_triangles=True)
ys=np.linspace(-.098,.098,99);bounds=[]
for y in ys:
 gaps=[]
 for z in np.linspace(-.215,-.115,201):
  hit=bvh.ray_cast(Vector((1,float(y),float(z))),Vector((-1,0,0)),2)[0]
  if hit is not None and hit.x<.22:gaps.append(float(z))
 if gaps:bounds.append((min(gaps)-.0007,max(gaps)+.0007))
 else:bounds.append((-.151,-.151))
delta=[]
for p in mouthbase:
 x,y,z=p;lo=float(np.interp(y,ys,[v[0] for v in bounds]));hi=float(np.interp(y,ys,[v[1] for v in bounds]));q=Vector()
 if abs(y)<.098 and hi-lo>.001 and -.255<z<-.095 and x>.21:
  seam=(lo+hi)/2;mid=(lo+hi)/2;front=smooth(.21,.275,x)
  if z<mid:
   w=smooth(lo-.055,lo-.004,z);dz=(seam-lo+.0014)*w
  else:
   w=1-smooth(hi+.003,hi+.040,z);dz=(seam-hi-.0014)*w
  q.z=dz*front
  # Match lip depths at contact, keeping the chin and outer mouth outline anchored.
  edge_weight=math.exp(-((z-(lo if z<mid else hi))/.012)**2)*front
  q.x=(.342-5.0*y*y-x)*.75*edge_weight
 delta.append(q)
for key in keys:
 if key.name=='jawOpen':continue
 for v,d in zip(key.data,delta):v.co+=d
for v,p in zip(head.data.vertices,keys['Basis'].data):v.co=p.co
head.data.update();sc.frame_set(2);sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
cam=sc.camera;sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.cycles.samples=20
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name):sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
camera((.1,0,0),(4,-.35,.12),1.3);render('neutral');sc.frame_set(18);render('blink');sc.frame_set(98);render('jaw-open');sc.frame_set(1)
camera((.25,0,-.16),(4,0,0),.43);render('mouth-closed')
camera((.18,-.149,.075),(4,-1.2,0),.4);render('eye-original-lash')
camera((.1,0,0),(3,-3,.1),1.3);render('angle');camera((.1,0,0),(4,-.35,.12),1.3)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.1,0,.02);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.45;s.region_3d.view_perspective='ORTHO'
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,'original_lashes_restored':restored,'mouth_gap_before_center':bounds[len(bounds)//2],'mouth_max_delta':max(d.length for d in delta),'chin_mouth_delta_max':max(d.length for p,d in zip(mouthbase,delta) if p.z<-.255),'eye_advance':.010,'iris_scale':1.15,'upper_eye_opening_increase':.018}
assert report['source_unchanged'] and report['chin_mouth_delta_max']==0
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_expression_v2d.blend'))
(OUT/'expression-restoration-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('EXPRESSION_V2D_SAVED',flush=True)
