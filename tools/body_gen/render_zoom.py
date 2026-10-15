"""Close-up render of one spot of a mesh (to show a fix before/after).

  blender -b -P tools/body_gen/render_zoom.py -- model.fbx out.png cx cy cz size view [culling]

cx, cy, cz: target point as fractions of the model height from the bounding-box minimum
(same coordinates as the QA notes); size: view width as a fraction of the height;
view: front | back | left | right | under | 3q. culling=1 turns on backface culling so
holes show as see-through.
"""
import math
import sys

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
src, out = a[0], a[1]
cx, cy, cz, size = (float(x) for x in a[2:6])
view = a[6]
cull = len(a) > 7 and a[7] == "1"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
H = max(hi - lo)
target = lo + Vector((cx, cy, cz)) * H

dirs = {"front": (0, -1, 0), "back": (0, 1, 0), "left": (-1, 0, 0), "right": (1, 0, 0),
        "under": (0, -0.4, -1), "3q": (0.7, -0.7, 0.25)}
d = Vector(dirs[view]).normalized()
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size * H
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = target + d * 3 * H
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam_data.clip_end = 10 * H
scene = bpy.context.scene
scene.camera = cam
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (0.75, 0.75, 0.75)
scene.display.shading.show_cavity = True
scene.display.shading.show_backface_culling = cull
scene.render.resolution_x = scene.render.resolution_y = 700
scene.render.film_transparent = False
world = bpy.data.worlds.new("w")
world.color = (0.12, 0.12, 0.14)
scene.world = world
scene.display.shading.background_type = "WORLD"
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("ZOOM", out)
