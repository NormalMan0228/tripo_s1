"""Image-guided experimental hand rig. Isolated part; never alters the explorer skin.

2D landmarks are fitted into the front-aligned mesh plane. BVH rays estimate
joint depth. This is a bounded test of automation, not a claim of production fit.
"""
import bpy, json, math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/detail-map-20261003/character'
DEST=ROOT/'labs/detail_parts_lab/assets';DEST.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'artifacts/detail-map-20261003/tripo/character_detail/open-hand-image/model.glb'))
skin=next(o for o in bpy.context.scene.objects if o.type=='MESH')
for v in skin.data.vertices:v.co=skin.matrix_world@v.co
skin.parent=None;skin.matrix_world.identity();skin.name='Image_conditioned_open_hand'
bpy.ops.object.select_all(action='DESELECT');skin.select_set(True);bpy.context.view_layer.objects.active=skin
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=.00001);bpy.ops.object.mode_set(mode='OBJECT')
lo=Vector(tuple(min(v.co[i] for v in skin.data.vertices) for i in range(3)));hi=Vector(tuple(max(v.co[i] for v in skin.data.vertices) for i in range(3)))
data=json.loads((OUT/'hand-landmarks.json').read_text());bbox=data['skin_bbox_px'];width,height=data['image_size']
bvh=BVHTree.FromObject(skin,bpy.context.evaluated_depsgraph_get());points=[];misses=0
for x,y,z in data['points']:
 u=(x*width-bbox[0])/(bbox[2]-bbox[0]);v=1-(y*height-bbox[1])/(bbox[3]-bbox[1])
 yy=lo.y+u*(hi.y-lo.y);zz=lo.z+v*(hi.z-lo.z)
 front=bvh.ray_cast(Vector((hi.x+.2,yy,zz)),Vector((-1,0,0)))[0]
 back=bvh.ray_cast(Vector((lo.x-.2,yy,zz)),Vector((1,0,0)))[0]
 if front is None or back is None:
  nearest=min(skin.data.vertices,key=lambda t:(t.co.y-yy)**2+(t.co.z-zz)**2).co
  xx=nearest.x;misses+=1
 else:xx=(front.x+back.x)*.5
 points.append(Vector((xx,yy,zz)))
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='Hand_Image_Landmark_Rig'
bpy.ops.object.mode_set(mode='EDIT');rig.data.edit_bones.remove(rig.data.edit_bones[0])
palm=rig.data.edit_bones.new('Palm');palm.head=points[0];palm.tail=sum([points[k] for k in [5,9,13,17]],Vector())*.25;palm.align_roll(Vector((1,0,0)))
specs=[('Thumb',[1,2,3,4]),('Index',[5,6,7,8]),('Middle',[9,10,11,12]),('Ring',[13,14,15,16]),('Pinky',[17,18,19,20])]
segments={'Palm':(palm.head.copy(),palm.tail.copy())};finger_names=[]
for name,ids in specs:
 parent=palm
 for i in range(3):
  b=rig.data.edit_bones.new(f'{name}_{i+1}');b.head=points[ids[i]];b.tail=points[ids[i+1]];b.parent=parent;b.use_connect=i>0;b.align_roll(Vector((1,0,0)));parent=b
  segments[b.name]=(b.head.copy(),b.tail.copy());finger_names.append(b.name)
bpy.ops.object.mode_set(mode='OBJECT')
groups={name:skin.vertex_groups.new(name=name) for name in segments}
def segment_distance(p,a,b):
 d=b-a;t=max(0,min(1,(p-a).dot(d)/max(d.length_squared,1e-9)));return (p-(a+d*t)).length
knuckle_z=sum(points[k].z for k in [5,9,13,17])/4
for v in skin.data.vertices:
 values=[]
 for name,(a,b) in segments.items():
  distance=segment_distance(v.co,a,b);sigma=.038 if name!='Palm' else .11
  values.append((math.exp(-distance*distance/(2*sigma*sigma)),name))
 values.sort(reverse=True);values=values[:3];total=sum(w for w,_ in values)
 if total<1e-10:groups['Palm'].add([v.index],1,'REPLACE')
 else:
  for w,name in values:groups[name].add([v.index],w/total,'REPLACE')
skin.parent=rig;mod=skin.modifiers.new('Hand skin','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=False
skin.select_set(True);bpy.context.view_layer.objects.active=skin
bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
bpy.ops.object.vertex_group_smooth(group_select_mode='ALL',factor=.7,repeat=18)
bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL',lock_active=False)
bpy.ops.object.mode_set(mode='OBJECT')
scene=bpy.context.scene;scene.render.fps=30;scene.frame_start=1;scene.frame_end=73
for frame in range(1,74):
 amount=math.sin(math.pi*(frame-1)/72)**2
 for name in finger_names:
  bone=rig.pose.bones[name];bone.rotation_mode='XYZ';joint=int(name[-1])-1
  angles=[38,48,28] if 'Thumb' not in name else [24,32,20]
  bone.rotation_euler=(math.radians(angles[joint])*amount,0,0);bone.keyframe_insert('rotation_euler',frame=frame)
 if frame==1:rig.animation_data.action.name='hand_gentle_grasp'
for layer in rig.animation_data.action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for key in fc.keyframe_points:key.interpolation='LINEAR'
scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/source/open_hand_rigged_20261003.blend'))
bpy.ops.object.select_all(action='DESELECT');skin.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(DEST/'open_hand_rigged.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_frame_range=True,export_force_sampling=True)
# Render actual deformation, retaining the neutral original face elsewhere.
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
world=bpy.data.worlds.new('Hand studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.66,.64,1);world.node_tree.nodes['Background'].inputs[1].default_value=.7;scene.world=world
center=(lo+hi)*.5
for pos,power in [((3,-4,4),650),((-3,1,3),400)]:
 bpy.ops.object.light_add(type='AREA',location=center+Vector(pos));light=bpy.context.object;light.data.energy=power;light.data.size=4;light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=center+Vector((4,-3,1.5)));cam=bpy.context.object;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.4;scene.camera=cam
for frame,name in [(1,'open-hand-rig-open'),(37,'open-hand-rig-grasp')]:
 scene.frame_set(frame);scene.render.filepath=str(OUT/f'{name}.png');bpy.ops.render.render(write_still=True)
result={'bones':len(rig.data.bones),'joints_2d':len(points),'depth_ray_misses':misses,'clip':'hand_gentle_grasp','seconds':2.4,'production_skin_replaced':False,'handedness_verified':False,'fit_method':'reference crop projection and mesh BVH depth; approximate, needs wrist/body fit','automatic_weights':True,'weight_cleanup':'weld shared vertices, smooth 18 passes, normalize; no hard palm cutoff','source_body_unchanged':True}
(OUT/'hand-rig-audit.json').write_text(json.dumps(result,indent=2));print('HAND_RIG_EXPORTED',result)
