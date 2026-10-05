"""Reopen delivered scenes and check selectable surfaces and packed textures."""
import hashlib
import json
from pathlib import Path
from collections import Counter
import bpy

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/characters/explorer_b_fullbody_v2/06_textured_parts'
manifest = json.loads((BASE/'preparation-report.json').read_text(encoding='utf-8'))
result = {'files': {}, 'source_files_unchanged': {}, 'errors': []}
for part in ('fullbody','head','hand','hair'):
    transfer = json.loads((BASE/part/'texture-transfer.json').read_text(encoding='utf-8'))
    path = ROOT / transfer['target_source']
    unchanged = hashlib.sha256(path.read_bytes()).hexdigest() == transfer['target_file_sha256']
    result['source_files_unchanged'][part] = unchanged
    assert unchanged, f'Native source changed: {part}'
    assert transfer['target_geometry_uv_digest_before'] == transfer['target_geometry_uv_digest_after']

paths = [('workbench', ROOT/manifest['workbench_blend'])]
paths += [(part, ROOT/r['individual_blend']) for part,r in manifest['parts'].items()]
for part, path in paths:
    bpy.ops.wm.open_mainfile(filepath=str(path))
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    armatures = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    assert objs and not armatures
    assert all(not o.hide_select and not o.hide_get() and not o.hide_viewport for o in objs)
    assert all(o.data.uv_layers for o in objs)
    used = set()
    for obj in objs:
        assert len(obj.data.materials) > 0
        for mat in obj.data.materials:
            assert mat and mat.use_nodes
            bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            assert bsdf.inputs['Base Color'].is_linked
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image:
                    used.add(n.image)
    assert used and all(im.packed_file or im.packed_files for im in used)
    assert all(im.size[0] > 0 and im.size[1] > 0 for im in used)
    vertices = sum(len(o.data.vertices) for o in objs)
    polygons = sum(len(o.data.polygons) for o in objs)
    if part != 'workbench':
        expected = manifest['parts'][part]
        assert len(objs) == expected['separately_selectable_meshes']
        assert vertices == expected['vertices'] and polygons == expected['polygons']
        assert all(o.get('source_part') == part for o in objs)
    result['files'][part] = {'path': str(path.relative_to(ROOT)), 'opened': True,
                            'selectable_meshes': len(objs), 'vertices': vertices, 'polygons': polygons,
                            'polygon_sides': dict(Counter(len(p.vertices) for o in objs for p in o.data.polygons)),
                            'packed_images': [{'name': im.name, 'size': list(im.size)} for im in used],
                            'armatures': 0, 'uv_present_on_all_meshes': True}
(BASE/'delivery-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print('DELIVERY_VERIFIED', len(paths), 'scenes', flush=True)
