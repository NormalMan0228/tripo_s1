"""Read a prepared Blender pier's deck height without rewriting its model."""
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'art/maps/archipelago_objects_v1/20_pier'
bpy.ops.wm.open_mainfile(filepath=str(folder/'pier.blend'))
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
tree=BVHTree.FromPolygons([v.co for v in mesh.data.vertices],[p.vertices[:] for p in mesh.data.polygons])
samples=[]
for y in [-1.3,-.65,0,.65,1.3]:
    for x in [-.4,0,.4]:
        hit,_,_,_=tree.ray_cast(Vector((x,y,5)),Vector((0,0,-1)),10)
        if hit is not None:
            samples.append(float(hit.z))
assert len(samples)>=12
report={'deck_height_m':float(np.median(samples)),'samples':samples,'model_unchanged':True}
(folder/'support_geometry.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PIER_DECK_INSPECTED height_m=',report['deck_height_m'])
