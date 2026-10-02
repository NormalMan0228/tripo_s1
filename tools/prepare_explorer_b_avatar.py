"""Developer-only wardrobe surfaces. Original geometry, normals, UVs and weights stay byte-identical.
Face, hair, fingers and exposed arms are deliberately kept in the untouched detail material.
"""
from pathlib import Path
import sys,copy,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.merge_explorer_animations import unpack,pack
from tools.partition_avatar import samples,normalize_sets,accessor

def main():
    original=(ROOT/'game/assets/explorer_b_reference.glb').read_bytes();doc,binary=unpack(original)
    initial=bytes(binary);counts={};protected=0
    for mesh_id,primitive_id,xyz,rgb,triangles in normalize_sets(samples(doc,binary)):
        source=copy.deepcopy(doc['meshes'][mesh_id]['primitives'][primitive_id])
        center=xyz[triangles].mean(1);color=rgb[triangles].mean(1)
        family=np.full(len(triangles),'detail',dtype='<U8')
        family[(center[:,1]<.15)]='boots'
        family[(center[:,1]>=.15)&(center[:,1]<.48)]='pants'
        # Broaden cloth around texture edges; per-fragment tint avoids jagged triangles.
        attributes=source['attributes'];weights=accessor(doc,binary,attributes['WEIGHTS_0'])
        joints=accessor(doc,binary,attributes['JOINTS_0']).astype(int)
        skin=doc['skins'][next(n['skin'] for n in doc['nodes'] if n.get('mesh')==mesh_id)]
        protected_joint=np.array([any(k in doc['nodes'][i].get('name','') for k in ['Head','Neck','Hand','Thumb','Index','Middle','Ring','Little']) for i in skin['joints']])
        skin_weight=(protected_joint[joints]*weights).sum(1)
        allowed=(center[:,1]>=.48)&(center[:,1]<.84)&(skin_weight[triangles].max(1)<.12)
        gold=(rgb[:,0]>rgb[:,1]*1.10)&(rgb[:,1]>rgb[:,2]*1.25)
        coat=allowed&gold[triangles].any(1)
        for _ in range(2):
            vertices=np.zeros(len(xyz),bool);vertices[np.unique(triangles[coat])]=True
            coat|=allowed&vertices[triangles].any(1)
        family[coat]='coat'
        protected+=int(((center[:,1]>=.73)&(family=='detail')).sum())
        primitives=[]
        for part in ['detail','coat','pants','boots']:
            selected=triangles[family==part]
            if not len(selected):continue
            data=selected.astype('<u4').tobytes();binary.extend(b'\0'*(-len(binary)%4))
            view=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':len(data),'target':34963});binary.extend(data)
            acc=len(doc['accessors']);doc['accessors'].append({'bufferView':view,'componentType':5125,'count':selected.size,'type':'SCALAR','min':[int(selected.min())],'max':[int(selected.max())]})
            material=copy.deepcopy(doc['materials'][source['material']]);ref=np.median(rgb[np.unique(selected)],0)
            material['name']=part+'__'+''.join(f'{round(float(v)*255):02x}' for v in ref)
            mat=len(doc['materials']);doc['materials'].append(material)
            primitive=copy.deepcopy(source);primitive.update(indices=acc,material=mat);primitives.append(primitive)
            counts[part]=len(selected)
        assert sum(len(triangles[family==k]) for k in counts)==len(triangles)
        doc['meshes'][mesh_id]['primitives']=primitives
    assert bytes(binary[:len(initial)])==initial
    output=ROOT/'game/assets/explorer_b_wardrobe.glb';output.write_bytes(pack(doc,binary))
    report={'source_sha256':hashlib.sha256(original).hexdigest(),'output':str(output),'triangles':counts,
            'original_binary_prefix_unchanged':True,'protected_upper_triangles':protected,
            'limitations':'Coat/pants/boots only; face, hair and hands keep original material. No skin/face editing.'}
    (ROOT/'artifacts/characters/explorer-b-hand-v4/wardrobe-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
