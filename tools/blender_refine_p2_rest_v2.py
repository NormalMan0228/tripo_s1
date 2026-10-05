"""Relaxed eyelids, rooted lashes, soft lower-lip/chin transition, and a subtle closed smile."""
import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_rest_refined_v2';O.mkdir(exist_ok=True)
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
  q.z=-.020*arc*math.exp(-((z-upper)/.028)**2)+.0035*arc*math.exp(-((z-lower)/.021)**2)
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
 w=math.exp(-((abs(y)-.057)/.022)**2-((z+.078)/.043)**2)*smooth(.18,.25,x)
 if w>.003:
  keys[0].data[i].co.z+=.0065*w;keys[0].data[i].co.x+=.0008*w;smile_count+=1
# Keep mesh coordinates synchronized with the new Basis for static attachment.
for v,b in zip(head.data.vertices,keys[0].data):v.co=b.co
head.data.update();head.name='HEAD_relaxed_smile_rest'
newtree=tree([v.co for v in keys[0].data])
# Rediscover free lid edges after deformation, then seat lash roots on those edges.
newtop=[];newbottom=[]
for y in ys:
 zz=np.linspace(.054,.192,461);gap=[z for z in zz if surface(newtree,y,z)<.145]
 newtop.append(max(gap)+.0006 if gap else .12);newbottom.append(min(gap)-.0006 if gap else .12)
lash_report=[]
for name in ['LASH_upper_L','LASH_upper_R','LASH_lower_L','LASH_lower_R']:
 o=bpy.data.objects[name];up='upper' in name;side=1 if name.endswith('_L') else -1
 nx=48;ny=4;offsets=[]
 for j in range(ny+1):
  t=j/ny
  for i in range(nx+1):
   s=i/nx;y=.069+.124*s;z=float(np.interp(y,ys,newtop if up else newbottom));rootx=surface(newtree,y,z)
   if rootx<.145:
    z+=(.001 if up else -.001);rootx=surface(newtree,y,z)
   arc=math.sin(math.pi*s)**.4
   length=((.007+.019*s) if up else (.0025+.005*s))*arc
   yy=y+.0045*t*s;zz=z+(1 if up else -1)*length*t
   xx=rootx+.00065+.022*t+.004*t*t
   xx=max(xx,surface(newtree,yy,zz)+.0008)
   o.data.vertices[j*(nx+1)+i].co=(xx,side*yy,zz)
   if j==0:offsets.append(xx-rootx)
 o.data.update();o['attachment']='Static fit to deformed connected eyelid free edge; bind to lid at facial rig stage.'
 lash_report.append({'object':name,'root_clearance_max':max(offsets),'root_clearance_min':min(offsets)})
# Flatter, thinner brow cards. The atlas retains individual hair texture.
for side in [-1,1]:
 o=bpy.data.objects['BROW_'+('L' if side>0 else 'R')];nx=64;ny=12
 for j in range(ny+1):
  t=j/ny
  for i in range(nx+1):
   s=i/nx;y=.070+.146*s;z=.215+.009*math.sin(math.pi*s)-.010*s+(t-.5)*.039
   x=surface(newtree,y,z)+.0016;o.data.vertices[j*(nx+1)+i].co=(x,side*y,z)
 for p in o.data.polygons:
  for li in p.loop_indices:
   s=(o.data.loops[li].vertex_index%(nx+1))/nx;w=.85*min(1,s*20,(1-s)*24)
   o.data.color_attributes['EdgeFade'].data[li].color=(w,w,w,1)
 o.data.update()
head['default_expression']='Closed-mouth subtle smile, relaxed open eyes'
text=bpy.data.texts.new('V2_refinement_notes');text.write('Rest v2: upper lids relaxed; lashes seated on free lid edges; brows flatter and thinner; lower-lip/chin profile smoothed; small closed-mouth smile.\nFACE_CONTROLS mouth_open 0..1 still opens to original P2 oral shape. Eyelid changes persist across this mouth morph.\nStatic appearance review; full eyelid/blink skinning pending.\n')
hair=bpy.data.objects['HAIR_latest_v2_fitted_to_P2'];hair.hide_render=False
cam=sc.camera
def view(pos,target=(0,0,.08),scale=1.14):
 target=Vector(target);cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();view((3,0,0))
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
target=O/'explorer_b_P2_rest_refined_v2.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target))
for name,pos in [('front',(3,0,0)),('angle',(3,-2,.05)),('side',(0,-3,0))]:
 view(pos);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True
for name,pos,tgt,scale in [('face_detail',(3,0,0),(0,0,.05),.66),('eye_detail',(3,-.3,0),(.2,0,.13),.40),('mouth_closed',(3,-.25,0),(.2,0,-.10),.33),('mouth_profile',(0,-3,0),(.23,0,-.10),.29)]:
 view(pos,tgt,scale);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(2);bpy.context.view_layer.update();view((3,-.25,0),(.20,0,-.075),.33);sc.render.filepath=str(O/'mouth_open.png');bpy.ops.render.render(write_still=True)
report={'source':str(SOURCE),'file':str(target),'api_credits':0,'upper_lid_center_lowering':.020,'lower_lid_center_raising':.0035,'eye_skin_vertices_adjusted':changed_eyes,'chin_vertices_adjusted':changed_chin,'chin_max_shift':max_chin_shift,'smile_vertices_adjusted':smile_count,'corner_lift_max':.0065,'lash_attachment':lash_report,'default_mouth_open':0,'full_facial_rig':False,'skin_vertices_before':len(before),'skin_vertices_after':len(head.data.vertices)}
(O/'refinement-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
