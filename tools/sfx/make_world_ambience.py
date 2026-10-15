"""make_world_ambience: long looping ambience beds and the random one-shots that play over them
(world_audio.gd, ambience_spots.gd).

    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\make_world_ambience.py                 # beds + one-shots
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\make_world_ambience.py --only beds
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\make_world_ambience.py --only coast,bird,gull --scratch

Beds -> game/assets/sfx/ambience/<name>.wav: 60 s (coast, wind and their muffled copies 64 s), mono
16-bit, periodic BY CONSTRUCTION: every noise layer is shaped in the frequency domain over the whole
loop, every slow envelope is a sum of whole cycles of the loop, every event wraps around the end and
reverbs are circular convolutions, so the last sample runs straight into the first (no crossfade,
no seam). Identifiable events (a bird phrase, a wave crash, a gust, a cricket) are NOT in the beds;
they are one-shots that ambience_spots.gd scatters at random times and places. Beds are levelled to
-20 dBFS long-term RMS (world_audio.gd BED_DB sets the in-game balance). Sample rates follow the
content and the size budget: the bright beds (birds, insects, night crickets, forest leaves,
waterfall spray, hearth crackle) 22050, coast 16000, the rest 11025 or lower (dark beds). Texture
grain sizes are given at 11025 Hz and scaled (smp()), so a bed keeps its character at any rate.

One-shots -> game/assets/sfx/ambience/spots/<kind>_<n>.wav: designed families (species / call
pattern / break shape / gust shape grids) rendered through tools/sfx/diverse.py, which keeps only
candidates that sfx_qa would not call near-identical. Levelled to st-rms -12 dBFS (ONE_SHOT_DB).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from scipy import signal as ss

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402
import diverse as D  # noqa: E402

OUT = L.SFX_ROOT / "ambience"
SPOTS = OUT / "spots"
BED_RMS = 0.1            # -20 dBFS long-term
ONE_SHOT_DB = -12.0
CTRL = 50                # control rate of slow envelopes (Hz)


# =========================================================================== periodic helpers
def rms(x):
    return math.sqrt(float(np.mean(x * x))) + 1e-12


def smp(sr, n_at_11025):
    """A texture grain length given in samples at 11025 Hz, at sample rate sr."""
    return max(1, int(round(n_at_11025 * sr / 11025.0)))


def fmask(n, sr, lo=None, hi=None, color="white", order=2):
    f = np.fft.rfftfreq(n, 1.0 / sr)
    fs = np.maximum(f, 1e-3)
    m = np.ones_like(f)
    if color == "pink":
        m /= np.sqrt(np.maximum(f, 20.0))
    elif color == "brown":
        m /= np.maximum(f, 20.0)
    if lo:
        m /= np.sqrt(1.0 + (lo / fs) ** (2 * order))
    if hi:
        m /= np.sqrt(1.0 + (f / hi) ** (2 * order))
    m[0] = 0.0
    return m


def cnoise(rng, n, sr, lo=None, hi=None, color="white", order=2):
    """Periodic coloured noise over n samples, RMS 0.25."""
    X = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    y = np.fft.irfft(X * fmask(n, sr, lo, hi, color, order), n)
    return y * (0.25 / rms(y))


def cfilt(x, sr, lo=None, hi=None, order=2):
    """Zero-phase circular band filter (keeps a loop seamless)."""
    return np.fft.irfft(np.fft.rfft(x) * fmask(x.size, sr, lo, hi, "white", order), x.size)


def cpeak(x, sr, f0, q, gain):
    """Circular resonant boost: adds `gain` x a narrow band around f0 (bandwidth f0/q)."""
    f = np.fft.rfftfreq(x.size, 1.0 / sr)
    bw = f0 / q
    return np.fft.irfft(np.fft.rfft(x) * (1.0 + gain * np.exp(-0.5 * ((f - f0) / bw) ** 2)), x.size)


def cenv(rng, dur, rate_max, rate_min=0.0, slope=0.5):
    """Periodic slow random envelope (0..1) at the control rate: whole cycles of the loop only."""
    m = int(round(dur * CTRL))
    F = np.zeros(m // 2 + 1, complex)
    k0 = max(1, int(round(rate_min * dur)))
    k1 = max(k0, int(round(rate_max * dur)))
    k = np.arange(k0, k1 + 1)
    F[k] = (rng.standard_normal(k.size) + 1j * rng.standard_normal(k.size)) / k ** slope
    e = np.fft.irfft(F, m)
    return (e - e.min()) / (e.max() - e.min() + 1e-12)


def up(e, n):
    """Periodic linear interpolation of a control-rate envelope to n samples."""
    m = e.size
    return np.interp(np.arange(n) * (m / n), np.arange(m + 1), np.append(e, e[0]))


def cplace(out, sig, at):
    """Add sig into out at sample `at`, wrapping past the end."""
    n = out.size
    at = int(at) % n
    s = np.asarray(sig, float)
    while s.size:
        k = min(s.size, n - at)
        out[at:at + k] += s[:k]
        s = s[k:]
        at = 0
    return out


def times_by(rng, env, n, count, min_gap=0):
    """`count` event positions (samples) drawn with density ~ env (control-rate array)."""
    w = env + 1e-6
    idx = rng.choice(env.size, size=count, p=w / w.sum())
    t = np.sort((idx + rng.random(count)) * (n / env.size)).astype(int)
    if min_gap and t.size:
        keep = [t[0]]
        for v in t[1:]:
            if v - keep[-1] >= min_gap:
                keep.append(v)
        t = np.array(keep)
    return t


def cconv(x, ir):
    """Circular convolution (reverb that wraps around the loop)."""
    n = x.size
    h = np.zeros(n)
    h[:min(n, ir.size)] = ir[:n]
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(h), n)


def ir_room(rng, sr, rt60, tone=5000.0, predelay=0.01):
    k = L.secs(rt60 * 1.1, sr)
    t = np.arange(k) / sr
    nz = rng.standard_normal(k)
    ir = L.lp(nz, sr, tone, 2) * np.exp(-6.9 * t / rt60)
    ir = np.concatenate([np.zeros(L.secs(predelay, sr)), ir])
    return ir / math.sqrt(float(np.sum(ir * ir)))


def creverb(x, rng, sr, rt60, wet, tone=5000.0):
    w = cconv(x, ir_room(rng, sr, rt60, tone))
    return x + wet * w * (rms(x) / rms(w))


def resample_loop(x, n_out):
    """FFT resampling: exact for a periodic signal, so the loop stays seamless."""
    return ss.resample(x, n_out)


def chirp_tone(sr, dur, f0, f1, harm=((1, 1.0), (2, 0.12)), shape=1.0, curve="exp"):
    n = max(8, L.secs(dur, sr))
    u = np.linspace(0, 1, n, endpoint=False)
    f = f0 * (f1 / f0) ** (u ** shape) if curve == "exp" else f0 + (f1 - f0) * u ** shape
    y = L.osc(sr, f, harm)
    e = np.clip(np.sin(np.pi * u), 0, None) ** 1.5
    return y * e


def tick(rng, sr, f_lo, f_hi, tau=(0.0006, 0.0018), noise_mix=0.4):
    f = math.exp(rng.uniform(math.log(f_lo), math.log(f_hi)))
    ta = rng.uniform(*tau)
    m = int(ta * 7 * sr) + 8
    t = np.arange(m) / sr
    g = np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / ta)
    k = min(m, 20)
    g[:k] += rng.standard_normal(k) * np.exp(-np.arange(k) / 4.0) * noise_mix
    return g


def finish_bed(x, sr):
    y = x - float(np.mean(x))
    y *= BED_RMS / rms(y)
    if np.max(np.abs(y)) > L.CEILING:
        y = L.limit(y, sr, L.CEILING)
    return np.clip(y, -L.CEILING, L.CEILING)


# =========================================================================== beds
def chirp_event(rng, sr, far):
    """One tiny bird sound for a bed texture: a chip, a slur or a short twitter (2-4 chips)."""
    kind = rng.integers(0, 4)
    f0 = rng.uniform(2400, 6200)
    if kind == 0:
        y = chirp_tone(sr, rng.uniform(0.015, 0.04), f0, f0 * rng.uniform(0.7, 1.45))
    elif kind == 1:
        y = chirp_tone(sr, rng.uniform(0.05, 0.12), f0, f0 * rng.uniform(0.8, 1.25), shape=rng.uniform(0.5, 2.0))
    else:
        parts = []
        for _ in range(rng.integers(2, 5)):
            g = chirp_tone(sr, rng.uniform(0.012, 0.03), f0 * rng.uniform(0.9, 1.1), f0 * rng.uniform(0.75, 1.3))
            parts.append(np.concatenate([g, np.zeros(L.secs(rng.uniform(0.015, 0.05), sr))]))
        y = np.concatenate(parts)
    cut = rng.uniform(1800, 3500) if far else rng.uniform(3500, 9000)
    return L.lp(y, sr, min(cut, sr * 0.45), 1)


def bed_birds(rng, sr, dur, far):
    n = L.secs(dur, sr)
    out = np.zeros(n)
    air = cnoise(rng, n, sr, 250, 1200 if far else 4500, "pink") * up(0.4 + 0.6 * cenv(rng, dur, 0.12), n)
    out += air * (0.18 if far else 0.12)
    busy = cenv(rng, dur, 0.08) ** 1.5
    count = int(dur * (7.0 if far else 4.0))
    for t in times_by(rng, busy, n, count):
        d = rng.uniform(0.15, 0.55) if far else rng.uniform(0.12, 1.0) ** 1.6
        cplace(out, chirp_event(rng, sr, far or d < 0.3) * d, t)
    for t in times_by(rng, busy, n, int(dur / 5)):      # a few soft far warbles
        m = L.secs(rng.uniform(0.3, 0.7), sr)
        tt = np.arange(m) / sr
        f = rng.uniform(2200, 3600) * (1 + 0.12 * np.sin(2 * np.pi * rng.uniform(6, 14) * tt) + 0.08 * np.sin(2 * np.pi * rng.uniform(1, 3) * tt))
        w = L.osc(sr, f, ((1, 1.0), (2, 0.1))) * np.clip(np.sin(np.pi * tt / tt[-1]), 0, None) ** 2
        cplace(out, L.lp(w, sr, 2500, 1) * rng.uniform(0.06, 0.15), t)
    return creverb(out, rng, sr, 1.1 if far else 0.8, 0.6 if far else 0.25, 3500 if far else 6000)


def bed_insects(rng, sr, dur):
    n = L.secs(dur, sr)
    out = np.zeros(n)
    for fc, rate, g in ((4150.0, 14.0, 1.0), (4900.0, 17.5, 0.8), (3550.0, 11.0, 0.5)):
        band = cpeak(cnoise(rng, n, sr, fc * 0.9, fc * 1.1, order=4), sr, fc, 40, 6.0)
        t = np.arange(n) / sr
        r = round(rate * dur) / dur                                   # whole cycles of the loop
        puls = (0.5 + 0.5 * np.sin(2 * np.pi * r * t + rng.uniform(0, 6.28))) ** 2
        out += band * puls * up(0.3 + 0.7 * cenv(rng, dur, 0.05), n) * g
    # a far cicada buzz swelling in and out
    t = np.arange(n) / sr
    buzz = cnoise(rng, n, sr, 3000, 4000, order=4) * (0.6 + 0.4 * np.sin(2 * np.pi * round(150 * dur) / dur * t))
    out += buzz * up(cenv(rng, dur, 0.15, 0.03) ** 3, n) * 0.7
    # a far cricket carpet: many tiny chirps, none close
    for tt in times_by(rng, np.ones(100), n, int(dur * 9)):
        f = rng.uniform(3800, 5000)
        m = L.secs(0.016, sr)
        p = np.sin(2 * np.pi * f * np.arange(m) / sr) * np.sin(np.pi * np.arange(m) / m)
        burst = np.concatenate([np.concatenate([p, np.zeros(L.secs(0.014, sr))]) for _ in range(rng.integers(2, 5))])
        cplace(out, burst * rng.uniform(0.03, 0.12), tt)
    return creverb(out, rng, sr, 0.9, 0.35, 4500)


def croak(rng, sr, low=False):
    dur = rng.uniform(0.12, 0.3) if not low else rng.uniform(0.3, 0.6)
    m = L.secs(dur, sr)
    t = np.arange(m) / sr
    f0 = rng.uniform(90, 160) if low else rng.uniform(380, 900)
    rate = rng.uniform(30, 70) if not low else rng.uniform(12, 25)
    car = L.osc(sr, np.full(m, f0), ((1, 1.0), (2, 0.5), (3, 0.3)))
    am = (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * rate * t))) * np.clip(np.sin(np.pi * t / dur), 0, None) ** 0.8
    return L.lp(car * am, sr, 1500 if not low else 600, 2)


def bed_night(rng, sr, dur):
    n = L.secs(dur, sr)
    out = cnoise(rng, n, sr, 60, 700, "pink") * up(0.5 + 0.5 * cenv(rng, dur, 0.06), n) * 0.12
    busy = cenv(rng, dur, 0.06) ** 2
    for t in times_by(rng, busy, n, int(dur * 2.2)):              # far frog chorus
        cplace(out, croak(rng, sr, rng.random() < 0.08) * rng.uniform(0.03, 0.1), t)
    for t in times_by(rng, np.ones(100), n, int(dur * 6)):        # very far crickets
        f = rng.uniform(3600, 4800)
        m = L.secs(0.018, sr)
        p = np.sin(2 * np.pi * f * np.arange(m) / sr) * np.sin(np.pi * np.arange(m) / m)
        burst = np.concatenate([np.concatenate([p, np.zeros(L.secs(0.016, sr))]) for _ in range(rng.integers(2, 4))])
        cplace(out, burst * rng.uniform(0.03, 0.08), t)
    return creverb(out, rng, sr, 1.3, 0.55, 3000)


def bed_coast(rng, sr, dur):
    n = L.secs(dur, sr)
    swell = cenv(rng, dur, 0.16, 0.04, 0.3)                       # irregular, never the same twice
    sw = up(0.3 + 0.7 * swell ** 1.4, n)
    lag = up(np.roll(0.25 + 0.75 * swell, int(1.2 * CTRL)), n)
    out = cnoise(rng, n, sr, 45, 320, "brown") * lag * 0.9         # deep rumble
    out += cnoise(rng, n, sr, 200, 1500, "pink") * sw * 0.9         # body of the surf
    out += cnoise(rng, n, sr, 1500, 6500) * sw ** 2 * 0.35          # wash hiss
    fizz_env = np.clip(np.diff(np.append(swell, swell[0])) * -CTRL, 0, None)
    fizz_env = np.convolve(np.concatenate([fizz_env, fizz_env[:40]]), np.ones(40) / 40, "same")[:swell.size]
    fizz_env = fizz_env / (fizz_env.max() + 1e-9)
    grains = np.repeat(rng.random(n // 60 + 2), 60)[:n] ** 3
    out += cnoise(rng, n, sr, 2500, 7000) * up(fizz_env, n) * grains * 0.9   # foam fizz after each swell
    return out


def bed_wind(rng, sr, dur):
    n = L.secs(dur, sr)
    I = cenv(rng, dur, 0.12, 0.015, 0.45)                         # slow irregular strength, no gust peaks
    i = up(0.35 + 0.65 * I, n)
    out = cnoise(rng, n, sr, 50, 200, "pink") * i * 1.2
    out += cnoise(rng, n, sr, 200, 520, "pink") * i ** 1.6 * 0.9
    out += cnoise(rng, n, sr, 520, 1300, "pink") * i ** 2.4 * 0.6
    out += cnoise(rng, n, sr, 1300, 3500) * i ** 3.2 * 0.25
    for k, fc in enumerate((480.0, 590.0, 720.0, 860.0)):        # a faint whistle that rises with strength
        wt = np.exp(-0.5 * ((up(I, n) - k / 3.0) / 0.22) ** 2) * i ** 3
        out += cpeak(cnoise(rng, n, sr, fc * 0.95, fc * 1.05, order=4), sr, fc, 60, 3.0) * wt * 0.12
    return out


def bed_waterfall(rng, sr, dur):
    n = L.secs(dur, sr)
    surge = up(0.85 + 0.15 * cenv(rng, dur, 0.25, 0.03), n)
    out = cnoise(rng, n, sr, 40, 220, "brown") * 0.8
    a, b = smp(sr, 220), smp(sr, 200)
    g = np.repeat(rng.random(n // a + 2), a)[:n]
    g = np.convolve(np.concatenate([g, g[:b]]), np.ones(b) / b, "same")[:n]
    out += cnoise(rng, n, sr, 450, 2400, "pink") * (0.6 + 1.2 * g ** 2) * 0.9
    out += cnoise(rng, n, sr, 2400, 5200) * 0.3
    for t in times_by(rng, np.ones(100), n, int(dur * 25)):        # spray droplets
        cplace(out, tick(rng, sr, 900, 3500, (0.002, 0.005), 0.2) * rng.uniform(0.05, 0.2), t)
    return out * surge


def bed_room(rng, sr, dur):
    n = L.secs(dur, sr)
    drift = up(0.88 + 0.12 * cenv(rng, dur, 0.05), n)
    return (cnoise(rng, n, sr, 30, 120, "brown") * 1.6 + cnoise(rng, n, sr, 220, 900, "pink") * 0.12) * drift


def leaves_layer(rng, n, sr, dur, I, lo=1600, hi=5200):
    i = up(I, n)
    a, b = smp(sr, 70), smp(sr, 30)
    g = np.repeat(rng.random(n // a + 2), a)[:n] ** 2.5              # many small leaves, each its own flick
    g = np.convolve(np.concatenate([g, g[:b]]), np.ones(b) / b, "same")[:n]
    return cnoise(rng, n, sr, lo, hi) * (0.3 + 1.6 * g) * i ** 1.7


def wood_creak(rng, sr, dur, f_lo=180, f_hi=520, rate=(25, 70)):
    m = L.secs(dur, sr)
    t = np.arange(m) / sr
    r = np.linspace(rng.uniform(*rate), rng.uniform(*rate), m) * (1 + 0.2 * np.sin(2 * np.pi * rng.uniform(0.5, 2) * t))
    ph = np.cumsum(r) / sr
    pulses = (np.diff(np.floor(ph), prepend=0) > 0).astype(float) * rng.uniform(0.5, 1.0, m)
    body = L.resonate(pulses, sr, [rng.uniform(f_lo, f_hi), rng.uniform(f_lo, f_hi) * 2.3, rng.uniform(f_lo, f_hi) * 3.9],
                      [0.012, 0.008, 0.005], [1.0, 0.5, 0.25])
    return body * np.clip(np.sin(np.pi * t / t[-1]), 0, None) ** 0.6


def bed_forest(rng, sr, dur):
    n = L.secs(dur, sr)
    I = cenv(rng, dur, 0.15, 0.02, 0.4)
    out = cnoise(rng, n, sr, 60, 420, "pink") * up(0.4 + 0.6 * I, n) * 0.7
    out += leaves_layer(rng, n, sr, dur, 0.25 + 0.75 * I) * 0.55
    for t in times_by(rng, np.ones(100), n, int(dur * 1.2)):      # a few far, dull bird chips
        cplace(out, chirp_event(rng, sr, True) * rng.uniform(0.04, 0.12), t)
    for t in times_by(rng, I ** 2, n, 5):                          # branches creaking in the stronger air
        cplace(out, wood_creak(rng, sr, rng.uniform(0.4, 0.9), 150, 380, (12, 35)) * rng.uniform(0.04, 0.09), t)
    return creverb(out, rng, sr, 0.9, 0.3, 4000)


def bed_frost(rng, sr, dur):
    n = L.secs(dur, sr)
    I = cenv(rng, dur, 0.14, 0.02, 0.4)
    i = up(0.3 + 0.7 * I, n)
    out = cnoise(rng, n, sr, 250, 900, "pink") * i ** 1.5 * 0.8
    out += cnoise(rng, n, sr, 900, 2600, "pink") * i ** 2.5 * 0.45
    for k, fc in enumerate((720.0, 940.0, 1180.0, 1450.0, 1720.0)):   # thin cold whistles drifting with the wind
        wt = np.exp(-0.5 * ((up(I, n) - k / 4.0) / 0.16) ** 2) * i ** 2
        out += cpeak(cnoise(rng, n, sr, fc * 0.96, fc * 1.04, order=4), sr, fc, 80, 3.0) * wt * 0.2
    sparkle = np.repeat(rng.random(n // 40 + 2), 40)[:n] ** 6
    out += cnoise(rng, n, sr, 3000, 5200) * sparkle * i * 0.6       # blown snow
    for t in times_by(rng, np.ones(100), n, 5):                     # faint ice creaks far off
        cplace(out, wood_creak(rng, sr, rng.uniform(0.5, 1.2), 110, 260, (8, 22)) * rng.uniform(0.04, 0.08), t)
    return creverb(out, rng, sr, 1.2, 0.3, 3500)


def bed_quarry(rng, sr, dur):
    n = L.secs(dur, sr)
    I = cenv(rng, dur, 0.12, 0.02, 0.45)
    i = up(0.35 + 0.65 * I, n)
    out = cnoise(rng, n, sr, 120, 700, "pink") * i * 0.9
    out += cnoise(rng, n, sr, 700, 3200, "pink") * i ** 2.2 * 0.4
    grit = np.repeat(rng.random(n // 25 + 2), 25)[:n] ** 8
    out += cnoise(rng, n, sr, 2500, 5000) * grit * i ** 2 * 0.9      # dust and sand on the wind
    for t in times_by(rng, np.ones(100), n, 14):                    # far pebble trickles
        k = rng.integers(3, 12)
        gap = rng.uniform(0.03, 0.09)
        for j in range(k):
            cplace(out, tick(rng, sr, 1800, 4800, (0.0008, 0.002)) * rng.uniform(0.04, 0.12) * (1 - j / (k + 1)),
                   t + L.secs(j * gap * rng.uniform(0.6, 1.4), sr))
    for t in times_by(rng, np.ones(100), n, 3):                     # a distant rock settling
        m = L.secs(0.4, sr)
        th = L.lp(rng.standard_normal(m), sr, 160, 2) * np.exp(-np.arange(m) / (0.08 * sr))
        cplace(out, L.norm_peak(th) * 0.15, t)
    return creverb(out, rng, sr, 1.4, 0.35, 3000)


def crackles(rng, sr, n, count, env, amp=(0.05, 0.3), f=(900, 4000)):
    out = np.zeros(n)
    for t in times_by(rng, env, n, count):
        c = tick(rng, sr, f[0], f[1], (0.0003, 0.0015), 1.0) * rng.uniform(*amp)
        if rng.random() < 0.2:                                      # a little burst
            for j in range(rng.integers(2, 6)):
                cplace(out, tick(rng, sr, f[0], f[1], (0.0003, 0.001), 1.0) * rng.uniform(*amp) * 0.6, t + L.secs(rng.uniform(0.004, 0.06), sr))
        cplace(out, c, t)
    return out


def bed_ember(rng, sr, dur):
    n = L.secs(dur, sr)
    I = cenv(rng, dur, 0.2, 0.03, 0.4)
    flick = up(cenv(rng, dur, 12.0, 3.0, 0.2), n)
    out = cnoise(rng, n, sr, 35, 220, "brown") * up(0.5 + 0.5 * I, n) * (0.7 + 0.6 * flick) * 0.6
    out += cnoise(rng, n, sr, 220, 900, "pink") * up(0.3 + 0.7 * I, n) ** 2 * (0.6 + 0.8 * flick) * 0.6
    out += cnoise(rng, n, sr, 1500, 4500) * up(I, n) * 0.08
    out += crackles(rng, sr, n, int(dur * 6), 0.3 + I, (0.06, 0.3))
    for t in times_by(rng, I ** 2, n, 4):                           # a flare of gas
        m = L.secs(rng.uniform(1.5, 2.6), sr)
        e = np.clip(np.sin(np.pi * np.arange(m) / m), 0, None) ** 2
        cplace(out, L.bp(rng.standard_normal(m), sr, 150, 1200) * e * 0.08, t)
    return creverb(out, rng, sr, 0.9, 0.2, 3000)


def bed_hearth(rng, sr, dur):
    n = L.secs(dur, sr)
    I = cenv(rng, dur, 0.15, 0.03, 0.4)
    flick = up(cenv(rng, dur, 10.0, 2.0, 0.2), n)
    out = cnoise(rng, n, sr, 40, 260, "brown") * up(0.6 + 0.4 * I, n) * (0.8 + 0.4 * flick) * 0.25
    out += cnoise(rng, n, sr, 200, 900, "pink") * up(0.4 + 0.6 * I, n) * (0.5 + 0.8 * flick) * 0.12
    out += cnoise(rng, n, sr, 1200, 4000) * 0.06 * up(0.5 + 0.5 * I, n)
    out += crackles(rng, sr, n, int(dur * 10), 0.4 + I, (0.1, 0.6), (1200, 4800))
    for t in times_by(rng, np.ones(100), n, 3):                     # a log settling
        m = L.secs(0.25, sr)
        th = L.lp(rng.standard_normal(m), sr, 220, 2) * np.exp(-np.arange(m) / (0.05 * sr))
        cplace(out, L.norm_peak(th) * 0.25, t)
        for j in range(rng.integers(5, 11)):
            cplace(out, tick(rng, sr, 1500, 4500, (0.0003, 0.0012), 1.0) * rng.uniform(0.1, 0.35), t + L.secs(rng.uniform(0.02, 0.5), sr))
    out += cnoise(rng, n, sr, 40, 110, "brown") * 0.08              # room
    return creverb(out, rng, sr, 0.5, 0.25, 4500)


def bed_clock(rng, sr, dur):
    n = L.secs(dur, sr)
    out = cnoise(rng, n, sr, 30, 120, "brown") * 0.25 + cnoise(rng, n, sr, 300, 1200, "pink") * 0.02
    period = 0.5
    beats = int(round(dur / period))
    sets = []
    for s in range(2):                                              # tick / tock: two escapement voices
        sets.append(dict(f=[rng.uniform(1800, 2600) * (1.0 if s == 0 else 0.82), rng.uniform(3600, 4800) * (1.0 if s == 0 else 0.9)],
                         box=rng.uniform(380, 520) * (1.0 if s == 0 else 0.86)))
    for b in range(beats):
        sp = sets[b % 2]
        m = L.secs(0.08, sr)
        ex = rng.standard_normal(m) * np.exp(-np.arange(m) / (0.0007 * sr))
        y = L.resonate(ex, sr, sp["f"] + [sp["box"], sp["box"] * 2.1], [0.004, 0.0025, 0.02, 0.012], [1.0, 0.6, 0.5, 0.3])
        at = L.secs(b * period, sr) + int(rng.normal(0, 0.0012) * sr)
        cplace(out, y * 0.35 * L.undb(rng.uniform(-1.2, 1.2)), at)
    return creverb(out, rng, sr, 0.45, 0.25, 5000)


def bed_mill(rng, sr, dur):
    n = L.secs(dur, sr)
    t = np.arange(n) / sr
    rev = 4.0                                                       # 15 turns of the stones per loop
    rot = 0.75 + 0.25 * np.sin(2 * np.pi * t / rev) + 0.08 * np.sin(4 * np.pi * t / rev + 1.0)
    out = cnoise(rng, n, sr, 35, 160, "brown") * rot * 0.5
    grind = np.repeat(rng.random(n // 50 + 2), 50)[:n] ** 3
    out += cnoise(rng, n, sr, 200, 1400, "pink") * (0.3 + grind) * rot * 0.55
    teeth = int(round(dur / rev)) * 12
    for k in range(teeth):                                          # wooden cogs clacking, each a bit different
        m = L.secs(0.06, sr)
        ex = rng.standard_normal(m) * np.exp(-np.arange(m) / (0.001 * sr))
        y = L.resonate(ex, sr, [rng.uniform(260, 420), rng.uniform(800, 1300)], [0.012, 0.006], [1.0, 0.4])
        cplace(out, y * rng.uniform(0.15, 0.35), L.secs(k * rev / 12, sr) + int(rng.normal(0, 0.004) * sr))
    for at in times_by(rng, np.ones(100), n, 7):
        cplace(out, wood_creak(rng, sr, rng.uniform(0.4, 1.0), 160, 420, (14, 40)) * rng.uniform(0.15, 0.3), at)
    out += cnoise(rng, n, sr, 60, 350, "pink") * up(0.4 + 0.6 * cenv(rng, dur, 0.1), n) * 0.25   # wind outside
    return creverb(out, rng, sr, 0.8, 0.3, 3000)


VOWELS = [(300, 870), (400, 2000), (530, 1840), (640, 1190), (660, 1720), (730, 1090), (570, 840), (440, 1020), (490, 1350), (500, 1500)]


def bed_cafe(rng, sr, dur):
    """Murmur without words: formant-filtered buzz syllables from several far talkers, smeared
    by the room until nothing is intelligible; a few soft cup clinks."""
    n = L.secs(dur, sr)
    out = cnoise(rng, n, sr, 40, 400, "pink") * 0.05
    for spk in range(9):
        f0 = rng.uniform(95, 140) if spk % 2 else rng.uniform(170, 240)
        gain = rng.uniform(0.25, 1.0)
        t = rng.uniform(0, dur)
        end = t + dur
        while t < end:
            phrase = rng.uniform(0.8, 3.0)
            pt = 0.0
            while pt < phrase:
                syl = rng.uniform(0.09, 0.22)
                m = L.secs(syl, sr)
                tt = np.arange(m) / sr
                pitch = f0 * (1 + 0.08 * math.sin(pt * 3.0) + rng.uniform(-0.05, 0.05)) * (1 - 0.1 * tt / syl)
                buzz = L.osc(sr, pitch, tuple((h, 1.0 / h) for h in range(1, 14)))
                buzz = buzz * 0.8 + rng.standard_normal(m) * 0.15
                f1, f2 = VOWELS[rng.integers(0, len(VOWELS))]
                v = L.resonate(buzz, sr, [f1, f2, 2600], [0.008, 0.006, 0.004], [1.0, 0.6, 0.2])
                e = np.clip(np.sin(np.pi * tt / syl), 0, None) ** 1.2
                cplace(out, v * e * gain * 0.2, L.secs(t + pt, sr))
                pt += syl * rng.uniform(1.0, 1.4)
            t += phrase + rng.uniform(0.4, 2.5)
    out = cfilt(out, sr, 120, 2200, order=2)
    for at in times_by(rng, np.ones(100), n, 14):                   # cups and spoons, far and soft
        cl = L.modal(sr, rng.uniform(1800, 3200), "ceramic", dur=0.25, rng=rng)
        cplace(out, cl * rng.uniform(0.02, 0.06), at)
    return creverb(out, rng, sr, 0.9, 0.6, 3000)


def muffle(x, sr_in, sr_out, cutoff):
    y = cfilt(x, sr_in, None, cutoff, order=4)
    return resample_loop(y, int(round(x.size * sr_out / sr_in)))


# name: (function, sr, seconds)
BEDS = {
    "birds": (lambda r, sr, d: bed_birds(r, sr, d, False), 22050, 60.0),
    "birds_far": (lambda r, sr, d: bed_birds(r, sr, d, True), 11025, 60.0),
    "insects": (bed_insects, 22050, 60.0),
    "night": (bed_night, 22050, 60.0),
    "coast": (bed_coast, 16000, 64.0),
    "wind": (bed_wind, 11025, 64.0),
    "waterfall": (bed_waterfall, 22050, 60.0),
    "room": (bed_room, 6000, 60.0),
    "forest": (bed_forest, 22050, 60.0),
    "frost": (bed_frost, 11025, 60.0),
    "quarry": (bed_quarry, 11025, 60.0),
    "ember": (bed_ember, 11025, 60.0),
    "hearth": (bed_hearth, 22050, 60.0),
    "clock": (bed_clock, 11025, 60.0),
    "mill": (bed_mill, 8000, 60.0),
    "cafe": (bed_cafe, 11025, 60.0),
}
# muffled twins (heard through the walls indoors): same loop, low-passed, same length.
MUFFLED = {"sea_muffled": ("coast", 380.0), "wind_muffled": ("wind", 320.0), "waterfall_muffled": ("waterfall", 380.0)}
MUFFLED_SR = 5000


def make_beds(out: Path, names) -> int:
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    raw = {}
    for name in [b for b in BEDS if b in names or any(MUFFLED.get(m, ("",))[0] == b for m in names)]:
        fn, sr, dur = BEDS[name]
        rng = np.random.default_rng(L.take_seed("bed_" + name, 0, "world"))
        x = fn(rng, sr, dur)
        assert x.size == L.secs(dur, sr), (name, x.size)
        raw[name] = (x, sr)
        if name in names:
            total += write_bed(out / (name + ".wav"), x, sr)
    for m, (src, cut) in MUFFLED.items():
        if m in names:
            x, sr = raw[src]
            total += write_bed(out / (m + ".wav"), muffle(x, sr, MUFFLED_SR, cut), MUFFLED_SR)
    return total


# In-game level of each bed at gain 1 (ambience_db -10 + BED_DB + file level), dBFS: the 150 Hz
# high-passed long-term RMS (what small speakers play), or for the dark beds (room tone, the
# muffled twins) the plain RMS. Used only to print the BED_DB that world_audio.gd should carry.
AMBIENCE_DB = -10.0
TARGET = {"birds": -47, "birds_far": -51, "insects": -50, "night": -50, "coast": -37, "wind": -41, "waterfall": -36,
          "room": -50, "forest": -42, "frost": -41, "quarry": -43, "ember": -40, "hearth": -40, "clock": -50, "mill": -42,
          "cafe": -44, "sea_muffled": -45, "wind_muffled": -49, "waterfall_muffled": -44}
PLAIN = ("room", "sea_muffled", "wind_muffled", "waterfall_muffled")


def wrms_db(y, sr):
    return L.db(rms(ss.sosfilt(ss.butter(2, 150, "high", fs=sr, output="sos"), y)))


def write_bed(path: Path, x, sr) -> int:
    L._guard([path], False)
    y = finish_bed(x, sr)
    L.write_wav(path, y, sr)
    b = path.stat().st_size
    lv = L.db(rms(y)) if path.stem in PLAIN else wrms_db(y, sr)
    print("bed %-18s %5d Hz %5.1f s  rms %.1f dB  hp-rms %.1f dB  peak %.1f dB  %7.1f KB  BED_DB %.1f" % (
        path.stem, sr, y.size / sr, L.db(rms(y)), wrms_db(y, sr), L.peak_db(y), b / 1024,
        TARGET.get(path.stem, -45) - AMBIENCE_DB - lv), flush=True)
    return b


# =========================================================================== one-shots
def outdoor(x, rng, sr, rt=0.7, wet=0.2, tone=5000):
    return L.reverb(x, sr, room=min(1.0, rt / 1.9) ** (1 / 1.3), wet=wet, rng=rng, tone=tone)


def note(sr, dur, f, harm=((1, 1.0), (2, 0.1)), att=0.15, rel=0.4):
    """A sung note following a frequency curve f (array or (f0, f1)); envelope with attack/release fractions."""
    n = max(8, L.secs(dur, sr))
    if isinstance(f, tuple):
        u = np.linspace(0, 1, n, endpoint=False)
        f = f[0] * (f[1] / f[0]) ** u
    f = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(f)), f)
    y = L.osc(sr, f, harm)
    u = np.linspace(0, 1, n)
    e = np.minimum(1, u / max(att, 1e-3)) * np.minimum(1, (1 - u) / max(rel, 1e-3))
    return y * e ** 1.5


def seq(sr, parts):
    """[(signal, gap_after_s)] -> one array."""
    out = []
    for s, gap in parts:
        out.append(s)
        out.append(np.zeros(L.secs(max(gap, 0.0), sr)))
    return np.concatenate(out)


SPOT_SR = {"bird": 22050, "gull": 16000, "wave_crash": 16000, "wave_slap": 16000, "gust": 11025, "cricket": 16000,
           "owl": 11025, "frog": 11025, "rooster": 16000, "windmill_creak": 11025, "distant_bell": 11025}


def bird_call(rng, k):
    sr = SPOT_SR["bird"]
    arche = k % 8
    p = rng.uniform(0.85, 1.18)
    H = ((1, 1.0), (2, rng.uniform(0.05, 0.2)))
    if arche == 0:      # descending tee-tee-tew-tew
        cnt = int(rng.integers(3, 7))
        start = rng.uniform(3800, 4800) * p
        step = rng.uniform(0.04, 0.09)
        parts = []
        for q in range(cnt):
            f = start * (1 - step * q)
            parts.append((note(sr, rng.uniform(0.06, 0.09), (f, f * rng.uniform(0.72, 0.85)), H) * (1 - 0.06 * q), rng.uniform(0.04, 0.07)))
        y = seq(sr, parts)
    elif arche == 1:    # rising chips
        cnt = int(rng.integers(2, 5))
        parts = [(note(sr, rng.uniform(0.03, 0.05), (2200 * p, rng.uniform(3500, 4300) * p), H, 0.1, 0.3), rng.uniform(0.04, 0.09)) for _ in range(cnt)]
        y = seq(sr, parts)
    elif arche == 2:    # fast trill, falling a little, with an end flourish
        cnt = int(rng.integers(9, 17))
        f = rng.uniform(4400, 5600) * p
        rate = rng.uniform(0.028, 0.042)
        parts = [(note(sr, rate * 0.65, (f * (1 - 0.01 * q), f * (1 - 0.01 * q) * 0.88), H, 0.1, 0.4), rate * 0.35) for q in range(cnt)]
        parts.append((note(sr, 0.09, (f * 0.7, f * 0.95), H), 0.0))
        y = seq(sr, parts)
    elif arche == 3:    # two whistled notes with vibrato (interval up or down)
        f1 = rng.uniform(2300, 3100) * p
        f2 = f1 * rng.choice([0.8, 0.84, 1.19, 1.26, 1.33])
        tt = np.arange(L.secs(0.3, sr)) / sr
        v = 1 + 0.025 * np.sin(2 * np.pi * rng.uniform(7, 11) * tt)
        y = seq(sr, [(note(sr, rng.uniform(0.2, 0.28), f1 * v, ((1, 1.0),), 0.2, 0.3), rng.uniform(0.06, 0.12)),
                     (note(sr, rng.uniform(0.24, 0.34), f2 * v, ((1, 1.0),), 0.2, 0.4), 0.0)])
    elif arche == 4:    # warble: a wandering FM line
        dur = rng.uniform(0.5, 0.95)
        n = L.secs(dur, sr)
        tt = np.arange(n) / sr
        f = rng.uniform(2600, 3600) * p * (1 + 0.18 * np.sin(2 * np.pi * rng.uniform(11, 19) * tt) * np.sin(np.pi * tt / dur)
                                         + 0.1 * np.sin(2 * np.pi * rng.uniform(1.5, 3.5) * tt + rng.uniform(0, 6)))
        y = note(sr, dur, f, H, 0.08, 0.2)
        gate = 0.35 + 0.65 * (np.sin(2 * np.pi * rng.uniform(5, 9) * tt) > -0.3)
        y = y * np.convolve(gate, np.ones(60) / 60, "same")
    elif arche == 5:    # chip-chip-trrrr
        f = rng.uniform(3200, 4200) * p
        parts = [(note(sr, 0.035, (f, f * 1.15), H, 0.1, 0.3), rng.uniform(0.08, 0.13)) for _ in range(int(rng.integers(2, 4)))]
        dur = rng.uniform(0.3, 0.5)
        tt = np.arange(L.secs(dur, sr)) / sr
        tr = note(sr, dur, f * 0.85 * (1 - 0.1 * tt / dur), H, 0.1, 0.3) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * rng.uniform(28, 40) * tt)))
        parts.append((tr, 0.0))
        y = seq(sr, parts)
    elif arche == 6:    # sweet-sweet-sweeter: up-slurs, speeding up
        cnt = int(rng.integers(3, 6))
        f = rng.uniform(2400, 3200) * p
        gap = rng.uniform(0.14, 0.2)
        parts = []
        for q in range(cnt):
            parts.append((note(sr, rng.uniform(0.08, 0.12), (f, f * rng.uniform(1.35, 1.6)), H, 0.25, 0.2), gap))
            gap *= 0.75
        y = seq(sr, parts)
    else:               # chick-a-dee: a high sweep then buzzy dee-dee
        f = rng.uniform(5000, 6200) * p
        parts = [(note(sr, 0.06, (f, f * 0.7), H, 0.1, 0.4), 0.03)]
        g = rng.uniform(2800, 3400) * p
        for q in range(int(rng.integers(2, 5))):
            d = rng.uniform(0.11, 0.16)
            tt = np.arange(L.secs(d, sr)) / sr
            parts.append((note(sr, d, np.full(tt.size, g), ((1, 1.0), (2, 0.4), (3, 0.2)), 0.1, 0.3)
                          * (0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(90, 140) * tt)), rng.uniform(0.04, 0.08)))
        y = seq(sr, parts)
    y = L.lp(y, sr, rng.uniform(6000, 9500), 1)
    return outdoor(y, rng, sr, rng.uniform(0.5, 1.0), rng.uniform(0.1, 0.25)), {"archetype": int(arche)}


def gull_call(rng, k):
    sr = SPOT_SR["gull"]
    arche = k % 4

    def kyow(dur, f0, rise=1.25, fall=0.7):
        n = L.secs(dur, sr)
        u = np.linspace(0, 1, n)
        f = f0 * np.where(u < 0.3, 1 + (rise - 1) * u / 0.3, rise - (rise - fall) * (u - 0.3) / 0.7)
        y = L.osc(sr, f, tuple((h, 1.0 / h ** 0.7) for h in range(1, 12)))
        y = L.resonate(y, sr, [rng.uniform(1300, 1900), rng.uniform(2600, 3400)], [0.004, 0.003], [1.0, 0.7]) + 0.3 * L.norm_peak(y)
        y += L.bp(rng.standard_normal(n), sr, 2000, 6000) * 0.05
        return y * np.minimum(1, u / 0.08) * np.minimum(1, (1 - u) / 0.35) ** 1.3

    if arche == 0:      # one long keow
        y = kyow(rng.uniform(0.35, 0.55), rng.uniform(650, 850))
    elif arche == 1:    # laughing ha-ha-ha-haaa
        cnt = int(rng.integers(4, 8))
        f = rng.uniform(700, 950)
        parts = [(kyow(rng.uniform(0.09, 0.13), f * (1 - 0.03 * q), 1.1, 0.9), rng.uniform(0.05, 0.09)) for q in range(cnt)]
        parts.append((kyow(rng.uniform(0.3, 0.45), f * 0.9, 1.15, 0.65), 0.0))
        y = seq(sr, parts)
    elif arche == 2:    # mew: kee-eer, two parts
        f = rng.uniform(900, 1150)
        y = seq(sr, [(kyow(rng.uniform(0.12, 0.18), f, 1.2, 1.1), 0.02), (kyow(rng.uniform(0.3, 0.42), f * 1.05, 1.0, 0.6), 0.0)])
    else:               # two gulls overlapping, one farther away
        a = kyow(rng.uniform(0.35, 0.5), rng.uniform(650, 800))
        b = L.lp(kyow(rng.uniform(0.3, 0.45), rng.uniform(850, 1050)), sr, 2500, 1)
        y = L.mix(a, (b, 0.5, rng.uniform(0.15, 0.3)), sr=sr)
    y = L.lp(y, sr, rng.uniform(4500, 8000), 1)
    return outdoor(y, rng, sr, rng.uniform(0.8, 1.4), rng.uniform(0.2, 0.35), 4000), {"archetype": int(arche)}


def wave_crash(rng, k):
    sr = SPOT_SR["wave_crash"]
    shapes = ["plunge", "spill", "double", "dump", "roll"]
    shape = shapes[k % len(shapes)]
    dur = {"plunge": 2.6, "spill": 3.4, "double": 3.2, "dump": 1.9, "roll": 3.0}[shape] * rng.uniform(0.88, 1.12)
    n = L.secs(dur, sr)
    t = np.arange(n) / sr
    peak = {"plunge": 0.35, "spill": 0.5, "double": 0.25, "dump": 0.22, "roll": 0.4}[shape] * dur * rng.uniform(0.85, 1.15)

    def hump(at, rise, fall):
        return np.where(t < at, np.clip((t - (at - rise)) / rise, 0, 1) ** 2, np.exp(-(t - at) / fall))
    if shape == "double":
        env = hump(peak, 0.3, 0.35) + 0.8 * hump(peak + rng.uniform(0.45, 0.7), 0.15, 0.6)
    elif shape == "roll":
        env = hump(peak, 0.6, 1.1) * (0.8 + 0.2 * np.sin(2 * np.pi * rng.uniform(2.5, 4) * t))
    elif shape == "spill":
        env = hump(peak, 1.0, 1.2)
    else:
        env = hump(peak, 0.35 if shape == "plunge" else 0.12, 0.7 if shape == "plunge" else 0.45)
    build = np.clip(t / max(peak, 0.1), 0, 1) ** 2 * np.exp(-np.clip(t - peak, 0, None) / 0.4)
    rumble = L.lp(L.noise(n, rng, "brown"), sr, 260, 2) * build * 1.2
    crash = L.bp(L.noise(n, rng, "pink"), sr, 250, 3500) * env
    hiss = L.bp(L.white(n, rng), sr, 2500, 7500) * np.clip(env - 0.2, 0, None) ** 1.3
    grains = np.repeat(rng.random(n // 48 + 2), 48)[:n] ** 3
    fizz_env = np.clip((t - peak) / 0.2, 0, 1) * np.exp(-np.clip(t - peak, 0, None) / rng.uniform(0.6, 1.1))
    fizz = L.bp(L.white(n, rng), sr, 3000, 7500) * grains * fizz_env
    y = rumble + crash * 1.1 + hiss * 0.6 + fizz * 0.9
    if k % 2 == 1:      # pebbles rattling in the backwash
        bw = np.zeros(n)
        for _ in range(int(rng.integers(25, 60))):
            at = rng.uniform(peak + 0.4, dur - 0.1)
            L.place(bw, tick(rng, sr, 1500, 4500, (0.0008, 0.002)), at, sr, rng.uniform(0.1, 0.4) * math.exp(-(at - peak) / 1.2))
        y = y + bw
    return L.tilt(y, sr, rng.uniform(-3, 2)), {"shape": shape}


def wave_slap(rng, k):
    sr = SPOT_SR["wave_slap"]
    arche = k % 4
    n = L.secs(1.0, sr)
    y = np.zeros(n)

    def slap(at, size):
        m = L.secs(0.35, sr)
        th = L.lp(L.white(m, rng), sr, 300 * size, 2) * L.exp_decay(0.35, sr, 0.05)
        sp = L.bp(L.white(m, rng), sr, 600, 5000) * L.exp_decay(0.35, sr, rng.uniform(0.04, 0.09), 0.004)
        L.place(y, L.norm_peak(th) * 0.8 + L.norm_peak(sp) * 0.7, at, sr)
    if arche == 0:      # one slap against a post
        slap(0.0, rng.uniform(0.8, 1.2))
    elif arche == 1:    # double slap
        slap(0.0, 1.0)
        slap(rng.uniform(0.12, 0.22), rng.uniform(0.7, 0.9))
    elif arche == 2:    # slosh: a slower swell into the rocks
        m = L.secs(0.7, sr)
        e = np.clip(np.sin(np.pi * np.linspace(0, 1, m)), 0, None) ** 2
        L.place(y, L.norm_peak(L.bp(L.noise(m, rng, "pink"), sr, 300, 3000) * e), 0.0, sr)
    else:               # hollow boom under the pier
        m = L.secs(0.5, sr)
        b = L.resonate(L.white(m, rng) * L.exp_decay(0.5, sr, 0.01), sr, [rng.uniform(70, 110), rng.uniform(180, 260)], [0.12, 0.06])
        L.place(y, b * 0.9, 0.0, sr)
        slap(0.01, 0.8)
    from_t = 0.08
    for _ in range(int(rng.integers(3, 9))):                       # drips and gurgles
        at = rng.uniform(from_t, 0.85)
        m = L.secs(rng.uniform(0.02, 0.05), sr)
        u = np.arange(m) / m
        f0 = rng.uniform(500, 1500)
        L.place(y, np.sin(2 * np.pi * np.cumsum(f0 * (1 + u)) / sr) * (1 - u) * np.minimum(u * 20, 1), at, sr, rng.uniform(0.05, 0.2))
    return outdoor(y, rng, sr, 0.5, 0.15, 4000), {"archetype": int(arche)}


def gust(rng, k):
    sr = SPOT_SR["gust"]
    arche = k % 6
    dur = rng.uniform(2.2, 3.4) if arche != 5 else rng.uniform(1.2, 1.7)
    n = L.secs(dur, sr)
    t = np.arange(n) / sr
    u = t / dur
    if arche == 0:
        e = np.clip(np.sin(np.pi * u ** rng.uniform(0.7, 1.4)), 0, None) ** 2
    elif arche == 1:    # double gust
        a = rng.uniform(0.25, 0.35)
        e = np.exp(-0.5 * ((u - a) / 0.12) ** 2) + rng.uniform(0.6, 1.0) * np.exp(-0.5 * ((u - a - rng.uniform(0.3, 0.4)) / 0.14) ** 2)
    elif arche == 2:    # flapping, fluttering
        e = np.clip(np.sin(np.pi * u), 0, None) ** 2 * (0.65 + 0.35 * np.sin(2 * np.pi * rng.uniform(7, 13) * t))
    elif arche == 3:    # slow rise, sudden drop
        e = np.clip(u / 0.7, 0, 1) ** 2 * np.clip((1 - u) / 0.3, 0, 1)
    elif arche == 4:    # buffeting: three or four uneven puffs
        e = np.zeros(n)
        for c in np.sort(rng.uniform(0.1, 0.85, int(rng.integers(3, 5)))):
            e += rng.uniform(0.5, 1.0) * np.exp(-0.5 * ((u - c) / rng.uniform(0.04, 0.08)) ** 2)
    else:               # a short quick puff
        e = np.clip(u / 0.25, 0, 1) * np.exp(-np.clip(u - 0.25, 0, None) / 0.2)
    e = e / e.max()
    fc = (250 + 1500 * e ** 1.3) if arche != 3 else (200 + 2200 * u ** 2 * e)
    y = L.svf(L.noise(n, rng, "pink"), sr, fc, q=0.9, mode="lp") * (0.25 + e)
    if k % 2 == 0:      # a whistle across an edge
        f = rng.uniform(500, 800) * (1 + 0.5 * e)
        w = L.svf(L.white(n, rng), sr, f, q=18, mode="bp")
        y = y + L.norm_peak(w) * e ** 2 * rng.uniform(0.15, 0.3) * float(np.max(np.abs(y)))
    if k % 3 == 1:      # leaves rushing
        g = np.repeat(rng.random(n // 60 + 2), 60)[:n] ** 3
        y = y + L.bp(L.white(n, rng), sr, 1800, 4800) * g * e ** 1.5 * 0.5
    return y * np.clip(np.sin(np.pi * u), 0, None) ** 0.3, {"archetype": int(arche)}


def cricket(rng, k):
    sr = SPOT_SR["cricket"]
    arche = k % 4
    f = rng.uniform(3600, 5200)

    def pulse(dur):
        m = L.secs(dur, sr)
        tt = np.arange(m) / sr
        return np.sin(2 * np.pi * f * tt * (1 + 0.02 * tt / dur)) * np.clip(np.sin(np.pi * tt / dur), 0, None) ** 0.8

    if arche == 0:      # field cricket: chirps of 3-5 pulses
        chirps, ppc = int(rng.integers(2, 5)), int(rng.integers(3, 6))
        parts = []
        for c in range(chirps):
            for q in range(ppc):
                parts.append((pulse(rng.uniform(0.012, 0.018)), rng.uniform(0.012, 0.02)))
            parts.append((np.zeros(1), rng.uniform(0.18, 0.35)))
        y = seq(sr, parts)
    elif arche == 1:    # trill
        dur = rng.uniform(0.6, 1.1)
        rate = rng.uniform(25, 45)
        cnt = int(dur * rate)
        y = seq(sr, [(pulse(0.6 / rate), 0.4 / rate) for _ in range(cnt)])
        y = y * np.clip(np.sin(np.pi * np.linspace(0, 1, y.size)), 0, None) ** 0.3
    elif arche == 2:    # two quick double pulses
        y = seq(sr, [(pulse(0.02), 0.015), (pulse(0.02), rng.uniform(0.12, 0.2)), (pulse(0.02), 0.015), (pulse(0.02), 0.0)])
    else:               # tree cricket: a soft, lower, long purr
        f = rng.uniform(2600, 3100)
        dur = rng.uniform(0.8, 1.3)
        m = L.secs(dur, sr)
        tt = np.arange(m) / sr
        y = np.sin(2 * np.pi * f * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(55, 75) * tt)) * np.clip(np.sin(np.pi * tt / dur), 0, None) ** 0.5
    y = y + 0.08 * np.sin(2 * np.pi * 2 * f * np.arange(y.size) / sr) * (np.abs(y) > 0.05)
    return outdoor(y, rng, sr, 0.4, 0.15), {"archetype": int(arche)}


def owl(rng, k):
    sr = SPOT_SR["owl"]
    arche = k % 6
    f = rng.uniform(320, 440)

    def hoot(dur, f0, f1=None, trem=0.0):
        n = L.secs(dur, sr)
        u = np.linspace(0, 1, n)
        fr = f0 + ((f1 or f0) - f0) * u
        tt = np.arange(n) / sr
        y = L.osc(sr, fr, ((1, 1.0), (2, 0.15), (3, 0.05)))
        y = y * (1 - trem * (0.5 + 0.5 * np.sin(2 * np.pi * 14 * tt)))
        y += L.bp(rng.standard_normal(n), sr, f0 * 0.8, f0 * 3) * 0.08
        return y * np.minimum(1, u / 0.15) * np.minimum(1, (1 - u) / 0.4)
    if arche == 0:      # hoo ... hoo-hoo-hooo
        y = seq(sr, [(hoot(0.35, f, f * 0.97), rng.uniform(0.35, 0.5)), (hoot(0.12, f * 1.02), 0.06), (hoot(0.12, f), 0.06), (hoot(0.55, f, f * 0.93), 0.0)])
    elif arche == 1:    # single hoot
        y = hoot(rng.uniform(0.45, 0.7), f, f * 0.92)
    elif arche == 2:    # hoo-hoo
        y = seq(sr, [(hoot(0.22, f * 1.03), rng.uniform(0.15, 0.25)), (hoot(0.35, f, f * 0.94), 0.0)])
    elif arche == 3:    # quavering
        y = hoot(rng.uniform(0.8, 1.1), f * 1.05, f * 0.9, trem=0.7)
    elif arche == 4:    # whoo rising then falling
        n = L.secs(0.7, sr)
        u = np.linspace(0, 1, n)
        y = L.osc(sr, f * (0.85 + 0.35 * np.sin(np.pi * u)), ((1, 1.0), (2, 0.12))) * np.clip(np.sin(np.pi * u), 0, None) ** 1.2
    else:               # three even hoots
        y = seq(sr, [(hoot(0.18, f), rng.uniform(0.22, 0.3)) for _ in range(3)])
    y = L.lp(y, sr, 1800, 1)
    return outdoor(y, rng, sr, 1.4, 0.35, 2500), {"archetype": int(arche)}


def frog(rng, k):
    sr = SPOT_SR["frog"]
    arche = k % 4
    if arche == 0:      # ribbit: two quick pulsed croaks
        y = seq(sr, [(croak(rng, sr), rng.uniform(0.04, 0.08)), (croak(rng, sr), 0.0)])
    elif arche == 1:    # bullfrog rumm
        y = croak(rng, sr, low=True)
    elif arche == 2:    # creaky series of clicks
        f = rng.uniform(800, 1400)
        y = seq(sr, [(tick(rng, sr, f * 0.9, f * 1.1, (0.003, 0.006), 0.6), rng.uniform(0.03, 0.05)) for _ in range(int(rng.integers(5, 10)))])
    else:               # peeper: a rising whistle
        n = L.secs(rng.uniform(0.1, 0.16), sr)
        u = np.linspace(0, 1, n)
        y = L.osc(sr, rng.uniform(2300, 2900) * (1 + 0.15 * u), ((1, 1.0),)) * np.clip(np.sin(np.pi * u), 0, None) ** 1.5
        y = seq(sr, [(y, rng.uniform(0.25, 0.45)), (y * 0.8, 0.0)]) if rng.random() < 0.5 else y
    return outdoor(y, rng, sr, 0.9, 0.25, 3000), {"archetype": int(arche)}


def rooster(rng, k):
    sr = SPOT_SR["rooster"]
    syl = [[0.14, 0.12, 0.16, 0.55], [0.18, 0.2, 0.75], [0.12, 0.1, 0.12, 0.14, 0.5]][k % 3]
    pitch = [[1.0, 1.25, 1.35, 1.2], [1.0, 1.3, 1.15], [0.95, 1.2, 1.3, 1.35, 1.1]][k % 3]
    f0 = rng.uniform(420, 560)
    parts = []
    for i, (d, p) in enumerate(zip(syl, pitch)):
        n = L.secs(d * rng.uniform(0.9, 1.1), sr)
        u = np.linspace(0, 1, n)
        fr = f0 * p * (1 + 0.05 * np.sin(np.pi * u) - (0.25 * u ** 2 if i == len(syl) - 1 else 0))
        y = L.osc(sr, fr, tuple((h, 1.0 / h ** 0.6) for h in range(1, 16)))
        y = L.resonate(y, sr, [rng.uniform(900, 1300), rng.uniform(2200, 2900)], [0.004, 0.003], [1.0, 0.6]) + 0.2 * L.norm_peak(y)
        y += L.bp(rng.standard_normal(n), sr, 1500, 5000) * (0.12 if k % 3 == 2 else 0.05)        # hoarse
        parts.append((y * np.minimum(1, u / 0.1) * np.minimum(1, (1 - u) / 0.25), 0.02))
    y = L.lp(seq(sr, parts), sr, 3500, 1)                                                       # far across the fields
    return outdoor(y, rng, sr, 1.3, 0.35, 3000), {"archetype": k % 3}


def windmill_creak(rng, k):
    sr = SPOT_SR["windmill_creak"]
    arche = k % 3
    if arche == 0:      # one long groan gliding down
        y = wood_creak(rng, sr, rng.uniform(0.9, 1.5), 140, 300, (10, 30))
    elif arche == 1:    # two creaks
        y = seq(sr, [(wood_creak(rng, sr, rng.uniform(0.3, 0.5), 220, 480, (30, 70)), rng.uniform(0.15, 0.35)),
                     (wood_creak(rng, sr, rng.uniform(0.4, 0.7), 200, 420, (20, 55)), 0.0)])
    else:               # the shaft knocks, then squeaks
        m = L.secs(0.2, sr)
        kn = L.resonate(L.white(m, rng) * L.exp_decay(0.2, sr, 0.003), sr, [rng.uniform(120, 180), rng.uniform(400, 600)], [0.05, 0.02])
        y = seq(sr, [(kn, 0.04), (wood_creak(rng, sr, rng.uniform(0.4, 0.8), 400, 800, (60, 140)), 0.0)])
    return outdoor(y, rng, sr, 0.8, 0.2, 3500), {"archetype": int(arche)}


def distant_bell(rng, k):
    sr = SPOT_SR["distant_bell"]
    strikes = [1, 2, 3][k % 3]
    f0 = [rng.uniform(300, 360), rng.uniform(380, 450), rng.uniform(250, 290)][k % 3]
    dur = 3.4 + 1.2 * (strikes - 1)
    y = np.zeros(L.secs(dur, sr))
    for s in range(strikes):
        b = L.modal(sr, f0, "bell", dur=2.6, rng=rng)
        L.place(y, b * (1 - 0.15 * s), s * rng.uniform(1.0, 1.3), sr)
    y = L.lp(y, sr, 2200, 2)
    return outdoor(y, rng, sr, 1.8, 0.5, 2000), {"strikes": strikes}


# kind: (fn, takes, finish max_dur); sample rate in SPOT_SR
ONE_SHOTS = {
    "bird": (bird_call, 16, 1.2),
    "gull": (gull_call, 8, 1.5),
    "wave_crash": (wave_crash, 10, 3.4),
    "wave_slap": (wave_slap, 8, 1.0),
    "gust": (gust, 8, 3.2),
    "cricket": (cricket, 8, 1.3),
    "owl": (owl, 6, 2.2),
    "frog": (frog, 8, 1.2),
    "rooster": (rooster, 3, 2.2),
    "windmill_creak": (windmill_creak, 6, 1.8),
    "distant_bell": (distant_bell, 3, 5.0),
}


def make_spots(out: Path, kinds, allow_overwrite=False) -> int:
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for kind in kinds:
        fn, takes, max_dur = ONE_SHOTS[kind]
        sr = SPOT_SR[kind]
        meta = D.diverse_family(out, kind, takes, fn, sr=sr, ref_db=ONE_SHOT_DB, seed_base="world", max_candidates=max(30, takes * 3),
                                allow_overwrite=allow_overwrite, finish_kw=dict(max_dur=max_dur, fade_out=0.03, trim_db=-50.0))
        b = sum(d["bytes"] for d in meta)
        total += b
        dur = [d["seconds"] for d in meta]
        print("spot %-15s %2d takes (%2d tried) %7.1f KB  dur %.2f-%.2f s  worst sim %.3f" % (
            kind, len(meta), D.tried(meta), b / 1024, min(dur), max(dur), max(d["worst_sim"] for d in meta)), flush=True)
    return total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma list: 'beds', 'spots', bed names and/or one-shot kinds")
    ap.add_argument("--scratch", action="store_true", help="write to the scratch area, not the repo")
    ap.add_argument("--allow-overwrite", action="store_true")
    args = ap.parse_args(argv)
    only = [s for s in args.only.split(",") if s]
    all_beds = list(BEDS) + list(MUFFLED)
    if not only:
        beds, kinds = all_beds, list(ONE_SHOTS)
    else:
        beds = all_beds if "beds" in only else [b for b in only if b in all_beds]
        kinds = list(ONE_SHOTS) if "spots" in only else [k for k in only if k in ONE_SHOTS]
    root = (L.SCRATCH / "world" / "ambience") if args.scratch else OUT
    total = 0
    if beds:
        total += make_beds(root, beds)
    if kinds:
        total += make_spots(root / "spots", kinds, args.allow_overwrite)
    print("TOTAL %.1f KB (%d bytes)" % (total / 1024, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
