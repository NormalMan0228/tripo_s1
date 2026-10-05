import bpy,json,math,struct
from pathlib import Path
from bl_ext.user_default.mpfb.services.faceservice import FaceService
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_original_identity_v9';F=A/'original_face_mpfb_rigify_v9.blend'
bpy.ops.wm.open_mainfile(filepath=str(F));sc=bpy.context.scene;head=bpy.data.objects['FACE_original_user_GLb'];rig=bpy.data.objects['Original_Identity_Rigify'];rows=[]
for f in [1,60,90,120,180,210,270,300,360,400,450]:
 sc.frame_set(f);bpy.context.view_layer.update();expr=FaceService.read_current_expression(head)
 for o in sc.objects:
  if o.type!='MESH' or o.hide_render:continue
  eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();assert all(math.isfinite(c) for v in me.vertices for c in v.co);eo.to_mesh_clear()
 rows.append({'frame':f,'units':{k:round(v,5) for k,v in expr.items() if v>1e-6}})
assert rows[0]['units']==rows[-1]['units']=={}
assert any(x['units'].get('mouthSmileLeft',0)>.35 for x in rows)
assert any(x['units'].get('jawOpen',0)>.30 for x in rows)
sc.frame_set(1);bpy.context.view_layer.update();hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];hair.hide_render=True;sc.render.filepath=str(A/'original_without_hair.png');bpy.ops.render.render(write_still=True);hair.hide_render=False
note=bpy.data.texts.new('ORIGINAL_FACE_RESTORATION');note.write('Neutral face, eyes, lids, brows, lashes, UV and materials preserved from the supplied GLB. Only hair fitting changes mesh geometry. MPFB 19 donor units spatially retargeted as separate shape keys; actual Rigify head controls drive them. Space plays 15 seconds. Full blink fitting and phoneme lipsync are not complete. The original parted-lip smile remains the default.\n')
bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if o==rig or (o.type=='MESH' and not o.hide_render and not o.name.startswith('WGT')):o.select_set(True)
bpy.context.view_layer.objects.active=rig
opts={'filepath':str(A/'original_face_mpfb_rigify_v9.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_frame_range':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIVE_ACTIONS','export_morph_animation':True,'export_bake_animation':True}
available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());bpy.ops.export_scene.gltf(**{k:v for k,v in opts.items() if k in available})
buf=(A/'original_face_mpfb_rigify_v9.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);assert g.get('skins') and g.get('animations');assert any(c['target']['path']=='weights' for a in g['animations'] for c in a['channels']);assert all('bufferView' in i for i in g['images'])
report=json.loads((A/'verification.json').read_text());report.update(sampled_frames=rows,animated_GLb_verified=True,embedded_textures=True);(A/'verification.json').write_text(json.dumps(report,indent=2))
sc.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(F));print('V9_EXPORT_VERIFIED')
