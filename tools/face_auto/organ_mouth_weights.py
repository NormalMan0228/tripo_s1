"""겹침생성 · weights for the mouth interior after rigify_fit.py (heat weights do not reach inside the head well).
tongue / teeth off the skin: heat weighting lets the DEF-tongue* bones (and DEF-teeth* where a rig has them) reach
the lips and most of the lower head, so tongueOut would drag the lip corners. Those weights are taken off every 'face'
vertex and given to the vertex's anchor instead: DEF-jaw below the mouth slit, the head (DEF-spine.006) above it,
blended across the corners (mouth rings by mouth_u like the cavity below, other skin by height against the slit line).
The tongue bones ride on jaw_master like DEF-jaw, so the lower half moves exactly as before in every key (jawOpen
too) and the upper half just stops following the jaw; the lip bones keep their weights, so mouthClose / smile /
pucker do not change. A vertex left with nothing else takes the weights of the nearest vertex on its own side of the
slit that keeps other weights (the closed slit's upper and lower vertices coincide, so the side matters), or its
anchor when there is none. The groups stay (empty) so names still resolve; the 'tongue' / teeth objects keep theirs.
lip zone (2026-10-13): upper / lower lip bones kept apart up to the corners, each lip vertex on the lip bone over it,
4 smoothing passes that never cross the slit (details at the code; env MOUTH_LIP_WEIGHTS=0 / MOUTH_LIP_SMOOTH)
inner lip roll rings: the weights of the slit vertex in the same column (they move with the lip edge); on an irregular
slit (loop_organs.py) interpolated in mouth_u between the two slit vertices of the same lip around it
cavity: lower half -> DEF-jaw 1.0, upper half -> head (DEF-spine.006) 1.0 (the teeth fill the cavity: a half that
followed the jaw only partly toward the back pushed the lower wall into the teeth on jawOpen), blended only over the
15 % of each half next to a corner (smoothstep, 0.5 / 0.5 at the corner); the cap 0.5 / 0.5. Teeth and tongue are bound by rigify_fit itself.
Usage: blender -b <rigify_fit.blend> -P organ_mouth_weights.py -- <out.blend>
"""
import bpy, sys, os, json
import numpy as np
from mathutils.kdtree import KDTree
OUT = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
face = bpy.data.objects['face']; me = face.data
rg = np.array([d.value for d in me.attributes['mouth_ring'].data]); uu = np.array([d.value for d in me.attributes['mouth_u'].data])
lip = rg[(rg > 0)]; K = int(np.max(rg)) - 7                    # slit ring (roll K+1..K+2, cavity K+3..K+6, cap K+7)
M = int((rg == K).sum())
jaw = face.vertex_groups.get('DEF-jaw'); head = face.vertex_groups.get('DEF-spine.006') or face.vertex_groups.new(name='DEF-spine.006')
sl_ids = np.where(rg == K)[0]; sl_u = uu[sl_ids]
def slit_of(u):
    """slit vertex nearest in u on the same lip (corners belong to both): the slit vertex of the same column on a
    regular ring mouth (organ_mouth: exact match), the nearest one on an irregular slit (loop_organs)"""
    d = np.abs(sl_u - u); d = np.minimum(d, 1 - d)
    ok = (sl_u <= 0.5) if u <= 0.5 else ((sl_u >= 0.5) | (sl_u == 0))
    return int(sl_ids[np.argmin(np.where(ok, d, np.inf))])
def jaw_share(u):                                               # mouth_u: upper lip 0..0.5 -> head, lower 0.5..1 -> jaw, corners and cap 0.5
    fr = np.where(u <= 0.5, u, u - 0.5) / 0.5; b = np.sqrt(np.abs(np.sin(np.pi * fr)))
    return np.where(u < 0, 0.5, np.where(u > 0.5, 0.5 + 0.5 * b, 0.5 - 0.5 * b))
def cavity_share(u, zone=0.15):                                # cavity: lower half all jaw, upper half all head, blended only
    fr = np.where(u <= 0.5, u, u - 0.5) / 0.5                   # over the 15 % of each half next to a corner; cap 0.5
    b = np.clip(np.minimum(fr, 1 - fr) / zone, 0, 1); b = b * b * (3 - 2 * b)
    return np.where(u < 0, 0.5, np.where(u > 0.5, 0.5 + 0.5 * b, 0.5 - 0.5 * b))
# ---- tongue / teeth weights off the skin, onto the jaw / head anchor (before the roll copies the slit weights)
X = np.array([tuple(v.co) for v in me.vertices]); sl = np.where(rg == K)[0]; o = np.argsort(X[sl, 0])
xs, zs = X[sl[o], 0], X[sl[o], 2]; band = 0.25 * (xs[-1] - xs[0])          # blend band across the slit line: a quarter mouth width
sz = np.clip(0.5 + (np.interp(X[:, 0], xs, zs) - X[:, 2]) / band, 0, 1)
wj = np.where(rg > 0, jaw_share(uu), sz * sz * (3 - 2 * sz))
bad = {g.index for g in face.vertex_groups if g.name.startswith(('DEF-tongue', 'DEF-teeth'))}
isdef = {g.index for g in face.vertex_groups if g.name.startswith('DEF')}
hit = {}; mem = {gi_: [] for gi_ in bad}
for v in me.vertices:
    ws = {g.group: g.weight for g in v.groups if g.group in isdef and g.weight > 0}
    if bad & ws.keys():
        hit[v.index] = ws
        for gi_ in bad & ws.keys(): mem[gi_].append(v.index)
tw = {vi: sum(w for k, w in ws.items() if k in bad) for vi, ws in hit.items()}
tq = {'verts': len(hit), 'verts_gt_1e-3': sum(b > 1e-3 for b in tw.values()), 'max_weight': round(max(tw.values(), default=0.0), 4),
      'to_jaw': round(sum(b * wj[vi] for vi, b in tw.items()), 2), 'to_head': round(sum(b * (1 - wj[vi]) for vi, b in tw.items()), 2), 'orphans': 0}
for gi_, vs in mem.items():
    if vs: face.vertex_groups[gi_].remove(vs)
orph = []
for vi, ws in hit.items():
    if sum(w for k, w in ws.items() if k not in bad) <= 1e-6: orph.append(vi); continue
    for gi_, x in ((jaw.index, tw[vi] * wj[vi]), (head.index, tw[vi] * (1 - wj[vi]))):
        if x > 1e-7: face.vertex_groups[gi_].add([vi], float(ws.get(gi_, 0.0) + x), 'REPLACE')
if orph:                                                        # only tongue / teeth: borrow from the nearest same-side vertex
    lo = wj >= 0.5; os_ = set(orph); kds = {}
    pool = [v.index for v in me.vertices if v.index not in os_ and any(g.group in isdef and g.weight > 0 for g in v.groups)]
    for side in (False, True):
        ids = [i for i in pool if lo[i] == side]; kd = KDTree(max(len(ids), 1))
        for j, i in enumerate(ids): kd.insert(X[i], j)
        kd.balance(); kds[side] = (kd, ids)
    for vi in orph:
        kd, ids = kds[bool(lo[vi])]; tot = sum(hit[vi].values())
        if ids: ws = {g.group: g.weight for g in me.vertices[ids[kd.find(X[vi])[1]]].groups if g.group in isdef and g.weight > 0}
        else: ws = {jaw.index: wj[vi], head.index: 1 - wj[vi]}
        s = sum(ws.values())
        for gi_, w in ws.items(): face.vertex_groups[gi_].add([vi], float(w * tot / s), 'REPLACE')
    tq['orphans'] = len(orph)
# ---- lip zone: upper / lower lip bones kept apart up to the corners (env MOUTH_LIP_WEIGHTS=0: off)
# Heat weights + 40 smoothing passes share the lip bones across the slit near the corners (P f02: a lower-lip slit
# vertex 1.4 mm from the corner carried 0.22 DEF-lip.T.L.003; upper/lower weight separation 0.22 at 5 % of the half
# width, 0.43 at 10 %; f11 0.22 / 0.22 / 0.35 at 20 %) and smear each lip bone over its neighbours (corner vertex: 0.22
# of the inner DEF-lip.T.L.001), so the corners stay shut on jawOpen and lag the corner control in smile / stretch.
# Inside the lip zone (distance to the slit <= D1 = max(lip-joint ring distance, 0.15 half width), fading out by 2 D1)
# the lip-bone mass of a vertex (plus the jaw / chin bones on the upper lip and nose / cheek.T bones on the lower lip)
# goes to the DEF-lip.T chain on the upper side and the DEF-lip.B chain on the lower side (side from mouth_u: slit
# vertices exactly, ring vertices blended only round the corner column, a little wider further from the slit; the
# corner itself 0.5 / 0.5), and along the lip to the bone whose span (in x) holds the vertex, cross-faded over a
# quarter bone at each joint. Every other bone keeps its heat weight; totals are unchanged.
import re
rig = next((m.object for m in face.modifiers if m.type == 'ARMATURE' and m.object), None)
lipq = {'on': False}
def lip_sep_stats():
    """upper / lower weight separation (0 = same weights, 1 = disjoint) of slit vertex pairs at f of the half width from each corner"""
    up_ = sl_ids[(sl_u > 0) & (sl_u < 0.5)]; lo_ = sl_ids[sl_u > 0.5]; xc_ = float(np.abs(X[sl_ids, 0]).max()); out = {}
    def wd(i): return {face.vertex_groups[g.group].name: g.weight for g in me.vertices[int(i)].groups if face.vertex_groups[g.group].name.startswith('DEF')}
    for f in (0.05, 0.1, 0.2, 0.3):
        s_ = []
        for sx in (1, -1):
            x = sx * xc_ * (1 - f); iu = up_[np.argmin(np.abs(X[up_, 0] - x))]; il = lo_[np.argmin(np.abs(X[lo_, 0] - x))]
            a_, b_ = wd(iu), wd(il); s_.append(0.5 * sum(abs(a_.get(k, 0) - b_.get(k, 0)) for k in set(a_) | set(b_)))
        out[f] = round(float(np.mean(s_)), 3)
    return out
if os.environ.get('MOUTH_LIP_WEIGHTS', '1') != '0' and rig is not None:
    Minv = np.array(face.matrix_world.inverted() @ rig.matrix_world)
    def to_face(p): return (Minv @ np.r_[np.array(p), 1.0])[:3]
    def spans_of(tb):
        bs = [b for b in rig.data.bones if b.use_deform and re.match(r'DEF-lip\.%s\.[LR](\.\d+)?$' % tb, b.name)]
        sp = sorted([(min(h, t), max(h, t), b.name) for b in bs for h, t in [(to_face(b.head_local)[0], to_face(b.tail_local)[0])]])
        return sp
    SP = {'T': spans_of('T'), 'B': spans_of('B')}
    if len(SP['T']) >= 2 and len(SP['T']) == len(SP['B']):
        def prof(x, sp):
            n = len(sp); w = np.ones(n)
            for i in range(n):
                lo_, hi_ = sp[i][0], sp[i][1]
                if i > 0:
                    c = 0.25 * min(hi_ - lo_, sp[i - 1][1] - sp[i - 1][0]); w[i] = min(w[i], np.clip(0.5 + (x - lo_) / (2 * max(c, 1e-6)), 0, 1))
                if i < n - 1:
                    c = 0.25 * min(hi_ - lo_, sp[i + 1][1] - sp[i + 1][0]); w[i] = min(w[i], np.clip(0.5 + (hi_ - x) / (2 * max(c, 1e-6)), 0, 1))
            return w / max(w.sum(), 1e-9)
        sep_before = lip_sep_stats()
        gidx = {g.name: g.index for g in face.vertex_groups}
        for tb in 'TB':
            for _, _, n in SP[tb]:
                if n not in gidx: gidx[n] = face.vertex_groups.new(name=n).index
        lipT = [n for _, _, n in SP['T']]; lipB = [n for _, _, n in SP['B']]; lipset = set(lipT) | set(lipB)
        is_jaw = lambda n: n.startswith(('DEF-jaw', 'DEF-chin'))
        is_up = lambda n: n.startswith(('DEF-nose', 'DEF-cheek.T'))
        from mathutils.kdtree import KDTree as _KD
        kd_s = _KD(len(sl_ids))
        for j, i in enumerate(sl_ids): kd_s.insert(X[i], j)
        kd_s.balance()
        dsl = np.array([kd_s.find(X[i])[2] for i in range(len(X))])
        xc = float(np.abs(X[sl_ids, 0]).max())
        r2 = np.where(rg == K - 2)[0]
        D1 = max(float(np.median(dsl[r2])) if len(r2) else 0.0, 0.15 * xc); D2 = 2 * D1
        zone = np.where((rg >= 1) & (rg <= K) & (dsl < D2))[0]
        # lip side fix (2026-10-13, P f09): where the cut path steps like a staircase near a corner, a few BFS-ring vertices
        # sitting on the upper lip carry a lower-lip mouth_u (or the reverse) and share edges with the other lip's vertices;
        # with the side taken from mouth_u they got half the other lip's motion and the smoothing below mixed both lips
        # across those edges, so on jawOpen the lips stayed joined by a stretched strip a quarter mouth width in from each
        # corner. Local relabel: a ring vertex (rings K-4..K-1, away from the corner column) whose skin neighbours are
        # mostly on the other side takes that side (2 passes). env MOUTH_SIDE_FIX=0: mouth_u only.
        u_side = np.where(np.minimum(uu % 0.5, 0.5 - uu % 0.5) < 1e-6, 0, np.where((uu % 1.0) < 0.5, 1, -1))
        geo_side = u_side.copy()
        if os.environ.get('MOUTH_SIDE_FIX', '1') != '0':
            cand = (rg >= K - 4) & (rg <= K - 1) & (np.minimum(uu % 0.5, 0.5 - uu % 0.5) > 0.03)
            nb_ = {}
            for e in me.edges:
                a_, b_ = e.vertices
                if 1 <= rg[a_] <= K and 1 <= rg[b_] <= K: nb_.setdefault(a_, []).append(b_); nb_.setdefault(b_, []).append(a_)
            for _ in range(2):
                gs = geo_side.copy()
                for i_ in np.where(cand)[0]:
                    sides = [geo_side[j] for j in nb_.get(int(i_), []) if geo_side[j] != 0]
                    if len(sides) >= 3:
                        other = sum(1 for x_ in sides if x_ == -geo_side[i_])
                        if other > len(sides) / 2: gs[i_] = -geo_side[i_]
                geo_side = gs
        side_fix = int(((geo_side != u_side) & (u_side != 0)).sum())
        nz = 0
        SB0, SB1 = (float(v) for v in os.environ.get('MOUTH_SIDE_BLEND', '0.003,0.010').split(','))   # side blend width in u: SB0 + SB1 * rings from the slit
        for vi in zone:
            vi = int(vi); d_ = dsl[vi]; t = 1.0 if d_ <= D1 else float(1 - (lambda s: s * s * (3 - 2 * s))((d_ - D1) / (D2 - D1)))
            if t <= 1e-4: continue
            u = float(uu[vi]); r = K - int(rg[vi]); m_ = u % 0.5; dc = min(m_, 0.5 - m_)
            sd = float(geo_side[vi]) if geo_side[vi] != 0 else (1.0 if u < 0.5 else -1.0)
            if dc < 1e-9: wu = 0.5
            elif r == 0: wu = 1.0 if sd > 0 else 0.0
            else:
                du = SB0 + SB1 * r; s_ = min(dc / du, 1.0); wu = 0.5 + 0.5 * sd * s_ * s_ * (3 - 2 * s_)
            ws = {face.vertex_groups[g.group].name: g.weight for g in me.vertices[vi].groups if g.weight > 0 and face.vertex_groups[g.group].name.startswith('DEF')}
            m_lip = sum(w for n, w in ws.items() if n in lipset)
            Jm = wu * sum(w for n, w in ws.items() if is_jaw(n)); Um = (1 - wu) * sum(w for n, w in ws.items() if is_up(n))
            M_ = m_lip + Jm + Um
            if M_ <= 1e-6: continue
            x = float(X[vi, 0]); pT = prof(x, SP['T']); pB = prof(x, SP['B'])
            new = {n: (1 - t) * ws.get(n, 0.0) for n in lipset}
            for k_, n in enumerate(lipT): new[n] += t * M_ * wu * pT[k_]
            for k_, n in enumerate(lipB): new[n] += t * M_ * (1 - wu) * pB[k_]
            for n, w in ws.items():
                if is_jaw(n) and n not in lipset: new[n] = w * (1 - t * wu)
                elif is_up(n) and n not in lipset: new[n] = w * (1 - t * (1 - wu))
            for n, w in new.items():
                if w > 1e-5: face.vertex_groups[gidx[n]].add([vi], float(w), 'REPLACE')
                elif n in ws: face.vertex_groups[gidx[n]].remove([vi])
            nz += 1
        # a few smoothing passes round the lips (rings 1..K-1 within 1.5 D2 of the slit; slit vertices stay fixed, so
        # nothing crosses it), so the zone edge and the corner column blend into the heat weights (env MOUTH_LIP_SMOOTH)
        NSM = int(os.environ.get('MOUTH_LIP_SMOOTH', '4'))
        sm = np.where((rg >= 1) & (rg < K) & (dsl < 1.5 * D2))[0]
        if NSM > 0 and len(sm):
            nbr = {int(i): [] for i in sm}; skin_ok = (rg >= 1) & (rg <= K)
            same = lambda p, q: geo_side[p] == 0 or geo_side[q] == 0 or geo_side[p] == geo_side[q]   # never average across the lips
            for e in me.edges:
                a_, b_ = e.vertices
                if a_ in nbr and skin_ok[b_] and same(a_, b_): nbr[a_].append(b_)
                if b_ in nbr and skin_ok[a_] and same(a_, b_): nbr[b_].append(a_)
            defg = [g.index for g in face.vertex_groups if g.name.startswith('DEF')]; col = {gi_: j for j, gi_ in enumerate(defg)}
            Wm = np.zeros((len(X), len(defg)), np.float32)
            for v in me.vertices:
                for g in v.groups:
                    if g.group in col: Wm[v.index, col[g.group]] = g.weight
            for _ in range(NSM):
                Wn = Wm.copy()
                for i, nb in nbr.items():
                    if nb: Wn[i] = 0.5 * Wm[i] + 0.5 * Wm[nb].mean(0)
                Wm = Wn
            for i in nbr:
                row = Wm[i]; s_ = row.sum()
                if s_ <= 1e-9: continue
                row = row / s_ * sum(g.weight for g in me.vertices[i].groups if g.group in col)
                for j, gi_ in enumerate(defg):
                    if row[j] > 1e-5: face.vertex_groups[gi_].add([i], float(row[j]), 'REPLACE')
                    elif any(g.group == gi_ for g in me.vertices[i].groups): face.vertex_groups[gi_].remove([i])
        lipq = {'on': True, 'zone_verts': nz, 'D1_mm': round(D1 * 1000, 2), 'D2_mm': round(D2 * 1000, 2), 'chain_bones': len(lipT),
                'smooth_passes': NSM, 'smoothed_verts': int(len(sm)), 'side_relabelled': side_fix,
                'sep_before': sep_before, 'sep_after': lip_sep_stats()}
def set_only(vi, ws):
    for g in face.vertex_groups:
        if g.index not in ws and g.name.startswith('DEF'):   # organ groups (mouth_bag, ...) stay
            try: g.remove([vi])
            except RuntimeError: pass
    for gi_, w in ws.items(): face.vertex_groups[gi_].add([vi], float(w), 'REPLACE')
n_roll = n_cav = 0
# roll weights: the slit weights interpolated in mouth_u between the two slit vertices of the same lip around the roll
# vertex (an irregular slit has fewer vertices than the 80-vertex roll ring: the nearest-vertex copy moved the inner
# lip in steps, visible as a jagged inner edge once the lips part at the corners); env MOUTH_ROLL_INTERP=0: nearest
ROLL_INTERP = os.environ.get('MOUTH_ROLL_INTERP', '1') != '0'
def dw(i): return {g.group: g.weight for g in me.vertices[int(i)].groups if face.vertex_groups[g.group].name.startswith('DEF')}
cor0 = [int(sl_ids[k]) for k in range(len(sl_ids)) if min(sl_u[k] % 0.5, 0.5 - sl_u[k] % 0.5) < 1e-9]
c_p = next((i for i in cor0 if uu[i] < 0.25 or uu[i] > 0.75), None); c_m = next((i for i in cor0 if 0.25 <= uu[i] <= 0.75), None)
UPL = sorted([(float(uu[i]), int(i)) for i in sl_ids if 0 < uu[i] < 0.5] + ([(0.0, c_p)] if c_p is not None else []) + ([(0.5, c_m)] if c_m is not None else []))
LOL = sorted([(float(uu[i]), int(i)) for i in sl_ids if uu[i] > 0.5] + ([(0.5, c_m)] if c_m is not None else []) + ([(1.0, c_p)] if c_p is not None else []))
def roll_w(u):
    L_ = UPL if u <= 0.5 else LOL
    if u == 0.0 and L_ is LOL: u = 1.0
    us_ = [a_ for a_, _ in L_]; j = int(np.clip(np.searchsorted(us_, u) - 1, 0, len(L_) - 2))
    (u0, i0), (u1, i1) = L_[j], L_[j + 1]; t = float(np.clip((u - u0) / max(u1 - u0, 1e-9), 0, 1))
    a_, b_ = dw(i0), dw(i1); return {k: (1 - t) * a_.get(k, 0.0) + t * b_.get(k, 0.0) for k in set(a_) | set(b_)}
for vi in np.where((rg == K + 1) | (rg == K + 2))[0]:
    if ROLL_INTERP and len(UPL) >= 2 and len(LOL) >= 2: ws_ = roll_w(float(uu[vi]))
    else: ws_ = dw(slit_of(float(uu[vi])))
    set_only(int(vi), {k: w for k, w in ws_.items() if w > 1e-6}); n_roll += 1
# the cavity rings next to the lips (the vestibule) move partly with the lips: in smile / pucker the lip skin moves
# 8-14 mm while a cavity bound only to jaw / head stayed and showed through the lower lip (P f09 smile, worse with
# the larger v3 cavity). First cavity ring 100 % lip weights (as the roll), second 60 %; env MOUTH_VESTIBULE='1.0,0.6' ('0': off)
_vs = [float(v) for v in os.environ.get('MOUTH_VESTIBULE', '1.0,0.6').split(',') if v.strip()]
_cw = [float(v) for v in os.environ.get('MOUTH_CORNER_WALL', '1.0,1.0,0.6,0.3').split(',') if v.strip()]   # cavity rings K+3.. near the corners
CORNER_WALL = {K + 3 + i: f for i, f in enumerate(_cw) if f > 0}
VEST = {K + 3 + i: f for i, f in enumerate(_vs) if f > 0} if ROLL_INTERP and len(UPL) >= 2 and len(LOL) >= 2 else {}
for vi in np.where(rg >= K + 3)[0]:
    w_ = float(cavity_share(uu[vi])); ws_ = {jaw.index: w_, head.index: 1 - w_}; fl_ = VEST.get(int(rg[vi]), 0.0)
    if fl_ > 0 and uu[vi] >= 0:
        lw_ = roll_w(float(uu[vi])); ws_ = {k: (1 - fl_) * ws_.get(k, 0.0) + fl_ * lw_.get(k, 0.0) for k in set(ws_) | set(lw_)}
    # the cavity's side walls next to the corners (inside the cheek) move with the mouth corner: in smile the corner
    # goes 8 mm out and 15 mm up, and a wall bound to jaw / head poked out beside it (P f11, red slivers)
    fc_ = CORNER_WALL.get(int(rg[vi]), 0.0)
    if fc_ > 0 and uu[vi] >= 0 and c_p is not None and c_m is not None:
        um_ = float(uu[vi]) % 0.5; dc_ = min(um_, 0.5 - um_); s_ = min(max(1 - dc_ / 0.10, 0.0), 1.0); fc_ *= s_ * s_ * (3 - 2 * s_)
        if fc_ > 0:
            cw_ = dw(c_p if (uu[vi] < 0.25 or uu[vi] > 0.75) else c_m)
            ws_ = {k: (1 - fc_) * ws_.get(k, 0.0) + fc_ * cw_.get(k, 0.0) for k in set(ws_) | set(cw_)}
    set_only(int(vi), {k: w for k, w in ws_.items() if w > 1e-6}); n_cav += 1
left = sum(1 for v in me.vertices if any(g.group in bad and g.weight > 0 for g in v.groups))
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('MOUTHW', json.dumps({'slit_ring': K, 'ring_verts': M, 'roll_verts': n_roll, 'cavity_verts': n_cav, 'lip_zone': lipq,
                            'tongue_teeth_off_skin': dict(tq, groups=sorted(face.vertex_groups[i].name for i in bad), left_after=left)}))
