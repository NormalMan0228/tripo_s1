import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10';F=A/'original_preserved_face_rig_v10.blend';bpy.ops.wm.open_mainfile(filepath=str(F));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];a=bpy.data.actions['IdleClosed'];rig.animation_data.action=a;rig.animation_data.action_slot=a.slots[0];sc.frame_start=1;sc.frame_end=90;sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT');rig.hide_set(False);rig.select_set(True);bpy.context.view_layer.objects.active=rig
for b in rig.data.bones:b.select=b.name=='head'
rig.data.bones.active=rig.data.bones['head'];bpy.ops.object.mode_set(mode='POSE');cam=sc.camera;cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.region_3d.view_location=(0,0,0);sp.region_3d.view_distance=1.45;sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_perspective='ORTHO';sp.shading.type='MATERIAL';sp.overlay.show_extras=False
  elif area.type=='DOPESHEET_EDITOR':area.ui_type='DOPESHEET';area.spaces.active.mode='ACTION'
bpy.ops.wm.save_as_mainfile(filepath=str(F));print('V10_READY_FOR_BLENDER_REVIEW')
