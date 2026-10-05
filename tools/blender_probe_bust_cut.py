import bpy
from mathutils import Vector
o=bpy.data.objects['Template_Face_Body'];b=o.data.shape_keys.key_blocks[0]
cs=[v.co.copy() for v in b.data]
for k in o.data.shape_keys.key_blocks[1:]:
 if k.value:
  for i,p in enumerate(k.data):cs[i]+=(p.co-b.data[i].co)*k.value
g=o.vertex_groups['body'].index
ids=[v.index for v in o.data.vertices if any(m.group==g and m.weight>.5 for m in v.groups)]
for z in [1.30,1.32,1.34,1.35,1.36,1.37,1.38,1.40,1.42]:
 p=[cs[i] for i in ids if abs(cs[i].z-z)<.008]
 print('CROSS',z,len(p),[(round(min(v[a] for v in p),4),round(max(v[a] for v in p),4)) for a in range(3)] if p else [])
