import bpy,json
from pathlib import Path
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_expressions_v7';f=A/'explorer_b_expressions_v7.blend';bpy.ops.wm.open_mainfile(filepath=str(f));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update();h=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];eo=h.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();t=BVHTree.FromPolygons([h.matrix_world@v.co for v in me.vertices],[tuple(t.vertices) for t in me.loop_triangles],all_triangles=True);eo.to_mesh_clear();ids=json.loads((A/'hair-residual.json').read_text())['vertices'];inv=hair.matrix_world.inverted().to_3x3()
for _ in range(4):
 for i in ids:
  v=hair.data.vertices[i];p=hair.matrix_world@v.co;q,n,_,dist=t.find_nearest(p);signed=(p-q).dot(n)
  if signed<.002:v.co+=inv@(n*(.003-signed))
bpy.ops.wm.save_as_mainfile(filepath=str(f));print('FINISHED_HAIR',len(ids))
