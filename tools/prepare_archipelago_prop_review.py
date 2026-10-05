"""Normalize the generated cafe, preserving the original mesh and PBR maps."""
from pathlib import Path
import json
import math
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/maps/archipelago_objects_v1/01_cafe'
DEST = ROOT / 'labs/archipelago_object_lab/assets'
DEST.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT / 'tripo-original.glb'))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert meshes, 'No generated geometry'
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
    transform = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = transform
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
building = bpy.context.object
building.name = 'Cafe_01_Tripo'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
building.rotation_mode = 'XYZ'
# Tripo +X front becomes Blender -Y front, exported as Godot +Z.
building.rotation_euler.z = -math.pi / 2
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
points = [building.matrix_world @ Vector(v) for v in building.bound_box]
lo = Vector([min(p[i] for p in points) for i in range(3)])
hi = Vector([max(p[i] for p in points) for i in range(3)])
factor = 8.0 / (hi.z - lo.z)
origin = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, lo.z))
for vertex in building.data.vertices:
    vertex.co = (vertex.co - origin) * factor
building.location = Vector()
building.data.update()
bpy.context.view_layer.update()
building['provenance'] = 'Tripo image-to-model P2-20260801'
building['reference'] = 'Upper-left island red-roof cafe'
building['review_status'] = 'awaiting user approval'
building['height_m'] = 8.0
building.data.calc_loop_triangles()
# The generated facade omits several panes. Recessed, opaque stylized glass
# closes their background without altering the preserved Tripo facade mesh.
glass = bpy.data.materials.new('Local_recessed_blue_glass')
glass.use_nodes = True
bs = glass.node_tree.nodes.get('Principled BSDF')
bs.inputs['Base Color'].default_value = (.015,.145,.23,1)
bs.inputs['Roughness'].default_value = .22
bs.inputs['Metallic'].default_value = .08
bs.inputs['Specular IOR Level'].default_value = .45
plaster = bpy.data.materials.new('Local_recessed_warm_plaster')
plaster.use_nodes = True
plaster.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.72,.52,.33,1)
plaster.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .85
repairs = []
for name, radius_bottom, radius_top, bottom, top in [
    ('Window_glass_recessed',3.70,3.70,.42,2.62),
    ('Wall_plaster_recessed',3.70,3.70,2.62,3.65),
    ('Dormer_glass_recessed',3.70,.72,3.65,5.80),
    ('Cupola_glass_recessed',.70,.70,6.00,6.90),
]:
    bpy.ops.mesh.primitive_cone_add(vertices=96, radius1=radius_bottom, radius2=radius_top,
                                   depth=top-bottom, location=(-.02,.34,(top+bottom)/2))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(plaster if 'plaster' in name else glass)
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    repairs.append(obj)
images = []
for image in bpy.data.images:
    if image.type == 'IMAGE' and image.size[0]:
        images.append({'name':image.name, 'size':list(image.size)})
        if image.packed_file is None:
            image.pack()
report = {'height_m':8.0, 'dimensions_m':list(building.dimensions),
          'vertices':len(building.data.vertices), 'triangles':len(building.data.loop_triangles),
          'materials':len(building.data.materials), 'textures':images,
          'uv_available':bool(building.data.uv_layers), 'original_preserved':True,
          'geometry_regenerated_locally':False, 'front_axis_godot':'+Z',
          'local_repairs':'Recessed blue glass behind missing panes and warm plaster above facade windows',
          'local_glass_objects':3, 'local_plaster_objects':1,
          'source':'tripo-original.glb', 'review_status':'awaiting user approval'}
assert report['uv_available'] and report['triangles'] > 100
bpy.ops.object.select_all(action='DESELECT')
for obj in [building]+repairs:
    obj.select_set(True)
bpy.context.view_layer.objects.active = building
bpy.ops.export_scene.gltf(filepath=str(OUT / 'cafe.glb'), export_format='GLB',
                           use_selection=True, export_animations=False)
import shutil
shutil.copy2(OUT / 'cafe.glb', DEST / 'cafe.glb')
for obj in list(bpy.context.scene.objects):
    if obj not in [building]+repairs:
        bpy.data.objects.remove(obj, do_unlink=True)
if bpy.context.screen:
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'MATERIAL'
            area.spaces.active.region_3d.view_distance = 18.0
            area.spaces.active.region_3d.view_location = Vector((0,0,4))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'cafe.blend'))
(OUT / 'mesh_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('CAFE_REVIEW_ASSET_READY',json.dumps(report),flush=True)
