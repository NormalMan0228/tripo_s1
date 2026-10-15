"""Shared synthesis kit for gen_combat.py / gen_combat_creatures.py (combat, creatures, hero).

Everything renders at 32 kHz with the building blocks of tools/make_creature_sfx.py (imported, its
main() is never run) and tools/sfx/sfxlib.py; families are resampled to their output rate (22050 Hz
by default, 32000 Hz where brightness matters) right before sfxlib.finish() levels and fades them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for p in (str(HERE), str(HERE.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import sfxlib as L  # noqa: E402
import make_creature_sfx as C  # noqa: E402  (helpers only; never call C.main())

V = C.V
SR = C.SR                     # 32000: synthesis rate of the make_creature_sfx helpers
SR22 = L.DEFAULT_SR           # 22050
SR32 = L.BRIGHT_SR            # 32000

ctl, place, secs, T = C.ctl, C.place, C.secs, C.time
band, low, high, norm = C.band, C.low, C.high, C.norm
vocal, snarl, breathy, nsweep, glide = C.vocal, C.snarl, C.breathy, C.nsweep, C.glide
pops, tinkles, rock, debris, rustle, scrape, bloop, fire = C.pops, C.tinkles, C.rock, C.debris, C.rustle, C.scrape, C.bloop, C.fire
thud, click, modal = C.thud, C.click, C.modal


def S(rng):
    """A make_village_sfx.Synth that draws from the take's numpy Generator."""
    s = V.Synth(0)
    s.rng = rng
    return s


def buf(t):
    return np.zeros(secs(t))


def pk(x):
    """Peak-normalised float copy."""
    return L.norm_peak(np.asarray(x, float))


def u(s, a, b):
    return float(s.rng.uniform(a, b))


def rel(dur, pts):
    """Relative (0..1, value) points -> absolute seconds for ctl()."""
    return [(p * dur, v) for p, v in pts]


def shaped(s, dur, fc_pts, amp_pts, bw=0.55, flutter=(0.0, 0.0), tone=0.0, body=0.0, relative=True):
    """Noise swoosh: STFT band centred on fc(t), amplitude amp(t); optional AM flutter (Hz, depth),
    a thin whistle tone and a low air push. Points are relative (0..1) unless relative=False."""
    n = secs(dur)
    fp = rel(dur, fc_pts) if relative else fc_pts
    ap = rel(dur, amp_pts) if relative else amp_pts
    fc = ctl(n, fp)
    a = np.clip(ctl(n, ap), 0, None)
    if flutter[1]:
        hz, d = flutter
        a = a * (1 - d + d * np.abs(np.sin(np.pi * hz * T(n) + u(s, 0, 3))))
    x = nsweep(s, n, fc, bw) * a
    if tone:
        x = x + glide(n, fc * 1.4) * a ** 2 * tone
    if body:
        x = x + nsweep(s, n, np.maximum(fc * 0.35, 60), 0.5) * a * body
    return x


def burst(s, dur, lo, hi, tau, attack=0.0008):
    """Band-limited noise transient (smack, puff, scuff)."""
    n = secs(dur)
    t = T(n)
    return norm(band(s.noise(n), lo, hi)) * np.exp(-t / tau) * np.minimum(t / max(attack, 1e-5), 1)


def tok(s, f, tau=0.02, ratios=(1.0, 2.43, 3.87), dur=None):
    """Small struck body (bone, wood grip, stone head)."""
    dur = dur or max(0.06, tau * 7)
    return pk(np.asarray(modal([f * r for r in ratios], [tau / (1 + 0.6 * i) for i in range(len(ratios))],
                               [1.0, 0.5, 0.25, 0.15][: len(ratios)], dur, s.rng))
              + click(s, 0.02, min(f * 1.5, 9000), min(f * 10, 12000), 0.0015) * 0.6)


def room(s, x, rt=0.4, wet=0.08, tone=6000, early=()):
    return V.reverb(s, np.asarray(x, float), rt, wet, 0.008, tone, early)


def to_sr(x, sr_out):
    x = np.asarray(x, float)
    return L.resample(x, SR, sr_out) if sr_out != SR else x


def pitch_env(n, f, pts):
    """f * ctl(points) helper for vocal contours in absolute seconds."""
    return ctl(n, [(t, f * v) for t, v in pts])
