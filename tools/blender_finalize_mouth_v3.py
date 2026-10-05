import bpy, json
import numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1];OUT=R/'art/characters/explorer_b_face_rig_manual_v3'
blend=OUT/'explorer_manual_face_rig_v3.blend'
bpy.ops.wm.open_mainfile(filepath=str(blend));sc=bpy.context.scene
rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];head=bpy.data.objects['01_Face_skin_neck']
visible=[o for o in sc.objects if o.type=='MESH' and o.visible_get() and not o.hide_render]
driven=[o.data.shape_keys for o in visible if o.data.shape_keys and o.data.shape_keys.animation_data and o.data.shape_keys.animation_data.drivers]
first=None;prev=None;max_step=0;samples=[]
for frame in range(1,241):
 sc.frame_set(frame);ev=head.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 arr=np.array([v.co[:] for v in mesh.vertices]);ev.to_mesh_clear();assert np.isfinite(arr).all()
 if first is None:first=arr.copy()
 if prev is not None:max_step=max(max_step,float(np.linalg.norm(arr-prev,axis=1).max()))
 prev=arr
 samples.append({'shapes':{sk.name:{k.name:float(k.value) for k in sk.key_blocks[1:]} for sk in driven},'eyes':{s:list(rig.pose.bones['eye.'+s].rotation_euler) for s in ('L','R')}})
assert np.abs(first-prev).max()<1e-7
report=json.loads((OUT/'mouth-refinement-report.json').read_text(encoding='utf-8'))
report.update(frames_checked=240,all_coordinates_finite=True,loop_max_difference=float(np.abs(first-prev).max()),max_frame_step=max_step,
 closed_mouth='Thin lip contact seam; microscopic clearance retained to avoid coincident faces.',
 visual_review='Neutral, smile, opened mouth, frontal closeup and oblique view inspected.',
 remaining_limitations=['Source topology outside the local mouth patch is not fully retopologized.','Manual prototype, not an ARKit/Faceit facial rig.','No Godot playback validation this turn.'])
(OUT/'mouth-refinement-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
sc.frame_set(1)
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS');txt.clear()
txt.write('MOUTH V3 — Closed rest pose and local oral retopology\nThin lower lip, softened philtrum, warm rose oral lining/gums/tongue. Original chin retained.\nSpace plays the 240-frame comparison.\nSelect FACE_RIG__select_Custom_Properties > Object Properties > Custom Properties.\nUnlink the demo action to pose manually. jaw_open 0=closed, 1=open.\nOther sliders: blink_L/R, smile, frown, pucker, brow_up, brow_frown (0..1), look_lr/look_ud (-1..1).\nMaterial colors are visible in Material Preview or Solid > Color: Material.\nPrototype: source topology outside local mouth patch remains. No Faceit or full ARKit set.\n')
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for sk in driven:
 for fc in list(sk.animation_data.drivers):sk.driver_remove(fc.data_path)
for side in ('L','R'):
 for axis in (1,2):rig.pose.bones['eye.'+side].driver_remove('rotation_euler',axis)
for i,sample in enumerate(samples,1):
 for sk in driven:
  for name,value in sample['shapes'][sk.name].items():
   k=sk.key_blocks[name];k.value=value;k.keyframe_insert('value',frame=i)
 for side,rot in sample['eyes'].items():
  pb=rig.pose.bones['eye.'+side];pb.rotation_euler=rot;pb.keyframe_insert('rotation_euler',frame=i)
sc.frame_set(1)
for obj in sc.objects:obj.select_set(False)
for obj in visible:obj.select_set(True)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer_manual_face_rig_v3.glb'),export_format='GLB',use_selection=True,export_animations=True,
 export_animation_mode='SCENE',export_anim_scene_split_object=False,export_force_sampling=True,export_frame_range=True,
 export_skins=True,export_morph=True,export_morph_animation=True,export_cameras=False,export_lights=False)
print('MOUTH_V3_VALIDATED',max_step,flush=True)
