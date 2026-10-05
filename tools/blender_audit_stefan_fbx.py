"""Read the two supplied baking FBX examples; do not save or alter sources."""
import bpy
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'artifacts/stefan-course-audit-20261004'
records = json.loads((folder / 'assignment-assets.json').read_text(encoding='utf-8'))
output = []
for rec in records:
    if Path(rec['path']).suffix.lower() != '.fbx':
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    item = {'path': rec['path'], 'archive': rec['archive']}
    try:
        bpy.ops.import_scene.fbx(filepath=rec['path'])
        item['objects'] = [dict(name=o.name, type=o.type,
            vertices=len(o.data.vertices) if o.type == 'MESH' else None,
            triangles=sum(len(p.vertices)-2 for p in o.data.polygons) if o.type == 'MESH' else None,
            uv_layers=[u.name for u in o.data.uv_layers] if o.type == 'MESH' else [],
            materials=[s.material.name if s.material else None for s in o.material_slots]) for o in bpy.data.objects]
        item['actions'] = [a.name for a in bpy.data.actions]
    except Exception as exc:
        item['error'] = str(exc)
    output.append(item)
(folder / 'fbx-audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(output, ensure_ascii=False, indent=2))
