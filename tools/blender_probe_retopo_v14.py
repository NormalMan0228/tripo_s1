import bpy,json,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_tripo_retopo_v14'
bpy.ops.wm.read_factory_settings(use_empty=True)
files=list(A.glob('model.*'));p=files[0]
if p.suffix=='.zip':
 with zipfile.ZipFile(p) as z:
  base=(A/'native').resolve()
  assert all((base/n).resolve().is_relative_to(base) for n in z.namelist())
  z.extractall(base)
 files=list(base.rglob('*.fbx')) or list(base.rglob('*.glb'));p=files[0]
if p.suffix=='.fbx':bpy.ops.import_scene.fbx(filepath=str(p))
else:bpy.ops.import_scene.gltf(filepath=str(p))
def info(o):
 pts=[o.matrix_world@v.co for v in o.data.vertices];o.data.calc_loop_triangles()
 return {'name':o.name,'vertices':len(pts),'faces':len(o.data.polygons),'quads':sum(len(f.vertices)==4 for f in o.data.polygons),'triangles':len(o.data.loop_triangles),'bounds':[[min(p[i] for p in pts) for i in range(3)],[max(p[i] for p in pts) for i in range(3)]],'uv':len(o.data.uv_layers),'materials':[m.name if m else None for m in o.data.materials]}
stats=[info(o) for o in bpy.context.scene.objects if o.type=='MESH'];(A/'output-probe.json').write_text(json.dumps({'file':str(p),'parts':stats},indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(A/'tripo_raw_retopology.blend'));print(json.dumps(stats))
