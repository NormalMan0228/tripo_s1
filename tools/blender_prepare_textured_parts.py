"""Prepare separately selectable textured parts, never assemble or rig them."""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/characters/explorer_b_fullbody_v2/06_textured_parts'
OLD = ROOT / 'art/characters/explorer_b_modular_v1/03_generated'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
try:
    p = bpy.context.preferences.addons['cycles'].preferences
    p.compute_device_type = 'CUDA'
    p.get_devices()
    for d in p.devices:
        d.use = d.type == 'CUDA'
    if any(d.type == 'CUDA' for d in p.devices):
        scene.cycles.device = 'GPU'
except Exception:
    pass
report = {'new_api_credits': 0, 'assembled': False, 'rigged': False,
          'display_scale_is_not_character_fitting': True, 'parts': {}}
work_collections = []

def bounds(objects):
    points = [o.matrix_world @ Vector(v) for o in objects for v in o.bound_box]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    return lo, hi

def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.hide_select = False
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

specs = [('fullbody', '01_Fullbody_P2', -3.2, 2.3, 1.65),
         ('head', '02_Head_P2', -1.1, 2.3, 1.05),
         ('hand', '03_Hand_P2', 1.1, 2.3, 1.05),
         ('hair', '04_Hair_P2', 3.2, 2.3, 1.05),
         ('jacket', '05_Jacket', -3.4, .55, 1.05),
         ('shirt', '06_Shirt', -1.7, .55, 1.05),
         ('pants', '07_Pants', 0, .55, 1.05),
         ('boots', '08_Boot', 1.7, .55, .95),
         ('belt', '09_Belt', 3.4, .55, 1.15)]
for part, cname, slot_y, slot_z, display_size in specs:
    collection = bpy.data.collections.new(cname)
    scene.collection.children.link(collection)
    work_collections.append(collection)
    source = BASE / part / f'{part}_textured.blend' if part in ('fullbody', 'head', 'hand', 'hair') else OLD / part / 'model.glb'
    if source.suffix == '.blend':
        with bpy.data.libraries.load(str(source), link=False) as (available, loaded):
            loaded.objects = [name for name in available.objects if name.startswith(f'P2_{part}_')]
        imported = loaded.objects
        for o in imported:
            collection.objects.link(o)
    else:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(source))
        added = [o for o in bpy.data.objects if o not in before]
        imported = [o for o in added if o.type == 'MESH']
        for o in imported:
            matrix = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = matrix
            for c in list(o.users_collection):
                c.objects.unlink(o)
            collection.objects.link(o)
            o.name = f'Existing_{part}'
        for o in added:
            if o not in imported:
                bpy.data.objects.remove(o, do_unlink=True)
    original_vertex_count = sum(len(o.data.vertices) for o in imported)
    original_polygons = sum(len(o.data.polygons) for o in imported)
    # Disconnect already separate source islands into actual clickable objects.
    # No welding, cutting, deleting, or change to any surface/UV coordinate.
    if part in ('fullbody', 'head', 'hair'):
        for o in list(imported):
            activate(o)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.separate(type='LOOSE')
            bpy.ops.object.mode_set(mode='OBJECT')
        imported = list(collection.objects)
        ordered = sorted(imported, key=lambda o: len(o.data.vertices), reverse=True)
        for i, o in enumerate(ordered):
            o.name = f'{part}_component_{i+1:02d}'
        if part == 'head':
            ordered[0].name = 'Head_Skin_Neck'
        if part == 'fullbody':
            ordered[0].name = 'Fullbody_Base_Head_Neck'
    assert sum(len(o.data.vertices) for o in imported) == original_vertex_count
    assert sum(len(o.data.polygons) for o in imported) == original_polygons
    for o in imported:
        o.hide_select = False
        o.hide_viewport = False
        o.hide_render = False
        o.hide_set(False)
        o['source_part'] = part
        o['assembled'] = False
        o['review_status'] = 'Texture review, fitting and rigging pending'

    # Dedicated standalone scenes are written after saving the workbench.
    part_folder = BASE / part
    part_folder.mkdir(exist_ok=True)
    individual = part_folder / f'{part}_individual.blend'
    lo, hi = bounds(imported)
    center = (lo + hi) / 2
    scale = display_size / max(hi - lo)
    matrix = Matrix.Translation(Vector((0, slot_y, slot_z))) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-center)
    for o in imported:
        o.matrix_world = matrix @ o.matrix_world
    report['parts'][part] = {'texture_source': str(source.relative_to(ROOT)),
                            'file_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                            'vertices': original_vertex_count, 'polygons': original_polygons,
                            'separately_selectable_meshes': len(imported),
                            'display_scale': scale, 'display_transform': [list(row) for row in matrix],
                            'individual_blend': str(individual.relative_to(ROOT))}

studio = bpy.data.collections.new('10_Review_Studio')
scene.collection.children.link(studio)
world = bpy.data.worlds.new('Parts Studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.78, .83, .88, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = .5
scene.world = world
center = Vector((0, 0, 1.55))
for name, offset, power, size in [('Key', (4, -4, 6), 1800, 5), ('Fill', (4, 4, 3), 1200, 5), ('Rim', (-3, 0, 5), 1000, 4)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.size = power, size
    o = bpy.data.objects.new(name, data)
    studio.objects.link(o)
    o.location = Vector(offset)
    o.rotation_euler = (center - o.location).to_track_quat('-Z', 'Y').to_euler()
    o.hide_select = True
    o.hide_set(True)

label_mat = bpy.data.materials.new('Labels')
label_mat.diffuse_color = (.06, .08, .1, 1)
for part, cname, y, z, sz in specs:
    data = bpy.data.curves.new(f'{part}_label', 'FONT')
    data.body = cname.replace('_', ' ')
    data.align_x = 'CENTER'
    data.size = .12
    o = bpy.data.objects.new(f'Label_{part}', data)
    studio.objects.link(o)
    o.location = (.65, y, 1.30 if z > 1 else -.13)
    o.rotation_euler = Vector((1,0,0)).to_track_quat('Z', 'Y').to_euler()
    o.data.materials.append(label_mat)
    o.hide_select = True
camera = bpy.data.objects.new('Workbench_Camera', bpy.data.cameras.new('Workbench_Camera'))
studio.objects.link(camera)
camera.location = (12, 0, 1.55)
camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 9.2
camera.hide_select = True
camera.hide_set(True)
scene.camera = camera
scene.render.resolution_x, scene.render.resolution_y = 1900, 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
bpy.ops.object.select_all(action='DESELECT')
head = next(o for o in work_collections[1].objects if o.name == 'Head_Skin_Neck')
head.select_set(True)
bpy.context.view_layer.objects.active = head
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'MATERIAL'
            area.spaces.active.overlay.show_floor = False
            area.spaces.active.overlay.show_axis_x = False
            area.spaces.active.overlay.show_axis_y = False
            rv = area.spaces.active.region_3d
            rv.view_location = center
            rv.view_rotation = camera.rotation_euler.to_quaternion()
            rv.view_perspective = 'ORTHO'
            rv.view_distance = 8
bpy.ops.file.pack_all()
workbench = BASE / 'explorer_b_textured_parts_workbench.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(workbench))
scene.render.filepath = str(BASE / 'workbench-preview.png')
bpy.ops.render.render(write_still=True)
report['workbench_blend'] = str(workbench.relative_to(ROOT))
report['limitations'] = ['Texture transfer is complete; fitting, topology cleanup, UV optimization and rigging still need separate review.',
                         'Component numbers identify pre-existing connected islands, not anatomical cutting.',
                         'Fullbody and replacement parts intentionally remain separate; display sizes are only for inspection.',
                         'Garments retain their existing generated textures and geometry.']
(BASE / 'preparation-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
for part, cname, _, _, _ in specs:
    bpy.ops.wm.open_mainfile(filepath=str(workbench))
    scene = bpy.context.scene
    collection = bpy.data.collections[cname]
    kept = list(collection.objects)
    for obj in list(bpy.data.objects):
        if obj not in kept:
            bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        if col != collection:
            bpy.data.collections.remove(col)
    inverse = Matrix(report['parts'][part]['display_transform']).inverted()
    for obj in kept:
        obj.matrix_world = inverse @ obj.matrix_world
        obj.hide_set(False)
        obj.hide_select = False
    lo, hi = bounds(kept)
    c, r = (lo+hi)/2, max(hi-lo)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                rv = area.spaces.active.region_3d
                rv.view_location = c
                rv.view_distance = r*2
                rv.view_rotation = Vector((-4, .4, -.2)).to_track_quat('-Z','Y')
    bpy.ops.object.select_all(action='DESELECT')
    largest = max(kept, key=lambda o: len(o.data.vertices))
    largest.select_set(True)
    bpy.context.view_layer.objects.active = largest
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(BASE / part / f'{part}_individual.blend'))
print('PARTS_WORKBENCH_READY', flush=True)
