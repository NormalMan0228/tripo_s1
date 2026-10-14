"""Per-part UV maps for a method-1 face asset (texture step 1 of 3: uv_parts -> bake_ref_texture -> tex_assign).

Parts and their UV ('uv_tex', made active for render and export):
  skin   'face'  seams where the eye never looks: the back of the head (crown to nape, on the midline), a loop
                 behind each ear (ear = its own island, see EARS below) and the mouth cavity (own island, cut on the
                 skin / 'mouth_inner' material edge). The eye openings (with their tuck rings) and the nostrils are
                 holes of the main island, so the lid tuck rings and the inner lip roll lie at the island's inner
                 edges. Unwrap = Blender's Minimum Stretch (SLIM) with an importance weight on the face, so the face
                 gets more texels than the skull and neck (texel-density emphasis without UDIMs). The main island
                 is turned upright (forehead up) before packing.
  eyes   'eyes'  per eyeball: azimuthal equal-area map (radius sin(theta/2)) about the forward axis (-y) through C
                 (eyes_eyes.json), left eye in the left half, right eye in the right half (one 2:1 texture). Works
                 for P2 eyeball pieces and for a UV-sphere eyeball alike (only C and the vertex directions are used).
  brows  'p2_brows' (if present) front projection into the brow crop of the front image (bake_ref_texture
                 writes the crop with the same box, see brows_box in mesh_brows.npz).
  teeth  'teeth_up' / 'teeth_lo' cylindrical about the arch: u = angle around the arch, v = gum line (0) to
                 biting edge (1); teeth faces in the left half, gum faces in the right half of one 2:1 texture.
  tongue 'tongue' top-down planar (x, y).
Every part also gets mesh_<part>.npz for the baker: rest-pose positions (shape key 0), smooth normals,
triangles, triangle UVs, material per triangle and the face's ring attributes.
EARS: the ear is found as the part of the side of the head that a heavy smoothing pulls in most (the auricle
stands off the skull); the seam is the loop where that region meets the skull. If no clear ear is found the ear
stays on the main island (reported).
Usage: blender -b <arkit_b.blend> -P uv_parts.py -- <landmarks.json> <eyes_eyes.json | eyes_meta.json> <out_dir> [--ears]
Writes <out_dir>/uv.blend, <out_dir>/mesh_<part>.npz, <out_dir>/uv_qa.json
"""
import bpy, bmesh, sys, os, json, heapq, math
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]
LMJ, EJ, OUT = a[0], a[1], os.path.abspath(a[2])
EARS = '--ears' in a
os.makedirs(OUT, exist_ok=True)
LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
# eyes: loop_organs' eyes_eyes.json ({'eyes': {L, R}}) or eye_fit_ref's eyes_meta.json ({L, R} with iris_dir,
# iris_radius_deg): C (and the iris, when given) are taken from it, never re-detected from an older eyeball
_EJ = json.load(open(EJ)) if os.path.exists(EJ) else {}
EYES = _EJ['eyes'] if 'eyes' in _EJ else {k: v for k, v in _EJ.items() if k in ('L', 'R')}
qa = {}
UVN = 'uv_tex'


def rest_co(o):
    me = o.data
    src = me.shape_keys.key_blocks[0].data if me.shape_keys else me.vertices
    X = np.array([tuple(d.co) for d in src])
    M = np.array(o.matrix_world)
    return X @ M[:3, :3].T + M[:3, 3]


def smooth_normals(X, F):
    n = np.zeros_like(X)
    for f in F:
        for k in range(1, len(f) - 1):
            c = np.cross(X[f[k]] - X[f[0]], X[f[k + 1]] - X[f[0]])
            n[f[0]] += c; n[f[k]] += c; n[f[k + 1]] += c
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def uv_layer(o):
    me = o.data
    for u in list(me.uv_layers):
        if u.name in (UVN,): me.uv_layers.remove(u)
    uv = me.uv_layers.new(name=UVN)
    me.uv_layers.active = uv; uv.active_render = True
    return uv


def export(o, part, extra=None):
    """rest positions, normals, triangles (vertex ids), triangle uvs, material per triangle (+ ring attributes)"""
    me = o.data; me.calc_loop_triangles()
    X = rest_co(o); F = [list(p.vertices) for p in me.polygons]
    uvd = np.array([tuple(l.uv) for l in me.uv_layers[UVN].data])
    T = np.array([tuple(t.vertices) for t in me.loop_triangles], np.int32)
    TL = np.array([tuple(t.loops) for t in me.loop_triangles], np.int32)
    TM = np.array([t.material_index for t in me.loop_triangles], np.int16)
    d = dict(V=X.astype(np.float64), N=smooth_normals(X, F), T=T, TUV=uvd[TL].astype(np.float64), TM=TM)
    for n in ('eye_ring', 'eye_u', 'mouth_ring', 'mouth_u'):
        if n in me.attributes: d[n] = np.array([v.value for v in me.attributes[n].data])
    d['mat_names'] = np.array([m.name if m else '' for m in me.materials])
    if extra: d.update(extra)
    np.savez_compressed(os.path.join(OUT, f'mesh_{part}.npz'), **d)


def uv_stats(o, scale_px=4096, region=None):
    """texel density (texture px per mm at scale_px) and angle distortion per triangle"""
    me = o.data; me.calc_loop_triangles(); X = rest_co(o)
    uvd = np.array([tuple(l.uv) for l in me.uv_layers[UVN].data])
    T = np.array([tuple(t.vertices) for t in me.loop_triangles]); TL = np.array([tuple(t.loops) for t in me.loop_triangles])
    P = X[T]; U = uvd[TL]
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    a3 = np.linalg.norm(np.cross(e1, e2), axis=1) / 2
    f1, f2 = U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]
    a2 = (f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0]) / 2
    ok = a3 > 1e-12
    dens = np.sqrt(np.abs(a2[ok]) / a3[ok]) * scale_px / 1000.0          # px per mm
    # angle distortion: singular values of the 2x2 map from a local 3D frame to uv
    ex = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
    nn = np.cross(e1, e2); ey = np.cross(nn, ex); ey /= np.maximum(np.linalg.norm(ey, axis=1, keepdims=True), 1e-12)
    p1 = np.c_[np.sum(e1 * ex, 1), np.zeros(len(e1))]; p2 = np.c_[np.sum(e2 * ex, 1), np.sum(e2 * ey, 1)]
    Pm = np.stack([p1, p2], 2); Um = np.stack([f1, f2], 2)
    with np.errstate(all='ignore'):
        J = Um[ok] @ np.linalg.inv(Pm[ok])
        sv = np.linalg.svd(J, compute_uv=False); ratio = sv[:, 0] / np.maximum(sv[:, 1], 1e-12)
    flips = int((a2[ok] < 0).sum()); flips = min(flips, int(ok.sum()) - flips)  # orientation may be mirrored as a whole
    res = {'px_per_mm_median': round(float(np.median(dens)), 2), 'px_per_mm_p5': round(float(np.percentile(dens, 5)), 2),
           'px_per_mm_p95': round(float(np.percentile(dens, 95)), 2), 'angle_ratio_median': round(float(np.median(ratio)), 3),
           'angle_ratio_p95': round(float(np.percentile(ratio, 95)), 3), 'flipped_tris': flips,
           'uv_area_used': round(float(np.abs(a2).sum()), 3)}
    if region is not None:
        r = region[T].all(1)[ok]
        if r.any(): res['face_px_per_mm_median'] = round(float(np.median(dens[r])), 2)
        if (~r).any(): res['rest_px_per_mm_median'] = round(float(np.median(dens[~r])), 2)
    return res


def select_only(o):
    for ob in bpy.context.view_layer.objects: ob.select_set(False)
    o.hide_set(False); o.hide_viewport = False
    o.select_set(True); bpy.context.view_layer.objects.active = o


def dijkstra(bm, X, src, targets, cost):
    dist = {src: 0.0}; prev = {}; pq = [(0.0, src)]; targets = set(targets)
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e30): continue
        if u in targets:
            path = [u]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path[::-1]
        for e in bm.verts[u].link_edges:
            w = e.other_vert(bm.verts[u]).index
            nd = d + cost(u, w)
            if nd < dist.get(w, 1e30): dist[w] = nd; prev[w] = u; heapq.heappush(pq, (nd, w))
    return []


def mark_path(bm, path):
    n = 0
    for u, w in zip(path, path[1:]):
        e = bm.edges.get((bm.verts[u], bm.verts[w]))
        if e: e.seam = True; n += 1
    return n


def boundary_loops(bm):
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
            i, j = e.verts[0].index, e.verts[1].index; adj.setdefault(i, []).append(j); adj.setdefault(j, []).append(i)
    seen, loops = set(), []
    for s in adj:
        if s in seen: continue
        comp, st = [], [s]
        while st:
            v = st.pop()
            if v in seen: continue
            seen.add(v); comp.append(v); st += adj[v]
        loops.append(comp)
    return loops


# =============================================================== skin
face = bpy.data.objects['face']; me = face.data
X = rest_co(face); Fp = [list(p.vertices) for p in me.polygons]; NV = len(X)
Nrm = smooth_normals(X, Fp)
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
for e in bm.edges: e.seam = False
z_chin, z_brow = LT[24][2], (LT[2][2] + LT[5][2]) / 2
eye_w = abs(LT[13][0] - LT[7][0]); fh = z_brow - z_chin
head = X[:, 2] > z_chin - 0.1 * fh
W_head = np.ptp(X[head, 0]); y_mid = (X[head, 1].min() + X[head, 1].max()) / 2
seams = {}
# -- mouth cavity: own island (skin | mouth_inner edge)
ci = next((i for i, m in enumerate(me.materials) if m and m.name in ('mouth_inner', 'ref_mouth')), None)
n_cav = 0
if ci is not None:
    for e in bm.edges:
        fs = e.link_faces
        if len(fs) == 2 and (fs[0].material_index == ci) != (fs[1].material_index == ci): e.seam = True; n_cav += 1
seams['cavity_edges'] = n_cav
# -- back seam: crown -> nape along the midline, behind the ears
loops = boundary_loops(bm)
neck = max(loops, key=len)                                    # the bust / neck cut is the longest boundary
crown_c = np.nonzero(np.abs(X[:, 0]) < 0.03 * W_head)[0]
crown = int(crown_c[np.argmax(X[crown_c, 2])])
neckv = np.array(neck)
nape = int(neckv[np.argmax(X[neckv, 1] - 3 * np.abs(X[neckv, 0]))])
def back_cost(u, w):
    m = (X[u] + X[w]) / 2; L = np.linalg.norm(X[u] - X[w])
    return L * (1 + 40 * abs(m[0]) / W_head) * (25 if m[1] < y_mid else 1)
bpath = dijkstra(bm, X, crown, [nape], back_cost)
seams['back_edges'] = mark_path(bm, bpath)

# -- ears: the auricle stands off the skull. Smooth the head hard (umbrella steps) and take the side vertices
# that moved inward the most; grow/shrink to a clean region per side; seam = region border.
ear_info = {}
if EARS:
    nb = [[] for _ in range(NV)]
    for e in bm.edges: i, j = e.verts[0].index, e.verts[1].index; nb[i].append(j); nb[j].append(i)
    ii = np.repeat(np.arange(NV), [len(n) for n in nb]); jj = np.concatenate([np.array(n, int) for n in nb])
    deg = np.bincount(ii, minlength=NV).astype(float)
    S = X.copy()
    for _ in range(120):
        acc = np.zeros_like(S); np.add.at(acc, ii, S[jj]); S = 0.5 * S + 0.5 * acc / np.maximum(deg, 1)[:, None]
    disp = X - S
    lateral = np.sign(X[:, 0]) * disp[:, 0]                     # outward (sideways) stand-off
    z_ear_lo, z_ear_hi = LT[24][2] + 0.15 * fh, z_brow + 0.15 * fh
    side_zone = (np.abs(X[:, 0]) > 0.30 * W_head) & (X[:, 2] > z_ear_lo) & (X[:, 2] < z_ear_hi) & \
                (X[:, 1] > LT[16][1] + 0.25 * (y_mid - LT[16][1]))
    for sgn, nm in ((1, 'L'), (-1, 'R')):
        zone = side_zone & (np.sign(X[:, 0]) == sgn)
        if zone.sum() < 20: ear_info[nm] = 'no side zone'; continue
        thr = np.percentile(lateral[zone], 75)
        seed = zone & (lateral > max(thr, 0.25 * lateral[zone].max()))
        # biggest connected seed blob
        lab = -np.ones(NV, int); best = []
        for s in np.nonzero(seed)[0]:
            if lab[s] >= 0: continue
            comp, st = [], [s]; lab[s] = s
            while st:
                v = st.pop(); comp.append(v)
                for w in nb[v]:
                    if seed[w] and lab[w] < 0: lab[w] = s; st.append(w)
            if len(comp) > len(best): best = comp
        reg = np.zeros(NV, bool); reg[best] = True
        # close holes: grow 2 rings, shrink 1 ring, then fill enclosed pockets
        for _ in range(2):
            g = reg.copy(); g[jj[reg[ii]]] = True; reg = g & side_zone | reg
        for _ in range(1):
            g = reg.copy(); bad = np.zeros(NV, bool); np.logical_or.at(bad, ii, ~reg[jj]); reg = reg & ~bad if reg.sum() > 50 else reg
        # fill: vertices not reachable from outside the zone without crossing the region
        out_ = np.zeros(NV, bool); st = [int(v) for v in np.nonzero(~side_zone)[0][:1]]
        for v in st: out_[v] = True
        while st:
            v = st.pop()
            for w in nb[v]:
                if not out_[w] and not reg[w]: out_[w] = True; st.append(w)
        reg = reg | ~out_
        n_reg = int(reg.sum())
        ext = np.ptp(X[reg], 0) if n_reg else np.zeros(3)
        okz = n_reg >= 30 and ext[2] > 0.25 * fh and ext[2] < 1.2 * fh
        if not okz: ear_info[nm] = {'skipped': True, 'verts': n_reg, 'height_mm': round(float(ext[2] * 1000), 1)}; continue
        cnt = 0
        for e in bm.edges:
            fs = e.link_faces
            if len(fs) == 2:
                inA = all(reg[v.index] for v in fs[0].verts); inB = all(reg[v.index] for v in fs[1].verts)
                if inA != inB: e.seam = True; cnt += 1
        ear_info[nm] = {'verts': n_reg, 'seam_edges': cnt, 'height_mm': round(float(ext[2] * 1000), 1),
                        'standoff_mm': round(float(lateral[reg].max() * 1000), 1)}
seams['ears'] = ear_info
# -- neck ring: the neck / bust below the jaw is its own island (lower density); the cut runs under the chin and
# rises to the nape, so the front view never sees it. Faces are split by a plane through the line under the chin
# and the nape point, then the split is cleaned by a majority vote over face neighbours.
NECK = '--no-neck' not in a
NECK_DENS = float(os.environ.get('UV_NECK_DENS', '0.8'))        # neck texels relative to the skull
if NECK:
    yb = X[head, 1].max()
    pa = np.array([LT[24][1] + 0.15 * fh, z_chin - 0.06 * fh]); pb = np.array([yb, z_chin + 0.18 * fh])
    dyz = pb - pa; nrm2 = np.array([-dyz[1], dyz[0]]); nrm2 /= np.linalg.norm(nrm2)
    if nrm2[1] > 0: nrm2 = -nrm2                                 # points down: positive = below the cut
    Fc = np.array([X[[v.index for v in f.verts]].mean(0) for f in bm.faces])
    below = ((Fc[:, [1, 2]] - pa) @ nrm2) > 0
    below &= Fc[:, 2] < z_chin + 0.3 * fh
    if ci is not None: below &= np.array([f.material_index != ci for f in bm.faces])
    fnb = [[g.index for e in f.edges for g in e.link_faces if g.index != f.index] for f in bm.faces]
    for _ in range(4):
        cnt = np.array([sum(below[j] for j in fn) for fn in fnb]); tot = np.array([len(fn) for fn in fnb])
        below = np.where(cnt * 4 >= tot * 3, True, np.where((tot - cnt) * 4 >= tot * 3, False, below))
    # keep the biggest connected neck part, the rest goes back to the head
    lab = -np.ones(len(below), int); best = []
    for s in np.nonzero(below)[0]:
        if lab[s] >= 0: continue
        comp, st = [], [s]; lab[s] = s
        while st:
            f_ = st.pop(); comp.append(f_)
            for j in fnb[f_]:
                if below[j] and lab[j] < 0: lab[j] = s; st.append(j)
        if len(comp) > len(best): best = comp
    below[:] = False; below[best] = True
    n_neck = 0
    if below.sum() > 30:
        for e in bm.edges:
            fs = e.link_faces
            if len(fs) == 2 and below[fs[0].index] != below[fs[1].index]: e.seam = True; n_neck += 1
        # big busts (shoulders, collars): front and back halves, so the islands are short and pack well
        bust_h = np.ptp(Fc[below, 2]) if below.any() else 0
        if bust_h > 0.35 * fh:
            yc = np.median(Fc[below, 1]); fb = below & (Fc[:, 1] < yc)
            for e in bm.edges:
                fs = e.link_faces
                if len(fs) == 2 and below[fs[0].index] and below[fs[1].index] and fb[fs[0].index] != fb[fs[1].index]:
                    e.seam = True; n_neck += 1
            seams['bust_split'] = True
    seams['neck_ring_edges'] = n_neck; seams['neck_faces'] = int(below.sum())
bm.to_mesh(me); bm.free(); me.update()
qa['skin_seams'] = seams

# importance weights: face front gets the texels (SLIM 'uv_importance')
fc = np.array([0.0, 0.0, (z_brow + z_chin) / 2])
dx = X[:, 0] / (1.1 * eye_w); dz = (X[:, 2] - fc[2]) / (0.85 * fh)
front = np.clip((Nrm @ np.array([0, -1.0, 0]) + 0.2) / 0.6, 0, 1)
wimp = np.exp(-(dx ** 2 + dz ** 2) ** 2) * front
vg = face.vertex_groups.get('uv_importance') or face.vertex_groups.new(name='uv_importance')
for i, w in enumerate(wimp): vg.add([i], float(w), 'REPLACE')
face_region = wimp > 0.5

uv = uv_layer(face)
face.active_shape_key_index = 0
select_only(face)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='MINIMUM_STRETCH', iterations=30, use_weights=True, weight_group='uv_importance',
                  weight_factor=float(os.environ.get('UVW', '1.0')), fill_holes=True, margin=0.0)
bpy.ops.object.mode_set(mode='OBJECT')
uv = me.uv_layers[UVN]                                         # edit mode re-allocates the layer: fetch again
# islands (by uv connectivity of faces through non-seam edges)
uvd = np.array([tuple(l.uv) for l in uv.data])
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
isl = -np.ones(len(bm.faces), int); k = 0
for f in bm.faces:
    if isl[f.index] >= 0: continue
    st = [f]; isl[f.index] = k
    while st:
        g = st.pop()
        for e in g.edges:
            if e.seam: continue
            for h in e.link_faces:
                if isl[h.index] < 0: isl[h.index] = k; st.append(h)
    k += 1
cav_faces = np.array([f.material_index == ci for f in bm.faces]) if ci is not None else np.zeros(len(bm.faces), bool)
bm.free()
sizes = np.bincount(isl); main = int(np.argmax(sizes))
# upright main island: chin -> brow direction in uv points to +v
loops_of = [list(p.loop_indices) for p in me.polygons]; verts_of = [list(p.vertices) for p in me.polygons]
v2uv = {}
for p in me.polygons:
    if isl[p.index] != main: continue
    for li, vi in zip(p.loop_indices, p.vertices): v2uv[vi] = uvd[li]
def near_uv(P):
    ids = np.array(list(v2uv.keys())); j = ids[np.argmin(np.linalg.norm(X[ids] - P, axis=1))]; return v2uv[j]
up = near_uv(np.array([0, LT[16][1], z_brow])) - near_uv(LT[24])
ang = math.atan2(up[0], up[1])                                 # rotate so that 'up' points to +v
ca, sa = math.cos(ang), math.sin(ang)
mainloops = np.concatenate([loops_of[i] for i in np.nonzero(isl == main)[0]])
c0 = uvd[mainloops].mean(0); d0 = uvd[mainloops] - c0
uvd[mainloops] = c0 + np.c_[ca * d0[:, 0] - sa * d0[:, 1], sa * d0[:, 0] + ca * d0[:, 1]]
uv.data.foreach_set('uv', uvd.ravel())
# scale: islands relative to the main one by 3D area (SLIM gave the main island its own scale); cavity at half
# density, ears at the face-free (skull) density
def island_scale_to(target_dens, faces_mask):
    lo = np.concatenate([loops_of[i] for i in np.nonzero(faces_mask)[0]])
    a3 = 0; a2 = 0
    for i in np.nonzero(faces_mask)[0]:
        P = X[verts_of[i]]; U = uvd[loops_of[i]]
        for t in range(1, len(P) - 1):
            a3 += np.linalg.norm(np.cross(P[t] - P[0], P[t + 1] - P[0])) / 2
            a2 += abs((U[t] - U[0])[0] * (U[t + 1] - U[0])[1] - (U[t] - U[0])[1] * (U[t + 1] - U[0])[0]) / 2
    s = target_dens / math.sqrt(a2 / max(a3, 1e-12)); c = uvd[lo].mean(0); uvd[lo] = c + (uvd[lo] - c) * s
def island_density(faces_mask):
    a3 = 0; a2 = 0
    for i in np.nonzero(faces_mask)[0]:
        P = X[verts_of[i]]; U = uvd[loops_of[i]]
        for t in range(1, len(P) - 1):
            a3 += np.linalg.norm(np.cross(P[t] - P[0], P[t + 1] - P[0])) / 2
            a2 += abs((U[t] - U[0])[0] * (U[t + 1] - U[0])[1] - (U[t] - U[0])[1] * (U[t + 1] - U[0])[0]) / 2
    return math.sqrt(a2 / max(a3, 1e-12))
# density of the main island away from the face (skull / neck): the reference for ears
mf = isl == main
pf = np.array([face_region[verts_of[i]].all() for i in range(len(verts_of))])
d_rest = island_density(mf & ~pf)
# neck / bust islands: NECK_DENS of the skull density, but all together at most a quarter of the head's uv area
def uv_area(mask):
    t = 0.0
    for i in np.nonzero(mask)[0]:
        U = uvd[loops_of[i]]
        for k in range(1, len(U) - 1): t += abs((U[k] - U[0])[0] * (U[k + 1] - U[0])[1] - (U[k] - U[0])[1] * (U[k + 1] - U[0])[0]) / 2
    return t
def area3(mask):
    t = 0.0
    for i in np.nonzero(mask)[0]:
        P_ = X[verts_of[i]]
        for k in range(1, len(P_) - 1): t += np.linalg.norm(np.cross(P_[k] - P_[0], P_[k + 1] - P_[0])) / 2
    return t
neck_isl = [k_ for k_ in range(len(sizes)) if k_ != main and NECK and below[isl == k_].mean() > 0.5]
d_neck = d_rest * NECK_DENS
if neck_isl:
    a3n = area3(np.isin(isl, neck_isl)); a_head = uv_area(mf)
    d_neck = min(d_neck, math.sqrt(0.25 * a_head / max(a3n, 1e-12)))
    qa['neck_density_vs_skull'] = round(d_neck / d_rest, 3)
for k_ in range(len(sizes)):
    if k_ == main: continue
    m_ = isl == k_
    island_scale_to(d_rest * 0.5 if cav_faces[m_].all() else d_neck if k_ in neck_isl else d_rest, m_)
me.uv_layers[UVN].data.foreach_set('uv', uvd.ravel())
select_only(face)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.pack_islands(rotate=os.environ.get('UV_ROT', '1') == '1', rotate_method='CARDINAL', scale=True, margin_method='FRACTION', margin=0.006, shape_method='CONCAVE')
bpy.ops.object.mode_set(mode='OBJECT')
# the packer may have turned the head; turn the whole square back (90 degree steps keep the packing valid)
uvd = np.array([tuple(l.uv) for l in me.uv_layers[UVN].data])
v2uv = {}
for p in me.polygons:
    if isl[p.index] != main: continue
    for li, vi in zip(p.loop_indices, p.vertices): v2uv[vi] = uvd[li]
up = near_uv(np.array([0, LT[16][1], z_brow])) - near_uv(LT[24])
k90 = int(round(math.atan2(up[0], up[1]) / (math.pi / 2))) % 4
for _ in range(k90):                                            # rotate by +90 degrees about the centre
    uvd = np.c_[1 - uvd[:, 1], uvd[:, 0]]
me.uv_layers[UVN].data.foreach_set('uv', uvd.ravel())
qa['head_turned_back_90deg'] = k90
face.vertex_groups.remove(face.vertex_groups['uv_importance'])    # only the unwrap needs it (no stray skin group)
qa['skin'] = {'islands': int(len(sizes)), 'island_faces': sorted(sizes.tolist(), reverse=True)[:8],
              **uv_stats(face, 4096, face_region)}
isl_arr = isl.copy()
export(face, 'skin', {'face_island': np.array([isl_arr[t.polygon_index] for t in me.loop_triangles], np.int16),
                      'main_island': np.int32(main), 'importance': wimp})

# =============================================================== eyes
eo = bpy.data.objects.get('eyes')
if eo:
    uv = uv_layer(eo); E = rest_co(eo); uvd = np.zeros((len(eo.data.loops), 2))
    fwd = np.array([0, -1.0, 0])
    info = {}
    for nm, side_u in (('L', 0.25), ('R', 0.75)):
        e = EYES.get(nm)
        sgn = 1 if nm == 'L' else -1
        if e is None: C = None
        else: C = np.array(e['C'])
        sel = np.nonzero(np.sign(E[:, 0]) == np.sign(C[0] if C is not None else sgn))[0]
        if C is None: C = E[sel].mean(0)
        D = E - C; Dn = D / np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-12)
        # frame: w = forward, u = +x (image right on the texture = subject's left when seen from the front: keep x)
        ex = np.array([1.0, 0, 0]); ez = np.array([0, 0, 1.0])
        th = np.arccos(np.clip(Dn @ fwd, -1, 1)); ph = np.arctan2(Dn @ ez, Dn @ ex)
        rho = np.sin(th / 2)                                   # equal-area: 0 front pole, 1 back pole, more texels in front
        info[nm] = {'C': C.tolist(), 'r': float(e['r']) if e else float(np.median(np.linalg.norm(D[sel], axis=1))),
                    'u0': side_u, 'v0': 0.5, 'R_uv_x': 0.25, 'R_uv_y': 0.5, 'map': 'equal_area'}
        if e:
            for k_ in ('iris_dir', 'iris_radius_deg', 'iris_radii_deg', 'iris_centre'):
                if k_ in e: info[nm][k_] = e[k_]
        for p in eo.data.polygons:
            vs = list(p.vertices)
            if np.sign(E[vs[0], 0]) != np.sign(C[0]): continue
            U = np.c_[side_u + 0.25 * rho[vs] * np.cos(ph[vs]), 0.5 + 0.5 * rho[vs] * np.sin(ph[vs])]
            if np.ptp(U[:, 0]) > 0.08 or np.ptp(U[:, 1]) > 0.16:          # faces around the back pole: park on the rim
                U[:] = U[0]
            for li, u_ in zip(p.loop_indices, U): uvd[li] = u_
    uv.data.foreach_set('uv', uvd.ravel())
    qa['eyes'] = {'pieces': info}
    export(eo, 'eyes', {'eye_info': json.dumps(info)})

# =============================================================== brows (P2 piece, front projection box)
bo = bpy.data.objects.get('p2_brows')
if bo and len(bo.data.vertices):
    uv = uv_layer(bo); B = rest_co(bo)
    x0, x1 = B[:, 0].min(), B[:, 0].max(); z0, z1 = B[:, 2].min(), B[:, 2].max()
    mx, mz = 0.08 * (x1 - x0), 0.15 * (z1 - z0); box = [x0 - mx, x1 + mx, z0 - mz, z1 + mz]
    uvd = np.zeros((len(bo.data.loops), 2))
    for l in bo.data.loops:
        p = B[l.vertex_index]; uvd[l.index] = ((p[0] - box[0]) / (box[1] - box[0]), (p[2] - box[2]) / (box[3] - box[2]))
    # faces that do not face the camera (slab edges, back against the skin) would smear the photo: they map to a
    # solid brow-colour patch in the texture's corner (bake_ref_texture paints it)
    fn = []
    for pl in bo.data.polygons:
        q = B[list(pl.vertices)]; nrm = np.zeros(3)
        for k in range(len(q)): nrm += np.cross(q[k], q[(k + 1) % len(q)])
        fn.append(nrm / max(np.linalg.norm(nrm), 1e-12))
    fn = np.array(fn); fy = -fn[:, 1]
    if (fy < -0.5).sum() > (fy > 0.5).sum(): fy = -fy                      # winding flipped: front = most faces
    n_side = 0
    for pl, f_ in zip(bo.data.polygons, fy):
        if f_ < 0.35:
            n_side += 1
            for li in pl.loop_indices: uvd[li] = (0.004, 0.008)
    uv.data.foreach_set('uv', uvd.ravel())
    qa['brows'] = {'object': 'p2_brows', 'verts': len(B), 'box_m': [round(float(v), 4) for v in box],
                   'shape_keys': len(bo.data.shape_keys.key_blocks) if bo.data.shape_keys else 0, 'edge_back_faces_solid': n_side}
    export(bo, 'brows', {'brows_box': np.array(box)})
else:
    qa['brows'] = 'no brow piece in the asset (brows are painted on the skin)'

# =============================================================== teeth (cylindrical about the arch) + tongue
for nm in ('teeth_up', 'teeth_lo'):
    o = bpy.data.objects.get(nm)
    if not o: continue
    uv = uv_layer(o); P = rest_co(o)
    gi = next((i for i, m in enumerate(o.data.materials) if m and m.name.startswith('gums')), -1)
    yc = P[:, 1].max(); zc0, zc1 = P[:, 2].min(), P[:, 2].max()
    ang = np.arctan2(P[:, 0], yc - P[:, 1])                       # 0 = front middle
    u = 0.5 + ang / np.pi                                          # 0..1
    v = (zc1 - P[:, 2]) / (zc1 - zc0) if nm == 'teeth_up' else (P[:, 2] - zc0) / (zc1 - zc0)   # 0 gum side, 1 bite
    uvd = np.zeros((len(o.data.loops), 2))
    for p in o.data.polygons:
        off = 0.5 if p.material_index == gi else 0.0
        for li, vi in zip(p.loop_indices, p.vertices): uvd[li] = (off + 0.5 * u[vi], v[vi])
    uv.data.foreach_set('uv', uvd.ravel())
    export(o, nm)
o = bpy.data.objects.get('tongue')
if o:
    uv = uv_layer(o); P = rest_co(o)
    x0, x1 = P[:, 0].min(), P[:, 0].max(); y0, y1 = P[:, 1].min(), P[:, 1].max(); cx = (x0 + x1) / 2; hw = max(x1 - cx, cx - x0)
    uvd = np.zeros((len(o.data.loops), 2))
    for l in o.data.loops:
        p = P[l.vertex_index]; uvd[l.index] = (0.5 + 0.5 * (p[0] - cx) / hw, 1 - (p[1] - y0) / (y1 - y0))   # tip at v=1
    uv.data.foreach_set('uv', uvd.ravel())
    export(o, 'tongue')

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'uv.blend'), compress=True)
json.dump(qa, open(os.path.join(OUT, 'uv_qa.json'), 'w'), indent=1)
print('UVPARTS', json.dumps(qa['skin']), json.dumps(qa['skin_seams']))
