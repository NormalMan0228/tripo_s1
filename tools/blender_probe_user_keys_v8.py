import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(A/'user_head_mpfb_rigify_v8.blend'));sc=bpy.context.scene;h=bpy.data.objects['FACE_user_head'];out={};b=h.data.shape_keys.key_blocks[0]
for f in [1,95,195,295,395]:
 sc.frame_set(f);bpy.context.view_layer.update();out[f]={k.name:{'value':k.value,'delta':max((v.co-w.co).length for v,w in zip(k.data,b.data))} for k in h.data.shape_keys.key_blocks if k.name.startswith('!ex-') and ('Blink' not in k.name)}
(A/'key-probe.json').write_text(json.dumps(out,indent=2));print(json.dumps(out[95]))
