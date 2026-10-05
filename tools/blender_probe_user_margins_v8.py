import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(A/'assembled_workbench.blend'));o=bpy.data.objects['FACE_user_head'];m=o.data;edges={}
for p in m.polygons:
 for e in p.edge_keys:edges[e]=edges.get(e,0)+1
adj={}
for (a,b),c in edges.items():
 if c==1:adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
seen=set();out=[]
for a in adj:
 if a in seen:continue
 stack=[a];ids=[];seen.add(a)
 while stack:
  i=stack.pop();ids.append(i)
  for j in adj[i]:
   if j not in seen:seen.add(j);stack.append(j)
 ps=[m.vertices[i].co for i in ids];out.append({'verts':ids,'count':len(ids),'min':[min(p[k] for p in ps) for k in range(3)],'max':[max(p[k] for p in ps) for k in range(3)]})
(A/'head-boundaries.json').write_text(json.dumps(out,indent=2));print('MARGINS',json.dumps([{k:v for k,v in d.items() if k!='verts'} for d in out]))
