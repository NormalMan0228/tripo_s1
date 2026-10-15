"""Trailer v3 audio: procedural stereo SFX/beds for VILLAGEN (numpy/scipy only, no downloads).

Output: D:/lsm26/trailer_media/audio/*.wav  (48 kHz, 16-bit, stereo, peak <= -1 dBFS)
Contact sheet: <scratch>/trailer/contact_sheet.png
Key: C major family (Am/F for the night bed).
"""
import math
import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal as ss

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402

SR = 48000
CEIL = 10 ** (-1.2 / 20)          # a hair under -1 dBFS so 16-bit rounding stays below it
OUT = Path(r"D:\lsm26\trailer_media\audio")
SCRATCH = Path(__file__).resolve().parent
AMB = Path(r"D:\lsm26\wt\monstersfx\game\assets\sfx\ambience")
EPS = 1e-12


# ----------------------------------------------------------------------------- helpers
def mhz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


PENTA = [m for m in range(36, 110) if m % 12 in (0, 2, 4, 7, 9)]


def snap_penta(m):
    return min(PENTA, key=lambda p: abs(p - m))


def n_(t):
    return int(round(t * SR))


def panLR(x, p):
    """Constant-power pan, normalised so centre = x in both channels. p in [-1, 1] (scalar/array)."""
    th = (np.asarray(p, float) + 1) * np.pi / 4
    return x * np.cos(th) * math.sqrt(2), x * np.sin(th) * math.sqrt(2)


class Bus:
    """Stereo accumulator."""

    def __init__(self, dur):
        self.L = np.zeros(n_(dur))
        self.R = np.zeros(n_(dur))

    def add(self, x, at=0.0, gain=1.0, pan=0.0):
        l, r = panLR(np.asarray(x, float) * gain, pan)
        L.place(self.L, l, at, SR)
        L.place(self.R, r, at, SR)

    def add_lr(self, l, r, at=0.0, gain=1.0):
        L.place(self.L, l, at, SR, gain)
        L.place(self.R, r, at, SR, gain)


def st_reverb(l, r, room, wet, seed, tone=5000.0, damp=0.6):
    """Independent tails per channel (different IR seeds / predelays) -> gentle, mono-safe width."""
    wl = L.reverb(l, SR, room, wet, rng=np.random.default_rng(seed), predelay=0.009, tone=tone, damp=damp)
    wr = L.reverb(r, SR, room, wet, rng=np.random.default_rng(seed + 7919), predelay=0.014, tone=tone, damp=damp)
    n = max(wl.size, wr.size)
    return L.pad_to(wl, n), L.pad_to(wr, n)


def mid(l, r):
    return 0.5 * (l + r)


def st_finish(l, r, ref_db, dur, fade_in=0.004, fade_out=0.05, loop=False):
    n = n_(dur)
    l, r = L.pad_to(l, n), L.pad_to(r, n)
    if loop:
        l, r = l - l.mean(), r - r.mean()
    else:
        l, r = L.remove_dc(l, SR, 20.0), L.remove_dc(r, SR, 20.0)
    for _ in range(5):
        g = L.undb(ref_db - L.st_rms_peak_db(mid(l, r), SR))
        l, r = l * g, r * g
        m = np.maximum(np.abs(l), np.abs(r))
        if m.max() > CEIL:
            gl = L.limit(m, SR, CEIL) / (m + EPS)
            gl = np.minimum(gl, 1.0)
            l, r = l * gl, r * gl
        if abs(L.st_rms_peak_db(mid(l, r), SR) - ref_db) < 0.15:
            break
    if not loop:
        l, r = L.fades(l, SR, fade_in, fade_out), L.fades(r, SR, fade_in, fade_out)
    return np.clip(l, -CEIL, CEIL), np.clip(r, -CEIL, CEIL)


def write_stereo(path, l, r):
    a = np.stack([l, r], axis=1)
    if not np.all(np.isfinite(a)):
        raise ValueError("non-finite")
    pcm = np.clip(np.round(a * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def soft_saw(f, dur, nh=10, detune_c=0.0, rng=None, bright=1.0):
    """Band-limited soft saw (1/h^1.3) following scalar f, with a cents offset."""
    n = n_(dur)
    ff = np.full(n, f * 2 ** (detune_c / 1200.0))
    harm = tuple((h, (1.0 / h ** (1.3 / bright))) for h in range(1, nh + 1))
    ph = 0.0 if rng is None else rng.uniform(0, 2 * np.pi)
    return L.osc(SR, ff, harm, phase=ph)


def ping(f, dur=0.5, t60=0.35, ratio=3.0, index=1.0, attack=0.002, seed=0):
    return L.fm_bell(SR, f, dur, ratio=ratio, index=index, t60=t60, attack=attack,
                     rng=np.random.default_rng(seed))


def kalimba(f, dur=2.4, t60=2.0, seed=0):
    """Warm tine: mostly fundamental, a soft FM octave sheen, a quiet inharmonic tine partial."""
    rng = np.random.default_rng(seed)
    body = L.fm_bell(SR, f, dur, ratio=2.0, index=1.3, t60=t60, index_t60=0.25, attack=0.003, rng=rng)
    t = np.arange(n_(dur)) / SR
    tine = np.sin(2 * np.pi * f * 5.95 * t + rng.uniform(0, 6.28)) * np.exp(-t / 0.05) * np.minimum(1, t / 0.002)
    return L.norm_peak(body + 0.12 * tine)


# ----------------------------------------------------------------------------- 1 logo sting
def logo_sting():
    D = 3.9
    rng = np.random.default_rng(101)
    B = Bus(D)
    hit = 1.35
    # swell: filtered pink noise, separate seeds per channel, lowpass opening upwards
    ns = n_(1.7)
    fc = np.geomspace(250, 4200, ns)
    env = L.env_points(1.7, SR, [(0, 0), (0.3, 0.05), (1.25, 1.0), (1.42, 0.35), (1.7, 0)], power=2.0)
    for ch, seed in ((0, 11), (1, 12)):
        nz = L.pink(ns, np.random.default_rng(seed))
        nz = L.svf(nz, SR, fc, q=0.8, mode="lp") * env
        nz = L.hp(nz, SR, 120)
        (B.L if ch == 0 else B.R)[:ns] += 0.30 * L.norm_peak(nz)
    # pad: C3 G3 C4 E4 G4 soft saws, opposite detune per channel, slow swell then gentle release
    pd = D
    penv = L.env_points(pd, SR, [(0, 0), (1.3, 1.0), (1.6, 0.75), (3.0, 0.35), (D, 0.0)], power=1.6)
    padL = np.zeros(n_(pd))
    padR = np.zeros(n_(pd))
    for m, g in ((48, 0.9), (55, 0.7), (60, 0.6), (64, 0.5), (67, 0.35)):
        padL += g * soft_saw(mhz(m), pd, 10, -4, rng)
        padR += g * soft_saw(mhz(m), pd, 10, +4, rng)
    fcp = np.concatenate([np.geomspace(400, 2200, n_(1.35)), np.geomspace(2200, 900, n_(pd) - n_(1.35))])
    padL = L.svf(padL, SR, fcp, 0.6) * penv
    padR = L.svf(padR, SR, fcp, 0.6) * penv
    B.add_lr(0.17 * L.norm_peak(padL), 0.17 * L.norm_peak(padR))
    # warm low bloom on the hit (C2 + C3 sines, soft attack)
    t = np.arange(n_(2.5)) / SR
    bloom = (np.sin(2 * np.pi * mhz(36) * t) + 0.5 * np.sin(2 * np.pi * mhz(48) * t)) \
        * np.minimum(1, t / 0.04) * np.exp(-t / 0.7)
    B.add(L.norm_peak(bloom), hit - 0.01, 0.18)
    # bell/kalimba chord, gently strummed C5 E5 G5 C6 E6
    notes = [72, 76, 79, 84, 88]
    pans = [-0.35, 0.25, -0.15, 0.35, 0.0]
    for i, (m, p) in enumerate(zip(notes, pans)):
        B.add(kalimba(mhz(m), 2.5, 2.1, seed=200 + i), hit + 0.028 * i, 0.42 - 0.04 * i, p)
        B.add(ping(mhz(m) * 2, 1.4, 1.1, ratio=3.5, index=0.6, attack=0.004, seed=300 + i),
              hit + 0.028 * i + 0.005, 0.06, -p)
    # rising sparkle tail: pentatonic pings climbing C6 -> G7
    k = 18
    for j in range(k):
        u = j / (k - 1)
        tt = hit + 0.12 + 1.45 * (u ** 0.85) + rng.uniform(-0.02, 0.02)
        m = snap_penta(84 + 19 * u + rng.uniform(-1.5, 1.5))
        g = 0.13 * (1.0 - 0.45 * u) * rng.uniform(0.75, 1.0)
        B.add(ping(mhz(m), 0.7, 0.45, ratio=3.0, index=0.9, attack=0.003, seed=400 + j), tt, g,
              rng.uniform(-0.7, 0.7))
    # airy shimmer under the tail
    ns2 = n_(2.2)
    for ch, seed in ((0, 21), (1, 22)):
        sh = L.bp(L.white(ns2, np.random.default_rng(seed)), SR, 5000, 11000) \
            * L.env_points(2.2, SR, [(0, 0), (0.3, 1), (1.2, 0.5), (2.2, 0)], 1.5)
        L.place(B.L if ch == 0 else B.R, 0.012 * L.norm_peak(sh), hit, SR)
    l, r = st_reverb(B.L, B.R, 0.62, 0.33, 501)
    l, r = L.lp(l, SR, 12500), L.lp(r, SR, 12500)
    return st_finish(l, r, -15.0, D, fade_in=0.01, fade_out=0.45)


# ----------------------------------------------------------------------------- 2 sparkle form
def sparkle_form():
    D = 2.85
    T = 2.1          # 'tok' time
    rng = np.random.default_rng(202)
    G = Bus(D)
    N = 80
    for i in range(N):
        u = math.sqrt(rng.uniform(0, 1))            # density grows with time
        t = 0.05 + (T - 0.08) * u
        prog = t / T
        m = snap_penta(82 + 20 * prog + rng.uniform(-3, 3))
        g = (0.18 + 0.42 * prog) * rng.uniform(0.5, 1.0)
        spread = 0.85 * (1 - prog) ** 0.7 + 0.08     # particles converge to the centre
        dur = rng.uniform(0.08, 0.16)
        G.add(ping(mhz(m), dur + 0.05, dur, ratio=rng.choice([2.0, 3.0, 3.5]), index=rng.uniform(0.4, 1.1),
                   attack=0.0015, seed=1000 + i), t, g, rng.uniform(-spread, spread))
    # rising shimmer noise bed (cut just before the tok)
    ns = n_(T + 0.05)
    fc = np.geomspace(1800, 7500, ns)
    env = L.env_points(T + 0.05, SR, [(0, 0), (1.6, 0.6), (T - 0.02, 1.0), (T + 0.05, 0)], 2.0)
    for ch, seed in ((0, 31), (1, 32)):
        nz = L.svf(L.pink(ns, np.random.default_rng(seed)), SR, fc, 1.6, "bp") * env
        L.place(G.L if ch == 0 else G.R, 0.10 * L.norm_peak(nz), 0, SR)
    # a soft rising tonal glide (C5 -> C6) underneath the grains
    tone = L.chirp(SR, T, mhz(72), mhz(84), "exp", ((1, 1), (2, 0.25)),
                   env=L.env_points(T, SR, [(0, 0), (1.5, 0.5), (T - 0.03, 1.0), (T, 0)], 2.0))
    G.add(tone, 0.0, 0.05)
    gl, gr = st_reverb(G.L, G.R, 0.5, 0.38, 601)
    # completion: wooden tok + tiny chime (drier)
    K = Bus(D)
    tok = L.modal(SR, 410, "wood", rng=np.random.default_rng(77), bright=0.9, click=0.35)
    tt = np.arange(n_(0.18)) / SR
    body = np.sin(2 * np.pi * 205 * tt) * np.exp(-tt / 0.035) * np.minimum(1, tt / 0.0015)
    tok = L.lp(L.mix((tok, 1.0), (body, 0.45), sr=SR), SR, 5200)
    K.add(L.norm_peak(tok), T, 1.0)
    K.add(ping(mhz(96), 1.0, 0.75, ratio=3.5, index=0.8, attack=0.003, seed=88), T + 0.035, 0.20, 0.2)
    K.add(ping(mhz(103), 0.8, 0.55, ratio=3.0, index=0.6, attack=0.003, seed=89), T + 0.075, 0.11, -0.25)
    kl, kr = st_reverb(K.L, K.R, 0.3, 0.16, 602)
    n = max(gl.size, kl.size)
    l = L.pad_to(gl, n) + L.pad_to(kl, n) * 2.4
    r = L.pad_to(gr, n) + L.pad_to(kr, n) * 2.4
    return st_finish(l, r, -15.5, D, fade_in=0.01, fade_out=0.25)


# ----------------------------------------------------------------------------- 3 bubble pop
def bubble_pop():
    D = 0.3
    t = np.arange(n_(0.2)) / SR
    f = 380 + (1150 - 380) * np.exp(-t / 0.018)          # quick downward 'ppok' glide
    tone = L.osc(SR, f, ((1, 1.0), (2, 0.12)))
    tone *= np.minimum(1, t / 0.0018) * np.exp(-t / 0.022)
    nz = L.bp(L.white(n_(0.01), np.random.default_rng(5)), SR, 1800, 6000)
    nz *= np.exp(-np.arange(nz.size) / SR / 0.0015)
    B = Bus(D)
    B.add(L.norm_peak(tone), 0.004, 1.0)
    B.add(L.norm_peak(nz), 0.004, 0.10)
    l, r = st_reverb(B.L, B.R, 0.18, 0.12, 701)
    return st_finish(l, r, -20.0, D, fade_in=0.002, fade_out=0.06)


# ----------------------------------------------------------------------------- 4 typing
def typing_ui():
    D = 2.0
    rng = np.random.default_rng(404)
    B = Bus(D)
    times, t = [], 0.07
    while t < 1.82 and len(times) < 15:
        times.append(t)
        step = rng.uniform(0.075, 0.15)
        if rng.uniform() < 0.15:
            step += rng.uniform(0.08, 0.16)          # little hesitation
        t += step
    for i, t0 in enumerate(times):
        f = rng.uniform(1500, 2500)
        n = n_(0.06)
        tt = np.arange(n) / SR
        tone = np.sin(2 * np.pi * f * tt) * np.exp(-tt / rng.uniform(0.007, 0.012))
        thump = np.sin(2 * np.pi * rng.uniform(170, 260) * tt) * np.exp(-tt / 0.009)
        nz = L.lp(L.white(n, rng), SR, 3800) * np.exp(-tt / 0.0025)
        c = 0.55 * tone + 0.35 * thump + 0.25 * L.norm_peak(nz)
        c *= np.minimum(1, tt / 0.0009)               # rounded attack
        c = L.lp(c, SR, 6000)
        B.add(L.norm_peak(c), t0, rng.uniform(0.55, 1.0), rng.uniform(-0.25, 0.25))
    l, r = st_reverb(B.L, B.R, 0.2, 0.12, 801)
    return st_finish(l, r, -20.0, D, fade_in=0.003, fade_out=0.08), len(times)


# ----------------------------------------------------------------------------- 5 whooshes
def whoosh_1():
    D = 0.85
    n = n_(D)
    pk = 0.5
    fc = np.concatenate([np.geomspace(420, 2300, n_(pk)), np.geomspace(2300, 650, n - n_(pk))])
    env = L.env_points(D, SR, [(0, 0), (pk, 1.0), (D, 0)], 1.8)
    out = []
    common = L.pink(n, np.random.default_rng(40))
    for seed in (41, 42):
        r = np.random.default_rng(seed)
        nz = 0.8 * common + 0.35 * L.pink(n, r)
        body = L.svf(nz, SR, fc, 0.9, "bp")
        air = L.svf(L.white(n, r), SR, fc * 3.0, 1.2, "bp") * 0.15
        out.append(L.hp((L.norm_peak(body) + air) * env, SR, 140))
    l, r = st_reverb(out[0], out[1], 0.3, 0.15, 901)
    return st_finish(l, r, -18.0, D, fade_in=0.01, fade_out=0.08)


def whoosh_2():
    D = 0.9
    n = n_(D)
    pk = 0.38
    env = L.env_points(D, SR, [(0, 0), (pk, 1.0), (pk + 0.12, 0.55), (D, 0)], 1.6)
    fc = np.concatenate([np.geomspace(900, 1900, n_(pk)), np.geomspace(1900, 520, n - n_(pk))])
    r = np.random.default_rng(51)
    nz = L.pink(n, r)
    body = L.norm_peak(L.svf(nz, SR, fc, 1.0, "bp"))
    air = L.norm_peak(L.svf(L.white(n, r), SR, fc * 2.6, 1.4, "bp")) * 0.18
    x = L.hp((body + air) * env, SR, 140)
    pan = np.tanh(3.0 * (np.linspace(0, 1, n) - 0.42)) * 0.75     # L -> R pass
    l, rr = panLR(x, pan)
    l, rr = st_reverb(l, rr, 0.32, 0.18, 902)
    return st_finish(l, rr, -18.0, D, fade_in=0.01, fade_out=0.08)


# ----------------------------------------------------------------------------- 6 night drone
def night_drone():
    D = 9.5
    n = n_(D)
    t = np.arange(n) / SR
    rng = np.random.default_rng(606)
    xf = np.clip((t - 4.2) / 1.6, 0, 1)
    xf = 0.5 - 0.5 * np.cos(np.pi * xf)               # Am -> Fmaj7 crossfade
    chans = []
    lfos = [1 + 0.25 * np.sin(2 * np.pi * rng.uniform(0.06, 0.14) * t + rng.uniform(0, 6.28)) for _ in range(7)]
    core = None
    wind_common = L.pink(n, np.random.default_rng(59))
    for side, det in ((None, 0.0), (0, -6.0), (1, 6.0)):
        acc = np.zeros(n)
        voices = [(45, 0.9, 1 - xf), (41, 0.9, xf),      # A2 -> F2 bass
                  (52, 0.55, 1), (57, 0.45, 1), (60, 0.4, 1), (64, 0.22, 1),  # E3 A3 C4 E4
                  (71, 0.10, 1 - xf)]                    # B4: a touch of tension, resolves away
        for k, (m, g, w) in enumerate(voices):
            acc += g * w * lfos[k] * soft_saw(mhz(m), D, 12, det * (1 if k % 2 else -1),
                                             np.random.default_rng(700 + k), bright=0.9)
        fc = 520 + 260 * np.sin(2 * np.pi * 0.07 * t) + 120 * np.sin(2 * np.pi * 0.19 * t)
        pad = L.norm_peak(L.svf(acc, SR, fc, 0.75))
        if side is None:
            core = pad
            continue
        pad = core + 0.35 * pad
        # soft wind: pink noise through a wandering band-pass, slow gusts
        wind_fc = 480 + 260 * np.sin(2 * np.pi * 0.11 * t + 0.3 * side) + 150 * np.sin(2 * np.pi * 0.043 * t + 1.3)
        wind = L.svf(0.8 * wind_common + 0.45 * L.pink(n, np.random.default_rng(60 + side)), SR, wind_fc, 1.1, "bp")
        gust = 0.55 + 0.45 * np.sin(2 * np.pi * 0.09 * t + 0.8 + side * 0.4) ** 2
        hiss = L.hp(L.white(n, np.random.default_rng(70 + side)), SR, 7000, 2)
        hiss *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t + side) ** 2
        chans.append(0.22 * L.norm_peak(pad) + 0.07 * L.norm_peak(wind) * gust + 0.006 * L.norm_peak(hiss))
    S = Bus(D)
    S.add_lr(chans[0], chans[1])
    # faint distant icy shimmer: sparse high pings, heavily reverberated
    I = Bus(D)
    for j, (tt, m) in enumerate([(1.6, 88), (2.9, 95), (3.7, 93), (5.3, 100), (6.4, 95), (7.2, 88)]):
        I.add(ping(mhz(m), 1.6, 1.2, ratio=3.5, index=1.0, attack=0.006, seed=6000 + j), tt, 0.05,
              rng.uniform(-0.7, 0.7))
    il, ir = st_reverb(I.L, I.R, 0.9, 1.4, 1601, tone=7000)
    l = S.L + L.pad_to(il, n)
    r = S.R + L.pad_to(ir, n)
    l, r = st_reverb(l, r, 0.5, 0.25, 1602, tone=4000)
    l, r = L.pad_to(l, n), L.pad_to(r, n)
    fe = L.env_points(D, SR, [(0, 0), (1.8, 1), (D - 2.5, 1), (D, 0)], 1.5)
    return st_finish(l * fe, r * fe, -24.0, D, fade_in=0.05, fade_out=0.3)


# ----------------------------------------------------------------------------- 7 ambience loop
def load48(name):
    x, sr = L.read_wav(AMB / name)
    x = L.resample(x, sr, SR)
    return L.remove_dc(x, SR, 30.0)


def tile(x, start, n):
    reps = int(math.ceil((start + n) / x.size)) + 1
    return np.tile(x, reps)[start:start + n]


def ambience_loop():
    D = 60.0
    XF = 2.0
    n = n_(D + XF)
    srcs = {}
    for name in ("birds.wav", "coast.wav", "wind.wav"):
        s = L.loopify(load48(name), SR, 0.5)          # make each source circular first
        srcs[name] = L.norm_rms(s, 0.1)
    gains = {"birds.wav": 0.9, "coast.wav": 0.45, "wind.wav": 0.35}
    offs = {"birds.wav": (0.0, 23.7), "coast.wav": (5.0, 31.3), "wind.wav": (12.0, 41.9)}
    lr = []
    common = np.zeros(n)
    for name, s in srcs.items():
        common += gains[name] * tile(s, n_(offs[name][0]), n)
    for side in (0, 1):
        acc = np.zeros(n)
        for name, s in srcs.items():
            acc += gains[name] * tile(s, n_(offs[name][1] + 9.0 * side), n)
        lr.append(L.loopify(0.8 * common + 0.45 * acc, SR, XF))
    l, r = lr
    return st_finish(l, r, -25.0, D, loop=True)


# ----------------------------------------------------------------------------- verify + sheet
def verify(name, l, r, loop=False):
    m = mid(l, r)
    pk = L.db(max(np.abs(l).max(), np.abs(r).max()))
    st = L.st_rms_peak_db(m, SR)
    edge = int(0.003 * SR)
    head = max(np.abs(l[:edge]).max(), np.abs(r[:edge]).max())
    tail = max(np.abs(l[-edge:]).max(), np.abs(r[-edge:]).max())
    corr = float(np.dot(l, r) / (np.linalg.norm(l) * np.linalg.norm(r) + EPS))
    side = 0.5 * (l - r)
    sm = L.db(np.sqrt(np.mean(side ** 2)) / (np.sqrt(np.mean(m ** 2)) + EPS))
    clip = int(np.sum(np.maximum(np.abs(l), np.abs(r)) >= 0.999))
    info = dict(name=name, dur=l.size / SR, peak=pk, st=st, head=L.db(head), tail=L.db(tail),
                corr=corr, side_mid_db=sm, clip=clip)
    if loop:
        d = np.abs(np.diff(m))
        seam = abs(m[0] - m[-1])
        info["seam_jump_vs_p99"] = seam / (np.percentile(d, 99) + EPS)
        w = n_(0.5)
        info["seam_rms_db"] = (L.db(np.sqrt(np.mean(m[-w:] ** 2))), L.db(np.sqrt(np.mean(m[:w] ** 2))))
    return info


def colormap(v):
    """v in [0,1] -> warm 'magma-ish' RGB."""
    stops = np.array([[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66],
                      [245, 125, 21], [250, 193, 39], [252, 255, 164]], float)
    x = np.clip(v, 0, 1) * (len(stops) - 1)
    i = np.minimum(x.astype(int), len(stops) - 2)
    f = (x - i)[..., None]
    return (stops[i] * (1 - f) + stops[i + 1] * f).astype(np.uint8)


def contact_sheet(items, path):
    from PIL import Image, ImageDraw
    W, WH, SH, PAD, LBL = 1100, 90, 120, 10, 22
    H = len(items) * (LBL + WH + SH + PAD) + PAD
    img = Image.new("RGB", (W + 2 * PAD, H), (22, 22, 28))
    d = ImageDraw.Draw(img)
    y = PAD
    for info, l, r in items:
        d.text((PAD, y + 4), "%s   %.2f s   peak %.1f dBFS   st %.1f dB   L/R corr %.2f" %
               (info["name"], info["dur"], info["peak"], info["st"], info["corr"]), fill=(235, 235, 235))
        y += LBL
        # waveform: L up (blue), R down (orange) as min/max columns
        n = l.size
        cols = np.array_split(np.arange(n), W)
        for x, idx in enumerate(cols):
            if idx.size == 0:
                continue
            a = np.abs(l[idx]).max()
            b = np.abs(r[idx]).max()
            c = y + WH // 2
            d.line([(PAD + x, c - int(a * WH / 2)), (PAD + x, c)], fill=(110, 170, 255))
            d.line([(PAD + x, c), (PAD + x, c + int(b * WH / 2))], fill=(255, 170, 90))
        d.line([(PAD, y + WH // 2), (PAD + W, y + WH // 2)], fill=(70, 70, 80))
        y += WH
        m = mid(l, r)
        f, t, S = ss.spectrogram(m, SR, nperseg=1024, noverlap=768)
        S = 10 * np.log10(S + 1e-14)
        S = np.clip((S - (S.max() - 80)) / 80, 0, 1)
        # log-frequency rows 40 Hz .. 20 kHz
        fr = np.geomspace(40, 20000, SH)[::-1]
        rows = np.array([np.argmin(np.abs(f - q)) for q in fr])
        Z = S[rows]
        xs = np.linspace(0, Z.shape[1] - 1, W).astype(int)
        rgb = colormap(Z[:, xs])
        img.paste(Image.fromarray(rgb), (PAD, y))
        y += SH + PAD
    img.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    jobs = [("logo_sting", logo_sting), ("sparkle_form", sparkle_form), ("bubble_pop", bubble_pop),
            ("typing_ui", typing_ui), ("whoosh_soft_1", whoosh_1), ("whoosh_soft_2", whoosh_2),
            ("night_drone", night_drone), ("village_ambience_loop", ambience_loop)]
    items = []
    for name, fn in jobs:
        if only and name not in only:
            continue
        res = fn()
        extra = ""
        if name == "typing_ui":
            res, cnt = res
            extra = " clicks=%d" % cnt
        l, r = res
        p = write_stereo(OUT / (name + ".wav"), l, r)
        # re-read the file for verification (what the editor will get)
        a, sr = L.read_wav(p, mono=False)
        assert sr == SR and a.shape[1] == 2
        info = verify(name, a[:, 0], a[:, 1], loop=(name == "village_ambience_loop"))
        items.append((info, a[:, 0], a[:, 1]))
        print(" ".join("%s=%s" % (k, ("%.2f" % v) if isinstance(v, float) else v) for k, v in info.items()) + extra,
              "size=%dKB" % (p.stat().st_size // 1024), flush=True)
    if not only:
        contact_sheet(items, SCRATCH / "contact_sheet.png")
        print("sheet", SCRATCH / "contact_sheet.png")


if __name__ == "__main__":
    main()
