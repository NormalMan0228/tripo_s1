"""Monster, combat, hero and NPC-voice sounds for the island survival RPG.

Writes mono 16-bit WAVs (everything synthesised, deterministic seeds):
  game/assets/sfx/creatures/<species>_<event>_<region>_<n>.wav
      species wolf | boar | brute | wisp | shroom
      event   idle | alert | windup | strike | hurt | death
      region  forest (moss rustle) | quarry (ember crackle) | frost (ice shimmer)
      n       1..2 takes, so repeats never sound identical
  game/assets/sfx/combat/<event>_<n>.wav       swings, impacts, block/dodge, crit, spawn,
                                               dissolve, player hit, heartbeat loop, fuel,
                                               night/dawn stings, harvest hits
  game/assets/sfx/hero/<event>_<n>.wav         cute vocal efforts and reward chimes
  game/assets/sfx/voice/<speaker>.wav          babble syllable bank per speaker (22050 Hz):
                                               len(ONSETS) x len(VOWELS) slots of SLOT seconds,
                                               slot = onset_index * len(VOWELS) + vowel_index

Building blocks (on top of tools/make_village_sfx.py): an additive formant voice
(harmonics weighted by moving formant resonances, so vowels and pitch glide without
filter artefacts), pulsed-noise snarls, STFT-shaped noise sweeps (whooshes, breaths,
flares), modal rocks/ice/wood, crackle and rustle layers. Region colouring is mixed
under every creature take and follows the take's own envelope.

Levels: every file is scaled to a short-term (120 ms, >150 Hz) RMS target per
category; runtime players then sit them next to the door sounds (-22.5 dBFS at -9 dB).

  .tools/art-venv/Scripts/python.exe tools/make_creature_sfx.py [--sheets] [--only creatures,combat,hero,voice]

--sheets writes spectrogram + envelope contact sheets to artifacts/audio-review/.
"""
from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np
import scipy.signal as ss
from scipy.ndimage import maximum_filter1d

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_village_sfx as V  # noqa: E402
from make_village_sfx import Synth, band, click, high, low, modal, place, reverb, secs, short_rms_peak, thud, time  # noqa: E402

ROOT = V.ROOT
SFX = ROOT / "game/assets/sfx"
REVIEW = ROOT / "artifacts/audio-review"
SR = V.SR  # 32000
VOICE_SR = 22050
MAX_BYTES = 150_000

SPECIES = ["wolf", "boar", "brute", "wisp", "shroom"]
EVENTS = ["idle", "alert", "windup", "strike", "hurt", "death"]
REGIONS = ["forest", "quarry", "frost"]
TAKES = 2
# Babble bank layout (voice_babble.gd mirrors these).
ONSETS = ["v", "n", "p", "s"]
VOWEL_ORDER = ["a", "e", "i", "o", "u", "eo", "eu"]
SLOT = 0.115


# --------------------------------------------------------------------------- primitives
def ctl(n, pts, smooth=0.006):
    """Piecewise-linear control curve over n samples from [(t, value), ...], lightly smoothed."""
    t = time(n)
    ts = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    y = np.interp(t, ts, vs)
    k = secs(smooth)
    if k > 1 and n > 2 * k + 1:
        ker = np.hanning(2 * k + 1)
        ker /= ker.sum()
        y = np.convolve(np.pad(y, k, mode="edge"), ker, mode="valid")
    return y


def wander(s, n, hz, depth=1.0):
    pad = secs(0.25)
    x = low(s.noise(n + pad), hz, 2)[pad:]
    return x / (x.std() + 1e-12) * depth


def norm(x):
    return x / (np.sqrt(np.mean(np.asarray(x) ** 2)) + 1e-12)


def full(n, v):
    return np.broadcast_to(np.asarray(v, float), (n,)).astype(float)


VOWELS = {
    "a": (800, 1300, 2600, 3600), "e": (500, 1900, 2600, 3600), "i": (320, 2300, 3000, 3800),
    "o": (480, 850, 2500, 3500), "u": (360, 800, 2300, 3400), "eo": (600, 1050, 2550, 3500),
    "eu": (380, 1400, 2500, 3500), "m": (250, 1050, 2300, 3300), "n": (260, 1500, 2500, 3400),
    "ae": (700, 1700, 2600, 3600),
}


def tracks(n, seq, scale=1.0):
    """[(t, vowel), ...] -> four formant tracks gliding between the vowels."""
    if isinstance(seq, str):
        seq = [(0.0, seq)]
    return [ctl(n, [(t, VOWELS[v][i] * scale) for t, v in seq], 0.012) for i in range(4)]


def voice(s, n, f0, F, amp=1.0, tilt=1.0, breath=0.0, jitter=0.005, shimmer=0.04, fmax=8000.0, bw=1.0,
          G=(1.0, 0.7, 0.4, 0.22), sub=0.0, flutter=0.0, odd=0.0, vib=(0.0, 0.0)):
    """Additive formant voice: harmonics of f0(t) weighted by resonances at F(t).
    breath mixes aspiration noise shaped by the same (mean) formants."""
    f0 = full(n, f0)
    if vib[1]:
        f0 = f0 * (1 + vib[1] * np.sin(2 * np.pi * vib[0] * time(n)))
    if jitter:
        f0 = f0 * (1 + wander(s, n, 30, jitter))
    phase = 2 * np.pi * np.cumsum(f0) / SR
    Fs = [full(n, f) for f in F]
    Bs = [np.maximum(60.0, 0.08 * f + 40.0) * bw for f in Fs]
    top = min(fmax, 0.45 * SR)
    K = int(top / max(float(f0.min()), 25.0))
    voiced = np.zeros(n)
    for k0 in range(1, K + 1, 24):
        ks = np.arange(k0, min(K, k0 + 23) + 1)[:, None].astype(float)
        fk = ks * f0[None, :]
        g = np.zeros_like(fk)
        for Fi, Bi, Gi in zip(Fs, Bs, G):
            g += Gi / (1 + ((fk - Fi[None, :]) / (0.5 * Bi[None, :])) ** 2)
        g *= ks ** -tilt
        g *= np.clip((top - fk) / (0.15 * top), 0, 1)
        if odd:
            g *= np.where(ks % 2 == 0, 1 - odd, 1.0)
        voiced += np.sum(g * np.sin(ks * phase[None, :]), axis=0)
    if sub:
        voiced *= 1 + sub * np.sin(phase / 2)
    if flutter:
        voiced *= 1 + flutter * np.clip(wander(s, n, 38, 0.6), -1, 1)
    out = norm(voiced) * (1 - breath)
    if breath:
        nz = s.noise(n)
        asp = sum(Gi * band(nz, max(np.mean(Fi) * 0.75, 80), np.mean(Fi) * 1.3) for Fi, Gi in zip(Fs, G))
        out = out + norm(asp) * breath
    if shimmer:
        out *= 1 + shimmer * np.clip(wander(s, n, 40, 1.0), -2, 2)
    return out * full(n, amp)


def rasp(s, n, f0, F, sharp=3.0, lo=250, hi=7000, G=(1.0, 0.7, 0.4, 0.25)):
    """Noise pulsed at the voice period and coloured by formants: snarls, squeals, hisses."""
    f0 = full(n, f0) * (1 + wander(s, n, 25, 0.02))
    phase = 2 * np.pi * np.cumsum(f0) / SR
    pulse = (0.5 + 0.5 * np.cos(phase)) ** sharp
    nz = band(s.noise(n), lo, hi) * pulse
    y = sum(g * band(nz, max(np.mean(f) * 0.78, 60), np.mean(f) * 1.28) for f, g in zip(F, G))
    return norm(y)


def nsweep(s, n, fc, bw=0.6, nper=512):
    """White noise shaped in the STFT domain by a log-Gaussian band centred on fc(t) (bw in octaves)."""
    x = s.noise(n + nper)
    f, tt, Z = ss.stft(x, SR, nperseg=nper, noverlap=nper * 3 // 4)
    fcs = np.interp(tt, time(n), full(n, fc))
    bws = np.interp(tt, time(n), full(n, bw))
    lf = np.log2(np.maximum(f, 20.0))[:, None]
    mask = np.exp(-0.5 * ((lf - np.log2(np.maximum(fcs, 30.0))[None, :]) / bws[None, :]) ** 2)
    _, y = ss.istft(Z * mask, SR, nperseg=nper, noverlap=nper * 3 // 4)
    return norm(y[:n])


def glide(n, f, harmonics=((1, 1.0),)):
    ph = 2 * np.pi * np.cumsum(full(n, f)) / SR
    return sum(a * np.sin(k * ph) for k, a in harmonics)


def env_at(env, i):
    return float(env[min(max(i, 0), env.size - 1)]) if env is not None else 1.0


def pops(s, n, density, lo=1500, hi=7000, env=None, size=(0.0015, 0.005)):
    """Sparse crackle clicks; env (n,) scales density and level over time."""
    out = np.zeros(n)
    for _ in range(int(density * n / SR)):
        at = int(s.rng.integers(0, n))
        g = s.rng.uniform(0.2, 1.0) * env_at(env, at)
        if g < 0.02:
            continue
        c = click(s, 0.025, lo, hi, s.rng.uniform(*size))
        j = min(n, at + c.size)
        out[at:j] += c[: j - at] * g
    return out


def tinkles(s, n, density, lo=3200, hi=9500, env=None, decay=(0.03, 0.11)):
    """Crystalline ice glints: tiny inharmonic modal pings."""
    out = np.zeros(n)
    for _ in range(int(density * n / SR)):
        at = int(s.rng.integers(0, n))
        g = s.rng.uniform(0.25, 1.0) * env_at(env, at)
        if g < 0.03:
            continue
        f = s.rng.uniform(lo, hi)
        d = s.rng.uniform(*decay)
        m = modal([f, f * 2.71, f * 4.13], [d, d * 0.55, d * 0.3], [1, 0.35, 0.15], d * 4 + 0.07, s.rng, attack=0.0005)
        j = min(n, at + m.size)
        out[at:j] += np.asarray(m)[: j - at] * g
    return out


def rock(s, size=1.0):
    f = s.rng.uniform(900, 2600) / size
    return np.asarray(modal([f, f * 1.63, f * 2.47, f * 3.9], [0.014 * size, 0.01 * size, 0.007 * size, 0.004 * size],
                            [1, 0.7, 0.5, 0.3], 0.07 + 0.08 * size, s.rng)
                      + click(s, 0.03, 1200 / size, 8000, 0.002) * 0.9)


def debris(s, n, count, start=0.0, spread=0.6, sizes=(0.4, 1.1), gain=1.0, falloff=1.6):
    """Pebbles/rock chips landing: dense first, sparse later."""
    out = np.zeros(n)
    for _ in range(count):
        u = s.rng.uniform(0, 1) ** falloff
        at = start + u * spread
        place(out, rock(s, s.rng.uniform(*sizes)), at, gain * s.rng.uniform(0.3, 1.0) * (1 - 0.6 * u))
    return out


def rustle(s, n, env, body_gain=1.0):
    """Leaf/moss rustle following an envelope."""
    am = 0.45 + 0.55 * np.clip(np.abs(wander(s, n, 22, 0.8)), 0, 1)
    body = band(s.noise(n), 1800, 6500) * am
    return norm(body) * env * body_gain + pops(s, n, 70, 2500, 9000, env, (0.001, 0.003)) * 1.2


def scrape(s, length, lo=180, hi=2600):
    n = secs(length)
    t = time(n)
    env = np.minimum(t / (length * 0.25), 1) * np.clip((length - t) / (length * 0.5), 0, 1)
    x = norm(band(s.noise(n), lo, hi)) * env * (0.7 + 0.3 * np.clip(wander(s, n, 30, 1), -1, 1))
    return x + pops(s, n, 140, 400, 3500, env, (0.001, 0.004)) * 1.5


def bloop(s, f_start, f_end, length=0.12, wet=0.3):
    """Wet bubble / squish pop: an exponential sine glide plus a little lowpassed splash."""
    n = secs(length)
    t = time(n)
    f = f_end + (f_start - f_end) * np.exp(-t / (length * 0.35))
    y = glide(n, f) * np.exp(-t / (length * 0.4)) * np.minimum(t / 0.004, 1)
    y += norm(low(s.noise(n), 1400)) * np.exp(-t / 0.015) * wet
    return y


def fire(s, length, lo=180, hi=2600, flick=7.0):
    n = secs(length)
    am = 0.55 + 0.45 * np.clip(wander(s, n, flick, 0.7), -1, 1)
    return norm(band(s.noise(n), lo, hi)) * am + norm(low(s.noise(n), 260)) * 0.6


def shape(x, pts):
    return x * ctl(x.size, pts)


def bell(s, f0, length=1.0, decay=0.6, bright=1.0):
    return np.asarray(V.bell(s, f0, length, decay=decay, bright=bright))


def follower(x, ms=25):
    e = maximum_filter1d(np.abs(x), max(1, secs(ms / 1000)))
    e = low(e, 30, 1)
    return np.clip(e / (np.max(e) + 1e-12), 0, 1)


def fades(x, fin=0.002, fout=0.03):
    x = x.copy()
    a = min(secs(fin), x.size)
    b = min(secs(fout), x.size)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b) ** 2
    return x


def trim(x, max_s=2.0, floor_db=-54.0, keep=0.04):
    peak = np.max(np.abs(x)) + 1e-12
    env = maximum_filter1d(np.abs(x), secs(0.02))
    above = np.nonzero(env > peak * 10 ** (floor_db / 20))[0]
    end = min(x.size, (above[-1] if above.size else x.size) + secs(keep), secs(max_s))
    return fades(x[:end], fout=0.04 if end < secs(max_s) else 0.25)


def level(x, target_db, window=0.12, ceiling=0.89):
    """Scale to a short-term RMS target; transients go through a soft limiter (at most ~4 dB)."""
    x = high(np.asarray(x, float), 25)
    r = short_rms_peak(x, window)
    g = 10 ** (target_db / 20) / (r + 1e-12)
    pk = np.max(np.abs(x)) * g
    if pk > ceiling * 1.6:
        g *= ceiling * 1.6 / pk
    x = x * g
    if np.max(np.abs(x)) > ceiling * 0.8:
        x = ceiling * np.tanh(x / ceiling)
    return x


def write(path: Path, x: np.ndarray, sr=SR):
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def jit(s, a, b):
    return float(s.rng.uniform(a, b))


# --------------------------------------------------------------------------- vocal helpers
def vocal(s, length, f0_pts, vowels, amp_pts, scale=1.0, **kw):
    n = secs(length)
    return voice(s, n, ctl(n, f0_pts), tracks(n, vowels, scale), ctl(n, amp_pts), **kw)


def snarl(s, length, f0_pts, vowels, amp_pts, scale=1.0, sharp=3.0, lo=250, hi=7000):
    n = secs(length)
    return rasp(s, n, ctl(n, f0_pts), tracks(n, vowels, scale), sharp, lo, hi) * ctl(n, amp_pts)


def breathy(s, length, fc_pts, amp_pts, bw=0.7):
    n = secs(length)
    return nsweep(s, n, ctl(n, fc_pts), bw) * ctl(n, amp_pts)


def shadow_under(s, length, amp_pts, fc=170):
    """Dark low swell under the shadow beasts (wolf): felt more than heard."""
    n = secs(length)
    return (nsweep(s, n, fc, 0.7) * 0.7 + glide(n, 55 + 4 * np.sin(2 * np.pi * 0.7 * time(n))) * 0.3) * ctl(n, amp_pts)


# --------------------------------------------------------------------------- creatures
def wolf(s, ev, take):
    p = jit(s, 0.94, 1.06)
    if ev == "idle":
        out = np.zeros(secs(1.25))
        if take == 0:
            for at in (0.0, 0.15):
                place(out, breathy(s, 0.1, [(0, 2600), (0.1, 3500)], [(0, 0), (0.015, 1), (0.05, 0.7), (0.1, 0)], 0.45), at + jit(s, 0, 0.02), 0.55)
            place(out, vocal(s, 0.72, [(0, 80 * p), (0.35, 92 * p), (0.72, 74 * p)], [(0, "eu"), (0.72, "o")],
                             [(0, 0), (0.12, 0.8), (0.5, 0.9), (0.72, 0)], 0.8, tilt=1.1, breath=0.25, sub=0.35, flutter=0.4, fmax=5000), 0.33, 0.7)
            place(out, snarl(s, 0.72, [(0, 80 * p), (0.72, 74 * p)], "eu", [(0, 0), (0.2, 0.6), (0.72, 0)], 0.8, 4), 0.33, 0.25)
            place(out, breathy(s, 0.26, [(0, 1000), (0.26, 650)], [(0, 0), (0.03, 1), (0.26, 0)], 0.8), 0.98, 0.45)
        else:
            for k in range(3):
                at = k * 0.25 + jit(s, 0, 0.03)
                place(out, breathy(s, 0.16, [(0, 1500), (0.16, 1100)], [(0, 0), (0.02, 1), (0.16, 0)], 0.6), at, 0.7)
                place(out, vocal(s, 0.12, [(0, 190 * p), (0.12, 150 * p)], "a", [(0, 0), (0.02, 0.5), (0.12, 0)], 0.85, breath=0.7), at, 0.35)
                place(out, breathy(s, 0.09, [(0, 2100), (0.09, 2500)], [(0, 0), (0.03, 0.6), (0.09, 0)], 0.5), at + 0.15, 0.4)
            place(out, vocal(s, 0.35, [(0, 78 * p), (0.35, 70 * p)], "eu", [(0, 0), (0.08, 0.6), (0.35, 0)], 0.8, breath=0.3, sub=0.4, flutter=0.4, fmax=4500), 0.8, 0.45)
        place(out, shadow_under(s, 1.2, [(0, 0), (0.4, 0.2), (1.2, 0)]), 0.0, 0.25)
        return out
    if ev == "alert":
        out = np.zeros(secs(1.3))
        if take == 0:  # a short eerie howl
            L = 0.95
            f = [(0, 330 * p), (0.12, 470 * p), (0.55, 505 * p), (L, 390 * p)]
            place(out, snarl(s, 0.12, [(0, 110 * p), (0.12, 140 * p)], "eu", [(0, 0), (0.03, 0.8), (0.12, 0)], 0.85, 3), 0.0, 0.45)
            place(out, vocal(s, L, f, [(0, "u"), (0.25, "o"), (0.7, "o"), (L, "u")], [(0, 0), (0.08, 0.9), (0.6, 1.0), (L, 0)], 0.92,
                             tilt=1.25, breath=0.28, vib=(5.5, 0.012), fmax=6000), 0.05, 1.0)
        else:  # two barks and a growl
            for k, at in enumerate((0.0, 0.24)):
                L = 0.15
                f0 = [(0, 300 * p), (0.035, 430 * p), (L, 250 * p)]
                place(out, vocal(s, L, f0, [(0, "eu"), (0.04, "a"), (L, "o")], [(0, 0), (0.012, 1), (0.08, 0.8), (L, 0)], 0.88,
                                 tilt=0.9, breath=0.15, sub=0.25, fmax=6500), at, 1.0 - 0.15 * k)
                place(out, snarl(s, L, f0, "a", [(0, 0), (0.01, 1), (L, 0)], 0.88, 2.5, 400, 6000), at, 0.45)
            place(out, vocal(s, 0.55, [(0, 95 * p), (0.55, 82 * p)], "eu", [(0, 0), (0.1, 0.7), (0.55, 0)], 0.8, breath=0.25, sub=0.4, flutter=0.4, fmax=5000), 0.5, 0.6)
            place(out, snarl(s, 0.55, [(0, 95 * p), (0.55, 82 * p)], "e", [(0, 0), (0.1, 0.6), (0.55, 0)], 0.85, 4), 0.5, 0.35)
        place(out, shadow_under(s, 1.2, [(0, 0), (0.3, 0.35), (1.2, 0)]), 0.0, 0.25)
        return out
    if ev == "windup":  # rising snarl, teeth bared, ends in a sharp intake
        L = 0.6
        out = np.zeros(secs(0.72))
        f0 = [(0, 88 * p), (L, 138 * p)]
        place(out, vocal(s, L, f0, [(0, "eu"), (L, "ae")], [(0, 0), (0.1, 0.4), (L - 0.05, 1.0), (L, 0)], 0.85,
                         breath=0.25, sub=0.45, flutter=0.45, fmax=5500), 0.0, 0.8)
        place(out, snarl(s, L, f0, [(0, "eu"), (L, "ae")], [(0, 0), (0.15, 0.4), (L - 0.04, 1.0), (L, 0)], 0.88, 3.5, 300, 7500), 0.0, 0.6)
        place(out, breathy(s, 0.09, [(0, 2200), (0.09, 3200)], [(0, 0), (0.04, 1), (0.09, 0)], 0.5), L - 0.04, 0.4)
        return out
    if ev == "strike":  # lunge whoosh, jaw snap, short "rrah"
        out = np.zeros(secs(0.6))
        place(out, breathy(s, 0.14, [(0, 500), (0.14, 1600)], [(0, 0), (0.1, 1), (0.14, 0)], 0.8), 0.0, 0.4)
        snap = modal([1750 * p, 2900 * p, 4200 * p], [0.012, 0.008, 0.005], [1, 0.6, 0.35], 0.08, s.rng) + click(s, 0.03, 2000, 9000, 0.0015)
        place(out, snap, 0.11, 1.0)
        place(out, snap * 0.5, 0.16 + jit(s, 0, 0.02), 0.6)
        f0 = [(0, 210 * p), (0.04, 300 * p), (0.24, 170 * p)]
        place(out, vocal(s, 0.24, f0, [(0, "a"), (0.24, "eu")], [(0, 0), (0.015, 1), (0.24, 0)], 0.88, tilt=0.9, breath=0.2, sub=0.3, flutter=0.3, fmax=6000), 0.1, 0.8)
        place(out, snarl(s, 0.24, f0, "a", [(0, 0), (0.015, 1), (0.24, 0)], 0.88, 2.5), 0.1, 0.45)
        return out
    if ev == "hurt":  # yelp
        out = np.zeros(secs(0.5))
        f0 = [(0, 780 * p), (0.03, 1150 * p), (0.2, 640 * p)]
        place(out, vocal(s, 0.2, f0, [(0, "i"), (0.08, "a"), (0.2, "u")], [(0, 0), (0.01, 1), (0.08, 0.9), (0.2, 0)], 1.0, tilt=1.0, breath=0.2, fmax=8000), 0.0, 1.0)
        place(out, vocal(s, 0.2, [(0, 560 * p), (0.2, 470 * p)], "u", [(0, 0), (0.04, 0.35), (0.2, 0)], 1.0, breath=0.45), 0.22, 0.6)
        return out
    if ev == "death":  # falling whine -> whimper, body drops, shadow drains away
        out = np.zeros(secs(1.6))
        f0 = [(0, 820 * p), (0.05, 940 * p), (0.45, 520 * p), (0.7, 380 * p)]
        place(out, vocal(s, 0.7, f0, [(0, "i"), (0.15, "a"), (0.7, "u")], [(0, 0), (0.02, 1), (0.4, 0.75), (0.7, 0)], 1.0,
                         tilt=1.1, breath=0.3, vib=(7, 0.02), fmax=7000), 0.0, 1.0)
        place(out, vocal(s, 0.35, [(0, 420 * p), (0.35, 330 * p)], "u", [(0, 0), (0.06, 0.3), (0.35, 0)], 1.0, breath=0.55), 0.75, 0.55)
        place(out, thud(s, 75, 0.35, 0.08, grit=0.5), 0.55, 0.8)
        place(out, shadow_under(s, 1.1, [(0, 0), (0.25, 0.8), (1.1, 0)], 140), 0.45, 0.3)
        return out
    raise KeyError(ev)


def boar(s, ev, take):
    p = jit(s, 0.94, 1.06)

    def grunt(L=0.13, f=105.0, g="eu"):
        f0 = [(0, f * 0.9), (0.03, f * 1.12), (L, f * 0.85)]
        return (vocal(s, L, f0, [(0, "m"), (0.03, g), (L, "u")], [(0, 0), (0.015, 1), (L * 0.6, 0.8), (L, 0)], 0.75,
                      tilt=0.8, breath=0.15, sub=0.5, flutter=0.5, fmax=4500)
                + snarl(s, L, f0, g, [(0, 0), (0.015, 0.6), (L, 0)], 0.75, 2.0, 200, 3500) * 0.5)

    def snort(L=0.16):
        return breathy(s, L, [(0, 900), (0.04, 1800), (L, 1300)], [(0, 0), (0.008, 1), (0.05, 0.6), (L, 0)], 0.9) \
            + snarl(s, L, [(0, 60), (L, 45)], "u", [(0, 0), (0.01, 0.7), (L, 0)], 1.0, 6, 300, 3000) * 0.6

    def squeal(L, f_pts, amp_pts):
        n = secs(L)
        f0 = ctl(n, f_pts)
        F = tracks(n, [(0, "i"), (L * 0.3, "e"), (L, "ae")], 1.05)
        a = ctl(n, amp_pts)
        return voice(s, n, f0, F, a, tilt=0.8, breath=0.25, flutter=0.3, fmax=9000) + rasp(s, n, f0, F, 2.0, 600, 9000) * a * 0.5

    if ev == "idle":
        out = np.zeros(secs(1.15))
        times = (0.0, 0.2, 0.55) if take == 0 else (0.0, 0.32)
        for k, at in enumerate(times):
            place(out, grunt(jit(s, 0.11, 0.16), 100 * p * jit(s, 0.92, 1.08), "eu" if k % 2 == 0 else "o"), at + jit(s, 0, 0.03), 1.0 - 0.15 * k)
        for k in range(4):  # snuffling nose
            place(out, breathy(s, 0.06, [(0, 2400), (0.06, 1900)], [(0, 0), (0.01, 1), (0.06, 0)], 0.6), 0.75 + k * 0.08 + jit(s, 0, 0.02), 0.35)
        return out
    if ev == "alert":
        out = np.zeros(secs(1.05))
        place(out, snort(), 0.0, 0.9)
        if take == 0:
            place(out, squeal(0.36, [(0, 650 * p), (0.06, 1000 * p), (0.25, 1080 * p), (0.36, 760 * p)], [(0, 0), (0.02, 1), (0.28, 0.85), (0.36, 0)]), 0.16, 0.95)
        else:
            place(out, grunt(0.16, 125 * p, "a"), 0.17, 1.0)
            place(out, squeal(0.26, [(0, 760 * p), (0.05, 1150 * p), (0.26, 820 * p)], [(0, 0), (0.02, 1), (0.26, 0)]), 0.33, 0.85)
        place(out, thud(s, 80, 0.25, 0.04, grit=0.7), 0.58, 0.55)  # hoof stamp
        place(out, scrape(s, 0.15, 300, 3000), 0.6, 0.15)
        return out
    if ev == "windup":  # hoof pawing and snorts building to a charge
        out = np.zeros(secs(0.95))
        for k, at in enumerate((0.0, 0.26, 0.5)):
            place(out, scrape(s, 0.2 + jit(s, 0, 0.04)), at, 0.4 + 0.15 * k)
            place(out, thud(s, 95, 0.15, 0.03, grit=0.6), at + 0.02, 0.25 + 0.1 * k)
        place(out, snort(0.14), 0.12, 0.5)
        place(out, snort(0.14), 0.38, 0.65)
        place(out, grunt(0.22, 120 * p, "a"), 0.62, 0.9)
        return out
    if ev == "strike":  # charge impact, tusk clack, grunt-squeal
        out = np.zeros(secs(0.7))
        place(out, breathy(s, 0.12, [(0, 400), (0.12, 1200)], [(0, 0), (0.1, 1), (0.12, 0)], 0.9), 0.0, 0.4)
        place(out, thud(s, 70, 0.4, 0.09, body=1.2, grit=0.7), 0.1, 1.0)
        place(out, modal([1250 * p, 2140 * p, 3300 * p], [0.02, 0.012, 0.008], [1, 0.6, 0.3], 0.1, s.rng) + click(s, 0.03, 1500, 7000, 0.002), 0.105, 0.55)
        place(out, squeal(0.22, [(0, 520 * p), (0.04, 900 * p), (0.22, 600 * p)], [(0, 0), (0.015, 1), (0.22, 0)]), 0.12, 0.7)
        place(out, grunt(0.14, 130 * p, "a"), 0.11, 0.6)
        return out
    if ev == "hurt":
        out = np.zeros(secs(0.5))
        place(out, squeal(0.22, [(0, 900 * p), (0.03, 1350 * p), (0.22, 760 * p)], [(0, 0), (0.01, 1), (0.22, 0)]), 0.0, 1.0)
        place(out, grunt(0.14, 110 * p, "eu"), 0.22, 0.6)
        return out
    if ev == "death":  # long falling squeal, body flop, thorns rattle
        out = np.zeros(secs(1.6))
        place(out, squeal(0.75, [(0, 950 * p), (0.08, 1150 * p), (0.5, 640 * p), (0.75, 380 * p)], [(0, 0), (0.02, 1), (0.5, 0.75), (0.75, 0)]), 0.0, 1.0)
        place(out, grunt(0.3, 90 * p, "o"), 0.7, 0.7)
        place(out, thud(s, 62, 0.45, 0.11, body=1.3, grit=0.6), 0.8, 1.0)
        place(out, pops(s, secs(0.45), 60, 2500, 8000), 0.82, 0.6)  # thorny back rattles
        place(out, breathy(s, 0.4, [(0, 1200), (0.4, 700)], [(0, 0), (0.05, 0.5), (0.4, 0)], 0.8), 1.0, 0.4)
        return out
    raise KeyError(ev)


def brute(s, ev, take):
    p = jit(s, 0.94, 1.06)

    def groan(L, f_pts, amp_pts, vowels=("o", "u")):
        n = secs(L)
        f0 = ctl(n, f_pts)
        F = tracks(n, [(0, vowels[0]), (L, vowels[1])], 0.68)
        a = ctl(n, amp_pts)
        return voice(s, n, f0, F, a, tilt=0.7, breath=0.18, sub=0.55, flutter=0.5, fmax=3500, bw=1.3) \
            + rasp(s, n, f0, F, 2.5, 120, 2500) * a * 0.35

    def grind(L, amp_pts):
        n = secs(L)
        a = ctl(n, amp_pts)
        x = norm(band(s.noise(n), 60, 420)) * (0.6 + 0.4 * np.clip(wander(s, n, 9, 1), -1, 1))
        return x * a + pops(s, n, 50, 700, 3500, a, (0.002, 0.006)) * 0.8

    def crack(g=1.0):
        return (click(s, 0.05, 1500, 9000, 0.003) * 1.2 + rock(s, 1.3) + rock(s, 0.8) * 0.6) * g

    if ev == "idle":
        out = np.zeros(secs(1.4))
        place(out, grind(1.3, [(0, 0), (0.3, 0.8), (0.9, 0.6), (1.3, 0)]), 0.0, 0.7)
        if take == 0:
            place(out, groan(0.9, [(0, 46 * p), (0.45, 52 * p), (0.9, 44 * p)], [(0, 0), (0.25, 0.8), (0.9, 0)]), 0.2, 0.8)
        else:
            place(out, breathy(s, 0.7, [(0, 380), (0.7, 260)], [(0, 0), (0.2, 1), (0.7, 0)], 0.6), 0.3, 0.6)  # mossy exhale
            place(out, groan(0.5, [(0, 50 * p), (0.5, 46 * p)], [(0, 0), (0.15, 0.6), (0.5, 0)]), 0.55, 0.6)
        place(out, debris(s, secs(1.4), 5, 0.3, 0.9, (0.3, 0.6), 0.25), 0.0, 1.0)
        return out
    if ev == "alert":
        out = np.zeros(secs(1.5))
        place(out, crack(1.0), 0.0, 0.8)
        f = [(0, 50 * p), (0.25, 68 * p), (0.8, 62 * p), (1.15, 45 * p)] if take == 0 else [(0, 58 * p), (0.2, 74 * p), (1.1, 48 * p)]
        place(out, groan(1.15, f, [(0, 0), (0.15, 1.0), (0.85, 0.85), (1.15, 0)], ("u", "o") if take == 0 else ("o", "a")), 0.05, 1.0)
        place(out, grind(1.0, [(0, 0), (0.2, 0.6), (1.0, 0)]), 0.1, 0.45)
        place(out, debris(s, secs(1.5), 9, 0.05, 0.8, (0.4, 1.0), 0.45), 0.0, 1.0)
        return out
    if ev == "windup":  # stone arms lift: creak, grind and a rising groan (server wind-up 1.15 s)
        out = np.zeros(secs(1.25))
        L = 1.1
        place(out, grind(L, [(0, 0), (0.2, 0.5), (L - 0.05, 1.0), (L, 0)]), 0.0, 0.7)
        place(out, V.creak(s, L, 38, 62, body=(90, 210, 430, 800), q=6, rough=0.3, wobble=4.0, swell=0.3, release=0.15), 0.0, 0.5)
        place(out, groan(L, [(0, 48 * p), (L, 86 * p)], [(0, 0), (0.3, 0.5), (L - 0.06, 1.0), (L, 0)], ("u", "a")), 0.0, 0.9)
        place(out, debris(s, secs(1.25), 6, 0.2, 0.8, (0.3, 0.6), 0.3), 0.0, 1.0)
        return out
    if ev == "strike":  # ground slam
        out = np.zeros(secs(1.0))
        place(out, breathy(s, 0.12, [(0, 300), (0.12, 900)], [(0, 0), (0.1, 1), (0.12, 0)], 0.9), 0.0, 0.35)
        place(out, thud(s, 52, 0.7, 0.16, drop=0.5, body=1.5, grit=0.8), 0.1, 1.0)
        place(out, crack(1.0), 0.1, 0.9)
        place(out, debris(s, secs(1.0), 22, 0.12, 0.7, (0.4, 1.3), 0.6), 0.0, 1.0)
        place(out, grind(0.7, [(0, 0), (0.05, 0.8), (0.7, 0)]), 0.12, 0.5)
        return out
    if ev == "hurt":  # chipped stone and a short grunt
        out = np.zeros(secs(0.65))
        place(out, crack(1.0), 0.0, 1.0)
        place(out, groan(0.3, [(0, 62 * p), (0.3, 50 * p)], [(0, 0), (0.04, 0.9), (0.3, 0)], ("a", "o")), 0.03, 0.8)
        place(out, debris(s, secs(0.65), 7, 0.03, 0.4, (0.3, 0.7), 0.4), 0.0, 1.0)
        return out
    if ev == "death":  # collapse into a heap of mossy rubble
        out = np.zeros(secs(1.9))
        place(out, groan(1.0, [(0, 64 * p), (0.3, 58 * p), (1.0, 34 * p)], [(0, 0), (0.08, 1.0), (0.6, 0.6), (1.0, 0)], ("o", "u")), 0.0, 0.9)
        for k, at in enumerate((0.35, 0.62, 0.8, 1.02)):
            place(out, thud(s, 58 - 5 * k, 0.45, 0.1, body=1.2, grit=0.8), at + jit(s, 0, 0.04), 0.9 - 0.12 * k)
            place(out, crack(0.7), at, 0.6 - 0.1 * k)
        place(out, debris(s, secs(1.9), 30, 0.35, 1.1, (0.3, 1.2), 0.5), 0.0, 1.0)
        place(out, breathy(s, 0.7, [(0, 1500), (0.7, 2500)], [(0, 0), (0.15, 0.4), (0.7, 0)], 1.0), 1.0, 0.35)  # dust settling
        return out
    raise KeyError(ev)


def wisp(s, ev, take):
    p = jit(s, 0.94, 1.06)

    def blip(L, f_pts, vowels="i", g=1.0, breath=0.12):
        return vocal(s, L, f_pts, vowels, [(0, 0), (0.008, 1), (L * 0.5, 0.8), (L, 0)], 1.55, tilt=1.1, breath=breath, fmax=11000) * g

    def flame(L, amp_pts, lo=200, hi=2600):
        x = fire(s, L, lo, hi, 9)
        return x * ctl(x.size, amp_pts)

    if ev == "idle":
        out = np.zeros(secs(1.15))
        place(out, flame(1.1, [(0, 0), (0.2, 0.6), (0.8, 0.5), (1.1, 0)]), 0.0, 0.6)
        n_bl = 4 if take == 0 else 3
        for k in range(n_bl):
            f = (980 + 140 * ((k * 7 + take) % 3)) * p
            place(out, blip(0.055, [(0, f), (0.055, f * 1.12)], "i"), 0.3 + k * 0.085 + jit(s, 0, 0.015), 0.7)
        place(out, pops(s, secs(1.1), 14, 1500, 7000), 0.0, 0.5)
        return out
    if ev == "alert":  # mischievous giggle: "hi-hi-hee!"
        out = np.zeros(secs(1.0))
        place(out, flame(0.5, [(0, 0), (0.08, 1), (0.5, 0)], 300, 3000), 0.0, 0.6)
        notes = [(1050, 0.075), (1180, 0.075), (1000, 0.075), (1320, 0.16)] if take == 0 else [(900, 0.07), (1100, 0.07), (1250, 0.07), (1400, 0.07), (1150, 0.15)]
        at = 0.05
        for k, (f, L) in enumerate(notes):
            place(out, breathy(s, 0.03, [(0, 3500), (0.03, 3000)], [(0, 0), (0.008, 1), (0.03, 0)], 0.6), at, 0.25)  # "h"
            place(out, blip(L, [(0, f * p * 0.95), (L * 0.3, f * p * 1.06), (L, f * p * (1.1 if k == len(notes) - 1 else 0.98))], [(0, "i"), (L, "e" if k == len(notes) - 1 else "i")]), at + 0.015, 0.85)
            at += L + 0.035
        return out
    if ev == "windup":  # breathing in the fire: rising whoosh, crackle and a charging hum
        L = 0.85
        n = secs(L)
        out = np.zeros(secs(0.95))
        rise = ctl(n, [(0, 0), (L * 0.85, 1), (L, 0)])
        place(out, nsweep(s, n, ctl(n, [(0, 300), (L, 2600)]), 0.55) * rise, 0.0, 0.8)
        place(out, pops(s, n, 60, 1500, 7000, rise), 0.0, 0.8)
        place(out, glide(n, ctl(n, [(0, 220 * p), (L, 780 * p)]), ((1, 1.0), (2, 0.3), (3, 0.12))) * rise, 0.0, 0.25)
        place(out, blip(0.3, [(0, 700 * p), (0.3, 900 * p)], "m", 0.6, 0.3), 0.45, 0.6)
        return out
    if ev == "strike":  # fire spit: fwoosh + pop + "ha!"
        out = np.zeros(secs(0.75))
        n = secs(0.45)
        place(out, nsweep(s, n, ctl(n, [(0, 3200), (0.45, 500)]), 0.7) * ctl(n, [(0, 0), (0.012, 1), (0.45, 0)]), 0.0, 1.0)
        place(out, thud(s, 140, 0.15, 0.03, grit=0.4), 0.0, 0.5)
        place(out, blip(0.09, [(0, 1250 * p), (0.09, 1000 * p)], [(0, "a"), (0.09, "a")], 0.7, 0.3), 0.02, 0.6)
        place(out, pops(s, secs(0.6), 50, 1500, 8000, ctl(secs(0.6), [(0, 1), (0.6, 0)])), 0.05, 0.8)
        return out
    if ev == "hurt":  # squeak and sizzle
        out = np.zeros(secs(0.5))
        place(out, blip(0.14, [(0, 1300 * p), (0.03, 1750 * p), (0.14, 1150 * p)], [(0, "i"), (0.14, "e")], 1.0, 0.15), 0.0, 1.0)
        place(out, breathy(s, 0.35, [(0, 5500), (0.35, 4500)], [(0, 0), (0.02, 1), (0.35, 0)], 0.8) * (0.7 + 0.3 * np.clip(wander(s, secs(0.35), 50, 1), -1, 1)), 0.03, 0.5)
        return out
    if ev == "death":  # fizzle out: falling squeak, steam, last embers, a soft puff
        out = np.zeros(secs(1.45))
        place(out, blip(0.6, [(0, 1250 * p), (0.08, 1400 * p), (0.6, 420 * p)], [(0, "i"), (0.3, "u"), (0.6, "u")], 1.0, 0.25), 0.0, 1.0)
        n = secs(1.0)
        place(out, nsweep(s, n, ctl(n, [(0, 6000), (1.0, 3000)]), 0.6) * ctl(n, [(0, 0), (0.05, 1), (1.0, 0)]) * (0.75 + 0.25 * np.clip(wander(s, n, 60, 1), -1, 1)), 0.15, 0.6)
        place(out, pops(s, secs(1.2), 25, 1500, 7000, ctl(secs(1.2), [(0, 1), (1.2, 0)])), 0.1, 0.6)
        place(out, thud(s, 160, 0.12, 0.025, grit=0.3), 0.6, 0.35)
        return out
    raise KeyError(ev)


def shroom(s, ev, take):
    p = jit(s, 0.94, 1.06)

    def hum(L, f_pts, vowels=("m", "u"), g=1.0, breath=0.5):
        return vocal(s, L, f_pts, [(0, vowels[0]), (L, vowels[1])], [(0, 0), (L * 0.2, 1), (L * 0.7, 0.8), (L, 0)], 1.1,
                     tilt=1.4, breath=breath, vib=(4.5, 0.02), fmax=6000) * g

    def puff(L=0.35, fc=1800, g=1.0):
        n = secs(L)
        x = nsweep(s, n, ctl(n, [(0, fc), (L, fc * 0.6)]), 1.0) * ctl(n, [(0, 0), (0.01, 1), (0.08, 0.5), (L, 0)])
        place(x, bloop(s, 260, 160, 0.1, 0.4), 0.0, 0.5)
        return x * g

    if ev == "idle":
        out = np.zeros(secs(1.2))
        for k in range(3 if take == 0 else 2):
            f0 = jit(s, 220, 380) * p
            place(out, bloop(s, f0, f0 * 1.6, 0.11, 0.25), k * 0.17 + jit(s, 0, 0.04), 0.6)
        place(out, hum(0.7, [(0, 250 * p), (0.35, 270 * p), (0.7, 235 * p)]), 0.4, 0.7)
        place(out, puff(0.3, 3500, 0.25), 0.8, 1.0)
        return out
    if ev == "alert":  # ghostly "oooh?" and a wobbling cap
        out = np.zeros(secs(1.1))
        f = [(0, 300 * p), (0.45, 340 * p), (0.75, 450 * p)] if take == 0 else [(0, 420 * p), (0.3, 360 * p), (0.75, 380 * p)]
        place(out, vocal(s, 0.75, f, [(0, "o"), (0.75, "u")], [(0, 0), (0.15, 1), (0.6, 0.85), (0.75, 0)], 1.1,
                         tilt=1.35, breath=0.6, vib=(5, 0.025), fmax=6000), 0.05, 1.0)
        place(out, bloop(s, 200, 330, 0.14, 0.3), 0.0, 0.5)
        place(out, bloop(s, 260, 380, 0.12, 0.3), 0.12, 0.35)
        return out
    if ev == "windup":  # the cap inflates: wobbling intake, rubbery creak, rising hum
        L = 0.8
        n = secs(L)
        out = np.zeros(secs(0.9))
        wob = 0.65 + 0.35 * np.sin(2 * np.pi * 8 * time(n))
        place(out, nsweep(s, n, ctl(n, [(0, 400), (L, 1500)]), 0.6) * ctl(n, [(0, 0), (L * 0.9, 1), (L, 0)]) * wob, 0.0, 0.6)
        place(out, V.creak(s, L, 130, 210, body=(220, 520, 1100), q=5, rough=0.12, wobble=8, swell=0.2, release=0.1), 0.0, 0.45)
        place(out, hum(L, [(0, 230 * p), (L, 380 * p)], ("u", "o"), 0.7, 0.45), 0.0, 1.0)
        return out
    if ev == "strike":  # spore puff
        out = np.zeros(secs(0.75))
        place(out, puff(0.5, 1600, 1.0), 0.0, 1.0)
        place(out, glide(secs(0.12), ctl(secs(0.12), [(0, 210), (0.12, 120)])) * np.exp(-time(secs(0.12)) / 0.04), 0.0, 0.6)
        n = secs(0.6)
        place(out, high(s.noise(n), 6000) * ctl(n, [(0, 0), (0.05, 0.3), (0.6, 0)]), 0.05, 0.6)  # drifting spores
        return out
    if ev == "hurt":
        out = np.zeros(secs(0.5))
        place(out, norm(low(s.noise(secs(0.08)), 1800)) * np.exp(-time(secs(0.08)) / 0.02), 0.0, 0.8)  # squish
        place(out, bloop(s, 420, 260, 0.1, 0.5), 0.0, 0.6)
        place(out, vocal(s, 0.2, [(0, 600 * p), (0.04, 800 * p), (0.2, 520 * p)], "u", [(0, 0), (0.015, 1), (0.2, 0)], 1.15, tilt=1.2, breath=0.3), 0.03, 0.9)
        return out
    if ev == "death":  # deflating wheeze, last spore cloud, soft squelch
        out = np.zeros(secs(1.55))
        place(out, vocal(s, 0.9, [(0, 420 * p), (0.9, 150 * p)], [(0, "o"), (0.9, "u")], [(0, 0), (0.05, 1), (0.6, 0.6), (0.9, 0)], 1.1,
                         tilt=1.4, breath=0.65, vib=(6, 0.03), fmax=6000), 0.0, 1.0)
        n = secs(0.9)
        place(out, nsweep(s, n, ctl(n, [(0, 2500), (0.9, 900)]), 0.5) * ctl(n, [(0, 0), (0.1, 0.7), (0.9, 0)]), 0.1, 0.5)  # air leak
        place(out, puff(0.6, 1400, 0.9), 0.85, 1.0)
        place(out, bloop(s, 300, 150, 0.16, 0.6), 0.95, 0.6)
        return out
    raise KeyError(ev)


SPECIES_FN = {"wolf": wolf, "boar": boar, "brute": brute, "wisp": wisp, "shroom": shroom}
# st-rms targets (dBFS) per event; idle chatter sits under the fight.
CREATURE_DB = {"idle": -21.0, "alert": -16.5, "windup": -17.5, "strike": -16.0, "hurt": -17.0, "death": -16.5}
MAX_LEN = {"idle": 1.35, "alert": 1.45, "windup": 1.3, "strike": 1.0, "hurt": 0.8, "death": 1.9}
REGION_ROOM = {"forest": (0.55, 0.11, 5000, ()), "quarry": (0.8, 0.15, 3800, ((0.09, 0.12), (0.17, 0.07))),
               "frost": (1.05, 0.15, 8500, ())}


# Region layer level relative to the take's RMS; the stone guardian keeps its layers darker.
LAYER_GAIN = {"forest": 0.15, "quarry": 0.24, "frost": 0.19}
SPECIES_LAYER = {"wolf": 1.0, "boar": 1.0, "brute": 0.6, "wisp": 1.0, "shroom": 0.9}


def region_layer(s, x, region, ev, species=""):
    """Moss rustle / ember crackle / ice shimmer mixed under the take, following its envelope."""
    n = x.size
    k = LAYER_GAIN[region] * SPECIES_LAYER.get(species, 1.0)
    e = follower(x)
    ref = np.sqrt(np.mean(x ** 2)) + 1e-9
    if region == "forest":
        lay = rustle(s, n, e ** 0.8, 0.45)
        if ev in ("strike", "death", "alert"):
            snap = np.asarray(modal([1400, 2300, 3700], [0.01, 0.007, 0.005], [1, 0.5, 0.3], 0.06, s.rng)) + click(s, 0.03, 1200, 6000, 0.002)
            place(lay, snap * 2.5, float(np.argmax(e > 0.6)) / SR, 0.6)  # twig snap on the accent
        return x + norm(lay) * ref * k
    if region == "quarry":
        warm = np.tanh(1.8 * x / (np.max(np.abs(x)) + 1e-9)) * np.max(np.abs(x)) / np.tanh(1.8)
        lay = pops(s, n, 55 if ev != "idle" else 30, 1200, 7500, e ** 0.6, (0.0015, 0.006)) + fire(s, n / SR, 150, 1400, 6) * e * 0.12
        if ev in ("strike", "death"):
            m = secs(0.5)
            place(lay, nsweep(s, m, ctl(m, [(0, 400), (0.5, 1800)]), 0.8) * ctl(m, [(0, 0), (0.05, 1), (0.5, 0)]) * 0.4,
                  float(np.argmax(e > 0.7)) / SR, 1.0)  # ember flare
        return 0.85 * warm + 0.15 * x + norm(lay) * ref * k
    if region == "frost":
        lay = tinkles(s, n, 22 if ev != "idle" else 12, 3000, 9500, e ** 0.7) + nsweep(s, n, 6500, 0.5) * e * 0.12
        if ev in ("strike", "death", "hurt"):
            at = float(np.argmax(e > 0.7)) / SR
            place(lay, click(s, 0.04, 2500, 10000, 0.002) * 1.5, at, 1.0)  # ice crack
            for i in range(5):
                place(lay, tinkles(s, secs(0.3), 40, 4000, 10000), at + 0.02 * i, 0.6)
        return x + norm(lay) * ref * k
    raise KeyError(region)


def creature(species, ev, region, take):
    seed = (sum(map(ord, species + ev)) * 7919 + take * 104729) % (2 ** 31)
    base = np.asarray(SPECIES_FN[species](Synth(seed), ev, take), float)
    if species == "brute" and ev in ("idle", "alert", "windup"):
        base = low(base, 3800, 2)  # moss and stone: keep the body dark
    s = Synth(seed + sum(map(ord, region)) * 31)
    x = region_layer(s, base, region, ev, species)
    rt, wet, tone, early = REGION_ROOM[region]
    x = reverb(s, x, rt, wet, 0.012, tone, early)
    return level(trim(x, MAX_LEN[ev], floor_db=-48.0), CREATURE_DB[ev])


# --------------------------------------------------------------------------- combat
def whoosh(s, L, f_lo, f_hi, peak=0.45, bw=0.55, tone=0.0, body=0.0):
    n = secs(L)
    u = time(n) / L
    fc = f_lo + (f_hi - f_lo) * np.exp(-((u - peak) / 0.22) ** 2)
    a = np.exp(-((u - peak) / 0.2) ** 2) * np.minimum(u / 0.05, 1) * np.clip((1 - u) / 0.15, 0, 1)
    x = nsweep(s, n, fc, bw) * a
    if tone:  # thin blade/shaft whistle
        x += glide(n, fc * 1.4) * a ** 2 * tone
    if body:  # heavy tool: low air push
        x += nsweep(s, n, fc * 0.35, 0.5) * a * body
    return x


def flesh(s, g=1.0):
    n = secs(0.3)
    t = time(n)
    smack = norm(band(s.noise(n), 400, 2600)) * np.exp(-t / 0.012)
    return (np.asarray(thud(s, jit(s, 105, 130), 0.3, 0.05, drop=0.5, grit=0.6)) + smack * 0.6) * g


def wood_hit(s, g=1.0):
    f = jit(s, 280, 360)
    out = np.zeros(secs(0.3))
    place(out, modal([f, f * 2.3, f * 4.1, f * 6.2], [0.05, 0.03, 0.018, 0.01], [1, 0.6, 0.35, 0.2], 0.3, s.rng), 0.0)
    place(out, click(s, 0.04, 900, 6000, 0.003), 0.0, 1.2)
    place(out, thud(s, 120, 0.2, 0.04, grit=0.4), 0.0, 0.5)
    return out * g


def spirit_hit(s, g=1.0):
    out = np.zeros(secs(0.8))
    n = secs(0.25)
    place(out, nsweep(s, n, ctl(n, [(0, 1200), (0.25, 6000)]), 0.6) * ctl(n, [(0, 0), (0.01, 1), (0.25, 0)]), 0.0, 0.7)
    f = jit(s, 1150, 1400)
    place(out, bell(s, f, 0.7, 0.35, 0.8), 0.0, 0.5)
    place(out, bell(s, f * 1.498, 0.6, 0.3, 0.6), 0.01, 0.3)
    place(out, tinkles(s, secs(0.6), 30, 3500, 9000, ctl(secs(0.6), [(0, 1), (0.6, 0)])), 0.02, 0.8)
    place(out, thud(s, 150, 0.15, 0.03, grit=0.3), 0.0, 0.4)
    return out * g


def stone_hit(s, g=1.0):
    out = np.zeros(secs(0.6))
    place(out, click(s, 0.05, 1500, 9000, 0.0025), 0.0, 1.2)
    place(out, rock(s, 1.4), 0.0, 1.0)
    place(out, rock(s, 0.9), 0.004, 0.6)
    place(out, debris(s, secs(0.6), 6, 0.02, 0.35, (0.3, 0.6), 0.35), 0.0, 1.0)
    place(out, thud(s, 110, 0.15, 0.03, grit=0.5), 0.0, 0.4)
    return out * g


def combat(ev, take):
    s = Synth((sum(map(ord, ev)) * 15485863 + take * 7919) % (2 ** 31))
    p = jit(s, 0.95, 1.05)
    out = np.zeros(secs(2.2))
    rt, wet, tone = 0.35, 0.07, 6000
    if ev == "swing_axe":
        place(out, whoosh(s, 0.28, 280 * p, 1100 * p, 0.5, 0.6, body=0.5), 0.0)
    elif ev == "swing_axe_heavy":
        place(out, whoosh(s, 0.42, 200 * p, 900 * p, 0.55, 0.65, body=0.8), 0.0)
        place(out, whoosh(s, 0.3, 400 * p, 1500 * p, 0.6, 0.5), 0.1, 0.4)
    elif ev == "swing_spear":
        place(out, whoosh(s, 0.22, 600 * p, 2600 * p, 0.45, 0.4, tone=0.12), 0.0)
    elif ev == "swing_spear_heavy":
        place(out, whoosh(s, 0.34, 450 * p, 2200 * p, 0.5, 0.45, tone=0.15, body=0.3), 0.0)
    elif ev == "swing_fist":
        place(out, whoosh(s, 0.13, 500 * p, 1800 * p, 0.45, 0.7), 0.0)
        place(out, rustle(s, secs(0.12), ctl(secs(0.12), [(0, 0), (0.03, 1), (0.12, 0)])), 0.0, 0.25)  # sleeve
    elif ev == "swing_fist_heavy":
        place(out, whoosh(s, 0.2, 350 * p, 1500 * p, 0.5, 0.7, body=0.4), 0.0)
        place(out, rustle(s, secs(0.18), ctl(secs(0.18), [(0, 0), (0.04, 1), (0.18, 0)])), 0.0, 0.3)
    elif ev == "hit_flesh":
        place(out, flesh(s), 0.0)
        rt, wet = 0.3, 0.05
    elif ev == "hit_stone":
        place(out, stone_hit(s), 0.0)
        rt, wet = 0.5, 0.1
    elif ev == "hit_wood":
        place(out, wood_hit(s), 0.0)
        rt, wet = 0.4, 0.08
    elif ev == "hit_spirit":
        place(out, spirit_hit(s), 0.0)
        rt, wet, tone = 0.8, 0.14, 8000
    elif ev == "block":  # weapon catches the blow: hard knock + short scrape
        f = jit(s, 480, 560)
        place(out, modal([f, f * 2.58, f * 4.31, f * 6.1], [0.09, 0.05, 0.03, 0.02], [1, 0.6, 0.4, 0.25], 0.35, s.rng) + click(s, 0.04, 1500, 8000, 0.002), 0.0)
        place(out, thud(s, 140, 0.15, 0.03, grit=0.5), 0.0, 0.5)
        n = secs(0.12)
        place(out, norm(band(s.noise(n), 2000, 6500)) * ctl(n, [(0, 0), (0.01, 1), (0.12, 0)]), 0.03, 0.25)
        rt, wet = 0.45, 0.1
    elif ev == "dodge":  # quick roll: cloth whoosh + skid
        place(out, whoosh(s, 0.26, 300 * p, 1300 * p, 0.35, 0.8), 0.0, 0.8)
        place(out, rustle(s, secs(0.25), ctl(secs(0.25), [(0, 0), (0.05, 1), (0.25, 0)])), 0.02, 0.4)
        place(out, scrape(s, 0.18, 200, 2400), 0.16, 0.5)
    elif ev == "critical":  # hit + bright "shing" + low boom + sparkles
        place(out, flesh(s, 0.9), 0.0)
        place(out, click(s, 0.05, 1500, 9000, 0.003), 0.0, 1.0)
        n = secs(0.6)
        place(out, glide(n, ctl(n, [(0, 70), (0.6, 45)])) * np.exp(-time(n) / 0.18), 0.0, 0.8)
        place(out, bell(s, 1568, 1.0, 0.45, 1.0), 0.02, 0.35)
        place(out, bell(s, 2349, 0.9, 0.4, 0.8), 0.05, 0.25)
        place(out, tinkles(s, secs(0.7), 35, 4000, 10000, ctl(secs(0.7), [(0, 1), (0.7, 0)])), 0.04, 0.8)
        rt, wet, tone = 0.7, 0.12, 8000
    elif ev == "spawn":  # dark reverse-swell, then a smoky pop
        n = secs(0.42)
        place(out, nsweep(s, n, ctl(n, [(0, 250), (0.42, 1500)]), 0.7) * ctl(n, [(0, 0), (0.38, 1), (0.42, 0.2)]) ** 1.5, 0.0, 0.9)
        place(out, glide(n, 55 * p, ((1, 1.0), (2, 0.4), (3, 0.2))) * ctl(n, [(0, 0), (0.4, 1), (0.42, 0)]), 0.0, 0.5)
        place(out, thud(s, 130, 0.25, 0.05, grit=0.7), 0.4, 0.8)
        m = secs(0.6)
        place(out, nsweep(s, m, ctl(m, [(0, 1200), (0.6, 400)]), 0.9) * ctl(m, [(0, 0), (0.02, 1), (0.6, 0)]), 0.4, 0.5)
        rt, wet, tone = 0.9, 0.15, 4000
    elif ev == "dissolve":  # cozy poof into motes: falling shimmer, soft fwoo, two fading notes
        n = secs(1.1)
        place(out, nsweep(s, n, ctl(n, [(0, 6500), (1.1, 900)]), 0.5) * ctl(n, [(0, 0), (0.06, 1), (1.1, 0)]), 0.0, 0.7)
        place(out, tinkles(s, n, 30, 3000, 9000, ctl(n, [(0, 1), (1.1, 0)])), 0.0, 0.7)
        m = secs(0.5)
        place(out, nsweep(s, m, 500, 0.8) * ctl(m, [(0, 0), (0.05, 1), (0.5, 0)]), 0.0, 0.5)
        place(out, bell(s, 1175 * p, 0.9, 0.4, 0.5), 0.12, 0.18)
        place(out, bell(s, 880 * p, 1.0, 0.45, 0.5), 0.32, 0.16)
        rt, wet, tone = 1.0, 0.16, 7000
    elif ev == "player_hit":  # the hero is struck: punchy but soft, with a cartoon "bwom"
        place(out, thud(s, 100, 0.3, 0.06, grit=0.6), 0.0)
        n = secs(0.06)
        place(out, norm(band(s.noise(n), 300, 2000)) * np.exp(-time(n) / 0.015), 0.0, 0.6)
        m = secs(0.22)
        place(out, glide(m, ctl(m, [(0, 200 * p), (0.22, 120 * p)]), ((1, 1.0), (2, 0.35), (3, 0.12))) * ctl(m, [(0, 0), (0.01, 1), (0.22, 0)]), 0.0, 0.5)
        place(out, click(s, 0.03, 3000, 8000, 0.002), 0.0, 0.35)
    elif ev == "heartbeat":  # handled by heartbeat_loop()
        raise KeyError(ev)
    elif ev == "fuel":  # logs onto the campfire: two knocks, a flare, crackle burst
        place(out, wood_hit(s, 0.9), 0.0)
        place(out, wood_hit(s, 0.7), 0.13 + jit(s, 0, 0.03))
        n = secs(0.8)
        place(out, nsweep(s, n, ctl(n, [(0, 300), (0.35, 1200), (0.8, 700)]), 0.8) * ctl(n, [(0, 0), (0.3, 1), (0.8, 0)]), 0.12, 0.6)
        place(out, fire(s, 1.1, 150, 1800) * ctl(secs(1.1), [(0, 0), (0.3, 0.5), (1.1, 0)]), 0.15, 0.4)
        m = secs(1.2)
        place(out, pops(s, m, 70, 1500, 7500, ctl(m, [(0, 0), (0.25, 1), (1.2, 0.1)])), 0.12, 1.0)
        rt, wet = 0.4, 0.06
    elif ev == "night":  # the sun is down: low minor swell, cold glints, a far howl
        n = secs(2.1)
        pad = np.zeros(n)
        for f, a in ((73.4, 0.9), (110.0, 0.7), (146.8, 0.5), (174.6, 0.35), (220.0, 0.25)):
            pad += glide(n, f * (1 + 0.002 * np.sin(2 * np.pi * 0.3 * time(n) + f)), ((1, 1.0), (2, 0.3), (3, 0.12))) * a
        place(out, pad * ctl(n, [(0, 0), (0.5, 1), (1.4, 0.8), (2.1, 0)]), 0.0, 0.5)
        place(out, thud(s, 60, 0.8, 0.25, drop=0.2, body=1.0, grit=0.2), 0.0, 0.6)
        for f, at in ((880.0, 0.25), (698.5, 0.6), (1174.7, 1.0)):
            place(out, bell(s, f, 1.0, 0.6, 0.5), at, 0.12)
        place(out, vocal(s, 1.1, [(0, 340), (0.2, 480), (0.7, 500), (1.1, 400)], [(0, "u"), (0.3, "o"), (1.1, "u")],
                         [(0, 0), (0.2, 0.8), (0.8, 0.7), (1.1, 0)], 0.92, tilt=1.3, breath=0.3, vib=(5, 0.012)) * 0.12, 0.7, 1.0)
        rt, wet, tone = 1.6, 0.25, 4000
    elif ev == "dawn":  # morning relief: warm major arpeggio, pad, birds
        n = secs(1.9)
        pad = np.zeros(n)
        for f, a in ((130.8, 0.7), (196.0, 0.5), (261.6, 0.45), (329.6, 0.35)):
            pad += glide(n, f, ((1, 1.0), (2, 0.25), (3, 0.08))) * a
        place(out, pad * ctl(n, [(0, 0), (0.4, 1), (1.2, 0.8), (1.9, 0)]), 0.0, 0.35)
        for k, f in enumerate((523.3, 659.3, 784.0, 1046.5, 1318.5)):
            place(out, bell(s, f, 1.2, 0.7, 0.6), 0.05 + k * 0.11, 0.28 * (0.92 ** k))
        for k in range(3):
            m = secs(0.09)
            f0 = jit(s, 3200, 4400)
            tt = time(m)
            chirp = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.3 * np.sin(np.pi * tt / 0.09))) / SR) * np.sin(np.pi * tt / 0.09) ** 2
            place(out, chirp, 0.95 + k * 0.14 + jit(s, 0, 0.04), 0.07)
        rt, wet, tone = 1.2, 0.18, 7000
    elif ev == "harvest_tree":  # axe bites wood, the crown shivers
        place(out, wood_hit(s), 0.0)
        place(out, click(s, 0.03, 2000, 8000, 0.002), 0.0, 0.6)
        n = secs(0.45)
        place(out, rustle(s, n, ctl(n, [(0, 0), (0.06, 1), (0.45, 0)])), 0.04, 0.35)
    elif ev == "harvest_stone":  # pick on rock: bright clink and chips
        place(out, stone_hit(s), 0.0)
        f = jit(s, 2400, 3200)
        place(out, modal([f, f * 1.52, f * 2.3], [0.06, 0.04, 0.02], [1, 0.5, 0.3], 0.2, s.rng), 0.0, 0.4)
    elif ev == "harvest_fiber":  # grass torn up
        n = secs(0.3)
        place(out, rustle(s, n, ctl(n, [(0, 0), (0.04, 1), (0.3, 0)])), 0.0, 0.9)
        m = secs(0.12)
        rip = norm(band(s.noise(m), 800, 5000)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 95 * time(m)))) * ctl(m, [(0, 0), (0.02, 1), (0.12, 0)])
        place(out, rip, 0.08, 0.5)
    elif ev == "harvest_berry":  # bush rustle and a soft pluck pop
        n = secs(0.3)
        place(out, rustle(s, n, ctl(n, [(0, 0), (0.05, 1), (0.3, 0)])), 0.0, 0.7)
        m = secs(0.12)
        f = ctl(m, [(0, 380), (0.12, 900)])
        place(out, glide(m, f) * np.exp(-time(m) / 0.04) * np.minimum(time(m) / 0.003, 1), 0.12, 0.6)
    else:
        raise KeyError(ev)
    out = reverb(s, out, rt, wet, 0.008, tone)
    return out


COMBAT = {  # event: (takes, st-rms dBFS, max seconds)
    "swing_axe": (3, -20.0, 0.8), "swing_axe_heavy": (2, -19.0, 0.9), "swing_spear": (3, -20.5, 0.7),
    "swing_spear_heavy": (2, -19.5, 0.8), "swing_fist": (3, -21.5, 0.5), "swing_fist_heavy": (2, -20.5, 0.6),
    "hit_flesh": (3, -16.5, 0.7), "hit_stone": (3, -16.5, 0.9), "hit_wood": (3, -16.5, 0.8), "hit_spirit": (3, -17.5, 1.2),
    "block": (2, -17.0, 0.9), "dodge": (2, -20.0, 0.7), "critical": (2, -15.0, 1.5), "spawn": (2, -18.0, 1.6),
    "dissolve": (2, -18.5, 1.9), "player_hit": (3, -16.0, 0.7), "fuel": (2, -18.0, 1.8), "night": (1, -18.5, 2.2),
    "dawn": (1, -19.0, 2.2), "harvest_tree": (3, -18.0, 0.9), "harvest_stone": (3, -18.0, 0.9),
    "harvest_fiber": (3, -19.5, 0.6), "harvest_berry": (3, -19.5, 0.6),
}
HEARTBEAT_PERIOD = 0.8


def heartbeat_loop():
    """One lub-dub cycle that loops seamlessly (silence at both ends); pitch_scale speeds it up."""
    s = Synth(4242)
    n = secs(HEARTBEAT_PERIOD)
    out = np.zeros(n)
    for at, f, g in ((0.02, 58.0, 1.0), (0.2, 70.0, 0.7)):
        m = secs(0.34)
        t = time(m)
        beat = glide(m, f * (1 + 0.25 * np.exp(-t / 0.02)), ((1, 1.0), (2, 0.55), (3, 0.3), (4, 0.15)))
        beat *= np.minimum(t / 0.006, 1) * np.exp(-t / 0.055) * np.clip((0.34 - t) / 0.12, 0, 1)
        beat += norm(low(s.noise(m), 260)) * np.exp(-t / 0.02) * 0.25
        place(out, beat, at, g)
    out = low(out, 900)
    tail = secs(0.12)
    out[-tail:] *= np.linspace(1, 0, tail)
    out[: secs(0.004)] *= np.linspace(0, 1, secs(0.004))
    return level(out, -18.0)


# --------------------------------------------------------------------------- hero voice
HERO = dict(f0=345.0, scale=1.17)


def hero(ev, take):
    s = Synth((sum(map(ord, "hero" + ev)) * 2654435761 + take * 97) % (2 ** 31))
    p = jit(s, 0.96, 1.05) * HERO["f0"]
    sc = HERO["scale"] * jit(s, 0.98, 1.03)
    out = np.zeros(secs(2.0))
    kw = dict(tilt=1.15, breath=0.12, jitter=0.004, fmax=9000)
    rt, wet = 0.3, 0.05

    def h(at, L=0.035, g=0.35, fc=2600):  # breathy "h" onset
        place(out, breathy(s, L, [(0, fc), (L, fc * 0.9)], [(0, 0), (L * 0.4, 1), (L, 0.5)], 0.9), at, g)

    if ev == "attack":  # "hup!" / "hap!" / "heup!"
        v = ["eo", "a", "eu"][take % 3]
        h(0.0)
        L = 0.12
        place(out, vocal(s, L, [(0, p * 1.05), (0.04, p * 1.18), (L, p * 1.08)], [(0, v), (L, "u")], [(0, 0), (0.012, 1), (L - 0.02, 0.9), (L, 0)], sc, **kw), 0.025)
        place(out, click(s, 0.02, 400, 2500, 0.002), 0.025 + L, 0.12)  # lip closure
    elif ev == "attack_heavy":  # "hyah!"
        h(0.0, 0.04, 0.4)
        L = 0.24
        place(out, vocal(s, L, [(0, p * 1.0), (0.06, p * 1.32), (L, p * 1.05)], [(0, "i"), (0.05, "a"), (L, "a")], [(0, 0), (0.015, 1), (0.16, 0.9), (L, 0)], sc, **kw), 0.03)
    elif ev == "hurt":  # "ah!" / "eup!" / "ow"
        v = [("a", "a"), ("eu", "u"), ("a", "u")][take % 3]
        L = 0.2 + 0.04 * take
        place(out, vocal(s, L, [(0, p * 1.42), (0.03, p * 1.5), (L, p * 1.0)], [(0, v[0]), (L, v[1])], [(0, 0), (0.008, 1), (L * 0.5, 0.7), (L, 0)], sc,
                         tilt=1.05, breath=0.22, jitter=0.01, fmax=9000), 0.0)
        place(out, breathy(s, 0.15, [(0, 1600), (0.15, 1200)], [(0, 0.6), (0.15, 0)], 0.8), L - 0.02, 0.2)
    elif ev == "pickup":  # happy "oh!" / "ung!"
        v = ["o", "eu"][take % 2]
        L = 0.2
        place(out, vocal(s, L, [(0, p * 1.0), (0.12, p * 1.38), (L, p * 1.32)], [(0, "m" if take else v), (0.03, v), (L, v)], [(0, 0), (0.02, 1), (L - 0.04, 0.9), (L, 0)], sc, **kw), 0.0)
    elif ev == "harvest":  # effort "hn!" / "eung" / "hup"
        h(0.0, 0.03, 0.3, 1800)
        L = 0.14 + 0.02 * take
        v = [("n", "eu"), ("eu", "n"), ("eo", "m")][take % 3]
        place(out, vocal(s, L, [(0, p * 0.98), (0.05, p * 1.1), (L, p * 0.96)], [(0, v[0]), (L * 0.5, v[1]), (L, v[1])], [(0, 0), (0.015, 1), (L, 0)], sc,
                         tilt=1.3, breath=0.15, fmax=7000), 0.02)
    elif ev == "dodge":  # quick exhale "hp!"
        h(0.0, 0.07, 0.6, 2200)
        L = 0.07
        place(out, vocal(s, L, [(0, p * 1.2), (L, p * 1.25)], "eu", [(0, 0), (0.01, 0.7), (L, 0)], sc, **kw), 0.04)
    elif ev == "tired":  # "hah... hah..."
        for k in range(2):
            at = k * 0.42
            L = 0.28
            place(out, breathy(s, L, [(0, 1500), (L, 1100)], [(0, 0), (0.04, 1), (L, 0)], 0.6), at, 0.8)
            place(out, vocal(s, L, [(0, p * 1.02), (L, p * 0.85)], "a", [(0, 0), (0.04, 0.35), (L, 0)], sc, tilt=1.4, breath=0.75), at, 0.5)
            place(out, breathy(s, 0.1, [(0, 2400), (0.1, 2800)], [(0, 0), (0.05, 0.4), (0.1, 0)], 0.5), at + 0.3, 0.25)  # in-breath
    elif ev == "eat":  # contented "mm~!"
        L = 0.38
        place(out, vocal(s, L, [(0, p * 1.0), (0.15, p * 1.25), (L, p * 1.1)], "m", [(0, 0), (0.04, 1), (0.3, 0.8), (L, 0)], sc, tilt=1.6, breath=0.1, fmax=5000), 0.0)
    elif ev == "faint":  # "aww..."
        L = 0.75
        place(out, vocal(s, L, [(0, p * 1.25), (0.1, p * 1.3), (L, p * 0.8)], [(0, "a"), (0.4, "a"), (L, "u")], [(0, 0), (0.03, 1), (0.5, 0.6), (L, 0)], sc,
                         tilt=1.2, breath=0.3, vib=(5, 0.015)), 0.0)
        place(out, breathy(s, 0.3, [(0, 1200), (0.3, 800)], [(0, 0.5), (0.3, 0)], 0.8), L - 0.05, 0.3)
    elif ev == "reward":  # bright arpeggio + sparkle
        for k, f in enumerate((784.0, 987.8, 1174.7, 1568.0)):
            place(out, bell(s, f, 1.0, 0.55, 0.8), k * 0.075, 0.32 * (0.95 ** k))
        n = secs(0.8)
        place(out, tinkles(s, n, 30, 4000, 10000, ctl(n, [(0, 0), (0.25, 1), (0.8, 0)])), 0.15, 0.5)
        rt, wet = 0.8, 0.12
    elif ev == "levelup":  # rising run, sustained chord, upward shimmer
        for k, f in enumerate((523.3, 659.3, 784.0, 1046.5, 1318.5)):
            place(out, bell(s, f, 1.3, 0.75, 0.8), k * 0.08, 0.3 * (0.94 ** k))
        n = secs(1.0)
        chord = sum(glide(n, f, ((1, 1.0), (2, 0.2))) for f in (523.3, 659.3, 784.0)) * ctl(n, [(0, 0), (0.15, 1), (1.0, 0)])
        place(out, chord, 0.4, 0.12)
        place(out, nsweep(s, n, ctl(n, [(0, 2000), (1.0, 8000)]), 0.4) * ctl(n, [(0, 0), (0.6, 1), (1.0, 0)]), 0.35, 0.18)
        place(out, tinkles(s, n, 35, 4000, 10000, ctl(n, [(0, 0), (0.5, 1), (1.0, 0)])), 0.4, 0.5)
        rt, wet = 1.0, 0.14
    else:
        raise KeyError(ev)
    return reverb(s, out, rt, wet, 0.006, 7000)


HERO_EVENTS = {  # event: (takes, st-rms dBFS, max seconds)
    "attack": (3, -19.0, 0.5), "attack_heavy": (2, -18.5, 0.6), "hurt": (3, -18.0, 0.7), "pickup": (2, -19.5, 0.6),
    "harvest": (3, -20.5, 0.5), "dodge": (2, -21.0, 0.5), "tired": (2, -22.0, 1.3), "eat": (2, -20.0, 0.8),
    "faint": (1, -18.5, 1.4), "reward": (1, -19.0, 1.8), "levelup": (1, -18.5, 2.2),
}


# --------------------------------------------------------------------------- NPC babble
# f0 Hz, formant scale, tilt (higher = softer), breath, syllable seconds, bounce (pitch rise inside
# the syllable), shadow (breathy, hollow, chorused), vib (Hz, depth), rough, gap (min seconds
# between syllables at runtime), db (runtime trim).
VOICE_CAST = {
    "naru": dict(f0=290, fs=1.12, tilt=1.0, breath=0.08, dur=0.072, bounce=0.07, gap=0.068),
    "sora": dict(f0=360, fs=1.2, tilt=1.25, breath=0.14, dur=0.082, bounce=0.04, vib=(6.0, 0.015), gap=0.078),
    "moru": dict(f0=125, fs=0.9, tilt=0.9, breath=0.1, dur=0.09, bounce=0.03, rough=0.12, gap=0.085),
    "haeru": dict(f0=205, fs=1.0, tilt=1.15, breath=0.12, dur=0.088, bounce=-0.05, gap=0.082),
    "villager": dict(f0=260, fs=1.1, tilt=1.1, breath=0.1, dur=0.078, bounce=0.04, gap=0.074),
    "postman": dict(f0=235, fs=1.05, dur=0.07, bounce=0.05, gap=0.066, shadow=True),
    "sweeper": dict(f0=175, fs=0.98, dur=0.085, breath=0.5, bounce=0.0, gap=0.082, shadow=True),
    "fisher": dict(f0=155, fs=0.95, dur=0.09, bounce=-0.04, gap=0.085, shadow=True),
    "kid": dict(f0=430, fs=1.32, dur=0.065, bounce=0.1, gap=0.062, shadow=True),
    "farmer": dict(f0=185, fs=1.0, dur=0.085, bounce=0.02, gap=0.08, shadow=True),
    "regular": dict(f0=255, fs=1.08, dur=0.08, bounce=0.03, gap=0.076, shadow=True),
    "miller": dict(f0=128, fs=0.92, dur=0.095, bounce=-0.02, gap=0.09, shadow=True),
    "stargazer": dict(f0=300, fs=1.15, dur=0.09, breath=0.55, bounce=0.05, vib=(5.0, 0.02), sparkle=True, gap=0.086, shadow=True),
    "gardener": dict(f0=275, fs=1.12, dur=0.08, bounce=0.04, gap=0.076, shadow=True),
    "shopkeeper": dict(f0=245, fs=1.06, dur=0.068, bounce=0.06, gap=0.064, shadow=True),
    "scout": dict(f0=215, fs=1.02, dur=0.072, bounce=0.03, gap=0.068, shadow=True),
    "lamplighter": dict(f0=195, fs=1.0, dur=0.085, bounce=0.02, gap=0.08, shadow=True),
    "gentleman": dict(f0=112, fs=0.9, dur=0.095, bounce=-0.03, gap=0.092, shadow=True),
    "poet": dict(f0=245, fs=1.08, dur=0.09, bounce=0.05, vib=(5.0, 0.035), gap=0.086, shadow=True),
    "stroller": dict(f0=170, fs=0.97, dur=0.09, breath=0.6, bounce=-0.02, gap=0.088, shadow=True),
    "shadow": dict(f0=210, fs=1.02, dur=0.08, bounce=0.02, gap=0.078, shadow=True),
}


def syllable(s, cfg, onset, vowel):
    shadow = cfg.get("shadow", False)
    f0 = cfg["f0"] * jit(s, 0.985, 1.015)
    fs = cfg["fs"]
    breath = cfg.get("breath", 0.42 if shadow else 0.1)
    L = cfg["dur"]
    pre = {"v": 0.0, "n": 0.0, "p": 0.012, "s": 0.026 if not shadow else 0.032}[onset]
    # The fricative overlaps the vowel a little; the whole syllable always fits its bank slot.
    L = min(L - 0.5 * pre, SLOT - 0.016 - pre)
    n_total = secs(pre + L + 0.006)
    out = np.zeros(n_total)
    if onset == "s":
        m = secs(pre + 0.01)
        hi = 5200 if vowel in ("i", "e") else 4200
        fr = nsweep(s, m, hi, 0.45) * ctl(m, [(0, 0), (pre * 0.6, 1), (pre + 0.01, 0)])
        place(out, fr, 0.0, 0.35 if not shadow else 0.45)
    if onset == "p":
        lo = 2500 if vowel in ("i", "e") else 1200
        place(out, click(s, 0.015, lo, lo * 2.5, 0.0025), pre - 0.008, 0.5)
    n = secs(L)
    b = cfg.get("bounce", 0.04)
    f_pts = [(0, f0 * (1 - b * 0.4)), (L * 0.4, f0 * (1 + b)), (L, f0 * (1 + b * 0.2))]
    seq = [(0, "m" if onset == "n" else ("eu" if onset == "p" else vowel)), (0.022 if onset in ("n", "p") else 0.0, vowel), (L, vowel)]
    attack = 0.01 if onset == "v" else (0.004 if onset == "p" else 0.008)
    amp = [(0, 0), (attack, 0.55 if onset == "n" else 1.0), (0.025, 1.0), (L - 0.022, 0.85), (L, 0)]
    v = voice(s, n, ctl(n, f_pts, 0.004), tracks(n, seq, fs), ctl(n, amp, 0.003), tilt=cfg.get("tilt", 1.2 if shadow else 1.1),
              breath=breath, jitter=0.004, shimmer=0.03, fmax=7500, odd=0.45 if shadow else 0.0,
              vib=cfg.get("vib", (0.0, 0.0)), sub=cfg.get("rough", 0.0), flutter=cfg.get("rough", 0.0))
    if shadow:  # hollow chorus: a second, slightly detuned and delayed voice
        v2 = voice(s, n, ctl(n, f_pts, 0.004) * 1.012, tracks(n, seq, fs * 0.97), ctl(n, amp, 0.003), tilt=1.3, breath=breath, jitter=0.006, fmax=6000, odd=0.5)
        v = v * 0.75 + np.concatenate([np.zeros(secs(0.006)), v2[: n - secs(0.006)]]) * 0.45
    if cfg.get("sparkle"):
        v += glide(n, f0 * 8.02) * ctl(n, amp) * 0.05
    place(out, v, pre, 1.0)
    return fades(out, 0.002, 0.008)


def voice_bank(name):
    cfg = VOICE_CAST[name]
    s = Synth(sum(map(ord, name)) * 6151)
    slot = secs(SLOT)
    bank = np.zeros(slot * len(ONSETS) * len(VOWEL_ORDER))
    sylls = []
    for oi, onset in enumerate(ONSETS):
        for vi, vowel in enumerate(VOWEL_ORDER):
            x = syllable(s, cfg, onset, vowel)
            x = level(x, -17.0, window=0.04)
            assert x.size <= slot - secs(0.008), (name, onset, vowel, x.size / SR)
            k = oi * len(VOWEL_ORDER) + vi
            bank[k * slot: k * slot + x.size] = x
            sylls.append(x)
    return bank, sylls


def resample_to(x, sr):
    from math import gcd
    g = gcd(SR, sr)
    return ss.resample_poly(x, sr // g, SR // g)


# --------------------------------------------------------------------------- checks + output
def check(path: Path, x: np.ndarray, sr: int, loop=False):
    problems = []
    size = path.stat().st_size
    if size >= MAX_BYTES:
        problems.append(f"{size} bytes")
    pk = float(np.max(np.abs(x)))
    if pk > 0.95:
        problems.append(f"peak {pk:.3f}")
    if not loop and (abs(x[0]) > 0.01 or abs(x[-1]) > 0.01):
        problems.append("edge click")
    if abs(float(np.mean(x))) > 0.01:
        problems.append("dc")
    # Click scan: a sample step far above the local high-frequency level.
    d = np.abs(np.diff(x))
    local = maximum_filter1d(d, max(3, sr // 400))
    smooth = np.convolve(d, np.ones(64) / 64, mode="same") + 1e-4
    if np.max(local / smooth) > 400:
        problems.append("possible click")
    return problems


def emit(path: Path, x, sr, entries, label, report, loop=False):
    write(path, x, sr)
    probs = check(path, x, sr, loop)
    st = 20 * np.log10(short_rms_peak(x) + 1e-12) if sr == SR else float("nan")
    report.append(dict(file=str(path.relative_to(ROOT)).replace("\\", "/"), seconds=round(x.size / sr, 3),
                       kb=round(path.stat().st_size / 1024, 1), peak_db=round(20 * np.log10(np.max(np.abs(x)) + 1e-12), 1),
                       st_rms_db=round(st, 1), problems=probs))
    if entries is not None:
        entries.append((label, x if sr == SR else resample_to(x, SR)))
    flag = ("  !! " + ", ".join(probs)) if probs else ""
    print(f"{label:34s} {x.size / sr:5.2f}s {path.stat().st_size / 1024:6.1f} KB  pk {20 * np.log10(np.max(np.abs(x)) + 1e-12):6.1f}  st {st:6.1f}{flag}")
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", action="store_true")
    ap.add_argument("--only", default="creatures,combat,hero,voice")
    args = ap.parse_args()
    groups = set(args.only.split(","))
    report = []
    sheets = {}
    REVIEW.mkdir(parents=True, exist_ok=True)
    if "creatures" in groups:
        for sp in SPECIES:
            entries = []
            for ev in EVENTS:
                for region in REGIONS:
                    for take in range(TAKES):
                        x = creature(sp, ev, region, take)
                        emit(SFX / "creatures" / f"{sp}_{ev}_{region}_{take + 1}.wav", x, SR, entries, f"{sp}_{ev}_{region}_{take + 1}", report)
            sheets[f"creatures_{sp}"] = entries
    if "combat" in groups:
        entries = []
        for ev, (takes, db, mx) in COMBAT.items():
            for take in range(takes):
                x = level(trim(combat(ev, take), mx), db)
                emit(SFX / "combat" / f"{ev}_{take + 1}.wav", x, SR, entries, f"{ev}_{take + 1}", report)
        emit(SFX / "combat" / "heartbeat_loop.wav", heartbeat_loop(), SR, entries, "heartbeat_loop", report, loop=True)
        sheets["combat"] = entries
    if "hero" in groups:
        entries = []
        for ev, (takes, db, mx) in HERO_EVENTS.items():
            for take in range(takes):
                x = level(trim(hero(ev, take), mx), db, window=0.06 if ev not in ("reward", "levelup", "tired") else 0.12)
                emit(SFX / "hero" / f"{ev}_{take + 1}.wav", x, SR, entries, f"{ev}_{take + 1}", report)
        sheets["hero"] = entries
    if "voice" in groups:
        entries = []
        for name in VOICE_CAST:
            bank, sylls = voice_bank(name)
            x = resample_to(bank, VOICE_SR)
            x = np.clip(x, -0.95, 0.95)
            emit(SFX / "voice" / f"{name}.wav", x, VOICE_SR, None, f"voice/{name}", report)
            # Review: a phrase made of the bank ("a e i o u" with mixed onsets) at the runtime gap.
            cfg = VOICE_CAST[name]
            phrase = np.zeros(secs(1.6))
            order = [(0, 0), (2, 3), (1, 1), (3, 2), (0, 4), (2, 5), (1, 0), (0, 6), (3, 3), (2, 1), (1, 2), (0, 0)]
            for k, (o, v) in enumerate(order):
                place(phrase, sylls[o * len(VOWEL_ORDER) + v], k * cfg["gap"] * 1.25, 1.0)
            entries.append((f"voice/{name}", phrase))
        sheets["voice"] = entries
        layout = dict(sample_rate=VOICE_SR, slot_seconds=SLOT, onsets=ONSETS, vowels=VOWEL_ORDER,
                      voices={k: dict(gap=v["gap"], shadow=bool(v.get("shadow", False))) for k, v in VOICE_CAST.items()})
        (REVIEW / "voice_bank_layout.json").write_text(json.dumps(layout, indent=1), encoding="utf-8")
    bad = [r for r in report if r["problems"]]
    total = sum(r["kb"] for r in report)
    print(f"files {len(report)}  total {total / 1024:.2f} MB  problems {len(bad)}")
    (REVIEW / f"report_{'_'.join(sorted(groups))}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    if args.sheets:
        for name, entries in sheets.items():
            V.sheet(entries, REVIEW / f"{name}.png")
            print("sheet", REVIEW / f"{name}.png")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
