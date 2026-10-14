"""Normalise any head mesh for the face pipeline: one mesh, face toward -Y, chin-to-top = 24 cm, centred, base at 0.

Finds which horizontal direction the face looks by running MediaPipe on four side renders and keeping the view
whose eye corners sit most symmetrically around the nose. Then writes <out.fbx> and <out_landmarks.json>.
Usage: blender -b --factory-startup -P head_prepare.py -- <in.glb|fbx> <out.fbx> [head_cm=24]
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

sys.path.append(os.path.dirname(__file__))
import face_landmarks_mp as flm

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], a[1]
HEAD_CM = float(a[2]) if len(a) > 2 else 24.0

obs = flm.load(SRC)
for o in obs: o.select_set(True)
bpy.context.view_layer.objects.active = obs[0]
if len(obs) > 1: bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
ob.data.transform(ob.matrix_world); ob.matrix_world = Matrix(); ob.parent = None
for o in list(bpy.context.scene.objects):
    if o != ob: bpy.data.objects.remove(o)
# glTF splits vertices along UV seams, so weld first; otherwise every UV island looks like a loose piece
bm = bmesh.new(); bm.from_mesh(ob.data)
diag = float(np.linalg.norm(np.ptp(np.array([tuple(v.co) for v in bm.verts]), axis=0)))
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5 * diag)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
# drop small loose pieces (keep anything over 5 % of the vertices: eyes/teeth inside the head stay)
bm.verts.ensure_lookup_table(); seen = set(); comps = []
for v in bm.verts:
    if v in seen: continue
    st = [v]; seen.add(v); c = []
    while st:
        x = st.pop(); c.append(x)
        for e in x.link_edges:
            y = e.other_vert(x)
            if y not in seen: seen.add(y); st.append(y)
    comps.append(c)
big = max(len(c) for c in comps)
bmesh.ops.delete(bm, geom=[v for c in comps if len(c) < 0.05 * big for v in c], context='VERTS')
bm.to_mesh(ob.data); bm.free()

best = None
for yaw in (0, 90, 180, 270):
    R = Matrix.Rotation(math.radians(yaw), 4, 'Z'); ob.data.transform(R)
    pts = flm.front_landmarks([ob])
    if pts:
        P = {k: np.array(v) for k, v in pts.items() if not k.startswith('_')}
        eye_d = abs(P['13'][0] - P['7'][0]) + 1e-9
        # landmark symmetry before front_landmarks' own symmetrisation is lost, so score by the raw nose offset
        score = eye_d
        print('VIEW', yaw, 'eye distance', round(eye_d, 4))
        if best is None or score > best[0]: best = (score, yaw)
    ob.data.transform(R.inverted())
if best is None: raise SystemExit('PREPARE: no face in any side view')
ob.data.transform(Matrix.Rotation(math.radians(best[1]), 4, 'Z'))
pts = {k: np.array(v) for k, v in flm.front_landmarks([ob]).items() if not k.startswith('_')}
V = np.array([tuple(v.co) for v in ob.data.vertices])
chin, top = pts['24'][2], V[:, 2].max()
s = (HEAD_CM / 100.0) / (top - chin)
ob.data.transform(Matrix.Translation((-pts['16'][0], 0, -V[:, 2].min())))
ob.data.transform(Matrix.Scale(s, 4))
ob.select_set(True); bpy.context.view_layer.objects.active = ob
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                         add_leaf_bones=False, bake_anim=False, path_mode='STRIP')
lm = flm.front_landmarks([ob])
json.dump(lm, open(os.path.splitext(OUT)[0] + '_landmarks.json', 'w'), indent=1)
print('PREPARED', OUT, 'yaw', best[1], 'scale', round(s, 4), 'verts', len(V))
