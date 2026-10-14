import bpy, sys, os, json
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]; ob = bpy.data.objects[a[0]]; sel = json.load(open(a[1])); pre = os.path.abspath(a[2]); keys = a[3].split(",")
sc = bpy.context.scene
for o in sc.objects: o.hide_render = o is not ob
me = ob.data; col = me.color_attributes.new("sel", 'FLOAT_COLOR', 'POINT')
for i in range(len(me.vertices)): col.data[i].color = (0.8, 0.78, 0.76, 1)
for k, c in zip(keys, [(1, 0.2, 0.2, 1), (0.2, 0.4, 1, 1), (0.2, 0.9, 0.2, 1)]):
    for i in sel[k]: col.data[i].color = c
me.color_attributes.active_color = col
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 700
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'VERTEX'
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
for name, (t, d, s) in {"front": ((0, 0, 0.55), (0, -1, 0), 1.0), "side": ((0, 0, 0.55), (1, 0, 0), 1.0)}.items():
    dv = Vector(d).normalized(); cd.ortho_scale = s
    cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{pre}_{name}.png"; bpy.ops.render.render(write_still=True)
