"""Rig points of the face rig as numbered dots: every distinct joint of the deform bones (DEF-* heads and tails of
'face_rig', merged within 0.2 mm), coloured by region, drawn over a grey head in front / 3/4 / side views. Joints that
the head surface hides from the camera are drawn hollow. Internal joints (eyeball centres, tongue, teeth, jaw hinge,
head/neck axis) are counted apart from the skin joints.
Usage: blender -b <rigify_sym.blend> -P rig_points_viz.py -- <out_dir> <landmarks.json>
Writes points_{front,34,side}.png (raw renders), points.json (per joint: position, region, bones, skin/internal) and
prints POINTS with the counts. Labels / legend are added by the report sheet script (PIL).
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

a = sys.argv[sys.argv.index('--') + 1:]; OUT, LMJ = os.path.abspath(a[0]), a[1]; os.makedirs(OUT, exist_ok=True)
rig = bpy.data.objects['face_rig']; face = bpy.data.objects['face']
REG = [('lid', 'eye/lid'), ('eye', 'eyeball'), ('brow', 'brow'), ('lip', 'lip/mouth'), ('mouth', 'lip/mouth'), ('nasolabial', 'cheek'),
       ('cheek', 'cheek'), ('nose', 'nose'), ('chin', 'jaw/chin'), ('jaw', 'jaw/chin'), ('tongue', 'tongue'), ('teeth', 'teeth'),
       ('ear', 'ear'), ('forehead', 'forehead/temple'), ('temple', 'forehead/temple'), ('head', 'head/neck'), ('neck', 'head/neck'), ('spine', 'head/neck')]
def region(n):
    s = n.lower()
    for k, r in REG:
        if k in s: return r
    return 'other'
pts = []                                    # [pos, region, bones]
for b in rig.data.bones:
    if not b.use_deform: continue
    r = region(b.name)
    if r == 'eyeball' and 'lid' not in b.name.lower(): pass
    for p in (b.head_local, b.tail_local):
        P = rig.matrix_world @ p
        for q in pts:
            if (q[0] - P).length < 2e-4: q[2].append(b.name); break
        else: pts.append([P.copy(), r, [b.name]])
# skin vs internal: distance to the face surface
me = face.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
MW = face.matrix_world
bvh = BVHTree.FromPolygons([MW @ v.co for v in me.vertices], [p.vertices[:] for p in me.polygons])
INTERNAL = {'eyeball', 'tongue', 'teeth', 'head/neck'}
rows = []
for P, r, bs in pts:
    loc, nrm, idx, d = bvh.find_nearest(P)
    internal = r in INTERNAL or d > 0.004
    rows.append({'p': [round(c, 5) for c in P], 'region': r, 'bones': sorted(set(bs)), 'skin_dist_mm': round(d * 1000, 2), 'internal': bool(internal)})
cnt = {}
for x in rows:
    k = ('내부 ' if x['internal'] else '') + x['region']; cnt[k] = cnt.get(k, 0) + 1
# ---- renders: workbench grey head, camera from landmarks
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'SINGLE'
sc.display.shading.single_color = (0.78, 0.78, 0.8); sc.render.resolution_x = sc.render.resolution_y = 900; sc.render.film_transparent = False
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.96, 0.96, 0.97)
for o in bpy.data.objects:
    if o.type == 'MESH': o.hide_render = o.name not in ('face', 'p2_brows')
    for md in getattr(o, 'modifiers', []):
        if md.type == 'ARMATURE': md.show_render = False
rig.hide_render = True
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]; cz = (top + LT[24][2]) / 2 + 0.06 * fh
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
cy = float(np.mean([LT[k][1] for k in LT])); look = Vector((0.0, cy, cz))
views = {}
for v, d, s in (('front', (0, -1, 0), 1.55 * fh), ('34', (0.72, -0.69, 0), 1.6 * fh), ('side', (1, 0, 0), 1.75 * fh)):
    co.location = look + Vector(d).normalized() * 1.0; co.rotation_euler = (look - co.location).to_track_quat('-Z', 'Y').to_euler()
    cam.ortho_scale = s; cam.clip_end = 10; bpy.context.view_layer.update()
    sc.render.filepath = os.path.join(OUT, f'points_{v}.png'); bpy.ops.render.render(write_still=True)
    vis = []
    for x in rows:
        P = Vector(x['p']); uv = world_to_camera_view(sc, co, P)
        dirv = (P - co.location).normalized(); hit = bvh.ray_cast(co.location, dirv)
        hidden = hit[0] is not None and (hit[0] - co.location).length < (P - co.location).length - 0.0015
        vis.append([round(uv.x, 5), round(1 - uv.y, 5), bool(hidden)])
    views[v] = vis
json.dump({'points': rows, 'views': views, 'counts': cnt, 'total': len(rows),
           'skin': sum(not x['internal'] for x in rows), 'internal': sum(x['internal'] for x in rows)},
          open(os.path.join(OUT, 'points.json'), 'w'), indent=0, ensure_ascii=False)
print('POINTS', json.dumps({'total': len(rows), 'skin': sum(not x['internal'] for x in rows), 'counts': cnt}, ensure_ascii=False))
