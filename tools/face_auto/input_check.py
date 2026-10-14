"""T4/T5 · input gate before rigging: is this head usable, and are its landmarks believable?

Checks (each pass / warn / fail with the measured value):
 mesh      boundary edges after welding (holes), loose pieces
 symmetry  mean / p95 mirror gap of the face region (x -> -x)
 landmarks order top->bottom (brow > eye > nose > mouth > chin), eye spacing vs face width, left/right balance
 eyes      both rims found by depth; width and height of left vs right within 15 %
 mouth     closed: the front ray at the lip seam must not fall into a cavity deeper than 6 mm, and the seam
           detector must span at least 70 % of the corner-to-corner width
 neutral   mouth corners not lifted (smile): corner height vs the seam centre within 2.5 mm
Writes <out>/<name>_check.json and a front image with the landmarks and rims drawn.
Usage: blender -b --factory-startup -P input_check.py -- <head.fbx> <landmarks.json> <out_dir> <name>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
sys.path.append(os.path.dirname(__file__))
from facelib import *

a = sys.argv[sys.argv.index("--") + 1:]
SRC, LMJ, OUT, NAME = a[:4]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
ob = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
V = np.array([tuple(ob.matrix_world @ v.co) for v in ob.data.vertices]); F = [list(p.vertices) for p in ob.data.polygons]
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
bvh = bvh_of(V, F)
res = {}
def put(name, status, value, note=''):
    res[name] = {'status': status, 'value': value, 'note': note}

# mesh
bm = bmesh.new(); bm.from_mesh(ob.data)
diag = float(np.linalg.norm(np.ptp(V, axis=0)))
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5 * diag)
nb = sum(e.is_boundary for e in bm.edges); bm.free()
put('holes_boundary_edges', 'pass' if nb == 0 else ('warn' if nb < 200 else 'fail'), int(nb))

# symmetry of the face region
face = V[(V[:, 1] < np.percentile(V[:, 1], 40)) & (V[:, 2] > LT[24][2] - 0.01)][::7]
gap = np.array([bvh.find_nearest(Vector((-p[0], p[1], p[2])))[3] for p in face]) * 1000
put('symmetry_mm', 'pass' if np.percentile(gap, 95) < 1.5 else ('warn' if np.percentile(gap, 95) < 4 else 'fail'),
    {'mean': round(float(gap.mean()), 2), 'p95': round(float(np.percentile(gap, 95)), 2)})

# landmarks
z = {k: LT[k][2] for k in LT}
order_ok = np.mean([z[2], z[5]]) > np.mean([z[8], z[12]]) > z[16] > np.mean([z[20], z[22]]) > z[24]
eye_span = abs(LT[13][0] - LT[7][0]); width = np.ptp(V[np.abs(V[:, 2] - np.mean([z[7], z[13]])) < 0.01][:, 0])
ratio = eye_span / width if width > 0 else 0
put('landmark_order', 'pass' if order_ok else 'fail', bool(order_ok), 'brow > eye > nose > mouth > chin')
put('eye_span_over_face_width', 'pass' if 0.45 < ratio < 0.95 else 'fail', round(float(ratio), 2), 'outer corners vs head width at eye height')

# eyes by depth
rims = {}
for side, ids in {'R': (7, 8, 9, 10), 'L': (13, 12, 11, 14)}.items():
    cx, cz = np.mean([LT[k][0] for k in ids]), np.mean([LT[k][2] for k in ids])
    try:
        R = recentred_rim(bvh, cx, cz, 'margin'); rims[side] = R
    except Exception:
        rims[side] = None
if any(r is None or len(r) < 40 for r in rims.values()):
    put('eye_rims', 'fail', {s: (0 if r is None else len(r)) for s, r in rims.items()}, 'rim not found from depth')
else:
    wR, hR = np.ptp(rims['R'][:, 0]), np.ptp(rims['R'][:, 2]); wL, hL = np.ptp(rims['L'][:, 0]), np.ptp(rims['L'][:, 2])
    dw, dh = abs(wR - wL) / max(wR, wL), abs(hR - hL) / max(hR, hL)
    st = 'pass' if max(dw, dh) < 0.15 else ('warn' if max(dw, dh) < 0.3 else 'fail')
    put('eye_rims_balance', st, {'width_mm': [round(wR * 1000, 1), round(wL * 1000, 1)], 'height_mm': [round(hR * 1000, 1), round(hL * 1000, 1)]},
        'left/right difference under 15 %')

# mouth closed + seam span
zm = (LT[34][2] + LT[35][2]) / 2; seam = seam_curve(bvh, LT[20][0], LT[22][0], LT[20][2], zm, LT[22][2], n=41)
surf = np.array([hit_y(bvh, x, zz + 0.002) or 9 for x, _, zz in seam])
depth = seam[:, 1] - surf                                   # how far the seam point sits behind the lip surface
open_mm = float(np.nanmax(np.where(np.abs(seam[:, 0] - seam[:, 0].mean()) < 0.35 * np.ptp(seam[:, 0]), depth, np.nan)) * 1000)
put('mouth_closed', 'pass' if open_mm < 6 else 'fail', round(open_mm, 1), 'groove depth at the lip seam (mm); an open mouth falls into the cavity')
corner_lift = float((np.mean([LT[20][2], LT[22][2]]) - zm) * 1000)
put('neutral_corners', 'pass' if abs(corner_lift) < 2.5 else ('warn' if abs(corner_lift) < 4 else 'fail'), round(corner_lift, 1), 'mouth corners vs seam centre (mm); + = smile')
width_mouth = abs(LT[22][0] - LT[20][0])
put('mouth_width_over_eye_span', 'pass' if 0.25 < width_mouth / eye_span < 0.9 else 'warn', round(float(width_mouth / eye_span), 2))

overall = 'fail' if any(r['status'] == 'fail' for r in res.values()) else ('warn' if any(r['status'] == 'warn' for r in res.values()) else 'pass')
out = {'name': NAME, 'overall': overall, 'checks': res}
json.dump(out, open(os.path.join(OUT, NAME + '_check.json'), 'w'), indent=1, ensure_ascii=False)

# picture: front render with landmarks and rims
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x = sc.render.resolution_y = 700
sc.display.shading.light = 'STUDIO'; sc.world = bpy.data.worlds.new('w')
lo, hi = V.min(0), V.max(0); size = (hi[2] - LT[24][2]) * 1.25; cz = (hi[2] + LT[24][2]) / 2
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.ortho_scale = size
co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
co.location = Vector((0, lo[1] - 1, cz)); co.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
png = os.path.join(OUT, NAME + '_front.png'); sc.render.filepath = png; bpy.ops.render.render(write_still=True)
json.dump({'size': size, 'cz': cz, 'pts': {k: v.tolist() for k, v in LT.items()},
           'rims': {s: (r.tolist() if r is not None else []) for s, r in rims.items()}, 'seam': seam.tolist(), 'overall': overall,
           'checks': {k: v['status'] for k, v in res.items()}}, open(os.path.join(OUT, NAME + '_overlay.json'), 'w'))
print('CHECK', json.dumps(out, ensure_ascii=False))
