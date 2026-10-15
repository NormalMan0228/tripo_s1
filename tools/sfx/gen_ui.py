"""gen_ui.py: RpgUi take families for game/assets/sfx/ui (tools/sfx, UI owner).

Soft cozy UI sounds in the style of the original ui/*.wav (tools/build_ui_sounds.py: wooden
ticks, small bell tones on a G-major pentatonic, filtered-noise swishes), 22.05 kHz mono 16-bit.
Every kind gets several structurally different takes (a cycle() grid of archetypes: body /
material, gesture or rhythm, pitch step, melodic motif, timbre, envelope shape) plus small random
detail. The originals ui/<kind>.wav stay untouched; takes are ui/<kind>_<n>.wav, each family
level-matched (120 ms st-rms) to the original of its kind or to a sibling original (REF_OF).

    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_ui.py                 # all families -> game/assets/sfx/ui
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_ui.py --only hover,click
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_ui.py --out <scratch dir>   # try-outs (copies the originals there)
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_ui.py --list

Never imports tools/build_ui_sounds.py (no main guard: importing it rewrites ui/*.wav).
Removes only its own stale untracked takes (<kind>_<m>.wav past the family size).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sfxlib as L  # noqa: E402

SR = L.DEFAULT_SR
UI = L.SFX_ROOT / "ui"
TAU = 2.0 * np.pi
PENTA = (0, 2, 4, 7, 9)          # G major pentatonic: G A B D E


def hz(step: float) -> float:
    """Pentatonic step above G4 (392 Hz): 5 = G5, 7 = B5, 9 = E6, 10 = G6, 12 = B6."""
    o, d = divmod(int(round(step)), 5)
    return 392.0 * 2.0 ** ((12 * o + PENTA[d]) / 12.0)


def tv(d: float) -> np.ndarray:
    return np.arange(L.secs(d, SR)) / SR


# ------------------------------------------------------------------------- primitives
# (partial multiple, amplitude, decay multiple)
TIMBRES = {
    "bell": ((1, 1, 1), (2.01, .35, .7), (3.02, .12, .5)),
    "glass": ((1, 1, 1), (2.32, .32, .55), (4.25, .14, .4), (6.63, .06, .3)),
    "marimba": ((1, 1, 1), (3.93, .32, .22), (9.2, .08, .1)),
    "kalimba": ((1, 1, 1), (5.92, .2, .18), (2.0, .06, .5)),
    "soft": ((1, 1, 1), (2, .1, .6)),
    "celesta": ((1, 1, 1), (2, .45, .6), (3, .2, .45), (4, .1, .35)),
    "musicbox": ((1, 1, 1), (2.76, .25, .45), (5.4, .1, .3)),
    "wood": ((1, 1, 1), (2.43, .42, .35), (3.87, .2, .22), (5.52, .1, .15)),
    "square": ((1, 1, 1), (3, .28, .8), (5, .12, .6), (7, .05, .5)),
}


def tone(f, dur, decay, timbre="bell", rng=None, attack=0.002, bend=0.0, bend_t=0.02, vib=0.0, vib_hz=6.0):
    """Struck tonal body: TIMBRES partials with their own decays. bend: relative pitch offset at
    the onset gliding to f (+ = falls into the note, - = scoops up), over bend_t s."""
    t = tv(dur)
    fc = f * (1.0 + bend * np.exp(-t / max(bend_t, 1e-4)))
    if vib:
        fc = fc * (1.0 + vib * np.sin(TAU * vib_hz * t))
    ph = TAU * np.cumsum(fc) / SR
    y = np.zeros(t.size)
    for m, a, dk in TIMBRES[timbre]:
        if f * m >= SR * 0.45:
            continue
        p0 = rng.uniform(0, TAU) if rng is not None else 0.0
        y += a * np.sin(m * ph + p0) * np.exp(-t / (decay * dk))
    return y * np.minimum(1.0, t / max(attack, 1e-4))


def seq(events, rng, timbre="bell", decay=0.14, attack=0.002):
    """events: (t, f, gain[, decay]) -> one mix of tones."""
    parts = []
    for ev in events:
        t0, f, g = ev[:3]
        dk = ev[3] if len(ev) > 3 else decay
        parts.append((tone(f, min(1.4, dk * 6.5 + 0.02), dk, timbre, rng, attack=attack), g, max(0.0, t0)))
    return L.mix(*parts)


def tick(f, decay=0.012, noise=0.4, rng=None, dur=None, nlp=7000.0, attack=0.0008):
    """The original UI tick: a sine body plus a shorter noise burst (low-passed)."""
    dur = dur or max(0.035, decay * 7)
    t = tv(dur)
    body = np.sin(TAU * f * t + rng.uniform(0, TAU)) * np.minimum(1, t / attack) * np.exp(-t / decay)
    n = rng.standard_normal(t.size) * np.minimum(1, t / 0.0005) * np.exp(-t / (decay * 0.35))
    return body + noise * L.lp(n, SR, nlp)


def knock(f, material, rng, tau, dur=None, click=None, bright=1.0):
    return L.modal(SR, f, material, dur=dur or max(0.04, tau * 7), rng=rng, tau=tau, click=click, bright=bright)


def burst(dur, rng, lo, hi, decay, attack=0.0008, color="white"):
    t = tv(dur)
    n = L.noise(t.size, rng, color)
    return L.bp(n, SR, lo, min(hi, SR * 0.44)) * np.minimum(1, t / attack) * np.exp(-t / decay)


def blip(f0, f1, dur, decay, rng, glide=0.02, harm=((1, 1.0),), attack=0.001):
    """Pitched sweep f0 -> f1 over `glide` s with an exponential decay (bubbles, beeps)."""
    t = tv(dur)
    f = f0 * (f1 / f0) ** np.minimum(1.0, t / max(glide, 1e-4))
    y = L.osc(SR, f, harm, phase=rng.uniform(0, TAU))
    return y * np.minimum(1, t / attack) * np.exp(-t / decay)


def shape_env(shape, dur, rng):
    n = L.secs(dur, SR)
    u = np.linspace(0, 1, n)
    t = u * dur
    if shape == "hump":
        e = np.sin(np.pi * u) ** 2
    elif shape == "rise":
        e = u ** 1.8 * np.clip((1 - u) / 0.12, 0, 1) ** 0.5
    elif shape == "fall":
        e = np.clip(u / 0.06, 0, 1) * (1 - u) ** 1.6
    elif shape == "early":
        e = (u / 0.25) * np.exp(1 - u / 0.25)
    elif shape == "late":
        e = (u / 0.7) ** 3 * np.exp(3 * (1 - u / 0.7))
    elif shape == "double":
        a = np.sin(np.pi * np.clip(u / 0.48, 0, 1)) ** 2 * 0.7
        b = np.sin(np.pi * np.clip((u - 0.4) / 0.6, 0, 1)) ** 2
        e = np.maximum(a, b)
    elif shape == "flutter":
        e = np.sin(np.pi * u) ** 2 * (0.55 + 0.45 * np.cos(TAU * rng.uniform(16, 24) * t))
    elif shape == "twopuff":
        a = np.sin(np.pi * np.clip(u / 0.4, 0, 1)) ** 2
        b = np.sin(np.pi * np.clip((u - 0.5) / 0.5, 0, 1)) ** 2 * 0.8
        e = a + b
    else:
        raise ValueError(shape)
    return e / (np.max(e) + 1e-12)


def swish(dur, rng, shape="hump", f0=900.0, f1=2400.0, q=0.8, color="white"):
    """Band-passed noise swell sweeping f0 -> f1."""
    n = L.secs(dur, SR)
    u = np.linspace(0, 1, n)
    y = L.svf(L.noise(n, rng, color), SR, f0 * (f1 / f0) ** u, q, "bp")
    return y * shape_env(shape, dur, rng)


def sparkle(dur, rng, density=40.0, lo=3000.0, hi=6500.0, env="fall", decay=0.03, timbre="soft"):
    """Scatter of tiny high tones (glitter)."""
    grain = lambda r: tone(r.uniform(lo, hi), decay * 5, decay * r.uniform(0.7, 1.3), timbre, r, attack=0.001)
    e = shape_env(env, dur, rng)
    return L.scatter(SR, dur, rng, grain, density=density, gain=(0.25, 1.0), env=e)


def paper(dur, rng, lo=1500.0, hi=6500.0, flutters=2, rate=150.0, decay=0.012):
    """Paper flick: band-passed noise with a few fast flutters."""
    t = tv(dur)
    n = L.bp(L.noise(t.size, rng, "white"), SR, lo, hi)
    am = 0.55 + 0.45 * np.cos(TAU * rate * t) if flutters > 1 else 1.0
    return n * am * np.minimum(1, t / 0.0015) * np.exp(-t / decay)


def thump(f, dur, rng, decay=0.03):
    """Soft low thump: a sine with a short pitch drop plus low noise."""
    t = tv(dur)
    y = blip(f * 1.5, f, dur, decay, rng, glide=0.012)
    n = L.lp(rng.standard_normal(t.size), SR, 700) * np.exp(-t / (decay * 0.5)) * 0.4
    return y + n


# ------------------------------------------------------------------------- families: core
def fam_hover(rng, i):
    body, step, gest = L.cycle(i, ("sine", "wood", "tine", "bubble"), (1.0, 1.19, 0.84, 1.41, 0.71),
                               ("single", "flam", "shimmer"))
    f = 1900 * step * rng.uniform(0.985, 1.015)

    def one(ff):
        if body == "sine":
            return L.lp(tick(ff, rng.uniform(0.009, 0.014), 0.25, rng, 0.06), SR, 6000)
        if body == "wood":
            return knock(ff, "wood", rng, rng.uniform(0.010, 0.016), 0.06, click=0.25)
        if body == "tine":
            return tone(ff, 0.07, rng.uniform(0.012, 0.02), "kalimba", rng, attack=0.0008)
        return blip(ff * 0.7, ff * 1.15, 0.06, 0.013, rng, glide=0.02)

    x = one(f)
    if gest == "flam":
        x = L.mix(x, (one(f * rng.uniform(1.12, 1.2)), 0.55, rng.uniform(0.010, 0.015)))
    elif gest == "shimmer":
        x = L.mix(x, (tone(f * rng.choice([1.5, 2.0]), 0.06, 0.02, "soft", rng), 0.3, rng.uniform(0.006, 0.012)))
    return L.lp(x, SR, 6000), {"arch": "%s/%.2f/%s" % (body, step, gest)}


def fam_click(rng, i):
    body, step, gest = L.cycle(i, ("wood", "pebble", "plastic", "sine"), (1.0, 1.18, 0.85, 1.38, 0.73),
                               ("single", "release", "flam"))
    f = 950 * step * rng.uniform(0.985, 1.015)

    def one(ff):
        if body == "wood":
            return knock(ff, "wood", rng, rng.uniform(0.018, 0.026), 0.09, click=0.35)
        if body == "pebble":
            return knock(ff, "stone", rng, rng.uniform(0.02, 0.03), 0.1, click=0.3)
        if body == "plastic":
            return L.mix(burst(0.04, rng, ff * 1.6, ff * 4, rng.uniform(0.004, 0.007)), (tick(ff, 0.008, 0.0, rng, 0.05), 0.9))
        return L.mix(tick(ff, 0.02, 0.6, rng, 0.09), (tick(ff * 1.58, 0.012, 0.2, rng, 0.09), 0.4))

    x = one(f)
    if gest == "release":
        x = L.mix(x, (one(f * rng.uniform(1.25, 1.35)), 0.45, rng.uniform(0.04, 0.065)))
    elif gest == "flam":
        x = L.mix(x, (one(f * rng.uniform(0.9, 0.95)), 0.6, rng.uniform(0.006, 0.01)))
    return L.lp(x, SR, 8000), {"arch": "%s/%.2f/%s" % (body, step, gest)}


def fam_open(rng, i):
    shape, motif, tim, dur = L.cycle(i, ("hump", "rise", "flutter", "early"), ("one", "up2", "up3"),
                                     ("bell", "glass", "kalimba", "celesta", "marimba"), (0.28, 0.24, 0.32, 0.21, 0.26))
    dur *= rng.uniform(0.95, 1.05)
    lo = rng.uniform(500, 800)
    sw = swish(dur, rng, shape, lo, lo * rng.uniform(2.2, 3.4), q=0.7, color="pink")
    root = int(rng.choice([6, 7, 8]))
    if motif == "one":
        ev = [(0.05, hz(root + 2), 1.0)]
    elif motif == "up2":
        ev = [(0.035, hz(root), 0.8), (0.035 + rng.uniform(0.06, 0.09), hz(root + 2), 1.0)]
    else:
        g = rng.uniform(0.04, 0.055)
        ev = [(0.03 + g * k, hz(root + k), 0.7 + 0.15 * k) for k in range(3)]
    bells = seq(ev, rng, tim, decay=rng.uniform(0.07, 0.1))
    return L.mix((sw, 0.6), (bells, 0.5)), {"arch": "%s/%s/%s" % (shape, motif, tim)}


def fam_close(rng, i):
    shape, motif, tim, dur = L.cycle(i, ("fall", "hump", "double", "late"), ("one", "down2", "down3"),
                                     ("bell", "marimba", "glass", "musicbox", "kalimba"), (0.26, 0.3, 0.22, 0.34, 0.24))
    dur *= rng.uniform(0.95, 1.05)
    hi = rng.uniform(1600, 2400)
    sw = swish(dur, rng, shape, hi, hi / rng.uniform(2.4, 3.4), q=0.7, color="pink")
    root = int(rng.choice([5, 6, 7]))
    dk = rng.uniform(0.06, 0.085)
    if motif == "one":
        ev = [(0.005, hz(root), 1.0)]
        at = 0.0
    elif motif == "down2":
        ev = [(0.0, hz(root + 3), 0.75), (rng.uniform(0.07, 0.1), hz(root + 1), 1.0)]
        at = 0.04
    else:
        g = rng.uniform(0.045, 0.06)
        ev = [(g * k, hz(root + 4 - 2 * k), 0.75 + 0.1 * k) for k in range(3)]
        at = 0.06
    bells = seq(ev, rng, tim, decay=dk)
    return L.mix((sw, 0.6, at), (bells, 0.4)), {"arch": "%s/%s/%s" % (shape, motif, tim)}


TOAST_MOTIFS = {"lift2": (0, 2), "lift1": (0, 1), "up3": (0, 1, 3), "grace": (-1, 0), "repeat": (0, 0), "dip": (0, -1, 2)}


def fam_toast(rng, i):
    motif, tim = L.cycle(i, tuple(TOAST_MOTIFS), ("bell", "glass", "kalimba", "celesta", "musicbox"))
    root = int(rng.choice([7, 8, 9, 10]))
    gap = rng.uniform(0.06, 0.11)
    steps = TOAST_MOTIFS[motif]
    ev, t = [], 0.0
    for k, s in enumerate(steps):
        if motif == "grace" and k == 0:
            ev.append((0.0, hz(root + s), 0.45, 0.05))
            t = rng.uniform(0.03, 0.045)
            continue
        g = 0.65 if (motif == "repeat" and k == 1) else (1.0 if k == 0 else 0.8)
        ev.append((t, hz(root + s), g, rng.uniform(0.12, 0.17)))
        t += gap * (0.8 if k else 1.0)
    return seq(ev, rng, tim), {"arch": "%s/%s/r%d" % (motif, tim, root)}


CONFIRM_MOTIFS = {"arp3": (0, 2, 4), "arp4": (0, 1, 2, 4), "octave": (0, 5), "turn": (0, 2, 1, 4)}
RHYTHMS = ((0.08, 0.08, 0.08), (0.055, 0.055, 0.11), (0.1, 0.07, 0.07), (0.045, 0.045, 0.045), (0.07, 0.12, 0.06))


def fam_confirm(rng, i):
    motif, tim, rhythm = L.cycle(i, tuple(CONFIRM_MOTIFS), ("celesta", "bell", "kalimba"), RHYTHMS)
    root = int(rng.choice([5, 6, 7]))
    steps = CONFIRM_MOTIFS[motif]
    ev, t = [], 0.0
    for k, s in enumerate(steps):
        last = k == len(steps) - 1
        ev.append((t, hz(root + s), 0.7 if last and len(steps) > 2 else 1.0, rng.uniform(0.12, 0.16)))
        t += rhythm[min(k, len(rhythm) - 1)] * rng.uniform(0.95, 1.05)
    x = seq(ev, rng, tim)
    if motif == "octave":
        x = L.mix(x, (sparkle(0.25, rng, 30, env="fall"), 0.18, t))
    return x, {"arch": "%s/%s/%s" % (motif, tim, rhythm)}


# ------------------------------------------------------------------------- new kinds: menus
def fam_deny(rng, i):
    pat, tim, f = L.cycle(i, ("pair", "step", "thud", "triple"), ("wood", "square", "marimba"), (330, 294, 370, 262, 349))
    f *= rng.uniform(0.99, 1.01)
    dk = 0.08 if tim == "marimba" else 0.06
    if pat == "pair":
        x = seq([(0, f, 1.0), (rng.uniform(0.11, 0.14), f, 0.75)], rng, tim, dk)
    elif pat == "step":
        x = seq([(0, f, 1.0), (rng.uniform(0.09, 0.12), f * 2 ** (-int(rng.choice([3, 4])) / 12), 0.85)], rng, tim, dk)
    elif pat == "thud":
        x = L.mix(thump(f * 0.4, 0.15, rng, 0.03), (tone(f, 0.3, dk * 1.2, tim, rng, bend=0.07, bend_t=0.05), 0.8, 0.012))
    else:
        x = seq([(0, f, 0.8), (0.055, f * 0.94, 0.7), (0.11, f * 0.89, 0.85)], rng, tim, dk * 0.8)
    return L.lp(x, SR, 2600), {"arch": "%s/%s/%d" % (pat, tim, f)}


def fam_tab(rng, i):
    gest, f, body = L.cycle(i, ("flick_tick", "tick_flick", "double"), (1500, 1850, 1250, 2200, 1650),
                            ("wood", "sine", "kalimba", "plastic"))
    f *= rng.uniform(0.99, 1.01)

    def tk(ff):
        if body == "wood":
            return knock(ff * 0.7, "wood", rng, 0.014, 0.07, click=0.4)
        if body == "sine":
            return tick(ff, 0.014, 0.3, rng, 0.07)
        if body == "kalimba":
            return tone(ff, 0.12, 0.03, "kalimba", rng, attack=0.001)
        return L.mix(burst(0.03, rng, ff * 1.4, ff * 4, 0.004), (tick(ff, 0.007, 0.0, rng, 0.04), 0.7))

    flick = paper(0.035, rng, 2500, 7000, 2, rng.uniform(130, 190), rng.uniform(0.005, 0.008))
    if gest == "flick_tick":
        x = L.mix((flick, 0.7), (tk(f), 1.0, rng.uniform(0.012, 0.02)))
    elif gest == "tick_flick":
        x = L.mix((tk(f), 1.0), (flick, 0.6, rng.uniform(0.02, 0.03)))
    else:
        x = L.mix((tk(f), 1.0), (tk(f * 1.19), 0.6, rng.uniform(0.028, 0.04)))
    return L.lp(x, SR, 8000), {"arch": "%s/%d/%s" % (gest, f, body)}


def fam_select(rng, i):
    step, tim, gest = L.cycle(i, (8, 10, 7, 11, 9), ("marimba", "kalimba", "wood"), ("single", "grace", "double", "tick"))
    f = hz(step)
    dk = rng.uniform(0.035, 0.05)
    if gest == "single":
        x = tone(f, 0.25, dk, tim, rng, attack=0.001)
    elif gest == "grace":
        x = seq([(0, hz(step - 1), 0.5, 0.025), (rng.uniform(0.025, 0.035), f, 1.0, dk)], rng, tim)
    elif gest == "double":
        x = seq([(0, f, 1.0, dk), (rng.uniform(0.05, 0.07), f, 0.45, dk)], rng, tim)
    else:
        x = L.mix(tick(f * 2, 0.005, 0.5, rng, 0.03), (tone(f, 0.25, dk, tim, rng), 0.9, 0.004))
    return x, {"arch": "%d/%s/%s" % (step, tim, gest)}


def fam_slider(rng, i):
    body, f, gest = L.cycle(i, ("click", "sine", "notch", "wood"), (2190, 1750, 3420, 1400, 2740), ("single", "double", "spring"))
    f *= rng.uniform(0.99, 1.01)

    def one(ff):
        if body == "click":
            return L.mix(burst(0.025, rng, ff * 0.8, ff * 2.5, 0.0025), (tick(ff, 0.004, 0.0, rng, 0.03), 0.6))
        if body == "sine":
            return tick(ff, 0.006, 0.3, rng, 0.035)
        if body == "notch":
            return blip(ff * 1.15, ff * 0.85, 0.035, 0.006, rng, glide=0.008)
        return knock(ff * 0.55, "wood", rng, 0.007, 0.04, click=0.6)

    x = one(f)
    if gest == "double":
        x = L.mix(x, (one(f * 1.2), 0.8, rng.uniform(0.018, 0.025)))
    elif gest == "spring":
        x = L.mix(x, (tone(f * 1.9, 0.09, 0.025, "soft", rng), 0.4, 0.004))
    return L.lp(x, SR, 7000), {"arch": "%s/%d/%s" % (body, f, gest)}


def slide(dur, rng, kind, up=True, band=1.0):
    """Drawer runner friction: band-passed pink noise sweeping, with rattle or roller texture."""
    n = L.secs(dur, SR)
    u = np.linspace(0, 1, n)
    t = u * dur
    a, b = rng.uniform(300, 420) * band, rng.uniform(800, 1100) * band
    f0, f1 = (a, b) if up else (b, a)
    y = L.svf(L.noise(n, rng, "pink"), SR, f0 * (f1 / f0) ** u, 1.1, "bp")
    y = y / (np.max(np.abs(y)) + 1e-9)
    if kind == "rattle":
        grain = lambda r: knock(r.uniform(900, 1600), "wood", r, 0.004, 0.02, click=0.8)
        y = y + 0.5 * L.pad_to(L.scatter(SR, dur, rng, grain, density=rng.uniform(55, 80), gain=(0.3, 1.0)), n)
    elif kind == "roller":
        y = y * (1 + 0.7 * np.sin(TAU * rng.uniform(26, 40) * t))
    env = np.clip(u / 0.25, 0, 1) ** 1.5 * np.clip((1 - u) / 0.05, 0, 1)
    return y * env


# drawer motions: (start, length, band) as fractions of the take's slide time
MOTIONS = {"pull": ((0.0, 1.0, 1.0),), "sticky": ((0.0, 0.5, 0.9), (0.68, 0.55, 1.25)), "quick": ((0.0, 0.6, 1.45),),
           "long": ((0.0, 1.35, 0.72),), "jerk": ((0.0, 0.32, 1.0), (0.4, 0.32, 1.1), (0.8, 0.4, 1.2))}


def drawer_slide(dur, rng, kind, motion, up):
    parts, end = [], 0.0
    for s0, ln, band in MOTIONS[motion]:
        parts.append((slide(dur * ln, rng, kind, up, band), 1.0, dur * s0))
        end = max(end, dur * (s0 + ln))
    return L.mix(*parts), end


def fam_drawer_open(rng, i):
    kind, end, motion = L.cycle(i, ("smooth", "rattle", "roller"), ("bump", "bell"), tuple(MOTIONS))
    s, dur = drawer_slide(0.17 * rng.uniform(0.95, 1.05), rng, kind, motion, True)
    if end == "bump":
        tail = knock(rng.uniform(180, 240), "wood", rng, 0.035, 0.16, click=0.3)
        x = L.mix((s, 0.8), (tail, 0.5, dur - 0.01))
    else:
        x = L.mix((s, 0.8), (tone(hz(int(rng.choice([8, 9]))), 0.4, 0.08, "kalimba", rng), 0.35, dur * 0.6))
    return x, {"arch": "%s/%s/%s" % (kind, end, motion)}


def fam_drawer_close(rng, i):
    kind, end, motion = L.cycle(i, ("smooth", "rattle", "roller"), ("shut", "rebound"), tuple(MOTIONS))
    s, dur = drawer_slide(0.13 * rng.uniform(0.95, 1.05), rng, kind, motion, False)
    f = rng.uniform(150, 210)
    shut = knock(f, "wood", rng, rng.uniform(0.04, 0.055), 0.2, click=0.5)
    x = L.mix((s, 0.7), (shut, 1.0, dur - 0.005))
    if end == "shut":
        x = L.mix(x, (tick(rng.uniform(1400, 1900), 0.008, 0.4, rng, 0.04), 0.35, dur + rng.uniform(0.02, 0.03)))
    else:
        x = L.mix(x, (knock(f * 1.12, "wood", rng, 0.03, 0.15, click=0.4), 0.35, dur + rng.uniform(0.055, 0.075)))
    return x, {"arch": "%s/%s/%s" % (kind, end, motion)}


def fam_count(rng, i):
    body, f, tail = L.cycle(i, ("metal", "glass", "coin2", "tink", "musicbox"), (3200, 3900, 2600), ("dry", "ring"))
    f *= rng.uniform(0.99, 1.01)
    ring = tail == "ring"
    if body == "metal":
        x = knock(f * 0.5, "metal", rng, 0.06 if ring else 0.02, 0.15 if ring else 0.07, click=0.2)
    elif body == "glass":
        x = tone(f, 0.15 if ring else 0.07, 0.04 if ring else 0.014, "glass", rng, attack=0.0006)
    elif body == "coin2":
        x = L.mix(knock(f * 0.5, "metal", rng, 0.02, 0.08, click=0.3),
                  (knock(f * 0.56, "metal", rng, 0.05 if ring else 0.02, 0.12, click=0.3), 0.6, rng.uniform(0.012, 0.018)))
    elif body == "tink":
        x = L.mix(burst(0.02, rng, f, f * 2, 0.003), (tone(f * 1.2, 0.12, 0.035 if ring else 0.01, "soft", rng), 0.8))
    else:
        x = tone(f * 0.8, 0.15, 0.045 if ring else 0.015, "musicbox", rng, attack=0.0008)
    return x, {"arch": "%s/%d/%s" % (body, f, tail)}


def coin(f, rng, tau=0.07):
    return knock(f, "metal", rng, tau, 0.3, click=0.25)


def fam_coin_gain(rng, i):
    coins, pattern, final = L.cycle(i, (2, 3, 4), ("even", "cascade"), ("bell", "sparkle", "fifth", "none", "glass"))
    t, parts, gaps = 0.0, [], (0.09, 0.06, 0.042)
    for k in range(coins):
        parts.append((coin(rng.uniform(1500, 2400), rng, rng.uniform(0.05, 0.09)), rng.uniform(0.6, 1.0), t))
        t += rng.uniform(0.06, 0.075) if pattern == "even" else gaps[min(k, 2)]
    x = L.mix(*parts)
    root = int(rng.choice([10, 11, 12]))
    if final == "bell":
        x = L.mix(x, (tone(hz(root), 0.6, 0.14, "bell", rng), 0.6, t + 0.02))
    elif final == "sparkle":
        x = L.mix(x, (sparkle(0.3, rng, 45, env="fall"), 0.35, t))
    elif final == "fifth":
        x = L.mix(x, (seq([(0, hz(root), 1.0), (0.07, hz(root + 3), 0.8)], rng, "celesta", 0.12), 0.55, t + 0.01))
    elif final == "glass":
        x = L.mix(x, (tone(hz(root + 1), 0.6, 0.12, "glass", rng), 0.5, t + 0.02))
    return x, {"arch": "%d/%s/%s" % (coins, pattern, final)}


# ------------------------------------------------------------------------- new kinds: social
def bubble(f, rng, dur=0.07, decay=0.022):
    return blip(f * 0.6, f * 1.2, dur, decay, rng, glide=0.03)


def fam_chat_in(rng, i):
    bubs, ding, tim = L.cycle(i, (1, 2), ("high", "two_up", "fifth", "two_down", "grace"), ("kalimba", "bell", "glass"))
    f = rng.uniform(650, 900)
    x = bubble(f, rng)
    at = 0.045
    if bubs == 2:
        x = L.mix(x, (bubble(f * 1.3, rng), 0.8, rng.uniform(0.05, 0.065)))
        at = 0.1
    root = int(rng.choice([8, 9, 10]))
    ev = {"high": [(0, hz(root + 2), 1.0)],
          "two_up": [(0, hz(root), 0.8), (0.075, hz(root + 2), 1.0)],
          "fifth": [(0, hz(root), 1.0), (0.06, hz(root + 3), 0.7)],
          "two_down": [(0, hz(root + 2), 1.0), (0.08, hz(root), 0.8)],
          "grace": [(0, hz(root + 1), 0.45, 0.04), (0.035, hz(root + 2), 1.0)]}[ding]
    return L.mix((x, 0.7), (seq(ev, rng, tim, 0.12), 0.6, at)), {"arch": "%d/%s/%s" % (bubs, ding, tim)}


def fam_chat_out(rng, i):
    shape, pop, f = L.cycle(i, ("rise", "flutter", "double"), ("blip", "tick"), (900, 1200, 750, 1400, 1050))
    dur = rng.uniform(0.07, 0.11)
    sw = swish(dur, rng, shape, f * 0.8, f * 3.0, q=0.9)
    p = blip(f, f * 1.6, 0.06, 0.012, rng, glide=0.015) if pop == "blip" else tick(f * 1.5, 0.01, 0.3, rng, 0.05)
    return L.mix((sw, 0.6), (p, 0.8, dur - 0.01)), {"arch": "%s/%s/%d" % (shape, pop, f)}


def fam_whisper(rng, i):
    shape, note = L.cycle(i, ("hump", "twopuff", "flutter", "late"), (11, 12, 10, 13))
    dur = rng.uniform(0.18, 0.26)
    breath = swish(dur, rng, shape, rng.uniform(2200, 2800), rng.uniform(4200, 5600), q=0.5)
    return L.mix((breath, 0.7), (tone(hz(note), 0.45, 0.12, "glass", rng), 0.25, dur * 0.35)), {"arch": "%s/%d" % (shape, note)}


FRIEND = {"third": ((0, 0), (0.09, 2)), "fifth": ((0, 0), (0.1, 3)), "three": ((0, 0), (0.07, 1), (0.14, 3)), "octave": ((0, 0), (0.08, 5))}


def fam_friend(rng, i):
    motif, tim = L.cycle(i, tuple(FRIEND), ("bell", "celesta", "kalimba", "musicbox"))
    root = int(rng.choice([7, 8]))
    ev = [(t * rng.uniform(0.95, 1.05), hz(root + s), 1.0 if k == 0 else 0.85, 0.16) for k, (t, s) in enumerate(FRIEND[motif])]
    x = seq(ev, rng, tim)
    return L.mix(x, (sparkle(0.35, rng, 30, env="hump"), 0.15, 0.05)), {"arch": "%s/%s" % (motif, tim)}


def fam_join(rng, i):
    motif, tim = L.cycle(i, ((0, 2, 4), (0, 1, 3), (0, 2, 5), (0, 3)), ("bell", "kalimba", "celesta", "glass"))
    root = int(rng.choice([6, 7]))
    gap = rng.uniform(0.07, 0.1)
    ev = [(k * gap, hz(root + s), 0.8 + 0.1 * k, 0.13) for k, s in enumerate(motif)]
    sw = swish(0.2, rng, "rise", 500, 1500, q=0.7, color="pink")
    return L.mix((sw, 0.3), (seq(ev, rng, tim), 0.7, 0.03)), {"arch": "%s/%s" % ("-".join(map(str, motif)), tim)}


def fam_leave(rng, i):
    motif, tim = L.cycle(i, ((4, 2, 0), (3, 1), (5, 2, 1), (2, 0)), ("bell", "marimba", "soft", "glass"))
    root = int(rng.choice([5, 6]))
    gap = rng.uniform(0.08, 0.11)
    ev = [(k * gap, hz(root + s), 0.9 - 0.1 * k, 0.12) for k, s in enumerate(motif)]
    sw = swish(0.22, rng, "fall", 1400, 450, q=0.7, color="pink")
    return L.mix((seq(ev, rng, tim), 0.7), (sw, 0.3, 0.02)), {"arch": "%s/%s" % ("-".join(map(str, motif)), tim)}


def fam_notify(rng, i):
    pat, tim, root = L.cycle(i, ("ding", "dingding", "grace", "lowhigh"), ("bell", "glass", "musicbox"), (9, 11, 10, 12, 8))
    if pat == "ding":
        ev = [(0, hz(root), 1.0, 0.2)]
    elif pat == "dingding":
        ev = [(0, hz(root), 1.0, 0.1), (rng.uniform(0.12, 0.15), hz(root), 0.8, 0.18)]
    elif pat == "grace":
        ev = [(0, hz(root + 1), 0.4, 0.03), (0.04, hz(root), 1.0, 0.2)]
    else:
        ev = [(0, hz(root - 2), 0.8, 0.08), (0.06, hz(root + 1), 1.0, 0.18)]
    return seq(ev, rng, tim), {"arch": "%s/%s" % (pat, tim)}


def fam_toast_success(rng, i):
    motif, tim, gap = L.cycle(i, ((0, 2, 4), (0, 4), (0, 1, 2, 4), (0, 2, 5), (1, 0, 3), (0, 3, 4)), ("celesta", "kalimba"),
                              (0.07, 0.09, 0.055, 0.11, 0.065))
    root = int(rng.choice([7, 8]))
    ev = [(k * gap, hz(root + s), 0.85 + 0.05 * k, 0.15) for k, s in enumerate(motif)]
    x = seq(ev, rng, tim)
    if len(motif) == 2:
        x = L.mix(x, (sparkle(0.25, rng, 35), 0.15, gap))
    return x, {"arch": "%s/%s/%.3f" % ("-".join(map(str, motif)), tim, gap)}


def fam_toast_warn(rng, i):
    pat, tim, root = L.cycle(i, ("double", "wobble", "lhl"), ("marimba", "bell"), (6, 8, 5, 9, 7))
    root += {"double": 0, "wobble": 2, "lhl": -1}[pat]
    f = hz(root)
    if pat == "double":
        ev = [(0, f, 1.0, 0.08), (rng.uniform(0.1, 0.13), f, 0.9, 0.12)]
    elif pat == "wobble":
        semi = 2 ** (1 / 12)
        ev = [(k * 0.065, f * (semi if k % 2 else 1.0), 0.85, 0.06) for k in range(4)]
    else:
        ev = [(0, f, 0.9, 0.07), (0.08, f * 2 ** (5 / 12), 1.0, 0.07), (0.16, f, 0.8, 0.12)]
    return L.lp(seq(ev, rng, tim), SR, 5000), {"arch": "%s/%s/%d" % (pat, tim, root)}


def fam_toast_error(rng, i):
    pat, tim, f = L.cycle(i, ("down2", "down3", "thud"), ("marimba", "square"), (440, 392, 494, 370, 466))
    dk = 0.1 if tim == "marimba" else 0.07
    if pat == "down2":
        ev = [(0, f, 1.0), (rng.uniform(0.1, 0.13), f * 2 ** (-3 / 12), 0.9)]
        x = seq(ev, rng, tim, dk)
    elif pat == "down3":
        ev = [(0, f, 0.85), (0.075, f * 2 ** (-2 / 12), 0.8), (0.15, f * 2 ** (-5 / 12), 0.95)]
        x = seq(ev, rng, tim, dk)
    else:
        x = L.mix(thump(f * 0.35, 0.18, rng, 0.04), (tone(f * 0.84, 0.4, dk * 1.4, tim, rng, bend=0.06, bend_t=0.08), 0.8, 0.015))
    return L.lp(x, SR, 3000), {"arch": "%s/%s/%d" % (pat, tim, f)}


def fam_toast_social(rng, i):
    pat, bubs, root = L.cycle(i, ("two_up", "grace", "fifth"), (1, 2), (8, 9, 7, 10, 8))
    x = bubble(rng.uniform(600, 850), rng)
    at = 0.04
    if bubs == 2:
        x = L.mix(x, (bubble(rng.uniform(900, 1100), rng), 0.7, 0.05))
        at = 0.09
    ev = {"two_up": [(0, hz(root), 0.85), (0.08, hz(root + 1), 1.0)],
          "grace": [(0, hz(root + 1), 0.4, 0.035), (0.035, hz(root + 2), 1.0)],
          "fifth": [(0, hz(root), 1.0), (0.07, hz(root + 3), 0.75)]}[pat]
    return L.mix((x, 0.6), (seq(ev, rng, "kalimba", 0.13), 0.65, at)), {"arch": "%s/%d/%d" % (pat, bubs, root)}


# ------------------------------------------------------------------------- new kinds: quests
def stamp(rng, kind="wood"):
    f = rng.uniform(110, 160)
    body = thump(f, 0.15, rng, 0.035) if kind == "wood" else knock(f * 1.6, "wood", rng, 0.03, 0.12, click=0.6)
    return L.mix(body, (paper(0.05, rng, 800, 4000, 1, 0, 0.015), 0.5))


def fam_quest_accept(rng, i):
    motif, tim, st = L.cycle(i, ((0, 2), (0, 1, 2), (0, 2, 4), (0, 3), (2, 4)), ("bell", "celesta"), ("wood", "knock", "none"))
    root = int(rng.choice([6, 7]))
    gap = rng.uniform(0.07, 0.1)
    at = 0.0 if st == "none" else rng.uniform(0.06, 0.08)
    ev = [(at + k * gap, hz(root + s), 0.85 + 0.1 * k, 0.15) for k, s in enumerate(motif)]
    x = seq(ev, rng, tim)
    if st != "none":
        x = L.mix((stamp(rng, st), 0.9), (x, 0.8))
    return x, {"arch": "%s/%s/%s" % ("-".join(map(str, motif)), tim, st)}


def fam_quest_ready(rng, i):
    sp, motif = L.cycle(i, ("rise", "late", "flutter", "hump"), ((0, 2), (0,), (2, 0, 4), (0, 3)))
    dur = rng.uniform(0.25, 0.35)
    shimmer = sparkle(dur, rng, rng.uniform(35, 60), lo=2500, hi=6000, env=sp)
    root = int(rng.choice([9, 10]))
    ev = [(k * 0.08, hz(root + s), 1.0 - 0.1 * k, 0.16) for k, s in enumerate(motif)]
    return L.mix((shimmer, 0.35), (seq(ev, rng, "glass" if i % 2 else "bell"), 0.7, dur * 0.55)), {"arch": "%s/%s" % (sp, motif)}


QC_MOTIFS = ((0, 2, 4, 5), (0, 1, 2, 4, 5), (0, 2, 3, 5), (2, 0, 2, 4, 7), (0, 4, 2, 5))
QC_RHYTHM = ((0.09, 0.09, 0.09, 0.09), (0.07, 0.07, 0.14, 0.07), (0.11, 0.06, 0.06, 0.12), (0.06, 0.06, 0.06, 0.06))


def fam_quest_complete(rng, i):
    motif, tim, rhythm = L.cycle(i, QC_MOTIFS, ("celesta", "bell", "kalimba"), QC_RHYTHM)
    root = int(rng.choice([5, 6]))
    ev, t = [], 0.0
    for k, s in enumerate(motif):
        last = k == len(motif) - 1
        ev.append((t, hz(root + s), 1.0 if last else 0.75, 0.3 if last else 0.12))
        if last:
            ev.append((t + 0.005, hz(root + s - 2), 0.45, 0.28))   # final dyad
        t += rhythm[min(k, len(rhythm) - 1)]
    x = seq(ev, rng, tim)
    return L.mix(x, (sparkle(0.45, rng, 40, env="fall"), 0.2, t - 0.05)), {"arch": "%s/%s" % (motif, tim)}


def fam_star(rng, i):
    body, step, extra = L.cycle(i, ("glass", "bell", "celesta", "musicbox"), (12, 13, 11, 14, 10), ("thump", "sparkle", "both"))
    f = hz(step)
    x = tone(f, 0.5, rng.uniform(0.09, 0.13), body, rng, attack=0.001)
    if extra in ("thump", "both"):
        x = L.mix((thump(rng.uniform(140, 200), 0.1, rng, 0.02), 0.5), (x, 1.0, 0.006))
    if extra in ("sparkle", "both"):
        x = L.mix(x, (sparkle(0.3, rng, 50, lo=f * 1.4, hi=f * 2.8, env="fall"), 0.25, 0.02))
    return x, {"arch": "%s/%d/%s" % (body, step, extra)}


def fam_unlock(rng, i):
    clack, motif = L.cycle(i, ("two", "three", "slide", "one"), ((0, 2), (0, 1, 3), (0, 3), (1, 2, 4)))
    f = rng.uniform(1400, 2000)
    if clack == "two":
        c = L.mix(knock(f * 0.5, "metal", rng, 0.012, 0.05, click=0.6), (knock(f * 0.38, "metal", rng, 0.015, 0.06, click=0.6), 0.9, 0.08))
        at = 0.12
    elif clack == "three":
        c = L.mix(*[(knock(f * (0.5 - 0.05 * k), "metal", rng, 0.01, 0.05, click=0.6), 0.8, 0.045 * k) for k in range(3)])
        at = 0.14
    elif clack == "slide":
        c = L.mix(burst(0.08, rng, 2000, 6000, 0.03), (knock(f * 0.42, "metal", rng, 0.015, 0.06, click=0.6), 1.0, 0.07))
        at = 0.12
    else:
        c = knock(f * 0.45, "metal", rng, 0.02, 0.08, click=0.7)
        at = 0.05
    root = int(rng.choice([7, 8]))
    ev = [(k * 0.075, hz(root + s), 0.9, 0.16) for k, s in enumerate(motif)]
    return L.mix((c, 0.7), (seq(ev, rng, "celesta"), 0.75, at)), {"arch": "%s/%s" % (clack, motif)}


# ------------------------------------------------------------------------- new kinds: placement
def fam_rotate(rng, i):
    teeth, mat, f = L.cycle(i, (1, 2, 3), ("plastic", "metal", "wood", "detent"), (2000, 2500, 1650, 3000, 1400))
    f *= rng.uniform(0.99, 1.01)

    def one(ff):
        if mat == "plastic":
            return L.mix(burst(0.02, rng, ff * 0.7, ff * 3, 0.002), (tick(ff, 0.004, 0.0, rng, 0.025), 0.7))
        if mat == "metal":
            return knock(ff * 0.6, "metal", rng, 0.008, 0.03, click=0.5)
        if mat == "wood":
            return knock(ff * 0.5, "wood", rng, 0.006, 0.03, click=0.7)
        return blip(ff * 1.2, ff * 0.85, 0.03, 0.005, rng, glide=0.006)

    gap = rng.uniform(0.009, 0.014)
    x = L.mix(*[(one(f * (1 - 0.04 * k)), 1.0 - 0.25 * k, k * gap * (1 + 0.15 * k)) for k in range(teeth)])
    return L.lp(x, SR, 9000), {"arch": "%d/%s/%d" % (teeth, mat, f)}


def fam_snap(rng, i):
    gest, body, f = L.cycle(i, ("thump_tick", "bright", "late_thump"), ("wood", "sine"), (1700, 2100, 1400, 2600, 1200))
    f *= rng.uniform(0.99, 1.01)
    tk = knock(f * 0.6, "wood", rng, 0.01, 0.05, click=0.5) if body == "wood" else tick(f, 0.008, 0.35, rng, 0.04)
    th = thump(rng.uniform(110, 200), 0.07, rng, 0.018)
    if gest == "thump_tick":
        x = L.mix((th, 0.7), (tk, 1.0, 0.003))
    elif gest == "bright":
        x = L.mix((tk, 1.0), (tone(f * 1.5, 0.06, 0.012, "soft", rng), 0.35, 0.002))
    else:
        x = L.mix((tk, 1.0), (th, 0.8, rng.uniform(0.008, 0.012)))
    return L.lp(x, SR, 8000), {"arch": "%s/%s/%d" % (gest, body, f)}


def fam_place(rng, i):
    mat, settle, f = L.cycle(i, ("wood", "cushion", "stone"), ("single", "bounce", "rattle", "slide"), (190, 240, 150, 300, 210))
    f *= rng.uniform(0.98, 1.02)

    def hit(ff):
        if mat == "wood":
            return L.mix(knock(ff, "wood", rng, rng.uniform(0.035, 0.05), 0.2, click=0.4), (thump(ff * 0.5, 0.1, rng, 0.02), 0.5))
        if mat == "cushion":
            return L.mix(thump(ff * 0.45, 0.14, rng, 0.04), (burst(0.08, rng, ff * 1.3, ff * 5, 0.02, attack=0.004, color="pink"), 0.7))
        return knock(ff * 1.3, "stone", rng, 0.025, 0.15, click=0.6)

    at = 0.0
    parts = []
    if settle == "slide":
        parts.append((L.norm_peak(swish(0.11, rng, "rise", 500, 1500, q=0.8, color="pink")), 0.55, 0.0))
        at = 0.095
    parts.append((L.norm_peak(hit(f)), 1.0, at))
    if settle == "bounce":
        parts.append((L.norm_peak(hit(f * 1.06)), 0.4, at + rng.uniform(0.06, 0.09)))
    elif settle == "rattle":
        grain = lambda r: knock(r.uniform(700, 1400), "wood", r, 0.005, 0.03, click=0.6)
        parts.append((L.scatter(SR, 0.09, rng, grain, count=int(rng.integers(3, 6)), gain=(0.2, 0.5)), 0.6, at + 0.03))
    return L.mix(*parts), {"arch": "%s/%s/%d" % (mat, settle, f)}


def fam_lift(rng, i):
    gest, body, f = L.cycle(i, ("tick_swish", "swish_pop", "pluck"), ("wood", "sine"), (1000, 1300, 1700, 2200, 1650))
    tk = knock(f, "wood", rng, 0.012, 0.05, click=0.35) if body == "wood" else tick(f, 0.01, 0.25, rng, 0.05)
    sw = swish(rng.uniform(0.08, 0.11), rng, "rise", f * 0.4, f * 1.7, q=0.8, color="pink")
    if gest == "tick_swish":
        x = L.mix((tk, 1.0), (sw, 0.5, 0.01))
    elif gest == "swish_pop":
        x = L.mix((sw, 0.5), (tk, 0.7, sw.size / SR - 0.02), (blip(f * 0.7, f * 1.1, 0.05, 0.012, rng), 0.6, sw.size / SR - 0.015))
    else:
        x = L.mix((tk, 0.8), (blip(f * 0.5, f * 0.75, 0.08, 0.025, rng, glide=0.04), 0.7, 0.012))
    return L.lp(x, SR, 7000), {"arch": "%s/%s/%d" % (gest, body, f)}


def fam_cancel(rng, i):
    shape, end, f = L.cycle(i, ("fall", "double", "hump"), ("down", "two"), (525, 820, 420, 1030, 660))
    dur = rng.uniform(0.12, 0.17)
    sw = swish(dur, rng, shape, 2000, 600, q=0.7, color="pink")
    if end == "down":
        b = blip(f, f * 0.7, 0.12, 0.035, rng, glide=0.06, harm=((1, 1.0), (2, 0.15)))
    else:
        b = L.mix(tick(f, 0.015, 0.2, rng, 0.06), (tick(f * 0.84, 0.015, 0.2, rng, 0.06), 0.8, 0.06))
    return L.mix((sw, 0.45), (b, 0.8, 0.02)), {"arch": "%s/%s/%d" % (shape, end, f)}


def fam_valid(rng, i):
    pat = ("up2", "glide", "up3", "glass")[(i - 1) % 4]
    root = int(rng.choice([10, 11]))
    if pat == "up2":
        x = L.mix(blip(hz(root), hz(root), 0.06, 0.02, rng), (blip(hz(root + 2), hz(root + 2), 0.07, 0.025, rng), 0.9, 0.045))
    elif pat == "glide":
        x = blip(hz(root) * 0.8, hz(root + 2), 0.12, 0.04, rng, glide=0.07)
    elif pat == "up3":
        x = L.mix(*[(blip(hz(root + k), hz(root + k), 0.05, 0.014, rng), 0.8, 0.03 * k) for k in range(3)])
    else:
        x = tone(hz(root + 1), 0.12, 0.03, "glass", rng)
    return x, {"arch": pat}


def fam_invalid(rng, i):
    pat = ("down2", "glide", "double", "buzz")[(i - 1) % 4]
    f = rng.uniform(300, 380)
    harm = ((1, 1.0), (3, 0.25), (5, 0.08))
    if pat == "down2":
        x = L.mix(blip(f, f, 0.07, 0.025, rng, harm=harm), (blip(f * 0.8, f * 0.8, 0.08, 0.03, rng, harm=harm), 0.9, 0.06))
    elif pat == "glide":
        x = blip(f * 1.1, f * 0.75, 0.12, 0.045, rng, glide=0.08, harm=harm)
    elif pat == "double":
        x = L.mix(blip(f, f, 0.05, 0.016, rng, harm=harm), (blip(f, f, 0.05, 0.016, rng, harm=harm), 0.8, 0.07))
    else:
        t = tv(0.12)
        x = blip(f * 0.9, f * 0.9, 0.12, 0.05, rng, harm=harm) * (0.6 + 0.4 * np.sin(TAU * 32 * t))
    return L.lp(x, SR, 2400), {"arch": pat}


# ------------------------------------------------------------------------- new kinds: painter
def fam_paint(rng, i):
    splats, wet, f = L.cycle(i, (1, 2, 3), ("squelch", "plop", "spray", "dab"), (220, 300, 180, 380, 260))
    f *= rng.uniform(0.98, 1.02)

    def one(ff):
        if wet == "squelch":
            n = L.noise(L.secs(0.08, SR), rng, "pink")
            y = L.svf(n, SR, np.geomspace(ff * 9, ff * 2, n.size), 1.4, "bp") * L.exp_decay(0.08, SR, 0.02, 0.003)
            return L.mix(y, (thump(ff, 0.06, rng, 0.015), 0.5))
        if wet == "plop":
            return blip(ff * 2.5, ff * 1.3, 0.07, 0.02, rng, glide=0.025)
        if wet == "spray":
            return burst(0.07, rng, ff * 12, ff * 26, 0.025, attack=0.006)
        return L.mix(knock(ff * 1.4, "wood", rng, 0.018, 0.08, click=0.2), (burst(0.05, rng, 300, 2000, 0.012, color="pink"), 0.6))

    gap = rng.uniform(0.05, 0.07)
    x = L.mix(*[(one(f * (1 + 0.08 * k)), 1.0 - 0.2 * k, k * gap) for k in range(splats)])
    return L.lp(x, SR, 7000), {"arch": "%d/%s/%d" % (splats, wet, f)}


def brush_stroke(dur, rng, c, shape, sweep, q, density):
    """One bristle drag: narrow band noise (sweeping or wobbling) plus sparse bristle grains."""
    n = L.secs(dur, SR)
    if sweep == "flat":       # a wobbling scrub instead of a sweep
        fc = c * (1 + 0.18 * np.sin(TAU * rng.uniform(10, 14) * np.arange(n) / SR + rng.uniform(0, TAU)))
    else:
        u = np.linspace(0, 1, n)
        f0, f1 = (c * 0.6, c * 1.5) if sweep == "up" else (c * 1.5, c * 0.6)
        fc = f0 * (f1 / f0) ** u
    y = L.norm_peak(L.svf(L.noise(n, rng), SR, fc, q, "bp") * shape_env(shape, dur, rng))
    grain = lambda r: burst(0.004, r, c * 0.8, c * 2.2, 0.0012)
    g = L.pad_to(L.scatter(SR, dur, rng, grain, density=density, gain=(0.2, 1.0), env=shape_env(shape, dur, rng)), n)
    return y + 0.4 * L.norm_peak(g)


def fam_brush(rng, i):
    gest = ("stroke", "back_forth", "dab_drag", "scrub", "flick", "drag")[i % 6]
    band = (1300, 3200)[(i // 6) % 2]                     # the two takes of a gesture: low and high band
    sweep = ("up", "down", "flat")[(i + 2 * (i // 6)) % 3]
    c = band * rng.uniform(0.95, 1.05)
    dens = rng.uniform(80, 220)
    if gest == "stroke":
        x = brush_stroke(0.12 * rng.uniform(0.9, 1.1), rng, c, "hump", sweep, 2.0, dens)
    elif gest == "back_forth":
        d = 0.07 * rng.uniform(0.9, 1.1)
        x = L.mix(brush_stroke(d, rng, c, "hump", sweep, 2.0, dens),
                  (brush_stroke(d, rng, c * 0.8, "hump", "down" if sweep == "up" else "up", 2.0, dens), 0.8, d + rng.uniform(0.015, 0.03)))
    elif gest == "dab_drag":
        dab = L.norm_peak(L.mix(burst(0.03, rng, c * 0.35, c * 1.2, 0.005), (thump(rng.uniform(160, 220), 0.04, rng, 0.01), 0.5)))
        x = L.mix(dab, (brush_stroke(0.08, rng, c, "fall", sweep, 2.0, dens), 0.7, rng.uniform(0.045, 0.06)))
    elif gest == "scrub":
        x = brush_stroke(0.15 * rng.uniform(0.9, 1.1), rng, c, "flutter", sweep, 2.0, dens * 1.5)
    elif gest == "flick":
        x = brush_stroke(0.06 * rng.uniform(0.9, 1.1), rng, c * 1.2, "early", "up", 1.6, dens)
    else:
        x = brush_stroke(0.18 * rng.uniform(0.9, 1.1), rng, c * 0.9, "late", sweep, 2.0, dens * 0.6)
    return x, {"arch": "%s/%d/%s" % (gest, band, sweep)}


def fam_fill(rng, i):
    pat = ("down3", "up2", "quick4", "big")[(i - 1) % 4]
    f = rng.uniform(380, 480)
    wash = L.lp(L.noise(L.secs(0.28, SR), rng, "pink"), SR, 1400) * shape_env("hump", 0.28, rng)
    if pat == "down3":
        b = [(bubble(f * (1.3 - 0.15 * k), rng, 0.08, 0.025), 0.9, 0.07 * k) for k in range(3)]
    elif pat == "up2":
        b = [(bubble(f * (0.9 + 0.3 * k), rng, 0.09, 0.03), 0.9, 0.1 * k) for k in range(2)]
    elif pat == "quick4":
        b = [(bubble(f * rng.uniform(0.9, 1.5), rng, 0.05, 0.015), 0.7, 0.04 * k) for k in range(4)]
    else:
        b = [(bubble(f * 0.6, rng, 0.15, 0.05), 1.0, 0.0)]
    return L.mix((wash, 0.35), *b), {"arch": pat}


def fam_undo(rng, i):
    kind, tim, f = L.cycle(i, ("swoop", "two", "rev"), ("soft", "kalimba"), (1100, 1370, 700, 1710, 875))
    if kind == "swoop":
        x = L.mix(blip(f, f * 0.6, 0.12, 0.05, rng, glide=0.07, harm=((1, 1.0), (2, 0.1))), (swish(0.1, rng, "fall", 2500, 900), 0.3),
                  (tone(f * 0.6, 0.12, 0.03, tim, rng), 0.5, 0.07))
    elif kind == "two":
        x = seq([(0, f, 0.9, 0.04), (0.06, f * 0.8, 1.0, 0.05)], rng, tim)
    else:
        r = tone(f * 0.9, 0.12, 0.04, tim, rng)[::-1]
        x = L.mix((r, 0.8), (tick(f * 0.7, 0.01, 0.3, rng, 0.05), 0.7, r.size / SR))
    return x, {"arch": "%s/%s/%d" % (kind, tim, f)}


def fam_redo(rng, i):
    kind, tim, f = L.cycle(i, ("swoop", "two", "rev"), ("soft", "kalimba"), (875, 1100, 1710, 700, 1370))
    if kind == "swoop":
        x = L.mix(blip(f * 0.65, f, 0.12, 0.05, rng, glide=0.07, harm=((1, 1.0), (2, 0.1))), (swish(0.1, rng, "rise", 900, 2500), 0.3),
                  (tone(f * 1.25, 0.12, 0.03, tim, rng), 0.5, 0.07))
    elif kind == "two":
        x = seq([(0, f * 0.8, 0.9, 0.04), (0.06, f, 1.0, 0.05)], rng, tim)
    else:
        x = L.mix((tick(f * 0.7, 0.01, 0.3, rng, 0.05), 0.7), (tone(f * 1.12, 0.14, 0.04, tim, rng), 0.8, 0.02))
        x = L.mix(x, (tone(f * 1.5, 0.1, 0.03, tim, rng), 0.4, 0.06))
    return x, {"arch": "%s/%s/%d" % (kind, tim, f)}


def fam_layer(rng, i):
    gest, body, f = L.cycle(i, ("flick", "double", "slide_tick"), ("wood", "sine"), (1100, 1650, 2500, 1300, 2150))
    fl = paper(0.04, rng, f * 0.9, f * 4, 2, rng.uniform(120, 200), rng.uniform(0.008, 0.012))
    tk = knock(f, "wood", rng, 0.012, 0.05, click=0.3) if body == "wood" else tick(f, 0.01, 0.25, rng, 0.05)
    if gest == "flick":
        x = L.mix((fl, 0.8), (tk, 0.7, 0.015))
    elif gest == "double":
        x = L.mix((fl, 0.8), (paper(0.04, rng, f * 1.1, f * 4.5, 2, 160, 0.01), 0.8, rng.uniform(0.045, 0.06)), (tk, 0.6, 0.11))
    else:
        x = L.mix((swish(0.07, rng, "rise", f * 0.9, f * 2.6, q=0.6), 0.5), (tk, 1.0, 0.065))
    return L.lp(x, SR, 8000), {"arch": "%s/%s/%d" % (gest, body, f)}


def fam_swatch(rng, i):
    kind, f, n = L.cycle(i, ("pop", "drop", "pluck"), (900, 1200, 700, 1500, 1050), (1, 2))
    f *= rng.uniform(0.99, 1.01)

    def one(ff):
        if kind == "pop":
            return blip(ff * 0.7, ff * 1.3, 0.045, 0.012, rng, glide=0.015)
        if kind == "drop":
            return L.mix(blip(ff * 1.6, ff, 0.05, 0.014, rng, glide=0.012), (tick(ff * 2, 0.004, 0.3, rng, 0.02), 0.4))
        return L.ks_pluck(SR, ff, 0.12, rng, damping=0.992, bright=0.4)

    x = one(f) if n == 1 else L.mix(one(f), (one(f * 1.25), 0.6, 0.04))
    return x, {"arch": "%s/%d/%d" % (kind, f, n)}


def fam_key_capture(rng, i):
    pat = ("lowhigh", "triple", "beep_tick", "glide")[(i - 1) % 4]
    f = rng.uniform(900, 1100)
    if pat == "lowhigh":
        x = L.mix(blip(f, f, 0.05, 0.015, rng), (blip(f * 1.5, f * 1.5, 0.06, 0.02, rng), 0.9, 0.06))
    elif pat == "triple":
        x = L.mix(*[(tick(f * 1.6, 0.006, 0.3, rng, 0.03), 0.8, 0.035 * k) for k in range(3)])
    elif pat == "beep_tick":
        x = L.mix(tone(f * 1.2, 0.12, 0.04, "soft", rng), (tick(f * 2, 0.005, 0.4, rng, 0.03), 0.6, 0.08))
    else:
        x = blip(f * 0.8, f * 1.4, 0.12, 0.05, rng, glide=0.08, harm=((1, 1.0), (2, 0.12)))
    return x, {"arch": pat}


def fam_save(rng, i):
    motif, st = L.cycle(i, ((0, 2), (0, 2, 4), (0, 4), (0, 1, 2), (2, 4)), ("wood", "knock", "none"))
    tim = ("bell", "celesta", "kalimba", "glass", "bell")[(i - 1) % 5]
    root = int(rng.choice([7, 8]))
    at = 0.0 if st == "none" else rng.uniform(0.05, 0.07)
    ev = [(at + k * 0.075, hz(root + s), 0.9, 0.14) for k, s in enumerate(motif)]
    x = seq(ev, rng, tim)
    if st != "none":
        x = L.mix((stamp(rng, st), 0.8), (x, 0.8))
    return x, {"arch": "%s/%s/%s" % (motif, st, tim)}


# ------------------------------------------------------------------------- new kinds: craft + dialogue
def fam_craft_submit(rng, i):
    shape, motif = L.cycle(i, ("rise", "flutter", "late", "double"), ((0, 2, 4), (0, 3, 5), (0, 1, 2, 4), (2, 4, 7)))
    dur = rng.uniform(0.28, 0.36)
    sw = swish(dur, rng, shape, 400, 3200, q=0.7, color="pink")
    root = int(rng.choice([7, 8]))
    ev = [(k * 0.06, hz(root + s), 0.8, 0.14) for k, s in enumerate(motif)]
    return L.mix((sw, 0.5), (seq(ev, rng, "celesta"), 0.6, dur * 0.7), (sparkle(0.3, rng, 40), 0.15, dur * 0.8)), \
        {"arch": "%s/%s" % (shape, motif)}


def fam_craft_step(rng, i):
    step, gest, tim = L.cycle(i, (7, 9, 8, 10, 6, 11), ("one", "two"), ("kalimba", "bell", "musicbox"))
    if gest == "one":
        x = L.mix(tick(hz(step) * 2, 0.005, 0.3, rng, 0.03), (tone(hz(step), 0.35, 0.1, tim, rng), 0.9, 0.004))
    else:
        x = seq([(0, hz(step - 1), 0.7, 0.06), (0.06, hz(step), 1.0, 0.1)], rng, tim)
    return x, {"arch": "%d/%s/%s" % (step, gest, tim)}


def fam_craft_done(rng, i):
    motif = ((0, 2, 4, 7), (0, 3, 5, 7), (0, 1, 2, 4, 5), (0, 4, 7))[(i - 1) % 4]
    tim = ("celesta", "bell", "glass", "kalimba")[(i - 1) % 4]
    root = int(rng.choice([5, 6]))
    sh = sparkle(0.35, rng, 50, lo=2000, hi=5000, env="rise")
    gap = rng.uniform(0.07, 0.09)
    ev = [(0.25 + k * gap, hz(root + s), 0.8 if k < len(motif) - 1 else 1.0, 0.13 if k < len(motif) - 1 else 0.3)
          for k, s in enumerate(motif)]
    end = 0.25 + (len(motif) - 1) * gap
    ev.append((end + 0.004, hz(root + motif[-1] - 3), 0.5, 0.28))
    return L.mix((sh, 0.3), seq(ev, rng, tim), (sparkle(0.4, rng, 40), 0.18, end)), {"arch": "%s/%s" % (motif, tim)}


def fam_craft_fail(rng, i):
    pat = ("fizzle", "down_thud", "wobble", "sigh")[(i - 1) % 4]
    f = rng.uniform(700, 900)
    if pat == "fizzle":
        x = L.mix(blip(f, f * 0.4, 0.35, 0.12, rng, glide=0.3), (burst(0.3, rng, 2000, 6000, 0.08, attack=0.01), 0.3, 0.04))
    elif pat == "down_thud":
        x = L.mix(seq([(0, f * 0.7, 0.9, 0.07), (0.1, f * 0.53, 0.9, 0.09)], rng, "marimba"), (thump(110, 0.15, rng, 0.04), 0.7, 0.2))
    elif pat == "wobble":
        x = blip(f * 0.8, f * 0.5, 0.35, 0.12, rng, glide=0.3) * (0.7 + 0.3 * np.sin(TAU * 9 * tv(0.35)))
    else:
        x = L.mix(swish(0.3, rng, "fall", 1800, 400, q=0.6, color="pink"), (seq([(0, f * 0.6, 0.8, 0.1), (0.12, f * 0.45, 0.7, 0.12)], rng, "soft"), 0.8, 0.02))
    return L.lp(x, SR, 5000), {"arch": pat}


def fam_page(rng, i):
    gest, f = L.cycle(i, ("flick", "flick2", "flick_tick", "slide"), (1300, 2400, 1700, 3000, 2000))
    hi = f * 1.9
    if gest == "flick":       # the two flick takes: slow flutter + short, fast flutter + longer
        slow = (i // 4) % 2 == 0
        x = paper(0.05 if slow else 0.07, rng, f * 0.75, hi, 2, 100 if slow else 190, 0.012 if slow else 0.02)
    elif gest == "flick2":
        x = L.mix((paper(0.035, rng, f * 0.75, hi, 1, 0, 0.008), 0.9), (paper(0.04, rng, f * 0.9, hi * 1.3, 1, 0, 0.01), 0.7, rng.uniform(0.03, 0.045)))
    elif gest == "flick_tick":
        x = L.mix((paper(0.04, rng, f * 0.8, hi, 1, 0, 0.008), 0.8), (tick(f, 0.01, 0.2, rng, 0.05), 0.7, 0.02))
    else:
        x = L.mix(swish(0.09, rng, "flutter", f * 0.7, hi, q=0.6), (paper(0.03, rng, f, hi, 1, 0, 0.006), 0.7, 0.07))
    return L.lp(x, SR, 8500), {"arch": "%s/%d" % (gest, f)}


def fam_choice(rng, i):
    step, tim = L.cycle(i, (8, 10, 7, 11, 9), ("marimba", "bell", "kalimba"))
    f = hz(step)
    x = L.mix(tick(f * 1.5, 0.006, 0.4, rng, 0.03), (tone(f, 0.3, 0.07, tim, rng), 0.9, 0.006))
    return x, {"arch": "%d/%s" % (step, tim)}


# ------------------------------------------------------------------------- registry
# kind: (takes, original whose loudness the family matches, generator, max seconds)
FAMILIES = {
    "hover": (14, "hover", fam_hover, 0.1),
    "click": (12, "click", fam_click, 0.2),
    "open": (8, "open", fam_open, 0.5),
    "close": (8, "close", fam_close, 0.45),
    "toast": (10, "toast", fam_toast, 0.6),
    "confirm": (8, "confirm", fam_confirm, 0.75),
    "deny": (8, "close", fam_deny, 0.45),
    "tab": (8, "click", fam_tab, 0.2),
    "select": (8, "click", fam_select, 0.25),
    "slider": (12, "hover", fam_slider, 0.08),
    "drawer_open": (6, "open", fam_drawer_open, 0.45),
    "drawer_close": (6, "close", fam_drawer_close, 0.45),
    "count": (10, "hover", fam_count, 0.15),
    "coin_gain": (6, "toast", fam_coin_gain, 0.8),
    "chat_in": (8, "toast", fam_chat_in, 0.65),
    "chat_out": (6, "close", fam_chat_out, 0.2),
    "whisper": (4, "toast", fam_whisper, 0.5),
    "friend": (4, "toast", fam_friend, 0.75),
    "join": (4, "open", fam_join, 0.7),
    "leave": (4, "close", fam_leave, 0.65),
    "notify": (6, "toast", fam_notify, 0.65),
    "toast_success": (6, "toast", fam_toast_success, 0.65),
    "toast_warn": (6, "toast", fam_toast_warn, 0.6),
    "toast_error": (6, "toast", fam_toast_error, 0.6),
    "toast_social": (6, "toast", fam_toast_social, 0.65),
    "quest_accept": (5, "confirm", fam_quest_accept, 0.8),
    "quest_ready": (4, "confirm", fam_quest_ready, 0.9),
    "quest_complete": (5, "confirm", fam_quest_complete, 1.3),
    "star": (8, "toast", fam_star, 0.5),
    "unlock": (4, "confirm", fam_unlock, 0.9),
    "rotate": (12, "hover", fam_rotate, 0.08),
    "snap": (10, "hover", fam_snap, 0.1),
    "place": (8, "click", fam_place, 0.3),
    "lift": (6, "click", fam_lift, 0.2),
    "cancel": (6, "close", fam_cancel, 0.25),
    "valid": (4, "hover", fam_valid, 0.15),
    "invalid": (4, "hover", fam_invalid, 0.18),
    "paint": (8, "click", fam_paint, 0.25),
    "brush": (12, "hover", fam_brush, 0.2),
    "fill": (4, "click", fam_fill, 0.32),
    "undo": (6, "click", fam_undo, 0.3),
    "redo": (6, "click", fam_redo, 0.3),
    "layer": (6, "click", fam_layer, 0.2),
    "swatch": (6, "hover", fam_swatch, 0.18),
    "key_capture": (4, "click", fam_key_capture, 0.15),
    "save": (5, "confirm", fam_save, 0.75),
    "craft_submit": (4, "confirm", fam_craft_submit, 1.0),
    "craft_step": (6, "toast", fam_craft_step, 0.45),
    "craft_done": (4, "confirm", fam_craft_done, 1.4),
    "craft_fail": (4, "close", fam_craft_fail, 0.6),
    "page": (8, "click", fam_page, 0.15),
    "choice": (6, "click", fam_choice, 0.3),
}
ORIGINALS = ("hover", "click", "open", "close", "toast", "confirm")


def clean_stale(out: Path, kind: str, n: int) -> list:
    """Remove this generator's own untracked takes numbered past n (left by an earlier, larger run)."""
    gone = []
    pat = re.compile(r"^%s_(\d+)\.wav$" % re.escape(kind))
    for p in sorted(out.glob("%s_*.wav" % kind)):
        m = pat.match(p.name)
        if m and int(m.group(1)) > n and not L.git_tracked(p):
            p.unlink()
            imp = p.with_name(p.name + ".import")
            if imp.exists() and not L.git_tracked(imp):
                imp.unlink()
            gone.append(p.name)
    return gone


TAIL = {"trim_db": -50.0, "fade_out": 0.03}     # UI tails: cut 50 dB down, 30 ms raised-cosine fade
# Peak ceilings (linear) for families whose sharp attacks jumped out in the in-game mix
# (2026-10-15 Movie Maker capture: click_7 peaked at -1.9 dBFS while its family sat near -8).
PEAK_CAP = {"click": 0.5}                         # about -6 dBFS


def leveled(fn, ref_db: float, max_dur: float, ceiling: float | None = None):
    """Finish each take once before make_family finishes it again: the second pass measures the
    trimmed, capped file, so short takes (< 120 ms window) land on ref_db too."""
    kw = dict(TAIL, max_dur=max_dur)
    if ceiling:
        kw["ceiling"] = ceiling

    def run(rng, i):
        res = fn(rng, i)
        x, notes = res if isinstance(res, tuple) else (res, {})
        return L.finish(x, SR, ref_db=ref_db, **kw), notes
    return run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(UI), help="output dir (default game/assets/sfx/ui)")
    ap.add_argument("--only", default="", help="comma list of kinds")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", default="", help="write the take metadata here")
    args = ap.parse_args(argv)
    if args.list:
        for k, (n, ref, _, mx) in FAMILIES.items():
            print("%-15s %3d takes  level of ui/%s.wav  <= %.2f s" % (k, n, ref, mx))
        print("total", sum(v[0] for v in FAMILIES.values()))
        return 0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    kinds = [k.strip() for k in args.only.split(",") if k.strip()] or list(FAMILIES)
    bad = [k for k in kinds if k not in FAMILIES]
    if bad:
        print("unknown kinds:", bad, file=sys.stderr)
        return 2
    if out.resolve() != UI.resolve():
        for k in ORIGINALS:      # try-out dirs get the originals too, so the QA compares against them
            if not (out / ("%s.wav" % k)).exists():
                shutil.copy2(UI / ("%s.wav" % k), out / ("%s.wav" % k))
    refs = {k: L.ref_db_of(UI / ("%s.wav" % k)) for k in ORIGINALS}
    allmeta, total = {}, 0
    for k in kinds:
        n, ref, fn, mx = FAMILIES[k]
        clean_stale(out, k, n)
        cap = PEAK_CAP.get(k)
        fkw = dict(TAIL, max_dur=mx, **({"ceiling": cap} if cap else {}))
        meta = L.make_family(out, k, n, leveled(fn, refs[ref], mx, cap), sr=SR, ref_db=refs[ref], seed_base="ui",
                             finish_kw=fkw, verbose=False)
        b = sum(d["bytes"] for d in meta)
        total += b
        st = [d["st_db"] for d in meta]
        lim = max(d.get("limit_db", 0.0) for d in meta)
        print("%-15s %2d takes %6.1f KB  st %.1f..%.1f (ref %.1f, limiter <= %.1f dB)  %.2f-%.2f s" % (
            k, n, b / 1024, min(st), max(st), refs[ref], lim, min(d["seconds"] for d in meta), max(d["seconds"] for d in meta)))
        allmeta[k] = meta
    print("TOTAL %d files, %.1f KB" % (sum(len(v) for v in allmeta.values()), total / 1024))
    if args.json:
        Path(args.json).write_text(json.dumps(allmeta, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
