import bpy,math
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v11';ns={'__file__':str(R/'tools/blender_npc_reference_rig_v11.py')};exec((R/'tools/blender_npc_reference_rig_v11.py').read_text().split('\nreports={}')[0],ns)
bpy.ops.wm.open_mainfile(filepath=str(O/'npc_rigged_idle_lineup_v11.blend'));scene=bpy.context.scene;scene.frame_set(1);rig=bpy.data.objects['haeru_BodyRig'];rig.animation_data_clear();h=1.85
for c in bpy.data.collections:
 if c.name in ['SORA','MORU','NARU','HAERU']:c.hide_render=c.name!='HAERU'
for side,sign in [('L',1),('R',-1)]:
 ns['ns']['ns']['solve_limb'](rig,'UpperArm.'+side,'Forearm.'+side,((.075 if side=='L' else .085)*h,-sign*.075*h,(.700 if side=='L' else .715)*h),(.06*h,sign*.17*h,.625*h),1.)
 rig.pose.bones['ElbowSupport.'+side].rotation_quaternion=Quaternion().slerp(rig.pose.bones['Forearm.'+side].rotation_quaternion,.5)
cam=scene.camera;cam.location=(5,1.95,1.22);cam.rotation_euler=Vector((-1,0,0)).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.1;scene.render.resolution_x=800;scene.render.resolution_y=800
for roll in [-65,0,65]:
 for side,sign in [('L',1),('R',-1)]:
  rig.pose.bones['ForeTwist.'+side].rotation_quaternion=Quaternion(Vector((0,1,0)),math.radians(-sign*roll));rig.pose.bones['Hand.'+side].rotation_quaternion=Quaternion();ns['align_wrist'](rig,side)
 scene.render.filepath=str(O/('folded-arms-'+str(roll)+'.png'));bpy.ops.render.render(write_still=True)
