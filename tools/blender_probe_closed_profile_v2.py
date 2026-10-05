import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_p2_closed_assembly_v1/explorer_b_P2_closed_assembly_v1.blend'))
o=bpy.data.objects['HEAD_closed_rest'];m=o.data;m.calc_loop_triangles();b=m.shape_keys.key_blocks[0]
t=BVHTree.FromPolygons([v.co for v in b.data],[tuple(p.vertices) for p in m.loop_triangles],all_triangles=True)
rows={}
for y in [0,.025,.05,.075]:
 a=[]
 for i in range(34):
  z=-.23+i*.005;p,*_=t.ray_cast(Vector((2,y,z)),Vector((-1,0,0)));a.append([round(z,3),round(p.x,5) if p else None])
 rows[str(y)]=a
print(json.dumps(rows))
