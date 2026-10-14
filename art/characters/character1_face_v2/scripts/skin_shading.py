"""Skin shading: lower specular / higher roughness, subtle subsurface (reduces mirror-like grazing highlights)."""
import bpy, sys, os
for mn in ("M_FaceSkin", "M_LidInner"):
    m = bpy.data.materials.get(mn)
    if not m: continue
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.68
    if b.inputs.get("Specular IOR Level"): b.inputs["Specular IOR Level"].default_value = 0.25
    if b.inputs.get("Subsurface Weight"): b.inputs["Subsurface Weight"].default_value = 0.08
    if b.inputs.get("Subsurface Radius"): b.inputs["Subsurface Radius"].default_value = (0.004, 0.0015, 0.001)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--")+1]))
