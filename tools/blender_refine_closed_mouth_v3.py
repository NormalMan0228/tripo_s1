"""Localized lip sculpt, closed rest pose and oral material revision."""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1]
SRC=R/'art/characters/explorer_b_face_rig_manual_v2/explorer_manual_face_rig_v2.blend'
OUT=R/'art/characters/explorer_b_face_rig_manual_v3';OUT.mkdir(exist_ok=True)
sha=hashlib.sha256(SRC.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene
rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];head=bpy.data.objects['01_Face_skin_neck']
keys=head.data.shape_keys.key_blocks
original=[v.co.copy() for v in keys['jawOpen'].data];previous=[v.co.copy() for v in keys['Basis'].data]
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def lerpmap(x,knots):
 if x<=knots[0][0] or x>=knots[-1][0]:return x
 for (a,va),(b,vb) in zip(knots,knots[1:]):
  if a<=x<=b:return va+(vb-va)*(x-a)/(b-a)
 return x
def rims(y):
 u=min(1,abs(y)/.10);return -.209+.066*u*u,-.132-.014*u*u
def refine_open(p):
 q=p.copy();x,y,z=p;lo,hi=rims(y)
 w=(1-smooth(.065,.11,abs(y)))*smooth(.19,.265,x)
 # Reduce oversized lower vermilion and under-lip bulge in the open target too.
 lip=math.exp(-((z-(lo-.014))/.019)**2)*w
 q.x-=.007*lip
 q.z+=(lo-.007-z)*.25*lip
 # Shallow philtrum, removing the bulbous upper-lip projection without moving nose.
 upper=math.exp(-((z-(hi+.016))/.019)**2)*w
 q.x-=.012*upper
 phil=smooth(-.123,-.107,z)*(1-smooth(-.091,-.075,z))*(1-smooth(.025,.067,abs(y)))*smooth(.27,.32,x)
 q.x-=.003*phil
 return q
def closed(p):
 q=refine_open(p);x,y,z=p;lo,hi=rims(y)
 width=1-smooth(.085,.125,abs(y));front=smooth(.15,.245,x);w=width*front
 if lo>=hi:return q
 seam=-.154+.008*min(1,(y/.10)**2)
 # Lip surface remap; fixed bottom anchor prevents the previous jaw compression.
 knots=[(-.265,-.265),(lo-.032,seam-.024),(lo-.018,seam-.011),(lo-.001,seam-.00035),
        (hi+.001,seam+.00035),(hi+.020,seam+.012),(-.075,-.075)]
 if all(knots[i+1][0]>knots[i][0] for i in range(len(knots)-1)):
  q.z=z+(lerpmap(z,knots)-z)*w
 # Bring both lips onto one depth profile, soften the lower-lip to chin transition.
 if -.265<z<-.075:
  depth_w=smooth(-.260,lo-.015,z)*(1-smooth(hi+.018,-.078,z))*w
  lower=max(0,seam-q.z);upper=max(0,q.z-seam)
  target=.331-7.0*y*y-.006*math.exp(-((q.z-seam)/.0028)**2)
  target-=.9*max(0,lower-.013)+.35*max(0,upper-.016)
  q.x=q.x*(1-depth_w)+target*depth_w
 return q
neutral=[closed(p) for p in original];opened=[refine_open(p) for p in original]
for key in keys:
 for i,v in enumerate(key.data):
  if key.name=='Basis':v.co=neutral[i]
  elif key.name=='jawOpen':v.co=opened[i]
  else:v.co=neutral[i]+(v.co-previous[i])
for v,p in zip(head.data.vertices,neutral):v.co=p
head.data.update()

def material(name,color,roughness):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=roughness
 return m
mucosa=material('Oral mucosa — muted warm rose',(.30,.075,.067),.48)
gum=material('Gums — muted coral',(.38,.115,.105),.5)
tongue_mat=material('Tongue — warm rose',(.40,.13,.125),.48)
head.data.materials.append(mucosa);idx=len(head.data.materials)-1;inside=[]
for poly in head.data.polygons:
 c=sum((original[i] for i in poly.vertices),Vector())/len(poly.vertices)
 lo,hi=rims(c.y)
 if abs(c.y)<.108 and -.02<c.x<(.294-7*c.y*c.y) and lo-.019<c.z<hi+.038:
  poly.material_index=idx;inside.append(poly.index)
gum_counts={}
for name,upper in [('02_Upper_dental_candidate',True),('03_Lower_dental_candidate',False)]:
 obj=bpy.data.objects[name];obj.data.materials.append(gum);gi=len(obj.data.materials)-1;n=0
 for poly in obj.data.polygons:
  if (upper and poly.center.z>-.103) or (not upper and poly.center.z<-.218):poly.material_index=gi;n+=1
 gum_counts[name]=n
obj=bpy.data.objects['06_Tongue_candidate'];obj.data.materials.clear();obj.data.materials.append(tongue_mat)
for poly in obj.data.polygons:poly.material_index=0

sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.cycles.samples=24
cam=sc.camera
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
camera((.10,0,0),(4,-.35,.12),1.30)
for name,frame in [('neutral',1),('jaw-open',98),('smile',124)]:
 sc.frame_set(frame);sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
sc.frame_set(1);camera((.2,0,-.15),(4,0,0),.52)
sc.render.filepath=str(OUT/'mouth-closeup.png');bpy.ops.render.render(write_still=True)
camera((.13,0,-.12),(3,-3,.02),.85)
sc.render.filepath=str(OUT/'mouth-angle.png');bpy.ops.render.render(write_still=True)
camera((.1,0,0),(4,-.35,.12),1.30);sc.frame_set(1)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.1,0,0);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.65;s.region_3d.view_perspective='ORTHO';s.shading.color_type='MATERIAL'
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,
 'oral_material_faces':len(inside),'gum_faces':gum_counts,'chin_anchor_max_error':max((p-q).length for p,q in zip(original,neutral) if p.z<=-.265)}
assert report['source_unchanged'] and report['chin_anchor_max_error']<1e-7
sc['RIG_STATUS']='V3 mouth refinement; closed lip rest, reduced lower lip, philtrum adjustment, mucosa material.'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_manual_face_rig_v3.blend'))
(OUT/'mouth-refinement-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('MOUTH_V3',json.dumps(report),flush=True)
