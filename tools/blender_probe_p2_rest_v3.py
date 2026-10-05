"""Relaxed eyelids, rooted lashes, soft lower-lip/chin transition, and a subtle closed smile."""
import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_rest_refined_v3';O.mkdir(exist_ok=True)
SOURCE=R/'art/characters/explorer_b_p2_closed_assembly_v1/explorer_b_P2_closed_assembly_v1.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene;head=bpy.data.objects['HEAD_closed_rest'];keys=head.data.shape_keys.key_blocks
ctrl=bpy.data.objects['FACE_CONTROLS'];ctrl['mouth_open']=0.;sc.frame_set(1);bpy.context.view_layer.update()
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def tree(coords):
 head.data.calc_loop_triangles();return BVHTree.FromPolygons(coords,[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True)
before=np.array([v.co[:] for v in keys[0].data]);oldtree=tree([Vector(v) for v in before])
def surface(t,y,z):
 p,*_=t.ray_cast(Vector((2,y,z)),Vector((-1,0,0)));return p.x if p else -.3
ys=np.linspace(.064,.199,91);top=[];bottom=[]
for y in ys:
 zz=np.linspace(.054,.192,461);gap=[z for z in zz if surface(oldtree,y,z)<.145]
 top.append(max(gap)+.0004 if gap else .12);bottom.append(min(gap)-.0004 if gap else .12)
# Lower the connected upper eyelid skin and gently raise the lower rim.
eye_delta=[];changed_eyes=0
for c in before:
 x,y,z=c;dy=abs(y);q=Vector();s=(dy-.068)/.129
 if .064<dy<.199 and x>.13 and .025<z<.23:
  arc=max(0,math.sin(math.pi*max(0,min(1,s))))**.7
  upper=float(np.interp(dy,ys,top));lower=float(np.interp(dy,ys,bottom))
  q.z=-.008*arc*math.exp(-((z-upper)/.028)**2)+.0018*arc*math.exp(-((z-lower)/.021)**2)
  q.z*=smooth(.13,.19,x)
  if abs(q.z)>.00005:changed_eyes+=1
 eye_delta.append(q)
for key in keys:
 for v,d in zip(key.data,eye_delta):v.co+=d
# Rebuild the lower-lip-to-chin front profile with a smooth Hermite transition.
for v in keys[0].data:
 x,y,z=v.co
 if x>.24 and abs(y)<.085 and -.119<z<-.061:
  w=math.exp(-((z+.092)/.020)**4)*(1-smooth(.042,.085,abs(y)))*smooth(.24,.27,x)
  v.co.x-=.012*w
aftereye=np.array([v.co[:] for v in keys[0].data]);basetree=tree([Vector(v) for v in aftereye])
changed_chin=0;max_chin_shift=0
for i,c in enumerate(aftereye):
 x,y,z=c
 if not -.182<z<-.100 or abs(y)>.115 or x<.19:continue
 frontx=surface(basetree,y,z)
 if frontx-x>.030:continue
 start=-.100;end=-.182;t=(start-z)/(start-end)
 a=surface(basetree,y,start);b=surface(basetree,y,end)
 target=(2*t**3-3*t*t+1)*a+(t**3-2*t*t+t)*(-.065)+(-2*t**3+3*t*t)*b+(t**3-t*t)*(-.037)
 w=(1-smooth(.067,.115,abs(y)))*smooth(.19,.24,x)*(1-smooth(.003,.030,frontx-x))
 shift=max(-.004,min(.036,target-x))*w
 keys[0].data[i].co.x+=shift
 if abs(shift)>.0001:changed_chin+=1;max_chin_shift=max(max_chin_shift,abs(shift))
# Lift closed lip corners slightly; move both sides of the seal together.
smile_count=0
for i,c in enumerate(aftereye):
 x,y,z=c
 w=math.exp(-((abs(y)-.072)/.024)**2-((z+.078)/.045)**2)*smooth(.18,.25,x)
 if w>.003:
  keys[0].data[i].co.z+=.021*w;keys[0].data[i].co.x+=.0008*w;smile_count+=1
# Keep mesh coordinates synchronized with the new Basis for static attachment.
for v,b in zip(head.data.vertices,keys[0].data):v.co=b.co
head.data.update();head.name='HEAD_relaxed_smile_rest'
newtree=tree([v.co for v in keys[0].data])

for side in [-1,1]:
 for y in np.linspace(.064,.199,28):
  zz=np.linspace(.045,.20,400);gap=[z for z in zz if surface(newtree,side*y,z)<.145]
  if gap:print(side,round(y,4),round(min(gap),4),round(max(gap),4))
