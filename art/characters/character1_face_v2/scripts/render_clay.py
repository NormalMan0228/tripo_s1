"""Workbench clay renders of chosen objects with shape keys. Same args as render_eevee.py."""
import bpy, sys, os, json
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
pre = os.path.abspath(a[0]); objs = set(a[1].split(",")); views = a[2].split(","); poses = json.load(open(a[3])); res = int(a[4]) if len(a) > 4 else 500
sc = bpy.context.scene
for o in sc.objects:
    if o.type == 'MESH': o.hide_render = o.name not in objs
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = res
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = os.environ.get("CLAY_COLOR", 'SINGLE'); sh.single_color = (0.8, 0.78, 0.76)
sh.show_backface_culling = bool(os.environ.get("CULL"))
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
V = {"eyes": ((0, -0.2, 0.63), (0, -1, 0), 0.42), "eyeL": ((0.11, -0.2, 0.63), (0.2, -1, 0.05), 0.22),
     "eyeLside": ((0.11, -0.15, 0.63), (0.8, -0.6, 0.05), 0.24), "eyeLsec": ((0.11, -0.15, 0.63), (1, 0, 0), 0.24),
     "face": ((0, -0.2, 0.57), (0, -1, 0), 0.5), "mouth": ((0, -0.2, 0.46), (0.2, -1, 0), 0.3), "mouthOpenSide": ((0, -0.2, 0.44), (0.7, -0.7, 0.05), 0.3), "face34": ((0.03, -0.2, 0.58), (0.65, -0.75, 0.08), 0.55)}
for pname, p in poses.items():
    for o in sc.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]: kb.value = float(p.get("keys", {}).get(kb.name, 0.0))
    for v in views:
        t, d, s = V[v]; dv = Vector(d).normalized(); cd.ortho_scale = s
        cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = f"{pre}_{pname}__{v}.png"; bpy.ops.render.render(write_still=True)
