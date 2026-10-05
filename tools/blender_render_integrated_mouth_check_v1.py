import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];OUT=R/'art/characters/explorer_b_integrated_face_haircards_v1/assembly'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_b_integrated_face_haircards_v1.blend'));sc=bpy.context.scene;ctrl=bpy.data.objects['FACE_CONTROLS'];cam=sc.camera;target=Vector((.23,0,-.10))
cam.location=target+Vector((3,-.1,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.34
for val,name in [(0.,'mouth_closed'),(1.,'mouth_open')]:
 ctrl['mouth_open']=val;ctrl.update_tag();sc.frame_set(1+int(val*100));bpy.context.view_layer.update()
 actual=bpy.data.objects['FACE_Tripo_integrated_0'].data.shape_keys.key_blocks['Mouth_open_Tripo_original'].value;assert abs(actual-val)<1e-6
 print('RENDERED_MOUTH_WEIGHT',val,actual);sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
