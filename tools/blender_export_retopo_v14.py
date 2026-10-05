import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_tripo_retopo_v14';A.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_mesh_reset_v13/original_mesh_with_user_hair_v13.blend'))
bpy.ops.object.select_all(action='DESELECT');o=bpy.data.objects['FACE_original_user_GLb'];o.select_set(True);bpy.context.view_layer.objects.active=o
bpy.ops.export_scene.gltf(filepath=str(A/'face_input.glb'),export_format='GLB',use_selection=True,export_animations=False,export_morph=False)
o.data.calc_loop_triangles();(A/'input-stats.json').write_text(json.dumps({'vertices':len(o.data.vertices),'faces':len(o.data.polygons),'triangles':len(o.data.loop_triangles),'scope':'Main face only; separate eyes, lashes, teeth, tongue, ears, clavicle and hair preserved in assembly'},indent=2))
