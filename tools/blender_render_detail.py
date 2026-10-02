"""Render actual authored detail controls in close-up; no generated video."""
import bpy,sys,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-detailed-v2'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-detailed.blend'))
scene=bpy.context.scene;cam=scene.camera
scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.cycles.samples=10
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU'
for name,target,offset,scale,count in [('face',(0,0,.855),(3,0,.1),.30,72),('hand',(0,.345,.700),(2,-2,3),.17,48)]:
    target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    folder=OUT/('frames-'+name);folder.mkdir(exist_ok=True)
    for i in range(count):
        scene.frame_set(1+i*2);scene.render.filepath=str(folder/f'{i+1:04d}.png');bpy.ops.render.render(write_still=True)
    print('DETAIL_RENDERED',name,flush=True)
