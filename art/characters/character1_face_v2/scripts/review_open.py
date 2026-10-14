import bpy, sys, os
from mathutils import Vector, Quaternion
cols = {"Body": (0.8, 0.78, 0.76, 1), "Eye.L": (0.3, 0.6, 1, 1), "Eye.R": (0.3, 0.6, 1, 1), "TeethUpper": (1, 1, 0.6, 1), "TeethLower": (1, 0.8, 0.3, 1), "Tongue": (0.9, 0.3, 0.35, 1)}
for o in bpy.data.objects:
    if o.type == 'MESH': o.color = cols.get(o.name, (0.5, 1, 0.5, 1))
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            sp = area.spaces.active; sp.shading.type = 'SOLID'; sp.shading.color_type = 'OBJECT'
            r3 = sp.region_3d; r3.view_perspective = 'PERSP'
            r3.view_location = Vector((0.0, -0.15, 0.52)); r3.view_rotation = Quaternion((0.82, 0.57, 0.0, 0.0)) @ Quaternion((0.985, 0.0, 0.0, 0.17)); r3.view_distance = 1.5
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--")+1]))
