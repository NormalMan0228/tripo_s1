"""Clay (Workbench studio) renders from named views; optional eye hide and wire overlay via freestyle-free wireframe modifier copy.
Usage: blender -b f.blend -P render_clay_views.py -- out_prefix view1,view2,... [hide=Eye.L,Eye.R] [wire=1]
views: front | q34 | side | face | eyeL | eyeLq | mouth | mouthq | top | back"""
import bpy, sys, os, math
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(a[0]); views = a[1].split(",")
opts = dict(x.split("=") for x in a[2:])
for nm in opts.get("hide", "").split(","):
    o = bpy.data.objects.get(nm)
    if o: o.hide_render = True
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = os.environ.get('COLOR_TYPE', 'SINGLE'); sh.single_color = (0.8, 0.8, 0.8); sh.show_cavity = True
sh.cavity_type = 'WORLD'; sh.show_specular_highlight = True
sc.render.resolution_x = sc.render.resolution_y = 900
sc.view_settings.view_transform = 'Standard'
if opts.get("wire") == "1":
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render]:
        w = o.copy(); w.data = o.data; sc.collection.objects.link(w)
        m = w.modifiers.new("w", 'WIREFRAME'); m.thickness = 0.0006; m.use_replace = True
        mat = bpy.data.materials.new("wire"); mat.diffuse_color = (0.1, 0.1, 0.1, 1); w.data = o.data.copy(); w.data.materials.clear(); w.data.materials.append(mat)
    sh.color_type = 'MATERIAL'
    for o in bpy.data.objects:
        if o.type == 'MESH' and not o.modifiers and not o.hide_render:
            o.data.materials.clear(); mm = bpy.data.materials.new("c"); mm.diffuse_color = (0.8, 0.8, 0.8, 1); o.data.materials.append(mm)
eye = Vector(bpy.data.objects["Head"].get("eye_centre_L", (0.115, -0.116, 0.636)))
V = {"front": ((0, -1, 0), (0, 0, 0.5), 1.1), "q34": ((0.6, -0.8, 0.05), (0, 0, 0.5), 1.1), "side": ((1, 0, 0), (0, 0, 0.5), 1.1),
     "face": ((0, -1, 0), (0, 0, 0.56), 0.5), "eyeL": ((0, -1, 0), eye, 0.24), "eyeLq": ((0.7, -0.7, 0.1), eye, 0.24),
     "eyeLs": ((1, -0.15, 0.05), eye, 0.24), "lidtop": ((0, -1, 0.25), eye + Vector((0.0, -0.06, 0.055)), 0.09), "mouth": ((0, -1, 0), (0, 0, 0.42), 0.24), "mouthq": ((0.6, -0.8, -0.1), (0, -0.2, 0.42), 0.26),
     "top": ((0, -0.3, 1), (0, 0, 0.6), 1.0), "back": ((0, 1, 0), (0, 0, 0.5), 1.1), "under": ((0, -0.5, -1), (0, -0.1, 0.4), 0.6)}
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
for v in views:
    d, tgt, osc = V[v]; d = Vector(d).normalized(); tgt = Vector(tgt)
    cd.ortho_scale = osc; cam.location = tgt + d * 3; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{OUT}_{v}.png"; bpy.ops.render.render(write_still=True)
