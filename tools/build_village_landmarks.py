"""Author two developer-built village landmarks in Blender; never run for player assets."""
import bpy
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "art" / "source"
SOURCE.mkdir(parents=True, exist_ok=True)
random.seed(4102)


def srgb(value):
    value = int(value, 16) / 255
    return value / 12.92 if value < 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def material(name, color):
    rgb = tuple(srgb(color[i : i + 2]) for i in (0, 2, 4))
    item = bpy.data.materials.new(name)
    item.diffuse_color = (*rgb, 1)
    item.use_nodes = True
    surface = item.node_tree.nodes.get("Principled BSDF")
    surface.inputs["Base Color"].default_value = (*rgb, 1)
    surface.inputs["Roughness"].default_value = 0.83
    return item


COLORS = {
    "cream": "E8D5AE", "white": "F2E6CC", "timber": "806346",
    "oak": "AE8251", "teal": "6C9389", "teal_light": "8AACA0",
    "teal_dark": "527A76", "stone": "ADA68C", "slate": "656C70",
    "glass": "8FB7B5", "amber": "DBB96F", "leaf": "7C9C71",
    "soil": "6B5847", "rope": "CFB48B", "sea": "9BBBC1",
}


def box(name, location, size, mat, bevel=0.035, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(M[mat])
    if bevel:
        mod = obj.modifiers.new("Hand-finished edge", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod = obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def cyl(name, location, radius, depth, mat, vertices=12, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(M[mat])
    return obj


def make(kind):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    global M
    M = {key: material(kind + "_" + key, value) for key, value in COLORS.items()}
    fishing = kind == "fishing_shack"
    width = 3.7 if fishing else 4.3
    depth = 3.4 if fishing else 3.7
    wall = "teal_light" if fishing else "cream"
    box("Cut stone foundation", (0, 0, 0.16), (width + 0.25, depth + 0.25, 0.32), "stone", 0.08)
    box("Storybook walls", (0, 0, 1.42), (width, depth, 2.45), wall, 0.07)
    for x in (-width / 2 + 0.08, width / 2 - 0.08):
        for y in (-depth / 2, depth / 2):
            box("Corner oak post", (x, y, 1.42), (0.17, 0.18, 2.55), "timber")
    for z in (0.35, 2.68):
        box("Facade beam", (0, -depth / 2 - 0.05, z), (width + 0.22, 0.15, 0.15), "timber")
    # A low-pitched tiled roof leaves the facade readable from the game camera.
    angle = math.atan2(1.12, width / 2 + 0.25)
    roof_length = math.hypot(width / 2 + 0.38, 1.12)
    for side in (-1, 1):
        box("Roof deck", (side * (width / 4 + 0.07), 0, 3.23), (roof_length, depth + 0.75, 0.12), "teal_dark", rotation=(0, side * angle, 0))
        for course in range(7):
            x = side * (0.16 + course * (width / 2 + 0.22) / 6)
            z = 3.78 - abs(x) * 1.12 / (width / 2 + 0.25)
            for along in range(9):
                y = -depth / 2 - 0.28 + along * (depth + 0.57) / 8
                box("Rounded roof tile", (x, y, z), (0.48, 0.51, 0.08),
                    ("teal", "teal_light", "teal", "teal_dark")[(course + along) % 4], 0.035,
                    (0, side * angle, 0))
    for along in range(11):
        y = -depth / 2 - 0.28 + along * (depth + 0.57) / 10
        cyl("Ridge ceramic", (0, y, 3.83), 0.095, 0.44, "teal_dark", rotation=(math.pi / 2, 0, 0))
    # Dark recess and individual planks make the door legible at gameplay scale.
    box("Door recess", (0, -depth / 2 - 0.06, 1.18), (1.13, 0.11, 1.82), "soil")
    for i in range(7):
        box("Door plank", ((i - 3) * 0.148, -depth / 2 - 0.15, 1.17), (0.142, 0.08, 1.72), "oak" if i % 3 else "timber", 0.01)
    cyl("Brass handle", (0.34, -depth / 2 - 0.22, 1.15), 0.055, 0.04, "amber", 12, (math.pi / 2, 0, 0))
    for x in (-width / 2 + 0.63, width / 2 - 0.63):
        box("Window frame", (x, -depth / 2 - 0.10, 1.67), (0.70, 0.12, 0.82), "timber")
        box("Sea-glass pane", (x, -depth / 2 - 0.18, 1.67), (0.55, 0.045, 0.65), "glass")
        box("Window cross", (x, -depth / 2 - 0.22, 1.67), (0.06, 0.05, 0.73), "white")
        box("Window sill", (x, -depth / 2 - 0.23, 1.23), (0.85, 0.27, 0.10), "oak")
    if fishing:
        for i in range(9):
            z = 0.57 + i * 0.25
            for x in (-width / 2 - 0.03, width / 2 + 0.03):
                box("Painted horizontal siding", (x, 0, z), (0.06, depth + 0.04, 0.065), "teal" if i % 3 else "teal_dark", 0.013)
        box("Weathered porch", (0, -depth / 2 - 0.75, 0.23), (width + 0.25, 1.70, 0.18), "oak", 0.045)
        for i in range(9):
            box("Porch board", (-width / 2 + 0.25 + i * width / 8, -depth / 2 - 0.75, 0.34),
                (width / 9 - 0.04, 1.58, 0.06), "timber" if i % 4 == 0 else "oak", 0.01)
        for x in (-width / 2 + 0.15, width / 2 - 0.15):
            cyl("Pier bollard", (x, -depth / 2 - 1.27, 0.67), 0.10, 0.8, "timber")
        cyl("Coiled rope", (1.25, -depth / 2 - 0.8, 0.49), 0.35, 0.08, "rope", 16)
        for i in range(4):
            box("Net float", (-1.35 + i * 0.18, -depth / 2 - 0.54, 0.43), (0.12, 0.12, 0.12), "amber" if i % 2 else "sea", 0.05)
    else:
        # Curved green canvas, seed trays and hanging signs establish the shop.
        box("Canvas awning", (0, -depth / 2 - 0.83, 2.55), (width + 0.32, 1.64, 0.12), "teal", 0.06, (0.08, 0, 0))
        for i in range(10):
            x = -width / 2 + 0.18 + i * width / 9
            box("Awning scallop", (x, -depth / 2 - 1.57, 2.43), (width / 10 - 0.015, 0.1, 0.25), "white" if i % 2 else "teal_light", 0.05)
        for x in (-width / 2 + 0.2, width / 2 - 0.2):
            box("Awning support", (x, -depth / 2 - 1.13, 1.48), (0.10, 0.10, 2.18), "timber")
        for x in (-1.4, -0.92, 0.92, 1.4):
            box("Seed display box", (x, -depth / 2 - 0.75, 0.75), (0.4, 0.62, 0.4), "oak", 0.025)
            cyl("Potted seedling", (x, -depth / 2 - 0.75, 1.06), 0.16, 0.18, "leaf", 8)
        box("Hanging shop sign", (0, -depth / 2 - 1.65, 2.02), (1.12, 0.08, 0.43), "oak", 0.07)
        for x in (-0.38, 0.38):
            cyl("Sign chain", (x, -depth / 2 - 1.65, 2.31), 0.018, 0.28, "rope")
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / f"{kind}.blend"))
    # Keep the editable blend; combine equal-material meshes for a lighter import.
    for item in list(M.values()):
        group = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.data.materials and o.data.materials[0] == item]
        if len(group) < 2:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        for obj in group:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = group[0]
        bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "game" / "assets" / f"{kind}.glb"), export_format="GLB", export_apply=True)
    print("EXPORTED", kind)


if __name__ == "__main__":
    make("seed_shop")
    make("fishing_shack")
