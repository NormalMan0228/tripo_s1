"""Check the new source-based assembly and its portable review export."""
import bpy,math,json,hashlib,struct
from pathlib import Path
from mathutils import Matrix,Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_face_multiview_meshhair_v2';A=O/'assembly';OLD=R/'art/characters/explorer_b_integrated_face_haircards_v1'
bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_multiview_mesh_hair_v2.blend'))
sc=bpy.context.scene;head=bpy.data.objects['FACE_Tripo_integrated_0'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];raw=bpy.data.objects['SOURCE_Tripo_face_0'];raw_hair=bpy.data.objects['HAIR_HD_SOURCE_UNCHANGED']
assert hair['hair_cards']==False
assert not any('HAIR_UV_strand_cards' in o.name or 'HAIR_bob_lowpoly_undercoat' in o.name or 'Hair_guide_' in o.name for o in sc.objects)
assert not hair.hide_render and not hair.hide_get();assert raw.hide_render and raw_hair.hide_render and raw.hide_get() and raw_hair.hide_get()
assert len(head.data.vertices)==len(raw.data.vertices)
# Match source coordinates including imported FBX parent transforms.
source_error=max((a.co-(raw.matrix_world@b.co)).length for a,b in zip(head.data.vertices,raw.data.vertices));assert source_error<1e-6,source_error
assert not head.data.shape_keys,'New source should not be reshaped during the geometry review stage'
assert all(math.isfinite(x) for v in hair.data.vertices for x in v.co)
shader=hair.data.materials[0].node_tree.nodes['Principled BSDF'];assert not shader.inputs['Alpha'].is_linked and shader.inputs['Alpha'].default_value==1
source_face_hash=hashlib.sha256((O/'head/model.fbx').read_bytes()).hexdigest();source_hair_hash=hashlib.sha256((OLD/'hair/model.glb').read_bytes()).hexdigest()
assert source_face_hash=='f65687754b992e1d309e5d5fedb97c0e3b2e1e1c50320e6327204fc00da12149';assert source_hair_hash=='7e44b377b976e7aaabe10f00b162aacb5686372c14c4467ee9152cb30aa076d3'
used_images={n.image for m in head.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image};assert used_images and all(im.packed_file for im in used_images)
bpy.ops.object.select_all(action='DESELECT')
for o in [head,hair]:o.select_set(True)
bpy.context.view_layer.objects.active=head
glb=A/'explorer_b_multiview_mesh_hair_v2.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_apply=False)
buf=glb.read_bytes();length,kind=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+length]);names=[n.get('name','') for n in g['nodes']]
assert not any('SOURCE' in n or 'Hair_guide' in n or 'undercoat' in n for n in names)
hm=next(m for m in g['materials'] if m['name']==hair.data.materials[0].name);assert hm.get('alphaMode','OPAQUE')=='OPAQUE'
assert all('bufferView' in im for im in g['images'])
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(glb));added=[o for o in bpy.data.objects if o not in before];rh=next(o for o in added if o.type=='MESH' and o.name.startswith(hair.name));assert len(rh.data.polygons)==len(hair.data.polygons)
for o in added:bpy.data.objects.remove(o,do_unlink=True)
inspection=json.loads((O/'head/inspection-report.json').read_text(encoding='utf-8'));counts=inspection['meshes'][0]
budget=json.loads((R/'artifacts/character-hd-restart-20261004/budget.json').read_text(encoding='utf-8-sig'));spent=sum(t.get('credits_consumed',0) for t in budget['tasks'].values());remaining=budget['tripo_cap']-spent
report={'status':'passed','saved_file_reopened':True,'hair_cards':False,'visible_hair_objects':1,'hair_alpha_mode':'OPAQUE','original_head_geometry_unmodified':True,'source_coordinate_max_error':source_error,'new_face_views':['front','left','right'],'source_hashes_unchanged':True,'face_texture_images_packed':len(used_images),'glb_textures_embedded':True,'glb_roundtrip_meshes':True,'source_objects_excluded_from_export':True,'hair_vertices':len(hair.data.vertices),'hair_triangles':len(hair.data.polygons),'head_faces':counts['faces'],'head_quads':counts['quads'],'head_boundary_edges':counts['boundary_edges'],'head_nonmanifold_edges':counts['nonmanifold_edges'],'new_face_credits':120,'texture_conversion_credits':5,'new_hair_credits':0,'total_spent':spent,'remaining_credits':remaining,'mouth_pose':'Original generated open mouth for oral/jaw review','closed_rest_prepared':False,'full_face_rig':False,'game_low_poly_final':False,'known_limits':['Original new head left open for geometry review; closed gentle game rest remains a later step.','Generated head has open boundaries/nonmanifold edges requiring cleanup before facial rigging.','Hair retains HD polygon density during form review; low-poly reduction/bake pending.','Fit is a preview; fine scalp/temple/ear contact needs review with the accepted new head.']}
(A/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('VERIFICATION',json.dumps(report,ensure_ascii=False))
