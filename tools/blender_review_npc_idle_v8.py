import bpy,json,sys
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v8'
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
for key,y in [('sora',-1.95),('moru',-.65),('naru',.65),('haeru',1.95)]:
 with bpy.data.libraries.load(str(O/key/(key+'_rigged_idle.blend')),link=False) as (source,destination):destination.objects=source.objects
 c=bpy.data.collections.new(key.upper());scene.collection.children.link(c)
 for obj in destination.objects:
  c.objects.link(obj)
  if obj.type=='ARMATURE':obj.location.y=y;obj.show_in_front=False
scene.frame_start=1;scene.frame_end=240;scene.render.fps=30
scene.render.engine='BLENDER_EEVEE_NEXT';scene.eevee.taa_render_samples=16
scene.render.resolution_x=1280;scene.render.resolution_y=640;scene.render.resolution_percentage=100
world=bpy.data.worlds.new('Studio');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.22,.25,.3,1);world.node_tree.nodes['Background'].inputs[1].default_value=.45
def light(name,position,power,size):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=position;o.rotation_euler=(Vector((0,0,1))-o.location).to_track_quat('-Z','Y').to_euler()
light('Key',(4,-3,5),1100,6);light('Fill',(3,4,3),850,5);light('Rim',(-3,0,4),1000,5)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.008));floor=bpy.context.object;floor.name='Review_Floor'
m=bpy.data.materials.new('Studio_floor');m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.17,.20,.23,1);m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8;floor.data.materials.append(m)
d=bpy.data.cameras.new('ReviewCamera');cam=bpy.data.objects.new('ReviewCamera',d);scene.collection.objects.link(cam);scene.camera=cam;d.type='ORTHO';d.ortho_scale=5.9
cam.location=(8,0,1);cam.rotation_euler=Vector((-1,0,0)).to_track_quat('-Z','Y').to_euler()
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.shading.type='MATERIAL';s.overlay.show_overlays=False;s.region_3d.view_location=(0,0,1);s.region_3d.view_distance=6.2;s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_perspective='ORTHO'
bpy.ops.object.select_all(action='DESELECT');scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v8.blend'))
for frame in [1,61,121,181]:
 scene.frame_set(frame);scene.render.filepath=str(O/('frame_'+str(frame)+'.png'));bpy.ops.render.render(write_still=True)
 print('NPC_IDLE_REVIEW_FRAME',frame,flush=True)
# Each still represents the actual skinned pose, not an altered reference image.
scene.render.resolution_x=1280;scene.render.resolution_y=640
scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='MEDIUM'
scene.render.filepath=str(O/'npc-idle-preview.mp4');scene.frame_step=1;scene.render.fps=30
bpy.ops.render.render(animation=True)
print('NPC_IDLE_VIDEO_READY',flush=True)



