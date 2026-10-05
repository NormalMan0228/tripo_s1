"""Transfer existing approved-reference textures onto unchanged native P2 meshes.

No provider calls, sculpting, remeshing, fitting or rigging. Run in Blender:
  blender --background --python tools/blender_texture_existing_p2.py -- --part head
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/characters/explorer_b_fullbody_v2'
OLD = ROOT / 'art/characters/explorer_b_modular_v1/03_generated'
OUT = BASE / '06_textured_parts'
parser = argparse.ArgumentParser()
parser.add_argument('--part', choices=['head', 'hand', 'hair', 'fullbody'], required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
part = args.part
folder = OUT / part
folder.mkdir(parents=True, exist_ok=True)
texdir = folder / 'textures'
texdir.mkdir(exist_ok=True)
target_path = BASE / ('03_generated_p2/model.fbx' if part == 'fullbody' else f'04_replacement_parts_p2/{part}/model.fbx')
source_path = BASE / '03_generated/model.glb' if part == 'fullbody' else OLD / part / 'model.glb'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def geometry_digest(obj):
    h = hashlib.sha256()
    for vertex in obj.data.vertices:
        h.update(bytes(str(tuple(vertex.co)), 'ascii'))
    for face in obj.data.polygons:
        h.update(bytes(str(tuple(face.vertices)), 'ascii'))
    for loop in obj.data.uv_layers.active.data:
        h.update(bytes(str(tuple(loop.uv)), 'ascii'))
    return h.hexdigest()

def meshes():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']

def bounds(objects):
    points = [o.matrix_world @ Vector(v) for o in objects for v in o.bound_box]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    return lo, hi

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source_path))
sources = meshes()
if len(sources) != 1:
    raise RuntimeError('Source material transfer expects one textured source mesh')
source = sources[0]
bpy.ops.import_scene.fbx(filepath=str(target_path), use_anim=False)
target = next(o for o in meshes() if o not in sources)
target.name = f'P2_{part}_Native'
before = geometry_digest(target)
original_uv_name = target.data.uv_layers.active.name

# Only the temporary texture donor is aligned. Native P2 vertices never move.
slo, shi = bounds(sources)
tlo, thi = bounds([target])
sc, tc = (slo + shi) / 2, (tlo + thi) / 2
factor = Vector([(thi[i] - tlo[i]) / (shi[i] - slo[i]) for i in range(3)])
inv = source.matrix_world.inverted()
for v in source.data.vertices:
    world = source.matrix_world @ v.co
    aligned = Vector([(world[i] - sc[i]) * factor[i] + tc[i] for i in range(3)])
    v.co = inv @ aligned
source.data.update()

def fill_projection_misses(image, socket):
    """Repair only zero-valued ray misses inside occupied P2 UV triangles.

    Surface lookup happens per texel, avoiding interpolation across donor UV
    seams. Empty atlas space and intentional donor colors remain untouched.
    """
    n = image.size[0]
    pixels = np.empty(n * n * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(n, n, 4)
    missing = np.max(pixels[:, :, :3], axis=2) < 1e-7
    source.data.calc_loop_triangles()
    st = list(source.data.loop_triangles)
    sv = [source.matrix_world @ v.co for v in source.data.vertices]
    tree = BVHTree.FromPolygons(sv, [tuple(t.vertices) for t in st], all_triangles=True)
    suv = source.data.uv_layers.active.data
    texture = next((node.image for node in oldnodes if node.type == 'TEX_IMAGE' and node.image and
                    node.image.name.startswith('Color_' if socket == 'Base Color' else 'ORM_')), None)
    if texture is None:
        return 0
    w, h = texture.size
    donor = np.empty(w * h * 4, dtype=np.float32)
    texture.pixels.foreach_get(donor)
    donor = donor.reshape(h, w, 4)
    target.data.calc_loop_triangles()
    tuv = target.data.uv_layers.active.data
    count = 0
    for triangle in target.data.loop_triangles:
        uv = np.array([tuple(tuv[li].uv) for li in triangle.loops]) * n
        low = np.maximum(np.floor(uv.min(axis=0)).astype(int), 0)
        high = np.minimum(np.ceil(uv.max(axis=0)).astype(int), n - 1)
        x0, y0 = low
        x1, y1 = high
        if x1 < x0 or y1 < y0 or not missing[y0:y1+1, x0:x1+1].any():
            continue
        ys, xs = np.nonzero(missing[y0:y1+1, x0:x1+1])
        xs, ys = xs + x0, ys + y0
        a, b, c = uv
        det = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
        if abs(det) < 1e-10:
            continue
        u = ((b[1]-c[1])*(xs+.5-c[0])+(c[0]-b[0])*(ys+.5-c[1])) / det
        v = ((c[1]-a[1])*(xs+.5-c[0])+(a[0]-c[0])*(ys+.5-c[1])) / det
        valid = (u >= -1e-6) & (v >= -1e-6) & (u+v <= 1.000001)
        points = [target.matrix_world @ target.data.vertices[vi].co for vi in triangle.vertices]
        for x, y, wa, wb in zip(xs[valid], ys[valid], u[valid], v[valid]):
            world = points[0]*float(wa) + points[1]*float(wb) + points[2]*float(1-wa-wb)
            hit, _, ti, _ = tree.find_nearest(world)
            t = st[ti]
            coord = barycentric_transform(hit, *[sv[vi] for vi in t.vertices],
                                          *[Vector((*suv[li].uv, 0)) for li in t.loops])
            tx, ty = np.clip(coord.x*w-.5, 0, w-1), np.clip(coord.y*h-.5, 0, h-1)
            ix, iy = int(tx), int(ty)
            fx, fy = tx-ix, ty-iy
            col = (donor[iy, ix]*(1-fx)+donor[iy, min(ix+1,w-1)]*fx)*(1-fy)
            col += (donor[min(iy+1,h-1),ix]*(1-fx)+donor[min(iy+1,h-1),min(ix+1,w-1)]*fx)*fy
            pixels[y,x,:3] = col[:3] if socket == 'Base Color' else col[1]
            pixels[y,x,3] = 1
            missing[y,x] = False
            count += 1
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    print('REPAIRED_RAY_MISSES', part, socket, count, flush=True)
    return count

# Project donor shaders at each texel. Per-vertex UV transfer is unsuitable:
# interpolation across the donor atlas seams introduces false patch boundaries.
target.data.uv_layers.active = target.data.uv_layers[original_uv_name]
target.data.uv_layers[original_uv_name].active_render = True

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'CUDA'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'CUDA'
    if any(d.type == 'CUDA' for d in prefs.devices):
        scene.cycles.device = 'GPU'
except Exception:
    pass

oldmat = source.data.materials[0]
oldnodes = oldmat.node_tree.nodes
oldbsdf = next(n for n in oldnodes if n.type == 'BSDF_PRINCIPLED')
material = bpy.data.materials.new(f'Explorer_P2_{part}_Baked')
material.use_nodes = True
material.name = f'Explorer_P2_{part}_Baked'
target.data.materials.clear()
target.data.materials.append(material)
nodes, links = material.node_tree.nodes, material.node_tree.links
bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
donor_links = oldmat.node_tree.links
donor_output = next(n for n in oldnodes if n.type == 'OUTPUT_MATERIAL')
emission = oldnodes.new('ShaderNodeEmission')
donor_links.new(emission.outputs[0], donor_output.inputs['Surface'])
destination = nodes.new('ShaderNodeTexImage')
destination.label = 'Bake destination on original P2 UVs'
nodes.active = destination
for o in bpy.context.selected_objects:
    o.select_set(False)
target.select_set(True)
bpy.context.view_layer.objects.active = target
source.select_set(True)
source.hide_render = False
scene.render.bake.use_selected_to_active = True
scene.render.bake.cage_extrusion = 0.025
scene.render.bake.max_ray_distance = 0.1
scene.render.bake.margin = 16
images = {}
repaired = {}
for name, socket, size in [('BaseColor', 'Base Color', 4096), ('Roughness', 'Roughness', 2048)]:
    for link in list(emission.inputs['Color'].links):
        donor_links.remove(link)
    if oldbsdf.inputs[socket].is_linked:
        donor_links.new(oldbsdf.inputs[socket].links[0].from_socket, emission.inputs['Color'])
    else:
        val = oldbsdf.inputs[socket].default_value
        emission.inputs['Color'].default_value = (val, val, val, 1) if isinstance(val, float) else val
    image = bpy.data.images.new(f'{part}_{name}', width=size, height=size, alpha=False)
    image.colorspace_settings.name = 'sRGB' if name == 'BaseColor' else 'Non-Color'
    destination.image = image
    bpy.ops.object.bake(type='EMIT', use_clear=True)
    repaired[name] = fill_projection_misses(image, socket)
    image.filepath_raw = str(texdir / f'{part}_{name}.png')
    image.file_format = 'PNG'
    image.save()
    images[name] = image
    print('BAKED', part, name, flush=True)

# Re-bake the normal information into P2 tangent space. Donor normal textures
# cannot simply be copied because donor and P2 use different UVs and tangents.
donor_links.new(oldbsdf.outputs['BSDF'], donor_output.inputs['Surface'])
normal_image = bpy.data.images.new(f'{part}_Normal', width=2048, height=2048, alpha=False)
normal_image.colorspace_settings.name = 'Non-Color'
destination.image = normal_image
source.hide_render = False
source.select_set(True)
scene.render.bake.use_selected_to_active = True
scene.render.bake.cage_extrusion = 0.025
scene.render.bake.max_ray_distance = 0.1
bpy.ops.object.bake(type='NORMAL', use_clear=True)
normal_image.filepath_raw = str(texdir / f'{part}_Normal.png')
normal_image.file_format = 'PNG'
normal_image.save()
images['Normal'] = normal_image

# Final material uses only the newly baked maps and original P2 UVs.
nodes.clear()
output = nodes.new('ShaderNodeOutputMaterial')
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
for name, sock in [('BaseColor', 'Base Color'), ('Roughness', 'Roughness')]:
    n = nodes.new('ShaderNodeTexImage')
    n.image = images[name]
    n.name = name
    links.new(n.outputs['Color'], bsdf.inputs[sock])
n = nodes.new('ShaderNodeTexImage')
n.image = images['Normal']
n.name = 'Normal'
normal = nodes.new('ShaderNodeNormalMap')
normal.inputs['Strength'].default_value = 0.35
links.new(n.outputs['Color'], normal.inputs['Color'])
links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])
after = geometry_digest(target)
if after != before:
    raise RuntimeError('Native P2 geometry or UVs unexpectedly changed')
for o in list(bpy.data.objects):
    if o != target:
        bpy.data.objects.remove(o, do_unlink=True)
for polygon in target.data.polygons:
    polygon.use_smooth = True

# Studio is review-only; hidden from viewport so clicking always selects a mesh.
lo, hi = bounds([target])
center, radius = (lo + hi) / 2, max(hi - lo)
world = bpy.data.worlds.new('Texture Review World')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.75, 0.80, 0.85, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = 0.5
scene.world = world
studio = bpy.data.collections.new('Review Studio')
scene.collection.children.link(studio)
for name, offset, power, size in [('Key', (3, -3, 4), 500, 3), ('Fill', (2, 3, 1), 200, 3), ('Rim', (-3, 0, 3), 400, 2)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.size = power * radius * radius, size * radius
    o = bpy.data.objects.new(name, data)
    studio.objects.link(o)
    o.location = center + Vector(offset) * radius
    o.rotation_euler = (center - o.location).to_track_quat('-Z', 'Y').to_euler()
    o.hide_select = True
    o.hide_set(True)
camera = bpy.data.objects.new('Preview Camera', bpy.data.cameras.new('Preview Camera'))
studio.objects.link(camera)
camera.hide_select = True
camera.hide_set(True)
scene.camera = camera
camera.data.type = 'ORTHO'
camera.data.ortho_scale = radius * 1.2
scene.render.resolution_x, scene.render.resolution_y = 900, 1100 if part == 'fullbody' else 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
for view, offset in [('front', (4, 0, 0)), ('angle', (4, -2, .5)), ('back', (-4, 0, 0))]:
    camera.location = center + Vector(offset) * radius
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(folder / f'preview-{view}.png')
    bpy.ops.render.render(write_still=True)
target.select_set(True)
bpy.context.view_layer.objects.active = target
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'MATERIAL'
            area.spaces.active.region_3d.view_location = center
            area.spaces.active.region_3d.view_distance = radius * 2
            area.spaces.active.region_3d.view_rotation = Vector((-4, 0, 0)).to_track_quat('-Z', 'Y')
bpy.ops.file.pack_all()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(folder / f'{part}_textured.blend'))
report = {'part': part, 'target_source': str(target_path.relative_to(ROOT)), 'target_file_sha256': digest(target_path),
          'texture_donor': str(source_path.relative_to(ROOT)), 'donor_sha256': digest(source_path),
          'target_geometry_uv_digest_before': before, 'target_geometry_uv_digest_after': after,
          'vertices': len(target.data.vertices), 'polygons': len(target.data.polygons),
          'geometry_changed': False, 'uv_changed': False, 'assembled': False, 'rigged': False,
          'new_api_credits': 0, 'maps': {n: [im.size[0], im.size[1]] for n, im in images.items()},
          'temporary_donor_axis_scale': list(factor),
          'normal_strength': 0.35, 'method': 'selected_to_active_emission_bake_plus_tangent_normal_rebake'}
report['ray_miss_texels_repaired_from_nearest_donor_surface'] = repaired
(folder / 'texture-transfer.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('TEXTURED_READY', part, flush=True)
