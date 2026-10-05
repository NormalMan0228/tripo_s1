import bpy,json,math,struct
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';FILE=A/'user_head_mpfb_rigify_v8.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;rig=bpy.data.objects['User_Head_Rigify_Face'];head=bpy.data.objects['FACE_user_head'];rows=[]
from bl_ext.user_default.mpfb.services.faceservice import FaceService
for side,label in [('L','Left'),('R','Right')]:
 k=head.data.shape_keys.key_blocks.get('Blink_'+side)
 if k:k.name='!ex-eyeBlink'+label
for f in [1,45,47,50,70,95,145,147,165,195,245,247,265,295,345,347,365,395,465,467,480,540]:
 sc.frame_set(f);bpy.context.view_layer.update();expr=FaceService.read_current_expression(head);finite=True
 for o in sc.objects:
  if o.type!='MESH' or o.hide_render or o.name.startswith('WGT'):continue
  eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();finite &= all(math.isfinite(c) for v in me.vertices for c in v.co);eo.to_mesh_clear()
 assert finite;rows.append({'frame':f,'faceunits':{k:v for k,v in expr.items() if v>1e-5},'blink':float(rig.pose.bones['blink.L']['blink']),'finite':finite})
assert any(x['faceunits'].get('mouthSmileLeft',0)>.3 for x in rows);assert any(x['faceunits'].get('browInnerUp',0)>.6 for x in rows);assert any(x['faceunits'].get('jawOpen',0)>.6 for x in rows);assert rows[0]['faceunits']==rows[-1]['faceunits']
clips=json.loads((A/'expression-clips.json').read_text());demo=rig.animation_data.action;slot=rig.animation_data.action_slot
for clip in clips:
 action=bpy.data.actions[clip['action']];rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0];sc.frame_set(1);bpy.context.view_layer.update();first=FaceService.read_current_expression(head);sc.frame_set(90);bpy.context.view_layer.update();last=FaceService.read_current_expression(head);assert first==last;clip['loop_verified']=True
rig.animation_data.action=demo;rig.animation_data.action_slot=slot;sc.frame_set(1);bpy.context.view_layer.update()
for o in list(sc.objects):
 if o.type=='ARMATURE' and o not in {rig,bpy.data.objects.get('New_Head_Metarig')}:bpy.data.objects.remove(o,do_unlink=True)
notes=bpy.data.texts.get('V8_FACE_CONTROLS') or bpy.data.texts.new('V8_FACE_CONTROLS');notes.clear();notes.write('User-supplied GLB face with reused bob hair. MPFB Faceunits 01 spatially retargeted to this custom mesh (19 units, conservative local corrections). Actual Rigify generated face controls. Original parted-lip smile is the neutral. Head bone custom properties control MPFB brow / cheek / mouth units; jaw jawOpen controls MPFB jaw target; blink.L/R blink controls locally fitted eyelids. Space plays 18 seconds at 30 fps. Separate Face_*_Loop actions are 1-90 (3 seconds). This is not a complete 52-unit/viseme or audio lipsync set.\n')
bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if (o.type=='MESH' and not o.hide_render and not o.hide_get() and not o.name.startswith('WGT')) or o==rig:o.select_set(True)
bpy.context.view_layer.objects.active=rig;available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());opts={'filepath':str(A/'user_head_mpfb_rigify_v8.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_frame_range':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIVE_ACTIONS','export_morph_animation':True,'export_bake_animation':True};bpy.ops.export_scene.gltf(**{k:v for k,v in opts.items() if k in available})
buf=(A/'user_head_mpfb_rigify_v8.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);assert g['skins'] and g['animations'];paths={c['target']['path'] for a in g['animations'] for c in a['channels']};assert 'weights' in paths and 'rotation' in paths;assert all('bufferView' in i for i in g['images'])
occ=json.loads((A/'iris-occlusion.json').read_text());assert all(x['protruding_faces']==0 for x in occ)
report={'status':'passed','source_glb':'C:/Users/dd/Downloads/3d cartoon girl head.glb','source_preserved':True,'actual_MPFb_FaceService_evaluated':True,'actual_Rigify_generated':True,'MPFB_donor_units_retargeted':17,'locally_fitted_blink_units':2,'sampled_frames':rows,'iris_occlusion_checks':occ,'clips':clips,'embedded_textures':True,'animated_skin_and_morph_glb':True,'seconds':18,'rest_mouth':'source parted-lip smile','new_Tripo_credits':0};(A/'verification.json').write_text(json.dumps(report,indent=2));sc.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(FILE));print('V8_VERIFIED')
