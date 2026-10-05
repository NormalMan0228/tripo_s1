import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_balanced_face_v4.blend'));sc=bpy.context.scene;deps=bpy.context.evaluated_depsgraph_get();coords=[];triangles=[]
for o in sc.objects:
 if o.type!='MESH' or o.hide_render or o.hide_get() or o.name.startswith('TOOTH_'):continue
 eo=o.evaluated_get(deps);me=eo.to_mesh();me.calc_loop_triangles();offset=len(coords);coords.extend(o.matrix_world@v.co for v in me.vertices);triangles.extend(tuple(offset+i for i in t.vertices) for t in me.loop_triangles);eo.to_mesh_clear()
tree=BVHTree.FromPolygons(coords,triangles,all_triangles=True);results={}
for name,cam in [('front',(3,0,.04)),('angle_L',(3,-2,.04)),('angle_R',(3,2,.04)),('side_R',(0,3,.04)),('front_low',(3,0,-.02))]:
 cam=Vector(cam);points=[]
 for o in sc.objects:
  if not o.name.startswith('TOOTH_') or o.hide_render:continue
  eo=o.evaluated_get(deps);me=eo.to_mesh()
  for p in me.polygons:
   point=o.matrix_world@p.center;d=point-cam;hit,n,idx,dist=tree.ray_cast(cam,d.normalized(),d.length+.002)
   if hit is None or dist>d.length-.0003:points.append({'name':o.name,'face':p.index,'point':list(point)})
  eo.to_mesh_clear()
 results[name]=points
(A/'tooth-exposure-probe.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('EXPOSED',json.dumps(results))
