import bpy,json
import numpy as np
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v6'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'archipelago_terrain_v6.blend'))
result={}
for obj in bpy.context.scene.objects:
    if not (obj.name=='Waterfall__water_volume' or obj.name.startswith('Waterfall__stream_volume_')):
        continue
    obj.data.calc_loop_triangles()
    vertices=np.array([vertex.co[:] for vertex in obj.data.vertices])
    triangles=np.array([triangle.vertices[:] for triangle in obj.data.loop_triangles])
    points=vertices[triangles]
    volume=np.sum(np.einsum('ij,ij->i',points[:,0],np.cross(points[:,1],points[:,2])))/6
    edges=Counter();directions=Counter()
    for polygon in obj.data.polygons:
        ids=list(polygon.vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):
            key=(min(a,b),max(a,b));edges[key]+=1;directions[key]+=1 if a<b else -1
    nonmanifold=sum(count!=2 for count in edges.values())
    inconsistent=sum(balance!=0 for balance in directions.values())
    result[obj.name]={'vertices':len(vertices),'triangles':len(triangles),'signed_volume_m3':float(volume),'nonmanifold_edges':nonmanifold,'inconsistent_edge_orientation':inconsistent}
(OUT/'water_volume_verification.json').write_text(json.dumps(result,indent=2))
print('WATER_VOLUME_AUDIT',json.dumps(result),flush=True)
assert len(result)==8
assert all(data['signed_volume_m3']>0 and data['nonmanifold_edges']==0 and data['inconsistent_edge_orientation']==0 for data in result.values())
print('WATER_VOLUME_AUDIT_PASS',flush=True)

