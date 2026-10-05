import bpy,bmesh
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];OUT=R/'art/characters/explorer_b_integrated_face_haircards_v1/assembly'
for filename in ['explorer_b_integrated_face_haircards_open.blend','explorer_b_integrated_face_haircards_v1.blend']:
 bpy.ops.wm.open_mainfile(filepath=str(OUT/filename));bpy.context.preferences.filepaths.save_version=0
 for name in ['HAIR_scalp_undercoat','HAIR_bob_lowpoly_undercoat']:
  o=bpy.data.objects[name]
  if not o.get('outward_normals_verified'):
   bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update();o['outward_normals_verified']=True
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/filename))
sc=bpy.context.scene;cam=sc.camera
for name,pos in [('rest_front',(3,0,0)),('rest_angle',(3,-2,0)),('rest_side',(0,-3,0)),('back',(-3,0,0))]:
 cam.location=Vector(pos);cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.18;sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
print('FINAL_NORMALS_RENDERS_SAVED')
