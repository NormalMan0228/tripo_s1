import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_expressions_v7';f=A/'explorer_b_expressions_v7.blend';bpy.ops.wm.open_mainfile(filepath=str(f));sc=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Rigify_Face_Rig'];demo=rig.animation_data.action;slot=rig.animation_data.action_slot;clips=[]
def curves(a):return list(a.fcurves) if hasattr(a,'fcurves') else [f for l in a.layers for s in l.strips for b in s.channelbags for f in b.fcurves]
for name,frame in [('Neutral',1),('Happy',100),('Curious',220),('Concern',340),('Determined',460),('Surprise',580)]:
 action=demo.copy();action.name='Face_'+name+'_Loop';action.use_fake_user=True
 for fc in curves(action):
  value=fc.evaluate(frame)
  while len(fc.keyframe_points):fc.keyframe_points.remove(fc.keyframe_points[-1],fast=True)
  points=[(1,value),(90,value)]
  if 'blink.' in fc.data_path and fc.data_path.endswith('["blink"]'):points=[(1,value),(58,value),(62,1.),(69,value),(90,value)]
  for x,y in points:
   k=fc.keyframe_points.insert(x,y);k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
  fc.update()
 clips.append({'action':action.name,'frames':90,'fps':30,'seconds':3,'loop':True})
rig.animation_data.action=demo;rig.animation_data.action_slot=slot;sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(f));(A/'expression-clips.json').write_text(json.dumps(clips,indent=2));print('V7_CLIPS',json.dumps(clips))
