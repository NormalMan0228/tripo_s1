import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
obj=bpy.data.objects['Template_Face_Body']
print('GROUPS',json.dumps([g.name for g in obj.vertex_groups if any(k in g.name.lower() for k in ['head','neck','mouth','lip','eye','clav','shoulder','jaw','chin','nose','body'])]))
print('ACTIVE_KEYS',[(k.name,k.value) for k in obj.data.shape_keys.key_blocks if k.value])
for name in ['Template_Face_Body.high-poly','Template_Face_Body.teeth_base','Template_Face_Body.eyebrow001','Template_Face_Body.eyelashes01']:
 ob=bpy.data.objects[name];pts=[ob.matrix_world@v.co for v in ob.data.vertices]
 print('BOUNDS',name,[(min(p[a] for p in pts),max(p[a] for p in pts)) for a in range(3)])
for g in obj.vertex_groups:
 if any(k in g.name.lower() for k in ['joint-neck','joint-head','joint-l-eye','joint-r-eye','joint-jaw','joint-spine']):
  coords=[v.co for v in obj.data.vertices if any(vg.group==g.index and vg.weight>.1 for vg in v.groups)]
  if coords:print('LANDMARK',g.name,tuple(sum(coords,Vector())/len(coords)))
