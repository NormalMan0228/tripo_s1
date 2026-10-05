import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_expressions_v7';bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_expressions_v7.blend'));sc=bpy.context.scene;h=bpy.data.objects['FACE_skin_eyelids_lashes'];rig=bpy.data.objects['Explorer_B_Rigify_Face_Rig'];ctrl=bpy.data.objects['FACE_CONTROLS'];results=[]
for frame in [45,47,50,100,165,167,170,220,340,460,580,679,681,684]:
 sc.frame_set(frame);bpy.context.view_layer.update();H=rig.matrix_world@rig.pose.bones['DEF-head'].matrix@rig.data.bones['DEF-head'].matrix_local.inverted();inv=H.inverted();eo=h.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();tree=BVHTree.FromPolygons([inv@h.matrix_world@v.co for v in me.vertices],[tuple(t.vertices) for t in me.loop_triangles],all_triangles=True);eo.to_mesh_clear()
 for side,sign in [('L',1),('R',-1)]:
  o=bpy.data.objects['IRIS_PUPIL_'+side];blink=float(ctrl['blink_'+side]);count=0;tested=0;worst=0
  for poly in o.data.polygons:
   p=inv@o.matrix_world@poly.center;u=(sign*p.y-.139)/.070
   if abs(u)<1:
    s=math.sqrt(1-u*u);mid=.108+.014*(u+1)/2;top=mid+.049*s**.9;bot=mid-.047*s**.9;closed=bot+.23*(top-bot);top=top*(1-blink)+(closed-.0004)*blink;bot=bot*(1-blink)+(closed+.0004)*blink
    if blink<.99 and bot-.0015<p.z<top+.0015:continue
   tested+=1;hit,*_=tree.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)))
   deficit=p.x-hit.x if hit else 1
   if deficit>.0005:count+=1;worst=max(worst,deficit)
  results.append({'frame':frame,'side':side,'blink':blink,'tested_occluded_iris_faces':tested,'protruding_faces':count,'maximum_deficit':worst})
(A/'iris-occlusion.json').write_text(json.dumps(results,indent=2));print(json.dumps(results));assert all(r['protruding_faces']==0 for r in results)
