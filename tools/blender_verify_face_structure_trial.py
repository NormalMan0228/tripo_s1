"""Reopen the derived face study and verify structural and source integrity claims."""
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_face_structure_v1'
report=json.loads((OUT/'construction-report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=report['blend_file'])
meshes=[o for o in bpy.data.objects if o.type=='MESH']
assert all(not o.hide_select and not o.hide_viewport and not o.hide_get() for o in meshes)
assert not any(o.type=='ARMATURE' for o in bpy.data.objects)
assert not any(o.data.shape_keys for o in meshes)
expected={'Head_Skin_HD_Working','Eyeball_L','Eyeball_R','Hair_HD_Fitted_Study',
          'Hair_Inner_Cap_Study','Body_HD_Head_Replaced_Study','Mouth_Interior_Layout',
          'Tongue_Layout','Upper_Gum_Layout','Lower_Gum_Layout',
          'Upper_Teeth_Layout','Lower_Teeth_Layout'}
assert {o.name for o in meshes}==expected
head=bpy.data.objects['Head_Skin_HD_Working']
edges=np.empty(len(head.data.edges)*2,dtype=np.int32)
head.data.edges.foreach_get('vertices',edges)
parent=np.arange(len(head.data.vertices),dtype=np.int32)
def find(x):
    while parent[x]!=x:
        parent[x]=parent[parent[x]]
        x=parent[x]
    return x
for a,b in edges.reshape(-1,2):
    a,b=find(a),find(b)
    if a!=b:parent[b]=a
roots=np.array([find(i) for i in range(len(parent))])
_,counts=np.unique(roots,return_counts=True)
left=bpy.data.objects['Eyeball_L'];right=bpy.data.objects['Eyeball_R']
symmetry=abs(left.location.y+right.location.y)<1e-6 and abs(left.location.x-right.location.x)<1e-6 and abs(left.location.z-right.location.z)<1e-6
sources={part:hashlib.sha256(Path(info['file']).read_bytes()).hexdigest()==info['sha256'] for part,info in report['sources'].items()}
assert all(sources.values()) and symmetry
verification={'reopened_saved_blend':True,'mesh_objects':len(meshes),
              'all_meshes_selectable':True,'armatures':0,'shape_keys':0,
              'head_component_vertex_counts':sorted(counts.tolist(),reverse=True),
              'eyeballs_mirrored_position':symmetry,'source_blend_hashes_unchanged':sources,
              'api_credits_spent':0,'production_deformation_verified':False,
              'review_images':{n: (OUT/(n+'.png')).exists() for n in
                ['face-front','face-angle','face-side','body-fit-front','body-fit-angle','mouth-layout-cutaway']}}
(OUT/'delivery-verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
print(json.dumps(verification))
