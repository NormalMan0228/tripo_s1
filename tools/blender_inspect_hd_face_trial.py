import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/characters/explorer_b_hd_restart_v1'
OUT = ROOT/'art/characters/explorer_b_face_structure_v1'
OUT.mkdir(exist_ok=True)
report = {}
for part in ['head','fullbody','hair']:
    bpy.ops.wm.open_mainfile(filepath=str(BASE/part/f'{part}_HD.blend'))
    obj = next(o for o in bpy.data.objects if o.type=='MESH')
    mesh = obj.data
    coords = np.empty(len(mesh.vertices)*3, dtype=np.float32)
    mesh.vertices.foreach_get('co', coords)
    coords=coords.reshape(-1,3)
    mat = np.array(obj.matrix_world)
    coords = coords@mat[:3,:3].T+mat[:3,3]
    edges=np.empty(len(mesh.edges)*2,dtype=np.int32)
    mesh.edges.foreach_get('vertices',edges)
    edges=edges.reshape(-1,2)
    parent=np.arange(len(coords))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    for a,b in edges:
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    roots=np.array([find(i) for i in range(len(coords))])
    unique, counts=np.unique(roots,return_counts=True)
    components=[]
    for index in np.argsort(counts)[::-1][:30]:
        subset=coords[roots==unique[index]]
        components.append({'root':int(unique[index]),'vertices':int(counts[index]),'min':subset.min(0).tolist(),'max':subset.max(0).tolist(),'mean':subset.mean(0).tolist()})
    sections=[]
    for z in np.linspace(coords[:,2].min(),coords[:,2].max(),30):
        subset=coords[np.abs(coords[:,2]-z)<.004]
        if len(subset): sections.append({'z':float(z),'min':subset.min(0).tolist(),'max':subset.max(0).tolist()})
    report[part]={'matrix':mat.tolist(),'components':components,'sections':sections}
    np.savez_compressed(OUT/f'{part}-inspection.npz',coords=coords,roots=roots)
(OUT/'source-inspection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FACE_SOURCE_INSPECTION_COMPLETE')
