"""Repack WrapHead UV islands and bake base colour (+ tangent normal) from the Tripo target (Body).

Base colour: Body material re-wired to emit its base-colour texture; EMIT bake, selected-to-active.
Normal: tangent-space normal bake from Body onto WrapHead.
Usage: blender --background wrapped_X.blend --python bake_texture.py -- <out.blend> <tex_dir> [res]
"""
import bpy, sys, os
a = sys.argv[sys.argv.index("--") + 1:]
OUT, TEX = os.path.abspath(a[0]), os.path.abspath(a[1]); RES = int(a[2]) if len(a) > 2 else 2048
os.makedirs(TEX, exist_ok=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.device = 'CPU'
w = bpy.data.objects["WrapHead"]; b = bpy.data.objects["Body"]
for o in bpy.data.objects:
    o.hide_render = False; o.hide_viewport = False; o.select_set(False)
# --- UV repack (keep template seams)
bpy.context.view_layer.objects.active = w; w.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.average_islands_scale()
bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
bpy.ops.object.mode_set(mode='OBJECT')
# --- target images
bm = b.data.materials[0]; nt = bm.node_tree
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
base_link = bsdf.inputs["Base Color"].links[0]
base_src = base_link.from_socket
out_node = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
orig_surface = out_node.inputs["Surface"].links[0].from_socket
emit = nt.nodes.new("ShaderNodeEmission"); nt.links.new(base_src, emit.inputs["Color"])
# --- wrap material with bake targets
wm = bpy.data.materials.new("M_FaceSkin"); wm.use_nodes = True
w.data.materials.clear(); w.data.materials.append(wm)
wnt = wm.node_tree; wb = wnt.nodes["Principled BSDF"]
img_c = bpy.data.images.new("face_basecolor", RES, RES); img_n = bpy.data.images.new("face_normal", RES, RES)
img_n.colorspace_settings.name = 'Non-Color'
tc = wnt.nodes.new("ShaderNodeTexImage"); tc.image = img_c
tn = wnt.nodes.new("ShaderNodeTexImage"); tn.image = img_n
nm = wnt.nodes.new("ShaderNodeNormalMap")
wnt.links.new(tc.outputs["Color"], wb.inputs["Base Color"])
wnt.links.new(tn.outputs["Color"], nm.inputs["Color"]); wnt.links.new(nm.outputs["Normal"], wb.inputs["Normal"])
wb.inputs["Roughness"].default_value = 0.55; wb.inputs["Metallic"].default_value = 0.0
for o in bpy.data.objects: o.select_set(False)
b.select_set(True); w.select_set(True); bpy.context.view_layer.objects.active = w
sc.render.bake.use_selected_to_active = True
sc.render.bake.cage_extrusion = 0.01; sc.render.bake.max_ray_distance = 0.03
sc.render.bake.margin = 8
# colour
nt.links.new(emit.outputs["Emission"], out_node.inputs["Surface"])
wnt.nodes.active = tc
bpy.ops.object.bake(type='EMIT')
img_c.filepath_raw = os.path.join(TEX, "face_basecolor.png"); img_c.file_format = 'PNG'; img_c.save()
# normal
nt.links.new(orig_surface, out_node.inputs["Surface"])
wnt.nodes.active = tn
bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
img_n.filepath_raw = os.path.join(TEX, "face_normal.png"); img_n.file_format = 'PNG'; img_n.save()
img_c.pack(); img_n.pack()
nt.nodes.remove(emit)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("BAKED", RES)
