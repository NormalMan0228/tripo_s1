"""Local lip corrections, unfolded welded eyelids, and edge-bound original lashes."""
import bpy,math,json,hashlib,collections
import numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1]
SRC=R/'art/characters/explorer_b_face_rig_manual_v2d/explorer_expression_v2d.blend'
OUT=R/'art/characters/explorer_b_face_rig_manual_v2e';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1)
head=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
keys=head.data.shape_keys.key_blocks;old={k.name:[v.co.copy() for v in k.data] for k in keys};base=old['Basis']
report0=json.loads((R/'art/characters/explorer_b_face_rig_manual_v2c/integrated-eye-report.json').read_text())
retained={int(i):j for i,j in report0['retained_source_mapping'].items()};added=sorted(set(range(len(base)))-set(retained))
adj=collections.defaultdict(set)
for f in head.data.polygons:
 vs=list(f.vertices)
 for a,b in zip(vs,vs[1:]+vs[:1]):adj[a].add(b);adj[b].add(a)
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)

# Keep the forward apex while flattening excessive side-on globe bulge.
eye_cx=.185;eye_rx=.066
for side in ('L','R'):
 for name in ['Eye_white.'+side,'Iris_pupil.'+side]:
  o=bpy.data.objects[name]
  for v in o.data.vertices:v.co.x=eye_cx+(v.co.x-.156)*(eye_rx/.095)
  o.data.update()
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for side in ('L','R'):
 b=rig.data.edit_bones['eye.'+side];b.head.x+=.029;b.tail.x+=.029
bpy.ops.object.mode_set(mode='OBJECT')

# Correct the lower lip contour without moving the closed contact seam or the chin.
mouth_delta={}
for i,p in enumerate(base):
 x,y,z=p;q=Vector()
 if x>.205 and abs(y)<.15 and -.28<z<-.10:
  front=smooth(.205,.28,x)
  ridge=-.197+.028*(y/.083)**2
  q.z=.017*math.exp(-((z-ridge)/.020)**2-(y/.065)**4)*front*(1-smooth(-.175,-.160,z))
  q.x=.011*math.exp(-((z+.217)/.032)**2-(y/.083)**4)*front
  # Fill the small pinched commissure depression into the cheek, tapering broadly.
  w=math.exp(-((abs(y)-.094)/.022)**2-((z+.153)/.019)**2)*smooth(.205,.255,x)
  target=.342-5.0*y*y
  q.x+=max(0,target-x)*.88*w
  mouth_delta[i]=q
# Shallow, rounded labiomental transition instead of a compressed V/U ridge.
for i,d in mouth_delta.items():
 p=base[i]+d;x,y,z=p
 if z<-.162:
  w=(1-smooth(.075,.13,abs(y)))*smooth(-.28,-.24,z)*(1-smooth(-.17,-.159,z))
  profile=float(np.interp(z,[-.28,-.25,-.225,-.20,-.185,-.17,-.16],[.316,.318,.321,.326,.334,.341,.342]))-4.5*y*y
  d.x+=(profile-x)*w*.94*smooth(.18,.29,x)
for k in keys:
 for i,d in mouth_delta.items():
  # Open-jaw expression receives the surface fill but not neutral closure compression.
  k.data[i].co+=d if k.name!='jawOpen' else Vector((d.x*.65,0,0))

# Smooth the compressed corner fans and lower lip transition on their actual connectivity.
points=[v.co.copy() for v in keys['Basis'].data];pre=[p.copy() for p in points];mw={}
for i,p in enumerate(points):
 x,y,z=p
 if -.27<z<-.095 and abs(y)<.15 and x>.18:
  corner=math.exp(-((abs(y)-.090)/.028)**2-((z+.16)/.028)**2)*.65
  below=.25*math.exp(-(y/.080)**4-((z+.204)/.031)**2)
  mw[i]=max(corner,below)*smooth(.18,.28,x)
for repeat in range(20):
 updates={i:points[i]+(sum((points[j] for j in adj[i]),Vector())/len(adj[i])-points[i])*w for i,w in mw.items()}
 for i,p in updates.items():points[i]=p
for k in keys:
 for i in mw:k.data[i].co+=(points[i]-pre[i])*(.3 if k.name=='jawOpen' else 1)

# Re-space every eyelid ring: the old annulus doubled back around the upper rim.
# New apertures stay inside the outer boundary in the frontal projection.
patches={};off=0;curves={}
for side,n in report0['shared_boundary_edges'].items():
 ids=np.array(added[off:off+10*n]).reshape(10,n).tolist();off+=10*n
 outer=[next(j for j in adj[i] if j in retained) for i in ids[0]]
 sign=1 if side=='L' else -1;cy=.149*sign
 angles=[math.atan2((base[i].z-.061)/(.053 if base[i].z>.061 else .043),(base[i].y-cy)/.077) for i in ids[-1]]
 inners=[]
 for a in angles:
  u=math.cos(a);s=math.sin(a)
  inners.append(Vector((0,cy+.0645*u,.063+(.046 if s>=0 else .033)*s+.002*u*sign)))
 def globe(p,margin=.006):
  return eye_cx+eye_rx*math.sqrt(max(.001,1-((p.y-cy)/.083)**2-((p.z-.061)/.085)**2))+margin
 samples=[]
 for amount in [0,.25,.50,.75,1]:
  pts=[]
  for j,a in enumerate(angles):
   p=inners[j].copy();seam=.057+.002*math.cos(a)**2
   p.z=p.z*(1-amount)+(seam+(0.00015 if math.sin(a)>0 else -0.00015))*amount
   p.x=globe(p);pts.append(p)
  samples.append(pts)
 curves[side]={'angles':angles,'samples':samples}
 for k in keys:
  amount=0
  if k.name.startswith('IntegratedBlink_'+side+'_'):amount=int(k.name.split('_')[-1])//25
  for r in range(10):
   t=(r+1)/10
   for j,idx in enumerate(ids[r]):
    start=base[outer[j]];end=samples[amount][j];p=start.lerp(end,t)
    # Soft maximum keeps the skin outside the eye without a hard clamp ridge.
    surface=globe(p,.006)
    if p.x<surface+.002 and t<.999:
     d=p.x-surface;p.x=surface+.5*(d+math.sqrt(d*d+.000006))
    if k.name not in ['Basis'] and not k.name.startswith('IntegratedBlink_'):
     p+=(old[k.name][outer[j]]-base[outer[j]])*(1-t)**2
    k.data[idx].co=p
 patches[side]={'rings':ids,'outer':outer}

# Relax the depth of the surrounding orbital skin, including the old socket crease.
# Keep the well-spaced Y/Z loops and aperture fixed; only the forward depth is relaxed.
weights={}
for i in retained:
 p=base[i];cy=.149*(1 if p.y>0 else -1)
 if p.x>.14 and -.045<p.z<.23 and .04<abs(p.y)<.29:
  weights[i]=math.exp(-((p.y-cy)/.105)**4-((p.z-.071)/.102)**4)*.6
for side,patch in patches.items():
 for r,ids in enumerate(patch['rings'][:-1]):
  for i in ids:weights[i]=.6*(1-r/10)
for k in keys:
 xx=np.array([v.co.x for v in k.data])
 for repeat in range(36):
  updated={i:xx[i]+w*(sum(xx[j] for j in adj[i])/len(adj[i])-xx[i]) for i,w in weights.items()}
  for i,x in updated.items():xx[i]=x
 for i,x in enumerate(xx):
  if i in weights:
   p=k.data[i].co;cy=.149*(1 if p.y>0 else -1)
   inside=1-((p.y-cy)/.083)**2-((p.z-.061)/.085)**2
   if inside>0:x=max(x,eye_cx+eye_rx*math.sqrt(inside)+.006)
   p.x=x
# Refresh the binding curves from the actual final eyelid vertices.
for side,patch in patches.items():
 for k in range(5):
  key=keys['Basis' if k==0 else 'IntegratedBlink_'+side+'_'+str(k*25)]
  curves[side]['samples'][k]=[key.data[i].co.copy() for i in patch['rings'][-1]]

# Attach the ORIGINAL eyelash meshes to actual upper lid-edge samples.
# Each vertex keeps a local offset in the moving edge frame (no separate blink formula).
bind_errors={}
for side,lname in [('L','08_Upper_lash_candidate_posY'),('R','07_Upper_lash_candidate_negY')]:
 obj=bpy.data.objects[lname];lk=obj.data.shape_keys.key_blocks;source=[v.co.copy() for v in lk['Basis'].data]
 c=curves[side];upper=[j for j,a in enumerate(c['angles']) if math.sin(a)>=0]
 upper.sort(key=lambda j:c['samples'][0][j].y)
 def curve(k,y,original=False):
  pts=[base[patches[side]['rings'][-1][j]] if original else c['samples'][k][j] for j in upper];ys=[p.y for p in pts]
  j=max(0,min(len(pts)-2,int(np.searchsorted(ys,y))-1));u=max(0,min(1,(y-ys[j])/(ys[j+1]-ys[j])))
  p=pts[j].lerp(pts[j+1],u)
  tangent=(pts[j+1]-pts[j]).normalized()
  cy=.149*(1 if side=='L' else -1)
  normal=Vector(((p.x-.156)/(.095**2),(p.y-cy)/(.083**2),(p.z-.061)/(.085**2))).normalized()
  normal=(normal-tangent*normal.dot(tangent)).normalized();across=normal.cross(tangent).normalized()
  frame=Matrix((normal,tangent,across)).transposed()
  return p,frame
 coords=[[] for _ in range(5)]
 for p in source:
  sign=1 if side=='L' else -1;ay=abs(p.y)
  y=p.y
  root,frame=curve(0,p.y);root.y=p.y
  offset=p-root+Vector((.002,0,-.003))
  for k in range(5):
   anchor,fr=curve(k,y);anchor.y=y;coords[k].append(anchor+offset)
 for k,keyname in enumerate(['Basis','Blink_25','Blink_50','Blink_75','Blink_100']):
  for v,p in zip(lk[keyname].data,coords[k]):v.co=p
 for v,p in zip(obj.data.vertices,coords[0]):v.co=p
 obj.data.update();bind_errors[side]={'original_vertices':len(source),'binding':'upper lid curve local frames; all four keys use the same anchors'}
for v,p in zip(head.data.vertices,keys['Basis'].data):v.co=p.co
head.data.update();sc.frame_set(2);sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.cycles.samples=24
cam=sc.camera
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name,hidehair=False):
 hidden=[]
 if hidehair:
  for o in sc.objects:
   if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
 sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 for o in hidden:o.hide_render=False
camera((.25,0,-.17),(4,0,0),.38);render('mouth-front')
camera((.24,0,-.16),(.25,-4,0),.48);render('mouth-profile',True)
for frame,label in [(1,'open'),(15,'half'),(18,'closed')]:
 sc.frame_set(frame)
 camera((.20,-.149,.070),(4,-.4,0),.30);render('eye-'+label+'-front',True)
 camera((.20,-.149,.070),(1.3,-4,.08),.34);render('eye-'+label+'-side',True)
sc.frame_set(1);camera((.1,0,0),(4,-.35,.12),1.3);render('neutral')
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.1,0,.02);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.4;s.region_3d.view_perspective='ORTHO'
sc['RIG_STATUS']='V2e: local mouth contour correction; unfolded eyelid annulus; original lashes bound to lid curves.'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_face_contours_v2e.blend'))
(OUT/'correction-report.json').write_text(json.dumps({'source':str(SRC),'credits':0,'lashes':bind_errors,'mouth_affected_vertices':len(mouth_delta),'eye_rings_rebuilt':680,'status':'awaiting rendered review'},indent=2))
print('FACE_V2E_SAVED',flush=True)
