import bpy
for n in ("Template_Face_Body.teeth_base", "Template_Face_Body.tongue01", "Template_Face_Body.eyebrow001", "Template_Face_Body.eyelashes01"):
    o = bpy.data.objects[n]
    print("OBJ", n, len(o.data.vertices), [k.name for k in o.data.shape_keys.key_blocks][:40] if o.data.shape_keys else None, [m.name for m in o.data.materials], o.parent.name if o.parent else None, [md.type for md in o.modifiers])
