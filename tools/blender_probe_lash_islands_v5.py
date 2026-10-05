import bpy,json,numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_clean_edges_v5/assembly'
bpy.ops.wm.open_mainfile(filepath=str(A/'baseline.blend'));o=bpy.data.objects['FACE_skin_eyelids_lashes'];m=o.data;uv=m.uv_layers.active.data
img=next(n.image for n in m.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'Color' in n.image.name);w,h=img.size;pix=np.array(img.pixels[:],dtype=np.float32).reshape(h,w,4)
edges={};adj=[set() for p in m.polygons];seeds=set()
for p in m.polygons:
 cols=[pix[min(h-1,max(0,int(uv[i].uv.y*h))),min(w-1,max(0,int(uv[i].uv.x*w))),:3] for i in p.loop_indices];rgb=np.mean(cols,axis=0);c=p.center
 if c.x>.11 and .06<abs(c.y)<.275 and .105<c.z<.207 and max(rgb)<.2 and np.mean(rgb)<.11:seeds.add(p.index)
 lis=list(p.loop_indices)
 for j,li in enumerate(lis):
  lj=lis[(j+1)%len(lis)];a=m.loops[li].vertex_index;b=m.loops[lj].vertex_index;vals={a:tuple(round(float(q),5) for q in uv[li].uv),b:tuple(round(float(q),5) for q in uv[lj].uv)};key=tuple(sorted(vals.items()));edges.setdefault(key,[]).append(p.index)
for ids in edges.values():
 for a in ids:adj[a].update(ids)
seen=set();groups=[]
for p in m.polygons:
 if p.index in seen:continue
 stack=[p.index];seen.add(p.index);g=[]
 while stack:
  a=stack.pop();g.append(a)
  for b in adj[a]-seen:seen.add(b);stack.append(b)
 groups.append(g)
result=[]
for g in groups:
 n=len(seeds.intersection(g))
 vs=[m.vertices[i].co for j in g for i in m.polygons[j].vertices];lo=[min(v[k] for v in vs) for k in range(3)];hi=[max(v[k] for v in vs) for k in range(3)]
 if n or (lo[0]>.14 and lo[2]>.078 and hi[2]<.190 and min(abs(lo[1]),abs(hi[1]))>.060 and max(abs(lo[1]),abs(hi[1]))<.26):
  result.append({'faces':len(g),'seeds':n,'min':lo,'max':hi,'indices':g})
(A/'lash-all-candidate-islands.json').write_text(json.dumps(result,indent=2));print('LASH_ISLANDS',json.dumps([{k:v for k,v in a.items() if k!='indices' and (a['seeds']==0)} for a in result if a['seeds']==0]))
