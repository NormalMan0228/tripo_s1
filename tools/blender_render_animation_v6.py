import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_animated_v6';bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_repaired_rigify_v6.blend'));sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=576;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.render.fps=30;sc.frame_start=1;sc.frame_end=360
if hasattr(sc.eevee,'taa_render_samples'):sc.eevee.taa_render_samples=16
sc.render.filepath=str(A/'animation_frames/frame_');(A/'animation_frames').mkdir(exist_ok=True);bpy.ops.render.render(animation=True);print('V6_ANIMATION_FRAMES_COMPLETE')
