"""Blender check for a generated full-body model (Tripo P2 GLB/FBX).

Run headless:
  blender -b -P tools/body_gen/inspect_body.py -- <model.glb> <out_dir>

Writes into out_dir:
  stats.json   vertex/face/quad counts, loose islands, open and non-manifold edges, size
  view_*.png   grey studio renders (front, right, back, three-quarter) with wire overlay
  mask_front.png / mask_side.png   flat white silhouettes for the gap check (gap_check.py)
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = os.path.abspath(argv[0]), os.path.abspath(argv[1])
os.makedirs(out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
if src.lower().endswith(".fbx"):
    bpy.ops.import_scene.fbx(filepath=src)
else:
    bpy.ops.import_scene.gltf(filepath=src)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for o in bpy.context.scene.objects:
    o.select_set(o in meshes)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
body = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.context.scene.objects):
    if o is not body:
        bpy.data.objects.remove(o, do_unlink=True)

# Feet on the floor, centred, 1.0 = model height.
co = [v.co for v in body.data.vertices]
lo = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
hi = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
size = hi - lo
body.location = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
bpy.ops.object.transform_apply(location=True)

bm = bmesh.new()
bm.from_mesh(body.data)
bm.edges.ensure_lookup_table()
faces = len(bm.faces)
quads = sum(1 for f in bm.faces if len(f.verts) == 4)
tris = sum(1 for f in bm.faces if len(f.verts) == 3)
boundary = sum(1 for e in bm.edges if e.is_boundary)
nonmanifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
# Loose islands by flood fill over edges.
seen, islands, sizes = set(), 0, []
for v in bm.verts:
    if v.index in seen:
        continue
    islands += 1
    stack, n = [v], 0
    seen.add(v.index)
    while stack:
        cur = stack.pop()
        n += 1
        for e in cur.link_edges:
            w = e.other_vert(cur)
            if w.index not in seen:
                seen.add(w.index)
                stack.append(w)
    sizes.append(n)
bm.free()
sizes.sort(reverse=True)
stats = {
    "source": os.path.basename(src),
    "vertices": len(body.data.vertices), "faces": faces, "quads": quads, "triangles": tris,
    "ngons": faces - quads - tris, "game_triangles": quads * 2 + tris,
    "islands": islands, "island_sizes_top": sizes[:6], "small_islands_under_50v": sum(1 for s in sizes if s < 50),
    "open_edges": boundary, "nonmanifold_edges": nonmanifold,
    "size_xyz": [round(size.x, 4), round(size.y, 4), round(size.z, 4)],
}

# Scene: ortho camera, workbench studio light, grey body + dark wire copy.
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
shading = scene.display.shading
shading.light = "STUDIO"
shading.color_type = "OBJECT"
shading.show_cavity = True
shading.cavity_type = "WORLD"
scene.world = bpy.data.worlds.new("w") if scene.world is None else scene.world
scene.world.color = (0.93, 0.92, 0.9)
body.color = (0.78, 0.78, 0.8, 1)

wire = body.copy()
wire.data = body.data.copy()
scene.collection.objects.link(wire)
mod = wire.modifiers.new("w", "WIREFRAME")
mod.thickness = 0.0012 * size.z
mod.use_even_offset = False  # even offset throws spikes off degenerate faces
mod.use_replace = True
wire.color = (0.42, 0.44, 0.5, 1)

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max(size.z, size.x, size.y) * 1.08
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
centre = Vector((0, 0, size.z / 2))


def shoot(name, yaw_deg, path):
    yaw = math.radians(yaw_deg)
    d = 4 * size.z
    # yaw 0 = front: camera on -Y looking +Y.
    cam.location = centre + Vector((d * math.sin(yaw), -d * math.cos(yaw), 0))
    cam.rotation_euler = (math.radians(90), 0, yaw)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


for name, yaw in (("front", 0), ("right", 90), ("back", 180), ("three_quarter", 35)):
    shoot(name, yaw, os.path.join(out, f"view_{name}.png"))

# Flat silhouettes for the gap check.
wire.hide_render = True
shading.light = "FLAT"
shading.show_cavity = False
scene.world.color = (0, 0, 0)
body.color = (1, 1, 1, 1)
scene.render.resolution_x = scene.render.resolution_y = 1200
shoot("mask", 0, os.path.join(out, "mask_front.png"))
shoot("mask", 90, os.path.join(out, "mask_side.png"))
stats["ortho_scale_m"] = cam_data.ortho_scale
stats["mask_px"] = 1200

with open(os.path.join(out, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=1)
print("STATS", json.dumps(stats))
