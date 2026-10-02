"""Combine simultaneous Blender-exported tracks into one GLB demonstration clip."""
import json,struct
from pathlib import Path

def merge(path):
    path=Path(path);data=path.read_bytes();size=struct.unpack_from('<I',data,12)[0]
    doc=json.loads(data[20:20+size]);trailing=data[20+size:]
    combined={'name':'Detail_Demo','samplers':[],'channels':[]};targets=set()
    for animation in doc.get('animations',[]):
        offset=len(combined['samplers']);combined['samplers'].extend(animation['samplers'])
        for channel in animation['channels']:
            key=(channel['target']['node'],channel['target']['path'])
            assert key not in targets,'Conflicting animation tracks'
            targets.add(key);channel['sampler']+=offset;combined['channels'].append(channel)
    doc['animations']=[combined]
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
    result=struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(trailing))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+trailing
    path.write_bytes(result)
    print('MERGED_DETAIL_TRACKS',len(combined['channels']))

if __name__=='__main__':
    merge(Path(__file__).resolve().parents[1]/'artifacts/characters/explorer-b-detailed-v2/explorer-b-detailed.glb')
