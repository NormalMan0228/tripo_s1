import copy
import json
import struct
import pytest
from server.config import ROOT
from server.provider import validate_glb, ProviderError


def test_malformed_model_references_fail_closed():
    blob=(ROOT/'game/assets/sample_stool.glb').read_bytes()
    size=struct.unpack_from('<I',blob,12)[0]
    original=json.loads(blob[20:20+size])
    tail=blob[20+size:]
    def pack(doc):
        data=json.dumps(doc).encode(); data+=b' '*((-len(data))%4)
        return struct.pack('<III',0x46546c67,2,20+len(data)+len(tail))+struct.pack('<II',len(data),0x4e4f534a)+data+tail
    edits=[
        lambda d: d['accessors'][0].update(bufferView=-1),
        lambda d: d['meshes'][0]['primitives'][0]['attributes'].update(POSITION=-1),
        lambda d: d['meshes'][0]['primitives'][0].update(indices=-1),
        lambda d: d['nodes'][0].update(mesh=-1),
        lambda d: d['scenes'][0].update(nodes=[-1]),
        lambda d: d['nodes'][0].update(translation=[0,0]),
        lambda d: d['accessors'][0].update(count=False),
        lambda d: d['meshes'][0].update(primitives=[]),
        lambda d: d.update(nodes=[5]),
    ]
    for edit in edits:
        data=copy.deepcopy(original);edit(data)
        with pytest.raises(ProviderError,match='invalid_model'): validate_glb(pack(data))
    with pytest.raises(ProviderError,match='invalid_model'): validate_glb(pack([]))


def test_non_position_float_payload_and_instancing_budget():
    blob=(ROOT/'game/assets/sample_stool.glb').read_bytes()
    size=struct.unpack_from('<I',blob,12)[0]
    original=json.loads(blob[20:20+size]);binary=blob[28+size:]
    def pack(doc,data=binary):
        header=json.dumps(doc).encode();header+=b' '*(-len(header)%4)
        return struct.pack('<III',0x46546c67,2,28+len(header)+len(data))+struct.pack('<II',len(header),0x4e4f534a)+header+struct.pack('<II',len(data),0x004e4942)+data
    stats={};validate_glb(blob,stats=stats)
    assert stats['vertices']>0 and stats['draw_calls']>0 and stats['texture_pixels']==0
    doc=copy.deepcopy(original)
    # A second float accessor can contain NaN even when POSITION remains valid.
    data=bytearray(binary);offset=len(data);data.extend(struct.pack('<fff',float('nan'),0,1))
    doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':12})
    doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'componentType':5126,'count':1,'type':'VEC3'})
    doc['buffers'][0]['byteLength']=len(data)
    with pytest.raises(ProviderError,match='invalid_model'):validate_glb(pack(doc,data))
    doc=copy.deepcopy(original)
    doc['nodes']=[{'mesh':0} for _ in range(129)];doc['scenes']=[{'nodes':list(range(129))}];doc['scene']=0
    with pytest.raises(ProviderError,match='invalid_model'):validate_glb(pack(doc))
