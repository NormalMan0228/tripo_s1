import bpy,json,math
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';FILE=A/'explorer_b_balanced_face_v4.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;ctrl=bpy.data.objects['FACE_CONTROLS'];head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh']
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
names=['GUMS_lower']+['TOOTH_%02d'%i for i in [9,17,19,20,21,23,24,26,27,28,29]]
for name in names:
 o=bpy.data.objects[name];basis=o.data.shape_keys.key_blocks[0]
 for v,b in zip(o.data.vertices,basis.data):b.co.z-=.020*smooth(.052,.079,abs(b.co.y));v.co=b.co
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();cam=sc.camera;sc.cycles.samples=32
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
render('front',(3,0,0));render('angle',(3,-2,0));hair.hide_render=True;render('mouth_closed',(3,-.6,0),Vector((.26,0,-.092)),.34);render('mouth_front',(3,0,0),Vector((.26,0,-.092)),.34);hair.hide_render=False
target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23;bpy.ops.wm.save_as_mainfile(filepath=str(FILE));print('POSTERIOR_MOLARS_REST_CORRECTED')
