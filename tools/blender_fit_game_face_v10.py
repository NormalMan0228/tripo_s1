"""Author non-destructive closed rest and fitted blink targets; never edit original Basis."""
import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10';A.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_original_identity_v9/original_face_mpfb_rigify_v9.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];rig.animation_data_clear();hp=rig.pose.bones['head']
for k in list(hp.keys()):
 if isinstance(hp[k],float):hp[k]=0.
for o in sc.objects:
 if o.type=='MESH' and o.data.shape_keys:o.data.shape_keys.animation_data_clear()
sc.frame_set(1);bpy.context.view_layer.update();native=[o for o in sc.objects if o.type=='MESH' and not o.hide_render and not o.name.startswith(('WGT','HAIR'))];head=bpy.data.objects['FACE_original_user_GLb'];raw={o.name:[v.co.copy() for v in o.data.vertices] for o in native};grid=json.loads((A/'probe.json').read_text())['mouth_grid'];ys=np.array(grid['y']);zs=np.array(grid['z']);top=[];bot=[];tx=[];bx=[]
def smooth(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
for y,row in zip(ys,grid['x']):
 gaps=[i for i,(z,x) in enumerate(zip(zs,row)) if -.155<z<-.055 and x is not None and x<.17]
 if gaps:
  ia,ib=max(gaps),min(gaps);a=zs[ia]+.001;b=zs[ib]-.001;at=min(len(row)-1,ia+2);bt=max(0,ib-2);ax=row[at];bxx=row[bt]
 else:a=b=-.089;ax=bxx=.24
 top.append(a);bot.append(b);tx.append(ax);bx.append(bxx)
for arr in [top,bot,tx,bx]:
 for _ in range(2):
  old=arr.copy()
  for i in range(1,len(arr)-1):arr[i]=.6*old[i]+.2*(old[i-1]+old[i+1])
def prof(arr,y):return float(np.interp(y,ys,arr))
def close_point(p):
 x,y,z=p;q=p.copy()
 if x<.075 or abs(y)>.17 or not -.34<z<-.025:return q
 a=prof(top,y);b=prof(bot,y);gap=max(0,a-b)
 if gap<.001:return q
 seam=-.095+.006*min(1,(abs(y)/.105)**2);w=smooth(.06,.15,x)*(1-smooth(.115,.17,abs(y)))
 # Monotone vertical cage maps the lip opening to a hairline seam without crossing faces.
 anchors=[-.34,b-.045,b,a,min(-.027,a+.05),-.025]
 values=[-.34,b-.045+(seam-b)*.40,seam-.00035,seam+.00035,min(-.027,a+.05),-.025]
 q.z+=(float(np.interp(z,anchors,values))-z)*w
 lower=1-smooth(b+.002,a-.002,z);rim=math.exp(-((z-b)/.035)**2)*lower
 dx=max(0,min(.018,prof(tx,y)-prof(bx,y)-.001));q.x+=dx*rim*w
 return q
closed={}
for o in native:
 keys=o.data.shape_keys
 if not keys:o.shape_key_add(name='Basis_original_unchanged');keys=o.data.shape_keys
 key=o.shape_key_add(name='RestClosed');coords=[]
 for p in raw[o.name]:
  q=close_point(p) if o==head else p.copy()
  if o.name.startswith(('TEETH_lower','TONGUE')):q.x-=.012;q.z+=.025
  if o.name.startswith('TEETH_upper'):q.x-=.004
  coords.append(q)
 for v,p in zip(key.data,coords):v.co=p
 key.value=1.;closed[o.name]=coords
# Fit eyelid trajectories to the native eyeball surfaces, preserving their original open shape.
eye_trees={}
for side in ['L','R']:
 o=bpy.data.objects['EYEBALL_original_'+side];o.data.calc_loop_triangles();eye_trees[side]=BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
Y=[.058,.072,.085,.105,.13,.155,.18,.202,.218];U=[.084,.102,.13,.15,.159,.162,.158,.145,.112];B=[.083,.067,.051,.047,.046,.055,.078,.099,.106]
def blink_point(p,side,kind='skin'):
 x,y,z=p;q=p.copy();sgn=1 if side=='L' else -1
 if sgn*y<.055 or sgn*y>.237 or x<.10 or z<.008 or z>.24:return q
 a=float(np.interp(abs(y),Y,U));b=float(np.interp(abs(y),Y,B));seam=b+.22*(a-b);w=smooth(.075,.115,x)*(1-smooth(.218,.237,abs(y)))
 if kind=='upper':dz=(seam+.001-a)*(1-smooth(a+.014,a+.07,z))
 elif kind=='lower':dz=(seam-.001-b)*smooth(b-.045,b-.003,z)
 else:dz=float(np.interp(z,[.008,b-.04,b,a,a+.035,.30],[.008,b-.04,seam-.0004,seam+.0004,a+.035,.30]))-z
 q.z+=dz*w
 hit,*_=eye_trees[side].ray_cast(Vector((1,q.y,q.z)),Vector((-1,0,0)))
 if hit is not None and q.x<hit.x+.003:q.x+=(hit.x+.003-q.x)*w
 return q
for side,label in [('L','Left'),('R','Right')]:
 for o in native:
  if o.name.startswith(('EYEBALL','TEETH','TONGUE','CLAVICLE','EAR')):continue
  name='!ex-eyeBlink'+label;key=o.data.shape_keys.key_blocks.get(name) or o.shape_key_add(name=name);kind='skin'
  for v,p in zip(key.data,raw[o.name]):v.co=blink_point(p,side,kind)
  key.value=0.
sc.render.engine='CYCLES';sc.cycles.samples=24;sc.frame_start=1;sc.frame_end=90;sc.render.fps=30;bpy.ops.wm.save_as_mainfile(filepath=str(A/'face_fitting_workbench.blend'))
cam=sc.camera
def render(label,target=Vector(),scale=1.2,pos=Vector((3,0,0))):
 cam.location=target+pos;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(label+'.png'));bpy.ops.render.render(write_still=True)
render('closed_front');render('closed_mouth',Vector((.23,0,-.095)),.30);render('closed_side',pos=Vector((0,-3,0)))
for o in native:
 for key in o.data.shape_keys.key_blocks:
  if key.name in ['!ex-eyeBlinkLeft','!ex-eyeBlinkRight']:key.value=1.
bpy.context.view_layer.update();render('blink_closed');render('blink_detail',Vector((.2,.13,.11)),.27)
(A/'mouth_profile.json').write_text(json.dumps({'y':ys.tolist(),'top':top,'bottom':bot,'upper_x':tx,'lower_x':bx},indent=2));print('V10_FITTING_COMPLETE')
