"""겹침생성 · lock left/right symmetry on a head built on a symmetric base (sym_mirror.py).

Every vertex of 'face' (and the other meshes) is paired with the vertex nearest its mirror image (x -> -x);
centre vertices pair with themselves. The organ builders run the same steps on mirrored input, so pairs match to
float noise; this step makes them exact and reports what it fixed.
  mesh     positions: right = mirror(left), centre x = 0 (also the shape-key basis)
  weights  vertex groups: right vertex gets its partner's weights with .L/.R, _L/_R, Left/Right swapped;
           centre vertices get the mean of a group and its mirror group
  keys     shape keys: ...Left / ...Right pairs: Right = mirror of Left; unpaired keys are averaged with their
           own mirror; QA = mirror error p95 (% of the largest move) before and after
Usage: blender -b <in.blend> -P sym_lock.py -- <mesh|weights|keys> <out.blend>
"""
import bpy, sys, os, json, re
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index('--') + 1:]
MODE, OUT = a[0], os.path.abspath(a[1])
MX = np.array([-1.0, 1.0, 1.0])
qa = {'mode': MODE}

def basis_co(o):
    me = o.data
    if me.shape_keys: return np.array([tuple(d.co) for d in me.shape_keys.key_blocks[0].data])
    return np.array([tuple(v.co) for v in me.vertices])

def partners(X, tol=0.0005):
    kd = KDTree(len(X))
    for i, p in enumerate(X): kd.insert(Vector(tuple(p)), i)
    kd.balance()
    part = np.full(len(X), -1); dist = np.zeros(len(X))
    for i, p in enumerate(X):
        co, j, d = kd.find(Vector(tuple(p * MX))); part[i] = j; dist[i] = d
    return part, dist

def pair_up(o, X, tol=0.0005):
    """mirror partners; vertices that share a position (the closed lip slit: its upper and lower halves) are paired
    by their ring index and parameter instead (mirror of u is 0.5 - u)"""
    part, dist = partners(X, tol)
    me = o.data
    if 'mouth_ring' in me.attributes and 'mouth_u' in me.attributes:
        rg = np.array([d.value for d in me.attributes['mouth_ring'].data]); uu = np.array([d.value for d in me.attributes['mouth_u'].data]).astype(float)
        g = o.vertex_groups.get('mouth_bag')
        if g is not None:                                   # bag vertices were made ring by ring in slit (u) order, cap last
            bag = sorted(v.index for v in me.vertices if any(q.group == g.index for q in v.groups))
            Mslit = int(round(1.0 / np.min(np.diff(np.unique(np.round(uu[(rg > 0) & (uu >= 0) & ~np.isin(np.arange(len(rg)), bag)], 6))))))
            if len(bag) > 2 and np.ptp(uu[bag[:-1]]) == 0:       # old bags stored no u: rebuild it from the order
                for j, vi in enumerate(bag[:-1]): rg[vi] = 1000 + j // Mslit; uu[vi] = (j % Mslit) / Mslit
        _, inv, cnt = np.unique(np.round(X, 7), axis=0, return_inverse=True, return_counts=True)
        sel = np.where((rg > 0) & (uu >= 0) & (cnt[inv.ravel()] > 1))[0]      # only vertices that share a position
        if len(sel):
            Mr = int(round(1.0 / np.min(np.diff(np.unique(np.round(uu[sel], 6)))))) if len(np.unique(uu[sel])) > 1 else 1
            reg = Mr <= 4096 and float(np.abs(uu[sel] * Mr - np.rint(uu[sel] * Mr)).max()) < 1e-3
            if reg:                                         # ring mouth (organ_mouth): u on a column grid
                key = {(int(rg[i]), int(round(uu[i] * Mr)) % Mr): i for i in sel}
                for i in sel:
                    j = key.get((int(rg[i]), int(round((0.5 - uu[i]) * Mr)) % Mr))
                    if j is not None: part[i] = j; dist[i] = np.linalg.norm(X[j] - X[i] * MX)
            else:                                           # irregular slit (loop_organs): same ring, at the mirror position,
                for i in sel:                               # mirrored u nearest on the same lip
                    tu = (0.5 - uu[i]) % 1.0; c = sel[(rg[sel] == rg[i]) & (np.linalg.norm(X[sel] - X[i] * MX, axis=1) < tol)]
                    if not len(c): continue
                    up_t = tu <= 0.5; ok = (uu[c] <= 0.5) if up_t else ((uu[c] >= 0.5) | (uu[c] == 0))
                    du = np.abs(uu[c] - tu); du = np.minimum(du, 1 - du); du[~ok] += 10
                    j = int(c[np.argmin(du)]); part[i] = j; dist[i] = np.linalg.norm(X[j] - X[i] * MX)
    ok = (dist < tol) & (part[part] == np.arange(len(X)))
    return part, dist, ok

def swap_name(n):
    for a_, b_ in (('.L', '.R'), ('_L_', '_R_'), ('Left', 'Right'), ('_L', '_R')):
        if a_ in n: return n.replace(a_, '\0').replace(b_, a_).replace('\0', b_)
        if b_ in n: return n.replace(b_, '\0').replace(a_, b_).replace('\0', a_)
    return n

meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name in ('face', 'eyes', 'teeth_up', 'teeth_lo', 'tongue')]
for o in meshes:
    X = basis_co(o); part, dist, ok = pair_up(o, X)
    rep = {'verts': len(X), 'unpaired': int((~ok).sum()), 'pair_gap_p95_mm': round(float(np.percentile(dist, 95) * 1000), 4), 'pair_gap_max_mm': round(float(dist[ok].max() * 1000) if ok.any() else 0, 4)}
    left = ok & (X[:, 0] > 1e-7); centre = ok & (part == np.arange(len(X)))
    if MODE == 'mesh':
        Y = X.copy(); Y[part[left]] = X[left] * MX; Y[centre, 0] = 0.0
        rep['moved_max_mm'] = round(float(np.linalg.norm(Y - X, axis=1).max() * 1000), 4)
        o.data.vertices.foreach_set('co', Y.ravel())
        if o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks:
                K = np.array([tuple(d.co) for d in kb.data]); K = K + (Y - X); kb.data.foreach_set('co', K.ravel())
        o.data.update()
    elif MODE == 'weights':
        names = [g.name for g in o.vertex_groups]; idx = {n: i for i, n in enumerate(names)}
        if not names: qa[o.name] = rep; continue
        Wt = np.zeros((len(X), len(names)), np.float32)
        for v in o.data.vertices:
            for g in v.groups: Wt[v.index, g.group] = g.weight
        perm = np.array([idx.get(swap_name(n), i) for i, n in enumerate(names)], dtype=int)
        W2 = Wt.copy()
        li = np.where(left)[0]; W2[part[li]] = Wt[li][:, perm]
        ci = np.where(centre)[0]; W2[ci] = (Wt[ci] + Wt[ci][:, perm]) / 2
        rep['weight_change_max'] = round(float(np.abs(W2 - Wt).max()), 4)
        for i, n in enumerate(names):
            g = o.vertex_groups[n]; col = W2[:, i]; nz = np.nonzero(col > 1e-6)[0]; z = np.nonzero((col <= 1e-6) & (Wt[:, i] > 1e-6))[0]
            if len(z): g.remove(z.tolist())
            for vi in nz: g.add([int(vi)], float(col[vi]), 'REPLACE')
    elif MODE == 'keys' and o.data.shape_keys:
        kbs = o.data.shape_keys.key_blocks; D = {kb.name: np.array([tuple(d.co) for d in kb.data]) - X for kb in kbs[1:]}
        def mirr(Dk):                                        # displacement field seen in the mirror
            M_ = np.zeros_like(Dk); M_[part[ok]] = Dk[ok] * MX; return M_
        def err(Dl, Dr):
            mx = max(np.linalg.norm(Dl, axis=1).max(), 1e-9); act = np.linalg.norm(Dl, axis=1) > 0.05 * mx
            return round(float(np.percentile(np.linalg.norm(mirr(Dl) - Dr, axis=1)[part[act & ok]] if (act & ok).any() else [0], 95) / mx * 100), 2)
        before, after = {}, {}
        for n in list(D):
            if n.endswith('Left') and n[:-4] + 'Right' in D:
                r = n[:-4] + 'Right'; before[n] = err(D[n], D[r]); D[r] = mirr(D[n]); after[n] = err(D[n], D[r])
            elif not (n.endswith('Right') and n[:-5] + 'Left' in D):
                Dm = (D[n] + mirr(D[n])) / 2; Dm[centre, 0] = 0.0; before[n] = err(D[n], D[n]); D[n] = Dm; after[n] = err(D[n], D[n])
        for kb in kbs[1:]: kb.data.foreach_set('co', (X + D[kb.name]).ravel())
        rep['mirror_err_p95_pct_before_median'] = round(float(np.median(list(before.values()))), 2) if before else None
        rep['mirror_err_p95_pct_after_max'] = round(float(max(after.values())), 2) if after else None
    qa[o.name] = rep
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(qa, open(os.path.splitext(OUT)[0] + '_symlock.json', 'w'), indent=1)
print('SYMLOCK', json.dumps(qa))
