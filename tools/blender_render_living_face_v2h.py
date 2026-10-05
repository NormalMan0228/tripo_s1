import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_face_rig_manual_v2h';bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_living_face_v2h.blend'));s=bpy.context.scene
s.render.resolution_x=512;s.render.resolution_y=512;s.render.resolution_percentage=100;s.cycles.samples=8;s.cycles.use_denoising=True;s.render.use_persistent_data=True
s.render.image_settings.file_format='PNG';s.render.film_transparent=False
c=s.camera;t=Vector((.17,0,.065));c.location=t+Vector((4,-.24,.05));c.rotation_euler=(t-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=1.02
frames=O/'animation-frames';frames.mkdir(exist_ok=True)
for f in range(1,289):
 s.frame_set(f);s.render.filepath=str(frames/('%04d.png'%f));bpy.ops.render.render(write_still=True)
 if f%24==0:print('VIDEO_SECOND',f//24,flush=True)
print('VIDEO_FRAMES_COMPLETE',flush=True)
