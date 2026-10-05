import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(A/'assembled_workbench.blend'));o=bpy.data.objects['FACE_user_head'];m=o.data;result={};finfaces=set()
for sign in [-1,1]:
 remove=set()
 for p in m.polygons:
  c=p.center;r=math.hypot((sign*c.y-.14)/.094,(c.z-.105)/.058)
  if (r<1.55 or p.index in finfaces) and sign*c.y>.043 and c.x>.075:remove.add(p.index)
 edges={}
 for _ in range(12):
  ee={}
  for p in m.polygons:
   for key in p.edge_keys:ee.setdefault(key,[]).append(p.index)
  aa={}
  for key,pp in ee.items():
   if any(i in remove for i in pp) and any(i not in remove for i in pp):
    for v in key:aa[v]=aa.get(v,0)+1
  bad={i for i,c in aa.items() if c!=2}
  if not bad:break
  remove.update(p.index for p in m.polygons if any(v in bad for v in p.vertices))
 for p in m.polygons:
  for key in p.edge_keys:edges.setdefault(key,[]).append(p.index)
 border=[k for k,ids in edges.items() if any(i in remove for i in ids) and any(i not in remove for i in ids)];adj={}
 for a,b in border:adj.setdefault(a,set()).add(b);adj.setdefault(b,set()).add(a)
 seen=set();groups=[]
 for a in adj:
  if a in seen:continue
  stack=[a];seen.add(a);vs=[]
  while stack:
   b=stack.pop();vs.append(b)
   for c in adj[b]-seen:seen.add(c);stack.append(c)
  groups.append({'verts':vs,'branch_vertices':sum(len(adj[i])!=2 for i in vs),'min':[min(m.vertices[i].co[k] for i in vs) for k in range(3)],'max':[max(m.vertices[i].co[k] for i in vs) for k in range(3)]})
 result[str(sign)]={'removed_faces':sorted(remove),'border_groups':groups};print('PATCH',sign,len(remove),[{k:v for k,v in g.items() if k!='verts'} for g in groups])
(A/'eye-patch-probe.json').write_text(json.dumps(result,indent=2))
m.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in m.vertices],[t.vertices for t in m.loop_triangles],all_triangles=True)
rows=[]
for sign in [-1,1]:
 for i in range(80,131,2):
  y=sign*i/1000;vals=[]
  for j in range(120):
   z=-.12+j*.0005;p,*_=tree.ray_cast(Vector((1,y,z)),Vector((-1,0,0)));vals.append((z,p.x if p else -.5))
  a=max(x for z,x in vals if z<-.093);b=max(x for z,x in vals if z>-.071);cut=min(a,b)-.006;valid=[z for z,x in vals if -.1<z<-.068 and x<cut];rows.append([y,cut,min(valid) if valid else None,max(valid) if valid else None])
(A/'mouth-gap-profiles.json').write_text(json.dumps(rows,indent=2));print('MOUTH_PROFILES',rows)
