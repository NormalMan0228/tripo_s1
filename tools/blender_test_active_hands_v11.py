import bpy,math
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v11';ns={'__file__':str(R/'tools/blender_npc_reference_rig_v11.py')};exec((R/'tools/blender_npc_reference_rig_v11.py').read_text(encoding='utf-8-sig').split('\nreports={}')[0],ns)
for key,frame in [('sora',211),('naru',391)]:
 bpy.ops.wm.open_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v11.blend'));scene=bpy.context.scene;scene.frame_set(frame);rig=bpy.data.objects[key+'_BodyRig'];rig.animation_data_clear()
 for c in bpy.data.collections:
  if c.name in ['SORA','MORU','NARU','HAERU']:c.hide_render=c.name!=key.upper()
 scene.render.resolution_x=700;scene.render.resolution_y=700
 if key=='sora':
  ns['ns']['ns']['solve_limb'](rig,'UpperArm.R','Forearm.R',(.105*1.65,-.045*1.65,.775*1.65),(.16*1.65,-.19*1.65,.60*1.65),1.)
  rig.pose.bones['ElbowSupport.R'].rotation_quaternion=Quaternion().slerp(rig.pose.bones['Forearm.R'].rotation_quaternion,.5)
 for roll in [-70,0,70]:
  rig.pose.bones['ForeTwist.R'].rotation_quaternion=Quaternion(Vector((0,1,0)),math.radians(roll));rig.pose.bones['Hand.R'].rotation_quaternion=Quaternion();ns['align_wrist'](rig,'R');bpy.context.view_layer.update()
  b=rig.pose.bones['Hand.R'];center=rig.matrix_world@((b.head+b.tail)/2);cam=scene.camera;cam.location=center+Vector((2,.1,.1));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.4
  scene.render.filepath=str(O/(key+'-hand-roll-'+str(roll)+'.png'));bpy.ops.render.render(write_still=True)

