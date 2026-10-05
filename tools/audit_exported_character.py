"""Reimport the delivered GLB and measure loops instead of trusting export flags."""
import bpy, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/production-lab-20261003'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.render.fps=60
bpy.ops.import_scene.gltf(filepath=str(ROOT/'labs/production_lab/assets/explorer_b.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
scene=bpy.context.scene;results={}
for action in list(bpy.data.actions):
 rig.animation_data.action=action
 if action.slots:rig.animation_data.action_slot=action.slots[0]
 start,end=action.frame_range;poses=[];hips=[];steps=[];translations=[];previous=None
 for f in [start]+[float(i) for i in range(math.ceil(start)+1,math.ceil(end))]+[end]:
  scene.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update()
  pose={b.name:(b.location.copy(),b.rotation_quaternion.copy()) for b in rig.pose.bones}
  hips.append(rig.pose.bones['Hip'].head.copy());poses.append(pose)
  if previous:
   steps.append(max(math.degrees(v[1].rotation_difference(previous[n][1]).angle) for n,v in pose.items()))
   translations.append(max(((v[0]-previous[n][0]).length,n) for n,v in pose.items()))
  previous=pose
 first,last=poses[0],poses[-1]
 results[action.name]={'frames':len(poses),'hip_horizontal_range_game_m':max(max(p[i] for p in hips)-min(p[i] for p in hips) for i in [0,1])*1.7,
  'loop_position_gap_m':max((last[n][0]-v[0]).length for n,v in first.items()),
  'loop_rotation_gap_deg':max(math.degrees(last[n][1].rotation_difference(v[1]).angle) for n,v in first.items()),
  'max_joint_step_deg_60hz':max(steps,default=0),'max_local_translation_step':max(translations,default=(0,''))}
report={'clips':results,'pass':len(results)==3 and all(r['hip_horizontal_range_game_m']<.02 and r['loop_position_gap_m']<.0001 and r['loop_rotation_gap_deg']<.15 for r in results.values())}
(OUT/'export-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('REIMPORT_AUDIT',json.dumps(report))
