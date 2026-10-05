"""Locate source surfaces under review image points for precise local repairs."""
import bpy
import bmesh
import json
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
asset=sys.argv[sys.argv.index('--')+1]
stem=asset.split('_',1)[1]
OUT=ROOT/'art/maps/archipelago_objects_v1'/asset
spec=json.loads((ROOT/'labs/archipelago_object_lab/reviews'/(asset+'.json')).read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(OUT/(stem+'.blend')))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
bm=bmesh.new()
bm.from_mesh(obj.data)
tree=BVHTree.FromBMesh(bm)
az=spec['initial_azimuth']
el=.38
size=max(spec['height_m']*1.56,spec['width_m']*.95)
center=Vector((0,0,spec['height_m']*.4625))
delta=Vector((math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)))*30
camera=center+delta
direction=-delta.normalized()
right=direction.cross(Vector((0,0,1))).normalized()
up=right.cross(direction).normalized()
pixels=json.loads(sys.argv[sys.argv.index('--')+2])
result=[]
for x,y in pixels:
    origin=camera+right*((x/1152-.5)*size*1.44)+up*((.5-y/800)*size)
    co,normal,index,distance=tree.ray_cast(origin,direction)
    result.append({'pixel':[x,y],'position':list(co) if co else None,'normal':list(normal) if normal else None,'face':index})
print('SURFACE_POINTS',json.dumps(result),flush=True)
