import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_hair_swap_v11';bpy.ops.wm.open_mainfile(filepath=str(A/'original_face_user_hair_v11.blend'));o=bpy.data.objects['HAIR_user_brown_v11'];rows=[]
for m in o.data.materials:
 rows.append({'name':m.name,'nodes':[{'name':n.name,'type':n.type,'uv':getattr(n,'uv_map',None),'image':n.image.name if n.type=='TEX_IMAGE' and n.image else None} for n in m.node_tree.nodes],'links':[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in m.node_tree.links]})
(A/'material-probe.json').write_text(json.dumps({'uv_layers':[x.name for x in o.data.uv_layers],'mats':rows},indent=2))
for i,im in enumerate(bpy.data.images):
 if im.name.startswith('Image_') or 'tripo' in im.name.lower():
  if im.size[0]>0:im.filepath_raw=str(A/('tex_'+str(i)+'.png'));im.file_format='PNG';im.save()
print('MATERIAL_PROBE_COMPLETE')
