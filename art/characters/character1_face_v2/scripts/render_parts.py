import bpy, sys, os, json
from mathutils import Vector
pre = os.path.abspath(sys.argv[sys.argv.index("--")+1])
sc = bpy.context.scene
cols = {"Eye.L": (1, 1, 1), "Eye.R": (1, 1, 1), "Teeth": (1, 1, 0.85), "Tongue": (0.9, 0.3, 0.35), "Brow.L": (0.25, 0.15, 0.1), "Brow.R": (0.25, 0.15, 0.1)}
w = bpy.data.objects["WrapHead"]
for o in sc.objects:
    if o.type == 'MESH':
        o.hide_render = not (o is w or o.name in cols)
        if o.name in cols:
            o.color = (*cols[o.name], 1)
            ca = o.data.color_attributes.new("part_id", 'FLOAT_COLOR', 'CORNER')
            for i in range(len(ca.data)): ca.data[i].color = (*cols[o.name], 1)
            o.data.color_attributes.active_color = ca
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 700
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'VERTEX'
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
poses = {"rest": {}, "jaw": {"jawOpen": 0.8}}
for pn, kv in poses.items():
    for o in sc.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]: kb.value = kv.get(kb.name, 0)
    for name, (t, d, s) in {"front": ((0, -0.2, 0.55), (0, -1, 0), 0.75), "q34": ((0, -0.1, 0.55), (0.7, -0.7, 0.05), 0.85), "side": ((0, -0.1, 0.55), (1, 0, 0), 0.85), "mouth": ((0, -0.2, 0.46), (0.3, -1, 0.1), 0.3)}.items():
        dv = Vector(d).normalized(); cd.ortho_scale = s
        cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = f"{pre}_{pn}_{name}.png"; bpy.ops.render.render(write_still=True)
