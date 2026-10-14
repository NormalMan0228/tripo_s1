import bpy, sys, os, numpy as np
from mathutils import Vector
out = os.path.abspath(sys.argv[sys.argv.index("--")+1]); os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
body = bpy.data.objects["Template_Face_Body"]
for o in sc.objects:
    if o.type == 'MESH' and o is not body: o.hide_render = True
for m in body.modifiers:
    if m.type == 'SUBSURF': m.show_render = False
if body.data.shape_keys:
    for kb in body.data.shape_keys.key_blocks[1:]: kb.value = 0
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 900
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.8, 0.78, 0.76)
dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
co = np.array([body.matrix_world @ v.co for v in me.vertices]); ev.to_mesh_clear()
top = co[:, 2].max(); head = co[co[:, 2] > top - 0.25]
c = head.mean(0); front_y = head[:, 1].min()
print("head center", c.round(3), "top", round(top, 3), "front y", round(front_y, 3), "x range", head[:,0].min().round(3), head[:,0].max().round(3))
body.show_wire = True; body.show_all_edges = True
# freestyle-free wire overlay via wireframe modifier copy is heavy; use object wire display in workbench
sh.show_object_outline = False
sc.display.shading.show_xray = False
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
wm = body.modifiers.new("wf", 'WIREFRAME'); wm.thickness = 0.0006; wm.use_replace = False; wm.material_offset = 1
mat = bpy.data.materials.new("wire"); mat.diffuse_color = (0.05, 0.05, 0.05, 1); body.data.materials.append(mat)
sh.color_type = 'MATERIAL'
for name, d, tgt, s in (("face", (0, -1, 0), c + Vector((0, 0, -0.02)), 0.24), ("eye", (0, -1, 0), c + Vector((0.033, 0, 0.01)), 0.08),
                        ("mouth", (0, -1, 0), c + Vector((0, 0, -0.075)), 0.08), ("side", (1, 0, 0), c + Vector((0, 0, -0.02)), 0.26),
                        ("mouth34", (0.6, -0.8, -0.1), c + Vector((0.01, 0, -0.075)), 0.1)):
    dv = Vector(d).normalized(); cd.ortho_scale = s
    t = Vector(tgt); t.y = front_y + 0.05 if d[1] else t.y
    cam.location = t + dv * 1.0; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(out, f"tmpl_{name}.png"); bpy.ops.render.render(write_still=True)
