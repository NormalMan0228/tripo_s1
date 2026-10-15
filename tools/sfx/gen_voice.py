"""NPC voice variety (tools/sfx convention): alternate babble banks, emote barks, greeting barks and
letter/sign quill ticks. Everything is synthesised with numpy/scipy (license-clean).

    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_voice.py [--only banks,emote,greet,quill]
                                                            [--out DIR] [--slots DIR]

  banks  game/assets/sfx/voice/<id>_2.wav, <id>_3.wav   21 voices x 2 alternate syllable banks with the
         SAME layout as <id>.wav (28 slots of 0.115 s = onset x vowel, 22050 Hz, PCM import):
         every syllable re-synthesised with another seed, contour archetype (fall / late rise / dip /
         flat / early peak against the original arch), length, attack, release, breath, vowel colour
         (a glide from or toward a neighbouring vowel), coda (n / m / breathy h / clipped stop) and
         onset detail. Same f0, formant scale, breathiness class and shadow chorus as the original,
         so the character stays recognisable. A syllable scoring >= SLOT_SIM_MAX (sfx_qa similarity)
         against the same slot of the original or of bank 2 is re-rendered with the next coda /
         contour / envelope (deterministic). --slots DIR also writes every slot of the three banks as <id>_s<k>.wav / _2 / _3 so
         sfx_qa.py can compare the takes of each syllable.
  emote  game/assets/sfx/voice/emote_<register>_<kind>_<n>.wav  4 registers x 6 kinds x 5 takes:
         note (hum, "hm-hm-hmm"), exclaim ("oh!"), dots ("hmm..."), heart ("aww~"), mail ("ta-da!"),
         sleep (snore, "zzz").
  greet  game/assets/sfx/voice/greet_<register>_<n>.wav  4 registers x 6 takes ("hiya!", "oh, hi!" ...).
  quill  game/assets/sfx/voice/quill_<n>.wav  10 soft paper/quill ticks for lines with no speaker.

Registers (voice_babble.gd BARK_VOICES maps every speaker to one and pitches the take toward the
speaker's own f0): low 128 Hz, mid 205 Hz, high 285 Hz, child 420 Hz.

Loudness: banks = the original generator's per-syllable level (-17 dBFS over 40 ms at 32 kHz); barks
= the median st-rms of the existing banks; quill = ui/hover.wav. Never overwrites a git-tracked file.
Builds on tools/make_creature_sfx.py (its formant voice; that file's main() is never run here).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import sfxlib as L  # noqa: E402
import make_creature_sfx as C  # noqa: E402  (SR 32000; main() is guarded)
import sfx_qa as Q  # noqa: E402  (similarity features for the syllable rerolls)

VSR = C.SR                  # synthesis rate (32 kHz, as the original banks)
OUT_SR = C.VOICE_SR         # 22050
SLOT = C.SLOT
ONSETS = C.ONSETS
VOWELS = C.VOWEL_ORDER
CAST = C.VOICE_CAST
ALT_BANKS = (2, 3)

REGISTERS = {
    "low": dict(f0=128.0, fs=0.92, tilt=1.0, breath=0.16, rough=0.06),
    "mid": dict(f0=205.0, fs=1.0, tilt=1.1, breath=0.14, rough=0.0),
    "high": dict(f0=285.0, fs=1.12, tilt=1.15, breath=0.12, rough=0.0),
    "child": dict(f0=420.0, fs=1.3, tilt=1.1, breath=0.12, rough=0.0),
}
KINDS = ("note", "exclaim", "dots", "heart", "mail", "sleep")
EMOTE_TAKES = 5
GREET_TAKES = 6
QUILL_TAKES = 10


def secs(t: float) -> int:
    return C.secs(t)


# --------------------------------------------------------------------------- formant tracks
def formants(v) -> np.ndarray:
    """A vowel name of make_creature_sfx.VOWELS, a 4-tuple, or (name_a, name_b, mix)."""
    if isinstance(v, str):
        return np.array(C.VOWELS[v], float)
    if len(v) == 3 and isinstance(v[0], str):
        a, b, m = v
        return (1 - m) * np.array(C.VOWELS[a], float) + m * np.array(C.VOWELS[b], float)
    return np.array(v, float)


def ftracks(n, seq, scale=1.0):
    """[(t seconds, vowel), ...] -> four formant tracks (like C.tracks, with blended vowels)."""
    pts = [(t, formants(v) * scale) for t, v in seq]
    return [C.ctl(n, [(t, f[i]) for t, f in pts], 0.012) for i in range(4)]


# --------------------------------------------------------------------------- alternate banks
NEIGH = {"a": ("ae", "eo"), "e": ("ae", "i"), "i": ("e", "eu"), "o": ("u", "eo"), "u": ("o", "eu"),
         "eo": ("a", "o"), "eu": ("u", "e")}
CONTOUR_ORDER = ("fall", "late", "dip", "flat", "peak")
CODAS = ("n", "h", "stop", "m")   # syllable endings; the original bank's syllables are all open


def contour(kind: str, b: float):
    """f0 multipliers at normalised times; the original bank uses an arch (rise to 0.4, settle)."""
    m = max(abs(b), 0.04) + 0.04
    return {
        "fall": [(0, 1 + 0.9 * m), (0.5, 1 + 0.2 * m), (1, 1 - 0.7 * m)],
        "late": [(0, 1 - 0.3 * m), (0.6, 1.0 - 0.1 * m), (1, 1 + 1.3 * m)],
        "dip": [(0, 1 + 0.4 * m), (0.45, 1 - 0.8 * m), (1, 1 + 0.6 * m)],
        "flat": [(0, 1.0 + 0.1 * m), (1, 1.0 - 0.25 * m)],
        "peak": [(0, 1 - 0.6 * m), (0.2, 1 + 1.4 * m), (1, 1 - 0.3 * m)],
    }[kind]


def slot_variant(b: int, k: int) -> dict:
    """Structural variant of slot k in alternate bank b (2 or 3): the two alternates of one slot
    always differ from each other (contour, length direction, vowel side, glide, breath, attack)
    and from the original (arch contour, length 1.0, pure vowel)."""
    j = 0 if b == 2 else 1
    long_first = (k % 2 == 0) == (j == 0)
    return dict(
        contour=CONTOUR_ORDER[(k + 2 * j) % 5],
        dur=0.8 if long_first else 1.2,
        pre=1.2 if long_first else 0.75,
        coda=CODAS[(k + 2 * j) % 4],
        swell=not long_first,      # the long take (often capped by the slot) peaks late instead
        side=j,
        glide=("in", "out", "blend")[(k + j) % 3],
        breath=(0.6, 1.5)[((k // 2) + j) % 2],
        attack=(0.45, 1.8)[((k // 3) + j) % 2],
        release=(0.55, 1.45)[((k // 2) + j + 1) % 2],
        sus=(0.62, 1.0)[(k + j + 1) % 2],
        tilt=(0.88, 1.14)[((k // 4) + j) % 2],
        chorus=(0.004, 0.009)[j], detune=(0.988, 1.018)[j],
        sparkle=(6.01, 10.03)[j],   # the stargazer's shimmer partial (8.02 in the original)
    )


def alt_syllable(s, cfg, onset, vowel, v):
    """make_creature_sfx.syllable() with the structural variant v (same voice identity)."""
    shadow = cfg.get("shadow", False)
    f0 = cfg["f0"] * C.jit(s, 0.975, 1.025)
    fs = cfg["fs"] * C.jit(s, 0.975, 1.025)
    breath = float(np.clip(cfg.get("breath", 0.42 if shadow else 0.1) * v["breath"], 0.03, 0.8))
    pre = {"v": 0.0, "n": 0.0, "p": 0.012, "s": 0.026 if not shadow else 0.032}[onset] * v["pre"]
    L_ = cfg["dur"] * v["dur"] * C.jit(s, 0.97, 1.03)
    L_ = min(L_ - 0.5 * pre, SLOT - 0.017 - pre)
    out = np.zeros(secs(pre + L_ + 0.006))
    if onset == "s":
        m = secs(pre + 0.01)
        hi = (5200 if vowel in ("i", "e") else 4200) * C.jit(s, 0.85, 1.2)
        fr = C.nsweep(s, m, hi, C.jit(s, 0.35, 0.6)) * C.ctl(m, [(0, 0), (pre * C.jit(s, 0.45, 0.75), 1), (pre + 0.01, 0)])
        C.place(out, fr, 0.0, (0.35 if not shadow else 0.45) * C.jit(s, 0.8, 1.15))
    if onset == "p":
        lo = (2500 if vowel in ("i", "e") else 1200) * C.jit(s, 0.75, 1.3)
        C.place(out, C.click(s, 0.015, lo, lo * C.jit(s, 2.0, 3.0), C.jit(s, 0.0018, 0.0035)), max(0.0, pre - 0.008), 0.5 * C.jit(s, 0.8, 1.2))
    n = secs(L_)
    b = cfg.get("bounce", 0.04)
    f_pts = [(u * L_, f0 * r) for u, r in contour(v["contour"], b)]
    first = "m" if onset == "n" else ("eu" if onset == "p" else vowel)
    lead = 0.022 if onset in ("n", "p") else 0.0
    nb = NEIGH[vowel][v["side"]]
    amt = C.jit(s, 0.45, 0.7)
    if v["glide"] == "in":      # starts on the neighbour, settles on the vowel
        seq = [(0, first), (lead, (nb, vowel, 1 - amt)), (lead + 0.45 * (L_ - lead), vowel), (L_, vowel)]
    elif v["glide"] == "out":   # the vowel drifts toward the neighbour at the end
        seq = [(0, first), (lead, vowel), (lead + 0.45 * (L_ - lead), vowel), (L_, (vowel, nb, amt))]
    else:                       # a coloured vowel throughout
        col = (vowel, nb, amt * 0.7)
        seq = [(0, first), (lead, col), (L_, col)]
    attack = (0.01 if onset == "v" else (0.004 if onset == "p" else 0.008)) * v["attack"]
    rel = min(0.022 * v["release"], 0.45 * L_)
    amp = [(0, 0), (attack, 0.55 if onset == "n" else 1.0), (max(attack + 0.004, 0.025), 1.0), (L_ - rel, 0.85 * v["sus"]), (L_, 0)]
    if v.get("swell"):
        amp = [(0, 0), (attack, 0.4), (max(attack + 0.01, 0.66 * L_), 1.0), (max(L_ - rel, 0.8 * L_), 0.85 * v["sus"]), (L_, 0)]
    # Coda: a nasal close (n / m), a breathy release (h) or a clipped stop; the original is open.
    coda = v.get("coda", "")
    end_v = seq[-1][1]
    asp = None
    if coda in ("n", "m"):
        cut = 0.62 * L_
        seq = [q for q in seq if q[0] < cut] + [(cut, end_v), (L_, coda)]
        amp = [q for q in amp if q[0] < cut] + [(cut, 0.9), (max(L_ - rel, 0.78 * L_), 0.5), (L_, 0)]
    elif coda == "h":
        cut = 0.55 * L_
        amp = [q for q in amp if q[0] < cut] + [(cut, 0.8), (0.8 * L_, 0)]
        m = secs(L_ - 0.5 * L_)
        fc = float(formants(end_v)[1]) * fs * C.jit(s, 0.9, 1.1)
        asp = (0.5 * L_, C.nsweep(s, m, fc, 0.6) * C.ctl(m, [(0, 0), (0.3 * L_ * 0.5, 1.0), (0.5 * L_, 0)]))
    elif coda == "stop":      # a clipped end: the pitch drops, the voice stops, a small glottal catch
        amp = [q for q in amp if q[0] < L_ - 0.02] + [(L_ - 0.007, 0.95), (L_, 0)]
        f_end = float(np.interp(0.75 * L_, [q[0] for q in f_pts], [q[1] for q in f_pts]))
        f_pts = [q for q in f_pts if q[0] < 0.75 * L_] + [(0.75 * L_, f_end), (L_, f_end * 0.88)]
        asp = (L_ - 0.005, C.click(s, 0.01, 1300 * fs, 3600 * fs, 0.0015) * 0.8)
    tilt = cfg.get("tilt", 1.2 if shadow else 1.1) * v["tilt"]
    vv = C.voice(s, n, C.ctl(n, f_pts, 0.004), ftracks(n, seq, fs), C.ctl(n, amp, 0.003), tilt=tilt,
                 breath=breath, jitter=0.004, shimmer=0.03, fmax=7500, odd=0.45 if shadow else 0.0,
                 vib=cfg.get("vib", (0.0, 0.0)), sub=cfg.get("rough", 0.0), flutter=cfg.get("rough", 0.0))
    if shadow:  # the hollow chorus, with this bank's own delay and detune
        d = secs(v["chorus"])
        v2 = C.voice(s, n, C.ctl(n, f_pts, 0.004) * v["detune"], ftracks(n, seq, fs * 0.97), C.ctl(n, amp, 0.003),
                     tilt=1.3, breath=breath, jitter=0.006, fmax=6000, odd=0.5)
        vv = vv * 0.75 + np.concatenate([np.zeros(d), v2[: n - d]]) * 0.45
    if cfg.get("sparkle"):
        vv += C.glide(n, f0 * v["sparkle"] * C.jit(s, 0.99, 1.01)) * C.ctl(n, amp) * 0.05
    if asp is not None:
        C.place(out, asp[1], pre + asp[0], 0.3 * (1.0 + breath))
    C.place(out, vv, pre, 1.0)
    return C.fades(out, 0.002, 0.008)


SLOT_SIM_MAX = 0.86   # reroll a syllable whose QA similarity to another take of its slot reaches this
REROLLS = 12


def slot_prep(part: np.ndarray, sr: int = OUT_SR) -> np.ndarray:
    """A slot slice as the QA sees it: trailing silence trimmed, tiny fades."""
    return L.fades(L.trim_silence(part, sr, -60.0, lead=False, keep=0.004), sr, 0.0005, 0.004)


def alt_bank(name: str, b: int, others=()):
    """Alternate bank b of one voice. others: per-slot QA features of the banks already made for
    this voice (the original, bank 2); a syllable that scores >= SLOT_SIM_MAX against any of them
    is re-rendered with the next coda / contour (QA-driven reroll, deterministic)."""
    cfg = CAST[name]
    s = C.Synth(sum(map(ord, name)) * 6151 + 104729 * b)
    slot = secs(SLOT)
    bank = np.zeros(slot * len(ONSETS) * len(VOWELS))
    feats, rerolls, worst = [], 0, 0.0
    for oi, onset in enumerate(ONSETS):
        for vi, vowel in enumerate(VOWELS):
            k = oi * len(VOWELS) + vi
            base = slot_variant(b, k)
            best = None
            for t in range(REROLLS):
                v = dict(base)
                if t:
                    v["coda"] = CODAS[(CODAS.index(base["coda"]) + t) % len(CODAS)]
                    v["contour"] = CONTOUR_ORDER[(CONTOUR_ORDER.index(base["contour"]) + 2 * t) % len(CONTOUR_ORDER)]
                    v["swell"] = (not base["swell"]) if t % 2 else base["swell"]
                    if t >= 3:   # later rerolls also flip length, vowel glide, breath and attack
                        v["dur"], v["pre"] = (1.2, 0.75) if base["dur"] < 1.0 else (0.8, 1.2)
                        v["glide"] = ("in", "out", "blend")[(("in", "out", "blend").index(base["glide"]) + t) % 3]
                        v["breath"] = 1.5 if base["breath"] < 1.0 else 0.6
                        v["attack"] = 1.8 if base["attack"] < 1.0 else 0.45
                x = C.level(alt_syllable(s, cfg, onset, vowel, v), -17.0, window=0.04)
                assert x.size <= slot - secs(0.008), (name, b, onset, vowel, x.size / VSR)
                f = Q.features(slot_prep(C.resample_to(x, OUT_SR)), OUT_SR)
                sim = max([Q.similarity(f, o[k]) for o in others] or [0.0])
                if best is None or sim < best[0]:
                    best = (sim, x, f)
                if sim < SLOT_SIM_MAX:
                    break
                rerolls += 1
            sim, x, f = best
            worst = max(worst, sim)
            feats.append(f)
            bank[k * slot: k * slot + x.size] = x
    x = C.resample_to(bank, OUT_SR)
    return np.clip(x, -0.95, 0.95), feats, rerolls, worst


def bank_slots(x: np.ndarray, sr: int):
    """The 28 slot slices of a bank (as voice_babble.gd cuts them)."""
    out = []
    for k in range(len(ONSETS) * len(VOWELS)):
        a = int(round(k * SLOT * sr))
        b = min(int(round((k + 1) * SLOT * sr)), x.size)
        out.append(x[a:b])
    return out


def check_bank(x: np.ndarray, sr: int) -> list:
    """voice_babble / audio_bank_check rules: 3.0-3.4 s, every slot sounds, last 5 ms silent."""
    probs = []
    dur = x.size / sr
    if not 3.0 <= dur <= 3.4:
        probs.append("length %.3f" % dur)
    for k, part in enumerate(bank_slots(x, sr)):
        if np.max(np.abs(part)) <= 0.05:
            probs.append("slot %d silent" % k)
        if np.max(np.abs(part[-int(0.005 * sr):])) >= 0.01:
            probs.append("slot %d runs into the next" % k)
    if np.max(np.abs(x)) > 0.95:
        probs.append("peak")
    return probs


def make_banks(out_dir: Path, slots_dir: Path | None) -> list:
    meta = []
    for name in CAST:
        orig_path = L.SFX_ROOT / "voice" / ("%s.wav" % name)
        orig = L.read_wav(orig_path)[0] if orig_path.exists() else None
        takes = {}
        others = [[Q.features(slot_prep(part), OUT_SR) for part in bank_slots(orig, OUT_SR)]] if orig is not None else []
        notes = []
        for b in ALT_BANKS:
            x, feats, rerolls, worst = alt_bank(name, b, others)
            others.append(feats)
            notes.append("bank %d: %d rerolls, max slot sim %.3f" % (b, rerolls, worst))
            probs = check_bank(x, OUT_SR)
            if probs:
                raise SystemExit("bank %s_%d: %s" % (name, b, ", ".join(probs[:6])))
            d = L.write_take(out_dir / ("%s_%d.wav" % (name, b)), x, OUT_SR, raw=True)
            d.update(event=name, take=b)
            meta.append(d)
            takes[b] = x
        if slots_dir is not None:
            sets = {1: orig} if orig is not None else {}
            sets.update(takes)
            for b, x in sets.items():
                for k, part in enumerate(bank_slots(x, OUT_SR)):
                    y = slot_prep(part)
                    suffix = "" if b == 1 else "_%d" % b
                    L.write_wav(slots_dir / ("%s_s%02d%s.wav" % (name, k, suffix)), y, OUT_SR)
        st = [L.st_rms_peak_db(t, OUT_SR) for t in takes.values()]
        ost = L.st_rms_peak_db(orig, OUT_SR) if orig is not None else float("nan")
        print("bank %-12s orig st %6.1f  alt st %s  %s" % (name, ost, " ".join("%6.1f" % v for v in st), "; ".join(notes)))
    return meta


# --------------------------------------------------------------------------- bark building blocks
def syl(s, reg, dur, f_rel, vow, onset="v", amp="arch", breath=None, vib=(0.0, 0.0), tilt=None,
        rough=None, f0_mul=1.0):
    """One voiced syllable at 32 kHz.
    f_rel: [(u 0..1, ratio)] pitch contour relative to the register f0 (x f0_mul);
    vow: [(u 0..1, vowel)] formant targets; onset: v soft, g glottal, h breathy, m / n nasal,
    d tap, l liquid, y i-glide, w u-glide; amp: arch | fall | swell | flat | clip."""
    pre = {"h": 0.05, "d": 0.006}.get(onset, 0.0) * C.jit(s, 0.85, 1.15)
    n = secs(dur)
    f0 = reg["f0"] * f0_mul
    f_pts = [(u * dur, f0 * r) for u, r in f_rel]
    if onset == "g":
        f_pts = [(0.0, f_pts[0][1] * 0.9)] + [(max(u, 0.02), r) for u, r in f_pts]
    seq = [(u * dur, v) for u, v in vow]
    lead = {"m": "m", "n": "n", "l": "n", "y": "i", "w": "u", "d": "eu"}.get(onset)
    if lead:
        g = {"m": 0.04, "n": 0.035, "l": 0.022, "y": 0.045, "w": 0.05, "d": 0.014}[onset] * C.jit(s, 0.85, 1.2)
        g = min(g, 0.4 * dur)
        seq = [(0.0, lead), (g, seq[0][1])] + [(max(t, g + 0.005), v) for t, v in seq[1:]]
    a = {"v": 0.016, "g": 0.004, "h": 0.022, "m": 0.012, "n": 0.01, "d": 0.003, "l": 0.01, "y": 0.014, "w": 0.02}[onset]
    a *= C.jit(s, 0.8, 1.25)
    r = min(0.045, 0.35 * dur)
    shapes = {
        "arch": [(0, 0), (a, 0.85), (0.4 * dur, 1.0), (dur - r, 0.75), (dur, 0)],
        "fall": [(0, 0), (a, 1.0), (0.3 * dur, 0.8), (dur - r, 0.35), (dur, 0)],
        "swell": [(0, 0), (a, 0.55), (0.7 * dur, 1.0), (dur - r, 0.85), (dur, 0)],
        "flat": [(0, 0), (a, 1.0), (dur - r, 0.9), (dur, 0)],
        "clip": [(0, 0), (a, 1.0), (dur - 0.012, 0.95), (dur, 0)],
    }
    pts = shapes[amp]
    if onset in ("m", "n", "l"):
        pts = [pts[0], (a, 0.5)] + [(max(t, a + 0.02), v) for t, v in pts[2:]]
    br = reg["breath"] if breath is None else breath
    rg = reg["rough"] if rough is None else rough
    vv = C.voice(s, n, C.ctl(n, f_pts, 0.005), ftracks(n, seq, reg["fs"]), C.ctl(n, pts, 0.003),
                 tilt=reg["tilt"] if tilt is None else tilt, breath=br, jitter=0.005, shimmer=0.035,
                 fmax=7500, vib=vib, sub=rg, flutter=rg)
    out = np.zeros(secs(pre) + n + secs(0.004))
    if onset == "h":
        m = secs(pre + 0.03)
        fc = float(formants(vow[0][1])[1]) * reg["fs"] * C.jit(s, 0.85, 1.1)
        asp = C.nsweep(s, m, fc, 0.7) * C.ctl(m, [(0, 0), (pre * 0.7, 1.0), (pre + 0.03, 0)])
        C.place(out, asp, 0.0, 0.38 * C.jit(s, 0.8, 1.2))
    if onset == "d":
        C.place(out, C.click(s, 0.012, 1400 * reg["fs"], 4200 * reg["fs"], 0.0022), 0.0, 0.35)
    C.place(out, vv, pre, 1.0)
    return out


def noise_swell(s, dur, fc_pts, amp_pts, bw=0.7):
    """Breath noise (inhale, exhale, sigh): fc and amp points in seconds."""
    return C.breathy(s, dur, fc_pts, amp_pts, bw)


def buzz(s, reg, dur, amp_pts, f_ratio=0.8, fc=4800.0):
    """A sleepy "zzz": a fricative band gated by a low voiced buzz, plus the buzz itself."""
    n = secs(dur)
    f0 = reg["f0"] * f_ratio
    hiss = C.nsweep(s, n, fc * C.jit(s, 0.9, 1.1), 0.35)
    ph = 2 * np.pi * np.cumsum(C.full(n, f0) * (1 + C.wander(s, n, 8, 0.01))) / VSR
    gate = 0.55 + 0.45 * np.sin(ph)
    hum = C.voice(s, n, f0, ftracks(n, [(0, "n")]), 1.0, tilt=1.4, breath=0.2, fmax=5000)
    return (hiss * gate * 0.8 + hum * 0.35) * C.ctl(n, amp_pts)


def phrase(parts, tail=0.02):
    """[(at seconds, signal, gain)] -> one signal."""
    end = max(at + x.size / VSR for at, x, _ in parts) + tail
    out = np.zeros(secs(end))
    for at, x, g in parts:
        C.place(out, x, at, g)
    return out


def st(semi: float) -> float:
    return 2.0 ** (semi / 12.0)


# --------------------------------------------------------------------------- emotes
def emote_note(s, reg, i, rng):
    """Hums: 5 melodic archetypes (note count, interval pattern, mouth shape, rhythm)."""
    j = rng.uniform(0.94, 1.06)
    p = rng.uniform(0.97, 1.03)
    if i == 0:   # "hm-hm-hmm" up the steps, even rhythm, closed mouth
        steps, durs, gap = (0, 2, 4), (0.11, 0.11, 0.26), 0.15
        parts = []
        at = 0.0
        for k, (sm, d) in enumerate(zip(steps, durs)):
            f = st(sm) * p
            parts.append((at, syl(s, reg, d * j, [(0, f), (1, f * 1.01)], [(0, "m"), (1, ("m", "u", 0.3))], "m",
                                  "flat" if k < 2 else "arch", tilt=1.6, vib=(5.5, 0.018) if k == 2 else (0, 0)), 1.0))
            at += gap * j
        return phrase(parts)
    if i == 1:   # "la-la" falling fourth, dotted (short-long), open vowel
        a = syl(s, reg, 0.15 * j, [(0, st(5) * p), (1, st(5) * p * 0.99)], [(0, "a"), (1, "a")], "l", "flat")
        b = syl(s, reg, 0.3 * j, [(0, p), (0.6, p * 1.01), (1, p * 0.97)], [(0, "a"), (1, ("a", "o", 0.4))], "l", "arch",
                vib=(5.0, 0.02))
        return phrase([(0.0, a, 1.0), (0.2 * j, b, 0.95)])
    if i == 2:   # "du-du-du" staccato arpeggio up, tap onsets
        parts = []
        for k, sm in enumerate((0, 4, 7)):
            f = st(sm) * p
            parts.append((k * 0.13 * j, syl(s, reg, 0.075 * j, [(0, f), (1, f)], [(0, "u"), (1, "o")], "d", "clip"), 0.9))
        return phrase(parts)
    if i == 3:   # "mm~mm" one long legato hum sliding up a fifth through a dip, vibrato
        return syl(s, reg, 0.62 * j, [(0, p), (0.3, p * 0.96), (0.55, st(7) * p), (1, st(7) * p * 0.98)],
                   [(0, "m"), (0.5, ("m", "u", 0.5)), (1, "m")], "m", "swell", tilt=1.5, vib=(5.5, 0.025))
    # "na-na-na-na" quick, alternating, last note held
    parts = []
    at = 0.0
    for k, (sm, d) in enumerate(zip((7, 4, 5, 0), (0.075, 0.075, 0.075, 0.17))):
        f = st(sm) * p
        parts.append((at, syl(s, reg, d * j, [(0, f), (1, f * (0.97 if k == 3 else 1.0))], [(0, "a"), (1, "ae")], "n",
                              "flat" if k < 3 else "fall"), 0.95))
        at += 0.1 * j
    return phrase(parts)


def emote_exclaim(s, reg, i, rng):
    j = rng.uniform(0.94, 1.06)
    p = rng.uniform(0.97, 1.03)
    if i == 0:   # "oh!" glottal, quick rise, falls away
        return syl(s, reg, 0.2 * j, [(0, 0.95 * p), (0.25, 1.32 * p), (1, 1.18 * p)], [(0, "o"), (1, "o")], "g", "fall")
    if i == 1:   # "eh?!" rising question
        return syl(s, reg, 0.26 * j, [(0, 1.0 * p), (0.5, 1.06 * p), (1, 1.5 * p)], [(0, "e"), (1, ("e", "ae", 0.5))], "g", "swell")
    if i == 2:   # "ah!" breathy start, high falling
        return syl(s, reg, 0.17 * j, [(0, 1.38 * p), (1, 1.05 * p)], [(0, "a"), (1, "a")], "h", "fall", breath=reg["breath"] + 0.1)
    if i == 3:   # "hup!" very short, lip pop at the end
        x = syl(s, reg, 0.085 * j, [(0, 1.2 * p), (1, 1.28 * p)], [(0, "u"), (1, "eu")], "h", "clip")
        pop = C.click(s, 0.01, 900 * reg["fs"], 2600 * reg["fs"], 0.0015)
        return phrase([(0.0, x, 1.0), (x.size / VSR - 0.004, pop, 0.4)])
    # "whoa~" u -> o -> a glide, rise and fall
    return syl(s, reg, 0.38 * j, [(0, 1.0 * p), (0.4, 1.35 * p), (1, 0.95 * p)], [(0, "u"), (0.35, "o"), (1, "a")], "w", "arch")


def emote_dots(s, reg, i, rng):
    j = rng.uniform(0.94, 1.06)
    p = rng.uniform(0.97, 1.03)
    if i == 0:   # "hmm..." long closed hum, sinking
        return syl(s, reg, 0.55 * j, [(0, p), (0.6, 0.97 * p), (1, 0.85 * p)], [(0, "m"), (1, "m")], "m", "fall",
                   tilt=1.6, breath=reg["breath"] + 0.12)
    if i == 1:   # "hm-hm" two short hums, the second lower
        a = syl(s, reg, 0.11 * j, [(0, 1.04 * p), (1, 1.02 * p)], [(0, "m"), (1, "m")], "m", "flat", tilt=1.6)
        b = syl(s, reg, 0.16 * j, [(0, 0.93 * p), (1, 0.88 * p)], [(0, "m"), (1, ("m", "eu", 0.3))], "m", "fall", tilt=1.6)
        return phrase([(0.0, a, 1.0), (0.21 * j, b, 0.9)])
    if i == 2:   # "uh..." open, flat-falling, creaky end
        return syl(s, reg, 0.42 * j, [(0, 1.0 * p), (0.5, 0.98 * p), (1, 0.82 * p)], [(0, "eo"), (1, "eu")], "v", "fall",
                   rough=0.22, breath=reg["breath"] + 0.08)
    if i == 3:   # "mmm?" dips then rises (puzzled)
        return syl(s, reg, 0.46 * j, [(0, 1.0 * p), (0.5, 0.9 * p), (1, 1.2 * p)], [(0, "m"), (0.6, "m"), (1, ("m", "eu", 0.5))],
                   "m", "swell", tilt=1.5)
    # "ehh..." breathy, long slow fall with a slow waver
    return syl(s, reg, 0.6 * j, [(0, 1.08 * p), (1, 0.86 * p)], [(0, "e"), (1, "eo")], "h", "fall", vib=(3.2, 0.02),
               breath=reg["breath"] + 0.22)


def emote_heart(s, reg, i, rng):
    j = rng.uniform(0.94, 1.06)
    p = rng.uniform(0.97, 1.03)
    if i == 0:   # "aww~" a -> o -> u, rise-fall, warm vibrato
        return syl(s, reg, 0.5 * j, [(0, 1.1 * p), (0.3, 1.3 * p), (1, 0.95 * p)], [(0, "a"), (0.5, "o"), (1, "u")], "w", "arch",
                   vib=(6.0, 0.025), breath=reg["breath"] + 0.08)
    if i == 1:   # "ooh~" rising slide
        return syl(s, reg, 0.42 * j, [(0, 0.95 * p), (1, 1.3 * p)], [(0, "u"), (1, "o")], "v", "swell", vib=(5.5, 0.015))
    if i == 2:   # "hehe" two giggles
        a = syl(s, reg, 0.075 * j, [(0, 1.3 * p), (1, 1.32 * p)], [(0, "e"), (1, "e")], "h", "clip", breath=reg["breath"] + 0.15)
        b = syl(s, reg, 0.085 * j, [(0, 1.22 * p), (1, 1.18 * p)], [(0, "e"), (1, "e")], "h", "fall", breath=reg["breath"] + 0.15)
        return phrase([(0.0, a, 1.0), (0.15 * j, b, 0.9)])
    if i == 3:   # "mm~" happy closed hum, up-down
        return syl(s, reg, 0.45 * j, [(0, 1.0 * p), (0.35, 1.26 * p), (1, 1.05 * p)], [(0, "m"), (1, ("m", "u", 0.4))], "m", "arch",
                   tilt=1.5)
    # "ehehe" three quick giggles, falling
    parts = []
    for k, f in enumerate((1.36, 1.29, 1.2)):
        parts.append((k * 0.1 * j, syl(s, reg, 0.058 * j, [(0, f * p), (1, f * p)], [(0, "e"), (1, "ae")], "v" if k == 0 else "h",
                                       "clip", breath=reg["breath"] + 0.12), 1.0 - 0.08 * k))
    return phrase(parts)


def emote_mail(s, reg, i, rng):
    j = rng.uniform(0.94, 1.06)
    p = rng.uniform(0.97, 1.03)
    if i == 0:   # "here!" i -> eo, rising
        return syl(s, reg, 0.26 * j, [(0, 1.05 * p), (1, 1.3 * p)], [(0, "i"), (0.5, "eo"), (1, "eo")], "h", "arch")
    if i == 1:   # "ta-da!" up a fourth
        a = syl(s, reg, 0.09 * j, [(0, p), (1, p)], [(0, "a"), (1, "a")], "d", "clip")
        b = syl(s, reg, 0.22 * j, [(0, st(5) * p), (1, st(5) * p * 0.98)], [(0, "a"), (1, "a")], "d", "fall")
        return phrase([(0.0, a, 0.9), (0.15 * j, b, 1.0)])
    if i == 2:   # "yoo-hoo" calling, high then lower
        a = syl(s, reg, 0.16 * j, [(0, 1.2 * p), (1, 1.24 * p)], [(0, "u"), (1, "u")], "y", "flat")
        b = syl(s, reg, 0.22 * j, [(0, 1.04 * p), (1, 0.98 * p)], [(0, "u"), (1, "o")], "h", "fall")
        return phrase([(0.0, a, 1.0), (0.22 * j, b, 0.9)])
    if i == 3:   # "o-ho!" low then a high hop
        a = syl(s, reg, 0.1 * j, [(0, p), (1, p)], [(0, "o"), (1, "o")], "v", "flat")
        b = syl(s, reg, 0.2 * j, [(0, 1.36 * p), (0.3, 1.42 * p), (1, 1.3 * p)], [(0, "o"), (1, "o")], "h", "fall")
        return phrase([(0.0, a, 0.85), (0.15 * j, b, 1.0)])
    # "hey-ya!" e -> i, then a
    a = syl(s, reg, 0.13 * j, [(0, 1.12 * p), (1, 1.18 * p)], [(0, "e"), (1, "i")], "h", "flat")
    b = syl(s, reg, 0.18 * j, [(0, 1.28 * p), (1, 1.22 * p)], [(0, "a"), (1, "a")], "y", "fall")
    return phrase([(0.0, a, 0.9), (0.17 * j, b, 1.0)])


def emote_sleep(s, reg, i, rng):
    j = rng.uniform(0.94, 1.06)
    p = rng.uniform(0.97, 1.03)
    if i == 0:   # snore: inhale hiss, then a low fluttering exhale
        inhale = noise_swell(s, 0.38 * j, [(0, 650), (0.38 * j, 1050)], [(0, 0), (0.3 * j, 1.0), (0.38 * j, 0)], 0.8)
        reg2 = dict(reg, f0=max(55.0, reg["f0"] * 0.45 * p))
        out = syl(s, reg2, 0.34 * j, [(0, 1.0), (1, 0.9)], [(0, "o"), (1, "eu")], "v", "fall", rough=0.6, breath=0.45, tilt=0.9)
        return phrase([(0.0, inhale, 0.55), (0.42 * j, out, 1.0)])
    if i == 1:   # "zzz" one long buzz, swelling and fading
        d = 0.62 * j
        return buzz(s, dict(reg, f0=reg["f0"] * p), d, [(0, 0), (0.15 * d, 0.7), (0.55 * d, 1.0), (d, 0)])
    if i == 2:   # "mmnn..." sleepy murmur, sinking, with a sigh after it
        m = syl(s, reg, 0.42 * j, [(0, 0.95 * p), (1, 0.8 * p)], [(0, "m"), (1, "n")], "m", "fall", tilt=1.6, breath=reg["breath"] + 0.25)
        sigh = noise_swell(s, 0.3 * j, [(0, 1300), (0.3 * j, 700)], [(0, 0), (0.06, 1.0), (0.3 * j, 0)], 0.9)
        return phrase([(0.0, m, 1.0), (0.38 * j, sigh, 0.4)])
    if i == 3:   # "zz-zz" two short buzzes
        a = buzz(s, dict(reg, f0=reg["f0"] * p), 0.24 * j, [(0, 0), (0.05, 1.0), (0.24 * j, 0)], f_ratio=0.85, fc=5200)
        b = buzz(s, dict(reg, f0=reg["f0"] * p), 0.32 * j, [(0, 0), (0.08, 1.0), (0.32 * j, 0)], f_ratio=0.78, fc=4500)
        return phrase([(0.0, a, 0.9), (0.36 * j, b, 1.0)])
    # "fuuu" long exhale with a faint low "u" inside
    d = 0.6 * j
    ex = noise_swell(s, d, [(0, 1250), (d, 600)], [(0, 0), (0.08, 1.0), (d, 0)], 0.6)
    u = syl(s, dict(reg, f0=reg["f0"] * 0.7 * p), d * 0.8, [(0, 1.0), (1, 0.9)], [(0, "u"), (1, "u")], "v", "fall", breath=0.6, tilt=1.4)
    return phrase([(0.0, ex, 1.0), (0.06, u, 0.45)])


EMOTE_FN = {"note": emote_note, "exclaim": emote_exclaim, "dots": emote_dots, "heart": emote_heart,
            "mail": emote_mail, "sleep": emote_sleep}


def greet_take(s, reg, i, rng):
    j = rng.uniform(0.94, 1.06)
    p = rng.uniform(0.97, 1.03)
    if i == 0:   # "hiya!" rising
        a = syl(s, reg, 0.1 * j, [(0, 1.12 * p), (1, 1.18 * p)], [(0, "i"), (1, "i")], "h", "flat")
        b = syl(s, reg, 0.18 * j, [(0, 1.24 * p), (0.4, 1.34 * p), (1, 1.26 * p)], [(0, "a"), (1, "a")], "y", "fall")
        return phrase([(0.0, a, 0.9), (0.12 * j, b, 1.0)])
    if i == 1:   # "oh, hi!" a low "oh", a pause, a high "hi"
        a = syl(s, reg, 0.14 * j, [(0, 1.0 * p), (1, 0.95 * p)], [(0, "o"), (1, "o")], "g", "fall")
        b = syl(s, reg, 0.16 * j, [(0, 1.28 * p), (1, 1.34 * p)], [(0, "a"), (0.4, "i"), (1, "i")], "h", "arch")
        return phrase([(0.0, a, 0.85), (0.24 * j, b, 1.0)])
    if i == 2:   # "hello~" two syllables, the second rising then falling
        a = syl(s, reg, 0.1 * j, [(0, 1.05 * p), (1, 1.08 * p)], [(0, "e"), (1, "e")], "h", "flat")
        b = syl(s, reg, 0.26 * j, [(0, 1.18 * p), (0.35, 1.28 * p), (1, 1.04 * p)], [(0, "o"), (1, ("o", "u", 0.4))], "l", "arch")
        return phrase([(0.0, a, 0.9), (0.11 * j, b, 1.0)])
    if i == 3:   # "hey!" one bright diphthong
        return syl(s, reg, 0.24 * j, [(0, 1.1 * p), (0.4, 1.32 * p), (1, 1.15 * p)], [(0, "e"), (0.6, "e"), (1, "i")], "h", "arch")
    if i == 4:   # "hi-hi!" two quick his, the second higher
        a = syl(s, reg, 0.08 * j, [(0, 1.24 * p), (1, 1.26 * p)], [(0, "a"), (0.35, "i"), (1, "i")], "h", "clip")
        b = syl(s, reg, 0.12 * j, [(0, 1.34 * p), (1, 1.36 * p)], [(0, "a"), (0.35, "i"), (1, "i")], "h", "fall")
        return phrase([(0.0, a, 0.9), (0.14 * j, b, 1.0)])
    # "yo-ho~" sing-song, falling with a little vibrato
    a = syl(s, reg, 0.13 * j, [(0, 1.2 * p), (1, 1.22 * p)], [(0, "o"), (1, "o")], "y", "flat")
    b = syl(s, reg, 0.24 * j, [(0, 1.06 * p), (1, 0.98 * p)], [(0, "o"), (1, ("o", "u", 0.3))], "h", "fall", vib=(5.5, 0.02))
    return phrase([(0.0, a, 1.0), (0.18 * j, b, 0.9)])


# --------------------------------------------------------------------------- quill ticks
QUILL_REF = None   # set by main() from ui/hover.wav
def quill_take(rng, i):
    """Soft paper/quill ticks: 10 archetypes (stroke direction, grain, taps, length, band)."""
    sr = OUT_SR
    i = i - 1                      # make_family numbers takes from 1
    j = rng.uniform(0.93, 1.07)

    def stroke(dur, f_a, f_b, grain_hz, q=1.2, rough=0.6):
        n = L.secs(dur, sr)
        x = L.white(n, rng)
        fc = np.geomspace(f_a, f_b, n)
        y = L.svf(x, sr, fc, q=q, mode="bp")
        # paper tooth: random grains modulating the stroke
        g = L.lp(np.abs(L.white(n, rng)) ** 3, sr, grain_hz)
        g = g / (np.max(g) + 1e-9)
        y = y * ((1 - rough) + rough * g)
        return y * L.env_points(dur, sr, [(0, 0), (min(0.006, dur * 0.2), 1.0), (dur * 0.6, 0.7), (dur, 0)])

    def tap(f, tau=0.004, body=180.0):
        n = L.secs(0.03, sr)
        t = L.tvec(n, sr)
        tip = L.bp(L.white(n, rng), sr, f * 0.7, f * 1.4) * np.exp(-t / tau)
        thump = np.sin(2 * np.pi * body * t) * np.exp(-t / 0.006) * 0.35
        return tip + thump

    out = np.zeros(L.secs(0.14, sr))
    if i == 0:     # a level hiss of the nib, then the pen knocks down for the next letter
        L.place(out, stroke(0.032 * j, 5200, 4900, 1500, q=1.3, rough=0.4), 0.0, sr)
        L.place(out, tap(1800 * j, 0.003, 120.0), 0.058 * j, sr, gain=0.7)
    elif i == 1:   # pen dot: a single tap with a little paper grain after it
        L.place(out, tap(2600 * j, 0.005), 0.0, sr)
        L.place(out, stroke(0.018 * j, 2400, 2000, 600, rough=0.8), 0.006, sr, gain=0.35)
    elif i == 2:   # double scritch
        L.place(out, stroke(0.022 * j, 3000, 4200, 1100), 0.0, sr)
        L.place(out, stroke(0.026 * j, 3600, 2800, 1100), 0.034 * j, sr, gain=0.85)
    elif i == 3:   # long wobbly swish, rising, the hand's loop audible as a slow flutter
        d = 0.09 * j
        y = stroke(d, 1400, 4600, 700, q=0.9, rough=0.4)
        y *= 0.55 + 0.45 * np.sin(2 * np.pi * 24.0 * L.tvec(y.size, sr) + 1.2) ** 2
        L.place(out, y, 0.0, sr)
    elif i == 4:   # pen-down thump, then a falling downstroke
        L.place(out, tap(1300 * j, 0.006, 140.0), 0.0, sr, gain=0.9)
        L.place(out, stroke(0.05 * j, 5000, 1800, 800), 0.03 * j, sr, gain=0.8)
    elif i == 5:   # tap then a short scratch
        L.place(out, tap(2000 * j, 0.003), 0.0, sr, gain=0.8)
        L.place(out, stroke(0.032 * j, 2800, 3800, 1000), 0.018 * j, sr, gain=0.9)
    elif i == 6:   # papery rustle tick (low band, rough)
        L.place(out, stroke(0.04 * j, 900, 2400, 500, q=0.8, rough=0.85), 0.0, sr)
    elif i == 7:   # triple flick
        for k, f in enumerate((4200, 3500, 4700)):
            L.place(out, stroke(0.014 * j, f, f * 1.15, 1400), k * 0.024 * j, sr, gain=1.0 - 0.15 * k)
    elif i == 8:   # nib "tsk": high and short
        L.place(out, stroke(0.024 * j, 5600, 7400, 1600, q=1.6, rough=0.5), 0.0, sr)
    else:          # zigzag scribble: three quick back-and-forth strokes, the band hopping
        n = L.secs(0.08 * j, sr)
        t = L.tvec(n, sr)
        fc = 3000 + 1100 * np.sign(np.sin(2 * np.pi * 37.0 * t))
        y = L.svf(L.white(n, rng), sr, fc, q=1.1, mode="bp")
        y = y * np.abs(np.sin(2 * np.pi * 18.5 * t)) ** 1.5 * L.env_points(0.08 * j, sr, [(0, 0), (0.006, 1), (0.06, 0.8), (0.08 * j, 0)])
        L.place(out, y, 0.0, sr)
    # matched and trimmed here, so finish() measures the level on the take's own length (a take
    # shorter than the 120 ms window is measured over its length, like ui/hover.wav)
    y = L.hp(out, sr, 400)
    y = L.match_to(y, sr, QUILL_REF) if QUILL_REF is not None else y
    return L.trim_silence(y, sr, -60.0, keep=0.012)


# --------------------------------------------------------------------------- families
def bark_family(out_dir: Path, event: str, n: int, fn, reg, ref_db: float) -> list:
    def take(rng, i):
        s = C.Synth(int(rng.integers(1, 2 ** 31 - 1)))
        x = fn(s, reg, i - 1, rng)
        return L.resample(x, VSR, OUT_SR)
    return L.make_family(out_dir, event, n, take, sr=OUT_SR, ref_db=ref_db, seed_base="voice",
                         finish_kw=dict(fade_in=0.003, fade_out=0.02), verbose=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="banks,emote,greet,quill")
    ap.add_argument("--out", default=str(L.SFX_ROOT / "voice"), help="output directory (default: the game's voice dir)")
    ap.add_argument("--slots", default="", help="also write per-slot syllables of all banks here (QA)")
    args = ap.parse_args()
    groups = set(args.only.split(","))
    out = Path(args.out)
    banks = sorted((L.SFX_ROOT / "voice").glob("*.wav"))
    bank_ref = L.ref_db_of([p for p in banks if p.stem in CAST])
    quill_ref = L.ref_db_of(L.SFX_ROOT / "ui" / "hover.wav")
    global QUILL_REF
    QUILL_REF = quill_ref
    meta = []
    if "banks" in groups:
        meta += make_banks(out, Path(args.slots) if args.slots else None)
    if "emote" in groups:
        for rname, reg in REGISTERS.items():
            for kind in KINDS:
                m = bark_family(out, "emote_%s_%s" % (rname, kind), EMOTE_TAKES, EMOTE_FN[kind], reg, bank_ref)
                meta += m
                print(L.family_report(m).splitlines()[-1].replace("takes", "takes emote_%s_%s:" % (rname, kind)))
    if "greet" in groups:
        for rname, reg in REGISTERS.items():
            m = bark_family(out, "greet_%s" % rname, GREET_TAKES, greet_take, reg, bank_ref)
            meta += m
            print(L.family_report(m).splitlines()[-1].replace("takes", "takes greet_%s:" % rname))
    if "quill" in groups:
        m = L.make_family(out, "quill", QUILL_TAKES, quill_take, sr=OUT_SR, ref_db=quill_ref, seed_base="voice",
                          finish_kw=dict(fade_in=0.002, fade_out=0.012), verbose=True)
        meta += m
    warn = [d for d in meta if d.get("warning")]
    total = sum(d["bytes"] for d in meta)
    print("voice: %d files, %.2f MB new, bark ref %.1f dB, quill ref %.1f dB, %d level warnings"
          % (len(meta), total / 1048576.0, bank_ref, quill_ref, len(warn)))
    return 1 if warn else 0


if __name__ == "__main__":
    sys.exit(main())
