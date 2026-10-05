import bpy, json, sys
from pathlib import Path
from mathutils import Vector
source = Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(source))
report = {'armatures': [], 'meshes': []}
for o in bpy.context.scene.objects:
    if o.type == 'ARMATURE':
        report['armatures'].append({'name':o.name,'matrix': [list(r) for r in o.matrix_world],
            'bones':[{'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None} for b in o.data.bones]})
    elif o.type == 'MESH':
        corners = [o.matrix_world@Vector(v) for v in o.bound_box]
        report['meshes'].append({'name':o.name,'bounds':[[min(p[i] for p in corners) for i in range(3)],[max(p[i] for p in corners) for i in range(3)]],
            'vertices':len(o.data.vertices),'faces':len(o.data.polygons),'materials':[m.name for m in o.data.materials]})
source.with_name('rig-inspection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
