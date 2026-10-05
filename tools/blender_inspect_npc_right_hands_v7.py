import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v7'
bpy.ops.wm.open_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v7.blend'))
s=bpy.context.scene;s.frame_set(1);s.render.resolution_x=800;s.render.resolution_y=800
for key,y in [('sora',-1.95),('moru',-.65),('naru',.65),('haeru',1.95)]:
 for c in bpy.data.collections:
  if c.name in ['SORA','MORU','NARU','HAERU']:c.hide_render=c.name!=key.upper()
 rig=bpy.data.objects[key+'_BodyRig'];mesh=bpy.data.objects[key+'_SkinnedMesh']
 b=rig.pose.bones['Hand.R'];center=rig.matrix_world@((b.head+b.tail)/2)
 cam=s.camera;cam.location=center+Vector((2,.1,.1));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.30
 s.render.filepath=str(O/key/'hand-right-detail.png');bpy.ops.render.render(write_still=True)
 print('HAND',key,[(n,list(rig.data.bones[n].head_local),list(rig.data.bones[n].tail_local)) for n in ['Forearm.R','Hand.R']],flush=True)
 # Save source positions and topology of hand-weighted vertices for anatomical inspection.
 groups={g.index:g.name for g in mesh.vertex_groups}
 ids=[v.index for v in mesh.data.vertices if any(groups[g.group]=='Hand.R' and g.weight>.45 for g in v.groups)]
 (O/key/'hand-right-source.json').write_text(json.dumps({'positions':[(i,list(mesh.data.vertices[i].co)) for i in ids],'edges':[[*e.vertices] for e in mesh.data.edges if all(i in set(ids) for i in e.vertices)]}))
