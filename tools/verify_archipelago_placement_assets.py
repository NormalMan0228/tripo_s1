"""Verify that runtime texture copies keep every reviewed building mesh intact."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/maps/archipelago_placement_v1'

def read(path):
    raw = path.read_bytes()
    assert struct.unpack_from('<III', raw) == (0x46546C67, 2, len(raw))
    n = struct.unpack_from('<I', raw, 12)[0]
    doc = json.loads(raw[20:20+n])
    at = 20+n
    size = struct.unpack_from('<I', raw, at)[0]
    return doc, raw[at+8:at+8+size]

def view(doc, binary, accessor):
    v = doc['bufferViews'][accessor['bufferView']]
    start = v.get('byteOffset', 0)
    return binary[start:start+v['byteLength']]

manifest = json.loads((OUT / 'placements.json').read_text(encoding='utf-8'))
result = []
for spec in manifest['buildings']:
    stem = spec['id'].split('_', 1)[1]
    source = ROOT / 'art/maps/archipelago_objects_v1' / spec['id'] / (stem+'.glb')
    target = ROOT / 'labs/terrain_lab/assets/buildings' / (stem+'.glb')
    a, x = read(source)
    b, y = read(target)
    for key in ['nodes', 'meshes', 'materials', 'scenes', 'scene']:
        assert a.get(key) == b.get(key), (spec['id'], key)
    assert len(a['accessors']) == len(b['accessors'])
    for aa, bb in zip(a['accessors'], b['accessors']):
        assert {k:v for k,v in aa.items() if k != 'bufferView'} == {k:v for k,v in bb.items() if k != 'bufferView'}
        assert view(a, x, aa) == view(b, y, bb), (spec['id'], 'accessor changed')
    result.append({'id':spec['id'], 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                   'geometry_and_material_records_unchanged': True,
                   'all_accessor_bytes_unchanged': True})
report = {'count':len(result), 'passed':True, 'buildings':result}
(OUT / 'source_preservation_verification.json').write_text(json.dumps(report, indent=2))
print('PLACEMENT_SOURCE_PRESERVATION_PASS count=',len(result))
