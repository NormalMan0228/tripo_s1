"""Loop organs: eye openings and a mouth slit cut ALONG EXISTING EDGES of a clean quad head (no kept skin vertex moves),
plus hidden added parts (lid tucks, eyeballs, mouth interior), with the ring attributes / vertex groups / json of
organ_eye.py and organ_mouth.py, so the rest of the face chain (organ_teeth, rigify_fit, organ_mouth_weights,
organ_blink_keys, sym_lock, organ_lid_colors) runs unchanged. Rings are BFS rings of the existing mesh, so their
vertex counts differ (eyes json / mouth json carry 'irregular': true; organ_lib.ring_blink_irregular closes the lids).

0. Frame: if the landmarks do not lie on the mesh but do after a Y-up -> Z-up turn ((x, y, z) -> (x, -z, y)), every
   mesh is turned (rigid; QA frame_fix). The head must be exactly mirror-symmetric: the left side is found, the right
   side is its mirror image (vertex indices mapped through the mirror partners, positions exact).
1. Eyes. Opening = a closed cycle of existing edges along the lid margin, first match of:
   - eyes_meta margin_vids (Track P bases): a boundary loop (open eye, f09) or a closed edge path (skin folding into a
     pocket behind the eyeball: cut along it);
   - an existing boundary loop near the rim (eyes_meta raw);
   - the cheapest cycle that winds once round the opening (loop_lib.eye_cycle) inside a band round the rim
     (outside: max(3 mm, 0.3 eye height, 2.5 edge lengths); inside: at most 0.35 eye height): sum over its edges of
     length * (1 + (rim distance / sigma)^2), sigma = max(0.6 mm, 0.03 eye width), plus 2 edge lengths (<= 2 mm)
     wherever it leaves an edge loop at a valence-4 vertex (half at poles). (No test head has a closed true edge loop
     there: poles interrupt them.)
   A cut deletes the smaller side of the cycle (both eyes' cycles block the flood: a pocket may join the two eyes).
   Rings: BFS rings outward from the margin over existing vertices (up to 10, while the ring's median distance to the
   margin stays under clip(0.33 eye width, 6, 14) mm); ring K = margin, ring 1 = outermost. Corners = the margin's ends
   along the eye's corner axis (eyes_meta A; the blink turns about it). eye_u: margin by arc length, u = 0 at the +x
   corner, 0.5 at the other, u < 0.5 upper lid; every other ring vertex takes the u of the margin point at the same
   angle round the opening in organ_eye's ray chart (radial columns, as organ_eye).
   Lid tuck: two added rings from the margin rolling under the lid onto the eyeball (rings K+1, K+2; 0.8 / 2.5 mm of
   arc, 0.5 / 0.3 mm above the eyeball). Eyeball: 'p2_eyes' if present (sphere fitted per side; radius = the 99th
   percentile of the front half, so lids clear the cornea bulge), else a UV sphere at eyes_meta C, r. It is shrunk
   about its centre until the kept skin is >= 0.6 mm (margin) / 0.45 mm (3 rings next to it) / 0.3 mm (any skin near
   the eye) outside it (r_shrink_mm); json r = the eyeball used.
2. Mouth. First match of:
   - an existing boundary loop along the seam: the slit;
   - lips that pinch into a mouth bag (P2 f02 / f06: upper and lower lip are two separate vertex chains on the centre
     line near the seam): the cheapest edge path on the +x half from one chain's seam vertex round the corner to the
     other's, near the seam (landmarks _lip_seam, else 20/34/22), mirrored, is a cycle; its smaller side (the bag,
     reaching > 4 mm behind the seam) is deleted and the cycle is the (open) slit -> mode 'bag removed';
   - RIP: an edge path from corner to corner along the seam (Dijkstra from the centre-line vertex nearest the seam to
     the vertex near the corner; cost length * (1 + (seam distance / sigma)^2) with _lip_seam, else
     length * exp(-concavity / 0.08) along the crease between the lips; the end vertex: nearest the seam corner, path
     cost x LOOP_CORNER_COST (0.2) only breaking near-ties; left half mirrored); its inner vertices are
     duplicated (bmesh split_edges; the copy on the upper lip is the one whose faces run the path -x -> +x with
     outward normals; bow-tie vertices on the seam are welded per lip), corner vertices stay single, nothing moves.
   Rings: BFS rings outward from the slit (up to 11, median distance <= 0.6 half mouth width), ring K = slit.
   mouth_u: 0 at the +x corner, 0.25 top centre, 0.5 the -x corner, 0.75 bottom centre; slit vertices by arc length
   per quarter; other vertices by confocal elliptic coordinates round the slit (seam line flattened): the hyperbola
   through the vertex lands on the slit at the point whose u it takes (columns fan out round the corners).
   Interior (organ_mouth v2 sizes, scaled by mouth width; M = 80 regular rings): 2 inner-lip roll rings (K+1, K+2),
   4 cavity rings (K+3..K+6, material mouth_inner), cap (K+7, u = -1); the slit is zipped to roll ring 1 per quarter
   (+x quarters built, -x quarters mirrored). Added faces are oriented against their kept neighbours and shaded like
   the kept faces. Base pieces replaced by added parts ('p2_lids', 'p2_mouth') are hidden, not deleted.
Vertex groups and attributes as organ_eye / organ_mouth (eye_ring, eye_u, mouth_ring, mouth_u; eye_<s>_upper / _lower
/ _skin / _margin_upper / _margin_lower; mouth_upper / _lower / _skin / _bag / _slit_upper / _slit_lower).
Writes <out.blend>, <out>_eyes.json, <out>_mouth.json (organ_eye / organ_mouth formats + 'irregular': true + QA) and
<out>_loopqa.json. QA line LOOPQA: per eye mode, cut-loop vertex count, rim deviation (loop -> rim, rim -> loop: mean /
max mm), deleted faces, ring counts, eyeball shrink; mouth mode, path / slit / ring counts; kept vertices' max
displacement (must be 0); winding conflicts; folds > 120 deg at added faces; boundary loops; mirror gap.
Usage: blender -b <base.blend> -P loop_organs.py -- <landmarks.json> <eyes_meta.json> <out.blend>
(env LOOP_SIGMA_MM: rim-distance scale in mm; LOOP_TURN: loop-leaving penalty in median edge lengths, default 2)
"""
import bpy, bmesh, sys, os, json, math, time
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from organ_lib import Chart
from loop_lib import (YUP_TO_ZUP, landmark_fit, mirror_partners, polyline_dist, Graph, dijkstra_turn, eye_cycle,
                      simple_cycle, boundary_loops, flood_faces, bfs, arc_param, periodic_interp, strip, winding_vs,
                      sphere_fit, smoothstep, inside_poly, bowtie_verts)

T0 = time.time()
a = sys.argv[sys.argv.index('--') + 1:]
LMJ, EMJ, OUT = a[0], a[1], os.path.abspath(a[2])
LT = {int(k): np.array(v, float) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
EM = json.load(open(EMJ))
N = bpy.data.objects.get('face') or bpy.data.objects['noface']
QA = {'frame_fix': None}
MX = np.array([-1.0, 1.0, 1.0])

# ---------------------------------------------------------------- 0. frame
for o in [o for o in bpy.data.objects if o.type == 'MESH']:
    if o.matrix_world != Matrix.Identity(4):
        o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4)
XN = np.array([tuple(v.co) for v in N.data.vertices]); FN = [list(p.vertices) for p in N.data.polygons]
LP = np.array(list(LT.values()))
fit_id = landmark_fit(XN, FN, LP)
if fit_id[0] > 0.005:
    fit_y = landmark_fit(XN @ YUP_TO_ZUP.T, FN, LP)
    if fit_y[0] < 0.002:
        R4 = Matrix([list(r) + [0.0] for r in YUP_TO_ZUP] + [[0, 0, 0, 1.0]])
        for o in [o for o in bpy.data.objects if o.type == 'MESH']: o.data.transform(R4); o.data.update()
        QA['frame_fix'] = {'turn': 'y-up -> z-up', 'landmarks_mm_before': round(fit_id[0] * 1000, 1), 'after': round(fit_y[0] * 1000, 2)}
    else:
        raise RuntimeError(f'landmarks do not lie on the mesh (median {fit_id[0] * 1000:.1f} mm, y-up {fit_y[0] * 1000:.1f} mm)')
else:
    QA['landmarks_on_mesh_mm'] = round(fit_id[0] * 1000, 2)

bm = bmesh.new(); bm.from_mesh(N.data)
L_oi = bm.verts.layers.int.new('_loop_oi')                     # original index: kept-vertex check, rip copies
# every layer before any BMVert reference is kept (a new layer invalidates Python references)
L_er = bm.verts.layers.int.get('eye_ring') or bm.verts.layers.int.new('eye_ring')
L_eu = bm.verts.layers.float.get('eye_u') or bm.verts.layers.float.new('eye_u')
L_mr = bm.verts.layers.int.get('mouth_ring') or bm.verts.layers.int.new('mouth_ring')
L_mu = bm.verts.layers.float.get('mouth_u') or bm.verts.layers.float.new('mouth_u')
L_def = bm.verts.layers.deform.verify()
for v in bm.verts: v[L_oi] = v.index + 1                     # stored + 1: new vertices read 0
G = Graph(bm); X = G.X.copy(); X_REF = X.copy(); NV0 = len(X)
part, pgap = mirror_partners(X)
SYM = bool(pgap.max() < 1e-6 and (part[part] == np.arange(len(X))).all())
QA['mirror_gap_max_mm'] = round(float(pgap.max() * 1000), 6); QA['symmetric_base'] = SYM
if not SYM: raise RuntimeError('loop_organs needs an exactly mirror-symmetric head (sym_mirror.py)')
# outward orientation of the kept faces (consistent winding assumed): +1 if face normals point away from the centre
fc = np.array([tuple(f.calc_center_median()) for f in bm.faces]); fn = np.array([tuple(f.normal) for f in bm.faces])
OUTW = 1.0 if (((fc - X.mean(0)) * fn).sum(1) > 0).mean() > 0.5 else -1.0
SMOOTH0 = sum(f.smooth for f in bm.faces) * 2 > len(bm.faces)            # added faces shade like the original
QA['outward_share'] = round(float((((fc - X.mean(0)) * fn).sum(1) * OUTW > 0).mean()), 3)
SIGMA_ENV = os.environ.get('LOOP_SIGMA_MM'); TURN = float(os.environ.get('LOOP_TURN', '2.0'))
BV = lambda ids: [bm.verts[int(i)] for i in ids]


# ---------------------------------------------------------------- 1a. eye openings (left found, right mirrored)
def eye_chart(s):
    C = np.array(EM[s]['C'], float); r = float(EM[s]['r']); rim = np.array(EM[s]['raw'], float); cen = rim.mean(0)
    n = (cen - C) / np.linalg.norm(cen - C); Q = C - n * 2 * r
    ch = Chart(Q, n, float(np.linalg.norm(cen - Q))); return C, r, rim, cen, n, ch

EYE = {}
for s, sgn in (('L', 1.0), ('R', -1.0)):
    C, r, rim, cen, n, ch = eye_chart(s); RUV = ch.uv(rim); w = float(np.ptp(RUV[:, 0])); h = float(np.ptp(RUV[:, 1]))
    EYE[s] = dict(C=C, r=r, rim=rim, cen=cen, n=n, ch=ch, w=w, h=h, sgn=sgn)
E = EYE['L']; C, r, rim, n, ch, w, h = E['C'], E['r'], E['rim'], E['n'], E['ch'], E['w'], E['h']
rd = polyline_dist(X, rim); UV = ch.uv(X); RUV = ch.uv(rim); c0 = RUV.mean(0)
# Track P: an existing boundary loop along the rim
cand = []
for lp in boundary_loops(bm):
    ids = np.array([v.index for v in lp]); P = X[ids]
    if len(ids) < 6 or (P[:, 0] <= 0).any(): continue
    dev = polyline_dist(P, rim)
    if dev.mean() < max(0.002, 0.25 * h) and np.linalg.norm(P.mean(0) - E['cen']) < 0.5 * w: cand.append((dev.mean(), ids))
given = [int(v) for v in EM['L'].get('margin_vids') or []]; kind = EM['L'].get('margin_kind')
def edge_cycle_ok(c):
    return len(c) >= 6 and len(set(c)) == len(c) and all(X[v, 0] > 1e-6 for v in c) and \
        all(any(w_ == c[(i + 1) % len(c)] for w_, _ in G.nbr[c[i]]) for i in range(len(c)))
if given and edge_cycle_ok(given) and all(bm.verts[v].is_boundary for v in given):
    cycL = given; E['mode'] = 'existing hole (eyes_meta margin_vids)'; E['deleted'] = 0; E['cut_cost'] = None
elif given and edge_cycle_ok(given):
    cycL = given; E['mode'] = 'cut (eyes_meta margin_vids path)'; E['cut_cost'] = None
elif cand:
    cycL = list(min(cand, key=lambda c: c[0])[1]); E['mode'] = 'existing hole'; E['deleted'] = 0; E['cut_cost'] = None
else:
    near = (X[:, 0] > 1e-6) & (rd < 0.004); Lmed = float(np.median(G.elen[near[G.ev[:, 0]] & near[G.ev[:, 1]]]))
    band = max(0.003, 0.3 * h, 2.5 * Lmed)                     # room to stay on an edge loop a little off the rim
    ok_ = np.isfinite(UV[:, 0]); ins = np.zeros(len(X), bool); ins[ok_] = inside_poly(UV[ok_], RUV)
    band_in = min(band, 0.35 * h)                              # inside the rim: never near the opening centre (no short cut)
    mask = (X[:, 0] > 1e-6) & np.where(ins, rd < band_in, rd < band) & ok_ & ((X - C) @ n > 0)
    th = np.mod(np.arctan2(UV[:, 1] - c0[1], UV[:, 0] - c0[0]) + np.pi / 2, 2 * np.pi)      # seam half-line: straight down
    sig = float(SIGMA_ENV) / 1000 if SIGMA_ENV else max(0.0006, 0.03 * w)
    cost, cyc = eye_cycle(G, mask, rd, th, sig, TURN * min(Lmed, 0.002))      # turn penalty: TURN edge lengths, at most 2 mm each
    if cyc is None: raise RuntimeError('no edge cycle round the left eye within the rim band')
    cycL = simple_cycle(cyc); E['mode'] = 'cut'; E['cut_cost'] = round(float(cost), 5)
    eid = lambda a_, b_: next(e for w_, e in G.nbr[a_] if w_ == b_)
    E['loop_turns'] = sum(1 for i in range(len(cycL)) if G.val[cycL[i]] == 4 and not G.straight(
        eid(cycL[i - 1], cycL[i]), cycL[i], eid(cycL[i], cycL[(i + 1) % len(cycL)])))       # leaves its edge loop here
    E['loop_poles'] = int(sum(G.val[v] != 4 for v in cycL))
    E.update(band_mm=round(band * 1000, 2), band_in_mm=round(band_in * 1000, 2), sigma_mm=round(sig * 1000, 2), edge_med_mm=round(Lmed * 1000, 2), band_verts=int(mask.sum()))
cycR = [int(part[v]) for v in cycL]
EYE['L']['cyc_v'] = BV(cycL); EYE['R']['cyc_v'] = BV(cycR)
for s, cyc in (('L', cycL), ('R', cycR)):
    P = X[cyc]; rim_ = EYE[s]['rim']; d1 = polyline_dist(P, rim_); d2 = polyline_dist(rim_, P)
    EYE[s]['rim_dev_mm'] = {'loop_to_rim_mean': round(d1.mean() * 1000, 2), 'loop_to_rim_max': round(d1.max() * 1000, 2),
                            'rim_to_loop_mean': round(d2.mean() * 1000, 2), 'rim_to_loop_max': round(d2.max() * 1000, 2)}
if EYE['L']['mode'].startswith('cut'):                         # delete inside: faces reached from inside without crossing the cycle
    bm.faces.ensure_lookup_table()
    cv = EYE['L']['cyc_v']; blocked = set()
    for i in range(len(cv)):
        e = bm.edges.get((cv[i], cv[(i + 1) % len(cv)]))
        if e is None: raise RuntimeError('cycle is not an edge cycle')
        blocked.add(e)
    blockedR = {bm.edges.get((bm.verts[int(part[a_.index])], bm.verts[int(part[b_.index])])) for a_, b_ in (e.verts for e in blocked)}
    e0 = next(iter(blocked)); sides = [flood_faces(f, blocked | blockedR) for f in e0.link_faces]   # both cycles block: an eye
    comp = min(sides, key=len)                                 # pocket may run behind the nose to the other eye; inside = smaller side
    EYE['L']['inner_side_votes'] = sorted(len(c_) for c_ in sides)
    byset = {frozenset(v.index for v in f.verts): f for f in bm.faces}                      # may run behind the nose to the other eye
    compR_ = {byset[frozenset(int(part[v.index]) for v in f.verts)] for f in comp}
    far = max(np.linalg.norm(np.array(v.co) * MX ** (np.array(v.co)[0] < 0) - E['cen']) for f in comp for v in f.verts)
    if len(comp) > 0.25 * len(bm.faces) or far > 1.2 * w: raise RuntimeError(f'eye cut leaks ({len(comp)} faces, {far * 1000:.0f} mm)')
    compL = {f for f in comp | compR_ if f.calc_center_median().x > 0}; compR = (comp | compR_) - compL
    EYE['L']['pocket_joins_eyes'] = bool(any(f.calc_center_median().x < 0 for f in comp))
    inner_v = {v for f in compL | compR for v in f.verts} - set(EYE['L']['cyc_v']) - set(EYE['R']['cyc_v'])
    bmesh.ops.delete(bm, geom=list(compL | compR), context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in inner_v if v.is_valid and not v.link_faces], context='VERTS')
    EYE['L']['deleted'] = EYE['R']['deleted'] = len(compL)
    EYE['L']['deleted_verts'] = EYE['R']['deleted_verts'] = len(inner_v) // 2


# ---------------------------------------------------------------- 1b. mouth slit: seam path + rip
cR = LT[22] if LT[22][0] > 0 else LT[20]; cS = (LT[34] + LT[35]) / 2 if 35 in LT else LT[34]
SEAM = json.load(open(LMJ)).get('_lip_seam')                   # Track P: the lip seam measured on the base (x from - to +)
if SEAM is not None:
    SEAM = np.array(SEAM, float); cR = SEAM[int(np.argmax(SEAM[:, 0]))]; cS = SEAM[int(np.argmin(np.abs(SEAM[:, 0])))]
half_w = float(abs(cR[0]))
G = Graph(bm); X = G.X
oi = np.array([v[L_oi] for v in bm.verts]) - 1
partG = np.full(len(X), -1); pos = {o: i for i, o in enumerate(oi)}
for i, o in enumerate(oi):
    if o >= 0 and part[o] in pos: partG[i] = pos[part[o]]
MO = {}
loopsM = []
for lp in boundary_loops(bm):
    ids = np.array([v.index for v in lp]); P = X[ids]
    if len(ids) < 6: continue
    if np.abs(P[:, 2] - cS[2]).max() < 0.5 * half_w and np.abs(P[:, 0]).max() < 1.4 * half_w and np.abs(P[:, 0]).max() > 0.6 * half_w \
            and np.linalg.norm(P.mean(0)[[0, 2]] - cS[[0, 2]]) < 0.3 * half_w:
        loopsM.append(ids)
if loopsM:                                                     # mouth already open: its boundary loop is the slit
    slit_ids = max(loopsM, key=len); MO['mode'] = 'existing hole'
    P = X[slit_ids]; ip = int(slit_ids[np.argmax(P[:, 0])]); im = int(partG[ip])
    MO['corner_p'], MO['corner_m'] = bm.verts[ip], bm.verts[im]
    lst = [int(i) for i in slit_ids]; k0 = lst.index(ip); lst = lst[k0:] + lst[:k0]; k1 = lst.index(im)
    A_, B_ = lst[:k1 + 1], lst[k1:] + [lst[0]]
    upper, lower = (A_, B_) if X[A_, 2].mean() > X[B_, 2].mean() else (B_[::-1], A_[::-1])
    MO['up_v'] = BV(upper); MO['lo_v'] = BV(lower[::-1])        # both from +x corner to -x corner
    MO['path_verts'] = len(slit_ids)
else:
    bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table()
    FN_ = np.array([tuple(f.normal) for f in bm.faces]) * OUTW; FC_ = np.array([tuple(f.calc_center_median()) for f in bm.faces])
    kap = np.zeros(len(bm.edges))
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2: continue
        i1, i2 = lf[0].index, lf[1].index
        if (FC_[i2] - FC_[i1]) @ (FN_[i1] - FN_[i2]) > 0: kap[e.index] = (1 - FN_[i1] @ FN_[i2]) / 2
    region = (X[:, 0] >= -1e-9) & (np.abs(X[:, 0]) < 1.3 * half_w) & (np.abs(X[:, 2] - cS[2]) < 0.45 * half_w) \
        & (X[:, 1] < max(cS[1] + 0.5 * half_w, (SEAM[:, 1].max() if SEAM is not None else cR[1]) + 0.3 * half_w))   # corners may sit far back
    Lm = float(np.median(G.elen[region[G.ev[:, 0]] & region[G.ev[:, 1]]]))
    centre = np.abs(X[:, 0]) < 1e-7
    SL = SEAM if SEAM is not None else np.array([cR * MX, cS, cR])
    dsm = polyline_dist(X, SL, closed=False)
    # ---- (a) lips that pinch into a mouth bag (P2 heads): on the centre line the upper and the lower lip are two separate
    # vertex chains near the seam (not one chain through it). Then the cheapest edge path on the +x half from the upper
    # chain's seam vertex round the corner to the lower chain's, along the seam, mirrored, is a cycle whose small side
    # is the bag. A bag (reaching more than 4 mm behind the seam) is deleted: the cycle is the slit (both lip edges).
    ea, eb = G.ev[:, 0], G.ev[:, 1]
    ecm = G.elen * (1 + ((dsm[ea] + dsm[eb]) / 2 / max(0.0004, 0.3 * Lm)) ** 2)
    cm = np.where(centre & (np.linalg.norm(X - cS, axis=1) < 0.004))[0]; cset = set(int(v) for v in cm); comps = []
    for v0 in cm:
        if any(v0 in c_ for c_ in comps): continue
        comp_, st_ = {int(v0)}, [int(v0)]
        while st_:
            v_ = st_.pop()
            for w_, _ in G.nbr[v_]:
                if w_ in cset and w_ not in comp_: comp_.add(w_); st_.append(w_)
        comps.append(comp_)
    comps.sort(key=lambda c_: min(dsm[list(c_)]))
    best_c = (np.inf, None)
    if len(comps) >= 2:
        BOW = bowtie_verts(bm)                                  # lips touching at single vertices: the path must not switch sheet there
        sa = min(comps[0], key=lambda v: dsm[v]); sb = min(comps[1], key=lambda v: dsm[v])
        for band_m in (max(0.002, 2.5 * Lm), 0.004, 0.008):
            mk = region & ~centre & ~BOW & (dsm < band_m) & (np.abs(X[:, 0]) < 1.25 * half_w); mk[[sa, sb]] = True
            c_, pth = dijkstra_turn(G, [sa], ecm, mk, 0.5 * Lm, goal=lambda v, sh: v == sb)
            if pth is not None: best_c = (c_, pth); break
    MO['bag'] = None; MO['bag_search'] = {'centre_chains_near_seam': len(comps), 'found': None if best_c[1] is None else len(best_c[1])}
    if best_c[1] is not None:
        hp = best_c[1]; cyc_m = hp + [int(partG[v]) for v in hp[-2:0:-1]]
        if len(set(cyc_m)) == len(cyc_m) and (np.array(cyc_m) >= 0).all():
            cvm = BV(cyc_m); blk = {bm.edges.get((cvm[i], cvm[(i + 1) % len(cvm)])) for i in range(len(cvm))}
            sides = [flood_faces(f, blk) for f in bm.edges.get((cvm[0], cvm[1])).link_faces]
            inner = min(sides, key=len); depth = max(f.calc_center_median().y for f in inner) - cS[1]
            MO['bag'] = {'cycle_verts': len(cyc_m), 'inner_faces': len(inner), 'depth_mm': round(float(depth * 1000), 1)}
            if depth > 0.004 and len(inner) < 0.25 * len(bm.faces):
                MO['mode'] = 'bag removed'
                ic = int(np.argmax(X[hp, 0])); s_a, s_b = hp[0], hp[-1]
                inner_set = set(inner); vote = 0                 # the upper lip edge: its kept faces run it -x -> +x (outward
                for a_, b_ in zip(hp[:ic], hp[1:ic + 1]):        # normals, seen from the front); the lips' sheets may cross
                    for f in bm.edges.get((bm.verts[a_], bm.verts[b_])).link_faces:
                        if f not in inner_set: vote += 1 if (winding_vs(list(f.verts), bm.verts[a_], bm.verts[b_]) > 0) == (OUTW > 0) else -1
                hu, hl = (hp[:ic + 1], hp[ic:][::-1]) if vote > 0 else (hp[ic:][::-1], hp[:ic + 1])   # centre -> corner
                MO['upper_votes'] = vote
                mir = lambda L_: [int(partG[v]) for v in L_]
                MO['up_v'] = BV(hu[::-1] + mir(hu[1:]))                 # +x corner -> centre -> -x corner
                MO['lo_v'] = BV(hl[::-1] + mir(hl[1:]))
                iv = {v for f in inner for v in f.verts} - set(cvm)
                bmesh.ops.delete(bm, geom=list(inner), context='FACES')
                bmesh.ops.delete(bm, geom=[v for v in iv if v.is_valid and not v.link_faces], context='VERTS')
                MO['bag_deleted_faces'] = len(inner)
                MO['path_verts'] = len(cyc_m); MO['seam_cost'] = round(float(best_c[0]), 5)
                MO['corner_dev_mm'] = round(float(np.linalg.norm(X[hp[ic]] - cR) * 1000), 2)
                MO['centre_dev_mm'] = round(float(min(np.linalg.norm(X[s_a] - cS), np.linalg.norm(X[s_b] - cS)) * 1000), 2)
                dd = dsm[cyc_m]; MO['path_to_seam_mm'] = [round(float(dd.mean() * 1000), 2), round(float(dd.max() * 1000), 2)]
                MO['seam_source'] = 'landmarks _lip_seam' if SEAM is not None else 'landmarks 20/34/22'
    if MO.get('mode') != 'bag removed':
        MO['mode'] = 'rip'
        reg_r = region & (~centre)                              # one centre vertex (S0) only: the mirrored path stays simple
        cen_ids = np.where(region & centre & (np.abs(X[:, 2] - cS[2]) < 0.2 * half_w))[0]
        if SEAM is not None:                                    # follow the measured seam line
            sig_s = max(0.0004, 0.3 * Lm)
            ecost = G.elen * (1 + ((dsm[G.ev[:, 0]] + dsm[G.ev[:, 1]]) / 2 / sig_s) ** 2); MO['seam_source'] = 'landmarks _lip_seam'
            S0 = int(min(cen_ids, key=lambda v: dsm[v]))
        else:                                                   # follow the crease between the lips
            ecost = G.elen * np.exp(-kap / 0.08); MO['seam_source'] = 'concave crease'
            def groove(v):
                return max([kap[e] for w_, e in G.nbr[v] if X[w_, 0] > 1e-7] + [0.0])
            S0 = int(max(cen_ids, key=lambda v: (groove(v), -abs(X[v, 2] - cS[2]))))
        reg_r[S0] = True
        dist, prev = dijkstra_turn(G, [S0], ecost, reg_r, 0.3 * Lm)
        bestv = {}
        for (v, e, sh), d in dist.items():
            if d < bestv.get(v, (np.inf,))[0]: bestv[v] = (d, (v, e, sh))
        cands = [v for v in bestv if np.linalg.norm(X[v] - cR) < 0.15 * half_w and X[v, 0] > 0.5 * half_w]
        if not cands: raise RuntimeError('no seam path reaches the mouth corner')
        # the path ends at the vertex nearest the measured seam corner; its cost only breaks near-ties (weight LOOP_CORNER_COST,
        # default 0.2; it was 1: cost and distance tied one edge short of the corner, P f11 ripped 2.8 mm short on each side
        # and the commissure could not open there)
        wcc = float(os.environ.get('LOOP_CORNER_COST', '0.2'))
        Vc = min(cands, key=lambda v: wcc * bestv[v][0] + np.linalg.norm(X[v] - cR))
        half = [Vc]; st = bestv[Vc][1]
        while st in prev: st = prev[st]; half.append(st[0])
        half = half[::-1]                                       # S0 (centre) -> Vc (+x corner)
        full = [int(partG[v]) for v in half[::-1]] + half[1:]   # -x corner -> centre -> +x corner
        if len(set(full)) != len(full) or (np.array(full) < 0).any(): raise RuntimeError('seam path not simple / not mirrored')
        MO['path_verts'] = len(full); MO['seam_cost'] = round(float(bestv[Vc][0]), 5)
        MO['corner_dev_mm'] = round(float(np.linalg.norm(X[Vc] - cR) * 1000), 2)
        MO['centre_dev_mm'] = round(float(np.linalg.norm(X[S0] - cS) * 1000), 2)
        MO['seam_concavity_mean'] = round(float(np.mean([kap[bm.edges.get((bm.verts[a_], bm.verts[b_])).index] for a_, b_ in zip(full[:-1], full[1:])])), 3)
        dd = dsm[full]; MO['path_to_seam_mm'] = [round(float(dd.mean() * 1000), 2), round(float(dd.max() * 1000), 2)]
        fv = BV(full); pedges = [bm.edges.get((fv[i], fv[i + 1])) for i in range(len(fv) - 1)]
        mid_oi = [v[L_oi] for v in fv[1:-1]]
        upper_f = set()                                         # the upper lip side of each path edge: with outward normals the
        for i, e in enumerate(pedges):                          # upper face runs the edge -x -> +x (seen from the front, ccw)
            for f in e.link_faces:
                if (winding_vs(list(f.verts), fv[i], fv[i + 1]) > 0) == (OUTW > 0): upper_f.add(f)
        bmesh.ops.split_edges(bm, edges=pedges)
        byoi = {}
        for v in bm.verts:
            if v[L_oi] in mid_oi: byoi.setdefault(v[L_oi], []).append(v)
        up, lo = [], []; MO['bowtie_welds'] = 0
        for o in mid_oi:
            vs = byoi[o]
            dz = [1.0 if any(f in upper_f for f in v.link_faces) else -1.0 for v in vs]     # copy on the upper lip side
            if len(vs) > 2:                                     # a bow-tie vertex on the seam: weld the copies of each lip
                U_ = [v for v, z_ in zip(vs, dz) if z_ > 0]; D_ = [v for v, z_ in zip(vs, dz) if z_ <= 0]
                if not U_ or not D_: raise RuntimeError(f'rip: vertex {o} has {len(vs)} copies on one side')
                tm = {v: U_[0] for v in U_[1:]}; tm.update({v: D_[0] for v in D_[1:]})
                bmesh.ops.weld_verts(bm, targetmap=tm); MO['bowtie_welds'] += 1; vs = [U_[0], D_[0]]; dz = [1, -1]
            if len(vs) != 2: raise RuntimeError(f'rip: vertex {o} has {len(vs)} copies')
            a0, b0 = (vs[0], vs[1]) if dz[0] > dz[1] else (vs[1], vs[0]); up.append(a0); lo.append(b0)
        MO['corner_m'], MO['corner_p'] = fv[0], fv[-1]
        MO['up_v'] = [fv[-1]] + up[::-1] + [fv[0]]; MO['lo_v'] = [fv[-1]] + lo[::-1] + [fv[0]]      # +x corner -> -x corner

# ---------------------------------------------------------------- 2. rings
G = Graph(bm); X = G.X; NV = len(X); VREF = list(bm.verts)          # index -> BMVert (new vertices may reuse freed slots)
oi = np.array([v[L_oi] for v in bm.verts]) - 1; pos = {}
for i, o in enumerate(oi): pos.setdefault(int(o), []).append(i)
ER = np.zeros(NV, int); EU = np.zeros(NV); MR = np.zeros(NV, int); MU = np.zeros(NV)
def mirror_idx(i):                                             # mirror of a current vertex (rip copies: the copy on the same lip)
    o = int(oi[i])
    if o < 0: return -1
    c = pos.get(int(part[o]), [])
    if len(c) == 1: return c[0]
    return min(c, key=lambda j: np.linalg.norm(np.mean([np.array(f.calc_center_median()) for f in VREF[j].link_faces], 0) * MX
                                               - np.mean([np.array(f.calc_center_median()) for f in VREF[i].link_faces], 0)))

# ---- eyes: BFS rings from the margin, u from the margin by angle in the chart
E = EYE['L']; C, r, n, ch, w = E['C'], E['r'], E['n'], E['ch'], E['w']
marg = [v.index for v in E['cyc_v']]; Pm = X[marg]; UVm = ch.uv(Pm)
area = 0.5 * np.sum(UVm[:, 0] * np.roll(UVm[:, 1], -1) - np.roll(UVm[:, 0], -1) * UVm[:, 1])
if area < 0: marg = marg[::-1]; Pm = Pm[::-1]; UVm = UVm[::-1]           # counter-clockwise in the chart
AXL = np.array(EM['L']['A'], float); AXL /= np.linalg.norm(AXL); Am = (Pm - C) @ AXL      # corners: the margin's ends
ia, ib = int(np.argmin(Am)), int(np.argmax(Am))                         # along the corner axis (the blink turns about it)
_cv = [int(v) for v in EM['L'].get('corner_vids') or []]                # eye-fit bases: the canthus vertices (outer, inner)
_mo = [int(oi[i]) for i in marg]
if len(_cv) == 2 and all(v in _mo for v in _cv): ia, ib = _mo.index(_cv[0]), _mo.index(_cv[1]); E['corners'] = 'eyes_meta corner_vids (canthi)'
up_path = np.array(EM['L']['up_path'])
E['corner_to_rim_corner_mm'] = sorted(round(float(np.linalg.norm(up_path[[0, -1]] - Pm[i], axis=1).min() * 1000), 2) for i in (ia, ib))
i0, i1 = (ia, ib) if UVm[ia, 0] > UVm[ib, 0] else (ib, ia)              # u = 0 at the +u (+x) corner
marg = marg[i0:] + marg[:i0]; Pm = X[marg]; UVm = ch.uv(Pm); i1 = (i1 - i0) % len(marg)
sU = arc_param(Pm[:i1 + 1]); sL = arc_param(np.r_[Pm[i1:], Pm[:1]])
um = np.r_[0.5 * sU[:-1] / sU[-1], 0.5 + 0.5 * sL[:-1] / sL[-1]]
if UVm[1:i1, 1].mean() < UVm[i1 + 1:, 1].mean(): raise RuntimeError('eye: upper path below the lower one')
cm = UVm.mean(0); phm = np.arctan2(UVm[:, 1] - cm[1], UVm[:, 0] - cm[0])
thm = np.mod(phm - phm[0], 2 * np.pi); thm[0] = 0.0
thm = np.maximum.accumulate(thm + np.arange(len(thm)) * 1e-9)          # monotone round the opening
E['margin_u_monotone_fix'] = int((np.diff(np.mod(phm - phm[0], 2 * np.pi)) < 0).sum())
def eye_u_of(P):
    uv = ch.uv(P); th_ = np.mod(np.arctan2(uv[:, 1] - cm[1], uv[:, 0] - cm[0]) - phm[0], 2 * np.pi)
    return np.mod(np.interp(th_, np.r_[thm, 2 * np.pi], np.r_[um, 1.0]), 1.0)
side = (X[:, 0] > 1e-7) & (oi >= 0)
dE = bfs(G, marg, side, 10)
DM = polyline_dist(X, Pm); lim = float(np.clip(0.33 * w, 0.006, 0.014)); D = 0
for d in range(1, 11):
    ids = np.where(dE == d)[0]
    if not len(ids) or np.median(DM[ids]) > lim: break
    D = d
KE = D + 1                                                      # ring K = margin, rings K-1 .. 1 outward
ring_ids = [np.where(dE == d)[0] for d in range(D, 0, -1)]          # ring 1 .. K-1
for k, ids in enumerate(ring_ids, start=1):
    ER[ids] = k; EU[ids] = eye_u_of(X[ids])
ER[marg] = KE; EU[marg] = um
E['ring_counts'] = [len(x) for x in ring_ids] + [len(marg)]; E['bfs_rings'] = D; E['ring_lim_mm'] = round(lim * 1000, 1)
E['margin_verts'] = len(marg); E['corner_idx'] = [0, int(i1)]
lidL = np.where(ER > 0)[0]
mi = np.array([mirror_idx(i) for i in lidL])
if (mi < 0).any(): raise RuntimeError('eye ring vertex without mirror')
ER[mi] = -ER[lidL]; EU[mi] = np.mod(0.5 - EU[lidL], 1.0)
margR = [mirror_idx(i) for i in marg]
EYE['L']['marg'] = marg; EYE['R']['marg'] = margR; EYE['L']['um'] = um; EYE['R']['um'] = np.mod(0.5 - um, 1.0)

# ---- eyeball radius: kept lid skin stays outside it
PE = bpy.data.objects.get('p2_eyes'); eyes_src = 'uv_sphere'; C_ball, r_ball = C, r
if PE is not None:
    XP = np.array([tuple(v.co) for v in PE.data.vertices]); kL = XP[:, 0] > 0
    if kL.sum() > 20:
        Cf, rf = sphere_fit(XP[kL]); dP = np.linalg.norm(XP[kL] - Cf, axis=1); fr_ = (XP[kL] - Cf) @ n > 0
        r99 = float(np.percentile(dP[fr_], 99)) if fr_.sum() > 10 else rf      # the cornea bulge counts: lids slide over it
        C_ball, r_ball = Cf, max(rf, r99); eyes_src = 'p2_eyes'
        EYE['L']['p2_fit'] = {'C_mm': (Cf * 1000).round(2).tolist(), 'r_fit_mm': round(rf * 1000, 2), 'r_front99_mm': round(r99 * 1000, 2)}
gap = lambda ids, C_, r_: np.linalg.norm(X[ids] - C_, axis=1) - r_
near_eye = np.where(side & (np.linalg.norm(X - C_ball, axis=1) < r_ball + 0.004) & ((X - C_ball) @ n > 0))[0]
g_m = gap(marg, C_ball, r_ball).min(); g_l = gap(np.where(ER >= max(KE - 3, 1))[0], C_ball, r_ball).min()
g_n = gap(near_eye, C_ball, r_ball).min() if len(near_eye) else 1.0
shrink = max(0.0, 0.0006 - g_m, 0.00045 - g_l, 0.0003 - g_n)
r_eff = r_ball - shrink
for s in 'LR':
    EYE[s]['r_eff'] = r_eff; EYE[s]['r_shrink_mm'] = round(shrink * 1000, 3)
    EYE[s]['gaps_before_mm'] = {'margin_min': round(g_m * 1000, 3), 'lid_min': round(g_l * 1000, 3), 'near_min': round(g_n * 1000, 3)}

# ---- mouth: BFS rings from the slit, u by elliptic coordinates round the flattened seam
up_v, lo_v = MO['up_v'], MO['lo_v']                             # both +x corner -> -x corner (corners shared)
up_i = [v.index for v in up_v]; lo_i = [v.index for v in lo_v]
slit_i = sorted(set(up_i) | set(lo_i))
nh = int(np.argmin(np.abs(X[up_i, 0]))); nl = int(np.argmin(np.abs(X[lo_i, 0])))     # centre vertices of the lips
if abs(X[up_i[nh], 0]) > 1e-7 or abs(X[lo_i[nl], 0]) > 1e-7: raise RuntimeError('slit has no centre vertex')
Ph = X[up_i[:nh + 1]][::-1]                                     # centre -> +x corner
sH = arc_param(Ph); sig_h = sH / sH[-1]                          # 0 at the centre, 1 at the corner
sLo = arc_param(X[lo_i[:nl + 1]][::-1]); sig_l = sLo / sLo[-1]   # lower lip (its own length when the slit is open)
x_c = float(X[up_i[0], 0]); xs = np.maximum.accumulate(Ph[:, 0] + np.arange(len(Ph)) * 1e-9); zs = Ph[:, 2]
def mouth_u_of(P, upper=None):
    ax = np.abs(P[:, 0]); z_s = np.interp(ax, xs, zs); xp = P[:, 0] / x_c; zp = (P[:, 2] - z_s) / x_c
    xi = np.clip((np.hypot(xp + 1, zp) - np.hypot(xp - 1, zp)) / 2, -1, 1)
    sg_ = np.interp(np.abs(xi) * x_c, xs, sig_h)
    q = 0.25 * (1 - sg_)                                        # distance (in u) from the corner on that side
    upr = zp > 0 if upper is None else upper
    return np.where(upr, np.where(xi >= 0, q, 0.5 - q), np.where(xi >= 0, 1 - q, 0.5 + q)) % 1.0
MU[up_i[:nh + 1]] = 0.25 * (1 - sig_h[::-1]); MU[up_i[nh:]] = 0.25 + 0.25 * sig_h
MU[lo_i[:nl + 1]] = 1 - 0.25 * (1 - sig_l[::-1]); MU[lo_i[nl:]] = 0.75 - 0.25 * sig_l
MU[up_i[0]] = 0.0; MU[up_i[-1]] = 0.5
free = (ER == 0) & (oi >= 0)
dM = bfs(G, slit_i, free, 11)
cor_m = {up_i[0], up_i[-1]}                                      # lip side of every ring vertex: the nearer slit half (topology:
dMU = bfs(G, [i for i in up_i if i not in cor_m], free, 14)     # crossing lip sheets defeat a height test)
dML = bfs(G, [i for i in lo_i if i not in cor_m], free, 14)
dMU = np.where(dMU < 0, 99, dMU); dML = np.where(dML < 0, 99, dML)
DMs = polyline_dist(X, X[up_i]); limm = 0.6 * half_w; DMo = 0
for d in range(1, 12):
    ids = np.where(dM == d)[0]
    if not len(ids) or np.median(DMs[ids]) > limm: break
    DMo = d
KM = DMo + 1
mring_ids = [np.where(dM == d)[0] for d in range(DMo, 0, -1)]
for k, ids in enumerate(mring_ids, start=1):
    MR[ids] = k; up_side = np.where(dMU[ids] == dML[ids], np.nan, (dMU[ids] < dML[ids]).astype(float))
    zup = mouth_u_of(X[ids]) < 0.5                              # height test only where both halves are equally near
    MU[ids] = mouth_u_of(X[ids], np.where(np.isnan(up_side), zup, up_side > 0.5))
MR[slit_i] = KM
MO['ring_counts'] = [len(x) for x in mring_ids] + [len(slit_i)]; MO['bfs_rings'] = DMo; MO['slit_verts'] = len(slit_i)
if KM < 4: raise RuntimeError(f'only {DMo} mouth rings (rigify_fit needs the lip ring K - 2)')

# ---------------------------------------------------------------- 3. added geometry
def orient(new_faces):
    """flip new faces so every edge shared with a kept face (then with an oriented new face) is traversed opposite
    (flips happen outside any iteration over bmesh link sequences: a flip rewires the edge's radial cycle)"""
    newset = set(new_faces); fixed = set(); conflicts = 0
    queue = []
    for f in new_faces:
        flip = None
        for e in list(f.edges):
            for g in list(e.link_faces):
                if g is not f and g not in newset:
                    a_, b_ = e.verts; flip = winding_vs(list(f.verts), a_, b_) == winding_vs(list(g.verts), a_, b_); break
            if flip is not None: break
        if flip is None: continue
        if flip: f.normal_flip()
        fixed.add(f); queue.append(f)
    while queue:
        f = queue.pop()
        todo = []
        for e in list(f.edges):
            for g in list(e.link_faces):
                if g is f or g not in newset: continue
                a_, b_ = e.verts; same = winding_vs(list(f.verts), a_, b_) == winding_vs(list(g.verts), a_, b_)
                if g in fixed: conflicts += int(same); continue
                todo.append((g, same))
        for g, same in todo:
            if g in fixed: continue
            if same: g.normal_flip()
            fixed.add(g); queue.append(g)
    return conflicts, len(newset - fixed)

# ---- lid tucks (left built, right mirrored)
tuck = {}
E = EYE['L']; C = C_ball; mv = BV(E['marg']); Pm = np.array([tuple(v.co) for v in mv]); cen3 = Pm.mean(0)
dm = (Pm - C) / np.linalg.norm(Pm - C, axis=1, keepdims=True)
tout = Pm - cen3; tout -= dm * np.sum(tout * dm, 1, keepdims=True); tout /= np.linalg.norm(tout, axis=1, keepdims=True)
TR = []
for rad, arc_mm in ((r_eff + 0.0005, 0.8), (r_eff + 0.0003, 2.5)):
    al = arc_mm / 1000 / r_eff; TR.append(C + rad * (dm * math.cos(al) + tout * math.sin(al)))
new_faces = []; MVS = {s: BV(EYE[s]["marg"]) for s in "LR"}
for s, sg in (('L', 1), ('R', -1)):
    mv = MVS[s]; P1, P2 = (TR[0], TR[1]) if s == 'L' else (TR[0] * MX, TR[1] * MX)
    t1 = [bm.verts.new(tuple(p)) for p in P1]; t2 = [bm.verts.new(tuple(p)) for p in P2]
    rings = [mv, t1, t2]; nm = len(mv)
    for k in range(2):
        for i in range(nm):
            j = (i + 1) % nm
            new_faces.append(bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i])))
    for v in t1: v[L_er] = sg * (KE + 1)
    for v in t2: v[L_er] = sg * (KE + 2)
    for i, v in enumerate(t1): v[L_eu] = float(EYE[s]['um'][i]); t2[i][L_eu] = float(EYE[s]['um'][i])
    tuck[s] = (t1, t2)
c_eye, unset_eye = orient(new_faces)


# ---- mouth interior: regular rings behind the slit (organ_mouth v2 profile), the slit zipped to roll ring 1
M = 80; t = np.arange(M) / M; Q4 = M // 4
slit_sorted = sorted(slit_i, key=lambda i: MU[i]); us = MU[slit_sorted]; PS = X[slit_sorted]
SR = np.c_[[periodic_interp(t, us, PS[:, j]) for j in range(3)]].T
SR[0] = X[up_i[0]]; SR[M // 2] = X[up_i[-1]]
jj = np.arange(1, M // 2); gap_ul = np.linalg.norm(SR[jj] - SR[M - jj], axis=1)  # upper / lower lip edge at the same x
wa = np.clip((0.003 - gap_ul) / 0.002, 0, 1)[:, None]          # a (nearly) closed slit: the interior starts on the mean
mean_ul = (SR[jj] + SR[M - jj]) / 2                            # line (crossing lip sheets of a removed bag would invert it)
SR[jj] = SR[jj] + wa * (mean_ul - SR[jj]); SR[M - jj] = SR[M - jj] + wa * (mean_ul - SR[M - jj])
for j in range(1, Q4): SR[M // 2 - j] = SR[j] * MX                # exact mirror: u <-> 0.5 - u
for j in range(3 * Q4 + 1, M): SR[3 * M // 2 - j] = SR[j] * MX
SR[Q4, 0] = 0.0; SR[3 * Q4, 0] = 0.0
s_ = half_w / 0.026; mc = SR.mean(0); mc[0] = 0.0
frac = np.where(t <= 0.5, t / 0.5, (t - 0.5) / 0.5); bell = np.sin(np.pi * frac)
sgnv = np.where((t > 0) & (t < 0.5), 1.0, np.where(t > 0.5, -1.0, 0.0))
PROF = [(0.0015, 0.0010, 1.00, 'roll'), (0.0035, 0.0022, 0.99, 'roll'),
        (0.0070, 0.0065, 1.03, 'bag'), (0.0140, 0.0110, 1.06, 'bag'), (0.0230, 0.0095, 0.85, 'bag'), (0.0300, 0.0050, 0.50, 'bag')]
CAP_D, BAG_E = 0.034, 0.5
# 2026-10-13 (env LOOP_BAG=v2: the old bag): the v2 bag (30 mm deep, 0.5 x the mouth width at the back) left room only
# for a dental arch 0.36 x the mouth width (P f02: intermolar 19.7 mm, tongue 10 mm, mouth 55 mm). The bag is now an
# oral cavity: 44 mm deep (52 mm mouth), up to 1.12 x the mouth width and 2 x 13 mm high, fuller at the sides (bell^0.3);
# every bag ring is shrunk toward the slit (width and height 8 % a step) while any of its vertices is outside the skin.
if os.environ.get('LOOP_BAG', 'v3') != 'v2':
    PROF = PROF[:2] + [(0.0060, 0.0105, 1.06, 'bag'), (0.0160, 0.0140, 1.25, 'bag'), (0.0300, 0.0145, 1.22, 'bag'), (0.0440, 0.0090, 0.90, 'bag')]
    CAP_D, BAG_E = 0.050, float(os.environ.get('LOOP_BAG_E', '0.3'))
bm.verts.index_update(); bm.verts.ensure_lookup_table()
_skin_bvh = BVHTree.FromPolygons([tuple(v.co) for v in bm.verts], [[v.index for v in f.verts] for f in bm.faces])
_DIRS = [Vector(v).normalized() for v in ((0.013, 1, 0.021), (0.35, 1, -0.04), (-0.35, 1, 0.05))]
def _outside(P):
    """vertices outside the head skin: ray parity on rays running back into the head (they never pass the mouth
    opening, so it needs no cap), 3 directions, majority"""
    out = np.zeros(len(P), bool)
    for i, p in enumerate(P):
        votes = 0
        for dv in _DIRS:
            o_, n_ = Vector(tuple(p)), 0
            for _ in range(40):
                h_ = _skin_bvh.ray_cast(o_, dv, 2.0)
                if h_[0] is None: break
                n_ += 1; o_ = h_[0] + dv * 2e-6
            votes += n_ & 1
        out[i] = votes < 2
    return out
RM = []; MO['bag_rings'] = []
# throat (env LOOP_BAG_THROAT = floor drop factors of the last two cavity rings, default '1.25,1.8'; '1,1' = off): the
# floor of the back of the cavity runs down toward the throat (only the lower half of those rings, the cap follows),
# so the tongue root can curve down there instead of stopping where the floor rose (organ_teeth_v3)
THR = [float(v) for v in os.environ.get('LOOP_BAG_THROAT', '1.25,1.8').split(',')] if os.environ.get('LOOP_BAG', 'v3') != 'v2' else [1.0, 1.0]
for kb_, (dep, dz, sx, kind) in enumerate(PROF):
    fdown = THR[kb_ - (len(PROF) - 2)] if kind == 'bag' and kb_ >= len(PROF) - 2 else 1.0
    for it_ in range(12):
        Qp = SR.copy(); Qp[:, 0] = mc[0] + sx * (SR[:, 0] - mc[0]); Qp[:, 1] = SR[:, 1] + dep * s_
        Qp[:, 2] = SR[:, 2] + sgnv * dz * s_ * (bell ** BAG_E if kind == 'bag' else bell) * np.where(sgnv < 0, fdown, 1.0)
        if kind != 'bag': break
        n_out = int(_outside(Qp).sum())
        if n_out == 0: break
        sx = 1 + 0.92 * (sx - 1) if sx > 1 else 0.92 * sx; dz *= 0.92
    if kind == 'bag': MO['bag_rings'].append({'depth_mm': round(dep * s_ * 1000, 1), 'half_height_mm': round(dz * s_ * 1000, 1), 'floor_drop': fdown, 'x_scale': round(sx, 3), 'shrink_steps': it_, 'outside_after': n_out})
    RM.append([bm.verts.new(tuple(q)) for q in Qp])
cap = bm.verts.new(tuple(mc + np.array([0, CAP_D * s_, -0.5 * (THR[-1] - 1) * PROF[-1][1] * s_])))   # lowered with the throat
bm.verts.ensure_lookup_table()
R1 = RM[0]; SV = lambda i: VREF[i]
mir = {}
for i in slit_i: mir[SV(i)] = SV(mirror_idx(i))
for k in range(len(RM)):
    for j in range(M): mir[RM[k][j]] = RM[k][(M // 2 - j) % M]
q0 = [i for i in slit_sorted if MU[i] <= 0.25 + 1e-12]
q3 = [i for i in slit_sorted if MU[i] >= 0.75 - 1e-12]
tris = strip(bm, [SV(i) for i in q0], [MU[i] for i in q0], R1[:Q4 + 1], list(t[:Q4 + 1]))
tris += strip(bm, [SV(i) for i in q3] + [SV(up_i[0])], [MU[i] for i in q3] + [1.0], R1[3 * Q4:] + [R1[0]], list(t[3 * Q4:]) + [1.0])
tris += [(mir[a_], mir[c_], mir[b_]) for a_, b_, c_ in tris]
mouth_new = []; dup = 0
for tri in tris:
    try: mouth_new.append(bm.faces.new(tri))
    except ValueError: dup += 1
roll_f, bag_f = [], []
prev = R1
for k in range(1, len(RM)):
    cur = RM[k]
    for j in range(M):
        f_ = bm.faces.new((prev[j], prev[(j + 1) % M], cur[(j + 1) % M], cur[j])); (roll_f if k == 1 else bag_f).append(f_)
    prev = cur
for j in range(M): bag_f.append(bm.faces.new((prev[j], prev[(j + 1) % M], cap)))
c_mouth, unset_mouth = orient(mouth_new + roll_f + bag_f)
for f_ in new_faces + mouth_new + roll_f + bag_f: f_.smooth = SMOOTH0          # shade like the kept faces

# ---------------------------------------------------------------- 4. attributes, groups, material
bm.verts.ensure_lookup_table()
for i in range(NV):
    v = VREF[i]; v[L_er] = int(ER[i]); v[L_eu] = float(EU[i]); v[L_mr] = int(MR[i]); v[L_mu] = float(MU[i])
for k, R_ in enumerate(RM):
    for j, v in enumerate(R_): v[L_mr] = KM + 1 + k; v[L_mu] = float(t[j])
cap[L_mr] = KM + 7; cap[L_mu] = -1.0
def up_w(u, d=0.02):
    """upper-lid / upper-lip share: 1 inside (0, 0.5), 0 inside (0.5, 1), 0.5 at the corners (blend over d of u)"""
    m_ = np.mod(u, 0.5); dc = np.minimum(m_, 0.5 - m_); sd = np.where(np.mod(u, 1.0) < 0.5, 1.0, -1.0)
    return np.where(dc < 1e-9, 0.5, 0.5 + 0.5 * sd * smoothstep(dc / d))
for s in 'LR':
    for nm in ('upper', 'lower', 'skin', 'margin_upper', 'margin_lower'):
        if not N.vertex_groups.get(f'eye_{s}_{nm}'): N.vertex_groups.new(name=f'eye_{s}_{nm}')
for nm in ('mouth_upper', 'mouth_lower', 'mouth_skin', 'mouth_bag', 'mouth_slit_upper', 'mouth_slit_lower'):
    if not N.vertex_groups.get(nm): N.vertex_groups.new(name=nm)
gi = {g.name: g.index for g in N.vertex_groups}
def setw(v, name, wt):
    if wt > 1e-6: v[L_def][gi[name]] = float(wt)
for v in bm.verts:
    k = v[L_er]
    if k != 0:
        s = 'L' if k > 0 else 'R'; k = abs(k); u = v[L_eu]; wu = float(up_w(np.array([u]))[0]); corner = abs(wu - 0.5) < 1e-9
        if k <= 2: setw(v, f'eye_{s}_skin', 1.0)
        else: setw(v, f'eye_{s}_upper', wu); setw(v, f'eye_{s}_lower', 1 - wu)
        if k >= KE and not corner: setw(v, f'eye_{s}_margin_upper' if u < 0.5 else f'eye_{s}_margin_lower', 1.0)
    k = v[L_mr]
    if k > 0:
        u = v[L_mu]
        if k >= KM + 3: setw(v, 'mouth_bag', 1.0); continue
        wu = float(up_w(np.array([u]))[0]); corner = abs(wu - 0.5) < 1e-9
        if k <= KM // 2: setw(v, 'mouth_skin', 1.0)
        else: setw(v, 'mouth_upper', wu); setw(v, 'mouth_lower', 1 - wu)
        if k == KM and not corner: setw(v, 'mouth_slit_upper' if u < 0.5 else 'mouth_slit_lower', 1.0)
me = N.data
if 'mouth_inner' not in [m.name for m in me.materials if m]:
    mi = bpy.data.materials.get('mouth_inner') or bpy.data.materials.new('mouth_inner'); mi.diffuse_color = (0.35, 0.08, 0.1, 1)
    if not me.materials: me.materials.append(bpy.data.materials.get('skin') or bpy.data.materials.new('skin'))
    me.materials.append(mi)
mi_idx = [m.name for m in me.materials].index('mouth_inner')
for f_ in bag_f: f_.material_index = mi_idx

# ---------------------------------------------------------------- 5. QA on the mesh
bm.verts.ensure_lookup_table(); bm.verts.index_update(); bm.faces.index_update(); bm.normal_update()
oi_all = np.array([v[L_oi] for v in bm.verts]) - 1; XA = np.array([tuple(v.co) for v in bm.verts]); kept = oi_all >= 0
QA['kept_verts'] = int(kept.sum()); QA['kept_moved_max_mm'] = round(float(np.linalg.norm(XA[kept] - X_REF[oi_all[kept]], axis=1).max() * 1000), 9)
conf = 0; folds = 0; newset = set(new_faces + mouth_new + roll_f + bag_f)
for e in bm.edges:
    lf = e.link_faces
    if len(lf) == 2:
        a_, b_ = e.verts
        if winding_vs(list(lf[0].verts), a_, b_) == winding_vs(list(lf[1].verts), a_, b_): conf += 1
        if (lf[0] in newset or lf[1] in newset) and lf[0].normal.dot(lf[1].normal) < -0.5: folds += 1
QA['winding_conflicts'] = conf; QA['new_faces'] = len(newset); QA['folds_gt_120deg_at_new_faces'] = folds
QA['orient'] = {'eye_conflicts': c_eye, 'eye_unreached': unset_eye, 'mouth_conflicts': c_mouth, 'mouth_unreached': unset_mouth, 'zip_dup_faces': dup}
from mathutils.kdtree import KDTree
kd = KDTree(len(XA))
for i, p in enumerate(XA): kd.insert(Vector(tuple(p)), i)
kd.balance(); QA['mirror_gap_after_mm'] = round(float(max(kd.find(Vector((-p[0], p[1], p[2])))[2] for p in XA) * 1000), 6)
QA['boundary_loops'] = sorted([len(l) for l in boundary_loops(bm)], reverse=True)[:8]
lidv = [v for v in bm.verts if v[L_er] != 0]
for s, sg in (('L', 1), ('R', -1)):
    Cs = C_ball * (MX if s == 'R' else 1); ids = [v.index for v in lidv if np.sign(v[L_er]) == sg]
    g = np.linalg.norm(XA[ids] - Cs, axis=1) - r_eff; mg = np.array([abs(bm.verts[i][L_er]) == KE for i in ids])
    EYE[s]['lid_min_gap_mm'] = round(float(g.min() * 1000), 3); EYE[s]['margin_gap_mm'] = round(float(np.median(g[mg]) * 1000), 3)
    EYE[s]['margin_min_gap_mm'] = round(float(g[mg].min() * 1000), 3)
bm.verts.layers.int.remove(L_oi)
bm.to_mesh(me); bm.free(); me.update()

# ---------------------------------------------------------------- 6. eyeballs
if eyes_src == 'p2_eyes':                                      # the base's eyeball pieces, scaled about their centres with the shrink
    XP = np.array([tuple(v.co) for v in PE.data.vertices]); k_ = XP[:, 0] > 0; f_ = r_eff / r_ball
    XP[k_] = C_ball + (XP[k_] - C_ball) * f_; XP[~k_] = C_ball * MX + (XP[~k_] - C_ball * MX) * f_
    PE.data.vertices.foreach_set('co', XP.ravel()); PE.data.update(); PE.name = 'eyes'
else:
    E = EYE['L']
    bm2 = bmesh.new(); bmesh.ops.create_uvsphere(bm2, u_segments=32, v_segments=16, radius=r_eff)
    rot = Vector((0, 0, 1)).rotation_difference(Vector(tuple(E['n']))).to_matrix().to_4x4()
    bmesh.ops.transform(bm2, matrix=rot, verts=bm2.verts); bmesh.ops.translate(bm2, verts=bm2.verts, vec=Vector(tuple(E['C'])))
    bm2.verts.index_update()
    VL = [tuple(v.co) for v in bm2.verts]; FL = [[v.index for v in f.verts] for f in bm2.faces]; bm2.free()
    nl = len(VL); VV = VL + [(-x, y, z) for x, y, z in VL]; FF = FL + [[i + nl for i in f[::-1]] for f in FL]
    m2 = bpy.data.meshes.new('eyes'); m2.from_pydata(VV, [], FF); m2.update()
    for p in m2.polygons: p.use_smooth = True
    eo = bpy.data.objects.new('eyes', m2); bpy.context.scene.collection.objects.link(eo)
for nm in ('p2_lids', 'p2_mouth'):                             # base pieces the added tucks / interior replace
    o = bpy.data.objects.get(nm)
    if o is not None: o.hide_render = True; o.hide_viewport = True
N.name = 'face'; N.hide_render = False; N.hide_viewport = False        # the base keeps 'noface' hidden behind 'orig'
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)

# ---------------------------------------------------------------- 7. json
CL = np.array(C_ball, float); AL = np.array(EM['L']['A'], float)
info = {'shape': 'loop', 'irregular': True, 'ring_verts': 64, 'rings': int(KE), 'eyes': {}}
for s in 'LR':
    e = EYE[s]; f_ = MX if s == 'R' else np.ones(3)
    info['eyes'][s] = {'C': (CL * f_).tolist(), 'r': float(r_eff), 'r_meta': float(EYE['L']['r']), 'axis': (AL * f_).tolist(),
                       'view': (EYE['L']['n'] * f_).tolist(), 'width_mm': round(EYE['L']['w'] * 1000, 1), 'height_mm': round(EYE['L']['h'] * 1000, 1),
                       'mode': EYE['L']['mode'], 'margin_verts': len(e['marg']), 'ring_counts': EYE['L']['ring_counts'],
                       'bfs_rings': EYE['L']['bfs_rings'], 'rim_dev_mm': e['rim_dev_mm'], 'deleted_faces': EYE['L'].get('deleted', 0),
                       'cut': {k: EYE['L'].get(k) for k in ('cut_cost', 'band_mm', 'sigma_mm', 'edge_med_mm', 'band_verts', 'loop_turns', 'loop_poles', 'corner_to_rim_corner_mm')},
                       'r_shrink_mm': e['r_shrink_mm'], 'gaps_before_mm': e['gaps_before_mm'], 'lid_min_gap_mm': e['lid_min_gap_mm'],
                       'margin_gap_mm': e['margin_gap_mm'], 'margin_min_gap_mm': e['margin_min_gap_mm'], 'eyeball': eyes_src, 'flipped': False,
                       'r_ball_mm': round(r_ball * 1000, 3), 'p2_fit': EYE['L'].get('p2_fit'), 'inner_side_votes': EYE['L'].get('inner_side_votes'),
                       'canthus_tip': EM[s].get('canthus_tip'),           # eye-fit bases: visible inner tip (caruncle wedge apex)
                       'canthus_wedge': {k_: v_ for k_, v_ in (EM[s].get('wedge') or {}).items() if k_ in ('p2_corner_mm', 'note')} or None}
json.dump(info, open(os.path.splitext(OUT)[0] + '_eyes.json', 'w'), indent=1)
minfo = {'shape': 'loop', 'irregular': True, 'mouth_width_mm': round(2 * half_w * 1000, 1), 'ring_verts': M, 'rings': int(KM),
         'mode': MO['mode'], 'path_verts': MO['path_verts'], 'slit_verts': MO['slit_verts'], 'ring_counts': MO['ring_counts'],
         'bfs_rings': MO['bfs_rings'], 'seam': {k: MO.get(k) for k in ('seam_source', 'seam_cost', 'corner_dev_mm', 'centre_dev_mm', 'seam_concavity_mean', 'path_to_seam_mm', 'bag', 'bag_search', 'bag_deleted_faces', 'upper_votes', 'bowtie_welds')},
         'flipped': False, 'interior': {'roll_rings': 2, 'cavity_rings': 4, 'depth_mm': round(CAP_D * s_ * 1000, 1), 'bag_rings': MO.get('bag_rings')},
         'c0_mm': (mc * 1000).round(1).tolist(), 'corner_mm': (X[up_i[0]] * 1000).round(1).tolist()}
json.dump(minfo, open(os.path.splitext(OUT)[0] + '_mouth.json', 'w'), indent=1)
QA['sec'] = round(time.time() - T0, 1)
json.dump(QA, open(os.path.splitext(OUT)[0] + '_loopqa.json', 'w'), indent=1)
print('LOOPQA', json.dumps({'eyes': {s: {k: info['eyes'][s][k] for k in ('mode', 'margin_verts', 'rim_dev_mm', 'deleted_faces', 'ring_counts', 'r_shrink_mm', 'lid_min_gap_mm', 'margin_min_gap_mm')} for s in 'LR'},
                            'mouth': {k: minfo[k] for k in ('mode', 'path_verts', 'slit_verts', 'ring_counts', 'seam')}, 'qa': QA}))
