"""Import and render one actual Tripo part without editing or assembling meshes.

Run with Blender --background --python this-file -- --part head (or another id).
Raw GLB transforms, topology and materials are preserved. Studio cameras/lights
are review aids only; the generated GLB remains the immutable API output.
"""
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "art/characters/explorer_b_modular_v1/03_generated"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--part", required=True,
                    choices=["head", "body", "hand", "hair", "jacket", "shirt", "pants", "boots", "belt", "fullbody"])
parser.add_argument("--folder", type=Path, help="Alternative developer review folder containing model.glb.")
parser.add_argument("--views", nargs="+", choices=["front", "angle", "side", "back", "clay", "top", "bottom", "inside"],
                    default=["front", "angle", "side", "back", "clay"])
parser.add_argument("--inspection-only", action="store_true")
parser.add_argument("--force", action="store_true", help="Re-render camera previews only; do not change mesh geometry.")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
folder = args.folder.resolve() if args.folder else OUT / args.part
if not folder.resolve().is_relative_to(ROOT.resolve()):
    raise RuntimeError("review_folder_outside_project")

bpy.ops.wm.read_factory_settings(use_empty=True)
source=next((folder/('model.'+ext) for ext in ('fbx','glb') if (folder/('model.'+ext)).exists()),None)
if source is None:
    raise RuntimeError('native_mesh_missing')
if source.suffix=='.fbx':
    bpy.ops.import_scene.fbx(filepath=str(source),use_anim=False)
else:
    bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise RuntimeError("empty_generated_mesh")
corners = [o.matrix_world @ Vector(v) for o in meshes for v in o.bound_box]
minimum = Vector([min(v[i] for v in corners) for i in range(3)])
maximum = Vector([max(v[i] for v in corners) for i in range(3)])
center = (minimum + maximum) / 2
size = maximum - minimum
radius = max(size)
if radius <= 0 or not all(math.isfinite(x) for x in (*minimum, *maximum)):
    raise RuntimeError("invalid_generated_bounds")

report = {"part": args.part, "source_mesh": source.relative_to(ROOT).as_posix(),
          "vertices": 0, "polygons": 0, "triangles": 0, "uv_layers": [], "mesh_objects": [],
          "bounds": {"min": list(minimum), "max": list(maximum), "size": list(size)},
          "materials": [], "textures": [], "rigged": False,
          "geometry_edited": False, "assembly_or_fit_verified": False,
          "raw_connectivity_includes_uv_and_normal_seams": True}
for o in meshes:
    mesh = o.data
    mesh.calc_loop_triangles()
    parent = list(range(len(mesh.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for edge in mesh.edges:
        a, b = map(find, edge.vertices)
        parent[a] = b
    connected = Counter(find(i) for i in range(len(parent)))
    edge_use = Counter(tuple(sorted(pair)) for poly in mesh.polygons for pair in poly.edge_keys)
    # glTF splits coincident vertices at UV/normal seams. Inspect equivalent
    # positions in a separate graph; never weld or mutate the original mesh.
    epsilon = max(max(o.dimensions), 1e-6) * 1e-6
    positions = {}
    mapping = []
    for vertex in mesh.vertices:
        key = tuple(round(c / epsilon) for c in vertex.co)
        mapping.append(positions.setdefault(key, len(positions)))
    equivalent_parent = list(range(len(positions)))

    def equivalent_find(i):
        while equivalent_parent[i] != i:
            equivalent_parent[i] = equivalent_parent[equivalent_parent[i]]
            i = equivalent_parent[i]
        return i

    for edge in mesh.edges:
        a, b = (equivalent_find(mapping[i]) for i in edge.vertices)
        equivalent_parent[a] = b
    equivalent_components = Counter(equivalent_find(i) for i in range(len(positions)))
    equivalent_edges = Counter(tuple(sorted((mapping[a], mapping[b])))
                               for poly in mesh.polygons for a, b in poly.edge_keys
                               if mapping[a] != mapping[b])
    report["mesh_objects"].append({"name": o.name, "vertices": len(mesh.vertices),
                                    "polygons": len(mesh.polygons), "triangles": len(mesh.loop_triangles),
                                    "polygon_sides": dict(Counter(len(p.vertices) for p in mesh.polygons)),
                                    "connected_components": len(connected),
                                    "largest_component_vertices": sorted(connected.values(), reverse=True)[:12],
                                    "boundary_edges": sum(n == 1 for n in edge_use.values()),
                                    "nonmanifold_edges": sum(n > 2 for n in edge_use.values()),
                                    "position_equivalence_epsilon": epsilon,
                                    "position_equivalent_vertices": len(positions),
                                    "position_equivalent_components": len(equivalent_components),
                                    "position_equivalent_largest_components": sorted(equivalent_components.values(), reverse=True)[:12],
                                    "position_equivalent_boundary_edges": sum(n == 1 for n in equivalent_edges.values()),
                                    "position_equivalent_nonmanifold_edges": sum(n > 2 for n in equivalent_edges.values())})
    report["vertices"] += len(mesh.vertices)
    report["polygons"] += len(mesh.polygons)
    report["triangles"] += len(mesh.loop_triangles)
    report["uv_layers"].extend(layer.name for layer in mesh.uv_layers)
    report["rigged"] |= bool(o.find_armature())
for material in bpy.data.materials:
    textures = []
    if material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                textures.append(node.image.name)
    report["materials"].append({"name": material.name, "textures": textures})
for image in bpy.data.images:
    if image.type == "IMAGE" and image.size[0]:
        report["textures"].append({"name": image.name, "size": list(image.size)})
report["has_uvs"] = bool(report["uv_layers"])
(folder / "mesh-inspection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
if args.inspection_only:
    print("PART_INSPECTED", args.part, report["vertices"], report["triangles"], flush=True)
    sys.exit(0)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 24
scene.cycles.use_denoising = True
try:
    preferences = bpy.context.preferences.addons["cycles"].preferences
    preferences.compute_device_type = "CUDA"
    preferences.get_devices()
    for device in preferences.devices:
        device.use = device.type == "CUDA"
    if any(d.type == "CUDA" for d in preferences.devices):
        scene.cycles.device = "GPU"
except Exception:
    scene.cycles.device = "CPU"
scene.render.resolution_x = 900
scene.render.resolution_y = 1100 if args.part in ("body", "fullbody") else 900
if args.part == "belt":
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 650
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("Review Studio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.88, 0.92, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.45
scene.world = world
for name, offset, power, light_size in [
    ("Key", (2.5, -3, 4), 700, 2.5),
    ("Fill", (1.5, 3, 1.8), 380, 3),
    ("Rim", (-2.5, 1, 3), 600, 2),
    ("Cavity Fill", (0.5, 0, -3), 220, 2.5),
]:
    light = bpy.data.lights.new(name, "AREA")
    light.energy = power * radius * radius
    light.shape = "DISK"
    light.size = light_size * radius
    o = bpy.data.objects.new(name, light)
    scene.collection.objects.link(o)
    o.location = center + Vector(offset) * radius
    o.rotation_euler = (center - o.location).to_track_quat("-Z", "Y").to_euler()
    o.hide_select = True
camera = bpy.data.objects.new("Review Camera", bpy.data.cameras.new("Review Camera"))
scene.collection.objects.link(camera)
scene.camera = camera
camera.data.type = "ORTHO"
camera.data.clip_start = radius / 1000
camera.data.clip_end = radius * 100
camera.hide_select = True
views = {"front": (4, 0, 0), "angle": (4, -2.2, 0.65),
         "side": (0, -4, 0), "back": (-4, 0, 0), "clay": (4, -2.2, 0.65),
         "top": (0.001, 0, 4), "bottom": (0.001, 0, -4), "inside": (2.4, -1, -2.8)}


def frame(view):
    camera.location = center + Vector(views[view]) * radius
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    basis = camera.rotation_euler.to_matrix().transposed()
    projected = [basis @ (v - center) for v in corners]
    width = max(p.x for p in projected) - min(p.x for p in projected)
    height = max(p.y for p in projected) - min(p.y for p in projected)
    # Blender's AUTO sensor fit uses a different dimension for wide canvases.
    # Fit against the actual camera frame so belt ends never get cropped.
    camera.data.ortho_scale = radius
    frame_points = camera.data.view_frame(scene=scene)
    frame_width = max(p.x for p in frame_points) - min(p.x for p in frame_points)
    frame_height = max(p.y for p in frame_points) - min(p.y for p in frame_points)
    camera.data.ortho_scale *= max(width / frame_width, height / frame_height) * 1.18


# Save an editable, mesh-selected review scene before applying render-only clay.
frame("angle")
for o in bpy.context.selected_objects:
    o.select_set(False)
for o in meshes:
    o.hide_select = False
    o.hide_viewport = False
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.shading.type = "MATERIAL"
            area.spaces.active.region_3d.view_location = center
            area.spaces.active.region_3d.view_distance = radius * 2
            area.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
bpy.ops.file.pack_all()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(folder / "review.blend"))
clay = bpy.data.materials.new("Review Clay")
clay.diffuse_color = (0.48, 0.5, 0.53, 1)
clay.use_nodes = True
bsdf = clay.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = clay.diffuse_color
bsdf.inputs["Roughness"].default_value = 0.65
original_materials = {o.name: list(o.data.materials) for o in meshes}
for view in args.views:
    path = folder / ("preview-" + view + ".png")
    if path.exists() and not args.force:
        continue
    if view == "clay":
        for o in meshes:
            o.data.materials.clear()
            o.data.materials.append(clay)
    frame(view)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("PART_RENDERED", args.part, view, flush=True)
print("PART_REVIEW_COMPLETE", args.part, report["vertices"], report["triangles"], flush=True)
