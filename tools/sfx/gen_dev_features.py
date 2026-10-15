"""Sounds for the post-0.11.8 dev features (docs/sound/DEV_FEATURE_SFX_KO.md): farm growth stages,
shop register, residents moving in/out, quest-board pins, sending letters, campfire buffs.

Writes mono 16-bit WAVs (each family loudness-matched to a sibling that already exists):
  life/sprout_<n>     a seed breaking the soil: tiny crack + leaf unfurling (6)        ~ life/seed
  life/ripe_<n>       a crop ready to pick: soft glint + leaf shiver (6)              ~ life/collect -3 dB
  life/untill_<n>     a plot filled back in: dirt pats + smoothing (4)                ~ life/hoe
  core/register_<n>   shop till: drawer slide, bell ding, coins (5)                  ~ core/sell
  core/build_appear_<n> a house rising on an empty lot: shimmer swell + timber knocks (3) ~ core/newday
  core/move_in_<n>    a resident moving in: warm rising jingle (3)                    ~ core/newday
  core/move_out_<n>   a resident leaving: gentle falling jingle (3)                   ~ core/newday -2 dB
  field/pin_<n>       a note pinned to the board: paper + tack press (5)              ~ field/paper
  ui/letter_send_<n>  a letter folded and sent: fold + soft whoosh (4)                ~ ui/page
  combat/buff_warm_<n>  stepping into the campfire's warmth: warm swell + glow chord (4) ~ combat/fuel
  combat/buff_heal_<n>  a heal tick by the fire: soft rising sparkle (6)              ~ life/collect -6 dB
  combat/buff_end_<n>   the buff fading: soft falling shimmer (3)                     ~ combat/fuel -4 dB

  $env:SFX_BASE='merge-version-gate'; .tools/art-venv/Scripts/python.exe tools/sfx/gen_dev_features.py [--only a,b]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SFX = ROOT / "game/assets/sfx"
SR = 22050
MAJOR = (0, 2, 4, 7, 9, 12, 14, 16)


def hz(semi, base=523.25):
    return base * 2 ** (semi / 12.0)


def tone(f, dur, rng, kind="marimba", amp=1.0):
    if kind == "bell":
        return L.fm_bell(SR, f, dur, ratio=rng.uniform(1.38, 1.44), index=rng.uniform(1.5, 2.5)) * amp
    if kind == "kalimba":
        return L.ks_pluck(SR, f, dur, rng, damping=0.995, bright=0.6) * amp
    x = L.modal(SR, f, "wood" if kind == "marimba" else "ceramic", dur=dur, rng=rng, tau=0.25 if kind == "marimba" else 0.4)
    return x * amp


def leaf(dur, rng, lo=1500, hi=6500, amp=0.4):
    n = L.secs(dur, SR)
    x = L.bp(L.noise(n, rng, "white"), SR, lo, hi)
    env = L.env_points(dur, SR, [(0, 0), (0.15, 1), (0.6, 0.5), (1.0, 0)])
    return x * env * amp * (0.7 + 0.3 * np.sin(np.linspace(0, rng.uniform(12, 30), n)))


def sprout(rng, i):
    # Six shapes: cracks then unfurl, a pop up or down, a soft double push, a long slow unfurl...
    crack_f, cracks, unfurl, pop, band = L.cycle(i, (2600, 3400, 2200), (1, 3, 2, 4, 2, 1),
                                                 (0.35, 0.55, 0.22, 0.42, 0.3, 0.6),
                                                 ("up", "none", "down", "up2", "none", "down"),
                                                 ((1200, 5000), (2500, 8000), (700, 3000)))
    out = np.zeros(L.secs(0.9, SR))
    t = 0.01
    for k in range(cracks):
        c = L.bp(L.noise(L.secs(0.012, SR), rng), SR, crack_f * 0.6, crack_f * 1.6) * L.exp_decay(0.012, SR, 0.003)
        L.place(out, c, t, SR, rng.uniform(0.4, 0.8))
        t += rng.uniform(0.02, 0.07)
    L.place(out, leaf(unfurl, rng, band[0], band[1], 0.5), t + 0.02, SR)
    if pop != "none":
        f0, f1 = (rng.uniform(450, 650), rng.uniform(1100, 1500)) if pop.startswith("up") else (rng.uniform(1300, 1600), rng.uniform(500, 650))
        L.place(out, L.chirp(SR, 0.07, f0, f1) * L.exp_decay(0.07, SR, 0.02), t, SR, 0.4)
        if pop == "up2":
            L.place(out, L.chirp(SR, 0.06, f0 * 1.3, f1 * 1.3) * L.exp_decay(0.06, SR, 0.018), t + 0.11, SR, 0.3)
    return out


def ripe(rng, i):
    # One glint, a fifth up, a three-note sparkle or a falling pair, on different timbres.
    root, tim, shape = L.cycle(i, (7, 9, 4, 12, 2, 5), ("kalimba", "glass", "marimba", "bell", "kalimba", "marimba"),
                               ("one", "fifth", "three", "pair_down", "three", "fifth"))
    out = np.zeros(L.secs(1.3, SR))
    f = hz(root, 880.0)
    notes = {"one": [(1.0, 0.0)], "fifth": [(1.0, 0.0), (1.5, 0.08)], "three": [(1.0, 0.0), (1.26, 0.07), (1.5, 0.14)],
             "pair_down": [(1.5, 0.0), (1.0, 0.1)]}[shape]
    for ratio, at in notes:
        L.place(out, tone(f * ratio, 0.8, rng, tim, 0.55), at, SR)
    L.place(out, leaf(rng.uniform(0.25, 0.5), rng, 2000, 7000, 0.4), 0.02, SR)
    return L.reverb(out, SR, room=0.3, wet=0.15, rng=rng)


def untill(rng, i):
    pats, smooth = L.cycle(i, (2, 3, 2, 4), (0.3, 0.45, 0.25, 0.38))
    out = np.zeros(L.secs(1.0, SR))
    t = 0.0
    for k in range(pats):
        thud = L.modal(SR, rng.uniform(90, 140), "stone", dur=0.12, rng=rng, tau=0.02)
        dirt = L.lp(L.noise(L.secs(0.08, SR), rng, "brown"), SR, 1800) * L.exp_decay(0.08, SR, 0.02)
        L.place(out, thud, t, SR, 0.7)
        L.place(out, dirt, t, SR, 0.5)
        t += rng.uniform(0.11, 0.17)
    L.place(out, leaf(smooth, rng, 400, 2500, 0.35), t, SR)
    return out[: L.secs(t + smooth + 0.05, SR)]


def register(rng, i):
    bell_f, coins, slide = L.cycle(i, (2093, 2349, 1976, 2637, 2217), (3, 5, 4), (True, False))
    out = np.zeros(L.secs(1.4, SR))
    t = 0.0
    if slide:
        s = L.bp(L.noise(L.secs(0.18, SR), rng), SR, 600, 3000) * L.env_points(0.18, SR, [(0, 0), (0.3, 1), (1, 0)])
        L.place(out, s, 0.0, SR, 0.35)
        L.place(out, L.modal(SR, rng.uniform(140, 180), "wood", dur=0.15, rng=rng), 0.18, SR, 0.6)
        t = 0.2
    L.place(out, tone(bell_f, 1.0, rng, "bell", 0.6), t + 0.02, SR)
    for k in range(coins):
        L.place(out, L.modal(SR, rng.uniform(2800, 4200), "metal", dur=0.18, rng=rng, tau=0.06), t + 0.12 + k * rng.uniform(0.04, 0.08), SR, 0.3)
    return L.reverb(out, SR, room=0.25, wet=0.12, rng=rng)


def build_appear(rng, i):
    dur, knocks, key = L.cycle(i, (2.4, 2.8, 2.1), (3, 4, 5), (0, 2, -3))
    n = L.secs(dur + 0.6, SR)
    out = np.zeros(n)
    sw = L.bp(L.noise(L.secs(dur, SR), rng, "pink"), SR, 800, 6000)
    sw *= L.env_points(dur, SR, [(0, 0), (0.7, 1), (0.85, 0.6), (1, 0)], power=1.5)
    L.place(out, sw, 0.0, SR, 0.35)
    for k, s in enumerate((0, 4, 7, 12, 16)):
        L.place(out, tone(hz(s + key, 659.25), 1.0, rng, "bell", 0.25), 0.25 + k * dur * 0.12, SR)
    for k in range(knocks):
        L.place(out, L.modal(SR, rng.uniform(110, 170), "wood", dur=0.2, rng=rng), dur * 0.72 + k * rng.uniform(0.09, 0.14), SR, 0.8)
    return L.reverb(out, SR, room=0.45, wet=0.22, rng=rng)


def jingle(rng, i, up=True):
    tim, key, tempo = L.cycle(i, ("marimba", "kalimba", "bell"), (0, 3, -2), (0.13, 0.16, 0.11))
    seq = [0, 4, 7, 12] if up else [12, 7, 4, 0]
    if not up:
        tempo *= 1.3
    out = np.zeros(L.secs(2.2, SR))
    for k, s in enumerate(seq):
        L.place(out, tone(hz(s + key), 1.0, rng, tim, 0.7 if k < 3 else 0.85), k * tempo, SR)
    L.place(out, tone(hz(seq[-1] + key - 12), 1.4, rng, "marimba", 0.4), len(seq) * tempo, SR)
    return L.reverb(out, SR, room=0.4, wet=0.2, rng=rng)


def pin(rng, i):
    # Paper laid on the board (short flick / long smooth / crumple), then one tack, two taps or a thumb press.
    press, paper, board, gap = L.cycle(i, ("tack", "double", "thumb", "tack", "double"), ("flick", "smooth", "crumple", "smooth", "crumple"),
                                       ((180, 230), (320, 400), (120, 150), (240, 290), (140, 170)), (0.08, 0.15, 0.1, 0.12, 0.06))
    out = np.zeros(L.secs(0.8, SR))
    if paper == "flick":
        L.place(out, leaf(0.08, rng, 2500, 8000, 0.6), 0.0, SR)
        t = 0.09
    elif paper == "smooth":
        L.place(out, leaf(0.22, rng, 800, 4000, 0.5), 0.0, SR)
        t = 0.2
    else:
        for k in range(4):
            L.place(out, leaf(0.03, rng, 1500, 7000, 0.5), k * rng.uniform(0.025, 0.04), SR)
        t = 0.16
    if press == "thumb":
        L.place(out, L.modal(SR, rng.uniform(*board), "wood", dur=0.18, rng=rng, tau=0.05), t, SR, 0.7)
        L.place(out, leaf(0.12, rng, 300, 1500, 0.3), t, SR)
    for k in range(2 if press == "double" else (1 if press == "tack" else 0)):
        L.place(out, L.modal(SR, rng.uniform(1700, 2600) * (1.3 if k else 1.0), "metal", dur=0.06, rng=rng, tau=0.015), t + k * gap, SR, 0.5)
        L.place(out, L.modal(SR, rng.uniform(*board), "wood", dur=0.12, rng=rng), t + k * gap, SR, 0.6 if k == 0 else 0.35)
    return out


def letter_send(rng, i):
    folds, rise = L.cycle(i, (2, 3, 1, 2), (True, False))
    out = np.zeros(L.secs(1.1, SR))
    t = 0.0
    for k in range(folds):
        L.place(out, leaf(0.09, rng, 2000, 8000, 0.6), t, SR)
        t += rng.uniform(0.1, 0.15)
    w = L.bp(L.noise(L.secs(0.45, SR), rng, "pink"), SR, 500, 4000) * L.env_points(0.45, SR, [(0, 0), (0.5, 1), (1, 0)])
    L.place(out, w, t, SR, 0.5)
    if rise:
        L.place(out, tone(hz(12, 880), 0.5, rng, "bell", 0.15), t + 0.3, SR)
    return out[: L.secs(t + 0.6, SR)]


def buff_warm(rng, i):
    # A warm glow: four shapes (a soft 'fwoomp' flare, a slow swell, embers crackling up, a bell-lit chord).
    chord, dur, shape = L.cycle(i, ((0, 4, 7), (0, 5, 9), (0, 3, 7), (0, 4, 9)), (1.4, 1.8, 1.2, 1.6),
                                ("flare", "swell", "embers", "bells"))
    n = L.secs(dur, SR)
    out = np.zeros(n)
    pts = {"flare": [(0, 0), (0.08, 1), (0.4, 0.4), (1, 0)], "swell": [(0, 0), (0.6, 1), (1, 0)],
           "embers": [(0, 0), (0.3, 0.5), (1, 0)], "bells": [(0, 0), (0.2, 0.4), (1, 0)]}[shape]
    sw = L.lp(L.noise(n, rng, "brown" if shape != "flare" else "pink"), SR, 900 if shape != "flare" else 2200) * L.env_points(dur, SR, pts)
    out += L.norm_peak(sw) * (0.6 if shape == "flare" else 0.35)
    for k, s in enumerate(chord):
        f = hz(s - 12, 392.0)
        pad = L.osc(SR, np.full(n, f), ((1, 1.0), (2, 0.3), (3, 0.12))) * L.env_points(dur, SR, [(0, 0), (0.3, 1), (0.8, 0.6), (1, 0)])
        out += pad * (0.08 if shape == "bells" else 0.18)
        if shape == "bells":
            L.place(out, tone(f * 2, dur, rng, "bell", 0.3), 0.05 + k * 0.12, SR)
    if shape == "embers":
        for k in range(int(rng.integers(10, 16))):
            c = L.bp(L.noise(L.secs(0.01, SR), rng), SR, 1500, 6000) * L.exp_decay(0.01, SR, 0.002)
            L.place(out, c, rng.uniform(0.05, dur * 0.8), SR, rng.uniform(0.2, 0.5))
    return L.reverb(out, SR, room=0.4, wet=0.25, rng=rng)


def buff_heal(rng, i):
    root, steps = L.cycle(i, (0, 2, 4, 5, 7, 9), (3, 4))
    out = np.zeros(L.secs(0.9, SR))
    for k in range(steps):
        L.place(out, tone(hz(MAJOR[(root // 2 + k) % len(MAJOR)] + 12, 523.25), 0.5, rng, "glass", 0.5 - 0.06 * k), k * 0.06, SR)
    L.place(out, leaf(0.4, rng, 4000, 9000, 0.12), 0.0, SR)
    return L.reverb(out, SR, room=0.3, wet=0.2, rng=rng)


def buff_end(rng, i):
    key, dur = L.cycle(i, (7, 4, 9), (1.0, 1.3, 0.9))
    out = np.zeros(L.secs(dur + 0.6, SR))
    for k, s in enumerate((12, 7, 4)):
        L.place(out, tone(hz(s + key, 523.25), 0.8, rng, "glass", 0.35), k * dur * 0.22, SR)
    w = L.lp(L.noise(L.secs(dur, SR), rng, "pink"), SR, 2500) * L.env_points(dur, SR, [(0, 0.6), (1, 0)])
    L.place(out, w, 0.0, SR, 0.15)
    return L.reverb(out, SR, room=0.35, wet=0.22, rng=rng)


# dir, event, takes, fn, reference family file, dB offset vs reference
FAMILIES = [
    ("life", "sprout", 6, sprout, "life/seed_1.wav", 0.0),
    ("life", "ripe", 6, ripe, "life/collect_1.wav", -3.0),
    ("life", "untill", 4, untill, "life/hoe_1.wav", 0.0),
    ("core", "register", 5, register, "core/sell_1.wav", 0.0),
    ("core", "build_appear", 3, build_appear, "core/newday_1.wav", 0.0),
    ("core", "move_in", 3, lambda r, i: jingle(r, i, True), "core/newday_1.wav", 0.0),
    ("core", "move_out", 3, lambda r, i: jingle(r, i, False), "core/newday_1.wav", -2.0),
    ("field", "pin", 5, pin, "field/paper.wav", 0.0),
    ("ui", "letter_send", 4, letter_send, "ui/page_1.wav", 0.0),
    ("combat", "buff_warm", 4, buff_warm, "combat/fuel_1.wav", 0.0),
    ("combat", "buff_heal", 6, buff_heal, "life/collect_1.wav", -6.0),
    ("combat", "buff_end", 3, buff_end, "combat/fuel_1.wav", -4.0),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    total = 0
    for d, event, n, fn, ref, off in FAMILIES:
        if only and event not in only:
            continue
        ref_db = L.ref_db_of(SFX / ref) + off
        meta = L.make_family(SFX / d, event, n, fn, sr=SR, ref_db=ref_db, seed_base="dev", verbose=False)
        b = sum(m["bytes"] for m in meta)
        total += b
        print("%-7s %-13s %d takes %7.1f KB  st %.1f..%.1f (ref %.1f)" % (d, event, n, b / 1024, min(m["st_db"] for m in meta),
                                                                        max(m["st_db"] for m in meta), ref_db))
    print("TOTAL %.1f KB" % (total / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
