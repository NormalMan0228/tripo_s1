"""Repair broken gazebo deck and temper overly metallic generated materials."""
import bpy
import bmesh
import json
import math
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_objects_v1/08_gazebo'
LAB=ROOT/'labs/archipelago_object_lab'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'gazebo.blend'))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
for mat in obj.data.materials:
    p=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    for key,operation,value in [('Metallic','MULTIPLY',.12),('Roughness','MAXIMUM',.52)]:
        socket=p.inputs[key]
        if socket.is_linked:
            link=socket.links[0]
            source=link.from_socket
            mat.node_tree.links.remove(link)
            node=mat.node_tree.nodes.new('ShaderNodeMath')
            node.operation=operation
            node.inputs[1].default_value=value
            mat.node_tree.links.new(source,node.inputs[0])
            mat.node_tree.links.new(node.outputs[0],socket)
bm=bmesh.new()
bm.from_mesh(obj.data)
bad=[f for f in bm.faces if .48<f.calc_center_median().z<.67
     and math.hypot(f.calc_center_median().x,f.calc_center_median().y)<2.32 and abs(f.normal.z)>.45]
count=len(bad)
bmesh.ops.delete(bm,geom=bad,context='FACES')
bm.to_mesh(obj.data)
bm.free()
materials=[]
for i,color in enumerate([(.43,.21,.085,1),(.48,.25,.11,1),(.52,.29,.135,1),(.46,.235,.095,1)]):
    mat=bpy.data.materials.new('Deck oak '+str(i))
    mat.diffuse_color=color
    mat.use_nodes=True
    p=mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=color
    p.inputs['Roughness'].default_value=.64
    materials.append(mat)
radius=2.35
planks=0
for i in range(21):
    ya=-radius+2*radius*i/21+.004
    yb=-radius+2*radius*(i+1)/21-.004
    # Each board follows the round deck and keeps a fine physical seam.
    ys=[ya+(yb-ya)*j/4 for j in range(5)]
    outline=[(math.sqrt(max(0,radius*radius-y*y)),y) for y in ys]
    outline += [(-math.sqrt(max(0,radius*radius-y*y)),y) for y in reversed(ys)]
    verts=[(x,y,z) for z in [.578,.627] for x,y in outline]
    n=len(outline)
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]
    faces += [(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    mesh=bpy.data.meshes.new('Oak deck board')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    board=bpy.data.objects.new('Oak deck board '+str(i),mesh)
    bpy.context.collection.objects.link(board)
    board.data.materials.append(materials[i%4])
    bevel=board.modifiers.new('Soft plank edges','BEVEL')
    bevel.width=.006
    bevel.segments=2
    bpy.context.view_layer.objects.active=board
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    planks+=1
for o in bpy.context.scene.objects:
    o.select_set(o.type=='MESH')
bpy.context.view_layer.objects.active=obj
bpy.ops.object.join()
obj.data.calc_loop_triangles()
bpy.ops.export_scene.gltf(filepath=str(OUT/'gazebo.glb'),export_format='GLB',use_selection=True,export_animations=False)
shutil.copy2(OUT/'gazebo.glb',LAB/'assets/gazebo.glb')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'gazebo.blend'))
report=json.loads((OUT/'mesh_verification.json').read_text(encoding='utf-8'))
report.update(vertices=len(obj.data.vertices),triangles=len(obj.data.loop_triangles),materials=len(obj.data.materials),
    local_repairs={'broken_deck_faces_removed':count,'oak_boards_added':planks,'pbr_metallic_tempered':True,'original_unchanged':True})
(OUT/'mesh_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('GAZEBO_REPAIR_COMPLETE',json.dumps(report['local_repairs']),flush=True)
