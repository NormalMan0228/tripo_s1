import bpy,json
import numpy as np
from pathlib import Path
from mathutils.bvhtree import BVHTree
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_face_refined_v2';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art/characters/explorer_b_hd_restart_v1/head/head_HD.blend'))
o=next(o for o in bpy.data.objects if o.type=='MESH')
mesh=o.data
v=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',v);v=v.reshape(-1,3)
mesh.calc_loop_triangles();f=np.empty(len(mesh.loop_triangles)*3,dtype=np.int32);mesh.loop_triangles.foreach_get('vertices',f);f=f.reshape(-1,3)
bvh=BVHTree.FromPolygons(v.tolist(),f.tolist(),all_triangles=True)
rows=[]
for z in [.16,.11,.085,.065,.04,.0,-.035,-.065,-.085,-.115,-.2,-.235,-.255,-.275,-.295,-.315,-.335]:
    row={'z':z,'samples':{}}
    for y in [0,.04,.07,.10,.14,.17,.21,.25,.28,.30]:
        hit=bvh.ray_cast(Vector((1,y,z)),Vector((-1,0,0)))
        row['samples'][str(y)]=round(hit[0].x,4) if hit[0] else None
    rows.append(row)
(OUT/'surface-probe.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows))
