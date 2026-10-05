"""Reopen the saved template, check evaluated motion, and improve review lighting."""
import bpy
import addon_utils
from pathlib import Path
from mathutils import Vector
import json, math

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'artifacts/face-stack-test-20261004'
human=bpy.data.objects['Template_Face_Body']
keys=human.data.shape_keys.key_blocks
scene=bpy.context.scene
rig=bpy.data.objects['Template_Control_Rig']
assert addon_utils.check('bl_ext.user_default.mpfb')[1] and addon_utils.check('rigify')[1]
samples=[]
deps=bpy.context.evaluated_depsgraph_get()
for frame in [1,10,19,37,55,139,199,259,319,379,439,499,559,619,655]:
    scene.frame_set(frame);bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.type!='MESH' or obj==human or not obj.data.shape_keys:continue
        for key in obj.data.shape_keys.key_blocks:
            if key.name in keys and key.name!='Basis':assert abs(key.value-keys[key.name].value)<1e-6,(frame,obj.name,key.name)
    ev=human.evaluated_get(deps);mesh=ev.to_mesh()
    assert all(math.isfinite(c) for v in mesh.vertices for c in v.co)
    ev.to_mesh_clear()
    samples.append({'frame':frame,'blink':keys['eyeBlinkLeft'].value,'jaw':keys['jawOpen'].value,'pucker':keys['mouthPucker'].value})
assert 0<samples[1]['blink']<.25,'No interpolated in-between pose'
scene.frame_set(1)
initial=human.evaluated_get(deps).to_mesh()
baseline=[v.co.copy() for v in initial.vertices]
human.evaluated_get(deps).to_mesh_clear()
head=rig.pose.bones.get('head')
assert head is not None
old=head.rotation_quaternion.copy();head.rotation_mode='QUATERNION';head.rotation_quaternion=__import__('mathutils').Quaternion((0,1,0),math.radians(8))
bpy.context.view_layer.update()
ev=human.evaluated_get(deps);mesh=ev.to_mesh()
shift=max((v.co-c).length for v,c in zip(mesh.vertices,baseline));ev.to_mesh_clear()
assert shift>.001,shift
head.rotation_quaternion=old;bpy.context.view_layer.update()
scene.view_settings.exposure=-1.3
scene.cycles.samples=32
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.show_region_ui=False
            area.spaces.active.region_3d.view_camera_zoom=8
            area.spaces.active.shading.type='MATERIAL'
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
result={'fresh_process_addons_enabled':True,'saved_blend_reopened':True,'sampled_frames':samples,
    'child_shape_driver_matches':True,'evaluated_vertices_finite':True,'rigify_head_control_displacement_m':shift,
    'note':'Functional integration test, not final character styling or Godot export acceptance.'}
(REPORT/'reopen-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

eye=bpy.data.objects['Template_Face_Body.high-poly']
points=[eye.matrix_world@v.co for v in eye.data.vertices]
target=sum(points,Vector())/len(points)+Vector((0,0,-.042))
camera=scene.camera
for label,frame,angle in [('Neutral',1,0),('Blink_25',19,0),('Blink_50',79,0),('Blink_75',139,0),('Blink_100',199,0),('Look_Left',259,0),('Look_Right',319,0),('Jaw_Open',379,0),('Smile',439,0),('Pucker',499,0),('Gaze_Blink',559,0),('Viseme_AA',619,0),('Profile_Neutral',1,85),('ThreeQuarter_Blink',199,45),('ThreeQuarter_Gaze',259,45),('Profile_Jaw',379,85)]:
    scene.frame_set(frame)
    rad=math.radians(angle);camera.location=target+Vector((math.sin(rad)*1.2,-math.cos(rad)*1.2,.035))
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(REPORT/(label+'.png'));bpy.ops.render.render(write_still=True)
print('REOPEN_VERIFIED',json.dumps(result),flush=True)
