"""gen_monsters: each staged expedition species gets its own voice (tools/sfx convention).

The 29 species of server/catalog.py ENEMIES that belong to a map (forest / quarry / frost) used to
borrow the voice of their stand-in (wolf, boar, brute, wisp, shroom). This writes their own takes:

  game/assets/sfx/creatures/<species>_<event>_<n>.wav   event = idle alert windup strike hurt death,
                                                        4 structurally different takes each
  game/assets/sfx/creatures/<boss>_roar_<n>.wav         bosses (tier "boss"): 4 long layered roars
  game/assets/sfx/creatures/<boss>_intro_<n>.wav        ... and 3 arrival stings (rumble/swell + cry)

Every species is a Kit (its own call, bark, pain cry, breath, texture, signature, hit, swish and
fall, built from the make_creature_sfx.py / make_village_sfx.py helpers through gen_combat_kit.py),
and every event has four archetypes (EVENT_FN) that arrange those parts differently: a long call
over a texture, a chatter of short calls, a texture with the signature, a breath into a call, and
so on, so two takes of a family never differ by jitter alone. A Kit can replace any archetype with
its own (Kit.custom). The species' map is baked in (make_creature_sfx.region_layer: moss and twigs,
ember warmth, ice shimmer, plus that map's room), so these takes get no runtime region layer.

Levels: each family matches the median st-rms of its stand-in's region-neutral takes for the same
event (make_creature_sfx.CREATURE_DB, gen_combat_creatures.py); boss roars and intros sit BOSS_DB
hotter than the stand-in's alert. 22050 Hz mono, sfxlib.finish() fades, A-weighted balance.

Numbering starts at 1 (no originals exist); make_family() refuses to overwrite a protected file, so
re-render the committed takes with the environment variable SFX_BASE=merge-version-gate set.

  .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_monsters.py [--only goblin,troll] [--events idle,roar]
        [--out <scratch dir>] [--list] [--dry-run]

Never imports-and-runs another generator: gen_combat_creatures.py and gen_combat_kit.py are used for
their helpers and level tables only (neither has a main()).
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter1d

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_combat_kit import (C, L, SR, SR22, S, T, V, band, bloop, breathy, buf, burst, click, ctl, debris,  # noqa: E402
                            fire, glide, high, low, modal, norm, nsweep, pk, place, pops, rock, rustle, scrape, secs,
                            shaped, snarl, thud, tinkles, to_sr, u)
import gen_combat_creatures as GC  # noqa: E402  (EVENTS and the per-event level table; no main())

CREAT = L.SFX_ROOT / "creatures"
EVENTS = list(GC.EVENTS)              # idle alert windup strike hurt death
TAKES = 4
BOSS_EVENTS = {"roar": 4, "intro": 3}
BOSS_DB = 2.0                         # roar / intro: this much hotter than the stand-in's alert
CAP = {"idle": 1.2, "alert": 1.3, "windup": 1.5, "strike": 0.9, "hurt": 0.68, "death": 1.75, "roar": 2.9, "intro": 3.2}
MAX_DUR = {k: v + 0.05 for k, v in CAP.items()}   # finish() safety cut; takes are faded out at CAP first
SEED = "gen_monsters-v1"


# =============================================================================== catalog
def catalog() -> dict:
    """The staged species of server/catalog.py ENEMIES (those with a map), read as a literal."""
    src = (L.REPO / "server" / "catalog.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ENEMIES" for t in node.targets):
            enemies = ast.literal_eval(node.value)
            return {k: v for k, v in enemies.items() if "map" in v}
    raise SystemExit("gen_monsters: ENEMIES not found in server/catalog.py")


# =============================================================================== primitives (32 kHz)
def R(d, pts):
    """Relative (0..1, value) points -> absolute seconds."""
    return [(t * d, v) for t, v in pts]


SHAPE = {   # pitch contours (relative time, multiplier)
    "rise": [(0, 0.86), (0.65, 1.1), (1, 1.16)],
    "fall": [(0, 1.14), (0.2, 1.12), (1, 0.74)],
    "arch": [(0, 0.88), (0.45, 1.14), (1, 0.84)],
    "flat": [(0, 1.0), (0.5, 1.03), (1, 0.96)],
    "dip": [(0, 1.1), (0.45, 0.84), (1, 1.12)],
    "step": [(0, 0.92), (0.3, 0.92), (0.36, 1.2), (0.7, 1.2), (0.76, 0.98), (1, 0.95)],
}
AMP = {     # loudness contour that belongs to each pitch contour
    "rise": [(0, 0), (0.6, 0.85), (0.92, 1), (1, 0)],
    "fall": [(0, 0), (0.06, 1), (0.5, 0.75), (1, 0)],
    "arch": [(0, 0), (0.3, 0.9), (0.6, 1), (1, 0)],
    "flat": [(0, 0), (0.12, 1), (0.8, 0.85), (1, 0)],
    "dip": [(0, 0), (0.1, 1), (0.45, 0.6), (0.85, 1), (1, 0)],
    "step": [(0, 0), (0.08, 0.8), (0.36, 1), (0.9, 0.8), (1, 0)],
}
ENV = {     # texture envelopes
    "swell": [(0, 0), (0.5, 1), (1, 0)],
    "pulse": [(0, 0), (0.15, 1), (0.35, 0.4), (0.55, 1), (0.75, 0.35), (1, 0)],
    "fade": [(0, 1), (0.1, 0.9), (1, 0)],
    "build": [(0, 0.05), (0.85, 1), (1, 0)],
    "burst": [(0, 0), (0.03, 1), (0.3, 0.45), (1, 0)],
    "decay": [(0, 0.2), (0.1, 1), (0.5, 0.55), (1, 0)],
}
IN_AMP = [(0, 0), (0.85, 1), (1, 0)]
OUT_AMP = [(0, 0), (0.08, 1), (1, 0)]


def fp(f, shape, k=1.0):
    pts = SHAPE[shape] if isinstance(shape, str) else shape
    return [(t, f * k * m) for t, m in pts]


def amp_of(shape):
    return AMP[shape] if isinstance(shape, str) else AMP["arch"]


def voc(s, d, f, vow, amp=None, scale=1.0, tilt=1.0, breath=0.2, rasp=0.0, sharp=3.0, rlo=250, rhi=7000, sub=0.0,
        flutter=0.0, vib=(0.0, 0.0), fmax=6000, bw=1.0, odd=0.0, jitter=0.005, am=None):
    """Formant voice over d s: f = [(rel t, Hz)], vow = vowel or [(rel t, vowel)], amp = [(rel t, a)];
    rasp adds pulsed formant noise (snarl / screech), am = (Hz, depth) a wandering tremolo (gurgle)."""
    n = secs(d)
    f0 = ctl(n, R(d, f))
    F = C.tracks(n, vow if isinstance(vow, str) else R(d, vow), scale)
    a = ctl(n, R(d, amp or [(0, 0), (0.12, 1), (0.7, 0.85), (1, 0)]))
    x = C.voice(s, n, f0, F, a, tilt=tilt, breath=breath, sub=sub, flutter=flutter, vib=vib, fmax=fmax, bw=bw, odd=odd, jitter=jitter)
    if rasp:
        x = x + C.rasp(s, n, f0, F, sharp, rlo, rhi) * a * rasp
    if am:
        x = x * wob(s, n, am[0], am[1])
    return pk(x)


def wob(s, n, hz, depth):
    """Wandering amplitude flutter in [1-depth, 1]."""
    return 1 - depth + depth * (0.5 + 0.5 * np.clip(C.wander(s, n, hz, 1.0), -1, 1))


def whisper(s, d, vow, amp=None, scale=1.0, bw=0.2, air=0.3):
    """Unvoiced formant noise (a whisper, a dry rasp of breath)."""
    n = secs(d)
    F = C.tracks(n, vow if isinstance(vow, str) else R(d, vow), scale)
    x = sum(g * nsweep(s, n, F[i], bw) for i, g in enumerate((1.0, 0.75, 0.45)))
    x = x + norm(high(s.noise(n), 4500)) * air
    return pk(x * ctl(n, R(d, amp or [(0, 0), (0.15, 1), (0.7, 0.8), (1, 0)])))


def hissn(s, d, lo, hi, amp=None, am=None):
    """Band noise with an envelope; am = (Hz, depth) pulses it."""
    n = secs(d)
    x = norm(band(s.noise(n), lo, hi))
    if am:
        x = x * (1 - am[1] + am[1] * np.abs(np.sin(np.pi * am[0] * T(n) + u(s, 0, 3))))
    return pk(x * ctl(n, R(d, amp or ENV["swell"])))


def sweep(s, d, f_pts, amp=None, bw=0.6):
    """Noise band whose centre follows f_pts (relative time)."""
    n = secs(d)
    return pk(nsweep(s, n, ctl(n, R(d, f_pts)), bw) * ctl(n, R(d, amp or ENV["swell"])))


def buzz(s, d, rate, lo, hi, amp=None, sharp=4.0):
    """Noise pulsed at rate Hz (number or relative points): a rattlesnake, a wing buzz."""
    n = secs(d)
    r = ctl(n, R(d, rate)) if isinstance(rate, list) else np.full(n, float(rate))
    pulse = (0.5 + 0.5 * np.cos(2 * np.pi * np.cumsum(r) / SR)) ** sharp
    return pk(norm(band(s.noise(n), lo, hi)) * pulse * ctl(n, R(d, amp or ENV["swell"])))


def train(s, d, rate_pts, grain, gain_pts=None, jit=0.25, gvar=(0.55, 1.0)):
    """Events at rate(t) Hz (relative points), each grain(j, pos) placed with gain(t)."""
    n = secs(d)
    out = np.zeros(n + secs(0.4))
    rate = ctl(n, R(d, rate_pts))
    g = ctl(n, R(d, gain_pts or [(0, 1), (1, 1)]))
    t, j = 0.0, 0
    while t < d:
        i = min(secs(t), n - 1)
        place(out, np.asarray(grain(j, t / d), float), t, g[i] * u(s, *gvar))
        t += u(s, 1 - jit, 1 + jit) / max(rate[i], 0.5)
        j += 1
    return out[: n + secs(0.15)]


def grow(x, n):
    return np.concatenate([x, np.zeros(n - x.size)]) if x.size < n else x


def mix(*parts):
    """Sum of (signal, gain, offset_s) or plain signals, padded to the longest."""
    items = [(p, 1.0, 0.0) if isinstance(p, np.ndarray) else (p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in parts]
    n = max(secs(o) + np.asarray(x).size for x, _, o in items)
    out = np.zeros(n)
    for x, g, o in items:
        place(out, np.asarray(x, float), o, g)
    return out


# ------------------------------------------------------------------ grains and bodies
def bone(s, f, tau=0.012):
    """Hollow dry bone / skull knock."""
    return pk(np.asarray(modal([f, f * 2.76, f * 5.4], [tau, tau * 0.6, tau * 0.35], [1, 0.45, 0.2], max(0.06, tau * 6), s.rng))
              + click(s, 0.015, min(f, 6000), min(f * 6, 12000), 0.0008) * 0.6)


def chitin(s, f):
    """Insect shell tick."""
    return pk(np.asarray(modal([f, f * 1.53, f * 2.31], [0.0035, 0.0025, 0.0018], [1, 0.6, 0.35], 0.03, s.rng))
              + click(s, 0.012, 2500, 11000, 0.0006) * 0.9)


def glass(s, f, tau=0.12):
    """Ice / crystal ping."""
    return pk(np.asarray(modal([f, f * 2.32, f * 4.25, f * 6.63], [tau, tau * 0.55, tau * 0.3, tau * 0.18], [1, 0.45, 0.25, 0.1],
                               tau * 4 + 0.05, s.rng, attack=0.0004)))


def metal(s, f, tau=0.2, bright=1.0):
    """Struck plate / blade (inharmonic)."""
    r = (1.0, 1.47, 2.09, 2.56, 3.31, 4.12)
    return pk(np.asarray(modal([f * x * u(s, 0.99, 1.01) for x in r], [tau / (1 + 0.5 * i) for i in range(6)],
                               [1, 0.7, 0.55 * bright, 0.4 * bright, 0.25 * bright, 0.15 * bright], tau * 3 + 0.05, s.rng))
              + click(s, 0.02, 1500, 9000, 0.001) * 0.7)


def woodk(s, f, tau=0.03):
    """Wooden knock (club, lid, staff)."""
    return pk(np.asarray(V.wood_block(s, f, max(0.12, tau * 5), tau)))


def creak(s, d, f0, f1, body=(190, 430, 820, 1450), q=7.0, rough=0.2, wobble=4.0, metal_=False):
    return pk(np.asarray(V.creak(s, d, f0, f1, body=body, q=q, rough=rough, wobble=wobble, swell=min(0.12, d * 0.3),
                                 release=min(0.25, d * 0.4), metal=metal_)))


def flap(s, size=1.0, grit=0.0):
    """One wing beat: an air push with a low whump."""
    d = 0.13 * size
    x = pk(shaped(s, d, [(0, 260 / size), (0.55, 900 / size), (1, 380 / size)], [(0, 0), (0.55, 1), (0.75, 0.6), (1, 0)], 0.9, body=0.9))
    x = mix(x, (pk(thud(s, 110 / size, d + 0.08, 0.03, grit=0.4)), 0.4))
    if grit:
        x = mix(x, (pops(s, secs(d), 120, 600, 4000), grit))
    return x


def tear(s, d, lo=900, hi=5000, rate=22):
    """Cloth / flesh rip: band noise chopped fast."""
    n = secs(d)
    return pk(band(s.noise(n), lo, hi) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * rate * T(n) + u(s, 0, 3)))) * ctl(n, [(0, 0), (0.01, 1), (d, 0)]))


def grind(s, d, lo=60, hi=420, amp=None, pops_hz=50):
    """Stone on stone."""
    n = secs(d)
    a = ctl(n, R(d, amp or ENV["swell"]))
    x = norm(band(s.noise(n), lo, hi)) * (0.6 + 0.4 * np.clip(C.wander(s, n, 9, 1), -1, 1))
    return pk(x * a + pops(s, n, pops_hz, 700, 3500, a, (0.002, 0.006)) * 0.8)


def crackle(s, d, dens, lo=1500, hi=9000, amp=None, size=(0.0008, 0.003)):
    n = secs(d)
    return pops(s, n, dens, lo, hi, ctl(n, R(d, amp or ENV["fade"])), size)


def boom(s, f=45, d=0.7, tau=0.18, grit=0.6):
    return pk(thud(s, f, d, tau, drop=0.5, body=1.5, grit=grit))


def rumble(s, d, lo=40, hi=280, amp=None):
    n = secs(d)
    return pk(norm(band(s.noise(n), lo, hi)) * ctl(n, R(d, amp or ENV["swell"])) + glide(n, 38 + 5 * np.sin(2 * np.pi * 0.8 * T(n))) * 0.4 * ctl(n, R(d, amp or ENV["swell"])))


def echo(x, taps=((0.13, 0.45), (0.27, 0.28), (0.41, 0.16)), tone=3500):
    """Discrete echoes (tomb, crypt, a spectral voice)."""
    x = np.asarray(x, float)
    out = np.zeros(x.size + secs(max(t for t, _ in taps)) + 1)
    out[: x.size] += x
    dark = low(x, tone)
    for t, g in taps:
        place(out, dark, t, g)
    return out


def tidy(x, floor_db=-42.0, fade=0.08):
    """Cut the tail where it falls floor_db under the peak (reverb tails stay short) with a fade."""
    x = np.asarray(x, float)
    env = maximum_filter1d(np.abs(x), secs(0.02))
    idx = np.nonzero(env > (env.max() + 1e-12) * 10 ** (floor_db / 20))[0]
    end = min(x.size, int(idx[-1]) + secs(fade)) if idx.size else x.size
    y = x[:end].copy()
    m = min(secs(fade), y.size)
    y[-m:] *= np.cos(np.linspace(0, np.pi / 2, m)) ** 2
    return y


# =============================================================================== Kit
class Kit:
    """One species' sound parts. Subclasses set region/tempo/VOX and override the parts."""
    region = "forest"
    tempo = 1.0             # stretches the event archetypes (bigger = slower)
    layer = 1.0             # how much of make_creature_sfx.region_layer() is mixed in
    room = 1.0              # reverb time scale of the map's room
    VOX: dict = {}

    def __init__(self, s, spec):
        self.s = s
        self.spec = spec
        self.p = u(s, 0.97, 1.03)
        self.W = float(spec.get("windup", 0.9))

    def u(self, a, b):
        return u(self.s, a, b)

    def v(self, d, f, vow, amp=None, **kw):
        o = dict(self.VOX)
        o.update(kw)
        return voc(self.s, d, f, vow, amp, **o)

    def custom(self, ev, a):
        return None

    # parts every species has (override for its own character)
    def call(self, d, shape="arch", k=1.0):
        raise NotImplementedError

    def bark(self, k=1.0):
        return self.call(0.15, "fall", k * 1.1)

    def pain(self, d, shape="fall", k=1.0):
        return self.call(d, shape, k * 1.35)

    def breath(self, d, inhale=True):
        f = [(0, 900), (1, 2200)] if inhale else [(0, 1600), (1, 700)]
        return pk(breathy(self.s, d, R(d, f), R(d, IN_AMP if inhale else OUT_AMP), 0.7))

    def tex(self, d, env="swell"):
        return hissn(self.s, d, 300, 2000, ENV[env])

    def sig(self, d=0.4):
        return self.call(d, "step")

    def hit(self, g=1.0):
        return pk(thud(self.s, 90, 0.3, 0.06, grit=0.7)) * g

    def swish(self, d=0.22):
        return pk(shaped(self.s, d, [(0, 400), (0.6, 1500), (1, 600)], [(0, 0), (0.6, 1), (1, 0)], 0.6))

    def fall(self):
        return pk(thud(self.s, 75, 0.45, 0.1, body=1.2, grit=0.6))


# =============================================================================== event archetypes
PACE = 0.88            # idle / alert / death length scale (keeps the families inside the size budget)

def ev_idle(K, a):
    t, out = K.tempo * PACE, buf(2.2)
    if a == 0:      # long call over its texture
        place(out, K.tex(0.95 * t, "swell"), 0.0, 0.35)
        place(out, K.call(0.62 * t, "arch"), 0.08 * t)
    elif a == 1:    # chatter of three short calls, breath out
        for j, (at, k) in enumerate(((0.0, 1.0), (0.21, 1.12), (0.53, 0.9))):
            place(out, K.bark(k), at * t, 0.9 - 0.12 * j)
        place(out, K.breath(0.3, False), 0.75 * t, 0.45)
    elif a == 2:    # texture with the signature in it, a small call at the end
        place(out, K.tex(0.85 * t, "pulse"), 0.0, 0.8)
        place(out, K.sig(0.32 * t), 0.28 * t, 0.65)
        place(out, K.bark(0.92), 0.8 * t, 0.55)
    else:           # breath in, falling call, texture tail
        place(out, K.breath(0.3 * t, True), 0.0, 0.55)
        place(out, K.call(0.45 * t, "fall", 0.94), 0.3 * t, 0.9)
        place(out, K.tex(0.38 * t, "fade"), 0.72 * t, 0.3)
    return out


def ev_alert(K, a):
    t, out = K.tempo * PACE, buf(2.2)
    if a == 0:      # one big rising call
        place(out, K.call(0.88 * t, "rise", 1.05), 0.0)
    elif a == 1:    # signature, then call-and-answer, the answer higher
        place(out, K.sig(0.3 * t), 0.0, 0.8)
        place(out, K.call(0.32 * t, "arch"), 0.24 * t, 0.85)
        place(out, K.call(0.42 * t, "rise", 1.15), 0.62 * t)
    elif a == 2:    # two barks, a long falling call
        place(out, K.bark(1.05), 0.0)
        place(out, K.bark(1.15), 0.15 * t, 0.9)
        place(out, K.call(0.7 * t, "fall", 1.1), 0.33 * t)
    else:           # a stamp / knock with texture, then a dipping call
        place(out, K.hit(0.7), 0.0, 0.7)
        place(out, K.tex(0.35 * t, "burst"), 0.0, 0.6)
        place(out, K.call(0.72 * t, "dip"), 0.18 * t)
    return out


def ev_windup(K, a):
    out = buf(2.2)
    W = K.W * [1.0, 0.9, 1.1, 0.97][a] + 0.06
    if a == 0:      # call rising through the wind-up, sharp intake at the top
        place(out, K.call(W, "rise"), 0.0)
        place(out, K.breath(0.14, True), W - 0.12, 0.45)
    elif a == 1:    # texture building, signature at the top
        place(out, K.tex(W, "build"), 0.0, 0.9)
        place(out, K.sig(0.28), W - 0.26, 0.8)
    elif a == 2:    # three short calls climbing
        for j in range(3):
            place(out, K.bark(1.0 + 0.13 * j), j * W * 0.31, 0.6 + 0.18 * j)
        place(out, K.tex(W, "build"), 0.0, 0.3)
    else:           # long breath in, short call at the end
        place(out, K.breath(W * 0.62, True), 0.0, 0.8)
        place(out, K.call(W * 0.4, "rise", 1.12), W * 0.6)
    return out


def ev_strike(K, a):
    out = buf(1.6)
    if a == 0:      # swing, hit, shout
        place(out, K.swish(0.22), 0.0, 0.6)
        place(out, K.hit(), 0.16)
        place(out, K.bark(1.15), 0.12, 0.75)
    elif a == 1:    # shout first, hit, signature after
        place(out, K.call(0.3, "fall", 1.15), 0.0, 0.85)
        place(out, K.hit(), 0.22)
        place(out, K.sig(0.25), 0.25, 0.5)
    elif a == 2:    # double hit with texture
        place(out, K.hit(), 0.0)
        place(out, K.hit(0.8), 0.17, 0.75)
        place(out, K.tex(0.4, "burst"), 0.02, 0.45)
    else:           # signature-led attack, bark, hit
        place(out, K.sig(0.35), 0.0, 0.8)
        place(out, K.bark(1.0), 0.2, 0.8)
        place(out, K.hit(), 0.24, 0.85)
    return out


def ev_hurt(K, a):
    out = buf(1.2)
    if a == 0:      # pain cry, falling, the species' own breath out after it
        d = 0.3 * min(K.tempo, 1.15)
        place(out, K.pain(d, "fall"), 0.0)
        place(out, K.breath(0.22, False), d * 0.8, 0.4)
    elif a == 1:    # texture burst (crack, rattle) + short bark
        place(out, K.tex(0.28, "burst"), 0.0, 0.6)
        place(out, K.bark(1.2), 0.04)
    elif a == 2:    # two quick barks, gasp
        place(out, K.bark(1.25), 0.0)
        place(out, K.bark(1.05), 0.15, 0.8)
        place(out, K.breath(0.18, False), 0.28, 0.35)
    else:           # signature, rising cry
        place(out, K.sig(0.2), 0.0, 0.55)
        place(out, K.pain(0.28, "rise", 1.1), 0.06)
    return out


def ev_death(K, a):
    t, out = K.tempo * PACE, buf(2.6)
    if a == 0:      # long falling cry, the body drops
        place(out, K.pain(0.85 * t, "fall"), 0.0)
        place(out, K.fall(), 0.68 * t, 0.85)
    elif a == 1:    # short call, the body breaks up / collapses in its texture
        place(out, K.call(0.4 * t, "arch", 1.1), 0.0)
        place(out, K.tex(1.0 * t, "decay"), 0.28 * t, 0.7)
        place(out, K.fall(), 0.42 * t, 0.7)
    elif a == 2:    # three weakening calls, fall
        for j, k in enumerate((1.05, 0.92, 0.8)):
            place(out, K.bark(k), j * 0.3 * t, 0.9 - 0.2 * j)
        place(out, K.fall(), 0.88 * t, 0.85)
    else:           # signature, a last breath out, soft fall
        place(out, K.sig(0.4), 0.0, 0.7)
        place(out, K.breath(0.8 * t, False), 0.25 * t, 0.6)
        place(out, K.fall(), 0.36 * t, 0.6)
    return out


EVENT_FN = {"idle": ev_idle, "alert": ev_alert, "windup": ev_windup, "strike": ev_strike, "hurt": ev_hurt, "death": ev_death}

# =============================================================================== forest (솔바람 숲)
class Goblin(Kit):
    """고블린: nasal whiny voice, quick cackles, mumbled chatter, trinkets, a club."""
    region, tempo = "forest", 0.9
    VOX = dict(scale=1.28, tilt=1.0, breath=0.28, rasp=0.35, sharp=2.5, rlo=600, rhi=7500, fmax=8500, flutter=0.2)

    def call(self, d, shape="arch", k=1.0):      # "nyeeeh"
        return self.v(d, fp(340 * self.p, shape, k), [(0, "n"), (0.18, "ae"), (1, "e")], amp_of(shape))

    def bark(self, k=1.0):                       # "hek!"
        f = 420 * k * self.p
        return self.v(0.1, [(0, f), (0.3, f * 1.12), (1, f * 0.78)], [(0, "e"), (1, "a")], [(0, 0), (0.1, 1), (0.6, 0.6), (1, 0)], breath=0.35, rasp=0.5)

    def pain(self, d, shape="fall", k=1.0):      # "aagh"
        return self.v(d, fp(520 * self.p, shape, k), [(0, "a"), (1, "e")], amp_of(shape), rasp=0.55, breath=0.3)

    def cackle(self, n=5, rate=10.5, f=430, drop=0.06):
        out = buf(n / rate + 0.25)
        for j in range(n):
            ff = f * self.p * (1 - drop * j) * self.u(0.96, 1.04)
            at = j / rate * self.u(0.92, 1.08)
            place(out, pk(breathy(self.s, 0.03, [(0, 2500), (0.03, 3200)], [(0, 0), (0.008, 1), (0.03, 0)], 0.6)), at, 0.35)
            place(out, self.v(0.06, [(0, ff * 1.06), (1, ff * 0.9)], [(0, "e"), (1, "ae")], [(0, 0), (0.15, 1), (1, 0)], breath=0.45, rasp=0.3), at + 0.012)
        return out

    def sig(self, d=0.4):
        return self.cackle(max(3, int(d * 11)), 11.0, 430)

    def breath(self, d, inhale=True):            # nasal sniffs
        out = buf(d + 0.1)
        m = max(2, int(d / 0.09))
        for j in range(m):
            place(out, pk(breathy(self.s, 0.05, [(0, 2800), (0.05, 3600)] if inhale else [(0, 2400), (0.05, 1500)], [(0, 0), (0.01, 1), (0.05, 0)], 0.5)), j * d / m, 0.6)
        return out

    def tex(self, d, env="swell"):               # mumbled chatter + rattling trinkets
        out = buf(d + 0.3)
        e = ctl(secs(d), R(d, ENV[env]))
        t = 0.0
        while t < d - 0.08:
            f = self.u(280, 420) * self.p
            vw = ["e", "a", "eu", "i", "o"][int(self.u(0, 4.99))]
            place(out, self.v(0.07, [(0, f), (1, f * self.u(0.85, 1.12))], vw, [(0, 0), (0.2, 1), (1, 0)], breath=0.5, rasp=0.2), t, 0.5 * e[min(secs(t), e.size - 1)] + 0.05)
            t += self.u(0.08, 0.16)
        place(out, train(self.s, d, [(0, 9), (1, 14)], lambda j, q: bone(self.s, self.u(1800, 3200), 0.006), ENV[env], 0.4), 0, 0.25)
        return out

    def hit(self, g=1.0):                        # club thwack
        return mix(woodk(self.s, self.u(170, 210), 0.025), (pk(thud(self.s, 120, 0.2, 0.04, grit=0.8)), 0.8)) * g

    def swish(self, d=0.15):
        return pk(shaped(self.s, d, [(0, 600), (0.6, 2400), (1, 900)], [(0, 0), (0.6, 1), (1, 0)], 0.5))

    def fall(self):
        out = buf(0.5)
        place(out, pk(thud(self.s, 115, 0.3, 0.06, grit=0.6)), 0.0)
        for j in range(3):
            place(out, bone(self.s, self.u(1500, 2600), 0.008), 0.03 + 0.05 * j + self.u(0, 0.02), 0.4)
        return out

    def custom(self, ev, a):
        if ev == "alert" and a == 1:             # a full cackle, then a whine
            return mix(self.cackle(7, 10.0, 470, 0.05), (self.call(0.4, "rise", 1.1), 0.8, 0.72))
        if ev == "death" and a == 3:             # a last weak cackle sinking into a gurgle
            return mix(self.cackle(4, 7.5, 380, 0.12), (self.v(0.5, [(0, 300), (1, 180)], "o", [(0, 0), (0.1, 1), (1, 0)], am=(16, 0.7), breath=0.4), 0.6, 0.5), (self.fall(), 0.5, 0.7))
        if ev == "death" and a == 1:             # "aagh!", trinkets scatter, a long whimper
            out = mix(self.pain(0.3, "arch", 1.05), (self.fall(), 0.8, 0.25), (self.v(0.5, fp(300, "fall"), [(0, "e"), (1, "u")], AMP["fall"], breath=0.5, rasp=0.15), 0.5, 0.55))
            for j in range(4):
                place(out, bone(self.s, self.u(1800, 3400), 0.007), 0.3 + 0.07 * j + self.u(0, 0.03), 0.35)
            return out
        return None


class Harpy(Kit):
    """하피: piercing trilled shriek, crow-like squawk, feather rustle and wing beats, talons."""
    region, tempo = "forest", 0.95
    VOX = dict(scale=1.38, tilt=0.9, breath=0.18, rasp=0.6, sharp=4.0, rlo=900, rhi=9500, fmax=10000, vib=(17, 0.025))

    def call(self, d, shape="arch", k=1.0):      # shriek
        return self.v(d, fp(980 * self.p, shape, k), [(0, "ae"), (0.4, "i"), (1, "e")], amp_of(shape))

    def bark(self, k=1.0):                       # "kraa"
        f = 640 * k * self.p
        return self.v(0.13, [(0, f), (0.25, f * 1.28), (1, f * 0.88)], "a", [(0, 0), (0.08, 1), (0.6, 0.7), (1, 0)], rasp=0.85, sharp=5, vib=(0, 0), scale=1.15)

    def pain(self, d, shape="fall", k=1.0):
        return self.v(d, fp(1250 * self.p, shape, k), [(0, "i"), (1, "e")], amp_of(shape), rasp=0.75, vib=(23, 0.04))

    def flaps(self, n=3, rate=6.0, size=1.0):
        out = buf(n / rate + 0.35)
        for j in range(n):
            place(out, flap(self.s, size * self.u(0.92, 1.08)), j / rate * self.u(0.94, 1.06), self.u(0.75, 1.0))
        return out

    def sig(self, d=0.4):
        return self.flaps(max(2, int(d * 6.5)), 6.5)

    def breath(self, d, inhale=True):            # bird hiss
        return hissn(self.s, d, 1800, 6000, IN_AMP if inhale else OUT_AMP)

    def tex(self, d, env="swell"):               # feathers ruffling, a soft beat or two
        n = secs(d)
        x = rustle(self.s, n, ctl(n, R(d, ENV[env])), 0.6) * (0.6 + 0.4 * np.abs(np.sin(np.pi * 5 * T(n))))
        return mix((pk(x), 0.7), (self.flaps(max(1, int(d * 3)), 3.0, 0.8), 0.5, d * 0.2))

    def hit(self, g=1.0):                        # talon rake
        out = buf(0.35)
        for j in range(2):
            place(out, pk(burst(self.s, 0.08, 2000, 8000, 0.02, 0.003)), 0.04 * j, 0.7)
        place(out, pk(thud(self.s, 140, 0.2, 0.04, grit=0.6)), 0.0, 0.8)
        return out * g

    def swish(self, d=0.25):                     # dive
        return pk(shaped(self.s, d, [(0, 2600), (0.7, 900), (1, 600)], [(0, 0.1), (0.75, 1), (1, 0)], 0.5, tone=0.25))

    def fall(self):
        return mix(pk(thud(self.s, 120, 0.3, 0.06, grit=0.5)), (pk(rustle(self.s, secs(0.4), ctl(secs(0.4), [(0, 1), (0.4, 0)]), 0.6)), 0.6),
                   (flap(self.s, 0.8), 0.4, 0.1))

    def custom(self, ev, a):
        if ev == "idle" and a == 2:              # preening: rustle, two beats, a soft chirr
            return mix((self.tex(0.6, "pulse"), 0.6), (self.flaps(2, 4.0, 0.9), 0.8, 0.15),
                       (self.v(0.25, [(0, 1100), (1, 1300)], "i", [(0, 0), (0.2, 1), (1, 0)], vib=(28, 0.05), rasp=0.3), 0.5, 0.65))
        if ev == "windup" and a == 1:            # hovering wing beats speeding up, shriek on top
            W = self.W + 0.05
            return mix(self.flaps(5, 5.5 / W), (self.call(0.3, "rise", 1.15), 0.9, W - 0.25))
        return None


class Centipede(Kit):
    """왕지네: no voice - chitin clicks and chitter, mandible clacks, spiracle hiss, many legs."""
    region, tempo = "forest", 0.85

    def call(self, d, shape="arch", k=1.0):      # chitter: tick rate follows the contour
        rates = [(t, 26 * k * m ** 2) for t, m in (SHAPE[shape] if isinstance(shape, str) else shape)]
        x = train(self.s, d, rates, lambda j, q: chitin(self.s, self.u(2400, 4600) * k), amp_of(shape), 0.3)
        return pk(mix(x, (hissn(self.s, d, 3000, 8000, amp_of(shape)), 0.15)))

    def bark(self, k=1.0):                       # mandible clack-clack
        out = buf(0.2)
        f = 1700 * k * self.p
        for j in range(2):
            place(out, pk(np.asarray(modal([f * (1 + 0.08 * j), f * 1.62, f * 2.5], [0.012, 0.008, 0.005], [1, 0.5, 0.3], 0.06, self.s.rng))
                          + click(self.s, 0.02, 2500, 10000, 0.0008)), 0.035 * j, 1.0 - 0.25 * j)
        return out

    def pain(self, d, shape="fall", k=1.0):      # hissing squeal through a chitter burst
        n = secs(d)
        sq = nsweep(self.s, n, ctl(n, R(d, fp(5200, shape, k))), 0.25) * ctl(n, R(d, amp_of(shape)))
        return pk(mix((pk(sq), 0.7), self.call(d, "fall", 1.5)))

    def breath(self, d, inhale=True):            # spiracles, pulsing
        return hissn(self.s, d, 1500, 5500, IN_AMP if inhale else OUT_AMP, am=(8, 0.6))

    def tex(self, d, env="swell"):               # legs pattering on leaf litter
        legs = train(self.s, d, [(0, 45), (1, 55)], lambda j, q: pk(click(self.s, 0.012, 1800, 8000, 0.0006)) * self.u(0.3, 1), ENV[env], 0.45)
        return mix(legs, (pk(rustle(self.s, secs(d), ctl(secs(d), R(d, ENV[env])), 0.3)), 0.25))

    def sig(self, d=0.4):                        # mandibles grinding
        return mix(train(self.s, d, [(0, 12), (1, 16)], lambda j, q: self.bark(self.u(0.9, 1.15)), ENV["swell"], 0.15),
                   (pk(scrape(self.s, d, 1200, 6000)), 0.3))

    def hit(self, g=1.0):                        # bite
        return mix(self.bark(0.85), (pk(thud(self.s, 160, 0.2, 0.04, grit=0.5)), 0.7)) * g

    def swish(self, d=0.25):                     # scuttling rush
        return mix(self.tex(d, "build"), (pk(shaped(self.s, d, [(0, 300), (1, 1200)], [(0, 0), (0.8, 1), (1, 0)], 0.7)), 0.4))

    def fall(self):                              # legs twitch slower and slower, flop
        tw = train(self.s, 0.9, [(0, 30), (1, 3)], lambda j, q: chitin(self.s, self.u(2200, 3800)), [(0, 1), (1, 0.2)], 0.4)
        return mix((tw, 0.8), (pk(thud(self.s, 150, 0.25, 0.05, grit=0.5)), 0.7))

    def custom(self, ev, a):
        if ev == "idle" and a == 0:              # long pattering scuttle with chitter on top
            return mix((self.tex(1.0, "swell"), 0.7), (self.call(0.5, "arch", 0.9), 0.8, 0.3))
        return None


class Werewolf(Kit):
    """늑대인간: deep throaty howl, roaring snarl, heavy panting, claws raking."""
    region, tempo = "forest", 1.0
    VOX = dict(scale=0.86, tilt=1.0, breath=0.25, rasp=0.5, sharp=3.0, rlo=300, rhi=6000, sub=0.35, flutter=0.5, fmax=6000)

    def call(self, d, shape="arch", k=1.0):
        if d >= 0.55 and shape in ("rise", "arch", "step"):     # howl over a growl
            x = self.v(d, fp(300 * self.p, shape, k), [(0, "u"), (0.3, "o"), (0.75, "a"), (1, "u")], [(0, 0), (0.1, 0.8), (0.65, 1), (1, 0)],
                       breath=0.3, rasp=0.22, sub=0.1, flutter=0.15, vib=(5, 0.014))
            g = self.v(d, fp(92 * self.p, "flat"), "o", [(0, 0), (0.2, 0.6), (1, 0)], rasp=0.6, sharp=2)
            return pk(x + g * 0.3)
        return self.v(d, fp(118 * self.p, shape, k), [(0, "eu"), (0.3, "a"), (1, "o")], amp_of(shape), rasp=0.75)

    def bark(self, k=1.0):                       # "RAH"
        f = 150 * k * self.p
        return self.v(0.18, [(0, f), (0.2, f * 1.43), (1, f * 0.8)], [(0, "eu"), (0.2, "a"), (1, "o")], [(0, 0), (0.06, 1), (0.5, 0.7), (1, 0)], rasp=0.7, sub=0.3)

    def pain(self, d, shape="fall", k=1.0):      # yelp breaking into a growl
        return self.v(d, fp(470 * self.p, shape, k), [(0, "a"), (0.5, "o"), (1, "u")], amp_of(shape), rasp=0.4, sub=0.1, scale=0.95)

    def breath(self, d, inhale=True):            # heavy panting
        out = buf(d + 0.15)
        m = max(2, int(d / 0.16))
        for j in range(m):
            place(out, pk(breathy(self.s, 0.12, [(0, 700), (0.12, 1300)] if inhale else [(0, 1100), (0.12, 800)], [(0, 0), (0.02, 1), (0.12, 0)], 0.7)), j * d / m, 0.8)
        return out

    def tex(self, d, env="swell"):               # rolling low growl
        return self.v(d, [(0, 74 * self.p), (0.5, 80 * self.p), (1, 70 * self.p)], "o", ENV[env], rasp=0.7, sharp=2.0, flutter=0.85, breath=0.35, fmax=3500)

    def sig(self, d=0.4):                        # claws on bark under a snarl
        return mix((pk(scrape(self.s, d, 400, 4000)), 0.6),
                   (self.v(d * 0.8, [(0, 130 * self.p), (1, 165 * self.p)], [(0, "e"), (1, "ae")], [(0, 0), (0.3, 1), (1, 0)], rasp=0.9, sharp=3.5), 0.9, 0.05))

    def hit(self, g=1.0):                        # claw rip + body
        return mix((tear(self.s, 0.25), 0.8), pk(thud(self.s, 95, 0.25, 0.05, grit=0.7))) * g

    def swish(self, d=0.2):
        return pk(shaped(self.s, d, [(0, 500), (0.6, 1800), (1, 700)], [(0, 0), (0.6, 1), (1, 0)], 0.6, body=0.4))

    def fall(self):
        return mix(pk(thud(self.s, 72, 0.45, 0.1, body=1.2, grit=0.6)), (pk(breathy(self.s, 0.5, [(0, 900), (0.5, 500)], [(0, 0), (0.05, 1), (0.5, 0)], 0.7)), 0.4, 0.1))


class Troll(Kit):
    """트롤: slow dumb grunts ("hurr", "huh"), snot snorts, belly rumbles, a wooden club."""
    region, tempo = "forest", 1.12
    VOX = dict(scale=0.72, tilt=0.85, breath=0.28, rasp=0.35, sharp=2.0, rlo=150, rhi=3000, sub=0.6, flutter=0.45, fmax=3600, bw=1.2)

    def call(self, d, shape="arch", k=1.0):      # "huurrr"
        return self.v(d, fp(86 * self.p, shape, k), [(0, "eo"), (0.35, "o"), (1, "u")], amp_of(shape))

    def bark(self, k=1.0):                       # "HUH!"
        f = 98 * k * self.p
        return self.v(0.17, [(0, f), (0.3, f * 1.22), (1, f * 0.84)], [(0, "a"), (1, "u")], [(0, 0), (0.04, 1), (0.5, 0.75), (1, 0)], breath=0.4)

    def pain(self, d, shape="fall", k=1.0):      # "oof-ohh"
        return self.v(d, fp(130 * self.p, shape, k), [(0, "u"), (0.15, "o"), (1, "u")], amp_of(shape), breath=0.45, rasp=0.45)

    def breath(self, d, inhale=True):            # wet snort
        f = [(0, 500), (1, 1300)] if inhale else [(0, 1200), (1, 450)]
        x = pk(breathy(self.s, d, R(d, f), R(d, IN_AMP if inhale else OUT_AMP), 0.8)
               + snarl(self.s, d, [(0, 45), (d, 40)], "u", [(0, 0), (0.5 * d, 0.6), (d, 0)], 1.0, 6, 200, 2500) * 0.5)
        return mix(x, (pk(bloop(self.s, 260, 140, 0.08, 0.6)), 0.3, d * (0.85 if inhale else 0.1)))

    def tex(self, d, env="swell"):               # belly rumble + a lazy "mmm"
        n = secs(d)
        g = pk((glide(n, 48 + 6 * np.sin(2 * np.pi * 1.3 * T(n))) * 0.5 + norm(band(self.s.noise(n), 50, 260)) * 0.6) * ctl(n, R(d, ENV[env])))
        return mix((g, 0.8), (self.v(min(0.4, d * 0.5), [(0, 70 * self.p), (1, 64 * self.p)], "m", [(0, 0), (0.3, 1), (1, 0)], rasp=0.2), 0.6, d * 0.35))

    def sig(self, d=0.4):                        # club dragged, knocked on the ground
        return mix((pk(scrape(self.s, d, 150, 1600)), 0.7), (woodk(self.s, self.u(180, 230), 0.04), 0.9, d * 0.85))

    def hit(self, g=1.0):                        # club thump
        return mix(pk(thud(self.s, 68, 0.4, 0.09, body=1.2, grit=0.7)), (woodk(self.s, self.u(150, 190), 0.035), 0.6),
                   (pk(rustle(self.s, secs(0.3), ctl(secs(0.3), [(0, 1), (0.3, 0)]), 0.4)), 0.25, 0.01)) * g

    def swish(self, d=0.3):
        return pk(shaped(self.s, d, [(0, 200), (0.6, 700), (1, 250)], [(0, 0), (0.6, 1), (1, 0)], 0.8, body=0.8))

    def fall(self):
        return mix(pk(thud(self.s, 55, 0.6, 0.14, drop=0.5, body=1.4, grit=0.8)), (pk(rustle(self.s, secs(0.5), ctl(secs(0.5), [(0, 1), (0.5, 0)]), 0.5)), 0.4, 0.02),
                   (pk(crackle(self.s, 0.4, 40, 900, 5000)), 0.3, 0.03))


class Cyclops(Kit):
    """사이클롭스: a huge open bellow with a roaring overtone, chest pounding, ground-shaking slams."""
    region, tempo = "forest", 1.2
    VOX = dict(scale=0.6, tilt=0.75, breath=0.3, rasp=0.55, sharp=3.0, rlo=150, rhi=4000, sub=0.7, flutter=0.5, fmax=3800, bw=1.35)

    def call(self, d, shape="arch", k=1.0):      # bellow + roar partial an octave up
        lo = self.v(d, fp(68 * self.p, shape, k), [(0, "o"), (0.25, "a"), (1, "o")], amp_of(shape))
        hi = self.v(d, fp(137 * self.p, shape, k), "a", amp_of(shape), rasp=0.85, scale=0.7, sub=0.0)
        return pk(lo + hi * 0.35)

    def bark(self, k=1.0):                       # "BWAH" with the roaring overtone
        f = 74 * k * self.p
        pts = [(0, f), (0.2, f * 1.3), (1, f * 0.82)]
        amp = [(0, 0), (0.05, 1), (0.5, 0.8), (1, 0)]
        lo = self.v(0.24, pts, [(0, "o"), (0.2, "a"), (1, "o")], amp, rasp=0.75)
        hi = self.v(0.24, [(t, v * 1.85) for t, v in pts], "ae", amp, rasp=0.9, scale=0.75, sub=0.0)
        return pk(lo + hi * 0.45)

    def pain(self, d, shape="fall", k=1.0):
        return self.v(d, fp(112 * self.p, shape, k), [(0, "a"), (1, "o")], amp_of(shape), rasp=0.85)

    def breath(self, d, inhale=True):            # giant nostrils
        f = [(0, 250), (1, 800)] if inhale else [(0, 700), (1, 260)]
        return pk(breathy(self.s, d, R(d, f), R(d, IN_AMP if inhale else OUT_AMP), 0.9))

    def tex(self, d, env="swell"):               # chest rumble and a deep hum
        return mix((rumble(self.s, d, 35, 180, ENV[env]), 0.8), (self.v(d * 0.7, [(0, 55), (1, 52)], "m", [(0, 0), (0.4, 1), (1, 0)], rasp=0.15), 0.5, d * 0.2))

    def sig(self, d=0.4):                        # pounds its chest twice
        return mix(pk(thud(self.s, 62, 0.35, 0.07, grit=0.5)), (pk(thud(self.s, 58, 0.35, 0.07, grit=0.5)), 0.85, min(0.22, d * 0.55)))

    def hit(self, g=1.0):                        # fist into the ground
        return mix(boom(self.s, 44, 0.7, 0.16), (debris(self.s, secs(0.6), 10, 0.02, 0.4, (0.4, 1.0), 0.6), 0.6), (rumble(self.s, 0.6, 30, 200, ENV["fade"]), 0.5)) * g

    def swish(self, d=0.32):
        return pk(shaped(self.s, d, [(0, 160), (0.6, 520), (1, 200)], [(0, 0), (0.6, 1), (1, 0)], 0.9, body=1.0))

    def custom(self, ev, a):
        if ev == "hurt" and a == 1:              # a hit thuds into the huge chest, a roaring "RAAH"
            return mix(pk(thud(self.s, 70, 0.3, 0.06, grit=0.7)), (self.pain(0.32, "arch", 1.1), 1.0, 0.05))
        return None

    def fall(self):
        return mix(boom(self.s, 40, 0.9, 0.2), (rumble(self.s, 0.9, 30, 220, ENV["fade"]), 0.6), (debris(self.s, secs(0.8), 14, 0.05, 0.6, (0.4, 1.1), 0.5), 0.5),
                   (pk(rustle(self.s, secs(0.6), ctl(secs(0.6), [(0, 1), (0.6, 0)]), 0.4)), 0.3))


class Treant(Kit):
    """고목 트렌트 (boss): creaking wooden groans, branches cracking, rushing leaves, root rumble."""
    region, tempo, room = "forest", 1.25, 1.2
    VOX = dict(scale=0.55, tilt=0.8, breath=0.4, rasp=0.2, sharp=2.0, rlo=100, rhi=2000, sub=0.6, flutter=0.4, fmax=3000, bw=1.4)

    def call(self, d, shape="arch", k=1.0):      # a creak-groan: wood pulses through a trunk plus a hollow voice
        sh = SHAPE[shape] if isinstance(shape, str) else shape
        cr = creak(self.s, d, 42 * k * sh[0][1] * self.p, 42 * k * sh[-1][1] * self.p, body=(85, 190, 380, 720, 1300), q=6.5, rough=0.3, wobble=3.0)
        g = self.v(d, fp(46 * self.p, shape, k), [(0, "o"), (1, "u")], amp_of(shape))
        n = secs(d)
        lv = pk(rustle(self.s, n, ctl(n, R(d, amp_of(shape))) * 0.6, 0.4))
        return mix((cr, 0.75), (g, 0.7), (lv, 0.2))

    def crack(self, g=1.0):                      # a branch snapping
        f = self.u(800, 1000)
        return mix(pk(click(self.s, 0.05, 1500, 9000, 0.003)), (pk(np.asarray(modal([f, f * 1.62, f * 2.6], [0.03, 0.02, 0.012], [1, 0.6, 0.3], 0.15, self.s.rng))), 0.8),
                   (pk(crackle(self.s, 0.25, 60, 900, 6000)), 0.5, 0.01)) * g

    def bark(self, k=1.0):
        return mix(self.crack(), (creak(self.s, 0.25, 70 * k, 52 * k, body=(110, 260, 560, 1100), q=6), 0.7, 0.03))

    def pain(self, d, shape="fall", k=1.0):
        return mix((self.crack(), 0.8), (self.call(d, shape, k * 1.5), 1.0, 0.03))

    def breath(self, d, inhale=True):            # wind through the crown
        n = secs(d)
        e = ctl(n, R(d, IN_AMP if inhale else OUT_AMP))
        return pk(mix(pk(rustle(self.s, n, e, 0.8)), (pk(np.asarray(V.wind(self.s, d, 250, 1200, d * 0.4, d * 0.5))), 0.5)))

    def tex(self, d, env="swell"):               # leaves, twigs, small creaks
        n = secs(d)
        e = ctl(n, R(d, ENV[env]))
        return mix((pk(rustle(self.s, n, e, 0.7)), 0.7), (crackle(self.s, d, 25, 900, 5000, ENV[env], (0.002, 0.005)), 0.6),
                   (creak(self.s, d * 0.5, 60, 48, body=(120, 300, 650), q=6), 0.35, d * 0.3))

    def sig(self, d=0.4):                        # crown shaking: leaf rush + sway creak
        n = secs(d + 0.2)
        return mix((pk(rustle(self.s, n, ctl(n, [(0, 0), (0.15, 1), (d + 0.2, 0)]), 1.0)), 1.0), (creak(self.s, d, 55, 38, body=(90, 210, 440, 900), q=7), 0.6))

    def hit(self, g=1.0):                        # a trunk-arm slam
        return mix(boom(self.s, 48, 0.8, 0.18), (woodk(self.s, 120, 0.06), 0.6), (crackle(self.s, 0.5, 70, 900, 6000), 0.5),
                   (pk(rustle(self.s, secs(0.6), ctl(secs(0.6), [(0, 1), (0.6, 0)]), 0.8)), 0.4)) * g

    def swish(self, d=0.35):                     # a leafy branch sweeping
        n = secs(d)
        return mix(pk(shaped(self.s, d, [(0, 200), (0.6, 700), (1, 260)], [(0, 0), (0.6, 1), (1, 0)], 0.9, body=0.7)),
                   (pk(rustle(self.s, n, ctl(n, R(d, [(0, 0), (0.6, 1), (1, 0)])), 0.8)), 0.6))

    def fall(self):                              # topples: long creak, crash, leaves raining down
        return mix((creak(self.s, 0.6, 50, 30, body=(85, 190, 380, 720), q=7), 0.7), (boom(self.s, 38, 0.9, 0.22), 1.0, 0.45),
                   (self.crack(0.8), 0.7, 0.45), (pk(rustle(self.s, secs(0.9), ctl(secs(0.9), [(0, 1), (0.9, 0)]), 0.7)), 0.5, 0.5))

    def roar(self, a):
        if a == 0:      # rising groan, leaf storm crescendo, cracks
            d = 2.3
            out = mix((self.call(d, [(0, 0.8), (0.7, 1.25), (1, 1.05)], 1.0), 1.0), (self.sig(d - 0.2), 0.6, 0.1), (rumble(self.s, d, 30, 220, [(0, 0), (0.7, 1), (1, 0)]), 0.6))
            for at in (0.9, 1.4, 1.7):
                place(out, self.crack(0.6), at, 0.5)
            return out
        if a == 1:      # two-part groan split by a big crack
            return mix((self.call(1.0, "arch", 0.95), 1.0), (self.crack(1.2), 0.9, 0.95), (self.call(1.2, "fall", 1.15), 1.0, 1.05),
                       (self.tex(2.2, "swell"), 0.4))
        if a == 2:      # deep falling groan over a root rumble
            return mix((rumble(self.s, 2.6, 25, 160, [(0, 0), (0.2, 1), (1, 0)]), 0.8), (self.call(2.2, "fall", 0.85), 1.0, 0.15),
                       (crackle(self.s, 2.4, 20, 600, 4000, ENV["swell"], (0.002, 0.006)), 0.6))
        # hollow trunk howl: the groan through a long wooden resonance, creaks around it
        d = 2.0
        g = self.v(d, fp(52 * self.p, "step"), [(0, "u"), (0.4, "o"), (1, "u")], AMP["step"], breath=0.5)
        holl = pk(L.resonate(g, SR, [95, 210, 330], [0.25, 0.18, 0.12], [1, 0.6, 0.4]))
        return mix((holl, 0.8), (g, 0.5), (creak(self.s, d, 40, 62, body=(85, 190, 380, 720, 1300), q=7, rough=0.35), 0.6), (self.sig(0.8), 0.5, 1.2))

    def intro(self, a):
        # ground rumble swelling, roots cracking, then the signature creak-groan and a final crack
        lead = [1.2, 0.9, 1.4][a]
        out = mix((rumble(self.s, lead + 0.6, 25, 200, [(0, 0), (0.75, 1), (1, 0)]), 0.9),
                  (crackle(self.s, lead, [30, 60, 20][a], 500, 4000, ENV["build"], (0.002, 0.006)), 0.7))
        place(out, self.sig(0.6), lead - 0.4, 0.7)
        place(out, self.call([1.3, 1.6, 1.2][a], ["rise", "arch", "dip"][a], 1.0), lead, 1.0)
        place(out, self.crack(1.0), lead + [1.3, 1.6, 1.15][a], 0.8)
        return out


# =============================================================================== quarry (노을 채석장)
class Skeleton(Kit):
    """해골 병사: no lungs - bone rattle, jaw clacks, a dry hollow hiss, a rusty blade."""
    region, tempo = "quarry", 0.95

    def call(self, d, shape="arch", k=1.0):      # jaw chatter rattling at the contour's rate + dry "haaa"
        pts = SHAPE[shape] if isinstance(shape, str) else shape
        ch = train(self.s, d, [(t, 19 * k * m ** 2) for t, m in pts], lambda j, q: bone(self.s, self.u(900, 1500) * k, 0.012), amp_of(shape), 0.15)
        return mix((ch, 1.0), (whisper(self.s, d, [(0, "a"), (1, "o")], amp_of(shape), 1.05, 0.25, 0.4), 0.35))

    def bark(self, k=1.0):                       # jaw clack-clack
        f = 1250 * k * self.p
        return mix(bone(self.s, f, 0.014), (bone(self.s, f * 0.9, 0.014), 0.8, 0.045), (pk(click(self.s, 0.015, 3000, 10000, 0.0006)), 0.3, 0.046))

    def pain(self, d, shape="fall", k=1.0):      # a bone cracks, the frame rattles
        return mix((pk(click(self.s, 0.04, 2000, 10000, 0.002)), 0.9), (bone(self.s, 2300, 0.02), 0.8),
                   (self.tex(d, "burst"), 0.8, 0.02), (whisper(self.s, d * 0.8, "a", OUT_AMP, 1.1), 0.25, 0.03))

    def breath(self, d, inhale=True):            # a hollow dry hiss through the ribs
        return whisper(self.s, d, [(0, "o"), (1, "a")] if inhale else [(0, "a"), (1, "u")], IN_AMP if inhale else OUT_AMP, 1.0, 0.3, 0.5)

    def tex(self, d, env="swell"):               # loose bones rattling
        return train(self.s, d, [(0, 34), (0.5, 48), (1, 30)], lambda j, q: bone(self.s, self.u(1500, 3000), 0.006), ENV[env], 0.5, (0.3, 1.0))

    def sig(self, d=0.4):                        # a full-body shake
        return mix((self.tex(d, "burst"), 1.0), (self.bark(0.9), 0.8, d * 0.6))

    def hit(self, g=1.0):                        # rusty blade, bony arm
        return mix(metal(self.s, self.u(650, 760), 0.06, 0.6), (bone(self.s, 1100, 0.012), 0.7), (pk(thud(self.s, 130, 0.2, 0.04, grit=0.6)), 0.5)) * g

    def swish(self, d=0.18):
        return pk(shaped(self.s, d, [(0, 800), (0.6, 2800), (1, 1100)], [(0, 0), (0.6, 1), (1, 0)], 0.42, tone=0.12))

    def fall(self):                              # collapses into a bone pile, the skull rolls
        pile = train(self.s, 0.7, [(0, 70), (1, 12)], lambda j, q: bone(self.s, self.u(700, 2600), 0.01), [(0, 1), (1, 0.2)], 0.5, (0.3, 1.0))
        out = mix((pile, 1.0), (pk(burst(self.s, 0.3, 300, 3000, 0.08)), 0.3))
        for j, at in enumerate((0.55, 0.72, 0.83)):
            place(out, bone(self.s, 620, 0.02), at, 0.7 - 0.2 * j)
        return out


class Imp(Kit):
    """임프: squeaky mischievous giggle, fire hiss and sizzle, a tiny wing buzz."""
    region, tempo = "quarry", 0.88
    VOX = dict(scale=1.55, tilt=1.0, breath=0.3, rasp=0.25, sharp=3.0, rlo=1200, rhi=9000, fmax=10000, vib=(9, 0.03))

    def call(self, d, shape="arch", k=1.0):      # "nyiii"
        return self.v(d, fp(800 * self.p, shape, k), [(0, "n"), (0.2, "i"), (1, "e")], amp_of(shape))

    def bark(self, k=1.0):                       # "hih!"
        f = 950 * k * self.p
        return self.v(0.08, [(0, f), (1, f * 1.16)], "i", [(0, 0), (0.15, 1), (1, 0)], breath=0.35, vib=(0, 0))

    def pain(self, d, shape="fall", k=1.0):      # "eek" + sizzle
        return mix(self.v(d, fp(1300 * self.p, shape, k), [(0, "i"), (1, "e")], amp_of(shape), rasp=0.5), (self.breath(d, False), 0.4))

    def giggle(self, n=6, rate=12.0, f=820):
        out = buf(n / rate + 0.2)
        for j in range(n):
            ff = f * self.p * (1.0 + 0.12 * ((j % 2) * 2 - 1) + 0.04 * j)
            at = j / rate * self.u(0.94, 1.06)
            place(out, pk(breathy(self.s, 0.025, [(0, 4000), (0.025, 5000)], [(0, 0), (0.006, 1), (0.025, 0)], 0.5)), at, 0.3)
            place(out, self.v(0.05, [(0, ff), (1, ff * 1.08)], [(0, "i"), (1, "e")], [(0, 0), (0.2, 1), (1, 0)], breath=0.4, vib=(0, 0)), at + 0.01)
        return out

    def sig(self, d=0.4):
        return self.giggle(max(3, int(d * 13)), 13.0)

    def breath(self, d, inhale=True):            # fire sizzle
        return mix(hissn(self.s, d, 3500, 10000, IN_AMP if inhale else OUT_AMP), (crackle(self.s, d, 70, 1500, 8000, IN_AMP if inhale else OUT_AMP), 1.2))

    def tex(self, d, env="swell"):               # tiny wings buzzing, embers popping
        n = secs(d)
        w = pk(shaped(self.s, d, [(0, 1100), (0.5, 1500), (1, 1000)], ENV[env], 0.5, (22, 0.85)))
        return mix((w, 0.8), (crackle(self.s, d, 40, 1500, 7000, ENV[env]), 0.9))

    def hit(self, g=1.0):                        # a fire spit that pops
        return mix(sweep(self.s, 0.22, [(0, 3500), (1, 900)], [(0, 0), (0.05, 1), (1, 0)], 0.5), (pk(click(self.s, 0.04, 900, 6000, 0.004)), 0.8),
                   (crackle(self.s, 0.3, 90, 1500, 8000), 1.0)) * g

    def swish(self, d=0.2):
        return sweep(self.s, d, [(0, 800), (1, 3500)], [(0, 0), (0.7, 1), (1, 0)], 0.5)

    def fall(self):                              # pops and fizzles out
        return mix(pk(click(self.s, 0.05, 700, 5000, 0.005)), (self.breath(0.6, False), 0.6, 0.02), (pk(thud(self.s, 170, 0.12, 0.025, grit=0.3)), 0.4))

    def custom(self, ev, a):
        if ev == "alert" and a == 1:             # giggle bursts out, then a mocking "nyiii"
            return mix(self.giggle(8, 12.0, 900), (self.call(0.35, "dip", 1.1), 0.9, 0.72))
        return None


class Lizardman(Kit):
    """리자드맨: sibilant hiss, tongue flicks, a gravelly throat croak, scales and a spear."""
    region, tempo = "quarry", 0.95
    VOX = dict(scale=0.95, tilt=0.5, breath=0.35, rasp=0.6, sharp=6.0, rlo=200, rhi=3000, flutter=0.6, fmax=4500)

    def croak(self, d, f=38, shape="flat", k=1.0, vow="a"):    # vocal fry
        return self.v(d, fp(f * self.p, shape, k), vow, amp_of(shape), jitter=0.05)

    def call(self, d, shape="arch", k=1.0):      # hiss with the croak under it
        n = secs(d)
        hs = pk(nsweep(self.s, n, ctl(n, R(d, fp(4300, shape, k))), 0.55) * ctl(n, R(d, amp_of(shape))))
        return mix((hs, 0.55), (self.croak(d, 40, shape, k, [(0, "a"), (1, "o")]), 1.0))

    def bark(self, k=1.0):                       # "KHAK"
        return mix(hissn(self.s, 0.1, 2500, 8000, [(0, 0), (0.05, 1), (1, 0)]), (self.croak(0.13, 46, "fall", k, "a"), 0.9, 0.02))

    def flick(self):                             # tongue: tk-tk + a wet smack
        out = buf(0.15)
        for j in range(2):
            place(out, pk(click(self.s, 0.01, 4000, 11000, 0.0004)), 0.03 * j, 0.8)
        place(out, pk(bloop(self.s, 900, 1500, 0.04, 0.5)), 0.065, 0.4)
        return out

    def pain(self, d, shape="fall", k=1.0):      # hissing screech
        return mix(self.v(d, fp(620 * self.p, shape, k), "ae", amp_of(shape), rasp=0.8, sharp=4, tilt=1.0, breath=0.3, jitter=0.01, rlo=600, rhi=8000),
                   (hissn(self.s, d, 3000, 9000, amp_of(shape)), 0.5))

    def breath(self, d, inhale=True):
        return sweep(self.s, d, [(0, 1500), (1, 6000)] if inhale else [(0, 6000), (1, 2000)], IN_AMP if inhale else OUT_AMP, 0.6)

    def tex(self, d, env="swell"):               # throat clicks
        return train(self.s, d, [(0, 9), (1, 13)], lambda j, q: mix(pk(click(self.s, 0.02, 900, 3000, 0.002)), (pk(np.asarray(modal([700], [0.02], [1], 0.05, self.s.rng))), 0.5)),
                     ENV[env], 0.3)

    def sig(self, d=0.4):
        out = buf(d + 0.2)
        for at in np.arange(0, d, 0.16):
            place(out, self.flick(), at, 0.8)
        return out

    def hit(self, g=1.0):                        # claw / spear + scales scraping
        return mix(pk(thud(self.s, 110, 0.25, 0.05, grit=0.7)), (pk(scrape(self.s, 0.15, 600, 5000)), 0.5), (tear(self.s, 0.12, 1500, 6000), 0.4)) * g

    def swish(self, d=0.2):
        return pk(shaped(self.s, d, [(0, 600), (0.6, 2200), (1, 900)], [(0, 0), (0.6, 1), (1, 0)], 0.5))

    def fall(self):
        return mix(pk(thud(self.s, 95, 0.4, 0.08, grit=0.6)), (hissn(self.s, 0.6, 2500, 7000, OUT_AMP), 0.4), (pk(scrape(self.s, 0.3, 300, 3000)), 0.4, 0.05))

    def custom(self, ev, a):
        if ev == "idle" and a == 2:              # flick-flick, a low croak, flick
            return mix(self.flick(), (self.flick(), 0.8, 0.22), (self.croak(0.45, 34, "dip"), 0.8, 0.38), (self.flick(), 0.7, 0.9))
        return None


class Mimic(Kit):
    """미믹: a hungry chest - lid clacks, hinge creaks, a muffled growl inside, gulps, coins."""
    region, tempo = "quarry", 0.95

    def growl(self, d, shape="arch", k=1.0):     # muffled inside the box
        g = voc(self.s, d, fp(92 * self.p, shape, k), "o", amp_of(shape), scale=0.9, rasp=0.5, sharp=2.5, sub=0.4, flutter=0.5, fmax=3000)
        return pk(L.resonate(low(g, 1100), SR, [230, 480, 900], [0.03, 0.02, 0.015], [1, 0.7, 0.4]) * 0.7 + low(g, 900))

    def call(self, d, shape="arch", k=1.0):      # hinge creak + the growl inside
        sh = SHAPE[shape] if isinstance(shape, str) else shape
        cr = creak(self.s, d, 170 * k * sh[0][1], 260 * k * sh[-1][1], body=(300, 700, 1500, 2600), q=8, rough=0.25, wobble=5, metal_=True)
        return mix((cr, 0.7), (self.growl(d, shape, k), 0.8))

    def clack(self, k=1.0):                      # the lid snapping shut
        f = 210 * k * self.p
        return mix(woodk(self.s, f, 0.04), (woodk(self.s, f * 1.48, 0.025), 0.7, 0.004), (pk(click(self.s, 0.02, 1500, 7000, 0.0015)), 0.6))

    def bark(self, k=1.0):
        return self.clack(k)

    def gulp(self):
        return mix(pk(bloop(self.s, 240, 85, 0.2, 0.5)), (pk(glide(secs(0.18), np.linspace(140, 70, secs(0.18))) * np.hanning(secs(0.18))), 0.6, 0.03))

    def pain(self, d, shape="fall", k=1.0):      # wood cracks, coins rattle, a muffled yelp
        return mix(pk(rock(self.s, 0.9)), (self.coins(d), 0.6, 0.02), (self.growl(d, shape, k * 2.2), 0.7, 0.03))

    def coins(self, d, dens=40):
        return pk(tinkles(self.s, secs(d), dens, 2800, 8000, ctl(secs(d), R(d, ENV["fade"])), (0.02, 0.06)))

    def breath(self, d, inhale=True):            # a long wet gulp / a sigh through the lid gap
        if inhale:
            return mix((sweep(self.s, d, [(0, 600), (1, 1400)], IN_AMP, 0.7), 0.5), (self.gulp(), 1.0, max(0.0, d - 0.2)))
        return mix(self.gulp(), (sweep(self.s, d, [(0, 1200), (1, 500)], OUT_AMP, 0.7), 0.4, 0.1))

    def tex(self, d, env="swell"):               # lid chattering, coins jingling
        ch = train(self.s, d, [(0, 10), (1, 14)], lambda j, q: woodk(self.s, self.u(240, 300), 0.012), ENV[env], 0.3)
        return mix((ch, 0.8), (self.coins(d, 50), 0.5))

    def sig(self, d=0.4):                        # chomp-chomp and a gulp
        return mix(self.clack(), (self.clack(1.1), 0.8, min(0.16, d * 0.4)), (self.gulp(), 0.7, min(0.3, d * 0.7)))

    def hit(self, g=1.0):                        # CHOMP: a big lid slam with teeth
        return mix(woodk(self.s, 160, 0.05), (pk(thud(self.s, 90, 0.3, 0.06, grit=0.6)), 0.8), (bone(self.s, 2000, 0.008), 0.5, 0.003)) * g

    def swish(self, d=0.2):                      # a hop: wood scrapes the floor
        return mix(pk(scrape(self.s, d, 200, 2500)), (pk(shaped(self.s, d, [(0, 300), (1, 900)], [(0, 0), (0.8, 1), (1, 0)], 0.7)), 0.5))

    def fall(self):                              # the lid falls open, coins spill, wood clatters
        return mix((creak(self.s, 0.45, 260, 150, body=(300, 700, 1500, 2600), q=8, metal_=True), 0.6), (woodk(self.s, 180, 0.05), 0.9, 0.42),
                   (self.coins(0.8, 120), 0.8, 0.45), (woodk(self.s, 260, 0.02), 0.5, 0.6))


class Basilisk(Kit):
    """바실리스크: a big dark serpent hiss, stone grinding and crackling (petrify), jaw snaps."""
    region, tempo = "quarry", 1.05
    VOX = dict(scale=0.85, tilt=0.5, breath=0.4, rasp=0.6, sharp=6.0, rlo=150, rhi=2500, flutter=0.5, fmax=3500)

    def call(self, d, shape="arch", k=1.0):      # deep hiss + rattling throat
        n = secs(d)
        hs = pk(nsweep(self.s, n, ctl(n, R(d, fp(2400, shape, k))), 0.9) * ctl(n, R(d, amp_of(shape))))
        th = hissn(self.s, d, 700, 2200, amp_of(shape))
        fry = self.v(d, fp(30 * self.p, shape, k), [(0, "o"), (1, "a")], amp_of(shape), jitter=0.06)
        return mix((hs, 0.7), (th, 0.45), (fry, 0.9))

    def snap(self, k=1.0):                       # heavy jaw snap
        f = 880 * k * self.p
        return mix(pk(np.asarray(modal([f, f * 1.7, f * 2.6], [0.02, 0.012, 0.008], [1, 0.6, 0.3], 0.1, self.s.rng))), (pk(click(self.s, 0.03, 1500, 8000, 0.002)), 0.8))

    def bark(self, k=1.0):
        return mix(self.snap(k), (hissn(self.s, 0.18, 1500, 5000, OUT_AMP), 0.6, 0.02))

    def pain(self, d, shape="fall", k=1.0):      # hiss-squeal, stone chips
        return mix(sweep(self.s, d, fp(3500, "rise" if shape == "fall" else shape, k), amp_of(shape), 0.3), (pk(rock(self.s, 0.8)), 0.6), (pk(rock(self.s, 0.6)), 0.4, 0.06))

    def breath(self, d, inhale=True):
        return sweep(self.s, d, [(0, 900), (1, 2400)] if inhale else [(0, 2400), (1, 800)], IN_AMP if inhale else OUT_AMP, 0.8)

    def tex(self, d, env="swell"):               # stone grinding, gravel
        return mix((grind(self.s, d, 60, 500, ENV[env], 70), 0.9), (debris(self.s, secs(d), 6, 0.1, d * 0.8, (0.3, 0.6), 0.4), 0.6))

    def sig(self, d=0.4):                        # the petrifying gaze: stone crackling, a thin whine
        n = secs(d)
        whine = pk(glide(n, ctl(n, [(0, 2100), (d, 2900)])) * ctl(n, R(d, [(0, 0), (0.7, 1), (1, 0)])))
        return mix((crackle(self.s, d, 220, 400, 2600, [(0, 0.2), (0.8, 1), (1, 0)], (0.002, 0.005)), 1.0), (whine, 0.15), (pk(rock(self.s, 1.2)), 0.6, d * 0.8))

    def hit(self, g=1.0):                        # lunge bite, stone cracks
        return mix(self.snap(0.9), (pk(thud(self.s, 90, 0.3, 0.06, grit=0.7)), 0.8), (pk(rock(self.s, 1.0)), 0.6, 0.01)) * g

    def swish(self, d=0.25):                     # slithering rush
        n = secs(d)
        return pk(band(self.s.noise(n), 300, 3000) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 9 * T(n)))) * ctl(n, R(d, [(0, 0), (0.7, 1), (1, 0)])))

    def fall(self):                              # deflates, the stone skin crumbles
        return mix((sweep(self.s, 0.9, [(0, 2200), (1, 700)], OUT_AMP, 0.8), 0.7), (debris(self.s, secs(0.9), 14, 0.1, 0.7, (0.3, 0.8), 0.6), 0.8),
                   (pk(thud(self.s, 85, 0.35, 0.08, grit=0.6)), 0.6, 0.1))


class Naga(Kit):
    """나가: a serpent woman - sibilant breathy "sssaah", a rattlesnake buzz, coils slithering."""
    region, tempo = "quarry", 1.0
    VOX = dict(scale=1.1, tilt=1.1, breath=0.55, rasp=0.3, sharp=3.0, rlo=800, rhi=7000, fmax=7500, vib=(5.5, 0.02))

    def call(self, d, shape="arch", k=1.0):      # "sssaaah": a hiss opening into a breathy vowel
        hs = hissn(self.s, d * 0.45, 4000, 10000, [(0, 0), (0.3, 1), (0.85, 0.8), (1, 0)])
        vo = self.v(d * 0.75, fp(270 * self.p, shape, k), [(0, "e"), (1, "a")], amp_of(shape))
        return mix((hs, 0.8), (vo, 1.0, d * 0.25), (hissn(self.s, d * 0.75, 5000, 10000, amp_of(shape)), 0.3, d * 0.25))

    def bark(self, k=1.0):                       # "tss!"
        return mix(hissn(self.s, 0.12, 4500, 10000, [(0, 0), (0.1, 1), (1, 0)]), (self.v(0.09, [(0, 330 * k), (1, 290 * k)], "e", [(0, 0), (0.2, 1), (1, 0)]), 0.6, 0.05))

    def rattle(self, d, rate=48, env="swell"):
        return buzz(self.s, d, rate if not isinstance(rate, list) else rate, 4000, 10000, ENV[env] if isinstance(env, str) else env, 5.0)

    def pain(self, d, shape="fall", k=1.0):      # shrill hissing shriek
        return mix(self.v(d, fp(720 * self.p, shape, k), "i", amp_of(shape), rasp=0.5, breath=0.5), (hissn(self.s, d, 4000, 10000, amp_of(shape)), 0.5))

    def breath(self, d, inhale=True):
        return hissn(self.s, d, 4000, 10000, IN_AMP if inhale else OUT_AMP)

    def tex(self, d, env="swell"):               # coils slithering over stone
        n = secs(d)
        return pk(band(self.s.noise(n), 600, 3500) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 3.5 * T(n) + u(self.s, 0, 3)))) * ctl(n, R(d, ENV[env]))
                  + pops(self.s, n, 40, 1000, 5000, ctl(n, R(d, ENV[env])), (0.001, 0.003)) * 0.6)

    def sig(self, d=0.4):
        return self.rattle(max(0.3, d), 50, "swell")

    def hit(self, g=1.0):                        # tail whip
        return mix(sweep(self.s, 0.12, [(0, 900), (1, 4000)], [(0, 0), (0.85, 1), (1, 0)], 0.5), (pk(click(self.s, 0.03, 2000, 10000, 0.0015)), 1.0, 0.11),
                   (pk(thud(self.s, 160, 0.2, 0.04, grit=0.5)), 0.6, 0.11)) * g

    def swish(self, d=0.25):
        return self.tex(d, "build")

    def fall(self):                              # the rattle slows, coils slump
        return mix((self.rattle(0.9, [(0, 50), (1, 14)], "fade"), 0.7), (self.tex(0.7, "fade"), 0.6, 0.1), (pk(thud(self.s, 120, 0.35, 0.07, grit=0.4)), 0.5, 0.2))

    def custom(self, ev, a):
        if ev == "idle" and a == 0:              # rattling softly, a breathy "sss-aah" over it
            return mix((self.rattle(1.0, 46, "swell"), 0.55), (self.call(0.7, "arch"), 1.0, 0.2))
        if ev == "death" and a == 3:             # the rattle slowing under a falling breathy wail
            return mix((self.rattle(1.2, [(0, 52), (1, 10)], "fade"), 0.7), (self.v(0.9, fp(320, "fall"), [(0, "a"), (1, "u")], AMP["fall"], breath=0.7), 0.8, 0.1))
        return None


class Gargoyle(Kit):
    """가고일: a stone-grinding screech, heavy gritty stone wings, cracking rock."""
    region, tempo = "quarry", 1.05
    VOX = dict(scale=1.05, tilt=0.9, breath=0.12, rasp=0.9, sharp=4.0, rlo=500, rhi=6000, fmax=7000, flutter=0.3)

    def call(self, d, shape="arch", k=1.0):      # screech with stone grinding under it
        sc = self.v(d, fp(600 * self.p, shape, k), [(0, "ae"), (1, "a")], amp_of(shape))
        return mix((sc, 0.85), (grind(self.s, d, 80, 900, amp_of(shape), 90), 0.6))

    def bark(self, k=1.0):                       # "kraak" + rock clack
        sc = self.v(0.14, [(0, 700 * k), (0.3, 780 * k), (1, 560 * k)], "a", [(0, 0), (0.08, 1), (1, 0)])
        return mix(pk(rock(self.s, 1.0)), (sc, 0.9, 0.01))

    def pain(self, d, shape="fall", k=1.0):
        return mix(pk(click(self.s, 0.05, 1500, 9000, 0.003)), (pk(rock(self.s, 1.2)), 0.8), (self.v(d, fp(820, shape, k), "ae", amp_of(shape)), 0.9, 0.02))

    def breath(self, d, inhale=True):            # a dusty exhale
        return mix(sweep(self.s, d, [(0, 500), (1, 1800)] if inhale else [(0, 1800), (1, 500)], IN_AMP if inhale else OUT_AMP, 0.8),
                   (crackle(self.s, d, 40, 600, 4000, IN_AMP if inhale else OUT_AMP), 0.8))

    def tex(self, d, env="swell"):
        return mix((grind(self.s, d, 70, 600, ENV[env], 60), 0.8), (debris(self.s, secs(d), 5, 0.2, d * 0.7, (0.3, 0.5), 0.4), 0.6))

    def sig(self, d=0.4):                        # heavy stone wings
        out = buf(d + 0.4)
        m = max(2, int(d * 4.5))
        for j in range(m):
            place(out, flap(self.s, 1.6, grit=0.6), j * d / m, 0.9)
        return out

    def hit(self, g=1.0):                        # stone claws
        return mix(pk(rock(self.s, 1.4)), (pk(thud(self.s, 80, 0.35, 0.07, grit=0.8)), 0.9), (pk(click(self.s, 0.04, 1500, 8000, 0.002)), 0.6)) * g

    def swish(self, d=0.28):                     # a stone dive
        return mix(pk(shaped(self.s, d, [(0, 1600), (0.7, 500), (1, 350)], [(0, 0.1), (0.75, 1), (1, 0)], 0.7, body=0.6)), (grind(self.s, d, 80, 600, None, 40), 0.3))

    def fall(self):                              # crumbles to rubble
        return mix(pk(click(self.s, 0.05, 1500, 9000, 0.003)), (debris(self.s, secs(1.0), 30, 0.0, 0.8, (0.3, 1.1), 0.5), 1.0), (pk(thud(self.s, 60, 0.5, 0.12, grit=0.8)), 0.7, 0.15))


class Minotaur(Kit):
    """미노타우로스: a bull's snorts and "mmOOOR" bellow, pawing hooves, a great axe."""
    region, tempo = "quarry", 1.1
    VOX = dict(scale=0.78, tilt=0.85, breath=0.3, rasp=0.45, sharp=2.5, rlo=200, rhi=3500, sub=0.5, flutter=0.4, fmax=4500, bw=1.2)

    def call(self, d, shape="arch", k=1.0):      # bellow
        return self.v(d, fp(115 * self.p, shape, k), [(0, "m"), (0.2, "o"), (0.7, "o"), (1, "u")], amp_of(shape))

    def snort(self, d=0.13):
        return pk(breathy(self.s, d, [(0, 600), (0.03, 1500), (d, 900)], [(0, 0), (0.008, 1), (0.05, 0.6), (d, 0)], 0.9)
                  + snarl(self.s, d, [(0, 55), (d, 45)], "u", [(0, 0), (0.01, 0.7), (d, 0)], 1.0, 6, 300, 3000) * 0.6)

    def bark(self, k=1.0):                       # snort-snort
        return mix(self.snort(0.12 * k), (self.snort(0.13), 0.85, 0.16))

    def pain(self, d, shape="fall", k=1.0):      # "MMRRH"
        return self.v(d, fp(150 * self.p, shape, k), [(0, "m"), (0.15, "a"), (1, "u")], amp_of(shape), rasp=0.7)

    def breath(self, d, inhale=True):            # long nostril blast
        return pk(breathy(self.s, d, R(d, [(0, 500), (1, 1300)] if inhale else [(0, 1400), (1, 600)]), R(d, IN_AMP if inhale else OUT_AMP), 0.8)
                  * wob(self.s, secs(d), 25, 0.4))

    def hoof(self, f=85):
        return mix(pk(thud(self.s, f, 0.2, 0.04, grit=0.7)), (pk(click(self.s, 0.02, 700, 3000, 0.002)), 0.5))

    def tex(self, d, env="swell"):               # pawing the ground
        out = mix((pk(scrape(self.s, d, 200, 2600)) * ctl(secs(d), R(d, ENV[env])), 0.7))
        for at in np.arange(0.05, d, 0.28):
            place(out, self.hoof(self.u(78, 95)), at, 0.6)
        return out

    def sig(self, d=0.4):                        # snort + stamp
        return mix(self.snort(), (self.hoof(80), 0.9, min(0.2, d * 0.5)), (self.hoof(88), 0.7, min(0.32, d * 0.8)))

    def hit(self, g=1.0):                        # the great axe / horns
        return mix(pk(thud(self.s, 70, 0.4, 0.09, body=1.2, grit=0.8)), (metal(self.s, 380, 0.08, 0.4), 0.45), (self.snort(0.1), 0.4, 0.02)) * g

    def swish(self, d=0.3):
        return pk(shaped(self.s, d, [(0, 250), (0.6, 900), (1, 300)], [(0, 0), (0.6, 1), (1, 0)], 0.75, body=0.7, tone=0.05))

    def fall(self):
        return mix(boom(self.s, 52, 0.6, 0.14), (self.snort(0.3), 0.6, 0.05), (debris(self.s, secs(0.5), 8, 0.03, 0.3, (0.3, 0.7), 0.5), 0.5))


class MummyKing(Kit):
    """미라 왕: a dry rasping moan, bandages ripping and fluttering, sand pouring, tomb echo."""
    region, tempo = "quarry", 1.15
    VOX = dict(scale=0.85, tilt=0.6, breath=0.72, rasp=0.85, sharp=5.0, rlo=300, rhi=5000, fmax=5000, flutter=0.4)

    def call(self, d, shape="arch", k=1.0):      # dry rasping moan, echoing
        m = self.v(d, fp(64 * self.p, shape, k), [(0, "a"), (0.5, "o"), (1, "eo")], amp_of(shape), jitter=0.04)
        return echo(mix((m, 1.0), (whisper(self.s, d, [(0, "a"), (1, "o")], amp_of(shape), 0.9, 0.25, 0.2), 0.4)), ((0.11, 0.35), (0.23, 0.2)), 3000)

    def bark(self, k=1.0):                       # a dry gasp "HAAH" + cloth snap
        return mix(whisper(self.s, 0.2, "a", [(0, 0), (0.05, 1), (1, 0)], 0.9 * k, 0.3, 0.3), (tear(self.s, 0.08, 1500, 6000, 40), 0.6))

    def pain(self, d, shape="fall", k=1.0):      # hoarse gasp, bandage rip
        return mix(self.v(d, fp(90, shape, k), "a", amp_of(shape), breath=0.8), (tear(self.s, d * 0.6, 1000, 6000, 35), 0.6, 0.03))

    def breath(self, d, inhale=True):            # rasping inhale
        return whisper(self.s, d, [(0, "o"), (1, "a")], IN_AMP if inhale else OUT_AMP, 0.85, 0.3, 0.35)

    def sand(self, d, env="fade", dens=260):
        n = secs(d)
        return pk(pops(self.s, n, dens, 2000, 7000, ctl(n, R(d, ENV[env] if isinstance(env, str) else env)), (0.0006, 0.0015)) + norm(band(self.s.noise(n), 400, 2500)) * 0.05 * ctl(n, R(d, ENV[env] if isinstance(env, str) else env)))

    def tex(self, d, env="swell"):               # sand trickling, cloth rustling
        n = secs(d)
        cloth = pk(band(self.s.noise(n), 900, 5000) * wob(self.s, n, 12, 0.8) * ctl(n, R(d, ENV[env])))
        return mix((self.sand(d, env), 0.7), (cloth, 0.5))

    def sig(self, d=0.4):                        # bandage whipping and ripping
        return mix((tear(self.s, d, 900, 6000, 45), 1.0), (self.sand(d * 0.8, "burst"), 0.5, d * 0.2))

    def hit(self, g=1.0):                        # a curse bursting: sand blast + low boom
        return mix(boom(self.s, 60, 0.5, 0.12, 0.4), (pk(burst(self.s, 0.6, 300, 4000, 0.15, 0.01)), 0.8), (self.sand(0.6, "fade"), 0.5, 0.05)) * g

    def swish(self, d=0.3):                      # cloth swirl
        return pk(shaped(self.s, d, [(0, 500), (0.6, 2200), (1, 700)], [(0, 0), (0.6, 1), (1, 0)], 0.7, (12, 0.6)))

    def fall(self):                              # cloth slumps, sand pours out
        return mix((self.sand(1.0, "decay"), 0.8), (pk(thud(self.s, 90, 0.4, 0.09, grit=0.3)), 0.6), (tear(self.s, 0.4, 700, 4000, 18), 0.4, 0.1))


class Chimera(Kit):
    """키메라 (boss): three heads - a lion's roar, a goat's quavering bleat, a snake's hiss."""
    region, tempo, room = "quarry", 1.15, 1.15

    def lion(self, d, shape="arch", k=1.0):
        return voc(self.s, d, fp(128 * self.p, shape, k), [(0, "eo"), (0.25, "a"), (1, "o")], amp_of(shape), scale=0.72, tilt=0.85, breath=0.25,
                   rasp=0.75, sharp=3.0, rlo=200, rhi=5000, sub=0.5, flutter=0.5, fmax=5000, bw=1.2)

    def goat(self, d, shape="flat", k=1.0):
        return voc(self.s, d, fp(390 * self.p, shape, k), [(0, "n"), (0.1, "e"), (1, "ae")], amp_of(shape), scale=1.0, tilt=1.0, breath=0.2,
                   rasp=0.35, sharp=3.0, rlo=800, rhi=6000, vib=(8, 0.05), fmax=7000, am=(9, 0.6))

    def snake(self, d, amp=None):
        return mix((hissn(self.s, d, 3000, 9500, amp or ENV["swell"]), 1.0), (buzz(self.s, d, 42, 4000, 9000, amp or ENV["swell"]), 0.3))

    def call(self, d, shape="arch", k=1.0):      # the lion leads, the goat answers inside it
        return mix((self.lion(d, shape, k), 1.0), (self.goat(d * 0.5, "fall", k), 0.45, d * 0.45))

    def bark(self, k=1.0):                       # a short goat bleat
        return self.goat(0.22, "fall", k)

    def pain(self, d, shape="fall", k=1.0):      # lion yelps, goat screams
        return mix((self.lion(d, shape, k * 1.6), 1.0), (self.goat(d, "rise", k * 1.2), 0.6))

    def breath(self, d, inhale=True):
        return self.snake(d, IN_AMP if inhale else OUT_AMP)

    def tex(self, d, env="swell"):               # lion's purring growl, the snake hisses now and then
        g = voc(self.s, d, [(0, 62), (1, 58)], "o", ENV[env], scale=0.72, rasp=0.6, sharp=2.0, sub=0.5, flutter=0.85, fmax=3500, breath=0.3)
        return mix((g, 0.8), (self.snake(d * 0.4, [(0, 0), (0.2, 1), (1, 0)]), 0.35, d * 0.5))

    def sig(self, d=0.4):                        # snarl -> bleat -> hiss
        q = max(0.12, d / 3)
        return mix((self.lion(q * 1.2, "fall", 1.1), 1.0), (self.goat(q * 1.1, "flat"), 0.8, q), (self.snake(q * 1.4, OUT_AMP), 0.7, 2 * q))

    def hit(self, g=1.0):                        # claws and horns, the snake bites
        return mix(pk(thud(self.s, 66, 0.4, 0.09, body=1.2, grit=0.8)), (tear(self.s, 0.2), 0.6), (pk(np.asarray(modal([950, 1600], [0.015, 0.01], [1, 0.5], 0.08, self.s.rng))), 0.5, 0.05)) * g

    def swish(self, d=0.3):
        return pk(shaped(self.s, d, [(0, 220), (0.6, 800), (1, 300)], [(0, 0), (0.6, 1), (1, 0)], 0.8, body=0.8))

    def fall(self):
        return mix(boom(self.s, 46, 0.8, 0.18), (self.snake(0.8, OUT_AMP), 0.4, 0.1), (debris(self.s, secs(0.6), 10, 0.03, 0.4, (0.3, 0.9), 0.5), 0.5))

    def roar(self, a):
        if a == 0:      # lion's great roar, the goat screaming over it, the hiss trailing
            return mix((self.lion(1.8, [(0, 0.8), (0.3, 1.2), (0.7, 1.1), (1, 0.75)], 1.0), 1.0), (self.goat(0.9, "arch", 1.1), 0.5, 0.4),
                       (self.snake(0.9, OUT_AMP), 0.5, 1.4))
        if a == 1:      # the snake hisses first, the lion answers, the goat last
            return mix((self.snake(0.7, IN_AMP), 0.8), (self.lion(1.3, "rise", 1.05), 1.0, 0.55), (self.goat(0.7, "fall", 1.15), 0.7, 1.75))
        if a == 2:      # goat leads, the lion drowns it
            return mix((self.goat(0.8, "rise", 1.0), 0.8), (self.lion(1.6, "fall", 1.1), 1.0, 0.5), (rumble(self.s, 2.2, 30, 200, ENV["swell"]), 0.4))
        # all three at once over a quarry rumble, twice
        out = mix((rumble(self.s, 2.6, 30, 220, ENV["swell"]), 0.5))
        for at, k in ((0.1, 1.0), (1.25, 0.9)):
            place(out, mix((self.lion(1.0, "arch", k), 1.0), (self.goat(0.8, "flat", k * 1.1), 0.45, 0.1), (self.snake(1.0), 0.4)), at)
        return out

    def intro(self, a):
        lead = [1.1, 0.8, 1.3][a]
        out = mix((rumble(self.s, lead + 0.7, 28, 220, [(0, 0), (0.8, 1), (1, 0)]), 0.9),
                  (debris(self.s, secs(lead + 0.5), [12, 20, 8][a], 0.0, lead, (0.3, 0.9), 0.5), 0.5))
        for j in range(3):
            place(out, pk(thud(self.s, 60, 0.3, 0.06, grit=0.6)), lead * (0.3 + 0.22 * j), 0.4 + 0.15 * j)
        seq = [(self.lion, 0.0, 1.0), (self.goat, 0.75, 0.7), (self.snake, 1.25, 0.6)]
        order = [[0, 1, 2], [2, 0, 1], [1, 2, 0]][a]
        for slot, idx in enumerate(order):
            fn, _, g = seq[idx]
            d = [1.0, 0.6, 0.7][idx]
            x = fn(d, "rise") if fn != self.snake else fn(d)
            place(out, x, lead + [0.0, 0.7, 1.15][slot], g)
        return out


# =============================================================================== frost (서리빛 분지)
class Ghoul(Kit):
    """구울: a wet bubbling gurgle in the throat, ragged wet breathing, slurps, claws."""
    region, tempo = "frost", 0.92
    VOX = dict(scale=0.95, tilt=0.9, breath=0.4, rasp=0.45, sharp=3.0, rlo=200, rhi=4000, flutter=0.9, fmax=4500, am=(18, 0.75))

    def bubbles(self, d, rate=11, f0=320, env="fade"):
        return train(self.s, d, [(0, rate), (1, rate * 0.8)], lambda j, q: pk(bloop(self.s, f0 * self.u(0.7, 1.4), f0 * self.u(0.4, 0.7), self.u(0.04, 0.08), 0.5)),
                     ENV[env], 0.4)

    def call(self, d, shape="arch", k=1.0):      # gurgling moan
        return mix((self.v(d, fp(135 * self.p, shape, k), [(0, "o"), (0.5, "eu"), (1, "u")], amp_of(shape)), 1.0), (self.bubbles(d, 12, 300, "swell"), 0.35))

    def bark(self, k=1.0):                       # "grk!"
        return mix(self.v(0.14, [(0, 170 * k), (1, 130 * k)], "eu", [(0, 0), (0.06, 1), (1, 0)], rasp=0.9, am=(30, 0.8)), (pk(bloop(self.s, 400, 180, 0.08, 0.7)), 0.5, 0.06))

    def pain(self, d, shape="fall", k=1.0):      # a choked yelp
        return self.v(d, fp(390 * self.p, shape, k), [(0, "a"), (1, "u")], amp_of(shape), rasp=0.6, am=(24, 0.8))

    def breath(self, d, inhale=True):            # ragged wet breath
        return mix(pk(breathy(self.s, d, R(d, [(0, 600), (1, 1600)] if inhale else [(0, 1500), (1, 600)]), R(d, IN_AMP if inhale else OUT_AMP), 0.7) * wob(self.s, secs(d), 20, 0.7)),
                   (self.bubbles(d, 8, 260), 0.3))

    def tex(self, d, env="swell"):               # chewing and slurping
        out = buf(d + 0.2)
        for at in np.arange(0.0, d - 0.05, self.u(0.16, 0.22)):
            place(out, mix(pk(norm(low(self.s.noise(secs(0.06)), 1600)) * np.exp(-T(secs(0.06)) / 0.015)), (pk(bloop(self.s, self.u(250, 500), 160, 0.07, 0.6)), 0.6, 0.01)), at,
                  0.4 + 0.6 * float(ctl(secs(d), R(d, ENV[env]))[min(secs(at), secs(d) - 1)]))
        return out

    def sig(self, d=0.4):
        return self.bubbles(d, 14, 360, "swell")

    def hit(self, g=1.0):                        # claw rip + wet smack
        return mix((tear(self.s, 0.2, 800, 4500, 26), 0.8), pk(thud(self.s, 120, 0.2, 0.04, grit=0.6)), (pk(norm(low(self.s.noise(secs(0.1)), 1200)) * np.exp(-T(secs(0.1)) / 0.02)), 0.5)) * g

    def swish(self, d=0.2):
        return self.breath(d, False)

    def fall(self):                              # drowning gurgle, wet flop
        return mix((self.v(0.7, [(0, 140), (1, 80)], "u", OUT_AMP, am=(12, 0.9)), 0.7), (pk(thud(self.s, 100, 0.35, 0.07, grit=0.5)), 0.8, 0.2), (self.bubbles(0.6, 7, 220), 0.4, 0.3))


class FrostWraith(Kit):
    """서리 망령: an icy whispering wail, frosty gusts, glassy shimmer."""
    region, tempo = "frost", 1.05
    VOX = dict(scale=1.15, tilt=1.3, breath=0.55, rasp=0.0, fmax=7000, vib=(5.5, 0.03))

    def shimmer(self, d, dens=50, env="swell"):
        return mix(pk(tinkles(self.s, secs(d), dens, 3500, 9500, ctl(secs(d), R(d, ENV[env])))), (sweep(self.s, d, [(0, 6500), (1, 8500)], ENV[env], 0.4), 0.3))

    def call(self, d, shape="arch", k=1.0):      # wail with a whisper inside
        w = self.v(d, fp(560 * self.p, shape, k), [(0, "u"), (0.5, "o"), (1, "u")], amp_of(shape))
        return mix((w, 1.0), (whisper(self.s, d, [(0, "i"), (1, "u")], amp_of(shape), 1.2, 0.18, 0.3), 0.45), (self.shimmer(d, 25), 0.25))

    def bark(self, k=1.0):                       # whispered "hih!" + a glint
        return mix(whisper(self.s, 0.16, "i", [(0, 0), (0.1, 1), (1, 0)], 1.25 * k, 0.15, 0.4), (glass(self.s, self.u(3000, 4200), 0.06), 0.4, 0.04))

    def pain(self, d, shape="fall", k=1.0):      # whispery shriek
        return mix(self.v(d, fp(880 * self.p, shape, k), "i", amp_of(shape), breath=0.6), (whisper(self.s, d, "i", amp_of(shape), 1.3), 0.4))

    def breath(self, d, inhale=True):            # an icy gust
        return sweep(self.s, d, [(0, 1500), (1, 5500)] if inhale else [(0, 5500), (1, 1800)], IN_AMP if inhale else OUT_AMP, 0.5)

    def tex(self, d, env="swell"):               # murmuring whispers
        out = buf(d + 0.3)
        t = 0.0
        while t < d - 0.1:
            place(out, whisper(self.s, 0.14, [(0, "aeiou"[int(self.u(0, 4.99))]), (1, "u")], None, 1.15, 0.2, 0.25), t, self.u(0.4, 0.9))
            t += self.u(0.12, 0.2)
        return mix((out * ctl(out.size, R(out.size / SR, ENV[env])), 1.0), (self.shimmer(d, 20, env), 0.3))

    def sig(self, d=0.4):
        return self.shimmer(d, 110, "burst")

    def hit(self, g=1.0):                        # an icy gust strikes, ice cracks
        return mix(sweep(self.s, 0.25, [(0, 2000), (1, 7000)], [(0, 0), (0.8, 1), (1, 0)], 0.5), (pk(click(self.s, 0.04, 2500, 10000, 0.002)), 0.9, 0.2),
                   (self.shimmer(0.3, 120, "fade"), 0.6, 0.2)) * g

    def swish(self, d=0.25):
        return self.breath(d, True)

    def fall(self):                              # dissolves into wind and falling glints
        return mix((self.breath(0.9, False), 0.6), (self.shimmer(0.9, 70, "fade"), 0.7, 0.05))


class IceShardling(Kit):
    """얼음 조각병: no voice - crystal pings and chime chirps, grinding crystal, shattering shards."""
    region, tempo, layer = "frost", 0.85, 0.5

    def call(self, d, shape="arch", k=1.0):      # a tinkling chime melody that follows the contour
        pts = SHAPE[shape] if isinstance(shape, str) else shape
        fc = ctl(secs(d), R(d, [(t, 2700 * k * m) for t, m in pts]))
        return train(self.s, d, [(0, 12), (1, 14)], lambda j, q: glass(self.s, float(fc[min(int(q * fc.size), fc.size - 1)]) * self.u(0.97, 1.03), 0.07), amp_of(shape), 0.15)

    def bark(self, k=1.0):                       # tink-tink
        f = 3300 * k * self.p
        return mix(glass(self.s, f, 0.08), (glass(self.s, f * 1.19, 0.08), 0.8, 0.05), (pk(click(self.s, 0.01, 4000, 11000, 0.0004)), 0.4))

    def pain(self, d, shape="fall", k=1.0):      # a crack and falling pings
        out = mix(pk(click(self.s, 0.04, 2500, 11000, 0.0015)), (glass(self.s, 1900, 0.05), 0.8))
        for j, f in enumerate((3600, 3000, 2500)):
            place(out, glass(self.s, f * k, 0.06), 0.05 + j * d / 3.5, 0.7 - 0.15 * j)
        return out

    def breath(self, d, inhale=True):            # frost hiss
        return hissn(self.s, d, 5000, 10500, IN_AMP if inhale else OUT_AMP)

    def tex(self, d, env="swell"):               # shimmering glints
        return pk(tinkles(self.s, secs(d), 45, 3000, 9500, ctl(secs(d), R(d, ENV[env])), (0.04, 0.12)))

    def sig(self, d=0.4):                        # crystal grinding
        n = secs(d)
        return mix(pk(band(self.s.noise(n), 2500, 9000) * wob(self.s, n, 30, 0.8) * ctl(n, R(d, ENV["swell"]))), (crackle(self.s, d, 150, 3000, 10000, ENV["swell"]), 0.8))

    def hit(self, g=1.0):                        # shard burst
        return mix(pk(click(self.s, 0.04, 2000, 11000, 0.002)), (pk(tinkles(self.s, secs(0.4), 160, 2500, 9500, ctl(secs(0.4), [(0, 1), (0.4, 0)]))), 0.8),
                   (pk(thud(self.s, 200, 0.12, 0.03, grit=0.3)), 0.4)) * g

    def swish(self, d=0.2):
        return sweep(self.s, d, [(0, 4000), (1, 9000)], [(0, 0), (0.7, 1), (1, 0)], 0.4)

    def fall(self):                              # shatters, shards rain down
        rain = train(self.s, 0.8, [(0, 40), (1, 6)], lambda j, q: glass(self.s, self.u(1800, 5200), 0.05), [(0, 1), (1, 0.3)], 0.5)
        return mix(pk(click(self.s, 0.05, 1500, 11000, 0.003)), (rain, 0.8, 0.01))


class Draugr(Kit):
    """드라우그: an undead moaning groan, rattling chainmail, clanking plate, a rusty sword."""
    region, tempo = "frost", 1.05
    VOX = dict(scale=0.82, tilt=1.0, breath=0.45, rasp=0.35, sharp=2.5, rlo=200, rhi=3500, flutter=0.5, fmax=4500, vib=(3, 0.02), sub=0.3)

    def chain(self, d, env="swell", dens=160):
        return pk(tinkles(self.s, secs(d), dens, 2500, 7000, ctl(secs(d), R(d, ENV[env])), (0.008, 0.025)))

    def call(self, d, shape="arch", k=1.0):      # moan
        return self.v(d, fp(88 * self.p, shape, k), [(0, "o"), (0.5, "u"), (1, "o")], amp_of(shape))

    def bark(self, k=1.0):                       # "huhh" + chain jingle
        return mix(self.v(0.18, [(0, 110 * k), (1, 90 * k)], [(0, "a"), (1, "u")], [(0, 0), (0.05, 1), (1, 0)], breath=0.5), (self.chain(0.2, "burst", 120), 0.4))

    def pain(self, d, shape="fall", k=1.0):      # clang + short groan
        return mix(metal(self.s, self.u(520, 600), 0.12, 0.7), (self.call(d, shape, k * 1.3), 0.9, 0.02))

    def breath(self, d, inhale=True):            # a cold rattling breath
        return mix(pk(breathy(self.s, d, R(d, [(0, 400), (1, 1100)] if inhale else [(0, 1000), (1, 400)]), R(d, IN_AMP if inhale else OUT_AMP), 0.8)),
                   (self.chain(d, "swell", 40), 0.2))

    def tex(self, d, env="swell"):               # chainmail shifting, a plate knocking
        return mix((self.chain(d, env), 0.8), (metal(self.s, self.u(420, 520), 0.05, 0.4), 0.35, d * 0.5))

    def sig(self, d=0.4):
        return mix(metal(self.s, self.u(480, 560), 0.15, 0.8), (self.chain(d, "fade"), 0.7))

    def hit(self, g=1.0):                        # rusty sword clang
        return mix(metal(self.s, self.u(600, 700), 0.22, 0.9), (pk(thud(self.s, 110, 0.25, 0.05, grit=0.6)), 0.6), (self.chain(0.3, "fade"), 0.4)) * g

    def swish(self, d=0.25):
        return mix(pk(shaped(self.s, d, [(0, 400), (0.6, 1500), (1, 600)], [(0, 0), (0.6, 1), (1, 0)], 0.6)), (self.chain(d, "build", 80), 0.4))

    def fall(self):                              # armour collapses
        out = mix((self.chain(0.9, "decay"), 0.8))
        for j, at in enumerate((0.0, 0.18, 0.31)):
            place(out, metal(self.s, self.u(380, 620), 0.1, 0.6), at, 0.8 - 0.15 * j)
        place(out, pk(thud(self.s, 90, 0.4, 0.09, grit=0.6)), 0.05, 0.7)
        return out


class Yeti(Kit):
    """예티: a big chesty roar, ape-like hoots, chest drumming, crunching snow."""
    region, tempo = "frost", 1.08
    VOX = dict(scale=0.76, tilt=0.9, breath=0.4, rasp=0.6, sharp=3.0, rlo=200, rhi=4500, sub=0.4, flutter=0.5, fmax=4500, bw=1.15)

    def call(self, d, shape="arch", k=1.0):      # roar
        return self.v(d, fp(150 * self.p, shape, k), [(0, "o"), (0.25, "a"), (1, "a")], amp_of(shape))

    def hoot(self, k=1.0):
        f = 230 * k * self.p
        return self.v(0.16, [(0, f * 0.85), (0.3, f), (1, f * 0.92)], "u", [(0, 0), (0.15, 1), (0.6, 0.8), (1, 0)], rasp=0.15, breath=0.35)

    def bark(self, k=1.0):
        return self.hoot(k)

    def pain(self, d, shape="fall", k=1.0):      # "HUAH"
        return self.v(d, fp(210 * self.p, shape, k), [(0, "u"), (0.2, "a"), (1, "o")], amp_of(shape), rasp=0.75)

    def breath(self, d, inhale=True):            # huffing
        out = buf(d + 0.2)
        for j in range(max(1, int(d / 0.22))):
            place(out, pk(breathy(self.s, 0.17, [(0, 500), (0.17, 1300)] if inhale else [(0, 1200), (0.17, 500)], [(0, 0), (0.03, 1), (0.17, 0)], 0.8)), j * 0.22, 0.8)
        return out

    def snow(self, d, dens=180):
        n = secs(d)
        return pk(pops(self.s, n, dens, 800, 6000, ctl(n, R(d, ENV["fade"])), (0.002, 0.006)) + norm(band(self.s.noise(n), 600, 5000)) * 0.15 * ctl(n, R(d, ENV["fade"])))

    def tex(self, d, env="swell"):               # chest drumming, grumble
        out = mix((self.v(d, [(0, 80), (1, 76)], "o", ENV[env], rasp=0.5, flutter=0.8), 0.5))
        for j, at in enumerate(np.arange(0.05, d, 0.11)[:6]):
            place(out, pk(thud(self.s, self.u(85, 100), 0.15, 0.03, grit=0.4)), at, 0.5 + 0.08 * j)
        return out

    def sig(self, d=0.4):                        # hoots climbing and speeding up
        out = buf(d + 0.3)
        m = max(3, int(d * 8))
        for j in range(m):
            place(out, self.hoot(1.0 + 0.07 * j), d * (j / m) ** 0.8, 0.6 + 0.4 * j / m)
        return out

    def hit(self, g=1.0):                        # slam into snow
        return mix(pk(thud(self.s, 70, 0.4, 0.09, body=1.2, grit=0.6)), (self.snow(0.4), 0.8)) * g

    def swish(self, d=0.28):
        return pk(shaped(self.s, d, [(0, 250), (0.6, 900), (1, 300)], [(0, 0), (0.6, 1), (1, 0)], 0.8, body=0.7))

    def fall(self):
        return mix(boom(self.s, 58, 0.6, 0.14), (self.snow(0.6, 260), 0.8, 0.01), (self.breath(0.4, False), 0.4, 0.1))


class Wendigo(Kit):
    """웬디고: an eerie, inharmonic two-voiced shriek, whistling breath, knocking antlers and bones."""
    region, tempo = "frost", 1.0
    VOX = dict(scale=1.2, tilt=1.0, breath=0.35, rasp=0.5, sharp=4.0, rlo=900, rhi=8000, fmax=8000, jitter=0.02)

    def call(self, d, shape="arch", k=1.0):      # two detuned voices a sharp tritone-ish apart, jumpy
        base = SHAPE[shape] if isinstance(shape, str) else shape
        jumps = []
        for i in range(9):                       # the contour broken into sudden pitch jumps
            t0, t1 = i / 9, (i + 1) / 9
            m = float(np.interp(t0, [q for q, _ in base], [v for _, v in base])) * (1.13 if i % 3 == 1 else 0.9 if i % 3 == 2 else 1.0)
            jumps += [(t0, m), (t1 - 0.01, m)]
        amp = amp_of(shape)
        a = self.v(d, fp(860 * self.p, jumps, k), [(0, "i"), (1, "ae")], amp, vib=(7.3, 0.03))
        b = self.v(d, fp(860 * 1.414 * self.p, jumps, k), [(0, "e"), (1, "i")], amp, vib=(5.1, 0.04), rasp=0.3)
        return mix((a, 1.0), (b, 0.55))

    def knock(self, k=1.0):
        return bone(self.s, self.u(520, 760) * k, 0.02)

    def bark(self, k=1.0):                       # antler knock + a short screech
        return mix(self.knock(k), (self.v(0.12, [(0, 1250 * k), (1, 1050 * k)], "i", [(0, 0), (0.1, 1), (1, 0)], rasp=0.7), 0.8, 0.03))

    def pain(self, d, shape="fall", k=1.0):      # jagged screech
        n = secs(d)
        x = self.v(d, fp(1300 * self.p, shape, k), "ae", amp_of(shape), rasp=0.8)
        return pk(x * (0.4 + 0.6 * (np.sin(2 * np.pi * 31 * T(n)) > -0.3)))

    def breath(self, d, inhale=True):            # whistling breath
        n = secs(d)
        wh = pk(glide(n, ctl(n, R(d, [(0, 1800), (1, 2600)] if inhale else [(0, 2600), (1, 1700)]))) * ctl(n, R(d, IN_AMP if inhale else OUT_AMP)))
        return mix((pk(breathy(self.s, d, R(d, [(0, 1500), (1, 3500)]), R(d, IN_AMP if inhale else OUT_AMP), 0.6)), 1.0), (wh, 0.25))

    def tex(self, d, env="swell"):               # bones knocking, rasping breath
        out = mix((pk(breathy(self.s, d, R(d, [(0, 1200), (1, 2000)]), R(d, ENV[env]), 0.7) * wob(self.s, secs(d), 6, 0.6)), 0.5))
        t = self.u(0.0, 0.1)
        while t < d:
            place(out, self.knock(), t, self.u(0.4, 0.9))
            t += self.u(0.13, 0.32)
        return out

    def sig(self, d=0.4):                        # a distant eerie wail
        x = voc(self.s, max(0.35, d), fp(430 * self.p, "arch"), "u", AMP["arch"], scale=1.1, tilt=1.6, breath=0.5, vib=(4.2, 0.05), fmax=5000)
        return echo(x, ((0.15, 0.4), (0.31, 0.2)), 4000)

    def hit(self, g=1.0):                        # claws rip, a bone snaps
        return mix((tear(self.s, 0.22, 1000, 6000, 28), 0.8), (pk(click(self.s, 0.04, 1500, 8000, 0.002)), 0.7), (self.knock(1.3), 0.6, 0.01), (pk(thud(self.s, 120, 0.2, 0.04, grit=0.5)), 0.6)) * g

    def swish(self, d=0.25):
        return sweep(self.s, d, [(0, 900), (1, 3500)], [(0, 0), (0.7, 1), (1, 0)], 0.6)

    def fall(self):                              # bones clattering down
        return mix(train(self.s, 0.6, [(0, 30), (1, 6)], lambda j, q: self.knock(self.u(0.8, 1.5)), [(0, 1), (1, 0.3)], 0.5), (pk(thud(self.s, 100, 0.3, 0.06, grit=0.5)), 0.7))

    def custom(self, ev, a):
        if ev == "alert" and a == 0:             # antlers knock, a far eerie wail, then the shriek
            return mix(self.knock(), (self.knock(1.2), 0.8, 0.12), (self.sig(0.45), 0.7, 0.2), (self.call(0.5, "rise", 1.05), 1.0, 0.6))
        if ev == "windup" and a == 3:            # whistling in-breath under knocking bones, a shriek on top
            W = self.W * 0.97 + 0.06
            return mix((self.breath(W * 0.7, True), 0.8), (self.tex(W * 0.7, "build"), 0.5), (self.pain(W * 0.35, "rise", 0.85), 1.0, W * 0.65))
        return None


class FrostHag(Kit):
    """서리 마녀: a crone's wobbling cackle, muttering, icy spell shimmer, a knocking staff."""
    region, tempo = "frost", 1.0
    VOX = dict(scale=1.05, tilt=1.0, breath=0.4, rasp=0.6, sharp=4.0, rlo=500, rhi=6500, fmax=7000, vib=(6.5, 0.05))

    def call(self, d, shape="arch", k=1.0):      # crone wail
        return self.v(d, fp(380 * self.p, shape, k), [(0, "a"), (1, "e")], amp_of(shape))

    def cackle(self, n=5, rate=6.0, f=440):
        out = buf(n / rate + 0.3)
        for j in range(n):
            ff = f * self.p * (1 - 0.07 * j)
            place(out, pk(breathy(self.s, 0.04, [(0, 2000), (0.04, 2600)], [(0, 0), (0.01, 1), (0.04, 0)], 0.6)), j / rate, 0.4)
            place(out, self.v(0.11, [(0, ff * 1.08), (1, ff * 0.86)], [(0, "e"), (1, "a")], [(0, 0), (0.15, 1), (1, 0)], breath=0.5), j / rate + 0.02)
        return out

    def bark(self, k=1.0):                       # one "HEH" + the staff
        return mix(self.cackle(1, 6.0, 470 * k), (woodk(self.s, 260, 0.03), 0.5, 0.0))

    def pain(self, d, shape="fall", k=1.0):      # crone shriek
        return self.v(d, fp(620 * self.p, shape, k), [(0, "a"), (1, "i")], amp_of(shape), rasp=0.8)

    def breath(self, d, inhale=True):            # icy whisper
        return whisper(self.s, d, [(0, "i"), (1, "u")], IN_AMP if inhale else OUT_AMP, 1.05, 0.2, 0.4)

    def spell(self, d, env="build"):
        return mix((pk(tinkles(self.s, secs(d), 70, 3000, 9500, ctl(secs(d), R(d, ENV[env])))), 0.8), (sweep(self.s, d, [(0, 1200), (1, 6000)], ENV[env], 0.4), 0.6))

    def tex(self, d, env="swell"):               # muttering under her breath, ice crackling
        out = buf(d + 0.2)
        t = 0.0
        while t < d - 0.1:
            f = self.u(300, 400)
            place(out, self.v(0.09, [(0, f), (1, f * 0.9)], "aeiou"[int(self.u(0, 4.99))], [(0, 0), (0.2, 1), (1, 0)], breath=0.7, rasp=0.3), t, 0.5)
            t += self.u(0.11, 0.17)
        return mix((out * ctl(out.size, R(out.size / SR, ENV[env])), 1.0), (crackle(self.s, d, 30, 2000, 9000, ENV[env]), 0.5))

    def sig(self, d=0.4):
        return self.cackle(max(3, int(d * 8)), 7.0)

    def hit(self, g=1.0):                        # spell burst + staff knock
        return mix(self.spell(0.35, "burst"), (woodk(self.s, 240, 0.035), 0.8), (pk(click(self.s, 0.04, 2500, 10000, 0.002)), 0.6, 0.02)) * g

    def swish(self, d=0.25):                     # robes
        return pk(shaped(self.s, d, [(0, 700), (0.6, 2500), (1, 900)], [(0, 0), (0.6, 1), (1, 0)], 0.7, (9, 0.5)))

    def fall(self):                              # the staff clatters, ice tinkles away
        return mix(woodk(self.s, 240, 0.03), (woodk(self.s, 300, 0.02), 0.6, 0.12), (woodk(self.s, 280, 0.015), 0.4, 0.2), (self.spell(0.7, "fade"), 0.5, 0.05))

    def custom(self, ev, a):
        if ev == "alert" and a == 1:             # a long cackle, then a wail
            return mix(self.cackle(6, 6.5, 470), (self.call(0.45, "rise", 1.1), 0.9, 0.95))
        if ev == "windup" and a == 1:            # the spell gathering under a muttered chant
            W = self.W + 0.05
            return mix((self.spell(W, "build"), 0.9), (self.tex(W * 0.8, "build"), 0.6))
        if ev == "death" and a == 1:             # a broken shriek, the spell unravelling, the staff falls
            return mix(self.pain(0.35, "arch"), (self.spell(0.9, "fade"), 0.6, 0.2), (self.fall(), 0.8, 0.4))
        return None


class FrostKnight(Kit):
    """서리 기사: grunts muffled inside a helmet, clanking plate, a ringing sword, frost on steel."""
    region, tempo = "frost", 1.0
    VOX = dict(scale=0.9, tilt=1.0, breath=0.3, rasp=0.35, sharp=2.5, rlo=200, rhi=3000, sub=0.3, flutter=0.4, fmax=4000)

    def helm(self, x):                           # the visor: a short comb + muffling
        x = np.asarray(x, float)
        y = low(x, 1600)
        dl = secs(0.0017)
        z = y.copy()
        z[dl:] += 0.6 * y[:-dl]
        return pk(L.resonate(z, SR, [420, 1150, 2300], [0.02, 0.015, 0.01], [1, 0.6, 0.3]) * 0.5 + z)

    def call(self, d, shape="arch", k=1.0):      # muffled war cry
        return self.helm(self.v(d, fp(118 * self.p, shape, k), [(0, "eo"), (0.4, "a"), (1, "o")], amp_of(shape)))

    def clank(self, k=1.0, tau=0.12):
        return metal(self.s, self.u(330, 420) * k, tau, 0.6)

    def bark(self, k=1.0):                       # "HUP" + clank
        return mix(self.helm(self.v(0.13, [(0, 130 * k), (1, 112 * k)], [(0, "a"), (1, "u")], [(0, 0), (0.05, 1), (1, 0)])), (self.clank(k), 0.5, 0.01))

    def pain(self, d, shape="fall", k=1.0):
        return mix(self.clank(1.2, 0.18), (self.call(d, shape, k * 1.35), 0.9, 0.02))

    def breath(self, d, inhale=True):            # breath inside the helmet
        return self.helm(breathy(self.s, d, R(d, [(0, 400), (1, 1200)] if inhale else [(0, 1100), (1, 400)]), R(d, IN_AMP if inhale else OUT_AMP), 0.8))

    def ring(self, f=None, tau=0.3):             # the sword's long ring
        f = f or self.u(1700, 2100)
        return pk(np.asarray(modal([f, f * 2.76, f * 1.003, f * 4.3], [tau, tau * 0.5, tau * 0.9, tau * 0.3], [1, 0.4, 0.6, 0.15], tau * 2 + 0.1, self.s.rng)))

    def tex(self, d, env="swell"):               # plates shifting, frost crackling on steel
        out = mix((crackle(self.s, d, 40, 2500, 9500, ENV[env]), 0.5))
        for at in np.arange(0.05, d, self.u(0.22, 0.3)):
            place(out, self.clank(self.u(0.9, 1.15), 0.06), at, self.u(0.4, 0.8))
        return out

    def sig(self, d=0.4):                        # the sword drawn and ringing
        n = secs(d)
        draw = pk(band(self.s.noise(n), 2500, 8000) * ctl(n, R(d, [(0, 0), (0.2, 1), (0.9, 0.7), (1, 0)])))
        return mix((draw, 0.5), (self.ring(), 0.7, d * 0.85))

    def hit(self, g=1.0):                        # sword clash, ice cracks off the blade
        return mix(metal(self.s, self.u(850, 1000), 0.25, 1.0), (pk(thud(self.s, 120, 0.25, 0.05, grit=0.5)), 0.6), (pk(click(self.s, 0.04, 3000, 10000, 0.0015)), 0.5, 0.01)) * g

    def swish(self, d=0.24):                     # a thin metallic whistle of the blade
        return pk(shaped(self.s, d, [(0, 900), (0.6, 3200), (1, 1200)], [(0, 0), (0.6, 1), (1, 0)], 0.35, tone=0.3))

    def fall(self):                              # armour collapsing, the sword falls ringing
        out = mix((pk(thud(self.s, 85, 0.4, 0.09, grit=0.6)), 0.8))
        for j, at in enumerate((0.0, 0.14, 0.3, 0.38)):
            place(out, self.clank(self.u(0.85, 1.25), 0.1), at, 0.85 - 0.15 * j)
        place(out, self.ring(self.u(1500, 1800), 0.3), 0.5, 0.6)
        return out


class IceGolem(Kit):
    """얼음 골렘: crackling, grinding ice; a deep glassy groan; creaking ice; shattering chunks."""
    region, tempo, room = "frost", 1.2, 1.1

    def groan(self, d, shape="arch", k=1.0):
        g = voc(self.s, d, fp(48 * self.p, shape, k), [(0, "o"), (1, "u")], amp_of(shape), scale=0.62, tilt=0.7, breath=0.35, rasp=0.3, sharp=2.0,
                rlo=100, rhi=2500, sub=0.6, flutter=0.4, fmax=3000, bw=1.3)
        return pk(L.resonate(g, SR, [650, 1300, 2150], [0.06, 0.04, 0.03], [1, 0.7, 0.4]) * 0.4 + g)

    def call(self, d, shape="arch", k=1.0):      # groan through ice + ice creak + crackle
        sh = SHAPE[shape] if isinstance(shape, str) else shape
        cr = creak(self.s, d, 32 * k * sh[0][1], 32 * k * sh[-1][1], body=(300, 900, 1800, 3400), q=9, rough=0.25, wobble=2.5)
        return mix((self.groan(d, shape, k), 1.0), (cr, 0.45), (crackle(self.s, d, 60, 1500, 9000, amp_of(shape)), 0.5))

    def crack(self, g=1.0, big=1.0):
        f = self.u(1300, 1700) / big
        return mix(pk(click(self.s, 0.05, 2000, 11000, 0.0025)), (glass(self.s, f, 0.05), 0.8), (glass(self.s, f * 1.7, 0.04), 0.5),
                   (pk(thud(self.s, 120 / big, 0.15, 0.03, grit=0.3)), 0.5)) * g

    def bark(self, k=1.0):
        return mix(self.crack(1.0, 1.0 / k), (crackle(self.s, 0.25, 160, 1500, 9000), 0.6, 0.01))

    def pain(self, d, shape="fall", k=1.0):
        return mix(self.crack(), (crackle(self.s, d, 200, 1500, 9000), 0.7), (self.groan(d, shape, k * 1.5), 0.7, 0.03))

    def breath(self, d, inhale=True):            # frosty exhale with glints
        return mix(hissn(self.s, d, 1500, 7000, IN_AMP if inhale else OUT_AMP), (pk(tinkles(self.s, secs(d), 30, 3500, 9000)), 0.3))

    def tex(self, d, env="swell"):               # crackling ice grinding
        return mix((crackle(self.s, d, 160, 1500, 9000, ENV[env]), 0.9), (grind(self.s, d, 50, 300, ENV[env], 10), 0.6))

    def sig(self, d=0.4):                        # a long creak of strained ice
        return creak(self.s, max(0.3, d), 620, 420, body=(900, 1800, 3400), q=9, rough=0.15, wobble=3)

    def hit(self, g=1.0):                        # ice slam, shards scatter
        return mix(boom(self.s, 50, 0.6, 0.14, 0.4), (self.crack(1.0, 1.4), 0.9), (pk(tinkles(self.s, secs(0.5), 90, 2500, 9000, ctl(secs(0.5), [(0, 1), (0.5, 0)]))), 0.6, 0.02)) * g

    def swish(self, d=0.3):
        return mix(pk(shaped(self.s, d, [(0, 200), (0.6, 700), (1, 250)], [(0, 0), (0.6, 1), (1, 0)], 0.8, body=0.8)), (crackle(self.s, d, 60), 0.4))

    def fall(self):                              # shatters: cracks, chunks, glints raining
        out = mix((boom(self.s, 46, 0.7, 0.16, 0.4), 0.8))
        for j, at in enumerate((0.0, 0.1, 0.22, 0.4)):
            place(out, self.crack(0.9 - 0.15 * j, self.u(1.2, 2.2)), at, 1.0)
        place(out, pk(tinkles(self.s, secs(0.8), 80, 2000, 9000, ctl(secs(0.8), [(0, 1), (0.8, 0)]))), 0.2, 0.5)
        return out


class Lich(Kit):
    """리치: echoing whispers, a hollow spectral choir hum, dark magic swelling and bursting, bones."""
    region, tempo, room = "frost", 1.1, 1.2

    def choir(self, d, shape="arch", k=1.0):
        out = mix(*[(voc(self.s, d, fp(f * self.p, shape, k), [(0, "o"), (1, "u")], amp_of(shape), scale=0.9, tilt=1.3, breath=0.5, fmax=4000,
                         vib=(4 + i, 0.01)), g) for i, (f, g) in enumerate(((110, 1.0), (111.7, 0.8), (165, 0.5)))])
        return pk(out)

    def call(self, d, shape="arch", k=1.0):      # spectral moan + a whisper, echoing
        w = whisper(self.s, d, [(0, "a"), (0.5, "o"), (1, "i")], amp_of(shape), 0.95, 0.18, 0.3)
        return echo(mix((self.choir(d, shape, k), 0.8), (w, 0.8)), ((0.12, 0.5), (0.25, 0.32), (0.38, 0.18)), 3500)

    def bark(self, k=1.0):                       # a whispered "HAH" and its echoes
        return echo(whisper(self.s, 0.16, "a", [(0, 0), (0.08, 1), (1, 0)], 0.95 * k, 0.2, 0.3), ((0.1, 0.55), (0.2, 0.35), (0.3, 0.2)), 3000)

    def pain(self, d, shape="fall", k=1.0):      # a hissing whisper-shriek
        return echo(mix(whisper(self.s, d, [(0, "i"), (1, "a")], amp_of(shape), 1.3, 0.15, 0.6), (self.choir(d, shape, k * 2.2), 0.5)), ((0.12, 0.4), (0.24, 0.2)))

    def breath(self, d, inhale=True):            # dark magic drawn in: a reversed swell
        n = secs(d)
        e = 0.05 + 0.95 * ctl(n, R(d, [(0, 0), (1, 1)])) ** 3 if inhale else ctl(n, R(d, [(0, 1), (1, 0)])) ** 2
        return pk(nsweep(self.s, n, ctl(n, R(d, [(0, 300), (1, 3000)] if inhale else [(0, 3000), (1, 300)])), 0.7) * e)

    def tex(self, d, env="swell"):               # murmured syllables echoing
        out = buf(d + 0.2)
        t = 0.0
        while t < d - 0.12:
            place(out, whisper(self.s, 0.12, "aeiou"[int(self.u(0, 4.99))], None, 0.95, 0.2, 0.2), t, self.u(0.5, 1.0))
            t += self.u(0.18, 0.28)
        return echo(out * ctl(out.size, R(out.size / SR, ENV[env])), ((0.15, 0.5), (0.3, 0.3)), 3000)

    def sig(self, d=0.4):                        # magic swells and bursts: sub boom, ice crack
        return mix((self.breath(d, True), 0.8), (boom(self.s, 42, 0.5, 0.12, 0.3), 1.0, d * 0.95), (pk(click(self.s, 0.04, 2500, 10000, 0.002)), 0.6, d))

    def hit(self, g=1.0):                        # a spell blast
        return mix(boom(self.s, 46, 0.5, 0.12, 0.3), (sweep(self.s, 0.35, [(0, 4000), (1, 600)], [(0, 0), (0.05, 1), (1, 0)], 0.5), 0.7),
                   (pk(tinkles(self.s, secs(0.3), 100, 3000, 9000, ctl(secs(0.3), [(0, 1), (0.3, 0)]))), 0.4)) * g

    def swish(self, d=0.3):
        return mix(pk(shaped(self.s, d, [(0, 500), (0.6, 2000), (1, 700)], [(0, 0), (0.6, 1), (1, 0)], 0.6, (7, 0.4))), (pk(tinkles(self.s, secs(d), 40, 4000, 9000)), 0.3))

    def fall(self):                              # implodes, the skull clatters
        out = mix((self.breath(0.5, True), 0.7), (boom(self.s, 40, 0.5, 0.12, 0.3), 0.8, 0.48))
        for j, at in enumerate((0.6, 0.74, 0.84)):
            place(out, bone(self.s, 700, 0.018), at, 0.6 - 0.15 * j)
        return out


class GlacierGiant(Kit):
    """빙하 거인: a massive sub-rumble voice, glacier groans, avalanches, huge ice cracks."""
    region, tempo, room = "frost", 1.25, 1.15
    VOX = dict(scale=0.52, tilt=0.7, breath=0.35, rasp=0.3, sharp=2.0, rlo=100, rhi=2500, sub=0.8, flutter=0.4, fmax=2800, bw=1.4)

    def call(self, d, shape="arch", k=1.0):      # rumbling groan + glacier creak
        sh = SHAPE[shape] if isinstance(shape, str) else shape
        g = self.v(d, fp(39 * self.p, shape, k), [(0, "o"), (1, "u")], amp_of(shape))
        cr = creak(self.s, d, 22 * k * sh[0][1], 22 * k * sh[-1][1], body=(60, 140, 300, 620), q=6, rough=0.35, wobble=1.5)
        return mix((g, 1.0), (cr, 0.6), (rumble(self.s, d, 30, 220, amp_of(shape)), 0.5))

    def crack(self, g=1.0):                      # a glacier crack: low glassy boom
        f = self.u(380, 520)
        return mix(pk(click(self.s, 0.06, 1200, 8000, 0.004)), (glass(self.s, f, 0.12), 0.8), (boom(self.s, 55, 0.5, 0.12, 0.6), 0.8)) * g

    def bark(self, k=1.0):
        return self.crack()

    def pain(self, d, shape="fall", k=1.0):
        return mix(self.crack(0.8), (self.v(d, fp(55, shape, k), [(0, "a"), (1, "u")], amp_of(shape), rasp=0.5), 1.0, 0.03))

    def avalanche(self, d, env="swell"):
        n = secs(d)
        return pk(norm(band(self.s.noise(n), 200, 3000)) * ctl(n, R(d, ENV[env])) * wob(self.s, n, 5, 0.5)
                  + pops(self.s, n, 120, 500, 4000, ctl(n, R(d, ENV[env])), (0.002, 0.007)) * 0.8)

    def breath(self, d, inhale=True):
        return self.avalanche(d, "build" if inhale else "fade")

    def tex(self, d, env="swell"):               # the glacier grinding
        return mix((creak(self.s, d, 18, 24, body=(60, 140, 300, 620), q=6, rough=0.4), 0.7), (rumble(self.s, d, 30, 240, ENV[env]), 0.8),
                   (crackle(self.s, d, 20, 1500, 7000, ENV[env], (0.002, 0.005)), 0.5))

    def sig(self, d=0.4):                        # an ice quake
        out = mix((rumble(self.s, d + 0.3, 25, 200, [(0, 0), (0.2, 1), (1, 0)]), 0.9))
        for at in np.linspace(0.02, d, 3):
            place(out, self.crack(self.u(0.5, 0.9)), at, 1.0)
        return out

    def hit(self, g=1.0):                        # colossal stomp
        return mix(boom(self.s, 38, 0.8, 0.2, 0.7), (self.crack(0.8), 0.8), (self.avalanche(0.7, "fade"), 0.6, 0.03)) * g

    def swish(self, d=0.35):
        return pk(shaped(self.s, d, [(0, 120), (0.6, 400), (1, 160)], [(0, 0), (0.6, 1), (1, 0)], 1.0, body=1.0))

    def fall(self):
        out = mix((self.avalanche(1.0, "decay"), 0.8), (boom(self.s, 34, 1.0, 0.25, 0.7), 1.0))
        for at in (0.05, 0.3, 0.55):
            place(out, self.crack(self.u(0.6, 0.9)), at, 0.8)
        return out


class Dragon(Kit):
    """서리 용 (boss): a huge layered roar with a screaming overtone, an icy breath of frost and glints,
    great leathery wing beats, snapping jaws."""
    region, tempo, room = "frost", 1.25, 1.15
    VOX = dict(scale=0.62, tilt=0.8, breath=0.3, rasp=0.8, sharp=3.0, rlo=150, rhi=5000, sub=0.7, flutter=0.5, fmax=5000, bw=1.3)

    def call(self, d, shape="arch", k=1.0):      # roar: chest + a screaming overtone + sub
        r = self.v(d, fp(92 * self.p, shape, k), [(0, "o"), (0.2, "a"), (1, "o")], amp_of(shape))
        sc = self.v(d, fp(92 * 4.1 * self.p, shape, k), "ae", amp_of(shape), scale=1.0, sub=0.0, rasp=0.6, rlo=800, rhi=7000, fmax=7000)
        n = secs(d)
        sub = pk(glide(n, ctl(n, R(d, fp(46, shape, k)))) * ctl(n, R(d, amp_of(shape))))
        return mix((r, 1.0), (sc, 0.3), (sub, 0.35))

    def snap(self, k=1.0):
        f = 700 * k * self.p
        return mix(pk(np.asarray(modal([f, f * 1.6, f * 2.5], [0.025, 0.015, 0.01], [1, 0.6, 0.3], 0.12, self.s.rng))), (pk(click(self.s, 0.03, 1200, 8000, 0.002)), 0.8))

    def bark(self, k=1.0):                       # snap-snarl
        return mix(self.snap(k), (self.v(0.2, [(0, 120 * k), (1, 100 * k)], "a", [(0, 0), (0.05, 1), (1, 0)]), 0.8, 0.02))

    def pain(self, d, shape="fall", k=1.0):      # roar-shriek: the scream on top
        r = self.v(d, fp(130 * self.p, shape, k), "a", amp_of(shape))
        sc = self.v(d, fp(130 * 4.1 * self.p, shape, k), "ae", amp_of(shape), scale=1.0, sub=0.0, rlo=800, rhi=7000, fmax=7000)
        return mix((r, 1.0), (sc, 0.6))

    def icebreath(self, d, env="swell"):         # frost spray: hiss sweeping, glints, crackle, a low roar of air
        n = secs(d)
        e = ctl(n, R(d, ENV[env] if isinstance(env, str) else env))
        h = pk(nsweep(self.s, n, ctl(n, R(d, [(0, 2500), (0.3, 5500), (1, 4000)])), 0.9) * e)
        return mix((h, 1.0), (pk(tinkles(self.s, n, 140, 3000, 9500, e)), 0.5), (pk(pops(self.s, n, 120, 2000, 9000, e, (0.0008, 0.002))), 0.4),
                   (pk(norm(band(self.s.noise(n), 150, 700)) * e), 0.5))

    def breath(self, d, inhale=True):
        if inhale:
            return pk(breathy(self.s, d, R(d, [(0, 300), (1, 1500)]), R(d, IN_AMP), 0.9))
        return self.icebreath(d, OUT_AMP)

    def wings(self, n=2, rate=1.6, size=2.6):
        out = buf(n / rate + 0.6)
        for j in range(n):
            place(out, flap(self.s, size * self.u(0.92, 1.08)), j / rate, self.u(0.8, 1.0))
        return out

    def tex(self, d, env="swell"):               # rumbling growl + leathery wing rustle
        g = self.v(d, [(0, 58), (1, 55)], "o", ENV[env], rasp=0.6, flutter=0.85, breath=0.4, fmax=3000)
        return mix((g, 0.9), (pk(band(self.s.noise(secs(d)), 300, 2500) * wob(self.s, secs(d), 4, 0.8) * ctl(secs(d), R(d, ENV[env]))), 0.3))

    def sig(self, d=0.4):
        return self.wings(max(1, int(d * 2.2) + 1), 2.2)

    def hit(self, g=1.0):                        # bite + weight
        return mix(self.snap(0.9), (boom(self.s, 50, 0.6, 0.14, 0.6), 0.9), (pk(tinkles(self.s, secs(0.4), 60, 3000, 9000, ctl(secs(0.4), [(0, 1), (0.4, 0)]))), 0.3)) * g

    def swish(self, d=0.4):                      # tail sweep
        return pk(shaped(self.s, d, [(0, 150), (0.6, 600), (1, 200)], [(0, 0), (0.6, 1), (1, 0)], 1.0, body=1.0))

    def fall(self):
        return mix(boom(self.s, 36, 1.0, 0.25, 0.7), (self.icebreath(0.9, "fade"), 0.4, 0.1), (pk(tinkles(self.s, secs(0.9), 80, 2500, 9000, ctl(secs(0.9), [(0, 1), (0.9, 0)]))), 0.4, 0.05))

    def custom(self, ev, a):
        if ev == "strike" and a == 3:            # breath attack: inhale, frost spray
            return mix((self.breath(0.25, True), 0.6), (self.icebreath(0.7, [(0, 0), (0.05, 1), (0.6, 0.7), (1, 0)]), 1.0, 0.22))
        return None

    def roar(self, a):
        if a == 0:      # rising-falling roar with the scream
            return mix((self.call(2.0, [(0, 0.8), (0.35, 1.25), (0.7, 1.15), (1, 0.7)], 1.0), 1.0), (rumble(self.s, 2.2, 25, 180, ENV["swell"]), 0.5))
        if a == 1:      # inhale, roar, icy breath tail
            return mix((self.breath(0.45, True), 0.6), (self.call(1.3, "arch", 1.05), 1.0, 0.4), (self.icebreath(1.0, OUT_AMP), 0.6, 1.4))
        if a == 2:      # two roars, the second higher
            return mix((self.call(0.9, "fall", 0.95), 1.0), (self.call(1.3, "rise", 1.15), 1.0, 0.95), (self.wings(1, 1.0, 2.8), 0.5, 0.75))
        # a growl builds into the roar
        return mix((self.tex(1.0, "build"), 0.8), (self.call(1.5, "dip", 1.1), 1.0, 0.85), (rumble(self.s, 2.4, 25, 200, ENV["build"]), 0.4))

    def intro(self, a):
        # great wing beats approaching over a swelling rumble, the roar, frost breath
        n_w, lead = [(3, 1.2), (2, 0.9), (4, 1.5)][a]
        out = mix((rumble(self.s, lead + 0.9, 25, 200, [(0, 0), (0.7, 1), (1, 0)]), 0.8))
        for j in range(n_w):
            place(out, flap(self.s, 2.8 * self.u(0.92, 1.08)), j * lead / n_w, 0.5 + 0.5 * (j + 1) / n_w)
        place(out, self.call([1.2, 1.5, 1.0][a], ["rise", "arch", "step"][a], 1.0), lead, 1.0)
        place(out, self.icebreath([0.8, 0.6, 0.9][a], OUT_AMP), lead + [1.05, 1.35, 0.9][a], 0.55)
        return out


KITS = {"goblin": Goblin, "harpy": Harpy, "centipede": Centipede, "werewolf": Werewolf, "troll": Troll, "cyclops": Cyclops,
        "treant": Treant, "skeleton": Skeleton, "imp": Imp, "lizardman": Lizardman, "mimic": Mimic, "basilisk": Basilisk,
        "naga": Naga, "gargoyle": Gargoyle, "minotaur": Minotaur, "mummy_king": MummyKing, "chimera": Chimera,
        "ghoul": Ghoul, "frost_wraith": FrostWraith, "ice_shardling": IceShardling, "draugr": Draugr, "yeti": Yeti,
        "wendigo": Wendigo, "frost_hag": FrostHag, "frost_knight": FrostKnight, "ice_golem": IceGolem, "lich": Lich,
        "glacier_giant": GlacierGiant, "dragon": Dragon}


# =============================================================================== render
LAYER_EV = {"roar": "alert", "intro": "alert"}


def take_fn(species, spec, ev):
    region = spec["map"]

    def fn(s, k):
        K = KITS[species](s, spec)
        a = k % (BOSS_EVENTS.get(ev, TAKES))
        x = K.custom(ev, a)
        if x is None:
            x = getattr(K, ev)(a) if ev in BOSS_EVENTS else EVENT_FN[ev](K, a)
        x = tidy(np.asarray(x, float), -50.0, 0.05)
        if K.layer:
            y = C.region_layer(s, x, region, LAYER_EV.get(ev, ev), species)
            x = x + (y - x) * K.layer
        rt, wet, tone, early = C.REGION_ROOM[region]
        x = V.reverb(s, x, rt * K.room * (1.25 if ev in BOSS_EVENTS else 0.85), wet, 0.012, tone, early)
        x = tidy(x, -34.0 if ev not in BOSS_EVENTS else -42.0, 0.1)
        n = secs(CAP[ev])
        if x.size > n:                      # a long tail: fade it out by the cap instead of cutting it
            x = x[:n].copy()
            m = secs(0.12 if ev in ("strike", "hurt") else 0.25)
            x[-m:] *= np.cos(np.linspace(0, np.pi / 2, m)) ** 2
        return x
    return fn


def stand_in_ref(stand_in, ev):
    """Median st-rms of the stand-in's region-neutral takes for this event (+BOSS_DB on roar/intro)."""
    base = "alert" if ev in BOSS_EVENTS else ev
    pat = re.compile(r"%s_%s_\d+\.wav$" % (re.escape(stand_in), base))
    refs = sorted(p for p in CREAT.glob("%s_%s_*.wav" % (stand_in, base)) if pat.fullmatch(p.name))
    if not refs:
        return float(GC.EVENT_DB[base]) + (BOSS_DB if ev in BOSS_EVENTS else 0.0)
    return L.ref_db_of(refs) + (BOSS_DB if ev in BOSS_EVENTS else 0.0)


def families(only=(), events=()) -> list:
    cat = catalog()
    missing = [k for k in cat if k not in KITS and (not only or k in only)]
    if missing:
        raise SystemExit("gen_monsters: no Kit for %s" % ", ".join(missing))
    out = []
    for sp, spec in cat.items():
        if only and sp not in only:
            continue
        evs = EVENTS + (list(BOSS_EVENTS) if spec.get("tier") == "boss" else [])
        for ev in evs:
            if events and ev not in events:
                continue
            out.append((sp, spec, ev, BOSS_EVENTS.get(ev, TAKES)))
    return out


def clean_stale(out_dir: Path, event: str, n: int, dry: bool) -> list:
    """Remove this generator's own takes numbered past the new range (never a protected file)."""
    pat = re.compile(r"%s_(\d+)\.wav$" % re.escape(event))
    gone = []
    for p in out_dir.glob("%s_*.wav" % event):
        m = pat.fullmatch(p.name)
        if m and int(m.group(1)) > n and not L.protected(p):
            gone.append(p)
            if not dry:
                p.unlink()
                imp = p.with_name(p.name + ".import")
                if imp.exists():
                    imp.unlink()
    return gone


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma list of species")
    ap.add_argument("--events", default="", help="comma list of events (idle alert windup strike hurt death roar intro)")
    ap.add_argument("--out", default="", help="write into this folder instead of game/assets/sfx/creatures (scratch trials)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    only = {x for x in a.only.split(",") if x}
    events = {x for x in a.events.split(",") if x}
    fams = families(only, events)
    if a.list:
        for sp, spec, ev, n in fams:
            print("%-14s %-7s %-6s %-6s stand-in %-6s %d takes  ref %.1f dB" % (sp, spec["map"], spec["tier"], ev, spec["stand_in"], n,
                                                                              stand_in_ref(spec["stand_in"], ev)))
        return 0
    out_dir = Path(a.out) if a.out else CREAT
    out_dir.mkdir(parents=True, exist_ok=True)
    if not a.out and not L.BASE_REF:
        print("gen_monsters: note: SFX_BASE is not set, so every git-tracked take is protected; set "
              "SFX_BASE=merge-version-gate to re-render the committed takes in place", file=sys.stderr)
    total = 0
    for sp, spec, ev, n in fams:
        name = "%s_%s" % (sp, ev)
        print("== %s (%s, stand-in %s)" % (name, spec["map"], spec["stand_in"]))
        clean_stale(out_dir, name, n, a.dry_run)
        fn = take_fn(sp, spec, ev)
        meta = L.make_family(out_dir, name, n, lambda rng, i, fn=fn: to_sr(fn(S(rng), i - 1), SR22), sr=SR22,
                             ref_db=stand_in_ref(spec["stand_in"], ev), seed_base=SEED, start=1,
                             finish_kw={"max_dur": MAX_DUR[ev]}, dry_run=a.dry_run)
        total += sum(d["bytes"] for d in meta)
    print("gen_monsters: %d families, %.2f MB of takes" % (len(fams), total / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
