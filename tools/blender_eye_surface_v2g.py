"""Replace accumulated socket rings with a clean broad patch and slow inspection action."""
import bpy,math,json,collections,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];SRC=R/'art/characters/explorer_b_face_rig_manual_v2f/explorer_orbit_gaze_v2f.blend';O=R/'art/characters/explorer_b_face_rig_manual_v2g';O.mkdir(exist_ok=True)
sha=hashlib.sha256(SRC.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1)
h=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];oldmesh=h.data;oldshapes={k.name:[v.co.copy() for v in k.data] for k in oldmesh.shape_keys.key_blocks};base=oldshapes['Basis'];faces=[list(f.vertices) for f in oldmesh.polygons]
drivers={fc.data_path:(fc.driver.expression,fc.driver.variables[0].targets[0].data_path) for fc in oldmesh.shape_keys.animation_data.drivers}
patches={};remove=set()
for side,sign in [('R',-1),('L',1)]:
 selected=set()
 for j,f in enumerate(faces):
  c=sum((base[i] for i in f),Vector())/len(f)
  if c.x>.08 and c.y*sign>.028 and ((c.y-.149*sign)/.111)**2+((c.z-.063)/.097)**2<1:selected.add(j)
 counts=collections.Counter(tuple(sorted((a,b))) for j in selected for f in [faces[j]] for a,b in zip(f,f[1:]+f[:1]));adj=collections.defaultdict(list)
 for (a,b),n in counts.items():
  if n==1:adj[a].append(b);adj[b].append(a)
 assert all(len(v)==2 for v in adj.values());todo=set(adj);loops=[]
 while todo:
  start=min(todo);loop=[start];prev=None
  while True:
   nxt=next(i for i in adj[loop[-1]] if i!=prev)
   if nxt==start:break
   prev=loop[-1];loop.append(nxt)
  loops.append(loop);todo.difference_update(loop)
 assert len(loops)==2
 loop=max(loops,key=lambda loop:sum(((base[i].y-.149*sign)/.111)**2+((base[i].z-.063)/.097)**2 for i in loop)/len(loop))
 if sum(base[a].y*base[b].z-base[b].y*base[a].z for a,b in zip(loop,loop[1:]+loop[:1]))<0:loop.reverse()
 raw=np.unwrap([math.atan2((base[i].z-.063)/.097,(base[i].y-.149*sign)/.111) for i in loop]);n=len(loop)
 angles=[float(sum(raw[(i+d)%n]+math.floor((i+d)/n)*2*math.pi for d in [-1,0,1])/3) for i in range(n)]
 assert all(angles[j+1]>angles[j] for j in range(n-1))
 patches[side]={'outer':loop,'angles':angles,'sign':sign};remove.update(selected)

advance=.012;cx=.185+advance;clearance=.0035
# Keep the nonmoving socket boundary outside the advanced eye as well.
for coords in oldshapes.values():
 for p in coords:
  if p.x>.12 and -.035<p.z<.16:
   cy=.149*(1 if p.y>0 else -1);inside=1-((p.y-cy)/.083)**2-((p.z-.061)/.085)**2
   if inside>0:p.x=max(p.x,cx+.066*math.sqrt(inside)+.004)
outer_normals=collections.defaultdict(Vector)
for j,f in enumerate(faces):
 if j in remove:continue
 a,b,c=(base[i] for i in f[:3]);normal=(b-a).cross(c-a)
 for i in f:outer_normals[i]+=normal
for side,sign in [('L',1),('R',-1)]:
 for name in ['Eye_white.'+side,'Iris_pupil.'+side]:
  o=bpy.data.objects[name]
  for v in o.data.vertices:v.co.x+=advance
  for mod in o.modifiers:
   if mod.type=='NODES':
    for node in mod.node_group.nodes:
     if node.bl_idname=='ShaderNodeVectorMath' and node.operation in ['ADD','SUBTRACT']:
      p=node.inputs[1].default_value
      if abs(p[0]-.185)<1e-6 and abs(p[1]-.149*sign)<1e-6 and abs(p[2]-.061)<1e-6:p[0]+=advance
  o.data.update()
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for side in ['L','R']:
 b=rig.data.edit_bones['eye.'+side];b.head.x+=advance;b.tail.x+=advance
bpy.ops.object.mode_set(mode='OBJECT')
def edge(side,a,blink):
 sign=patches[side]['sign'];cy=.149*sign;u=math.cos(a);s=math.sin(a)
 y=cy+.071*u;z=.063+(.043 if s>=0 else .032)*s+.002*u*sign
 seam=.059+.0015*u*u;z=z*(1-blink)+(seam+(-.0002 if s>=0 else .0002))*blink
 inside=1-((y-cy)/.083)**2-((z-.061)/.085)**2
 return Vector((cx+.066*math.sqrt(max(.001,inside))+clearance+.003*blink,y,z))
def point(side,j,t,blink,outer):
 end=edge(side,patches[side]['angles'][j],blink);p=outer.lerp(end,t)
 n=outer_normals[patches[side]['outer'][j]]
 m0=-(n.y*(end.y-outer.y)+n.z*(end.z-outer.z))/n.x if abs(n.x)>1e-10 else end.x-outer.x
 m0=max(-.04,min(.04,m0));m1=end.x-outer.x
 p.x=(2*t**3-3*t*t+1)*outer.x+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*end.x+(t**3-t*t)*m1
 cy=.149*patches[side]['sign'];inside=1-((p.y-cy)/.083)**2-((p.z-.061)/.085)**2
 if inside>0:
  surface=cx+.066*math.sqrt(inside)+clearance+.003*blink;d=p.x-surface
  p.x=surface+.5*(d+math.sqrt(d*d+.0000002))
 return p
allbase=[p.copy() for p in base];newfaces=[f for j,f in enumerate(faces) if j not in remove];newinfo={}
for side,pa in patches.items():
 prev=pa['outer'];n=len(prev);rings=[]
 for row in range(1,9):
  t=row/8;ring=[]
  for j,oi in enumerate(pa['outer']):
   idx=len(allbase);allbase.append(point(side,j,t,0,base[oi]));ring.append(idx);newinfo[idx]=(side,j,t,oi)
  for j in range(n):
   k=(j+1)%n;newfaces.append([prev[j],ring[j],ring[k],prev[k]])
  prev=ring;rings.append(ring)
 pa['inner']=ring;pa['rings']=rings
used=sorted({i for f in newfaces for i in f});remap={i:j for j,i in enumerate(used)}
mesh=bpy.data.meshes.new('Face_clean_orbital_surface_v2g');mesh.from_pydata([allbase[i] for i in used],[],[[remap[i] for i in f] for f in newfaces])
for mat in oldmesh.materials:mesh.materials.append(mat)
for f in mesh.polygons:f.use_smooth=True
h.data=mesh
for vg in list(h.vertex_groups):h.vertex_groups.remove(vg)
vg=h.vertex_groups.new(name='head');vg.add(list(range(len(used))),1,'REPLACE')
for name,coords in oldshapes.items():
 key=h.shape_key_add(name=name)
 for v,i in zip(key.data,used):
  if i not in newinfo:v.co=coords[i]
  else:
   side,j,t,oi=newinfo[i];blink=int(name.split('_')[-1])/100 if name.startswith('IntegratedBlink_'+side+'_') else 0
   p=point(side,j,t,blink,coords[oi]);v.co=p
 path='key_blocks["'+name+'"].value'
 if path in drivers:
  expr,prop=drivers[path];d=key.driver_add('value').driver;d.expression=expr;var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path=prop

# Original lash silhouette remains; bind each blink to the rebuilt upper edge.
for side,name in [('L','08_Upper_lash_candidate_posY'),('R','07_Upper_lash_candidate_negY')]:
 o=bpy.data.objects[name];keys=o.data.shape_keys.key_blocks;neutral=[v.co.copy()+Vector((.004,0,-.002)) for v in keys['Basis'].data]
 angles=patches[side]['angles'];indices=sorted([j for j,a in enumerate(angles) if math.sin(a)>=0],key=lambda j:edge(side,angles[j],0).y)
 def anchor(y,b):
  points=[edge(side,angles[j],b) for j in indices];ys=[p.y for p in points]
  return Vector((float(np.interp(y,ys,[p.x for p in points])),y,float(np.interp(y,ys,[p.z for p in points]))))
 for v,p in zip(keys['Basis'].data,neutral):v.co=p
 for k in range(1,5):
  amount=k/4
  for v,p in zip(keys['Blink_'+str(k*25)].data,neutral):
   root=anchor(p.y,0);off=p-root;off.x*=1-.60*amount;off.z*=1-.50*amount;v.co=anchor(p.y,amount)+off
 for v,p in zip(o.data.vertices,neutral):v.co=p
 o.data.update()

# Slow, held inspection poses. Preserve the previous action as an alternate take.
oldaction=rig.animation_data.action;oldaction.use_fake_user=True;rig.animation_data.action=None
props=['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']
poses=[(1,{}),(48,{}),(84,{'blink_L':1,'blink_R':1}),(108,{'blink_L':1,'blink_R':1}),(144,{}),(180,{}),(228,{'look_lr':-1}),(276,{'look_lr':-1}),(324,{}),(360,{}),(408,{'look_lr':1}),(456,{'look_lr':1}),(504,{}),(528,{}),(564,{'look_ud':.7}),(600,{'look_ud':.7}),(636,{'look_ud':-.7}),(672,{'look_ud':-.7}),(708,{}),(744,{})]
for frame,values in poses:
 for prop in props:rig[prop]=values.get(prop,0.);rig.keyframe_insert(data_path='["'+prop+'"]',frame=frame)
rig.animation_data.action.name='Eye inspection - 31 seconds with pose holds'
for fc in rig.animation_data.action.fcurves:
 for key in fc.keyframe_points:key.interpolation='BEZIER';key.handle_left_type='AUTO_CLAMPED';key.handle_right_type='AUTO_CLAMPED'
sc.render.fps=24;sc.frame_start=1;sc.frame_end=744;sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
sc.render.resolution_x=720;sc.render.resolution_y=720;sc.cycles.samples=16;c=sc.camera
def camera(target,offset,scale):
 t=Vector(target);c.location=t+Vector(offset);c.rotation_euler=(t-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=scale
hidden=[]
for o in sc.objects:
 if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
for f,label in [(1,'neutral'),(66,'half'),(96,'closed'),(240,'left'),(420,'right')]:
 sc.frame_set(f)
 for off,view in [((4,-.4,0),'front'),((1.1,-4,.04),'side')]:
  camera((.22,-.149,.066),off,.35);sc.render.filepath=str(O/('eye-'+label+'-'+view+'.png'));bpy.ops.render.render(write_still=True)
for o in hidden:o.hide_render=False
sc.frame_set(1);camera((.12,0,0),(4,-.35,.12),1.3);sc.render.filepath=str(O/'neutral.png');bpy.ops.render.render(write_still=True)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.14,0,.03);s.region_3d.view_rotation=c.rotation_euler.to_quaternion();s.region_3d.view_distance=1.15;s.region_3d.view_perspective='ORTHO';s.overlay.show_overlays=False
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS');txt.clear();txt.write('V2g clean eye surface and slow inspection\nEight clean orbital loops replace the accumulated socket patches. Eye centers advanced 0.012; thin lid contact margin 0.0035. Original head outside the orbital patch, mouth, and hair preserved.\nSpace plays a 31-second eye inspection with long neutral/closed/left/right/up/down holds. The previous 240-frame action remains available.\nGaze remains normalized-sphere rotation with a stable ellipsoid envelope; live Geometry Nodes need baking or equivalent engine logic for export.\n')
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,'eye_center_x':cx,'eye_advance':advance,'lid_clearance':clearance,'removed_orbital_faces':len(remove),'outer_boundary_vertices':{s:len(p['outer']) for s,p in patches.items()},'new_loops_per_eye':8,'inspection_frames':744,'inspection_fps':24,'inspection_seconds':31,'previous_action_preserved':oldaction.name}
(O/'eye-surface-report.json').write_text(json.dumps(report,indent=2));bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(O/'explorer_clean_eyes_v2g.blend'));print('EYES_V2G_SAVED',flush=True)
