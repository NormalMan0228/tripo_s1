import bpy, json, hashlib
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_face_rig_manual_v2'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_manual_face_rig_v2.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
head=bpy.data.objects['01_Face_skin_neck'];keys=head.data.shape_keys.key_blocks
source=np.array([p.co[:] for p in keys['jawOpen'].data]);anchor=source[:,2]<=-.265
key_errors={k.name:float(np.max(np.linalg.norm(np.array([p.co[:] for p in k.data])[anchor]-source[anchor],axis=1))) for k in keys}
assert max(key_errors.values())<1e-7
visible=[o for o in scene.objects if o.type=='MESH' and o.visible_get() and not o.hide_render]
driven=[o.data.shape_keys for o in visible if o.data.shape_keys and o.data.shape_keys.animation_data and o.data.shape_keys.animation_data.drivers]
samples=[];first=None;last=None;maxstep=0.;previous=None
for frame in range(1,241):
    scene.frame_set(frame)
    ev=head.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    arr=np.array([v.co[:] for v in mesh.vertices]);ev.to_mesh_clear()
    assert np.isfinite(arr).all()
    if first is None:first=arr.copy()
    if previous is not None:maxstep=max(maxstep,float(np.max(np.linalg.norm(arr-previous,axis=1))))
    previous=arr;last=arr
    samples.append({'shapes':{sk.name:{k.name:float(k.value) for k in sk.key_blocks[1:]} for sk in driven},
                    'eyes':{s:list(rig.pose.bones['eye.'+s].rotation_euler) for s in ('L','R')}})
assert np.max(np.abs(first-last))<1e-7
scene.frame_set(1)
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS');txt.clear()
txt.write('CHIN CORRECTION V2 — Faceit-free prototype\nOriginal chin, jaw outline and neck restored. Neutral mouth intentionally slightly open.\nSelect FACE_RIG__select_Custom_Properties > Object Properties > Custom Properties.\nSpace plays the 240-frame demonstration. Unlink its action for free manual posing.\nblink_L/R, jaw_open, smile, frown, pucker, brow_up, brow_frown: 0..1. look_lr/look_ud: -1..1.\nJaw control interpolates the local relaxed lip pose to the original open-mouth pose; this is not a finished anatomical jaw rig.\nRemaining: lip sealing, eyelid edge refinement, local retopology and production expression corrections.\n')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_manual_face_rig_v2.blend'))
report=json.loads((OUT/'chin-correction-report.json').read_text(encoding='utf-8'))
report.update(chin_anchor_errors_by_shape=key_errors,frames_checked=240,finite_coordinates=True,
              first_last_difference=float(np.max(np.abs(first-last))),maximum_head_vertex_step=maxstep,
              neutral_mouth='Slightly open. Full sealing is not implemented.',
              visual_review='Front and oblique jaw renders inspected; depressed chin removed. Lip and eyelid refinement remains.')
(OUT/'chin-correction-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Driver baking is applied only to the unsaved export copy.
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
scene.frame_set(1)
for o in scene.objects:o.select_set(False)
for o in visible:o.select_set(True)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer_manual_face_rig_v2.glb'),export_format='GLB',use_selection=True,
    export_animations=True,export_animation_mode='SCENE',export_anim_scene_split_object=False,
    export_force_sampling=True,export_frame_range=True,export_skins=True,export_morph=True,
    export_morph_animation=True,export_cameras=False,export_lights=False)
print('CHIN_VALIDATION',json.dumps(report),flush=True)
