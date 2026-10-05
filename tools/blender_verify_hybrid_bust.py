import bpy,json,math,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v1'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_hybrid_bust_v1.blend'))
meshes=[o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render]
assert len(meshes)==5
for o in meshes:
    assert all(math.isfinite(c) for v in o.data.vertices for c in v.co)
cards=[o for o in meshes if o.name.startswith(('BROW','LASH'))]
assert len(cards)==3 and all(o.data.uv_layers.get('HairAtlas') for o in cards)
assert all(o.modifiers.get('Mirror_to_opposite_side') for o in cards)
assert all(i.packed_file is not None for i in bpy.data.images if i.source=='FILE')
for part in ['head','hair']:
    result=json.loads((O/part/'generation-result.json').read_text())
    source=R/result['file'];assert hashlib.sha256(source.read_bytes()).hexdigest()==result['sha256']
checks={'blend_reopened':True,'finite_mesh_coordinates':True,'original_Tripo_hashes_unchanged':True,'packed_file_textures':True,'three_UV_master_meshes_with_mirror':True,'visible_meshes':[o.name for o in meshes],'facial_rig_present':False,'artistic_acceptance':'pending_user_review'}
(O/'verification.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks))
