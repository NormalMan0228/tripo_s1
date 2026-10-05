"""Remove generated rear strip and glaze/frame the missing rear elevation."""
import bpy
import bmesh
import json
import math
from mathutils import Vector
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_objects_v1/07_greenhouse'
LAB=ROOT/'labs/archipelago_object_lab'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'greenhouse.blend'))
building=next(o for o in bpy.context.scene.objects if o.type=='MESH')
angle=math.radians(-37.95)
c,s=math.cos(angle),math.sin(angle)
def local(co):
    return Vector((c*co.x+s*co.y,-s*co.x+c*co.y,co.z))
def world(x,y,z):
    return Vector((c*x-s*y,s*x+c*y,z))
bm=bmesh.new()
bm.from_mesh(building.data)
bad=[]
for f in bm.faces:
    points=[local(v.co) for v in f.verts]
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    if lo[1]>2.57 and hi[1]<2.64 and lo[2]>3.85 and hi[2]<4.78 and hi[0]-lo[0]>6:
        bad.append(f)
assert len(bad)>0,'rear_artifact_not_found'
count=len(bad)
bmesh.ops.delete(bm,geom=bad,context='FACES')
bm.to_mesh(building.data)
bm.free()

def material(name,color,roughness):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=color
    mat.use_nodes=True
    p=mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=color
    p.inputs['Roughness'].default_value=roughness
    return mat
glass=material('Rear glazing · pale aqua',(.22,.57,.60,.38),.16)
glass.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value=.38
glass.surface_render_method='DITHERED'
frame=material('Rear mullions · sage green',(.19,.28,.10,1),.42)
verts=[]
faces=[]
radius=2.31
for i in range(49):
    x=-radius+radius*2*i/48
    top=4.02+2.12*math.sqrt(max(0,1-(x/radius)**2))
    verts.extend([world(x,2.43,.76),world(x,2.43,top)])
    if i:
        k=i*2
        faces.append((k-2,k,k+1,k-1))
mesh=bpy.data.meshes.new('Rear arch glazing')
mesh.from_pydata(verts,[],faces)
mesh.update()
obj=bpy.data.objects.new('Rear arch glazing',mesh)
bpy.context.collection.objects.link(obj)
obj.data.materials.append(glass)
def beam(name,a,b,thickness=.055):
    midpoint=(a+b)*.5
    length=(b-a).length
    bpy.ops.mesh.primitive_cube_add(size=1,location=midpoint)
    o=bpy.context.object
    o.name=name
    o.scale=(thickness,thickness,length)
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(frame)
    bevel=o.modifiers.new('Soft frame edges','BEVEL')
    bevel.width=.012
    bevel.segments=2
    bpy.context.view_layer.objects.active=o
    bpy.ops.object.modifier_apply(modifier=bevel.name)
for x in [-1.54,-.77,0,.77,1.54]:
    top=4.02+2.12*math.sqrt(max(0,1-(x/radius)**2))
    beam('Rear vertical mullion',world(x,2.47,.76),world(x,2.47,top))
for z in [1.6,2.55,3.5,4.02]:
    beam('Rear horizontal rail',world(-radius,2.47,z),world(radius,2.47,z))
for i in range(32):
    a=math.pi*i/32
    b=math.pi*(i+1)/32
    beam('Rear curved arch rail',world(radius*math.cos(a),2.47,4.02+2.12*math.sin(a)),
         world(radius*math.cos(b),2.47,4.02+2.12*math.sin(b)),.08)
for o in bpy.context.scene.objects:
    o.select_set(o.type=='MESH')
bpy.context.view_layer.objects.active=building
bpy.ops.object.join()
building.data.calc_loop_triangles()
bpy.ops.export_scene.gltf(filepath=str(OUT/'greenhouse.glb'),export_format='GLB',use_selection=True,export_animations=False)
shutil.copy2(OUT/'greenhouse.glb',LAB/'assets/greenhouse.glb')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'greenhouse.blend'))
report=json.loads((OUT/'mesh_verification.json').read_text(encoding='utf-8'))
report.update(vertices=len(building.data.vertices),triangles=len(building.data.loop_triangles),materials=len(building.data.materials),
              local_repairs={'removed_rear_artifact_faces':count,'rear_glazing_and_mullions_added':True,'original_unchanged':True})
(OUT/'mesh_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('GREENHOUSE_REPAIR_COMPLETE',json.dumps(report['local_repairs']),flush=True)
