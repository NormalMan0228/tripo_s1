"""Render the actual authored animation, not AI-generated animation imagery."""
import bpy,sys,json
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'artifacts/characters/explorer-b-v1'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-custom.blend'))
scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
scene.render.resolution_x=640;scene.render.resolution_y=640
scene.cycles.samples=12
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 scene.cycles.device='GPU'
except:pass
for name,frames in [('B_Scout',144),('B_TrailWalk',32),('B_Dash',20),('B_ShapeSummon',96)]:
 rig.animation_data.action=bpy.data.actions[name]
 folder=OUT/'frames'/name;folder.mkdir(parents=True,exist_ok=True)
 for f in range(1,frames+1):
  path=folder/(str(f).zfill(4)+'.png')
  if path.exists():continue
  scene.frame_set(f);scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
 print('RENDERED',name,flush=True)
