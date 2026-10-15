"""sfx_qa: quality and repetition check for sound take families (tools/sfx convention).

    python tools/sfx/sfx_qa.py <dir|glob|file>... [--group auto|dir|none] [--sheet out.png]
                               [--json out.json] [--min-takes N] [--strict] [--quiet]

Per file: duration, peak dBFS, short-term RMS peak (120 ms, 150 Hz high-pass: the game's
audio_bank_check measure), DC offset, clipped samples, edge levels (max |x| in the first/last
2 ms and the first/last sample), leading/trailing silence, spectral centroid, header shape.

Families (--group auto): files in one directory whose names differ only by a trailing _<n>
(the bare original <event>.wav joins its <event>_<n>.wav takes). Per family: take count,
loudness spread and outliers, and pairwise similarity of every two takes:
  sim = the lower of two resolutions' scores; each is the best Pearson correlation of the takes'
        log band-energy maps (40 dB range under each take's own peak) after aligning onsets and
        searching +-30 ms lag, time scale 0.92..1.08 and pitch 0.92..1.08 (independently, 2 %
        steps). "freq": 80 bands (~1/11 octave) 80 Hz..10 kHz, 1024-point frames every 5 ms
        (partials, contours, material). "time": 32 bands 100 Hz..10 kHz, 256-point frames every
        2.5 ms (flams, double taps, rhythm, attacks). Jittered copies of one take (runtime-style pitch/gain/time jitter, or a
        re-seeded noise layer under the same envelope) land near 1; structurally different
        takes (other transients, partials, timing, length) land well below.
  xc  = peak normalised waveform cross-correlation (catches sample-level copies).
A pair FAILs when sim >= SIM_FAIL or xc >= XC_FAIL (calibration notes in tools/sfx/README.md).

FAIL rules (exit code 1): clipped samples, |DC| > 0.01, first sample above -40 dBFS, last
sample above -50 dBFS or last 2 ms above -36 dBFS, leading silence > 40 ms or trailing silence
> 80 ms (below -60 dBFS) -- loops (*loop* names, beds/ambience/loops dirs, --loop) get a seam
check instead -- not mono 16-bit with a 44-byte header, silent file, family loudness
outlier (> 2 dB from the family median), spread > --max-spread, near-identical pair, fewer
than --min-takes takes. Problems of files that git already tracks (team recordings, older
generators) are reported as WARN unless --strict, since those files must not be changed;
a loudness outlier or a near-identical pair that involves a new take is always a FAIL.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal as ss
from scipy.ndimage import maximum_filter1d, uniform_filter1d

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402

SIM_FAIL = 0.90          # calibrated on the existing assets, see README "QA similarity calibration"
XC_FAIL = 0.95           # literal (time-shifted, re-levelled) copies
OUTLIER_DB = 2.0
MAX_SPREAD_DB = 3.0
FEAT_SR = 22050
SCALES = (0.92, 0.94, 0.96, 0.98, 1.0, 1.02, 1.04, 1.06, 1.08)    # time-scale search
PITCHES = (0.92, 0.94, 0.96, 0.98, 1.0, 1.02, 1.04, 1.06, 1.08)   # pitch search (independent)
LAG_MS = 30.0                                                       # lag search after onset alignment


class Spec:
    """One analysis resolution: log band-energy map over [fmin, fmax], range_db under the peak."""

    def __init__(self, name, nfft, hop, bands, fmin, fmax, range_db, smooth):
        self.name, self.nfft, self.hop, self.bands = name, nfft, hop, bands
        self.range_db, self.smooth = range_db, smooth
        freqs = np.fft.rfftfreq(nfft, 1.0 / FEAT_SR)
        c = np.geomspace(fmin, fmax, bands)
        lo = np.concatenate([[c[0] / (c[1] / c[0])], c[:-1]])
        hi = np.concatenate([c[1:], [c[-1] * (c[-1] / c[-2])]])
        W = np.zeros((bands, freqs.size))
        for k in range(bands):
            W[k] = np.clip(np.minimum((freqs - lo[k]) / (c[k] - lo[k]), (hi[k] - freqs) / (hi[k] - c[k])), 0, None)
            if W[k].sum() == 0:      # band narrower than one FFT bin: take the nearest bin
                W[k, int(np.argmin(np.abs(freqs - c[k])))] = 1.0
        self.W = W / (W.sum(axis=1, keepdims=True) + 1e-12)
        band_oct = math.log2(fmax / fmin) / (bands - 1)
        self.shifts = tuple(math.log2(p) / band_oct for p in PITCHES)
        n = int(round(LAG_MS / 1000.0 * FEAT_SR / hop))
        self.lags = range(-n, n + 1)


# Fine frequency (46 ms frames, ~1/11 octave bands): partials, pitch contours, materials.
# Fine time (12 ms frames, ~1/4.6 octave bands): flams, double taps, rhythm, attack shapes.
# A pair is near-identical only when it matches at both resolutions (sim = the lower score).
SPECS = (Spec("freq", 1024, 110, 80, 80.0, 10000.0, 40.0, 3),
         Spec("time", 256, 55, 32, 100.0, 10000.0, 40.0, 3))
TAKE_RE = re.compile(r"^(.*?)_(\d+)$")


# --------------------------------------------------------------------------- git
_REPOS: dict = {}


def tracked_set(paths) -> set:
    """Resolved paths that git tracks, for every repo the inputs live in."""
    out = set()
    roots = set()
    for p in paths:
        d = p.parent
        if d in _REPOS:
            roots.add(_REPOS[d])
            continue
        try:
            r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(d), capture_output=True, text=True)
            root = Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else None
        except OSError:
            root = None
        _REPOS[d] = root
        roots.add(root)
    for root in roots:
        if root is None:
            continue
        r = subprocess.run(["git", "ls-files", "-z", "--", "*.wav"], cwd=str(root), capture_output=True)
        for rel in r.stdout.decode("utf-8", "replace").split("\0"):
            if rel:
                out.add((root / rel).resolve())
    return out


# --------------------------------------------------------------------------- features
def band_map(x, sr, spec: Spec):
    """(frames, bands) log energy, floored range_db under its own peak, 0..range_db."""
    a = L.resample(x, sr, FEAT_SR) if sr != FEAT_SR else np.asarray(x, float)
    a = np.concatenate([np.zeros(spec.nfft // 2), a, np.zeros(spec.nfft)])
    n = max(1, 1 + (a.size - spec.nfft) // spec.hop)
    idx = np.arange(spec.nfft)[None, :] + spec.hop * np.arange(n)[:, None]
    P = np.abs(np.fft.rfft(a[idx] * np.hanning(spec.nfft)[None, :], axis=1)) ** 2
    E = 10 * np.log10(P @ spec.W.T + 1e-14)
    if spec.smooth > 1:
        E = uniform_filter1d(E, spec.smooth, axis=0)
    return np.clip(E - (float(E.max()) - spec.range_db), 0, None)


def active_span(F, spec: Spec):
    """Onset (first frame within 20 dB of the peak) .. last frame above 16 % of the range."""
    m = F.max(axis=1)
    on = int(np.argmax(m > spec.range_db - 20))
    alive = np.nonzero(m > spec.range_db * 0.16)[0]
    end = int(alive[-1]) + 1 if alive.size else F.shape[0]
    return on, max(end, on + 1)


def features(x, sr) -> dict:
    """Similarity features of one take: the active part of each SPECS map + a 150 Hz high-passed
    22.05 kHz waveform for the cross-correlation."""
    maps = {}
    for spec in SPECS:
        F = band_map(x, sr, spec)
        on, end = active_span(F, spec)
        maps[spec.name] = F[on:end]
    xh = L.resample(x, sr, FEAT_SR) if sr != FEAT_SR else np.asarray(x, float)
    return {"maps": maps, "hp": ss.sosfilt(ss.butter(2, 150, "high", fs=FEAT_SR, output="sos"), xh)}


def _warp(F, scale, shift):
    T, K = F.shape
    if scale != 1.0:
        nt = max(1, int(round(T * scale)))
        src = np.linspace(0, T - 1, nt)
        i0 = np.floor(src).astype(int)
        i1 = np.minimum(i0 + 1, T - 1)
        f = (src - i0)[:, None]
        F = F[i0] * (1 - f) + F[i1] * f
    if shift:
        b = np.arange(K) - shift
        b0 = np.clip(np.floor(b).astype(int), 0, K - 1)
        b1 = np.clip(b0 + 1, 0, K - 1)
        f = (b - np.floor(b))[None, :]
        G = F[:, b0] * (1 - f) + F[:, b1] * f
        G[:, (b < 0) | (b > K - 1)] = 0.0
        F = G
    return F


def _pearson(a, b):
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    d = math.sqrt(float(a @ a) * float(b @ b))
    return float(a @ b) / d if d > 1e-9 else 0.0


def _best_lag(A, B, lags):
    """Max Pearson of A and B (zero-padded to their union) over lags; B starts `lag` frames
    after A's onset (negative lag cuts B's head). Uses running sums, no padded copies."""
    Ta, K = A.shape
    SA, SA2 = float(A.sum()), float((A * A).sum())
    cs = np.concatenate([[0.0], np.cumsum(B.sum(axis=1))])
    cs2 = np.concatenate([[0.0], np.cumsum((B * B).sum(axis=1))])
    best = -1.0
    for lag in lags:
        if lag >= 0:
            Tb, cut = B.shape[0], 0
            e = min(Ta, lag + Tb)
            dot = float(np.einsum("ij,ij->", A[lag:e], B[:max(0, e - lag)])) if e > lag else 0.0
            T = max(Ta, lag + Tb)
        else:
            cut = min(-lag, B.shape[0] - 1)
            Tb = B.shape[0] - cut
            e = min(Ta, Tb)
            dot = float(np.einsum("ij,ij->", A[:e], B[cut:cut + e]))
            T = max(Ta, Tb)
        SB = float(cs[-1] - cs[cut])
        SB2 = float(cs2[-1] - cs2[cut])
        N = float(T * K)
        va = SA2 - SA * SA / N
        vb = SB2 - SB * SB / N
        if va <= 1e-9 or vb <= 1e-9:
            continue
        best = max(best, (dot - SA * SB / N) / math.sqrt(va * vb))
    return best


def similarity_parts(fa, fb) -> dict:
    """Per resolution: best map correlation over lag x time scale x pitch shift."""
    out = {}
    for spec in SPECS:
        A, B0 = fa["maps"][spec.name], fb["maps"][spec.name]
        best = -1.0
        for scale in SCALES:
            Bt = _warp(B0, scale, 0.0)
            for shift in spec.shifts:
                best = max(best, _best_lag(A, _warp(Bt, 1.0, shift) if shift else Bt, spec.lags))
        out[spec.name] = best
    return out


def similarity(fa, fb):
    """Near-identity score: the lower of the per-resolution scores."""
    return min(similarity_parts(fa, fb).values())


def xcorr(fa, fb):
    a, b = fa["hp"], fb["hp"]
    na, nb = math.sqrt(float(a @ a)), math.sqrt(float(b @ b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.max(np.abs(ss.fftconvolve(a, b[::-1])))) / (na * nb)


# --------------------------------------------------------------------------- per file
LOOP_DIRS = ("beds", "ambience", "loops")


def is_loop(path: Path) -> bool:
    """Loops keep their edges: named *loop*, or living in a beds/ambience/loops directory."""
    return "loop" in path.stem.lower() or path.parent.name.lower() in LOOP_DIRS


def analyse(path: Path, tracked: bool, loop: bool | None = None) -> dict:
    loop = is_loop(path) if loop is None else loop
    d = {"path": str(path), "name": path.stem, "dir": path.parent.name, "tracked": tracked, "loop": loop, "problems": []}
    try:
        info = L.wav_info(path)
        x, sr = L.read_wav(path)
    except Exception as e:  # noqa: BLE001
        d["problems"].append("unreadable: %s" % e)
        return d
    d.update(sr=sr, channels=info["channels"], bits=info["bits"], header=info["data_offset"])
    n = x.size
    d["seconds"] = round(n / sr, 4) if sr else 0.0
    if n == 0:
        d["problems"].append("empty")
        return d
    pk = float(np.max(np.abs(x)))
    d["peak_db"] = round(L.db(pk), 2)
    d["st_db"] = round(L.st_rms_peak_db(x, sr), 2)
    d["dc"] = round(float(np.mean(x)), 5)
    if info["tag"] == 1 and info["bits"] == 16:
        raw = np.round(x * 32768.0) if info["channels"] == 1 else None
        d["clipped"] = int(np.sum((raw >= 32767) | (raw <= -32768))) if raw is not None else int(np.sum(np.abs(x) >= 0.9999))
    else:
        d["clipped"] = int(np.sum(np.abs(x) >= 0.9999))
    k = max(1, L.secs(0.002, sr))
    d["start_db"] = round(L.db(np.max(np.abs(x[:k]))), 1)
    d["end_db"] = round(L.db(np.max(np.abs(x[-k:]))), 1)
    d["first_db"] = round(L.db(x[0]), 1)
    d["last_db"] = round(L.db(x[-1]), 1)
    env = maximum_filter1d(np.abs(x), max(1, L.secs(0.005, sr)))
    loud = np.nonzero(env > L.undb(L.SILENCE_DB))[0]
    d["lead_ms"] = round(1000 * (loud[0] if loud.size else n) / sr, 1)
    d["tail_ms"] = round(1000 * (n - 1 - loud[-1] if loud.size else n) / sr, 1)
    spec = np.abs(np.fft.rfft(x * np.hanning(n))) ** 2 if n > 8 else np.zeros(2)
    f = np.fft.rfftfreq(max(n, 2), 1.0 / sr)[: spec.size]
    d["centroid_hz"] = round(float((spec * f).sum() / (spec.sum() + 1e-18)), 0)
    p = d["problems"]
    if info["channels"] != 1:
        p.append("not mono (%d ch)" % info["channels"])
    if info["bits"] != 16 or info["tag"] != 1:
        p.append("not 16-bit PCM")
    if info["data_offset"] != 44:
        p.append("header %d bytes (want canonical 44)" % info["data_offset"])
    if pk < L.undb(-40):
        p.append("silent (peak %.1f dBFS)" % L.db(pk))
    if d["clipped"]:
        p.append("clipped %d samples" % d["clipped"])
    if abs(d["dc"]) > 0.01:
        p.append("DC %.4f" % d["dc"])
    if loop:
        # the wrap must continue the waveform like any other point: second difference across
        # the seam vs the file's own p99
        if n > 8:
            d2 = float(np.percentile(np.abs(x[2:] - 2 * x[1:-1] + x[:-2]), 99))
            seam = max(abs(x[0] - 2 * x[-1] + x[-2]), abs(x[1] - 2 * x[0] + x[-1]))
            d["seam"] = round(float(seam), 5)
            if seam > 4 * d2 + 1e-3:
                p.append("loop seam break %.4f (p99 2nd diff %.4f)" % (seam, d2))

    else:
        if abs(x[0]) > L.undb(-40):
            p.append("click at start (first sample %.1f dBFS)" % d["first_db"])
        if abs(x[-1]) > L.undb(-50) or d["end_db"] > -36:
            p.append("click at end (last 2 ms %.1f dBFS)" % d["end_db"])
        if d["lead_ms"] > 40:
            p.append("leading silence %.0f ms" % d["lead_ms"])
        if d["tail_ms"] > 80:
            p.append("trailing silence %.0f ms" % d["tail_ms"])
    d["_feat"] = features(x, sr)
    return d


# --------------------------------------------------------------------------- grouping
def family_key(path: Path, mode: str) -> str:
    if mode == "none":
        return "%s/%s" % (path.parent.name, path.stem)
    if mode == "dir":
        return "%s/*" % path.parent.name
    m = TAKE_RE.match(path.stem)
    return "%s/%s" % (path.parent.name, m.group(1) if m else path.stem)


def collect(inputs) -> list:
    files = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(p.glob("*.wav"))
        elif any(c in item for c in "*?["):
            files += sorted(Path(q) for q in glob.glob(item, recursive=True) if q.lower().endswith(".wav"))
        elif p.is_file():
            files.append(p)
        else:
            print("sfx_qa: no such file or dir: %s" % item, file=sys.stderr)
    seen, out = set(), []
    for f in files:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _take_no(name):
    m = TAKE_RE.match(name)
    return int(m.group(2)) if m else 0


def evaluate(files, mode="auto", min_takes=0, max_spread=MAX_SPREAD_DB, sim_fail=SIM_FAIL, xc_fail=XC_FAIL,
             strict=False, loop=None):
    tracked = tracked_set(files)
    rows = [analyse(f, f in tracked, loop) for f in files]
    fams: dict = {}
    for r in rows:
        fams.setdefault(family_key(Path(r["path"]), mode), []).append(r)
    families, fails, warns = [], [], []

    def flag(level_fail, msg):
        (fails if level_fail else warns).append(msg)

    for r in rows:
        for prob in r["problems"]:
            flag(strict or not r["tracked"], "%s/%s: %s" % (r["dir"], r["name"], prob))
    for key, members in sorted(fams.items()):
        members.sort(key=lambda r: (_take_no(r["name"]), r["name"]))
        ok = [m for m in members if "_feat" in m]
        st = [m["st_db"] for m in ok]
        fam = {"family": key, "count": len(members), "files": [m["name"] for m in members], "pairs": [], "fails": []}
        if st:
            med = float(np.median(st))
            fam.update(st_median=round(med, 2), spread=round(max(st) - min(st), 2),
                       dur_min=min(m["seconds"] for m in ok), dur_max=max(m["seconds"] for m in ok))
            if len(ok) > 1:
                for m in ok:
                    if abs(m["st_db"] - med) > OUTLIER_DB:
                        msg = "%s: %s loudness %.1f dB vs family median %.1f" % (key, m["name"], m["st_db"], med)
                        fam["fails"].append(msg)
                        flag(True, msg)
                if fam["spread"] > max_spread:
                    new = any(not m["tracked"] for m in ok)
                    msg = "%s: loudness spread %.1f dB > %.1f" % (key, fam["spread"], max_spread)
                    fam["fails"].append(msg)
                    flag(strict or new, msg)
        if min_takes and len(members) < min_takes:
            msg = "%s: %d takes < --min-takes %d" % (key, len(members), min_takes)
            fam["fails"].append(msg)
            flag(True, msg)
        best = {}
        for i in range(len(ok)):
            for j in range(i + 1, len(ok)):
                a, b = ok[i], ok[j]
                parts = similarity_parts(a["_feat"], b["_feat"])
                s = min(parts.values())
                c = xcorr(a["_feat"], b["_feat"])
                near = s >= sim_fail or c >= xc_fail
                fam["pairs"].append([a["name"], b["name"], round(s, 3), round(c, 3), near,
                                     {k: round(v, 3) for k, v in parts.items()}])
                for u, v in ((a, b), (b, a)):
                    if s > best.get(u["name"], (-2, ""))[0]:
                        best[u["name"]] = (s, v["name"])
                if near:
                    msg = "%s: %s ~ %s near-identical (sim %.3f = min(freq %.3f, time %.3f), xc %.3f)" % (
                        key, a["name"], b["name"], s, parts["freq"], parts["time"], c)
                    fam["fails"].append(msg)
                    flag(strict or not (a["tracked"] and b["tracked"]), msg)
        for m in ok:
            if m["name"] in best:
                m["max_sim"], m["max_sim_with"] = round(best[m["name"]][0], 3), best[m["name"]][1]
        fam["max_sim"] = round(max((p[2] for p in fam["pairs"]), default=0.0), 3)
        fam["max_xc"] = round(max((p[3] for p in fam["pairs"]), default=0.0), 3)
        families.append(fam)
    return rows, families, fails, warns


# --------------------------------------------------------------------------- output
def print_report(rows, families, fails, warns, quiet=False):
    by = {r["name"] + "|" + r["dir"]: r for r in rows}
    print("%-34s %3s %13s %7s %6s %6s %6s  %s" % ("family", "n", "dur s", "st med", "spread", "maxsim", "maxxc", "status"))
    for fam in families:
        status = "FAIL" if any(m in fails for m in fam["fails"]) else ("warn" if fam["fails"] else "ok")
        dur = "%.2f-%.2f" % (fam.get("dur_min", 0), fam.get("dur_max", 0))
        print("%-34s %3d %13s %7.1f %6.2f %6.3f %6.3f  %s" % (fam["family"][:34], fam["count"], dur, fam.get("st_median", float("nan")),
                                                         fam.get("spread", 0.0), fam["max_sim"], fam["max_xc"], status))
        if quiet:
            continue
        d = fam["family"].split("/")[0]
        for name in fam["files"]:
            r = by.get(name + "|" + d)
            if not r or "seconds" not in r or "st_db" not in r:
                continue
            print("    %-28s %5.3fs pk %6.1f st %6.1f dc %+.4f clip %d edge %5.0f/%5.0f lead %3.0f tail %3.0f cen %5.0f%s%s" % (
                r["name"][:28], r["seconds"], r["peak_db"], r["st_db"], r["dc"], r["clipped"], r["start_db"], r["end_db"],
                r["lead_ms"], r["tail_ms"], r["centroid_hz"],
                ("  sim %.2f~%s" % (r["max_sim"], r["max_sim_with"])) if "max_sim" in r else "",
                "  [git]" if r["tracked"] else ""))
    if warns:
        print("\nWARN (%d, files already in git):" % len(warns))
        for w in warns[:200]:
            print("  " + w)
    print("\nFAIL (%d):" % len(fails))
    for f in fails[:400]:
        print("  " + f)
    print("SFX_QA %s files=%d families=%d fails=%d warns=%d" % ("PASS" if not fails else "FAIL", len(rows), len(families), len(fails), len(warns)))


_LUT_ANCHORS = [(0.0, (8, 6, 20)), (0.25, (60, 15, 110)), (0.5, (170, 45, 105)), (0.75, (245, 125, 60)), (1.0, (252, 245, 180))]


def _lut():
    xs = np.linspace(0, 1, 256)
    ax = [a for a, _ in _LUT_ANCHORS]
    return np.stack([np.interp(xs, ax, [c[k] for _, c in _LUT_ANCHORS]) for k in range(3)], axis=1).astype(np.uint8)


def draw_sheet(rows, families, fails, out: Path, max_s=None, sim_fail=SIM_FAIL):
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default()
    lut = _lut()
    by = {r["name"] + "|" + r["dir"]: r for r in rows}
    durs = [r.get("seconds", 0) for r in rows if "seconds" in r]
    span = min(max(durs or [1.0]), max_s or 3.0)
    W, LABEL, ROW, HEAD = 1400, 360, 58, 20
    px_s = (W - LABEL - 10) / max(span, 0.05)
    height = 10 + sum(HEAD + ROW * f["count"] + 6 for f in families)
    img = Image.new("RGB", (W, max(height, 40)), (24, 24, 30))
    dr = ImageDraw.Draw(img)
    y = 6
    for fam in families:
        bad = any(m in fails for m in fam["fails"])
        dr.text((8, y + 4), "%s  n=%d  spread %.1f dB  max sim %.2f  max xc %.2f%s" % (
            fam["family"], fam["count"], fam.get("spread", 0), fam["max_sim"], fam["max_xc"], "  FAIL" if bad else ""),
            fill=(255, 110, 110) if bad else (200, 220, 255), font=font)
        y += HEAD
        d = fam["family"].split("/")[0]
        for name in fam["files"]:
            r = by.get(name + "|" + d)
            if r is None or "_feat" not in r:
                y += ROW
                continue
            x, sr = L.read_wav(r["path"])
            S = _sheet_spec(x, sr, ROW - 6)
            cols = max(1, int(round(r["seconds"] * px_s)))
            cols = min(cols, W - LABEL - 10)
            im = Image.fromarray(lut[np.clip((S * 255).astype(int), 0, 255)][::-1])
            im = im.resize((cols, ROW - 6), Image.BILINEAR)
            img.paste(im, (LABEL, y + 2))
            red = any(r["name"] in m for m in fam["fails"]) or (r["problems"] and not r["tracked"])
            dr.text((8, y + 4), r["name"][:44] + ("  [git]" if r["tracked"] else ""), fill=(255, 120, 120) if red else (230, 230, 230), font=font)
            dr.text((8, y + 18), "%.3fs  st %.1f  pk %.1f  cen %.0f" % (r["seconds"], r["st_db"], r["peak_db"], r["centroid_hz"]),
                    fill=(170, 170, 170), font=font)
            if "max_sim" in r:
                dr.text((8, y + 32), "max sim %.2f vs %s" % (r["max_sim"], r["max_sim_with"][-14:]),
                        fill=(255, 120, 120) if r["max_sim"] >= sim_fail else (150, 190, 150), font=font)
            y += ROW
        y += 6
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def _sheet_spec(x, sr, rows_px):
    """Log-frequency spectrogram 60 Hz..min(11 kHz, nyq), 0..1 over 60 dB, frames 2.5 ms."""
    a = L.resample(x, sr, FEAT_SR) if sr != FEAT_SR else x
    nfft, hop = 512, 55
    a = np.concatenate([np.zeros(nfft // 2), a, np.zeros(nfft)])
    n = max(1, 1 + (a.size - nfft) // hop)
    idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
    P = np.abs(np.fft.rfft(a[idx] * np.hanning(nfft)[None, :], axis=1)) ** 2
    f = np.fft.rfftfreq(nfft, 1.0 / FEAT_SR)
    edges = np.geomspace(60, 10800, rows_px + 1)
    S = np.stack([P[:, (f >= edges[k]) & (f < edges[k + 1])].mean(axis=1) if np.any((f >= edges[k]) & (f < edges[k + 1]))
                  else P[:, int(np.argmin(np.abs(f - edges[k])))] for k in range(rows_px)], axis=1)
    S = 10 * np.log10(S + 1e-14)
    S = np.clip((S - (S.max() - 60)) / 60, 0, 1)
    return S.T


def _jsonable(rows, families, fails, warns, args):
    clean = []
    for r in rows:
        clean.append({k: v for k, v in r.items() if not k.startswith("_")})
    return {"thresholds": {"sim_fail": args.sim_fail, "xc_fail": args.xc_fail, "outlier_db": OUTLIER_DB,
                           "max_spread_db": args.max_spread},
            "files": clean, "families": families, "fails": fails, "warns": warns}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="QA for sound take families (levels, clicks, near-identical takes)")
    ap.add_argument("inputs", nargs="+", help="directories, globs or wav files")
    ap.add_argument("--group", default="auto", choices=["auto", "dir", "none"])
    ap.add_argument("--sheet", help="write a spectrogram contact sheet PNG")
    ap.add_argument("--json", help="write the full report as JSON")
    ap.add_argument("--min-takes", type=int, default=0, help="FAIL families with fewer takes")
    ap.add_argument("--max-spread", type=float, default=MAX_SPREAD_DB, help="max family loudness spread (dB)")
    ap.add_argument("--sim-fail", type=float, default=SIM_FAIL, help="near-identical band-map similarity")
    ap.add_argument("--xc-fail", type=float, default=XC_FAIL, help="near-identical waveform correlation")
    ap.add_argument("--strict", action="store_true", help="problems of git-tracked files FAIL too")
    ap.add_argument("--quiet", action="store_true", help="family table and FAIL list only")
    ap.add_argument("--loop", action="store_true", help="treat every input as a loop (seam check instead of "
                    "fades/silence); *loop* names and beds/ambience/loops dirs are loops anyway")
    args = ap.parse_args(argv)
    files = collect(args.inputs)
    if not files:
        print("sfx_qa: no wav files", file=sys.stderr)
        return 2
    rows, families, fails, warns = evaluate(files, args.group, args.min_takes, args.max_spread, args.sim_fail,
                                            args.xc_fail, args.strict, True if args.loop else None)
    print_report(rows, families, fails, warns, args.quiet)
    if args.sheet:
        print("sheet:", draw_sheet(rows, families, fails, Path(args.sheet), sim_fail=args.sim_fail))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(_jsonable(rows, families, fails, warns, args), indent=1), encoding="utf-8")
        print("json:", args.json)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
