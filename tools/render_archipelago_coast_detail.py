import bpy
from pathlib import Path
from mathutils import Vector

root=Path(__file__).resolve().parents[1]
folder=root/'art/maps/archipelago_terrain_v2'
bpy.ops.wm.open_mainfile(filepath=str(folder/'archipelago_terrain_v2.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene
try:
    pref=bpy.context.preferences.addons['cycles'].preferences
    pref.compute_device_type='CUDA';pref.get_devices()
    for device in pref.devices:device.use=device.type=='CUDA'
    scene.cycles.device='GPU'
except Exception:scene.cycles.device='CPU'
camera=scene.camera
camera.location=(-61,-90,10)
camera.rotation_euler=(Vector((-56,-65,1))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='PERSP';camera.data.lens=42
scene.render.resolution_x=1500;scene.render.resolution_y=1000
scene.render.filepath=str(folder/'terrain_coast_detail.png')
bpy.ops.render.render(write_still=True)
