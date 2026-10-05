import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1'
bpy.ops.wm.open_mainfile(filepath=str(O/'head/explorer_b_integrated_face_open_workbench.blend'))
o=bpy.data.objects['FACE_Tripo_integrated_0'];o.data.calc_loop_triangles()
t=BVHTree.FromPolygons([v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
data=[]
for y in [0,.04,.07,.10,-.04,-.07,-.10]:
 row=[]
 for i in range(41):
  z=-.20+i*.005;p,*_=t.ray_cast(Vector((1,y,z)),Vector((-1,0,0)));row.append([round(z,3),round(p.x,4) if p else None])
 data.append({'y':y,'front_x':row})
(O/'head/mouth-profile.json').write_text(json.dumps(data,indent=2),encoding='utf-8');print(json.dumps(data))
