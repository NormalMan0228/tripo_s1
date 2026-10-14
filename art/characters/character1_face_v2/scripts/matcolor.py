"""Viewport/workbench colours per material for clay part review."""
import bpy, sys, os
cols = {"M_FaceSkin": (0.8, 0.78, 0.76, 1), "M_LidInner": (0.65, 0.5, 0.48, 1), "M_MouthInside": (0.5, 0.2, 0.2, 1), "M_LashFlap": (0.05, 0.04, 0.04, 1)}
for m in bpy.data.materials:
    m.diffuse_color = cols.get(m.name, m.diffuse_color)
pc = {"TeethUpper": (1, 1, 0.85, 1), "TeethLower": (1, 1, 0.85, 1), "Tongue": (0.85, 0.35, 0.4, 1), "MouthLower": (0.7, 0.4, 0.45, 1)}
for o in bpy.data.objects:
    if o.name in pc:
        m = bpy.data.materials.new("C_" + o.name); m.diffuse_color = pc[o.name]; o.data.materials.clear(); o.data.materials.append(m)
    if o.name.startswith("Eye.") and not o.material_slots:
        m = bpy.data.materials.new("C_Eye"); o.data.materials.append(m)
for o in bpy.data.objects:
    if o.name.startswith("Eye."):
        for s in o.material_slots:
            if s.material: s.material.diffuse_color = (0.95, 0.95, 0.95, 1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--")+1]))
