"""M1 · teeth + gums and tongue v3 for a ring mouth (loop_organs.py / organ_mouth.py), fitted into the oral cavity of
each head. Drop-in for organ_teeth.py (v2): same objects (teeth_up on the head, teeth_lo on the jaw, tongue for the
3 tongue bones along y), same materials ('teeth', 'gums' in teeth_up / teeth_lo, 'tongue'), exact L/R mirror symmetry
(sym_lock pairs them), same QA line / <out>_teeth.json keys plus the arch metrics.

What changed against v2 and why (2026-10-13, user: "the teeth arch is too U-shaped; the tongue should look like a
tongue; make the teeth together with the gums"):
1. Natural dental arch. v2 ran a quarter ellipse into two parallel straight lines (a U). v3 puts the crown centres on
   a parabolic arch y = yf + D (al u^2 + (1 - al) u^4), u = 2x / W (a Bonwill-Hawley / Braun beta-like curve: wide,
   flat incisor curve, canines at the turn, premolars and molars diverging backwards, widest at the second molars).
   Canonical upper arch at tooth scale 1: W = 52 mm, D = 39 mm, al = 0.30 -> crown-centre widths canine 32,
   first molar 48 mm (canine / first molar 0.67; adult norms ~0.70 upper, ~0.60 lower). The lower arch is the
   upper one offset inward along its normal (overjet + incisor thickness in front, lower buccal cusps under the upper
   central fossae at the back), so it keeps the same natural shape, inside the upper one. Search per head: the
   largest tooth scale q for which a near-natural arch (arch scale ka >= 0.93 against the teeth, width / depth
   aspect r 0.86-1.08, front flatness al 0.24-0.46, posterior scale kp 0.8-1, incisal edge 2.5-12 mm behind the
   slit) fits every crown + root stub + minimal gum into the eroded cavity; then, at 4 scales under it, the best
   shape by a score that keeps the natural shape first (r, al), full-size posterior teeth, crowns at full height,
   and the upper incisors close behind the lip (gap over 2.5 mm costs), the larger scale winning ties. On the four
   test heads every arch came out at ka 0.93-1, r = 1, al = 0.30: canine / first molar 0.67-0.69 upper,
   0.59-0.61 lower, posterior segments diverging 14-16 deg per side (v2: 0.78, ~3 deg).
2. Gums made with the teeth: one gum per jaw, swept along the same tooth frames as the crowns: a scalloped margin
   that hugs every crown neck (gingival zenith at the middle of each tooth, papillae up into the embrasures between
   teeth), attached gingiva bulging over the roots and running on to the vestibule (labial: up / down to where the
   lips cover it) and to the lingual side; the root stubs sit inside it, so no gap shows between tooth and gum. The
   labial / lingual gum depth is fitted per section to the cavity (largest that fits, smoothed along the arch), not
   pressed flat; the deep part runs on a smoothed arch frame (no per-tooth steps at the vestibule edge). Rounded
   ends behind the last molars (tuberosity / retromolar pad), shortened where the cavity ends. (v2 stopped the gum
   frame at the last tooth centre: the distal half of the last molar had stacked sections; fixed here.)
3. Tongue: its own tongue-shaped mesh (1410 verts): planform with a rounded tip tapering over the front third, the
   back two thirds as wide as the lower arch allows (each section's outline kept 0.7 mm off every lower tooth / gum
   point near it, so the lateral borders lie just inside the lingual gums), reaching back to the lower second
   molars; dorsum arched and thicker toward the root, a median sulcus (deepest in the middle third, fading at the
   tip and at the back), rounded lateral margins; underside free under the tip and blending smoothly down onto the
   mouth floor (attached by ~40 % of the length), with a soft lingual frenulum fold; the root: over the last quarter
   the dorsum curves down onto the floor (a thick rounded end, no thin edge; the cavity runs on behind it like the
   throat), never past where the rising cavity floor leaves < 30 % of the deepest room. Section outlines are
   resampled with more vertices at the sulcus, the lateral margins and the frenulum. Top at or below the lower
   occlusal plane, tip just behind the lower incisors. (v2's tongue pole fans were wound against its quads: fixed.)
4. Materials: enamel (vertex colour: warmer at the neck, bluish translucent toward the incisal edges / cusp tips:
   attribute 'enamel_edge' drives transmission), pink gums (redder toward the vestibule), pink-red tongue (vertex
   colour: paler coated dorsum, darker sulcus, redder tip / margins, darker underside; base colour = the mean of the
   MakeHuman tongue01_diffuse.png, CC0). Colour attribute 'Col'. UVs as uv_parts.py lays them out (teeth / gums:
   cylindrical about the arch, gums in the right half; tongue: top-down planar, tip at v = 1).

Assets: evaluated the MakeHuman / MPFB CC0 teeth (teeth_base: 32 low-poly crowns of 63 verts + one gum mesh joining
both jaws, intercanine 26 / intermolar 34 mm, also near-parallel posterior segments) and tongue01 (226 verts, curled,
placed above the teeth). Neither keeps a natural arch or survives a per-head fit better than the parametric crowns,
so v3 is procedural (crown shapes from v2, Wheeler crown sizes) and only uses the CC0 tongue diffuse for its colour.
MakeHuman assets: CC0 since September 2020, (C) 2020 Data Collection AB, Joel Palmius, Jonas Hauquier,
http://www.makehumancommunity.org.

Cavity, crowns, frames, overbite / overjet, the lower set-back and the QA follow v2 (see organ_teeth.py).
Usage: blender -b <eyes.blend> -P organ_teeth_v3.py -- <mouth.json> <out.blend>
(env TEETH_ZF: occlusal plane drop at the incisors, mm at a 52 mm mouth, default 2; TEETH_QSLACK: share of the
largest fitting tooth scale tried first, default 0.96; TEETH_KAMIN: smallest arch scale still called natural,
default 0.93 (fallback 0.68 when nothing fits); TEETH_QW: weight of the tooth size against the shape, default 4;
TEETH_GAPW: score per mm of incisor-lip gap over 2.5 mm, default 0.12; TEETH_DEBUG: print the natural-shape trials)
Extra outputs: 'tongue' point attributes tongue_v (0 tip .. 1 back) and tongue_top (1 dorsum, 0 underside) for
smooth weights; json tongue_chain_proposal_m (5 joints tip -> root on the tongue mid-line), room_outline_occlusal
(cavity footprint at the occlusal level, x >= 0) for views.
"""
import bpy, sys, os, json, math, time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index('--') + 1:]
MJ, OUT = a[0], os.path.abspath(a[1]); T0 = time.time()
J = json.load(open(MJ)); half = abs(J['corner_mm'][0]) / 1000; S = half / 0.026     # interior sizes are for a 52 mm mouth
MM = 1e-3
for n in ('teeth_up', 'teeth_lo', 'tongue'):
    if n in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[n])
F = bpy.data.objects['face']; me = F.data; MW = np.array(F.matrix_world)
X = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', X); X = X.reshape(-1, 3) @ MW[:3, :3].T + MW[:3, 3]
rg = np.empty(len(X), np.int32); me.attributes['mouth_ring'].data.foreach_get('value', rg)
mu = np.empty(len(X), np.float32); me.attributes['mouth_u'].data.foreach_get('value', mu)
SL = int(J.get('rings', 12))                                  # slit ring; behind it: roll, cavity rings, cap
sl = np.where(rg == SL)[0]; ctr = sl[np.argmin(np.abs(mu[sl] - 0.25))]; Z0, YS = X[ctr, 2], X[ctr, 1]
lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_start', ls)
lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
od = np.argsort(ls); rmin = np.empty(len(ls), np.int32); rmax = np.empty(len(ls), np.int32)
rmin[od] = np.minimum.reduceat(rg[lv], ls[od]); rmax[od] = np.maximum.reduceat(rg[lv], ls[od])
polys = lambda sel: [lv[ls[i]:ls[i] + lt[i]].tolist() for i in np.where(sel)[0]]
XL = X.tolist()
BAG = BVHTree.FromPolygons(XL, polys(rmin >= SL))
slo = sl[np.argsort(mu[sl])]; fan = [[int(slo[i]), int(slo[(i + 1) % len(slo)]), len(X)] for i in range(len(slo))]
ENV = BVHTree.FromPolygons(XL + [tuple(X[sl].mean(0))], polys(rmax <= SL) + fan)   # skin up to the slit + a fan over it
info = {'version': 3, 'mouth_width_mm': round(2000 * half, 1), 'S': round(float(S), 3)}

# ---- 1. cavity height field (x >= 0 cast, mirrored), eroded by CLR (as v2)
CLR, HX = 0.25 * MM * S, 0.3 * MM * S
B3 = X[rg >= SL]; xs = np.arange(0, B3[:, 0].max() + 2 * HX, HX); ys = np.arange(B3[:, 1].min() - HX, B3[:, 1].max() + 2 * HX, HX)
zlo = B3[:, 2].min() - 0.002; UPV = Vector((0, 0, 1))
FL = np.full((len(ys), len(xs)), np.nan); CE = FL.copy()
for i, y in enumerate(ys):
    for j, x in enumerate(xs):
        h = BAG.ray_cast(Vector((x, y, zlo)), UPV, 1.0)
        if h[0] is None: continue
        h2 = BAG.ray_cast(h[0] + UPV * 1e-6, UPV, 1.0)
        if h2[0] is not None: FL[i, j], CE[i, j] = h[0].z, h2[0].z
XS = np.r_[-xs[:0:-1], xs]; FL = np.hstack([FL[:, :0:-1], FL]); CE = np.hstack([CE[:, :0:-1], CE])
r_ = int(math.ceil(CLR / HX)); H_, W_ = FL.shape
Fp = np.pad(FL, r_, constant_values=np.nan); Cp = np.pad(CE, r_, constant_values=np.nan)
FE = np.full_like(FL, -np.inf); CEe = np.full_like(CE, np.inf)
for di in range(-r_, r_ + 1):
    for dj in range(-r_, r_ + 1):
        if di * di + dj * dj <= r_ * r_:                       # NaN (no cavity) spreads: np.maximum keeps NaN
            FE = np.maximum(FE, Fp[r_ + di:r_ + di + H_, r_ + dj:r_ + dj + W_]); CEe = np.minimum(CEe, Cp[r_ + di:r_ + di + H_, r_ + dj:r_ + dj + W_])
FE, CEe = FE + CLR, CEe - CLR; bad_ = ~(CEe > FE); FE[bad_] = np.nan; CEe[bad_] = np.nan

def room(P):
    """eroded floor and ceiling over the columns of P (bilinear; NaN where any corner has no cavity)"""
    fx, fy = (P[:, 0] - XS[0]) / HX, (P[:, 1] - ys[0]) / HX
    j0, i0 = np.floor(fx).astype(int), np.floor(fy).astype(int); tx, ty = fx - j0, fy - i0
    ok = (i0 >= 0) & (j0 >= 0) & (i0 < H_ - 1) & (j0 < W_ - 1); i0, j0 = np.clip(i0, 0, H_ - 2), np.clip(j0, 0, W_ - 2)
    bil = lambda G: G[i0, j0] * (1 - tx) * (1 - ty) + G[i0, j0 + 1] * tx * (1 - ty) + G[i0 + 1, j0] * (1 - tx) * ty + G[i0 + 1, j0 + 1] * tx * ty
    f, c = bil(FE), bil(CEe); f[~ok] = np.nan; c[~ok] = np.nan
    return f, c
def fits(P):
    f, c = room(P); return (P[:, 2] > f) & (P[:, 2] < c)

# ---- 2. crowns (as v2). Tooth space: x mesiodistal (+ distal), y labial / buccal, z from the cervical line (0) to
#      the occlusal end (h); below 0 a root stub that stays inside the gum
NT, VR, CAP = 16, np.array([0, .15, .35, .55, .75, .9, 1.0]), np.array([.8, .58, .36, .15])
TH = 2 * np.pi * np.arange(NT) / NT
def se(n): c, s_ = np.cos(TH), np.sin(TH); return np.sign(c) * np.abs(c) ** (2 / n), np.sign(s_) * np.abs(s_) ** (2 / n)
PROF = {'inc': ([.70, .78, .88, .96, 1.0, 1.0, .96], [.95, 1.0, .88, .66, .44, .27, .15], [.95, 1.0, .98, .92, .84, .77, .71], 2.6),
        'can': ([.66, .76, .88, .97, 1.0, .97, .90], [.92, 1.0, .92, .78, .60, .45, .30], [.94, 1.0, 1.0, .96, .90, .84, .78], 2.4),
        'pm':  ([.74, .84, .94, 1.0, .99, .95, .87], [.84, .93, 1.0, 1.0, .95, .87, .76], None, 2.4),
        'mol': ([.80, .88, .96, 1.0, .99, .95, .88], [.84, .92, .99, 1.0, .96, .89, .80], None, 2.8)}
PM_U = [(0, .42, 1, .5), (0, -.42, .9, .5), (-.75, 0, .5, .3), (.75, 0, .5, .3)]
PM_L1 = [(0, .35, 1, .55), (0, -.55, .55, .4), (-.75, 0, .45, .3), (.75, 0, .45, .3)]
PM_L2 = [(0, .38, 1, .5), (-.28, -.45, .8, .38), (.3, -.45, .7, .38), (-.75, 0, .45, .3), (.75, 0, .45, .3)]
M_U = [(-.42, .45, 1, .45), (.45, .45, .92, .42), (-.38, -.42, 1, .5), (.5, -.5, .7, .38)]
M_U2 = [(-.4, .45, 1, .45), (.45, .45, .85, .4), (-.35, -.42, .95, .5), (.55, -.5, .45, .35)]
M_L = [(-.55, .45, 1, .4), (0, .5, .95, .4), (.62, .38, .8, .35), (-.5, -.45, 1, .42), (.42, -.45, .95, .42)]
#   class, w, t, h (mm, Wheeler), crown inclination (deg, + = occlusal end labial / buccal), options
UP = [('inc', 8.5, 7.0, 10.5, 16, dict(rd=.12, fos=.22)), ('inc', 6.6, 6.0, 9.0, 12, dict(rd=.25, fos=.25)),
      ('can', 7.6, 8.0, 10.0, 8, dict(fos=.12)), ('pm', 7.0, 9.0, 8.2, 5, dict(cu=PM_U)), ('pm', 6.6, 9.0, 7.8, 5, dict(cu=PM_U)),
      ('mol', 10.2, 11.0, 7.2, 4, dict(cu=M_U)), ('mol', 9.0, 11.0, 6.6, 4, dict(cu=M_U2))]
LO = [('inc', 5.2, 5.8, 9.0, 18, dict(fos=.08)), ('inc', 5.8, 6.2, 9.4, 16, dict(rd=.06, fos=.1)),
      ('can', 6.9, 7.6, 10.6, 9, dict(fos=.08)), ('pm', 7.0, 7.6, 8.2, 3, dict(cu=PM_L1)), ('pm', 7.2, 8.2, 7.8, 2, dict(cu=PM_L2)),
      ('mol', 11.0, 10.4, 7.2, 2, dict(cu=M_L)), ('mol', 10.4, 10.0, 6.8, 2, dict(cu=M_L))]
GUM_H, GUM_M = 2.2, 0.3                                        # minimal gum beyond the cervical line, margin over it (mm)
NU_MIN, NU_FRONT, OB, GP = 0.62, 0.85, 1.5, 0.5                # min crown height fraction (front teeth); overbite, posterior gap (mm)
KP = (1.0, .9, .8)                                             # premolars + molars may be this much smaller than the front teeth
Q_SLACK = float(os.environ.get('TEETH_QSLACK', .96))

def ztop(cls, o, xi, eta, h):
    if cls == 'inc': return np.full_like(xi, h)
    if cls == 'can': return h * (1 - np.where(xi < 0, .22, .30) * np.sqrt(xi ** 2 + .004) - .04 * eta ** 2)
    g = sum((am * np.exp(-((xi - x0) ** 2 + (eta - y0) ** 2) / r ** 2)) ** 4 for x0, y0, am, r in o['cu']) ** .25
    return h * (1 - .3 * (1 - g))

def crown(cls, w, t, h, G, o):
    """closed crown: bottom pole, 2 stub rings, 7 crown rings, 4 cap rings, top pole (NT per ring); also the
    height fraction of every vertex (z / h, < 0 on the stub) for the enamel colour"""
    A, B, L, n = PROF[cls]; A, B = np.array(A), np.array(B); L = B if L is None else np.array(L)
    C, Sn = se(n); Ad = A * (1 - o.get('rd', 0) * np.clip((VR - .55) / .45, 0, 1) ** 2)
    zr = ztop(cls, o, C, Sn, h); R = []
    cy0 = (L[0] - B[0]) * t / 2
    for f, zz in ((.62, -.7 * G), (.86, -.35 * G)):
        R.append(np.c_[f * A[0] * w / 2 * C, cy0 + f * B[0] * t / 2 * Sn, np.full(NT, zz)])
    for k, v in enumerate(VR):
        x = np.where(C > 0, Ad[k], A[k]) * w / 2 * C; y = (L[k] - B[k]) * t / 2 + B[k] * t / 2 * Sn
        if o.get('fos'): y = y + o['fos'] * t / 2 * (1 - C ** 2) * np.clip(-Sn, 0, 1) * np.sin(np.pi * np.clip((v - .2) / .75, 0, 1))
        R.append(np.c_[x, y, v * zr])
    cy1 = (L[-1] - B[-1]) * t / 2; a1 = np.where(C > 0, Ad[-1], A[-1])
    for p in CAP: R.append(np.c_[p * a1 * w / 2 * C, cy1 + p * B[-1] * t / 2 * Sn, ztop(cls, o, p * C, p * Sn, h)])
    V = np.vstack([[0, cy0, -.85 * G]] + R + [[0, cy1, float(ztop(cls, o, np.zeros(1), np.zeros(1), h)[0])]])
    nr, F_ = len(R), []
    for j in range(NT): F_.append((0, 1 + (j + 1) % NT, 1 + j))
    for r in range(nr - 1):
        for j in range(NT): b = 1 + r * NT; F_.append((b + j, b + (j + 1) % NT, b + NT + (j + 1) % NT, b + NT + j))
    top = len(V) - 1; b = 1 + (nr - 1) * NT
    for j in range(NT): F_.append((b + j, b + (j + 1) % NT, top))
    return V, F_, cy1, (cy0, B[0] * t / 2)

GL = np.array([(.80, 0), (.93, -.16), (1.0, -.38), (.99, -.62), (.88, -.85), (.55, -.99), (0, -1.03), (-.55, -.99), (-.88, -.85),
               (-.99, -.62), (-1.0, -.38), (-.93, -.16), (-.80, 0), (-.52, .12), (0, .16), (.52, .12)])   # minimal gum (fit proxy)
def gum_yz(wl, wi, m, G):
    return np.where(GL[:, 0] > 0, GL[:, 0] * wl, GL[:, 0] * wi), m + GL[:, 1] * (m + G)

POST = np.array([c in ('pm', 'mol') for c, *_ in UP + LO]); FRONT = ~POST
_TPL = {}
def templates(q, kp):
    """14 left teeth (upper 0-6, lower 7-13): crown mesh + minimal gum proxy points at front scale q, premolars /
    molars at q * kp (graded from the canine back); all points stacked with their tooth index"""
    if (q, kp) in _TPL: return _TPL[(q, kp)]
    out = []
    for tab in (UP, LO):
        for j, (cls, w, t, h, inc, o) in enumerate(tab):
            sg = q * S * MM * (1 - (1 - kp) * (0, 0, 0, .45, .75, 1, 1)[j]); G = GUM_H * q * S * MM
            V, F_, ycap, (cy0, b0) = crown(cls, w * sg, t * sg, h * sg, G, o)
            W = (b0 + .15 * sg) / .8; gy, gz = gum_yz(W, W, GUM_M * sg, G)
            Gp = np.vstack([np.c_[np.full(len(GL), xx), cy0 + gy, gz] for xx in (-w * sg / 2, 0, w * sg / 2)])
            out.append(dict(cls=cls, w=w * sg, t=t * sg, h=h * sg, sg=sg, inc=math.radians(inc), V=V, F=F_, ycap=ycap, cy0=cy0, b0=b0, P=np.vstack([V, Gp])))
    P = np.vstack([d['P'] for d in out]); tid = np.concatenate([np.full(len(d['P']), i) for i, d in enumerate(out)])
    _TPL[(q, kp)] = (out, P, tid, np.array([d['h'] for d in out]), np.array([d['ycap'] for d in out])); return _TPL[(q, kp)]

# ---- 3. natural arch: crown-centre line y = yf + D (al u^2 + (1 - al) u^p), u = 2x / W (left half, x >= 0)
# 2026-10-13 b (user: "the teeth should curve more; the side teeth should not show so much"): canonical arch 'ovoid'
# W 40, D 40, al .65, p 8: a rounder incisor curve, the canines turning back sooner (canine centre 12 mm behind the
# incisal point, was 8), the premolars / molars on narrower, less diverging lines behind the canines (10 deg, was
# 15) so from the front they recede behind the canines and the mouth corners (a buccal corridor) instead of
# filling the smile to the corners. Canine / first molar 0.70. env TEETH_ARCH=a: the first v3 arch (52, 39, .30, 4).
if os.environ.get('TEETH_ARCH', 'b') == 'a':
    W0, D0, AL0, PEX = 52.0, 39.0, 0.30, 4; ALS = (0.30, 0.24, 0.38, 0.46)
else:
    W0, D0, AL0, PEX = 40.0, 40.0, 0.65, 8; ALS = (0.65, 0.58, 0.72)  # canonical upper arch, mm at tooth scale 1
KA = (1.08, 1.0, 0.93, 0.86, 0.8, 0.74, 0.68); RS = (1.0, 0.93, 1.08, 0.86)   # arch scale, width / depth aspect
KA_MIN = float(os.environ.get('TEETH_KAMIN', .93))
sst = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
def arch_pts(W, D, al, yf):
    u = np.linspace(0, 1.5, 700); return np.c_[u * W / 2, yf + D * (al * u ** 2 + (1 - al) * u ** PEX)]
def on_curve(P, sc):
    """points and unit tangents at arc lengths sc along the polyline P (from its first point)"""
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    f = lambda s_: np.c_[np.interp(s_, L, P[:, 0]), np.interp(s_, L, P[:, 1])]
    Tg = f(sc + 1e-4) - f(np.maximum(sc - 1e-4, 0)); Tg /= np.linalg.norm(Tg, axis=1, keepdims=True)
    return f(sc), Tg
def lower_pts(Pu, wu, dant, dpost):
    """the upper crown-centre line offset inward along its normal: dant at the incisors, dpost behind the canine"""
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pu, axis=0), axis=1))]
    Tg = np.gradient(Pu, axis=0); Tg /= np.linalg.norm(Tg, axis=1, keepdims=True); Nin = np.c_[-Tg[:, 1], Tg[:, 0]]
    s1, s2 = wu[:2].sum(), wu[:4].sum() + wu[4] / 2               # front offset to the lateral incisor, posterior from PM2
    off = dpost + (dant - dpost) * (1 - sst((L - s1) / max(s2 - s1, 1e-6)))
    Pl = Pu + Nin * off[:, None]; Pl[0, 0] = 0.0
    return Pl

def frames(Cxy, Tg, zocc, inc, up):
    """occlusal point E, distal m, labial yh, toward-occlusal ah per tooth"""
    n = len(Cxy); m = np.c_[Tg, np.zeros(n)]; l = np.c_[Tg[:, 1], -Tg[:, 0], np.zeros(n)]; z = np.array([0, 0, 1.0])
    sg = -1.0 if up else 1.0; ca, sa = np.cos(inc)[:, None], np.sin(inc)[:, None]
    return [np.c_[Cxy, zocc], m, ca * l - sg * sa * z, ca * sg * z + sa * l]

ZF = float(os.environ.get('TEETH_ZF', 2.0))
def zoccs(q):
    """occlusal levels (v2): overbite at the incisors and canines, a small gap at the back; the plane drops ZF toward
    the incisors"""
    sg = q * S * MM; tilt = -ZF * S * MM * np.array([1, 1, .8, .45, .2, 0, 0])
    return (Z0 + tilt + sg * np.array([-OB / 2, -OB / 2, -OB / 2 - .3, GP / 2, GP / 2, GP / 2, GP / 2]),
            Z0 + tilt + sg * np.array([OB / 2, OB / 2, OB / 2 + .2, -GP / 2, -GP / 2, -GP / 2, -GP / 2]))

def layout(tp, q, W, D, al, yf, dant, dpost):
    """frames of the 14 left teeth: [E, m, yh, ah] arrays (14, 3); the lower arch inside the upper one"""
    zu, zl = zoccs(q); w = np.array([d['w'] for d in tp]); inc = np.array([d['inc'] for d in tp])
    Pu = arch_pts(W, D, al, yf); Pl = lower_pts(Pu, w[:7], dant, dpost)
    Fu = frames(*on_curve(Pu, np.cumsum(w[:7]) - w[:7] / 2), zu, inc[:7], True)
    Fl = frames(*on_curve(Pl, np.cumsum(w[7:]) - w[7:] / 2), zl, inc[7:], False)
    return [np.vstack([u, l]) for u, l in zip(Fu, Fl)]

def to_world(Pl, fr, h, ycap, nu, tid=None):
    """tooth space -> world; the crown shortens toward its occlusal end (nu), the stub and gum keep their size"""
    E, m, yh, ah = fr if tid is None else [f[tid] for f in fr]
    if tid is not None: h, ycap, nu = h[tid], ycap[tid], nu[tid]
    Z = Pl[:, 2]; ze = np.where(Z >= 0, nu * (Z - h), Z - nu * h)
    return E + Pl[:, :1] * m + (Pl[:, 1] - ycap)[:, None] * yh + ze[:, None] * ah

def fit_nu(tpl, fr):
    """per tooth the largest crown height fraction in [nu_min, 1] at which all its points fit; and which teeth fit at
    nu_min"""
    tp, P, tid, h, yc = tpl; n = len(tp); nmin = np.where(POST, NU_MIN - .07, NU_MIN)
    def ok(nu): return np.bincount(tid, weights=~fits(to_world(P, fr, h, yc, nu, tid)), minlength=n) == 0
    hi_ok, lo_ok = ok(np.ones(n)), ok(nmin); lo, hi = nmin.copy(), np.ones(n)
    for _ in range(6):
        mid = (lo + hi) / 2; g = ok(mid); lo = np.where(g, mid, lo); hi = np.where(g, hi, mid)
    return np.where(hi_ok, 1.0, lo), lo_ok

# inner lip surface on the midline: y of the first cavity wall in front of a point inside, per height (the upper
# incisors should rest close behind the lip, as in v2, not float in the cavity)
LZ = Z0 + np.arange(-16, 16.01, .25) * MM * S; LY = np.full(len(LZ), np.nan)
for i, z in enumerate(LZ):
    h = BAG.ray_cast(Vector((0, YS + 25 * MM * S, z)), Vector((0, -1, 0)), 0.1)
    if h[0] is not None and h[0].y < YS + 8 * MM * S: LY[i] = h[0].y
LZ, LY = LZ[np.isfinite(LY)], LY[np.isfinite(LY)]
GAP0, GAPW = 2.5, float(os.environ.get('TEETH_GAPW', .12))     # incisor-lip gap (mm) taken as natural; score per mm beyond
def lip_gap(fr, tp):
    V0 = to_world(tp[0]['V'], [f[0] for f in fr], tp[0]['h'], tp[0]['ycap'], 1.0); i = int(np.argmin(V0[:, 1]))
    return float(V0[i, 1] - np.interp(V0[i, 2], LZ, LY)) if len(LZ) else 0.0

def search(q, early, ka_min):
    """best (score, W, D, al, y_f, kp, ka, r) at tooth scale q with arch scale ka >= ka_min (W = ka sqrt(r) W0,
    D = ka / sqrt(r) D0); early: the first fit. The score keeps the natural shape first (aspect r, flatness al),
    then full-size posterior teeth, then the arch size"""
    sg = q * S * MM; best = None
    for ka in [k for k in KA if k >= ka_min - 1e-9]:
        for r in RS:
            for al in ALS:
                W, D = ka * math.sqrt(r) * W0 * sg, ka / math.sqrt(r) * D0 * sg
                for yf in YS + np.linspace(2.5, 12, 9) * MM * S:
                    for kp in KP:
                        tpl = templates(q, kp); fr = layout(tpl[0], q, W, D, al, yf, 2.3 * sg, 1.9 * sg); nu, ok = fit_nu(tpl, fr)
                        if os.environ.get('TEETH_DEBUG') and not early and r == 1.0 and al == AL0: print('DBG q', round(q, 3), 'ka', ka, 'yf', round((yf - YS) / MM / S, 1), 'kp', kp, 'fail', np.where(~ok)[0].tolist(), 'nu', np.round(nu, 2).tolist())
                        if not ok[FRONT].all() or nu[FRONT].min() < NU_FRONT: break
                        if not ok.all(): continue
                        sc = (1.2 * kp + nu.mean() + .5 * nu[FRONT].min() - 2.5 * abs(math.log(r)) - .8 * abs(math.log(ka))
                              - 3.0 * abs(al - AL0) - GAPW * max(0.0, lip_gap(fr, tpl[0]) / (MM * S) - GAP0))
                        if best is None or sc > best[0]: best = (sc, W, D, al, yf, kp, ka, r)
                        if early: return best
                        break
    return best

def largest_q(ka_min):
    lo_q, hi_q = 0.35, 1.0
    if not search(lo_q, True, ka_min): return None
    for _ in range(6):                                         # largest tooth scale q with a fitting arch (bisection)
        mid = (lo_q + hi_q) / 2
        if search(mid, True, ka_min): lo_q = mid
        else: hi_q = mid
    return lo_q
ka_used = KA_MIN; qmax = largest_q(KA_MIN)
if qmax is None: ka_used = float(min(KA)); qmax = largest_q(ka_used)   # no near-natural arch fits: allow smaller
if qmax is None: raise SystemExit('TEETH no arch fits the cavity')
# tooth size against shape / lip contact: the best shape at a few scales under the largest; total = score + QW q / qmax
QW = float(os.environ.get('TEETH_QW', 4.0)); cand = []
for fq in (Q_SLACK, Q_SLACK - .05, Q_SLACK - .1, Q_SLACK - .15):
    b_ = search(fq * qmax, False, ka_used)
    if b_: cand.append((b_[0] + QW * fq, fq * qmax, b_))
_, Q, best = max(cand, key=lambda c: c[0])
_, WA_, DA_, AL_, YF, KP_, KA_, R_ = best; TPL = templates(Q, KP_); TP = TPL[0]; SG = Q * S * MM
info['scale_candidates'] = [{'q': round(c[1], 3), 'total': round(c[0], 3), 'ka': c[2][6], 'r': c[2][7], 'al': c[2][3], 'kp': c[2][5],
                             'front_behind_slit_mm': round((c[2][4] - YS) * 1000, 1)} for c in cand]
info.update(q=round(Q, 3), tooth_scale=round(Q * S, 3), posterior_scale=KP_,
            arch_mm={'W': round(WA_ * 1000, 1), 'D': round(DA_ * 1000, 1), 'al': AL_, 'arch_scale': KA_, 'aspect': R_,
                     'front_behind_slit': round((YF - YS) * 1000, 1), 'arch_scale_min': round(ka_used, 3)})

DIRS = [Vector(v).normalized() for v in ((0.013, 1, 0.021), (1, 0.017, 0.011), (-1, 0.019, -0.013))]
def inside(bvh, P):
    """ray parity, 3 directions, majority vote"""
    res = np.zeros(len(P), bool)
    for i, p in enumerate(P):
        votes = 0
        for dv in DIRS:
            o, n = Vector(tuple(p)), 0
            for _ in range(40):
                h = bvh.ray_cast(o, dv, 2.0)
                if h[0] is None: break
                n += 1; o = h[0] + dv * 2e-6
            votes += n & 1
        res[i] = votes >= 2
    return res
MX = np.array([-1.0, 1.0, 1.0])
def tooth(i):
    d = TP[i]; return to_world(d['V'], [f[i] for f in FR], d['h'], d['ycap'], NU[i])
def teeth_mesh(idx, both=True):
    """crowns of the left half-arch idx and their mirror images (mirrored / left-handed frames: winding reversed);
    also per vertex the height fraction z / h (enamel colour) and the tooth class"""
    Vs, Fs, Zf, Cl, o_ = [], [], [], [], 0
    for i in idx:
        V = tooth(i); hand = np.linalg.det(np.array([FR[1][i], FR[2][i], FR[3][i]])) > 0
        zf = TP[i]['V'][:, 2] / TP[i]['h']
        for mir in ((False, True) if both else (False,)):
            Fs += [[o_ + k for k in (f[::-1] if hand == mir else f)] for f in TP[i]['F']]; Vs.append(V * MX if mir else V); o_ += len(V)
            Zf.append(zf); Cl += [TP[i]['cls']] * len(V)
    return np.vstack(Vs), Fs, np.concatenate(Zf), np.array(Cl)
def bvh(V, Fs): return BVHTree.FromPolygons(V.tolist(), Fs)

# the lower arch steps back from a tight overjet until no lower crown touches an upper one (as v2)
DANT, DPOST = 1.6 * SG, 1.85 * SG
for it in range(20):
    FR = layout(TP, Q, WA_, DA_, AL_, YF, DANT, DPOST); NU, _ = fit_nu(TPL, FR)
    (Vu, Fu, _, _), (Vl, Fl, _, _) = teeth_mesh(range(7), False), teeth_mesh(range(7, 14), False)
    cross = int(inside(bvh(Vu, Fu), Vl).sum() + inside(bvh(Vl, Fl), Vu).sum())
    if cross == 0: break
    DANT += .15 * SG; DPOST += .03 * SG
DANT += .1 * SG; FR = layout(TP, Q, WA_, DA_, AL_, YF, DANT, DPOST); NU, NUOK = fit_nu(TPL, FR)
info['lower_setback_mm'] = {'front': round(DANT * 1000, 2), 'back': round(DPOST * 1000, 2), 'steps': it}

# ---- 4. gums: one per jaw, swept along the tooth frames of the arch
#   section (tooth frame: y labial +, z toward the crown), margin at height m over the cervical line; labial side
#   (y / wl, z / Hl below the margin): margin on the neck, bulge over the root, on to the vestibule; then the base,
#   the lingual side (mirror, wi / Hi) and a crest inside the tooth (shows as the col between the papillae)
GLAB = np.array([(1.00, 0.0), (1.05, -.10), (1.09, -.25), (1.11, -.43), (1.10, -.62), (1.06, -.78), (.95, -.91), (.74, -.99), (.40, -1.03)])
NGS = 2 * len(GLAB) + 5
PAP = {'inc': 2.8, 'can': 2.5, 'pm': 2.0, 'mol': 1.6}           # papilla height over the margin at the contacts (mm)
HNOM = {'inc': (5.5, 5.0), 'can': (5.5, 5.0), 'pm': (4.6, 5.0), 'mol': (4.2, 5.0)}   # nominal labial / lingual depth (mm)
NSPT, PW, JUG = 10, .36, .05                                   # sections per tooth; papilla half base (share of the tooth
                                                               # width from the contact); root bulge (share of the width)
def gum_section(wb, pf, m, m0, Hl, Hi, crest, jug):
    """section (y, z) and per point depth (0 margin .. 1 deep). The papilla (pf, margin m) only shapes the points
    near the margin: deeper points keep the base margin m0 and the full width (a smooth vestibule edge); the root
    bulge jug peaks half way down the labial face"""
    dl = np.clip(-GLAB[:, 1], 0, 1); near = 1 - sst(dl / .5); mz = m0 + (m - m0) * near
    lab = np.c_[GLAB[:, 0] * wb * (1 - .22 * pf * near) * (1 + jug * np.sin(np.pi * dl)), mz + GLAB[:, 1] * Hl]
    lin = np.c_[-GLAB[::-1, 0] * wb * (1 - .22 * pf * near[::-1]), mz[::-1] + GLAB[::-1, 1] * Hi]
    base = np.array([[0.0, m0 - 1.05 * (Hl + Hi) / 2]]); wt = wb * (1 - .22 * pf)
    top = np.array([[-.45 * wt, m + .8 * crest], [-.15 * wt, m + crest], [.15 * wt, m + crest], [.45 * wt, m + .8 * crest]])
    return np.vstack([lab, base, lin, top]), np.r_[dl, 1.0, dl[::-1], np.zeros(4)]

def tri(Fs): return [(f[0], f[i], f[i + 1]) for f in Fs for i in range(1, len(f) - 1)]
def vol_sign(V, Fs): return sum(np.dot(V[f[0]], np.cross(V[f[1]], V[f[2]])) for f in tri(Fs))
def smooth_along(ss, V, sig):
    """gaussian smoothing along the arch (arc length ss from the midline; mirrored samples continue it past x = 0)"""
    se_ = np.r_[-ss[:0:-1], ss]; Ve = np.vstack([V[:0:-1] * MX, V]); out = np.empty_like(V)
    for i, s_ in enumerate(ss):
        wv = np.exp(-.5 * ((se_ - s_) / sig) ** 2); out[i] = (wv[:, None] * Ve).sum(0) / wv.sum()
    return out
def gum_mesh(idx):
    """closed gum of one jaw; per vertex a depth fraction (0 margin .. 1 vestibule / floor) for the colour"""
    idx = list(idx); tp = [TP[i] for i in idx]; w = np.array([d['w'] for d in tp]); G = GUM_H * SG
    s0 = np.cumsum(w) - w; ks = np.r_[-(s0[0] + w[0] / 2), s0 + w / 2, s0[-1] + w[-1]]   # mirrored central incisor = first knot;
    neck = np.array([to_world(np.array([[0, d['cy0'], 0.0]]), [f[i] for f in FR], d['h'], d['ycap'], NU[i])[0] for i, d in zip(idx, tp)])
    neck_end = neck[-1] + FR[1][idx[-1]] * w[-1] / 2                       # last knot: the distal end of the last tooth
    def at(s_, A2, end=None):                                               # (v2 clamped past the last tooth centre)
        A2 = np.asarray(A2, float); e_ = A2[-1] if end is None else end
        if A2.ndim == 1: return np.interp(s_, ks, np.r_[A2[0], A2, e_])
        A2 = np.vstack([A2[0] * MX, A2, e_]); return np.stack([np.interp(s_, ks, A2[:, c]) for c in range(3)], 1)
    ss = np.r_[np.concatenate([s0[i] + w[i] * np.arange(NSPT) / NSPT for i in range(len(w))]), s0[-1] + w[-1]]
    k_ = np.clip(np.searchsorted(s0, ss, 'right') - 1, 0, len(w) - 1); fr_ = np.clip((ss - s0[k_]) / w[k_], 0, 1)
    pap = np.array([PAP[d['cls']] * d['sg'] for d in tp]); pap = np.minimum(pap, .3 * np.array([d['h'] for d in tp]) * NU[idx])
    pp = np.where(fr_ < .5, np.minimum(pap[k_], pap[np.maximum(k_ - 1, 0)]), np.minimum(pap[k_], pap[np.minimum(k_ + 1, len(w) - 1)]))
    dc = np.minimum(fr_, 1 - fr_); pf = np.where(dc < PW, np.cos(np.pi / 2 * dc / PW) ** 2, 0.0)   # 1 at the contacts, 0 over the zenith
    m0 = GUM_M * SG; m = m0 + pp * pf
    Pn, Y, A = at(ss, neck, neck_end), at(ss, FR[2][idx]), at(ss, FR[3][idx])
    Y /= np.linalg.norm(Y, axis=1, keepdims=True); A /= np.linalg.norm(A, axis=1, keepdims=True)
    sig = .55 * w.mean(); Pns, Ys, As = smooth_along(ss, Pn, sig), smooth_along(ss, Y, sig), smooth_along(ss, A, sig)
    Ys /= np.linalg.norm(Ys, axis=1, keepdims=True); As /= np.linalg.norm(As, axis=1, keepdims=True)
    wb = at(ss, [d['b0'] for d in tp]) + .15 * SG
    Hn = np.array([[HNOM[d['cls']][0] * d['sg'], HNOM[d['cls']][1] * d['sg']] for d in tp]); Hl_n, Hi_n = at(ss, Hn[:, 0]), at(ss, Hn[:, 1])
    crest = .16 * (m0 + G) + .1 * pp * pf; jug = JUG * (1 - pf)
    def build(fl):
        out, dps = [], None
        for i in range(len(ss)):
            Hl = G + fl[i] * (Hl_n[i] - G); Hi = G + fl[i] * (Hi_n[i] - G)
            yz, dps = gum_section(wb[i], pf[i], m[i], m0, Hl, Hi, crest[i], jug[i]); b = sst(dps / .6)[:, None]
            loc = Pn[i] + yz[:, :1] * Y[i] + yz[:, 1:] * A[i]; smo = Pns[i] + yz[:, :1] * Ys[i] + yz[:, 1:] * As[i]
            out.append(loc + b * (smo - loc))                              # deep part on the smoothed arch frame
        return out, dps
    # largest depth per section that fits the cavity (labial and lingual together), smoothed along the arch
    FLS = np.linspace(1, 0, 11); fbest = np.zeros(len(ss))
    for f_ in FLS[::-1]:
        secs, _ = build(np.full(len(ss), f_)); okk = np.array([fits(s_).all() for s_ in secs]); fbest = np.where(okk, f_, fbest)
    fl = fbest.copy()
    for _ in range(6):                                                      # erode, then blur (no bumps, never above the fit)
        fl = np.minimum(fl, np.minimum(np.r_[fl[0], fl[:-1]], np.r_[fl[1:], fl[-1]]))
    for _ in range(6): fl = np.minimum(fbest, (np.r_[fl[0], fl[:-1]] + 2 * fl + np.r_[fl[1:], fl[-1]]) / 4)
    sec, dep = build(fl)
    last, c_, Md = sec[-1], sec[-1].mean(0), FR[1][idx[-1]]                 # behind the last molar: rounded end,
    for ce in (1.0, .75, .5, .3, .15):                                      # shorter where the cavity ends
        cap = [c_ + ce * dd * G * Md + sh * (last - c_) for dd, sh in ((.45, .82), (.85, .5), (1.1, .2))]; tipc = c_ + ce * 1.25 * G * Md
        if all(fits(q_).all() for q_ in cap) and fits(tipc[None]).all(): break
    sec += cap
    sec[0][:, 0] = 0.0
    Ls = [s_ * MX for s_ in sec[:0:-1]] + sec; n = NGS; Fs = []
    for k in range(len(Ls) - 1):
        for j in range(n): Fs.append([k * n + j, k * n + (j + 1) % n, (k + 1) * n + (j + 1) % n, (k + 1) * n + j])
    V = np.vstack(Ls + [tipc * MX, tipc]); e0, e1, k1 = len(V) - 2, len(V) - 1, len(Ls) - 1
    Fs += [[(j + 1) % n, j, e0] for j in range(n)] + [[k1 * n + j, k1 * n + (j + 1) % n, e1] for j in range(n)]
    if vol_sign(V, Fs) < 0: Fs = [f[::-1] for f in Fs]
    D = np.concatenate([dep] * len(Ls) + [[.5, .5]])
    return V, Fs, D, {'depth_factor_mean': round(float(fl.mean()), 2), 'depth_factor_min': round(float(fl.min()), 2),
                      'labial_depth_mm_max': round(float((G + fl * (Hl_n - G)).max() * 1000), 2)}

def clamp_gum(V):
    """gum points the eroded cavity would still cut are pressed into the room (last resort, counted)"""
    f, c = room(V); okc = np.isfinite(f) & np.isfinite(c); z = V[:, 2].copy()
    z[okc] = np.clip(z[okc], f[okc] + 1e-5, c[okc] - 1e-5); n = int((np.abs(z - V[:, 2]) > 1e-9).sum()); V = V.copy(); V[:, 2] = z
    return V, n

Vut, Fut, Zfu, Clu = teeth_mesh(range(7)); Vlt, Flt, Zfl, Cll = teeth_mesh(range(7, 14))
Vug, Fug, Dug, giu = gum_mesh(range(7)); Vlg, Flg, Dlg, gil = gum_mesh(range(7, 14))
Vug, nu_c = clamp_gum(Vug); Vlg, nl_c = clamp_gum(Vlg); info['gum_pressed_verts'] = [nu_c, nl_c]
info['gum'] = {'up': giu, 'lo': gil}

# ---- 5. tongue: its own tongue-shaped mesh
NY, KH = 32, 22                                                 # stations along y; half-ring samples (ring = 2 KH)
TM = S * MM
EL = FR[0][7:, 1]                                                # lower cusp plane (no overbite) along y, by tooth
ZP = lambda y: np.interp(y, EL, Z0 - ZF * S * MM * np.array([1, 1, .8, .45, .2, 0, 0])) - GP / 2 * SG
ZD = ZP(np.inf) - .6 * SG
BLt, BLg, BUt, BUg = bvh(Vlt, Flt), bvh(Vlg, Flg), bvh(Vut, Fut), bvh(Vug, Fug)
rnd = lambda d, r: np.sqrt(np.clip(1 - (1 - np.clip(d / r, 0, 1)) ** 2, 0, 1))            # quarter circle 0 -> 1 over r
zt0 = ZP(YF) - .6 * SG - 1.2 * TM - 2 * TM                        # tip centre height
LO3 = np.vstack([Vlt, Vlg]); band = LO3[(np.abs(LO3[:, 2] - zt0) < 1.5 * TM) & (np.abs(LO3[:, 0]) < 3 * TM) & (LO3[:, 1] < YF + 15 * SG)]
# the root: a real tongue fills the floor between all the molars and its dorsum curves down behind them into the
# throat. Here it ends just behind the lower second molars, but never where the cavity floor, rising toward the back
# wall, leaves less than 30 % of the deepest room under the dorsum; its dorsum curves down onto the floor over the
# last quarter (a thick, rounded root, no thin back edge showing through the open mouth)
jc = len(xs) - 1; dep_ = ZD - FE[:, jc]; okd = np.isfinite(dep_) & (dep_ > 2.5 * TM); iy = np.arange(len(ys))
imx = int(np.nanargmax(np.where(okd, dep_, np.nan)))
def _last(mask):
    ib = imx
    while ib + 1 < len(ys) and mask[ib + 1]: ib += 1
    return ys[ib]
y30 = _last(okd & (dep_ >= .30 * dep_[imx]))
y_m2 = FR[0][13][1] + TP[13]['w'] / 2 * FR[1][13][1] + .5 * SG
y_back = float(min(y_m2, y30))
if os.environ.get('TEETH_DEBUG'): print('DBGT y_m2', round((y_m2 - YS) * 1000, 1), 'y30', round((y30 - YS) * 1000, 1), 'ymax', round((_last(okd) - YS) * 1000, 1), 'deep', round(dep_[imx] * 1000, 1))
LH = np.vstack([Vlt[Vlt[:, 0] > 0], Vlg[Vlg[:, 0] > 0]])
GAPT = .7 * TM                                                  # lateral border to the lingual gum / teeth (at rest)
def sec_frac(z, zt, zb):
    """half width of a tongue section at height z as a share of its widest (dome n 2.3 above the lateral margin,
    n 3.2 below; 0 outside the section)"""
    zc = zb + .42 * (zt - zb); up = z >= zc
    u = np.where(up, (z - zc) / max(zt - zc, 1e-9), (zc - z) / max(zc - zb, 1e-9)); n = np.where(up, 2.3, 3.2)
    return np.where(u < 1, (1 - np.clip(u, 0, 1) ** n) ** (1 / n), 0.0)
def stations(y_tip):
    """station y, length fraction, dorsum (arched, lower at the tip, curving down to the floor at the root),
    bottom (free under the tip, blending smoothly down onto the floor by FA of the length), half-width limit
    (lingual side of the lower arch and gum / the cavity), planform"""
    Lt = y_back - y_tip; ph = np.pi * (np.arange(NY) + 1) / (NY + 1); ty = y_tip + Lt * (1 - np.cos(ph)) / 2; fy = (ty - y_tip) / Lt
    dor = ZP(ty) - .6 * SG - 1.2 * TM * (1 - sst(fy / .45))
    f0, c0 = room(np.c_[np.zeros(NY), ty, dor]); dor = np.where(np.isfinite(c0), np.minimum(dor, c0 - .4 * TM), dor)
    flo = np.where(np.isfinite(f0), f0, dor - 17 * TM)
    for _ in range(3): flo[1:-1] = np.maximum(flo[1:-1], (flo[:-2] + 2 * flo[1:-1] + flo[2:]) / 4)   # smooth, never below the floor
    FA = .42; zfree = dor - (4 + 8 * np.clip(fy / FA, 0, 1)) * TM                       # free underside of the tip
    bot = flo + np.maximum(zfree - flo, 0) * (1 - sst(fy / FA)) + 1e-5
    for _ in range(4): bot[1:-1] = np.maximum(flo[1:-1] + 1e-5, (bot[:-2] + 2 * bot[1:-1] + bot[2:]) / 4)
    bot = np.minimum(bot, dor - 1.5 * TM)
    Wl, Wa = np.zeros(NY), np.zeros(NY)
    for k in range(NY):
        # widest section whose outline keeps GAPT off every lower tooth / gum point near this station (the lateral
        # border lies against the lingual gum at rest; the dome stays clear of the crowns above it)
        b_ = LH[(np.abs(LH[:, 1] - ty[k]) < .6 * SG) & (LH[:, 2] > bot[k]) & (LH[:, 2] < dor[k])]
        fz = sec_frac(b_[:, 2], dor[k], bot[k]) if len(b_) else np.zeros(0); okz = fz > .08
        wa = float(((b_[okz, 0] - GAPT) / fz[okz]).min()) if okz.any() and fy[k] > .2 else np.inf
        xx = np.linspace(0, half * 1.2, 160); f_, c_ = room(np.c_[xx, np.full(160, ty[k]), np.full(160, dor[k])])
        okx = np.isfinite(f_) & (c_ > dor[k]) & (f_ < dor[k] - 2 * TM); wc = xx[np.argmin(okx)] - .4 * TM if not okx.all() else xx[-1]
        Wa[k], Wl[k] = wa, max(wc, .5 * TM)
    fin = np.isfinite(Wa); Wa[~fin & (fy > .2)] = Wa[fin][-1]; Wa[fy <= .2] = Wa[fin][0]
    Wl = np.maximum(np.minimum(Wl, np.where(np.isfinite(Wa), Wa, Wl)), .5 * TM)
    for _ in range(3): Wl[1:-1] = np.minimum(Wl[1:-1], (Wl[:-2] + 2 * Wl[1:-1] + Wl[2:]) / 4)
    if os.environ.get('TEETH_DEBUG'): print('DBGW', [(round((t - YS) * 1000, 1), round(a * 1000, 1) if np.isfinite(a) else None, round(c * 1000, 1)) for t, a, c in zip(ty, Wa, Wl)])
    km = int(np.argmax(Wl)); Wl[:km + 1] = np.minimum.accumulate(Wl[:km + 1][::-1])[::-1]; Wl[km:] = np.minimum.accumulate(Wl[km:])
    Wl = Wl * (1 - .05 * sst((fy - .7) / .3))                             # the body narrows a little toward the root
    dor = bot + (dor - bot) * rnd(y_back - ty, max(5 * TM, .25 * Lt))        # root: the dorsum curves down onto the floor
    return dict(y_tip=y_tip, Lt=Lt, ty=ty, fy=fy, dor=dor, bot=bot, flo=flo, Wl=Wl, rt=min(1.35 * Wl[(fy > .15) & (fy < .45)].mean(), .38 * Lt))   # the tip taper stays in the front third

ND = 1600; THD = np.linspace(0, np.pi, ND)                      # dense half outline: top centre (0) .. bottom centre (pi)
def half_outline(w, zt, zb, g, fren):
    """right half of a section: superellipse dome on top (n 2.3), flatter underside (n 3.2), lateral margin lower
    than the middle; median sulcus (depth g) on top, frenulum fold (height fren) under the middle"""
    zc = zb + .42 * (zt - zb); s_, c_ = np.sin(THD), np.cos(THD)
    top = c_ >= 0; nn = np.where(top, 2.3, 3.2)
    x = w * s_ ** (2 / nn); hz = np.where(top, zt - zc, zc - zb); z = zc + np.sign(c_) * hz * np.abs(c_) ** (2 / nn)
    z = z - g * np.exp(-(x / max(.16 * w, 1e-6)) ** 2) * top * np.clip(c_, 0, 1) ** .5
    z = z - fren * np.exp(-(x / (1.3 * TM)) ** 2) * ~top
    x[0] = 0.0; x[-1] = 0.0
    return np.c_[x, z]
def resample(Pd):
    """KH + 1 points along the half outline, denser at the sulcus, the lateral margin and the frenulum"""
    sd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=1))]; u = sd / sd[-1]
    um = u[np.argmax(Pd[:, 0])]
    rho = 1 + 2.2 * np.exp(-(u / .07) ** 2) + 1.6 * np.exp(-((u - um) / .1) ** 2) + 2.6 * np.exp(-((1 - u) / .07) ** 2)
    cum = np.r_[0, np.cumsum((rho[1:] + rho[:-1]) / 2 * np.diff(u))]; cum /= cum[-1]
    t = np.linspace(0, 1, KH + 1); ui = np.interp(t, cum, u)
    return np.c_[np.interp(ui, u, Pd[:, 0]), np.interp(ui, u, Pd[:, 1])], ui
def tongue(T):
    """rings along y: rounded tip (planform radius rt, vertical rv), rounded back (rb), sulcus, frenulum; ring =
    right half + its mirror (exact symmetry); per vertex: length fraction, outline parameter (colour)"""
    ty, fy, dor, bot, Wl, y_tip, flo = T['ty'], T['fy'], T['dor'], T['bot'], T['Wl'], T['y_tip'], T['flo']
    rb, rv = max(3 * TM, .25 * Wl[-1]), 2.5 * TM                          # rounded tip (planform / vertical), back
    R, U = [], []; ztip = (dor[0] + max(bot[0], dor[0] - 4 * TM)) / 2
    for k in range(NY):
        e_t, e_b = rnd(ty[k] - y_tip, T['rt']), rnd(y_back - ty[k], rb); ev = rnd(ty[k] - y_tip, rv)
        w_ = Wl[k] * e_t * e_b; top = ztip + (dor[k] - ztip) * ev; lo_ = ztip + (bot[k] - ztip) * ev
        g = .9 * TM * sst((fy[k] - .04) / .2) * (1 - sst((fy[k] - .62) / .22))
        fren = min(max(0.0, lo_ - flo[k] - .25 * TM), 1.6 * TM) * sst((fy[k] - .06) / .12) * (1 - sst((fy[k] - .26) / .16))   # soft fold
        H_, ui = resample(half_outline(w_, top, lo_, g * ev, fren))
        ring = np.vstack([H_, (H_[-2:0:-1] * [-1, 1])])           # right half (top -> bottom), then the left half back up
        P_ = np.c_[ring[:, 0], np.full(len(ring), ty[k]), ring[:, 1]]
        zc_ = lo_ + .42 * (top - lo_); f_, c_ = room(P_); lowr = (P_[:, 2] < zc_) & np.isfinite(f_); upr = ~lowr & np.isfinite(c_)
        P_[lowr, 2] = np.maximum(P_[lowr, 2], f_[lowr] + 1e-5); P_[upr, 2] = np.minimum(P_[upr, 2], c_[upr] - 1e-5); R.append(P_)
        U.append(np.c_[np.full(len(ring), fy[k]), (ring[:, 1] >= zc_).astype(float), ring[:, 0] / max(w_, 1e-6)])
    NA = 2 * KH
    V = np.vstack([[0, y_tip, ztip]] + R + [[0, y_back, R[-1][:, 2].mean()]])
    Ua = np.vstack([[0, 1, 0]] + U + [[1, 1, 0]])
    Fs = [[0, 1 + j, 1 + (j + 1) % NA] for j in range(NA)]               # pole fans wound like the quads (v2 had them
    for k in range(NY - 1):                                              # flipped: a dark dent at the tip)
        b = 1 + k * NA; Fs += [[b + j, b + NA + j, b + NA + (j + 1) % NA, b + (j + 1) % NA] for j in range(NA)]
    b = 1 + (NY - 1) * NA; Fs += [[b + (j + 1) % NA, b + j, len(V) - 1] for j in range(NA)]
    if vol_sign(V, Fs) < 0: Fs = [f[::-1] for f in Fs]
    return V, Fs, Ua
T_ = stations((band[:, 1].max() if len(band) else YF + 3 * SG) + .6 * SG)
for it in range(24):                                              # narrow the stations that touch anything; the tip steps back
    Vt, Ft, Ut = tongue(T_)
    badv = ~fits(Vt) | inside(BLt, Vt) | inside(BLg, Vt) | inside(BUt, Vt) | inside(BUg, Vt)
    if not badv.any(): break
    st = np.clip((np.where(badv)[0] - 1) // (2 * KH), 0, NY - 1)
    if badv[0] or (T_['fy'][st] < .2).any(): T_ = stations(T_['y_tip'] + .3 * SG); continue
    for k in np.unique(st): T_['Wl'][max(k - 1, 0):k + 2] *= .95
Lt = T_['Lt']
info['tongue_fix_steps'] = it
# proposed tongue chain (report only; rigify_fit places its 3 bones itself): 5 joints tip -> root on the mid-line
# halfway between the dorsum and the underside
NA_ = 2 * KH; ky = np.array([Vt[1 + k * NA_, 1] for k in range(NY)]); kz = np.array([(Vt[1 + k * NA_, 2] + Vt[1 + k * NA_ + KH, 2]) / 2 for k in range(NY)])
jy = np.linspace(Vt[:, 1].min(), Vt[:, 1].max(), 5); info['tongue_chain_proposal_m'] = [[0.0, round(float(y), 5), round(float(np.interp(y, ky, kz)), 5)] for y in jy]

# ---- objects, materials, colours, UVs
def lin(c): c = np.asarray(c, float) / 255; return np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)
ENAMEL = dict(neck=lin((226, 206, 168)), body=lin((242, 238, 226)), edge=lin((206, 214, 224)))
GUMC = dict(margin=lin((236, 158, 162)), deep=lin((206, 104, 116)))   # attached gingiva / redder mucosa toward the vestibule
TONG = dict(base=lin((220, 134, 134)), coat=lin((226, 160, 158)), red=lin((212, 96, 102)), sulcus=lin((168, 72, 80)),
            under=lin((176, 86, 106)), fren=lin((196, 118, 130)))           # base = mean of MakeHuman tongue01_diffuse (CC0)
def node_mat(name, rgb, rough, kind):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.diffuse_color = (*rgb, 1); m.roughness = rough
    m.use_nodes = True; nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    if b is None: return m
    def inp(k, v):
        if k in b.inputs: b.inputs[k].default_value = v
    inp('Base Color', (*rgb, 1)); inp('Roughness', rough)
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'; vc.location = (-500, 300)
    nt.links.new(vc.outputs['Color'], b.inputs['Base Color'])
    if kind == 'teeth':
        inp('Subsurface Weight', .12); inp('Subsurface Radius', (1.0, .8, .6)); inp('Subsurface Scale', .002); inp('Coat Weight', .3); inp('Coat Roughness', .1)
        at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'enamel_edge'; at.location = (-500, 0)
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = (-300, 0); mr.inputs['To Max'].default_value = .25
        nt.links.new(at.outputs['Fac'], mr.inputs['Value'])
        if 'Transmission Weight' in b.inputs: nt.links.new(mr.outputs['Result'], b.inputs['Transmission Weight'])
    elif kind == 'gums':
        inp('Subsurface Weight', .2); inp('Subsurface Radius', (1.0, .3, .2)); inp('Subsurface Scale', .002); inp('Coat Weight', .35); inp('Coat Roughness', .15)
    else:
        inp('Subsurface Weight', .15); inp('Subsurface Radius', (1.0, .3, .2)); inp('Subsurface Scale', .002); inp('Coat Weight', .2)
        tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); bp = nt.nodes.new('ShaderNodeBump')
        tc.location, nz.location, bp.location = (-700, -200), (-500, -200), (-300, -200)
        nz.inputs['Scale'].default_value = 2500.0; nz.inputs['Detail'].default_value = 2.0; bp.inputs['Strength'].default_value = .25
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m
MT = {'teeth': node_mat('teeth', tuple(ENAMEL['body']), 0.25, 'teeth'), 'gums': node_mat('gums', tuple(GUMC['margin']), 0.4, 'gums'),
      'tongue': node_mat('tongue', tuple(TONG['base']), 0.5, 'tongue')}
def make(name, parts, mats, col, attrs=()):
    V = np.vstack([p[0] for p in parts]); Fs, mi, o_ = [], [], 0
    for k, (Vp, Fp) in enumerate(parts): Fs += [[o_ + i for i in f] for f in Fp]; mi += [k] * len(Fp); o_ += len(Vp)
    V[np.abs(V[:, 0]) < 1e-9, 0] = 0.0
    m = bpy.data.meshes.new(name); m.from_pydata(V.tolist(), [], Fs); m.update()
    for mt in mats: m.materials.append(MT[mt])
    m.polygons.foreach_set('material_index', mi); m.polygons.foreach_set('use_smooth', [True] * len(Fs))
    ca = m.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT'); ca.data.foreach_set('color', np.c_[col, np.ones(len(col))].ravel().astype(np.float32))
    m.color_attributes.active_color = ca; m.color_attributes.render_color_index = m.color_attributes.find('Col')
    for an, av in attrs:
        at = m.attributes.new(an, 'FLOAT', 'POINT'); at.data.foreach_set('value', np.asarray(av, np.float32))
    m.update()
    o = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(o); o.color = (*MT[mats[0]].diffuse_color[:3], 1)
    return o, V
lerp = lambda a_, b_, t: a_ + (b_ - a_) * np.asarray(t)[:, None]
def enamel(zf, cl):
    front = np.isin(cl, ('inc', 'can')); zc = np.clip(zf, 0, 1)
    c = lerp(ENAMEL['neck'], ENAMEL['body'], sst((zc - .05) / .45))
    edge = np.where(front, sst((zc - .72) / .28), .6 * sst((zc - .86) / .14))
    return lerp(c, ENAMEL['edge'], .8 * edge), edge
def gum_col(D): return lerp(GUMC['margin'], GUMC['deep'], sst((D - .3) / .7))
cu_, eu_ = enamel(Zfu, Clu); cl_, el_ = enamel(Zfl, Cll)
gu_, gl_ = gum_col(Dug), gum_col(Dlg)
oup, Vup = make('teeth_up', [(Vut, Fut), (Vug, Fug)], ['teeth', 'gums'], np.vstack([cu_, gu_]), [('enamel_edge', np.r_[eu_, np.zeros(len(Vug))])])
olo, Vlo = make('teeth_lo', [(Vlt, Flt), (Vlg, Flg)], ['teeth', 'gums'], np.vstack([cl_, gl_]), [('enamel_edge', np.r_[el_, np.zeros(len(Vlg))])])
fyv, topv, xr = Ut[:, 0], Ut[:, 1] > .5, np.abs(Ut[:, 2]); rng = np.random.default_rng(7)
ctg = lerp(TONG['base'], TONG['coat'], .55 * sst((fyv - .2) / .35) * (1 - sst((xr - .35) / .45)))        # paler coated dorsum
ctg = lerp(ctg, TONG['red'], np.clip(.7 * (1 - sst(fyv / .25)) + .5 * sst((xr - .6) / .35), 0, 1))       # redder tip, margins
ctg = lerp(ctg, TONG['sulcus'], .65 * np.exp(-(xr / .1) ** 2) * sst((fyv - .05) / .2) * (1 - sst((fyv - .62) / .22)))
ctg = np.where(topv[:, None], ctg, lerp(TONG['under'], TONG['fren'], np.exp(-(xr / .08) ** 2)))
ctg = np.clip(ctg * (1 + .06 * rng.standard_normal((len(ctg), 1))), 0, 1)   # papillae speckle (mirror pairs synced below)
otg, Vtg = make('tongue', [(Vt, Ft)], ['tongue'], ctg, [('tongue_v', fyv), ('tongue_top', topv.astype(float))])   # helpers for smooth weights
# mirror pairs share colours / attributes (exact symmetry of everything, not only positions)
for o in (oup, olo, otg):
    P = np.array([tuple(v.co) for v in o.data.vertices]); kd = KDTree(len(P))
    for i, p in enumerate(P): kd.insert(Vector(tuple(p)), i)
    kd.balance(); part = np.array([kd.find(Vector(tuple(p * MX)))[1] for p in P])
    ca = o.data.color_attributes['Col']; C = np.empty(len(P) * 4, np.float32); ca.data.foreach_get('color', C); C = C.reshape(-1, 4)
    C2 = C.copy(); left = P[:, 0] > 0; C2[part[left]] = C[left]; ca.data.foreach_set('color', C2.ravel())
# UVs as uv_parts.py: teeth / gums cylindrical about the arch (gums in the right half), tongue top-down (tip at v = 1)
for o in (oup, olo):
    me_ = o.data; uv = me_.uv_layers.new(name='UVMap'); P = np.array([tuple(v.co) for v in me_.vertices])
    yc = P[:, 1].max(); zc0, zc1 = P[:, 2].min(), P[:, 2].max(); u = .5 + np.arctan2(P[:, 0], yc - P[:, 1]) / np.pi
    v = (zc1 - P[:, 2]) / (zc1 - zc0) if o.name == 'teeth_up' else (P[:, 2] - zc0) / (zc1 - zc0)
    lvi = np.empty(len(me_.loops), np.int32); me_.loops.foreach_get('vertex_index', lvi)
    lmat = np.repeat(np.array([p.material_index for p in me_.polygons]), [p.loop_total for p in me_.polygons])   # loops in polygon order
    uv.data.foreach_set('uv', np.c_[.5 * (lmat == 1) + .5 * u[lvi], v[lvi]].ravel())
me_ = otg.data; uv = me_.uv_layers.new(name='UVMap'); P = Vtg
lvi = np.empty(len(me_.loops), np.int32); me_.loops.foreach_get('vertex_index', lvi); hw = np.abs(P[:, 0]).max()
uv.data.foreach_set('uv', np.c_[.5 + .5 * P[lvi, 0] / hw, 1 - (P[lvi, 1] - P[:, 1].min()) / np.ptp(P[:, 1])].ravel())

# ---- QA (v2 keys + arch metrics, clearance, symmetry)
qa = {}
def clearance(V):
    d = np.array([(BAG.find_nearest(Vector(tuple(p)))[3] or 0) for p in V]); return d
for n, V in (('teeth_up', Vup), ('teeth_lo', Vlo), ('tongue', Vtg)):
    cl = clearance(V)
    qa[n] = {'verts': len(V), 'outside_skin': int((~inside(ENV, V)).sum()), 'outside_cavity': int((~inside(BAG, V)).sum()),
             'clearance_min_mm': round(float(cl.min() * 1000), 3), 'clearance_p5_mm': round(float(np.percentile(cl, 5) * 1000), 3)}
qa['lower_in_upper_teeth'] = int(inside(BUt, Vlt).sum()); qa['upper_in_lower_teeth'] = int(inside(BLt, Vut).sum())
qa['tongue_in_teeth_gums'] = int((inside(BLt, Vtg) | inside(BLg, Vtg) | inside(BUt, Vtg) | inside(BUg, Vtg)).sum())
qa['crowns_fit_min_height'] = bool(NUOK.all())
mc = X[sl].mean(0); qa['parity_sanity'] = bool(inside(BAG, [mc + [0, .01 * S, 0]])[0] and inside(ENV, [mc + [0, .01 * S, 0]])[0]
                                             and not inside(BAG, [mc - [0, .02, 0]])[0] and not inside(ENV, [mc - [0, .02, 0]])[0])
sym = {}
for o in (oup, olo, otg):
    P = np.array([tuple(v.co) for v in o.data.vertices]); kd = KDTree(len(P))
    for i, p in enumerate(P): kd.insert(Vector(tuple(p)), i)
    kd.balance(); sym[o.name] = round(max(kd.find(Vector(tuple(p * MX)))[2] for p in P) * 1000, 6)
qa['mirror_gap_max_mm'] = sym
cu, cl = tooth(0), tooth(7); eu, el = cu[:, 2].min(), cl[:, 2].max()
lab = cu[np.argmin(cu[:, 1])]; hit = BAG.ray_cast(Vector(tuple(lab)), Vector((0, -1, 0)), 0.05)
mm = lambda v: round(float(v) * 1000, 2)
def arch_metrics(i0):
    E = FR[0][i0:i0 + 7]; Wd = 2 * E[:, 0]; tp = TP[i0:i0 + 7]
    back = E[6, 1] + tp[6]['w'] / 2 * FR[1][i0 + 6][1]
    div = math.degrees(math.atan2(E[6, 0] - E[3, 0], E[6, 1] - E[3, 1]))
    return {'canine_mm': mm(Wd[2]), 'premolar1_mm': mm(Wd[3]), 'premolar2_mm': mm(Wd[4]), 'molar1_mm': mm(Wd[5]), 'molar2_mm': mm(Wd[6]),
            'depth_mm': mm(back - E[0, 1] + 0 * tp[0]['w']), 'canine_to_molar1': round(float(Wd[2] / Wd[5]), 3),
            'posterior_divergence_deg': round(div, 1)}
info.update(qa=qa, overbite_mm=mm(el - eu), overjet_mm=mm(cl[cl[:, 2] > el - SG][:, 1].min() - cu[cu[:, 2] < eu + SG][:, 1].min()),
            intercanine_mm=mm(2 * FR[0][2][0]), intermolar_mm=mm(2 * FR[0][5][0]),
            arch_depth_mm=mm(FR[0][6][1] + TP[6]['w'] / 2 * FR[1][6][1] - FR[0][0][1]),
            arch_upper=arch_metrics(0), arch_lower=arch_metrics(7),
            upper_incisor_wh_mm=[mm(TP[0]['w']), mm(TP[0]['h'] * NU[0])], incisor_behind_slit_mm=mm(lab[1] - YS),
            incisor_to_lip_mm=mm(hit[3]) if hit[0] is not None else None,
            crown_height_frac={'up': np.round(NU[:7], 2).tolist(), 'lo': np.round(NU[7:], 2).tolist()},
            tongue_mm={'length': mm(Lt), 'max_width': mm(2 * Vtg[:, 0].max()),
                       'max_thick': mm(max(np.ptp(Vtg[1 + k * 2 * KH:1 + (k + 1) * 2 * KH, 2]) for k in range(NY))),
                       'top_below_occlusal_min': mm((ZP(Vtg[:, 1]) - Vtg[:, 2]).min()),
                       'tip_behind_lower_incisors_mm': mm(Vtg[:, 1].min() - Vlt[np.abs(Vlt[:, 0]) < 3 * TM][:, 1].max())},
            secs=round(time.time() - T0, 1))
_lo = Vlt[np.abs(Vlt[:, 1] - FR[0][12][1]) < TP[12]['w'] / 2]; _ow = 2 * np.abs(np.r_[Vut[:, 0], Vlt[:, 0]]).max()
info['size_vs_mouth'] = {'arch_outer_w_mm': mm(_ow), 'arch_to_mouth': round(float(_ow / (2 * half)), 3),
                         'lower_lingual_w_mm': mm(2 * np.abs(_lo[:, 0]).min()) if len(_lo) else None,
                         'tongue_to_arch': round(float(2 * Vtg[:, 0].max() / _ow), 3)}
ro = []                                                          # cavity footprint at the occlusal level (x >= 0), for views
for i in range(0, len(ys), 2):
    okr = np.isfinite(FE[i]) & (FE[i] < Z0) & (CEe[i] > Z0)
    if okr.any(): ro.append([round(float(XS[okr].max()), 5), round(float(ys[i]), 5)])
info['room_outline_occlusal'] = ro
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(info, open(os.path.splitext(OUT)[0] + '_teeth.json', 'w'), indent=1)
print('TEETH', json.dumps(info))
