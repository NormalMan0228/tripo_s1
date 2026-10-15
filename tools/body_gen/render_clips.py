"""Render a few frames of every clip in a game monster GLB, and measure ground contact.

  blender -b --factory-startup -P tools/body_gen/render_clips.py -- model.glb outdir [frames_per_clip] [view] [size]

frames_per_clip < 0 renders the whole clip at that many frames per second (e.g. -10 for a GIF).

Writes outdir/<clip>_<i>.png (Workbench, base colour texture, on a ground plane) and
outdir/clips.json: for every rendered frame, the lowest point of the deformed mesh in metres
(negative = sinks into the ground, positive = floats). view: 3q (default) | front | side.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
per = int(a[2]) if len(a) > 2 else 6
view = a[3] if len(a) > 3 else '3q'
size = int(a[4]) if len(a) > 4 else 420
os.makedirs(out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
scene = bpy.context.scene
arm = next(o for o in scene.objects if o.type == 'ARMATURE')
meshes = [o for o in scene.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')]
fps = scene.render.fps / scene.render.fps_base


def lowest_and_box():
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for m in meshes:
        ev = m.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
        ev.to_mesh_clear()
    return lo, hi


# Workbench shows a material's active image node: make it the base colour (not the emission map)
for m in meshes:
    for slot in m.material_slots:
        mt = slot.material
        if mt and mt.use_nodes:
            bsdf = next((n for n in mt.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bsdf and bsdf.inputs['Base Color'].links:
                node = bsdf.inputs['Base Color'].links[0].from_node
                while node.type != 'TEX_IMAGE' and node.inputs and node.inputs[0].links:
                    node = node.inputs[0].links[0].from_node
                if node.type == 'TEX_IMAGE':
                    mt.node_tree.nodes.active = node
if arm.animation_data is None:
    arm.animation_data_create()
for t in list(arm.animation_data.nla_tracks):
    arm.animation_data.nla_tracks.remove(t)
acts = [x for x in bpy.data.actions]
arm.animation_data.action = None
scene.frame_set(0)
rest_lo, rest_hi = lowest_and_box()
H = rest_hi.z - rest_lo.z

bpy.ops.mesh.primitive_plane_add(size=H * 6, location=(0, 0, 0))
plane = bpy.context.object
mat = bpy.data.materials.new('ground')
mat.diffuse_color = (0.72, 0.70, 0.66, 1)
plane.data.materials.append(mat)

dirs = {'3q': (0.75, -1.0, 0.35), 'front': (0, -1, 0.12), 'side': (1, 0, 0.12)}
d = Vector(dirs[view]).normalized()
cam_data = bpy.data.cameras.new('cam')
cam_data.type = 'ORTHO'
cam_data.ortho_scale = 1.6 * H
cam = bpy.data.objects.new('cam', cam_data)
scene.collection.objects.link(cam)
target = Vector((0, 0, 0.42 * H))
cam.location = target + d * 4 * H
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam_data.clip_end = 20 * H
scene.camera = cam
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = False
sh.show_cavity = False
scene.render.resolution_x = scene.render.resolution_y = size
world = bpy.data.worlds.new('w')
world.color = (0.86, 0.87, 0.89)
scene.world = world
sh.background_type = 'WORLD'

report = {'height': round(H, 3), 'rest_lowest': round(rest_lo.z, 4), 'clips': {}}
for act in acts:
    arm.animation_data.action = act
    if hasattr(arm.animation_data, 'action_slot') and arm.animation_data.action_slot is None and len(act.slots):
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = act.frame_range
    last = int(f1)  # glTF imports can give a fractional end frame; never step past it
    if per > 0:
        frames = [min(last, round(f0 + (f1 - f0) * i / (per - 1))) for i in range(per)]
    else:
        step = fps / -per
        frames = [min(last, round(f0 + i * step)) for i in range(int((f1 - f0) / step) + 1)]
    rows = []
    # ground contact over every frame (not only the rendered ones)
    low_all = []
    for f in range(int(f0), int(f1) + 1):
        scene.frame_set(f)
        lo, hi = lowest_and_box()
        low_all.append(lo.z)
    for i, f in enumerate(frames):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out, '%s_%d.png' % (act.name, i))
        bpy.ops.render.render(write_still=True)
        rows.append({'frame': f, 'seconds': round((f - f0) / fps, 3), 'lowest_m': round(low_all[f - int(f0)], 4)})
    report['clips'][act.name] = {'frames': rows, 'lowest_min_m': round(min(low_all), 4),
                                 'lowest_max_m': round(max(low_all), 4), 'seconds': round((f1 - f0) / fps, 3)}
json.dump(report, open(os.path.join(out, 'clips.json'), 'w'), indent=1)
print('CLIPS', json.dumps({k: (v['lowest_min_m'], v['lowest_max_m'], v['seconds']) for k, v in report['clips'].items()}))
