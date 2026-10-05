"""Move only connected rock components that intersect bridge corridors."""
import json
import struct
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'labs/terrain_lab'
layout=json.loads((LAB/'environment_layout.json').read_text(encoding='utf-8'))
OUT=ROOT/layout.get('output_directory','art/maps/archipelago_environment_v1')
raw=(LAB/'assets/archipelago_terrain_v6.glb').read_bytes()
size=struct.unpack_from('<I',raw,12)[0]
doc=json.loads(raw[20:20+size])
at=20+size
binary=bytearray(raw[at+8:at+8+struct.unpack_from('<I',raw,at)[0]])
node=next(n for n in doc['nodes'] if n.get('name')=='Coast__shore_rock_clusters')
basis=Rotation.from_quat(node['rotation']).as_matrix()@np.diag(node['scale'])
origin=np.array(node['translation'])
primitives=doc['meshes'][node['mesh']]['primitives']
arrays=[];faces=[];offset=0
def accessor(index):
    a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
    start=v.get('byteOffset',0)+a.get('byteOffset',0)
    dtype={5126:'<f4',5125:'<u4',5123:'<u2'}[a['componentType']]
    count=a['count']*(3 if a['type']=='VEC3' else 1)
    result=np.frombuffer(binary,dtype=dtype,count=count,offset=start).copy()
    return result.reshape((-1,3)) if a['type']=='VEC3' else result,start
for p in primitives:
    vertices,_=accessor(p['attributes']['POSITION'])
    indices,start=accessor(p['indices'])
    arrays.append(vertices)
    faces.append(indices.reshape((-1,3))+offset)
    offset+=len(vertices)
points=np.concatenate(arrays)
_,inverse=np.unique(np.round(points,4),axis=0,return_inverse=True)
tri=inverse[np.concatenate(faces)]
edges=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]])
graph=coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(inverse.max()+1,inverse.max()+1)).tocsr()
count,labels=connected_components(graph,directed=False)
components=labels[inverse]
world=points@basis.T+origin
layout=json.loads((LAB/'environment_layout.json').read_text(encoding='utf-8'))
records=[]
routes=layout['bridges']+[{'id':'pier_island_'+str(p['island']),'a':p['landing'],'b':p['tip'],'width_m':3.0} for p in layout.get('piers',[])]
for component in range(count):
    selected=np.flatnonzero(components==component)
    w=world[selected]
    low,high=w.min(axis=0),w.max(axis=0)
    center=(low+high)/2
    radius=max(high[0]-low[0],high[2]-low[2])/2
    for bridge in routes:
        a,b=np.array(bridge['a']),np.array(bridge['b'])
        direction=(b-a)/np.linalg.norm(b-a)
        along=np.dot(center[[0,2]]-a,direction)
        if not -1<along<np.linalg.norm(b-a)+1:
            continue
        side=np.array([-direction[1],direction[0]])
        distance=np.dot(center[[0,2]]-a,side)
        margin=bridge['width_m']/2+radius+.9
        if abs(distance)<margin:
            shift_xz=side*((1 if distance>=0 else -1)*margin-distance)
            shift=np.array([shift_xz[0],0,shift_xz[1]])
            local=np.linalg.solve(basis,shift)
            points[selected]+=local
            world[selected]+=shift
            center+=shift
            records.append({'component':component,'bridge':bridge['id'],'vertices':len(selected),
                            'shift_xz_m':shift_xz.tolist(),'original_center':((low+high)/2).tolist()})
offset=0
changed_accessors=[]
for primitive,original in zip(primitives,arrays):
    index=primitive['attributes']['POSITION'];a=doc['accessors'][index]
    updated=points[offset:offset+len(original)].astype('<f4')
    if not np.array_equal(updated,original):
        v=doc['bufferViews'][a['bufferView']]
        start=v.get('byteOffset',0)+a.get('byteOffset',0)
        binary[start:start+updated.nbytes]=updated.tobytes()
        a['min']=updated.min(axis=0).tolist();a['max']=updated.max(axis=0).tolist()
        changed_accessors.append(index)
    offset+=len(original)
encoded=json.dumps(doc,separators=(',',':')).encode()
encoded+=b' '*((-len(encoded))%4)
payload=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
target=LAB/'assets/archipelago_terrain_environment_v1.glb'
assembled=struct.pack('<III',0x46546c67,2,len(payload)+12)+payload
if not target.exists() or target.read_bytes()!=assembled:
    target.write_bytes(assembled)
# Every binary byte outside those specific rock position accessors stays unchanged.
old_binary=raw[at+8:at+8+len(binary)]
check=bytearray(binary)
for index in changed_accessors:
    a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
    start=v.get('byteOffset',0)+a.get('byteOffset',0);end=start+a['count']*12
    check[start:end]=old_binary[start:end]
assert check==old_binary
report={'rock_components':count,'relocated_rocks':records,'changed_rock_position_accessors':changed_accessors,
        'all_ground_water_normals_uv_and_texture_bytes_preserved':True,'source_glb_untouched':True}
(OUT/'rock_clearance_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('BRIDGE_ROCK_CLEARANCE_READY moved=',len(records),'components=',count,'other_bytes_preserved=True')
