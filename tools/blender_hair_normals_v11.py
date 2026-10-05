import bpy
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_hair_swap_v11';F=A/'original_face_user_hair_v11.blend';bpy.ops.wm.open_mainfile(filepath=str(F));hair=bpy.data.objects['HAIR_user_brown_v11']
for m in hair.data.materials:
 for n in m.node_tree.nodes:
  if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=.12
sc=bpy.context.scene;sc.render.filepath=str(A/'front_normal_soft.png');bpy.ops.render.render(write_still=True);bpy.ops.wm.save_as_mainfile(filepath=str(F))
