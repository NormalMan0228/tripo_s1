import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';FILE=A/'explorer_b_balanced_face_v4.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS'];contours=json.loads((A/'lash-contours.json').read_text(encoding='utf-8'))
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
profiles={}
for sign in [-1,1]:
 arr=np.array(contours[str(sign)]);ys=arr[:,0];bot=arr[:,1];top=arr[:,2];xmin=arr[:,3]
 for _ in range(2):
  for value in (bot,top,xmin):value[1:-1]=value[1:-1]*.5+(value[:-2]+value[2:])*.25
 # Trace the tapered solid wing beyond the last dark atlas sample.
 final_y=.239 if sign==-1 else .240;ys=np.append(ys,[final_y]);bot=np.append(bot,[.148]);top=np.append(top,[.148]);xmin=np.append(xmin,[.145]);profiles[sign]=(ys,bot,top,xmin)
attr=head.data.attributes['Lash_color_repair']
for v,a in zip(head.data.vertices,attr.data):
 x,y,z=v.co;sign=1 if y>0 else -1;yy=abs(y);ys,bot,top,xmin=profiles[sign];b=float(np.interp(yy,ys,bot));t=float(np.interp(yy,ys,top));minx=float(np.interp(yy,ys,xmin));a.value=smooth(ys[0]-.001,ys[0]+.007,yy)*(1-smooth(ys[-1]-.001,ys[-1]+.004,yy))*smooth(minx-.007,minx-.002,x)*smooth(b-.003,b-.001,z)*(1-smooth(t+.002,t+.0045,z))
for loop,c in zip(head.data.loops,head.data.color_attributes['Lash_tint'].data):
 f=attr.data[loop.vertex_index].value;c.color=(1-f+f*.012,1-f+f*.009,1-f+f*.006,1)
head['lash_color_repair']='Contour-traced fully dark lash band and tapered wing, painted as smooth corner tint; skin outside upper/lower contours excluded'
# Reattach each highlight to its final iris position after moving it sideways.
for side in ('L','R'):
 cap=bpy.data.objects['IRIS_PUPIL_'+side];cap.data.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in cap.data.vertices],[t.vertices for t in cap.data.loop_triangles],all_triangles=True)
 for name in ('main','small'):
  o=bpy.data.objects['EYE_CATCHLIGHT_'+side+'_'+name];p,*_=tree.ray_cast(Vector((.3,o.location.y,o.location.z)),Vector((-1,0,0)))
  if p:o.location.x=p.x+.00055
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();sc.cycles.samples=32;cam=sc.camera
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0))]:render(n,pos)
hair.hide_render=True;render('eyes_detail',(3,0,0),Vector((.18,0,.145)),.52);render('mouth_closed',(3,-.6,0),Vector((.26,0,-.092)),.34);render('mouth_front',(3,0,0),Vector((.26,0,-.092)),.34)
hair.hide_render=False;target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23;bpy.ops.wm.save_as_mainfile(filepath=str(FILE));print('CONTOUR_PAINT_SAVED')
