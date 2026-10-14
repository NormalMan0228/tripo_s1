import bpy, sys, os, json
from mathutils import Vector
pre = os.path.abspath(sys.argv[sys.argv.index("--")+1])
ob = bpy.data.objects["WrapHead"]; C = json.loads(ob["vertex_classes"])
sc = bpy.context.scene
for o in sc.objects:
    o.hide_render = o is not ob
me = ob.data; col = me.color_attributes.new("cls", 'FLOAT_COLOR', 'POINT')
for i in range(len(me.vertices)): col.data[i].color = (0.8, 0.78, 0.76, 1)
for k, c in (("socket", (0.2, 0.5, 1, 1)), ("bag", (1, 0.3, 0.3, 1)), ("pinned", (1, 1, 0, 1))):
    for i in C[k]: col.data[i].color = c
me.color_attributes.active_color = col
wm = ob.modifiers.new("wf", "WIREFRAME"); wm.thickness = 0.0008; wm.use_replace = False; wm.use_even_offset = False; wm.use_relative_offset = False
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 800
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'VERTEX'
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
VIEWS = {"front": ((0, -0.2, 0.55), (0, -1, 0), 0.7), "side": ((0, -0.1, 0.55), (1, 0, 0), 0.8), "back": ((0, 0, 0.55), (0, 1, 0), 0.8),
         "mouth": ((0, -0.2, 0.43), (0.3, -1, -0.2), 0.25), "under": ((0, -0.15, 0.40), (0, -0.4, -1), 0.3), "ear": ((0.27, -0.0, 0.58), (1, -0.3, 0), 0.25),
         "lips": ((0, -0.25, 0.45), (0, -1, 0.05), 0.2), "lipsside": ((0.03, -0.25, 0.45), (1, -0.25, 0), 0.16),
         "mcL": ((0.085, -0.24, 0.465), (0.3, -1, 0.1), 0.08), "mcR": ((-0.085, -0.24, 0.465), (-0.3, -1, 0.1), 0.08)}
sel = os.environ.get("VIEWS", "front,side,back").split(",")
for name, (t, d, s) in [(k, VIEWS[k]) for k in sel]:
    dv = Vector(d).normalized(); cd.ortho_scale = s
    cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{pre}_{name}.png"; bpy.ops.render.render(write_still=True)
