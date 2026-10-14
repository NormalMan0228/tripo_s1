"""Side-by-side review of segmentation results transferred onto our quad heads. Usage: blender -b --python make_segref_review.py -- out.blend job..."""
import bpy, sys, os
a = sys.argv[sys.argv.index("--") + 1:]; OUT = os.path.abspath(a[0]); HERE = os.path.dirname(OUT)
bpy.ops.wm.read_factory_settings(use_empty=True)
for k, job in enumerate(a[1:]):
    with bpy.data.libraries.load(os.path.join(HERE, "seg", "transfer", f"{job}.blend"), link=False) as (df, dt):
        dt.objects = [n for n in df.objects]
    col = bpy.data.collections.new(job); bpy.context.scene.collection.children.link(col)
    for o in dt.objects:
        if o is None or o.type != 'MESH': continue
        col.objects.link(o); o.location.x += k * 0.9
        o.name = f"{job}:{o.name}"
for area in []: pass
bpy.context.scene.display.shading.color_type = 'MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("REVIEW", OUT)
