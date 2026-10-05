"""Read-only Blender measurements to fit independently generated components."""
import bpy, bmesh, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_modular_v1/04_blender_assembly'
OUT.mkdir(parents=True,exist_ok=True)
report={}
for name in ['body','head','hand','hair','jacket','shirt','pants','boots','belt']:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(ROOT/f'art/characters/explorer_b_modular_v1/03_generated/{name}/model.glb'))
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
 points=[obj.matrix_world@v.co for v in obj.data.vertices]
 lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
 v={'bounds':[lo,hi],'size':[hi[i]-lo[i] for i in range(3)],'slices':{}}
 for z in [.49,.44,.40,.35,.30,.25,.20,.15,.10,.05,0,-.05,-.10,-.15,-.20,-.25,-.30,-.35,-.40,-.45,-.49]:
  pts=[p for p in points if abs(p.z-z)<.009]
  if pts:v['slices'][str(z)]={'min':[min(p[i] for p in pts) for i in range(3)],'max':[max(p[i] for p in pts) for i in range(3)]}
 if name in ['body','head','hand','jacket']:
  bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.transform(bm,matrix=obj.matrix_world,verts=bm.verts)
  bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-5)
  boundary=set(v for e in bm.edges if e.is_boundary for v in e.verts);rings=[]
  while boundary:
   first=boundary.pop();todo=[first];members=[first]
   while todo:
    cur=todo.pop()
    for e in cur.link_edges:
     if not e.is_boundary:continue
     other=e.other_vert(cur)
     if other in boundary:boundary.remove(other);todo.append(other);members.append(other)
   rings.append({'vertices':len(members),'center':list(sum((v.co for v in members),Vector())/len(members)),
                 'bounds':[[min(v.co[i] for v in members) for i in range(3)],[max(v.co[i] for v in members) for i in range(3)]]})
  v['boundary_rings']=sorted(rings,key=lambda r:-r['vertices'])
  bm.verts.ensure_lookup_table();remaining=set(bm.verts);components=[]
  while remaining:
   first=remaining.pop();todo=[first];members=[first]
   while todo:
    cur=todo.pop()
    for e in cur.link_edges:
     other=e.other_vert(cur)
     if other in remaining:remaining.remove(other);todo.append(other);members.append(other)
   components.append({'vertices':len(members),'bounds':[[min(p.co[i] for p in members) for i in range(3)],[max(p.co[i] for p in members) for i in range(3)]]})
  v['components']=sorted(components,key=lambda c:-c['vertices'])[:20];bm.free()
 report[name]=v
(OUT/'source-measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SOURCE_MEASUREMENTS_READY')
