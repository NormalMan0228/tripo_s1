import bpy, sys, os
m = bpy.data.materials["M_LidInner"]; b = m.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0, 1, 0, 1); b.inputs["Roughness"].default_value = 1.0
fs = bpy.data.materials["M_FaceSkin"]; fb = fs.node_tree.nodes["Principled BSDF"]
for l in list(fb.inputs["Normal"].links): fs.node_tree.links.remove(l)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--")+1]))
