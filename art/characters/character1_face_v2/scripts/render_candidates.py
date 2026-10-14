"""Render every collection (candidate) of a .blend from fixed cameras: textured EEVEE, clay, face wireframe.
Usage: blender --background candidates.blend --python render_candidates.py -- <out_dir> [modes] [views] [collections]"""
import bpy, sys, os
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(a[0]); os.makedirs(out, exist_ok=True)
modes = a[1].split(",") if len(a) > 1 else ["tex", "clay", "wire"]
views = a[2].split(",") if len(a) > 2 else ["front", "q34", "side", "face"]
only = a[3].split(",") if len(a) > 3 else None
sc = bpy.context.scene
w = bpy.data.worlds.new("w"); w.use_nodes = True; sc.world = w
env = w.node_tree.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(os.path.join(os.path.dirname(bpy.app.binary_path), "4.5", "datafiles", "studiolights", "world", "forest.exr"))
w.node_tree.links.new(env.outputs["Color"], w.node_tree.nodes["Background"].inputs["Color"])
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = sc.render.resolution_y = int(os.environ.get("RES", 700))
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
CAMS = {"front": ((0, 0, 0.55), (0, -1, 0), 1.0), "q34": ((0, 0, 0.55), (0.7, -0.7, 0.05), 1.0),
        "side": ((0, 0, 0.55), (1, 0, 0), 1.0), "face": ((0, -0.2, 0.58), (0, -1, 0), 0.5),
        "eyeL": ((0.13, -0.2, 0.63), (0.25, -1, 0.05), 0.22), "mouth": ((0, -0.2, 0.45), (0.15, -1, 0), 0.25)}
colls = [c for c in bpy.data.collections if (only is None or c.name in only)]
for c in colls:
    for c2 in bpy.data.collections:
        for o in c2.objects:
            o.hide_render = (c2 is not c)
    for m in modes:
        wfs = []
        if m == "tex":
            sc.render.engine = 'BLENDER_EEVEE_NEXT'
        else:
            sc.render.engine = 'BLENDER_WORKBENCH'
            sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.8, 0.78, 0.76)
            if m == "wire":
                sh.color_type = 'MATERIAL'
                wm = bpy.data.materials.get("wiremat") or bpy.data.materials.new("wiremat"); wm.diffuse_color = (0.05, 0.05, 0.05, 1)
                cm = bpy.data.materials.get("claymat") or bpy.data.materials.new("claymat"); cm.diffuse_color = (0.8, 0.78, 0.76, 1)
                for o in c.objects:
                    if o.type == 'MESH':
                        o["_mats"] = [s.material.name if s.material else "" for s in o.material_slots]
                        o.data.materials.clear(); o.data.materials.append(cm); o.data.materials.append(wm)
                        md = o.modifiers.new("wf", 'WIREFRAME'); md.thickness = 0.0008; md.use_replace = False; md.material_offset = 1
                        wfs.append((o, md))
        for v in views:
            t, d, s = CAMS[v]; dv = Vector(d).normalized(); cd.ortho_scale = s
            cam.location = Vector(t) + dv * 2.5; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = os.path.join(out, f"{c.name}__{m}__{v}.png"); bpy.ops.render.render(write_still=True)
        for o, md in wfs:
            o.modifiers.remove(md)
            o.data.materials.clear()
            for n in o["_mats"]:
                o.data.materials.append(bpy.data.materials.get(n) if n else None)
print("DONE")
