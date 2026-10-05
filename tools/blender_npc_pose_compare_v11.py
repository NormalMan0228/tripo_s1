import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v11';bpy.ops.wm.open_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v11.blend'));scene=bpy.context.scene;scene.render.resolution_x=600;scene.render.resolution_y=800
for key,y,h,frame in [('sora',-1.95,1.65,211),('moru',-.65,1.65,1),('naru',.65,1.55,391),('haeru',1.95,1.85,1)]:
 for c in bpy.data.collections:
  if c.name in ['SORA','MORU','NARU','HAERU']:c.hide_render=c.name!=key.upper()
 scene.frame_set(frame);cam=scene.camera;cam.location=(5,y,h*.5);target=Vector((0,y,h*.5));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=h*1.18;scene.render.filepath=str(O/key/'key-pose-front.png');bpy.ops.render.render(write_still=True)
