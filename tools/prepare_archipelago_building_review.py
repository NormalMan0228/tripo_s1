"""Normalize one Tripo building for review, retaining its source and PBR maps."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import struct
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/maps/archipelago_objects_v1'
LAB = ROOT / 'labs/archipelago_object_lab'
parser = argparse.ArgumentParser()
parser.add_argument('--asset', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
queue = json.loads((BASE/'queue.json').read_text(encoding='utf-8'))
item = next(item for item in queue['items'] if item['id']==args.asset)
OUT = BASE / item['id']
stem = item['id'].split('_',1)[1]
height = float(item['target_height_m'])
assert height > 0
original_path = OUT/'tripo-original.glb'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(original_path))
meshes = [o for o in bpy.context.scene.objects if o.type=='MESH']
assert meshes
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
    transform = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = transform
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
building = bpy.context.object
building.name = item['id']+'_Tripo'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
building.rotation_mode = 'XYZ'
building.rotation_euler.z = -math.pi/2
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
if item['category'] == 'bridge' or item.get('long_axis_godot'):
    import numpy as np
    xy = np.array([v.co[:2] for v in building.data.vertices])
    _, vectors = np.linalg.eigh(np.cov(xy.T))
    axis = vectors[:, -1]
    building.rotation_euler.z = (0 if item.get('long_axis_godot')=='+X' else math.pi/2)-math.atan2(float(axis[1]),float(axis[0]))
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
points = [building.matrix_world@Vector(v) for v in building.bound_box]
lo = Vector([min(p[i] for p in points) for i in range(3)])
hi = Vector([max(p[i] for p in points) for i in range(3)])
factor = height/(hi.z-lo.z)
axis_factor = Vector((factor, factor, factor))
if item.get('target_dimensions_m'):
    dims = item['target_dimensions_m']
    axis_factor = Vector((dims[0]/(hi.x-lo.x), dims[1]/(hi.y-lo.y), dims[2]/(hi.z-lo.z)))
origin = Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
for vertex in building.data.vertices:
    centered = vertex.co-origin
    vertex.co = Vector((centered.x*axis_factor.x, centered.y*axis_factor.y, centered.z*axis_factor.z))
building.location = Vector()
building.data.update()
bpy.context.view_layer.update()
local_repairs='none'
if item['id']=='20_pier':
    sys.path.insert(0,str(ROOT/'tools'))
    from repair_archipelago_pier_geometry import repair_pier
    building=repair_pier(building,height)
    local_repairs='Rebuilt obstructed pier deck and side rails with open approaches; retained Tripo sculpted piling and projected original Tripo wood UV textures onto the new planks.'
if item['id']=='28_beach_umbrella':
    # Preserve Tripo's cloth sculpt and UVs, but supply the missing structural pole.
    import bmesh
    bm=bmesh.new();bm.from_mesh(building.data)
    for sector in range(4):
        angle=sector*math.pi/4
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            dist=.00001,plane_co=(0,0,0),plane_no=(math.cos(angle),math.sin(angle),0),
            clear_inner=False,clear_outer=False)
    bm.normal_update();bm.to_mesh(building.data);bm.free();building.data.update()
    original_materials=list(building.data.materials)
    stripes={}
    for original_index, original_material in enumerate(original_materials):
        if not original_material:
            continue
        for stripe,color in [('blue',(.12,.42,.88,1)),('cream',(.98,.97,.92,1))]:
            material=original_material.copy();material.name='Beach_Cloth_'+stripe+'_'+str(original_index)
            bs=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            if bs.inputs['Base Color'].links:
                socket=bs.inputs['Base Color'].links[0].from_socket
                multiply=material.node_tree.nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY'
                multiply.inputs[0].default_value=1.0;multiply.inputs[2].default_value=color
                material.node_tree.links.new(socket,multiply.inputs[1]);material.node_tree.links.new(multiply.outputs[0],bs.inputs['Base Color'])
            else:
                bs.inputs['Base Color'].default_value=color
            stripes[original_index,stripe]=len(building.data.materials)
            building.data.materials.append(material)
    for polygon in building.data.polygons:
        center=polygon.center
        if center.z>height*.55 and math.hypot(center.x,center.y)>.12:
            sector=int((math.atan2(center.y,center.x)+math.pi)/(math.pi/4))%8
            polygon.material_index=stripes.get((polygon.material_index,'blue' if sector%2==0 else 'cream'),polygon.material_index)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.043,depth=height*.93,location=(0,0,height*.465+.018))
    pole=bpy.context.object
    wood=bpy.data.materials.new('Beach_Pole_Warm_Wood');wood.use_nodes=True
    wood.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.44,.23,.085,1)
    pole.data.materials.append(wood)
    bevel=pole.modifiers.new('Rounded_pole_edges','BEVEL');bevel.width=.006;bevel.segments=3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    for polygon in pole.data.polygons:
        polygon.use_smooth=True
    bpy.ops.object.select_all(action='DESELECT')
    building.select_set(True);pole.select_set(True)
    bpy.context.view_layer.objects.active=building
    bpy.ops.object.join()
    building.data.update()
    bpy.context.view_layer.update()
    local_repairs='Added missing solid timber pole; bisected cloth at radial wedge boundaries and assigned blue/cream sectors using original Tripo texture and sculpt.'
building['provenance'] = 'Tripo '+item.get('generation_method','image')+'-to-model P2-20260801'
building['reference_location'] = item['reference_location']
building['review_status'] = 'awaiting user approval'
building['height_m'] = height
building.data.calc_loop_triangles()
textures = []
for image in bpy.data.images:
    if image.type=='IMAGE' and image.size[0]:
        textures.append({'name':image.name,'size':list(image.size)})
        if image.packed_file is None:
            image.pack()
report = {'asset':item['id'],'height_m':height,'dimensions_m':list(building.dimensions),
          'vertices':len(building.data.vertices),'triangles':len(building.data.loop_triangles),
          'materials':len(building.data.materials),'textures':textures,
          'uv_available':bool(building.data.uv_layers),'original_preserved':True,
          'geometry_regenerated_locally':local_repairs!='none','front_axis_godot':'+Z',
          'local_repairs':local_repairs,'source':'tripo-original.glb',
          'review_status':'awaiting user approval'}
report['material_calibration_version'] = 1 if item['category'] != 'building' else 0
if item['id']=='28_beach_umbrella':
    report['cloth_sector_geometry_version']=1
if item['id']=='20_pier':
    report['open_approaches_version']=2
if item['category'] == 'bridge':
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromPolygons([v.co for v in building.data.vertices], [p.vertices[:] for p in building.data.polygons])
    samples = []
    length = float(building.dimensions.y)
    for i in range(41):
        t = -.485+i*.97/40
        hits = []
        for cross in [-.35, 0.0, .35]:
            point, normal, face, distance = tree.ray_cast(Vector((cross, t*length, height+3)), Vector((0,0,-1)), height+6)
            if point is not None:
                hits.append(float(point.z))
        samples.append({'t':t, 'height_m':float(np.median(hits)) if hits else None, 'hits':len(hits)})
    report['deck_centerline'] = samples
    report['long_axis_godot'] = '+Z'
assert report['uv_available'] and report['triangles']>100
if item['category'] != 'building':
    tint = {'37_round_tree':(.72,.82,.69,1),'40_shrub':(.72,.82,.69,1),'38_conifer':(.64,.75,.72,1),'39_palm':(.77,.85,.72,1)}.get(item['id'])
    for material in building.data.materials:
        if not material or not material.use_nodes:
            continue
        nodes=material.node_tree.nodes;links=material.node_tree.links
        bs=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
        if bs is None:
            continue
        for name,value in [('Metallic',0.0),('Roughness',.90 if item['category']=='vegetation' else .74),('Specular IOR Level',.25)]:
            for link in list(bs.inputs[name].links):
                links.remove(link)
            bs.inputs[name].default_value=value
        if tint and bs.inputs['Base Color'].links:
            socket=bs.inputs['Base Color'].links[0].from_socket
            multiply=nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY'
            multiply.inputs[0].default_value=1.0
            multiply.inputs[2].default_value=tint
            links.new(socket,multiply.inputs[1]);links.new(multiply.outputs[0],bs.inputs['Base Color'])
bpy.ops.export_scene.gltf(filepath=str(OUT/(stem+'.glb')),export_format='GLB',
                          use_selection=True,export_animations=False)
if item['category'] != 'building':
    # Material constants only: preserve every geometry and embedded image byte.
    path = OUT/(stem+'.glb')
    raw = path.read_bytes()
    jl,jt = struct.unpack_from('<II',raw,12)
    gltf = json.loads(raw[20:20+jl])
    at = 20+jl
    bl,bt = struct.unpack_from('<II',raw,at)
    binary = raw[at+8:at+8+bl]
    for material in gltf.get('materials',[]):
        pbr = material.setdefault('pbrMetallicRoughness',{})
        pbr['metallicFactor'] = 0.0
        pbr['roughnessFactor'] = .90 if item['category']=='vegetation' else .74
        pbr.pop('metallicRoughnessTexture',None)
        if item['id'] in ('37_round_tree','40_shrub'):
            pbr['baseColorFactor'] = [.72,.82,.69,1.0]
        elif item['id']=='38_conifer':
            pbr['baseColorFactor'] = [.64,.75,.72,1.0]
        elif item['id']=='39_palm':
            pbr['baseColorFactor'] = [.77,.85,.72,1.0]
        elif item['id']=='28_beach_umbrella' and material.get('name','').startswith('Beach_Cloth_'):
            pbr['baseColorFactor'] = [.12,.42,.88,1] if '_blue_' in material['name'] else [.98,.97,.92,1]
        if 'normalTexture' in material:
            material['normalTexture']['scale'] = .55 if item['category']=='vegetation' else .7
    text = json.dumps(gltf,separators=(',',':')).encode()
    text += b' '*((-len(text))%4)
    path.write_bytes(struct.pack('<III',0x46546c67,2,28+len(text)+len(binary))+struct.pack('<II',len(text),jt)+text+struct.pack('<II',len(binary),bt)+binary)
(LAB/'assets').mkdir(parents=True,exist_ok=True)
shutil.copy2(OUT/(stem+'.glb'),LAB/'assets'/(stem+'.glb'))
for obj in list(bpy.context.scene.objects):
    if obj!=building:
        bpy.data.objects.remove(obj,do_unlink=True)
if bpy.context.screen:
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.region_3d.view_distance=height*2.25
            area.spaces.active.region_3d.view_location=Vector((0,0,height*.5))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(stem+'.blend')))
(OUT/'mesh_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
spec = {'asset':item['id'],'name':item['name'],'stem':stem,'height_m':height,
        'width_m':report['dimensions_m'][0],
        'depth_m':report['dimensions_m'][1],
        'category':item['category'],
        'initial_azimuth':item.get('review_azimuth',.55),
        'model':'res://assets/'+stem+'.glb',
        'out':'res://../../art/maps/archipelago_objects_v1/'+item['id']+'/'}
(LAB/'reviews').mkdir(exist_ok=True)
text = json.dumps(spec,ensure_ascii=False,indent=2)
(LAB/'reviews'/(item['id']+'.json')).write_text(text,encoding='utf-8')
(LAB/'active_review.json').write_text(text,encoding='utf-8')
print('BUILDING_REVIEW_ASSET_READY',json.dumps(report),flush=True)
