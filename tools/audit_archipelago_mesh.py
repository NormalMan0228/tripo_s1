"""Inspect geometry components for targeted repair of generated artifacts."""
import bpy
import bmesh
import json
import sys
import math
import numpy as np
from pathlib import Path
from collections import defaultdict
args=sys.argv[sys.argv.index('--')+1:]
asset=args[0]
base=Path(__file__).resolve().parents[1]/'art/maps/archipelago_objects_v1'/asset
bpy.ops.wm.open_mainfile(filepath=str(base/(asset.split('_',1)[1]+'.blend')))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
mesh=obj.data
bm=bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0005)
bm.to_mesh(mesh)
bm.free()
parent=list(range(len(mesh.vertices)))
def root(i):
    while parent[i]!=i:
        parent[i]=parent[parent[i]]
        i=parent[i]
    return i
for edge in mesh.edges:
    a,b=edge.vertices
    parent[root(a)]=root(b)
groups=defaultdict(list)
for v in mesh.vertices:
    groups[root(v.index)].append(v)
report=[]
for vertices in sorted(groups.values(),key=len,reverse=True)[:24]:
    lo=[min(v.co[i] for v in vertices) for i in range(3)]
    hi=[max(v.co[i] for v in vertices) for i in range(3)]
    report.append({'count':len(vertices),'lo':lo,'hi':hi})
print('MESH_COMPONENTS',json.dumps({'asset':asset,'total_components':len(groups),'components':report}),flush=True)
if asset=='08_gazebo':
    mats=[]
    for mat in obj.data.materials:
        p=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        mats.append({key:{'value':p.inputs[key].default_value,'linked':p.inputs[key].is_linked} for key in ['Metallic','Roughness']})
    levels={}
    for p in mesh.polygons:
        if abs(p.normal.z)>.85 and p.center.z<2:
            z=round(p.center.z,2)
            levels[z]=levels.get(z,0)+p.area
    print('GAZEBO_AUDIT',json.dumps({'dims':list(obj.dimensions),'materials':mats,'floor_levels':sorted(levels.items(),key=lambda v:v[1],reverse=True)[:12]}),flush=True)
if asset=='07_greenhouse':
    angle=math.radians(-37.95)
    c,s=math.cos(angle),math.sin(angle)
    def local(v):
        return [c*v.co.x+s*v.co.y,-s*v.co.x+c*v.co.y,v.co.z]
    parts=[]
    for vertices in groups.values():
        points=[local(v) for v in vertices]
        lo=[min(p[i] for p in points) for i in range(3)]
        hi=[max(p[i] for p in points) for i in range(3)]
        dims=[hi[i]-lo[i] for i in range(3)]
        if min(dims)<.008 and max(dims)>1:
            parts.append({'count':len(vertices),'lo':lo,'hi':hi,'dims':dims})
    print('PLANAR_PARTS',json.dumps(parts),flush=True)
    polys=[]
    for poly in sorted(mesh.polygons,key=lambda p:p.area,reverse=True)[:30]:
        points=[local(mesh.vertices[i]) for i in poly.vertices]
        polys.append({'index':poly.index,'area':poly.area,'lo':[min(p[i] for p in points) for i in range(3)],'hi':[max(p[i] for p in points) for i in range(3)]})
    print('LARGEST_FACES',json.dumps(polys),flush=True)
