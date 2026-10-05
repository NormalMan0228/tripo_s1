import bpy,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_animated_v6';bpy.ops.wm.open_mainfile(filepath=str(A/'face_repaired_workbench.blend'));o=bpy.data.objects['FACE_skin_eyelids_lashes'];eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=eo.to_mesh();m.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in m.vertices],[t.vertices for t in m.loop_triangles],all_triangles=True)
for y,z in [(-.129,.1808),(-.055,.151),(.139,.044),(.054,.146),(.230,.18),(-.232,.17),(.08,.077)]:
 p,n,idx,d=tree.ray_cast(Vector((1,y,z)),Vector((-1,0,0)));t=m.loop_triangles[idx];poly=m.polygons[t.polygon_index];mat=m.materials[poly.material_index];print('SPOT',y,z,p,n,poly.index,mat.name)
eo.to_mesh_clear()
