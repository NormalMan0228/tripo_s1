import bpy,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly';bpy.ops.wm.open_mainfile(filepath=str(A/'face_local_cleanup.blend'));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes']
polys=head.data.polygons;original_mask=[p for p in polys if p.material_index==1];kd=KDTree(len(original_mask))
for i,p in enumerate(original_mask):kd.insert(p.center,i)
kd.balance();added=[]
for p in polys:
 c=p.center
 if not c.x>.135 or not .074<abs(c.y)<.249 or not .108<c.z<.195:continue
 _,i,d=kd.find(c)
 # The solid outer lash wing has a peach-colored tip. Cover the entire
 # narrow wing surface while keeping the upper lid skin beyond it unchanged.
 limit=.012 if abs(c.y)>.185 else .0065
 if d<limit and p.material_index!=1:p.material_index=1;added.append(p.index)
sc.cycles.samples=16;cam=sc.camera;target=Vector((.18,0,.145));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.52;sc.render.filepath=str(A/'lashes_refined.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(A/'face_lashes_refined.blend'));(A/'lash-refinement.json').write_text(json.dumps({'added_faces':len(added),'total_dark_lash_faces':len(original_mask)+len(added),'method':'dark atlas ribbon + narrow geometric tip envelope; eyelid skin remains original atlas'},indent=2),encoding='utf-8');print('LASH_REFINED',len(added))
