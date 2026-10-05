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
  q.z=-.012*arc*math.exp(-((z-upper)/.028)**2)+.0018*arc*math.exp(-((z-lower)/.021)**2)
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
# Seat independent sides on their actual free rim, instead of mirroring the ray samples.
from mathutils.bvhtree import BVHTree
atlas=bpy.data.images.get('brow_lash_atlas.png')
pixels=np.array(atlas.pixels[:]).reshape(atlas.size[1],atlas.size[0],4)[::-1]
alpha=pixels[:,:,3];W,H=atlas.size
cardmat=bpy.data.materials['Brow_lash_alpha_clean']
collection=bpy.data.collections['04_Brows_lashes']
for obj in list(collection.objects):
 if obj.name.startswith(('LASH_','BROW_')):bpy.data.objects.remove(obj,do_unlink=True)
def makecard(name,verts,uvs,faces,fades):
 m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update()
 o=bpy.data.objects.new(name,m);collection.objects.link(o);m.materials.append(cardmat)
 m.uv_layers.new(name='HairAtlas');m.color_attributes.new(name='EdgeFade',type='FLOAT_COLOR',domain='CORNER')
 uv=m.uv_layers['HairAtlas'];fade=m.color_attributes['EdgeFade']
 for p in m.polygons:
  p.use_smooth=True
  for li in p.loop_indices:
   vi=m.loops[li].vertex_index;uv.data[li].uv=uvs[vi];fade.data[li].color=(fades[vi],)*3+(1,)
 return o
def gridfaces(nx,ny):
 return [(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)]
def lid_edge(y,upper):
 zz=np.linspace(.045,.20,620);gap=[z for z in zz if surface(newtree,y,z)<.145]
 if not gap:raise ValueError(('No aperture at lash root',y))
 z=max(gap) if upper else min(gap)
 # Search for the crossing with the skin, then inset 1 mm onto the lid surface.
 step=1 if upper else -1
 for k in range(30):
  if surface(newtree,y,z)>=.145:break
  z+=step*.00005
 return z+step*.0012
# Continuous tapered lash strands avoid disconnected alpha fragments.
# Keep the former atlas in brows; lashes use thin, editable low-sided strands.
import random
strandmat=bpy.data.materials.new('Lashes_dark_brown_strands');strandmat.use_nodes=True
bs=strandmat.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.025,.009,.0035,1);bs.inputs['Roughness'].default_value=.48
lash_report=[]
for up in [True,False]:
 for side in [-1,1]:
  rng=random.Random(81+(1 if up else 2));count=48 if up else 24
  verts=[];faces=[];uvs=[];fades=[];roots=[]
  for strand in range(count):
   s=(strand+.5)/count;s+=rng.uniform(-.18,.18)/count
   y=side*(.078+.115*s);z=lid_edge(y,up)+( .0015 if up else -.0006)
   x=surface(newtree,y,z)+.00025
   taper=math.sin(math.pi*s)**.35
   length=((.009+.017*s) if up else (.003+.004*s))*taper*rng.uniform(.84,1.13)
   width=(.00062 if up else .00040)*rng.uniform(.82,1.12)
   first=len(verts);rings=12;sides=4
   for j in range(rings):
    t=j/(rings-1);zz=z+(1 if up else -1)*length*t
    yy=y+side*(s-.38)*.010*t*t
    radius=width*.5*(1-t)**.7+.000012
    xx=max(x+.035*t+.004*t*t,surface(newtree,yy,zz)+(radius+.0007 if j else .0002))
    for k in range(sides):
     angle=2*math.pi*k/sides
     verts.append((xx+radius*math.cos(angle),yy+radius*math.sin(angle),zz))
     uvs.append((s,t));fades.append(1.)
     if j==0:roots.append(len(verts)-1)
   for j in range(rings-1):
    for k in range(sides):
     f=first+j*sides+k;n=first+j*sides+(k+1)%sides
     faces.append((f,n,n+sides,f+sides))
   faces.append(tuple(first+(rings-1)*sides+k for k in range(sides)))
  name='LASH_'+('upper' if up else 'lower')+('_L' if side>0 else '_R')
  obj=makecard(name,verts,uvs,faces,fades);obj.data.materials.clear();obj.data.materials.append(strandmat)
  obj['attachment']='Continuous tapered strands with embedded roots above upper lid / below lower lid. Rest fit; blink binding pending.'
  distances=[newtree.find_nearest(Vector(verts[i]))[3] for i in roots]
  lash_report.append({'object':name,'root_nearest_skin_max':max(distances),'root_nearest_skin_mean':sum(distances)/len(distances),'root_vertices':len(roots),'root_indices':roots,'strands':count,'quads_per_strand':44,'alpha_fragments':False})
# Map only the contiguous eyebrow body and conform a thin card to the forehead.
# The UV strip follows the alpha silhouette; rectangular cards caused intersected islands.
nx=96;ny=12;xs=np.linspace(105,1170,nx+1);bounds=[]
for px in xs:
 ix=int(px);score=(alpha[45:440,ix-2:ix+3]>.60).sum(1)
 runs=[];start=None
 for row,valid in enumerate(score>=3):
  if valid and start is None:start=row
  if start is not None and (not valid or row==len(score)-1):
   runs.append((start,row));start=None
 low,high=max(runs,key=lambda r:r[1]-r[0]);bounds.append((low+45-2,high+45+2))
for side in [-1,1]:
 verts=[];uvs=[];fades=[]
 for j in range(ny+1):
  t=j/ny
  for i,(lo,hi) in enumerate(bounds):
   s=i/nx;y=side*(.073+.142*s)
   center=.228+.010*math.sin(math.pi*s)-.016*s
   thickness=.024*(hi-lo)/220
   z=center+(t-.5)*thickness;x=surface(newtree,y,z)+.0024
   verts.append((x,y,z));uvs.append((xs[i]/W,1-(hi+(lo-hi)*t)/H))
   fades.append(.9*min(1,s*20,(1-s)*20))
 obj=makecard('BROW_'+('L' if side>0 else 'R'),verts,uvs,gridfaces(nx,ny),fades)
 obj['UV_cleanup']='Contiguous main alpha silhouette only; no rectangular image margin'
 # Project even between mesh samples onto the head; geometry has a small positive offset.
 modifier=obj.modifiers.new('Forehead_contact','SHRINKWRAP');modifier.target=head;modifier.wrap_method='NEAREST_SURFACEPOINT';modifier.offset=.0024
# Match the supplied friendly-expression reference: a little sclera beside the iris.
for suffix in ['L','R']:
 eye=bpy.data.objects['EYEBALL_'+suffix];disc=bpy.data.objects['IRIS_PUPIL_'+suffix]
 center=eye.location;radius=eye.dimensions.y*.5
 for v in disc.data.vertices:
  dy=(v.co.y-center.y)*.90;dz=(v.co.z-center.z)*.90
  v.co.y=center.y+dy;v.co.z=center.z+dz
  v.co.x=center.x+math.sqrt(max(.000001,radius*radius-dy*dy-dz*dz))+.00035
 disc.data.update()
head['default_expression']='Closed-mouth subtle smile, relaxed open eyes'
text=bpy.data.texts.new('V3_refinement_notes');text.write('Rest v3: upper lids relaxed; lashes seated on free lid edges; brows flatter and thinner; lower-lip/chin profile smoothed; small closed-mouth smile.\nFACE_CONTROLS mouth_open 0..1 still opens to original P2 oral shape. Eyelid changes persist across this mouth morph.\nContinuous lash strands with embedded roots. Static appearance review; full eyelid/blink skinning pending.\n')
hair=bpy.data.objects['HAIR_latest_v2_fitted_to_P2'];hair.hide_render=False
cam=sc.camera
def view(pos,target=(0,0,.08),scale=1.14):
 target=Vector(target);cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();view((3,0,0))
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
target=O/'explorer_b_P2_rest_refined_v3.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target))
for name,pos in [('front',(3,0,0)),('angle',(3,-2,.05)),('side',(0,-3,0))]:
 view(pos);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True
for name,pos,tgt,scale in [('face_detail',(3,0,0),(0,0,.05),.66),('eye_detail',(3,-.3,0),(.2,0,.13),.40),('mouth_closed',(3,-.25,0),(.2,0,-.10),.33),('mouth_profile',(0,-3,0),(.23,0,-.10),.29),('eye_oblique',(2,-3,0),(.20,-.125,.135),.23),('brow_detail',(3,-.3,0),(.2,-.13,.235),.24)]:
 view(pos,tgt,scale);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(2);bpy.context.view_layer.update();view((3,-.25,0),(.20,0,-.075),.33);sc.render.filepath=str(O/'mouth_open.png');bpy.ops.render.render(write_still=True)
report={'source':str(SOURCE),'file':str(target),'api_credits':0,'upper_lid_center_lowering':.012,'lower_lid_center_raising':.0018,'eye_skin_vertices_adjusted':changed_eyes,'chin_vertices_adjusted':changed_chin,'chin_max_shift':max_chin_shift,'smile_vertices_adjusted':smile_count,'corner_lift_max':.021,'lash_attachment':lash_report,'default_mouth_open':0,'expression_reference':'codex-clipboard-d86b1eef-42f9-41c7-85b7-316c7ba2ad35.png','iris_radius_scale':.90,'lash_method':'continuous tapered low-sided strands; no disconnected alpha fragments','full_facial_rig':False,'skin_vertices_before':len(before),'skin_vertices_after':len(head.data.vertices)}
(O/'refinement-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))


