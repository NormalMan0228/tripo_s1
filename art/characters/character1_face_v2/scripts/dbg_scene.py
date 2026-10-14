import bpy
for o in bpy.data.objects:
    print("OBJ", o.name, o.type, o.hide_render, [round(d,3) for d in o.dimensions], [round(x,3) for x in o.location], len(o.data.vertices) if o.type=='MESH' else '')
