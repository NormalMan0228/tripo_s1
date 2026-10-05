import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_open_mouth_p2_v1/explorer_b_open_mouth_P2_workbench.blend'))
o=bpy.data.objects['HEAD_P2_EDIT_01'];bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();seen=set();groups=[]
for v in bm.verts:
 if v.index in seen:continue
 stack=[v];seen.add(v.index);g=[]
 while stack:
  a=stack.pop();g.append(a)
  for e in a.link_edges:
   b=e.other_vert(a)
   if b.index not in seen:seen.add(b.index);stack.append(b)
 groups.append(g)
g=max(groups,key=len);fs=set(f for v in g for f in v.link_faces)
tree=BVHTree.FromPolygons([v.co for v in bm.verts],[tuple(v.index for v in f.verts) for f in fs])
samples={}
for y in [0,.02,.04,.06,.075,.09]:
 arr=[]
 for n in range(46):
  z=-.16+n*.003;p,*_=tree.ray_cast(Vector((2,y,z)),Vector((-1,0,0)))
  arr.append([round(z,4),round(p.x,4) if p else None])
 samples[str(y)]=arr
eye={}
for y in [.045,.06,.08,.10,.12,.14,.16,.18,.20,.215]:
 arr=[]
 for n in range(41):
  z=.025+n*.005;p,*_=tree.ray_cast(Vector((2,y,z)),Vector((-1,0,0)))
  arr.append([round(z,4),round(p.x,4) if p else None])
 eye[str(y)]=arr
O=R/'art/characters/explorer_b_open_mouth_p2_v1'
(O/'assembly-probe.json').write_text(json.dumps({'mouth':samples,'eyes':eye}))
print('MOUTH',json.dumps(samples))
with bpy.data.libraries.load(str(R/'art/characters/explorer_b_hybrid_bust_v2/explorer_b_hybrid_bust_v2.blend'),link=False) as (a,b):
 print('V2_OBJECTS',json.dumps(a.objects))
