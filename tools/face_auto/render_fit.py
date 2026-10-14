"""Contact renders of a fitted face: one PNG per (expression, view).
Usage: blender -b <fit.blend> -P render_fit.py -- <out_dir> <prefix> <key[+key..]|neutral>,... [views=front,34,side,eye]
Each comma item sets those shape keys to 1 on every object that has them. 'target' renders the scaled target.
"""
import bpy, sys, os, math
from mathutils import Vector
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]
OUT, PFX, ITEMS = a[0], a[1], a[2].split(',')
VIEWS = a[3].split(',') if len(a) > 3 else ['front', '34', 'side']
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 560
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'OBJECT'; sc.display.shading.show_cavity = False
if not sc.world: sc.world = bpy.data.worlds.new('w')
col = {'head': (0.86, 0.72, 0.64, 1), 'face': (0.86, 0.72, 0.64, 1), 'eyes': (0.95, 0.95, 0.95, 1), 'mouth_cavity': (0.35, 0.08, 0.1, 1), 'eye_L': (0.95, 0.95, 0.95, 1), 'eye_R': (0.95, 0.95, 0.95, 1), 'teeth_up': (1, 1, 0.95, 1),
       'teeth_lo': (1, 1, 0.95, 1), 'tongue': (0.8, 0.35, 0.4, 1), 'lash_L': (0.1, 0.08, 0.08, 1), 'lash_R': (0.1, 0.08, 0.08, 1), 'target': (0.7, 0.7, 0.72, 1)}
for o in bpy.data.objects:
    if o.type == 'MESH': o.color = col.get(o.name, col['face'] if o.name.startswith('lid_') else (0.6, 0.6, 0.6, 1))
if 'mouth_inner' in bpy.data.materials:
    # multi-material face (skin + mouth interior): colour by material instead of by object
    sc.display.shading.color_type = 'MATERIAL'
    for o in bpy.data.objects:
        if o.type != 'MESH': continue
        if o.name in ('face',) or o.name.startswith('lid_'):
            for m in o.data.materials:
                if m and m.name != 'mouth_inner': m.diffuse_color = col['face']
        elif o.name == 'eyes':
            m = bpy.data.materials.new('eye_white'); m.diffuse_color = col['eyes']; o.data.materials.clear(); o.data.materials.append(m)
head = bpy.data.objects.get('head') or bpy.data.objects.get('face')
H = np.array([tuple(head.matrix_world @ v.co) for v in head.data.vertices])
lo, hi = H.min(0), H.max(0); cz = hi[2] - (hi[2] - lo[2]) * 0.42; size = (hi[2] - lo[2]) * 0.78
# iris discs so gaze and lid cover are readable
for n in ('eye_L', 'eye_R'):
    e = bpy.data.objects.get(n)
    if not e: continue
    P = np.array([tuple(e.matrix_world @ v.co) for v in e.data.vertices]); c = (P.max(0) + P.min(0)) / 2; r = (P.max(0) - P.min(0)).max() / 2
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r * 0.42, location=(c[0], c[1] - r * 0.93, c[2]), segments=24, ring_count=12)
    d = bpy.context.active_object; d.scale = (1, 0.25, 1); d.name = 'iris_' + n[-1]; d.color = (0.25, 0.16, 0.1, 1)
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
views = {'front': ((0, -1, 0), size, (0, 0, cz)), '34': ((0.7, -0.7, 0.05), size, (0, 0, cz)), 'side': ((1, 0, 0), size * 1.15, (0, (lo[1] + hi[1]) / 2, cz)),
         'eye': ((0.25, -1, 0.1), size * 0.42, (-(hi[0] - lo[0]) * 0.16, 0, cz)),
         'mouth': ((0.15, -1, -0.1), size * 0.34, (0, 0, cz - (hi[2] - lo[2]) * 0.17))}
def keyed():
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            yield o
for item in ITEMS:
    tgt_only = item == 'target'
    for o in bpy.data.objects:
        if o.type == 'MESH': o.hide_render = (o.name == 'target') != tgt_only and not (tgt_only and False)
        if tgt_only and o.type == 'MESH': o.hide_render = o.name != 'target'
    for o in keyed():
        for kb in o.data.shape_keys.key_blocks[1:]: kb.value = 1.0 if kb.name in item.split('+') else 0.0
    for v in VIEWS:
        d, s, c = views[v]; d = Vector(d).normalized(); co.location = Vector(c) + d * 2; cam.ortho_scale = s
        co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, f'{PFX}_{item.replace("+", "_")}_{v}.png'); bpy.ops.render.render(write_still=True)
print('RENDERED', len(ITEMS) * len(VIEWS))
