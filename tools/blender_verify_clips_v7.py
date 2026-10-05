import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_expressions_v7';bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_expressions_v7.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Rigify_Face_Rig'];hp=rig.pose.bones['head'];rows=[]
for name in ['Neutral','Happy','Curious','Concern','Determined','Surprise']:
 action=bpy.data.actions['Face_'+name+'_Loop'];rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0];samples=[]
 for frame in [1,60,62,66,90]:
  sc.frame_set(frame);bpy.context.view_layer.update();samples.append({'frame':frame,'expression':[float(hp[x]) for x in ['happy','concern','determined','surprise']],'blink':float(bpy.data.objects['FACE_CONTROLS']['blink_L'])})
 assert samples[0]['expression']==samples[-1]['expression'];assert samples[2]['blink']>.999
 expected=[1. if name.lower()==x else 0. for x in ['happy','concern','determined','surprise']];assert samples[0]['expression']==expected,(name,samples)
 rows.append({'name':action.name,'loop_verified':True,'blink_verified':True})
(A/'clip-verification.json').write_text(json.dumps(rows,indent=2));print('CLIPS_VERIFIED',json.dumps(rows))
