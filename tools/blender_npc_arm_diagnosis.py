import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v8'
bpy.ops.wm.open_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v8.blend'))
s=bpy.context.scene;s.frame_set(1);s.render.resolution_x=600;s.render.resolution_y=800
for key,y in [('sora',-1.95),('moru',-.65),('naru',.65),('haeru',1.95)]:
 for c in bpy.data.collections:
  if c.name in ['SORA','MORU','NARU','HAERU']:c.hide_render=c.name!=key.upper()
 rig=bpy.data.objects[key+'_BodyRig'];mesh=bpy.data.objects[key+'_SkinnedMesh'];rig.data.pose_position='REST'
 h=max(v.co.z for v in mesh.data.vertices);cam=s.camera;cam.location=(3,y-3,h*.55);target=Vector((0,y,h*.5));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=h*1.18
 s.render.filepath=str(O/key/'original-rest.png');bpy.ops.render.render(write_still=True)
 groups={g.index:g.name for g in mesh.vertex_groups}
 data=[{'p':list(v.co),'w':{groups[g.group]:g.weight for g in v.groups if g.weight>.001}} for v in mesh.data.vertices if sum(g.weight for g in v.groups if any(n in groups[g.group] for n in ['UpperArm','Forearm','Hand','Digit']))>.65]
 (O/key/'arm-source.json').write_text(json.dumps(data))
 rig.data.pose_position='POSE'
