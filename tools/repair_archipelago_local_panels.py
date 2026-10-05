"""Close specific missing panes/wall patches using measured source planes."""
import bpy
import json
import math
from mathutils import Vector
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
asset=sys.argv[sys.argv.index('--')+1]
assert asset in ['09_town_hall','10_red_house','16_blue_cottage']
stem=asset.split('_',1)[1]
OUT=ROOT/'art/maps/archipelago_objects_v1'/asset
LAB=ROOT/'labs/archipelago_object_lab'
spec=json.loads((LAB/'reviews'/(asset+'.json')).read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(OUT/(stem+'.blend')))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
az=spec['initial_azimuth']
size=max(spec['height_m']*1.56,spec['width_m']*.95)
center=Vector((0,0,spec['height_m']*.4625))
delta=Vector((math.sin(az)*math.cos(.38),-math.cos(az)*math.cos(.38),math.sin(.38)))*30
camera=center+delta
direction=-delta.normalized()
right=direction.cross(Vector((0,0,1))).normalized()
up=right.cross(direction).normalized()
def material(name,color,roughness):
    m=bpy.data.materials.new(name)
    m.diffuse_color=color
    m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=color
    p.inputs['Roughness'].default_value=roughness
    m.use_backface_culling=False
    return m
glass=material('Closed recessed teal glass',(.018,.13,.16,1),.25)
def panel(name,vertices,mat):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],[tuple(range(len(vertices)))])
    mesh.update()
    o=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
def screen_panel(rect,normal,distance):
    x1,y1,x2,y2=rect
    n=Vector(normal).normalized()
    vertices=[]
    for x,y in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]:
        origin=camera+right*((x/1152-.5)*size*1.44)+up*((.5-y/800)*size)
        t=(distance-n.dot(origin))/n.dot(direction)
        vertices.append(origin+direction*t)
    panel('Recessed window pane',vertices,glass)
if asset=='09_town_hall':
    for rect in [(427,532,498,610),(774,494,837,590)]:
        screen_panel(rect,(.3204,-.9473,0),2.50)
    repair={'closed_front_window_panes':2}
elif asset=='10_red_house':
    for rect in [(372,513,431,626),(448,533,506,633)]:
        screen_panel(rect,(-.79194,-.61060,0),3.42)
    repair={'closed_lower_window_panes':2}
else:
    n=Vector((-.70616,-.70805,0)).normalized()
    tangent=Vector((.70805,-.70616,0)).normalized()
    cream=material('Recessed cream gable plaster',(.72,.62,.43,1),.82)
    outline=[(-2.5,2.70),(2.5,2.70),(2.5,3.85),(0,5.40),(-2.5,3.85)]
    panel('Closed cream front gable',[n*2.53+tangent*t+Vector((0,0,z)) for t,z in outline],cream)
    vertices=[]
    for i in range(64):
        a=2*math.pi*i/64
        x,y=440+14*math.cos(a),404+18*math.sin(a)
        origin=camera+right*((x/1152-.5)*size*1.44)+up*((.5-y/800)*size)
        vertices.append(origin+direction*((2.56-n.dot(origin))/n.dot(direction)))
    panel('Round attic glass',vertices,glass)
    repair={'front_gable_wall_closed':True,'attic_window_glazed':True}
for o in bpy.context.scene.objects:
    o.select_set(o.type=='MESH')
bpy.context.view_layer.objects.active=obj
bpy.ops.object.join()
obj.data.calc_loop_triangles()
bpy.ops.export_scene.gltf(filepath=str(OUT/(stem+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
shutil.copy2(OUT/(stem+'.glb'),LAB/'assets'/(stem+'.glb'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(stem+'.blend')))
report=json.loads((OUT/'mesh_verification.json').read_text(encoding='utf-8'))
report.update(vertices=len(obj.data.vertices),triangles=len(obj.data.loop_triangles),materials=len(obj.data.materials),
              local_repairs={**repair,'original_unchanged':True})
(OUT/'mesh_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('LOCAL_PANEL_REPAIR_COMPLETE',json.dumps(repair),flush=True)
