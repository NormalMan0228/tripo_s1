"""V2i: connected inner eyelid rims, medial lash seating, balanced profile and mouth motion."""
import bpy,math,json,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];SRC=R/'art/characters/explorer_b_face_rig_manual_v2h/explorer_living_face_v2h.blend';O=R/'art/characters/explorer_b_face_rig_manual_v2i';O.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1);h=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];oldmesh=h.data
shapes={k.name:[v.co.copy() for v in k.data] for k in oldmesh.shape_keys.key_blocks};base=shapes['Basis'];N=len(base);assert N==7530
start=N-688;cx=.1985
# A small eye advance closes the previous depth mismatch; retain fixed gaze envelope.
for side,sg in [('L',1),('R',-1)]:
 for name in ['Eye_white.'+side,'Iris_pupil.'+side]:
  o=bpy.data.objects[name]
  for v in o.data.vertices:v.co.x+=.0015
  for m in o.modifiers:
   if m.type=='NODES':
    for n in m.node_group.nodes:
     if n.bl_idname=='ShaderNodeVectorMath' and n.operation in ['ADD','SUBTRACT']:
      p=n.inputs[1].default_value
      if abs(p[0]-.197)<1e-6 and abs(p[1]-.149*sg)<1e-6 and abs(p[2]-.061)<1e-6:p[0]=cx
  o.data.update()
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for side in ['L','R']:
 b=rig.data.edit_bones['eye.'+side];b.head.x+=.0015;b.tail.x+=.0015
bpy.ops.object.mode_set(mode='OBJECT')
def smooth(a,b,t):
 t=max(0.,min(1.,(t-a)/(b-a)));return t*t*(3-2*t)
def profile(p):
 x,y,z=p;q=p.copy()
 front=smooth(.10,.245,x)
 lips=.029*math.exp(-(y/.115)**4-((z+.148)/.060)**4)
 chin=.018*math.exp(-(y/.135)**4-((z+.267)/.081)**4)
 cheek=.016*math.exp(-((abs(y)-.205)/.073)**2-((z+.036)/.072)**2)
 upperlip=.007*math.exp(-(y/.10)**4-((z+.127)/.023)**4)
 lowerchin=.012*math.exp(-(y/.12)**4)*(1-smooth(-.345,-.275,z))*smooth(-.40,-.35,z)
 q.x-=front*(lips+chin+cheek+upperlip+lowerchin)
 # Preserve eye clearance while rounding the cheek transition.
 if x>.12 and z>-.04:
  c=.149*(1 if y>0 else -1);inside=1-((y-c)/.083)**2-((z-.061)/.085)**2
  if inside>0:q.x=max(q.x,cx+.066*math.sqrt(inside)+.0080)
 return q
for name,coords in shapes.items():
 for i,p in enumerate(coords):
  q=profile(p)
  if i>=start and ((i-start)%344)//43>=6:
   q=p.copy()
  coords[i]=q
# Add TWO connected return rings to each existing 43-vertex eyelid aperture.
faces=[list(f.vertices) for f in oldmesh.polygons];materials=[f.material_index for f in oldmesh.polygons];rimids={}
for side,sg,off in [('R',-1,0),('L',1,344)]:
 outer=[start+off+7*43+j for j in range(43)];prev=outer
 for row in [1,2]:
  ring=list(range(len(shapes['Basis']),len(shapes['Basis'])+43))
  for name,coords in shapes.items():
   blink=int(name.split('_')[-1])/100 if name.startswith('IntegratedBlink_'+side+'_') else 0.
   for j,oi in enumerate(outer):
    p=coords[oi].copy();yb=p.y-.149*sg;zb=base[oi].z-.063
    radius=math.hypot(yb/.071,zb/.040);uy=yb/.071/max(radius,.001);uz=zb/.040/max(radius,.001)
    # Visible rounded margin, then a tucked posterior surface touching the globe.
    inset=(.0018 if row==1 else .0033)*(1-blink)
    p.y-=inset*uy;p.z-=inset*uz
    inside=1-((p.y-.149*sg)/.083)**2-((p.z-.061)/.085)**2
    globe=cx+.066*math.sqrt(max(.001,inside))
    p.x=globe+(.0018 if row==1 else -.0010)+.0055*blink
    coords.append(p)
  for j in range(43):
   k=(j+1)%43;faces.append([prev[j],ring[j],ring[k],prev[k]]);materials.append(len(oldmesh.materials))
  prev=ring
 rimids[side]={'outer':outer,'inner':ring}
# Keep morph drivers while rebuilding topology. All new faces share vertices with face skin.
drivers={fc.data_path:(fc.driver.expression,fc.driver.variables[0].targets[0].data_path) for fc in oldmesh.shape_keys.animation_data.drivers}
mesh=bpy.data.meshes.new('Face_with_connected_inner_lids_v2i');mesh.from_pydata(shapes['Basis'],[],faces)
for m in oldmesh.materials:mesh.materials.append(m)
rimmat=oldmesh.materials[0].copy();rimmat.name='Eyelid inner margin - warm skin';rimmat.diffuse_color=(.56,.43,.34,1)
p=rimmat.node_tree.nodes.get('Principled BSDF');col=list(p.inputs['Base Color'].default_value);p.inputs['Base Color'].default_value=(col[0]*.94,col[1]*.86,col[2]*.84,1);p.inputs['Roughness'].default_value=.48
mesh.materials.append(rimmat)
for f,mi in zip(mesh.polygons,materials):f.use_smooth=True;f.material_index=mi
h.data=mesh
for vg in list(h.vertex_groups):h.vertex_groups.remove(vg)
vg=h.vertex_groups.new(name='head');vg.add(list(range(len(shapes['Basis']))),1,'REPLACE')
for side,r in rimids.items():
 vg=h.vertex_groups.new(name='Connected_inner_eyelid_'+side);vg.add(r['outer']+r['inner'],1,'REPLACE')
for name,coords in shapes.items():
 key=h.shape_key_add(name=name)
 for v,p in zip(key.data,coords):v.co=p
 path='key_blocks["'+name+'"].value'
 if path in drivers:
  expr,prop=drivers[path];d=key.driver_add('value').driver;d.expression=expr;v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path=prop
# Keep oral components behind the rebalanced lips in every existing morph.
for o in sc.objects:
 if o.type=='MESH' and o.name.startswith(('02_','03_','06_')):
  if o.data.shape_keys:
   for k in o.data.shape_keys.key_blocks:
    for v in k.data:v.co=profile(v.co)
   for v,p in zip(o.data.vertices,o.data.shape_keys.key_blocks['Basis'].data):v.co=p.co
  else:
   for v in o.data.vertices:v.co=profile(v.co)
  o.data.update()
# Fit the medial lash segment to the actual upper lid, including all four blink targets.
lashstats={}
for side,sg,name in [('R',-1,'07_Upper_lash_candidate_negY'),('L',1,'08_Upper_lash_candidate_posY')]:
 o=bpy.data.objects[name];ks=o.data.shape_keys.key_blocks;old={k.name:np.array([v.co[:] for v in k.data]) for k in ks}
 indices=[i for i in rimids[side]['outer'] if base[i].z>.063]
 count=0
 for key in ks:
  headkey='Basis' if key.name=='Basis' else 'IntegratedBlink_'+side+'_'+key.name.split('_')[-1]
  coords=shapes[headkey];points=sorted([coords[i] for i in indices],key=lambda p:abs(p.y));ys=np.array([abs(p.y) for p in points])
  arr=old[key.name];neutral=old['Basis'];fixed=arr.copy()
  for i,p in enumerate(arr):
   ay=abs(neutral[i,1]);w=1-smooth(.103,.142,ay)
   if w<=0:continue
   y=max(abs(p[1]),float(ys.min())+.001)
   anchor=Vector((float(np.interp(y,ys,[p.x for p in points])),sg*y,float(np.interp(y,ys,[p.z for p in points]))))
   near=np.abs(np.abs(arr[:,1])-abs(p[1]))<.004
   floor=float(arr[near,2].min());median=float(np.median(arr[near,0]))
   target=anchor+Vector((.0015+np.clip(p[0]-median,-.002,.004)*.45,0,.0008+(p[2]-floor)*.60))
   fixed[i]=p*(1-w)+np.array(target)*w
   if key.name=='Basis':count+=1
  for v,p in zip(key.data,fixed):v.co=p
 for v,p in zip(o.data.vertices,ks['Basis'].data):v.co=p.co
 o.data.update();lashstats[side]=count
# Restore mouth articulation alongside the smooth eye action, keeping neutral lips closed.
oldaction=rig.animation_data.action;oldaction.use_fake_user=True;rig.animation_data.action=oldaction.copy();action=rig.animation_data.action;action.name='Face gaze blink and mouth - 12s loop'
def ease(t):return t*t*t*(t*(t*6-15)+10)
def track(f,pts):
 for (a,x),(b,y) in zip(pts,pts[1:]):
  if a<=f<=b:return float(x+(y-x)*ease((f-a)/(b-a)))
 return float(pts[-1][1])
tracks={'jaw_open':[(1,0),(74,0),(87,.16),(98,.48),(109,.08),(122,.30),(138,0),(198,0),(210,.16),(224,.08),(237,0),(289,0)],'smile':[(1,0),(25,0),(48,.28),(70,.14),(92,.06),(139,0),(159,.30),(179,.16),(195,0),(247,.12),(271,0),(289,0)],'pucker':[(1,0),(198,0),(211,.24),(226,.12),(240,0),(289,0)],'frown':[(1,0),(289,0)]}
for f in range(1,290):
 for prop,pts in tracks.items():rig[prop]=track(f,pts);rig.keyframe_insert(data_path='["'+prop+'"]',frame=f)
for prop in ['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']:rig[prop]=float(rig[prop])
for fc in action.fcurves:
 fc.update_autoflags(rig)
 for k in fc.keyframe_points:k.interpolation='LINEAR'
sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update();sc.render.resolution_x=760;sc.render.resolution_y=760;sc.cycles.samples=20;sc.cycles.use_denoising=True
cam=sc.camera
def camera(target,offset,scale):
 t=Vector(target);cam.location=t+Vector(offset);cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name):sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
camera((.13,0,0),(4,-.3,.08),1.24)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.14,0,.01);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.18;s.region_3d.view_perspective='ORTHO'
F=O/'explorer_lids_profile_v2i.blend';bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(F));render('neutral')
hidden=[]
for o in sc.objects:
 if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
for f,label in [(1,'open'),(55,'half'),(56,'closed')]:
 sc.frame_set(f);camera((.22,-.149,.07),(4,-.3,0),.30);render('eye-'+label)
sc.frame_set(1);camera((.23,-.149,.064),(1.4,-4,0),.28);render('eye-oblique')
camera((.26,0,-.13),(0,-4,0),.52);render('profile')
sc.frame_set(98);camera((.26,0,-.16),(4,-.3,0),.42);render('mouth-open')
for o in hidden:o.hide_render=False
sc.frame_set(1);camera((.13,0,0),(4,-.3,.08),1.24)
report={'source':str(SRC),'api_credits':0,'eye_center_x':cx,'connected_inner_lid_faces':172,'medial_lash_vertices_adjusted':lashstats,'animation_frames':288,'fps':24,'mouth_animation_restored':True,'status':'pending verification'}
(O/'refinement-report.json').write_text(json.dumps(report,indent=2))
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS');txt.clear();txt.write('V2i connected inner eyelids, seated medial lashes and balanced profile\nTwo return loops per eye create genuine connected inner lid surfaces. Eyes advanced 0.0015. Medial lashes fitted separately for neutral and every blink key. Lips/chin and cheek projection softened; oral parts adjusted with them.\nSpace: 12-second combined gaze/blink/mouth demonstration. Neutral frame 1 keeps lips closed. Rig properties remain floating point for continuous animation.\nPrototype: arbitrary extreme facial combinations and game export require further validation.\n')
bpy.ops.wm.save_as_mainfile(filepath=str(F));print('V2I_BUILT',flush=True)
