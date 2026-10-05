import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v8'
bpy.ops.wm.open_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v8.blend'))
s=bpy.context.scene;s.frame_set(1);s.render.resolution_x=800;s.render.resolution_y=800
for key,y in [('sora',-1.95),('moru',-.65),('naru',.65),('haeru',1.95)]:
 for c in bpy.data.collections:
  if c.name in ['SORA','MORU','NARU','HAERU']:c.hide_render=c.name!=key.upper()
 rig=bpy.data.objects[key+'_BodyRig'];mesh=bpy.data.objects[key+'_SkinnedMesh']
 b=rig.pose.bones['Forearm.L'];center=rig.matrix_world@((b.head+b.tail)/2)
 cam=s.camera;cam.location=center+Vector((2,-2,.2));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.55
 s.render.filepath=str(O/key/'arm-detail.png');bpy.ops.render.render(write_still=True)
 print('HAND',key,[(n,list(rig.data.bones[n].head_local),list(rig.data.bones[n].tail_local)) for n in ['Forearm.L','Hand.L']],flush=True)
