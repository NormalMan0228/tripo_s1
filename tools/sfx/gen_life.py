"""gen_life: take families for village life, fishing and the core game effects.

    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_life.py              # every family -> game/assets/sfx/{life,core}
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_life.py --only tick,nibble --out <scratch dir>
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_life.py --list

Every family is synthesised here (numpy/scipy, license-clean). Takes are built on a grid of
structural archetypes (sfxlib.cycle with coprime axis lengths) plus small random detail, so no
two takes of a family are the same gesture (tools/sfx/sfx_qa.py checks it).

Runtime: game/scripts/life_sfx.gd plays life/<kind>_<n>.wav, game/scripts/sound.gd plays
core/<kind>_<n>.wav, both through game/scripts/sfx_bank.gd (shuffle bag + pitch/volume jitter)
and fall back to their old runtime synths when a family has no takes.

Loudness: the "existing file of that kind" is the runtime synth the family replaces
(life_sfx.gd make() at -13 dB, sound.gd make_effect() at -16 dB). Its numpy port below is
measured (120 ms st-rms, 150 Hz high-pass) and every family is matched to the same effective
level, HEADROOM_DB lower in the file; life_sfx.gd and sound.gd add BAKED_DB (= HEADROOM_DB) back
when they play a baked take. New kinds match a sibling (REFS).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402

SR = L.DEFAULT_SR          # 22050
HI = L.BRIGHT_SR           # 32000: clicks, chimes, coins, glints
TAU = 2 * math.pi
HEADROOM_DB = 6.0          # baked takes sit this far under the runtime synth; the players add it back
VOLUME = {"life": -13.0, "core": -16.0}   # life_sfx.gd / sound.gd player volume_db
SEED_BASE = "gen_life-v1"


# =========================================================================== runtime synth ports
# Numpy ports of life_sfx.gd make() and sound.gd make_effect(), only used to measure loudness.
RATE = 22050
LIFE_LENGTH = {"hoe": 0.26, "seed": 0.3, "water": 0.75, "pop": 0.22, "collect": 0.42, "cast": 0.4, "plop": 0.22,
               "nibble": 0.09, "bite": 0.5, "tick": 0.035, "catch": 1.1, "escape": 0.45, "rock": 0.22,
               "rustle": 0.32, "shell": 0.2, "card": 0.35}
CORE_SPEC = {"click": (0.045, 620), "gather": (0.17, 410), "craft": (0.38, 660), "eat": (0.13, 270),
             "fire": (0.24, 170), "hit": (0.12, 110), "hurt": (0.18, 140), "error": (0.13, 185), "reward": (0.58, 780)}


def life_synth(kind: str, seed: int = 1) -> np.ndarray:
    length = LIFE_LENGTH.get(kind, 0.2)
    n = int(length * RATE)
    noise = np.random.default_rng(seed).uniform(-1, 1, n)
    t = np.arange(n) / RATE
    u = t / length

    def lowpass(k):
        out, lo = np.empty(n), 0.0
        kk = np.broadcast_to(np.asarray(k, float), (n,))
        for i in range(n):
            lo += (noise[i] - lo) * kk[i]
            out[i] = lo
        return out

    sin = np.sin
    if kind == "hoe":
        v = lowpass(0.18) * 2.2 * np.exp(-u * 9) + sin(TAU * (95 - 40 * u) * t) * 0.7 * np.exp(-u * 7)
    elif kind == "seed":
        v = (lowpass(0.6) - noise * 0.5) * np.exp(-np.fmod(t, 0.08) * 70) * 0.8 * (1 - u)
    elif kind == "water":
        v = (noise - lowpass(0.35)) * 0.55 * sin(np.pi * u) * (0.7 + 0.3 * sin(t * 55))
    elif kind == "pop":
        v = sin(TAU * (320 + 900 * u) * t) * 0.8 * np.exp(-u * 5) + sin(TAU * 1560 * t) * 0.2 * np.exp(-u * 8)
    elif kind == "collect":
        f = np.where(u < 0.4, 1320.0, 1760.0)
        v = (sin(TAU * f * t) * 0.5 + sin(TAU * f * 2 * t) * 0.12) * np.exp(-np.fmod(u, 0.4) * 7)
    elif kind == "cast":
        v = lowpass(0.05 + 0.4 * sin(np.pi * u)) * 1.8 * sin(np.pi * u)
    elif kind == "plop":
        v = sin(TAU * (640 - 470 * u) * t) * 0.75 * np.exp(-u * 6) + lowpass(0.3) * 0.5 * np.exp(-u * 12)
    elif kind == "nibble":
        v = sin(TAU * (980 - 300 * u) * t) * 0.5 * np.exp(-u * 5)
    elif kind == "bite":
        f = np.where(u < 0.3, 880.0, 1175.0)
        v = lowpass(0.4) * 1.2 * np.exp(-u * 7) + np.where(
            u > 0.12, sin(TAU * f * t) * 0.45 * np.exp(-np.fmod(np.maximum(u - 0.12, 0), 0.18) * 12), 0.0)
    elif kind == "tick":
        v = noise * np.exp(-u * 8) * 0.6 + sin(TAU * 2400 * t) * 0.3 * np.exp(-u * 10)
    elif kind == "catch":
        notes = np.array([523.25, 659.25, 783.99, 1046.5])
        k = np.minimum(3, (u * 5).astype(int))
        f = notes[k]
        v = (sin(TAU * f * t) * 0.45 + sin(TAU * f * 2 * t) * 0.1) * np.exp(-np.fmod(u * 5, 1.0) * np.where(k == 3, 3.0, 5.0))
        v = np.where(k == 3, v * (1.0 - np.clip((u - 0.6) / 0.4, 0, 1)), v)
    elif kind == "escape":
        v = sin(TAU * (420 - 240 * u) * t) * 0.55 * np.exp(-u * 3)
    elif kind == "rock":
        v = (sin(TAU * 1250 * t) * 0.45 + sin(TAU * 1930 * t) * 0.25) * np.exp(-u * 14) + noise * 0.5 * np.exp(-u * 20)
    elif kind == "rustle":
        v = (noise - lowpass(0.55)) * 0.7 * sin(np.pi * u) * (0.6 + 0.4 * sin(t * 90))
    elif kind == "shell":
        v = (sin(TAU * 2100 * t) * 0.35 + sin(TAU * 3150 * t) * 0.2) * np.exp(-u * 10) + noise * 0.25 * np.exp(-u * 25)
    elif kind == "card":
        v = (sin(TAU * 784 * t) * 0.4 + sin(TAU * 1175 * t) * 0.3) * np.exp(-u * 4) * np.minimum(1, u * 30)
    else:
        v = np.zeros(n)
    return np.clip(v * np.minimum(1.0, t * 400), -1, 1) * 21000 / 32768.0


def core_synth(kind: str, seed: int = 1) -> np.ndarray:
    length, freq = CORE_SPEC.get(kind, (0.15, 550.0))
    n = int(length * RATE)
    t = np.arange(n) / RATE
    env = np.minimum(t * 100, 1.0) * (1.0 - np.arange(n) / n) ** 2
    wave = np.sin(TAU * freq * t) * 0.55 + np.sin(TAU * freq * 2 * t) * 0.12
    if kind in ("craft", "reward"):
        wave = np.sin(TAU * freq * np.array([1.0, 1.25, 1.5])[np.minimum(2, (t / length * 3).astype(int))] * t) * 0.55
    elif kind in ("hit", "hurt", "fire", "eat"):
        wave = wave * 0.55 + np.random.default_rng(seed).uniform(-0.3, 0.3, n)
    return np.clip(wave * env, -1, 1) * 22000 / 32768.0


def synth_level(module: str, kind: str) -> float:
    """Effective level of a runtime synth: st-rms of its samples + the player's volume_db."""
    x = life_synth(kind) if module == "life" else core_synth(kind)
    return L.st_rms_peak_db(x, RATE) + VOLUME[module]


# =========================================================================== building blocks
def T(n, sr):
    return np.arange(int(n)) / float(sr)


def sweep_tone(sr, dur, f0, f1, tau, harmonics=((1, 1.0),), attack=0.002, curve="exp", vib=0.0, vib_hz=6.0):
    n = L.secs(dur, sr)
    u = np.linspace(0, 1, n, endpoint=False)
    f = f0 * (f1 / f0) ** u if curve == "exp" else f0 + (f1 - f0) * u
    if vib:
        f = f * (1 + vib * np.sin(TAU * vib_hz * T(n, sr)))
    t = T(n, sr)
    return L.osc(sr, f, harmonics) * np.exp(-t / tau) * np.minimum(1, t / max(attack, 1e-5))


def bubble(sr, f0, rng, tau=None, rise=None, dur=None):
    """Minnaert-style water bubble/drop: a sine that rises in pitch while it dies away."""
    tau = rng.uniform(0.012, 0.03) if tau is None else tau
    rise = rng.uniform(0.8, 2.2) if rise is None else rise
    dur = min(0.4, tau * 7) if dur is None else dur
    n = L.secs(dur, sr)
    t = T(n, sr)
    f = f0 * (1 + rise * t / (4 * tau))
    return np.sin(TAU * np.cumsum(f) / sr) * np.exp(-t / tau) * np.minimum(1, t / 0.0006)


def burst(sr, dur, lo, hi, tau, rng, color="white", attack=0.001):
    n = L.secs(dur, sr)
    t = T(n, sr)
    return L.bp(L.noise(n, rng, color), sr, lo, hi) * np.exp(-t / tau) * np.minimum(1, t / max(attack, 1e-5))


def droplets(sr, dur, count, rng, f=(900, 2600), gain=(0.2, 0.6), env=None, tau=(0.006, 0.018)):
    return L.scatter(sr, dur, rng, lambda r: bubble(sr, r.uniform(*f), r, tau=r.uniform(*tau)),
                     count=max(1, int(count)), gain=gain, env=env)


def splash(sr, size, rng, dur=None, bright=1.0):
    """Water splash: noise body + a low gloop + droplets; size ~0.5 (flick) .. 1.6 (big)."""
    dur = 0.16 * size + 0.08 if dur is None else dur
    body = burst(sr, dur, 300 / size, min(sr * 0.44, 6500 * bright / size ** 0.5), 0.03 * size, rng, "white", 0.002)
    low = bubble(sr, 240 / size * rng.uniform(0.85, 1.15), rng, tau=0.025 * size, rise=0.6)
    drops = droplets(sr, dur * 1.6, 3 + 4 * size, rng, f=(800 / size ** 0.3, 2800 * bright / size ** 0.3),
                     env=[0.1, 1, 0.7, 0.3, 0.1])
    return L.mix(L.norm_peak(body), (L.norm_peak(low), 0.45 * min(size, 1.3)), (L.norm_peak(drops), 0.3, 0.012), sr=sr)


def whoosh(sr, dur, f_from, f_to, rng, peak=0.5, q=1.2, width=0.18, shape="single", color="pink"):
    n = L.secs(dur, sr)
    u = np.linspace(0, 1, n)
    fc = f_from * (f_to / f_from) ** u
    env = np.exp(-((u - peak) / width) ** 2)
    if shape == "double":
        env = 0.7 * np.exp(-((u - peak + 0.28) / (width * 0.55)) ** 2) + np.exp(-((u - peak) / (width * 0.65)) ** 2)
    elif shape == "flutter":
        env = env * (1 - 0.6 * (0.5 + 0.5 * np.sin(TAU * rng.uniform(16, 28) * u * dur)))
    return L.svf(L.noise(n, rng, color), sr, fc, q=q, mode="bp") * env


def crack(sr, rng, hp=1800, n_imp=None, spread=0.004, tail=0.02):
    """Twig/paper snap: a cluster of sub-millisecond noise impulses, high-passed."""
    n_imp = int(rng.integers(3, 7)) if n_imp is None else n_imp
    out = np.zeros(L.secs(spread + tail, sr))
    for _ in range(n_imp):
        m = max(4, L.secs(rng.uniform(0.0006, 0.002), sr))
        imp = rng.standard_normal(m) * np.exp(-T(m, sr) / rng.uniform(0.0003, 0.0008))
        L.place(out, imp, rng.uniform(0, spread), sr, gain=rng.uniform(0.4, 1.0))
    return L.hp(out, sr, hp)


def thump(sr, f0, f1, tau, rng, noise_hi=600, noise_gain=0.5, dur=None):
    dur = tau * 7 if dur is None else dur
    tone = sweep_tone(sr, dur, f0, f1, tau, harmonics=((1, 1.0), (2, 0.15)), attack=0.0015)
    nz = burst(sr, dur, 40, noise_hi, tau * 0.5, rng)
    return L.norm_peak(tone) + L.norm_peak(nz) * noise_gain


def grains(sr, dur, count, rng, lo, hi, g_dur=(0.002, 0.008), gain=(0.3, 1.0), env=None):
    """Granular texture of short band-passed noise ticks (crackle, rustle, soil, cloth)."""
    def g(r):
        m = max(8, L.secs(r.uniform(*g_dur), sr))
        return L.bp(r.standard_normal(m), sr, lo, hi) * np.hanning(m)
    return L.scatter(sr, dur, rng, g, count=max(1, int(count)), gain=gain, env=env)


def marimba(sr, f, dur, rng, decay=0.22, bright=1.0):
    ratios = np.array([1.0, 3.93, 9.2]) * (1 + rng.uniform(-0.01, 0.01, 3))
    y = L.modal_bank(sr, f * ratios, [decay, decay / 4, decay / 10], [1.0, 0.3 * bright, 0.1 * bright], dur, rng)
    k = L.secs(0.004, sr)
    y[:k] += L.bp(rng.standard_normal(k), sr, f * 2, min(sr * 0.44, f * 12)) * 0.15 * np.hanning(k)
    return L.norm_peak(y)


def kalimba(sr, f, dur, rng, decay=0.5):
    ratios = np.array([1.0, 5.95, 2.0]) * (1 + rng.uniform(-0.004, 0.004, 3))
    y = L.modal_bank(sr, f * ratios, [decay, decay / 8, decay / 2], [1.0, 0.25, 0.08], dur, rng)
    return L.norm_peak(y)


def note(sr, f, dur, timbre, rng, decay=None):
    """One pitched note in a named timbre (peak ~1)."""
    if timbre == "sine":
        d = 0.18 if decay is None else decay
        return L.norm_peak(sweep_tone(sr, dur, f, f, d, harmonics=((1, 1.0), (2, 0.22), (3, 0.05)), attack=0.003))
    if timbre == "soft":     # triangle-ish, gentle
        d = 0.2 if decay is None else decay
        return L.norm_peak(sweep_tone(sr, dur, f, f, d, harmonics=((1, 1.0), (3, 0.11), (5, 0.04)), attack=0.008))
    if timbre == "glass":
        return L.modal(sr, f, "glass", dur=dur, rng=rng, tau=0.35 if decay is None else decay)
    if timbre == "fm":
        d = 0.5 if decay is None else decay
        return L.fm_bell(sr, f, dur, ratio=float(rng.choice([1.4, 2.0, 3.5])), index=rng.uniform(1.5, 3.2),
                         t60=d * 6.9 / 2, rng=rng)
    if timbre == "pluck":
        return L.ks_pluck(sr, f, dur, rng=rng, bright=0.55, damping=0.996 if decay is None else decay)
    if timbre == "marimba":
        return marimba(sr, f, dur, rng, 0.22 if decay is None else decay)
    if timbre == "kalimba":
        return kalimba(sr, f, dur, rng, 0.5 if decay is None else decay)
    if timbre == "bell":
        return L.modal(sr, f, "bell", dur=dur, rng=rng, tau=1.0 if decay is None else decay)
    raise KeyError(timbre)


def phrase(sr, base, timbre, notes, rng, decay=None, humanize=0.006):
    """notes: (t s, semitones, dur s, gain). Small timing/level humanisation per note."""
    layers = []
    for (t, st, d, g) in notes:
        f = base * L.semitones(st) * rng.uniform(0.997, 1.003)
        layers.append((note(sr, f, d, timbre, rng, decay), g * rng.uniform(0.9, 1.0), max(0.0, t + rng.uniform(-humanize, humanize))))
    return L.mix(*layers, sr=sr)


def coin(sr, f0, rng, dur=0.35):
    return L.modal(sr, f0, "metal", dur=dur, rng=rng, tau=rng.uniform(0.18, 0.3), bright=1.3)


def ratchet_click(sr, res, mat, rng):
    """One pawl click on a gear: an impulse plus a small housing resonance."""
    m = max(6, L.secs(0.0012, sr))
    exc = rng.standard_normal(m) * np.exp(-T(m, sr) / 0.00025)
    taus = {"metal": (0.011, 0.007, 0.004), "plastic": (0.0028, 0.002, 0.0014), "brass": (0.007, 0.0055, 0.0035)}[mat]
    ratios = np.array([1.0, 1.53, 2.31]) * (1 + rng.uniform(-0.03, 0.03, 3))
    n = L.secs(max(taus) * 6 + 0.004, sr)
    ring = L.resonate(L.pad_to(exc, n), sr, list(res * ratios), list(np.array(taus) * rng.uniform(0.85, 1.15, 3)),
                      [1.0, 0.6, 0.35])
    click = L.norm_peak(L.hp(L.pad_to(exc, n), sr, 2500))
    return L.norm_peak(click * (0.9 if mat == "plastic" else 0.5) + ring)


def cloth(sr, dur, rng, lo=900, hi=5000, density=220, env=None):
    """Fabric: dense soft grains under a band-passed noise bed."""
    n = L.secs(dur, sr)
    bed = L.bp(L.pink(n, rng), sr, lo, hi)
    tex = grains(sr, dur, density * dur, rng, lo * 1.4, hi, g_dur=(0.003, 0.012), gain=(0.2, 1.0))
    y = L.norm_peak(bed) * 0.6 + L.norm_peak(L.pad_to(tex, n))
    if env is not None:
        y *= np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(env)), env)
    return y


def wood_knock(sr, f0, rng, hard=1.0):
    """Knuckle on a wooden door: plate modes + low panel boom + knuckle click."""
    plate = L.modal(sr, f0, "wood", rng=rng, tau=rng.uniform(0.05, 0.08), bright=0.9 * hard)
    m = L.secs(0.003, sr)
    exc = L.pad_to(rng.standard_normal(m) * np.hanning(m), L.secs(0.25, sr))
    boom = L.resonate(exc, sr, [f0 * 0.42, f0 * 0.67, f0 * 1.08], [0.06, 0.045, 0.03], [1.0, 0.6, 0.4])
    click = L.hp(L.pad_to(rng.standard_normal(m) * np.hanning(m), L.secs(0.02, sr)), sr, 2000)
    return L.mix(plate, (boom, 0.75), (L.norm_peak(click), 0.25 * hard), sr=sr)


def stone_clack(sr, f0, rng, dur=0.12):
    return L.modal(sr, f0, "stone", dur=dur, rng=rng, tau=rng.uniform(0.012, 0.022), bright=1.2)


def synth_brass(sr, f, dur, rng, attack=0.04):
    """Soft horn: band-limited saw through a swelling low-pass."""
    n = L.secs(dur, sr)
    t = T(n, sr)
    fr = f * (1 + 0.004 * np.sin(TAU * 5.2 * t))
    harm = [(h, 1.0 / h) for h in range(1, 14)]
    y = L.osc(sr, fr, harm)
    env = L.adsr(dur, sr, a=attack, d=0.12, s=0.7, r=min(0.25, dur * 0.4))
    fc = 600 + 2600 * np.clip(env, 0, 1)
    return L.norm_peak(L.svf(y, sr, fc, q=0.8, mode="lp") * env)


# =========================================================================== life families
TICK_PATTERNS = [((0.0, 1.0),), ((0.0, 1.0), (0.0035, 0.5)), ((0.0, 0.7), (0.009, 1.0)),
                 ((0.0, 1.0), (0.003, 0.45), (0.0068, 0.28))]
TICK_RES = [1500.0 * 1.1 ** k for k in (0, 9, 4, 13, 2, 11, 6, 15, 1, 10, 5, 14, 3, 12, 7, 8)]   # 16 housings, 10 % apart


def tick(rng, i):
    """Reel ratchet micro-click: pawl pattern x housing resonance x material (4 x 7 x 3 grid)."""
    pat, res, mat = L.cycle(i, TICK_PATTERNS, TICK_RES, ["metal", "plastic", "brass"])
    res *= rng.uniform(0.98, 1.02)
    out = np.zeros(L.secs(0.05, HI))
    for at, g in pat:
        c = ratchet_click(HI, res * rng.uniform(0.97, 1.03), mat, rng)
        L.place(out, c, at + rng.uniform(0, 0.0006), HI, gain=g * rng.uniform(0.85, 1.0))
    # spool body: a low, short knock of the reel housing carries the click (and keeps the crest sane)
    body = L.modal(HI, res * rng.uniform(0.21, 0.27), "wood" if mat == "plastic" else "ceramic", rng=rng, dur=0.03,
                   tau=0.006 if mat == "plastic" else 0.009, click=0.0)
    out = L.mix(out, (body, 0.45), sr=HI)
    if i % 2:      # a little gear rattle under it
        out += L.pad_to(grains(HI, 0.012, 3, rng, 3000, 9000, g_dur=(0.0008, 0.002), gain=(0.05, 0.15)), out.size)
    if mat == "plastic":
        out = L.lp(out, HI, 7000)
    out = L.saturate(out, drive=2.2)      # rounds the spike so the click reaches its level without the limiter
    return out, {"pattern": len(pat), "res": round(res), "mat": mat}


def nibble(rng, i):
    """Bobber nibble: one or two little 'tuk's with a water plip."""
    taps, f0, shape = L.cycle(i, [1, 2], [600.0, 760.0, 950.0, 1200.0, 1500.0], ["down", "downup", "flat"])
    out = np.zeros(L.secs(0.3, SR))
    at = 0.0
    for k in range(taps):
        f = f0 * rng.uniform(0.97, 1.03) * (1.0 if k == 0 else rng.uniform(1.06, 1.14))
        d = rng.uniform(0.07, 0.1)
        if shape == "down":
            tone = sweep_tone(SR, d, f, f * 0.68, d * 0.35, harmonics=((1, 1.0), (2, 0.1)))
        elif shape == "downup":
            n = L.secs(d, SR)
            u = np.linspace(0, 1, n)
            fr = f * np.interp(u, [0, 0.45, 1], [1.0, 0.72, 0.9])
            tone = L.osc(SR, fr, ((1, 1.0), (2, 0.08))) * np.exp(-T(n, SR) / (d * 0.4)) * np.minimum(1, T(n, SR) / 0.002)
        else:
            tone = L.mix(sweep_tone(SR, d * 0.6, f, f, d * 0.2), (bubble(SR, f * 1.5, rng, tau=0.008, rise=1.4), 0.5, d * 0.35), sr=SR)
        tuk = L.modal(SR, f * 0.36, "wood", rng=rng, tau=0.012) * 0.35
        plip = bubble(SR, f * rng.uniform(1.6, 2.1), rng, tau=0.006, rise=1.8) * 0.25
        L.place(out, L.mix(L.norm_peak(tone), (tuk, 1.0), (plip, 1.0, 0.012), sr=SR), at, SR)
        at += rng.uniform(0.06, 0.095)
    return out, {"taps": taps, "f0": f0, "shape": shape}


COLLECT_PATTERNS = [
    [(0.0, 0, 0.3, 1.0), (0.09, 5, 0.4, 0.9)],                       # fourth up (the old synth)
    [(0.0, 0, 0.22, 0.9), (0.065, 4, 0.22, 0.85), (0.13, 7, 0.4, 1.0)],  # quick triad
    [(0.0, 7, 0.06, 0.5), (0.028, 12, 0.45, 1.0)],                  # grace note into the octave
    [(0.0, 0, 0.25, 0.8), (0.11, 12, 0.42, 1.0), (0.2, 7, 0.3, 0.35)],  # octave leap, echo below
]


def collect(rng, i):
    """Pick-up chime: note pattern x timbre (base pitch near the old 1320 Hz)."""
    pat, timbre, base, ring = L.cycle(i, COLLECT_PATTERNS, ["sine", "glass", "fm"], [1320.0, 1175.0, 1480.0, 1245.0, 1397.0],
                                      [0.12, 0.22, 0.35, 0.18, 0.28, 0.15, 0.3])
    y = phrase(HI, base * 0.5 if timbre == "glass" and base > 1300 else base, timbre, pat, rng, decay=ring)
    if i % 3 == 1:     # a pinch of sparkle
        glint = lambda r: L.modal(HI, r.uniform(4500, 8000), "glass", rng=r, dur=0.05, tau=0.02)
        y = L.mix(y, (L.scatter(HI, 0.25, rng, glint, count=int(rng.integers(3, 6)), gain=(0.05, 0.16)), 1.0, 0.05), sr=HI)
    return y, {"pattern": COLLECT_PATTERNS.index(pat), "timbre": timbre}


def pop(rng, i):
    """Mushroom pop: cork thwop / wet squelch / rising lip pop / double pop, three sizes."""
    kind, size = L.cycle(i, ["cork", "squelch", "lip", "double"], [0.8, 1.0, 1.3])
    if kind == "cork":
        f = 950.0 / size
        n = L.secs(0.14, SR)
        exc = L.pad_to(crack(SR, rng, hp=600, n_imp=3, spread=0.001), n)
        tube = L.resonate(exc, SR, [f, f * 2.01, f * 3.03], [0.025, 0.015, 0.009], [1.0, 0.4, 0.2])
        tube = tube * np.interp(np.arange(n), [0, n], [1.0, 0.0]) ** 0.5
        fall = sweep_tone(SR, 0.1, f * 1.05, f * 0.7, 0.025, ((1, 1.0), (2, 0.3)))
        y = L.mix(tube, (crack(SR, rng, hp=2500, n_imp=2), 0.5), (fall, 0.5, 0.002), sr=SR)
    elif kind == "squelch":
        f = 420.0 / size
        wet = L.svf(L.pink(L.secs(0.12, SR), rng), SR, np.geomspace(500, 1800, L.secs(0.12, SR)), q=4.0, mode="bp")
        wet = wet * np.interp(np.linspace(0, 1, wet.size), [0, 0.5, 1], [0.1, 1, 0])
        y = L.mix(L.norm_peak(wet), (sweep_tone(SR, 0.1, f, f * 2.4, 0.03, ((1, 1.0), (2, 0.2))), 0.8, 0.07), sr=SR)
    elif kind == "lip":
        f = 700.0 / size
        y = sweep_tone(SR, 0.16, f * 0.45, f * 1.7, 0.045, ((1, 1.0), (2, 0.25), (3, 0.08)))
    else:
        f = 820.0 / size
        a = sweep_tone(SR, 0.09, f * 0.6, f * 1.4, 0.025)
        b = sweep_tone(SR, 0.12, f * 0.75, f * 2.0, 0.035)
        y = L.mix(a * 0.7, (b, 1.0, rng.uniform(0.05, 0.08)), sr=SR)
    soil = grains(SR, 0.12, int(rng.integers(4, 9)), rng, 800, 4000, gain=(0.05, 0.2))
    return L.mix(L.norm_peak(y), (soil, 1.0, 0.01), sr=SR), {"kind": kind, "size": size}


def hoe(rng, i):
    """Hoe into soil: soil type x motion (chop / chop + drag / double chop)."""
    soil, motion = L.cycle(i, ["loam", "gravel", "root", "clay"], ["chop", "drag", "double"])
    f0 = {"loam": 100.0, "gravel": 128.0, "root": 84.0, "clay": 70.0}[soil] * rng.uniform(0.95, 1.05)

    def chop(gain):
        y = thump(SR, f0, f0 * 0.5, rng.uniform(0.035, 0.05), rng, noise_hi=900, noise_gain=0.8)
        if soil == "loam":
            tex = grains(SR, 0.15, 30, rng, 300, 2500, gain=(0.1, 0.5), env=[1, 0.4, 0.1])
        elif soil == "gravel":
            tex = L.scatter(SR, 0.14, rng, lambda r: stone_clack(SR, r.uniform(1800, 4200), r, dur=0.05), count=int(rng.integers(4, 8)),
                            gain=(0.1, 0.35), env=[1, 0.6, 0.2])
        elif soil == "root":
            tex = L.mix(crack(SR, rng, hp=900, n_imp=5, spread=0.012), (L.modal(SR, rng.uniform(380, 520), "wood", rng=rng), 0.4, 0.004), sr=SR)
        else:
            tex = L.svf(L.pink(L.secs(0.16, SR), rng), SR, np.linspace(1400, 500, L.secs(0.16, SR)), q=3.0, mode="bp") * L.exp_decay(0.16, SR, 0.05)
        return L.mix(L.norm_peak(y) * 0.8, (L.norm_peak(tex), 0.95), sr=SR) * gain

    if motion == "chop":
        out = chop(1.0)
    elif motion == "drag":
        n = L.secs(rng.uniform(0.14, 0.2), SR)
        scrape = L.bp(L.pink(n, rng), SR, 500, 3000) * np.hanning(n * 2)[n:] * 0.5
        out = L.mix(chop(1.0), (scrape, 1.0, rng.uniform(0.07, 0.1)), sr=SR)
    else:
        out = L.mix(chop(0.5), (chop(1.0), 1.0, {"loam": 0.12, "gravel": 0.2, "root": 0.15, "clay": 0.24}[soil]), sr=SR)
    return out, {"soil": soil, "motion": motion}


def seed(rng, i):
    """Sowing: seeds rattling out of a pouch or pattering onto soil."""
    mat, pattern, count = L.cycle(i, ["pouch", "soil"], ["even", "accel", "cluster"], [3, 5, 4, 6, 7])
    span = rng.uniform(0.24, 0.34)
    if pattern == "even":
        times = np.linspace(0, span, count) + rng.uniform(-0.008, 0.008, count)
    elif pattern == "accel":
        times = span * (1 - np.sqrt(1 - np.linspace(0, 1, count) * 0.95))
    else:
        half = count // 2 + 1
        times = np.concatenate([np.linspace(0, 0.06, half), span * 0.6 + np.linspace(0, 0.07, count - half)])
    out = np.zeros(L.secs(span + 0.12, SR))
    for t in np.clip(times, 0, None):
        if mat == "pouch":
            g = L.mix(grains(SR, 0.02, 3, rng, 2500, 8000, g_dur=(0.0008, 0.002)), (stone_clack(SR, rng.uniform(2500, 4500), rng, 0.03), 0.4), sr=SR)
        else:
            g = L.mix(thump(SR, rng.uniform(260, 420), 180, 0.008, rng, noise_hi=2500, noise_gain=1.0) * 0.6,
                      (grains(SR, 0.02, 2, rng, 1200, 5000), 0.5), sr=SR)
        L.place(out, L.norm_peak(g), t, SR, gain=rng.uniform(0.5, 1.0))
    if mat == "pouch":
        out = L.mix(out, (cloth(SR, span * 0.8, rng, env=[0, 1, 0.5, 0]), 0.18), sr=SR)
    return out, {"mat": mat, "pattern": pattern, "count": count}


def water(rng, i):
    """Watering can: stream / gurgle / sprinkle x swell / front-loaded envelope."""
    tex, shape, dur = L.cycle(i, ["stream", "gurgle", "sprinkle"], ["swell", "front"], [0.66, 0.8, 0.92, 0.72, 0.86])
    n = L.secs(dur, SR)
    u = np.linspace(0, 1, n)
    env = np.interp(u, [0, 0.12, 0.7, 1], [0, 1, 0.9, 0]) if shape == "swell" else np.interp(u, [0, 0.04, 0.35, 0.75, 1], [0, 1, 0.55, 0.25, 0])
    if tex == "stream":
        y = L.bp(L.white(n, rng), SR, 900, 5200) * (0.75 + 0.25 * np.sin(TAU * rng.uniform(7, 11) * T(n, SR)))
        y = L.norm_peak(y) + L.norm_peak(droplets(SR, dur, 18, rng, f=(500, 1400)))[:n] * 0.4
    elif tex == "gurgle":
        y = L.norm_peak(L.bp(L.pink(n, rng), SR, 300, 2400)) * 0.5 + L.norm_peak(L.pad_to(droplets(SR, dur, 40, rng, f=(280, 900), tau=(0.01, 0.03)), n))
    else:
        y = L.norm_peak(L.hp(L.white(n, rng), SR, 3000)) * 0.35 + L.norm_peak(L.pad_to(droplets(SR, dur, 70, rng, f=(1500, 4200), tau=(0.003, 0.009)), n))
    y = y * env
    if shape == "front":     # last drips
        y = L.mix(y, (droplets(SR, 0.25, 3, rng, f=(900, 1800), tau=(0.01, 0.02)), 0.6, dur * 0.8), sr=SR)
    return y, {"tex": tex, "shape": shape}


def rustle(rng, i):
    """Leaves/grass rustle: crisp (dry crackle) or soft (swish) x burst pattern."""
    kind, pattern = L.cycle(i, ["crisp", "soft"], ["single", "double", "triple", "long_short", "shake"])
    plans = {"single": [(0.0, 0.3)], "double": [(0.0, 0.15), (0.18, 0.17)], "triple": [(0.0, 0.1), (0.12, 0.1), (0.25, 0.12)],
             "long_short": [(0.0, 0.26), (0.3, 0.08)], "shake": [(0.0, 0.34)]}
    out = np.zeros(L.secs(0.5, SR))
    for at, d in plans[pattern]:
        d *= rng.uniform(0.9, 1.1)
        n = L.secs(d, SR)
        env = np.hanning(n) ** 0.7
        if pattern == "shake":
            env = env * (0.45 + 0.55 * (0.5 + 0.5 * np.sin(TAU * rng.uniform(11, 15) * T(n, SR))))
        if kind == "crisp":
            y = L.norm_peak(L.pad_to(grains(SR, d, 260 * d, rng, 2500, 9000, g_dur=(0.001, 0.004), gain=(0.15, 1.0)), n))
            y = y + L.norm_peak(L.bp(L.white(n, rng), SR, 3000, 8000)) * 0.25
        else:
            y = L.norm_peak(L.bp(L.pink(n, rng), SR, 1200, 5000)) + L.norm_peak(L.pad_to(grains(SR, d, 80 * d, rng, 1500, 5000), n)) * 0.3
        L.place(out, y * env, at, SR, gain=rng.uniform(0.75, 1.0))
    return out, {"kind": kind, "pattern": pattern}


def rock(rng, i):
    """Pebble clack: size x one clack / a small rattle."""
    f0, count = L.cycle(i, [950.0, 1500.0, 2400.0], [1, 3])
    out = np.zeros(L.secs(0.3, SR))
    at = 0.0
    for k in range(count):
        L.place(out, stone_clack(SR, f0 * rng.uniform(0.9, 1.15), rng, 0.1), at, SR, gain=(1.0 if k == 0 else 0.55 / k) * rng.uniform(0.85, 1.0))
        at += rng.uniform(0.035, 0.07) / (k + 1)
    out += L.pad_to(grains(SR, 0.04, 4, rng, 1500, 6000, gain=(0.05, 0.2)), out.size)
    return out, {"f0": f0, "count": count}


def shell(rng, i):
    """Shell pick-up: tink size x clean / sand scrape first."""
    f0, scrape = L.cycle(i, [1900.0, 2700.0, 3700.0], [False, True])
    mat = "ceramic" if f0 < 3000 else "glass"
    tink = L.modal(HI, f0 * rng.uniform(0.97, 1.03), mat, rng=rng, dur=0.18, tau=rng.uniform(0.04, 0.07), bright=1.2)
    if scrape:
        n = L.secs(rng.uniform(0.05, 0.08), HI)
        sand = L.norm_peak(L.pad_to(grains(HI, n / HI, 25, rng, 2000, 9000, g_dur=(0.0008, 0.003)), n)) * np.hanning(n)
        y = L.mix(sand * 0.5, (tink, 1.0, n / HI * 0.8), sr=HI)
    else:
        y = L.mix(tink, (L.modal(HI, f0 * rng.uniform(1.25, 1.4), mat, rng=rng, dur=0.12, tau=0.03), 0.35, rng.uniform(0.03, 0.05)), sr=HI)
    return y, {"f0": f0, "scrape": scrape}


def escape(rng, i):
    """The fish slips away: six falling gestures (glide / two steps / wobble / bloop + flick /
    three marimba notes / fall-and-bend with a tail splash)."""
    kind = ["glide", "steps", "wobble", "bloop", "three", "bend"][i % 6]
    f = rng.uniform(400, 440)
    if kind == "glide":
        y = sweep_tone(SR, 0.42, f, f * 0.42, 0.18, ((1, 1.0), (2, 0.12)), attack=0.01)
    elif kind == "steps":
        y = L.mix(note(SR, f * 0.94, 0.16, "soft", rng, 0.08), (note(SR, f * 0.94 * L.semitones(-5), 0.3, "soft", rng, 0.14), 1.0, 0.13), sr=SR)
    elif kind == "wobble":
        y = sweep_tone(SR, 0.48, f * 1.05, f * 0.5, 0.2, ((1, 1.0), (2, 0.2), (3, 0.06)), attack=0.012, vib=0.045, vib_hz=rng.uniform(9, 13))
    elif kind == "bloop":
        b = sweep_tone(SR, 0.2, f * 1.6, f * 0.55, 0.06, ((1, 1.0), (2, 0.1)), attack=0.004)
        y = L.mix((splash(SR, 0.55, rng), 0.7), (L.norm_peak(b), 1.0, 0.05), sr=SR)
    elif kind == "three":
        y = phrase(SR, f * 1.2, "marimba", [(0.0, 0, 0.2, 0.9), (0.11, -3, 0.2, 0.85), (0.22, -7, 0.35, 1.0)], rng, decay=0.12)
    else:
        n = L.secs(0.5, SR)
        fr = f * np.interp(np.linspace(0, 1, n), [0, 0.6, 0.8, 1], [0.9, 0.48, 0.56, 0.5])
        tone = L.osc(SR, fr, ((1, 1.0), (3, 0.1))) * np.exp(-T(n, SR) / 0.22) * np.minimum(1, T(n, SR) / 0.01)
        y = L.mix(L.norm_peak(tone), (splash(SR, 0.6, rng), 0.45, 0.33), sr=SR)
    return y, {"kind": kind}


def cast(rng, i):
    """Forward rod swing, six gestures: rising swish / falling swish + whistle / back-and-forth /
    fluttering line / swish + spool buzz / short whip + line hiss."""
    kind = ["rise", "whistle", "double", "flutter", "spool", "whip"][(i - 1) % 6]
    dur = [0.36, 0.42, 0.46, 0.4, 0.34, 0.2][(i - 1) % 6] * rng.uniform(0.95, 1.05)
    if kind == "rise":
        y = whoosh(SR, dur, 500, 2600, rng, peak=0.55, q=1.1, width=0.2)
    elif kind == "whistle":
        y = L.norm_peak(whoosh(SR, dur, 2400, 700, rng, peak=0.5, q=0.9, width=0.22))
        u = np.linspace(0, 1, y.size)
        y = y + L.osc(SR, np.interp(u, [0, 0.5, 1], [1500, 1900, 1100]) * rng.uniform(0.95, 1.05)) * np.exp(-((u - 0.5) / 0.16) ** 2) * 0.45
    elif kind == "double":
        a = whoosh(SR, 0.18, 2200, 700, rng, peak=0.5, q=1.2, width=0.22)
        b = whoosh(SR, 0.3, 600, 2800, rng, peak=0.55, q=1.0, width=0.2)
        y = L.mix(L.norm_peak(a) * 0.6, (L.norm_peak(b), 1.0, 0.2), sr=SR)
    elif kind == "flutter":
        n = L.secs(dur, SR)
        fc = np.interp(np.linspace(0, 1, n), [0, 0.5, 1], [700, 2800, 900])
        y = L.svf(L.pink(n, rng), SR, fc, q=1.1, mode="bp") * np.exp(-((np.linspace(0, 1, n) - 0.5) / 0.22) ** 2)
        y = y * (1 - 0.65 * (0.5 + 0.5 * np.sin(TAU * rng.uniform(22, 30) * T(n, SR))))
    elif kind == "spool":
        sw = L.norm_peak(whoosh(SR, dur, 2000, 800, rng, peak=0.35, q=1.2, width=0.16))
        clicks = np.zeros(L.secs(0.25, SR))
        for k in range(10):
            L.place(clicks, ratchet_click(SR, rng.uniform(2600, 3000), "metal", rng), k * (0.014 + k * 0.002), SR, gain=0.5 * (1 - k / 12))
        y = L.mix(sw, (L.norm_peak(clicks), 0.75, dur * 0.45), sr=SR)
    else:
        w = L.norm_peak(whoosh(SR, dur, 1000, 4200, rng, peak=0.6, q=1.8, width=0.2, color="white"))
        n = L.secs(0.3, SR)
        hiss = L.svf(L.white(n, rng), SR, np.linspace(3000, 1500, n), q=5.0, mode="bp") * np.interp(np.linspace(0, 1, n), [0, 0.1, 1], [0, 1, 0])
        y = L.mix(w, (L.norm_peak(hiss), 0.4, dur * 0.7), sr=SR)
    return y, {"kind": kind}


def plop(rng, i):
    """Bobber lands: bubble size x clean / splashy."""
    f0, kind = L.cycle(i, [420.0, 620.0, 900.0], ["clean", "splashy"])
    b = bubble(SR, f0 * rng.uniform(0.95, 1.05), rng, tau=0.03, rise=rng.uniform(0.7, 1.2), dur=0.2)
    hit = burst(SR, 0.06, 600, 4000, 0.012, rng)
    if kind == "clean":
        y = L.mix(L.norm_peak(b), (L.norm_peak(hit), 0.35), (bubble(SR, f0 * 2.2, rng, tau=0.01), 0.25, 0.09), sr=SR)
    else:
        y = L.mix(L.norm_peak(b) * 0.8, (splash(SR, 0.7, rng), 0.7), (droplets(SR, 0.25, 5, rng), 0.35, 0.08), sr=SR)
    return y, {"f0": f0, "kind": kind}


BITE_ALERTS = {"up2": [(0.0, 0, 0.12, 0.9), (0.1, 5, 0.25, 1.0)], "up3": [(0.0, -2, 0.1, 0.8), (0.07, 2, 0.1, 0.85), (0.14, 7, 0.28, 1.0)],
               "octave": [(0.0, 0, 0.08, 0.8), (0.06, 12, 0.08, 0.9), (0.12, 0, 0.06, 0.6), (0.17, 12, 0.25, 1.0)]}


def bite(rng, i):
    """The big bite: splash type x alert motif."""
    kind, alert = L.cycle(i, ["yank", "tug"], ["up2", "up3", "octave"])
    if kind == "yank":
        sp = L.mix(splash(SR, 1.2, rng), (bubble(SR, 160, rng, tau=0.05, rise=0.5), 0.5), sr=SR)
    else:
        sp = L.mix(splash(SR, 0.7, rng), (splash(SR, 0.6, rng), 0.7, rng.uniform(0.08, 0.12)), sr=SR)
    mot = phrase(SR, 880.0 * rng.uniform(0.97, 1.03), "sine" if kind == "yank" else "glass", BITE_ALERTS[alert], rng, decay=0.1)
    return L.mix((L.norm_peak(sp), 0.9), (L.norm_peak(mot), 0.55, 0.08), sr=SR), {"kind": kind, "alert": alert}


CATCH_PATTERNS = [
    [(0.0, 0, 0.3, 0.8), (0.13, 4, 0.3, 0.85), (0.26, 7, 0.3, 0.9), (0.4, 12, 0.8, 1.0)],
    [(0.0, -5, 0.3, 0.8), (0.12, 0, 0.3, 0.85), (0.24, 4, 0.3, 0.9), (0.36, 7, 0.9, 1.0)],
    [(0.0, 0, 0.2, 0.7), (0.08, 2, 0.2, 0.75), (0.16, 4, 0.2, 0.8), (0.24, 7, 0.2, 0.85), (0.34, 12, 0.8, 1.0)],
    [(0.0, 0, 0.3, 0.85), (0.16, 7, 0.3, 0.9), (0.32, 12, 0.3, 0.9), (0.42, 16, 0.12, 0.6), (0.48, 19, 0.7, 0.9)],
    [(0.0, 0, 0.6, 0.7), (0.0, 4, 0.6, 0.6), (0.0, 7, 0.6, 0.6), (0.3, 12, 0.7, 0.9), (0.42, 16, 0.6, 0.7)],
]


def catch(rng, i):
    """Catch fanfare: arpeggio pattern x timbre, with a sparkle tail."""
    pat, timbre, base = L.cycle(i, CATCH_PATTERNS, ["marimba", "glass", "kalimba"], [523.25, 587.33, 493.88, 554.37, 523.25])
    y = phrase(HI, base, timbre, pat, rng, decay={"marimba": 0.3, "glass": 0.45, "kalimba": 0.6}[timbre])
    glint = lambda r: L.modal(HI, r.uniform(3500, 7500), "glass", rng=r, dur=0.08, tau=0.03)
    sp = L.scatter(HI, 0.5, rng, glint, count=int(rng.integers(5, 9)), gain=(0.05, 0.2), env=[0.3, 1, 0.6, 0.2])
    return L.mix(y, (sp, 1.0, pat[-1][0] * 0.8), sr=HI), {"pattern": CATCH_PATTERNS.index(pat), "timbre": timbre}


def card(rng, i):
    """Catch card: paper flick / slide / flip / snap, each with its own small chime."""
    kind = ["flick", "slide", "flip", "snap"][i % 4]
    if kind == "flick":
        paper = crack(SR, rng, hp=2500, n_imp=4, spread=0.006, tail=0.04)
        ch = phrase(SR, 784.0, "sine", [(0.0, 0, 0.2, 0.8), (0.07, 7, 0.3, 1.0)], rng, decay=0.1)
        y = L.mix(L.norm_peak(paper), (ch, 0.35, 0.03), sr=SR)
    elif kind == "slide":
        paper = whoosh(SR, 0.16, 2500, 5000, rng, peak=0.4, q=0.7, width=0.25, color="white")
        y = L.mix(L.norm_peak(paper), (note(SR, 1175.0, 0.35, "glass", rng, 0.15), 0.3, 0.1), sr=SR)
    elif kind == "flip":
        a = whoosh(SR, 0.07, 1800, 4000, rng, peak=0.4, q=0.9, width=0.25)
        b = whoosh(SR, 0.08, 2200, 4800, rng, peak=0.4, q=0.9, width=0.25)
        tw = L.scatter(SR, 0.2, rng, lambda r: L.modal(SR, r.uniform(2500, 5000), "glass", rng=r, dur=0.06, tau=0.025), count=3, gain=(0.15, 0.3))
        y = L.mix(L.norm_peak(a), (L.norm_peak(b), 0.8, 0.07), (tw, 1.0, 0.13), sr=SR)
    else:
        snap = L.mix(thump(SR, 300, 200, 0.008, rng, noise_hi=3000, noise_gain=1.0), (crack(SR, rng, hp=3000, n_imp=3), 0.6), sr=SR)
        ch = phrase(SR, 660.0, "marimba", [(0.0, 0, 0.25, 0.9), (0.09, 12, 0.3, 0.8)], rng, decay=0.12)
        y = L.mix(L.norm_peak(snap), (ch, 0.35, 0.04), sr=SR)
    return y, {"kind": kind}


THRASH_GAPS = [(0.12, 0.12, 0.12), (0.2, 0.1, 0.06), (0.07, 0.11, 0.18), (0.16, 0.05, 0.14)]


def thrash(rng, i):
    """Fish fight splash: hits x size x spacing (small flicks to big thrashes)."""
    hits, size, gaps = L.cycle(i, [3, 2, 4, 1], [0.7, 1.0, 1.4, 0.85, 1.2], THRASH_GAPS)
    out = np.zeros(L.secs(0.9, SR))
    at = 0.0
    for h in range(hits):
        s = size * rng.uniform(0.85, 1.15)
        L.place(out, splash(SR, s, rng), at, SR, gain=rng.uniform(0.6, 1.0) if h else 1.0)
        at += gaps[h % 3] * rng.uniform(0.9, 1.1)
    if hits == 1:    # single big slap: a tail slap transient on top
        out = L.mix(out, (thump(SR, 180 / size, 90 / size, 0.02, rng, noise_hi=3000, noise_gain=1.2), 0.5), sr=SR)
    return L.reverb(out, SR, room=rng.uniform(0.05, 0.2), wet=0.1, rng=rng), {"hits": hits, "size": size}


def ripple(rng, i):
    """Idle bobber ripple: water lap / plips / lap + plips, two variants each."""
    kind, var = L.cycle(i, ["lap", "plip", "lap_plip"], [0, 1])
    if kind == "lap":
        d = 0.32 if var == 0 else 0.5
        n = L.secs(d, SR)
        env = np.hanning(n) if var == 0 else np.interp(np.linspace(0, 1, n), [0, 0.2, 0.45, 0.6, 1], [0, 1, 0.3, 0.8, 0])
        y = L.svf(L.pink(n, rng), SR, np.linspace(900, 450, n), q=1.6, mode="bp") * env
    elif kind == "plip":
        if var == 0:     # one low bloop
            y = L.mix(bubble(SR, rng.uniform(520, 600), rng, tau=0.022, rise=0.9, dur=0.16), (burst(SR, 0.03, 400, 1500, 0.008, rng), 0.2), sr=SR)
        else:            # three tiny high plips
            y = L.mix(bubble(SR, rng.uniform(1300, 1500), rng, tau=0.007, rise=2.0),
                      (bubble(SR, rng.uniform(1800, 2100), rng, tau=0.006, rise=2.2), 0.7, rng.uniform(0.08, 0.11)),
                      (bubble(SR, rng.uniform(1100, 1250), rng, tau=0.008, rise=1.8), 0.5, rng.uniform(0.2, 0.24)), sr=SR)
    else:
        n = L.secs(0.38, SR)
        lap = L.svf(L.pink(n, rng), SR, np.linspace(700, 1200, n), q=1.3, mode="bp") * np.hanning(n)
        y = L.mix(L.norm_peak(lap) * 0.6, (droplets(SR, 0.3, 2 + var, rng, f=(1100, 2200), gain=(0.4, 0.8)), 1.0, 0.06), sr=SR)
    return y, {"kind": kind, "var": var}


def whiz(rng, i):
    """Line paying out while the bobber flies: spool clicks / line hiss / clicks + whistle."""
    tex, curve = L.cycle(i, ["spool", "hiss", "zip"], ["fast", "long"])
    dur = rng.uniform(0.42, 0.5) if curve == "fast" else rng.uniform(0.6, 0.7)
    n = L.secs(dur, SR)
    u = np.linspace(0, 1, n)
    env = np.interp(u, [0, 0.05, 0.5 if curve == "fast" else 0.75, 1], [0, 1, 0.7, 0])
    y = np.zeros(n)
    if tex in ("spool", "zip"):
        r0, r1 = (75, 22) if curve == "fast" else (60, 35)
        rate = np.interp(u, [0, 1], [r0, r1]) * rng.uniform(0.9, 1.1)
        ph = np.cumsum(rate) / SR
        times = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
        res = rng.uniform(2200, 3600)
        for k in times:
            L.place(y, ratchet_click(SR, res * rng.uniform(0.97, 1.03), "metal", rng) * 0.6, k / SR, SR, gain=rng.uniform(0.7, 1.0))
    if tex in ("hiss", "zip"):
        fc = np.interp(u, [0, 1], [3400, 1300] if curve == "fast" else [2600, 1800]) * rng.uniform(0.9, 1.1)
        h = L.svf(L.white(n, rng), SR, fc, q=4.0, mode="bp")
        y = y + L.norm_peak(h) * (0.8 if tex == "hiss" else 0.3)
    if tex == "zip":
        y = y + L.osc(SR, np.interp(u, [0, 1], [1600, 900]) * rng.uniform(0.95, 1.05)) * 0.12
    return y * env, {"tex": tex, "curve": curve}


def windup(rng, i):
    """Rod drawn back: back swish / creak + swish / bail click + swish / double wiggle."""
    kind = ["swish", "creak", "click", "double"][i % 4]
    if kind == "swish":
        y = whoosh(SR, 0.26, 1800, 600, rng, peak=0.55, q=1.0, width=0.22)
    elif kind == "creak":
        n = L.secs(0.18, SR)
        rate = np.interp(np.linspace(0, 1, n), [0, 1], [90, 140]) * rng.uniform(0.9, 1.1)
        pulses = (np.diff(np.floor(np.cumsum(rate) / SR), prepend=0) > 0).astype(float)
        cr = L.resonate(pulses, SR, [rng.uniform(700, 900), rng.uniform(1500, 1900)], [0.004, 0.003]) * np.hanning(n)
        y = L.mix(L.norm_peak(cr) * 0.8, (whoosh(SR, 0.22, 1400, 500, rng, peak=0.6), 0.6, 0.06), sr=SR)
    elif kind == "click":
        y = L.mix(ratchet_click(SR, rng.uniform(2500, 3200), "metal", rng),
                  (ratchet_click(SR, rng.uniform(1800, 2200), "metal", rng), 0.7, 0.03),
                  (L.norm_peak(whoosh(SR, 0.24, 1600, 700, rng, peak=0.5)), 0.7, 0.05), sr=SR)
    else:
        y = whoosh(SR, 0.32, 1300, 900, rng, peak=0.55, q=1.2, width=0.18, shape="double")
    return y, {"kind": kind}


def strike(rng, i):
    """Hook set / heave: rod whip + line twang + splash (five archetypes)."""
    kind = ["whip_twang", "whip_splash", "twang_splash", "creak_whip", "whip_double"][i % 5]
    whip = whoosh(SR, 0.13, 900, 3800, rng, peak=0.55, q=1.6, width=0.2, color="white")
    twang = L.ks_pluck(SR, rng.uniform(150, 290), 0.3, rng=rng, bright=0.75, damping=0.993)
    if kind == "whip_twang":
        y = L.mix(L.norm_peak(whip), (twang, 0.55, 0.06), sr=SR)
    elif kind == "whip_splash":
        y = L.mix(L.norm_peak(whip), (splash(SR, 0.8, rng), 0.6, 0.08), sr=SR)
    elif kind == "twang_splash":
        y = L.mix(twang, (splash(SR, 1.0, rng), 0.6, 0.02), (L.ks_pluck(SR, rng.uniform(320, 420), 0.15, rng=rng, bright=0.9), 0.3, 0.05), sr=SR)
    elif kind == "creak_whip":
        n = L.secs(0.1, SR)
        pulses = (np.diff(np.floor(np.cumsum(np.full(n, rng.uniform(110, 160))) / SR), prepend=0) > 0).astype(float)
        cr = L.resonate(pulses, SR, [rng.uniform(600, 800), rng.uniform(1300, 1600)], [0.004, 0.003]) * np.hanning(n)
        y = L.mix(L.norm_peak(cr) * 0.6, (L.norm_peak(whip), 1.0, 0.07), (twang, 0.35, 0.13), sr=SR)
    else:
        y = L.mix(L.norm_peak(whip) * 0.7, (L.norm_peak(whoosh(SR, 0.12, 1200, 4400, rng, peak=0.5, q=1.8, color="white")), 1.0, 0.09), sr=SR)
    return y, {"kind": kind}


def reel_back(rng, i):
    """Quick reel-in after a miss: ratchet spin pattern + bobber skips on the water."""
    spin, skips = L.cycle(i, ["accel", "steady", "stutter", "decel"], [2, 1, 3])
    dur = rng.uniform(0.4, 0.5)
    n = L.secs(dur, SR)
    u = np.linspace(0, 1, n)
    rate = {"accel": np.interp(u, [0, 1], [30, 70]), "steady": np.full(n, 55.0), "stutter": np.where((u * 4) % 1 < 0.7, 60.0, 8.0),
            "decel": np.interp(u, [0, 1], [70, 32])}[spin] * rng.uniform(0.9, 1.1)
    times = np.nonzero(np.diff(np.floor(np.cumsum(rate) / SR)) > 0)[0]
    y = np.zeros(n + L.secs(0.2, SR))
    res = rng.uniform(1900, 3000)
    for k in times:
        L.place(y, ratchet_click(SR, res, "brass" if spin in ("steady", "decel") else "metal", rng) * 0.5, k / SR, SR, gain=rng.uniform(0.7, 1.0))
    for s in range(skips):
        L.place(y, L.norm_peak(splash(SR, 0.45, rng, dur=0.08)), 0.05 + s * dur / (skips + 0.5), SR, gain=0.5 / (s + 1))
    return y, {"spin": spin, "skips": skips}


def fish_out(rng, i):
    """Fish pulled out of the water: five gestures (rush + drips / splash + flop / wriggle double
    splash / quick lift + long drip trail / splash + two flops)."""
    kind = ["rush", "flop", "wriggle", "lift", "flops"][i % 5]
    n = L.secs(0.3, SR)
    rush = L.svf(L.white(n, rng), SR, np.geomspace(500, 3500, n), q=0.9, mode="bp") * np.interp(np.linspace(0, 1, n), [0, 0.15, 1], [0, 1, 0])

    def slap():
        return L.norm_peak(L.mix(thump(SR, rng.uniform(190, 250), 140, 0.012, rng, noise_hi=4000, noise_gain=1.4),
                                 (crack(SR, rng, hp=1500, n_imp=3), 0.4), sr=SR))
    if kind == "rush":
        y = L.mix(L.norm_peak(rush) * 0.8, (splash(SR, 1.3, rng), 0.8, 0.05), (droplets(SR, 0.45, 9, rng, gain=(0.15, 0.45)), 0.6, 0.2), sr=SR)
    elif kind == "flop":
        y = L.mix(splash(SR, 1.0, rng), (slap(), 0.6, 0.28), (droplets(SR, 0.3, 4, rng), 0.4, 0.15), sr=SR)
    elif kind == "wriggle":
        y = L.mix(splash(SR, 0.8, rng), (splash(SR, 0.65, rng), 0.8, rng.uniform(0.12, 0.16)), (splash(SR, 0.5, rng), 0.5, 0.27), sr=SR)
    elif kind == "lift":
        y = L.mix(splash(SR, 0.6, rng, dur=0.1), (droplets(SR, 0.7, 12, rng, f=(1200, 3200), gain=(0.1, 0.5), env=[1, 0.8, 0.5, 0.3, 0.1]), 0.8, 0.05), sr=SR)
    else:
        y = L.mix(L.norm_peak(rush) * 0.5, (splash(SR, 1.1, rng), 0.8, 0.04), (slap(), 0.55, 0.24), (slap(), 0.4, 0.38), sr=SR)
    return y, {"kind": kind}


def rod_equip(rng, i):
    """Rod taken out: handle tap + reel clicks / bail open-close / spool rattle / slide out."""
    kind = ["tap_click", "bail", "rattle", "slide"][i % 4]
    tap = L.modal(SR, rng.uniform(520, 700), "wood", rng=rng, tau=0.03)
    if kind == "tap_click":
        y = L.mix(tap, (ratchet_click(SR, rng.uniform(2600, 3400), "metal", rng), 0.5, 0.05), sr=SR)
    elif kind == "bail":
        y = L.mix(ratchet_click(SR, rng.uniform(2000, 2400), "brass", rng), (ratchet_click(SR, rng.uniform(3000, 3600), "metal", rng), 0.9, 0.11),
                  (tap, 0.35, 0.16), sr=SR)
    elif kind == "rattle":
        y = np.zeros(L.secs(0.2, SR))
        for k in range(7):
            L.place(y, ratchet_click(SR, rng.uniform(2200, 2600), "plastic", rng), k * 0.017 + rng.uniform(0, 0.003), SR, gain=0.6 * (1 - k / 9))
        y = L.mix(y, (tap, 0.6, 0.15), sr=SR)
    else:
        sl = whoosh(SR, 0.2, 1200, 2600, rng, peak=0.5, q=0.8, width=0.3, color="white")
        y = L.mix(L.norm_peak(sl) * 0.6, (tap, 0.8, 0.16), sr=SR)
    return y, {"kind": kind}


def pocket(rng, i):
    """Item lands in the bag: body (cloth flump / leather tap / bloop / rustle / bead clack) x pip."""
    body, pip = L.cycle(i, ["cloth", "leather", "bloop", "rustle", "bead"], ["pip", "glint"])
    if body == "cloth":
        b = L.mix(thump(HI, 170, 120, 0.012, rng, noise_hi=1800, noise_gain=1.2), (cloth(HI, 0.05, rng, env=[1, 0.4, 0]), 0.4), sr=HI)
    elif body == "leather":
        b = L.modal(HI, rng.uniform(280, 340), "wood", rng=rng, tau=0.02, bright=0.7)
    elif body == "bloop":
        b = sweep_tone(HI, 0.09, 480, 900, 0.025, ((1, 1.0), (2, 0.1)))
    elif body == "rustle":
        b = cloth(HI, 0.06, rng, lo=1500, hi=7000, env=[0, 1, 0.3, 0])
    else:
        b = L.mix(stone_clack(HI, rng.uniform(2600, 3200), rng, 0.05), (stone_clack(HI, rng.uniform(3600, 4200), rng, 0.05), 0.6, 0.022), sr=HI)
    if pip == "pip":
        p = sweep_tone(HI, 0.08, 1900, 2050, 0.018, ((1, 1.0), (2, 0.15)), attack=0.001)
    else:
        p = L.modal(HI, rng.uniform(3000, 3400), "glass", rng=rng, dur=0.1, tau=0.03)
    return L.mix(L.norm_peak(b), (L.norm_peak(p), 0.55, rng.uniform(0.012, 0.03)), sr=HI), {"body": body, "pip": pip}


def fruit_detach(rng, i):
    """Fruit lets go: snap (single / double / creak + snap) x leaves (flutter after / shake before)."""
    snap, leaf = L.cycle(i, ["single", "double", "creak"], ["flutter", "shake"])
    if snap == "single":
        s = crack(SR, rng, hp=1200, n_imp=5, spread=0.005)
    elif snap == "double":
        s = L.mix(crack(SR, rng, hp=1500, n_imp=3, spread=0.003), (crack(SR, rng, hp=1000, n_imp=5, spread=0.005), 1.0, rng.uniform(0.018, 0.035)), sr=SR)
    else:
        n = L.secs(0.07, SR)
        pulses = (np.diff(np.floor(np.cumsum(np.interp(np.linspace(0, 1, n), [0, 1], [60, 160])) / SR), prepend=0) > 0).astype(float)
        cr = L.resonate(pulses, SR, [rng.uniform(900, 1200), rng.uniform(2100, 2600)], [0.004, 0.002]) * np.hanning(n)
        s = L.mix(L.norm_peak(cr) * 0.5, (crack(SR, rng, hp=1200, n_imp=5), 1.0, 0.065), sr=SR)
    stem = L.modal(SR, rng.uniform(600, 900), "wood", rng=rng, tau=0.015) * 0.3
    s = L.mix(L.norm_peak(s), (stem, 1.0), sr=SR)
    lv = rustle(rng, 2 * (i % 5) + (1 if leaf == "flutter" else 0))[0] * 0.5
    y = L.mix(s, (L.norm_peak(lv) * 0.45, 1.0, 0.02), sr=SR) if leaf == "flutter" else L.mix((L.norm_peak(lv) * 0.4, 1.0), (s, 1.0, 0.1), sr=SR)
    return y, {"snap": snap, "leaf": leaf}


def bounce(rng, i):
    """Fruit bounce (after the first landing): object (firm apple tock / hollow coconut knock /
    light pine-cone clicks / soft squish) x surface (grass / dirt / path); some takes hop twice."""
    obj, surface, f0 = L.cycle(i, ["firm", "hollow", "cone", "soft"], ["grass", "dirt", "path"],
                               [150.0, 175.0, 205.0, 240.0, 280.0, 325.0, 380.0])

    def hit(f, g):
        if obj == "firm":
            b = L.mix(thump(SR, f, f * 0.7, 0.018, rng, noise_hi=1200, noise_gain=0.5) * 0.7,
                      (L.modal(SR, f * 3.1, "wood", rng=rng, tau=0.012), 0.7), sr=SR)
        elif obj == "hollow":
            b = L.mix(thump(SR, f * 0.8, f * 0.7, 0.012, rng, noise_hi=900, noise_gain=0.3) * 0.5,
                      (L.modal(SR, f * 2.2, "wood", rng=rng, tau=0.06), 1.0), sr=SR)
        elif obj == "cone":
            b = L.scatter(SR, 0.035, rng, lambda r: L.modal(SR, r.uniform(f * 5, f * 9), "wood", rng=r, tau=0.008, dur=0.04),
                          count=5, gain=(0.4, 1.0))
        else:
            n = L.secs(0.08, SR)
            sq = L.svf(L.pink(n, rng), SR, np.linspace(f * 5, f * 2, n), q=2.5, mode="bp") * np.interp(np.linspace(0, 1, n), [0, 0.1, 1], [0, 1, 0])
            b = L.mix(L.norm_peak(sq), (thump(SR, f * 0.6, f * 0.45, 0.015, rng, noise_hi=500, noise_gain=0.2), 0.35), sr=SR)
        if surface == "grass":
            b = L.lp(L.mix(L.norm_peak(b), (cloth(SR, 0.08, rng, lo=1500, hi=6000, env=[1, 0.4, 0]), 0.5), sr=SR), SR, 3200)
        elif surface == "dirt":
            b = L.mix(L.norm_peak(b), (grains(SR, 0.07, 8, rng, 1000, 5000, gain=(0.1, 0.5)), 0.8, 0.004), sr=SR)
        else:
            b = L.mix(L.norm_peak(b), (stone_clack(SR, f * rng.uniform(5, 7), rng, 0.06), 0.6), sr=SR)
        return L.norm_peak(b) * g

    y = hit(f0 * rng.uniform(0.97, 1.03), 1.0)
    hops = 2 if i % 3 == 1 else 1
    if hops == 2:
        y = L.mix(y, (hit(f0 * 1.1, 0.4), 1.0, rng.uniform(0.09, 0.14)), sr=SR)
    return y, {"obj": obj, "surface": surface, "f0": f0, "hops": hops}


def fruit_water(rng, i):
    """Fruit into water: plunk / splash / plunk + glugs / flat slap."""
    kind = ["plunk", "splash", "glug", "slap"][i % 4]
    if kind == "plunk":
        y = L.mix(bubble(SR, rng.uniform(280, 360), rng, tau=0.05, rise=1.0, dur=0.3), (splash(SR, 0.6, rng), 0.4), sr=SR)
    elif kind == "splash":
        y = L.mix(splash(SR, 1.1, rng), (droplets(SR, 0.3, 6, rng), 0.5, 0.1), sr=SR)
    elif kind == "glug":
        y = L.mix(bubble(SR, rng.uniform(330, 400), rng, tau=0.04, rise=0.9, dur=0.25),
                  (bubble(SR, rng.uniform(520, 600), rng, tau=0.02, rise=1.5), 0.6, 0.14),
                  (bubble(SR, rng.uniform(700, 820), rng, tau=0.015, rise=1.8), 0.45, 0.24), sr=SR)
    else:
        slap = thump(SR, 260, 140, 0.01, rng, noise_hi=5000, noise_gain=1.6)
        y = L.mix(L.norm_peak(slap), (droplets(SR, 0.25, 8, rng, f=(1200, 3500)), 0.5, 0.02), sr=SR)
    return y, {"kind": kind}


def grab(rng, i):
    """Hand closes on an item: palm pat / grass brush + pat / skin squeak + pat, single or double."""
    kind, double = L.cycle(i, ["palm", "brush", "squeak"], [False, True])
    pat = thump(SR, rng.uniform(150, 200), 110, 0.012, rng, noise_hi=2500, noise_gain=1.0)
    if kind == "palm":
        y = L.norm_peak(pat)
    elif kind == "brush":
        y = L.mix(cloth(SR, 0.09, rng, lo=1500, hi=6000, env=[0, 1, 0.4, 0]) * 0.5, (L.norm_peak(pat), 1.0, 0.05), sr=SR)
    else:
        n = L.secs(0.06, SR)
        sq = L.osc(SR, np.interp(np.linspace(0, 1, n), [0, 1], [rng.uniform(900, 1100), rng.uniform(1300, 1500)]), ((1, 1.0), (2, 0.3), (3, 0.15))) * np.hanning(n)
        y = L.mix(L.norm_peak(pat), (sq, 0.3, 0.015), sr=SR)
    if double:
        y = L.mix(y, (L.norm_peak(thump(SR, 230, 150, 0.008, rng, noise_hi=3000)), 0.45, rng.uniform(0.07, 0.1)), sr=SR)
    return y, {"kind": kind, "double": double}


KNOCK_PATTERNS = [(0.0, 0.17), (0.0, 0.14, 0.28), (0.0, 0.1, 0.33), (0.0, 0.22), (0.0, 0.19, 0.33, 0.43)]


def knock(rng, i):
    """Knuckles on a wooden door: rhythm x door (thick oak / panel / thin plank)."""
    times, f0 = L.cycle(i, KNOCK_PATTERNS, [210.0, 280.0, 360.0])
    out = np.zeros(L.secs(times[-1] + 0.35, SR))
    for k, t in enumerate(times):
        hard = rng.uniform(0.75, 1.0) if k < len(times) - 1 else rng.uniform(0.85, 1.05)
        L.place(out, wood_knock(SR, f0 * rng.uniform(0.96, 1.04), rng, hard), t + rng.uniform(-0.01, 0.01), SR, gain=hard)
    return out, {"pattern": len(times), "f0": f0}


def bell(rng, i):
    """Lighthouse bell: single long strike / double strike / strike + clapper buzz."""
    kind = ["single", "double", "clapper"][i % 3]
    f0 = [207.65, 233.08, 185.0][i % 3] * rng.uniform(0.995, 1.005)
    dur = 3.0
    if kind == "single":
        y = L.modal(SR, f0, "bell", dur=dur, rng=rng, tau=1.3)
    elif kind == "double":
        a = L.modal(SR, f0, "bell", dur=dur, rng=rng, tau=1.1)
        y = L.mix(a, (L.modal(SR, f0, "bell", dur=dur - 0.8, rng=rng, tau=1.0), 0.55, 0.8), sr=SR)
    else:
        b = L.fm_bell(SR, f0, dur, ratio=1.4, index=3.0, t60=2.6, rng=rng)
        buzz = L.modal(SR, f0 * 6.1, "metal", dur=0.25, rng=rng, tau=0.05) * 0.2
        y = L.mix(b, (buzz, 1.0, 0.005), (L.modal(SR, f0 * 1.5, "bell", dur=2.0, rng=rng, tau=0.7), 0.3, 0.02), sr=SR)
    y = L.reverb(y, SR, room=0.6, wet=0.25, rng=rng)
    return y[: L.secs(3.2, SR)] * np.interp(np.arange(L.secs(3.2, SR)) / SR, [0, 2.4, 3.2], [1, 1, 0])[: y[: L.secs(3.2, SR)].size], {"kind": kind}


# =========================================================================== core families
REWARD_PATTERNS = [
    [(0.0, 0, 0.3, 0.85), (0.15, 4, 0.3, 0.9), (0.3, 7, 0.55, 1.0)],
    [(0.0, 0, 0.3, 0.8), (0.12, 7, 0.3, 0.9), (0.24, 12, 0.6, 1.0)],
    [(0.0, -1, 0.06, 0.4), (0.03, 0, 0.3, 0.85), (0.16, 4, 0.12, 0.7), (0.22, 9, 0.55, 1.0)],
]


def reward(rng, i):
    """Small reward jingle: pattern x timbre (around the old 780 Hz)."""
    pat, timbre = L.cycle(i, REWARD_PATTERNS, ["glass", "fm"])
    y = phrase(SR, 780.0 * rng.uniform(0.98, 1.02) * (0.5 if timbre == "fm" and i % 2 else 1.0), timbre, pat, rng, decay=0.28)
    if i >= 3:
        glint = lambda r: L.modal(SR, r.uniform(3000, 6000), "glass", rng=r, dur=0.06, tau=0.02)
        y = L.mix(y, (L.scatter(SR, 0.3, rng, glint, count=4, gain=(0.05, 0.15)), 1.0, 0.25), sr=SR)
    return y, {"pattern": REWARD_PATTERNS.index(pat), "timbre": timbre}


def gather(rng, i):
    """Gather blip: pluck / wood / bubble x single / two notes up."""
    timbre, two = L.cycle(i, ["pluck", "marimba", "bubble"], [False, True])
    f = 410.0 * rng.uniform(0.97, 1.03) * (2.0 if timbre == "marimba" else 1.0)
    if timbre == "bubble":
        first = sweep_tone(SR, 0.12, f * 1.2, f * 2.2, 0.03, ((1, 1.0), (2, 0.1)))
        second = sweep_tone(SR, 0.12, f * 1.45, f * 2.6, 0.03, ((1, 1.0), (2, 0.1)))
    else:
        first = note(SR, f, 0.2, timbre, rng, 0.993 if timbre == "pluck" else 0.08)
        second = note(SR, f * L.semitones(3), 0.25, timbre, rng, 0.993 if timbre == "pluck" else 0.1)
    y = L.mix(L.norm_peak(first), (L.norm_peak(second), 0.85, rng.uniform(0.07, 0.09)), sr=SR) if two else L.norm_peak(first)
    return y, {"timbre": timbre, "two": two}


def craft(rng, i):
    """Something got made: tool taps (1 / 2 / 3 / rasp + tap) x completion chime."""
    taps, chime = L.cycle(i, [1, 2, 3, 0], ["up2", "up3", "sparkle"])
    mat = ["wood", "metal"][int(rng.integers(0, 2))]
    out = np.zeros(L.secs(0.9, SR))
    at = 0.0
    if taps == 0:
        n = L.secs(0.16, SR)
        rasp = L.bp(L.white(n, rng), SR, 1500, 5000) * (0.5 + 0.5 * np.sin(TAU * 38 * T(n, SR))) ** 2 * np.hanning(n)
        L.place(out, L.norm_peak(rasp) * 0.6, 0.0, SR)
        at = 0.18
        taps = 1
    for k in range(taps):
        f = rng.uniform(400, 700) if mat == "wood" else rng.uniform(900, 1300)
        L.place(out, L.modal(SR, f, mat, rng=rng, tau=0.04 if mat == "wood" else 0.15, dur=0.2), at, SR, gain=rng.uniform(0.6, 0.85))
        at += rng.uniform(0.09, 0.13)
    base = 660.0 * rng.uniform(0.98, 1.02)
    if chime == "up2":
        c = phrase(SR, base, "glass", [(0.0, 0, 0.25, 0.8), (0.1, 7, 0.4, 1.0)], rng, decay=0.25)
    elif chime == "up3":
        c = phrase(SR, base, "sine", [(0.0, 0, 0.15, 0.8), (0.09, 4, 0.15, 0.85), (0.18, 7, 0.35, 1.0)], rng, decay=0.15)
    else:
        glint = lambda r: L.modal(SR, r.uniform(2000, 5000), "glass", rng=r, dur=0.1, tau=0.04)
        c = L.mix(note(SR, base * 2, 0.5, "fm", rng, 0.3) * 0.7, (L.scatter(SR, 0.3, rng, glint, count=6, gain=(0.1, 0.3)), 1.0, 0.03), sr=SR)
    L.place(out, L.norm_peak(c) * 0.8, at + 0.02, SR)
    return out, {"taps": taps, "chime": chime, "mat": mat}


def eat(rng, i):
    """Eating: crunchy bite / soft chews / soup slurp, short or long."""
    kind, count = L.cycle(i, ["crunch", "chew", "slurp"], [1, 2])
    out = np.zeros(L.secs(0.7, SR))
    if kind == "crunch":
        at = 0.0
        for k in range(count + 1):
            c = L.mix(grains(SR, 0.07, 25, rng, 1500, 7000, g_dur=(0.001, 0.004), env=[1, 0.6, 0.2]),
                      (thump(SR, 160, 100, 0.012, rng, noise_hi=1500), 0.5), sr=SR)
            L.place(out, L.norm_peak(c), at, SR, gain=1.0 if k == 0 else 0.55)
            at += rng.uniform(0.14, 0.19)
    elif kind == "chew":
        at = 0.0
        for k in range(count + 1):
            n = L.secs(rng.uniform(0.07, 0.1), SR)
            m = L.lp(L.pink(n, rng), SR, 900) * np.hanning(n) + L.pad_to(grains(SR, n / SR, 4, rng, 600, 2500, gain=(0.1, 0.3)), n)
            L.place(out, L.norm_peak(m), at, SR, gain=rng.uniform(0.7, 1.0))
            at += rng.uniform(0.15, 0.2)
    else:
        n = L.secs(0.28 if count == 1 else 0.4, SR)
        fc = np.interp(np.linspace(0, 1, n), [0, 0.6, 1], [700, 2200, 1500])
        sl = L.svf(L.white(n, rng), SR, fc, q=2.5, mode="bp") * np.interp(np.linspace(0, 1, n), [0, 0.2, 0.8, 1], [0, 1, 0.8, 0])
        L.place(out, L.norm_peak(sl), 0.0, SR)
        L.place(out, bubble(SR, rng.uniform(250, 320), rng, tau=0.04, rise=0.8), n / SR + 0.03, SR, gain=0.7)
    return out, {"kind": kind, "count": count}


def bandage(rng, i):
    """Bandage: cloth rip, wraps and a pat (four orders)."""
    kind = ["rip_wraps", "wraps_pat", "rip_tie", "wrap_pats"][i % 4]

    def rip(d):
        n = L.secs(d, SR)
        return L.norm_peak(L.pad_to(grains(SR, d, 400 * d, rng, 1500, 8000, g_dur=(0.0008, 0.003)), n)) * np.interp(np.linspace(0, 1, n), [0, 0.2, 1], [0.3, 1, 0.2])

    def wrap(d):
        return L.norm_peak(cloth(SR, d, rng, lo=700, hi=4000, env=[0, 1, 0.8, 0]))

    def pat():
        return L.norm_peak(thump(SR, 180, 120, 0.012, rng, noise_hi=1500, noise_gain=1.0))
    if kind == "rip_wraps":
        y = L.mix(rip(0.2), (wrap(0.16), 0.6, 0.25), (wrap(0.14), 0.55, 0.43), sr=SR)
    elif kind == "wraps_pat":
        y = L.mix(wrap(0.13), (wrap(0.13), 0.8, 0.15), (wrap(0.15), 0.7, 0.3), (pat(), 0.6, 0.48), sr=SR)
    elif kind == "rip_tie":
        y = L.mix(rip(0.12), (wrap(0.18), 0.6, 0.16), (crack(SR, rng, hp=900, n_imp=4, spread=0.01), 0.4, 0.38), sr=SR)
    else:
        y = L.mix(wrap(0.2), (wrap(0.16), 0.7, 0.22), (pat(), 0.6, 0.42), (pat(), 0.45, 0.53), sr=SR)
    return y, {"kind": kind}


def fire(rng, i):
    """Fire catches: whoomph / match strike / quick flare / double whoosh, then crackles."""
    kind = ["whoomph", "match", "flare", "double"][i % 4]
    n = L.secs(0.5, SR)
    u = np.linspace(0, 1, n)
    if kind == "whoomph":
        y = L.svf(L.pink(n, rng), SR, np.interp(u, [0, 0.3, 1], [200, 900, 400]), q=0.8, mode="lp") * np.interp(u, [0, 0.25, 1], [0, 1, 0])
    elif kind == "match":
        sc = L.bp(L.white(L.secs(0.08, SR), rng), SR, 2000, 7000) * np.hanning(L.secs(0.08, SR))
        hiss = L.bp(L.white(n, rng), SR, 1500, 6000) * np.interp(u, [0, 0.1, 1], [0, 1, 0]) * 0.5
        y = L.mix(L.norm_peak(sc), (hiss, 1.0, 0.07), sr=SR)
    elif kind == "flare":
        y = L.svf(L.pink(n, rng), SR, np.interp(u, [0, 0.15, 1], [400, 2500, 600]), q=0.9, mode="bp") * np.interp(u, [0, 0.08, 1], [0, 1, 0]) ** 1.5
    else:
        y = whoosh(SR, 0.5, 300, 1200, rng, peak=0.5, q=0.7, width=0.18, shape="double")
    pops = L.scatter(SR, 0.5, rng, lambda r: crack(SR, r, hp=r.uniform(800, 2500), n_imp=int(r.integers(1, 4)), spread=0.002),
                     count=int(rng.integers(4, 9)), gain=(0.2, 0.7), env=[0.2, 1, 0.8, 0.5])
    return L.mix(L.norm_peak(y), (L.norm_peak(pops), 0.6, 0.08), sr=SR), {"kind": kind}


def error(rng, i):
    """Soft deny: bonk (two notes down) / muted thunk / nuh-uh pulses / falling glide."""
    kind, f = L.cycle(i, ["bonk", "thunk", "nuh", "glide"], [185.0, 155.0, 220.0])
    f *= rng.uniform(0.98, 1.02)
    if kind == "bonk":
        y = L.mix(note(SR, f * 2, 0.12, "soft", rng, 0.05), (note(SR, f * 2 * L.semitones(-1), 0.16, "soft", rng, 0.07), 1.0, 0.1), sr=SR)
    elif kind == "thunk":
        y = L.mix(L.modal(SR, f * 1.6, "wood", rng=rng, tau=0.04), (thump(SR, f, f * 0.7, 0.03, rng, noise_hi=800, noise_gain=0.3), 0.7), sr=SR)
    elif kind == "nuh":
        p = lambda ff: L.norm_peak(L.lp(sweep_tone(SR, 0.07, ff, ff * 0.97, 0.03, [(h, 1.0 / h) for h in range(1, 8)], attack=0.004), SR, 1800))
        y = L.mix(p(f * 1.5), (p(f * 1.5 * L.semitones(-2)), 0.9, 0.11), sr=SR)
    else:
        y = sweep_tone(SR, 0.2, f * 2.2, f * 1.3, 0.08, ((1, 1.0), (2, 0.15)), attack=0.004)
    return y, {"kind": kind, "f": round(f)}


def sell(rng, i):
    """Sold: register ding + coins (ding first / coins first / two dings), drawer slide in some."""
    order, n_coin = L.cycle(i, ["ding_coins", "coins_ding", "double_ding"], [3, 5, 2, 4, 6])
    ding = L.modal(HI, rng.uniform(1800, 2300), "bell", dur=0.6, rng=rng, tau=0.5)
    coins = np.zeros(L.secs(0.5, HI))
    at = 0.0
    for k in range(n_coin):
        L.place(coins, coin(HI, rng.uniform(3500, 6000), rng, 0.25), at, HI, gain=rng.uniform(0.3, 0.7))
        at += rng.uniform(0.025, 0.07)
    if order == "ding_coins":
        y = L.mix(ding, (L.norm_peak(coins), 0.6, 0.12), sr=HI)
    elif order == "coins_ding":
        y = L.mix(L.norm_peak(coins) * 0.6, (ding, 1.0, at + 0.03), sr=HI)
    else:
        y = L.mix(ding, (L.modal(HI, rng.uniform(2400, 2800), "bell", dur=0.5, rng=rng, tau=0.4), 0.8, 0.13), (L.norm_peak(coins), 0.4, 0.25), sr=HI)
    if i in (1, 3):
        y = L.mix(L.norm_peak(whoosh(HI, 0.15, 600, 1500, rng, peak=0.5, q=0.8, width=0.3)) * 0.3, (y, 1.0, 0.08), sr=HI)
    return y, {"order": order, "coins": n_coin}


def buy(rng, i):
    """Paid: coins set down on the counter (2-5 clinks with a little roll) + pouch."""
    n_coin, roll, pouch = L.cycle(i, [2, 4, 3, 5, 3], [False, True], ["tie", "pat", "none"])
    y = np.zeros(L.secs(0.7, HI))
    at = 0.0
    for k in range(n_coin):
        L.place(y, coin(HI, rng.uniform(2800, 4800), rng, 0.3), at, HI, gain=rng.uniform(0.5, 1.0))
        at += rng.uniform(0.04, 0.09)
    if roll:
        n = L.secs(0.25, HI)
        rate = np.interp(np.linspace(0, 1, n), [0, 1], [40, 12])
        hits = np.nonzero(np.diff(np.floor(np.cumsum(rate) / HI)) > 0)[0]
        for k in hits:
            L.place(y, coin(HI, rng.uniform(5000, 6500), rng, 0.08), at + k / HI, HI, gain=0.18)
    if pouch == "tie":
        y = L.mix(y, (cloth(HI, 0.1, rng, env=[0, 1, 0]), 0.25, at + 0.12), sr=HI)
    elif pouch == "pat":
        y = L.mix(y, (thump(HI, 170, 120, 0.012, rng, noise_hi=1500), 0.3, at + 0.1), sr=HI)
    return y, {"coins": n_coin, "roll": roll, "pouch": pouch}


ERRAND_PATTERNS = [[(0.0, 0, 0.3, 0.9), (0.14, 4, 0.5, 1.0)], [(0.0, 0, 0.3, 0.85), (0.12, 7, 0.3, 0.9), (0.24, 4, 0.5, 1.0)],
                   [(0.0, 0, 0.3, 0.8), (0.1, 5, 0.3, 0.9), (0.2, 9, 0.5, 1.0)], [(0.0, 4, 0.3, 0.9), (0.16, 0, 0.55, 1.0)],
                   [(0.0, 0, 0.2, 0.8), (0.08, 4, 0.2, 0.85), (0.16, 7, 0.2, 0.9), (0.26, 12, 0.5, 1.0)]]


def errand(rng, i):
    """Errand done / thanks: warm motif (five shapes) on kalimba / marimba / soft sine."""
    pat, timbre = L.cycle(i, ERRAND_PATTERNS, ["kalimba", "marimba", "soft"])
    y = phrase(SR, 587.33 * rng.uniform(0.98, 1.02), timbre, pat, rng, decay={"kalimba": 0.45, "marimba": 0.25, "soft": 0.2}[timbre])
    return y, {"pattern": ERRAND_PATTERNS.index(pat), "timbre": timbre}


def newday(rng, i):
    """A new day: rising pentatonic morning motif with a chirp (three shapes)."""
    pats = [[(0.0, 0, 0.3, 0.7), (0.12, 2, 0.3, 0.75), (0.24, 4, 0.3, 0.8), (0.36, 7, 0.3, 0.85), (0.5, 9, 0.7, 1.0)],
            [(0.0, 0, 0.5, 0.8), (0.2, 7, 0.5, 0.85), (0.4, 12, 0.8, 1.0)],
            [(0.0, 4, 0.3, 0.7), (0.1, 7, 0.3, 0.75), (0.2, 9, 0.3, 0.8), (0.3, 12, 0.3, 0.85), (0.45, 16, 0.8, 0.9)]]
    timbre = ["glass", "kalimba", "marimba"][i % 3]
    y = phrase(SR, 523.25 * rng.uniform(0.98, 1.02), timbre, pats[i % 3], rng, decay=0.4)
    n = L.secs(0.09, SR)
    chirp = L.osc(SR, np.interp(np.linspace(0, 1, n), [0, 0.6, 1], [3200, 4200, 3600]) * rng.uniform(0.9, 1.1)) * np.hanning(n)
    return L.mix(y, (chirp, 0.15, pats[i % 3][-1][0] + 0.25), (chirp, 0.1, pats[i % 3][-1][0] + 0.38), sr=SR), {"timbre": timbre}


def win(rng, i):
    """Run won: horn fanfare (three shapes) with a bell on top."""
    base = 392.0 * rng.uniform(0.99, 1.01)
    shapes = [[(0.0, 0, 0.18), (0.18, 0, 0.12), (0.3, 4, 0.18), (0.48, 7, 0.75)],
              [(0.0, -5, 0.22), (0.22, 0, 0.22), (0.44, 4, 0.22), (0.66, 12, 0.8)],
              [(0.0, 7, 0.15), (0.15, 4, 0.15), (0.3, 7, 0.15), (0.45, 12, 0.85)]]
    out = np.zeros(L.secs(1.6, SR))
    for t, st, d in shapes[i % 3]:
        f = base * L.semitones(st)
        L.place(out, synth_brass(SR, f, d + 0.1, rng), t, SR, gain=0.8)
        L.place(out, synth_brass(SR, f * 1.5 if st < 7 else f * 0.75, d + 0.1, rng), t, SR, gain=0.35)
    last = shapes[i % 3][-1]
    out = L.mix(out, (note(SR, base * L.semitones(last[1]) * 2, 0.9, "bell" if i != 1 else "glass", rng, 0.5), 0.35, last[0]), sr=SR)
    return L.reverb(out, SR, room=0.35, wet=0.15, rng=rng), {"shape": i % 3}


def lose(rng, i):
    """Run lost: a soft falling minor phrase (three shapes)."""
    base = 392.0 * rng.uniform(0.99, 1.01)
    pats = [[(0.0, 7, 0.35, 0.8), (0.25, 5, 0.35, 0.8), (0.5, 3, 0.35, 0.8), (0.75, 0, 0.8, 0.9)],
            [(0.0, 3, 0.5, 0.8), (0.35, 2, 0.5, 0.75), (0.7, -2, 0.9, 0.85)],
            [(0.0, 0, 0.3, 0.8), (0.2, -1, 0.3, 0.7), (0.45, -5, 0.4, 0.75), (0.7, -9, 0.9, 0.85)]]
    timbre = ["soft", "marimba", "kalimba"][i % 3]
    y = phrase(SR, base, timbre, pats[i % 3], rng, decay={"soft": 0.35, "marimba": 0.3, "kalimba": 0.5}[timbre])
    return L.reverb(y, SR, room=0.4, wet=0.18, rng=rng), {"timbre": timbre}


# =========================================================================== registry
# (dir, event, takes, fn, sr, reference). reference = (module, synth kind, delta dB): the family's
# effective level = that runtime synth's (st-rms + its player volume) + delta.
FAMILIES = [
    ("life", "tick", 16, tick, HI, ("life", "tick", 0.0), {"keep": 0.006, "fade_out": 0.012}),
    ("life", "nibble", 10, nibble, SR, ("life", "nibble", 0.0)),
    ("life", "collect", 12, collect, HI, ("life", "collect", 0.0)),
    ("life", "pop", 8, pop, SR, ("life", "pop", 0.0)),
    ("life", "hoe", 8, hoe, SR, ("life", "hoe", 0.0)),
    ("life", "seed", 8, seed, SR, ("life", "seed", 0.0)),
    ("life", "water", 6, water, SR, ("life", "water", 0.0)),
    ("life", "rustle", 8, rustle, SR, ("life", "rustle", 0.0)),
    ("life", "rock", 6, rock, SR, ("life", "rock", 0.0)),
    ("life", "shell", 6, shell, HI, ("life", "shell", 0.0)),
    ("life", "escape", 6, escape, SR, ("life", "escape", 0.0)),
    ("life", "cast", 6, cast, SR, ("life", "cast", 0.0)),
    ("life", "plop", 6, plop, SR, ("life", "plop", 0.0)),
    ("life", "bite", 6, bite, SR, ("life", "bite", 0.0)),
    ("life", "catch", 5, catch, HI, ("life", "catch", 0.0)),
    ("life", "card", 4, card, SR, ("life", "card", 0.0)),
    # new kinds: matched to a sibling
    ("life", "thrash", 10, thrash, SR, ("life", "plop", 0.0)),
    ("life", "ripple", 6, ripple, SR, ("life", "plop", 0.0)),
    ("life", "whiz", 6, whiz, SR, ("life", "cast", -3.0)),
    ("life", "windup", 4, windup, SR, ("life", "cast", -3.0)),
    ("life", "strike", 5, strike, SR, ("life", "cast", 0.0)),
    ("life", "reel_back", 4, reel_back, SR, ("life", "escape", -3.0)),
    ("life", "fish_out", 5, fish_out, SR, ("life", "plop", 0.0)),
    ("life", "rod_equip", 4, rod_equip, SR, ("life", "rock", 0.0)),
    ("life", "pocket", 10, pocket, HI, ("life", "collect", 0.0)),
    ("life", "fruit_detach", 6, fruit_detach, SR, ("life", "rustle", 0.0)),
    ("life", "bounce", 8, bounce, SR, ("life", "rock", 0.0)),
    ("life", "fruit_water", 4, fruit_water, SR, ("life", "plop", 0.0)),
    ("life", "grab", 6, grab, SR, ("life", "rustle", 0.0)),
    ("life", "knock", 5, knock, SR, ("life", "rock", 0.0)),
    ("life", "bell", 3, bell, SR, ("core", "reward", 0.0)),
    ("core", "reward", 6, reward, SR, ("core", "reward", 0.0)),
    ("core", "gather", 6, gather, SR, ("core", "gather", 0.0)),
    ("core", "craft", 8, craft, SR, ("core", "craft", 0.0)),
    ("core", "eat", 6, eat, SR, ("core", "eat", 0.0)),
    ("core", "bandage", 4, bandage, SR, ("core", "eat", 0.0)),
    ("core", "fire", 4, fire, SR, ("core", "fire", 0.0)),
    ("core", "error", 8, error, SR, ("core", "error", 0.0)),
    ("core", "sell", 5, sell, HI, ("core", "reward", 0.0)),
    ("core", "buy", 5, buy, HI, ("core", "gather", 0.0)),
    ("core", "errand", 5, errand, SR, ("core", "reward", 0.0)),
    ("core", "newday", 3, newday, SR, ("core", "reward", 0.0)),
    ("core", "win", 3, win, SR, ("core", "reward", 0.0)),
    ("core", "lose", 3, lose, SR, ("core", "error", 0.0)),
]


def family_ref_db(directory: str, ref) -> float:
    module, kind, delta = ref
    return synth_level(module, kind) + delta - VOLUME[directory] - HEADROOM_DB


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="render the life/fishing/core take families")
    ap.add_argument("--out", help="root dir for <dir>/<event>_<n>.wav (default game/assets/sfx)")
    ap.add_argument("--only", help="comma-separated event names")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="no per-take lines")
    args = ap.parse_args(argv)
    root = Path(args.out) if args.out else L.SFX_ROOT
    only = set(args.only.split(",")) if args.only else None
    total, count = 0, 0
    for directory, event, n, fn, sr, ref, *rest in FAMILIES:
        if only and event not in only:
            continue
        ref_db = family_ref_db(directory, ref)
        if args.list:
            print("%-5s %-13s %2d takes  %5d Hz  ref %6.1f dBFS (%s/%s %+.1f)" % (directory, event, n, sr, ref_db, *ref))
            continue
        print("== %s/%s (%d takes, ref %.1f dBFS)" % (directory, event, n, ref_db))
        meta = L.make_family(root / directory, event, n, fn, sr=sr, ref_db=ref_db, seed_base=SEED_BASE,
                             finish_kw=rest[0] if rest else None, verbose=not args.quiet)
        total += sum(d["bytes"] for d in meta)
        count += len(meta)
    if not args.list:
        print("GEN_LIFE wrote %d takes, %.1f KB" % (count, total / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
