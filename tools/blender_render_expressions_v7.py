import bpy
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_expressions_v7';bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_expressions_v7.blend'));sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=576;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.eevee.taa_render_samples=32
for name,f in [('neutral',1),('happy',100),('curious',220),('concern',340),('determined',460),('surprise',580),('blink',47)]:
 sc.frame_set(f);sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
sc.eevee.taa_render_samples=16;sc.render.filepath=str(A/'animation_frames/frame_');(A/'animation_frames').mkdir(exist_ok=True);bpy.ops.render.render(animation=True);print('V7_VIDEO_FRAMES_COMPLETE')
