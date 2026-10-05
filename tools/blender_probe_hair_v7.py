import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_face_animated_v6/explorer_b_repaired_rigify_v6.blend'));o=bpy.data.objects['HAIR_sculptural_bob_mesh'];m=o.data;p=list(range(len(m.vertices)))
def root(i):
 while p[i]!=i:p[i]=p[p[i]];i=p[i]
 return i
for e in m.edges:
 a,b=e.vertices;a=root(a);b=root(b);p[a]=b
groups={}
for i in range(len(p)):groups.setdefault(root(i),[]).append(i)
data=[{'count':len(ids),'min':[min(m.vertices[i].co[k] for i in ids) for k in range(3)],'max':[max(m.vertices[i].co[k] for i in ids) for k in range(3)]} for ids in groups.values()];print('HAIR_PARTS',json.dumps(data))
