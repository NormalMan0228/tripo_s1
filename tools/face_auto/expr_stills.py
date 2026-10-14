"""Expression stills for review: grey material with a painted iris (gaze readable), EEVEE, orthographic camera from the
landmarks; one PNG per combo of shape-key values (every mesh with keys of those names gets the same values, so teeth,
tongue, caruncle and bound brows ride along).
Usage: blender -b <arkit_bp.blend> -P expr_stills.py -- <out_dir> <landmarks.json> <eyes_meta.json|-> <view face|34|mouth|eyes|cut> <combo,combo,...>
  combo = rest | key | key+key | key=0.5+key ...   env RES (default 512), SLIT_RING (mouth json 'rings', default 12)
Writes <out_dir>/<view>_<combo with + -> _ and = removed>.png and <out_dir>/stills_qa.json (missing keys per combo).
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
OUT, LMJ, EMJ, VIEW, COMBOS = os.path.abspath(a[0]), a[1], a[2], a[3], a[4].split(',')
os.makedirs(OUT, exist_ok=True); RES = int(os.environ.get('RES', 512))
sc = bpy.context.scene
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try: sc.render.engine = eng; break
    except TypeError: pass
sc.render.resolution_x = sc.render.resolution_y = RES; sc.view_settings.view_transform = 'Standard'
if not sc.world: sc.world = bpy.data.worlds.new('w')
sc.world.use_nodes = True; bgn = sc.world.node_tree.nodes['Background']; bgn.inputs[0].default_value = (0.62, 0.62, 0.64, 1); bgn.inputs[1].default_value = 0.55
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 1.6; so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (0.75, 0.25, -0.35)

IRIS = {}
if EMJ != '-' and os.path.exists(EMJ):
    J = json.load(open(EMJ)); E = J.get('eyes', {k: v for k, v in J.items() if k in ('L', 'R')})
    for sd, e in E.items():
        if 'iris_dir' in e:
            IRIS[sd] = (np.array(e['iris_dir'], float) / np.linalg.norm(e['iris_dir']), float(e.get('iris_radius_deg', 22)), np.array(e['C'], float))
cols = {'face': (0.55, 0.55, 0.57), 'eyes': (0.86, 0.86, 0.87), 'teeth_up': (0.9, 0.88, 0.8), 'teeth_lo': (0.9, 0.88, 0.8),
        'tongue': (0.62, 0.3, 0.32), 'caruncle': (0.75, 0.45, 0.47), 'p2_brows': (0.3, 0.24, 0.2)}
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for md in [m for m in o.modifiers if m.type == 'ARMATURE']: md.show_render = md.show_viewport = False   # keys only
    m = bpy.data.materials.new('g_' + o.name); m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value = (*cols.get(o.name, (0.55, 0.55, 0.57)), 1)
    bs.inputs['Roughness'].default_value = 0.2 if o.name == 'eyes' else 0.55
    slots = [x.name if x else '' for x in o.data.materials]
    o.data.materials.clear(); o.data.materials.append(m)
    if any('gum' in x for x in slots):                            # teeth objects: keep the gum faces pink (slot order kept)
        gm = bpy.data.materials.new('g_gum_' + o.name); gm.use_nodes = True
        gm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (0.72, 0.36, 0.38, 1)
        o.data.materials.clear()
        for x in slots: o.data.materials.append(gm if 'gum' in x else m)
    if o.name == 'eyes':
        X = np.array([tuple(v.co) for v in o.data.vertices]); col = np.ones((len(X), 4), np.float32)
        Cs = {sd: v[2] for sd, v in IRIS.items()} if len(IRIS) == 2 else {'L': X[X[:, 0] > 0].mean(0), 'R': X[X[:, 0] < 0].mean(0)}
        near = np.array(list(Cs))[np.argmin(np.stack([np.linalg.norm(X - c, axis=1) for c in Cs.values()]), axis=0)]
        for sd in Cs:
            sel = near == sd; C = Cs[sd]; g = IRIS.get(sd, (np.array([0, -1.0, 0]), 22.0, C))
            ang = np.degrees(np.arccos(np.clip(((X[sel] - C) / np.linalg.norm(X[sel] - C, axis=1)[:, None]) @ g[0], -1, 1)))
            c = np.tile([0.86, 0.86, 0.87, 1], (sel.sum(), 1)); c[ang < g[1]] = [0.32, 0.22, 0.14, 1]; c[ang < 0.42 * g[1]] = [0.03, 0.03, 0.03, 1]
            col[sel] = c
        at = o.data.color_attributes.new('irisc', 'FLOAT_COLOR', 'POINT'); at.data.foreach_set('color', col.ravel())
        nt = m.node_tree; an = nt.nodes.new('ShaderNodeAttribute'); an.attribute_name = 'irisc'
        nt.links.new(an.outputs['Color'], bs.inputs['Base Color'])
# mouth interior: faces of 'face' behind the slit get a dark red second material
F = bpy.data.objects.get('face')
if F is not None and 'mouth_ring' in F.data.attributes:
    rg = np.empty(len(F.data.vertices), np.int32); F.data.attributes['mouth_ring'].data.foreach_get('value', rg)
    SL = int(os.environ.get('SLIT_RING', 12))                     # loop_organs / organ_mouth: slit ring = mouth json 'rings'
    mi = bpy.data.materials.new('g_inner'); mi.use_nodes = True
    mi.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (0.35, 0.1, 0.11, 1)
    F.data.materials.append(mi)
    lv = np.empty(len(F.data.loops), np.int32); F.data.loops.foreach_get('vertex_index', lv)
    for p in F.data.polygons:
        r = rg[lv[p.loop_start:p.loop_start + p.loop_total]]
        if r.min() > SL: p.material_index = 1                         # behind the slit ring

LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]; cz = (top + LT[24][2]) / 2 + 0.02 * fh
mz = (LT[20][2] + LT[22][2]) / 2; ez = (LT[8][2] + LT[12][2]) / 2
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
cy = float(np.mean([LT[k][1] for k in LT]))
d, size, zc, xc = {'face': ((0, -1, 0), 1.18 * fh, cz, 0.0), '34': ((0.7, -0.7, 0), 1.3 * fh, cz, 0.0),
                   'mouth': ((0, -1, 0), 0.5 * fh, mz, 0.0), 'eyes': ((0, -1, 0), 0.62 * fh, ez, 0.0),
                   'cut': ((1, 0, 0), 0.42 * fh, mz, 0.0)}[VIEW]
look_at = Vector((xc, cy, zc)); co.location = look_at + Vector(d).normalized() * 1.0
co.rotation_euler = (look_at - co.location).to_track_quat('-Z', 'Y').to_euler(); cam.ortho_scale = size; cam.clip_end = 10
if VIEW == 'cut':                                                  # mid-sagittal section: the camera's near plane is x = 0
    look_at.y = (LT[34][1] + LT[35][1]) / 2 + 0.12 * fh if 34 in LT and 35 in LT else cy; co.location = look_at + Vector((1.0, 0, 0)); cam.clip_start = 1.0; cam.clip_end = 1.5
    co.rotation_euler = (look_at - co.location).to_track_quat('-Z', 'Y').to_euler()
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.data.shape_keys]
qa = {}
for cb in COMBOS:
    vals = {}
    if cb != 'rest':
        for t in cb.split('+'):
            k, _, v = t.partition('='); vals[k] = float(v) if v else 1.0
    qa[cb] = [k for k in vals if not any(k in o.data.shape_keys.key_blocks for o in meshes)]
    for o in meshes:
        for kb in o.data.shape_keys.key_blocks[1:]: kb.value = vals.get(kb.name, 0.0)
    sc.render.filepath = os.path.join(OUT, f"{VIEW}_{cb.replace('+', '_').replace('=', '')}.png")
    bpy.ops.render.render(write_still=True)
json.dump(qa, open(os.path.join(OUT, 'stills_qa.json'), 'w'), indent=0)
print('STILLS', VIEW, len(COMBOS), 'missing', {k: v for k, v in qa.items() if v})
