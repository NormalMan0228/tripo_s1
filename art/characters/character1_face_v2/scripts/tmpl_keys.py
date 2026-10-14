import bpy
b = bpy.data.objects["Template_Face_Body"]
print("KEYS", [k.name for k in b.data.shape_keys.key_blocks][70:])
print("PARENT", b.parent.name if b.parent else None, [m.object.name for m in b.modifiers if m.type=='ARMATURE' and m.object])
