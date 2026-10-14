"""Review copy: solid view with part colours, face framed, no animation clutter."""
import bpy, sys, os
from mathutils import Vector, Quaternion
out = os.path.abspath(sys.argv[sys.argv.index("--")+1])
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name not in ("WrapHead", "Eye.L", "Eye.R", "Teeth", "Tongue", "Brow.L", "Brow.R"):
        o.hide_set(True); o.hide_render = True
    if o.type == 'MESH' and o.data.shape_keys:
        for kb in o.data.shape_keys.key_blocks[1:]: kb.value = 0
cols = {"Eye.L": (1, 1, 1, 1), "Eye.R": (1, 1, 1, 1), "Teeth": (1, 1, 0.85, 1), "Tongue": (0.9, 0.3, 0.35, 1), "Brow.L": (0.25, 0.15, 0.1, 1), "Brow.R": (0.25, 0.15, 0.1, 1)}
for n, c in cols.items():
    o = bpy.data.objects.get(n)
    if o:
        ca = o.data.color_attributes.get("part_id") or o.data.color_attributes.new("part_id", 'FLOAT_COLOR', 'CORNER')
        for i in range(len(ca.data)): ca.data[i].color = c
        o.data.color_attributes.active_color = ca
w = bpy.data.objects["WrapHead"]
w.data.color_attributes.active_color = w.data.color_attributes["part_id"]
bpy.context.view_layer.objects.active = w
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            sp = area.spaces.active
            sp.shading.type = 'SOLID'; sp.shading.color_type = 'VERTEX'; sp.shading.light = 'STUDIO'
            sp.overlay.show_bones = False
            r3 = sp.region_3d
            r3.view_perspective = 'PERSP'
            r3.view_location = Vector((0.0, -0.15, 0.56))
            r3.view_rotation = Quaternion((0.82, 0.57, 0.0, 0.0)) @ Quaternion((0.985, 0.0, 0.0, 0.17))
            r3.view_distance = 1.4
bpy.context.scene.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("REVIEW", out)
