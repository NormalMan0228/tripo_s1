"""Render a blend with material colours (Workbench) from a few close views. Usage: blender -b f.blend -P render_matcol.py -- out.png"""
import bpy, sys, math, os
from mathutils import Vector
OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = os.environ.get('COLOR_TYPE', 'MATERIAL')
sc.render.resolution_x = sc.render.resolution_y = 640
sc.view_settings.view_transform = 'Standard'
for o in bpy.data.objects:
    if o.type == 'CAMERA': bpy.data.objects.remove(o)
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
for k, (az, el, cz, osc) in enumerate([(0, 0, 0.5, 1.15), (0, 0, 0.53, 0.5), (35, 5, 0.52, 0.55), (0, 0, 0.62, 0.3), (0, 0, 0.43, 0.28)]):
    cd.ortho_scale = osc
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)), -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
    cam.location = Vector((0, 0, cz)) + d * 3; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = OUT.replace(".png", f"_v{k}.png"); bpy.ops.render.render(write_still=True)
