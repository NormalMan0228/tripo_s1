import bpy, sys, os
w = bpy.data.objects["WrapHead"]
cols = {"M_FaceSkin": (0.8, 0.78, 0.76, 1), "M_LidInner": (0, 1, 0, 1), "M_MouthInside": (1, 0, 0, 1)}
for m in w.data.materials: m.diffuse_color = cols.get(m.name, (1, 1, 0, 1))
for o in bpy.data.objects:
    if o.name.startswith("Eye."):
        for m in o.data.materials: m.diffuse_color = (0.2, 0.3, 1, 1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--")+1]))
