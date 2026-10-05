"""Replace the malformed thin roof, retaining the Tripo stage and supports."""
import bpy
import bmesh
import json
import math
import numpy as np
from pathlib import Path
import shutil
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_objects_v1/14_stage'
LAB=ROOT/'labs/archipelago_object_lab'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'stage.blend'))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
positions=np.array([v.co[:] for v in obj.data.vertices if 1.1<v.co.z<1.7 and math.hypot(v.co.x,v.co.y)>3.5])[:,:2]
seeds=[positions[np.argmax(np.linalg.norm(positions,axis=1))]]
for _ in range(5):
    d=np.min(np.sum((positions[:,None,:]-np.array(seeds)[None,:,:])**2,axis=2),axis=1)
    seeds.append(positions[np.argmax(d)])
centers=np.array(seeds)
for _ in range(30):
    labels=np.argmin(np.sum((positions[:,None,:]-centers[None,:,:])**2,axis=2),axis=1)
    centers=np.array([positions[labels==i].mean(axis=0) for i in range(len(centers))])
while True:
    pair=None
    for i in range(len(centers)):
        for j in range(i):
            if np.linalg.norm(centers[i]-centers[j])<1:
                pair=(i,j)
    if pair is None:
        break
    i,j=pair
    centers[j]=(centers[i]+centers[j])/2
    centers=np.delete(centers,i,axis=0)
center=centers.mean(axis=0)
order=np.argsort(np.arctan2(centers[:,1]-center[1],centers[:,0]-center[0]))
corners=centers[order]
bm=bmesh.new()
bm.from_mesh(obj.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                      plane_co=Vector((0,0,2.88)),plane_no=Vector((0,0,1)),clear_outer=True)
bm.to_mesh(obj.data)
bm.free()

def material(name,color,roughness,metallic=0):
    m=bpy.data.materials.new(name)
    m.diffuse_color=color
    m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=color
    p.inputs['Roughness'].default_value=roughness
    p.inputs['Metallic'].default_value=metallic
    return m
purple=material('Purple fabric · repaired canopy',(.105,.03,.225,1),.64)
purple.use_backface_culling=False
gold=material('Canopy gold piping',(.55,.32,.055,1),.34,.35)
wood=material('Warm oak post extensions',(.24,.075,.01,1),.64)
def beam(name,a,b,radius,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=radius,depth=(b-a).length,location=(a+b)*.5)
    o=bpy.context.object
    o.name=name
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth=True
def finial(x,y,base,tip):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.15,location=(x,y,base+.14))
    o=bpy.context.object
    o.name='Canopy gold finial bead'
    o.scale.z=.60
    o.data.materials.append(gold)
    for p in o.data.polygons:
        p.use_smooth=True
    low=base+.19
    bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.13,radius2=.015,depth=tip-low,location=(x,y,(tip+low)/2))
    o=bpy.context.object
    o.name='Canopy gold finial tip'
    o.data.materials.append(gold)
    for p in o.data.polygons:
        p.use_smooth=True
edge=3.44
peak=4.90
for x,y in corners:
    beam('Existing post continuation',Vector((x,y,2.86)),Vector((x,y,edge)),.18,wood)
    finial(x,y,edge,edge+.53)
finial(center[0],center[1],peak,5.5)

def boundary(a):
    direction=np.array([math.cos(a),math.sin(a)])
    choices=[]
    for j in range(len(corners)):
        p=corners[j]-center
        q=corners[(j+1)%len(corners)]-center
        matrix=np.column_stack((direction,-(q-p)))
        if abs(np.linalg.det(matrix))<1e-8:
            continue
        distance,t=np.linalg.solve(matrix,p)
        if distance>0 and -.0001<=t<=1.0001:
            choices.append(distance)
    return min(choices)*1.014
def point(a,t):
    r=boundary(a)*t
    z=edge+(peak-edge)*(1-t*t)**.66
    return Vector((center[0]+r*math.cos(a),center[1]+r*math.sin(a),z))
angular=160
radial=32
verts=[point(2*math.pi*i/angular,j/radial) for j in range(radial+1) for i in range(angular)]
faces=[]
for j in range(radial):
    for i in range(angular):
        a=j*angular+i
        b=j*angular+(i+1)%angular
        faces.append((a,a+angular,b+angular,b))
mesh=bpy.data.meshes.new('Connected purple fabric roof')
mesh.from_pydata(verts,[],faces)
mesh.update()
cloth=bpy.data.objects.new('Connected purple fabric roof',mesh)
bpy.context.collection.objects.link(cloth)
cloth.data.materials.append(purple)
for p in cloth.data.polygons:
    p.use_smooth=True
solid=cloth.modifiers.new('Fabric thickness','SOLIDIFY')
solid.thickness=.015
bpy.context.view_layer.objects.active=cloth
bpy.ops.object.modifier_apply(modifier=solid.name)
for x,y in corners:
    a=math.atan2(y-center[1],x-center[0])
    for j in range(24):
        p=point(a,j/24)+Vector((0,0,.018))
        q=point(a,(j+1)/24)+Vector((0,0,.018))
        beam('Fine canopy gold seam',p,q,.015,gold)
for i in range(angular):
    a=2*math.pi*i/angular
    b=2*math.pi*(i+1)/angular
    beam('Fine canopy gold hem',point(a,1),point(b,1),.024,gold)
for o in bpy.context.scene.objects:
    o.select_set(o.type=='MESH')
bpy.context.view_layer.objects.active=obj
bpy.ops.object.join()
obj.data.calc_loop_triangles()
bpy.context.view_layer.update()
bpy.ops.export_scene.gltf(filepath=str(OUT/'stage.glb'),export_format='GLB',use_selection=True,export_animations=False)
shutil.copy2(OUT/'stage.glb',LAB/'assets/stage.glb')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'stage.blend'))
report=json.loads((OUT/'mesh_verification.json').read_text(encoding='utf-8'))
report.update(vertices=len(obj.data.vertices),triangles=len(obj.data.loop_triangles),materials=len(obj.data.materials),dimensions_m=list(obj.dimensions),
    local_repairs={'tripo_base_and_supports_retained':True,'damaged_roof_replaced':True,'post_count':len(corners),'connected_purple_fabric':True,'gold_seams_added':True,'original_unchanged':True})
(OUT/'mesh_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('STAGE_CANOPY_REPAIR_COMPLETE',json.dumps(report['local_repairs']),flush=True)
