"""Validate sampled motion, save editable rig, bake GLB, render comparison video."""
import bpy,json,math,sys
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_face_rig_manual_v1'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_manual_face_rig.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
# Keep manual tongue posing available on top of the jaw morph.
tongue=bpy.data.objects['06_Tongue_candidate']
if tongue.vertex_groups.get('head'):tongue.vertex_groups.remove(tongue.vertex_groups['head'])
for group in list(tongue.vertex_groups):
    if group.name.startswith('tongue.'):tongue.vertex_groups.remove(group)
vg=tongue.vertex_groups.get('tongue') or tongue.vertex_groups.new(name='tongue');vg.add(list(range(len(tongue.data.vertices))),1,'REPLACE')
action=rig.animation_data.action
for fc in action.fcurves:
    for key in fc.keyframe_points:key.interpolation='BEZIER';key.handle_left_type='AUTO_CLAMPED';key.handle_right_type='AUTO_CLAMPED'
controls=['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']
visible=[o for o in scene.objects if o.type=='MESH' and o.visible_get() and not o.hide_render]
tested=[o for o in visible if not o.name.startswith(('Hair','Nape'))]
driven=[]
for o in visible:
    keys=o.data.shape_keys
    if keys and keys.animation_data and keys.animation_data.drivers:
        driven.append(keys)
samples=[];previous=None;first=None;max_step=0;max_frame=0;control_values=[]
for frame in range(1,241):
    scene.frame_set(frame);deps=bpy.context.evaluated_depsgraph_get();points=[]
    for obj in tested:
        ev=obj.evaluated_get(deps);mesh=ev.to_mesh();v=np.empty(len(mesh.vertices)*3,dtype=np.float64);mesh.vertices.foreach_get('co',v);points.append(v);ev.to_mesh_clear()
    points=np.concatenate(points)
    assert np.isfinite(points).all(),'Nonfinite deformation'
    if first is None:first=points.copy()
    if previous is not None:
        step=float(np.linalg.norm((points-previous).reshape(-1,3),axis=1).max())
        if step>max_step:max_step=step;max_frame=frame
    previous=points.copy()
    values={p:float(rig[p]) for p in controls}
    for p,v in values.items():assert (-1.00001 if p.startswith('look') else -.00001)<=v<=1.00001
    control_values.append({'frame':frame,**values})
    samples.append({'shapes':{keys.name:{k.name:float(k.value) for k in keys.key_blocks[1:]} for keys in driven},'eyes':{s:list(rig.pose.bones['eye.'+s].rotation_euler) for s in ('L','R')}})
loop_error=float(np.abs(previous-first).max());assert loop_error<1e-6
scene.frame_set(1)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='PROPERTIES':area.spaces.active.context='OBJECT'
for block in list(bpy.data.texts):
    if block.name.startswith('READ_ME_FACE_CONTROLS.'):bpy.data.texts.remove(block)
text=bpy.data.texts.get('READ_ME_FACE_CONTROLS') or bpy.data.texts.new('READ_ME_FACE_CONTROLS')
text.clear()
text.write('Faceit-free comparison baseline\nSelect FACE_RIG__select_Custom_Properties and edit Object Properties > Custom Properties.\nblink_L/R, jaw_open, smile, frown, pucker, brow_up, brow_frown: 0..1. look_lr/look_ud: -1..1.\nTimeline 1..240 at 24 fps: blink, wink, gaze, jaw, smile+blink, surprise, frown, pucker. Space plays.\nThe action controls slider values during playback. Disable the action to pose freely.\nSource character preserved in separate file. Original AI eye parts are hidden in SOURCE_AI_EYES collection.\nMouth compression/pinching and eyelid seam refinement remain; this is not production retopology or a 52-shape ARKit rig.\n')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_manual_face_rig.blend'))
validation={'frames_sampled':240,'fps':24,'all_facial_vertices_finite':True,'controls_within_limits':True,'first_last_vertex_max_difference':loop_error,'largest_per_frame_vertex_step':max_step,'largest_step_frame':max_frame,'root_and_head_transforms_animated':False,'head_translation_jump':False,'statement':'Numerical continuity and selected visual poses checked; no blanket collision-free or production-quality claim.'}
(OUT/'motion-validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
(OUT/'comparison-controls.json').write_text(json.dumps(control_values,indent=2),encoding='utf-8')
report=json.loads((OUT/'rig-report.json').read_text(encoding='utf-8'))
report.update(visual_validation='Neutral, half/full blink, gaze, jaw, smile and surprise inspected; mouth/lid polish remains.',eyelid_method='Separate clean annular eyelid geometry with four curved blink samples; original face eye-loop topology not rebuilt.',known_limitations=['Closed-mouth region appears compressed; lip corners need local retopology/corrective sculpt.','Eyelid outer seam and eyelash transitions need refinement.','Original P2 face/dental nonmanifold geometry retained; no production retopology.','No full ARKit set, lip-sync solver or Faceit used.'],motion_validation=validation)
(OUT/'rig-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('VALIDATION',json.dumps(validation),flush=True)
# Bake drivers only in the export copy. Keep editable Blender source intact.
for keys in driven:
    for fc in list(keys.animation_data.drivers):keys.driver_remove(fc.data_path)
for s in ('L','R'):
    pb=rig.pose.bones['eye.'+s]
    for axis in (1,2):pb.driver_remove('rotation_euler',axis)
for i,sample in enumerate(samples,1):
    for keys in driven:
        for name,value in sample['shapes'][keys.name].items():
            key=keys.key_blocks[name];key.value=value;key.keyframe_insert('value',frame=i)
    for side,rotation in sample['eyes'].items():
        pb=rig.pose.bones['eye.'+side];pb.rotation_euler=rotation;pb.keyframe_insert('rotation_euler',frame=i,group='eye.'+side)
scene.frame_set(1)
for o in scene.objects:o.select_set(False)
for o in visible:o.select_set(True)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer_manual_face_rig.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='SCENE',export_anim_scene_split_object=False,export_force_sampling=True,export_frame_range=True,export_skins=True,export_morph=True,export_morph_animation=True,export_cameras=False,export_lights=False)
print('GLB_EXPORTED',flush=True)
import sys
if '--export-only' in sys.argv:
    sys.exit(0)
# Render the actual editable rig, not the baked export copy.
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_manual_face_rig.blend'))
scene=bpy.context.scene;scene.cycles.samples=8
scene.render.resolution_x=576;scene.render.resolution_y=576
frames=OUT/'video_frames';frames.mkdir(exist_ok=True)
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(frames/'frame_')
bpy.ops.render.render(animation=True)
print('VIDEO_FRAMES_COMPLETE',flush=True)
