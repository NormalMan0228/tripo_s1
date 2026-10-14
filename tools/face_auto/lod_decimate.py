"""T6 · game LODs of the rigged face without reshaping it: collapse-decimate with symmetry, keep the shape keys.

The face is decimated in edit mode, where Blender carries shape-key layers through every edge collapse, so jaw and
viseme keys survive (no re-transfer). A vertex group locks only the cut edges themselves (eye openings, and the lip edge where
skin meets the mouth interior: the lid and mouth parts sit on them), so they stay exact while the rest decimates freely. For each ratio the LOD is measured against the original:
  surface deviation  both directions (LOD -> original, original -> LOD), mm, at rest and under every key at 100 %
  symmetry           mirror gap of the LOD face (x -> -x onto itself) next to the original's, and the share of LOD
                     vertices that have an exact mirror vertex (topological symmetry)
  skin_folds         skin faces turned > 60 deg away from the original surface at rest (pinches, notches), and faces a
                     key turns over where the original does not. Optional repair (LOD_REPAIR=n): the original
                     around each fold (3 mm) is locked and the decimation redone; at 5 % it moved the notch rather than removing it
  cuts               eye-opening and lip-seam boundary: how far the LOD boundary drifts from the original one
Writes <out>/lod_<pct>.blend (whole rig with the LOD face), <out>/qa_lod.json.
Usage: blender -b <rig_mouth.blend> -P lod_decimate.py -- <out_dir> [ratios=0.25,0.1,0.05,0.025]
"""
import bpy, bmesh, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
OUT = a[0]; RATIOS = [float(r) for r in (a[1] if len(a) > 1 else '0.25,0.1,0.05,0.025').split(',')]
os.makedirs(OUT, exist_ok=True)
SRC = bpy.data.filepath
face0 = bpy.data.objects['face']
KEYS = [k.name for k in face0.data.shape_keys.key_blocks[1:]]

def tris_of(me):
    me.calc_loop_triangles()
    return [tuple(t.vertices) for t in me.loop_triangles]

def key_coords(me, name=None):
    if name is None or not me.shape_keys:
        return np.array([tuple(v.co) for v in me.vertices])
    kb = me.shape_keys.key_blocks[name]
    return np.array([tuple(p.co) for p in kb.data])

def bvh(P, T):
    return BVHTree.FromPolygons([tuple(p) for p in P], T)

def one_way(P, tree, step=1):
    d = np.array([tree.find_nearest(Vector(p))[3] for p in P[::step]]) * 1000
    return d

def boundary(me):
    """cut edges: open boundaries (eye openings, neck) and the lip edge, where skin meets the mouth interior"""
    inner = {i for i, m in enumerate(me.materials) if m and m.name == 'mouth_inner'}
    bm = bmesh.new(); bm.from_mesh(me)
    E = [(e.verts[0].index, e.verts[1].index) for e in bm.edges
         if e.is_boundary or len({f.material_index in inner for f in e.link_faces}) == 2]
    bm.free(); return E

def seg_dist(P, A, B):
    """distance from every point of P to the nearest segment A[i]-B[i]"""
    out = np.full(len(P), np.inf)
    AB = B - A; L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    for s in range(0, len(P), 2000):
        p = P[s:s + 2000, None, :]
        t = np.clip(((p - A) * AB).sum(2) / L2, 0, 1)
        out[s:s + 2000] = np.sqrt(((A + t[..., None] * AB - p) ** 2).sum(2)).min(1)
    return out

# ---- original measurements
me0 = face0.data
P0 = key_coords(me0); T0 = tris_of(me0)
K0 = {k: key_coords(me0, k) for k in KEYS}; K0[None] = P0
tree0 = {k: bvh(K0[k], T0) for k in K0}
E0 = boundary(me0); bA0, bB0 = P0[[e[0] for e in E0]], P0[[e[1] for e in E0]]
# protect a narrow band along the cuts (eye openings, lip seam): weight 1 within NEAR mm, 0 beyond FAR mm
NEAR, FAR = [float(x) for x in os.environ.get('LOD_BAND', '0.05,0.5').split(',')]
FACTOR = float(os.environ.get('LOD_FACTOR', '10'))
d_cut = seg_dist(P0, bA0, bB0) * 1000
w_keep = np.clip((FAR - d_cut) / (FAR - NEAR), 0, 1)
# soft weight on the parts that move (any key moves the vertex > 0.2 mm) and around the eye openings: they keep more
# triangles than the still back of the head. SOFT = 0 turns this off.
SOFT = float(os.environ.get('LOD_SOFT', '0'))
moving = np.max([np.linalg.norm(K0[k] - P0, axis=1) for k in KEYS], axis=0) > 0.0002
w_keep = np.maximum(w_keep, SOFT * ((moving | (d_cut < 15)) & (w_keep < 1)))
chin_z = P0[:, 2].min(); face_band = (P0[:, 1] < np.percentile(P0[:, 1], 40))
def mirror_gap(P, tree, mask):
    Q = P[mask][::5]
    return np.array([tree.find_nearest(Vector((-p[0], p[1], p[2])))[3] for p in Q]) * 1000
g0 = mirror_gap(P0, tree0[None], face_band)
res = {'original': {'verts': len(P0), 'tris': len(T0), 'boundary_edges': len(E0),
                    'mirror_gap_mm': {'mean': round(float(g0.mean()), 3), 'p95': round(float(np.percentile(g0, 95)), 3)}}}
print('ORIG', res['original'])

def stats(d):
    return {'mean': round(float(d.mean()), 3), 'p95': round(float(np.percentile(d, 95)), 3), 'max': round(float(d.max()), 3)}

# original triangle normals per key, and which triangles a key itself turns over (inherited, not the LOD's fault)
def tri_normals(P, T):
    T = np.asarray(T); n = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-14)
N0 = {k: tri_normals(K0[k], T0) for k in K0}
flip0 = {k: (N0[k] * N0[None]).sum(1) < 0 for k in KEYS}

def decimate(r, w):
    bpy.ops.wm.open_mainfile(filepath=SRC)
    face = bpy.data.objects['face']
    vg = face.vertex_groups.new(name='lod_keep')
    for i in np.nonzero(w > 0)[0]: vg.add([int(i)], float(w[i]), 'REPLACE')
    for o in bpy.context.view_layer.objects: o.select_set(o is face)
    bpy.context.view_layer.objects.active = face
    face.active_shape_key_index = 0
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    face.vertex_groups.active_index = vg.index
    # weight 1 = locked (with invert + a high factor the weighted verts are never collapsed)
    bpy.ops.mesh.decimate(ratio=r, use_vertex_group=FACTOR > 0, vertex_group_factor=FACTOR, invert_vertex_group=os.environ.get('LOD_INVERT', '1') == '1',
                          use_symmetry=os.environ.get('LOD_SYM', '1') == '1', symmetry_axis='X')
    bpy.ops.object.mode_set(mode='OBJECT')
    face.vertex_groups.remove(face.vertex_groups['lod_keep'])
    return face.data

def find_folds(me):
    """skin faces of the LOD that (a) at rest turn > 60 deg away from the original surface under them, or
    (b) are turned over by a key where the original is not. Returns {key: [centroid at rest, ...]}"""
    inner = {i for i, m in enumerate(me.materials) if m and m.name == 'mouth_inner'}
    F = np.array([list(p.vertices)[:3] for p in me.polygons if p.material_index not in inner and len(p.vertices) == 3])
    Pr = key_coords(me); nr = tri_normals(Pr, F); C = Pr[F].mean(1)
    hits = [tree0[None].find_nearest(Vector(c)) for c in C]
    hn = np.array([h[1] for h in hits]); hi = np.array([h[2] for h in hits])
    out = {'rest': C[(nr * hn).sum(1) < 0.5]}
    for k in KEYS:
        nk = tri_normals(key_coords(me, k), F)
        out[k] = C[((nk * nr).sum(1) < 0) & ~flip0[k][hi]]
    return out

PASSES = int(os.environ.get('LOD_REPAIR', '0')); RADIUS = 3.0
for r in RATIOS:
    w = w_keep.copy(); log = []
    for it in range(PASSES + 1):
        me = decimate(r, w)
        folds = find_folds(me); bad = np.concatenate([v for v in folds.values() if len(v)] or [np.zeros((0, 3))])
        log.append({k: int(len(v)) for k, v in folds.items()})
        print('  pass', it, 'folds', log[-1])
        if not len(bad) or it == PASSES: break
        # protect the original around every fold and decimate again from the original
        for c in bad:
            near = np.linalg.norm(P0 - c, axis=1) * 1000 < RADIUS
            w[near] = 1.0
    face = bpy.data.objects['face']
    P = key_coords(me); T = tris_of(me)
    tr = bvh(P, T)
    q = {'ratio': r, 'verts': len(P), 'tris': len(T), 'repair_passes': log, 'protected_verts': int((w > 0).sum())}
    # surface deviation both ways, rest + keys
    dev = {}
    for k in [None] + KEYS:
        Pk = key_coords(me, k); trk = tr if k is None else bvh(Pk, T)
        P0k = K0[k]
        dev[k or 'rest'] = {'lod_to_orig': stats(one_way(Pk, tree0[k])), 'orig_to_lod': stats(one_way(P0k, trk, 3))}
    q['deviation_mm'] = dev
    q['skin_folds'] = {k: {'count': int(len(v)), 'at_mm': (v[:6] * 1000).round(1).tolist()} for k, v in folds.items()}
    g = mirror_gap(P, tr, P[:, 1] < np.percentile(P0[:, 1], 40))
    q['mirror_gap_mm'] = {'mean': round(float(g.mean()), 3), 'p95': round(float(np.percentile(g, 95)), 3)}
    from mathutils.kdtree import KDTree
    kd = KDTree(len(P))
    for i, p in enumerate(P): kd.insert(Vector(p), i)
    kd.balance(); dm = np.array([kd.find(Vector((-p[0], p[1], p[2])))[2] for p in P])
    q['mirror_vertex_share'] = round(float((dm < 5e-5).mean()), 3)
    E = boundary(me); bA, bB = P[[e[0] for e in E]], P[[e[1] for e in E]]
    bverts = P[sorted({i for e in E for i in e})]
    q['cuts'] = {'boundary_edges': len(E), 'drift_mm': stats(seg_dist(bverts, bA0, bB0) * 1000),
                 'orig_cut_to_lod_cut_mm': stats(seg_dist(P0[sorted({i for e in E0 for i in e})], bA, bB) * 1000)}
    # density near the cuts vs elsewhere (verts per cm^2 is overkill; share of verts within 12 mm of a cut)
    near = seg_dist(P, bA0, bB0) * 1000 < 12
    q['share_near_cuts'] = {'lod': round(float(near.mean()), 3), 'original': round(float((d_cut < 12).mean()), 3)}
    res['lod_%g' % (r * 100)] = q
    print('LOD', r, json.dumps({k: q[k] for k in ('verts', 'tris', 'mirror_gap_mm', 'mirror_vertex_share', 'cuts', 'share_near_cuts')}))
    print('   rest', dev['rest'], '\n   jaw', dev['jaw_open'])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'lod_%g.blend' % (r * 100)), compress=True)
json.dump(res, open(os.path.join(OUT, 'qa_lod.json'), 'w'), indent=1)
print('DONE')
