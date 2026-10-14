"""M1 · teeth, gums and tongue (v2) for a ring mouth (organ_mouth.py), fitted to the oral cavity of each head.

1. Cavity: the bag behind the lip slit (mouth_ring >= slit: inner lip roll, cavity rings, cap) as a height field:
   per (x, y) column the floor and the ceiling a vertical ray meets, eroded by CLR so that a point inside keeps CLR
   from the wall.
2. Crowns: one closed parametric mesh per tooth: superellipse sections from a root stub (inside the gum) over the
   cervical line to the incisal edge / occlusal table, then a cap. Incisors: thin spade with a straight edge and a
   lingual fossa; canines: pointed; premolars 2-3 cusps, molars 4-5 cusps (soft max of bumps, fissures between).
   Standard crown sizes (Wheeler, mm) per side: central / lateral incisor, canine, 2 premolars, 2 molars.
3. Arches: teeth placed by arc length on a quarter ellipse (half width a, depth D, front y_f) that runs straight
   back past its end. The lower arch sits inside the upper one (overjet in front; at the back the lower central
   fossae under the upper lingual cusps); overbite at the incisors and canines, a small gap between the posterior
   cusps at rest; the occlusal plane drops ZF toward the incisors (upper edges show when the mouth opens).
   Search: the largest front scale q for which some (a, D, y_f) and posterior scale kp in KP (premolars / molars
   smaller, graded from the canine back) fit every crown + root stub + gum into the eroded cavity, each crown
   shortened toward its occlusal end to no less than NU_MIN (front teeth NU_FRONT); then the lower arch steps
   back until no lower crown touches an upper one.
4. Gums: a tube along each arch round the tooth necks (margin hugging the neck, papillae up between the teeth,
   bulge over the roots), closed behind the last molars; second material 'gums' in teeth_up / teeth_lo.
5. Tongue: rings along y from a rounded tip just behind the lower incisors to the back of the cavity, as wide as the
   lower arch allows, top just under the lower occlusal plane with a median groove, thickness 4 -> 10 mm (mouth
   scale) where the floor allows, underside on the floor; narrowed where it would touch teeth, gums or the wall.
Objects teeth_up (head), teeth_lo (jaw), tongue (3 bones along y), exactly mirror-symmetric (sym_lock pairs them
with zero gap). QA line TEETH (also <out>_teeth.json): scales, arch sizes, overbite / overjet, crown height
fractions, vertex counts, vertices outside the skin or outside the cavity (ray parity, 3 directions), lower inside
upper crowns and back, tongue inside teeth / gums.
Usage: blender -b <eyes.blend> -P organ_teeth.py -- <mouth.json> <out.blend>
(env TEETH_ZF: occlusal plane drop at the incisors, mm at a 52 mm mouth, default 2; TEETH_QSLACK: share of the
largest fitting front scale actually used, default 0.96)
"""
import bpy, sys, os, json, math, time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

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
info = {'mouth_width_mm': round(2000 * half, 1), 'S': round(float(S), 3)}

# ---- 1. cavity height field (x >= 0 cast, mirrored), eroded by CLR
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

# ---- 2. crowns. Tooth space: x mesiodistal (+ distal), y labial / buccal, z from the cervical line (0) to the
#      occlusal end (h); below 0 a root stub that stays inside the gum
NT, VR, CAP = 16, np.array([0, .15, .35, .55, .75, .9, 1.0]), np.array([.8, .58, .36, .15])
TH = 2 * np.pi * np.arange(NT) / NT
def se(n): c, s_ = np.cos(TH), np.sin(TH); return np.sign(c) * np.abs(c) ** (2 / n), np.sign(s_) * np.abs(s_) ** (2 / n)
#   rows VR: mesiodistal half width, labio-lingual half thickness, labial face (fractions of w/2, t/2, t/2); exponent
PROF = {'inc': ([.70, .78, .88, .96, 1.0, 1.0, .96], [.95, 1.0, .88, .66, .44, .27, .15], [.95, 1.0, .98, .92, .84, .77, .71], 2.6),
        'can': ([.66, .76, .88, .97, 1.0, .97, .90], [.92, 1.0, .92, .78, .60, .45, .30], [.94, 1.0, 1.0, .96, .90, .84, .78], 2.4),
        'pm':  ([.74, .84, .94, 1.0, .99, .95, .87], [.84, .93, 1.0, 1.0, .95, .87, .76], None, 2.4),
        'mol': ([.80, .88, .96, 1.0, .99, .95, .88], [.84, .92, .99, 1.0, .96, .89, .80], None, 2.8)}
#   cusps (x / half width, y / half thickness of the occlusal table, height, radius); x < 0 = mesial
PM_U = [(0, .42, 1, .5), (0, -.42, .9, .5), (-.75, 0, .5, .3), (.75, 0, .5, .3)]
PM_L1 = [(0, .35, 1, .55), (0, -.55, .55, .4), (-.75, 0, .45, .3), (.75, 0, .45, .3)]
PM_L2 = [(0, .38, 1, .5), (-.28, -.45, .8, .38), (.3, -.45, .7, .38), (-.75, 0, .45, .3), (.75, 0, .45, .3)]
M_U = [(-.42, .45, 1, .45), (.45, .45, .92, .42), (-.38, -.42, 1, .5), (.5, -.5, .7, .38)]
M_U2 = [(-.4, .45, 1, .45), (.45, .45, .85, .4), (-.35, -.42, .95, .5), (.55, -.5, .45, .35)]
M_L = [(-.55, .45, 1, .4), (0, .5, .95, .4), (.62, .38, .8, .35), (-.5, -.45, 1, .42), (.42, -.45, .95, .42)]
#   class, w, t, h (mm), crown inclination (deg, + = occlusal end labial / buccal), options
UP = [('inc', 8.5, 7.0, 10.5, 16, dict(rd=.12, fos=.22)), ('inc', 6.6, 6.0, 9.0, 12, dict(rd=.25, fos=.25)),
      ('can', 7.6, 8.0, 10.0, 8, dict(fos=.12)), ('pm', 7.0, 9.0, 8.2, 5, dict(cu=PM_U)), ('pm', 6.6, 9.0, 7.8, 5, dict(cu=PM_U)),
      ('mol', 10.2, 11.0, 7.2, 4, dict(cu=M_U)), ('mol', 9.0, 11.0, 6.6, 4, dict(cu=M_U2))]
LO = [('inc', 5.2, 5.8, 9.0, 18, dict(fos=.08)), ('inc', 5.8, 6.2, 9.4, 16, dict(rd=.06, fos=.1)),
      ('can', 6.9, 7.6, 10.6, 9, dict(fos=.08)), ('pm', 7.0, 7.6, 8.2, 3, dict(cu=PM_L1)), ('pm', 7.2, 8.2, 7.8, 2, dict(cu=PM_L2)),
      ('mol', 11.0, 10.4, 7.2, 2, dict(cu=M_L)), ('mol', 10.4, 10.0, 6.8, 2, dict(cu=M_L))]
PAP = {'inc': 2.2, 'can': 2.0, 'pm': 1.5, 'mol': 1.1}          # papilla height over the margin (mm)
GUM_H, GUM_M = 2.2, 0.3                                        # gum above the cervical line, margin over it (mm)
NU_MIN, NU_FRONT, OB, GP = 0.62, 0.85, 1.5, 0.5                # min crown height fraction (front teeth); overbite, posterior gap (mm)
KP = (1.0, .9, .8, .7)                                         # premolars + molars may be this much smaller than the front teeth
Q_SLACK = float(os.environ.get('TEETH_QSLACK', .96))
W_WIDE = float(os.environ.get('TEETH_WIDE', 1.5))           # score weight of a wide arch (a / half mouth width)

def ztop(cls, o, xi, eta, h):
    if cls == 'inc': return np.full_like(xi, h)
    if cls == 'can': return h * (1 - np.where(xi < 0, .22, .30) * np.sqrt(xi ** 2 + .004) - .04 * eta ** 2)
    g = sum((am * np.exp(-((xi - x0) ** 2 + (eta - y0) ** 2) / r ** 2)) ** 4 for x0, y0, am, r in o['cu']) ** .25
    return h * (1 - .3 * (1 - g))

def crown(cls, w, t, h, G, o):
    """closed crown: bottom pole, 2 stub rings, 7 crown rings, 4 cap rings, top pole (NT per ring)"""
    A, B, L, n = PROF[cls]; A, B = np.array(A), np.array(B); L = B if L is None else np.array(L)
    C, Sn = se(n); Ad = A * (1 - o.get('rd', 0) * np.clip((VR - .55) / .45, 0, 1) ** 2)    # rounder distal incisal corner
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
               (-.99, -.62), (-1.0, -.38), (-.93, -.16), (-.80, 0), (-.52, .12), (0, .16), (.52, .12)])   # gum section (labial = +y)
def gum_yz(wl, wi, m, G):
    """gum section points in a tooth frame: y across (labial +), z toward the crown, margin at height m"""
    return np.where(GL[:, 0] > 0, GL[:, 0] * wl, GL[:, 0] * wi), m + GL[:, 1] * (m + G)

POST = np.array([c in ('pm', 'mol') for c, *_ in UP + LO]); FRONT = ~POST
_TPL = {}
def templates(q, kp):
    """14 left teeth (upper 0-6, lower 7-13): crown mesh + gum proxy points (sections at the mesial edge, centre and
    distal edge) at front scale q, premolars / molars at q * kp; all points stacked with their tooth index"""
    if (q, kp) in _TPL: return _TPL[(q, kp)]
    out = []
    for tab in (UP, LO):
        for j, (cls, w, t, h, inc, o) in enumerate(tab):                # graded from the canine back: no size step
            sg = q * S * MM * (1 - (1 - kp) * (0, 0, 0, .45, .75, 1, 1)[j]); G = GUM_H * q * S * MM
            V, F_, ycap, (cy0, b0) = crown(cls, w * sg, t * sg, h * sg, G, o)
            W = (b0 + .15 * sg) / .8; gy, gz = gum_yz(W, W, GUM_M * sg, G)
            Gp = np.vstack([np.c_[np.full(len(GL), xx), cy0 + gy, gz] for xx in (-w * sg / 2, 0, w * sg / 2)])
            out.append(dict(cls=cls, w=w * sg, t=t * sg, h=h * sg, inc=math.radians(inc), V=V, F=F_, ycap=ycap, cy0=cy0, b0=b0, P=np.vstack([V, Gp])))
    P = np.vstack([d['P'] for d in out]); tid = np.concatenate([np.full(len(d['P']), i) for i, d in enumerate(out)])
    _TPL[(q, kp)] = (out, P, tid, np.array([d['h'] for d in out]), np.array([d['ycap'] for d in out])); return _TPL[(q, kp)]

# ---- 3. arches
def arch(a_, D_, yf, w):
    """quarter ellipse from the midline (0, yf) to (a_, yf + D_), then straight back; centres / tangents of teeth of
    widths w placed by arc length from the midline"""
    ph = np.linspace(0, np.pi / 2, 120); P = np.c_[a_ * np.sin(ph), yf + D_ * (1 - np.cos(ph))]
    P = np.vstack([P, P[-1] + np.c_[np.zeros(40), np.linspace(1e-3, .05, 40)]])
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    f = lambda s_: np.c_[np.interp(s_, L, P[:, 0]), np.interp(s_, L, P[:, 1])]
    sc = np.cumsum(w) - w / 2; Tg = f(sc + 1e-4) - f(np.maximum(sc - 1e-4, 0)); Tg /= np.linalg.norm(Tg, axis=1, keepdims=True)
    return f(sc), Tg

def frames(Cxy, Tg, zocc, inc, up):
    """occlusal point E, distal m, labial yh, toward-occlusal ah per tooth"""
    n = len(Cxy); m = np.c_[Tg, np.zeros(n)]; l = np.c_[Tg[:, 1], -Tg[:, 0], np.zeros(n)]; z = np.array([0, 0, 1.0])
    sg = -1.0 if up else 1.0; ca, sa = np.cos(inc)[:, None], np.sin(inc)[:, None]
    return [np.c_[Cxy, zocc], m, ca * l - sg * sa * z, ca * sg * z + sa * l]

ZF = float(os.environ.get('TEETH_ZF', 2.0))
def zoccs(q):
    """occlusal levels: overbite at the incisors and canines, a small gap at the back; the plane drops ZF (mm,
    mouth scale) toward the incisors (the upper incisal edges show under the upper lip when the mouth opens) and
    stays at the slit at the molars, where the cavity is lowest"""
    sg = q * S * MM; tilt = -ZF * S * MM * np.array([1, 1, .8, .45, .2, 0, 0])
    return (Z0 + tilt + sg * np.array([-OB / 2, -OB / 2, -OB / 2 - .3, GP / 2, GP / 2, GP / 2, GP / 2]),
            Z0 + tilt + sg * np.array([OB / 2, OB / 2, OB / 2 + .2, -GP / 2, -GP / 2, -GP / 2, -GP / 2]))

def layout(tp, q, a_, D_, yf, dant, dpost):
    """frames of the 14 left teeth: [E, m, yh, ah] arrays (14, 3); the lower arch inside the upper one"""
    zu, zl = zoccs(q); w = np.array([d['w'] for d in tp]); inc = np.array([d['inc'] for d in tp])
    Fu = frames(*arch(a_, D_, yf, w[:7]), zu, inc[:7], True); Fl = frames(*arch(a_ - dpost, D_ - dant + dpost, yf + dant, w[7:]), zl, inc[7:], False)
    return [np.vstack([u, l]) for u, l in zip(Fu, Fl)]

def to_world(Pl, fr, h, ycap, nu, tid=None):
    """tooth space -> world; the crown shortens toward its occlusal end (nu), the stub and gum keep their size"""
    E, m, yh, ah = fr if tid is None else [f[tid] for f in fr]
    if tid is not None: h, ycap, nu = h[tid], ycap[tid], nu[tid]
    Z = Pl[:, 2]; ze = np.where(Z >= 0, nu * (Z - h), Z - nu * h)
    return E + Pl[:, :1] * m + (Pl[:, 1] - ycap)[:, None] * yh + ze[:, None] * ah
def tooth(i):
    d = TP[i]; return to_world(d['V'], [f[i] for f in FR], d['h'], d['ycap'], NU[i])

def fit_nu(tpl, fr):
    """per tooth the largest crown height fraction in [nu_min, 1] at which all its points fit (bisection, all teeth
    at once); nu_min = NU_MIN for the front teeth, a little less for premolars / molars; and which teeth fit at nu_min"""
    tp, P, tid, h, yc = tpl; n = len(tp); nmin = np.where(POST, NU_MIN - .07, NU_MIN)
    def ok(nu): return np.bincount(tid, weights=~fits(to_world(P, fr, h, yc, nu, tid)), minlength=n) == 0
    hi_ok, lo_ok = ok(np.ones(n)), ok(nmin); lo, hi = nmin.copy(), np.ones(n)
    for _ in range(6):
        mid = (lo + hi) / 2; g = ok(mid); lo = np.where(g, mid, lo); hi = np.where(g, hi, mid)
    return np.where(hi_ok, 1.0, lo), lo_ok

def search(q, early):
    """best (score, a, D, y_f, kp) at front scale q; early: the first that fits"""
    sg = q * S * MM; best = None
    for a_ in np.linspace(.36, .76, 6) * half:
        for r in (.8, 1.0, 1.25, 1.55):
            for yf in YS + np.linspace(2.5, 9, 7) * MM * S:
                for kp in KP:                                  # the front teeth do not move with kp
                    tpl = templates(q, kp); nu, ok = fit_nu(tpl, layout(tpl[0], q, a_, a_ * r, yf, 2.3 * sg, 1.9 * sg))
                    if os.environ.get('TEETH_DEBUG') and not early: print('DBG a', round(a_ * 1000, 1), 'r', r, 'yf', round((yf - YS) * 1000, 1), 'kp', kp, 'fail', np.where(~ok)[0].tolist(), 'nu', np.round(nu, 2).tolist())
                    if not ok[FRONT].all() or nu[FRONT].min() < NU_FRONT: break
                    if not ok.all(): continue
                    sc = 2 * kp + nu.mean() + .5 * nu[FRONT].min() + W_WIDE * a_ / half - .02 * (yf - YS) / (MM * S) - .05 * abs(math.log(r))
                    if best is None or sc > best[0]: best = (sc, a_, a_ * r, yf, kp)
                    if early: return best
                    break
    return best

lo_q, hi_q = 0.35, 1.0
for _ in range(6):                                             # largest front scale q with a fitting arch (bisection)
    mid = (lo_q + hi_q) / 2
    if search(mid, True): lo_q = mid
    else: hi_q = mid
Q = Q_SLACK * lo_q; best = search(Q, False)                 # a little under the largest: room for a wider arch
if best is None: raise SystemExit('TEETH no arch fits the cavity')
_, A_, D_, YF, KP_ = best; TPL = templates(Q, KP_); TP = TPL[0]; SG = Q * S * MM
info.update(q=round(Q, 3), tooth_scale=round(Q * S, 3), posterior_scale=KP_,
            arch_mm={'a': round(A_ * 1000, 1), 'D': round(D_ * 1000, 1), 'front_behind_slit': round((YF - YS) * 1000, 1)})

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
def teeth_mesh(idx, both=True):
    """crowns of the left half-arch idx and their mirror images (mirrored / left-handed frames: winding reversed)"""
    Vs, Fs, o_ = [], [], 0
    for i in idx:
        V = tooth(i); hand = np.linalg.det(np.array([FR[1][i], FR[2][i], FR[3][i]])) > 0
        for mir in ((False, True) if both else (False,)):
            Fs += [[o_ + k for k in (f[::-1] if hand == mir else f)] for f in TP[i]['F']]; Vs.append(V * MX if mir else V); o_ += len(V)
    return np.vstack(Vs), Fs
def bvh(V, Fs): return BVHTree.FromPolygons(V.tolist(), Fs)

# the lower arch steps back from a tight overjet until no lower crown touches an upper one (left half, both ways)
DANT, DPOST = 1.6 * SG, 1.85 * SG
for it in range(20):
    FR = layout(TP, Q, A_, D_, YF, DANT, DPOST); NU, _ = fit_nu(TPL, FR)
    (Vu, Fu), (Vl, Fl) = teeth_mesh(range(7), False), teeth_mesh(range(7, 14), False)
    cross = int(inside(bvh(Vu, Fu), Vl).sum() + inside(bvh(Vl, Fl), Vu).sum())
    if cross == 0: break
    DANT += .15 * SG; DPOST += .03 * SG
DANT += .1 * SG; FR = layout(TP, Q, A_, D_, YF, DANT, DPOST); NU, NUOK = fit_nu(TPL, FR)   # a little air: faces, not only vertices
info['lower_setback_mm'] = {'front': round(DANT * 1000, 2), 'back': round(DPOST * 1000, 2), 'steps': it}

# ---- 4. gum tube along the necks of one arch (sections in the tooth frames, interpolated by arc length)
def tri(Fs): return [(f[0], f[i], f[i + 1]) for f in Fs for i in range(1, len(f) - 1)]
def vol_sign(V, Fs): return sum(np.dot(V[f[0]], np.cross(V[f[1]], V[f[2]])) for f in tri(Fs))
def gum_mesh(idx):
    idx = list(idx); tp = [TP[i] for i in idx]; w = np.array([d['w'] for d in tp]); G = GUM_H * SG
    s0 = np.cumsum(w) - w; ks = np.r_[-(s0[0] + w[0] / 2), s0 + w / 2]        # mirrored central incisor = first knot
    neck = np.array([to_world(np.array([[0, d['cy0'], 0.0]]), [f[i] for f in FR], d['h'], d['ycap'], NU[i])[0] for i, d in zip(idx, tp)])
    def at(s_, A2):
        A2 = np.asarray(A2, float)
        if A2.ndim == 1: return np.interp(s_, ks, np.r_[A2[0], A2])
        A2 = np.vstack([A2[0] * MX, A2]); return np.stack([np.interp(s_, ks, A2[:, c]) for c in range(3)], 1)
    ss = np.r_[np.concatenate([s0[i] + w[i] * np.array([0, .2, .4, .6, .8]) for i in range(len(w))]), s0[-1] + w[-1]]
    k_ = np.clip(np.searchsorted(s0, ss, 'right') - 1, 0, len(w) - 1); fr_ = np.clip((ss - s0[k_]) / w[k_], 0, 1)
    pap = np.array([PAP[d['cls']] for d in tp]) * SG
    pp = np.where(fr_ < .5, np.maximum(pap[k_], pap[np.maximum(k_ - 1, 0)]), np.maximum(pap[k_], pap[np.minimum(k_ + 1, len(w) - 1)]))
    m = GUM_M * SG + pp * (.5 + .5 * np.cos(2 * np.pi * fr_)) ** 1.5          # papillae up at the contacts
    Pn, Y, A = at(ss, neck), at(ss, FR[2][idx]), at(ss, FR[3][idx]); Wb = (at(ss, [d['b0'] for d in tp]) + .15 * SG) / .8
    Y /= np.linalg.norm(Y, axis=1, keepdims=True); A /= np.linalg.norm(A, axis=1, keepdims=True)
    sec = []
    for i in range(len(ss)):
        gy, gz = gum_yz(Wb[i], Wb[i], m[i], G); sec.append(Pn[i] + gy[:, None] * Y[i] + gz[:, None] * A[i])
    last, c_, Md = sec[-1], sec[-1].mean(0), FR[1][idx[-1]]                 # behind the last molar: rounded end
    for dd, sh in ((.45, .8), (.85, .45)): sec.append(c_ + dd * G * Md + sh * (last - c_))
    sec[0][:, 0] = 0.0
    Ls = [s_ * MX for s_ in sec[:0:-1]] + sec; n = len(GL); Fs = []
    for k in range(len(Ls) - 1):
        for j in range(n): Fs.append([k * n + j, k * n + (j + 1) % n, (k + 1) * n + (j + 1) % n, (k + 1) * n + j])
    tipc = c_ + 1.1 * G * Md
    V = np.vstack(Ls + [tipc * MX, tipc]); e0, e1, k1 = len(V) - 2, len(V) - 1, len(Ls) - 1
    Fs += [[(j + 1) % n, j, e0] for j in range(n)] + [[k1 * n + j, k1 * n + (j + 1) % n, e1] for j in range(n)]
    if vol_sign(V, Fs) < 0: Fs = [f[::-1] for f in Fs]
    return V, Fs

def clamp_gum(V):
    """gum points the eroded cavity would cut (the crest against the palate / floor) are pressed into the room"""
    f, c = room(V); okc = np.isfinite(f) & np.isfinite(c); z = V[:, 2].copy()
    z[okc] = np.clip(z[okc], f[okc] + 1e-5, c[okc] - 1e-5); n = int((np.abs(z - V[:, 2]) > 1e-9).sum()); V = V.copy(); V[:, 2] = z
    return V, n

Vut, Fut = teeth_mesh(range(7)); Vlt, Flt = teeth_mesh(range(7, 14))
Vug, Fug = gum_mesh(range(7)); Vlg, Flg = gum_mesh(range(7, 14))
Vug, nu_c = clamp_gum(Vug); Vlg, nl_c = clamp_gum(Vlg); info['gum_pressed_verts'] = [nu_c, nl_c]

# ---- 5. tongue: rings along y from a rounded tip just behind the lower incisors to the back of the cavity
NA, NY, TM = 20, 24, S * MM                                       # tongue sizes follow the mouth
EL = FR[0][7:, 1]                                                # lower cusp plane (no overbite) along y, by tooth
ZP = lambda y: np.interp(y, EL, Z0 - ZF * S * MM * np.array([1, 1, .8, .45, .2, 0, 0])) - GP / 2 * SG
ZD = ZP(np.inf) - .6 * SG                                         # dorsum just under the lower posterior cusp tips
BLt, BLg, BUt, BUg = bvh(Vlt, Flt), bvh(Vlg, Flg), bvh(Vut, Fut), bvh(Vug, Fug)
th = 2 * np.pi * np.arange(NA) / NA; TC, TS = np.cos(th), np.sin(th)
TC = np.sign(TC) * np.abs(TC) ** (2 / 2.4); TS = np.sign(TS) * np.abs(TS) ** (2 / 2.4); TC[np.abs(TC) < 1e-9] = 0
sst = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
rnd = lambda d, r: np.sqrt(np.clip(1 - (1 - np.clip(d / r, 0, 1)) ** 2, 0, 1))            # quarter circle 0 -> 1 over r
zt = ZP(YF) - .6 * SG - .6 * TM - 2 * TM                           # tip centre height (4 mm thick tip)
LO3 = np.vstack([Vlt, Vlg]); band = LO3[(np.abs(LO3[:, 2] - zt) < 1.5 * TM) & (np.abs(LO3[:, 0]) < 3 * TM) & (LO3[:, 1] < YF + 15 * SG)]
jc = len(xs) - 1; colok = np.isfinite(FE[:, jc]) & (FE[:, jc] < ZD - 2.5 * TM)
y_back = ys[np.where(colok)[0].max()]
LH = np.vstack([Vlt[Vlt[:, 0] > 0], Vlg[Vlg[:, 0] > 0]])
def stations(y_tip):
    """station y, length fraction, dorsum, bottom at the centre (the floor, at most Tmx under the dorsum), half width
    limit (lingual side of the lower arch / the cavity)"""
    Lt = y_back - y_tip; ph = np.pi * (np.arange(NY) + 1) / (NY + 1); ty = y_tip + Lt * (1 - np.cos(ph)) / 2; fy = (ty - y_tip) / Lt
    dor = ZP(ty) - .6 * SG - .6 * TM * (1 - sst(fy / .4)); Tmx = (4 + 6 * sst(fy / .55)) * TM
    f0, _ = room(np.c_[np.zeros(NY), ty, dor]); bot = np.maximum(np.where(np.isfinite(f0), f0, dor - Tmx) + 1e-5, dor - Tmx)
    Wl, Wa = np.zeros(NY), np.zeros(NY)
    for k in range(NY):
        b_ = LH[(LH[:, 1] > ty[k] - .25 * SG) & (LH[:, 1] < ty[k] + SG) & (LH[:, 2] > bot[k] - SG) & (LH[:, 2] < dor[k] + .5 * SG)]
        wa = b_[:, 0].min() - .3 * SG if len(b_) and fy[k] > .2 else np.inf      # the tip is rounded, not squeezed
        xx = np.linspace(0, half * 1.1, 150); f_, c_ = room(np.c_[xx, np.full(150, ty[k]), np.full(150, dor[k])])
        okx = np.isfinite(f_) & (c_ > dor[k]) & (f_ < dor[k] - 2 * TM); wc = xx[np.argmin(okx)] - .4 * TM if not okx.all() else xx[-1]
        Wa[k], Wl[k] = wa, max(wc, .5 * TM)
    fin = np.isfinite(Wa); Wa[~fin & (fy > .2)] = Wa[fin][-1]; Wa[fy <= .2] = Wa[fin][0]   # tip / behind the arch: as in it
    Wl = np.maximum(np.minimum(Wl, np.where(np.isfinite(Wa), Wa, Wl)), .5 * TM)
    for _ in range(3): Wl[1:-1] = np.minimum(Wl[1:-1], (Wl[:-2] + 2 * Wl[1:-1] + Wl[2:]) / 4)
    km = int(np.argmax(Wl)); Wl[:km + 1] = np.minimum.accumulate(Wl[:km + 1][::-1])[::-1]; Wl[km:] = np.minimum.accumulate(Wl[km:])   # no waist
    return dict(y_tip=y_tip, Lt=Lt, ty=ty, fy=fy, dor=dor, bot=bot, Wl=Wl, rt=.75 * Wl[(fy > .15) & (fy < .45)].mean())
def tongue(T):
    """rings: superellipse sections, planform rounded at the tip (radius rt) and the back (rb); groove on top;
    underside pressed onto the floor"""
    ty, fy, dor, bot, Wl, y_tip = T['ty'], T['fy'], T['dor'], T['bot'], T['Wl'], T['y_tip']; rb, rv = 5 * TM, 2.5 * TM
    R = []; ztip = (dor[0] + max(bot[0], dor[0] - 4 * TM)) / 2
    for k in range(NY):
        e_t, e_b = rnd(ty[k] - y_tip, T['rt']), rnd(y_back - ty[k], rb); ev = rnd(ty[k] - y_tip, rv)
        w_ = Wl[k] * e_t * e_b; top = ztip + (dor[k] - ztip) * ev; lo_ = ztip + (bot[k] - ztip) * ev
        x = w_ * TC; z = (top + lo_) / 2 + (top - lo_) / 2 * TS
        gr = .9 * TM * np.sin(np.pi * fy[k]) ** .5; z = z - gr * np.exp(-(x / (.22 * max(w_, 1e-6))) ** 2) * np.clip(TS, 0, 1) ** 3
        P_ = np.c_[x, np.full(NA, ty[k]), z]; f_, _ = room(P_); lowr = (TS < 0) & np.isfinite(f_)
        P_[lowr, 2] = np.maximum(P_[lowr, 2], f_[lowr] + 1e-5); R.append(P_)
    V = np.vstack([[0, y_tip, ztip]] + R + [[0, y_back, R[-1][:, 2].mean()]])
    Fs = [[0, 1 + (j + 1) % NA, 1 + j] for j in range(NA)]
    for k in range(NY - 1):
        b = 1 + k * NA; Fs += [[b + j, b + NA + j, b + NA + (j + 1) % NA, b + (j + 1) % NA] for j in range(NA)]
    b = 1 + (NY - 1) * NA; Fs += [[b + j, b + (j + 1) % NA, len(V) - 1] for j in range(NA)]
    if vol_sign(V, Fs) < 0: Fs = [f[::-1] for f in Fs]
    return V, Fs
T_ = stations((band[:, 1].max() if len(band) else YF + 3 * SG) + .5 * SG)
for it in range(20):                                              # narrow the stations that touch anything; the tip steps back
    Vt, Ft = tongue(T_)
    badv = ~fits(Vt) | inside(BLt, Vt) | inside(BLg, Vt) | inside(BUt, Vt) | inside(BUg, Vt)
    if not badv.any(): break
    st = np.clip((np.where(badv)[0] - 1) // NA, 0, NY - 1)
    if badv[0] or (T_['fy'][st] < .2).any(): T_ = stations(T_['y_tip'] + .3 * SG); continue
    for k in np.unique(st): T_['Wl'][max(k - 1, 0):k + 2] *= .94
Lt = T_['Lt']
info['tongue_fix_steps'] = it

# ---- objects, materials
def mat(name, rgb, rough):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.diffuse_color = (*rgb, 1); m.roughness = rough
    m.use_nodes = True; b = m.node_tree.nodes.get('Principled BSDF')
    if b: b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    return m
MT = {'teeth': mat('teeth', (0.84, 0.78, 0.64), 0.3), 'gums': mat('gums', (0.62, 0.17, 0.19), 0.45), 'tongue': mat('tongue', (0.6, 0.14, 0.16), 0.55)}
def make(name, parts, mats):
    V = np.vstack([p[0] for p in parts]); Fs, mi, o_ = [], [], 0
    for k, (Vp, Fp) in enumerate(parts): Fs += [[o_ + i for i in f] for f in Fp]; mi += [k] * len(Fp); o_ += len(Vp)
    V[np.abs(V[:, 0]) < 1e-9, 0] = 0.0
    m = bpy.data.meshes.new(name); m.from_pydata(V.tolist(), [], Fs); m.update()
    for mt in mats: m.materials.append(MT[mt])
    m.polygons.foreach_set('material_index', mi); m.polygons.foreach_set('use_smooth', [True] * len(Fs)); m.update()
    o = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(o); o.color = (*MT[mats[0]].diffuse_color[:3], 1)
    return o, V
_, Vup = make('teeth_up', [(Vut, Fut), (Vug, Fug)], ['teeth', 'gums'])
_, Vlo = make('teeth_lo', [(Vlt, Flt), (Vlg, Flg)], ['teeth', 'gums'])
_, Vtg = make('tongue', [(Vt, Ft)], ['tongue'])

# ---- QA
qa = {}
for n, V in (('teeth_up', Vup), ('teeth_lo', Vlo), ('tongue', Vtg)):
    qa[n] = {'verts': len(V), 'outside_skin': int((~inside(ENV, V)).sum()), 'outside_cavity': int((~inside(BAG, V)).sum())}
qa['lower_in_upper_teeth'] = int(inside(BUt, Vlt).sum()); qa['upper_in_lower_teeth'] = int(inside(BLt, Vut).sum())
qa['tongue_in_teeth_gums'] = int((inside(BLt, Vtg) | inside(BLg, Vtg) | inside(BUt, Vtg) | inside(BUg, Vtg)).sum())
qa['crowns_fit_min_height'] = bool(NUOK.all())
mc = X[sl].mean(0); qa['parity_sanity'] = bool(inside(BAG, [mc + [0, .01 * S, 0]])[0] and inside(ENV, [mc + [0, .01 * S, 0]])[0]
                                             and not inside(BAG, [mc - [0, .02, 0]])[0] and not inside(ENV, [mc - [0, .02, 0]])[0])
cu, cl = tooth(0), tooth(7); eu, el = cu[:, 2].min(), cl[:, 2].max()
lab = cu[np.argmin(cu[:, 1])]; hit = BAG.ray_cast(Vector(tuple(lab)), Vector((0, -1, 0)), 0.05)
mm = lambda v: round(float(v) * 1000, 2)
info.update(qa=qa, overbite_mm=mm(el - eu), overjet_mm=mm(cl[cl[:, 2] > el - SG][:, 1].min() - cu[cu[:, 2] < eu + SG][:, 1].min()),
            intercanine_mm=mm(2 * FR[0][2][0]), intermolar_mm=mm(2 * FR[0][5][0]),
            arch_depth_mm=mm(FR[0][6][1] + TP[6]['w'] / 2 * FR[1][6][1] - FR[0][0][1]),
            upper_incisor_wh_mm=[mm(TP[0]['w']), mm(TP[0]['h'] * NU[0])], incisor_behind_slit_mm=mm(lab[1] - YS),
            incisor_to_lip_mm=mm(hit[3]) if hit[0] is not None else None,
            crown_height_frac={'up': np.round(NU[:7], 2).tolist(), 'lo': np.round(NU[7:], 2).tolist()},
            tongue_mm={'length': mm(Lt), 'max_width': mm(2 * Vtg[:, 0].max()), 'max_thick': mm(max(np.ptp(Vtg[1 + k * NA:1 + (k + 1) * NA, 2]) for k in range(NY))),
                       'top_below_occlusal_min': mm((ZP(Vtg[:, 1]) - Vtg[:, 2]).min())},
            secs=round(time.time() - T0, 1))
# sizes against the mouth (2026-10-13): outer arch width at the molars, the tongue against it and against the room
# between the lower arches (lingual), all from the meshes
_lo = Vlt[np.abs(Vlt[:, 1] - FR[0][12][1]) < TP[12]['w'] / 2]; _ow = 2 * np.abs(np.r_[Vut[:, 0], Vlt[:, 0]]).max()
info['size_vs_mouth'] = {'arch_outer_w_mm': mm(_ow), 'arch_to_mouth': round(float(_ow / (2 * half)), 3),
                         'lower_lingual_w_mm': mm(2 * np.abs(_lo[:, 0]).min()) if len(_lo) else None,
                         'tongue_to_arch': round(float(2 * Vtg[:, 0].max() / _ow), 3)}
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(info, open(os.path.splitext(OUT)[0] + '_teeth.json', 'w'), indent=1)
print('TEETH', json.dumps(info))
