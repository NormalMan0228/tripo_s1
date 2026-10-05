import bpy,json,numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_clean_edges_v5/assembly';A.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_face_balance_v4/assembly/explorer_b_balanced_face_v4.blend'));o=bpy.data.objects['FACE_skin_eyelids_lashes'];basis=o.data.shape_keys.key_blocks[0]
rows=[]
for y in np.linspace(-.15,.15,61):
 coords=[v.co for v in basis.data if abs(v.co.y-y)<.005 and v.co.x>.09 and -.30<v.co.z<-.165]
 if coords:rows.append([float(y),min(v.z for v in coords)])
print('CUSTOM_NORMALS',o.data.has_custom_normals);print('CHIN_EDGE',rows)
(A/'chin-edge-before.json').write_text(json.dumps({'custom_normals':o.data.has_custom_normals,'rows':rows},indent=2),encoding='utf-8')
