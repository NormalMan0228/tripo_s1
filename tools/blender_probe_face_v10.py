import bpy,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10';A.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_original_identity_v9/original_face_mpfb_rigify_v9.blend'));sc=bpy.context.scene;sc.frame_set(1);out={}
for o in sc.objects:
 if o.type!='MESH' or o.hide_render:continue
 ps=[o.matrix_world@v.co for v in o.data.vertices];out[o.name]={'verts':len(ps),'lo':[min(p[i] for p in ps) for i in range(3)],'hi':[max(p[i] for p in ps) for i in range(3)]}
head=bpy.data.objects['FACE_original_user_GLb'];head.data.calc_loop_triangles();ps=[v.co.copy() for v in head.data.vertices];tree=BVHTree.FromPolygons(ps,[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True)
grid=[]
for y in np.linspace(-.115,.115,47):
 row=[]
 for z in np.linspace(-.22,-.025,196):
  p,*_=tree.ray_cast(Vector((1,y,z)),Vector((-1,0,0)));row.append(p.x if p else None)
 grid.append(row)
out['mouth_grid']={'y':np.linspace(-.115,.115,47).tolist(),'z':np.linspace(-.22,-.025,196).tolist(),'x':grid};(A/'probe.json').write_text(json.dumps(out,indent=2))
np.savez(A/'head_arrays.npz',vertices=np.array(ps),triangles=np.array([tuple(t.vertices) for t in head.data.loop_triangles]))
cam=sc.camera
for label,target,scale in [('mouth',Vector((.2,0,-.10)),.30),('eyeL',Vector((.2,.12,.11)),.26),('side',Vector((0,0,0)),1.2)]:
 cam.location=target+Vector((3,0,0) if label!='side' else (0,-3,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(label+'_source.png'));bpy.ops.render.render(write_still=True)
print('V10_PROBE_COMPLETE')
