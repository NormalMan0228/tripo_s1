"""Transfer reviewed Tripo face labels to independently selectable skinned parts.

The original animation file remains untouched. This separates existing surfaces;
it does not invent a hidden body beneath the clothes or add facial/finger rigs.
"""
import bpy
import bmesh
import json
import numpy as np
from pathlib import Path
from collections import defaultdict
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/character-parts-20261003'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'artifacts/video-motion-20261003/explorer_video_motions.blend'
DEST = ROOT / 'art/source/explorer_b_parts_20261003.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene = bpy.context.scene
scene.name = 'Explorer_B_Parts'
scene.frame_set(1)
source = bpy.data.objects['Explorer_B_Cohesive_Surface']
rig = bpy.data.objects['Explorer_B_Video_Reference_Rig']
original = source.data
before = {'polygons': len(original.polygons), 'vertices': len(original.vertices),
          'bones': len(rig.data.bones), 'actions': sorted(a.name for a in bpy.data.actions)}
source_points = np.array([source.matrix_world @ v.co for v in original.vertices])
alignment = json.loads((OUT / 'segment-inspection.json').read_text(encoding='utf-8'))
rotation = Matrix.Rotation(np.radians(alignment['rotation_deg']), 3, 'Z')
old_objects = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(ROOT / 'artifacts/detail-map-20261003/tripo/character_detail/body-detailed-segment/model.glb'))
imported = [o for o in bpy.data.objects if o not in old_objects]
segments = [o for o in imported if o.type == 'MESH']
centroids, segment_ids, segment_corners = [], [], []
for obj in segments:
    transformed = [(rotation @ (obj.matrix_world @ v.co - Vector(alignment['raw_center'])))
                   * alignment['scale'] + Vector(alignment['source_center'])
                   for v in obj.data.vertices]
    sid = int(obj.name.rsplit('_', 1)[1])
    for polygon in obj.data.polygons:
        centroids.append(sum((transformed[i] for i in polygon.vertices), Vector()) / len(polygon.vertices))
        segment_ids.append(sid)
        segment_corners.append([transformed[i] for i in polygon.vertices])
tree = KDTree(len(centroids))
for i, point in enumerate(centroids):
    tree.insert(point, i)
tree.balance()
labels, distances, matches = [], [], []
matched = set()
max_matching_corner_error = 0.0
for polygon in original.polygons:
    center = source.matrix_world @ polygon.center
    corners = [source.matrix_world @ original.vertices[i].co for i in polygon.vertices]
    candidates = [hit for hit in tree.find_range(center, .000002) if hit[1] not in matched]
    if not candidates:
        raise RuntimeError('No unique corresponding triangle')
    def corner_error(hit):
        return max(min((point - candidate).length for candidate in segment_corners[hit[1]]) for point in corners)
    _, index, distance = min(candidates, key=corner_error)
    max_matching_corner_error = max(max_matching_corner_error, corner_error((None, index, distance)))
    matched.add(index)
    labels.append(segment_ids[index])
    distances.append(distance)
    matches.append(index)
if max(distances) > 0.00001 or max_matching_corner_error > .000002 or len(set(matches)) != len(original.polygons):
    raise RuntimeError(f'Face labels did not match the original exactly: {max(distances)}; unique {len(set(matches))}')
for obj in imported:
    bpy.data.objects.remove(obj, do_unlink=True)

# Group IDs were reviewed in segment-contact-sheet-{1,2}.png.
mapping = {
    0: 'Hair_Main', 20: 'Hair_Sidelock_R',
    3: 'Head_Face_Neck', 53: 'Head_Face_Neck',
    13: 'Eye_R', 26: 'Eye_L',
    28: 'Eyelid_Upper_R', 29: 'Eyelid_Upper_L',
    41: 'Eyelid_Lower_R', 42: 'Eyelid_Lower_L',
    34: 'Eyebrow_R', 35: 'Eyebrow_L', 14: 'Nose', 45: 'Lips',
    1: 'Jacket_Torso', 17: 'Jacket_Torso', 22: 'Jacket_Torso',
    44: 'Jacket_Torso', 46: 'Jacket_Torso', 47: 'Jacket_Torso',
    48: 'Jacket_Torso', 49: 'Jacket_Torso',
    11: 'Jacket_Sleeve_R', 18: 'Jacket_Sleeve_L',
    8: 'Jacket_Cuff_R', 19: 'Jacket_Cuff_L', 9: 'Shirt_Torso',
    12: 'Pants_Cuff_L', 21: 'Pants_Cuff_R',
    25: 'Pants_Cargo_Pocket_L', 27: 'Pants_Cargo_Pocket_R',
    50: 'Belt_Strap', 51: 'Belt_Strap', 52: 'Belt_Strap', 54: 'Belt_Strap',
    23: 'Belt_Buckle', 72: 'Belt_Buckle', 76: 'Belt_Buckle',
}
sole_ids = {5: 'Boot_Sole_L', 15: 'Boot_Sole_R'}
upper_ids = {6: 'Boot_Upper_L', 16: 'Boot_Upper_R', 40: 'Boot_Upper_L', 43: 'Boot_Upper_R'}
lace_ids = {10, 24, 30, 31, 32, 33, 36, 37, 38, 39}
shoe_detail_ids = {p['id'] for p in alignment['parts'] if p['hi'][2] < .14}

def classify(polygon, sid):
    center = source.matrix_world @ polygon.center
    if sid == 2:
        if center.z > .595:
            return 'Pants_Waist'
        return 'Pants_Leg_L' if center.y >= 0 else 'Pants_Leg_R'
    if sid in (4, 7):
        side = 'R' if sid == 4 else 'L'
        hand = rig.data.bones[side + '_Hand']
        wrist = rig.matrix_world @ hand.head_local
        direction = (rig.matrix_world.to_3x3() @ (hand.tail_local - hand.head_local)).normalized()
        return ('Hand_' if (center - wrist).dot(direction) >= 0 else 'Forearm_') + side
    if sid in sole_ids:
        return sole_ids[sid]
    if sid in upper_ids:
        return upper_ids[sid]
    if sid in lace_ids:
        return 'Boot_Laces_L' if center.y >= 0 else 'Boot_Laces_R'
    if sid in shoe_detail_ids:
        return 'Boot_Hardware_L' if center.y >= 0 else 'Boot_Hardware_R'
    if sid not in mapping:
        raise RuntimeError(f'Unreviewed fragment {sid}')
    return mapping[sid]

families = defaultdict(list)
for polygon, sid in zip(original.polygons, labels):
    families[classify(polygon, sid)].append(polygon.index)

collections = {}
for label in ('01_Head_and_Face', '02_Hair', '03_Torso_Clothes',
              '04_Arms_and_Hands', '05_Pants_and_Belt', '06_Boots', '07_Rig'):
    collection = bpy.data.collections.new(label)
    scene.collection.children.link(collection)
    collections[label] = collection

def target_collection(name):
    if name.startswith('Hair_'):
        return collections['02_Hair']
    if name.startswith(('Head_', 'Eye', 'Nose', 'Lips')):
        return collections['01_Head_and_Face']
    if name.startswith(('Jacket_', 'Shirt_')):
        return collections['03_Torso_Clothes']
    if name.startswith(('Forearm_', 'Hand_')):
        return collections['04_Arms_and_Hands']
    if name.startswith(('Pants_', 'Belt_')):
        return collections['05_Pants_and_Belt']
    return collections['06_Boots']

source_normals = [tuple(n.vector) for n in original.corner_normals]
parts, part_report = [], []
for name, face_indices in sorted(families.items()):
    polygons = [original.polygons[i] for i in face_indices]
    indices = sorted({i for p in polygons for i in p.vertices})
    remap = {old: new for new, old in enumerate(indices)}
    data = bpy.data.meshes.new(name + '_Mesh')
    data.from_pydata([original.vertices[i].co[:] for i in indices], [],
                     [[remap[i] for i in p.vertices] for p in polygons])
    for material in original.materials:
        data.materials.append(material)
    for new_polygon, old_polygon in zip(data.polygons, polygons):
        new_polygon.material_index = old_polygon.material_index
        new_polygon.use_smooth = old_polygon.use_smooth
    loops = [i for p in polygons for i in p.loop_indices]
    for layer in original.uv_layers:
        new_layer = data.uv_layers.new(name=layer.name)
        for new_loop, old_loop in zip(new_layer.data, loops):
            new_loop.uv = layer.data[old_loop].uv
    obj = source.copy()
    obj.name = name
    obj.data = data
    # Blender 4.5 clears the object's group-name table when assigning a fresh
    # mesh datablock. Restore names in the exact source index order before
    # writing deform weights; indices alone do not make an animated skin.
    obj.vertex_groups.clear()
    for group in source.vertex_groups:
        obj.vertex_groups.new(name=group.name).lock_weight = group.lock_weight
    target_collection(name).objects.link(obj)
    obj.hide_viewport = False
    obj.hide_render = False
    obj.hide_select = False
    obj.hide_set(False)
    bm = bmesh.new()
    bm.from_mesh(data)
    bm.verts.ensure_lookup_table()
    deform = bm.verts.layers.deform.verify()
    for vertex, source_index in zip(bm.verts, indices):
        for assignment in original.vertices[source_index].groups:
            vertex[deform][assignment.group] = assignment.weight
    bm.to_mesh(data)
    bm.free()
    data.normals_split_custom_set([source_normals[i] for i in loops])
    vertex_attribute = data.attributes.new('source_vertex_index', 'INT', 'POINT')
    vertex_attribute.data.foreach_set('value', indices)
    face_attribute = data.attributes.new('source_face_index', 'INT', 'FACE')
    face_attribute.data.foreach_set('value', face_indices)
    obj['semantic_part'] = name
    obj['source_segment_ids'] = sorted(set(labels[i] for i in face_indices))
    obj['source'] = 'Tripo detailed labels transferred to original animated mesh'
    obj['wardrobe_status'] = 'Existing surface only; hidden under-clothing body and caps are not generated'
    obj.select_set(False)
    parts.append(obj)
    part_report.append({'name': name, 'faces': len(polygons), 'vertices': len(indices),
                        'source_segment_ids': list(obj['source_segment_ids'])})
    print('CREATED_PART', name, len(polygons), flush=True)

# Check the split retained UVs, corner normals, vertex weights and all faces.
max_weight_error = 0.0
max_uv_error = 0.0
max_normal_error = 0.0
seen_faces = []
seam_copies = defaultdict(list)
for obj in parts:
    assert [g.name for g in obj.vertex_groups] == [g.name for g in source.vertex_groups]
    indices = [x.value for x in obj.data.attributes['source_vertex_index'].data]
    face_indices = [x.value for x in obj.data.attributes['source_face_index'].data]
    seen_faces.extend(face_indices)
    for vertex, index in zip(obj.data.vertices, indices):
        expected = {g.group: g.weight for g in original.vertices[index].groups}
        actual = {g.group: g.weight for g in vertex.groups}
        if set(expected) != set(actual):
            raise RuntimeError('Skin group indices changed')
        for key in expected:
            max_weight_error = max(max_weight_error, abs(expected[key] - actual[key]))
        seam_copies[index].append((obj, vertex.index))
    for polygon, source_index in zip(obj.data.polygons, face_indices):
        old_polygon = original.polygons[source_index]
        for new_loop, old_loop in zip(polygon.loop_indices, old_polygon.loop_indices):
            for layer in original.uv_layers:
                max_uv_error = max(max_uv_error, (obj.data.uv_layers[layer.name].data[new_loop].uv - layer.data[old_loop].uv).length)
            max_normal_error = max(max_normal_error, (obj.data.corner_normals[new_loop].vector - original.corner_normals[old_loop].vector).length)
assert sorted(seen_faces) == list(range(len(original.polygons)))
assert max_weight_error == 0 and max_uv_error == 0
# Blender encodes custom corner normals relative to the new vertex fans.
# Splitting a fan re-encodes their short integer representation; allow less
# than 0.5 degrees of storage error, but reject a changed shading direction.
if max_normal_error > 0.0087266:
    raise RuntimeError(f'Corner normals changed: {max_normal_error}')

# Verify exact skinning continuity against the full surface at multiple frames
# in each action, not merely the visible first-frame pose.
shared = {k: v for k, v in seam_copies.items() if len(v) > 1}
action_before = rig.animation_data.action
max_deformation_error = 0.0
max_seam_gap = 0.0
worst_sample = None
checks = []
for action in bpy.data.actions:
    rig.animation_data.action = action
    start, end = action.frame_range
    frames = sorted({int(start), int(end), round((start + end) / 2),
                     round(start + (end - start) * .25), round(start + (end - start) * .75)})
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        reference = source.evaluated_get(depsgraph)
        evaluated = {obj.name: obj.evaluated_get(depsgraph) for obj in parts}
        for obj in parts:
            target = evaluated[obj.name]
            indices = obj.data.attributes['source_vertex_index'].data
            for vertex, index in zip(target.data.vertices, indices):
                error = (target.matrix_world @ vertex.co - reference.matrix_world @ reference.data.vertices[index.value].co).length
                if error > max_deformation_error:
                    max_deformation_error = error
                    worst_sample = {'action': action.name, 'frame': frame, 'part': obj.name,
                                    'vertex': vertex.index, 'source_vertex': index.value,
                                    'new_rest': list(obj.data.vertices[vertex.index].co),
                                    'source_rest': list(original.vertices[index.value].co),
                                    'new_pose': list(vertex.co),
                                    'source_pose': list(reference.data.vertices[index.value].co),
                                    'new_matrix': [list(row) for row in target.matrix_world],
                                    'source_matrix': [list(row) for row in reference.matrix_world],
                                    'new_groups': [g.name for g in obj.vertex_groups],
                                    'source_groups': [g.name for g in source.vertex_groups],
                                    'new_modifiers': [{'type':m.type, 'rig':m.object.name,
                                                       'groups':m.use_vertex_groups, 'envelopes':m.use_bone_envelopes,
                                                       'preserve_volume':m.use_deform_preserve_volume}
                                                      for m in obj.modifiers if m.type=='ARMATURE']}
        for original_index, copies in shared.items():
            first_obj, first_vertex = copies[0]
            first = evaluated[first_obj.name]
            position = first.matrix_world @ first.data.vertices[first_vertex].co
            for obj, vertex_index in copies[1:]:
                other = evaluated[obj.name]
                max_seam_gap = max(max_seam_gap, (other.matrix_world @ other.data.vertices[vertex_index].co - position).length)
        checks.append({'action': action.name, 'frame': frame})
    print('VERIFIED_ACTION', action.name, flush=True)
if max_deformation_error > 0.000001 or max_seam_gap > 0.000001:
    (OUT / 'failed-animation-sample.json').write_text(json.dumps(worst_sample, indent=2), encoding='utf-8')
    raise RuntimeError(f'Split broke animation continuity: {max_deformation_error}, {max_seam_gap}')
rig.animation_data.action = action_before
scene.frame_set(1)
bpy.data.objects.remove(source, do_unlink=True)
for collection in list(rig.users_collection):
    collection.objects.unlink(rig)
collections['07_Rig'].objects.link(rig)
rig.hide_set(True)
rig.data.display_type = 'STICK'
rig.show_in_front = False

# A safe modelling view: object mode, selectable parts, visible selection outline.
points = [obj.matrix_world @ Vector(p) for obj in parts for p in obj.bound_box]
low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (low + high) * .5
height = high.z - low.z
direction = Vector((1, -.35, .17)).normalized()
rotation = (-direction).to_track_quat('-Z', 'Y')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.shading.type = 'MATERIAL'
            space.shading.use_scene_world = False
            space.shading.use_scene_lights = False
            space.overlay.show_overlays = True
            space.overlay.show_outline_selected = True
            space.overlay.show_bones = False
            space.overlay.show_extras = False
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_wireframes = False
            space.clip_start = .001
            space.region_3d.view_perspective = 'ORTHO'
            space.region_3d.view_location = center
            space.region_3d.view_rotation = rotation
            space.region_3d.view_distance = height * 1.6
        elif area.type == 'OUTLINER':
            area.spaces.active.show_restrict_column_select = True
for window in bpy.context.window_manager.windows:
    window.workspace = bpy.data.workspaces['Layout']
for obj in scene.objects:
    obj.select_set(False)
active = next(obj for obj in parts if obj.name == 'Jacket_Torso')
active.select_set(True)
bpy.context.view_layer.objects.active = active

# Compact studio preview, using the exact assembled geometry.
for obj in list(scene.objects):
    if obj.type in {'CAMERA', 'LIGHT'}:
        bpy.data.objects.remove(obj, do_unlink=True)
camera_data = bpy.data.cameras.new('Parts_Preview_Camera')
camera = bpy.data.objects.new('Parts_Preview_Camera', camera_data)
scene.collection.objects.link(camera)
camera.location = center + direction * height * 3
camera.rotation_euler = rotation.to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = height * 1.22
scene.camera = camera
for name, pos, power, size in [('Key', (2,-3,4),160,2), ('Fill', (2,3,2),75,2.5), ('Rim', (-2,1,3),120,1.5)]:
    data = bpy.data.lights.new('Parts_' + name, 'AREA')
    data.energy = power * height * height
    data.shape = 'DISK'
    data.size = size * height
    obj = bpy.data.objects.new('Parts_' + name, data)
    scene.collection.objects.link(obj)
    obj.location = center + Vector(pos) * height
    obj.rotation_euler = (center - obj.location).to_track_quat('-Z', 'Y').to_euler()
world = bpy.data.worlds.new('Parts_Preview_World')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.12,.15,.2,1)
world.node_tree.nodes['Background'].inputs[1].default_value = .5
scene.world = world
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 900
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
scene.render.filepath = str(OUT / 'parts-assembled.png')
guide = bpy.data.texts.new('START_HERE_PARTS.txt')
guide.write('EXPLORER B - INDEPENDENTLY SELECTABLE PARTS\n\n'
            'Object Mode: left-click a visible part or its named object in the Outliner.\n'
            'Tab: edit the active part only. H: hide it. Alt-H: show hidden parts (including the rig).\n'
            'The 41-bone rig and all six existing animation Actions are retained.\n'
            'This is semantic separation of the existing visible surfaces.\n'
            'It does not add a complete body under the clothes, watertight caps, new finger bones, or facial blendshapes.\n'
            'The original unified animation source is preserved separately.\n')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(DEST))
report = {'source': str(SOURCE), 'blend': str(DEST), 'semantic_parts': len(parts),
          'part_inventory': part_report, 'original': before,
          'polygon_conservation': sum(len(obj.data.polygons) for obj in parts) == before['polygons'],
          'matching_face_distance_max': max(distances),
          'matching_corner_distance_max': max_matching_corner_error,
          'matching_faces_bijective': len(set(matches)) == before['polygons'],
          'uv_error_max': max_uv_error, 'skin_weight_error_max': max_weight_error,
          'corner_normal_error_max': max_normal_error,
          'corner_normal_storage_tolerance_degrees': .5,
          'animation_deformation_error_max': max_deformation_error,
          'seam_gap_max': max_seam_gap, 'animation_samples': checks,
          'shared_boundary_vertices': len(shared),
          'original_source_modified': False, 'new_api_calls': 0,
          'limitations': ['No hidden body under clothes or new boundary caps',
                          'No added facial morphs or individual finger rig',
                          'Existing generated surface topology retained']}
(OUT / 'parts-manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('SEMANTIC_PARTS_READY ' + json.dumps({k: v for k, v in report.items() if k not in {'part_inventory','animation_samples'}}), flush=True)

# Export a reuse asset without deploying it to the game.
for obj in scene.objects:
    obj.select_set(False)
rig.hide_set(False)
rig.select_set(True)
for obj in parts:
    obj.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=str(OUT / 'explorer_b_parts.glb'), export_format='GLB',
                         use_selection=True, export_animations=True, export_animation_mode='ACTIONS',
                         export_force_sampling=True, export_def_bones=True, export_skins=True)
rig.hide_set(True)
for obj in parts:
    obj.select_set(False)
active.select_set(True)
bpy.context.view_layer.objects.active = active
bpy.ops.wm.save_as_mainfile(filepath=str(DEST))
bpy.ops.render.render(write_still=True)
