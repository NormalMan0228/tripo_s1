"""Check the delivered part objects can individually enter mesh edit mode."""
import bpy
import json
import struct
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/character-parts-20261003'
parts = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(parts) == 40
assert len({o.data.as_pointer() for o in parts}) == len(parts)
assert bpy.context.mode == 'OBJECT'
assert bpy.context.object.name == 'Jacket_Torso'
checked = []
for obj in bpy.context.scene.objects:
    obj.select_set(False)
for obj in sorted(parts, key=lambda o: o.name):
    assert not obj.hide_select and not obj.hide_get() and not obj.hide_viewport
    assert len(obj.vertex_groups) == 41
    assert any(m.type == 'ARMATURE' for m in obj.modifiers)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    assert 'FINISHED' in bpy.ops.object.mode_set(mode='EDIT')
    assert bpy.context.mode == 'EDIT_MESH'
    assert 'FINISHED' in bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    checked.append(obj.name)
payload = (out / 'explorer_b_parts.glb').read_bytes()
magic, version, size = struct.unpack_from('<III', payload)
assert magic == 0x46546c67 and version == 2 and size == len(payload)
length, kind = struct.unpack_from('<II', payload, 12)
doc = json.loads(payload[20:20+length])
mesh_nodes = [n for n in doc['nodes'] if 'mesh' in n]
assert len(mesh_nodes) == 40
assert len(doc['skins']) == 1 and len(doc['skins'][0]['joints']) == 41
assert len(doc['animations']) == 6
assert not any('uri' in x for x in doc.get('images', []))
assert not any('uri' in x for x in doc.get('buffers', []))
report = {'blend_mesh_objects': len(parts), 'independent_mesh_datablocks': len(parts),
          'individual_edit_mode_checks': checked,
          'glb_mesh_nodes': len(mesh_nodes), 'glb_joints': len(doc['skins'][0]['joints']),
          'glb_animations': [a['name'] for a in doc['animations']],
          'embedded_textures': True, 'file_loaded_successfully': True}
(out / 'delivery-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('PARTS_DELIVERY_VERIFIED ' + json.dumps(report), flush=True)
