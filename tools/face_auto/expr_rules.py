"""Hand-authored (rule-based) expression shapes measured from each face: no motion template.

Every shape is a displacement field built from the face's own mouth structure (loop_organs attributes: mouth_ring BFS
rings with the lip slit at ring K, mouth_u position round the mouth: upper lip 0..0.5, lower 0.5..1, corners 0 / 0.5)
and its own sizes:
  w   half mouth width (slit corner x)            L   lip zone depth (median distance of ring K-2 to the slit)
  d   distance of a skin vertex to the slit        x   left-right position (head-local, centre 0)
Roll rings (K+1, K+2) move with the slit; the front cavity rings follow partly, so nothing pokes out of the lips.
Style presets (realistic / semi / cartoon / anime) hold the amounts as fractions of w and L, so a thin or a chubby face of
the same style gets the same expression language at its own size.

Shapes so far:
  mouthFunnel ("오"): corners drawn in, lips pushed forward and everted, slit opened into a rounded hole, jaw a little open
  mouthPucker ("우"): corners drawn in further, lips pushed forward and pressed together into a small rounded bud
Writes the keys onto 'face' (replacing same-named keys), lower teeth / tongue follow the small jaw part.
Usage: blender -b <arkit_bp.blend> -P expr_rules.py -- <eyes_mouth.json> <style> <out.blend> [keys,...]
"""
import bpy, sys, os, json
import numpy as np
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index('--') + 1:]
MJ, STYLE, OUT = a[0], a[1], os.path.abspath(a[2]); KEYS = a[3].split(',') if len(a) > 3 else ['mouthFunnel', 'mouthPucker']
PRESET = {   # fractions of w (half mouth width) or L (lip zone depth); jaw = share of the face's own jawOpen key
    'realistic': {'mouthFunnel': dict(inward=0.24, fwd=0.85, evert=0.45, open=0.55, jaw=0.18, reach=1.15),
                  'mouthPucker': dict(inward=0.36, fwd=1.25, evert=0.35, open=0.08, press=0.25, jaw=0.04, reach=1.2)},
    'semi':      {'mouthFunnel': dict(inward=0.26, fwd=0.85, evert=0.45, open=0.6, jaw=0.18, reach=1.15),
                  'mouthPucker': dict(inward=0.38, fwd=1.25, evert=0.35, open=0.08, press=0.25, jaw=0.04, reach=1.2)},
    'cartoon':   {'mouthFunnel': dict(inward=0.32, fwd=1.1, evert=0.6, open=0.75, jaw=0.2, reach=1.25),
                  'mouthPucker': dict(inward=0.45, fwd=1.6, evert=0.45, open=0.1, press=0.3, jaw=0.04, reach=1.3)},
    'anime':     {'mouthFunnel': dict(inward=0.3, fwd=0.55, evert=0.3, open=0.7, jaw=0.15, reach=1.0),
                  'mouthPucker': dict(inward=0.42, fwd=0.8, evert=0.25, open=0.06, press=0.3, jaw=0.03, reach=1.05)},
}[STYLE]
J = json.load(open(MJ)); K = int(J.get('rings', 12))
F = bpy.data.objects['face']; me = F.data; n = len(me.vertices)
rg = np.array([d.value for d in me.attributes['mouth_ring'].data]); uu = np.array([d.value for d in me.attributes['mouth_u'].data]) % 1.0
kb = me.shape_keys.key_blocks
def co(b): X = np.empty(n * 3); b.data.foreach_get('co', X); return X.reshape(-1, 3)
X0 = co(kb[0])
sl = np.where(rg == K)[0]
corner = np.minimum(uu % 0.5, 0.5 - uu % 0.5) < 1e-6
side = np.where(corner, 0.0, np.where(uu < 0.5, 1.0, -1.0))
w = float(np.abs(X0[sl[corner[sl]], 0]).max()) if corner[sl].any() else float(np.abs(X0[sl, 0]).max())
kd = KDTree(len(sl))
for j, i in enumerate(sl): kd.insert(X0[i], j)
kd.balance()
d = np.array([kd.find(p)[2] for p in X0]); near = np.array([sl[kd.find(p)[1]] for p in X0])
r2 = np.where(rg == K - 2)[0]; L = float(np.median(d[r2])) if len(r2) else 0.12 * w
zc = float(np.median(X0[sl, 2])); yc = float(np.median(X0[sl, 1]))
ss = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))
skin = (rg >= 1) & (rg <= K); roll = (rg == K + 1) | (rg == K + 2); cav = rg > K + 2
# region weights: lips (d <= L) full, fading over 'reach' * w into the cheeks / chin; roll = slit; cavity front rings partly
def falloff(reach):
    f = np.zeros(n); f[skin] = 1 - ss((d[skin] - L) / max(reach * w, 1e-6)); f[roll] = 1.0
    depth = rg[cav] - (K + 2); f[cav] = np.clip(1 - 0.35 * depth, 0, 1); return f
lipness = np.where(skin, 1 - ss(d / max(L, 1e-6)), np.where(roll, 1.0, 0.0))          # 1 at the slit, 0 past the lip zone
sd = np.where(skin | roll, side, side[near])
# the opening profile along x: 1 at the centre, 0 at the (drawn-in) corner
def open_profile(inward):
    wc = w * (1 - inward); t = np.clip(np.abs(X0[:, 0]) / max(wc, 1e-6), 0, 1)
    return np.sqrt(np.clip(1 - t ** 2, 0, 1))
jawk = kb.get('jawOpen'); XJ = co(jawk) if jawk else X0.copy()
def build(p):
    f = falloff(p['reach']); D = np.zeros_like(X0)
    D[:, 0] = -p['inward'] * X0[:, 0] * f                                   # corners and cheeks drawn toward the centre
    fwd = p['fwd'] * L * f ** 1.5                                           # lips forward (front = -y), less on the cheeks
    D[:, 1] = -fwd - p['evert'] * L * lipness                               # the lip edge everts further
    op = open_profile(p['inward'])
    D[:, 2] = sd * p['open'] * L * op * (0.35 + 0.65 * lipness) * (f > 0)   # rounded hole: upper lip up, lower down
    if 'press' in p:                                                        # pucker: the lip bodies pressed together
        D[:, 2] -= sd * p['press'] * L * lipness * (1 - op * 0.5)
    D += p['jaw'] * (XJ - X0)                                               # a little jaw for the vowel
    return D
qa = {'style': STYLE, 'w_mm': round(w * 1000, 2), 'L_mm': round(L * 1000, 2), 'slit_ring': K, 'keys': {}}
for k in KEYS:
    if k not in PRESET: continue
    D = build(PRESET[k])
    if k in kb: F.shape_key_remove(kb[k])
    sk = F.shape_key_add(name=k, from_mix=False); sk.data.foreach_set('co', (X0 + D).ravel())
    qa['keys'][k] = {'max_mm': round(float(np.linalg.norm(D, axis=1).max() * 1000), 2), 'corner_in_mm': round(PRESET[k]['inward'] * w * 1000, 2)}
    for nm in ('teeth_lo', 'tongue'):                                       # lower teeth / tongue: only the jaw share
        o = bpy.data.objects.get(nm)
        if o is None or not o.data.shape_keys or 'jawOpen' not in o.data.shape_keys.key_blocks: continue
        okb = o.data.shape_keys.key_blocks; m_ = len(o.data.vertices)
        B0 = np.empty(m_ * 3); okb[0].data.foreach_get('co', B0); BJ = np.empty(m_ * 3); okb['jawOpen'].data.foreach_get('co', BJ)
        if k in okb: o.shape_key_remove(okb[k])
        s2 = o.shape_key_add(name=k, from_mix=False); s2.data.foreach_set('co', B0 + PRESET[k]['jaw'] * (BJ - B0))
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('RULES', json.dumps(qa))
