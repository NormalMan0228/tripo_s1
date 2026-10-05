import bpy
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
assets = root / 'art/characters/npc_cast_closed_v2'
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
meshes = []
for key, offset in [('sora', -2.1), ('moru', -.7), ('naru', .7), ('haeru', 2.1)]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(assets / key / (key + '_static.glb')))
    imported = set(bpy.data.objects) - before
    collection = bpy.data.collections.new(key.upper())
    scene.collection.children.link(collection)
    for obj in imported:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
        if obj.parent is None:
            obj.location.y += offset
        if obj.type == 'MESH':
            obj.name = key + '_' + obj.name
            meshes.append(obj)

for image in bpy.data.images:
    if image.has_data and not image.packed_file:
        image.pack()
view_rotation = (Vector((0, 0, 1)) - Vector((8, 0, 1))).to_track_quat('-Z', 'Y')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.shading.type = 'MATERIAL'
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.region_3d.view_rotation = view_rotation
            space.region_3d.view_location = (0, 0, .95)
            space.region_3d.view_distance = 6.2
            space.region_3d.view_perspective = 'ORTHO'
bpy.ops.object.select_all(action='DESELECT')
scene['character_order'] = 'sora / moru / naru / haeru'
scene['asset_status'] = 'Static closed-mouth models, no face or body rig'
assert len([o for o in scene.objects if o.type == 'MESH']) >= 4
assert not any(o.type == 'ARMATURE' for o in scene.objects)
destination = assets / 'npc_lineup_v2.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(destination))
print('NPC_LINEUP_SAVED', str(destination), 'meshes', len(meshes))
