import bpy
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-hand-v4'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Body_Rig'];cam=scene.camera
scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.cycles.samples=10
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU'
for name,seconds,target,offset,scale in [('Hands_Open_Grasp',4,(.09,.17,.64),(2,-3,2),.28)]:
    rig.animation_data.action=bpy.data.actions[name];target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    folder=OUT/'frames'/name;folder.mkdir(parents=True,exist_ok=True)
    for f in range(1,seconds*24+1):
        path=folder/f'{f:04d}.png'
        if path.exists():continue
        scene.frame_set(f);scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    print('BODY_V3_RENDERED',name,flush=True)
