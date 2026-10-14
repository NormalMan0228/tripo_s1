"""Bind loose P2 pieces (brows, lashes …) to the face's shape keys so they follow every expression.

Tripo Smart Mesh P2 can return small separate pieces next to the head skin, e.g. 'p2_brows'. They carry no rig and no
shape keys, so after the bake they stay put while the skin under them moves (brows did not rise with browInnerUp).
Each piece vertex is tied to its nearest face triangle on the face Basis: barycentric foot point plus an offset in the
triangle's frame (edge, normal, normal x edge). For every face shape key the deformed triangle rebuilds the frame and the
vertex is placed by the same local offset, written as a shape key of the same name on the piece (relative to Basis, same
slider values). Pieces hidden for render are skipped unless named with --all.
QA (<out>_bind.json): per piece verts, max foot distance (how far the piece floats above the skin), rest error (Basis
rebuild must equal the piece, < 1e-4 mm) and the largest move per key against the skin's largest move nearby.
Usage: blender -b <arkit_b.blend> -P bind_pieces.py -- <out.blend> [piece names, default: visible p2_* meshes]
"""
import bpy, sys, os, json
import numpy as np
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(a[0]); NAMES = a[1:]
face = bpy.data.objects['face']; me = face.data
assert me.shape_keys, 'face has no shape keys'
kb = me.shape_keys.key_blocks; basis = kb[0]
me.calc_loop_triangles()
T = np.array([lt.vertices[:] for lt in me.loop_triangles], dtype=np.int64)
def co(block):
    X = np.empty(len(me.vertices) * 3); block.data.foreach_get('co', X); return X.reshape(-1, 3)
X0 = co(basis)
bvh = BVHTree.FromPolygons([tuple(p) for p in X0], [tuple(t) for t in T])

def frames(X, tri):
    """per triangle: origin p0, orthonormal frame (e1, n, e1 x n)."""
    p0, p1, p2 = X[tri[:, 0]], X[tri[:, 1]], X[tri[:, 2]]
    e1 = p1 - p0; e1 /= np.linalg.norm(e1, axis=1, keepdims=True) + 1e-12
    n = np.cross(p1 - p0, p2 - p0); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    e2 = np.cross(n, e1)
    return p0, p1, p2, np.stack([e1, n, e2], axis=1)            # (k, 3 axes, 3)

pieces = [bpy.data.objects[n] for n in NAMES] if NAMES else \
    [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('p2_') and not o.hide_render]
qa = {'pieces': {}}
for ob in pieces:
    assert ob.matrix_world.is_identity and face.matrix_world.is_identity, 'piece and face are expected in head space'
    pm = ob.data
    P = np.array([tuple(v.co) for v in pm.vertices])
    fi = np.empty(len(P), dtype=np.int64); dist = np.empty(len(P))
    for i, p in enumerate(P):
        _, _, idx, d = bvh.find_nearest(p); fi[i] = idx; dist[i] = d
    tri = T[fi]
    p0, p1, p2, F0 = frames(X0, tri)
    # barycentric foot point on the triangle plane
    v0, v1, v2 = p1 - p0, p2 - p0, P - p0
    d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
    den = d00 * d11 - d01 * d01 + 1e-18
    bv = (d11 * d20 - d01 * d21) / den; bw = (d00 * d21 - d01 * d20) / den; bu = 1 - bv - bw
    foot = bu[:, None] * p0 + bv[:, None] * p1 + bw[:, None] * p2
    local = np.einsum('kij,kj->ki', F0, P - foot)             # offset in the triangle frame
    def place(X):
        q0, q1, q2, Fk = frames(X, tri)
        f = bu[:, None] * q0 + bv[:, None] * q1 + bw[:, None] * q2
        return f + np.einsum('kij,ki->kj', Fk, local)
    rest_err = float(np.abs(place(X0) - P).max() * 1000)
    if pm.shape_keys:
        for k in list(pm.shape_keys.key_blocks)[::-1]: ob.shape_key_remove(k)
    ob.shape_key_add(name=basis.name, from_mix=False)
    moves = {}
    for k in kb[1:]:
        Xk = co(k)
        if np.abs(Xk[np.unique(tri)] - X0[np.unique(tri)]).max() < 1e-7: continue   # key does not touch the skin under the piece
        Pk = place(Xk); nk = ob.shape_key_add(name=k.name, from_mix=False)
        nk.data.foreach_set('co', Pk.ravel()); nk.slider_min, nk.slider_max = k.slider_min, k.slider_max
        moves[k.name] = [round(float(np.linalg.norm(Pk - P, axis=1).max() * 1000), 2),
                         round(float(np.linalg.norm(Xk[np.unique(tri)] - X0[np.unique(tri)], axis=1).max() * 1000), 2)]
    pm.update()
    qa['pieces'][ob.name] = {'verts': len(P), 'foot_dist_max_mm': round(float(dist.max() * 1000), 3),
                             'rest_err_mm': round(rest_err, 6), 'keys': len(moves), 'move_mm_piece_vs_skin': moves}
qa['ok'] = all(v['rest_err_mm'] < 1e-4 for v in qa['pieces'].values())
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(qa, open(os.path.splitext(OUT)[0] + '_bind.json', 'w'), indent=1)
print('BIND', json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'move_mm_piece_vs_skin'} for k, v in qa['pieces'].items()}), 'ok', qa['ok'])
