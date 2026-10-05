"""Fill the broad orbital trough; rotate gaze in normalized ellipsoid space."""
import bpy,math,json,hashlib,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];SRC=R/'art/characters/explorer_b_face_rig_manual_v2e/explorer_face_contours_v2e.blend'
O=R/'art/characters/explorer_b_face_rig_manual_v2f';O.mkdir(exist_ok=True);sha=hashlib.sha256(SRC.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1)
head=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];ks=head.data.shape_keys.key_blocks
base=[v.co.copy() for v in ks['Basis'].data];head.data.calc_loop_triangles()
bvh=BVHTree.FromPolygons(base,[t.vertices[:] for t in head.data.loop_triangles],all_triangles=True)
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
N=128;tables={}
for side,sign in [('L',1),('R',-1)]:
 cy=.149*sign;outer=[];inner=[];limits=[]
 for j in range(N):
  a=2*math.pi*j/N;u=math.cos(a);s=math.sin(a);rz=.046 if s>=0 else .033
  y=.0645*u;z=rz*s
  limit=1/math.sqrt((y/.123)**2+(z/.114)**2)
  oy=cy+y*limit;oz=.063+z*limit
  hit=bvh.ray_cast(Vector((1,oy,oz)),Vector((-1,0,0)),2)[0]
  assert hit is not None
  outer.append(hit.x);limits.append(limit)
  iy=cy+y;iz=.063+z+.002*u*sign
  inner.append(.185+.066*math.sqrt(max(.001,1-((iy-cy)/.083)**2-((iz-.061)/.085)**2))+.006)
 # Suppress tiny reference-surface noise without flattening the nose/temple gradient.
 outer=np.array(outer)
 for _ in range(4):outer=(np.roll(outer,1)+2*outer+np.roll(outer,-1))/4
 tables[side]=(outer,inner,limits)
def sample(table,a):
 t=(a%(2*math.pi))*N/(2*math.pi);j=int(t);return table[j%N]*(1-(t-j))+table[(j+1)%N]*(t-j)
delta={}
for i,p in enumerate(base):
 if p.x<.075 or not -.065<p.z<.23:continue
 sign=1 if p.y>0 else -1;side='L' if sign>0 else 'R';cy=.149*sign
 dy=p.y-cy;dz=p.z-.063;rz=.046 if dz>=0 else .033
 a=math.atan2(dz/rz,dy/.0645);rho=math.sqrt((dy/.0645)**2+(dz/rz)**2)
 outer,inner,limits=tables[side];limit=sample(limits,a)
 if rho<.96 or rho>=limit:continue
 t=max(0,min(1,(rho-1)/(limit-1)))
 target=sample(inner,a)*(1-t)+sample(outer,a)*t+.0025*math.sin(math.pi*t)
 # Anchor the lash line; fill the broad depression, blend back into the cheek/brow.
 w=smooth(.98,1.10,rho)*(1-smooth(.75,1,t))
 hit=bvh.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)),2)[0]
 # Include the formerly folded skin under the visible layer; otherwise a hidden
 # low vertex remains a crease when the overlapping faces are repaired.
 visible=1.
 dx=max(-.006,min(.032,target-p.x))*w*visible
 if abs(dx)>1e-7:delta[i]=Vector((dx,0,0))
for k in ks:
 for i,d in delta.items():k.data[i].co+=d
for v,p in zip(head.data.vertices,ks['Basis'].data):v.co=p.co
head.data.update()

# D*R*D^-1: rotation takes place on a sphere, then scales back to the original envelope.
# Both white and iris retain their neutral appearance and the same numerical look controls.
def scaling_modifier(obj,name,center,scale):
 ng=bpy.data.node_groups.new(name,'GeometryNodeTree')
 ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
 ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
 inp=ng.nodes.new('NodeGroupInput');out=ng.nodes.new('NodeGroupOutput');pos=ng.nodes.new('GeometryNodeInputPosition');setp=ng.nodes.new('GeometryNodeSetPosition')
 sub=ng.nodes.new('ShaderNodeVectorMath');sub.operation='SUBTRACT';sub.inputs[1].default_value=center
 mul=ng.nodes.new('ShaderNodeVectorMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=scale
 add=ng.nodes.new('ShaderNodeVectorMath');add.operation='ADD';add.inputs[1].default_value=center
 ng.links.new(pos.outputs['Position'],sub.inputs[0]);ng.links.new(sub.outputs['Vector'],mul.inputs[0]);ng.links.new(mul.outputs['Vector'],add.inputs[0]);ng.links.new(add.outputs['Vector'],setp.inputs['Position'])
 ng.links.new(inp.outputs['Geometry'],setp.inputs['Geometry']);ng.links.new(setp.outputs['Geometry'],out.inputs['Geometry'])
 mod=obj.modifiers.new(name,'NODES');mod.node_group=ng;return mod
for side,sign in [('L',1),('R',-1)]:
 center=(.185,.149*sign,.061)
 for name in ['Eye_white.'+side,'Iris_pupil.'+side]:
  obj=bpy.data.objects[name]
  pre=scaling_modifier(obj,'Gaze 1 - normalize to sphere',center,(.083/.066,1,.083/.085))
  obj.modifiers.move(len(obj.modifiers)-1,0)
  scaling_modifier(obj,'Gaze 3 - restore fixed eye envelope',center,(.066/.083,1,.085/.083))
sc.frame_set(2);sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
cam=sc.camera
def camera(target,offset,scale):
 t=Vector(target);cam.location=t+Vector(offset);cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name):
 if '--quick' in sys.argv:return
 sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
action=rig.animation_data.action;rig.animation_data.action=None
props=['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']
def pose(values):
 for p in props:rig[p]=values.get(p,0.)
 rig.update_tag();bpy.context.view_layer.update()
hidden=[]
for obj in sc.objects:
 if obj.type=='MESH' and obj.name.startswith(('Hair','Nape')) and not obj.hide_render:obj.hide_render=True;hidden.append(obj)
sc.render.resolution_x=720;sc.render.resolution_y=720;sc.cycles.samples=16
for label,values in [('neutral',{}),('left',{'look_lr':-1}),('right',{'look_lr':1}),('half',{'blink_L':.5,'blink_R':.5}),('closed',{'blink_L':1,'blink_R':1})]:
 pose(values)
 camera((.2,-.149,.065),(4,-.4,0),.34);render('eye-'+label+'-front')
 camera((.2,-.149,.065),(1.1,-4,.04),.35);render('eye-'+label+'-side')
pose({})
for obj in hidden:obj.hide_render=False
camera((.1,0,0),(4,-.35,.12),1.3);render('neutral')
rig.animation_data.action=action;sc.frame_set(1)
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'api_credits':0,'orbital_vertices_adjusted':len(delta),'maximum_skin_depth_change':max(abs(d.x) for d in delta.values()),'mouth_changed':False,'neutral_eye_mesh_changed':False,'gaze_method':'Normalized sphere rotation followed by ellipsoid scaling (D R D^-1). Geometry Nodes remain live in Blender.'}
(O/'orbit-gaze-report.json').write_text(json.dumps(report,indent=2))
sc['RIG_STATUS']='V2f: orbital trough filled; stable eye envelope during gaze; V2e mouth and lashes preserved.'
for obj in sc.objects:obj.select_set(False)
head.select_set(True);bpy.context.view_layer.objects.active=head
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(O/'explorer_orbit_gaze_v2f.blend'))
print('ORBIT_V2F_SAVED',flush=True)
