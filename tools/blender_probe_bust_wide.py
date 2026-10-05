import bpy
from pathlib import Path
s=bpy.context.scene;s.frame_set(1)
o=bpy.data.objects['Face_Neck_Clavicle'];o.data.shape_keys.animation_data.action=None
for name in ['eyeWideLeft','eyeWideRight']:
 k=o.data.shape_keys.key_blocks[name];k.slider_max=2;k.value=1.5
s.render.filepath=str(Path(__file__).resolve().parents[1]/'artifacts/mpfb-clavicle-bust-20261004/eye_wide_trial.png')
bpy.ops.render.render(write_still=True)
