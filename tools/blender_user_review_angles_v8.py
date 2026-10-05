import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(A/'user_head_mpfb_rigify_v8.blend'));sc=bpy.context.scene;sc.frame_set(1);sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True;sc.render.resolution_x=640;sc.render.resolution_y=720;cam=sc.camera
for name,pos,target,scale in [('angle',(3,-2,0),(0,0,0),1.2),('side',(0,-3,0),(0,0,0),1.2),('eyes_detail',(3,0,0),(.18,0,.125),.49)]:
 cam.location=Vector(target)+Vector(pos);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
