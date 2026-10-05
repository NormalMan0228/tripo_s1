"""Render original Tripo fragments with IDs for semantic grouping review."""
import bpy
import math
import json
from pathlib import Path
from mathutils import Vector, Matrix

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/character-parts-20261003'
out.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(root / 'artifacts/detail-map-20261003/tripo/character_detail/body-detailed-segment/model.glb'))
parts = {int(o.name.rsplit('_', 1)[1]): o for o in bpy.context.scene.objects if o.type == 'MESH'}
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 2100
scene.render.resolution_y = 1800
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.32, 0.36, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.8
scene.view_settings.view_transform = 'AgX'
target = Vector((0, 3.0, -2.45))
cam_data = bpy.data.cameras.new('Atlas_Camera')
cam = bpy.data.objects.new('Atlas_Camera', cam_data)
scene.collection.objects.link(cam)
cam.location = target + Vector((18, 0, 0))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 7.6
scene.camera = cam
for name, pos, energy, size in [
    ('Atlas_Key', (7, -2, 5), 2200, 12),
    ('Atlas_Fill', (6, 8, -5), 1500, 10),
]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = Vector(pos)
    obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()
label_mat = bpy.data.materials.new('Atlas_Label')
label_mat.diffuse_color = (0.8, 0.85, 0.95, 1)
label_mat.use_nodes = True
shader = label_mat.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = (0.8, 0.85, 0.95, 1)
shader.inputs['Emission Color'].default_value = (0.6, 0.65, 0.75, 1)
shader.inputs['Emission Strength'].default_value = 1
for obj in parts.values():
    obj.hide_render = True
for batch, indices in enumerate((list(range(30)), list(range(30, 54)))):
    copies = []
    for slot, index in enumerate(indices):
        source = parts[index]
        clone = source.copy()
        clone.data = source.data.copy()
        clone.hide_render = False
        scene.collection.objects.link(clone)
        pts = [source.matrix_world @ v.co for v in source.data.vertices]
        low = Vector(tuple(min(p[a] for p in pts) for a in range(3)))
        high = Vector(tuple(max(p[a] for p in pts) for a in range(3)))
        center = (low + high) * 0.5
        scale = 0.86 / max(high - low)
        cell = Vector((0, (slot % 6) * 1.2, -(slot // 6) * 1.2))
        clone.matrix_world = Matrix.Identity(4)
        for vertex, point in zip(clone.data.vertices, pts):
            vertex.co = (point - center) * scale + cell
        text_data = bpy.data.curves.new(f'ID_{index}', 'FONT')
        text_data.body = f'{index}  ({len(source.data.polygons)} tris)'
        text_data.size = 0.13
        text_data.align_x = 'CENTER'
        text = bpy.data.objects.new(f'ID_{index}', text_data)
        scene.collection.objects.link(text)
        text.location = cell + Vector((0.6, 0, -0.55))
        text.rotation_euler = cam.rotation_euler
        text_data.materials.append(label_mat)
        copies.extend([clone, text])
    scene.render.filepath = str(out / f'segment-contact-sheet-{batch + 1}.png')
    bpy.ops.render.render(write_still=True)
    for obj in copies:
        bpy.data.objects.remove(obj, do_unlink=True)
print('SEGMENT_ATLAS_READY', flush=True)
