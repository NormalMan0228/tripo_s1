import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_rest_refined_v2'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_P2_rest_refined_v2.blend'))
sc=bpy.context.scene;head=bpy.data.objects['HEAD_relaxed_smile_rest'];ctrl=bpy.data.objects['FACE_CONTROLS'];assert ctrl['mouth_open']==0
results=[]
for value in [0,.25,.5,.75,1,0]:
 ctrl['mouth_open']=value;ctrl.update_tag();sc.frame_set(sc.frame_current+1);bpy.context.view_layer.update()
 e=head.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();m.calc_loop_triangles()
 assert all(math.isfinite(x) for v in m.vertices for x in v.co)
 tree=BVHTree.FromPolygons([v.co for v in m.vertices],[tuple(t.vertices) for t in m.loop_triangles],all_triangles=True)
 gaps={}
 for y in [-.04,0,.04]:
  missed=[]
  for i in range(301):
   z=-.135+i*.0003;p,*_=tree.ray_cast(Vector((2,y,z)),Vector((-1,0,0)))
   if p is None or p.x<.16:missed.append(z)
  gaps[str(y)]=len(missed)*.0003
 results.append({'mouth_open':value,'cavity_height_by_y':gaps})
 if value==0:assert max(gaps.values())<=.0006, gaps
 if value==1:assert gaps['0']>.03
 e.to_mesh_clear()
report=json.loads((O/'refinement-report.json').read_text())
assert all(x['root_clearance_max']<.0015 for x in report['lash_attachment'])
uv={}
for o in bpy.data.collections['04_Brows_lashes'].objects:
 coords=[tuple(round(x,6) for x in v.uv) for v in o.data.uv_layers['HairAtlas'].data]
 uv[o.name]=len(set(coords));assert uv[o.name]>100
assert not bpy.data.objects['P2_OPEN_SOURCE_UNCHANGED'].visible_get()
assert bpy.data.objects['HAIR_latest_v2_fitted_to_P2'].visible_get()
packed=[im.name for im in bpy.data.images if im.source=='FILE' and im.packed_file];assert packed
result={'reopened':True,'default_closed_smile':True,'mouth_morph_sweep':results,'lash_roots':report['lash_attachment'],'uv_unique_coordinates':uv,'packed_images':packed,'source_preserved':True,'skin_vertex_count_unchanged':report['skin_vertices_before']==report['skin_vertices_after'],'full_face_rig':False,'blink_rig':False,'api_credits':0}
(O/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
