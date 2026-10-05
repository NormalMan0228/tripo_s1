import bpy,json,numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly/face_local_cleanup.blend'));o=bpy.data.objects['FACE_skin_eyelids_lashes'];groups={}
for sign in [-1,1]:
 rows=[]
 for y in np.linspace(.065,.245,37):
  faces=[p for p in o.data.polygons if p.material_index==1 and abs(sign*p.center.y-y)<.004]
  if faces:
   coords=[o.data.vertices[i].co for p in faces for i in p.vertices];rows.append([round(float(y),3),float(min(c.z for c in coords)),float(max(c.z for c in coords)),float(min(c.x for c in coords)),float(max(c.x for c in coords))])
 groups[str(sign)]=rows
(A/'lash-contours.json').write_text(json.dumps(groups,indent=2),encoding='utf-8');print('CONTOURS',json.dumps(groups))
