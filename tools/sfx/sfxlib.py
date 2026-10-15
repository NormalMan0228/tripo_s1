"""sfxlib: synthesis building blocks, WAV IO, loudness matching and the take-family writer
shared by every tools/sfx generator (Villagen sound variety work).

    import sys
    sys.path.insert(0, r"D:/lsm26/wt/sound/tools/sfx")   # or Path(__file__).parent
    import sfxlib as L

    def knock(rng, i):                     # take i: an archetype from the grid + small random detail
        mat, hits, step = L.cycle(i, ["wood", "ceramic"], [1, 2, 3], [1.0, 1.15, 0.86, 1.32, 0.76])
        f0 = 430 * step * rng.uniform(0.985, 1.015)
        x = L.modal(L.DEFAULT_SR, f0, mat, rng=rng)
        for h in range(1, hits):           # double / triple knocks
            x = L.mix(x, (L.modal(L.DEFAULT_SR, f0 * rng.uniform(1.03, 1.1), mat, rng=rng), 0.6, h * rng.uniform(0.08, 0.12)))
        return x

    ref = L.ref_db_of(L.SFX_ROOT / "ui" / "click.wav")
    meta = L.make_family(L.SFX_ROOT / "ui", "click", 10, knock, ref_db=ref)   # click_1..click_10.wav

Conventions (tools/sfx/README.md has the full list):
- mono 16-bit PCM with the canonical 44-byte header (stdlib wave), 22050 Hz by default,
  32000 Hz where brightness matters;
- loudness = the loudest 120 ms RMS after a 2nd-order 150 Hz high-pass, the same measure as
  game/tests/audio_bank_check.gd and the older generators (make_village_sfx.short_rms_peak);
- finish(): DC removal, peak guard at -1 dBFS (gain-envelope limiter, no clipping), silence
  trimmed below -60 dBFS, raised-cosine fades (3 ms in, 20 ms out);
- make_family() never overwrites a file tracked in git (team recordings, earlier generators)
  unless allow_overwrite=True.

Signals are float64 numpy arrays in [-1, 1]. Building blocks return roughly peak-normalised
signals (peak ~1) so layers mix by gain; final level comes from finish()/match_to().
Durations and times are in seconds unless a name says samples (n, idx, start/end of segments()).
Every random choice takes an explicit numpy Generator (rng) so takes are reproducible.

Self-test: python tools/sfx/sfxlib.py [--out DIR]   (renders demo families to a temp dir)
"""
from __future__ import annotations

import glob
import hashlib
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
from scipy import signal as ss
from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d

REPO = Path(__file__).resolve().parents[2]
SFX_ROOT = REPO / "game" / "assets" / "sfx"
SCRATCH = Path(os.environ.get(
    "SFX_SCRATCH",
    r"C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\72dd4eba-2f77-432d-a4e0-50886f25eeb1\scratchpad\sfxwork"))
DEFAULT_SR = 22050
BRIGHT_SR = 32000
CEILING = 0.89            # peak guard, about -1 dBFS
SILENCE_DB = -60.0        # trim floor (absolute dBFS)
LEVEL_TOL_DB = 1.5        # make_family warns when a take misses ref_db by more than this
EPS = 1e-12

__all__ = [
    "REPO", "SFX_ROOT", "SCRATCH", "DEFAULT_SR", "BRIGHT_SR", "CEILING",
    "secs", "tvec", "db", "undb", "semitones",
    "write_wav", "read_wav", "resample", "repitch",
    "finish", "limit", "fades", "trim_silence", "remove_dc", "loopify",
    "st_rms_peak_db", "peak_db", "match_to", "ref_db_of",
    "white", "pink", "brown", "noise",
    "lp", "hp", "bp", "peaking", "shelf", "tilt", "svf", "resonate",
    "env_points", "adsr", "exp_decay", "attack_decay",
    "MATERIALS", "modal", "modal_bank", "ks_pluck", "fm_bell", "osc", "chirp",
    "scatter", "reverb", "saturate",
    "pad_to", "place", "mix", "concat", "norm_peak", "norm_rms",
    "envelope", "onsets", "segments", "take_slice", "xfade_concat", "transient_shape", "splice",
    "cycle", "take_seed", "git_tracked", "write_take", "make_family", "family_report",
]


# --------------------------------------------------------------------------- units
def secs(t: float, sr: int = DEFAULT_SR) -> int:
    """Seconds -> whole samples."""
    return max(0, int(round(float(t) * sr)))


def tvec(n: int, sr: int = DEFAULT_SR) -> np.ndarray:
    """Time axis (s) for n samples."""
    return np.arange(int(n)) / float(sr)


def db(x: float) -> float:
    """Linear amplitude -> dB (floored)."""
    return 20.0 * math.log10(max(abs(float(x)), EPS))


def undb(d: float) -> float:
    """dB -> linear amplitude."""
    return 10.0 ** (float(d) / 20.0)


def semitones(n: float) -> float:
    """Frequency ratio of n semitones."""
    return 2.0 ** (float(n) / 12.0)


def _arr(x) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    if a.ndim != 1:
        raise ValueError("expected a mono 1-D signal, got shape %s" % (a.shape,))
    return a


def _rng(rng) -> np.random.Generator:
    return rng if isinstance(rng, np.random.Generator) else np.random.default_rng(0 if rng is None else rng)


def _nyq(hz, sr):
    return np.clip(hz, 1.0, sr * 0.45)


# --------------------------------------------------------------------------- IO
def write_wav(path, x, sr: int = DEFAULT_SR) -> Path:
    """Mono 16-bit PCM, canonical 44-byte header (stdlib wave). Values are clipped to 16-bit range;
    run finish() first so nothing actually clips."""
    a = _arr(x)
    if not np.all(np.isfinite(a)):
        raise ValueError("non-finite samples in %s" % path)
    pcm = np.clip(np.round(a * 32767.0), -32768, 32767).astype("<i2")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())
    return path


def wav_info(path) -> dict:
    """Header facts: format tag, channels, sr, bits, frames, data offset (44 = canonical)."""
    raw = Path(path).read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("%s is not a RIFF/WAVE file" % path)
    pos, fmt, data_off, data_len = 12, None, -1, 0
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            fmt = raw[pos + 8:pos + 8 + size]
        elif cid == b"data":
            data_off, data_len = pos + 8, min(size, len(raw) - pos - 8)
            break
        pos += 8 + size + (size & 1)
    if fmt is None or data_off < 0:
        raise ValueError("%s has no fmt/data chunk" % path)
    tag, ch, sr, _, block, bits = struct.unpack("<HHIIHH", fmt[:16])
    if tag == 0xFFFE and len(fmt) >= 26:
        tag = struct.unpack("<H", fmt[24:26])[0]
    return {"tag": tag, "channels": ch, "sr": sr, "bits": bits, "block": block,
            "frames": data_len // max(block, 1), "data_offset": data_off, "data_len": data_len}


def read_wav(path, mono: bool = True):
    """Any PCM 8/16/24/32-bit or float WAV -> (float signal, sr). Stereo is averaged to mono
    unless mono=False (then shape (n, channels))."""
    info = wav_info(path)
    raw = Path(path).read_bytes()
    data = raw[info["data_offset"]:info["data_offset"] + info["frames"] * info["block"]]
    tag, bits, ch = info["tag"], info["bits"], info["channels"]
    if tag == 1:
        if bits == 8:
            a = (np.frombuffer(data, np.uint8).astype(float) - 128.0) / 128.0
        elif bits == 16:
            a = np.frombuffer(data, "<i2").astype(float) / 32768.0
        elif bits == 24:
            b = np.frombuffer(data, np.uint8).reshape(-1, 3).astype(np.int32)
            v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            v = np.where(v >= 1 << 23, v - (1 << 24), v)
            a = v.astype(float) / float(1 << 23)
        elif bits == 32:
            a = np.frombuffer(data, "<i4").astype(float) / 2147483648.0
        else:
            raise ValueError("%s: unsupported PCM width %d" % (path, bits))
    elif tag == 3:
        a = np.frombuffer(data, "<f4" if bits == 32 else "<f8").astype(float)
    else:
        raise ValueError("%s: unsupported WAV format tag %d" % (path, tag))
    a = a[: (a.size // ch) * ch].reshape(-1, ch)
    return (a.mean(axis=1) if mono else a), int(info["sr"])


def resample(x, sr_from: int, sr_to: int) -> np.ndarray:
    """Polyphase resample (scipy.signal.resample_poly)."""
    a = _arr(x)
    if int(sr_from) == int(sr_to) or a.size == 0:
        return a.copy()
    fr = Fraction(int(sr_to), int(sr_from)).limit_denominator(2000)
    return ss.resample_poly(a, fr.numerator, fr.denominator)


def repitch(x, ratio: float) -> np.ndarray:
    """Pitch shift by resampling (tape-speed): ratio 1.06 = 6 % higher AND 6 % shorter."""
    a = _arr(x)
    if abs(ratio - 1.0) < 1e-6 or a.size == 0:
        return a.copy()
    fr = Fraction(1.0 / float(ratio)).limit_denominator(400)
    return ss.resample_poly(a, fr.numerator, fr.denominator)


# --------------------------------------------------------------------------- loudness
def _weight(x, sr):
    return ss.sosfilt(ss.butter(2, 150.0, btype="high", fs=sr, output="sos"), x)


def st_rms_peak_db(x, sr: int = DEFAULT_SR, win: float = 0.12, weighted: bool = True) -> float:
    """Loudest short-term RMS (dBFS) over a `win` s window; weighted = 2nd-order 150 Hz
    high-pass first (the game's audio_bank_check measure)."""
    a = _arr(x)
    if a.size == 0:
        return -200.0
    if weighted:
        a = _weight(a, sr)
    w = max(1, secs(win, sr))
    if a.size <= w:
        return db(math.sqrt(float(np.mean(a * a))))
    c = np.concatenate([[0.0], np.cumsum(a * a)])
    return db(math.sqrt(max(float(np.max(c[w:] - c[:-w])) / w, 0.0)))


def peak_db(x) -> float:
    a = _arr(x)
    return db(float(np.max(np.abs(a)))) if a.size else -200.0


def match_to(x, sr: int, ref_db: float, win: float = 0.12, weighted: bool = True) -> np.ndarray:
    """Scale so st_rms_peak_db equals ref_db (no peak guard; finish() limits afterwards)."""
    a = _arr(x)
    cur = st_rms_peak_db(a, sr, win, weighted)
    if cur <= -199.0:
        return a.copy()
    return a * undb(ref_db - cur)


def ref_db_of(paths, win: float = 0.12, weighted: bool = True) -> float:
    """st-rms (dBFS) of an existing WAV, or the median over several (path, dir/glob string or list)."""
    if isinstance(paths, (str, Path)):
        p = Path(paths)
        if p.is_dir():
            items = sorted(p.glob("*.wav"))
        elif any(c in str(paths) for c in "*?["):
            items = sorted(Path(q) for q in glob.glob(str(paths)))
        else:
            items = [p]
    else:
        items = [Path(p) for p in paths]
    if not items:
        raise FileNotFoundError("no reference WAV for %s" % (paths,))
    vals = []
    for p in items:
        x, sr = read_wav(p)
        vals.append(st_rms_peak_db(x, sr, win, weighted))
    return float(np.median(vals))


# --------------------------------------------------------------------------- finishing
def remove_dc(x, sr: int = DEFAULT_SR, hp_hz: float = 20.0) -> np.ndarray:
    a = _arr(x)
    a = a - float(np.mean(a)) if a.size else a
    if hp_hz and a.size > 8:
        a = ss.sosfilt(ss.butter(2, hp_hz, btype="high", fs=sr, output="sos"), a)
    return a


def limit(x, sr: int = DEFAULT_SR, ceiling: float = CEILING, ms: float = 4.0) -> np.ndarray:
    """Look-ahead gain-envelope limiter: |out| <= ceiling guaranteed, smooth gain (no hard clip).
    The gain is a min-filter of ceiling/|x| smoothed by a box of the same width, which stays
    below the needed gain at every sample."""
    a = _arr(x)
    pk = float(np.max(np.abs(a))) if a.size else 0.0
    if pk <= ceiling:
        return a.copy()
    w = max(3, secs(ms / 1000.0, sr) | 1)
    need = np.minimum(1.0, ceiling / (np.abs(a) + EPS))
    g = minimum_filter1d(need, w, mode="nearest")
    g = uniform_filter1d(g, w, mode="nearest")
    g = np.minimum(g, need)       # numerical safety
    return a * g


def trim_silence(x, sr: int = DEFAULT_SR, floor_db: float = SILENCE_DB, lead: bool = True,
                 keep: float = 0.012, pre: float = 0.0015) -> np.ndarray:
    """Cut samples below floor_db (absolute dBFS, 10 ms peak envelope) at the end and, with lead,
    at the start; keeps `keep` s after the last loud sample and `pre` s before the first."""
    a = _arr(x)
    if a.size == 0:
        return a
    env = maximum_filter1d(np.abs(a), max(1, secs(0.01, sr)))
    loud = np.nonzero(env > undb(floor_db))[0]
    if loud.size == 0:
        return a[: secs(0.02, sr)].copy()
    start = max(0, loud[0] - secs(pre, sr)) if lead else 0
    end = min(a.size, loud[-1] + secs(keep, sr))
    return a[start:end].copy()


def fades(x, sr: int = DEFAULT_SR, fade_in: float = 0.003, fade_out: float = 0.02) -> np.ndarray:
    """Raised-cosine fade in/out; the first and last samples end up exactly 0."""
    a = _arr(x).copy()
    n = a.size
    i = min(secs(fade_in, sr), n // 2)
    o = min(secs(fade_out, sr), n - i)
    if i > 0:
        a[:i] *= np.sin(0.5 * np.pi * np.arange(i) / i) ** 2
    if o > 0:
        a[n - o:] *= np.cos(0.5 * np.pi * (np.arange(o) + 1) / o) ** 2
    if n:
        a[0] = 0.0
        a[-1] = 0.0
    return a


def finish(x, sr: int = DEFAULT_SR, ref_db: float | None = None, fade_in: float = 0.003,
           fade_out: float = 0.02, trim_db: float = SILENCE_DB, trim_lead: bool = True,
           keep: float = 0.012, ceiling: float = CEILING, max_dur: float | None = None,
           hp_hz: float = 20.0, win: float = 0.12, loop: bool = False) -> np.ndarray:
    """DC removal -> optional loudness match to ref_db (st-rms) with the peak limiter, iterated
    so limiting does not leave the take quiet -> trim silence below trim_db dBFS -> optional
    max_dur cut -> fades. Never clips.
    loop=True (beds, loops made with loopify()): only the mean is removed and the level matched;
    no high-pass, trim or fades, so the seam stays continuous."""
    a = _arr(x)
    if not np.all(np.isfinite(a)):
        raise ValueError("non-finite samples")
    if loop:
        a = a - float(np.mean(a))
        if ref_db is not None:
            a = match_to(a, sr, ref_db, win)
        return np.clip(limit(a, sr, ceiling), -ceiling, ceiling)
    a = remove_dc(a, sr, hp_hz)
    if ref_db is not None:
        for _ in range(4):
            a = limit(match_to(a, sr, ref_db, win), sr, ceiling)
            if abs(st_rms_peak_db(a, sr, win) - ref_db) < 0.15:
                break
    else:
        a = limit(a, sr, ceiling)
    a = trim_silence(a, sr, trim_db, trim_lead, keep)
    if max_dur is not None and a.size > secs(max_dur, sr):
        a = a[: secs(max_dur, sr)]
    a = fades(a, sr, fade_in, fade_out)
    return np.clip(a, -ceiling, ceiling)


def loopify(x, sr: int = DEFAULT_SR, xfade: float = 0.05) -> np.ndarray:
    """Seamless loop: the last `xfade` s are equal-power crossfaded over the head, so the result
    (xfade s shorter) wraps without a seam. High-pass/remove_dc() BEFORE this, then
    finish(..., loop=True)."""
    a = _arr(x)
    k = min(secs(xfade, sr), a.size // 3)
    if k <= 0:
        return a.copy()
    u = np.arange(k) / k
    body = a[:-k].copy()
    body[:k] = a[-k:] * np.cos(0.5 * np.pi * u) + a[:k] * np.sin(0.5 * np.pi * u)
    return body


# --------------------------------------------------------------------------- noise
def _norm_rms_to(a, target=0.25):
    r = math.sqrt(float(np.mean(a * a))) if a.size else 0.0
    return a * (target / r) if r > EPS else a


def white(n: int, rng=None) -> np.ndarray:
    """White noise, RMS 0.25 (n samples)."""
    return _rng(rng).standard_normal(int(n)) * 0.25


def pink(n: int, rng=None) -> np.ndarray:
    """1/f noise by spectral shaping, RMS 0.25."""
    n = int(n)
    if n <= 0:
        return np.zeros(0)
    m = 1 << int(math.ceil(math.log2(max(n, 2))))
    r = _rng(rng)
    spec = r.standard_normal(m // 2 + 1) + 1j * r.standard_normal(m // 2 + 1)
    f = np.arange(m // 2 + 1, dtype=float)
    f[0] = 1.0
    spec /= np.sqrt(f)
    spec[0] = 0.0
    return _norm_rms_to(np.fft.irfft(spec, m)[:n])


def brown(n: int, rng=None) -> np.ndarray:
    """Leaky-integrated white (1/f^2 above ~5 Hz at 22 kHz), RMS 0.25."""
    w = _rng(rng).standard_normal(int(n))
    y = ss.lfilter([1.0], [1.0, -0.9985], w)
    return _norm_rms_to(y - y.mean())


def noise(n: int, rng=None, color: str = "white") -> np.ndarray:
    return {"white": white, "pink": pink, "brown": brown}[color](n, rng)


# --------------------------------------------------------------------------- filters
def _apply(sos, x, zero_phase):
    a = _arr(x)
    if a.size < 16:
        return a.copy()
    return ss.sosfiltfilt(sos, a) if zero_phase else ss.sosfilt(sos, a)


def lp(x, sr: int, hz: float, order: int = 2, zero_phase: bool = False) -> np.ndarray:
    return _apply(ss.butter(order, _nyq(hz, sr), btype="low", fs=sr, output="sos"), x, zero_phase)


def hp(x, sr: int, hz: float, order: int = 2, zero_phase: bool = False) -> np.ndarray:
    return _apply(ss.butter(order, _nyq(hz, sr), btype="high", fs=sr, output="sos"), x, zero_phase)


def bp(x, sr: int, lo: float, hi: float, order: int = 2, zero_phase: bool = False) -> np.ndarray:
    """Band-pass lo..hi Hz; a band at or past 0.45*sr is squeezed below it (never inverted)."""
    hi = float(_nyq(hi, sr))
    lo = float(np.clip(lo, 1.0, hi / 1.15))
    return _apply(ss.butter(order, [lo, hi], btype="band", fs=sr, output="sos"), x, zero_phase)


def _rbj(kind, sr, f0, gain_db=0.0, q=0.707):
    A = 10 ** (gain_db / 40.0)
    w = 2 * math.pi * float(_nyq(f0, sr)) / sr
    cw, sw = math.cos(w), math.sin(w)
    al = sw / (2 * q)
    if kind == "peak":
        b = [1 + al * A, -2 * cw, 1 - al * A]
        a = [1 + al / A, -2 * cw, 1 - al / A]
    elif kind == "low":
        sq = 2 * math.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * cw + sq), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sq)]
        a = [(A + 1) + (A - 1) * cw + sq, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sq]
    elif kind == "high":
        sq = 2 * math.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * cw + sq), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sq)]
        a = [(A + 1) - (A - 1) * cw + sq, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sq]
    else:
        raise KeyError(kind)
    return np.array(b) / a[0], np.array(a) / a[0]


def peaking(x, sr: int, f0: float, gain_db: float, q: float = 1.0, zero_phase: bool = False) -> np.ndarray:
    """RBJ peaking EQ band."""
    b, a = _rbj("peak", sr, f0, gain_db, q)
    return _apply(ss.tf2sos(b, a), x, zero_phase)


def shelf(x, sr: int, f0: float, gain_db: float, kind: str = "low", q: float = 0.707,
          zero_phase: bool = False) -> np.ndarray:
    """RBJ low/high shelf."""
    b, a = _rbj(kind, sr, f0, gain_db, q)
    return _apply(ss.tf2sos(b, a), x, zero_phase)


def tilt(x, sr: int, gain_db: float, pivot: float = 1000.0) -> np.ndarray:
    """Spectral tilt around pivot: +gain_db brightens (highs up, lows down by half each)."""
    y = shelf(x, sr, pivot, -gain_db / 2.0, "low")
    return shelf(y, sr, pivot, gain_db / 2.0, "high")


def svf(x, sr: int, fc, q: float = 0.7, mode: str = "lp") -> np.ndarray:
    """Time-varying state-variable filter (TPT/Simper). fc may be a scalar or a per-sample
    array (sweeps for whooshes). mode lp/bp/hp/notch. Python loop: fine for one-shots."""
    a = _arr(x)
    n = a.size
    f = np.broadcast_to(np.asarray(fc, float), (n,)) if np.ndim(fc) == 0 else np.asarray(fc, float)
    if f.size != n:
        f = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, f.size), f)
    g = np.tan(np.pi * _nyq(f, sr) / sr)
    k = 1.0 / max(q, 0.05)
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    out = np.empty(n)
    ic1 = ic2 = 0.0
    m = {"lp": 0, "bp": 1, "hp": 2, "notch": 3}[mode]
    for i in range(n):
        v3 = a[i] - ic2
        v1 = a1[i] * ic1 + a2[i] * v3
        v2 = ic2 + a2[i] * ic1 + a3[i] * v3
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        if m == 0:
            out[i] = v2
        elif m == 1:
            out[i] = v1
        elif m == 2:
            out[i] = a[i] - k * v1 - v2
        else:
            out[i] = a[i] - k * v1
    return out


def resonate(x, sr: int, freqs: Sequence[float], taus: Sequence[float], amps: Sequence[float] | None = None) -> np.ndarray:
    """Excite a bank of 2-pole resonators (decay time constant tau s each) with x: the
    exciter's texture shows through, unlike additive modal(). Peak-normalised."""
    a = _arr(x)
    amps = np.ones(len(freqs)) if amps is None else np.asarray(amps, float)
    y = np.zeros(a.size)
    for f, tau, g in zip(freqs, taus, amps):
        if f >= sr * 0.45:
            continue
        r = math.exp(-1.0 / (max(tau, 1e-4) * sr))
        w = 2 * math.pi * f / sr
        y += g * ss.lfilter([(1 - r * r) * math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], a)
    return norm_peak(y)


# --------------------------------------------------------------------------- envelopes
def env_points(dur: float, sr: int, pts: Sequence[tuple], power: float = 1.0) -> np.ndarray:
    """Piecewise-linear envelope through (t, value) points over dur s; power shapes the result."""
    n = secs(dur, sr)
    t = tvec(n, sr)
    ts = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    e = np.interp(t, ts, vs)
    return np.sign(e) * np.abs(e) ** power if power != 1.0 else e


def adsr(dur: float, sr: int, a: float = 0.005, d: float = 0.06, s: float = 0.6, r: float = 0.1,
         curve: float = 2.0) -> np.ndarray:
    """Attack/decay/sustain/release over dur s (release ends at dur); curve > 1 = exponential-ish."""
    n = secs(dur, sr)
    t = tvec(n, sr)
    e = np.empty(n)
    rel0 = max(dur - r, a + d)
    up = t < a
    e[up] = (t[up] / max(a, 1e-6)) ** (1.0 / curve)
    dk = (t >= a) & (t < a + d)
    e[dk] = 1 - (1 - s) * (1 - (1 - (t[dk] - a) / max(d, 1e-6)) ** curve)
    su = (t >= a + d) & (t < rel0)
    e[su] = s
    re = t >= rel0
    e[re] = s * (1 - np.clip((t[re] - rel0) / max(dur - rel0, 1e-6), 0, 1)) ** curve
    return e


def exp_decay(dur: float, sr: int, tau: float, attack: float = 0.0) -> np.ndarray:
    """exp(-t/tau) with an optional linear attack."""
    n = secs(dur, sr)
    t = tvec(n, sr)
    e = np.exp(-t / max(tau, 1e-5))
    if attack > 0:
        e *= np.minimum(1.0, t / attack)
    return e


def attack_decay(dur: float, sr: int, attack: float = 0.004, t60: float = 0.3, curve: float = 1.0) -> np.ndarray:
    """Rise over `attack` s (curve-shaped), then fall to -60 dB at attack + t60."""
    n = secs(dur, sr)
    t = tvec(n, sr)
    up = np.clip(t / max(attack, 1e-6), 0, 1) ** curve
    down = np.exp(-6.9 * np.clip(t - attack, 0, None) / max(t60, 1e-5))
    return up * down


# --------------------------------------------------------------------------- resonant bodies
# ratios: struck-mode frequency ratios; tau: fundamental decay constant (s); tilt: higher modes
# decay as ratio**-tilt; roll: amplitude roll-off exponent; spread: +-relative ratio randomisation;
# click: share of the noisy strike transient.
MATERIALS = {
    "wood": dict(ratios=(1.0, 2.43, 3.87, 5.52, 7.3), tau=0.045, tilt=1.1, roll=1.3, spread=0.05, click=0.5),
    "metal": dict(ratios=(1.0, 2.756, 5.404, 8.933, 13.34), tau=0.9, tilt=0.5, roll=0.8, spread=0.015, click=0.15),
    "glass": dict(ratios=(1.0, 2.32, 4.25, 6.63, 9.38), tau=0.5, tilt=0.7, roll=0.9, spread=0.02, click=0.1),
    "stone": dict(ratios=(1.0, 1.47, 2.09, 2.56, 3.39, 4.1), tau=0.02, tilt=0.8, roll=0.6, spread=0.08, click=0.9),
    "ceramic": dict(ratios=(1.0, 2.15, 3.6, 5.3, 7.4), tau=0.16, tilt=0.9, roll=1.0, spread=0.03, click=0.3),
    "bell": dict(ratios=(0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011), tau=1.4, tilt=0.6, roll=0.5, spread=0.008, click=0.05),
}


def modal_bank(sr: int, freqs, taus, amps, dur: float, rng=None, attack: float = 0.0006) -> np.ndarray:
    """Additive damped sinusoids (random phases when rng is given). Not normalised."""
    n = secs(dur, sr)
    t = tvec(n, sr)
    y = np.zeros(n)
    r = None if rng is None else _rng(rng)
    for f, tau, g in zip(freqs, taus, amps):
        if f >= sr * 0.45 or f <= 0:
            continue
        ph = 0.0 if r is None else r.uniform(0, 2 * np.pi)
        y += g * np.exp(-t / max(tau, 1e-5)) * np.sin(2 * np.pi * f * t + ph)
    if attack > 0 and n:
        y *= np.minimum(1.0, t / attack)
    return y


def modal(sr: int, f0: float, material: str = "wood", dur: float | None = None, rng=None,
          spread: float | None = None, tau: float | None = None, bright: float = 1.0,
          click: float | None = None, n_modes: int | None = None) -> np.ndarray:
    """A struck object: the material's mode set with randomised ratios (+-spread), decays
    (x0.8..1.25) and amplitudes, plus a short noisy strike (click). bright > 1 lifts upper modes.
    Peak-normalised. dur defaults to the time the slowest mode needs to fall 60 dB (<= 4 s)."""
    m = MATERIALS[material]
    r = _rng(rng)
    ratios = np.array(m["ratios"][: n_modes or None], float)
    sp = m["spread"] if spread is None else spread
    jit = 1.0 + r.uniform(-sp, sp, ratios.size)
    jit[0] = 1.0
    ratios = ratios * jit
    tau0 = m["tau"] if tau is None else tau
    taus = tau0 / ratios ** m["tilt"] * r.uniform(0.8, 1.25, ratios.size)
    amps = ratios ** (-m["roll"] / max(bright, 0.05)) * r.uniform(0.55, 1.0, ratios.size)
    if dur is None:
        dur = min(4.0, 6.9 * float(np.max(taus)) + 0.01)
    y = modal_bank(sr, f0 * ratios, taus, amps, dur, r)
    ck = m["click"] if click is None else click
    if ck > 0 and y.size:
        k = secs(0.012, sr)
        burst = r.standard_normal(k) * np.exp(-tvec(k, sr) / r.uniform(0.0012, 0.003))
        burst = bp(burst, sr, f0 * 1.5, min(f0 * 12, sr * 0.44))
        y[:k] += norm_peak(burst) * ck * float(np.max(np.abs(y)) + EPS)
    return norm_peak(y)


def ks_pluck(sr: int, f0: float, dur: float, rng=None, damping: float = 0.996, bright: float = 0.5,
             excite: np.ndarray | None = None) -> np.ndarray:
    """Karplus-Strong string. bright 0..1: darker loop/burst (0) to brighter (1). Block-vectorised
    (one period per step). excite: optional custom burst (one period long or longer)."""
    r = _rng(rng)
    N = max(2, int(round(sr / float(f0))))
    n = secs(dur, sr)
    y = np.zeros(n + N + 1)
    burst = r.uniform(-1, 1, N) if excite is None else np.resize(_arr(excite), N)
    if bright < 0.999:
        burst = lp(burst, sr, 600 + 9000 * bright, 1)
    y[1:N + 1] = burst
    s = 0.5 + 0.45 * float(np.clip(bright, 0, 1))
    k = N + 1
    while k < y.size:
        e = min(k + N, y.size)
        y[k:e] = damping * (s * y[k - N:e - N] + (1 - s) * y[k - N - 1:e - N - 1])
        k = e
    return norm_peak(y[1:n + 1])


def fm_bell(sr: int, f0: float, dur: float = 1.5, ratio: float = 1.4, index: float = 3.5,
            t60: float | None = None, index_t60: float | None = None, rng=None, attack: float = 0.0015) -> np.ndarray:
    """Chowning FM bell/chime: carrier f0, modulator f0*ratio, index decaying faster than the
    amplitude (bright strike, mellow ring). Peak-normalised."""
    r = _rng(rng)
    n = secs(dur, sr)
    t = tvec(n, sr)
    t60 = dur if t60 is None else t60
    index_t60 = t60 * 0.45 if index_t60 is None else index_t60
    amp = np.exp(-6.9 * t / max(t60, 1e-4)) * np.minimum(1.0, t / max(attack, 1e-5))
    idx = index * np.exp(-6.9 * t / max(index_t60, 1e-4))
    y = np.sin(2 * np.pi * f0 * t + idx * np.sin(2 * np.pi * f0 * ratio * t + r.uniform(0, 2 * np.pi)))
    return norm_peak(y * amp)


def osc(sr: int, freq, harmonics: Sequence[tuple] = ((1, 1.0),), phase: float = 0.0) -> np.ndarray:
    """Oscillator following a per-sample frequency array; harmonics = ((multiple, amp), ...),
    partials above 0.45*sr are muted sample by sample."""
    f = np.asarray(freq, float)
    ph = 2 * np.pi * np.cumsum(f) / sr + phase
    y = np.zeros(f.size)
    for h, g in harmonics:
        y += g * np.sin(h * ph) * (h * f < sr * 0.45)
    return y


def chirp(sr: int, dur: float, f0: float, f1: float, curve: str = "exp",
          harmonics: Sequence[tuple] = ((1, 1.0),), env: np.ndarray | None = None) -> np.ndarray:
    """Sweep from f0 to f1 Hz (exp or lin), optional amplitude envelope. Peak-normalised."""
    n = secs(dur, sr)
    u = np.linspace(0, 1, n, endpoint=False) if n else np.zeros(0)
    f = f0 * (f1 / f0) ** u if curve == "exp" else f0 + (f1 - f0) * u
    y = osc(sr, f, harmonics)
    if env is not None:
        y *= pad_to(np.asarray(env, float), n)
    return norm_peak(y)


# --------------------------------------------------------------------------- texture
def scatter(sr: int, dur: float, rng, grain, count: int | None = None, density: float | None = None,
            gain: tuple = (0.4, 1.0), pitch: tuple = (1.0, 1.0), env: np.ndarray | None = None,
            grain_dur: tuple = (0.01, 0.04), min_gap: float = 0.0) -> np.ndarray:
    """Granular scatter: place `count` grains (or density per second) at random times.
    grain: callable(rng) -> array, or a source array to cut Hann-windowed grains of grain_dur s
    from. env (any length) weights where grains land. gain is a linear range; pitch a repitch
    ratio range. Output = dur s plus the last grain's tail. Not normalised."""
    r = _rng(rng)
    n = secs(dur, sr)
    if count is None:
        count = max(1, int(round((density if density is not None else 20.0) * dur)))
    if env is not None and n > 1:
        w = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(env)), np.clip(np.asarray(env, float), 0, None)) + 1e-9
        times = np.sort(r.choice(n, size=count, p=w / w.sum()))
    else:
        times = np.sort(r.integers(0, max(n, 1), size=count))
    if min_gap > 0 and times.size:
        keep, last = [], -10 ** 9
        for t in times:
            if t - last >= secs(min_gap, sr):
                keep.append(t)
                last = t
        times = np.array(keep, int)
    grains = []
    for t in times:
        if callable(grain):
            g = _arr(grain(r))
        else:
            src = _arr(grain)
            L = min(src.size, max(4, secs(r.uniform(*grain_dur), sr)))
            s0 = int(r.integers(0, max(1, src.size - L + 1)))
            g = src[s0:s0 + L] * np.hanning(L)
        if pitch != (1.0, 1.0):
            g = repitch(g, r.uniform(*pitch))
        grains.append((int(t), g * r.uniform(*gain)))
    total = max([n] + [t + g.size for t, g in grains])
    out = np.zeros(total)
    for t, g in grains:
        out[t:t + g.size] += g
    return out


def reverb(x, sr: int, room: float = 0.35, wet: float = 0.18, rng=None, predelay: float = 0.008,
           tone: float = 5000.0, damp: float = 0.6, early: int = 4) -> np.ndarray:
    """Small synthetic room: decaying filtered-noise impulse (rt60 0.1..2 s from room 0..1),
    darker towards its end (damp), a few early reflections, convolved. wet = wet/dry RMS ratio.
    Output is longer than x by the tail (finish() trims it)."""
    a = _arr(x)
    r = _rng(rng)
    rt60 = 0.1 + 1.9 * float(np.clip(room, 0, 1)) ** 1.3
    n = secs(rt60 * 1.05, sr)
    t = tvec(n, sr)
    nz = r.standard_normal(n)
    bright = lp(nz, sr, tone, 2)
    dark = lp(nz, sr, tone * 0.25, 2)
    c = np.clip(t / rt60, 0, 1) ** 0.7 * damp
    ir = (bright * (1 - c) + dark * c) * np.exp(-6.9 * t / rt60)
    for _ in range(int(early)):
        k = secs(r.uniform(0.003, 0.02 + 0.05 * room), sr)
        if k < n:
            ir[k] += r.uniform(0.3, 0.7) * r.choice([-1, 1]) * float(np.max(np.abs(ir)))
    ir = np.concatenate([np.zeros(secs(predelay, sr)), ir])
    ir /= math.sqrt(float(np.sum(ir * ir))) + EPS
    w = ss.fftconvolve(a, ir)
    dr = math.sqrt(float(np.mean(a * a))) + EPS
    wr = math.sqrt(float(np.mean(w * w))) + EPS
    return pad_to(a, w.size) + wet * w * (dr / wr)


def saturate(x, drive: float = 2.0, asym: float = 0.0, mix: float = 1.0) -> np.ndarray:
    """tanh saturation keeping the input peak; asym adds even harmonics (warmth/grit)."""
    a = _arr(x)
    pk = float(np.max(np.abs(a))) if a.size else 0.0
    if pk < EPS:
        return a.copy()
    y = np.tanh(drive * a / pk + asym) - math.tanh(asym)
    y = y / (float(np.max(np.abs(y))) + EPS) * pk
    return (1 - mix) * a + mix * y


# --------------------------------------------------------------------------- mixing
def pad_to(x, n: int) -> np.ndarray:
    a = _arr(x)
    n = int(n)
    return a[:n].copy() if a.size >= n else np.concatenate([a, np.zeros(n - a.size)])


def place(out: np.ndarray, sig, at: float, sr: int = DEFAULT_SR, gain: float = 1.0) -> np.ndarray:
    """Add sig into out (in place) at `at` s; what falls past the end is dropped."""
    s = _arr(sig)
    i = secs(at, sr)
    if i < out.size:
        j = min(out.size, i + s.size)
        out[i:j] += s[: j - i] * gain
    return out


def mix(*layers, sr: int = DEFAULT_SR) -> np.ndarray:
    """Sum layers of different lengths. Each layer: array, (array, gain) or (array, gain, offset_s)."""
    items = []
    for l in layers:
        if isinstance(l, tuple):
            arr, g = _arr(l[0]), float(l[1]) if len(l) > 1 else 1.0
            off = secs(l[2], sr) if len(l) > 2 else 0
        else:
            arr, g, off = _arr(l), 1.0, 0
        items.append((arr, g, off))
    total = max([0] + [off + a.size for a, _, off in items])
    out = np.zeros(total)
    for a, g, off in items:
        out[off:off + a.size] += a * g
    return out


def concat(parts: Iterable, sr: int = DEFAULT_SR, xfade: float = 0.0) -> np.ndarray:
    """Join parts end to end, equal-power crossfading `xfade` s between neighbours."""
    out = np.zeros(0)
    for p in parts:
        out = _arr(p).copy() if out.size == 0 else xfade_concat(out, p, sr, xfade)
    return out


def norm_peak(x, peak: float = 1.0) -> np.ndarray:
    a = _arr(x)
    m = float(np.max(np.abs(a))) if a.size else 0.0
    return a * (peak / m) if m > EPS else a.copy()


def norm_rms(x, rms: float = 0.25) -> np.ndarray:
    return _norm_rms_to(_arr(x).copy(), rms)


# --------------------------------------------------------------------------- deriving takes from a recording
def envelope(x, sr: int = DEFAULT_SR, ms: float = 5.0) -> np.ndarray:
    """Peak envelope: |x| max-filtered and box-smoothed over `ms`."""
    w = max(1, secs(ms / 1000.0, sr))
    return uniform_filter1d(maximum_filter1d(np.abs(_arr(x)), w), w)


def onsets(x, sr: int = DEFAULT_SR, rise_db: float = 8.0, floor_db: float = -36.0,
           min_gap: float = 0.04, ms: float = 3.0, lag: float = 0.012) -> np.ndarray:
    """Transient onsets (sample indices): the envelope rises rise_db within `lag` s while above
    floor_db relative to the file peak; onsets closer than min_gap s are merged."""
    a = _arr(x)
    if a.size == 0:
        return np.zeros(0, int)
    e = envelope(a, sr, ms)
    if float(np.max(e)) < 1e-6:          # silence: no onsets
        return np.zeros(0, int)
    ed = 20 * np.log10(e + EPS)
    floor = float(np.max(ed)) + floor_db
    L = min(max(1, secs(lag, sr)), a.size)
    prev = np.concatenate([np.full(L, ed[0] - 120.0), ed[:a.size - L]])
    hit = (ed - prev > rise_db) & (ed > floor)
    idx = np.nonzero(hit & ~np.concatenate([[False], hit[:-1]]))[0]
    out, last = [], -10 ** 9
    gap = secs(min_gap, sr)
    for i in idx:
        j = max(0, i - L)
        j = j + int(np.argmax(ed[j:i + 1] > ed[i] - rise_db))   # walk back to where the rise starts
        if j - last >= gap:
            out.append(j)
            last = j
    return np.array(out, int)


def segments(x, sr: int = DEFAULT_SR, pre: float = 0.002, **onset_kw) -> list:
    """(start, end) sample pairs from each onset (minus pre-roll) to the next onset."""
    a = _arr(x)
    on = onsets(a, sr, **onset_kw)
    if on.size == 0:
        return [(0, a.size)]
    starts = [max(0, int(o) - secs(pre, sr)) for o in on]
    ends = starts[1:] + [a.size]
    return [(s, e) for s, e in zip(starts, ends) if e - s > secs(0.004, sr)]


def take_slice(x, sr: int, start: int, end: int, fade_in: float = 0.002, fade_out: float = 0.012) -> np.ndarray:
    """Cut x[start:end] (samples) with short fades."""
    return fades(_arr(x)[int(start):int(end)], sr, fade_in, fade_out)


def xfade_concat(a, b, sr: int = DEFAULT_SR, dur: float = 0.01) -> np.ndarray:
    """a then b with an equal-power crossfade of dur s (shortened to fit)."""
    a, b = _arr(a), _arr(b)
    k = min(secs(dur, sr), a.size, b.size)
    if k <= 0:
        return np.concatenate([a, b])
    u = np.linspace(0, 1, k)
    mid = a[-k:] * np.cos(0.5 * np.pi * u) + b[:k] * np.sin(0.5 * np.pi * u)
    return np.concatenate([a[:-k], mid, b[k:]])


def transient_shape(x, sr: int = DEFAULT_SR, attack_db: float = 0.0, sustain_db: float = 0.0,
                    fast_ms: float = 1.0, slow_ms: float = 25.0) -> np.ndarray:
    """Transient designer: boosts/cuts where a fast envelope leads a slow one (attack) and where
    it trails (sustain/tail). +attack_db = snappier take, -attack_db = softer strike."""
    a = _arr(x)
    if a.size == 0:
        return a.copy()
    fast = envelope(a, sr, fast_ms)
    slow = uniform_filter1d(fast, max(1, secs(slow_ms / 1000.0, sr)))
    d = np.clip((fast - slow) / (fast + EPS), -1, 1)
    gdb = np.where(d > 0, d * attack_db, -d * sustain_db)
    return a * 10 ** (uniform_filter1d(gdb, max(1, secs(0.002, sr))) / 20.0)


def splice(x, sr: int, rng, order: Sequence[int] | None = None, drop: float = 0.0,
           xfade: float = 0.006, **seg_kw) -> np.ndarray:
    """Re-cut a recording at its onsets and join the pieces in a new order (random keeping the
    first, or `order`), dropping each later piece with probability `drop`. Gives a new rhythm
    from the same material; pair it with repitch/tilt/transient_shape for a distinct take."""
    a = _arr(x)
    r = _rng(rng)
    segs = segments(a, sr, **seg_kw)
    if order is None:
        rest = list(range(1, len(segs)))
        r.shuffle(rest)
        order = [0] + [i for i in rest if r.random() >= drop]
    parts = [take_slice(a, sr, *segs[i], fade_in=0.0015, fade_out=xfade) for i in order if 0 <= i < len(segs)]
    return concat(parts, sr, xfade)


# --------------------------------------------------------------------------- take families
def cycle(i: int, *axes: Sequence) -> tuple:
    """Pick axis[i % len(axis)] from each axis: a design grid for take i. With coprime axis lengths
    (2, 3, 5, 7...) every take up to their product gets a different combination, e.g.
        mat, hits, step = cycle(i, ["wood", "ceramic"], [1, 2, 3], [1.0, 1.15, 0.86, 1.32, 0.76])"""
    return tuple(axis[int(i) % len(axis)] for axis in axes)


def take_seed(event: str, i: int, base: str = "") -> int:
    """Stable 63-bit seed from (base, event, take index)."""
    h = hashlib.sha256(("%s|%s|%d" % (base, event, int(i))).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "little") >> 1


_TRACKED: dict = {}


def git_tracked(path) -> bool:
    """True when git tracks the file (git ls-files --error-unmatch). Without git an existing
    file counts as tracked (safe side)."""
    p = Path(path).resolve()
    if p in _TRACKED:
        return _TRACKED[p]
    cwd = p.parent if p.parent.exists() else REPO
    try:
        r = subprocess.run(["git", "ls-files", "--error-unmatch", "--", str(p)], cwd=str(cwd),
                           capture_output=True, text=True)
        tracked = r.returncode == 0
    except (FileNotFoundError, OSError):
        tracked = p.exists()
    _TRACKED[p] = tracked
    return tracked


def _guard(paths: Sequence[Path], allow_overwrite: bool):
    if allow_overwrite:
        return
    bad = [str(p) for p in paths if p.exists() and git_tracked(p)]
    if bad:
        raise FileExistsError("refusing to overwrite git-tracked file(s) (use a higher start index, "
                              "or allow_overwrite=True if this really is your own file):\n  " + "\n  ".join(bad))


def _describe(path: Path, x: np.ndarray, sr: int, ref_db: float | None) -> dict:
    st = st_rms_peak_db(x, sr)
    d = {"path": str(path), "name": path.stem, "sr": sr, "seconds": round(x.size / sr, 4),
         "bytes": path.stat().st_size if path.exists() else 44 + 2 * x.size,
         "peak_db": round(peak_db(x), 2), "st_db": round(st, 2)}
    if ref_db is not None:
        d["ref_db"] = round(ref_db, 2)
        d["delta_db"] = round(st - ref_db, 2)
    return d


def write_take(path, x, sr: int = DEFAULT_SR, ref_db: float | None = None, allow_overwrite: bool = False,
               finish_kw: dict | None = None, raw: bool = False) -> dict:
    """finish() + write one file (new bare kinds, one-offs); same overwrite guard as make_family."""
    path = Path(path)
    _guard([path], allow_overwrite)
    y = _arr(x) if raw else finish(x, sr, ref_db=ref_db, **(finish_kw or {}))
    write_wav(path, y, sr)
    return _describe(path, y, sr, ref_db)


def make_family(out_dir, event: str, n: int, fn: Callable, sr: int = DEFAULT_SR, ref_db: float | None = None,
                seed_base: str = "", start: int = 1, allow_overwrite: bool = False,
                finish_kw: dict | None = None, dry_run: bool = False, verbose: bool = True) -> list:
    """Render takes <event>_<start>.wav .. <event>_<start+n-1>.wav into out_dir.

    fn(rng, i) -> float array at `sr` (or (array, notes_dict)); rng is a numpy Generator seeded
    from take_seed(event, i, seed_base), so a take re-renders identically. Each take goes through
    finish() (DC, limiter, trim, fades) and is matched to ref_db (st-rms) when given.
    Refuses (before writing anything) when a target is tracked in git, e.g. a team recording
    harvest_tree_1.wav: start=2 then. Warns when numbering would leave a gap (sfx_bank.gd
    tolerates one missing index only). Returns one metadata dict per take."""
    out_dir = Path(out_dir)
    idx = list(range(int(start), int(start) + int(n)))
    targets = [out_dir / ("%s_%d.wav" % (event, i)) for i in idx]
    _guard(targets, allow_overwrite)
    if start > 1 and not (out_dir / ("%s_%d.wav" % (event, start - 1))).exists():
        print("sfxlib: warning: %s_%d.wav does not exist; takes from %d leave a gap (sfx_bank.gd skips at most one)"
              % (event, start - 1, start), file=sys.stderr)
    meta = []
    for i, path in zip(idx, targets):
        seed = take_seed(event, i, seed_base)
        res = fn(np.random.default_rng(seed), i)
        notes = {}
        if isinstance(res, tuple):
            res, notes = res[0], dict(res[1]) if len(res) > 1 else {}
        raw = _arr(res)
        y = finish(raw, sr, ref_db=ref_db, **(finish_kw or {}))
        if not dry_run:
            write_wav(path, y, sr)
        d = _describe(path, y, sr, ref_db)
        d.update({"event": event, "take": i, "seed": seed}, **notes)
        if ref_db is not None and raw.size:
            # how far the limiter had to pull the peak down to reach ref_db (transient squash)
            crest = peak_db(raw) - st_rms_peak_db(raw, sr)
            d["limit_db"] = round(max(0.0, ref_db + crest - db((finish_kw or {}).get("ceiling", CEILING))), 1)
            if d["limit_db"] > 6.0:
                print("sfxlib: warning: %s: limiter takes %.1f dB off the peak (soften the transient or lower ref_db)"
                      % (path.name, d["limit_db"]), file=sys.stderr)
        if ref_db is not None and abs(d["delta_db"]) > LEVEL_TOL_DB:
            d["warning"] = "level %.1f dB off ref (crest factor too high for the ceiling?)" % d["delta_db"]
            print("sfxlib: warning: %s: %s" % (path.name, d["warning"]), file=sys.stderr)
        meta.append(d)
    if verbose:
        print(family_report(meta))
    return meta


def family_report(meta: Sequence[dict]) -> str:
    """One line per take plus the family's byte total and level spread."""
    if not meta:
        return "(no takes)"
    rows = ["%-28s %6.3fs  st %6.1f dB  peak %6.1f dB%s" % (
        d["name"], d["seconds"], d["st_db"], d["peak_db"],
        ("  d %+5.2f" % d["delta_db"]) if "delta_db" in d else "") for d in meta]
    st = [d["st_db"] for d in meta]
    rows.append("%d takes, %.1f KB, st spread %.2f dB" % (len(meta), sum(d["bytes"] for d in meta) / 1024.0, max(st) - min(st)))
    return "\n".join(rows)


# --------------------------------------------------------------------------- self-test
def _selftest(out: Path) -> int:
    """Render demo families with every building block, then assert the IO/level/fade rules."""
    sr = DEFAULT_SR
    fails = []

    def check(ok, what):
        if not ok:
            fails.append(what)
            print("SELFTEST FAIL", what)

    # Families are designed on a grid of structural archetypes (cycle() with coprime lengths) plus
    # small random detail; pure random draws give near-identical pairs that sfx_qa flags.
    def knock(rng, i):
        mat, hits, step = cycle(i, ["wood", "ceramic"], [1, 2, 3], [1.0, 1.15, 0.86, 1.32, 0.76])
        f0 = 430.0 * step * rng.uniform(0.985, 1.015)
        x = modal(sr, f0, mat, rng=rng, bright=rng.uniform(0.8, 1.3))
        for h in range(1, hits):
            x = mix(x, (modal(sr, f0 * rng.uniform(1.03, 1.1), mat, rng=rng), rng.uniform(0.45, 0.7),
                        h * rng.uniform(0.08, 0.12)), sr=sr)
        return reverb(x, sr, room=rng.uniform(0.1, 0.3), wet=0.12, rng=rng), {"material": mat, "hits": hits}

    def chime(rng, i):
        kind, note, ratio = cycle(i, ["glass", "fm"], [880.0, 988.0, 1175.0, 1319.0, 1480.0], [1.4, 2.0, 3.5])
        f0 = note * rng.uniform(0.995, 1.005)
        if kind == "fm":
            return fm_bell(sr, f0, rng.uniform(0.8, 1.2), ratio=ratio, index=rng.uniform(2, 5), rng=rng)
        return modal(sr, f0, "glass", rng=rng, dur=rng.uniform(0.8, 1.2))

    def pluck(rng, i):
        note, bright, dur = cycle(i, [196.0, 233.0, 277.0, 330.0, 392.0], [0.25, 0.8], [0.5, 0.75, 0.95])
        return ks_pluck(sr, note * rng.uniform(0.995, 1.005), dur, rng=rng, bright=bright)

    def whoosh(rng, i):
        shape, (length, sweep), peak = cycle(i, ["single", "double", "flutter"],
                                             [(0.24, (500, 3400)), (0.3, (1800, 700)), (0.36, (700, 1600)),
                                              (0.42, (2600, 1200)), (0.28, (400, 2200))], [0.32, 0.6])
        n = secs(length * rng.uniform(0.95, 1.05), sr)
        u = np.linspace(0, 1, n)
        fc = np.interp(u, [0, peak, 1], [sweep[0], sweep[0] + (sweep[1] - sweep[0]) * 0.9, sweep[1]])
        w = rng.uniform(0.14, 0.2)
        env = np.exp(-((u - peak) / w) ** 2)
        if shape == "double":
            env = 0.8 * np.exp(-((u - peak + 0.2) / (w * 0.6)) ** 2) + np.exp(-((u - peak) / (w * 0.7)) ** 2)
        elif shape == "flutter":
            env = env * (1 - 0.6 * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(20, 28) * u * length)))
        return svf(pink(n, rng), sr, fc, q=rng.uniform(0.9, 1.8), mode="bp") * env, {"shape": shape}

    def sparkle(rng, i):
        grain = lambda r: modal(sr, r.uniform(2500, 6000), "glass", rng=r, dur=0.08)
        x = scatter(sr, rng.uniform(0.3, 0.5), rng, grain, count=int(rng.integers(5, 10)),
                    gain=(0.3, 1.0), env=np.linspace(1, 0.2, 16))
        return reverb(x, sr, room=0.5, wet=0.3, rng=rng)

    rec = mix(*[(modal(sr, 300 * (1 + 0.1 * k), "wood", rng=k), 1.0 - 0.1 * k, 0.12 * k) for k in range(5)], sr=sr)
    rec = rec + brown(rec.size, 7) * 0.02

    def derived(rng, i):
        x = splice(rec, sr, rng, drop=0.3)
        x = transient_shape(x, sr, attack_db=rng.uniform(-4, 4))
        return tilt(repitch(x, cycle(i, [0.9, 1.0, 1.12])[0]), sr, rng.uniform(-4, 4))

    ref = -18.0
    fams = {"knock": knock, "chime": chime, "pluck": pluck, "whoosh": whoosh, "sparkle": sparkle, "derived": derived}
    metas = {}
    for name, fn in fams.items():
        metas[name] = make_family(out, name, 6, fn, sr=sr, ref_db=ref, seed_base="selftest", verbose=False)
        print(family_report(metas[name]))
    for name, meta in metas.items():
        for d in meta:
            p = Path(d["path"])
            info = wav_info(p)
            check(info["data_offset"] == 44 and info["channels"] == 1 and info["bits"] == 16, "%s header" % p.name)
            x, s2 = read_wav(p)
            check(s2 == sr, "%s rate" % p.name)
            check(abs(st_rms_peak_db(x, sr) - ref) <= LEVEL_TOL_DB, "%s level %.2f" % (p.name, st_rms_peak_db(x, sr)))
            check(np.max(np.abs(x)) < 0.999, "%s clipped" % p.name)
            check(abs(x[0]) < 1e-3 and abs(x[-1]) < 1e-3, "%s edges not zero" % p.name)
            check(abs(float(np.mean(x))) < 0.01, "%s DC" % p.name)
    # determinism + no-overwrite guard + IO round trip
    again = make_family(out / "again", "knock", 2, knock, sr=sr, ref_db=ref, seed_base="selftest", verbose=False)
    a, _ = read_wav(again[0]["path"])
    b, _ = read_wav(metas["knock"][0]["path"])
    check(a.size == b.size and np.allclose(a, b), "same seed renders the same take")
    c, _ = read_wav(metas["knock"][1]["path"])
    check(a.size != c.size or not np.allclose(a, c), "different takes differ")
    tracked = REPO / "game" / "assets" / "sfx" / "ui" / "hover.wav"
    if tracked.exists() and git_tracked(tracked):
        try:
            write_take(tracked, np.zeros(100), sr)
            check(False, "tracked file was not protected")
        except FileExistsError:
            pass
    y = resample(np.sin(2 * np.pi * 440 * tvec(sr, sr)), sr, 32000)
    check(abs(y.size - 32000) <= 1, "resample length")
    print("selftest output:", out)
    if not fails:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import sfx_qa  # noqa: E402
            code = sfx_qa.main([str(out), "--min-takes", "6", "--quiet"])
            check(code == 0, "sfx_qa passes the demo families")
        except ImportError:
            print("(sfx_qa.py not found next to sfxlib.py; skipped the QA pass)")
    print("SELFTEST %s (%d problems)" % ("PASS" if not fails else "FAIL", len(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="sfxlib self-test: renders demo takes and checks the rules")
    ap.add_argument("--out", help="output dir (default: a new temp dir)")
    args = ap.parse_args()
    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="sfxlib_selftest_"))
    sys.exit(_selftest(out_dir))
