"""Reopen all seven HD scenes and validate delivered geometry and selection."""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/explorer_b_hd_restart_v1'
manifest=json.loads((BASE/'generation-manifest.json').read_text(encoding='utf-8'))
audit={'state':'verified','parts':{},'actual_credits':manifest['actual_credits'],
       'cap':manifest['cap'],'remaining':manifest['authorized_remaining']}
for part,entry in manifest['parts'].items():
    source=ROOT/entry['model_file']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/entry['review_blend']))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert meshes and all(not o.hide_select and not o.hide_get() for o in meshes)
    assert not any(o.type=='ARMATURE' for o in bpy.context.scene.objects)
    assert bpy.context.scene.camera
    assert all(o.data.materials for o in meshes)
    vertices=sum(len(o.data.vertices) for o in meshes)
    polygons=sum(len(o.data.polygons) for o in meshes)
    assert vertices==entry['measured_vertices'] and polygons==entry['measured_triangles']
    assert not any(n.type=='TEX_IMAGE' for o in meshes for m in o.data.materials for n in m.node_tree.nodes)
    report=json.loads((BASE/part/'mesh-review.json').read_text(encoding='utf-8'))
    corners=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
    lo=[min(v[i] for v in corners) for i in range(3)]
    hi=[max(v[i] for v in corners) for i in range(3)]
    assert all(abs(lo[i]-report['bounds']['min'][i])<1e-5 and abs(hi[i]-report['bounds']['max'][i])<1e-5 for i in range(3))
    audit['parts'][part]={'source_hash_verified':True,'blend_reopened':True,
                        'selectable_meshes':len(meshes),'vertices':vertices,'triangles':polygons,
                        'bounds_preserved':True,'rigged':False,'texture_generated':False}
(BASE/'delivery-verification.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print('HD_DELIVERY_VERIFIED',len(audit['parts']),'parts',flush=True)
