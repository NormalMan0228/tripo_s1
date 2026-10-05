import bpy,json,numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1];bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/npc_cast_idle_v9/naru/naru_rigged_idle.blend'));m=next(o for o in bpy.context.scene.objects if o.type=='MESH').data;h=1.55
pos={v.index:tuple(round(x,5) for x in v.co) for v in m.vertices}
for sign in [-1,1]:
 remain={p for p in pos.values() if sign*p[1]>.12*h and .39*h<p[2]<.76*h};adj={p:set() for p in remain};groups=[]
 for e in m.edges:
  a,b=[pos[i] for i in e.vertices]
  if a in remain and b in remain:adj[a].add(b);adj[b].add(a)
 while remain:
  stack=[remain.pop()];part=[]
  while stack:
   a=stack.pop();part.append(a)
   for b in adj[a]:
    if b in remain:remain.remove(b);stack.append(b)
  if len(part)>20:groups.append(part)
 for part in sorted(groups,key=len,reverse=True):print('COMP',sign,len(part),np.min(part,0),np.max(part,0),flush=True)
 (R/f'art/characters/npc_cast_idle_v10/reference/naru-components-{sign}.json').write_text(json.dumps(groups))
