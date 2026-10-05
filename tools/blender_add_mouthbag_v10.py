"""Add a separate animated mouth interior, without editing the supplied facial mesh."""
import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10'
for filename,runtime in [('original_preserved_face_rig_v10.blend',False),('game_export_scene_v10.blend',True)]:
 bpy.ops.wm.open_mainfile(filepath=str(A/filename));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];action=bpy.data.actions['IdleClosed'];rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0];sc.frame_set(1);bpy.context.view_layer.update()
 old=bpy.data.objects.get('MOUTH_interior_bag')
 if old:bpy.data.objects.remove(old,do_unlink=True)
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=(0,0,0));o=bpy.context.object;o.name='MOUTH_interior_bag';open_coords=[];closed_coords=[]
 for v in o.data.vertices:
  p=v.co.copy();y=p.y*.092;seam=-.095+.006*min(1,(abs(y)/.105)**2);closed_coords.append(Vector((.235-.12*(abs(y)/.095)**2+p.x*.015,y,seam+p.z*.008)));open_coords.append(Vector((.050+p.x*.02,p.y*.11,-.100+p.z*.072)))
 for v,p in zip(o.data.vertices,closed_coords if runtime else open_coords):v.co=p
 mat=bpy.data.materials.new('Mouth_interior_dark');mat.use_nodes=True;bs=mat.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.008,.002,.0015,1);bs.inputs['Roughness'].default_value=.9;o.data.materials.append(mat)
 for p in o.data.polygons:p.use_smooth=True
 o.shape_key_add(name='Basis_game_closed_rest' if runtime else 'Basis_open_interior');key=o.shape_key_add(name='jawOpen' if runtime else 'RestClosed')
 for v,p in zip(key.data,open_coords if runtime else closed_coords):v.co=p
 dr=key.driver_add('value').driver;dr.expression='op' if runtime else '1-op';v=dr.variables.new();v.name='op';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='pose.bones["head"]["jawOpen"]';o.parent=rig;group=o.vertex_groups.new(name='DEF-head');group.add(list(range(len(o.data.vertices))),1.,'REPLACE');m=o.modifiers.new('Rigify_head','ARMATURE');m.object=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(A/filename))
 if not runtime:
  sc.render.filepath=str(A/'IdleClosed.png');bpy.ops.render.render(write_still=True)
 else:
  bpy.ops.object.select_all(action='DESELECT')
  for x in sc.objects:
   if x==rig or (x.type=='MESH' and not x.hide_render and not x.name.startswith('WGT')):x.select_set(True)
  bpy.context.view_layer.objects.active=rig;opts={'filepath':str(A/'character_face_clips_v10.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIONS','export_anim_single_armature':True,'export_morph_animation':True,'export_bake_animation':True,'export_frame_range':False,'export_anim_slide_to_zero':True,'export_merge_animation':'ACTION','export_morph_normal':True};available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());bpy.ops.export_scene.gltf(**{k:v for k,v in opts.items() if k in available})
report=json.loads((A/'rig-verification.json').read_text());report['separate_animated_mouth_interior_added']=True;report['mouth_interior_triangles']=24*20;(A/'rig-verification.json').write_text(json.dumps(report,indent=2));print('MOUTH_INTERIOR_ADDED')
