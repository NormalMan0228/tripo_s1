import bpy, sys, os
fs = bpy.data.materials["M_FaceSkin"]; fb = fs.node_tree.nodes["Principled BSDF"]
for l in list(fb.inputs["Normal"].links): fs.node_tree.links.remove(l)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--")+1]))
