import bpy,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_animated_v6';bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_clean_edges_v5/assembly/explorer_b_clean_edges_v5.blend'));o=bpy.data.objects['FACE_skin_eyelids_lashes'];eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=eo.to_mesh();m.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in m.vertices],[t.vertices for t in m.loop_triangles],all_triangles=True);rows=[]
zz=np.linspace(-.12,-.015,1051)
for sign in [-1,1]:
 for y in np.arange(.065,.116,.0025):
  xs=[]
  for z in zz:
   p,*_=tree.ray_cast(Vector((1,sign*y,z)),Vector((-1,0,0)));xs.append(p.x if p else -.4)
  deficits=[]
  for i in range(50,len(xs)-50):deficits.append((min(max(xs[i-50:i-8]),max(xs[i+8:i+50]))-xs[i],i))
  d,idx=max(deficits);seam=float(zz[idx]);rows.append([sign*float(y),seam,float(d),float(xs[idx])])
(A/'mouth-actual-valleys.json').write_text(json.dumps(rows,indent=2));print('ACTUAL_MOUTH_VALLEYS',rows)
