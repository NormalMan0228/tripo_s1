"""EEVEE + forest HDRI renders (Material Preview look) of chosen objects with optional shape keys / bone poses.
Usage: blender --background X.blend --python render_eevee.py -- <out_prefix> <objects,comma> <views,comma> [poses.json] [res]
poses.json: {"name": {"keys": {"k": v}, "bones": {"bone": [degx,degy,degz]}}}  (world-axis rotations at bone head)
"""
import bpy, sys, os, json, math
from mathutils import Vector, Euler
a = sys.argv[sys.argv.index("--") + 1:]
pre = os.path.abspath(a[0]); objs = set(a[1].split(",")); views = a[2].split(",")
poses = json.load(open(a[3])) if len(a) > 3 and a[3] != "-" else {"rest": {}}
res = int(a[4]) if len(a) > 4 else 700
sc = bpy.context.scene
for o in sc.objects:
    if o.type == 'MESH': o.hide_render = o.name not in objs
w = bpy.data.worlds.new("w"); w.use_nodes = True; sc.world = w
env = w.node_tree.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(os.path.join(os.path.dirname(bpy.app.binary_path), "4.5", "datafiles", "studiolights", "world", "forest.exr"))
w.node_tree.links.new(env.outputs["Color"], w.node_tree.nodes["Background"].inputs["Color"])
sc.render.engine = 'BLENDER_EEVEE_NEXT'; sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = sc.render.resolution_y = res
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
V = {"front": ((0, -0.2, 0.55), (0, -1, 0), 0.75), "q34": ((0, -0.1, 0.55), (0.7, -0.7, 0.05), 0.85),
     "side": ((0, -0.1, 0.55), (1, 0, 0), 0.85), "face": ((0, -0.2, 0.57), (0, -1, 0), 0.5),
     "eyes": ((0, -0.2, 0.63), (0, -1, 0), 0.42), "eyeL": ((0.11, -0.2, 0.63), (0.2, -1, 0.05), 0.22),
     "eyeLside": ((0.11, -0.15, 0.63), (0.8, -0.6, 0.05), 0.24), "mouth": ((0, -0.2, 0.46), (0.2, -1, 0), 0.3),
     "mouthside": ((0, -0.2, 0.46), (0.9, -0.45, 0), 0.32), "back": ((0, 0, 0.55), (0, 1, 0), 0.85)}
arm = next((o for o in sc.objects if o.type == 'ARMATURE'), None)
for pname, p in poses.items():
    for o in sc.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = float(p.get("keys", {}).get(kb.name, 0.0))
    if arm:
        for pb in arm.pose.bones:
            pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
        for bn, ang in p.get("bones", {}).items():
            pb = arm.pose.bones[bn]; B = pb.bone.matrix_local.to_3x3()
            Rw = Euler([math.radians(x) for x in ang], 'XYZ').to_matrix()
            pb.rotation_quaternion = (B.inverted() @ Rw @ B).to_quaternion()
    bpy.context.view_layer.update()
    for v in views:
        t, d, s = V[v]; dv = Vector(d).normalized(); cd.ortho_scale = s
        cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = f"{pre}_{pname}__{v}.png"; bpy.ops.render.render(write_still=True)
print("RENDERED", len(poses))
