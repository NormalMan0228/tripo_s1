import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_hair_swap_v11';A.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_game_face_v10/original_preserved_face_rig_v10.blend'))
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
old=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath='C:/Users/dd/Downloads/brown hair 3d model.glb');new=[o for o in bpy.data.objects if o not in old];rows=[]
for o in new:
 if o.type!='MESH':continue
 ps=[o.matrix_world@v.co for v in o.data.vertices];rows.append({'name':o.name,'vertices':len(ps),'low':[min(p[i] for p in ps) for i in range(3)],'high':[max(p[i] for p in ps) for i in range(3)],'materials':[m.name for m in o.data.materials]})
(A/'hair-import.json').write_text(json.dumps(rows,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(A/'hair_import_inspection.blend'));print('HAIR_IMPORT',json.dumps(rows))
