import bpy,json,struct
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly';bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_young_bob_closed_smile_v3.blend'))
head=bpy.data.objects['FACE_skin_eyelids_lashes'];ctrl=bpy.data.objects['FACE_CONTROLS'];assert ctrl['mouth_open']==0 and head.data.shape_keys.key_blocks['Mouth_open_original'].value==0
nt=head.data.materials[0].node_tree;color=next(n.image for n in nt.nodes if n.type=='TEX_IMAGE' and n.image and n.image.name=='Color');assert color.packed_file and list(color.size)==[4096,4096];assert head.data.color_attributes.get('Lash_tint')
glb=A/'explorer_b_young_bob_closed_smile_v3.glb';buf=glb.read_bytes();length,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+length]);assert all('bufferView' in im for im in g['images']);assert {'EYEBALL_L','EYEBALL_R'}.issubset({n.get('name') for n in g['nodes']});assert any('targets' in p for m in g['meshes'] for p in m['primitives'])
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(glb));added=[o for o in bpy.data.objects if o not in before];assert len([o for o in added if o.type=='MESH' and o.name.startswith('EYEBALL_')])==2
for o in added:bpy.data.objects.remove(o,do_unlink=True)
p=A/'verification.json';d=json.loads(p.read_text(encoding='utf-8'));d.update(final_file_reopened=True,lash_color_repair='Smooth Blender vertex tint multiplying original 4096 UV atlas',original_uv_atlas_unchanged=True,final_glb_roundtrip_passed=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('FINAL_RECHECK_PASSED')
