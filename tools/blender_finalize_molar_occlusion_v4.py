import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';FILE=A/'explorer_b_balanced_face_v4.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
for i in [17,19,21,24,26,27]:
 o=bpy.data.objects['TOOTH_%02d'%i]
 for v,b in zip(o.data.vertices,o.data.shape_keys.key_blocks[0].data):b.co.z-=.035-.020*smooth(.052,.079,abs(b.co.y));v.co=b.co
bpy.ops.wm.save_as_mainfile(filepath=str(FILE));print('MOLAR_OCCLUSION_FINALIZED')
