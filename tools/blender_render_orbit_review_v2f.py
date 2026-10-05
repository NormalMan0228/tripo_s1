import bpy,math
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_face_rig_manual_v2f';bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_orbit_gaze_v2f.blend'));sc=bpy.context.scene;sc.frame_set(1);rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];rig.animation_data.action=None
for o in sc.objects:
 if o.type=='MESH' and o.name.startswith(('Hair','Nape')):o.hide_render=True
c=sc.camera
def pose(lr=0,blink=0):
 for p in ['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']:rig[p]=0.
 rig['look_lr']=lr;rig['blink_L']=blink;rig['blink_R']=blink;rig.update_tag();bpy.context.view_layer.update()
def camera(side):
 t=Vector((.2,-.149,.065));c.location=t+Vector((1.1,-4,.04) if side else (4,-.4,0));c.rotation_euler=(t-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=.35
for amount,label in [(.5,'half'),(1,'closed')]:
 pose(blink=amount)
 for side in [False,True]:
  camera(side);sc.render.filepath=str(O/('eye-'+label+('-side' if side else '-front')+'.png'));bpy.ops.render.render(write_still=True)
sc.render.resolution_x=512;sc.render.resolution_y=512;sc.cycles.samples=8
frames=O/'review_frames';frames.mkdir(exist_ok=True)
for i in range(40):
 phase=(i%20)/19;yaw=math.sin(2*math.pi*phase)
 blink=max(0,1-abs(phase-.5)/.10)
 pose(yaw,blink);camera(i>=20);sc.render.filepath=str(frames/(f'{i:03d}.png'));bpy.ops.render.render(write_still=True)
print('ORBIT_REVIEW_RENDERED',flush=True)
