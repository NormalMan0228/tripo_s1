"""Merge reviewed authored Tripo clips without changing the skinned geometry."""
import argparse,copy,json
from pathlib import Path
from tools.merge_explorer_animations import unpack,pack,remove_horizontal_drift

def merge_clips(clips):
    doc,binary=unpack(clips[0][1].read_bytes())
    doc['animations']=[]
    names={n.get('name'):i for i,n in enumerate(doc['nodes'])}
    for label,path in clips:
        source,data=unpack(path.read_bytes())
        if not source.get('animations'): raise ValueError(f'No animation: {path}')
        # Same source character must have the same bind pose, hierarchy and skin.
        if source['nodes']!=doc['nodes'] or source['skins']!=doc['skins']:
            raise ValueError(f'Incompatible bind pose: {path}')
        animation=copy.deepcopy(source['animations'][0]);animation['name']=label
        if label in ('walk','run'): remove_horizontal_drift(source,data,animation)
        views={};accessors={}
        def copy_accessor(index):
            if index in accessors:return accessors[index]
            acc=copy.deepcopy(source['accessors'][index]);old=acc['bufferView']
            if old not in views:
                view=copy.deepcopy(source['bufferViews'][old]);start=view.get('byteOffset',0)
                payload=data[start:start+view['byteLength']]
                binary.extend(b'\0'*(-len(binary)%4));view['byteOffset']=len(binary)
                views[old]=len(doc['bufferViews']);doc['bufferViews'].append(view);binary.extend(payload)
            acc['bufferView']=views[old]
            accessors[index]=len(doc['accessors']);doc['accessors'].append(acc)
            return accessors[index]
        for sampler in animation['samplers']:
            sampler['input']=copy_accessor(sampler['input']);sampler['output']=copy_accessor(sampler['output'])
        doc['animations'].append(animation)
    doc['asset']['extras']={'source':'Scenario Tripo authored game assets','clips':[x[0] for x in clips],'in_place':['walk','run']}
    return pack(doc,binary)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);parser.add_argument('clips',nargs='+')
    args=parser.parse_args();clips=[(s.split('=',1)[0],Path(s.split('=',1)[1])) for s in args.clips]
    args.output.write_bytes(merge_clips(clips));print('Merged:',','.join(x[0] for x in clips))
