"""Check reviewed geometry survives runtime texture preparation."""
import ast
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime_manifest=json.loads((ROOT/'labs/terrain_lab/environment_layout.json').read_text(encoding='utf-8'))
OUT = ROOT / runtime_manifest.get('output_directory','art/maps/archipelago_environment_v1')
source = (ROOT/'tools/verify_archipelago_placement_assets.py').read_text()
helpers = {'json':json, 'struct':struct}
exec('\n\n'.join(ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)),helpers)
read,view = helpers['read'],helpers['view']
manifest=json.loads((OUT/'environment_layout.json').read_text(encoding='utf-8'))
results=[]
for spec in manifest['models']:
    stem=spec['id'].split('_',1)[1]
    original=ROOT/'art/maps/archipelago_objects_v1'/spec['id']/(stem+'.glb')
    runtime=ROOT/'labs/terrain_lab/assets/environment'/(stem+'.glb')
    a,x=read(original)
    b,y=read(runtime)
    for key in ['nodes','meshes','materials','scenes','scene']:
        assert a.get(key)==b.get(key),(spec['id'],key)
    assert len(a['accessors'])==len(b['accessors'])
    for aa,bb in zip(a['accessors'],b['accessors']):
        assert {k:v for k,v in aa.items() if k!='bufferView'}=={k:v for k,v in bb.items() if k!='bufferView'}
        assert view(a,x,aa)==view(b,y,bb),(spec['id'],'geometry changed')
    results.append({'id':spec['id'],'reviewed_source_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
                    'all_geometry_and_material_records_preserved':True})
authored=[b for b in manifest['bridges'] if b.get('authored_at_bank_span')]
for b in authored:
    assert b['scale_z']==1.0
    assert (ROOT/'labs/terrain_lab'/b['fitted_model'].replace('res://','')).exists()
report={'passed':True,'models':len(results),'results':results,
        'retained_tripo_copies_preserved':True,
        'active_authored_bridge_models':[{'id':b['id'],'model':b['fitted_model'],'scale_z':b['scale_z']} for b in authored],
        'bridge_runtime_deformation':'Active fitted bridges use separately authored metre-sized planks, posts and rails. Reviewed Tripo copies are retained unchanged.' if authored else 'Intentional bank height fitting and additional arch, checked separately in Godot.'}
(OUT/'source_preservation_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ENVIRONMENT_SOURCE_PRESERVATION_PASS count=',len(results))
