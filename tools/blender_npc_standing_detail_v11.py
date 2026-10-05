import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v11'
bpy.ops.wm.open_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v11.blend'))
scene=bpy.context.scene;scene.frame_set(1);scene.render.resolution_x=600;scene.render.resolution_y=800;camera=scene.camera
for key,y in [('sora',-1.95),('moru',-.65),('naru',.65),('haeru',1.95)]:
 for collection in bpy.data.collections:
  if collection.name in ['SORA','MORU','NARU','HAERU']:collection.hide_render=collection.name!=key.upper()
 height={'sora':1.65,'moru':1.65,'naru':1.55,'haeru':1.85}[key]
 camera.location=(3,y-3,height*.55);target=Vector((0,y,height*.50));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=height*1.18
 scene.render.filepath=str(O/key/'standing-angle.png');bpy.ops.render.render(write_still=True)
 rig=bpy.data.objects[key+'_BodyRig'];mesh=bpy.data.objects[key+'_SkinnedMesh'];bpy.context.view_layer.update()
 report=json.loads((O/key/'verification.json').read_text())
 report['standing_pose']={'ankle_distance_m':(rig.pose.bones['Foot.L'].head-rig.pose.bones['Foot.R'].head).length,'original_ankle_distance_m':(rig.data.bones['Foot.L'].head_local-rig.data.bones['Foot.R'].head_local).length,'hip_lowering_m':height*.006,'soft_knees':True,'toe_out_degrees':4,'arms':'Reference-video resting posture; fitted arm joints'}
 e=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();report['standing_pose']['sole_min_z_m']=min(v.co.z for v in m.vertices);e.to_mesh_clear()
 (O/key/'verification.json').write_text(json.dumps(report,indent=2))
 print('STANDING_POSE',key,json.dumps(report['standing_pose']),flush=True)
all_reports={k:json.loads((O/k/'verification.json').read_text()) for k in ['sora','moru','naru','haeru']};(O/'verification.json').write_text(json.dumps(all_reports,indent=2))
