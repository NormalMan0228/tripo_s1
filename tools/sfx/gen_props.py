"""gen_props: take families for props, field objects and interiors (Villagen sound variety).

    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_props.py                 # everything
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_props.py --only fx       # fx | field | interior
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_props.py --family thud,leaves --root <scratch>

Writes NEW files only (never a git-tracked one):
  game/assets/sfx/fx/<kind>_<n>.wav        fx.gd Fx.sound kinds (were runtime synth; now baked takes)
  game/assets/sfx/field/<name>_<n>.wav     field_objects.gd play() (the bare <name>.wav stays take 0)
  game/assets/sfx/interior/<kind>_<n>.wav  interiors.gd Interiors.sfx / Interiors.play kinds
  game/assets/sfx/world/portal_<n>.wav     sound.gd stinger() takes of world/portal.wav (the team's
                                           original stays take 0; the takes are derived from it)
Each family is built on a grid of structural archetypes (sfxlib.cycle) plus small random detail,
so every take is a different "recording" of the same action. Levels: the fx and interior families
match the st-rms of the runtime synth they replace (fx_synth / interior_synth below are ports of
fx.gd _synth and interiors.gd sfx); field families match the existing field/<name>.wav (new
kinds match a sibling). Everything is synthesised here (numpy/scipy), license-clean.
Helpers from tools/make_village_sfx.py are imported (its main() is never run: it overwrites).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from scipy import signal as ss

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import sfxlib as L  # noqa: E402
import make_village_sfx as V  # noqa: E402  (helpers only; has a __main__ guard)

SR = L.DEFAULT_SR       # 22050
BR = L.BRIGHT_SR        # 32000 (metal, glass, sparkles)
SEED_BASE = "props"
TAU = 2 * np.pi


# =========================================================================== shared helpers
def S(rng, sr):
    """A make_village_sfx Synth that draws from this take's rng, with V at sample rate sr."""
    V.SR = sr
    s = V.Synth(0)
    s.rng = rng
    return s


def arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def bump(u, c, w):
    return np.exp(-((u - c) / w) ** 2)


def shape_env(shape: str, n: int, rng, dur: float) -> np.ndarray:
    """Named amplitude contours over n samples (dur s): the main structural axis of noise sounds."""
    u = np.linspace(0, 1, max(n, 2))[:n]
    if shape == "swell":
        e = np.sin(np.pi * u) ** 1.5
    elif shape == "double":
        e = bump(u, 0.24, 0.11) + 0.72 * bump(u, 0.66, 0.13)
    elif shape == "triple":
        e = bump(u, 0.16, 0.07) + 0.85 * bump(u, 0.46, 0.08) + 0.6 * bump(u, 0.77, 0.09)
    elif shape == "decay":
        e = np.minimum(u / 0.03, 1) * np.exp(-u / 0.28)
    elif shape == "late":
        e = np.minimum(u / 0.6, 1) ** 2 * np.clip((1 - u) / 0.25, 0, 1)
    elif shape == "shiver":
        e = np.sin(np.pi * u) * (0.5 + 0.5 * np.sin(TAU * rng.uniform(13, 19) * u * dur + rng.uniform(0, 6)) ** 2)
    elif shape == "quad":
        e = sum((1.0 - 0.15 * k) * bump(u, 0.12 + 0.24 * k, 0.06) for k in range(4))
    elif shape == "front":
        e = np.minimum(u / 0.08, 1) * (1 - u) ** 2.2
    else:
        raise KeyError(shape)
    return e


def grains(rng, sr, dur, density, env, lo, hi, glen=(0.002, 0.012), gain=(0.15, 1.0)):
    """Crinkle texture: Hann-windowed noise grains landing where env is high, band-passed."""
    def g(r):
        k = max(8, L.secs(r.uniform(*glen), sr))
        return r.standard_normal(k) * np.hanning(k)
    x = L.scatter(sr, dur, rng, g, density=density, env=env, gain=gain)
    x = L.bp(x, sr, lo, hi)
    e = L.pad_to(np.sqrt(np.clip(env, 0, None)), x.size)
    return x * (0.35 + 0.65 * e)


def rustle(rng, sr, dur, shape, lo, hi, density=380.0, bed=0.3, glen=(0.002, 0.012)):
    n = L.secs(dur, sr)
    env = shape_env(shape, n, rng, dur)
    x = L.norm_peak(grains(rng, sr, dur, density, env, lo, hi, glen))
    b = L.bp(L.pink(n, rng), sr, lo * 0.7, hi) * env
    return x + L.pad_to(L.norm_peak(b), x.size) * bed


def sweep_noise(rng, sr, dur, f_from, f_to, q=1.2, env=None, color="pink"):
    n = L.secs(dur, sr)
    fc = f_from * (f_to / f_from) ** np.linspace(0, 1, n)
    y = L.svf(L.noise(n, rng, color), sr, fc, q=q, mode="bp")
    return y * (env if env is not None else np.sin(np.pi * np.linspace(0, 1, n)))


def tone(sr, dur, f, harmonics=((1, 1.0),), env=None):
    """Oscillator over a frequency contour f (scalar, array or callable of u in 0..1)."""
    n = L.secs(dur, sr)
    u = np.linspace(0, 1, max(n, 2))[:n]
    fr = f(u) if callable(f) else np.broadcast_to(np.asarray(f, float), (n,)) if np.ndim(f) == 0 else np.interp(u, np.linspace(0, 1, len(f)), f)
    y = L.osc(sr, fr, harmonics)
    if env is not None:
        y = y * (env(u) if callable(env) else L.pad_to(arr(env), n))
    return y


def bloop(sr, rng, f0, dur=0.05, rise=1.8, tau=0.35):
    """A water bubble: a sine whose pitch rises as it decays."""
    n = L.secs(dur, sr)
    t = L.tvec(n, sr)
    f = f0 * (1 + (rise - 1) * t / dur)
    return np.sin(TAU * np.cumsum(f) / sr) * np.exp(-t / (dur * tau)) * np.minimum(1, t / 0.0015)


def thump(sr, rng, f0=90.0, dur=0.22, tau=0.05, drop=0.4, grit=0.4, grit_hz=800.0):
    """Body hitting something soft: falling low sine plus a low-passed knock."""
    n = L.secs(dur, sr)
    t = L.tvec(n, sr)
    f = f0 * (1 - drop * (1 - np.exp(-t / 0.04)))
    body = np.sin(TAU * np.cumsum(f) / sr) * np.exp(-t / tau)
    knock = L.lp(rng.standard_normal(n), sr, grit_hz) * np.exp(-t / 0.012) * grit * 2.5
    return (body + knock) * np.minimum(1, t / 0.001)


def creak(rng, sr, length, f0, f1, body=(190, 430, 820, 1450, 2400), q=7.0, rough=0.18, wobble=9.0,
          swell=0.08, release=0.25, metal=False):
    """make_village_sfx.creak (stick-slip pulse train through a resonant body) on this rng."""
    return arr(V.creak(S(rng, sr), length, f0, f1, body=body, q=q, rough=rough, wobble=wobble, swell=swell,
                       release=release, metal=metal))


def knock(sr, rng, f0, material="wood", dur=None, bright=1.0):
    return L.modal(sr, f0, material, dur=dur, rng=rng, bright=bright)


def notes_hz(midi):
    return [440.0 * 2 ** ((m - 69) / 12.0) for m in midi]


def cap(x, sr, max_s, fade=0.25):
    """Cut to max_s with a long cosine fade (finish() would only give 20 ms)."""
    x = arr(x)
    n = L.secs(max_s, sr)
    if x.size <= n:
        return x
    x = x[:n].copy()
    k = min(L.secs(fade, sr), n)
    x[n - k:] *= np.cos(0.5 * np.pi * np.arange(k) / k) ** 2
    return x


def room(x, sr, rng, size=0.15, wet=0.1):
    return L.reverb(x, sr, room=size, wet=wet, rng=rng)


# =========================================================================== runtime synth ports (levels)
def _onepole(a, x):
    return ss.lfilter([a], [1.0, -(1.0 - a)], x)


FX_LEN = {"thud": 0.2, "leaves": 0.6, "twinkle": 0.6, "crackle": 0.7, "splash": 0.4, "pluck": 0.35, "pop": 0.2,
          "chirp": 0.5, "whoosh": 0.45, "tune": 1.5, "drink": 0.5}
FX_SYNTH_KINDS = list(FX_LEN)


def fx_synth(kind: str, rate: int = 22050) -> np.ndarray:
    """Port of fx.gd _synth (same shapes and scale; the noise draw differs, the level does not)."""
    length = FX_LEN.get(kind, 0.3)
    n = int(length * rate)
    rng = np.random.default_rng(L.take_seed(kind, 0, "fx_synth"))
    t = np.arange(n) / rate
    u = t / length
    noise = rng.uniform(-1, 1, n)
    if kind == "thud":
        v = np.sin(TAU * (140 - 70 * u) * t) * 0.9 * np.exp(-u * 9) + _onepole(0.25, noise) * 0.8 * np.exp(-u * 20)
    elif kind == "leaves":
        low = _onepole(0.5, noise)
        v = (noise - low) * 0.8 * np.sin(np.pi * u) * (0.55 + 0.45 * np.abs(np.sin(t * 26)))
    elif kind == "twinkle":
        v = np.zeros(n)
        for k, f in enumerate([1568.0, 2093.0, 2637.0]):
            s0 = k * 0.12
            on = t >= s0
            v[on] += np.sin(TAU * f * (t[on] - s0)) * 0.32 * np.exp(-(t[on] - s0) * 9)
    elif kind == "crackle":
        low = _onepole(0.7, noise)
        pulse = (np.mod(t * 37 + np.sin(t * 11) * 3, 1.0) < 0.06).astype(float)
        v = (noise - low) * (0.15 + pulse * 0.9) * (1 - u)
    elif kind == "splash":
        v = _onepole(0.35, noise) * 1.4 * np.exp(-u * 6) + np.sin(TAU * (500 - 300 * u) * t) * 0.4 * np.exp(-u * 10)
    elif kind == "pluck":
        v = (np.sin(TAU * 660 * t) * 0.5 + np.sin(TAU * 1320 * t) * 0.2 + np.sin(TAU * 1980 * t) * 0.08) * np.exp(-u * 7)
    elif kind == "pop":
        v = np.sin(TAU * (300 + 900 * u) * t) * 0.75 * np.exp(-u * 5)
    elif kind == "chirp":
        k2 = np.mod(u * 3, 1.0)
        v = np.sin(TAU * (2400 + 1400 * np.sin(k2 * np.pi)) * t) * 0.35 * np.sin(np.pi * k2) * (k2 < 0.7)
    elif kind == "whoosh":
        low = np.zeros(n)
        acc = 0.0
        for i in range(n):
            acc += (noise[i] - acc) * (0.05 + 0.35 * math.sin(math.pi * u[i]))
            low[i] = acc
        v = low * 1.6 * np.sin(np.pi * u)
    elif kind == "tune":
        notes = [523.25, 659.25, 783.99, 659.25, 880.0, 783.99]
        step = np.minimum(len(notes) - 1, (u * len(notes)).astype(int))
        local = np.mod(u * len(notes), 1.0)
        f = np.array(notes)[step]
        v = (np.sin(TAU * f * t) * 0.4 + np.sin(TAU * f * 2 * t) * 0.1) * np.exp(-local * 3)
    elif kind == "drink":
        g = np.mod(u * 4, 1.0)
        v = np.sin(TAU * (260 + 200 * g) * t) * 0.5 * np.exp(-g * 6)
    else:
        v = np.zeros(n)
    return np.clip(v * np.minimum(1, t * 300), -1, 1) * 20000 / 32768


IN_LEN = {"click": 0.08, "creak": 0.55, "splash": 0.6, "sizzle": 0.9, "ding": 1.3, "tick": 0.95, "page": 0.32, "knock": 0.42,
          "crackle": 0.9, "steps": 1.0, "cushion": 0.3, "whoosh": 0.9, "chime": 1.2, "rumble": 1.1, "clink": 0.45, "pop": 0.16}
INTERIOR_SYNTH_KINDS = list(IN_LEN)


def interior_synth(kind: str, rate: int = 22050) -> np.ndarray:
    """Port of interiors.gd sfx() (same shapes and scale)."""
    length = IN_LEN.get(kind, 0.2)
    n = int(length * rate)
    rng = np.random.default_rng(L.take_seed(kind, 0, "interior_synth"))
    t = np.arange(n) / rate
    u = t / length
    noise = rng.uniform(-1, 1, n)
    if kind == "click":
        w = np.sin(TAU * 1400 * t) * np.exp(-t * 90) + noise * np.exp(-t * 160) * 0.4
    elif kind == "creak":
        f = 180 + 140 * u + np.sin(t * 40) * 25
        w = (np.sin(TAU * f * t) * 0.5 + np.sin(TAU * f * 2 * t) * 0.2) * np.sin(np.pi * u) * 0.6 + noise * 0.04
    elif kind == "splash":
        env = np.sin(np.pi * np.minimum(u * 3, 1)) * (1 - u) ** 1.4
        w = _onepole(0.18, noise) * env * 1.6
    elif kind == "whoosh":
        w = _onepole(0.05, noise) * np.sin(np.pi * u) * 2.4
    elif kind == "sizzle":
        w = _onepole(0.6, noise) * 0.35 * np.minimum(u * 6, 1) * (1 - u) + noise * 0.8 * (rng.random(n) < 0.01)
    elif kind == "ding":
        w = (np.sin(TAU * 1318.5 * t) * 0.5 + np.sin(TAU * 2637 * t) * 0.18 + np.sin(TAU * 3955 * t) * 0.06) * np.exp(-t * 3.2)
    elif kind == "chime":
        t2 = np.maximum(t - 0.18, 0)
        w = np.sin(TAU * 1046.5 * t) * 0.4 * np.exp(-t * 3) + np.sin(TAU * 1568 * t2) * 0.4 * np.exp(-t2 * 3) * (t > 0.18)
    elif kind == "tick":
        k = np.mod(t, 0.3)
        f = np.where((t / 0.3).astype(int) % 2 == 0, 2200.0, 1700.0)
        w = np.sin(TAU * f * k) * np.exp(-k * 120) * 0.7
    elif kind == "page":
        w = _onepole(0.3, noise) * np.sin(np.pi * u) * 0.7
    elif kind == "knock":
        k = np.mod(t, 0.18)
        w = (np.sin(TAU * 170 * k) * 0.8 + noise * 0.25) * np.exp(-k * 38) * (t < 0.36)
    elif kind == "crackle":
        w = _onepole(0.2, noise) * 0.15 + noise * 0.9 * np.exp(-np.mod(t, 0.07) * 90) * (rng.random(n) < 0.02)
    elif kind == "steps":
        k = np.mod(t, 0.25)
        w = (np.sin(TAU * (95 - 40 * k) * k) * 0.9 + noise * 0.3) * np.exp(-k * 30)
    elif kind == "cushion":
        w = (np.sin(TAU * 70 * t) * 0.5 + _onepole(0.08, noise) * 1.2) * np.exp(-t * 14)
    elif kind == "rumble":
        w = (np.sin(TAU * 55 * t) * 0.4 + _onepole(0.03, noise) * 1.6) * np.sin(np.pi * u)
    elif kind == "clink":
        k = np.mod(t, 0.17)
        w = (np.sin(TAU * 2600 * k) * 0.4 + np.sin(TAU * 3900 * k) * 0.2) * np.exp(-k * 40) * (t < 0.34)
    else:  # "pop" and anything else: the default branch
        w = np.sin(TAU * (520 + 300 * u) * t) * np.exp(-t * 28)
    return np.clip(w, -1, 1) * 20000 / 32768


_REF_CACHE: dict = {}


def ref_fx(kind):
    key = ("fx", kind)
    if key not in _REF_CACHE:
        _REF_CACHE[key] = L.st_rms_peak_db(fx_synth(kind), 22050)
    return _REF_CACHE[key]


def ref_interior(kind):
    key = ("interior", kind)
    if key not in _REF_CACHE:
        _REF_CACHE[key] = L.st_rms_peak_db(interior_synth(kind), 22050)
    return _REF_CACHE[key]


def ref_field(name):
    return L.ref_db_of(L.SFX_ROOT / "field" / ("%s.wav" % name))


# =========================================================================== registry
FAMILIES: list = []


def family(dir_, event, n, sr=SR, ref=None, start=1, max_s=None):
    """Register fn(rng, i) as a take family. ref: callable -> dB (evaluated at run time)."""
    def deco(fn):
        FAMILIES.append(dict(dir=dir_, event=event, n=n, sr=sr, ref=ref, start=start, fn=fn, max_s=max_s))
        return fn
    return deco


# =========================================================================== fx (Fx.sound kinds)
@family("fx", "thud", 8, ref=lambda: ref_fx("thud"))
def fx_thud(rng, i):
    """Fruit / furniture landing: ground surface x bounce pattern x body pitch."""
    surf, bounce, f0 = L.cycle(i, ["grass", "dirt", "deck", "leafy"], ["single", "double", "scuff"], [95, 130, 80, 160, 112])
    f0 *= rng.uniform(0.97, 1.03)
    dur = rng.uniform(0.17, 0.24)
    n = L.secs(dur, SR)
    t = L.tvec(n, SR)
    body = thump(SR, rng, f0, dur, tau=rng.uniform(0.035, 0.06), drop=rng.uniform(0.3, 0.5), grit=0.25)
    if surf == "grass":
        top = L.lp(rng.standard_normal(n), SR, 650) * np.exp(-t / 0.03) + L.bp(L.white(n, rng), SR, 2000, 6000) * np.exp(-t / 0.05) * 0.8
    elif surf == "dirt":
        top = grains(rng, SR, 0.08, 500, np.exp(-np.linspace(0, 4, 64)), 400, 3200, (0.001, 0.004))
    elif surf == "deck":
        top = knock(SR, rng, f0 * rng.uniform(3.0, 3.6), "wood") * 0.9
    else:
        top = rustle(rng, SR, 0.16, "front", 1500, 6500, density=500, bed=0.2) * 0.7
    x = L.mix(L.norm_peak(body), (L.norm_peak(top), {"grass": 0.5, "dirt": 0.8, "deck": 0.9, "leafy": 0.75}[surf] * rng.uniform(0.9, 1.1)))
    if bounce == "double":
        x = L.mix(x, (L.repitch(x, rng.uniform(1.05, 1.12)), rng.uniform(0.28, 0.4), rng.uniform(0.08, 0.13)))
    elif bounce == "scuff":
        roll = sweep_noise(rng, SR, rng.uniform(0.12, 0.18), 900, 400, q=0.8, env=None)
        x = L.mix(x, (L.norm_peak(roll), 0.3, rng.uniform(0.04, 0.07)))
    return x, {"surface": surf, "bounce": bounce}


@family("fx", "leaves", 8, ref=lambda: ref_fx("leaves"))
def fx_leaves(rng, i):
    """Broadleaf rustle: shake contour x leaf band x length (+ a twig snap now and then)."""
    shape, band, dur, twig = L.cycle(i, ["swell", "double", "triple", "decay"], [(1800, 6500), (2600, 9000), (1200, 5200)],
                                     [0.55, 0.72, 0.46, 0.64, 0.85], [False, False, True])
    x = rustle(rng, SR, dur * rng.uniform(0.95, 1.05), shape, *band, density=rng.uniform(300, 480))
    if twig:
        x = L.mix(x, (knock(SR, rng, rng.uniform(1100, 1700), "wood", dur=0.06), 0.45, rng.uniform(0.1, dur * 0.6)))
    return x, {"shape": shape}


@family("fx", "leaves_needle", 5, ref=lambda: ref_fx("leaves"))
def fx_leaves_needle(rng, i):
    """Conifer: fine dry needle hiss, then a few needles and a cone tick."""
    shape, dur, ticks, band = L.cycle(i, ["shiver", "double", "quad", "triple", "decay"], [0.6, 0.48, 0.75, 0.66, 0.52], [3, 0, 5, 2, 6],
                                      [(3200, 10000), (4500, 10500), (2400, 7500), (3800, 9000), (2800, 10500)])
    x = rustle(rng, SR, dur, shape, *band, density=rng.uniform(650, 900), bed=0.5, glen=(0.0008, 0.004))
    for k in range(ticks):
        x = L.mix(x, (knock(SR, rng, rng.uniform(2200, 3600), "wood", dur=0.03), rng.uniform(0.15, 0.3), dur * rng.uniform(0.35, 1.0)))
    return x


@family("fx", "leaves_palm", 5, ref=lambda: ref_fx("leaves"))
def fx_leaves_palm(rng, i):
    """Palm: big frond swishes (low, papery) and stem clacks."""
    swishes, dirs, clack = L.cycle(i, [2, 1, 3, 2, 1], [(700, 2400), (2600, 900), (1200, 3400), (3000, 1400), (500, 1500)],
                                   [True, False, True, False, True])
    out = np.zeros(L.secs(0.9, SR))
    at = 0.0
    for k in range(swishes):
        d = rng.uniform(0.2, 0.32)
        e = shape_env("swell", L.secs(d, SR), rng, d)
        sw = sweep_noise(rng, SR, d, dirs[0] * rng.uniform(0.9, 1.1), dirs[1] * rng.uniform(0.9, 1.1), q=0.9, env=e)
        flap = grains(rng, SR, d, 140, e, 600, 3500, (0.004, 0.015))
        L.place(out, L.norm_peak(sw) + 0.5 * L.norm_peak(flap), at, SR, 1.0 - 0.2 * k)
        at += d * rng.uniform(0.6, 0.85)
    if clack:
        L.place(out, knock(SR, rng, rng.uniform(320, 480), "wood"), rng.uniform(0.05, at), SR, 0.5)
    return out


TWINKLE_PATTERNS = [[7, 9, 11], [11, 9, 7, 9], [5, 7, 9, 12], [12, 10, 8], [7, 9, 11], [9, 11, 9, 12], [8, 11], [10, 8, 10, 12, 14]]
PENTA = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24, 26, 28, 31, 33]   # C major pentatonic, semitones


@family("fx", "twinkle", 8, sr=BR, ref=lambda: ref_fx("twinkle"))
def fx_twinkle(rng, i):
    """Sparkle arpeggio: note pattern (contour) x timbre x spacing."""
    pat = TWINKLE_PATTERNS[i % len(TWINKLE_PATTERNS)]
    timbre, gap = L.cycle(i, ["glass", "fm", "sine"], [0.12, 0.08, 0.15, 0.035, 0.1])
    base = 523.25 * rng.uniform(0.995, 1.005)
    out = np.zeros(L.secs(1.0, BR))
    for k, deg in enumerate(pat):
        f = base * 2 ** (PENTA[deg] / 12.0)
        if timbre == "glass":
            v = L.modal(BR, f, "glass", dur=0.5, rng=rng)
        elif timbre == "fm":
            v = L.fm_bell(BR, f, 0.55, ratio=3.5, index=rng.uniform(1.5, 2.5), t60=0.5, rng=rng)
        else:
            v = tone(BR, 0.5, f, ((1, 1.0), (2, 0.25), (3, 0.06)), env=lambda u: np.exp(-u * 6) * np.minimum(1, u * 400))
        L.place(out, v, k * gap * rng.uniform(0.9, 1.1), BR, 0.85 ** k)
    if i % 3 == 1:
        dust = L.scatter(BR, 0.3, rng, lambda r: L.modal(BR, r.uniform(5000, 9000), "glass", dur=0.05, rng=r), count=6, gain=(0.1, 0.3))
        L.place(out, dust, 0.05, BR)
    return out, {"pattern": pat, "timbre": timbre}


PLUCK_NOTES = [587.33, 392.0, 783.99, 493.88, 659.25, 440.0, 987.77, 523.25]


@family("fx", "pluck", 8, ref=lambda: ref_fx("pluck"))
def fx_pluck(rng, i):
    """Wooden pluck / tap: note x articulation (single, grace note, repeated) x brightness."""
    f0 = PLUCK_NOTES[i % len(PLUCK_NOTES)] * rng.uniform(0.997, 1.003)
    style, bright = L.cycle(i, ["single", "grace", "double"], [0.3, 0.75])
    dur = rng.uniform(0.3, 0.42)
    x = L.ks_pluck(SR, f0, dur, rng=rng, damping=rng.uniform(0.990, 0.995), bright=bright)
    x = L.mix(x, (knock(SR, rng, f0 * 0.5, "wood", dur=0.08), 0.25))
    if style == "grace":
        g = L.ks_pluck(SR, f0 * 2 ** (-rng.choice([2, 3, 5]) / 12), 0.12, rng=rng, damping=0.985, bright=bright)
        x = L.mix((g, 0.5), (x, 1.0, rng.uniform(0.045, 0.065)))
    elif style == "double":
        x = L.mix(x, (L.ks_pluck(SR, f0, dur * 0.8, rng=rng, damping=0.99, bright=bright * 0.8), 0.55, rng.uniform(0.09, 0.13)))
    return x, {"style": style}


@family("fx", "pop", 8, ref=lambda: ref_fx("pop"))
def fx_pop(rng, i):
    """Appear pop: kind (sweep, cork, bubble, double) x pitch x length."""
    kind, p, dur = [("sweep", 1.0, 0.16), ("cork", 1.3, 0.22), ("bubble", 0.78, 0.12), ("double", 1.55, 0.16),
                    ("drop", 1.1, 0.18), ("cork", 0.85, 0.14), ("burst", 1.2, 0.2), ("sweep", 1.45, 0.11)][i]
    if kind == "sweep":
        x = tone(SR, dur, lambda u: (300 + 900 * u ** rng.uniform(0.7, 1.3)) * p, ((1, 1.0), (2, 0.15)), env=lambda u: np.exp(-u * 5) * np.minimum(1, u * 60))
    elif kind == "cork":
        n = L.secs(dur, SR)
        burst = L.bp(L.white(n, rng), SR, 600 * p, 4000 * p) * np.exp(-L.tvec(n, SR) / 0.006)
        ring = L.resonate(burst, SR, [520 * p, 1180 * p], [0.03, 0.02])
        x = L.mix(burst * 2, ring)
    elif kind == "bubble":   # three quick high blips
        x = L.mix(*[(bloop(SR, rng, (900 + 250 * k) * p, 0.035, rise=1.5), 1.0 - 0.2 * k, k * rng.uniform(0.03, 0.045)) for k in range(3)])
    elif kind == "drop":
        x = tone(SR, dur, lambda u: (1400 - 900 * u ** 0.6) * p, ((1, 1.0), (3, 0.08)), env=lambda u: np.exp(-u * 4) * np.minimum(1, u * 60))
    elif kind == "burst":
        n = L.secs(dur, SR)
        x = L.bp(L.white(n, rng), SR, 900 * p, 5000) * np.exp(-L.tvec(n, SR) / 0.01)
        for k in range(4):
            x = L.mix(x, (bloop(SR, rng, rng.uniform(600, 1300) * p, 0.04, rise=2.0), 0.5, rng.uniform(0.005, dur * 0.6)))
    else:
        a = tone(SR, dur * 0.5, lambda u: (450 + 600 * u) * p, ((1, 1.0),), env=lambda u: np.exp(-u * 4))
        b = tone(SR, dur * 0.6, lambda u: (650 + 900 * u) * p, ((1, 1.0),), env=lambda u: np.exp(-u * 4))
        x = L.mix(a, (b, 0.8, dur * 0.42))
    return x, {"kind": kind}


TUNES = [  # (midi notes, beat lengths): six different jingles
    ([72, 76, 79, 76, 81, 79], [1, 1, 1, 1, 1, 2]),
    ([79, 76, 72, 74, 76, 72], [1, 1, 2, 1, 1, 2]),
    ([72, 74, 76, 79, 84], [1, 1, 1, 1, 3]),
    ([76, 79, 81, 79, 76, 74, 72], [0.75, 0.75, 1, 0.75, 0.75, 1, 2]),
    ([81, 79, 76, 79, 84], [1, 0.5, 0.5, 1, 2]),
    ([84, 79, 76, 72, 74, 76], [1, 1, 1, 1, 0.5, 2.5]),
]


def melody(rng, sr, midi, beats, beat, voice, gain_tail=0.85):
    total = sum(beats) * beat + 0.9
    out = np.zeros(L.secs(total, sr))
    at = 0.0
    for k, (m, b) in enumerate(zip(midi, beats)):
        f = notes_hz([m])[0]
        d = min(1.2, b * beat + 0.5)
        if voice == "musicbox":
            v = L.fm_bell(sr, f, d, ratio=3.0, index=rng.uniform(1.0, 1.8), t60=d * 0.9, rng=rng)
        elif voice == "marimba":
            v = L.modal(sr, f, "wood", dur=d, rng=rng, tau=0.25, n_modes=3)
        elif voice == "kalimba":
            v = L.ks_pluck(sr, f, d, rng=rng, damping=0.997, bright=0.6)
        elif voice == "glock":
            v = L.modal(sr, f * 2, "glass", dur=d, rng=rng)
        elif voice == "square":
            v = tone(sr, d * 0.8, f * (1 + 0.004 * np.sin(np.linspace(0, TAU * 5 * d, L.secs(d * 0.8, sr)))),
                     ((1, 1.0), (3, 0.3), (5, 0.15), (7, 0.07)), env=lambda u: np.minimum(1, u * 40) * (1 - u) ** 1.2)
        else:  # "flute"
            n = L.secs(d * 0.85, sr)
            v = tone(sr, d * 0.85, f, ((1, 1.0), (2, 0.12)), env=lambda u: np.minimum(1, u * 12) * (1 - u) ** 0.8)
            v = v + L.bp(L.white(n, rng), sr, f, f * 3) * 0.05
        L.place(out, v, at + rng.uniform(-0.008, 0.008), sr, 0.75 * (gain_tail ** k) + 0.25)
        at += b * beat
    return out


@family("fx", "tune", 6, ref=lambda: ref_fx("tune"))
def fx_tune(rng, i):
    midi, beats = TUNES[i]
    voice, beat = L.cycle(i, ["musicbox", "marimba", "kalimba", "glock"], [0.2, 0.17, 0.23])
    return cap(melody(rng, SR, midi, beats, beat * rng.uniform(0.97, 1.03), voice), SR, 2.3), {"voice": voice}


@family("fx", "splash", 6, ref=lambda: ref_fx("splash"))
def fx_splash(rng, i):
    kind = ["plunge", "slap", "pour", "patter", "slosh", "drips"][i]
    out = np.zeros(L.secs(0.8, SR))
    if kind in ("plunge", "slap", "drips"):
        hits = {"plunge": [0.0], "slap": [0.0, rng.uniform(0.07, 0.11)], "drips": [0.0]}[kind]
        for k, at in enumerate(hits):
            d = rng.uniform(0.18, 0.28)
            n = L.secs(d, SR)
            burst = L.bp(L.white(n, rng), SR, 300, 4500) * np.exp(-L.tvec(n, SR) / rng.uniform(0.03, 0.06))
            L.place(out, L.norm_peak(burst), at, SR, 1.0 - 0.3 * k)
            for _ in range(rng.integers(3, 7)):
                L.place(out, bloop(SR, rng, rng.uniform(300, 900), rng.uniform(0.03, 0.07)), at + rng.uniform(0.01, 0.15), SR, rng.uniform(0.2, 0.5))
        if kind == "drips":
            for k in range(3):
                L.place(out, bloop(SR, rng, rng.uniform(900, 1500), 0.04, rise=2.5), 0.3 + k * rng.uniform(0.1, 0.15), SR, 0.35)
    elif kind == "pour":
        d = 0.6
        n = L.secs(d, SR)
        e = np.minimum(1, L.tvec(n, SR) / 0.05) * np.clip((d - L.tvec(n, SR)) / 0.15, 0, 1)
        stream = L.bp(L.white(n, rng), SR, 800, 5000) * e * (0.8 + 0.2 * np.sin(TAU * 9 * L.tvec(n, SR)))
        L.place(out, L.norm_peak(stream) * 0.6, 0.0, SR)
        bub = L.scatter(SR, d, rng, lambda r: bloop(SR, r, r.uniform(400, 1100), r.uniform(0.02, 0.05)), density=30, gain=(0.1, 0.4))
        L.place(out, bub, 0.02, SR)
    elif kind == "patter":
        drops = L.scatter(SR, 0.45, rng, lambda r: L.mix(bloop(SR, r, r.uniform(600, 1600), 0.03, rise=2.0),
                                                         (L.bp(L.white(L.secs(0.01, SR), r), SR, 2000, 7000), 0.5)), density=45, gain=(0.3, 1.0))
        L.place(out, drops, 0.0, SR)
    else:  # slosh: two swells of low water noise
        d = 0.65
        n = L.secs(d, SR)
        e = shape_env("double", n, rng, d)
        L.place(out, L.norm_peak(L.lp(L.brown(n, rng), SR, 1200) * e), 0.0, SR)
        L.place(out, L.norm_peak(L.bp(L.white(n, rng), SR, 1500, 4000) * e ** 2) * 0.3, 0.0, SR)
    return out, {"kind": kind}


@family("fx", "crackle", 6, ref=lambda: ref_fx("crackle"))
def fx_crackle(rng, i):
    """Fire flare-up: pop density x length x extra event (log shift, hiss, ember shower)."""
    density, dur, extra = L.cycle(i, [26, 55, 38], [0.7, 0.55, 0.9, 0.62, 0.8, 0.5], ["none", "log", "hiss", "embers"])
    n = L.secs(dur, SR)
    t = L.tvec(n, SR)
    env = np.minimum(1, t / 0.05) * np.clip((dur - t) / (dur * 0.6), 0, 1)
    roar = L.lp(L.brown(n, rng), SR, 400) * env * 0.35
    pops = L.scatter(SR, dur, rng, lambda r: L.bp(r.standard_normal(L.secs(0.02, SR)), SR, 1500, 7000) * np.exp(-L.tvec(L.secs(0.02, SR), SR) / r.uniform(0.0015, 0.005)),
                     density=density, env=env, gain=(0.15, 1.0))
    x = L.mix(L.norm_peak(roar), (L.norm_peak(pops), 0.9))
    if extra == "log":
        x = L.mix(x, (thump(SR, rng, 70, 0.25, 0.05, grit=0.6), 0.5, rng.uniform(0.1, 0.3)))
    elif extra == "hiss":
        h = L.hp(L.white(n, rng), SR, 3000) * shape_env("swell", n, rng, dur)
        x = L.mix(x, (L.norm_peak(h), 0.25))
    elif extra == "embers":
        sh = L.scatter(SR, 0.3, rng, lambda r: knock(SR, r, r.uniform(2500, 4500), "glass", dur=0.03), count=8, gain=(0.1, 0.35))
        x = L.mix(x, (sh, 1.0, dur * 0.4))
    return x, {"extra": extra}


def whoosh_take(rng, sr, i, lengths, sweeps, shapes=("single", "double", "flutter"), whistle=None):
    shape, (length, sweep), peak = L.cycle(i, list(shapes), lengths_sweeps(lengths, sweeps), [0.34, 0.62])
    n = L.secs(length * rng.uniform(0.95, 1.05), sr)
    u = np.linspace(0, 1, n)
    fc = np.interp(u, [0, peak, 1], [sweep[0], sweep[0] + (sweep[1] - sweep[0]) * 0.9, sweep[1]])
    w = rng.uniform(0.14, 0.2)
    env = np.exp(-((u - peak) / w) ** 2)
    if shape == "double":
        env = 0.8 * np.exp(-((u - peak + 0.22) / (w * 0.6)) ** 2) + np.exp(-((u - peak) / (w * 0.7)) ** 2)
    elif shape == "flutter":
        env = env * (1 - 0.6 * (0.5 + 0.5 * np.sin(TAU * rng.uniform(18, 26) * u * length)))
    elif shape == "late":
        env = np.minimum(u / max(peak, 0.1), 1) ** 2.5 * np.clip((1 - u) / 0.12, 0, 1)
    elif shape != "single":
        env = shape_env(shape, n, rng, length)
    x = L.svf(L.pink(n, rng), sr, fc, q=rng.uniform(0.9, 1.6), mode="bp") * env
    if whistle:
        x = x + tone(sr, n / sr, fc * whistle, ((1, 1.0),), env=env) * 0.05
    return x, shape


def lengths_sweeps(lengths, sweeps):
    return [(l, s) for l, s in zip(lengths, sweeps)]


@family("fx", "whoosh", 6, ref=lambda: ref_fx("whoosh"))
def fx_whoosh(rng, i):
    x, shape = whoosh_take(rng, SR, i, [0.4, 0.5, 0.36, 0.56, 0.45, 0.62], [(500, 3200), (2200, 700), (800, 1800), (2800, 1300), (400, 2400), (1500, 900)],
                           shapes=("single", "double", "flutter", "late"))
    return x, {"shape": shape}


def bird_call(rng, sr, kind, f0):
    """One songbird call; kind picks the gesture."""
    if kind == "up":
        return tone(sr, 0.09, lambda u: f0 * (1 + 0.45 * u ** 1.5), ((1, 1.0), (2, 0.08)), env=lambda u: np.sin(np.pi * u) ** 2)
    if kind == "down":
        return tone(sr, 0.11, lambda u: f0 * (1.5 - 0.5 * u), ((1, 1.0), (2, 0.08)), env=lambda u: np.sin(np.pi * u) ** 1.5)
    if kind == "tsee":
        a = tone(sr, 0.07, lambda u: f0 * 1.6 * (1 + 0.04 * np.sin(np.pi * u)), ((1, 1.0),), env=lambda u: np.sin(np.pi * u) ** 2)
        return L.mix(a, (a, 0.8, 0.12))
    if kind == "trill":
        n = L.secs(0.28, sr)
        u = np.linspace(0, 1, n)
        am = (0.5 + 0.5 * np.sin(TAU * rng.uniform(26, 34) * u * 0.28)) ** 2
        return tone(sr, 0.28, lambda u: f0 * (1.25 - 0.3 * u), ((1, 1.0),), env=lambda u: np.sin(np.pi * u)) * am
    if kind == "warble":
        return tone(sr, 0.22, lambda u: f0 * (1.1 + 0.18 * np.sin(TAU * 11 * u * 0.22)), ((1, 1.0), (2, 0.1)), env=lambda u: np.sin(np.pi * u) ** 1.2)
    if kind == "chips":
        c = tone(sr, 0.035, lambda u: f0 * (1.3 - 0.4 * u), ((1, 1.0),), env=lambda u: np.sin(np.pi * u))
        return L.mix(*[(c, 1.0 - 0.12 * k, k * rng.uniform(0.06, 0.08)) for k in range(4)])
    if kind == "dee":
        c = tone(sr, 0.04, lambda u: f0 * (1.4 - 0.4 * u), ((1, 1.0),), env=lambda u: np.sin(np.pi * u))
        d = tone(sr, 0.16, f0 * 0.62, ((1, 1.0), (2, 0.5), (3, 0.3)), env=lambda u: np.sin(np.pi * u) ** 0.7)
        d = d * (0.6 + 0.4 * np.sin(np.linspace(0, TAU * 0.16 * 70, d.size)))
        return L.mix(c, (c, 0.9, 0.09), (d, 0.6, 0.19), (d, 0.55, 0.38))
    if kind == "peep":
        p = tone(sr, 0.05, f0 * 1.1, ((1, 1.0),), env=lambda u: np.sin(np.pi * u) ** 2)
        return L.mix(p, (p, 0.85, 0.14), (p, 0.7, 0.28))
    if kind == "zwee":
        return tone(sr, 0.18, lambda u: f0 * (0.8 + 0.7 * u), ((1, 1.0), (2, 0.2), (3, 0.08)), env=lambda u: np.sin(np.pi * u) ** 0.8 * (0.7 + 0.3 * np.sin(TAU * 40 * u * 0.18)))
    raise KeyError(kind)


@family("fx", "chirp", 6, ref=lambda: ref_fx("chirp"))
def fx_chirp(rng, i):
    kind, f0 = L.cycle(i, ["tsee", "trill", "up", "warble", "chips", "dee"], [3100, 3600, 2700, 4100, 3300])
    x = bird_call(rng, SR, kind, f0 * rng.uniform(0.97, 1.03))
    if kind in ("up", "warble"):   # a second, answering call
        x = L.mix(x, (bird_call(rng, SR, "down" if kind == "up" else "up", f0 * 1.12), 0.6, rng.uniform(0.18, 0.26)))
    return room(x, SR, rng, 0.2, 0.06), {"kind": kind}


@family("fx", "drink", 5, ref=lambda: ref_fx("drink"))
def fx_drink(rng, i):
    gulps, f0, extra = L.cycle(i, [3, 4, 2, 5, 3], [260, 220, 300, 240, 200], ["none", "slurp", "ahh", "none", "slurp"])
    out = np.zeros(L.secs(1.0, SR))
    at = 0.0
    if extra == "slurp":
        L.place(out, sweep_noise(rng, SR, 0.15, 1800, 3500, q=2.0), 0.0, SR, 0.4)
        at = 0.14
    for k in range(gulps):
        g = bloop(SR, rng, f0 * rng.uniform(0.92, 1.08), rng.uniform(0.08, 0.11), rise=rng.uniform(1.6, 1.9), tau=0.45)
        g = L.mix(g, (L.lp(L.white(g.size, rng), SR, 900) * np.exp(-L.tvec(g.size, SR) / 0.02), 0.3))
        L.place(out, g, at, SR, 1.0 - 0.08 * k)
        at += rng.uniform(0.11, 0.16) if gulps > 2 else rng.uniform(0.17, 0.22)
    if extra == "ahh":
        d = 0.3
        n = L.secs(d, SR)
        breath = L.bp(L.pink(n, rng), SR, 500, 2200) * shape_env("front", n, rng, d)
        L.place(out, L.norm_peak(breath), at + 0.05, SR, 0.35)
    return out, {"gulps": gulps, "extra": extra}


@family("fx", "canvas", 5, ref=lambda: ref_fx("leaves"))
def fx_canvas(rng, i):
    """Tent canvas: flaps (low fabric whumps) and nylon rustle."""
    kind = ["flap", "double", "flap_rustle", "pats", "billow"][i]
    out = np.zeros(L.secs(0.9, SR))

    def flap(r, size=1.0):
        d = r.uniform(0.09, 0.14) * size
        n = L.secs(d, SR)
        t = L.tvec(n, SR)
        w = L.lp(L.white(n, r), SR, 500 / size) * np.exp(-t / (0.025 * size)) * np.minimum(1, t / 0.002)
        snap = L.bp(L.white(n, r), SR, 1200, 4500) * np.exp(-t / 0.008)
        return L.norm_peak(w) + 0.4 * L.norm_peak(snap)
    if kind == "flap":
        L.place(out, flap(rng, 1.2), 0.0, SR)
    elif kind == "double":
        L.place(out, flap(rng), 0.0, SR)
        L.place(out, flap(rng, 0.8), rng.uniform(0.14, 0.2), SR, 0.7)
    elif kind == "flap_rustle":
        L.place(out, flap(rng), 0.0, SR)
        L.place(out, rustle(rng, SR, 0.4, "decay", 1500, 6000, density=250, bed=0.5), 0.05, SR, 0.5)
    elif kind == "pats":
        for k in range(3):
            L.place(out, flap(rng, 0.7), k * rng.uniform(0.11, 0.14), SR, 0.9 - 0.15 * k)
    else:
        d = 0.5
        n = L.secs(d, SR)
        bil = L.lp(L.brown(n, rng), SR, 300) * shape_env("late", n, rng, d)
        L.place(out, L.norm_peak(bil) * 0.7, 0.0, SR)
        L.place(out, flap(rng, 1.3), d * 0.85, SR)
    return out, {"kind": kind}


@family("fx", "hull", 5, ref=lambda: ref_fx("thud"))
def fx_hull(rng, i):
    """Boat hull: low wooden creak (contour) with water lapping and a bump on the jetty."""
    kind = ["rise", "fall", "two", "bump", "lap"][i]
    out = np.zeros(L.secs(1.2, SR))
    body = (110, 260, 520, 900, 1500)
    if kind in ("rise", "two"):
        L.place(out, creak(rng, SR, 0.55, 95, 140, body=body, rough=0.25, wobble=5), 0.05, SR)
    if kind == "fall":
        L.place(out, creak(rng, SR, 0.7, 150, 100, body=body, rough=0.28, wobble=4), 0.0, SR)
    if kind == "two":
        L.place(out, creak(rng, SR, 0.4, 135, 110, body=body, rough=0.22), 0.58, SR, 0.7)
    if kind == "bump":
        L.place(out, thump(SR, rng, 75, 0.3, 0.07, grit=0.5), 0.0, SR)
        L.place(out, knock(SR, rng, 210, "wood"), 0.0, SR, 0.5)
        L.place(out, creak(rng, SR, 0.4, 120, 105, body=body, rough=0.3), 0.18, SR, 0.6)
    if kind == "lap":
        L.place(out, creak(rng, SR, 0.35, 110, 125, body=body, rough=0.2), 0.3, SR, 0.4)
    d = 1.0
    n = L.secs(d, SR)
    lap = L.lp(L.brown(n, rng), SR, 900) * shape_env({"rise": "late", "fall": "front", "two": "double", "bump": "decay", "lap": "triple"}[kind], n, rng, d)
    L.place(out, L.norm_peak(lap), 0.0, SR, 0.25 if kind != "lap" else 0.8)
    return out, {"kind": kind}


@family("fx", "seat", 8, ref=lambda: ref_fx("pluck"))
def fx_seat(rng, i):
    """Sitting on a bench / chair: weight thump x creak contour (wood or a light metal cafe chair)."""
    kind, f0 = L.cycle(i, ["thump_up", "down", "double", "metal", "plank", "tick", "squeak", "settle"], [200, 260, 170, 300, 230])
    out = np.zeros(L.secs(0.8, SR))
    if kind in ("thump_up", "plank", "tick"):
        L.place(out, thump(SR, rng, rng.uniform(80, 110), 0.2, 0.04, grit=0.4), 0.0, SR, 0.8)
    if kind == "thump_up":
        L.place(out, creak(rng, SR, 0.35, f0, f0 * 1.3, rough=0.2, swell=0.05), 0.04, SR)
    elif kind == "down":
        L.place(out, creak(rng, SR, 0.45, f0 * 1.3, f0, rough=0.18, swell=0.06), 0.0, SR)
    elif kind == "double":
        L.place(out, creak(rng, SR, 0.25, f0, f0 * 1.15, rough=0.22, swell=0.04, release=0.1), 0.0, SR)
        L.place(out, creak(rng, SR, 0.3, f0 * 1.2, f0 * 1.05, rough=0.22, swell=0.04, release=0.12), 0.3, SR, 0.75)
    elif kind == "metal":
        L.place(out, knock(SR, rng, f0 * 4.5, "metal", dur=0.25), 0.0, SR, 0.5)
        L.place(out, creak(rng, SR, 0.25, f0 * 2.2, f0 * 2.6, body=(600, 1300, 2500), q=9, rough=0.08, metal=True, release=0.1), 0.05, SR, 0.8)
    elif kind == "plank":
        L.place(out, knock(SR, rng, f0 * 1.6, "wood"), 0.01, SR, 0.6)
        L.place(out, creak(rng, SR, 0.3, f0 * 0.9, f0 * 0.8, rough=0.25), 0.12, SR, 0.6)
    elif kind == "tick":
        L.place(out, creak(rng, SR, 0.3, f0 * 1.25, f0 * 0.95, rough=0.12, q=9), 0.0, SR, 0.8)
        for k in range(3):
            L.place(out, knock(SR, rng, rng.uniform(1500, 2200), "wood", dur=0.04), 0.32 + k * 0.06, SR, 0.45)
    elif kind == "squeak":
        L.place(out, creak(rng, SR, 0.18, f0 * 2.4, f0 * 2.9, body=(500, 1100, 2100), q=10, rough=0.05, release=0.06, swell=0.02), 0.0, SR, 0.7)
        L.place(out, creak(rng, SR, 0.14, f0 * 2.8, f0 * 2.5, body=(500, 1100, 2100), q=10, rough=0.05, release=0.05, swell=0.02), 0.2, SR, 0.4)
    else:
        L.place(out, fabric_puff(SR, rng, 0.18, 400, 0.4), 0.0, SR, 0.8)
        L.place(out, creak(rng, SR, 0.5, f0 * 0.8, f0 * 0.7, rough=0.3, wobble=4, swell=0.15), 0.08, SR, 0.7)
    return out, {"kind": kind}


def fabric_puff(sr, rng, d=0.22, lp_hz=420, air=0.35):
    n = L.secs(d, sr)
    t = L.tvec(n, sr)
    e = np.minimum(1, t / 0.006) * np.exp(-t / (d * 0.3))
    w = L.lp(L.brown(n, rng), sr, lp_hz) * e
    a = L.bp(L.white(n, rng), sr, 900, 3200) * e ** 1.5
    return L.norm_peak(w) + air * L.norm_peak(a)


@family("fx", "cushion", 6, ref=lambda: ref_fx("thud"))
def fx_cushion(rng, i):
    """Lounger / cushions: fabric puff x springs or frame."""
    kind = ["puff", "spring", "sink", "long", "frame", "pat"][i]
    out = np.zeros(L.secs(0.8, SR))
    if kind == "puff":
        L.place(out, fabric_puff(SR, rng, 0.25), 0.0, SR)
    elif kind == "spring":
        L.place(out, fabric_puff(SR, rng, 0.16, 520, 0.2), 0.0, SR, 0.7)
        for k in range(2):
            L.place(out, creak(rng, SR, 0.16, 700 + 120 * k, 820 + 60 * k, body=(800, 1700, 3000), q=10, rough=0.06, metal=True, release=0.06, swell=0.02),
                    0.04 + k * 0.17, SR, 0.7 - 0.2 * k)
    elif kind == "sink":
        L.place(out, fabric_puff(SR, rng, 0.18, 500), 0.0, SR)
        L.place(out, fabric_puff(SR, rng, 0.3, 300, 0.2), 0.16, SR, 0.8)
    elif kind == "long":
        d = 0.55
        n = L.secs(d, SR)
        w = L.lp(L.brown(n, rng), SR, 350) * shape_env("front", n, rng, d)
        L.place(out, L.norm_peak(w), 0.0, SR)
        L.place(out, rustle(rng, SR, 0.4, "decay", 900, 4000, density=120, bed=0.4), 0.05, SR, 0.35)
    elif kind == "frame":
        L.place(out, fabric_puff(SR, rng, 0.2, 450), 0.0, SR)
        L.place(out, knock(SR, rng, 980, "metal", dur=0.2), 0.03, SR, 0.25)
        L.place(out, creak(rng, SR, 0.25, 300, 360, rough=0.12), 0.08, SR, 0.4)
    else:
        for k in range(2):
            L.place(out, fabric_puff(SR, rng, 0.12, 550, 0.5), k * rng.uniform(0.14, 0.19), SR, 1.0 - 0.25 * k)
    return out, {"kind": kind}


SPEAKER_SONGS = [  # (midi, beats, beat s, voice)
    ([67, 72, 76, 74, 72, 74, 76, 79], [1, 1, 1, 1, 1, 1, 1, 2], 0.16, "square"),
    ([72, 72, 79, 79, 81, 81, 79], [1, 1, 1, 1, 1, 1, 2], 0.18, "flute"),
    ([76, 74, 72, 74, 76, 76, 76], [1, 1, 1, 1, 1, 1, 2], 0.17, "marimba"),
    ([60, 64, 67, 72, 67, 64, 60, 67], [0.5] * 7 + [2], 0.2, "square"),
    ([79, 77, 76, 74, 72, 71, 72], [1, 0.5, 0.5, 1, 1, 1, 2], 0.17, "kalimba"),
    ([69, 72, 76, 81, 79, 76, 72], [1, 1, 1, 1.5, 0.5, 1, 2], 0.15, "flute"),
]


@family("fx", "speaker", 6, ref=lambda: ref_fx("tune"))
def fx_speaker(rng, i):
    """Little outdoor speaker: six different short songs through a small, band-limited driver."""
    midi, beats, beat, voice = SPEAKER_SONGS[i]
    x = melody(rng, SR, midi, beats, beat * rng.uniform(0.97, 1.03), voice, gain_tail=0.95)
    if i % 2 == 0:    # bass line under the even songs
        bass = melody(rng, SR, [m - 24 for m in midi[::2]], [b * 2 for b in beats[::2]][: len(midi[::2])], beat, "marimba")
        x = L.mix(x, (bass, 0.35))
    x = L.bp(x, SR, 280, 6500, order=2)
    x = L.saturate(x, drive=1.6, asym=0.1, mix=0.5)
    return cap(x, SR, 2.6), {"voice": voice}


@family("fx", "dragonfly", 4, ref=lambda: ref_fx("whoosh"))
def fx_dragonfly(rng, i):
    """Dragonfly wings: a buzzing wingbeat along a flight path (pass-by, hover-dart, zigzag, away)."""
    path = ["pass", "hover", "zigzag", "away"][i]
    d = {"pass": 1.6, "hover": 2.0, "zigzag": 1.9, "away": 1.5}[path] * rng.uniform(0.95, 1.05)
    n = L.secs(d, SR)
    u = np.linspace(0, 1, n)
    if path == "pass":
        amp, pitch = bump(u, 0.45, 0.22), 1.06 - 0.12 * u
    elif path == "hover":
        amp, pitch = np.minimum(u / 0.15, 1) * np.where(u < 0.6, 0.8, 0.8 + 0.5 * bump(u, 0.75, 0.1)) * np.clip((1 - u) / 0.2, 0, 1), 1.0 + 0.1 * (u > 0.65)
    elif path == "zigzag":
        amp, pitch = (bump(u, 0.2, 0.1) + 0.8 * bump(u, 0.5, 0.1) + 0.6 * bump(u, 0.8, 0.1)), 1.0 + 0.05 * np.sin(TAU * 3 * u)
    else:
        amp, pitch = np.minimum(u / 0.05, 1) * np.exp(-u * 3.2), 1.02 - 0.08 * u
    beat = rng.uniform(28, 38)
    f0 = rng.uniform(140, 190)
    wing = (0.5 + 0.5 * np.sin(TAU * np.cumsum(beat * pitch) / SR)) ** 3
    buzz = L.osc(SR, f0 * pitch * (1 + 0.02 * np.sin(TAU * 7 * u)), ((1, 0.6), (2, 1.0), (3, 0.5), (4, 0.3), (6, 0.12)))
    rasp = L.bp(L.white(n, rng), SR, 1000, 4500)
    x = (0.6 * buzz + 0.5 * L.norm_peak(rasp)) * wing * amp
    return x, {"path": path}


@family("fx", "sputter", 4, ref=lambda: ref_fx("crackle"))
def fx_sputter(rng, i):
    """Fire sputter: sap hiss, pop cluster, log settling, steam whistle."""
    kind = ["hiss_pop", "pops", "settle", "whistle"][i]
    out = np.zeros(L.secs(1.0, SR))
    pop = lambda r: L.bp(r.standard_normal(L.secs(0.02, SR)), SR, 1200, 6000) * np.exp(-L.tvec(L.secs(0.02, SR), SR) / r.uniform(0.002, 0.006))
    if kind == "hiss_pop":
        d = 0.5
        n = L.secs(d, SR)
        h = L.hp(L.white(n, rng), SR, 2500) * shape_env("swell", n, rng, d) * (0.6 + 0.4 * np.sin(TAU * 17 * L.tvec(n, SR)))
        L.place(out, L.norm_peak(h) * 0.6, 0.0, SR)
        L.place(out, pop(rng), d * 0.9, SR)
    elif kind == "pops":
        L.place(out, L.scatter(SR, 0.35, rng, pop, count=7, gain=(0.4, 1.0)), 0.0, SR)
    elif kind == "settle":
        L.place(out, thump(SR, rng, 60, 0.3, 0.07, grit=0.7), 0.0, SR)
        L.place(out, L.scatter(SR, 0.5, rng, pop, density=30, env=np.linspace(1, 0.1, 32), gain=(0.2, 0.8)), 0.05, SR)
    else:
        d = 0.6
        w = tone(SR, d, lambda u: 2200 + 600 * u, ((1, 1.0),), env=lambda u: np.sin(np.pi * u) ** 2)
        L.place(out, w * 0.35, 0.05, SR)
        n = L.secs(d, SR)
        L.place(out, L.norm_peak(L.hp(L.white(n, rng), SR, 3000) * shape_env("swell", n, rng, d)) * 0.4, 0.0, SR)
        L.place(out, pop(rng), 0.0, SR, 0.6)
    return out, {"kind": kind}


def firepit_loop(rng, seconds=12.0, sr=SR):
    """Positional campfire bed: roar, flicker and an even scatter of crackles, then loopified."""
    n = L.secs(seconds + 0.2, sr)
    t = L.tvec(n, sr)
    roar = L.lp(L.brown(n, rng), sr, 320)
    flick = L.bp(L.pink(n, rng), sr, 600, 2500) * (0.55 + 0.45 * L.lp(rng.standard_normal(n), sr, 3.0) / 0.2)
    pop = lambda r: L.bp(r.standard_normal(L.secs(0.02, sr)), sr, 1400, 7500) * np.exp(-L.tvec(L.secs(0.02, sr), sr) / r.uniform(0.0012, 0.005))
    pops = L.scatter(sr, seconds + 0.2, rng, pop, density=9, gain=(0.05, 0.8))[:n]
    small = L.scatter(sr, seconds + 0.2, rng, pop, density=40, gain=(0.02, 0.15))[:n]
    x = L.norm_peak(roar) * 0.5 + L.norm_peak(flick) * 0.12 + L.norm_peak(L.pad_to(pops, n)) * 0.8 + L.norm_peak(L.pad_to(small, n)) * 0.25
    x = L.remove_dc(x, sr)
    return L.loopify(x, sr, 0.2)


# =========================================================================== field (field_objects.play)
def creak_script(rng, sr, events, body, total=1.8, **kw):
    """Play a list of creak events: (at s, length s, f_start, f_end, gain[, overrides dict])."""
    out = np.zeros(L.secs(total, sr))
    for ev in events:
        at, length, f0, f1, g = ev[:5]
        opts = dict(kw)
        if len(ev) > 5:
            opts.update(ev[5])
        j = rng.uniform(0.97, 1.03)
        L.place(out, creak(rng, sr, length * rng.uniform(0.95, 1.05), f0 * j, f1 * j, body=opts.pop("body", body), **opts),
                at * rng.uniform(0.97, 1.03), sr, g)
    return out


def chain_rattle(rng, sr, count=5, span=0.25):
    return L.scatter(sr, span, rng, lambda r: knock(sr, r, r.uniform(2500, 4200), "metal", dur=0.05), count=count, gain=(0.1, 0.3))


# Swing chains (the original creak_soft.wav is a 520->600 squeak, then 560->500 at 0.75 s).
CREAK_SOFT_RECIPES = [
    ([(0.0, 0.5, 600, 520, 0.6), (0.62, 0.42, 500, 580, 0.45)], "rattle"),               # fall then rise, rattle
    ([(0.0, 1.0, 560, 560, 0.6, {"wobble": 3.0, "swell": 0.3, "release": 0.4})], None),   # one long wobbling squeak
    ([(0.0, 0.2, 600, 660, 0.55), (0.3, 0.2, 640, 590, 0.5), (0.6, 0.22, 610, 670, 0.45)], None),   # quick swinging
    ([(0.0, 0.4, 680, 740, 0.55), (0.6, 0.38, 720, 650, 0.45)], None),                   # high pair
    ([(0.0, 0.55, 430, 480, 0.6), (0.95, 0.5, 470, 420, 0.5)], None),                    # low pair, slow swing
    ([(0.0, 0.45, 540, 610, 0.6)], "clink"),                                             # squeak and a chain clink at the turn
    ([(0.0, 0.3, 500, 560, 0.6), (0.42, 0.3, 520, 560, 0.25)], None),                    # strong then faint
    ([(0.0, 0.12, 620, 680, 0.55), (0.15, 0.12, 640, 690, 0.5), (0.7, 0.3, 600, 560, 0.5)], None),   # eek-eek ... eek
    ([(0.0, 0.25, 640, 520, 0.6), (0.24, 0.3, 520, 640, 0.6)], None),                    # V-shaped squeak
    ([(0.0, 0.6, 580, 470, 0.6)], "rattle"),                                             # falling, rattle
]


@family("field", "creak_soft", 10, ref=lambda: ref_field("creak_soft"))
def field_creak_soft(rng, i):
    """Swing chains: ten different squeak rhythms (single, pairs, quick swings, V-shapes) and chain noises."""
    events, extra = CREAK_SOFT_RECIPES[i]
    out = creak_script(rng, SR, events, (600, 1300, 2500), q=9, rough=0.06, swell=0.1, release=0.25, metal=True)
    if extra == "rattle":
        L.place(out, chain_rattle(rng, SR), rng.uniform(0.05, 0.35), SR)
    elif extra == "clink":
        L.place(out, knock(SR, rng, rng.uniform(1800, 2400), "metal", dur=0.3), 0.42, SR, 0.3)
    return room(out, SR, rng, 0.2, 0.05), {"recipe": i, "extra": extra}


# Rocking chair (the original wood_creak.wav is 180->230, then 210->170 at 0.7 s).
WOOD_RECIPES = [
    ([(0.0, 0.8, 160, 240, 0.8, {"wobble": 5.0})], None),                                  # one long rising groan
    ([(0.0, 0.2, 210, 240, 0.7), (0.3, 0.2, 230, 200, 0.6), (0.6, 0.2, 215, 245, 0.55)], None),   # quick rocking
    ([(0.0, 0.4, 240, 190, 0.8), (0.5, 0.4, 185, 230, 0.6)], "rail"),                        # fall, rise, rail knock
    ([(0.12, 0.45, 200, 230, 0.8)], "land"),                                                 # rail lands, then creak
    ([(0.0, 0.9, 125, 150, 0.9, {"rough": 0.3, "wobble": 3.0})], None),                     # low slow groan
    ([(0.0, 0.25, 300, 340, 0.6), (0.4, 0.22, 330, 290, 0.5)], None),                      # high joint squeak pair
    ([(0.0, 0.45, 190, 225, 0.8), (0.95, 0.4, 220, 185, 0.55)], None),                     # slow rock, long gap
    ([(0.0, 0.35, 230, 200, 0.8)], "ticks"),                                                 # creak and two joint ticks
    ([(0.0, 0.18, 170, 200, 0.8), (0.2, 0.18, 200, 215, 0.6), (0.4, 0.3, 215, 180, 0.6)], None),   # stick-slip grabs
    ([(0.0, 0.5, 260, 175, 0.8)], "floor"),                                                  # falling creak, floor knock
]


@family("field", "wood_creak", 10, ref=lambda: ref_field("wood_creak"))
def field_wood_creak(rng, i):
    """Rocking chair: ten creak rhythms (groans, quick rocks, pairs, grabs) with rail and joint knocks."""
    events, extra = WOOD_RECIPES[i]
    out = creak_script(rng, SR, events, (200, 450, 900, 1600), rough=0.2, swell=0.08)
    if extra in ("rail", "floor"):
        L.place(out, knock(SR, rng, rng.uniform(260, 340), "wood"), 0.42 if extra == "rail" else 0.5, SR, 0.4)
    elif extra == "land":
        L.place(out, L.mix(knock(SR, rng, 300, "wood"), (thump(SR, rng, 95, 0.15, 0.03, grit=0.4), 0.6)), 0.0, SR, 0.6)
    elif extra == "ticks":
        for k in range(2):
            L.place(out, knock(SR, rng, rng.uniform(1300, 1900), "wood", dur=0.04), 0.38 + k * 0.08, SR, 0.35)
    return room(out, SR, rng, 0.2, 0.04), {"recipe": i, "extra": extra}


@family("field", "hammock", 8, ref=lambda: ref_field("wood_creak"))
def field_hammock(rng, i):
    """Hammock rope on the posts: eight gestures (stretch, sway pair, bark rub, long groan, twang, knot
    squeeze, quick sways, settle) with cloth."""
    kind = ["stretch", "pair", "rub", "long", "twang", "knot", "sways", "settle"][i]
    f0 = [170, 220, 140, 260, 195, 230, 205, 155][i] * rng.uniform(0.98, 1.02)
    out = np.zeros(L.secs(1.6, SR))
    rope = (f0 * 1.2, f0 * 2.6, f0 * 5.0)
    if kind == "stretch":
        L.place(out, creak(rng, SR, 0.6, f0, f0 * 1.25, body=rope, q=5, rough=0.32, wobble=6, swell=0.2), 0.0, SR)
    elif kind == "pair":
        L.place(out, creak(rng, SR, 0.4, f0 * 1.2, f0, body=rope, q=5, rough=0.3, swell=0.1), 0.0, SR)
        L.place(out, creak(rng, SR, 0.45, f0 * 0.95, f0 * 1.15, body=rope, q=5, rough=0.3, swell=0.12), 0.62, SR, 0.7)
    elif kind == "rub":
        L.place(out, rustle(rng, SR, 0.6, "double", 700, 3500, density=200, bed=0.6), 0.0, SR, 0.6)
        L.place(out, creak(rng, SR, 0.35, f0, f0 * 1.1, body=rope, q=4, rough=0.35), 0.2, SR, 0.8)
    elif kind == "long":
        L.place(out, creak(rng, SR, 1.0, f0 * 1.15, f0 * 0.9, body=rope, q=6, rough=0.28, wobble=3, swell=0.25, release=0.4), 0.0, SR)
    elif kind == "twang":
        L.place(out, creak(rng, SR, 0.3, f0, f0 * 1.3, body=rope, q=6, rough=0.25), 0.0, SR)
        L.place(out, L.ks_pluck(SR, f0 * 0.5, 0.4, rng=rng, damping=0.985, bright=0.2), 0.28, SR, 0.4)
    elif kind == "knot":   # fibres squeezing: a crackle of tiny grabs rising in pitch
        for k in range(7):
            L.place(out, creak(rng, SR, 0.06, f0 * (1 + 0.06 * k), f0 * (1.05 + 0.06 * k), body=rope, q=4, rough=0.4, swell=0.01, release=0.03),
                    k * rng.uniform(0.05, 0.08), SR, rng.uniform(0.5, 0.9))
    elif kind == "sways":
        for k in range(3):
            up = k % 2 == 0
            L.place(out, creak(rng, SR, 0.22, f0 * (1.0 if up else 1.2), f0 * (1.2 if up else 1.0), body=rope, q=5, rough=0.3, release=0.08),
                    k * 0.36, SR, 0.85 - 0.15 * k)
    else:
        L.place(out, fabric_puff(SR, rng, 0.25, 350, 0.3), 0.0, SR, 0.8)
        L.place(out, creak(rng, SR, 0.7, f0 * 1.3, f0, body=rope, q=5, rough=0.3, swell=0.05, release=0.4), 0.05, SR, 0.8)
    L.place(out, rustle(rng, SR, 0.4, "decay", 1200, 5000, density=90, bed=0.3), rng.uniform(0.0, 0.3), SR, 0.25)
    return room(out, SR, rng, 0.25, 0.04), {"kind": kind}


@family("field", "paper", 6, ref=lambda: ref_field("paper"))
def field_paper(rng, i):
    """Notes and letters: crumple, page flip, sheet flapping, slide, two rustles, pinned note tapped."""
    kind = ["crumple", "flip", "flap", "slide", "two", "pin"][i]
    out = np.zeros(L.secs(0.8, SR))
    if kind == "crumple":
        L.place(out, rustle(rng, SR, 0.5, "swell", 2500, 9000, density=150, bed=0.15, glen=(0.002, 0.008)), 0.0, SR)
    elif kind == "flip":
        d = 0.22
        n = L.secs(d, SR)
        L.place(out, sweep_noise(rng, SR, d, 1500, 5000, q=0.8, env=shape_env("late", n, rng, d)), 0.0, SR)
        L.place(out, fabric_puff(SR, rng, 0.08, 900, 0.8), d * 0.92, SR, 0.6)
    elif kind == "flap":   # a loose sheet slapping in the breeze: low "pap" transients
        for k in range(4):
            d = 0.05
            n = L.secs(d, SR)
            pap = L.bp(L.white(n, rng), SR, 400, 2500) * np.exp(-L.tvec(n, SR) / 0.008)
            L.place(out, L.norm_peak(pap), k * rng.uniform(0.09, 0.12), SR, 1.0 - 0.18 * k)
    elif kind == "slide":
        d = 0.4
        n = L.secs(d, SR)
        L.place(out, L.bp(L.pink(n, rng), SR, 800, 4000) * shape_env("front", n, rng, d), 0.0, SR)
    elif kind == "two":
        L.place(out, rustle(rng, SR, 0.25, "decay", 2500, 8000, density=200, bed=0.2), 0.0, SR)
        L.place(out, rustle(rng, SR, 0.25, "decay", 2000, 7000, density=200, bed=0.2), 0.3, SR, 0.8)
    else:
        L.place(out, knock(SR, rng, 2600, "wood", dur=0.04), 0.0, SR, 0.4)
        L.place(out, rustle(rng, SR, 0.35, "double", 2200, 8500, density=260, bed=0.25), 0.03, SR)
    return room(out, SR, rng, 0.15, 0.04), {"kind": kind}


CHIME_SETS = [[1174.7, 1318.5, 1568.0, 1760.0, 2093.0, 2349.3], [1046.5, 1174.7, 1318.5, 1568.0, 1760.0],
              [1396.9, 1568.0, 1760.0, 2093.0, 2349.3, 2793.8], [880.0, 987.8, 1174.7, 1318.5, 1480.0]]


@family("field", "chimes", 8, ref=lambda: ref_field("chimes"))
def field_chimes(rng, i):
    """Wind chimes: tuning set x strike count x tempo (cascade, gust, lazy, clatter)."""
    notes, count, tempo = L.cycle(i, CHIME_SETS, [9, 6, 12, 5, 8], [0.11, 0.075, 0.16])
    s = S(rng, SR)
    out = np.zeros(L.secs(2.2, SR))
    at = 0.02
    for k in range(count):
        f = rng.choice(notes)
        L.place(out, arr(V.tube(s, f, 1.6, rng.uniform(0.8, 1.1))), at, SR, 0.3 * (0.9 ** k))
        at += tempo * rng.uniform(0.5, 1.5)
    return cap(room(out, SR, rng, 0.25, 0.08), SR, 1.8, 0.4), {"count": count, "tempo": tempo}


@family("field", "birds", 10, ref=lambda: ref_field("birds"))
def field_birds(rng, i):
    """Flock lifting off: wing flutters x chirps x call type."""
    flaps, chirps, kind = L.cycle(i, [5, 3, 7, 4], [4, 2, 0, 3, 5], ["up", "chips", "down", "peep", "tsee"])
    out = np.zeros(L.secs(1.4, SR))
    n = L.secs(0.9, SR)
    t = L.tvec(n, SR)
    for k in range(flaps):
        rate = rng.uniform(13, 21)
        beats = (0.5 + 0.5 * np.sin(TAU * rate * t + rng.uniform(0, 6))) ** 3
        flap = L.bp(L.white(n, rng), SR, 500, 4000) * beats * np.exp(-t / rng.uniform(0.3, 0.5)) * np.minimum(t / 0.02, 1)
        L.place(out, flap, k * rng.uniform(0.02, 0.06), SR, 0.5)
    for c in range(chirps):
        L.place(out, bird_call(rng, SR, kind, rng.uniform(3000, 4400)), 0.08 + c * rng.uniform(0.1, 0.17), SR, 0.25)
    return room(out, SR, rng, 0.3, 0.06), {"flaps": flaps, "chirps": chirps}


@family("field", "whoosh", 5, ref=lambda: ref_field("whoosh"))
def field_whoosh(rng, i):
    """Signpost travel: a swoosh (shape / sweep) and a two-note chime."""
    x, shape = whoosh_take(rng, SR, i, [0.9, 0.75, 1.0, 0.8, 0.95], [(300, 2500), (2400, 500), (500, 1800), (1500, 3000), (2000, 900)],
                           shapes=("single", "double", "flutter", "late", "single"))
    pair = [(1568.0, 2093.0), (2093.0, 1568.0), (1318.5, 1760.0), (1760.0, 2349.3), (1174.7, 1568.0)][i]
    s = S(rng, SR)
    x = L.mix(x, (arr(V.tube(s, pair[0], 1.0, 0.6)), 0.2, x.size / SR * 0.6), (arr(V.tube(s, pair[1], 1.0, 0.6)), 0.16, x.size / SR * 0.6 + rng.uniform(0.06, 0.1)))
    return room(x, SR, rng, 0.35, 0.1), {"shape": shape}


@family("field", "lid", 5, ref=lambda: ref_field("lid"))
def field_lid(rng, i):
    """Mailbox opening: tin hinge (contour) and the flap clapping open (pitch, rattle)."""
    hinge, clap_f, rattle = L.cycle(i, [(700, 820), (850, 720), (640, 760), (780, 900), (900, 800)], [920, 1180, 780, 1350, 1040], [False, True])
    out = np.zeros(L.secs(0.7, SR))
    lh = rng.uniform(0.14, 0.24)
    L.place(out, creak(rng, SR, lh, *hinge, body=(800, 1700, 3000), q=10, rough=0.08, release=0.06, swell=0.02, metal=True), 0.0, SR, 0.4)
    L.place(out, knock(SR, rng, clap_f, "metal", dur=0.25), lh * 0.95, SR, 0.7)
    if rattle:
        L.place(out, knock(SR, rng, clap_f * 1.07, "metal", dur=0.15), lh * 0.95 + rng.uniform(0.05, 0.08), SR, 0.3)
    return room(out, SR, rng, 0.2, 0.05), {"hinge": hinge, "rattle": rattle}


@family("field", "coin", 5, sr=BR, ref=lambda: ref_field("coin"))
def field_coin(rng, i):
    """Wishing well coin: rim bounce, spin on the rim, deep drop, quick flips, skip (two plops)."""
    kind = ["rim", "spin", "deep", "flips", "skip"][i]
    ping = [4100, 3700, 4500, 3900, 4300][i] * rng.uniform(0.99, 1.01)
    s = S(rng, BR)
    out = np.zeros(L.secs(1.9, BR))
    L.place(out, arr(V.bell(s, ping, 0.5, ratios=(1, 1.53, 2.4, 3.1), decay=0.18 if kind != "deep" else 0.35, amps=[1, .5, .3, .2])), 0.0, BR, 0.35)

    def plop(at, size=1.0, f0=None):
        n = L.secs(0.25, BR)
        t = L.tvec(n, BR)
        f = (f0 or rng.uniform(420, 600)) / size
        pl = np.sin(TAU * np.cumsum(f + 900 / size * (1 - np.exp(-t / 0.03))) / BR) * np.exp(-t / (0.05 * size))
        L.place(out, pl * 0.6 + L.bp(L.white(n, rng), BR, 400, 2500) * np.exp(-t / 0.02) * 0.3, at, BR, min(1.0, size))
    if kind == "rim":
        L.place(out, L.mix(knock(BR, rng, ping * 0.55, "metal", dur=0.2), (knock(BR, rng, 1800, "stone"), 0.6)), 0.22, BR, 0.4)
        plop(0.82)
    elif kind == "spin":   # rolls round the rim, faster and faster, before it drops
        at, gap = 0.15, 0.09
        for k in range(16):
            L.place(out, knock(BR, rng, ping * rng.uniform(0.6, 0.7), "metal", dur=0.05), at, BR, 0.18 * (1 - k / 24))
            at += gap
            gap *= 0.9
        plop(at + 0.35)
    elif kind == "deep":
        plop(1.05, 1.3)
        for k in range(2):
            L.place(out, bloop(BR, rng, rng.uniform(900, 1300), 0.05, rise=2.5), 1.35 + k * 0.17, BR, 0.2)
    elif kind == "flips":
        for k in range(5):
            L.place(out, arr(V.bell(s, ping * rng.uniform(1.03, 1.1), 0.2, ratios=(1, 1.6), decay=0.05, amps=[1, .4])), 0.07 + k * 0.05, BR, 0.12)
        plop(0.55, 0.8)
    else:
        plop(0.68, 0.9)
        plop(0.83, 0.6, 750)
    x = L.reverb(out, BR, room=0.55, wet=0.35, rng=rng)
    return cap(x, BR, 1.85), {"kind": kind}


@family("field", "water", 5, ref=lambda: ref_field("water"))
def field_water(rng, i):
    """Drinking fountain: tap squeak or not, stream length and pulse, drips."""
    squeak, length, pulse, drips = L.cycle(i, [True, False], [1.0, 0.7, 1.2, 0.85, 1.1], [11, 6, 15], [10, 4, 7])
    out = np.zeros(L.secs(1.8, SR))
    at = 0.0
    if squeak:
        L.place(out, creak(rng, SR, 0.12, 900, 1100, body=(1200, 2600), q=10, rough=0.05, release=0.05, swell=0.01), 0.0, SR, 0.25)
        at = 0.08
    n = L.secs(length, SR)
    t = L.tvec(n, SR)
    stream = L.bp(L.white(n, rng), SR, 900, 5200) * np.minimum(t / 0.05, 1) * np.clip((length - t) / 0.25, 0, 1)
    stream *= 0.8 + 0.2 * np.sin(TAU * pulse * t)
    L.place(out, stream * 0.5, at, SR)
    for _ in range(drips):
        L.place(out, bloop(SR, rng, rng.uniform(700, 1500), 0.06, rise=2.5, tau=0.25), at + rng.uniform(0.02, length + 0.15), SR, 0.35)
    return cap(room(out, SR, rng, 0.3, 0.05), SR, 1.8), {"squeak": squeak, "length": length}


@family("field", "vane", 5, ref=lambda: ref_field("vane"))
def field_vane(rng, i):
    """Weather vane: two pushes, long fall in a gust, back-and-forth squeaks, spinning pivot ticks, gust first."""
    kind = ["pushes", "fall", "swing", "spin", "gust"][i]
    f0 = [760, 900, 650, 1050, 820][i] * rng.uniform(0.98, 1.02)
    body = [(700, 1500, 2700), (900, 1900, 3300), (1100, 2300, 3900), (800, 2100, 3600), (1000, 1700, 3000)][i]
    out = np.zeros(L.secs(1.5, SR))
    sq = lambda d, a, b, **kw: creak(rng, SR, d, a, b, body=body, q=12, rough=0.05, metal=True, **kw)
    wind_at, wind_g = None, 0.0
    if kind == "pushes":
        L.place(out, sq(0.3, f0, f0 * 1.2, swell=0.04, release=0.1), 0.0, SR, 0.5)
        L.place(out, sq(0.3, f0 * 1.1, f0 * 1.3, swell=0.04, release=0.1), 0.42, SR, 0.45)
    elif kind == "fall":   # swings round, knocks against its stop, a small rebound squeak
        L.place(out, sq(0.5, f0 * 1.25, f0 * 0.9, swell=0.05, release=0.15), 0.0, SR, 0.5)
        L.place(out, knock(SR, rng, rng.uniform(600, 800), "metal", dur=0.3), 0.5, SR, 0.5)
        L.place(out, sq(0.18, f0 * 0.95, f0 * 1.05, swell=0.03, release=0.06), 0.62, SR, 0.3)
    elif kind == "swing":
        for k in range(3):
            up = k % 2 == 0
            L.place(out, sq(0.16, f0 * (1.0 if up else 1.2), f0 * (1.2 if up else 1.0), swell=0.03, release=0.06), k * 0.26, SR, 0.5 - 0.1 * k)
    elif kind == "spin":
        at = 0.0
        for k in range(10):
            L.place(out, knock(SR, rng, rng.uniform(2400, 2900), "metal", dur=0.04), at, SR, 0.35)
            at += 0.05 + 0.012 * k
        L.place(out, sq(0.6, f0, f0 * 1.05, swell=0.2, release=0.3), 0.1, SR, 0.15)
    else:
        wind_at, wind_g = 0.0, 0.7
        L.place(out, sq(0.4, f0, f0 * 1.25, swell=0.1, release=0.15), 0.6, SR, 0.5)
    if wind_at is not None:
        s = S(rng, SR)
        L.place(out, arr(V.wind(s, rng.uniform(0.8, 1.1), 300, 1600, rng.uniform(0.15, 0.35), 0.5)), wind_at, SR, wind_g)
    return room(out, SR, rng, 0.3, 0.06), {"kind": kind}


@family("field", "gong", 4, ref=lambda: ref_field("gong"))
def field_gong(rng, i):
    """Gong: opera gong (pitch falls), hand-muted strike, soft mallet roll, double strike on a brighter gong."""
    kind = ["opera", "muted", "roll", "double"][i]
    f = [150.0, 122.0, 108.0, 136.0][i] * rng.uniform(0.99, 1.01)
    s = S(rng, SR)

    def strike(r, ratios, bright=1.0, attack=0.004, glide=0.0, dur=2.1):
        n = L.secs(dur, SR)
        t = L.tvec(n, SR)
        g = np.zeros(n)
        for k, q in enumerate(ratios):
            fr = f * q * (1 + r.normal(0, 0.004)) * (1 - glide * (1 - np.exp(-t / 0.5)))
            g += (1.0 if k == 0 else bright * 0.7 / (1 + 0.3 * k)) * np.sin(TAU * np.cumsum(fr) / SR + r.uniform(0, 6)) * np.exp(-t / (1.6 / (1 + 0.35 * k)))
        g *= np.minimum(1, t / attack)
        g = L.mix(g, (arr(V.low(V.click(s, 0.08, 100, 1200, 0.01), 1500)), 0.8))
        tt = L.tvec(g.size, SR)
        return g + L.bp(L.white(g.size, r), SR, 1200, 3800) * 0.06 * bright * (1 - np.exp(-tt / 0.25)) * np.exp(-tt / 0.9)
    if kind == "opera":
        x = strike(rng, [1, 2.0, 2.9, 4.1], bright=1.2, glide=0.09)
    elif kind == "muted":
        x = strike(rng, [1, 1.52, 2.03, 2.71, 3.3, 4.4], dur=1.2)
        n = x.size
        t = L.tvec(n, SR)
        x = x * np.where(t < 0.42, 1.0, np.exp(-(t - 0.42) / 0.06))
        x = L.mix(x, (fabric_puff(SR, rng, 0.12, 600, 0.6), 0.25, 0.42))
    elif kind == "roll":
        x = np.zeros(L.secs(2.2, SR))
        at = 0.0
        for k in range(7):
            L.place(x, strike(rng, [1, 1.47, 2.2, 3.1], bright=0.5, attack=0.03, dur=1.6), at, SR, 0.25 + 0.1 * k)
            at += 0.14 * (0.92 ** k)
    else:
        x = L.mix(strike(rng, [1, 1.6, 2.4, 3.6, 4.9], bright=1.6, attack=0.002), (strike(rng, [1, 1.6, 2.4, 3.6, 4.9], bright=2.0, attack=0.002), 0.9, 0.24))
    x = L.reverb(x, SR, room=0.65, wet=0.18, rng=rng)
    return cap(x, SR, 2.0, 0.45), {"kind": kind}


@family("field", "shutter", 5, sr=BR, ref=lambda: ref_field("shutter"))
def field_shutter(rng, i):
    """Cameras: double clack + lever, single clack + motor, small leaf shutter with a spring, mirror slap, instant camera eject."""
    kind = ["lever", "motor", "leaf", "slap", "instant"][i]
    s = S(rng, BR)
    out = np.zeros(L.secs(1.0, BR))
    f = rng.uniform(1600, 2100)
    clack = lambda ff, g=1.0: (arr(V.modal([ff, ff * 1.72, ff * 2.6], [0.012, 0.009, 0.006], [1, .6, .4], 0.06, s.rng)) + arr(V.click(s, 0.06, 2500, 9000, 0.002))) * g
    tick = lambda: arr(V.click(s, 0.02, 3000, 9000, 0.0015))
    if kind == "lever":
        L.place(out, clack(f), 0.0, BR, 0.8)
        L.place(out, clack(f * 0.85), 0.055, BR, 0.6)
        for j in range(3):
            L.place(out, tick(), 0.25 + j * 0.035, BR, 0.35)
    elif kind == "motor":
        L.place(out, clack(f), 0.0, BR, 0.8)
        n = L.secs(0.35, BR)
        whirr = L.bp(L.white(n, rng), BR, 2000, 7000) * (0.5 + 0.5 * np.sign(np.sin(TAU * 70 * L.tvec(n, BR)))) * np.hanning(n)
        L.place(out, whirr * 0.35, 0.1, BR)
    elif kind == "leaf":
        L.place(out, clack(f * 1.5), 0.0, BR, 0.6)
        L.place(out, tick(), 0.03, BR, 0.5)
        L.place(out, creak(rng, BR, 0.14, 2500, 2250, body=(2600, 4800), q=12, rough=0.04, metal=True, release=0.05, swell=0.01), 0.05, BR, 0.5)
        n = L.secs(0.2, BR)
        L.place(out, L.bp(L.white(n, rng), BR, 1500, 5000) * np.hanning(n) * 0.25, 0.3, BR)
    elif kind == "slap":
        L.place(out, thump(BR, rng, 180, 0.08, 0.015, grit=0.6), 0.0, BR, 0.6)
        L.place(out, clack(f * 0.7), 0.012, BR, 0.9)
        for j in range(5):
            L.place(out, tick(), 0.3 + j * 0.028, BR, 0.3)
    else:
        L.place(out, clack(f * 1.2), 0.0, BR, 0.7)
        n = L.secs(0.55, BR)
        t = L.tvec(n, BR)
        gear = L.bp(L.white(n, rng), BR, 600, 3000) * (0.6 + 0.4 * np.sin(TAU * 120 * t)) * np.hanning(n)
        L.place(out, L.norm_peak(gear) * 0.45, 0.15, BR)
        L.place(out, tick(), 0.7, BR, 0.4)
    return room(out, BR, rng, 0.1, 0.04), {"kind": kind}


@family("field", "box", 5, ref=lambda: ref_field("box"))
def field_box(rng, i):
    """Lost-and-found box lid: lid laid back gently, flopping lid, stutter + heavy knock, latch, bouncing drop."""
    kind = ["gentle", "flop", "stutter", "latch", "drop"][i]
    out = np.zeros(L.secs(0.9, SR))
    lid = lambda f, g=1.0: L.mix(knock(SR, rng, f, "wood"), (thump(SR, rng, 120, 0.15, 0.03, grit=0.3), 0.5)) * g
    if kind == "gentle":
        L.place(out, creak(rng, SR, 0.3, 300, 230, rough=0.12, release=0.1, swell=0.04), 0.0, SR, 0.6)
        L.place(out, creak(rng, SR, 0.3, 230, 290, rough=0.12, release=0.1, swell=0.04), 0.28, SR, 0.55)
        L.place(out, fabric_puff(SR, rng, 0.1, 500, 0.2), 0.6, SR, 0.5)
    elif kind == "flop":
        L.place(out, lid(470), 0.0, SR)
        for k in range(3):
            L.place(out, lid(500 + 30 * k, 0.4 / (k + 1)), 0.08 + k * 0.06, SR)
    elif kind == "stutter":
        for k in range(3):
            L.place(out, creak(rng, SR, 0.1, 250 + 20 * k, 270 + 20 * k, rough=0.2, swell=0.02, release=0.04), k * 0.12, SR, 0.5)
        L.place(out, lid(390, 1.0), 0.4, SR)
    elif kind == "latch":
        L.place(out, knock(SR, rng, 2100, "metal", dur=0.08), 0.0, SR, 0.4)
        L.place(out, creak(rng, SR, 0.25, 300, 240, rough=0.15, release=0.08, swell=0.03), 0.06, SR, 0.5)
        L.place(out, lid(610), 0.32, SR)
    else:
        L.place(out, lid(520), 0.0, SR)
        for k in range(1, 4):
            L.place(out, lid(540, 0.45 ** k), sum(0.1 * 0.7 ** j for j in range(k)), SR)
    return room(out, SR, rng, 0.15, 0.05), {"kind": kind}


# --------------------------------------------------------------------------- treasure chests (treasure.gd)
CHEST_SPARKLES = ["rise", "fall", "chord", "dust", "trill"]


def chest_latch(rng, sr, kind):
    """The catch let go: a hasp unhooked and flipped down, a spring catch snapping, or a small bolt."""
    out = np.zeros(L.secs(0.14, sr))
    if kind == "hasp":
        L.place(out, knock(sr, rng, rng.uniform(2300, 2600), "metal", dur=0.06), 0.0, sr, 0.5)
        L.place(out, knock(sr, rng, rng.uniform(1500, 1750), "metal", dur=0.08), rng.uniform(0.035, 0.05), sr, 0.45)
    elif kind == "snap":
        L.place(out, knock(sr, rng, rng.uniform(2900, 3300), "metal", dur=0.05, bright=1.3), 0.0, sr, 0.6)
        L.place(out, knock(sr, rng, rng.uniform(700, 820), "wood", dur=0.05), 0.004, sr, 0.35)
    else:
        n = L.secs(0.05, sr)
        L.place(out, L.bp(L.white(n, rng), sr, 2200, 6000) * np.hanning(n) * 0.35, 0.0, sr)
        L.place(out, knock(sr, rng, rng.uniform(1900, 2200), "metal", dur=0.05), 0.05, sr, 0.5)
    return out


def chest_hinge(rng, sr, kind, f0):
    """The lid's hinges while it swings up (the game's swing takes about half a second)."""
    if kind == "long":
        return creak(rng, sr, rng.uniform(0.36, 0.44), f0, f0 * 1.35, rough=0.14, release=0.12, swell=0.05) * 0.6
    if kind == "two":      # stick, a breath, then the rest of the way
        out = np.zeros(L.secs(0.5, sr))
        L.place(out, creak(rng, sr, 0.16, f0 * 1.1, f0 * 0.95, rough=0.2, release=0.05, swell=0.02), 0.0, sr, 0.55)
        L.place(out, creak(rng, sr, 0.22, f0 * 0.95, f0 * 1.3, rough=0.16, release=0.08, swell=0.03), 0.21, sr, 0.6)
        return out
    if kind == "low":      # a heavy lid, groaning down the scale
        return creak(rng, sr, rng.uniform(0.3, 0.36), f0 * 0.75, f0 * 0.62, body=(150, 330, 640, 1150), rough=0.22,
                     release=0.1, swell=0.04) * 0.65
    out = np.zeros(L.secs(0.45, sr))   # "airy": a quick smooth swing, a short squeak and the lid's air
    L.place(out, creak(rng, sr, 0.12, f0 * 1.5, f0 * 1.8, rough=0.08, release=0.05, swell=0.02), 0.02, sr, 0.4)
    L.place(out, sweep_noise(rng, sr, 0.35, 300, 1400, q=1.0) * 0.35, 0.04, sr)
    return out


def chest_stop(rng, sr, kind, f):
    """The open lid meeting its stop: one wooden thunk, or a small bounce."""
    if kind == "thunk":
        return L.mix(knock(sr, rng, f, "wood"), (thump(sr, rng, 110, 0.18, 0.04, grit=0.3), 0.6)) * 0.55
    out = np.zeros(L.secs(0.25, sr))
    L.place(out, knock(sr, rng, f * 1.05, "wood"), 0.0, sr, 0.45)
    L.place(out, knock(sr, rng, f * 1.08, "wood"), rng.uniform(0.07, 0.09), sr, 0.2)
    return out


def chest_sparkle(rng, sr, kind, root_hz):
    """The gold inside catching the light: a short run of glassy notes over a little dust."""
    out = np.zeros(L.secs(1.1, sr))
    steps = {"rise": [0, 4, 7, 12], "fall": [12, 9, 4], "chord": [0, 4, 7], "dust": [], "trill": [7, 12, 7, 12, 7]}[kind]
    gap = {"rise": 0.075, "fall": 0.11, "chord": 0.012, "dust": 0.0, "trill": 0.055}[kind]
    for k, st in enumerate(steps):
        f = root_hz * 2 ** (st / 12.0)
        if kind in ("fall", "chord"):
            v = L.fm_bell(sr, f, 0.7, ratio=3.5, index=rng.uniform(1.2, 2.0), t60=0.6, rng=rng)
        else:
            v = L.modal(sr, f, "glass", dur=0.5, rng=rng)
        L.place(out, v, k * gap * rng.uniform(0.92, 1.08), sr, (0.75 * 0.82 ** k) if kind == "trill" else 0.8 ** k)
    swirl = kind == "dust"
    dust = L.scatter(sr, 0.6 if swirl else 0.35, rng, lambda r: L.modal(sr, r.uniform(4500, 9000), "glass", dur=0.06, rng=r),
                     count=10 if swirl else 4, gain=(0.12, 0.35), env=np.hanning(32) if swirl else None)
    L.place(out, dust, 0.03, sr, 1.0 if swirl else 0.6)
    return out


@family("field", "chest", 6, sr=BR, ref=lambda: ref_field("box"))
def field_chest(rng, i):
    """Treasure chest opening: latch x hinge creak x the lid's stop x the gold's sparkle (rise, fall, chord, dust, trill)."""
    latch, stop, sparkle, hinge = L.cycle(i, ["hasp", "snap", "bolt"], ["thunk", "bounce"], CHEST_SPARKLES, ["long", "two", "low", "airy"])
    f0 = [230, 260, 210, 280, 245, 220][i] * rng.uniform(0.97, 1.03)
    out = np.zeros(L.secs(1.7, BR))
    L.place(out, chest_latch(rng, BR, latch), 0.0, BR)
    swing = chest_hinge(rng, BR, hinge, f0)
    at = rng.uniform(0.04, 0.07)
    L.place(out, swing, at, BR)
    L.place(out, chest_stop(rng, BR, stop, [300, 340, 270, 360, 320, 290][i]), at + min(swing.size / BR, 0.48), BR)
    L.place(out, chest_sparkle(rng, BR, sparkle, [1046.5, 1174.7, 987.8, 1318.5, 1108.7, 1244.5][i]), 0.28 + 0.04 * (i % 2), BR, 0.5)
    return room(out, BR, rng, 0.15, 0.06), {"latch": latch, "hinge": hinge, "stop": stop, "sparkle": sparkle}


# knock gaps (s): even, rushing, slow pair, dragging, flam then a gap, a gap then a quick pair
RATTLE_GAPS = [(0.09, 0.07), (0.07, 0.06, 0.05), (0.13,), (0.05, 0.07, 0.09, 0.11), (0.035, 0.13), (0.11, 0.05, 0.05)]


@family("field", "chest_rattle", 6, ref=lambda: ref_field("box") - 4.0)
def field_chest_rattle(rng, i):
    """A chest's lid jiggled against its catch while it gives (treasure.gd): knock rhythm x lid pitch x hasp."""
    gaps = RATTLE_GAPS[i]
    f, hasp = L.cycle(i, [430, 380, 470, 400, 450, 360], ["jingle", "clack", "none"])
    out = np.zeros(L.secs(0.6, SR))
    at = 0.0
    for k in range(len(gaps) + 1):
        g = 1.0 if k == 0 else rng.uniform(0.55, 0.85)
        L.place(out, knock(SR, rng, f * rng.uniform(0.96, 1.05), "wood", dur=0.09), at, SR, g * 0.8)
        if hasp == "jingle" or (hasp == "clack" and k == len(gaps)):
            L.place(out, knock(SR, rng, rng.uniform(2200, 2800), "metal", dur=0.05), at + rng.uniform(0.008, 0.02), SR,
                    0.25 if hasp == "jingle" else 0.4)
        if k < len(gaps):
            at += gaps[k] * rng.uniform(0.92, 1.08)
    return room(out, SR, rng, 0.12, 0.05), {"knocks": len(gaps) + 1, "hasp": hasp}


def brass_slide(rng, sr, sections, step, direction=1):
    s = S(rng, sr)
    out = np.zeros(L.secs(1.0, sr))
    at = 0.0
    for k in range(sections):
        d = step * rng.uniform(0.85, 1.15)
        r = arr(V.rumble(s, d, 900 * (1 + 0.15 * k * direction), 3200, 6, 0.02))
        L.place(out, r * 0.5, at, sr)
        L.place(out, arr(V.modal([2600 + 300 * k * direction, 4100, 6200], [0.03, 0.02, 0.015], [1, .5, .3], 0.08, s.rng)), at + d, sr, 0.45)
        at += d + rng.uniform(0.02, 0.05)
    return out, at


@family("field", "brass", 5, sr=BR, ref=lambda: ref_field("brass"))
def field_brass(rng, i):
    """Telescope extending: 2, 3, 1, 4 sections sliding out (a click each), or one long pull and a cap pop."""
    sections, step, cap_kind = [(2, 0.16, "click"), (3, 0.1, "click"), (0, 0.0, "focus"), (4, 0.07, "none"), (1, 0.45, "pop")][i]
    if cap_kind == "focus":   # no slide: the focus ring is turned, a run of fine detents and a small squeak
        out, at = np.zeros(L.secs(0.8, BR)), 0.0
        for k in range(9):
            L.place(out, knock(BR, rng, rng.uniform(3800, 4600), "metal", dur=0.03), at, BR, 0.5)
            at += 0.045 * rng.uniform(0.85, 1.15)
        L.place(out, creak(rng, BR, 0.2, 1900, 2100, body=(2000, 3800), q=12, rough=0.05, metal=True, release=0.06, swell=0.02), 0.1, BR, 0.3)
    else:
        out, at = brass_slide(rng, BR, sections, step, 1)
    s = S(rng, BR)
    if cap_kind == "click":
        cap_click = L.mix(arr(V.modal([2600, 4100, 6200], [0.04, 0.03, 0.02], [1, .5, .3], 0.12, s.rng)), arr(V.click(s, 0.03, 2000, 8000, 0.002)), sr=BR)
        L.place(out, cap_click, at + 0.03, BR, 0.7)
    elif cap_kind == "pop":
        L.place(out, L.mix(fabric_puff(BR, rng, 0.06, 1500, 0.5), (knock(BR, rng, 1900, "metal", dur=0.1), 0.5)), at + 0.05, BR, 0.8)
    return room(out, BR, rng, 0.15, 0.05), {"sections": sections}


@family("field", "flap", 4, ref=lambda: ref_field("lid"))
def field_flap(rng, i):
    """Mailbox flap closing: tin clap, clap with rattle, slow creak then clap, dull thud on the seal."""
    kind = ["clap", "rattle", "soft", "seal"][i]
    f = [1100, 950, 1250, 820][i]
    out = np.zeros(L.secs(0.6, SR))
    at = 0.0
    if kind == "soft":
        L.place(out, creak(rng, SR, 0.18, 820, 700, body=(800, 1700, 3000), q=10, rough=0.08, release=0.06, swell=0.02, metal=True), 0.0, SR, 0.35)
        at = 0.16
    if kind == "seal":
        L.place(out, L.mix(thump(SR, rng, 160, 0.12, 0.02, grit=0.6), (L.lp(knock(SR, rng, f, "metal", dur=0.1), SR, 2500), 0.35)), 0.0, SR)
        L.place(out, knock(SR, rng, 2400, "metal", dur=0.05), 0.012, SR, 0.25)
    else:
        L.place(out, L.mix(knock(SR, rng, f, "metal", dur=0.3), (L.bp(L.white(L.secs(0.02, SR), rng), SR, 1500, 7000), 0.4)), at, SR)
    if kind == "rattle":
        for k in range(3):
            L.place(out, knock(SR, rng, f * rng.uniform(1.02, 1.1), "metal", dur=0.08), at + 0.04 + k * 0.035, SR, 0.35 / (k + 1))
    return room(out, SR, rng, 0.2, 0.05), {"kind": kind}


@family("field", "flag", 4, ref=lambda: ref_field("lid"))
def field_flag(rng, i):
    """Mailbox flag swinging up: little pivot squeak and a clack against its stop."""
    hinge = [(1100, 1350), (1300, 1150), (1000, 1250), (1400, 1600)][i]
    out = np.zeros(L.secs(0.5, SR))
    lh = rng.uniform(0.1, 0.18)
    L.place(out, creak(rng, SR, lh, *hinge, body=(1200, 2600, 4200), q=12, rough=0.06, release=0.04, swell=0.02, metal=True), 0.0, SR, 0.5)
    L.place(out, knock(SR, rng, rng.uniform(1700, 2300), "metal", dur=0.12), lh, SR, 0.5)
    if i % 2:
        L.place(out, knock(SR, rng, rng.uniform(1700, 2300), "metal", dur=0.08), lh + 0.05, SR, 0.2)
    return room(out, SR, rng, 0.15, 0.04)


PECK_RHYTHMS = [[0, 0.07], [0, 0.06, 0.12], [0, 0.05, 0.09, 0.16], [0, 0.1, 0.16, 0.2, 0.31], [0, 0.04], [0, 0.09, 0.27],
                [0, 0.05, 0.1, 0.15, 0.2, 0.25], [0, 0.12, 0.18]]


@family("field", "peck", 8, ref=lambda: ref_field("box"))
def field_peck(rng, i):
    """Beaks on the feeder tray: tap rhythm x tray pitch (+ seeds skittering)."""
    rhythm = PECK_RHYTHMS[i]
    f, seeds = L.cycle(i, [2200, 2900, 1800, 3400, 2500], [False, True, False])
    out = np.zeros(L.secs(0.6, SR))
    for k, at in enumerate(rhythm):
        L.place(out, knock(SR, rng, f * rng.uniform(0.94, 1.06), "wood", dur=0.04, bright=1.4), at * rng.uniform(0.92, 1.08), SR, rng.uniform(0.55, 1.0))
    if seeds:
        sk = L.scatter(SR, 0.2, rng, lambda r: L.bp(r.standard_normal(L.secs(0.004, SR)), SR, 3000, 9000), count=6, gain=(0.1, 0.35))
        L.place(out, sk, rhythm[-1] * 0.5, SR)
    return out, {"taps": len(rhythm)}


@family("field", "tweet", 8, ref=lambda: ref_field("birds"))
def field_tweet(rng, i):
    """One small bird at the feeder: eight different calls."""
    kind = ["up", "tsee", "trill", "chips", "down", "peep", "zwee", "dee"][i]
    f0 = [3300, 3000, 3800, 3500, 2900, 4200, 2600, 3400][i] * rng.uniform(0.98, 1.02)
    return room(bird_call(rng, SR, kind, f0), SR, rng, 0.3, 0.07), {"kind": kind}


@family("field", "bucket", 5, ref=lambda: ref_field("coin"))
def field_bucket(rng, i):
    """Well bucket swinging: rope creak, wooden bucket knocking the stone rim, water sloshing inside."""
    kind = ["swing", "knock2", "slosh", "creak_long", "clank"][i]
    out = np.zeros(L.secs(1.3, SR))
    rope = (220, 520, 1050)
    if kind in ("swing", "creak_long", "clank"):
        d = 0.8 if kind == "creak_long" else 0.45
        L.place(out, creak(rng, SR, d, 180, 230 if kind != "clank" else 200, body=rope, q=5, rough=0.3, swell=0.1), 0.0, SR, 0.7)
    if kind in ("swing", "knock2", "clank"):
        hits = 2 if kind == "knock2" else 1
        first = 0.0 if kind == "knock2" else 0.35
        for k in range(hits):
            L.place(out, L.mix(knock(SR, rng, rng.uniform(280, 360), "wood"), (knock(SR, rng, 900, "stone"), 0.4)), first + k * 0.22, SR, 0.8 - 0.25 * k)
    if kind == "clank":
        L.place(out, knock(SR, rng, 1450, "metal", dur=0.4), 0.38, SR, 0.3)   # iron hoop
    if kind in ("slosh", "knock2", "creak_long"):
        d = 0.7
        n = L.secs(d, SR)
        L.place(out, L.norm_peak(L.lp(L.brown(n, rng), SR, 1000) * shape_env("double", n, rng, d)), 0.05 if kind != "creak_long" else 0.15, SR, 0.5)
        for _ in range(3):
            L.place(out, bloop(SR, rng, rng.uniform(500, 900), 0.05), 0.2 + rng.uniform(0, 0.5), SR, 0.25)
    return room(out, SR, rng, 0.45, 0.12), {"kind": kind}


@family("field", "telescope", 4, sr=BR, ref=lambda: ref_field("brass"))
def field_telescope(rng, i):
    """Telescope pushed shut: sections sliding in (falling pitch) and the cap snapping on."""
    sections, step = [(2, 0.12), (3, 0.08), (1, 0.25), (2, 0.18)][i]
    s = S(rng, BR)
    out = np.zeros(L.secs(0.9, BR))
    L.place(out, arr(V.click(s, 0.03, 2000, 8000, 0.002)) * 0.6, 0.0, BR)
    body, at = brass_slide(rng, BR, sections, step, -1)
    L.place(out, body, 0.04, BR)
    L.place(out, fabric_puff(BR, rng, 0.06, 1200, 0.3), at + 0.06, BR, 0.4)
    return room(out, BR, rng, 0.15, 0.05)


@family("field", "arrive", 4, ref=lambda: ref_field("whoosh"))
def field_arrive(rng, i):
    """Signpost travel arrival: a swoosh settling in, two feet landing on the path, a soft chime."""
    sweep, steps, note = [((2600, 600), 2, 1568.0), ((1800, 400), 1, 1318.5), ((3000, 900), 3, 2093.0), ((1200, 500), 2, 1760.0)][i]
    d = rng.uniform(0.5, 0.65)
    n = L.secs(d, SR)
    sw = sweep_noise(rng, SR, d, *sweep, q=1.1, env=shape_env("late", n, rng, d))
    out = np.zeros(L.secs(1.4, SR))
    L.place(out, L.norm_peak(sw), 0.0, SR, 0.8)
    for k in range(steps):
        st = L.mix(thump(SR, rng, rng.uniform(90, 120), 0.12, 0.025, grit=0.5), (grains(rng, SR, 0.06, 600, np.exp(-np.linspace(0, 4, 32)), 500, 3500, (0.001, 0.004)), 0.6))
        L.place(out, st, d * 0.95 + k * rng.uniform(0.12, 0.2), SR, 0.5)
    s = S(rng, SR)
    L.place(out, arr(V.tube(s, note, 1.0, 0.6)), d * 0.9, SR, 0.2)
    return room(out, SR, rng, 0.3, 0.08)


@family("field", "stand", 5, ref=lambda: ref_field("paper"))
def field_stand(rng, i):
    """Getting up from a seat: the seat creaks as the weight lifts, cloth slides, a foot lands."""
    kind = ["creak_up", "cloth", "step", "two", "rope"][i]
    out = np.zeros(L.secs(0.8, SR))
    if kind in ("creak_up", "two", "step"):
        f = rng.uniform(190, 260)
        L.place(out, creak(rng, SR, 0.3, f, f * 1.35, rough=0.2, swell=0.03, release=0.12), 0.0, SR, 0.8)
    if kind == "rope":
        L.place(out, creak(rng, SR, 0.4, 210, 160, body=(250, 550, 1100), q=5, rough=0.3), 0.0, SR, 0.8)
    if kind in ("cloth", "two", "rope"):
        L.place(out, rustle(rng, SR, 0.35, "front", 800, 4000, density=150, bed=0.5), 0.05, SR, 0.5)
    if kind in ("step", "cloth"):
        L.place(out, thump(SR, rng, 105, 0.12, 0.025, grit=0.5), 0.28, SR, 0.5)
    if kind == "two":
        L.place(out, creak(rng, SR, 0.2, 260, 240, rough=0.2, release=0.08), 0.35, SR, 0.45)
    return room(out, SR, rng, 0.15, 0.04), {"kind": kind}


@family("field", "seeds", 5, ref=lambda: ref_field("paper"))
def field_seeds(rng, i):
    """Seed pouring into the feeder tray: patter of tiny ticks on wood (pour, scoops, shake)."""
    kind = ["pour", "scoops", "sprinkle", "long", "shake"][i]
    out = np.zeros(L.secs(1.0, SR))
    seed = lambda r: L.mix(knock(SR, r, r.uniform(3000, 6000), "wood", dur=0.012, bright=1.5), (L.bp(r.standard_normal(L.secs(0.004, SR)), SR, 3000, 9000), 0.5))
    if kind in ("pour", "long"):
        d = 0.45 if kind == "pour" else 0.75
        n = L.secs(d, SR)
        L.place(out, L.scatter(SR, d, rng, seed, density=160, env=shape_env("front" if kind == "pour" else "swell", n, rng, d), gain=(0.1, 0.8)), 0.0, SR)
    elif kind == "scoops":
        for k in range(2):
            L.place(out, L.scatter(SR, 0.18, rng, seed, density=200, env=np.linspace(1, 0.1, 32), gain=(0.1, 0.8)), k * 0.3, SR)
    elif kind == "sprinkle":
        L.place(out, L.scatter(SR, 0.6, rng, seed, density=40, gain=(0.2, 1.0)), 0.0, SR)
    else:
        for k in range(4):
            L.place(out, L.scatter(SR, 0.08, rng, seed, density=250, gain=(0.1, 0.7)), k * 0.11, SR, 1 - 0.15 * k)
    L.place(out, knock(SR, rng, rng.uniform(700, 900), "wood", dur=0.08), 0.0, SR, 0.15)
    return out, {"kind": kind}


@family("field", "settle", 5, ref=lambda: ref_field("wood_creak"))
def field_settle(rng, i):
    """Sitting down on a swing / rocker / hammock: weight landing, the seat answering, cloth."""
    kind = ["wood", "rope", "chain", "plop", "rock"][i]
    out = np.zeros(L.secs(0.9, SR))
    L.place(out, fabric_puff(SR, rng, 0.2, 380, 0.3), 0.0, SR, 0.7)
    if kind == "wood":
        L.place(out, creak(rng, SR, 0.4, 210, 175, rough=0.2, swell=0.04), 0.04, SR, 0.8)
    elif kind == "rope":
        L.place(out, creak(rng, SR, 0.5, 170, 210, body=(200, 470, 950), q=5, rough=0.32, swell=0.06), 0.03, SR, 0.8)
    elif kind == "chain":
        L.place(out, creak(rng, SR, 0.35, 560, 500, body=(600, 1300, 2500), q=9, rough=0.06, metal=True), 0.04, SR, 0.5)
        L.place(out, L.scatter(SR, 0.2, rng, lambda r: knock(SR, r, r.uniform(2500, 4000), "metal", dur=0.05), count=4, gain=(0.1, 0.3)), 0.02, SR)
    elif kind == "plop":
        L.place(out, thump(SR, rng, 85, 0.25, 0.05, grit=0.3), 0.0, SR, 0.8)
        L.place(out, knock(SR, rng, 300, "wood"), 0.01, SR, 0.3)
    else:
        L.place(out, creak(rng, SR, 0.3, 190, 220, rough=0.2), 0.03, SR, 0.7)
        L.place(out, knock(SR, rng, 280, "wood"), 0.35, SR, 0.4)
        L.place(out, creak(rng, SR, 0.25, 215, 190, rough=0.2), 0.42, SR, 0.4)
    return room(out, SR, rng, 0.15, 0.04), {"kind": kind}


# =========================================================================== interior (Interiors.sfx kinds)
@family("interior", "cushion", 6, ref=lambda: ref_interior("cushion"))
def in_cushion(rng, i):
    """Sofa / bed / sacks: leather sofa squeak, deep bed, bouncing springs, two pats, grain sack, slow sink."""
    kind = ["sofa", "bed", "springs", "pat", "sack", "sink"][i]
    out = np.zeros(L.secs(0.7, SR))
    if kind == "sofa":
        L.place(out, fabric_puff(SR, rng, 0.3, 330, 0.15), 0.0, SR)
        L.place(out, creak(rng, SR, 0.16, 420, 520, body=(500, 1100, 2200), q=6, rough=0.15, release=0.06, swell=0.03), 0.05, SR, 0.5)
    elif kind == "bed":   # big soft landing, then the duvet settles
        L.place(out, fabric_puff(SR, rng, 0.42, 220, 0.1), 0.0, SR)
        L.place(out, rustle(rng, SR, 0.45, "decay", 900, 4500, density=160, bed=0.6), 0.12, SR, 0.45)
    elif kind == "springs":
        L.place(out, fabric_puff(SR, rng, 0.12, 600, 0.25), 0.0, SR, 0.6)
        for k in range(3):
            L.place(out, creak(rng, SR, 0.12, 900 + 150 * k, 1000 + 150 * k, body=(1000, 2100, 3600), q=12, rough=0.04, metal=True, release=0.05, swell=0.02),
                    0.03 + k * 0.11, SR, 0.7 - 0.15 * k)
    elif kind == "pat":
        for k in range(2):
            L.place(out, fabric_puff(SR, rng, 0.1, 650, 0.6), k * rng.uniform(0.12, 0.16), SR, 1 - 0.3 * k)
    elif kind == "sack":
        L.place(out, fabric_puff(SR, rng, 0.14, 700, 0.2), 0.0, SR, 0.6)
        L.place(out, grains(rng, SR, 0.35, 500, np.linspace(1, 0.1, 32), 2000, 7000, (0.001, 0.003)), 0.01, SR, 1.0)
    else:
        L.place(out, fabric_puff(SR, rng, 0.15, 480, 0.4), 0.0, SR)
        L.place(out, fabric_puff(SR, rng, 0.3, 300, 0.2), 0.18, SR, 0.75)
    return out, {"kind": kind}


@family("interior", "creak", 6, ref=lambda: ref_interior("creak"))
def in_creak(rng, i):
    """Cupboard doors, lids, wheels and hoists: wood hinge up, squeaky metal hinge, stutter, drawer, heavy lid, pulley."""
    kind = ["hinge_up", "metal_hinge", "stutter", "drawer", "heavy", "pulley"][i]
    out = np.zeros(L.secs(0.9, SR))
    if kind == "hinge_up":
        L.place(out, creak(rng, SR, 0.5, 190, 300, rough=0.15), 0.0, SR)
    elif kind == "metal_hinge":
        L.place(out, creak(rng, SR, 0.45, 760, 620, body=(800, 1700, 3000), q=10, rough=0.06, metal=True), 0.0, SR, 0.8)
        L.place(out, knock(SR, rng, 520, "wood"), 0.47, SR, 0.4)
    elif kind == "stutter":
        for k in range(3):
            L.place(out, creak(rng, SR, 0.14, 210 + 30 * k, 240 + 30 * k, rough=0.2, swell=0.02, release=0.05), k * 0.17, SR, 1 - 0.15 * k)
    elif kind == "drawer":
        d = 0.35
        n = L.secs(d, SR)
        L.place(out, L.bp(L.pink(n, rng), SR, 300, 2500) * shape_env("front", n, rng, d) * (0.7 + 0.3 * np.sin(TAU * 40 * L.tvec(n, SR))), 0.0, SR)
        L.place(out, knock(SR, rng, 420, "wood"), d, SR, 0.6)
    elif kind == "heavy":
        L.place(out, creak(rng, SR, 0.6, 120, 165, body=(140, 330, 610, 1100), rough=0.25), 0.0, SR)
        L.place(out, thump(SR, rng, 90, 0.2, 0.04, grit=0.4), 0.6, SR, 0.5)
    else:
        for k in range(3):
            L.place(out, creak(rng, SR, 0.16, 700, 820, body=(800, 1700, 3000), q=10, rough=0.06, metal=True, release=0.05, swell=0.02), k * 0.22, SR, 0.5)
        L.place(out, creak(rng, SR, 0.6, 200, 240, body=(220, 520, 1050), q=5, rough=0.3), 0.0, SR, 0.5)
    return room(out, SR, rng, 0.2, 0.08), {"kind": kind}


@family("interior", "splash", 6, ref=lambda: ref_interior("splash"))
def in_splash(rng, i):
    """Washing and watering indoors: hands in the basin, can pouring, scoops, trickle, tub slosh."""
    kind = ["hands", "pour", "scoops", "trickle", "slosh", "drips"][i]
    out = np.zeros(L.secs(0.9, SR))
    if kind == "hands":
        for k in range(3):
            d = rng.uniform(0.1, 0.16)
            n = L.secs(d, SR)
            L.place(out, L.norm_peak(L.bp(L.white(n, rng), SR, 500, 4000) * np.exp(-L.tvec(n, SR) / 0.03)), k * rng.uniform(0.13, 0.18), SR, 0.8)
            for _ in range(3):
                L.place(out, bloop(SR, rng, rng.uniform(400, 1000), 0.04), k * 0.15 + rng.uniform(0, 0.08), SR, 0.3)
    elif kind == "pour":
        d = 0.7
        n = L.secs(d, SR)
        e = np.minimum(1, L.tvec(n, SR) / 0.08) * np.clip((d - L.tvec(n, SR)) / 0.2, 0, 1)
        L.place(out, L.norm_peak(L.bp(L.white(n, rng), SR, 700, 4500) * e), 0.0, SR, 0.6)
        L.place(out, L.scatter(SR, d, rng, lambda r: bloop(SR, r, r.uniform(300, 900), r.uniform(0.02, 0.05)), density=25, gain=(0.1, 0.4)), 0.0, SR)
    elif kind == "scoops":
        for k in range(2):
            d = 0.22
            n = L.secs(d, SR)
            L.place(out, L.norm_peak(L.lp(L.brown(n, rng), SR, 1500) * shape_env("swell", n, rng, d)), k * 0.32, SR)
            L.place(out, bloop(SR, rng, rng.uniform(250, 450), 0.08, rise=1.6), k * 0.32 + 0.12, SR, 0.5)
    elif kind == "trickle":
        L.place(out, L.scatter(SR, 0.6, rng, lambda r: bloop(SR, r, r.uniform(800, 1600), 0.03, rise=2.2), density=40, gain=(0.2, 0.8)), 0.0, SR)
    elif kind == "slosh":
        d = 0.75
        n = L.secs(d, SR)
        L.place(out, L.norm_peak(L.lp(L.brown(n, rng), SR, 900) * shape_env("double", n, rng, d)), 0.0, SR)
    else:
        d = 0.18
        n = L.secs(d, SR)
        L.place(out, L.norm_peak(L.bp(L.white(n, rng), SR, 400, 3500) * np.exp(-L.tvec(n, SR) / 0.04)), 0.0, SR)
        for k in range(4):
            L.place(out, bloop(SR, rng, rng.uniform(900, 1500), 0.04, rise=2.5), 0.25 + k * rng.uniform(0.1, 0.16), SR, 0.4)
    return room(out, SR, rng, 0.25, 0.1), {"kind": kind}


@family("interior", "page", 6, ref=lambda: ref_interior("page"))
def in_page(rng, i):
    kind = ["flick", "slow", "two", "riffle", "open", "slide"][i]
    out = np.zeros(L.secs(0.8, SR))
    if kind == "flick":
        d = 0.16
        n = L.secs(d, SR)
        L.place(out, sweep_noise(rng, SR, d, 2000, 6000, q=0.8, env=shape_env("late", n, rng, d)), 0.0, SR)
    elif kind == "slow":
        d = 0.45
        n = L.secs(d, SR)
        L.place(out, sweep_noise(rng, SR, d, 900, 4500, q=0.7, env=shape_env("swell", n, rng, d)), 0.0, SR)
        L.place(out, fabric_puff(SR, rng, 0.07, 1000, 0.8), d * 0.9, SR, 0.4)
    elif kind == "two":
        for k in range(2):
            d = 0.18
            n = L.secs(d, SR)
            L.place(out, sweep_noise(rng, SR, d, 1500, 5000, q=0.8, env=shape_env("late", n, rng, d)), k * 0.24, SR, 1 - 0.2 * k)
    elif kind == "riffle":
        for k in range(7):
            L.place(out, knock(SR, rng, rng.uniform(2500, 4000), "wood", dur=0.02) * 0.5 + L.bp(L.white(L.secs(0.02, SR), rng), SR, 2000, 8000) * np.exp(-L.tvec(L.secs(0.02, SR), SR) / 0.004), k * 0.045, SR, 0.6)
    elif kind == "open":
        L.place(out, thump(SR, rng, 140, 0.12, 0.025, grit=0.6), 0.0, SR, 0.6)
        d = 0.25
        n = L.secs(d, SR)
        L.place(out, sweep_noise(rng, SR, d, 1200, 4000, q=0.8, env=shape_env("front", n, rng, d)), 0.08, SR)
    else:
        d = 0.35
        n = L.secs(d, SR)
        L.place(out, L.bp(L.pink(n, rng), SR, 1000, 5000) * shape_env("front", n, rng, d), 0.0, SR)
    return room(out, SR, rng, 0.15, 0.05), {"kind": kind}


@family("interior", "click", 6, ref=lambda: ref_interior("click"))
def in_click(rng, i):
    """Lamp switches: toggle, pull chain, rocker, push button, rotary detents, soft click."""
    kind = ["toggle", "chain", "rocker", "push", "rotary", "soft"][i]
    out = np.zeros(L.secs(0.4, SR))
    ck = lambda f, d=0.03: L.mix(knock(SR, rng, f, "ceramic", dur=d), (L.bp(L.white(L.secs(0.01, SR), rng), SR, 2000, 9000), 0.6))
    if kind == "toggle":
        L.place(out, ck(1400), 0.0, SR)
        L.place(out, ck(1800, 0.02), 0.025, SR, 0.5)
    elif kind == "chain":
        L.place(out, L.scatter(SR, 0.1, rng, lambda r: knock(SR, r, r.uniform(3000, 5000), "metal", dur=0.03), count=4, gain=(0.1, 0.3)), 0.0, SR)
        L.place(out, ck(1200), 0.1, SR)
    elif kind == "rocker":
        L.place(out, L.mix(ck(900, 0.05), (thump(SR, rng, 300, 0.04, 0.008, grit=0.2), 0.4)), 0.0, SR)
    elif kind == "push":
        L.place(out, ck(2000, 0.02), 0.0, SR, 0.8)
        L.place(out, ck(1500, 0.03), rng.uniform(0.07, 0.1), SR)
    elif kind == "rotary":
        for k in range(3):
            L.place(out, ck(1700 + 100 * k, 0.015), k * 0.05, SR, 0.6 + 0.2 * k)
    else:
        L.place(out, L.lp(ck(1100, 0.04), SR, 3000), 0.0, SR)
    return out, {"kind": kind}


@family("interior", "pop", 6, ref=lambda: ref_interior("pop"))
def in_pop(rng, i):
    kind, p = L.cycle(i, ["up", "down", "double", "cork", "bloop", "pluck"], [1.0, 1.25, 0.8])
    d = 0.16
    if kind == "up":
        x = tone(SR, d, lambda u: (480 + 420 * u) * p, ((1, 1.0), (2, 0.1)), env=lambda u: np.exp(-u * 6) * np.minimum(1, u * 80))
    elif kind == "down":
        x = tone(SR, d, lambda u: (900 - 400 * u) * p, ((1, 1.0),), env=lambda u: np.exp(-u * 6) * np.minimum(1, u * 80))
    elif kind == "double":
        a = tone(SR, 0.08, lambda u: (520 + 300 * u) * p, ((1, 1.0),), env=lambda u: np.exp(-u * 4))
        x = L.mix(a, (L.repitch(a, 1.25), 0.7, 0.07))
    elif kind == "cork":
        n = L.secs(0.1, SR)
        burst = L.bp(L.white(n, rng), SR, 500 * p, 3500 * p) * np.exp(-L.tvec(n, SR) / 0.005)
        x = L.mix(burst * 1.5, L.resonate(burst, SR, [600 * p, 1300 * p], [0.02, 0.015]))
    elif kind == "bloop":
        x = bloop(SR, rng, 380 * p, 0.12, rise=2.4, tau=0.4)
    else:
        x = L.ks_pluck(SR, 700 * p, 0.18, rng=rng, damping=0.985, bright=0.4)
    return x, {"kind": kind}


KNOCK_RECIPES = [("crate", [0, 0.18]), ("barrel", [0, 0.13, 0.26]), ("bench", [0, 0.24]), ("crate", [0, 0.1, 0.2, 0.3]),
                 ("barrel", [0]), ("bench", [0, 0.2, 0.32])]


@family("interior", "knock", 6, ref=lambda: ref_interior("knock"))
def in_knock(rng, i):
    """Crates, barrels and the workbench: six knock patterns (two, three, four, one heavy, accelerating)."""
    mat, times = KNOCK_RECIPES[i]
    out = np.zeros(L.secs(0.9, SR))

    def hit(r):
        if mat == "crate":
            return L.mix(knock(SR, r, r.uniform(280, 340), "wood"), (thump(SR, r, 150, 0.1, 0.02, grit=0.5), 0.5))
        if mat == "barrel":
            b = L.mix(thump(SR, r, 140, 0.25, 0.06, grit=0.3), (knock(SR, r, 420, "wood"), 0.4))
            return L.resonate(b, SR, [140, 290, 470], [0.12, 0.08, 0.05]) * 0.6 + b * 0.5
        return L.mix(knock(SR, r, r.uniform(190, 230), "wood", bright=0.7), (thump(SR, r, 110, 0.15, 0.03, grit=0.6), 0.7))
    for k, at in enumerate(times):
        L.place(out, hit(rng), at * rng.uniform(0.95, 1.05), SR, 1.0 if k == 0 else rng.uniform(0.6, 0.85))
    if len(times) == 1:   # one heavy thump makes the hoops rattle
        L.place(out, L.scatter(SR, 0.2, rng, lambda r: knock(SR, r, r.uniform(1400, 2000), "metal", dur=0.08), count=3, gain=(0.1, 0.25)), 0.03, SR)
    return room(out, SR, rng, 0.2, 0.08), {"mat": mat, "count": len(times)}


@family("interior", "ding", 6, sr=BR, ref=lambda: ref_interior("ding"))
def in_ding(rng, i):
    """Counter bell: single, double, soft, rattle, three quick, palm-muted."""
    kind = ["single", "double", "soft", "rattle", "triple", "muted"][i]
    f = [1318.5, 1174.7, 1568.0, 2093.0, 1760.0, 1046.5][i] * rng.uniform(0.998, 1.002)
    s = S(rng, BR)
    bellf = lambda g, dec=0.9: arr(V.bell(s, f, 1.3, decay=dec, bright=g))
    out = np.zeros(L.secs(1.6, BR))
    if kind == "single":
        L.place(out, bellf(1.0), 0.0, BR)
    elif kind == "double":
        L.place(out, bellf(1.0), 0.0, BR)
        L.place(out, bellf(0.9), rng.uniform(0.11, 0.16), BR, 0.65)
    elif kind == "soft":
        L.place(out, bellf(0.4, 0.7), 0.0, BR)
    elif kind == "rattle":   # loose clapper: a flam, then the clapper buzzing on the dome
        L.place(out, bellf(1.1), 0.0, BR)
        L.place(out, bellf(0.8), 0.028, BR, 0.6)
        L.place(out, L.scatter(BR, 0.25, rng, lambda r: knock(BR, r, r.uniform(3000, 4500), "metal", dur=0.05), count=7, gain=(0.15, 0.45)), 0.05, BR)
    elif kind == "triple":
        for k in range(3):
            L.place(out, bellf(1.0, 0.6), k * 0.09, BR, 0.85 ** k)
    else:
        b = bellf(1.0)
        t = L.tvec(b.size, BR)
        L.place(out, b * np.where(t < 0.3, 1.0, np.exp(-(t - 0.3) / 0.05)), 0.0, BR)
        L.place(out, fabric_puff(BR, rng, 0.06, 900, 0.5), 0.3, BR, 0.2)
    return cap(room(out, BR, rng, 0.25, 0.08), BR, 1.5), {"kind": kind}


@family("interior", "chime", 6, sr=BR, ref=lambda: ref_interior("chime"))
def in_chime(rng, i):
    """Two- and three-note chimes: up a fifth, down a third, arpeggio, repeated note, octave, sigh."""
    seq, gap = [([72, 79], 0.18), ([79, 76], 0.2), ([72, 76, 79], 0.12), ([84, 84], 0.15), ([72, 84], 0.22), ([81, 77, 74], 0.14)][i]
    out = np.zeros(L.secs(1.6, BR))
    for k, m in enumerate(seq):
        f = notes_hz([m])[0]
        v = L.fm_bell(BR, f, 1.1, ratio=2.0 if i % 2 else 3.5, index=rng.uniform(1.2, 2.2), t60=1.0, rng=rng)
        L.place(out, v, k * gap * rng.uniform(0.95, 1.05), BR, 0.9 ** k)
    return cap(room(out, BR, rng, 0.25, 0.08), BR, 1.5), {"seq": seq}


@family("interior", "clink", 6, sr=BR, ref=lambda: ref_interior("clink"))
def in_clink(rng, i):
    """Tea: cup on saucer (count, porcelain pitch) or a spoon stirring."""
    kind, f = L.cycle(i, ["one", "two", "stir", "set", "three", "lift"], [2600, 3100, 2250, 2850, 3400])
    out = np.zeros(L.secs(0.7, BR))
    cup = lambda g, ff: knock(BR, rng, ff * rng.uniform(0.98, 1.02), "ceramic", dur=0.3) * g
    if kind == "one":
        L.place(out, cup(1.0, f), 0.0, BR)
    elif kind == "two":
        L.place(out, cup(1.0, f), 0.0, BR)
        L.place(out, cup(0.6, f * 1.08), rng.uniform(0.12, 0.17), BR)
    elif kind == "stir":
        for k in range(5):
            L.place(out, knock(BR, rng, f * 1.6 * rng.uniform(0.97, 1.03), "glass", dur=0.06) * 0.5, k * rng.uniform(0.07, 0.09), BR)
    elif kind == "set":
        L.place(out, thump(BR, rng, 260, 0.06, 0.012, grit=0.3) * 0.5, 0.0, BR)
        L.place(out, cup(0.8, f), 0.005, BR)
    elif kind == "three":
        for k in range(3):
            L.place(out, cup(1.0 - 0.25 * k, f * (1 + 0.04 * k)), k * 0.07, BR)
    else:
        L.place(out, cup(0.5, f * 1.1), 0.0, BR)
        L.place(out, cup(0.9, f), 0.2, BR)
    return room(out, BR, rng, 0.2, 0.06), {"kind": kind}


@family("interior", "sizzle", 6, ref=lambda: ref_interior("sizzle"))
def in_sizzle(rng, i):
    """Pan on the stove: hiss envelope x pop density (x lid clank)."""
    shape, density, extra = L.cycle(i, ["front", "swell", "decay"], [30, 80, 15], ["none", "lid", "none", "spit"])
    d = rng.uniform(0.75, 0.95)
    n = L.secs(d, SR)
    e = shape_env(shape, n, rng, d)
    hiss = L.hp(L.white(n, rng), SR, 2500) * e * (0.8 + 0.2 * L.lp(rng.standard_normal(n), SR, 20) / 0.1)
    pops = L.scatter(SR, d, rng, lambda r: L.bp(r.standard_normal(L.secs(0.01, SR)), SR, 2000, 8000) * np.hanning(L.secs(0.01, SR)), density=density, env=e, gain=(0.1, 0.8))
    x = L.mix(L.norm_peak(hiss) * 0.6, L.norm_peak(pops))
    if extra == "lid":
        x = L.mix(x, (knock(SR, rng, 880, "metal", dur=0.3), 0.4, 0.0))
    elif extra == "spit":
        x = L.mix(x, (L.scatter(SR, 0.15, rng, lambda r: L.bp(r.standard_normal(L.secs(0.02, SR)), SR, 1500, 5000), count=4), 0.6, d * 0.5))
    return x, {"shape": shape, "extra": extra}


@family("interior", "crackle", 6, ref=lambda: ref_interior("crackle"))
def in_crackle(rng, i):
    return fx_crackle(rng, i + 3)


@family("interior", "tick", 6, ref=lambda: ref_interior("tick"))
def in_tick(rng, i):
    """Clock: winding ratchet (count, speed up / down) or tick-tock."""
    kind = ["wind_even", "wind_fast", "tick_tock", "wind_slow", "key", "tick3"][i]
    out = np.zeros(L.secs(1.1, SR))
    tk = lambda f: L.mix(knock(SR, rng, f * rng.uniform(0.97, 1.03), "metal", dur=0.03), (L.bp(L.white(L.secs(0.006, SR), rng), SR, 3000, 9000), 0.4))
    if kind.startswith("wind"):
        count, step = {"wind_even": (8, 0.07), "wind_fast": (12, 0.045), "wind_slow": (6, 0.11)}[kind]
        at = 0.0
        for k in range(count):
            L.place(out, tk(2600 if kind != "wind_slow" else 2100), at, SR, 0.6 + 0.4 * (k % 2))
            at += step * (1 - 0.3 * k / count if kind == "wind_fast" else 1.0) * rng.uniform(0.92, 1.08)
    elif kind == "tick_tock":
        for k in range(4):
            L.place(out, tk(2200 if k % 2 == 0 else 1700), k * 0.27, SR, 0.8)
    elif kind == "key":
        L.place(out, knock(SR, rng, 1300, "metal", dur=0.08), 0.0, SR, 0.5)
        for k in range(5):
            L.place(out, tk(3000), 0.12 + k * 0.09, SR, 0.6)
    else:
        for k in range(3):
            L.place(out, tk(1900), k * 0.33, SR, 0.8)
            L.place(out, tk(2400), k * 0.33 + 0.02, SR, 0.25)
    return room(out, SR, rng, 0.25, 0.08), {"kind": kind}


@family("interior", "whoosh", 6, ref=lambda: ref_interior("whoosh"))
def in_whoosh(rng, i):
    """Window breeze: single swell, double, flutter, late, three gusts, fading gust (whistle in some)."""
    x, shape = whoosh_take(rng, SR, i, [0.9, 0.75, 1.0, 0.8, 0.95, 0.7], [(300, 900), (1200, 400), (500, 1300), (900, 600), (250, 700), (700, 1500)],
                           shapes=("single", "double", "flutter", "late", "triple", "decay"), whistle=1.9 if i % 3 == 2 else None)
    return L.lp(x, SR, 3000), {"shape": shape}


@family("interior", "rumble", 6, ref=lambda: ref_interior("rumble"))
def in_rumble(rng, i):
    """Millstone grinding: low rumble with grit, rotation pulse rate x length x grain size."""
    rate, d, grit = L.cycle(i, [1.6, 2.4, 3.2], [1.1, 0.9, 1.3, 1.0, 0.85], [(1500, 5000), (800, 3000)])
    n = L.secs(d, SR)
    t = L.tvec(n, SR)
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 0.6
    pulse = 0.6 + 0.4 * np.sin(TAU * rate * t + rng.uniform(0, 6)) ** 2
    rum = L.lp(L.brown(n, rng), SR, 180) * env * pulse
    g = grains(rng, SR, d, 120, env * pulse, *grit, (0.001, 0.006))
    hum = np.sin(TAU * rng.uniform(48, 62) * t) * env * 0.3
    return L.norm_peak(rum) + 0.5 * L.norm_peak(g) + hum, {"rate": rate}


STEP_RHYTHMS = [[0, 0.25, 0.5, 0.75], [0, 0.2, 0.4, 0.6], [0, 0.3, 0.6, 0.9], [0, 0.22, 0.48, 0.7], [0, 0.18, 0.42, 0.6, 0.8],
                [0, 0.27, 0.52, 0.8], [0, 0.24, 0.46, 0.7], [0, 0.32, 0.58, 0.88]]


@family("interior", "steps", 8, ref=lambda: ref_interior("steps"))
def in_steps(rng, i):
    """Wooden stairs: four or five treads, each its own board (pitch walk up / down, a creaky one)."""
    rhythm = STEP_RHYTHMS[i]
    direction, creaky = L.cycle(i, [1, -1], [1, 2, None, 0, 3])
    out = np.zeros(L.secs(1.3, SR))
    base = rng.uniform(85, 115)
    for k, at in enumerate(rhythm):
        f = base * (1 + 0.06 * k * direction) * rng.uniform(0.95, 1.05)
        st = L.mix(thump(SR, rng, f, 0.14, 0.03, grit=0.5), (knock(SR, rng, f * rng.uniform(2.6, 3.4), "wood"), rng.uniform(0.2, 0.4)))
        if creaky == k:
            st = L.mix(st, (creak(rng, SR, 0.2, 260, 230, rough=0.2, release=0.08), 0.5, 0.02))
        L.place(out, st, at * rng.uniform(0.97, 1.03), SR, rng.uniform(0.75, 1.0))
    return room(out, SR, rng, 0.25, 0.1), {"direction": direction, "creaky": creaky}


# =========================================================================== world: portal stinger takes
PORTAL = L.SFX_ROOT / "world" / "portal.wav"     # the team's stinger (git original, stays take 0)
_PORTAL: list = []


def portal_rec():
    """The original portal stinger at SR, cached (a low swell to a peak at ~0.7 s, then a long decay)."""
    if not _PORTAL:
        x, sr = L.read_wav(PORTAL)
        _PORTAL.append(L.resample(x, sr, SR))
    return _PORTAL[0]


def _decay_from(x, at, tau):
    """x with an extra exponential fade from `at` s on (a shorter tail)."""
    y = x.copy()
    k = L.secs(at, SR)
    if k < y.size:
        y[k:] *= np.exp(-np.arange(y.size - k) / (tau * SR))
    return y


@family("world", "portal", 4, ref=lambda: L.ref_db_of(PORTAL))
def portal(rng, i):
    """Portal stinger variants derived from the original recording, so the family stays one sound:
    deep (re-pitched 13 % down, the fading hum wavers), quick (the build cut short, a snappier
    swell and a shorter tail), double (the swell, then a softer second wave), open (the build is
    the reversed decay, a whoosh drawing in, and a low-pass opens on the way to the peak). Re-pitch alone would be a jittered copy
    (sim > 0.9), so every take also changes the gesture's timing."""
    x = portal_rec()
    kind = ["deep", "quick", "double", "open"][i % 4]
    if kind == "deep":
        y = L.repitch(x, 0.87 * rng.uniform(0.99, 1.01))
        k = L.secs(0.82, SR)                                    # the hum wavers as it fades
        t = np.arange(y.size - k) / SR
        y[k:] *= 0.72 + 0.28 * np.cos(TAU * rng.uniform(4.5, 5.5) * t)
        y = _decay_from(y, 1.05, 0.28)
    elif kind == "quick":
        y = L.take_slice(x, SR, L.secs(0.36, SR), x.size, fade_in=0.04, fade_out=0.05)
        y = _decay_from(L.repitch(y, 1.07 * rng.uniform(0.99, 1.01)), 0.5, 0.16)
    elif kind == "double":
        head = L.repitch(x, 0.95)
        y = np.zeros(head.size + L.secs(0.45, SR))
        L.place(y, _decay_from(head, 0.82, 0.07), 0.0, SR)
        second = L.take_slice(head, SR, L.secs(0.55, SR), head.size, fade_in=0.06, fade_out=0.05)
        L.place(y, second, 0.98 * rng.uniform(0.97, 1.03), SR, gain=0.55)
    else:
        tail = x[L.secs(0.75, SR):][::-1]                      # the decay reversed: a whoosh drawing in
        lead = L.take_slice(tail, SR, max(0, tail.size - L.secs(0.55, SR)), tail.size, 0.12, 0.01)
        body = L.take_slice(x, SR, L.secs(0.62, SR), x.size, fade_in=0.02, fade_out=0.05)
        y = np.zeros(lead.size + body.size)
        L.place(y, lead, 0.0, SR, gain=0.8)
        L.place(y, body, lead.size / SR - 0.04, SR)              # the original's peak ~0.6 s in, as before
        fc = np.interp(np.linspace(0, 1, y.size), [0, 0.25, 0.35, 1], [250, 1400, 2600, 900])
        y = 0.65 * L.svf(y, SR, fc, q=0.8, mode="lp") + 0.35 * y
        y = _decay_from(L.repitch(y, 0.96), 1.1, 0.2)
    return y, {"kind": kind}


# =========================================================================== loops (one take each)
LOOPS = [("fx", "firepit_loop", 1, SR, lambda: ref_fx("crackle") - 6.0, firepit_loop)]


# =========================================================================== runner
def relevel(d: dict, tol: float = 0.75) -> None:
    """Short takes (under the 120 ms window) read louder once finish() has trimmed their tail; scale
    such a take back to its reference (never above the -1 dBFS ceiling) and rewrite it."""
    want = d.get("aw_gain_db", 0.0)      # make_family's A-weighted balance may have lowered the take on purpose
    if "delta_db" not in d or abs(d["delta_db"] - want) <= tol:
        return
    x, sr = L.read_wav(d["path"])
    y = x * L.undb(want - d["delta_db"])
    if float(np.max(np.abs(y))) > L.CEILING:
        y = y * (L.CEILING / float(np.max(np.abs(y))))
    L.write_wav(d["path"], y, sr)
    st = L.st_rms_peak_db(y, sr)
    d.update(st_db=round(st, 2), peak_db=round(L.peak_db(y), 2), delta_db=round(st - d["ref_db"], 2))
    d.pop("warning", None)


def run(root: Path, only=None, names=None, quiet=False) -> list:
    metas = []
    for fam in FAMILIES:
        if only and fam["dir"] not in only:
            continue
        if names and fam["event"] not in names:
            continue
        ref = fam["ref"]() if fam["ref"] else None
        sr = fam["sr"]
        out_dir = root / fam["dir"]
        # take files are numbered from `start`; the design functions get a 0-based index
        fn = (lambda f, s0: (lambda rng, i: f(rng, i - s0)))(fam["fn"], fam["start"])
        meta = L.make_family(out_dir, fam["event"], fam["n"], fn, sr=sr, ref_db=ref, seed_base=SEED_BASE,
                             start=fam["start"], verbose=not quiet)
        for d in meta:
            relevel(d)
        metas.extend(meta)
    for d, event, n, sr, ref, fn in LOOPS:
        if only and d not in only:
            continue
        if names and event not in names:
            continue
        for k in range(1, n + 1):
            rng = np.random.default_rng(L.take_seed(event, k, SEED_BASE))
            x = fn(rng)
            meta = L.write_take(root / d / ("%s_%d.wav" % (event, k)), x, sr, ref_db=ref(), finish_kw={"loop": True})
            meta.update(event=event, take=k)
            if not quiet:
                print("%-28s %6.3fs  st %6.1f dB  (loop)" % (meta["name"], meta["seconds"], meta["st_db"]))
            metas.append(meta)
    return metas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="comma list of dirs: fx,field,interior,world")
    ap.add_argument("--family", help="comma list of event names")
    ap.add_argument("--root", help="output root instead of game/assets/sfx (trial runs in scratch)")
    ap.add_argument("--list", action="store_true", help="list the families and exit")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    if args.list:
        for f in FAMILIES:
            print("%-9s %-14s %2d takes  %d Hz" % (f["dir"], f["event"], f["n"], f["sr"]))
        for d, event, n, sr, _, _ in LOOPS:
            print("%-9s %-14s %2d loop   %d Hz" % (d, event, n, sr))
        return 0
    root = Path(args.root) if args.root else L.SFX_ROOT
    only = set(args.only.split(",")) if args.only else None
    names = set(args.family.split(",")) if args.family else None
    metas = run(root, only, names, args.quiet)
    total = sum(m["bytes"] for m in metas)
    print("gen_props: %d files, %.1f KB (%.2f MB) under %s" % (len(metas), total / 1024.0, total / 1048576.0, root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
