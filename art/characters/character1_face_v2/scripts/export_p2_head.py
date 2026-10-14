import bpy, os, sys
out = os.path.abspath(sys.argv[sys.argv.index("--")+1])
for o in bpy.data.objects: o.select_set(False)
o = next(o for o in bpy.data.collections["p2_mv_tex"].objects if o.type == 'MESH')
o.select_set(True); bpy.context.view_layer.objects.active = o
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_apply=True)
print("EXPORTED", os.path.getsize(out))
