"""Clean procedural textures for the mouth parts (texture step 2c). No reference needed: the painting never
shows them. UVs from uv_parts.py:
  teeth.png  (1024 x 512) left half = teeth: u = around the arch (0.5 = front middle), v = gum line (0) ->
             biting edge (1): ivory, yellower at the neck, a translucent blue-grey biting edge, faint
             per-tooth variation and enamel speckle. Right half = gums: pink, deeper red away from the teeth.
  tongue.png (512 x 512) top-down: v = 1 at the tip, 0 at the back: pink-red, darker toward the back, a central
             groove, papillae speckle, lighter rim.
Colours are sRGB; --tint r,g,b (0..1) multiplies the gums / tongue (e.g. from the lip colour) if given.
Usage: python mouth_textures.py <out_dir> [--tint r,g,b]
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_views as rv

a = sys.argv[1:]; OUT = os.path.abspath(a[0]); os.makedirs(OUT, exist_ok=True)
tint = np.array([float(x) for x in a[a.index('--tint') + 1].split(',')]) if '--tint' in a else np.ones(3)
rng = np.random.default_rng(3)
import cv2


def noise(h, w, scale, seed):
    r = np.random.default_rng(seed).standard_normal((max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(cv2.GaussianBlur(r, (0, 0), 1.0), (w, h), interpolation=cv2.INTER_CUBIC)


def lerp(c0, c1, t): return c0 * (1 - t[..., None]) + c1 * t[..., None]


def sstep(e0, e1, x): t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)


# ---- teeth + gums
H, W = 512, 1024
v = 1 - (np.arange(H) + 0.5) / H; u = (np.arange(W // 2) + 0.5) / (W // 2)
V_, U_ = np.meshgrid(v, u, indexing='ij')
neck = np.array([0.86, 0.80, 0.66]); body = np.array([0.95, 0.93, 0.87]); edge = np.array([0.78, 0.81, 0.84])
teeth = lerp(neck, body, sstep(0.0, 0.35, V_))
teeth = lerp(teeth, edge, sstep(0.80, 0.98, V_) * 0.75)
# per-tooth variation: ~16 teeth across the arch, slight darkening between them
tooth_id = U_ * 16; between = np.abs((tooth_id % 1.0) - 0.5) * 2              # 1 at the gaps
teeth *= (1 - 0.03 * sstep(0.9, 1.0, between) * (1 - sstep(0.85, 1.0, V_)))[..., None]   # faint: the arch is not split per tooth
var = noise(H, W // 2, 32, 1)[..., None]; teeth *= 1 + 0.025 * var
teeth *= 1 + 0.015 * noise(H, W // 2, 3, 2)[..., None]                          # enamel speckle
gum_hi = np.array([0.82, 0.45, 0.48]) * tint; gum_lo = np.array([0.62, 0.24, 0.28]) * tint
gums = lerp(gum_lo, gum_hi, sstep(0.0, 0.6, V_)) * (1 + 0.04 * noise(H, W // 2, 8, 4))[..., None]
tex = np.concatenate([teeth, gums], 1)
rv.save_rgb(os.path.join(OUT, 'teeth.png'), tex)

# ---- tongue
H = W = 512
v = 1 - (np.arange(H) + 0.5) / H; u = (np.arange(W) + 0.5) / W
V_, U_ = np.meshgrid(v, u, indexing='ij')
tip = np.array([0.86, 0.47, 0.49]) * tint; back = np.array([0.52, 0.20, 0.24]) * tint
tg = lerp(back, tip, sstep(0.0, 0.85, V_))
groove = np.exp(-((U_ - 0.5) / 0.035) ** 2) * sstep(0.15, 0.6, V_) * (1 - sstep(0.85, 1.0, V_))
tg *= (1 - 0.18 * groove)[..., None]
rim = sstep(0.36, 0.48, np.abs(U_ - 0.5)); tg = lerp(tg, tg * 1.08, rim)
pap = (noise(H, W, 2, 5) > 1.2).astype(np.float32); pap = cv2.GaussianBlur(pap, (0, 0), 0.6)
tg *= (1 + 0.06 * pap - 0.03 * noise(H, W, 16, 6))[..., None]
rv.save_rgb(os.path.join(OUT, 'tongue.png'), tg)
print('MOUTH_TEX', json.dumps({'teeth': 'teeth.png 1024x512', 'tongue': 'tongue.png 512x512', 'tint': tint.tolist()}))
