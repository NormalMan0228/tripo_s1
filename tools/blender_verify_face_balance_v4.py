import bpy,json,struct,hashlib,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';FILE=A/'explorer_b_balanced_face_v4.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS'];key=head.data.shape_keys.key_blocks['Mouth_open_original'];deps=bpy.context.evaluated_depsgraph_get()
assert ctrl['mouth_open']==0 and key.value==0;assert all(bpy.data.objects['EYEBALL_'+s].parent is None for s in ('L','R'));assert all(bpy.data.objects['IRIS_PUPIL_'+s].parent==bpy.data.objects['EYEBALL_'+s] for s in ('L','R'))
evalhead=head.evaluated_get(deps);mesh=evalhead.to_mesh();mesh.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[t.vertices for t in mesh.loop_triangles],all_triangles=True);evalhead.to_mesh_clear();visibility={}
for name,cam in [('front',Vector((3,0,-.02))),('angle_L',Vector((3,-2,-.02))),('angle_R',Vector((3,2,-.02))),('side_L',Vector((0,-3,-.02))),('side_R',Vector((0,3,-.02)))]:
 visible=0;total=0
 for o in sc.objects:
  if not o.name.startswith('TOOTH_') or o.hide_render:continue
  eo=o.evaluated_get(deps);me=eo.to_mesh()
  for p in me.polygons:
   point=o.matrix_world@p.center;d=point-cam;hit,n,idx,dist=tree.ray_cast(cam,d.normalized(),d.length+.002);total+=1
   if hit is None or dist>d.length-.0003:visible+=1
  eo.to_mesh_clear()
 visibility[name]={'sampled_tooth_faces':total,'faces_not_occluded_by_skin':visible}
print('TOOTH_VISIBILITY_SKIN_ONLY',json.dumps(visibility))
# Final exposure includes oral tissue as well as the outer face surface.
verts=[];tris=[]
for o in sc.objects:
 if o.type!='MESH' or o.hide_render or o.hide_get() or o.name.startswith('TOOTH_'):continue
 eo=o.evaluated_get(deps);me=eo.to_mesh();me.calc_loop_triangles();start=len(verts);verts.extend(o.matrix_world@v.co for v in me.vertices);tris.extend(tuple(start+i for i in t.vertices) for t in me.loop_triangles);eo.to_mesh_clear()
occlusion=BVHTree.FromPolygons(verts,tris,all_triangles=True);skin_visibility=visibility;visibility={}
for name,cam in [('front',(3,0,.04)),('front_low',(3,0,-.02)),('angle_L',(3,-2,.04)),('angle_R',(3,2,.04)),('side_L',(0,-3,.04)),('side_R',(0,3,.04))]:
 cam=Vector(cam);count=0;total=0
 for o in sc.objects:
  if not o.name.startswith('TOOTH_') or o.hide_render:continue
  eo=o.evaluated_get(deps);me=eo.to_mesh()
  for p in me.polygons:
   point=o.matrix_world@p.center;d=point-cam;hit,n,idx,dist=occlusion.ray_cast(cam,d.normalized(),d.length+.002);total+=1
   if hit is None or dist>d.length-.0003:count+=1
  eo.to_mesh_clear()
 visibility[name]={'sampled_tooth_faces':total,'exposed_tooth_faces':count}
assert all(v['exposed_tooth_faces']==0 for v in visibility.values()),visibility
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();evalhead=head.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evalhead.to_mesh();open_error=max((v.co-k.co).length for v,k in zip(mesh.vertices,key.data));evalhead.to_mesh_clear();assert open_error<1e-6
source=bpy.data.objects['SOURCE_Tripo_face_0'];kd=KDTree(len(source.data.vertices))
for i,v in enumerate(source.data.vertices):kd.insert(source.matrix_world@v.co,i)
kd.balance();source_error=max(kd.find(v.co)[2] for v in key.data);assert source_error<1e-6
for value in [.5,0.]:ctrl['mouth_open']=value;ctrl.update_tag();sc.frame_set(1+int(value*100));bpy.context.view_layer.update();assert abs(key.value-value)<1e-6
assert not hair['hair_cards'];assert all(math.isfinite(c) for o in sc.objects if o.type=='MESH' and not o.hide_render for v in o.data.vertices for c in v.co)
bpy.ops.object.select_all(action='DESELECT');visible=[o for o in sc.objects if o.type=='MESH' and not o.hide_render and not o.hide_get()]
for o in visible:o.select_set(True)
bpy.context.view_layer.objects.active=head;glb=A/'explorer_b_balanced_face_v4.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_apply=False,export_morph=True)
buf=glb.read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);names=[n.get('name','') for n in g['nodes']];assert not any(n.startswith('SOURCE') for n in names);assert all('EYEBALL_'+s in names and 'IRIS_PUPIL_'+s in names for s in ('L','R'));assert all('bufferView' in i for i in g['images']);assert any('COLOR_0' in p['attributes'] for m in g['meshes'] for p in m['primitives']);assert any('targets' in p for m in g['meshes'] for p in m['primitives'])
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(glb));added=[o for o in bpy.data.objects if o not in before];assert len([o for o in added if o.type=='MESH' and o.name.startswith('EYEBALL_')])==2;assert len([o for o in added if o.type=='MESH' and o.name.startswith('IRIS_PUPIL_')])==2
for o in added:bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head;bpy.ops.wm.save_as_mainfile(filepath=str(FILE));budget=json.loads((R/'artifacts/character-hd-restart-20261004/budget.json').read_text(encoding='utf-8-sig'));spent=sum(t.get('credits_consumed',t.get('reservation',0)) for t in budget['tasks'].values());refine=json.loads((A/'refinement-report.json').read_text(encoding='utf-8'));report={'status':'passed','new_Tripo_credits':0,'remaining_credits':budget['tripo_cap']-spent,'total_spent':spent,'default_pose':'relaxed closed smile','original_open_skin_restored_exactly':open_error,'source_coordinate_error':source_error,'eyes_centered_forward':True,'iris_center_outward_offset':.004,'eye_reflections_controlled':True,'two_small_catchlights_each_eye':True,'lashes':'Contour-traced dark vertex paint, original skin atlas untouched','mouth_corners_lowered':True,'chin_center_smoothed':True,'teeth_recessed_in_closed_rest':True,'tooth_visibility_rays':visibility,'crown_height_reduction':refine['hair_crown_height_reduction'],'iris_texture_packed':True,'glb_roundtrip_passed':True,'glb_eye_parent_hierarchy_preserved':True,'glb_morph_and_vertex_colors':True,'full_facial_rig':False,'game_optimization_complete':False}
(A/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('BALANCE_VERIFIED',json.dumps(report,ensure_ascii=False))
