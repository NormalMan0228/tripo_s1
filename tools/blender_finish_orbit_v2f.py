import bpy,math,json,collections,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_face_rig_manual_v2f';F=O/'explorer_orbit_gaze_v2f.blend'
bpy.ops.wm.open_mainfile(filepath=str(F));sc=bpy.context.scene;sc.frame_set(1);h=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];ks=h.data.shape_keys.key_blocks
base=np.array([v.co[:] for v in ks['Basis'].data]);faces=[list(p.vertices) for p in h.data.polygons]
ec=collections.Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]));boundary={i for e,n in ec.items() if n==1 for i in e};adj=collections.defaultdict(set)
for a,b in ec:adj[a].add(b);adj[b].add(a)
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
weights={}
for i,(x,y,z) in enumerate(base):
 if i in boundary or x<.11 or not -.06<z<.20:continue
 cy=.149*(1 if y>0 else -1);dy=y-cy;dz=z-.063
 outer=math.sqrt((dy/.116)**2+(dz/.105)**2)
 if outer<1:weights[i]=.42*(1-smooth(.70,1,outer))
ids=np.array(list(weights));wi=np.array([weights[i] for i in ids])[:,None]
maxn=max(len(adj[i]) for i in ids);nbr=np.array([list(adj[i])+[i]*(maxn-len(adj[i])) for i in ids]);mask=np.array([[1]*len(adj[i])+[0]*(maxn-len(adj[i])) for i in ids])[:,:,None]
def folded(coords):
 out=[]
 for j,f in enumerate(faces):
  a=coords[f];c=a.mean(0)
  if c[0]>.13 and abs(abs(c[1])-.149)<.095 and -.025<c[2]<.15:
   n=np.cross(a[1]-a[0],a[2]-a[0])
   if n[0]>1e-9:out.append(j)
 return out
before=folded(base);seeds=set()
for f in faces:
 a=base[f];c=a.mean(0);n=np.cross(a[1]-a[0],a[2]-a[0])
 if max(f)<len(base)-682 and c[0]>.13 and abs(abs(c[1])-.149)<.10 and -.005<c[2]<.09 and n[0]>1e-9:seeds.update(f)
selected={j for j,f in enumerate(faces) if any(i in seeds for i in f)}
remaining=collections.Counter(tuple(sorted((a,b))) for j,f in enumerate(faces) if j not in selected for a,b in zip(f,f[1:]+f[:1]))
region={i for j in selected for i in faces[j]};edges=[e for e,n in remaining.items() if n==1 and all(i in region for i in e)];ad=collections.defaultdict(list)
for a,b in edges:ad[a].append(b);ad[b].append(a)
assert all(len(v)==2 for v in ad.values());todo=set(ad);loops=[]
while todo:
 first=min(todo);loop=[first];prev=None
 while True:
  nxt=next(i for i in ad[loop[-1]] if i!=prev)
  if nxt==first:break
  prev=loop[-1];loop.append(nxt)
 todo.difference_update(loop);loops.append(loop)
newfaces=[f for j,f in enumerate(faces) if j not in selected]
for loop in loops:
 poly=[Vector((0,base[i,1],base[i,2])) for i in loop]
 tri=tessellate_polygon([poly]);assert len(tri)==len(loop)-2
 for t in tri:
  f=[loop[v] if isinstance(v,int) else loop[min(range(len(poly)),key=lambda i:(poly[i]-v).length_squared)] for v in t]
  a=base[f]
  if np.cross(a[1]-a[0],a[2]-a[0])[0]>0:f.reverse()
  newfaces.append(f)
shapes={k.name:[v.co.copy() for v in k.data] for k in ks}
drivers={fc.data_path:(fc.driver.expression,fc.driver.variables[0].targets[0].data_path) for fc in h.data.shape_keys.animation_data.drivers}
used=sorted({i for f in newfaces for i in f});remap={i:j for j,i in enumerate(used)}
mesh=bpy.data.meshes.new('Face_skin_orbit_local_patch_repair');mesh.from_pydata([base[i] for i in used],[],[[remap[i] for i in f] for f in newfaces])
for mat in h.data.materials:mesh.materials.append(mat)
for f in mesh.polygons:f.use_smooth=True
h.data=mesh
for vg in list(h.vertex_groups):h.vertex_groups.remove(vg)
vg=h.vertex_groups.new(name='head');vg.add(list(range(len(used))),1,'REPLACE')
for name,coords in shapes.items():
 k=h.shape_key_add(name=name)
 for v,i in zip(k.data,used):v.co=coords[i]
 path='key_blocks["'+name+'"].value'
 if path in drivers:
  expression,prop=drivers[path];d=k.driver_add('value').driver;d.expression=expression;var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path=prop
after=[];print('LOCAL_ORBIT_PATCHES',len(loops),'replaced',len(selected),flush=True)

# Post-scaling operates in the posed head frame, so head/root rotation stays correct too.
anchor=bpy.data.objects.new('Gaze_head_pose_anchor',None);sc.collection.objects.link(anchor)
con=anchor.constraints.new('COPY_TRANSFORMS');con.target=rig;con.subtarget='head'
frame=bpy.data.objects.new('Gaze_head_deformation_frame',None);sc.collection.objects.link(frame);frame.parent=anchor;frame.matrix_local=rig.data.bones['head'].matrix_local.inverted()
anchor.hide_render=True;frame.hide_render=True;anchor.hide_set(True);frame.hide_set(True)
for side in ['L','R']:
 for name in ['Eye_white.'+side,'Iris_pupil.'+side]:
  o=bpy.data.objects[name];ng=o.modifiers['Gaze 3 - restore fixed eye envelope'].node_group
  pos=next(n for n in ng.nodes if n.bl_idname=='GeometryNodeInputPosition');sub=next(n for n in ng.nodes if n.bl_idname=='ShaderNodeVectorMath' and n.operation=='SUBTRACT');add=next(n for n in ng.nodes if n.bl_idname=='ShaderNodeVectorMath' and n.operation=='ADD');setp=next(n for n in ng.nodes if n.bl_idname=='GeometryNodeSetPosition')
  info=ng.nodes.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=frame;info.transform_space='RELATIVE'
  minus=ng.nodes.new('ShaderNodeVectorMath');minus.operation='SUBTRACT';invrot=ng.nodes.new('ShaderNodeVectorRotate');invrot.rotation_type='EULER_XYZ';invrot.invert=True
  divide=ng.nodes.new('ShaderNodeVectorMath');divide.operation='DIVIDE';mult=ng.nodes.new('ShaderNodeVectorMath');mult.operation='MULTIPLY';rot=ng.nodes.new('ShaderNodeVectorRotate');rot.rotation_type='EULER_XYZ';plus=ng.nodes.new('ShaderNodeVectorMath');plus.operation='ADD'
  for src,dst in [(pos.outputs['Position'],minus.inputs[0]),(info.outputs['Location'],minus.inputs[1]),(minus.outputs['Vector'],invrot.inputs['Vector']),(info.outputs['Rotation'],invrot.inputs['Rotation']),(invrot.outputs['Vector'],divide.inputs[0]),(info.outputs['Scale'],divide.inputs[1]),(divide.outputs['Vector'],sub.inputs[0]),(add.outputs['Vector'],mult.inputs[0]),(info.outputs['Scale'],mult.inputs[1]),(mult.outputs['Vector'],rot.inputs['Vector']),(info.outputs['Rotation'],rot.inputs['Rotation']),(rot.outputs['Vector'],plus.inputs[0]),(info.outputs['Location'],plus.inputs[1]),(plus.outputs['Vector'],setp.inputs['Position'])]:ng.links.new(src,dst)
sc.frame_set(2);sc.frame_set(1);bpy.context.view_layer.update()
action=rig.animation_data.action;rig.animation_data.action=None
props=['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']
def pose(vals):
 for p in props:rig[p]=vals.get(p,0.)
 rig.update_tag();bpy.context.view_layer.update()
cam=sc.camera
def camera(offset):
 t=Vector((.2,-.149,.065));cam.location=t+Vector(offset);cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.35
hidden=[]
for obj in sc.objects:
 if obj.type=='MESH' and obj.name.startswith(('Hair','Nape')) and not obj.hide_render:obj.hide_render=True;hidden.append(obj)
for label,vals in [('neutral',{}),('left',{'look_lr':-1}),('right',{'look_lr':1}),('half',{'blink_L':.5,'blink_R':.5}),('closed',{'blink_L':1,'blink_R':1})]:
 pose(vals)
 for view,offset in [('front',(4,-.4,0)),('side',(1.1,-4,.04))]:
  camera(offset);sc.render.filepath=str(O/('eye-'+label+'-'+view+'.png'))
  if '--quick' not in sys.argv:bpy.ops.render.render(write_still=True)
pose({})
for obj in hidden:obj.hide_render=False
t=Vector((.1,0,0));cam.location=t+Vector((4,-.35,.12));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.3
sc.render.filepath=str(O/'neutral.png')
if '--quick' not in sys.argv:bpy.ops.render.render(write_still=True)
rig.animation_data.action=action;sc.frame_set(1)
report=json.loads((O/'orbit-gaze-report.json').read_text());report.update(local_orbital_repair_patches=len(loops),overlapping_orbital_faces_replaced=len(selected),head_pose_compensated=True)
(O/'orbit-gaze-report.json').write_text(json.dumps(report,indent=2))
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(F));print('ORBIT_FINISH_SAVED',flush=True)
