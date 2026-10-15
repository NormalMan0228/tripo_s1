"""make_world_steps: baked footstep takes for WorldAudio (world_audio.gd), plus the cloth/gear layer.

    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\make_world_steps.py            # every surface + cloth
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\make_world_steps.py --only snow,ice --scratch

Writes game/assets/sfx/steps/<surface>_<walk|run>_<n>.wav (n = 1..TAKES) and steps/cloth_<n>.wav,
22050 Hz mono 16-bit (tools/sfx conventions). --scratch renders into the scratch area instead.

One step is a list of contacts (heel, toe, flat plant, slide/scuff, drag, settle) rendered through a
surface model: band-limited grainy noise, a low body thump, resonant grit grains (crunch), resonant
modes (boards, rock, tile, ice), water (splash + bubbles), creaks and a small room for indoor floors.
Candidates come from a grid (sfxlib.cycle): 14 contact rhythms (7 per surface texture) x 3 tones
(band shift, sole formant, thump weight) x 5 grit/decay sizes, with small random detail on top;
diverse.py keeps the 14 that sfx_qa would not call near-identical. Running takes are
shorter, harder and brighter than walking ones.

Level: every surface is matched to its own file reference REF_DB (st-rms, 120 ms, 150 Hz high-pass);
world_audio.gd SURFACE_DB turns that back into the in-game balance of the earlier runtime synth
(measured by a numpy port of it: grass -15.0, sand -16.0, stone -14.8, wood -14.2, rock -19.0,
shallow -14.5 dBFS st-rms). Seeds are stable (sfxlib.take_seed), so a re-run renders the same files.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402
import diverse as D  # noqa: E402

SR = L.DEFAULT_SR
TAKES = 14
CLOTH_TAKES = 8
OUT = L.SFX_ROOT / "steps"

# File loudness per surface (st-rms dBFS). Hard, clicky floors sit lower so the limiter never has
# to squash their transient; world_audio.gd SURFACE_DB compensates.
REF_DB = {
    "grass": -16.5, "sand": -15.0, "stone": -17.0, "wood": -15.0, "rock": -17.0, "shallow": -14.0,
    "snow": -15.0, "ice": -18.0, "gravel": -15.0, "leaves": -15.0, "ash": -16.0, "dirt": -16.0,
    "planks": -16.0, "tile": -18.0, "rug": -18.0, "stairs": -16.0,
}
CLOTH_REF_DB = -20.0


# --------------------------------------------------------------------------- building blocks
def env_ad(n, attack, decay, end=4.0):
    """(1 - e^-t/a) * e^-t/d, tapered to zero at attack + end*decay (a contact dies out instead of
    leaving a long noise tail), peak-normalised, n samples."""
    t = np.arange(n) / SR
    e = (1.0 - np.exp(-t / max(attack, 1e-4))) * np.exp(-t / max(decay, 1e-4))
    stop = attack + end * decay
    e *= np.clip(1.0 - t / stop, 0.0, 1.0) ** 1.5
    m = float(e.max()) if n else 1.0
    return e / m if m > 0 else e


def grain_mod(rng, n, grain_s, depth):
    """Rough multiplicative texture: a random level per grain, slightly smoothed."""
    if depth <= 0 or n == 0:
        return np.ones(n)
    g = max(1, int(grain_s * SR))
    k = n // g + 2
    u = rng.random(k)
    lv = 1.0 - depth + depth * 2.4 * u * u
    x = np.repeat(lv, g)[:n]
    a = 0.3
    from scipy.signal import lfilter
    return lfilter([a], [1, -(1 - a)], x, zi=[x[0] * (1 - a)])[0]


def band_noise(rng, n, lo, hi, color="white", order=2):
    x = L.noise(n, rng, color)
    return L.bp(x, SR, lo, min(hi, SR * 0.45), order)


def thump(rng, n, f, tau, attack=0.004):
    t = np.arange(n) / SR
    f_t = f * (1.0 + 0.25 * np.exp(-t / 0.012))          # a slight downward pitch drop
    ph = 2 * np.pi * np.cumsum(f_t) / SR + rng.uniform(0, 2 * np.pi)
    return np.sin(ph) * np.exp(-t / tau) * np.minimum(1.0, t / attack)


def grit(rng, n, t0, spread, count, f_lo, f_hi, tau_lo, tau_hi, amp=1.0, shape=1.5, noise_mix=0.35):
    """`count` tiny resonant clicks (stones, crystals, twigs) between t0 and t0+spread s; their
    density falls off with `shape` (1 = even, >1 = bunched at the start)."""
    out = np.zeros(n)
    if count <= 0:
        return out
    for _ in range(int(count)):
        u = rng.random() ** shape
        at = int((t0 + u * spread) * SR)
        if at >= n:
            continue
        f = math.exp(rng.uniform(math.log(f_lo), math.log(f_hi)))
        tau = rng.uniform(tau_lo, tau_hi)
        m = min(n - at, int(tau * 6 * SR) + 8)
        t = np.arange(m) / SR
        g = np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / tau)
        k = min(m, 24)
        g[:k] += rng.standard_normal(k) * np.exp(-np.arange(k) / 5.0) * noise_mix
        out[at:at + m] += g * amp * rng.uniform(0.25, 1.0) * (1.0 - 0.6 * u)
    return out


def creak(rng, n, t0, dur, f0, f1, rate_hz, amp):
    """Stick-slip creak: a pulse train (rate gliding) through a formant around f0..f1."""
    out = np.zeros(n)
    a = int(t0 * SR)
    m = min(n - a, int(dur * SR))
    if m <= 16:
        return out
    t = np.arange(m) / SR
    rate = rate_hz * (1 + 0.35 * np.sin(np.pi * t / dur + rng.uniform(-0.5, 0.5)))
    ph = np.cumsum(rate) / SR
    pulses = (np.diff(np.floor(ph), prepend=0) > 0).astype(float) * rng.uniform(0.6, 1.0, m)
    body = L.resonate(pulses, SR, [f0, (f0 + f1) * 0.5 * 1.9, f1 * 2.7], [0.006, 0.004, 0.003], [1.0, 0.5, 0.3])
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7
    out[a:a + m] = body * e * amp
    return out


def bubbles(rng, n, t0, spread, count, amp):
    out = np.zeros(n)
    for _ in range(int(count)):
        at = int((t0 + rng.uniform(0.0, spread)) * SR)
        f0 = rng.uniform(420, 1400)
        m = min(n - at, int(rng.uniform(0.018, 0.05) * SR))
        if m <= 8:
            continue
        u = np.arange(m) / m
        ph = 2 * np.pi * np.cumsum(f0 * (1 + rng.uniform(0.6, 1.2) * u)) / SR
        out[at:at + m] += np.sin(ph) * (1 - u) * np.minimum(u * 20, 1) * amp * rng.uniform(0.4, 1.0)
    return out


# --------------------------------------------------------------------------- contact patterns
# (kind, time s, amplitude). Times are jittered +-12 % per take, amplitudes +-10 %.
WALK_PATTERNS = [
    [("heel", 0.0, 1.0), ("toe", 0.040, 0.55)],
    [("heel", 0.0, 1.0), ("toe", 0.088, 0.42)],
    [("flat", 0.0, 1.0)],
    [("heel", 0.0, 0.72), ("toe", 0.062, 1.0)],
    [("scuff", 0.0, 0.38), ("heel", 0.034, 1.0), ("toe", 0.086, 0.5)],
    [("heel", 0.0, 1.0), ("toe", 0.125, 0.62), ("drag", 0.150, 0.3)],
    [("heel", 0.0, 1.0), ("toe", 0.024, 0.75), ("settle", 0.150, 0.32)],
]
RUN_PATTERNS = [
    [("heel", 0.0, 1.0), ("toe", 0.036, 0.8)],
    [("toe", 0.0, 1.0), ("heel", 0.056, 0.4)],
    [("flat", 0.0, 1.0)],
    [("heel", 0.0, 1.0), ("toe", 0.072, 0.9)],
    [("scuff", 0.0, 0.5), ("flat", 0.042, 1.0)],
    [("heel", 0.0, 0.9), ("toe", 0.05, 1.0), ("drag", 0.11, 0.36)],
    [("toe", 0.0, 0.8), ("heel", 0.018, 1.0), ("settle", 0.125, 0.3)],
]


# --------------------------------------------------------------------------- surfaces
# Each surface: a base dict plus two texture variants (v0, v1) merged over it.
# noise: lo/hi Hz, color, attack/decay s, grain s, depth; thump: f Hz, tau s, amp;
# grit: count per contact, f range, tau range, spread s, amp; modes: [(f, tau, amp)] rung by the
# contact; room: (size, wet) for indoor floors; extra keys per surface below.
# The second texture uses its own 7 rhythms, so all 14 takes of a family have different contacts.
WALK_ALT = [
    [("heel", 0.0, 1.0), ("toe", 0.060, 0.35), ("settle", 0.170, 0.22)],
    [("flat", 0.0, 1.0), ("drag", 0.060, 0.3)],
    [("heel", 0.0, 0.9), ("toe", 0.105, 0.9)],
    [("scuff", 0.0, 0.45), ("heel", 0.060, 1.0)],
    [("heel", 0.0, 1.0), ("toe", 0.030, 0.5), ("toe", 0.095, 0.3)],
    [("toe", 0.0, 1.0)],
    [("heel", 0.0, 1.0), ("toe", 0.145, 0.65)],
]
RUN_ALT = [
    [("heel", 0.0, 1.0), ("toe", 0.026, 0.5), ("drag", 0.070, 0.3)],
    [("flat", 0.0, 1.0), ("settle", 0.075, 0.35)],
    [("toe", 0.0, 1.0), ("heel", 0.090, 0.7)],
    [("scuff", 0.0, 0.35), ("heel", 0.025, 1.0), ("toe", 0.060, 0.6)],
    [("heel", 0.0, 1.0)],
    [("toe", 0.0, 0.9), ("toe", 0.040, 0.5)],
    [("heel", 0.0, 0.8), ("toe", 0.100, 1.0)],
]


SURF = {
    "grass": dict(noise=dict(lo=800, hi=6500, color="white", attack=0.010, decay=0.034, grain=0.003, depth=0.8, amp=1.0),
                  thump=dict(f=(60, 80), tau=0.03, amp=0.45),
                  grit=dict(count=10, f=(2600, 4200), tau=(0.0008, 0.0016), spread=0.07, amp=0.35),
                  var=[dict(), dict(noise=dict(lo=1300, hi=8000, decay=0.042, grain=0.0018), blades=True,
                                    grit=dict(count=26, f=(3500, 6500), spread=0.11, amp=0.45), thump=dict(amp=0.3))]),
    "sand": dict(noise=dict(lo=250, hi=2400, color="pink", attack=0.018, decay=0.06, grain=0.0011, depth=0.95, amp=1.0),
                 thump=dict(f=(48, 62), tau=0.035, amp=0.55),
                 grit=dict(count=0),
                 var=[dict(), dict(noise=dict(lo=420, hi=3600, decay=0.08, grain=0.0007), pour=True, thump=dict(amp=0.35))]),
    "stone": dict(noise=dict(lo=700, hi=4500, color="white", attack=0.0025, decay=0.032, grain=0.0045, depth=0.9, amp=0.8),
                  thump=dict(f=(85, 110), tau=0.028, amp=0.7),
                  grit=dict(count=14, f=(2200, 4200), tau=(0.0012, 0.0025), spread=0.05, amp=0.7),
                  modes=[((1500, 2400), 0.006, 0.35)],
                  var=[dict(), dict(noise=dict(lo=1100, hi=6500, decay=0.024), grit=dict(count=34, f=(3200, 7000), spread=0.09, amp=0.6),
                                    modes=[((2600, 3600), 0.004, 0.45)], thump=dict(amp=0.5))]),
    "wood": dict(noise=dict(lo=1500, hi=6000, color="white", attack=0.0015, decay=0.012, grain=0.0, depth=0.0, amp=0.35),
                 thump=dict(f=(70, 90), tau=0.03, amp=0.4),
                 grit=dict(count=3, f=(2000, 3500), tau=(0.001, 0.002), spread=0.03, amp=0.25),
                 modes=[((115, 160), 0.085, 1.0), ((265, 380), 0.05, 0.6), ((560, 760), 0.03, 0.55), ((1500, 1900), 0.015, 0.3)],
                 var=[dict(), dict(modes=[((150, 205), 0.06, 1.0), ((420, 520), 0.04, 0.7), ((900, 1150), 0.022, 0.5), ((2100, 2600), 0.01, 0.3)],
                                   rattle=True)]),
    "rock": dict(noise=dict(lo=1500, hi=8000, color="white", attack=0.001, decay=0.010, grain=0.0, depth=0.0, amp=0.6),
                 thump=dict(f=(80, 100), tau=0.022, amp=0.8),
                 grit=dict(count=12, f=(2500, 6000), tau=(0.0006, 0.0015), spread=0.05, amp=0.6),
                 modes=[((750, 1050), 0.024, 0.55), ((1300, 1800), 0.016, 0.4), ((1950, 2700), 0.01, 0.3)],
                 var=[dict(), dict(modes=[((480, 640), 0.03, 0.6), ((1100, 1350), 0.02, 0.45), ((2900, 3800), 0.008, 0.35)],
                                   grit=dict(count=28, spread=0.1, amp=0.5), pebble=True)]),
    "shallow": dict(noise=dict(lo=450, hi=5000, color="white", attack=0.008, decay=0.09, grain=0.0018, depth=0.9, amp=1.0),
                    thump=dict(f=(85, 100), tau=0.03, amp=0.5),
                    grit=dict(count=0), splash=dict(bubbles=(4, 7), spread=0.22, slosh=0.25),
                    var=[dict(), dict(noise=dict(lo=700, hi=6500, decay=0.07, grain=0.0012), splash=dict(bubbles=(9, 14), spread=0.3, slosh=0.5),
                                      thump=dict(amp=0.3))]),
    # new surfaces ------------------------------------------------------------------------
    "snow": dict(noise=dict(lo=300, hi=3000, color="pink", attack=0.02, decay=0.07, grain=0.004, depth=0.95, amp=0.55),
                 thump=dict(f=(45, 60), tau=0.04, amp=0.5),
                 grit=dict(count=45, f=(900, 3200), tau=(0.0015, 0.004), spread=0.14, amp=0.55, shape=1.1),
                 var=[dict(), dict(squeak=True, grit=dict(count=70, f=(1400, 4500), spread=0.18, amp=0.5), noise=dict(lo=500, hi=4200))]),
    "ice": dict(noise=dict(lo=2500, hi=9000, color="white", attack=0.0008, decay=0.008, grain=0.0, depth=0.0, amp=0.5),
                thump=dict(f=(70, 95), tau=0.02, amp=0.45),
                grit=dict(count=4, f=(4000, 8000), tau=(0.0006, 0.0012), spread=0.03, amp=0.4),
                modes=[((1800, 2400), 0.05, 0.6), ((3100, 3900), 0.03, 0.45), ((5200, 6400), 0.018, 0.3)],
                var=[dict(), dict(slide=True, modes=[((1200, 1500), 0.07, 0.6), ((2600, 2900), 0.04, 0.4), ((4300, 4800), 0.02, 0.3)],
                                  crack=True)]),
    "gravel": dict(noise=dict(lo=900, hi=6000, color="white", attack=0.004, decay=0.04, grain=0.002, depth=0.9, amp=0.45),
                   thump=dict(f=(75, 95), tau=0.03, amp=0.55),
                   grit=dict(count=55, f=(2200, 6500), tau=(0.0008, 0.0022), spread=0.12, amp=0.8, shape=1.6),
                   var=[dict(), dict(grit=dict(count=90, f=(1500, 4500), tau=(0.0012, 0.003), spread=0.16, amp=0.7, shape=1.2),
                                     roll=True, noise=dict(lo=600, hi=4500))]),
    "leaves": dict(noise=dict(lo=1200, hi=9000, color="white", attack=0.006, decay=0.05, grain=0.0025, depth=0.97, amp=0.6),
                   thump=dict(f=(55, 75), tau=0.035, amp=0.45),
                   grit=dict(count=40, f=(1800, 7000), tau=(0.0004, 0.0012), spread=0.13, amp=0.7, shape=1.3, noise_mix=1.2),
                   var=[dict(), dict(twig=True, grit=dict(count=60, f=(1200, 5000), spread=0.17), noise=dict(lo=900, hi=7000, decay=0.07))]),
    "ash": dict(noise=dict(lo=200, hi=2200, color="pink", attack=0.016, decay=0.05, grain=0.0016, depth=0.95, amp=1.0),
                thump=dict(f=(45, 60), tau=0.03, amp=0.45),
                grit=dict(count=16, f=(2200, 5500), tau=(0.0006, 0.0014), spread=0.14, amp=0.45, shape=1.0, noise_mix=0.8),
                var=[dict(), dict(puff=True, grit=dict(count=18, f=(1800, 4200), amp=0.4), noise=dict(lo=150, hi=1500, decay=0.08))]),
    "dirt": dict(noise=dict(lo=180, hi=1600, color="pink", attack=0.012, decay=0.045, grain=0.002, depth=0.85, amp=0.7),
                 thump=dict(f=(55, 75), tau=0.04, amp=0.9),
                 grit=dict(count=10, f=(700, 1800), tau=(0.002, 0.004), spread=0.08, amp=0.5, shape=1.4),
                 var=[dict(), dict(clods=True, grit=dict(count=16, f=(500, 1300), spread=0.12), noise=dict(lo=250, hi=2200, decay=0.06))]),
    "planks": dict(noise=dict(lo=1800, hi=6500, color="white", attack=0.0012, decay=0.01, grain=0.0, depth=0.0, amp=0.4),
                   thump=dict(f=(85, 105), tau=0.025, amp=0.45),
                   grit=dict(count=2, f=(2500, 4000), tau=(0.001, 0.002), spread=0.03, amp=0.2),
                   modes=[((180, 240), 0.05, 1.0), ((420, 540), 0.035, 0.6), ((900, 1200), 0.02, 0.45), ((2200, 2800), 0.009, 0.25)],
                   room=(0.18, 0.22),
                   var=[dict(), dict(creak=True, modes=[((130, 165), 0.06, 1.0), ((330, 400), 0.04, 0.55), ((720, 880), 0.024, 0.45), ((1700, 2100), 0.01, 0.25)])]),
    "tile": dict(noise=dict(lo=2500, hi=9000, color="white", attack=0.0008, decay=0.006, grain=0.0, depth=0.0, amp=0.6),
                 thump=dict(f=(95, 120), tau=0.018, amp=0.35),
                 grit=dict(count=3, f=(4000, 7000), tau=(0.0005, 0.001), spread=0.02, amp=0.3),
                 modes=[((1900, 2500), 0.012, 0.6), ((3300, 4200), 0.008, 0.45)],
                 room=(0.28, 0.32),
                 var=[dict(), dict(modes=[((1300, 1600), 0.016, 0.55), ((2700, 3100), 0.01, 0.45), ((5000, 5800), 0.006, 0.3)], heel_tap=True)]),
    "rug": dict(noise=dict(lo=150, hi=1600, color="pink", attack=0.012, decay=0.035, grain=0.003, depth=0.6, amp=0.8),
                thump=dict(f=(60, 80), tau=0.03, amp=0.8),
                grit=dict(count=0), room=(0.12, 0.12),
                var=[dict(), dict(brush=True, noise=dict(lo=300, hi=2600, decay=0.05))]),
    "stairs": dict(noise=dict(lo=1500, hi=6000, color="white", attack=0.0015, decay=0.012, grain=0.0, depth=0.0, amp=0.35),
                   thump=dict(f=(65, 85), tau=0.04, amp=0.6),
                   grit=dict(count=2, f=(2000, 3500), tau=(0.001, 0.002), spread=0.03, amp=0.2),
                   modes=[((88, 120), 0.11, 1.0), ((240, 320), 0.06, 0.7), ((600, 760), 0.03, 0.45), ((1400, 1800), 0.014, 0.25)],
                   room=(0.3, 0.26),
                   var=[dict(), dict(creak=True, rattle=True, modes=[((110, 140), 0.09, 1.0), ((300, 360), 0.05, 0.6), ((780, 950), 0.026, 0.45), ((1900, 2300), 0.01, 0.25)])]),
}
SURFACES = list(SURF)


def merged(surface: str, v: int) -> dict:
    base = {k: (dict(val) if isinstance(val, dict) else val) for k, val in SURF[surface].items() if k != "var"}
    for k, val in SURF[surface]["var"][v].items():
        if isinstance(val, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **val}
        else:
            base[k] = val
    return base


# --------------------------------------------------------------------------- one step
CONTACT = {   # per contact kind: noise attack x, decay x, brightness x, thump x, grit x, modes x
    "heel":   (0.6, 0.85, 1.15, 1.0, 0.8, 1.0),
    "toe":    (1.2, 1.1, 0.9, 0.45, 1.2, 0.7),
    "flat":   (1.0, 1.25, 1.0, 1.1, 1.0, 1.0),
    "scuff":  (6.0, 0.9, 1.25, 0.0, 0.6, 0.15),
    "drag":   (4.0, 1.6, 1.1, 0.0, 0.8, 0.1),
    "settle": (3.0, 1.4, 0.85, 0.3, 1.3, 0.3),
}


def render_step(rng, surface: str, v: int, pattern, hard: float, i: int, shift: float = 1.0, gshift: float = 1.0,
                formant: float = 1.0, weight: float = 1.0):
    """One footstep. From the take grid: shift scales the noise band and modes (shoe/surface size),
    gshift the grit grains' frequencies (stone size), formant places a +9 dB sole/ground resonance
    (x the surface's band centre) and weight scales the body thump. gshift also stretches the
    contacts' decay (a heavier, slower or a lighter, quicker plant)."""
    p = merged(surface, v)
    nz, th, gr = p["noise"], p["thump"], p.get("grit", {})
    dur = 0.55 if surface in ("shallow", "snow", "stairs") else 0.42
    n = L.secs(dur, SR)
    out = np.zeros(n)
    bright = 1.0 + 0.35 * hard
    tscale = rng.uniform(0.88, 1.12) * (1.0 - 0.15 * hard)
    f_th = rng.uniform(*th["f"]) * shift ** 0.5
    modes = [(rng.uniform(*fr) * shift, tau * (1.0 - 0.15 * hard), a) for fr, tau, a in p.get("modes", [])]
    for kind, t, amp in pattern:
        at_s = t * tscale * rng.uniform(0.9, 1.1)
        amp = amp * rng.uniform(0.9, 1.1)
        k_att, k_dec, k_br, k_th, k_gr, k_md = CONTACT[kind]
        att = nz["attack"] * k_att * (1.0 - 0.5 * hard)
        dec = nz["decay"] * k_dec * (1.0 - 0.25 * hard) * rng.uniform(0.9, 1.1) * gshift ** 0.9
        if kind in ("scuff", "drag"):
            dec = max(dec, 0.02)
        m = min(n - L.secs(at_s, SR), L.secs(min(dur, 6 * dec + att + 0.03), SR))
        if m <= 32:
            continue
        lo = nz["lo"] * (k_br ** 0.5) * (1.0 + 0.2 * hard) * shift
        hi = nz["hi"] * k_br * bright * shift
        x = band_noise(rng, m, lo, hi, nz.get("color", "white"))
        x = L.norm_peak(x) * env_ad(m, att, dec) * grain_mod(rng, m, nz.get("grain", 0.0) or 0.0, nz.get("depth", 0.0))
        # running: a harder, brighter strike and less of the slow weight roll
        seg = x * nz.get("amp", 1.0) * (0.8 + 0.5 * hard)
        if k_th > 0 and th["amp"] > 0:
            seg = seg + thump(rng, m, f_th * rng.uniform(0.97, 1.03), th["tau"] * (1.0 - 0.2 * hard), 0.002 + 0.004 * (1 - hard)) * th["amp"] * k_th * (1.1 - 0.4 * hard) * weight
        if modes and k_md > 0:
            ex = band_noise(rng, m, 300, 9000) * env_ad(m, 0.0004, 0.0025 * (1.2 - 0.5 * hard))
            body = L.resonate(ex, SR, [f for f, _, _ in modes], [tau for _, tau, _ in modes], [a for _, _, a in modes])
            seg = seg + body * k_md * (1.0 - 0.3 * hard)
        if gr.get("count", 0) > 0 and k_gr > 0:
            cnt = int(round(gr["count"] * k_gr * rng.uniform(0.75, 1.25) * (0.8 + 0.4 * hard)))
            seg = seg + grit(rng, m, 0.0, gr.get("spread", 0.06) * (1.0 - 0.3 * hard), cnt, gr["f"][0] * bright ** 0.5 * gshift, gr["f"][1] * bright ** 0.5 * gshift,
                             gr.get("tau", (0.001, 0.002))[0], gr.get("tau", (0.001, 0.002))[1], gr.get("amp", 0.5), gr.get("shape", 1.5),
                             gr.get("noise_mix", 0.35))
        L.place(out, seg * amp, at_s, SR)
    tail_at = max(t for _, t, _ in pattern) * tscale
    # surface extras ----------------------------------------------------------------------
    if p.get("blades"):          # long grass blades brushing past the shin
        m = L.secs(0.12, SR)
        sw = band_noise(rng, m, 2500, 9000) * env_ad(m, 0.03, 0.03) * grain_mod(rng, m, 0.004, 0.8)
        L.place(out, L.norm_peak(sw) * 0.35, rng.uniform(0.0, 0.03), SR)
    if p.get("pour"):            # dry sand sliding off the shoe
        m = L.secs(0.16, SR)
        po = band_noise(rng, m, 1200, 5000) * env_ad(m, 0.02, 0.05) * grain_mod(rng, m, 0.0012, 1.0)
        L.place(out, L.norm_peak(po) * 0.35, tail_at + rng.uniform(0.04, 0.08), SR)
    if p.get("rattle"):          # a loose board answering
        L.place(out, grit(rng, L.secs(0.08, SR), 0.0, 0.05, rng.integers(2, 4), 300, 700, 0.004, 0.009, 0.5, 1.0, 0.1),
                tail_at + rng.uniform(0.02, 0.05), SR)
    if p.get("pebble"):          # a pebble kicked loose
        L.place(out, grit(rng, L.secs(0.15, SR), 0.0, 0.12, rng.integers(2, 5), 2000, 4500, 0.002, 0.004, 0.45, 1.0),
                tail_at + rng.uniform(0.04, 0.09), SR)
    if p.get("splash"):
        sp = p["splash"]
        m = L.secs(0.42, SR)
        sl = band_noise(rng, m, 300, 2200) * env_ad(m, 0.03, 0.08) * grain_mod(rng, m, 0.006, 0.7)
        L.place(out, L.norm_peak(sl) * sp["slosh"], rng.uniform(0.03, 0.07), SR)
        L.place(out, bubbles(rng, m, 0.01, sp["spread"] * (1 - 0.3 * hard), rng.integers(*sp["bubbles"]), 0.32), 0.0, SR)
    if p.get("squeak"):          # cold snow squeak
        m = L.secs(0.1, SR)
        f0 = rng.uniform(900, 1500)
        tt = np.arange(m) / SR
        sq = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.15 * np.sin(2 * np.pi * rng.uniform(25, 45) * tt))) / SR)
        sq *= (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * rng.uniform(70, 120) * tt))) * np.sin(np.pi * tt / tt[-1]) ** 2
        L.place(out, L.bp(sq, SR, 600, 4000) * 0.22, tail_at * 0.5 + rng.uniform(0.02, 0.05), SR)
    if p.get("slide"):           # a short skid on ice
        m = L.secs(0.09, SR)
        sk = band_noise(rng, m, 3000, 9500) * env_ad(m, 0.025, 0.03)
        L.place(out, L.norm_peak(sk) * 0.3, tail_at + rng.uniform(0.0, 0.03), SR)
    if p.get("crack"):           # a faint crackle in the ice
        L.place(out, grit(rng, L.secs(0.12, SR), 0.0, 0.09, rng.integers(3, 7), 3000, 7000, 0.0005, 0.001, 0.35, 1.0, 1.0),
                tail_at + rng.uniform(0.03, 0.07), SR)
    if p.get("roll"):            # gravel rolling away
        L.place(out, grit(rng, L.secs(0.18, SR), 0.0, 0.16, rng.integers(6, 12), 2500, 6000, 0.0008, 0.0016, 0.3, 0.8),
                tail_at + rng.uniform(0.04, 0.08), SR)
    if p.get("twig"):            # a small twig snapping under the foot
        m = L.secs(0.05, SR)
        tw = L.resonate(band_noise(rng, m, 500, 6000) * env_ad(m, 0.0003, 0.002), SR,
                        [rng.uniform(700, 1100), rng.uniform(1800, 2600)], [0.006, 0.004], [1.0, 0.6])
        L.place(out, tw * 0.55, rng.uniform(0.01, 0.05), SR)
    if p.get("puff"):            # ash puffing up
        m = L.secs(0.2, SR)
        pf = band_noise(rng, m, 150, 900, "pink") * env_ad(m, 0.05, 0.06)
        L.place(out, L.norm_peak(pf) * 0.4, tail_at + rng.uniform(0.0, 0.03), SR)
    if p.get("clods"):           # clods of soil tumbling
        L.place(out, grit(rng, L.secs(0.14, SR), 0.0, 0.1, rng.integers(2, 5), 250, 600, 0.006, 0.012, 0.6, 1.0, 0.2),
                tail_at + rng.uniform(0.03, 0.07), SR)
    if p.get("creak"):           # an old board creaking under the weight
        L.place(out, creak(rng, L.secs(0.2, SR), 0.0, rng.uniform(0.07, 0.12), rng.uniform(330, 520), rng.uniform(520, 760),
                           rng.uniform(140, 260), 0.3), tail_at * 0.5 + rng.uniform(0.01, 0.04), SR)
    if p.get("heel_tap"):        # hard heel clack on tile
        m = L.secs(0.03, SR)
        hc = L.resonate(band_noise(rng, m, 2000, 9000) * env_ad(m, 0.0002, 0.0012), SR, [rng.uniform(3800, 4800)], [0.004])
        L.place(out, hc * 0.4, rng.uniform(0.0, 0.004), SR)
    if p.get("brush"):           # fabric pile brushing the shoe
        m = L.secs(0.1, SR)
        br = band_noise(rng, m, 600, 3500) * env_ad(m, 0.03, 0.03) * grain_mod(rng, m, 0.003, 0.6)
        L.place(out, L.norm_peak(br) * 0.3, tail_at + rng.uniform(0.0, 0.03), SR)
    fc = math.sqrt(nz["lo"] * nz["hi"]) * shift * formant
    out = L.peaking(out, SR, min(fc, SR * 0.4), 9.0, 1.6)
    if p.get("room"):
        size, wet = p["room"]
        out = L.reverb(out, SR, room=size * rng.uniform(0.85, 1.15), wet=wet, rng=rng, predelay=0.004, tone=4000)
    return out


TONES = [(1.0, 1.0, 1.0), (0.82, 0.5, 1.5), (1.22, 1.9, 0.45)]   # (band shift, formant, thump weight)
GSHIFTS = [1.0, 0.72, 1.38, 0.86, 1.18]


def family_fn(surface: str, gait: str):
    sets = (WALK_PATTERNS, WALK_ALT) if gait == "walk" else (RUN_PATTERNS, RUN_ALT)

    def fn(rng, k):
        # candidate k: 14 contact rhythms (7 per texture) x 3 tones x 5 grit/decay sizes; the
        # first 14 candidates are 14 different rhythms. diverse.py keeps the ones that differ.
        pat_i, tone, gshift = L.cycle(k, list(range(7)), TONES, GSHIFTS)
        v = (k // 7) % 2
        patterns = sets[v]
        shift, formant, weight = tone
        hard = rng.uniform(0.1, 0.35) if gait == "walk" else rng.uniform(0.75, 0.95)
        x = render_step(rng, surface, v, patterns[pat_i], hard, k, shift, gshift, formant, weight)
        return x, {"pattern": pat_i, "texture": v, "tone": list(tone), "gshift": gshift}
    return fn


# --------------------------------------------------------------------------- cloth / gear layer
CLOTH = [  # swishes (count, spacing s), band, gear
    dict(sw=1, gap=0.0, lo=600, hi=5000, gear="buckle"),
    dict(sw=2, gap=0.055, lo=900, hi=7000, gear=None),
    dict(sw=1, gap=0.0, lo=400, hi=3500, gear="leather"),
    dict(sw=3, gap=0.04, lo=1200, hi=8000, gear=None),
    dict(sw=2, gap=0.09, lo=500, hi=4500, gear="pouch"),
    dict(sw=1, gap=0.0, lo=1500, hi=9000, gear="leather"),
    dict(sw=2, gap=0.025, lo=700, hi=6000, gear="buckle"),
    dict(sw=1, gap=0.0, lo=300, hi=2600, gear="pouch"),
]


def cloth_fn(rng, i):
    c = CLOTH[(i - 1) % len(CLOTH)]
    n = L.secs(0.32, SR)
    out = np.zeros(n)
    at = rng.uniform(0.0, 0.01)
    for s in range(c["sw"]):
        m = L.secs(rng.uniform(0.06, 0.13), SR)
        x = band_noise(rng, m, c["lo"], c["hi"]) * grain_mod(rng, m, 0.0025, 0.7)
        e = np.sin(np.pi * np.linspace(0, 1, m)) ** rng.uniform(1.2, 2.5)
        L.place(out, L.norm_peak(x * e) * rng.uniform(0.6, 1.0), at, SR)
        at += c["gap"] * rng.uniform(0.85, 1.15)
    g = c["gear"]
    if g == "buckle":
        for k in range(rng.integers(1, 3)):
            m = L.secs(0.06, SR)
            b = L.modal(SR, rng.uniform(2800, 4200), "metal", dur=0.06, rng=rng)
            L.place(out, b * rng.uniform(0.25, 0.4), rng.uniform(0.02, 0.1), SR)
    elif g == "leather":
        L.place(out, creak(rng, L.secs(0.16, SR), 0.0, rng.uniform(0.06, 0.12), rng.uniform(250, 380), rng.uniform(380, 520),
                           rng.uniform(90, 160), 0.45), rng.uniform(0.01, 0.05), SR)
    elif g == "pouch":
        L.place(out, grit(rng, L.secs(0.12, SR), 0.0, 0.08, rng.integers(3, 6), 1500, 3200, 0.0015, 0.003, 0.5, 1.2, 0.2),
                rng.uniform(0.02, 0.06), SR)
    return out


# --------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma list of surfaces and/or 'cloth' (default: all)")
    ap.add_argument("--gait", default="walk,run")
    ap.add_argument("--scratch", action="store_true", help="write to the scratch area, not the repo")
    ap.add_argument("--allow-overwrite", action="store_true",
                    help="re-render files this generator wrote before (never needed for git-tracked files)")
    args = ap.parse_args(argv)
    out = (L.SCRATCH / "world" / "steps") if args.scratch else OUT
    out.mkdir(parents=True, exist_ok=True)
    only = [s for s in args.only.split(",") if s] or SURFACES + ["cloth"]
    total = 0
    for s in only:
        if s == "cloth":
            meta = L.make_family(out, "cloth", CLOTH_TAKES, cloth_fn, sr=SR, ref_db=CLOTH_REF_DB, seed_base="world",
                                 allow_overwrite=args.allow_overwrite, verbose=False, finish_kw=dict(max_dur=0.3))
            total += sum(d["bytes"] for d in meta)
            print("cloth: %d takes, %.1f KB" % (len(meta), sum(d["bytes"] for d in meta) / 1024))
            continue
        for gait in args.gait.split(","):
            meta = D.diverse_family(out, "%s_%s" % (s, gait), TAKES, family_fn(s, gait), sr=SR, ref_db=REF_DB[s], seed_base="world",
                                    allow_overwrite=args.allow_overwrite, max_candidates=40,
                                    finish_kw=dict(max_dur=0.5 if gait == "walk" else 0.42, fade_out=0.025, trim_db=-50.0))
            b = sum(d["bytes"] for d in meta)
            total += b
            st = [d["st_db"] for d in meta]
            dur = [d["seconds"] for d in meta]
            print("%-8s %-4s %2d takes (%2d tried) %6.1f KB  dur %.2f-%.2f s  st %.1f..%.1f  worst sim %.3f" % (
                s, gait, len(meta), D.tried(meta), b / 1024, min(dur), max(dur), min(st), max(st), max(d["worst_sim"] for d in meta)), flush=True)
    print("TOTAL %.1f KB (%d bytes)" % (total / 1024, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
