import bpy, sys, os
from mathutils import Vector
pre = os.path.abspath(sys.argv[sys.argv.index("--")+1])
sc = bpy.context.scene
cols = {"Body": (0.8, 0.78, 0.76), "Eye.L": (0.3, 0.6, 1), "Eye.R": (0.3, 0.6, 1), "TeethUpper": (1, 1, 0.6), "TeethLower": (1, 0.8, 0.3), "Tongue": (0.9, 0.3, 0.35), "MouthLower": (0.6, 0.35, 0.6)}
for o in sc.objects:
    if o.type == 'MESH': o.color = (*cols.get(o.name, (0.5, 1, 0.5)), 1)
hide = set(os.environ.get("HIDE", "").split(","))
for o in sc.objects:
    if o.type == 'MESH': o.hide_render = o.name in hide
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 600
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'OBJECT'
if os.environ.get('WIRE'):
    for o in sc.objects:
        if o.type == 'MESH':
            m = o.modifiers.new('wf', 'WIREFRAME'); m.thickness = 0.0003; m.use_replace = False; m.use_even_offset = False
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
VIEWS_ALL = {"front": ((0, -0.2, 0.55), (0, -1, 0), 0.75), "q34": ((0, -0.1, 0.55), (0.7, -0.7, 0.05), 0.85), "mouth": ((0, -0.2, 0.42), (0.2, -1, 0.1), 0.3), "eyeL": ((0.11, -0.2, 0.63), (0.25, -1, 0.05), 0.24), "eyeLside": ((0.12, -0.15, 0.63), (0.9, -0.4, 0.05), 0.26), "ear": ((0.27, -0.0, 0.58), (1, -0.3, 0), 0.25), "under": ((0, -0.15, 0.40), (0, -0.4, -1), 0.35), "corner": ((0.2, -0.17, 0.64), (0.5, -0.85, 0.1), 0.09), "cornerIn": ((0.2, -0.12, 0.64), (-0.3, -0.9, 0.2), 0.1)}
sel = os.environ.get('VIEWS')
for name, (t, d, s) in [(k, VIEWS_ALL[k]) for k in (sel.split(',') if sel else VIEWS_ALL)]:
    dv = Vector(d).normalized(); cd.ortho_scale = s
    cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{pre}_{name}.png"; bpy.ops.render.render(write_still=True)
