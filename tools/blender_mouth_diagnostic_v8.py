import bpy
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(A/'assembled_workbench.blend'));sc=bpy.context.scene
for o in sc.objects:
 if o.name.startswith(('TEETH','TONGUE')):o.hide_render=True
sc.render.filepath=str(A/'mouth_without_teeth.png');bpy.ops.render.render(write_still=True)
