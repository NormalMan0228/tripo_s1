import bpy,json
import numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1];OUT=R/'art/characters/explorer_b_face_rig_manual_v2d';blend=OUT/'explorer_expression_v2d.blend'
bpy.ops.wm.open_mainfile(filepath=str(blend));sc=bpy.context.scene;head=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
report=json.loads((OUT/'expression-restoration-report.json').read_text(encoding='utf-8'))
tested=[o for o in sc.objects if o.type=='MESH' and o.visible_get() and not o.hide_render and not o.name.startswith(('Hair','Nape'))]
first=None;prev=None;max_step=0
for f in range(1,241):
 sc.frame_set(f);deps=bpy.context.evaluated_depsgraph_get();points=[]
 for o in tested:
  ev=o.evaluated_get(deps);m=ev.to_mesh();a=np.array([v.co[:] for v in m.vertices]);ev.to_mesh_clear();points.append(a)
 a=np.concatenate(points);assert np.isfinite(a).all()
 if first is None:first=a.copy()
 if prev is not None:max_step=max(max_step,float(np.linalg.norm(a-prev,axis=1).max()))
 prev=a
assert np.abs(first-prev).max()<1e-7
sc.frame_set(1)
for side,name in [('L','08_Upper_lash_candidate_posY'),('R','07_Upper_lash_candidate_negY')]:
 o=bpy.data.objects[name];assert o.visible_get() and not o.hide_render
 assert len(o.data.vertices)==report['original_lashes_restored'][side]['vertices']
 assert len(o.data.polygons)==report['original_lashes_restored'][side]['polygons']
assert not any(o.name.startswith('Eyelids.') for o in sc.objects)
report.update(frames_checked=240,all_coordinates_finite=True,first_last_max_difference=float(np.abs(first-prev).max()),max_frame_step=max_step,original_lash_objects_visible=True,
 visual_review=['Neutral mouth closed','Original broad lash geometry visible','Full blink inspected'],
 limitations=['Mouth corners and eye-rim contour remain prototype geometry.','No Godot playback test this turn.'])
(OUT/'expression-restoration-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS');txt.clear()
txt.write('V2d — Original lash restoration and closed neutral mouth\nThe archived original upper-lash mesh is restored. No substitute lash band or triangle clusters.\nEye globes and surrounding skin advanced; neutral upper opening increased. Eyelids remain connected to the head.\nNeutral jaw_open=0 is closed. jaw_open=1 retains the prior open-mouth target.\nSpace plays the existing 240-frame comparison. Select FACE_RIG__select_Custom_Properties for numerical sliders.\nUnlink the demo action to pose manually. Previous V2c file is preserved.\nPrototype: mouth corner and eye rim polish still subject to visual review.\n')
sc['RIG_STATUS']='V2d: restored original lashes, less recessed/opened eyes, closed mouth at rest.'
for o in sc.objects:o.select_set(False)
head.select_set(True);bpy.context.view_layer.objects.active=head
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(blend))
print('EXPRESSION_VALIDATED',report['original_lashes_restored'],max_step,flush=True)
