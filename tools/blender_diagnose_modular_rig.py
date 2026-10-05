import bpy,json,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_modular_v1/04_blender_assembly'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_b_assembled_rigged.blend'))
scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
diagnostics={}
diagnostics['collections']={c.name:{'hide_render':c.hide_render,'hide_viewport':c.hide_viewport,'objects':len(c.objects)} for c in bpy.data.collections}
for o in scene.objects:
 if o.type!='MESH':continue
 e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
 delta=max((a.co-b.co).length for a,b in zip(o.data.vertices,m.vertices))
 diagnostics[o.name]={'base_evaluated_max_delta':delta,'modifiers':[(x.name,x.type) for x in o.modifiers],
 'has_custom_normals':o.data.has_custom_normals,'materials':[{ 'name':s.material.name,'links':[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in s.material.node_tree.links]} for s in o.material_slots if s.material]}
 e.to_mesh_clear()
 for mod in o.modifiers:mod.show_render=False
 if o.name.startswith('WGT'):o.hide_render=True
 if o.data.has_custom_normals:
  bpy.context.view_layer.objects.active=o;o.select_set(True)
  bpy.ops.mesh.customdata_custom_splitnormals_clear()
  o.select_set(False)
(OUT/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
scene.cycles.samples=12
scene.render.filepath=str(OUT/'diagnose-no-armature.png')
bpy.ops.render.render(write_still=True)
for target in ['Body','Pants','Jacket','Boot.R']:
 for o in scene.objects:
  if o.type=='MESH':o.hide_render=o.name!=target
 scene.render.filepath=str(OUT/('diagnose-'+target+'.png'))
 bpy.ops.render.render(write_still=True)
