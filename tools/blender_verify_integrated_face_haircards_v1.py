"""Reopen the saved asset and verify morphs, UVs, portability and export exclusion."""
import bpy,json,math,hashlib,struct
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1';OUT=O/'assembly'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_b_integrated_face_haircards_v1.blend'));sc=bpy.context.scene
head=bpy.data.objects['FACE_Tripo_integrated_0'];ctrl=bpy.data.objects['FACE_CONTROLS'];hair=bpy.data.objects['HAIR_UV_strand_cards'];hd=bpy.data.objects['HAIR_Tripo_HD_form_guide']
assert ctrl['mouth_open']==0
assert head.data.shape_keys and 'Mouth_open_Tripo_original' in head.data.shape_keys.key_blocks
assert hd.hide_render and hd.hide_get()
checks=[]
original=head.data.shape_keys.key_blocks['Mouth_open_Tripo_original'];reference=[p.co.copy() for p in original.data]
for val in [0.,.25,.5,.75,1.]:
 ctrl['mouth_open']=val;ctrl.update_tag();sc.frame_set(1+int(val*100));bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();ev=head.evaluated_get(dg);me=ev.to_mesh()
 coords=[v.co for v in me.vertices];assert len(coords)==len(reference);assert all(math.isfinite(x) for p in coords for x in p)
 error=max((a-b).length for a,b in zip(coords,reference))
 checks.append({'mouth_open':val,'max_distance_from_original':error,'vertices':len(coords)})
 print('MORPH_CHECK',val,error,head.data.shape_keys.key_blocks['Mouth_open_Tripo_original'].value)
 if val==1:assert error<1e-6
 ev.to_mesh_clear()
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update()
uvs=[v.uv.copy() for v in hair.data.uv_layers.active.data];assert uvs and all(-1e-5<=x<=1+1e-5 for v in uvs for x in v)
material=hair.data.materials[0];nodes=material.node_tree.nodes;images=[n.image for n in nodes if n.type=='TEX_IMAGE' and n.image];assert images and all(i.packed_file for i in images)
assert material.node_tree.nodes['Principled BSDF'].inputs['Alpha'].is_linked
export=[head]+list(sc.collection.children['03_Hair_cards_GAME'].objects)
assert all(o.type=='MESH' for o in export);assert hd not in export
bpy.ops.object.select_all(action='DESELECT')
for o in export:o.hide_set(False);o.select_set(True)
bpy.context.view_layer.objects.active=head
glb=OUT/'explorer_b_integrated_face_haircards_v1.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_morph=True,export_apply=False)
raw=glb.read_bytes();length,kind=struct.unpack_from('<II',raw,12);gltf=json.loads(raw[20:20+length]);names=[n.get('name','') for n in gltf['nodes']]
assert not any('SOURCE' in n or 'HD_form' in n or 'Guide' in n for n in names)
hm=next(m for m in gltf['materials'] if m['name']==material.name);assert hm.get('alphaMode')=='BLEND'
assert gltf.get('images') and all('bufferView' in im for im in gltf['images'])
roundtrip_names=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(glb));roundtrip=[o for o in bpy.data.objects if o not in roundtrip_names]
rh=next(o for o in roundtrip if o.type=='MESH' and o.name.startswith('HAIR_UV_strand_cards'));assert rh.data.uv_layers
assert rh.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Alpha'].is_linked
for o in roundtrip:bpy.data.objects.remove(o,do_unlink=True)
summary=json.loads((OUT/'haircard-build-report.json').read_text(encoding='utf-8'))
hair_triangles=summary['cards_triangles']+summary['scalp_quads']*2+summary['bob_support_faces']*2
source_head_hash=hashlib.sha256((O/'head/model.fbx').read_bytes()).hexdigest();source_hair_hash=hashlib.sha256((O/'hair/model.glb').read_bytes()).hexdigest()
assert source_head_hash=='f2d9f13a773877196524dbfd6db9c8e767af4ebe6d44c06a4fd9847eb4886457'
assert source_hair_hash=='7e44b377b976e7aaabe10f00b162aacb5686372c14c4467ee9152cb30aa076d3'
report={'status':'passed','saved_file_reopened':True,'original_sources_hash_unchanged':True,'default_closed':True,'original_open_restored_exactly':True,'morph_sweep':checks,'guide_count':summary['guide_count'],'hair_card_triangles':summary['cards_triangles'],'support_triangles':summary['scalp_quads']*2+summary['bob_support_faces']*2,'total_hair_triangles':hair_triangles,'dense_hair_triangles':summary['dense_reference_triangles'],'reduction_percent':100*(1-hair_triangles/summary['dense_reference_triangles']),'card_uv_range':[[min(v[j] for v in uvs),max(v[j] for v in uvs)] for j in range(2)],'atlas_packed':True,'glb_alpha_mode':hm.get('alphaMode'),'glb_textures_embedded':True,'dense_reference_excluded_from_export':True,'glb_roundtrip_uv_alpha':True,'full_face_rig':False,'blink_rig':False,'known_limits':['Tripo facial topology has boundaries and nonmanifold edges; cleanup required before rigging.','Hair is a card prototype with a low-poly support shell; card flow and layer transitions need further art polish.','Integrated lashes preserved as generated, not independently bound for blinking.','GLB has an open-mouth morph, but the Blender custom-property driver is not exported.']}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('VERIFICATION',json.dumps(report,ensure_ascii=False))
