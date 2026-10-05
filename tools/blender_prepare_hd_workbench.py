"""Append the seven approved HD sources for inspection, without assembling them."""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/characters/explorer_b_hd_restart_v1'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
specs = [
    ('fullbody', '01_Fullbody_HD', -3.2, 2.4, 1.8),
    ('head', '02_Head_HD', -1.1, 2.4, 1.15),
    ('hair', '03_Hair_HD', 1.1, 2.4, 1.15),
    ('hand', '04_Hand_HD', 3.2, 2.4, 1.15),
    ('upper_clothing', '05_Upper_Clothing_HD', -2.5, .55, 1.35),
    ('lower_clothing', '06_Lower_Clothing_HD', 0, .55, 1.35),
    ('footwear', '07_Footwear_HD', 2.5, .55, 1.2),
]
report = {'assembled': False, 'rigged': False, 'new_api_credits': 0,
          'display_transforms_only': True, 'parts': {}}
for part, collection_name, y, z, size in specs:
    source = BASE / part / f'{part}_HD.blend'
    assert source.is_file(), source
    collection = bpy.data.collections.new(collection_name)
    scene.collection.children.link(collection)
    with bpy.data.libraries.load(str(source), link=False) as (available, loaded):
        loaded.objects = [name for name in available.objects if name.startswith(f'HD_{part}_')]
    assert len(loaded.objects) == 1, (part, len(loaded.objects))
    obj = loaded.objects[0]
    assert obj.type == 'MESH'
    collection.objects.link(obj)
    native_matrix = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = native_matrix
    points = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    scale = size / max(hi-lo)
    transform = Matrix.Translation(Vector((0, y, z))) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-(lo+hi)/2)
    obj.matrix_world = transform @ native_matrix
    obj.hide_select = False
    obj.hide_viewport = False
    obj.hide_render = False
    obj.hide_set(False)
    obj['source_part'] = part
    obj['source_blend'] = str(source)
    obj['display_only_not_fitted'] = True
    obj['original_matrix_world'] = [value for row in native_matrix for value in row]
    obj.data.calc_loop_triangles()
    report['parts'][part] = {
        'source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'object': obj.name, 'collection': collection_name,
        'vertices': len(obj.data.vertices), 'polygons': len(obj.data.polygons),
        'triangles': len(obj.data.loop_triangles),
        'display_transform': [list(row) for row in transform],
        'original_matrix_world': [list(row) for row in native_matrix],
    }

studio = bpy.data.collections.new('08_Review_Studio')
scene.collection.children.link(studio)
center = Vector((0, 0, 1.6))
camera = bpy.data.objects.new('Workbench_Camera', bpy.data.cameras.new('Workbench_Camera'))
studio.objects.link(camera)
camera.location = (12, 0, 1.6)
camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 9.2
camera.hide_select = True
camera.hide_set(True)
scene.camera = camera
world = bpy.data.worlds.new('HD_Workbench_World')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.78, .83, .88, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = .5
scene.world = world
for name, position, power in [('Key', (4,-4,6), 1800), ('Fill', (4,4,3), 1200), ('Rim', (-3,0,5), 1000)]:
    light = bpy.data.lights.new(name, 'AREA')
    light.energy, light.size = power, 5
    obj = bpy.data.objects.new(name, light)
    studio.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (center-obj.location).to_track_quat('-Z', 'Y').to_euler()
    obj.hide_select = True
    obj.hide_set(True)
for part, collection_name, y, z, size in specs:
    curve = bpy.data.curves.new(f'Label_{part}', 'FONT')
    curve.body = collection_name.replace('_', ' ')
    curve.align_x, curve.size = 'CENTER', .12
    obj = bpy.data.objects.new(curve.name, curve)
    studio.objects.link(obj)
    obj.location = (.7, y, 1.35 if z > 1 else -.25)
    obj.rotation_euler = Vector((1,0,0)).to_track_quat('Z', 'Y').to_euler()
    obj.hide_select = True
bpy.ops.object.select_all(action='DESELECT')
body = bpy.data.objects['HD_fullbody_01']
body.select_set(True)
bpy.context.view_layer.objects.active = body
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.shading.type = 'SOLID'
            space.shading.light = 'STUDIO'
            space.shading.color_type = 'MATERIAL'
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.region_3d.view_location = center
            space.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            space.region_3d.view_perspective = 'ORTHO'
            space.region_3d.view_distance = 8
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
try:
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.compute_device_type = 'CUDA'
    preferences.get_devices()
    for device in preferences.devices:
        device.use = device.type == 'CUDA'
    if any(device.type == 'CUDA' for device in preferences.devices):
        scene.cycles.device = 'GPU'
except Exception:
    pass
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(BASE / 'HD-workbench-preview.png')
target = BASE / 'explorer_b_HD_parts_workbench.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(target))
bpy.ops.render.render(write_still=True)
bpy.ops.wm.open_mainfile(filepath=str(target))
meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
assert len(meshes) == 7
assert not any(obj.type == 'ARMATURE' for obj in bpy.data.objects)
for part, entry in report['parts'].items():
    obj = bpy.data.objects[entry['object']]
    assert not obj.hide_select and not obj.hide_viewport and not obj.hide_get()
    assert obj.visible_get()
    assert len(obj.data.vertices) == entry['vertices']
    assert len(obj.data.polygons) == entry['polygons']
    assert entry['collection'] in [col.name for col in obj.users_collection]
    assert hashlib.sha256(Path(entry['source']).read_bytes()).hexdigest() == entry['sha256']
report['workbench_blend'] = str(target)
report['verified_after_reopening'] = True
report['total_triangles'] = sum(entry['triangles'] for entry in report['parts'].values())
(BASE / 'HD-workbench-import-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('HD_WORKBENCH_VERIFIED', len(meshes), report['total_triangles'], flush=True)
