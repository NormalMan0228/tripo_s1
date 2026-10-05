import bpy,json
import numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1];OUT=R/'art/characters/explorer_b_face_rig_manual_v2b';blend=OUT/'explorer_profile_eye_v2b.blend'
bpy.ops.wm.open_mainfile(filepath=str(blend));sc=bpy.context.scene;rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
meshes=[o for o in sc.objects if o.type=='MESH' and o.visible_get() and not o.hide_render]
driven=[o.data.shape_keys for o in meshes if o.data.shape_keys and o.data.shape_keys.animation_data and o.data.shape_keys.animation_data.drivers]
tested=[o for o in meshes if not o.name.startswith(('Hair','Nape'))];first=None;prev=None;max_step=0;samples=[]
for f in range(1,241):
 sc.frame_set(f);deps=bpy.context.evaluated_depsgraph_get();points=[]
 for o in tested:
  ev=o.evaluated_get(deps);m=ev.to_mesh();a=np.array([v.co[:] for v in m.vertices]);ev.to_mesh_clear();points.append(a)
 a=np.concatenate(points);assert np.isfinite(a).all()
 if first is None:first=a.copy()
 if prev is not None:max_step=max(max_step,float(np.linalg.norm(a-prev,axis=1).max()))
 prev=a
 samples.append({'shapes':{sk.name:{k.name:float(k.value) for k in sk.key_blocks[1:]} for sk in driven},'eyes':{s:list(rig.pose.bones['eye.'+s].rotation_euler) for s in ('L','R')}})
assert np.max(np.abs(first-prev))<1e-7
sc.frame_set(1)
text=bpy.data.texts.get('READ_ME_FACE_CONTROLS');text.clear()
text.write('V2b — Profile support and fitted eyelids\nBased on accepted V2a lower-lip edit. Lower-lip/chin depth adjusted; smaller fitted eyeballs; relaxed upper lids; thin replacement lashes.\nSelect FACE_RIG__select_Custom_Properties > Object Properties > Custom Properties. Space plays the 240-frame comparison.\nblink_L/R, jaw_open, smile, frown, pucker, brow_up/brow_frown 0..1; look_lr/look_ud -1..1. Unlink demo Action to pose freely.\nOriginal lash objects are archived hidden. Previous V2a blend is unchanged.\nPrototype: eyelid/skin boundary polish and full facial retopology remain. Hair is hidden ONLY in inspection renders.\n')
sc['RIG_STATUS']='V2b profile depth and fitted relaxed eyelids. Prototype with residual eyelid boundary refinements.'
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(blend))
report=json.loads((OUT/'profile-eye-report.json').read_text(encoding='utf-8'));report.update(frames_checked=240,finite_coordinates=True,first_last_max_difference=float(np.max(np.abs(first-prev))),max_per_frame_vertex_step=max_step,visual_checks=['front','profile','oblique eye closeup','closed eyelids'],remaining_limitations=['Eyelid/skin junction is still a separate surface; small seams remain at close range.','Original AI head topology retained; not production retopology.','Godot playback not checked this turn.'])
(OUT/'profile-eye-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for sk in driven:
 for fc in list(sk.animation_data.drivers):sk.driver_remove(fc.data_path)
for side in ('L','R'):
 for axis in (1,2):rig.pose.bones['eye.'+side].driver_remove('rotation_euler',axis)
for f,sample in enumerate(samples,1):
 for sk in driven:
  for name,value in sample['shapes'][sk.name].items():
   k=sk.key_blocks[name];k.value=value;k.keyframe_insert('value',frame=f)
 for side,rot in sample['eyes'].items():
  pb=rig.pose.bones['eye.'+side];pb.rotation_euler=rot;pb.keyframe_insert('rotation_euler',frame=f)
sc.frame_set(1)
for o in sc.objects:o.select_set(False)
for o in meshes:o.select_set(True)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer_profile_eye_v2b.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='SCENE',export_anim_scene_split_object=False,export_force_sampling=True,export_frame_range=True,export_skins=True,export_morph=True,export_morph_animation=True,export_cameras=False,export_lights=False)
print('PROFILE_EYE_VALIDATED',max_step,flush=True)
