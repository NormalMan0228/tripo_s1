"""Review sheet for one built monster GLB: one row per clip, evenly spaced frames, game-like 3/4 camera.

blender -b --factory-startup --python tools/blender_monster_sheet.py -- <monster.glb> <out_prefix> [frames]
Writes <out_prefix>_<clip>_<n>.png tiles; tools/build_monsters.py --sheets assembles them.
"""
import bpy
import math
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
src, out = args[0], args[1]
count = int(args[2]) if len(args) > 2 else 6
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
for ob in list(bpy.data.objects):
    if ob.type == 'MESH' and ob.name.startswith('Icosphere'):
        bpy.data.objects.remove(ob)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE'
scene.render.resolution_x = scene.render.resolution_y = 256
scene.render.fps = 30
for mat in bpy.data.materials:  # show the base colour, not the last-added (emission) image node
    if mat.use_nodes:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        links = bsdf.inputs['Base Color'].links if bsdf else []
        if links:
            mat.node_tree.nodes.active = links[0].from_node
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for m in meshes:
    for c in m.bound_box:
        w = m.matrix_world @ Vector(c)
        lo, hi = Vector(map(min, lo, w)), Vector(map(max, hi, w))
size = max(hi - lo) * 1.15
center = Vector((0, 0, (hi.z - lo.z) * 0.45))
cam_data = bpy.data.cameras.new('cam')
cam_data.type = 'ORTHO'
cam_data.ortho_scale = size * 1.5
cam = bpy.data.objects.new('cam', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
azimuth, elevation = math.radians(-60), math.radians(32)  # front-right 3/4 (creature faces -Y)
cam.location = center + Vector((math.cos(azimuth) * math.cos(elevation), math.sin(azimuth) * math.cos(elevation),
                                math.sin(elevation))) * size * 4
cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
floor = bpy.data.meshes.new('floor')
floor.from_pydata([(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [], [(0, 1, 2, 3)])
scene.collection.objects.link(bpy.data.objects.new('floor', floor))
for action in sorted(bpy.data.actions, key=lambda a: a.name):
    arm.animation_data.action = action
    if hasattr(arm.animation_data, 'action_slot') and len(action.slots):
        arm.animation_data.action_slot = action.slots[0]
    start, end = action.frame_range
    for i in range(count):
        scene.frame_set(int(round(start + (end - start) * i / max(1, count - 1))))
        scene.render.filepath = '%s_%s_%02d.png' % (out, action.name, i)
        bpy.ops.render.render(write_still=True)
print('SHEET_OK')
