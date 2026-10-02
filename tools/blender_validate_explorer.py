import bpy,json,math
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parents[1]/'artifacts/characters/explorer-b-v1'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-custom.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
mesh=bpy.data.objects['Explorer_B_SkinnedMesh'];scene=bpy.context.scene
report={'blender':bpy.app.version_string,'vertex_count':len(mesh.data.vertices),'bone_count':len(rig.data.bones),'clips':{}}
weights=[sum(g.weight for g in v.groups) for v in mesh.data.vertices]
report['unweighted_vertices']=sum(w<.999 for w in weights)
report['max_weight_sum_error']=max(abs(w-1) for w in weights)
for name,n in [('B_Scout',144),('B_TrailWalk',32),('B_Dash',20),('B_ShapeSummon',96)]:
 rig.animation_data.action=bpy.data.actions[name]
 scene.frame_set(1);start={b.name:b.matrix.copy() for b in rig.pose.bones}
 min_z=1e5;max_z=-1e5
 for f in range(1,n+2):
  scene.frame_set(f)
  evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=evaluated.to_mesh()
  coords=[evaluated.matrix_world@v.co for v in data.vertices]
  min_z=min(min_z,min(v.z for v in coords));max_z=max(max_z,max(v.z for v in coords))
  evaluated.to_mesh_clear()
 end={b.name:b.matrix.copy() for b in rig.pose.bones}
 delta=max(abs(start[k][r][c]-end[k][r][c]) for k in start for r in range(4) for c in range(4))
 report['clips'][name]={'duration_seconds':n/24,'min_vertex_z_m':min_z,'max_vertex_z_m':max_z,'start_end_max_matrix_delta':delta,'finite':math.isfinite(min_z) and math.isfinite(max_z)}
 assert math.isfinite(min_z) and min_z>-.025, 'Severe ground penetration'
 assert delta<.0001,'Loop/rest return mismatch'
assert report['unweighted_vertices']==0
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
