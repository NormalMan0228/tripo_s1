"""V2h: fair orbital skin, integral lid margins, brows/nose, shaded eyes and relaxed idle."""
import bpy,math,json,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector,kdtree
R=Path(__file__).resolve().parents[1];SRC=R/'art/characters/explorer_b_face_rig_manual_v2g/explorer_clean_eyes_v2g.blend';O=R/'art/characters/explorer_b_face_rig_manual_v2h';O.mkdir(exist_ok=True)
sha=hashlib.sha256(SRC.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1)
h=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];keys=h.data.shape_keys.key_blocks
base=np.array([v.co[:] for v in keys['Basis'].data]);N=len(base);start=N-688
assert N==7530
# A scalar surface fit removes angular ripples without collapsing the YZ eye loops.
def smoothstep(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
def fair(coords):
 arr=coords.copy();eligible=np.where((arr[:,0]>.11)&(np.abs(arr[:,1])>.035)&(arr[:,2]>-.075)&(arr[:,2]<.21))[0]
 kd=kdtree.KDTree(len(eligible))
 for i in eligible:kd.insert((0,arr[i,1],arr[i,2]),int(i))
 kd.balance();fits=[]
 for i in eligible:
  p=arr[i];rr=math.sqrt(((abs(p[1])-.149)/.12)**2+((p[2]-.063)/.108)**2);w=1-smoothstep(.80,1.28,rr)
  if i>=start:
   row=((i-start)%344)//43
   if row>=6:continue
   w*=1 if row<5 else .65
  if w<.001:continue
  nei=kd.find_range((0,p[1],p[2]),.039)
  ids=np.array([j for _,j,d in nei]);d=(arr[ids,1:]-p[1:])/.039
  if len(ids)<8:continue
  A=np.column_stack((np.ones(len(ids)),d[:,0],d[:,1],d[:,0]**2,d[:,0]*d[:,1],d[:,1]**2))
  wt=np.exp(-3*np.sum(d*d,axis=1));mat=A.T@(wt[:,None]*A)+np.diag([1e-9,1e-6,1e-6,.0003,.0003,.0003])
  co=np.linalg.solve(mat,A.T*wt)[0];fits.append((i,ids,co,w*.85))
 for _ in range(5):
  old=arr[:,0].copy()
  for i,ids,co,w in fits:arr[i,0]=old[i]+w*np.clip(co@old[ids]-old[i],-.009,.009)
 return arr
changes={}
for key in keys:
 a=np.array([v.co[:] for v in key.data]);a=fair(a)
 for side,sign,offset in [('R',-1,0),('L',1,344)]:
  blink=int(key.name.split('_')[-1])/100 if key.name.startswith('IntegratedBlink_'+side+'_') else 0
  for row in range(8):
   for j in range(43):
    i=start+offset+row*43+j;p=a[i];q=1-((p[1]-.149*sign)/.083)**2-((p[2]-.061)/.085)**2
    # Thin, continuous lid roll is shaped from the existing skin loops.
    upper=base[i,2]>.063
    roll=([0,0,0,0,0,.0006,.0028,.0010][row])*(1 if upper else .72)
    a[i,0]+=roll*(1-.4*blink)
    if q>0:
     envelope=.197+.066*math.sqrt(q)+.0035+.003*blink;d=a[i,0]-envelope
     a[i,0]=envelope+.5*(d+math.sqrt(d*d+1e-7))
 # Local nose-tip rotation downwards, fading before the philtrum/lips.
 for i,p in enumerate(base):
  x,y,z=p
  w=math.exp(-(y/.057)**4)*smoothstep(.293,.353,x)*(1-smoothstep(.066,.085,abs(z+.040)))
  if z<-.107 or z>.047:w=0
  if w:
   angle=.19*w;dx=x-.317;dz=z+.012
   a[i,0]+=math.cos(angle)*dx+math.sin(angle)*dz-dx
   a[i,2]+=-math.sin(angle)*dx+math.cos(angle)*dz-dz
   a[i,1]-=.035*w*y
 for v,p in zip(key.data,a):v.co=p
 changes[key.name]=float(np.max(np.linalg.norm(a-np.array([v.co[:] for v in h.data.vertices]),axis=1)))
for v,p in zip(h.data.vertices,keys['Basis'].data):v.co=p.co
h.data.update()
for side,off in [('R',0),('L',344)]:
 for title,rows in [('Upper',True),('Lower',False)]:
  vg=h.vertex_groups.new(name=title+'_integrated_lid_'+side)
  ids=[start+off+r*43+j for r in [6,7] for j in range(43) if (base[start+off+r*43+j,2]>.063)==rows]
  vg.add(ids,1,'REPLACE')
# Symmetric brows: soften their thickness, bring the arch closer to the eye.
for name,sign in [('09_Brow_candidate_negY',-1),('10_Brow_candidate_posY',1)]:
 o=bpy.data.objects[name];ks=o.data.shape_keys.key_blocks;b=np.array([v.co[:] for v in ks['Basis'].data]);coef=np.polyfit(abs(b[:,1]),b[:,2],3)
 delta=[]
 for p in b:
  center=float(np.polyval(coef,abs(p[1])));q=p.copy();q[2]=center+.78*(p[2]-center)-.008;q[1]=sign*(.155+(abs(p[1])-.155)*.96);q[0]-=.002
  delta.append(q-p)
 for k in ks:
  for v,d in zip(k.data,delta):v.co+=Vector(d)
 for v,p in zip(o.data.vertices,ks['Basis'].data):v.co=p.co
 o.data.update()
# Keep existing lash geometry, adjusting all targets by the small lid contact offset.
for name in ['07_Upper_lash_candidate_negY','08_Upper_lash_candidate_posY']:
 o=bpy.data.objects[name]
 for k in o.data.shape_keys.key_blocks:
  for v in k.data:v.co.x+=.001
 for v,p in zip(o.data.vertices,o.data.shape_keys.key_blocks['Basis'].data):v.co=p.co
# Iris colors are mesh attributes and follow the gaze deformation.
mat=bpy.data.materials.new('Living amber iris - radial fibers and corneal coat');mat.use_nodes=True;mat.diffuse_color=(.24,.11,.035,1)
nt=mat.node_tree;p=nt.nodes.get('Principled BSDF');p.inputs['Roughness'].default_value=.22;p.inputs['Coat Weight'].default_value=1;p.inputs['Coat Roughness'].default_value=.07;p.inputs['IOR'].default_value=1.38
attr=nt.nodes.new('ShaderNodeVertexColor');attr.layer_name='IrisTone';nt.links.new(attr.outputs['Color'],p.inputs['Base Color'])
for side,sg in [('L',1),('R',-1)]:
 o=bpy.data.objects['Iris_pupil.'+side];me=o.data;ca=me.color_attributes.new(name='IrisTone',type='FLOAT_COLOR',domain='POINT')
 for v,c in zip(me.vertices,ca.data):
  yy=(v.co.y-.149*sg)/.0445;zz=(v.co.z-.061)/.0456;r=math.hypot(yy,zz);a=math.atan2(zz,yy)
  fiber=.88+.09*math.sin(a*43+2*math.sin(r*18))+.055*math.sin(a*79-r*13)
  light=.90+.14*(-zz);col=np.array([.26,.116,.035])*fiber*light
  pupil=1-smoothstep(.405,.46,r);rim=smoothstep(.86,.99,r)
  col=col*(1-pupil)+np.array([.0015,.0012,.0008])*pupil;col=col*(1-.72*rim)
  c.color=(*col,1)
 me.materials.clear();me.materials.append(mat)
 for f in me.polygons:f.material_index=0
white=bpy.data.materials['Eye sclera ivory'];p=white.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.82,.81,.76,1);p.inputs['Roughness'].default_value=.19;p.inputs['Coat Weight'].default_value=.7;p.inputs['Coat Roughness'].default_value=.08
# Two restrained studio reflections illuminate the corneal surface.
for name,loc,energy,size in [('Eye softbox',(2,-.47,.65),55,.30),('Eye bounce',(1.5,.60,.25),18,.19)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);sc.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((.22,0,.06))-o.location).to_track_quat('-Z','Y').to_euler()
# Replace the held inspection take with a continuous 12-second relaxed idle.
old=rig.animation_data.action;old.use_fake_user=True;rig.animation_data.action=None
props=['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']
def ease(t):return t*t*t*(t*(t*6-15)+10)
def track(f,points):
 for (a,x),(b,y) in zip(points,points[1:]):
  if a<=f<=b:return x+(y-x)*ease((f-a)/(b-a))
 return points[-1][1]
lr=[(1,0),(25,.03),(40,-.40),(71,-.37),(86,.11),(120,.08),(133,.42),(168,.38),(184,-.16),(226,-.12),(242,.05),(266,.04),(289,0)]
ud=[(1,0),(27,.025),(43,.12),(70,.10),(90,-.08),(122,-.06),(138,.08),(166,.06),(189,-.12),(222,-.10),(244,.02),(267,.02),(289,0)]
blinks=[(53,56,57,63),(113,116,117,123),(178,181,182,188),(251,254,255,261)]
def blink(f):
 for a,b,c,d in blinks:
  if a<=f<=b:return ease((f-a)/(b-a))
  if b<f<=c:return 1.
  if c<f<=d:return 1-ease((f-c)/(d-c))
 return 0.
bone=rig.pose.bones['head'];bone.rotation_mode='XYZ'
for f in range(1,290):
 vals={p:0. for p in props};vals.update(look_lr=track(f,lr),look_ud=track(f,ud),blink_L=blink(f),blink_R=blink(f-.12),brow_up=.018*(1-math.cos(2*math.pi*(f-1)/288)))
 for prop,v in vals.items():rig[prop]=v;rig.keyframe_insert(data_path='["'+prop+'"]',frame=f)
 t=(f-1)/288;bone.rotation_euler=(.004*math.sin(2*math.pi*t),.007*(1-math.cos(2*math.pi*t)),.005*math.sin(2*math.pi*t));bone.keyframe_insert(data_path='rotation_euler',frame=f)
action=rig.animation_data.action;action.name='Relaxed gaze and blink - seamless 12s'
for fc in action.fcurves:
 for k in fc.keyframe_points:k.interpolation='LINEAR'
sc.frame_start=1;sc.frame_end=288;sc.render.fps=24;sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.cycles.samples=24;sc.cycles.use_denoising=True
cam=sc.camera
def camera(target,offset,scale):
 t=Vector(target);cam.location=t+Vector(offset);cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(label):sc.render.filepath=str(O/(label+'.png'));bpy.ops.render.render(write_still=True)
# Save before rendering so long renders cannot lose the editable result.
camera((.13,0,0),(4,-.30,.08),1.24)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.shading.type='MATERIAL';s.shading.use_scene_lights=True;s.shading.use_scene_world=True;s.region_3d.view_location=(.14,0,.01);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.18;s.region_3d.view_perspective='ORTHO';s.overlay.show_overlays=False
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,'frames':288,'fps':24,'seconds':12,'previous_inspection_action':old.name,'blink_events':blinks,'status':'awaiting visual and deformation checks'}
(O/'refinement-report.json').write_text(json.dumps(report,indent=2))
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS');txt.clear();txt.write('V2h face refinement\nIntegrated upper/lower lid margins and scalar orbital skin fairing. Original lashes preserved. Paired brow alignment, gently lowered nose tip, amber iris fibers and corneal gloss.\nSpace: 12 second relaxed looping gaze/blink animation. The former 31 second inspection action is retained. Rig custom properties remain editable; unlink action for manual posing.\nLive eye Geometry Nodes require baking or equivalent implementation for game export. This is a Blender prototype.\n')
F=O/'explorer_living_face_v2h.blend';bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(F));render('neutral')
hidden=[]
for o in sc.objects:
 if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
for f,label in [(1,'open'),(55,'half'),(56,'closed')]:
 sc.frame_set(f);camera((.22,-.149,.073),(4,-.3,0),.34);render('eye-'+label)
sc.frame_set(1);camera((.25,0,-.02),(.5,-4,0),.58);render('profile')
for o in hidden:o.hide_render=False
sc.frame_set(1);camera((.13,0,0),(4,-.3,.08),1.24);bpy.ops.wm.save_as_mainfile(filepath=str(F));print('FACE_V2H_READY',flush=True)
