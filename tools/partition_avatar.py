"""Transfer Tripo part labels to the original weighted mesh; never split skin weights.
Art-only requirements: numpy, scipy, Pillow. Images are read for classification only.
"""
import argparse,copy,io,json,struct,colorsys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from tools.merge_explorer_animations import unpack,pack,basis

def accessor(d,b,i):
    a=d['accessors'][i];v=d['bufferViews'][a['bufferView']]
    n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
    dtype=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']])
    result=np.ndarray((a['count'],n),dtype,buffer=b,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',n*dtype.itemsize),dtype.itemsize)).copy()
    return result

def matrices(d):
    parents={c:i for i,n in enumerate(d['nodes']) for c in n.get('children',[])}
    cache={}
    def matrix(i):
        if i in cache:return cache[i]
        n=d['nodes'][i]
        if 'matrix' in n:m=np.array(n['matrix']).reshape(4,4).T
        else:
            m=np.eye(4);m[:3,:3]=basis(n);m[:3,3]=n.get('translation',[0,0,0])
        if i in parents:m=matrix(parents[i])@m
        cache[i]=m
        return m
    return matrix

def samples(d,b):
    matrix=matrices(d);out=[];images={}
    for ni,node in enumerate(d['nodes']):
        if 'mesh' not in node:continue
        for pi,p in enumerate(d['meshes'][node['mesh']]['primitives']):
            points=accessor(d,b,p['attributes']['POSITION']).astype(float)
            points=(matrix(ni)@np.c_[points,np.ones(len(points))].T).T[:,:3]
            uv=accessor(d,b,p['attributes']['TEXCOORD_0'])
            mat=d['materials'][p['material']];ti=mat['pbrMetallicRoughness']['baseColorTexture']['index'];ii=d['textures'][ti]['source']
            if ii not in images:
                v=d['bufferViews'][d['images'][ii]['bufferView']];start=v.get('byteOffset',0)
                images[ii]=np.array(Image.open(io.BytesIO(b[start:start+v['byteLength']])).convert('RGB'))/255.
            image=images[ii];h,w=image.shape[:2]
            rgb=image[np.clip((uv[:,1]*h).astype(int),0,h-1),np.clip((uv[:,0]*w).astype(int),0,w-1)]
            indices=accessor(d,b,p['indices']).ravel().reshape(-1,3)
            out.append((node['mesh'],pi,points,rgb,indices))
    return out

def normalize_sets(items):
    allp=np.concatenate([x[2] for x in items]);lo=allp.min(0);hi=allp.max(0)
    origin=(lo+hi)/2;origin[1]=lo[1]
    scale=hi[1]-lo[1]
    return [(m,p,(xyz-origin)/scale,rgb,indices) for m,p,xyz,rgb,indices in items]

def inspect(path):
    d,b=unpack(path.read_bytes());items=normalize_sets(samples(d,b))
    for m,p,xyz,rgb,tri in items:
        avg=np.median(rgb,axis=0);center=xyz.mean(0)
        print(m,len(tri),'xyz',np.round(center,3).tolist(),'bounds',np.round(xyz.min(0),3).tolist(),np.round(xyz.max(0),3).tolist(),'rgb',np.round(avg,2).tolist())

def partition(rig_path,seg_path,character,output):
    d,b=unpack(rig_path.read_bytes());seg,sb=unpack(seg_path.read_bytes())
    mapping=json.loads((Path(__file__).with_name('avatar_parts.json')).read_text(encoding='utf-8-sig'))[character]
    families=list(mapping)+['detail']
    labels={part:families.index(family) for family,parts in mapping.items() for part in parts}
    segmented=normalize_sets(samples(seg,sb));original=normalize_sets(samples(d,b))
    points=np.concatenate([x[2] for x in segmented]);ids=np.concatenate([np.full(len(x[2]),labels.get(x[0],len(families)-1)) for x in segmented])
    tree=cKDTree(points)
    total=0;counts={};distances=[]
    for mi,pi,xyz,rgb,triangles in original:
        source=d['meshes'][mi]['primitives'][pi]
        distance,nearest=tree.query(xyz,k=1);distances.extend(distance.tolist())
        vertex_labels=ids[nearest];tri_labels=vertex_labels[triangles]
        chosen=np.array([np.bincount(row,minlength=len(families)).argmax() for row in tri_labels])
        primitives=[]
        for li,family in enumerate(families):
            selected=triangles[chosen==li]
            if not len(selected):continue
            # Only the index buffers change. POSITION/NORMAL/UV/JOINTS/WEIGHTS stay byte-for-byte.
            payload=selected.astype('<u4').tobytes();b.extend(b'\0'*(-len(b)%4))
            view=len(d['bufferViews']);d['bufferViews'].append({'buffer':0,'byteOffset':len(b),'byteLength':len(payload),'target':34963});b.extend(payload)
            acc=len(d['accessors']);d['accessors'].append({'bufferView':view,'componentType':5125,'count':selected.size,'type':'SCALAR','min':[int(selected.min())],'max':[int(selected.max())]})
            material=copy.deepcopy(d['materials'][source['material']])
            pixels=rgb[np.unique(selected)]
            reference=np.median(pixels,axis=0)
            if family=='skin': reference=np.quantile(pixels,0.65,axis=0)
            color='#'+''.join(f'{int(round(c*255)):02x}' for c in reference)
            material['name']=family+'__'+color[1:]
            material['extras']={'semantic_part':family,'reference_color':color,'source':'Tripo Segmentation v2 transferred to original skin'}
            mat=len(d['materials']);d['materials'].append(material)
            primitive=copy.deepcopy(source);primitive['indices']=acc;primitive['material']=mat;primitives.append(primitive)
            counts[family]=counts.get(family,0)+len(selected);total+=len(selected)
        assert total==sum(len(x[4]) for x in original), 'triangle conservation failed'
        d['meshes'][mi]['primitives']=primitives
    if np.quantile(distances,0.95)>.035:raise ValueError('segmentation does not align with bind geometry')
    d['asset']['extras']['part_transfer']={'triangles':total,'parts':counts,'distance_p95':float(np.quantile(distances,0.95))}
    output.write_bytes(pack(d,b));print(character,d['asset']['extras']['part_transfer'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('segmented',type=Path);parser.add_argument('--rig',type=Path);parser.add_argument('--character');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.rig:partition(args.rig,args.segmented,args.character,args.output)
    else:inspect(args.segmented)
