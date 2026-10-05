import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(A/'import_inspection.blend'));sc=bpy.context.scene;cam=sc.camera;target=Vector((0,-.13,.60));cam.location=target+Vector((0,-3,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.1;sc.render.resolution_x=500;sc.render.resolution_y=500
parts=[o for o in sc.objects if o.name.startswith('tripo_part_')]
for o in parts:o.hide_render=True
for ids,name in [(['14'],'part14'),(['5','8'],'mouthparts'),(['9','11'],'eyes'),(['17','18','19','20','35','37'],'lids')]:
 for o in parts:o.hide_render=o.name.removeprefix('tripo_part_') not in ids
 sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
