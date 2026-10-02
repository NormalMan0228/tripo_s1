"""Merge matching Scenario rigs and remove horizontal walk drift from the hip.

Only for these reviewed authored assets. Does not loosen private prop validation.
"""
import argparse
import copy
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.import_scenario_glb import normalize


def unpack(blob):
    blob=normalize(blob)
    size=struct.unpack_from('<I',blob,12)[0]
    return json.loads(blob[20:20+size]),bytearray(blob[28+size:])


def pack(doc,binary):
    doc['buffers'][0]['byteLength']=len(binary)
    binary+=b'\0'*((-len(binary))%4)
    data=json.dumps(doc,separators=(',',':')).encode();data+=b' '*((-len(data))%4)
    return struct.pack('<III',0x46546c67,2,28+len(data)+len(binary))+struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',len(binary),0x004e4942)+binary


def multiply(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def apply(basis,vector):
    return [sum(basis[i][j]*vector[j] for j in range(3)) for i in range(3)]


def inverse(m):
    a,b,c=m[0];d,e,f=m[1];g,h,i=m[2]
    result=[[e*i-f*h,c*h-b*i,b*f-c*e],[f*g-d*i,a*i-c*g,c*d-a*f],[d*h-e*g,b*g-a*h,a*e-b*d]]
    determinant=a*result[0][0]+b*result[1][0]+c*result[2][0]
    if abs(determinant)<1e-8: raise ValueError('singular_rig_transform')
    return [[value/determinant for value in row] for row in result]


def basis(node):
    if 'matrix' in node: return [[node['matrix'][r+c*4] for c in range(3)] for r in range(3)]
    x,y,z,w=node.get('rotation',[0,0,0,1]);s=node.get('scale',[1,1,1])
    rotation=[[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],
              [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],
              [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]]
    return [[rotation[r][c]*s[c] for c in range(3)] for r in range(3)]


def float_accessor(doc,binary,index,components):
    accessor=doc['accessors'][index];view=doc['bufferViews'][accessor['bufferView']]
    if accessor['componentType']!=5126 or accessor['type']!={1:'SCALAR',3:'VEC3'}[components]:
        raise ValueError('unsupported_animation_accessor')
    offset=view.get('byteOffset',0)+accessor.get('byteOffset',0)
    stride=view.get('byteStride',components*4)
    values=[struct.unpack_from('<'+'f'*components,binary,offset+n*stride) for n in range(accessor['count'])]
    return accessor,offset,stride,values


def remove_horizontal_drift(doc,binary,animation,node_name='Hip'):
    nodes=doc['nodes'];parents={child:i for i,node in enumerate(nodes) for child in node.get('children',[])}
    def global_basis(index):
        local=basis(nodes[index])
        return multiply(global_basis(parents[index]),local) if index in parents else local
    changed=False
    for channel in animation['channels']:
        node=channel['target']['node']
        if channel['target']['path']!='translation' or nodes[node].get('name')!=node_name: continue
        sampler=animation['samplers'][channel['sampler']]
        if sampler.get('interpolation','LINEAR')!='LINEAR': raise ValueError('unsupported_interpolation')
        _,_,_,times=float_accessor(doc,binary,sampler['input'],1)
        accessor,offset,stride,points=float_accessor(doc,binary,sampler['output'],3)
        if len(points)!=len(times) or len(points)<2: raise ValueError('invalid_animation_samples')
        parent_basis=global_basis(parents[node]) if node in parents else [[1,0,0],[0,1,0],[0,0,1]]
        world_drift=apply(parent_basis,[points[-1][j]-points[0][j] for j in range(3)])
        world_drift[1]=0 # Preserve vertical foot/hip movement.
        local_drift=apply(inverse(parent_basis),world_drift)
        duration=times[-1][0]-times[0][0]
        if duration<=0: raise ValueError('invalid_animation_duration')
        corrected=[]
        for i,point in enumerate(points):
            ratio=(times[i][0]-times[0][0])/duration
            value=[point[j]-local_drift[j]*ratio for j in range(3)]
            struct.pack_into('<fff',binary,offset+i*stride,*value)
            corrected.append(value)
        accessor['min']=[min(p[j] for p in corrected) for j in range(3)]
        accessor['max']=[max(p[j] for p in corrected) for j in range(3)]
        changed=True
    if not changed: raise ValueError('hip_translation_track_missing')


def merge(walk_blob,idle_blob):
    doc,binary=unpack(walk_blob);idle,idle_binary=unpack(idle_blob)
    if doc['nodes']!=idle['nodes'] or doc['skins']!=idle['skins']:
        raise ValueError('rigs_do_not_match')
    walk=doc['animations'][0];walk['name']='walk'
    remove_horizontal_drift(doc,binary,walk)
    animation=copy.deepcopy(idle['animations'][0]);animation['name']='idle'
    views,accessors={},{}
    def copy_accessor(old):
        if old in accessors: return accessors[old]
        value=copy.deepcopy(idle['accessors'][old]);old_view=value['bufferView']
        if old_view not in views:
            view=copy.deepcopy(idle['bufferViews'][old_view]);start=view.get('byteOffset',0)
            payload=idle_binary[start:start+view['byteLength']]
            binary.extend(b'\0'*((-len(binary))%4));view['byteOffset']=len(binary)
            views[old_view]=len(doc['bufferViews']);doc['bufferViews'].append(view);binary.extend(payload)
        value['bufferView']=views[old_view]
        accessors[old]=len(doc['accessors']);doc['accessors'].append(value)
        return accessors[old]
    for sampler in animation['samplers']:
        sampler['input']=copy_accessor(sampler['input']);sampler['output']=copy_accessor(sampler['output'])
    doc['animations'].append(animation)
    doc['asset']['extras']={'source':'Scenario explorer; Tripo Rigging walk and idle','horizontal_walk_drift_removed':True}
    return pack(doc,binary)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('walk',type=Path);parser.add_argument('idle',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();args.output.write_bytes(merge(args.walk.read_bytes(),args.idle.read_bytes()))
    print('Merged matching rigs with idle and in-place walk clips.')
