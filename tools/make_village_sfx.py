"""Door sounds per building and small field-object sounds for the island village.

Writes mono 16-bit WAVs:
  game/assets/sfx/doors/<room>_<open|close>.wav   (one pair per building with a door)
  game/assets/sfx/field/<name>.wav                 (field_objects.gd interactions)

Everything is synthesised (modal resonators for metal/wood/glass, stick-slip
creaks through a wooden body, filtered noise for wind, hiss and rumble, a noise
reverb tail sized to each building). Levels are matched to the generic door
sound in game/scripts/transition.gd by short-term loudness, so the per-room
sounds sit at the same level under its player (-9 dB).

  .tools/art-venv/Scripts/python.exe tools/make_village_sfx.py [--sheet out.png]

--sheet also renders a spectrogram + envelope contact sheet for review.
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np
import scipy.signal as ss

ROOT = Path(__file__).resolve().parents[1]
DOORS = ROOT / "game/assets/sfx/doors"
FIELD = ROOT / "game/assets/sfx/field"
SR = 32000
# Short-term (120 ms) RMS peak of the generic door "open" sound from transition.gd,
# measured below; every door sound is scaled to sit within a couple of dB of it.
MAX_BYTES = 120_000


# --------------------------------------------------------------------------- helpers
class Sig(np.ndarray):
    """Signal that pads the shorter operand when two sounds of different length are summed."""

    def __add__(self, other):
        if isinstance(other, np.ndarray) and other.ndim == 1 and other.size != self.size:
            n = max(self.size, other.size)
            a = np.zeros(n)
            a[: self.size] += np.asarray(self)
            a[: other.size] += np.asarray(other)
            return a.view(Sig)
        return np.ndarray.__add__(self, other)

    __radd__ = __add__


class Synth:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def noise(self, n: int) -> np.ndarray:
        return self.rng.uniform(-1.0, 1.0, n)


def secs(n: float) -> int:
    return int(round(n * SR))


def time(n: int) -> np.ndarray:
    return np.arange(n) / SR


def band(x, lo, hi, order=2):
    sos = ss.butter(order, [lo, min(hi, SR * 0.45)], btype="band", fs=SR, output="sos")
    return ss.sosfilt(sos, x)


def low(x, hz, order=2):
    return ss.sosfilt(ss.butter(order, hz, btype="low", fs=SR, output="sos"), x)


def high(x, hz, order=2):
    return ss.sosfilt(ss.butter(order, hz, btype="high", fs=SR, output="sos"), x)


def place(out: np.ndarray, sig: np.ndarray, at: float, gain=1.0):
    i = secs(at)
    if i >= out.size:
        return
    j = min(out.size, i + sig.size)
    out[i:j] += sig[: j - i] * gain


def modal(freqs, decays, amps, length, phase_rng=None, attack=0.0008):
    """Sum of exponentially decaying partials (struck metal, wood, glass)."""
    n = secs(length)
    t = time(n)
    out = np.zeros(n)
    for f, d, a in zip(freqs, decays, amps):
        if f >= SR * 0.47:
            continue
        ph = 0.0 if phase_rng is None else phase_rng.uniform(0, 2 * np.pi)
        out += a * np.sin(2 * np.pi * f * t + ph) * np.exp(-t / d)
    if attack > 0:
        out *= np.minimum(t / attack, 1.0)
    # Taper the last 60 ms so a cut-off partial never ends in a click.
    tail = min(n, secs(0.06))
    out[n - tail:] *= np.cos(np.linspace(0, np.pi / 2, tail)) ** 2
    return out.view(Sig)


def click(s: Synth, length=0.03, lo=900, hi=6000, tau=0.004):
    n = secs(length)
    return (band(s.noise(n), lo, hi) * np.exp(-time(n) / tau)).view(Sig)


def thud(s: Synth, f0=85.0, length=0.32, tau=0.07, drop=0.45, body=1.0, grit=0.35):
    """Door slab hitting the frame: a falling low sine plus a lowpassed knock."""
    n = secs(length)
    t = time(n)
    freq = f0 * (1.0 - drop * (1.0 - np.exp(-t / 0.05)))
    phase = 2 * np.pi * np.cumsum(freq) / SR
    tone = np.sin(phase) * np.exp(-t / tau) * body
    knock = low(s.noise(n), 900) * np.exp(-t / 0.012) * grit * 3.0
    return (tone + knock).view(Sig)


def creak(s: Synth, length, f_start, f_end, body=(190, 430, 820, 1450, 2400), q=7.0,
          rough=0.18, wobble=9.0, swell=0.08, release=0.25, metal=False):
    """Stick-slip hinge creak: a jittered pulse train driven through a resonant body."""
    n = secs(length)
    t = time(n)
    pos = np.clip(t / max(length - release * 0.5, 1e-3), 0, 1)
    curve = f_start + (f_end - f_start) * (pos ** 0.8)
    curve *= 1.0 + 0.07 * np.sin(2 * np.pi * wobble * t + s.rng.uniform(0, 6))
    pulses = np.zeros(n)
    i = 0.0
    while i < n:
        k = int(i)
        amp = 1.0 + s.rng.normal(0, rough * 2)
        pulses[k] += amp
        period = SR / max(curve[k], 30.0)
        i += period * (1.0 + s.rng.normal(0, rough))
    pulses = high(pulses, 60)
    out = np.zeros(n)
    for idx, fc in enumerate(body):
        bw = fc / q
        out += band(pulses, max(fc - bw, 40), fc + bw) * (1.0 / (1 + idx * 0.35))
    if metal:
        out += band(pulses, 2800, 5200) * 0.35
    env = np.minimum(t / swell, 1.0) * np.clip((length - t) / release, 0, 1) ** 1.3
    # Creaks come in grabs, not as a steady tone.
    grab = 0.65 + 0.35 * np.abs(np.sin(2 * np.pi * (2.3 + s.rng.uniform(0, 1.5)) * t + s.rng.uniform(0, 3)))
    return out * env * grab


def bell(s: Synth, f0, length=1.2, ratios=(1.0, 2.0, 2.76, 4.07, 5.41, 6.9), decay=0.9,
         bright=1.0, amps=None):
    amps = amps or [1.0, 0.55, 0.42, 0.26 * bright, 0.17 * bright, 0.09 * bright]
    decays = [decay * (1.0 / (1 + 0.55 * i)) for i in range(len(ratios))]
    freqs = [f0 * r * (1 + s.rng.normal(0, 0.0015)) for r in ratios]
    ring = modal(freqs, decays, amps, length, s.rng)
    n = ring.size
    strike = band(s.noise(n), 2500, 9000) * np.exp(-time(n) / 0.0025) * 0.6
    return ring + strike


def tube(s: Synth, f0, length=1.0, decay=0.7):
    """Hollow chime tube (free-free bar partials)."""
    return bell(s, f0, length, ratios=(1.0, 2.756, 5.404, 8.933), decay=decay,
                amps=[1.0, 0.5, 0.22, 0.08])


def wood_block(s: Synth, f0, length=0.18, decay=0.03):
    return modal([f0, f0 * 2.61, f0 * 4.2], [decay, decay * 0.6, decay * 0.4], [1.0, 0.45, 0.2], length, s.rng) \
        + click(s, length, 1200, 5000, 0.002) * 0.4


def wind(s: Synth, length, lo=250, hi=1400, rise=0.35, fall=0.6, gust=0.7):
    n = secs(length)
    t = time(n)
    base = s.noise(n)
    a = band(base, lo, hi, 2)
    b = band(s.noise(n), lo * 1.8, hi * 1.6, 2)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 1.7 * t + 1.0)
    env = np.minimum(t / rise, 1.0) * np.clip((length - t) / fall, 0, 1)
    env *= (1 - gust) + gust * (0.5 + 0.5 * np.sin(2 * np.pi * 0.9 * t - 1.2))
    return (a * (1 - 0.5 * lfo) + b * 0.6 * lfo) * env


def hiss(s: Synth, length, lo=2200, attack=0.015, tau=0.18, tone=0.0):
    n = secs(length)
    t = time(n)
    x = high(s.noise(n), lo, 2)
    x = low(x, 9000)
    env = np.minimum(t / attack, 1.0) * np.exp(-t / tau)
    return x * env


def rumble(s: Synth, length, lo=70, hi=320, ticks=14, fade=0.06):
    n = secs(length)
    t = time(n)
    x = band(s.noise(n), lo, hi, 2) * 2.2
    env = np.minimum(t / fade, 1.0) * np.clip((length - t) / fade, 0, 1)
    out = x * env
    for k in range(ticks):
        at = (k + s.rng.uniform(0.1, 0.9)) / ticks * length * 0.92
        place(out, click(s, 0.02, 600, 3500, 0.003) * env[min(secs(at), n - 1)], at, 0.35)
    return out


def crackle(s: Synth, length, density=38, fade_in=0.05):
    n = secs(length)
    t = time(n)
    out = band(s.noise(n), 60, 400) * 0.25
    for _ in range(int(density * length)):
        at = s.rng.uniform(0, length)
        place(out, click(s, 0.025, 1500, 7000, s.rng.uniform(0.0015, 0.005)), at, s.rng.uniform(0.2, 1.0))
    env = np.minimum(t / fade_in, 1.0) * np.clip((length - t) / (length * 0.6), 0, 1)
    return out * env


def reverb(s: Synth, x, rt60=0.5, wet=0.2, predelay=0.012, tone=4500, early=()):
    """Noise-tail convolution reverb; early = ((delay_s, gain), ...) discrete echoes."""
    n_ir = secs(rt60 * 1.1)
    t = time(n_ir)
    ir = s.noise(n_ir) * np.exp(-6.9 * t / rt60)
    ir = low(ir, tone)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    ir = np.concatenate([np.zeros(secs(predelay)), ir])
    tail = ss.fftconvolve(x, ir)[: x.size + ir.size]
    out = np.zeros(tail.size)
    out[: x.size] += x
    out += tail * wet
    for delay, gain in early:
        place(out, low(x, tone), delay, gain)
    return out


def fades(x, fin=0.002, fout=0.06):
    n = x.size
    a = min(secs(fin), n)
    b = min(secs(fout), n)
    x = x.copy()
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b) ** 2
    return x


MAX_SECONDS = 1.8


def trim(x, floor_db=-56.0, keep=0.05):
    """Cut the silent tail (below floor relative to peak), keeping a short fade."""
    peak = np.max(np.abs(x)) + 1e-12
    from scipy.ndimage import maximum_filter1d
    env = maximum_filter1d(np.abs(x), secs(0.02))
    above = np.nonzero(env > peak * 10 ** (floor_db / 20))[0]
    end = min(x.size, (above[-1] if above.size else x.size) + secs(keep), secs(MAX_SECONDS))
    return fades(x[:end], fout=0.06 if end < secs(MAX_SECONDS) else 0.35)


def short_rms_peak(x, window=0.12, weighted=True):
    """Loudest 120 ms RMS. Weighted drops the sub-150 Hz band the ear (and laptop
    speakers) barely hear, so a low thud and a bright bell compare fairly."""
    if weighted:
        x = high(np.asarray(x, dtype=float), 150)
    w = secs(window)
    if x.size <= w:
        return float(np.sqrt(np.mean(x ** 2)))
    c = np.cumsum(np.concatenate([[0.0], x ** 2]))
    return float(np.sqrt(np.max(c[w:] - c[:-w]) / w))


def level(x, target_rms, peak_ceiling=0.89):
    """Scale to target short-term loudness; a soft limiter keeps peaks under the ceiling."""
    x = x / (short_rms_peak(x) + 1e-9) * target_rms
    if np.max(np.abs(x)) > peak_ceiling * 0.8:
        # Soft knee: transients above ~-3 dBFS are rounded off rather than clipped.
        x = peak_ceiling * np.tanh(x / peak_ceiling)
    return x


def write(path: Path, x: np.ndarray):
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ------------------------------------------------- reference: transition.gd generic door
def generic_door(kind: str) -> np.ndarray:
    rate = 22050
    length = 0.62 if kind == "open" else 0.34
    frames = int(length * rate)
    rng = np.random.default_rng(7)
    t = np.arange(frames) / rate
    if kind == "open":
        click_ = np.exp(-t * 90.0) * rng.uniform(-1, 1, frames) * 0.9
        ct = np.maximum(t - 0.05, 0.0)
        freq = 170.0 + 150.0 * ct + np.sin(ct * 38.0) * 22.0
        phase = np.cumsum(2 * np.pi * freq / rate)
        cr = (np.sin(phase) * 0.5 + np.sin(phase * 2.0) * 0.22) * np.minimum(ct * 12.0, 1.0) * (1.0 - t / length) ** 1.6 * 0.6
        wave_ = click_ + cr + rng.uniform(-0.05, 0.05, frames) * (1.0 - t / length)
    else:
        th = np.sin(2 * np.pi * (88.0 - 40.0 * t) * t) * np.exp(-t * 14.0)
        wave_ = th * 0.95 + rng.uniform(-0.25, 0.25, frames) * np.exp(-t * 55.0)
    return np.clip(wave_, -1, 1) * 21000 / 32767


# --------------------------------------------------------------------------- doors
def door_parts(s: Synth):
    """Shared vocabulary: returns callables for latches and swings."""
    return {
        "metal_latch": lambda f=2300, g=1.0: (modal([f, f * 1.47, f * 2.31, f * 3.2], [0.03, 0.022, 0.015, 0.01],
                                                     [1, 0.6, 0.35, 0.2], 0.12, s.rng) + click(s, 0.05, 2000, 9000, 0.003)) * g,
        "wood_latch": lambda f=720, g=1.0: (wood_block(s, f, 0.15, 0.025) + click(s, 0.04, 800, 4500, 0.004)) * g,
        "swing": lambda length=0.5, g=1.0: low(band(s.noise(secs(length)), 120, 900), 700)
        * np.sin(np.linspace(0, np.pi, secs(length))) ** 2 * g,
    }


def door_sound(room: str, kind: str) -> np.ndarray:
    s = Synth(sum(map(ord, room + kind)) * 7919)
    p = door_parts(s)
    length = 1.0
    out = np.zeros(secs(2.4))
    rt, wet, early, tone = 0.3, 0.12, (), 5000

    if room == "home":  # red brick house: warm painted wood door, thumb latch
        rt, wet = 0.35, 0.13
        if kind == "open":
            place(out, p["metal_latch"](2100, 0.55), 0.0)
            place(out, p["metal_latch"](1750, 0.35), 0.045)
            place(out, creak(s, 0.55, 230, 330, rough=0.14), 0.07, 0.9)
            place(out, p["swing"](0.45, 0.25), 0.12)
        else:
            place(out, p["swing"](0.25, 0.3), 0.0)
            place(out, thud(s, 92, 0.32, 0.06), 0.2)
            place(out, p["metal_latch"](2200, 0.6), 0.215)
    elif room == "workshop":  # town hall: big double wooden door, iron ring handle
        rt, wet, tone = 0.95, 0.24, 3800
        if kind == "open":
            place(out, modal([780, 1240, 1990, 2870], [0.09, 0.07, 0.05, 0.03], [1, .6, .4, .2], 0.3, s.rng), 0.0, 0.7)
            place(out, click(s, 0.05, 700, 3000, 0.006), 0.0, 0.6)
            place(out, creak(s, 0.85, 125, 190, body=(140, 330, 610, 1100, 1900), rough=0.2), 0.08, 1.0)
            place(out, creak(s, 0.7, 150, 215, body=(160, 360, 680, 1250), rough=0.22), 0.3, 0.75)
            place(out, p["swing"](0.8, 0.35), 0.15)
        else:
            place(out, p["swing"](0.35, 0.35), 0.0)
            place(out, thud(s, 68, 0.45, 0.1, body=1.2), 0.22)
            place(out, thud(s, 74, 0.4, 0.09, body=1.0), 0.34, 0.85)
            place(out, modal([780, 1240, 1990], [0.07, 0.05, 0.03], [1, .5, .3], 0.2, s.rng), 0.36, 0.45)
    elif room == "01_cafe":  # door + brass chime bells over the frame
        rt, wet = 0.4, 0.14
        notes = [1046.5, 1318.5, 1568.0, 1760.0, 2093.0]
        if kind == "open":
            place(out, p["metal_latch"](2400, 0.45), 0.0)
            place(out, creak(s, 0.35, 260, 320, rough=0.12), 0.05, 0.5)
            for i, f in enumerate([notes[2], notes[0], notes[3], notes[1], notes[4], notes[2]]):
                place(out, tube(s, f, 1.4, 0.85), 0.07 + i * 0.055 + s.rng.uniform(0, 0.02), 0.32 * (0.92 ** i))
        else:
            place(out, thud(s, 95, 0.3, 0.055), 0.0, 0.85)
            place(out, p["metal_latch"](2300, 0.45), 0.012)
            for i, f in enumerate([notes[1], notes[3], notes[0]]):
                place(out, tube(s, f, 1.1, 0.7), 0.03 + i * 0.07, 0.22 * (0.85 ** i))
    elif room == "02_timber_house":  # heavy timber, wooden thumb latch knock
        rt, wet = 0.32, 0.12
        if kind == "open":
            place(out, p["wood_latch"](640, 1.0), 0.0)
            place(out, p["wood_latch"](520, 0.6), 0.06)
            place(out, creak(s, 0.6, 165, 255, body=(170, 380, 700, 1250, 2100), rough=0.25), 0.1, 1.0)
            place(out, p["swing"](0.5, 0.3), 0.14)
        else:
            place(out, p["swing"](0.22, 0.3), 0.0)
            place(out, thud(s, 80, 0.35, 0.07, grit=0.5), 0.17)
            place(out, p["wood_latch"](600, 0.9), 0.19)
            place(out, p["wood_latch"](690, 0.35), 0.25)
    elif room == "03_teal_cottage":  # seed shop: light door + hollow bamboo chimes
        rt, wet = 0.3, 0.11
        if kind == "open":
            place(out, p["metal_latch"](2500, 0.4), 0.0)
            place(out, creak(s, 0.3, 280, 340, rough=0.1), 0.04, 0.45)
            for i in range(7):
                f = s.rng.choice([620, 740, 830, 990, 1110])
                place(out, wood_block(s, f, 0.3, 0.07), 0.08 + i * 0.06 + s.rng.uniform(0, 0.03), 0.35 * (0.85 ** i))
        else:
            place(out, thud(s, 100, 0.28, 0.05), 0.0, 0.8)
            for i in range(4):
                f = s.rng.choice([620, 740, 830, 990])
                place(out, wood_block(s, f, 0.3, 0.07), 0.04 + i * 0.075, 0.28 * (0.8 ** i))
    elif room == "04_windmill":  # wooden bar latch, big creaky door, wind
        rt, wet, tone = 0.6, 0.18, 3500
        if kind == "open":
            place(out, p["wood_latch"](430, 1.0), 0.0)
            place(out, p["wood_latch"](360, 0.7), 0.09)
            place(out, creak(s, 1.0, 105, 160, body=(120, 280, 520, 980, 1700), rough=0.28, wobble=5.0), 0.15, 1.0)
            place(out, wind(s, 1.45, 260, 1300, 0.35, 0.7), 0.1, 0.45)
        else:
            place(out, wind(s, 0.55, 260, 1300, 0.08, 0.35), 0.0, 0.4)
            place(out, thud(s, 70, 0.45, 0.1, body=1.2, grit=0.5), 0.2)
            place(out, p["wood_latch"](400, 1.0), 0.33)
            place(out, p["wood_latch"](340, 0.5), 0.39)
    elif room == "05_observatory":  # metal hatch: clunk, pneumatic hiss, rim ring
        rt, wet, tone = 0.7, 0.16, 6000
        ring = lambda g: modal([420, 1135, 2050, 3240], [0.5, 0.35, 0.22, 0.14], [0.6, 0.45, 0.3, 0.15], 1.0, s.rng) * g
        if kind == "open":
            place(out, modal([310, 760, 1520], [0.05, 0.035, 0.02], [1, .6, .3], 0.2, s.rng) + click(s, 0.05, 600, 4000, 0.004), 0.0, 0.9)
            place(out, hiss(s, 0.75, 1800, 0.02, 0.22), 0.06, 0.55)
            place(out, ring(0.3), 0.02)
            place(out, creak(s, 0.4, 330, 410, body=(420, 1135, 2050), q=12, rough=0.08, metal=True), 0.25, 0.25)
        else:
            place(out, hiss(s, 0.35, 2400, 0.01, 0.09), 0.0, 0.5)
            place(out, thud(s, 78, 0.3, 0.05, grit=0.25), 0.16, 0.85)
            place(out, modal([310, 760, 1520], [0.05, 0.035, 0.02], [1, .6, .3], 0.2, s.rng), 0.165, 0.8)
            place(out, ring(0.35), 0.165)
    elif room == "06_orange_cottage":  # bakery: door and one soft brass bell
        rt, wet = 0.34, 0.12
        if kind == "open":
            place(out, p["metal_latch"](2150, 0.45), 0.0)
            place(out, creak(s, 0.4, 240, 300, rough=0.12), 0.05, 0.55)
            place(out, bell(s, 1175, 1.3, decay=0.8, bright=0.6), 0.08, 0.42)
            place(out, bell(s, 1175, 1.0, decay=0.6, bright=0.6), 0.29, 0.22)
        else:
            place(out, thud(s, 95, 0.3, 0.055), 0.0, 0.85)
            place(out, p["metal_latch"](2200, 0.45), 0.012)
            place(out, bell(s, 1175, 1.0, decay=0.6, bright=0.5), 0.03, 0.26)
    elif room == "07_greenhouse":  # glass sliding door on rollers
        rt, wet, tone = 0.45, 0.14, 7000
        glass = lambda g: modal([2630, 4120, 6310, 8120], [0.18, 0.12, 0.08, 0.05], [0.5, 0.4, 0.25, 0.12], 0.6, s.rng) * g
        if kind == "open":
            place(out, click(s, 0.04, 1500, 6000, 0.004), 0.0, 0.5)
            place(out, rumble(s, 0.62, 70, 340, 16), 0.03, 0.9)
            place(out, glass(0.12), 0.05)
            place(out, thud(s, 140, 0.18, 0.025, grit=0.3), 0.64, 0.45)
            place(out, glass(0.2), 0.65)
        else:
            place(out, rumble(s, 0.5, 70, 340, 13), 0.0, 0.9)
            place(out, thud(s, 120, 0.22, 0.03, grit=0.35), 0.5, 0.6)
            place(out, glass(0.3), 0.505)
            place(out, click(s, 0.04, 1500, 6000, 0.004), 0.56, 0.4)
    elif room == "11_purple_house":  # music parlour: two-tone door chime
        rt, wet = 0.42, 0.14
        if kind == "open":
            place(out, p["metal_latch"](2250, 0.5), 0.0)
            place(out, creak(s, 0.4, 250, 310, rough=0.12), 0.05, 0.45)
            place(out, tube(s, 659.3, 1.3, 0.9), 0.06, 0.45)
            place(out, tube(s, 523.3, 1.5, 1.0), 0.42, 0.45)
        else:
            place(out, thud(s, 92, 0.3, 0.055), 0.0, 0.85)
            place(out, p["metal_latch"](2250, 0.5), 0.012)
            place(out, tube(s, 523.3, 1.2, 0.7), 0.04, 0.22)
    elif room == "12_blue_house":  # bedroom: quiet, careful door
        rt, wet = 0.28, 0.1
        if kind == "open":
            place(out, p["metal_latch"](2600, 0.4), 0.0)
            place(out, p["metal_latch"](2350, 0.3), 0.07)
            place(out, creak(s, 0.35, 300, 370, rough=0.09), 0.1, 0.35)
            place(out, p["swing"](0.4, 0.2), 0.1)
        else:
            place(out, p["swing"](0.3, 0.3), 0.0)
            place(out, thud(s, 110, 0.18, 0.035, grit=0.2), 0.24, 0.5)
            place(out, p["metal_latch"](2600, 0.45), 0.25)
            place(out, p["metal_latch"](2350, 0.35), 0.31)
    elif room == "13_shop":  # general store: brass shop bell on a coil spring
        rt, wet = 0.36, 0.12
        hits = [0.0, 0.11, 0.2, 0.27, 0.33, 0.38]
        if kind == "open":
            place(out, p["metal_latch"](2300, 0.4), 0.0)
            for i, at in enumerate(hits):
                place(out, bell(s, 2210, 1.1, decay=0.55, bright=1.0), 0.05 + at, 0.48 * (0.72 ** i))
            place(out, creak(s, 0.3, 260, 320, rough=0.1), 0.06, 0.3)
        else:
            place(out, thud(s, 96, 0.3, 0.055), 0.0, 0.8)
            for i, at in enumerate(hits[:4]):
                place(out, bell(s, 2210, 1.0, decay=0.5), 0.02 + at, 0.4 * (0.7 ** i))
    elif room == "16_blue_cottage":  # fireplace cottage: door, then the hearth crackles
        rt, wet = 0.33, 0.12
        if kind == "open":
            place(out, p["wood_latch"](700, 0.8), 0.0)
            place(out, creak(s, 0.5, 200, 280, rough=0.18), 0.06, 0.8)
            place(out, low(crackle(s, 1.1, 30), 5000), 0.25, 0.55)
        else:
            place(out, low(crackle(s, 0.45, 26), 2200), 0.0, 0.45)
            place(out, thud(s, 88, 0.32, 0.06), 0.12)
            place(out, p["wood_latch"](680, 0.8), 0.135)
    elif room == "17_lighthouse":  # stone tower, heavy iron door, echo
        rt, wet, tone = 1.5, 0.3, 3000
        early = ((0.075, 0.28), (0.15, 0.2), (0.24, 0.14), (0.37, 0.08))
        iron = lambda g, f=345: modal([f, f * 2.52, f * 4.29, f * 6.7, f * 9.1], [0.35, 0.22, 0.14, 0.09, 0.05],
                                      [1, .7, .45, .25, .12], 1.0, s.rng) * g
        if kind == "open":
            place(out, iron(0.7, 410) + click(s, 0.06, 900, 5000, 0.005) * 0.8, 0.0)
            place(out, creak(s, 0.9, 72, 104, body=(110, 250, 520, 980), q=9, rough=0.22, metal=True), 0.12, 1.0)
            place(out, p["swing"](0.7, 0.3), 0.15)
        else:
            place(out, p["swing"](0.3, 0.35), 0.0)
            place(out, thud(s, 58, 0.5, 0.12, body=1.3, grit=0.5), 0.2)
            place(out, iron(0.55, 345), 0.205)
            place(out, iron(0.35, 410) + click(s, 0.05, 900, 5000, 0.004), 0.36)
    else:
        raise KeyError(room)

    out = reverb(s, out, rt, wet, 0.01, tone, early)
    return trim(out)


ROOMS = ["home", "workshop", "01_cafe", "02_timber_house", "03_teal_cottage", "04_windmill", "05_observatory",
         "06_orange_cottage", "07_greenhouse", "11_purple_house", "12_blue_house", "13_shop", "16_blue_cottage",
         "17_lighthouse"]


# --------------------------------------------------------------------------- field sounds
def field_sound(name: str) -> np.ndarray:
    s = Synth(sum(map(ord, name)) * 104729)
    out = np.zeros(secs(2.2))
    rt, wet = 0.5, 0.08
    if name == "chimes":  # wind chimes: pentatonic tubes in a loose cascade
        notes = [1174.7, 1318.5, 1568.0, 1760.0, 2093.0, 2349.3]
        for i in range(9):
            place(out, tube(s, s.rng.choice(notes), 1.6, 1.0), 0.02 + i * 0.11 + s.rng.uniform(0, 0.06), 0.3 * (0.9 ** i))
    elif name == "gong":
        f = 128.0
        g = modal([f, f * 1.52, f * 2.03, f * 2.71, f * 3.3, f * 4.4, f * 5.9], [1.6, 1.2, 0.9, 0.7, 0.5, 0.35, 0.25],
                  [1, .7, .55, .4, .3, .2, .12], 2.1, s.rng, attack=0.004)
        g = g + low(click(s, 0.08, 100, 1200, 0.01), 1500) * 0.8
        # The shimmer swells a moment after the strike, like a real tam-tam.
        t = time(g.size)
        g += band(s.noise(g.size), 1200, 3800) * 0.06 * (1 - np.exp(-t / 0.25)) * np.exp(-t / 0.9)
        place(out, g, 0.0)
        rt, wet = 1.2, 0.18
    elif name == "coin":  # coin tossed: ping, flip, plop into the well water far below
        place(out, bell(s, 3950, 0.5, ratios=(1, 1.53, 2.4, 3.1), decay=0.18, amps=[1, .5, .3, .2]), 0.0, 0.35)
        for i in range(3):
            place(out, bell(s, 4200 + i * 90, 0.2, ratios=(1, 1.6), decay=0.05, amps=[1, .4]), 0.09 + i * 0.07, 0.12)
        t = time(secs(0.25))
        plop = np.sin(2 * np.pi * np.cumsum(500 + 900 * (1 - np.exp(-t / 0.03))) / SR) * np.exp(-t / 0.05)
        place(out, plop * 0.6 + band(s.noise(t.size), 400, 2500) * np.exp(-t / 0.02) * 0.3, 0.75, 1.0)
        rt, wet = 0.9, 0.35
    elif name == "water":  # drinking fountain: tap squeak, stream, drips
        place(out, creak(s, 0.12, 900, 1100, body=(1200, 2600), q=10, rough=0.05, release=0.05, swell=0.01), 0.0, 0.25)
        n = secs(1.05)
        t = time(n)
        stream = band(s.noise(n), 900, 5200) * (np.minimum(t / 0.05, 1) * np.clip((1.05 - t) / 0.25, 0, 1))
        stream *= 0.8 + 0.2 * np.sin(2 * np.pi * 11 * t)
        place(out, stream * 0.5, 0.08)
        for i in range(10):
            f = s.rng.uniform(700, 1500)
            tt = time(secs(0.06))
            drop = np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * tt / 0.06)) / SR) * np.exp(-tt / 0.015)
            place(out, drop, 0.1 + s.rng.uniform(0, 1.15), 0.35)
    elif name == "birds":  # flock lifting off: wing flutter + a couple of chirps
        n = secs(0.9)
        t = time(n)
        for k in range(5):
            rate = s.rng.uniform(14, 20)
            beats = (0.5 + 0.5 * np.sin(2 * np.pi * rate * t + s.rng.uniform(0, 6))) ** 3
            flap = band(s.noise(n), 500, 4000) * beats * np.exp(-t / 0.45) * np.minimum(t / 0.02, 1)
            place(out, flap, k * 0.035, 0.5)
        for i in range(4):
            tt = time(secs(0.09))
            f0 = s.rng.uniform(3200, 4600)
            sweep = f0 * (1 + 0.35 * np.sin(np.pi * tt / 0.09))
            chirp = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.sin(np.pi * tt / 0.09) ** 2
            place(out, chirp, 0.1 + i * 0.13 + s.rng.uniform(0, 0.05), 0.22)
        rt, wet = 0.6, 0.06
    elif name == "shutter":  # film camera: shutter clack + advance lever
        place(out, modal([1800, 3100, 4700], [0.012, 0.009, 0.006], [1, .6, .4], 0.06, s.rng) + click(s, 0.03, 2500, 9000, 0.002), 0.0, 0.8)
        place(out, modal([1500, 2700], [0.01, 0.007], [1, .5], 0.05, s.rng) + click(s, 0.03, 2000, 8000, 0.002), 0.055, 0.6)
        n = secs(0.2)
        wind_ = band(s.noise(n), 2000, 7000) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 70 * time(n)))) * 0.25
        place(out, wind_ * np.hanning(n), 0.28)
        rt, wet = 0.25, 0.05
    elif name == "creak_soft":  # swing chains / rocking chair: slow squeak
        place(out, creak(s, 0.55, 520, 600, body=(600, 1300, 2500), q=9, rough=0.06, swell=0.12, release=0.3, metal=True), 0.0, 0.6)
        place(out, creak(s, 0.45, 560, 500, body=(600, 1300, 2500), q=9, rough=0.06, swell=0.1, release=0.25, metal=True), 0.75, 0.45)
        rt, wet = 0.3, 0.05
    elif name == "wood_creak":  # rocking chair / hammock rope on wood
        place(out, creak(s, 0.5, 180, 230, body=(200, 450, 900, 1600), rough=0.2, swell=0.1), 0.0, 0.8)
        place(out, creak(s, 0.4, 210, 170, body=(200, 450, 900, 1600), rough=0.2, swell=0.08), 0.7, 0.55)
        rt, wet = 0.25, 0.04
    elif name == "paper":  # pinned notes / letters rustle
        n = secs(0.5)
        t = time(n)
        crinkle = np.zeros(n)
        for _ in range(60):
            place(crinkle, click(s, 0.02, 2500, 9000, s.rng.uniform(0.001, 0.004)), s.rng.uniform(0, 0.45), s.rng.uniform(0.1, 0.6))
        crinkle += band(s.noise(n), 1500, 6000) * 0.15 * np.sin(np.pi * t / 0.5)
        place(out, crinkle, 0.0)
        rt, wet = 0.2, 0.04
    elif name == "lid":  # mailbox flap / box lid: tin hinge + clap
        place(out, creak(s, 0.18, 700, 820, body=(800, 1700, 3000), q=10, rough=0.08, release=0.06, swell=0.02, metal=True), 0.0, 0.4)
        place(out, modal([920, 1610, 2480, 3900], [0.06, 0.04, 0.03, 0.02], [1, .6, .4, .2], 0.25, s.rng) + click(s, 0.03, 1500, 7000, 0.002), 0.17, 0.7)
        rt, wet = 0.25, 0.05
    elif name == "whoosh":  # signpost travel
        n = secs(0.9)
        t = time(n)
        env = np.sin(np.pi * np.clip(t / 0.9, 0, 1)) ** 2
        sweep = band(s.noise(n), 300, 2500) * env
        place(out, sweep, 0.0, 0.9)
        place(out, tube(s, 1568.0, 1.0, 0.6), 0.55, 0.2)
        place(out, tube(s, 2093.0, 1.0, 0.6), 0.62, 0.16)
        rt, wet = 0.6, 0.12
    elif name == "brass":  # telescope: brass tube slides out, lens cap click
        place(out, rumble(s, 0.35, 900, 3200, 10, 0.03) * 0.5, 0.0)
        place(out, modal([2600, 4100, 6200], [0.04, 0.03, 0.02], [1, .5, .3], 0.12, s.rng) + click(s, 0.03, 2000, 8000, 0.002), 0.36, 0.7)
        rt, wet = 0.3, 0.05
    elif name == "vane":  # weather vane spins on its pivot
        place(out, creak(s, 0.7, 760, 980, body=(900, 1900, 3300), q=12, rough=0.05, swell=0.06, release=0.3, metal=True), 0.0, 0.5)
        place(out, wind(s, 1.0, 300, 1600, 0.2, 0.5), 0.0, 0.3)
        rt, wet = 0.4, 0.06
    elif name == "box":  # wooden lost-and-found box lid
        place(out, creak(s, 0.25, 240, 290, rough=0.15, release=0.08, swell=0.03), 0.0, 0.5)
        place(out, wood_block(s, 520, 0.2, 0.03) + thud(s, 120, 0.15, 0.03, grit=0.3) * 0.5, 0.26, 0.9)
        rt, wet = 0.25, 0.05
    else:
        raise KeyError(name)
    out = reverb(s, out, rt, wet, 0.008, 6000)
    return trim(out)


FIELD_SOUNDS = ["chimes", "gong", "coin", "water", "birds", "shutter", "creak_soft", "wood_creak", "paper", "lid",
                "whoosh", "brass", "vane", "box"]


# --------------------------------------------------------------------------- review sheet
def sheet(entries, path: Path):
    from PIL import Image, ImageDraw
    cols = 4
    tile_w, tile_h = 420, 190
    rows = (len(entries) + cols - 1) // cols
    img = Image.new("RGB", (cols * tile_w, rows * tile_h), (18, 20, 26))
    d = ImageDraw.Draw(img)
    for k, (name, x) in enumerate(entries):
        ox, oy = (k % cols) * tile_w, (k // cols) * tile_h
        f, t, z = ss.stft(x, SR, nperseg=512, noverlap=384)
        mag = 20 * np.log10(np.abs(z) + 1e-7)
        mag = np.clip((mag + 100) / 80, 0, 1)
        h = 120
        # Log-ish frequency rows: 60 Hz .. 12 kHz.
        fq = np.geomspace(60, 12000, h)[::-1]
        idx = np.clip(np.searchsorted(f, fq), 0, f.size - 1)
        spec = mag[idx]
        span = 2.0  # seconds across a tile
        cols_px = tile_w - 20
        tx = np.clip((np.linspace(0, span, cols_px) / (t[1] - t[0])).astype(int), 0, spec.shape[1] - 1)
        valid = np.linspace(0, span, cols_px) <= x.size / SR
        spec = spec[:, tx] * valid
        rgb = np.stack([spec ** 0.8 * 255, spec ** 1.6 * 220, (spec ** 0.5) * 140 + 30 * spec], -1).astype(np.uint8)
        img.paste(Image.fromarray(rgb), (ox + 10, oy + 22))
        # Envelope (abs peak per column) under the spectrogram.
        per = max(1, int(span * SR / cols_px))
        for c in range(cols_px):
            seg = x[c * per:(c + 1) * per]
            if seg.size == 0:
                break
            a = float(np.max(np.abs(seg)))
            d.line([(ox + 10 + c, oy + 182), (ox + 10 + c, oy + 182 - int(a * 38))], fill=(120, 200, 140))
        rms = short_rms_peak(x)
        d.text((ox + 10, oy + 5), f"{name}  {x.size / SR:.2f}s  pk {20 * np.log10(np.max(np.abs(x)) + 1e-9):.1f}dB  "
                                  f"st-rms {20 * np.log10(rms + 1e-9):.1f}dB", fill=(235, 225, 190))
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="")
    args = ap.parse_args()
    ref = generic_door("open")
    ref_close_x = generic_door("close")
    # The reference runs at 22050 Hz; resample to SR before measuring.
    ref = np.interp(np.arange(int(ref.size * SR / 22050)) * 22050 / SR, np.arange(ref.size), ref)
    ref_close_x = np.interp(np.arange(int(ref_close_x.size * SR / 22050)) * 22050 / SR, np.arange(ref_close_x.size), ref_close_x)
    target = short_rms_peak(ref)
    ref_close = short_rms_peak(ref_close_x)
    print(f"generic door: open st-rms {20 * np.log10(target):.1f} dBFS peak {20 * np.log10(np.max(np.abs(ref))):.1f}; "
          f"close st-rms {20 * np.log10(ref_close):.1f}")
    entries = [("generic_open", ref), ("generic_close", ref_close_x)]
    for room in ROOMS:
        for kind in ("open", "close"):
            x = door_sound(room, kind)
            # Closing thuds land a touch softer than the opening, like the generic pair.
            x = level(x, target if kind == "open" else ref_close)
            path = DOORS / f"{room}_{kind}.wav"
            write(path, x)
            size = path.stat().st_size
            assert size < MAX_BYTES, (path, size)
            entries.append((f"{room}_{kind}", x))
            print(f"{path.name:32s} {x.size / SR:5.2f}s {size / 1024:6.1f} KB  peak {20 * np.log10(np.max(np.abs(x))):6.1f} dBFS"
                  f"  st-rms {20 * np.log10(short_rms_peak(x)):6.1f}")
    for name in FIELD_SOUNDS:
        x = field_sound(name)
        x = level(x, target * 0.85)
        path = FIELD / f"{name}.wav"
        write(path, x)
        size = path.stat().st_size
        assert size < MAX_BYTES, (path, size)
        entries.append((f"field/{name}", x))
        print(f"{'field/' + path.name:32s} {x.size / SR:5.2f}s {size / 1024:6.1f} KB  peak {20 * np.log10(np.max(np.abs(x))):6.1f} dBFS"
              f"  st-rms {20 * np.log10(short_rms_peak(x)):6.1f}")
    if args.sheet:
        sheet(entries, Path(args.sheet))
        print("sheet", args.sheet)


if __name__ == "__main__":
    main()
