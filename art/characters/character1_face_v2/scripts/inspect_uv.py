import bpy
w = bpy.data.objects["WrapHead"]; b = bpy.data.objects["Body"]
print("WRAP uv", [u.name for u in w.data.uv_layers], "mats", [m.name if m else None for m in w.data.materials])
print("BODY uv", [u.name for u in b.data.uv_layers], "mats", [m.name for m in b.data.materials])
for m in b.data.materials:
    for nd in m.node_tree.nodes:
        if nd.type == 'TEX_IMAGE': print("  img", nd.image.name, tuple(nd.image.size), nd.image.packed_file is not None)
