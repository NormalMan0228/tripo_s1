"""Export the head (Body + eyes/teeth/tongue/gum) as one GLB in Tripo's native orientation (face toward +X in Blender).
Usage: blender --background <head.blend> --python export_seg_glb.py -- <out.glb>"""
import bpy, sys, os, math
from mathutils import Matrix
OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
KEEP = {"Body", "Eye.L", "Eye.R", "TeethUpper", "TeethLower", "Tongue", "MouthLower"}
for o in list(bpy.data.objects):
    if o.type != 'MESH' or o.name not in KEEP: bpy.data.objects.remove(o)
R = Matrix.Rotation(math.radians(90), 4, 'Z')
for o in bpy.data.objects:
    o.data.transform(R @ o.matrix_basis); o.matrix_basis = Matrix()
    if o.data.shape_keys: o.shape_key_clear()
    o.vertex_groups.clear(); o.data.materials.clear()
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_materials='NONE', export_yup=True, use_selection=False)
print("EXPORTED", OUT, [o.name for o in bpy.data.objects], sum(len(o.data.polygons) for o in bpy.data.objects))
