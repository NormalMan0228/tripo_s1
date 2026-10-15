"""gen_combat: take families for survival combat, monsters and the hero's voice (tools/sfx convention).

Writes NEW takes next to the existing ones (never touches a git-tracked WAV):
  game/assets/sfx/combat/<event>_<n>.wav     swings, hits, block, dodge, critical, spawn, dissolve,
                                             player_hit, fuel, night/dawn, harvest_* (the recorded
                                             tree/stone/fiber _1 stay; _2.._12 are derived from them),
                                             whiff, equip, campfire_loop.wav, sputter, depleted_<kind>,
                                             night_warn, cold, hunger, ember, craft_<recipe>, bandage
  game/assets/sfx/hero/<event>_<n>.wav       vocal efforts and chimes
  game/assets/sfx/creatures/<species>_<event>_<n>.wav     region-neutral takes (gen_combat_creatures.py)
  game/assets/sfx/creatures/layer_<region>_<accent|bed>_<n>.wav   region colour, layered at runtime
  game/assets/sfx/creatures/step_<gait>_<n>.wav, boar_charge_<n>.wav, boar_dazed_<n>.wav

Each family is a grid of structural archetypes (L.cycle) plus small random detail, levelled to the
existing files of that kind (st-rms, sfxlib.finish). Numbering continues after the highest
git-tracked take; re-running re-renders the same files (seeded) and removes this generator's own
stale higher-numbered takes.

  .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_combat.py [--only combat,hero,creatures,layers,steps]
        [--family swing_axe,hit_flesh] [--list] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_combat_kit import (C, L, SR, SR22, SR32, S, T, V, band, bloop, breathy, buf, burst, click, ctl, debris,  # noqa: E402
                            fire, glide, high, low, modal, norm, nsweep, pk, place, pops, rel, rock, room, rustle,
                            scrape, secs, shaped, snarl, thud, tinkles, to_sr, tok, u, vocal)

COMBAT = L.SFX_ROOT / "combat"
HERO = L.SFX_ROOT / "hero"
CREAT = L.SFX_ROOT / "creatures"


@dataclass
class Fam:
    group: str              # combat | hero | creatures | layers | steps
    dir: Path
    event: str
    n: int
    fn: Callable            # fn(s, k) -> float array at SR (32 kHz); k = 0-based index inside the new takes
    sr: int = SR22
    ref: object = None      # float dB, or a list of reference paths (median), or None
    max_dur: float | None = None
    start: int | None = None
    loop: bool = False
    finish_kw: dict = field(default_factory=dict)


# =============================================================================== combat: swings
SHAPE = {
    "early": [(0, 0), (0.14, 1), (0.42, 0.45), (1, 0)],              # fast attack, long tail
    "late": [(0, 0), (0.6, 0.45), (0.8, 1), (0.9, 0.3), (1, 0)],      # slow rise, abrupt end
    "double": [(0, 0), (0.2, 0.75), (0.36, 0.1), (0.62, 1), (1, 0)],  # two humps, second bigger
    "double2": [(0, 0), (0.22, 1), (0.38, 0.15), (0.6, 0.45), (1, 0)],# two humps, first bigger
    "flutter": [(0, 0), (0.35, 1), (1, 0)],                           # tumbling (deep AM)
    "cut": [(0, 0), (0.55, 0.35), (0.75, 1), (0.8, 0.1), (1, 0)],     # swell and stop
    "whip": [(0, 0), (0.06, 1), (0.15, 0.3), (1, 0)],                 # crack-fast peak, low tail
    "ramp": [(0, 0), (0.88, 1), (0.93, 0.15), (1, 0)],                # linear build, sudden stop
}
CONTOUR = {"up": [(0, 0.0), (1, 1.0)], "down": [(0, 1.0), (1, 0.05)], "arch": [(0, 0.0), (0.5, 1.0), (1, 0.1)], "dip": [(0, 0.65), (0.42, 0.0), (1, 1.0)]}
WEAPON = {
    "axe": dict(dur=0.28, lo=240, hi=1150, bw=0.6, body=0.5, tone=0.0),
    "spear": dict(dur=0.22, lo=620, hi=2700, bw=0.42, body=0.1, tone=0.14),
    "fist": dict(dur=0.15, lo=520, hi=1850, bw=0.72, body=0.15, tone=0.0),
}
# (shape, contour, duration scale, register, extra layer, flutter Hz): one archetype per take
SWING_SPECS = [
    ("early", "down", 1.0, 1.0, "none", 0), ("late", "up", 1.1, 0.88, "grip", 0), ("double", "arch", 0.95, 1.1, "none", 0),
    ("flutter", "arch", 1.15, 0.95, "none", 18), ("cut", "up", 1.0, 1.15, "air", 0), ("whip", "up", 0.9, 0.9, "none", 0),
    ("early", "dip", 0.86, 1.2, "rattle", 0), ("late", "down", 1.16, 1.0, "whistle", 0), ("double2", "up", 1.05, 0.85, "follow", 0),
    ("double", "dip", 1.2, 0.8, "none", 0), ("early", "up", 0.95, 0.92, "feint", 0), ("ramp", "dip", 0.9, 1.05, "sleeve", 0),
]
FIST_SPECS = [
    ("early", "up", 0.8, 1.0, "jab", 0), ("cut", "arch", 1.5, 0.9, "sleeve2", 0), ("double", "up", 0.6, 1.1, "double", 0),
    ("late", "up", 1.2, 1.0, "snap", 0), ("flutter", "arch", 1.6, 0.95, "none", 16), ("double2", "arch", 1.4, 1.2, "none", 0),
    ("early", "down", 1.0, 0.7, "air", 0), ("whip", "down", 1.1, 1.05, "sleeve2", 0), ("early", "up", 0.5, 1.1, "flurry", 0),
    ("whip", "dip", 0.6, 1.25, "tail", 0), ("late", "arch", 1.6, 0.85, "scuff", 0), ("double2", "dip", 1.2, 1.0, "feint", 0),
]


def swing(weapon):
    W = WEAPON[weapon]
    specs = FIST_SPECS if weapon == "fist" else SWING_SPECS

    def fn(s, k):
        shape, cont, dsc, reg, extra, fl_hz = specs[k % len(specs)]
        dur = W["dur"] * dsc * u(s, 0.97, 1.03)
        lo, hi = W["lo"] * reg, W["hi"] * reg
        fc = [(p, lo + (hi - lo) * v) for p, v in CONTOUR[cont]]
        fl = (fl_hz * u(s, 0.92, 1.08), 0.92) if fl_hz else (0, 0)
        tone = W["tone"] * (2.4 if extra == "whistle" else 1.0)
        body = W["body"] * (2.0 if extra == "air" else 1.0)
        out = buf(dur * 2 + 0.4)
        main_at = 0.0
        if extra == "feint":           # small pre-swish, then the real swing
            place(out, pk(shaped(s, dur * 0.5, [(0, lo * 1.2), (1, hi * 0.6)], [(0, 0), (0.5, 1), (1, 0)], W["bw"])), 0.0, 0.35)
            main_at = dur * 0.55
        if extra in ("double", "flurry"):
            reps = 2 if extra == "double" else 3
            for j in range(reps):
                place(out, pk(shaped(s, dur, fc, SHAPE["early"], W["bw"], (0, 0), tone, body)), j * u(s, 0.065, 0.08), 1.0 - 0.15 * j)
        else:
            place(out, pk(shaped(s, dur, fc, SHAPE[shape], W["bw"], fl, tone, body)), main_at)
        if weapon == "fist" or extra == "sleeve":
            g = 0.3 if extra == "sleeve2" else (0.16 if weapon == "fist" else 0.12)
            m = secs(dur)
            place(out, pk(rustle(s, m, ctl(m, rel(dur, [(0, 0), (0.35, 1), (1, 0)])))), main_at, g)
        if extra == "grip":
            place(out, tok(s, u(s, 650, 900), 0.01), u(s, 0.0, 0.02), 0.18)
        if extra == "follow":
            place(out, pk(shaped(s, dur * 0.8, [(0, hi * 0.7), (1, lo)], [(0, 0), (0.3, 1), (1, 0)], W["bw"] * 1.2)), dur * 0.55, 0.35)
        if extra == "rattle":
            for j in range(3):
                place(out, tok(s, u(s, 900, 1500), 0.008), dur * (0.15 + 0.12 * j) + u(s, 0, 0.01), 0.08)
        if extra == "snap":            # cloth snaps tight at the end of the punch
            place(out, pk(burst(s, 0.03, 1500, 7000, 0.004)), main_at + dur * 0.9, 0.35)
        if extra == "jab":
            place(out, pk(burst(s, 0.025, 800, 4000, 0.004)), main_at + dur * 0.25, 0.2)
        if extra == "tail":
            place(out, pk(shaped(s, dur * 2.0, [(0, lo * 0.7), (1, lo * 0.5)], [(0, 0), (0.1, 1), (1, 0)], 0.9)), dur * 0.3, 0.35)
        if extra == "scuff":
            place(out, pk(scrape(s, 0.1, 300, 3000)), 0.0, 0.3)
        return room(s, out, 0.3, 0.05)
    return fn


HEAVY_ARCH = ["windup", "spin", "overhead", "double", "whistle", "cut"]


def swing_heavy(weapon):
    W = WEAPON[weapon]

    def fn(s, k):
        arch, reg, dsc = L.cycle(k, HEAVY_ARCH, [1.0, 0.88, 1.12, 0.94, 1.06], [1.0, 1.1, 0.9, 1.05])
        dur = W["dur"] * 1.55 * dsc
        lo, hi = W["lo"] * 0.82 * reg, W["hi"] * 0.9 * reg
        bw = W["bw"]
        out = buf(dur * 1.6 + 0.4)
        if arch == "windup":
            place(out, pk(shaped(s, dur * 0.4, [(0, lo * 1.4), (1, lo * 2.0)], [(0, 0), (0.6, 1), (1, 0)], bw, body=0.2)), 0.0, 0.3)
            place(out, pk(shaped(s, dur, [(0, lo), (0.55, hi), (1, lo * 1.2)], [(0, 0), (0.55, 1), (1, 0)], bw, tone=W["tone"], body=W["body"] * 1.6)), dur * 0.36)
        elif arch == "spin":
            place(out, pk(shaped(s, dur * 1.3, [(0, lo), (0.5, hi), (1, lo * 1.3)], [(0, 0), (0.3, 0.8), (0.65, 1), (1, 0)], bw,
                                 (u(s, 7, 10), 0.7), W["tone"], W["body"] * 1.3)), 0.0)
        elif arch == "overhead":
            place(out, pk(shaped(s, dur, [(0, hi * 1.1), (0.7, lo * 1.4), (1, lo)], [(0, 0), (0.62, 0.6), (0.82, 1), (1, 0)], bw, tone=W["tone"], body=W["body"] * 2.2)), 0.0)
            place(out, pk(thud(s, u(s, 70, 90), 0.2, 0.05, grit=0.2)), dur * 0.82, 0.25)
        elif arch == "double":
            for j, (at, g) in enumerate(((0.0, 0.8), (dur * 0.55, 1.0))):
                place(out, pk(shaped(s, dur * 0.7, [(0, lo), (0.5, hi * (1 - 0.15 * j)), (1, lo)], [(0, 0), (0.5, 1), (1, 0)], bw, tone=W["tone"], body=W["body"] * 1.4)), at, g)
        elif arch == "whistle":
            place(out, pk(shaped(s, dur * 1.2, [(0, lo), (0.18, hi), (1, hi * 0.55)], [(0, 0), (0.16, 1), (0.5, 0.45), (1, 0)], bw * 0.8,
                                 tone=max(W["tone"], 0.1) * 3.0, body=W["body"])), 0.0)
        else:  # cut: swell, stop, air thump
            place(out, pk(shaped(s, dur, [(0, lo), (0.8, hi), (1, hi)], [(0, 0), (0.6, 0.45), (0.8, 1), (0.84, 0.08), (1, 0)], bw, tone=W["tone"], body=W["body"] * 1.5)), 0.0)
            place(out, pk(burst(s, 0.1, 120, 900, 0.03)), dur * 0.8, 0.3)
        if weapon == "fist":
            m = secs(dur)
            place(out, pk(rustle(s, m, ctl(m, rel(dur, [(0, 0), (0.4, 1), (1, 0)])))), 0.02, 0.18)
        return room(s, out, 0.35, 0.06)
    return fn


# =============================================================================== combat: hits
def smack(s, lo=400, hi=2600, tau=0.012, dur=0.08):
    return pk(burst(s, dur, lo, hi, tau))


def hit_flesh(s, k):
    arch, reg = L.cycle(k, list(range(10)), [1.0, 0.87, 1.14])
    f = u(s, 105, 125) * reg * [1.5, 1.3, 0.6, 1.4, 0.8, 1.0, 1.2, 1.6, 1.15, 0.72][arch]
    out = buf(0.6)
    if arch == 0:      # wet slap: bright smack, light high thump, squelch
        place(out, smack(s, 900 * reg, 4500, 0.01, 0.06), 0.0, 1.0)
        place(out, pk(thud(s, f, 0.15, 0.03, drop=0.3, grit=0.3)), 0.0, 0.45)
        place(out, pk(bloop(s, 260 * reg, 120 * reg, 0.1, 0.6)), 0.02, 0.4)
    elif arch == 1:    # pat-pat: bright smack, darker smack, late light thump
        place(out, smack(s, 1000 * reg, 4500, 0.008, 0.05), 0.0, 0.9)
        place(out, smack(s, 400 * reg, 2000, 0.012, 0.06), u(s, 0.04, 0.05), 1.0)
        place(out, pk(thud(s, f, 0.15, 0.03, drop=0.3, grit=0.4)), 0.05, 0.4)
        m = secs(0.12)
        place(out, pk(band(s.noise(m), 1000, 4000) * ctl(m, [(0, 0), (0.01, 1), (0.12, 0)])), 0.06, 0.2)
    elif arch == 2:    # heavy body + bounce
        place(out, pk(thud(s, f, 0.45, 0.12, drop=0.35, body=1.3, grit=0.4)), 0.0)
        place(out, smack(s, 200, 1000, 0.025), 0.0, 0.4)
        place(out, pk(thud(s, f * 1.1, 0.2, 0.04, grit=0.4)), u(s, 0.09, 0.11), 0.35)
    elif arch == 3:    # slap
        place(out, smack(s, 1200 * reg, 5200, 0.007, 0.05), 0.0, 1.0)
        place(out, pk(thud(s, f, 0.16, 0.03, grit=0.3)), 0.003, 0.4)
    elif arch == 4:    # squelchy
        place(out, pk(thud(s, f, 0.25, 0.045, grit=0.5)), 0.0, 0.8)
        place(out, pk(bloop(s, 320 * reg, 140 * reg, 0.16, 0.5)), 0.012, 0.7)
    elif arch == 5:    # double thump
        for j, at in enumerate((0.0, u(s, 0.065, 0.09))):
            place(out, pk(thud(s, f * (1 - 0.08 * j), 0.22, 0.04, grit=0.6)), at, 1.0 - 0.35 * j)
            place(out, smack(s, 500, 2400, 0.01), at, 0.45 - 0.15 * j)
    elif arch == 6:    # bonk: bone-ish tok on top
        place(out, tok(s, u(s, 560, 760) * reg, 0.03), 0.0, 1.0)
        place(out, pk(thud(s, f, 0.2, 0.035, grit=0.3)), 0.002, 0.5)
    elif arch == 7:    # smack + fur rustle tail
        place(out, smack(s, 450, 3000, 0.014), 0.0, 1.0)
        place(out, pk(thud(s, f, 0.15, 0.025, grit=0.3)), 0.0, 0.4)
        m = secs(0.25)
        place(out, pk(rustle(s, m, ctl(m, [(0, 0), (0.02, 1), (0.25, 0)]))), 0.02, 0.4)
    elif arch == 8:    # punch: click + short thud
        place(out, click(s, 0.02, 2200, 8000, 0.0016), 0.0, 0.7)
        place(out, pk(thud(s, f, 0.12, 0.022, drop=0.3, grit=0.9)), 0.0, 1.0)
    else:              # oomph: low thump + air pushed out
        place(out, pk(thud(s, f, 0.3, 0.07, grit=0.4)), 0.0)
        place(out, pk(breathy(s, 0.2, [(0, 900), (0.2, 420)], [(0, 0), (0.01, 1), (0.2, 0)], 0.8)), 0.01, 0.6)
    return room(s, out, 0.3, 0.05)


def hit_stone(s, k):
    arch, size = L.cycle(k, list(range(10)), [1.0, 1.25, 0.82])
    out = buf(0.9)
    crack = lambda g=1.0: click(s, 0.05, 1500, 9000, u(s, 0.002, 0.003)) * g  # noqa: E731
    if arch == 0:
        place(out, crack(1.2), 0.0)
        place(out, pk(rock(s, 1.4 * size)), 0.0)
        place(out, debris(s, secs(0.6), 4, 0.03, 0.3, (0.3, 0.6), 0.3), 0.0)
    elif arch == 1:    # shower of chips
        place(out, crack(1.0), 0.0)
        place(out, pk(rock(s, 1.0 * size)), 0.0, 0.8)
        place(out, debris(s, secs(0.8), 14, 0.02, 0.55, (0.25, 0.6), 0.45, 1.2), 0.0)
    elif arch == 2:    # dull thunk
        place(out, pk(thud(s, u(s, 85, 105), 0.25, 0.05, grit=0.8)), 0.0)
        place(out, pk(rock(s, 1.7 * size)), 0.0, 0.7)
        place(out, debris(s, secs(0.5), 3, 0.05, 0.25, (0.3, 0.5), 0.25), 0.0)
    elif arch == 3:    # double crack
        for j, at in enumerate((0.0, u(s, 0.035, 0.055))):
            place(out, crack(1.0 - 0.3 * j), at)
            place(out, pk(rock(s, (1.2 - 0.3 * j) * size)), at, 1.0 - 0.3 * j)
    elif arch == 4:    # spark ting
        place(out, crack(1.1), 0.0)
        place(out, pk(rock(s, 1.2 * size)), 0.0, 0.8)
        f = u(s, 2600, 3400)
        place(out, pk(modal([f, f * 1.52, f * 2.31], [0.07, 0.04, 0.02], [1, 0.5, 0.3], 0.3, s.rng)), 0.003, 0.35)
    elif arch == 5:    # crack + crumble tail
        place(out, crack(1.1), 0.0)
        place(out, pk(rock(s, 1.3 * size)), 0.0, 0.9)
        place(out, pk(scrape(s, 0.32, 150, 2200)), 0.05, 0.35)
    elif arch == 6:    # bright tick + delayed shower
        place(out, crack(0.9), 0.0)
        place(out, pk(rock(s, 0.7 * size)), 0.0, 0.8)
        place(out, debris(s, secs(0.8), 9, 0.12, 0.35, (0.3, 0.55), 0.4, 0.8), 0.0)
    elif arch == 7:    # gravel slide
        place(out, crack(1.0), 0.0)
        place(out, pk(rock(s, 1.1 * size)), 0.0, 0.8)
        m = secs(0.3)
        place(out, pops(s, m, 260, 900, 6000, ctl(m, [(0, 1), (0.3, 0)]), (0.001, 0.004)), 0.02, 0.6)
    elif arch == 8:    # thud + three ticks
        place(out, pk(thud(s, u(s, 110, 130), 0.18, 0.035, grit=0.6)), 0.0, 0.8)
        for j in range(3):
            place(out, pk(rock(s, u(s, 0.4, 0.6))), 0.02 + 0.055 * j + u(s, 0, 0.01), 0.7 - 0.15 * j)
    else:              # ringing stone
        place(out, crack(1.0), 0.0)
        f = u(s, 900, 1300) / size
        place(out, pk(modal([f, f * 1.47, f * 2.09, f * 2.56], [0.09, 0.06, 0.04, 0.03], [1, 0.7, 0.5, 0.3], 0.5, s.rng)), 0.0, 0.8)
    return room(s, out, 0.5, 0.09)


def wood_modal(s, f, tau=0.05):
    return pk(np.asarray(modal([f, f * 2.3, f * 4.1, f * 6.2], [tau, tau * 0.6, tau * 0.36, tau * 0.2], [1, 0.6, 0.35, 0.2], max(0.3, tau * 7), s.rng)))


def hit_wood(s, k):
    arch, reg = L.cycle(k, list(range(10)), [1.0, 1.15, 0.87])
    f = u(s, 290, 330) * reg
    out = buf(0.7)
    if arch == 0:
        place(out, wood_modal(s, f), 0.0)
        place(out, click(s, 0.04, 900, 6000, 0.003), 0.0, 1.0)
    elif arch == 1:    # low hollow
        place(out, wood_modal(s, f * 0.62, 0.09), 0.0)
        place(out, pk(thud(s, 110, 0.2, 0.05, grit=0.4)), 0.0, 0.6)
    elif arch == 2:    # high knock + splinters
        place(out, wood_modal(s, f * 1.4, 0.035), 0.0)
        m = secs(0.2)
        place(out, pops(s, m, 140, 1500, 7000, ctl(m, [(0, 1), (0.2, 0)]), (0.001, 0.003)), 0.01, 0.8)
    elif arch == 3:    # double knock
        place(out, wood_modal(s, f), 0.0)
        place(out, wood_modal(s, f * 1.09, 0.04), u(s, 0.055, 0.075), 0.6)
    elif arch == 4:    # bark chips flying
        place(out, wood_modal(s, f * 1.3, 0.03), 0.0, 0.8)
        for j in range(6):
            place(out, tok(s, u(s, 1400, 2600), 0.008), 0.03 + 0.035 * j + u(s, 0, 0.02), u(s, 0.25, 0.45))
    elif arch == 5:    # hollow ring
        place(out, wood_modal(s, f * 0.8, 0.12), 0.0)
        place(out, click(s, 0.04, 700, 4000, 0.004), 0.0, 0.6)
    elif arch == 6:    # dull thud
        place(out, pk(thud(s, u(s, 120, 145), 0.25, 0.05, grit=0.7)), 0.0)
        place(out, wood_modal(s, f, 0.025), 0.0, 0.4)
    elif arch == 7:    # leaves shiver
        place(out, wood_modal(s, f), 0.0, 0.9)
        m = secs(0.35)
        place(out, pk(rustle(s, m, ctl(m, [(0, 0), (0.05, 1), (0.35, 0)]))), 0.03, 0.3)
    elif arch == 8:    # crack-splinter
        place(out, click(s, 0.05, 1500, 9000, 0.002), 0.0, 1.0)
        place(out, wood_modal(s, f * 1.2, 0.03), 0.0, 0.7)
        place(out, pk(V.crackle(s, 0.16, 120, 0.02)), 0.015, 0.5)
    else:              # knock + creak
        place(out, wood_modal(s, f), 0.0)
        place(out, pk(V.creak(s, 0.22, u(s, 160, 200), u(s, 120, 140), q=6, rough=0.2, swell=0.02, release=0.1)), 0.04, 0.3)
    return room(s, out, 0.4, 0.08)


SPIRIT_IVL = [(1.0, 1.5), (1.0, 1.335), (1.0, 1.26), (1.0, 2.0), (1.0, 1.19)]


def hit_spirit(s, k):
    ivl, sweep_up, mat = L.cycle(k, SPIRIT_IVL, [True, False], ["bell", "glass", "fm"])
    out = buf(1.2)
    n = secs(0.25)
    sw = [(0, 1200), (0.25, 6000)] if sweep_up else [(0, 6500), (0.25, 1300)]
    place(out, pk(nsweep(s, n, ctl(n, sw), 0.6) * ctl(n, [(0, 0), (0.01, 1), (0.25, 0)])), 0.0, 0.6)
    f = u(s, 1050, 1400)
    for j, r in enumerate(ivl):
        at = 0.0 if mat != "glass" else 0.045 * j
        if mat == "bell":
            x = C.bell(s, f * r, 0.7, 0.35, 0.8)
        elif mat == "glass":
            x = L.modal(SR, f * r, "glass", dur=0.6, rng=s.rng)
        else:
            x = L.fm_bell(SR, f * r, 0.7, ratio=1.4 + 0.07 * j, index=2.5, rng=s.rng)
        place(out, pk(x), at + 0.005, 0.45 - 0.12 * j)
    m = secs(0.6)
    place(out, tinkles(s, m, [30, 14, 50][k % 3], 3500, 9000, ctl(m, [(0, 1), (0.6, 0)])), 0.02, 0.7)
    place(out, pk(thud(s, 150, 0.15, 0.03, grit=0.3)), 0.0, 0.35)
    return room(s, out, 0.8, 0.14, 8000)


def block(s, k):
    arch, reg = L.cycle(k, list(range(6)), [1.0, 1.12, 0.9, 1.06])
    f = u(s, 470, 560) * reg
    knock = lambda ff, g=1.0: pk(np.asarray(modal([ff, ff * 2.58, ff * 4.31, ff * 6.1], [0.09, 0.05, 0.03, 0.02], [1, 0.6, 0.4, 0.25], 0.35, s.rng))  # noqa: E731
                                 + click(s, 0.04, 1500, 8000, 0.002)) * g
    out = buf(0.9)
    if arch == 0:      # knock + long scrape
        place(out, knock(f), 0.0)
        place(out, pk(scrape(s, 0.28, 900, 6000)), 0.03, 0.35)
    elif arch == 1:    # knock-knock
        place(out, knock(f), 0.0)
        place(out, knock(f * 1.07, 0.6), u(s, 0.05, 0.07))
    elif arch == 2:    # knock + ring
        place(out, knock(f), 0.0)
        g = u(s, 1900, 2400)
        place(out, pk(modal([g, g * 2.756, g * 5.4], [0.25, 0.12, 0.06], [1, 0.4, 0.15], 0.6, s.rng)), 0.002, 0.25)
    elif arch == 3:    # deep thunk + slide
        place(out, knock(f * 0.7), 0.0)
        place(out, pk(thud(s, 120, 0.2, 0.04, grit=0.6)), 0.0, 0.7)
        n = secs(0.18)
        place(out, pk(band(s.noise(n), 600, 3000) * ctl(n, [(0, 0), (0.03, 1), (0.18, 0)])), 0.05, 0.25)
    elif arch == 4:    # glancing: scrape first, then knock
        place(out, pk(scrape(s, 0.12, 1200, 6500)), 0.0, 0.4)
        place(out, knock(f * 1.05), 0.08)
    else:              # clack + rattle
        place(out, knock(f * 1.2, 0.9), 0.0)
        for j in range(3):
            place(out, tok(s, u(s, 1100, 1700), 0.01), 0.04 + 0.035 * j + u(s, 0, 0.01), 0.3 - 0.07 * j)
    place(out, pk(thud(s, 140, 0.15, 0.03, grit=0.5)), 0.0, 0.35)
    return room(s, out, 0.45, 0.1)


def dodge(s, k):
    arch, reg = L.cycle(k, list(range(8)), [1.0, 1.12, 0.9])
    out = buf(0.9)
    cloth = lambda d, pts: pk(rustle(s, secs(d), ctl(secs(d), rel(d, pts))))  # noqa: E731
    sw = lambda d, lo, hi, amp, bw=0.8: pk(shaped(s, d, [(0, lo * reg), (0.4, hi * reg), (1, lo * reg)], amp, bw))  # noqa: E731
    if arch == 0:      # roll: long rustle + whoosh + skid
        place(out, sw(0.3, 300, 1300, [(0, 0), (0.35, 1), (1, 0)]), 0.0, 0.8)
        place(out, cloth(0.3, [(0, 0), (0.2, 1), (1, 0)]), 0.02, 0.45)
        place(out, pk(scrape(s, 0.18, 200, 2400)), 0.2, 0.5)
    elif arch == 1:    # sidestep: short whoosh + one foot
        place(out, sw(0.16, 400, 1600, [(0, 0), (0.3, 1), (1, 0)]), 0.0, 0.8)
        place(out, pk(thud(s, 160, 0.1, 0.02, grit=0.8)), 0.13, 0.45)
    elif arch == 2:    # slide
        place(out, sw(0.12, 400, 1400, [(0, 0), (0.4, 1), (1, 0)]), 0.0, 0.5)
        place(out, pk(scrape(s, 0.32, 300, 3500)), 0.05, 0.8)
    elif arch == 3:    # hop + land
        place(out, sw(0.22, 350, 1500, [(0, 0), (0.6, 1), (1, 0)]), 0.0, 0.7)
        place(out, pk(thud(s, 120, 0.16, 0.035, grit=0.7)), 0.24, 0.7)
        place(out, cloth(0.12, [(0, 0), (0.1, 1), (1, 0)]), 0.24, 0.3)
    elif arch == 4:    # double step
        for j, at in enumerate((0.0, 0.11)):
            place(out, pk(thud(s, 170 - 20 * j, 0.09, 0.02, grit=0.8)), at + 0.04, 0.45)
        place(out, sw(0.24, 320, 1200, [(0, 0), (0.25, 0.8), (0.5, 0.4), (0.75, 1), (1, 0)]), 0.0, 0.7)
    elif arch == 5:    # spin
        place(out, pk(shaped(s, 0.34, [(0, 300 * reg), (0.5, 1400 * reg), (1, 500 * reg)], [(0, 0), (0.5, 1), (1, 0)], 0.75, (u(s, 9, 13), 0.6))), 0.0, 0.8)
        place(out, cloth(0.34, [(0, 0), (0.5, 1), (1, 0)]), 0.0, 0.35)
    elif arch == 6:    # duck: low whoosh, knee scuff
        place(out, sw(0.2, 220, 900, [(0, 0), (0.2, 1), (1, 0)], 0.9), 0.0, 0.8)
        place(out, pk(burst(s, 0.08, 300, 2500, 0.02)), 0.15, 0.4)
    else:              # skid stop
        place(out, sw(0.14, 380, 1500, [(0, 0), (0.5, 1), (1, 0)]), 0.0, 0.6)
        place(out, pk(scrape(s, 0.2, 250, 2800)), 0.09, 0.7)
        place(out, pk(thud(s, 150, 0.1, 0.02, grit=0.8)), 0.28, 0.4)
    return room(s, out, 0.35, 0.06)


CRIT_CHORDS = [(1568, 2349), (1318.5, 1975.5, 2637), (1760, 2217.5), (1174.7, 1568, 2349), (2093, 3136)]


def critical(s, k):
    chord = CRIT_CHORDS[k % len(CRIT_CHORDS)]
    out = buf(1.6)
    place(out, pk(thud(s, u(s, 100, 125), 0.3, 0.05, drop=0.5, grit=0.6)), 0.0, 0.8)
    place(out, click(s, 0.05, 1500, 9000, 0.003), 0.0, 0.9)
    if k % 2:
        place(out, click(s, 0.05, 1500, 9000, 0.003), 0.045, 0.6)       # second strike
    n = secs(0.6)
    boom = [55, 70, 48, 62, 80][k % 5]
    place(out, glide(n, ctl(n, [(0, boom * 1.3), (0.6, boom)])) * np.exp(-T(n) / 0.18), 0.0, 0.8)
    m = secs(0.3)
    up = k % 3 != 1
    place(out, pk(nsweep(s, m, ctl(m, [(0, 2000), (0.3, 9000)] if up else [(0, 9000), (0.3, 2500)]), 0.4) * ctl(m, [(0, 0), (0.02, 1), (0.3, 0)])), 0.01, 0.35)
    for j, f in enumerate(chord):
        place(out, pk(C.bell(s, f, 1.0, 0.45, 1.0)), 0.02 + j * [0.03, 0.0, 0.06, 0.02, 0.05][k % 5], 0.33 - 0.06 * j)
    m = secs(0.7)
    place(out, tinkles(s, m, [35, 20, 55, 28, 42][k % 5], 4000, 10000, ctl(m, [(0, 1), (0.7, 0)])), 0.04, 0.8)
    return room(s, out, 0.7, 0.12, 8000)


def spawn(s, k):
    swell, pop, tone = L.cycle(k, [0.32, 0.45, 0.58], ["thud", "bloop", "whoomp", "double"], [True, False])
    out = buf(1.8)
    n = secs(swell)
    up = [(0, 250), (swell, 1500)] if k % 2 == 0 else [(0, 900), (swell * 0.6, 300), (swell, 1200)]
    place(out, pk(nsweep(s, n, ctl(n, up), 0.7) * ctl(n, [(0, 0), (swell * 0.9, 1), (swell, 0.2)]) ** 1.5), 0.0, 0.9)
    if tone:
        f = u(s, 48, 62)
        place(out, pk(glide(n, ctl(n, [(0, f), (swell, f * 1.6)]), ((1, 1.0), (2, 0.4), (3, 0.2))) * ctl(n, [(0, 0), (swell * 0.95, 1), (swell, 0)])), 0.0, 0.45)
    at = swell
    if pop == "thud":
        place(out, pk(thud(s, 130, 0.25, 0.05, grit=0.7)), at, 0.8)
    elif pop == "bloop":
        place(out, pk(bloop(s, 420, 120, 0.2, 0.6)), at, 0.8)
    elif pop == "whoomp":
        m = secs(0.3)
        place(out, pk(nsweep(s, m, ctl(m, [(0, 200), (0.3, 900)]), 0.8) * ctl(m, [(0, 0), (0.02, 1), (0.3, 0)])), at, 0.8)
        place(out, pk(thud(s, 80, 0.3, 0.07, grit=0.3)), at, 0.6)
    else:
        place(out, pk(thud(s, 140, 0.18, 0.04, grit=0.7)), at, 0.7)
        place(out, pk(thud(s, 110, 0.22, 0.05, grit=0.6)), at + u(s, 0.09, 0.13), 0.6)
    m = secs(0.6)
    place(out, pk(nsweep(s, m, ctl(m, [(0, 1200), (0.6, 400)]), 0.9) * ctl(m, [(0, 0), (0.02, 1), (0.6, 0)])), at, 0.45)
    return room(s, out, 0.9, 0.15, 4000)


DISSOLVE_NOTES = [(1568, 1047, 784), (1047, 784, 659), (1319,), (988, 740), (1397, 1175, 880), (784, 1175)]
DISSOLVE_SWEEPS = [[(0, 0.4), (0.25, 1.0), (1, 0.2)], [(0, 0.3), (0.3, 0.9), (1, 0.25)], [(0, 0.6), (1, 0.4)], [(0, 1.0), (0.45, 0.15), (1, 0.12)]]


def dissolve(s, k):
    notes = DISSOLVE_NOTES[k % len(DISSOLVE_NOTES)]
    out = buf(1.9)
    d = [1.0, 1.15, 0.8, 0.6][k % 4]
    n = secs(d)
    fall = [(t_ * d, 6500 * v) for t_, v in DISSOLVE_SWEEPS[k % 4]]
    amp = [[(0, 0), (0.06, 1), (d, 0)], [(0, 0), (0.3 * d, 0.4), (0.5 * d, 1), (d, 0)], [(0, 0), (0.1, 1), (0.4 * d, 0.3), (0.6 * d, 0.8), (d, 0)], [(0, 0), (0.03, 1), (d, 0)]][k % 4]
    place(out, pk(nsweep(s, n, ctl(n, fall), 0.5) * ctl(n, amp)), 0.0, 0.7)
    place(out, tinkles(s, n, [30, 18, 44][k % 3], 3000, 9000, ctl(n, [(0, 1), (d, 0)])), 0.0, 0.7)
    m = secs(0.5)
    place(out, pk(nsweep(s, m, 500, 0.8) * ctl(m, [(0, 0), (0.05, 1), (0.5, 0)])), [0.0, 0.25, 0.1][k % 3], 0.5)
    for j, f in enumerate(notes):
        place(out, pk(C.bell(s, f * u(s, 0.98, 1.02), 1.0, 0.45, 0.5)), 0.12 + j * [0.12, 0.15, 0.0, 0.26, 0.1, 0.3][k % 6], 0.3 - 0.05 * j)
    return room(s, out, 1.0, 0.16, 7000)


def player_hit(s, k):
    arch, reg = L.cycle(k, list(range(8)), [1.0, 0.9, 1.12])
    out = buf(0.7)
    bwom = lambda pts, g=0.5, L_=0.22: place(out, pk(glide(secs(L_), ctl(secs(L_), [(t * L_, f * reg) for t, f in pts]), ((1, 1.0), (2, 0.35), (3, 0.12)))  # noqa: E731
                                                     * ctl(secs(L_), [(0, 0), (0.01, 1), (L_, 0)])), 0.0, g)
    place(out, pk(thud(s, u(s, 92, 108) * reg, 0.3, 0.06, grit=0.6)), 0.0, 1.0 if arch != 3 else 0.6)
    if arch == 0:      # two-tone "bwom-bom"
        bwom([(0, 240), (1, 190)], 0.5, 0.1)
        place(out, pk(glide(secs(0.12), ctl(secs(0.12), [(0, 150 * reg), (0.12, 110 * reg)]), ((1, 1.0), (2, 0.35))) * ctl(secs(0.12), [(0, 0), (0.01, 1), (0.12, 0)])), 0.11, 0.5)
    elif arch == 1:    # down-up "bwoing"
        bwom([(0, 230), (0.5, 120), (1, 170)], 0.55, 0.28)
    elif arch == 2:    # double thump
        place(out, pk(thud(s, 120 * reg, 0.2, 0.04, grit=0.6)), u(s, 0.06, 0.08), 0.6)
        bwom([(0, 180), (1, 110)], 0.35, 0.18)
    elif arch == 3:    # slap + high bwip
        place(out, smack(s, 1200, 5000, 0.007, 0.05), 0.0, 1.0)
        bwom([(0, 320), (1, 190)], 0.45, 0.14)
    elif arch == 4:    # muffled oof + air
        place(out, pk(breathy(s, 0.18, [(0, 800), (0.18, 400)], [(0, 0), (0.01, 1), (0.18, 0)], 0.8)), 0.0, 0.45)
        bwom([(0, 160), (1, 105)], 0.4, 0.25)
    elif arch == 5:    # rising bwip + star-ish ding
        bwom([(0, 130), (1, 230)], 0.4, 0.15)
        place(out, pk(C.bell(s, u(s, 1700, 2100), 0.4, 0.15, 0.6)), 0.12, 0.25)
    elif arch == 6:    # wobble
        n = secs(0.3)
        f = ctl(n, [(0, 190 * reg), (0.3, 125 * reg)]) * (1 + 0.08 * np.sin(2 * np.pi * 18 * T(n)))
        place(out, pk(glide(n, f, ((1, 1.0), (2, 0.3))) * ctl(n, [(0, 0), (0.01, 1), (0.3, 0)])), 0.0, 0.5)
    else:              # click + bwom up
        place(out, click(s, 0.03, 3000, 8000, 0.002), 0.0, 0.5)
        bwom([(0, 150), (1, 210)], 0.45, 0.16)
    return room(s, out, 0.3, 0.05)


def fuel(s, k):
    knocks, flare, crack = L.cycle(k, [2, 1, 3, 2, 1], [0.8, 0.5, 1.1, 0.65, 0.95], [70, 40, 110, 55, 90])
    out = buf(1.9)
    at = 0.0
    for j in range(knocks):
        place(out, wood_modal(s, u(s, 260, 340) * (1 + 0.1 * j)), at, 0.9 - 0.15 * j)
        at += u(s, 0.1, 0.16)
    n = secs(flare)
    place(out, pk(nsweep(s, n, ctl(n, [(0, 300), (flare * 0.4, 1200), (flare, 700)]), 0.8) * ctl(n, [(0, 0), (flare * 0.35, 1), (flare, 0)])), at, 0.55)
    if k % 2:
        place(out, pk(thud(s, 75, 0.35, 0.08, grit=0.2)), at, 0.35)     # flame whump
    m = secs(1.2)
    place(out, pops(s, m, crack, 1500, 7500, ctl(m, [(0, 0), (0.2, 1), (1.2, 0.1)])), at, 1.0)
    place(out, pk(fire(s, 1.1, 150, 1800)) * ctl(secs(1.1), [(0, 0), (0.3, 0.5), (1.1, 0)])[:secs(1.1)], at + 0.03, 0.4)
    return room(s, out, 0.4, 0.06)


NIGHT_CHORDS = [((55.0, 82.4, 110.0, 130.8, 164.8), (659.3, 523.3, 987.8)),
                ((65.4, 98.0, 130.8, 155.6, 196.0), (784.0, 622.3, 1046.5)),
                ((82.4, 123.5, 164.8, 196.0, 246.9), (987.8, 784.0, 659.3))]


def night(s, k):
    pad_f, glints = NIGHT_CHORDS[k % 3]
    out = buf(2.25)
    n = secs(2.05)
    pad = np.zeros(n)
    for j, f in enumerate(pad_f):
        pad += glide(n, f * (1 + 0.002 * np.sin(2 * np.pi * 0.3 * T(n) + f)), ((1, 1.0), (2, 0.3), (3, 0.12))) * (0.9 - 0.15 * j)
    shape = [[(0, 0), (0.5, 1), (1.4, 0.8), (2.05, 0)], [(0, 0), (1.0, 1), (1.6, 0.7), (2.05, 0)], [(0, 0), (0.25, 0.8), (0.7, 0.5), (1.3, 1), (2.05, 0)]][k % 3]
    place(out, pk(pad * ctl(n, shape)), 0.0, 0.5)
    place(out, pk(thud(s, [60, 52, 66][k % 3], 0.8, 0.25, drop=0.2, body=1.0, grit=0.2)), 0.0, 0.6)
    for j, (f, at) in enumerate(zip(glints, [(0.3, 0.7, 1.05), (0.15, 0.4, 1.2), (0.55, 0.85, 1.0)][k % 3])):
        place(out, pk(C.bell(s, f, 1.0, 0.6, 0.5)), at, 0.12)
    if k % 3 == 0:     # far howl, a different contour from night_1
        place(out, pk(vocal(s, 1.0, [(0, 380), (0.3, 520), (1.0, 360)], [(0, "u"), (0.4, "o"), (1.0, "u")], [(0, 0), (0.3, 0.8), (0.8, 0.6), (1.0, 0)],
                            0.92, tilt=1.3, breath=0.3, vib=(5, 0.012))), 0.9, 0.12)
    elif k % 3 == 1:   # owl
        for at in (0.8, 1.15):
            place(out, pk(vocal(s, 0.22, [(0, 420), (0.22, 380)], "u", [(0, 0), (0.05, 1), (0.22, 0)], 0.85, tilt=1.6, breath=0.3)), at, 0.12)
    else:              # wind gust
        m = secs(1.2)
        place(out, pk(V.wind(s, 1.2, 300, 1200, 0.4, 0.6, 0.6)), 0.6, 0.18)
    return room(s, out, 1.6, 0.25, 4000)


DAWN_ARPS = [(1174.7, 880.0, 740.0, 587.3), (466.2, 587.3, 698.5, 932.3), (698.5, 880.0, 1046.5, 1396.9, 1760.0)]
DAWN_PADS = [(146.8, 220.0, 293.7, 370.0), (116.5, 174.6, 233.1, 293.7), (174.6, 261.6, 349.2, 440.0)]


def dawn(s, k):
    out = buf(2.25)
    n = secs(1.9)
    pad = sum(glide(n, f, ((1, 1.0), (2, 0.25), (3, 0.08))) * a for f, a in zip(DAWN_PADS[k % 3], (0.7, 0.5, 0.45, 0.35)))
    place(out, pk(pad * ctl(n, [(0, 0), (0.4 + 0.2 * k, 1), (1.3, 0.8), (1.9, 0)])), 0.0, 0.35)
    step = [0.13, 0.09, 0.16][k % 3]
    for j, f in enumerate(DAWN_ARPS[k % 3]):
        place(out, pk(C.bell(s, f, 1.2, 0.7, 0.6)), 0.05 + j * step, 0.28 * (0.92 ** j))
    birds = [2, 4, 3][k % 3]
    for j in range(birds):
        m = secs(u(s, 0.06, 0.12))
        f0 = u(s, 2800, 4800)
        tt = T(m)
        L_ = m / SR
        ch = np.sin(2 * np.pi * np.cumsum(f0 * (1 + [0.3, -0.25, 0.45][j % 3] * np.sin(np.pi * tt / L_))) / SR) * np.sin(np.pi * tt / L_) ** 2
        place(out, ch, 0.9 + j * u(s, 0.1, 0.2), 0.07)
    return room(s, out, 1.2, 0.18, 7000)


def harvest_berry(s, k):
    pops_n, up, rust = L.cycle(k, [1, 2, 3, 1, 2], [True, False], [0.3, 0.2, 0.42])
    out = buf(0.7)
    m = secs(rust)
    place(out, pk(rustle(s, m, ctl(m, rel(rust, [(0, 0), (0.15 + 0.1 * (k % 3), 1), (1, 0)])))), 0.0, 0.7)
    at = rust * 0.4
    for j in range(pops_n):
        q = secs(0.12)
        f0, f1 = (u(s, 330, 430), u(s, 800, 1000)) if up else (u(s, 900, 1100), u(s, 380, 460))
        f0 *= 1 + 0.12 * j
        f1 *= 1 + 0.12 * j
        place(out, pk(glide(q, ctl(q, [(0, f0), (0.12, f1)])) * np.exp(-T(q) / 0.04) * np.minimum(T(q) / 0.003, 1)), at, 0.6 - 0.1 * j)
        at += u(s, 0.06, 0.1)
    if k % 4 == 3:     # twig snap
        place(out, tok(s, u(s, 1500, 2200), 0.008), 0.05, 0.25)
    return room(s, out, 0.3, 0.05)


# =============================================================================== combat: harvest takes derived from the recordings
def rec(name):
    x, sr = L.read_wav(COMBAT / ("harvest_%s_1.wav" % name))
    return L.resample(x, sr, SR)


def _hp_noise(s, d, lo, hi, pts):
    n = secs(d)
    return pk(band(s.noise(n), lo, hi) * ctl(n, rel(d, pts)))


def harvest_tree(s, k):
    """The team's chop: its impact (+ crack) stays the core; the body, follow-up and tail change."""
    x = rec("tree")
    a, b = secs(0.02), secs(0.13)                      # main impact segment
    hit = L.take_slice(x, SR, a, b, 0.001, 0.02)
    tail = x[b:]
    arch, ratio = L.cycle(k, list(range(11)), [1.0, 0.9, 1.1, 0.95, 1.06])
    out = buf(0.9)
    h = L.repitch(hit, ratio)
    if arch == 0:      # chop + a deeper wood body
        place(out, h, 0.0)
        place(out, wood_modal(s, u(s, 170, 210), 0.07), 0.028, 0.45)
    elif arch == 1:    # double chop
        place(out, h, 0.0)
        place(out, L.transient_shape(L.repitch(hit, ratio * 1.06), SR, -4.0), u(s, 0.11, 0.15), 0.55)
    elif arch == 2:    # chop + splinters
        place(out, h, 0.0)
        place(out, pk(V.crackle(s, 0.25, 110, 0.01)), 0.035, 0.35)
    elif arch == 3:    # chop + crown shiver (leaves)
        place(out, h, 0.0)
        place(out, L.repitch(tail, ratio), hit.size / SR, 0.5)
        m = secs(0.45)
        place(out, pk(rustle(s, m, ctl(m, [(0, 0), (0.08, 1), (0.45, 0)]))), 0.05, 0.3)
    elif arch == 4:    # snappy chop + chips
        place(out, L.transient_shape(h, SR, 6.0, -6.0), 0.0)
        for j in range(4):
            place(out, tok(s, u(s, 1300, 2400), 0.008), 0.04 + u(s, 0, 0.15), u(s, 0.12, 0.22))
    elif arch == 5:    # soft chop, hollow trunk ring
        place(out, L.transient_shape(h, SR, -5.0, 2.0), 0.0)
        place(out, wood_modal(s, u(s, 240, 280), 0.14), 0.02, 0.35)
    elif arch == 6:    # recording tail first reversed-in swish, then chop (wind-up)
        place(out, _hp_noise(s, 0.12, 400, 2500, [(0, 0), (0.8, 1), (1, 0)]), 0.0, 0.25)
        place(out, h, 0.1)
        place(out, L.repitch(tail, ratio * 0.95), 0.1 + hit.size / SR, 0.35)
    elif arch == 7:    # glancing chop + bark scrape
        place(out, h, 0.0, 0.8)
        place(out, pk(scrape(s, 0.2, 600, 4500)), 0.03, 0.35)
    elif arch == 8:    # chop + creak of the trunk
        place(out, h, 0.0)
        place(out, pk(V.creak(s, 0.3, u(s, 120, 150), u(s, 90, 110), q=6, rough=0.2, swell=0.03, release=0.12)), 0.06, 0.28)
    elif arch == 9:    # chop with heavier low thump
        place(out, h, 0.0)
        place(out, pk(thud(s, u(s, 95, 115), 0.25, 0.05, grit=0.4)), 0.004, 0.45)
        place(out, L.repitch(tail, ratio * 1.04), hit.size / SR, 0.3)
    else:              # triple quick chop
        for j in range(3):
            place(out, L.repitch(hit, ratio * (1 + 0.05 * j)), j * u(s, 0.075, 0.09), 1.0 - 0.25 * j)
    return L.tilt(out, SR, [0.0, -2.0, 2.0][k % 3])


def harvest_stone(s, k):
    """Pick on rock: the recording's strikes re-cut into new rhythms, plus chips and sparks."""
    x = rec("stone")
    segs = L.segments(x, SR)
    arch, ratio = L.cycle(k, list(range(11)), [1.0, 0.92, 1.08, 0.96, 1.04])
    rng = s.rng
    count = [3, 4, 2, 5, 3, 4, 2, 6, 3, 4, 3][arch]
    first = [0, 1, 2, 0, 3, 5, 6, 1, 8, 4, 10][arch] % len(segs)
    rest = [i for i in range(len(segs)) if i != first]
    rng.shuffle(rest)
    order = [first] + rest[: count - 1]
    parts = [L.take_slice(x, SR, *segs[i], fade_in=0.0015, fade_out=0.008) for i in order]
    gaps = [[0.0, 0.05, 0.09], [0.02, 0.0, 0.07], [0.04, 0.12, 0.0]][arch % 3]
    out = np.zeros(0)
    for j, p in enumerate(parts):
        out = np.concatenate([out, p[: secs(0.16)] * (1.0 if j == 0 else u(s, 0.45, 0.8)), np.zeros(secs(gaps[j % 3] * u(s, 0.8, 1.2)))])
    out = L.repitch(out, ratio)
    lay = buf(out.size / SR + 0.3)
    place(lay, out, 0.0)
    if arch in (1, 5, 9):
        f = u(s, 2600, 3600)
        place(lay, pk(modal([f, f * 1.52, f * 2.31], [0.06, 0.035, 0.02], [1, 0.5, 0.3], 0.25, s.rng)), 0.004, 0.25)   # spark
    if arch in (2, 6, 10):
        place(lay, debris(s, secs(0.4), 6, 0.05, 0.3, (0.25, 0.5), 0.35), 0.0, 0.8)
    if arch in (3, 7):
        place(lay, pk(thud(s, u(s, 100, 125), 0.18, 0.04, grit=0.7)), 0.0, 0.35)
    if arch in (4, 8):
        place(lay, pk(scrape(s, 0.25, 300, 4000)), 0.06, 0.3)
    return L.tilt(lay, SR, [0.0, 2.0, -2.0, 1.0][k % 4])


def harvest_fiber(s, k):
    """Grass torn up: the recording's tear re-cut (other order, length, splits) plus a synthetic rip or root snap."""
    x = rec("fiber")
    segs = L.segments(x, SR)
    arch, ratio = L.cycle(k, list(range(11)), [1.0, 0.93, 1.07, 0.97, 1.04])
    rng = s.rng
    idx = list(range(len(segs)))
    if arch % 3 == 0:
        rng.shuffle(idx)
    elif arch % 3 == 1:
        idx = idx[::-1]
    else:
        idx = idx[1:] + idx[:1]
    keep = [5, 3, 4, 2, 5, 3, 4, 3, 2, 4, 3][arch]
    parts = [L.take_slice(x, SR, *segs[i], fade_in=0.002, fade_out=0.01)[: secs(u(s, 0.06, 0.13))] for i in idx[:keep]]
    out = L.concat(parts, SR, 0.006)
    out = L.repitch(out, ratio)
    lay = buf(out.size / SR + 0.35)
    place(lay, out, 0.0)
    if arch in (0, 4, 8):      # pulsed rip
        m = secs(0.12)
        rip = norm(band(s.noise(m), 800, 5000)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * u(s, 70, 120) * T(m)))) * ctl(m, [(0, 0), (0.02, 1), (0.12, 0)])
        place(lay, pk(rip), out.size / SR * 0.5, 0.35)
    if arch in (1, 5, 9):      # root snap
        place(lay, tok(s, u(s, 900, 1400), 0.012), out.size / SR * 0.7, 0.3)
    if arch in (2, 6, 10):     # soil crumble
        place(lay, pops(s, secs(0.25), 120, 600, 3500, ctl(secs(0.25), [(0, 1), (0.25, 0)]), (0.002, 0.005)), out.size / SR * 0.6, 0.5)
    if arch in (3, 7):         # leafy swish
        place(lay, _hp_noise(s, 0.18, 2000, 8000, [(0, 0), (0.3, 1), (1, 0)]), 0.0, 0.2)
    return L.tilt(lay, SR, [0.0, -2.0, 2.0][k % 3])


# =============================================================================== combat: new cues
def whiff(s, k):
    """An enemy attack that misses: something passes close by."""
    out = buf(0.9)
    if k == 0:     # fast pass-by (doppler-ish downward sweep)
        place(out, pk(shaped(s, 0.24, [(0, 2600), (0.4, 1500), (1, 500)], [(0, 0), (0.35, 1), (1, 0)], 0.5)), 0.0)
    elif k == 1:   # jaws snap shut on air
        place(out, pk(shaped(s, 0.14, [(0, 600), (1, 1800)], [(0, 0), (0.8, 1), (1, 0)], 0.7)), 0.0, 0.7)
        snap = modal([1750, 2900, 4200], [0.012, 0.008, 0.005], [1, 0.6, 0.35], 0.08, s.rng)
        place(out, pk(np.asarray(snap) + click(s, 0.03, 2000, 9000, 0.0015)), 0.12, 0.8)
    elif k == 2:   # heavy slam into empty ground
        place(out, pk(shaped(s, 0.3, [(0, 900), (1, 200)], [(0, 0), (0.7, 1), (1, 0)], 0.8, body=1.0)), 0.0, 0.8)
        place(out, pk(thud(s, 70, 0.4, 0.09, grit=0.8)), 0.28, 0.9)
        place(out, debris(s, secs(0.5), 6, 0.3, 0.3, (0.3, 0.6), 0.4), 0.0, 0.8)
    elif k == 3:   # double claw swipe
        for j, at in enumerate((0.0, 0.13)):
            place(out, pk(shaped(s, 0.13, [(0, 1200), (0.5, 3200), (1, 1500)], [(0, 0), (0.4, 1), (1, 0)], 0.45)), at, 1.0 - 0.25 * j)
    elif k == 4:   # flame swoosh past
        place(out, pk(shaped(s, 0.36, [(0, 3000), (1, 600)], [(0, 0), (0.25, 1), (1, 0)], 0.7)), 0.0, 0.8)
        m = secs(0.4)
        place(out, pops(s, m, 70, 1500, 7000, ctl(m, [(0, 1), (0.4, 0)])), 0.02, 0.8)
    else:          # spore puff misses: airy poof + drifting hiss
        place(out, pk(nsweep(s, secs(0.3), 1600, 1.0) * ctl(secs(0.3), [(0, 0), (0.01, 1), (0.08, 0.5), (0.3, 0)])), 0.0, 0.8)
        n = secs(0.5)
        place(out, pk(high(s.noise(n), 5500) * ctl(n, [(0, 0), (0.05, 0.4), (0.5, 0)])), 0.05, 0.4)
    return room(s, out, 0.35, 0.06)


def equip(s, k):
    out = buf(0.6)
    if k == 0:     # grab the grip: leather creak + tap
        place(out, pk(V.creak(s, 0.12, 300, 240, body=(600, 1300, 2400), q=5, rough=0.25, swell=0.02, release=0.05)), 0.0, 0.5)
        place(out, tok(s, u(s, 700, 850), 0.015), 0.09, 0.6)
    elif k == 1:   # shaft slapped into the palm
        place(out, smack(s, 600, 3500, 0.01, 0.05), 0.0, 0.8)
        place(out, pk(thud(s, 180, 0.12, 0.025, grit=0.5)), 0.0, 0.6)
    elif k == 2:   # flip and catch
        place(out, pk(shaped(s, 0.18, [(0, 500), (0.5, 1800), (1, 600)], [(0, 0), (0.5, 1), (1, 0)], 0.6, (u(s, 14, 18), 0.6))), 0.0, 0.5)
        place(out, smack(s, 500, 3000, 0.01, 0.05), 0.19, 0.7)
        place(out, tok(s, u(s, 600, 750), 0.012), 0.19, 0.3)
    elif k == 3:   # stone head clunk + cloth
        place(out, pk(rock(s, 1.5)), 0.0, 0.6)
        place(out, pk(thud(s, 130, 0.12, 0.03, grit=0.6)), 0.0, 0.5)
        m = secs(0.18)
        place(out, pk(rustle(s, m, ctl(m, [(0, 0), (0.05, 1), (0.18, 0)]))), 0.02, 0.3)
    else:          # drawn from the back: cloth slide, then tok
        m = secs(0.22)
        place(out, pk(rustle(s, m, ctl(m, [(0, 0), (0.15, 1), (0.22, 0)]))), 0.0, 0.45)
        place(out, pk(shaped(s, 0.12, [(0, 700), (1, 1600)], [(0, 0), (0.7, 1), (1, 0)], 0.6)), 0.12, 0.4)
        place(out, tok(s, u(s, 800, 950), 0.012), 0.24, 0.55)
    return room(s, out, 0.3, 0.05)


CAMPFIRE_LEN = 6.0


def campfire_loop(s, k):
    """Seamless campfire: low roar, flicker, crackle and the odd bigger pop (6 s, loops at the seam)."""
    d = CAMPFIRE_LEN + 0.6       # render() resamples, trims 0.15 s per edge, then loops (0.2 s crossfade)
    n = secs(d)
    roar = norm(band(s.noise(n), 90, 900)) * (0.6 + 0.4 * np.clip(C.wander(s, n, 1.5, 1.0), -1, 1))
    flick = norm(band(s.noise(n), 500, 2800)) * (0.4 + 0.6 * np.clip(np.abs(C.wander(s, n, 7, 1.0)), 0, 1)) * 0.35
    out = roar * 0.5 + flick
    out = out + pops(s, n, 26, 1500, 7500, None, (0.0012, 0.005)) * 1.6
    for _ in range(9):     # bigger pops / wood snaps
        place(out, pk(click(s, 0.04, 900, 6000, u(s, 0.002, 0.005))) * 2.2, u(s, 0.1, d - 0.2))
    for _ in range(2):     # sap hiss
        m = secs(u(s, 0.3, 0.6))
        place(out, pk(high(s.noise(m), 3500)) * ctl(m, [(0, 0), (m / SR * 0.3, 0.5), (m / SR, 0)]), u(s, 0.3, d - 1.0))
    return out


def sputter(s, k):
    out = buf(1.2)
    if k == 0:     # hiss, pop, pop
        n = secs(0.35)
        place(out, pk(high(s.noise(n), 3000) * ctl(n, [(0, 0), (0.02, 1), (0.35, 0)])), 0.0, 0.5)
        for at in (0.08, 0.2):
            place(out, pk(click(s, 0.04, 900, 6000, 0.003)), at + u(s, 0, 0.02), 0.8)
    elif k == 1:   # flare then die down
        n = secs(0.6)
        place(out, pk(nsweep(s, n, ctl(n, [(0, 400), (0.15, 1400), (0.6, 300)]), 0.8) * ctl(n, [(0, 0), (0.12, 1), (0.6, 0)])), 0.0, 0.9)
        place(out, pk(thud(s, 80, 0.3, 0.07, grit=0.2)), 0.0, 0.3)
    elif k == 2:   # sizzle (sap) with tiny pops
        n = secs(0.55)
        place(out, pk(band(s.noise(n), 3000, 9000) * ctl(n, [(0, 0), (0.05, 1), (0.3, 0.6), (0.55, 0)]) * (0.6 + 0.4 * np.clip(C.wander(s, n, 40, 1), -1, 1))), 0.0, 0.6)
        place(out, pops(s, n, 40, 2000, 8000), 0.0, 0.6)
    elif k == 3:   # log shifts: wood tok + crackle burst
        place(out, wood_modal(s, u(s, 230, 280), 0.04), 0.0, 0.7)
        m = secs(0.5)
        place(out, pops(s, m, 90, 1500, 7000, ctl(m, [(0, 1), (0.5, 0)])), 0.02, 0.9)
    else:          # embers collapse: low thud + shower of pops
        place(out, pk(thud(s, 90, 0.3, 0.07, grit=0.7)), 0.0, 0.7)
        m = secs(0.7)
        place(out, pops(s, m, 70, 1200, 6500, ctl(m, [(0, 0.3), (0.1, 1), (0.7, 0)])), 0.03, 0.9)
    return room(s, out, 0.4, 0.06)


def depleted(kind):
    def fn(s, k):
        out = buf(2.0)
        if kind == "tree":
            if k == 0:     # crack, creak, thud
                place(out, pk(click(s, 0.06, 900, 7000, 0.004)), 0.0, 0.9)
                place(out, pk(V.creak(s, 0.7, 140, 70, q=6, rough=0.25, swell=0.05, release=0.2)), 0.05, 0.5)
                place(out, pk(thud(s, 62, 0.5, 0.12, body=1.3, grit=0.7)), 0.8, 1.0)
                m = secs(0.5)
                place(out, pk(rustle(s, m, ctl(m, [(0, 0), (0.03, 1), (0.5, 0)]))), 0.8, 0.4)
            elif k == 1:   # splintering crack, leafy crash, two bounces
                place(out, pk(V.crackle(s, 0.4, 140, 0.02)), 0.0, 0.7)
                m = secs(0.7)
                place(out, pk(rustle(s, m, ctl(m, [(0, 0), (0.1, 1), (0.7, 0)]))), 0.35, 0.6)
                for j, at in enumerate((0.55, 0.78)):
                    place(out, pk(thud(s, 70 + 10 * j, 0.4, 0.09, body=1.2, grit=0.7)), at, 0.9 - 0.3 * j)
            else:          # long creak, crash
                place(out, pk(V.creak(s, 0.9, 110, 60, q=7, rough=0.3, swell=0.1, release=0.25)), 0.0, 0.6)
                place(out, pk(thud(s, 58, 0.6, 0.14, body=1.4, grit=0.8)), 0.9, 1.0)
                place(out, pk(V.crackle(s, 0.3, 90, 0.02)), 0.9, 0.4)
        elif kind == "stone":
            if k == 0:     # crack + rubble cascade
                place(out, pk(rock(s, 1.6)), 0.0, 0.9)
                place(out, debris(s, secs(1.2), 26, 0.05, 0.9, (0.3, 1.0), 0.6, 1.3), 0.0, 1.0)
            elif k == 1:   # split + a few big tumbles
                place(out, click(s, 0.05, 1200, 9000, 0.004), 0.0, 1.0)
                place(out, pk(rock(s, 1.9)), 0.0, 0.8)
                for j in range(4):
                    place(out, pk(thud(s, 95 + 15 * j, 0.2, 0.04, grit=0.8)), 0.15 + 0.16 * j + u(s, 0, 0.04), 0.7 - 0.12 * j)
                    place(out, pk(rock(s, 1.2)), 0.15 + 0.16 * j, 0.4)
            else:          # grinding collapse + dust
                n = secs(0.8)
                place(out, pk(band(s.noise(n), 60, 500) * ctl(n, [(0, 0), (0.2, 1), (0.8, 0)])), 0.0, 0.7)
                place(out, debris(s, secs(1.0), 16, 0.2, 0.6, (0.4, 1.2), 0.5), 0.0, 1.0)
                place(out, pk(breathy(s, 0.6, [(0, 1500), (0.6, 2500)], [(0, 0), (0.15, 1), (0.6, 0)], 1.0)), 0.5, 0.3)
        elif kind == "fiber":
            if k == 0:     # long rip + rustle settle
                m = secs(0.35)
                rip = norm(band(s.noise(m), 900, 6000)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 85 * T(m)))) * ctl(m, [(0, 0), (0.05, 1), (0.35, 0)])
                place(out, pk(rip), 0.0, 0.8)
                q = secs(0.5)
                place(out, pk(rustle(s, q, ctl(q, [(0, 0), (0.1, 1), (0.5, 0)]))), 0.3, 0.5)
            elif k == 1:   # root snap + rustle
                place(out, tok(s, u(s, 900, 1200), 0.015), 0.0, 0.8)
                q = secs(0.45)
                place(out, pk(rustle(s, q, ctl(q, [(0, 0), (0.03, 1), (0.45, 0)]))), 0.02, 0.6)
                place(out, pops(s, secs(0.3), 120, 600, 3500, ctl(secs(0.3), [(0, 1), (0.3, 0)])), 0.05, 0.5)
            else:          # two rips, leaves fall
                for j, at in enumerate((0.0, 0.22)):
                    m = secs(0.14)
                    rip = norm(band(s.noise(m), 1000, 7000)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * (110 - 25 * j) * T(m)))) * ctl(m, [(0, 0), (0.02, 1), (0.14, 0)])
                    place(out, pk(rip), at, 0.8)
                q = secs(0.5)
                place(out, pk(rustle(s, q, ctl(q, [(0, 0), (0.2, 1), (0.5, 0)]))), 0.35, 0.35)
        else:  # berry bush emptied
            if k == 0:     # shake, last pop, leaves settle
                q = secs(0.45)
                place(out, pk(rustle(s, q, ctl(q, [(0, 0), (0.1, 1), (0.25, 0.5), (0.45, 0)]))), 0.0, 0.8)
                p = secs(0.12)
                place(out, pk(glide(p, ctl(p, [(0, 900), (0.12, 380)])) * np.exp(-T(p) / 0.04)), 0.3, 0.5)
            elif k == 1:   # rustle + twig snap + settle
                q = secs(0.6)
                place(out, pk(rustle(s, q, ctl(q, [(0, 0), (0.05, 1), (0.6, 0)]))), 0.0, 0.7)
                place(out, tok(s, u(s, 1600, 2100), 0.01), 0.12, 0.5)
            else:          # shake-shake + soft thump
                for j, at in enumerate((0.0, 0.22)):
                    q = secs(0.2)
                    place(out, pk(rustle(s, q, ctl(q, [(0, 0), (0.05, 1), (0.2, 0)]))), at, 0.7 - 0.15 * j)
                place(out, pk(thud(s, 140, 0.15, 0.04, grit=0.4)), 0.45, 0.45)
        return room(s, out, 0.5, 0.08)
    return fn


def night_warn(s, k):
    out = buf(2.2)
    if k == 0:     # distant double toll
        for j, at in enumerate((0.0, 0.7)):
            place(out, pk(C.bell(s, [220.0, 207.7][j], 1.4, 0.9, 0.5)), at, 0.6)
        n = secs(1.6)
        place(out, pk(glide(n, 55, ((1, 1.0), (2, 0.3))) * ctl(n, [(0, 0), (0.8, 1), (1.6, 0)])), 0.2, 0.3)
    elif k == 1:   # rising minor swell + owl
        n = secs(1.4)
        pad = sum(glide(n, f * ctl(n, [(0, 1.0), (1.4, 1.03)]), ((1, 1.0), (2, 0.25))) * a for f, a in ((110, 0.8), (130.8, 0.6), (164.8, 0.5)))
        place(out, pk(pad * ctl(n, [(0, 0), (1.1, 1), (1.4, 0)])), 0.0, 0.6)
        for at in (0.9, 1.25):
            place(out, pk(vocal(s, 0.2, [(0, 410), (0.2, 370)], "u", [(0, 0), (0.05, 1), (0.2, 0)], 0.85, tilt=1.6, breath=0.3)), at, 0.25)
    else:          # low horn + wind gust
        n = secs(1.3)
        place(out, pk(glide(n, ctl(n, [(0, 98), (0.2, 110), (1.3, 104)]), ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15))) * ctl(n, [(0, 0), (0.25, 1), (1.0, 0.8), (1.3, 0)])), 0.0, 0.5)
        place(out, pk(V.wind(s, 1.4, 300, 1300, 0.4, 0.7, 0.7)), 0.4, 0.4)
    return room(s, out, 1.4, 0.22, 4000)


def cold(s, k):
    out = buf(1.4)
    if k == 0:     # icy gust + glints
        place(out, pk(V.wind(s, 0.9, 500, 2500, 0.25, 0.5, 0.6)), 0.0, 0.7)
        m = secs(0.8)
        place(out, tinkles(s, m, 25, 3500, 9500, ctl(m, [(0, 0), (0.3, 1), (0.8, 0)])), 0.1, 0.7)
    elif k == 1:   # shiver "brrr": a rolled, trembling breath
        n = secs(0.55)
        am = 0.5 + 0.5 * np.sin(2 * np.pi * u(s, 22, 28) * T(n))
        place(out, pk(vocal(s, 0.55, [(0, 290), (0.55, 260)], [(0, "u"), (0.55, "eu")], [(0, 0), (0.05, 1), (0.45, 0.8), (0.55, 0)], 1.1, tilt=1.4, breath=0.5) * am), 0.0, 0.8)
    elif k == 2:   # ice creak + crackle
        place(out, pk(V.creak(s, 0.6, 900, 650, body=(1200, 2400, 4200), q=8, rough=0.15, swell=0.05, release=0.2)), 0.0, 0.6)
        place(out, click(s, 0.04, 2500, 10000, 0.002), 0.35, 0.6)
        place(out, tinkles(s, secs(0.4), 30, 4000, 10000), 0.35, 0.5)
    else:          # frosty breath
        place(out, pk(breathy(s, 0.55, [(0, 1700), (0.55, 1200)], [(0, 0), (0.08, 1), (0.55, 0)], 0.6)), 0.0, 0.7)
        m = secs(0.6)
        place(out, tinkles(s, m, 18, 4000, 9000, ctl(m, [(0, 0.5), (0.3, 1), (0.6, 0)])), 0.15, 0.6)
    return room(s, out, 0.9, 0.12, 8000)


def growl_tone(s, d, f_pts, flutter=0.6):
    n = secs(d)
    f = ctl(n, f_pts) * (1 + 0.05 * np.clip(C.wander(s, n, 18, 1.0), -2, 2))
    x = glide(n, f, ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)))
    x *= 0.6 + 0.4 * np.clip(np.abs(C.wander(s, n, 30, flutter)), 0, 1)
    return low(x, 900)


def hunger(s, k):
    out = buf(1.5)
    if k == 0:     # long rising growl
        place(out, pk(growl_tone(s, 0.9, [(0, 70), (0.9, 110)]) * ctl(secs(0.9), [(0, 0), (0.3, 1), (0.9, 0)])), 0.0)
    elif k == 1:   # double gurgle
        for j, at in enumerate((0.0, 0.32)):
            place(out, pk(growl_tone(s, 0.22, [(0, 90 + 20 * j), (0.22, 70)]) * ctl(secs(0.22), [(0, 0), (0.05, 1), (0.22, 0)])), at, 0.8)
            place(out, pk(bloop(s, 260 + 60 * j, 140, 0.12, 0.4)), at + 0.12, 0.4)
    elif k == 2:   # squeaky growl (higher, falling)
        place(out, pk(growl_tone(s, 0.6, [(0, 190), (0.25, 150), (0.6, 90)], 0.9) * ctl(secs(0.6), [(0, 0), (0.08, 1), (0.6, 0)])), 0.0)
    else:          # bubbly gurgles
        for j in range(5):
            place(out, pk(bloop(s, u(s, 180, 320), u(s, 90, 140), u(s, 0.08, 0.14), 0.3)), 0.06 * j + u(s, 0, 0.03), 0.6)
        place(out, pk(growl_tone(s, 0.4, [(0, 80), (0.4, 72)]) * ctl(secs(0.4), [(0, 0), (0.1, 1), (0.4, 0)])), 0.15, 0.6)
    return room(s, out, 0.3, 0.04)


def ember(s, k):
    out = buf(1.2)
    if k == 0:     # sizzle + crackle
        n = secs(0.6)
        place(out, pk(band(s.noise(n), 2500, 9000) * ctl(n, [(0, 0), (0.03, 1), (0.6, 0)]) * (0.6 + 0.4 * np.clip(C.wander(s, n, 45, 1), -1, 1))), 0.0, 0.7)
        place(out, pops(s, n, 60, 1500, 7000, ctl(n, [(0, 1), (0.6, 0)])), 0.0, 0.8)
    elif k == 1:   # flare whoosh + pops
        n = secs(0.5)
        place(out, pk(nsweep(s, n, ctl(n, [(0, 300), (0.5, 1800)]), 0.8) * ctl(n, [(0, 0), (0.15, 1), (0.5, 0)])), 0.0, 0.8)
        place(out, pops(s, secs(0.6), 50, 1500, 7500, ctl(secs(0.6), [(0, 0), (0.2, 1), (0.6, 0)])), 0.1, 0.8)
    elif k == 2:   # blistering pops
        for j in range(6):
            place(out, pk(click(s, 0.04, 800, 5000, u(s, 0.002, 0.005))), j * 0.07 + u(s, 0, 0.03), u(s, 0.5, 1.0))
        n = secs(0.5)
        place(out, pk(high(s.noise(n), 4000) * ctl(n, [(0, 0), (0.1, 0.5), (0.5, 0)])), 0.05, 0.3)
    else:          # low roar + hiss
        n = secs(0.7)
        place(out, pk(fire(s, 0.7, 120, 900)) * ctl(n, [(0, 0), (0.2, 1), (0.7, 0)])[: secs(0.7)], 0.0, 0.8)
        place(out, pk(high(s.noise(n), 3000) * ctl(n, [(0, 0), (0.3, 1), (0.7, 0)])), 0.1, 0.35)
    return room(s, out, 0.5, 0.07)


def craft_tool(s, k):
    out = buf(1.2)
    if k == 0:     # knock-knock-knock + cord pull
        for j in range(3):
            place(out, wood_modal(s, u(s, 300, 380) * (1 + 0.06 * j), 0.035), j * 0.13 + u(s, 0, 0.02), 0.8)
        place(out, pk(V.creak(s, 0.2, 380, 300, body=(500, 1100, 2100), q=4, rough=0.3, swell=0.02, release=0.06)), 0.45, 0.4)
    elif k == 1:   # sharpening scrape-scrape + tap
        for j in range(2):
            place(out, pk(scrape(s, 0.2, 1200, 7000)), j * 0.26, 0.6)
        place(out, pk(rock(s, 1.0)), 0.55, 0.6)
    elif k == 2:   # cord wraps + knot
        for j in range(3):
            q = secs(0.12)
            place(out, pk(rustle(s, q, ctl(q, [(0, 0), (0.06, 1), (0.12, 0)]))), j * 0.12, 0.5)
        place(out, pk(L.ks_pluck(SR, u(s, 160, 200), 0.25, s.rng, 0.99, 0.3)), 0.38, 0.4)
        place(out, wood_modal(s, u(s, 320, 360), 0.03), 0.55, 0.7)
    else:          # two hard knocks + slide
        place(out, pk(rock(s, 1.3)), 0.0, 0.8)
        place(out, wood_modal(s, u(s, 280, 320)), 0.17, 0.8)
        n = secs(0.2)
        place(out, pk(band(s.noise(n), 500, 3000) * ctl(n, [(0, 0), (0.03, 1), (0.2, 0)])), 0.3, 0.35)
    return room(s, out, 0.4, 0.08)


def craft_soup(s, k):
    out = buf(1.4)
    bub = lambda at, cnt, spread: [place(out, pk(bloop(s, u(s, 250, 520), u(s, 500, 900), u(s, 0.05, 0.1), 0.2)), at + u(s, 0, spread), u(s, 0.3, 0.7)) for _ in range(cnt)]  # noqa: E731
    clink = lambda at: place(out, pk(L.modal(SR, u(s, 1800, 2400), "ceramic", dur=0.3, rng=s.rng)), at, 0.4)  # noqa: E731
    if k == 0:     # bubbles + spoon clink
        bub(0.0, 7, 0.6)
        clink(0.65)
    elif k == 1:   # pour + bubbles
        n = secs(0.45)
        place(out, pk(band(s.noise(n), 400, 3000) * ctl(n, [(0, 0), (0.05, 1), (0.4, 0.7), (0.45, 0)]) * (0.7 + 0.3 * np.clip(C.wander(s, n, 25, 1), -1, 1))), 0.0, 0.6)
        bub(0.35, 5, 0.4)
    elif k == 2:   # stir swish + bloops + lid tap
        place(out, pk(shaped(s, 0.4, [(0, 400), (0.5, 900), (1, 500)], [(0, 0), (0.3, 1), (0.6, 0.4), (1, 0)], 0.8)), 0.0, 0.5)
        bub(0.2, 4, 0.4)
        place(out, pk(L.modal(SR, u(s, 900, 1100), "metal", dur=0.3, rng=s.rng)), 0.7, 0.3)
    else:          # sizzle + bubbles + double clink
        n = secs(0.5)
        place(out, pk(high(s.noise(n), 3500) * ctl(n, [(0, 0), (0.05, 1), (0.5, 0)])), 0.0, 0.35)
        bub(0.1, 5, 0.4)
        clink(0.55)
        clink(0.68)
    return room(s, out, 0.4, 0.07)


def cloth_rip(s, d, rate):
    m = secs(d)
    return pk(norm(band(s.noise(m), 1200, 7500)) * (0.4 + 0.6 * np.abs(np.sin(np.pi * rate * T(m)))) * ctl(m, [(0, 0), (0.02, 1), (d * 0.7, 0.8), (d, 0)]))


def craft_bandage(s, k):
    out = buf(1.0)
    fold = lambda at, d=0.16: place(out, pk(rustle(s, secs(d), ctl(secs(d), [(0, 0), (d * 0.3, 1), (d, 0)]))), at, 0.5)  # noqa: E731
    if k == 0:
        place(out, cloth_rip(s, 0.3, 60), 0.0, 0.8)
        fold(0.35)
    elif k == 1:
        place(out, cloth_rip(s, 0.16, 80), 0.0, 0.8)
        place(out, cloth_rip(s, 0.2, 55), 0.24, 0.7)
    elif k == 2:
        place(out, cloth_rip(s, 0.25, 70), 0.0, 0.8)
        place(out, smack(s, 800, 4000, 0.006, 0.04), 0.35, 0.5)     # tie snap
        fold(0.42, 0.12)
    else:
        fold(0.0, 0.2)
        fold(0.22, 0.18)
        place(out, pk(thud(s, 170, 0.1, 0.02, grit=0.4)), 0.45, 0.4)
    return room(s, out, 0.3, 0.05)


def bandage(s, k):
    out = buf(1.2)
    wrap = lambda at, d: place(out, pk(rustle(s, secs(d), ctl(secs(d), [(0, 0), (d * 0.5, 1), (d, 0)]))), at, 0.6)  # noqa: E731
    pat = lambda at, g=0.4: place(out, pk(thud(s, u(s, 150, 190), 0.1, 0.02, grit=0.4)), at, g)  # noqa: E731
    if k == 0:     # three wraps + tie snap
        for j in range(3):
            wrap(j * 0.17, 0.16)
        place(out, smack(s, 800, 4000, 0.006, 0.04), 0.55, 0.5)
    elif k == 1:   # rip + wrap
        place(out, cloth_rip(s, 0.18, 75), 0.0, 0.7)
        wrap(0.25, 0.35)
    elif k == 2:   # wrap + double pat
        wrap(0.0, 0.3)
        pat(0.38)
        pat(0.52, 0.3)
    else:          # slow wrap + tug
        wrap(0.0, 0.5)
        place(out, pk(V.creak(s, 0.12, 420, 360, body=(700, 1500, 2800), q=4, rough=0.3, swell=0.02, release=0.04)), 0.52, 0.35)
    return room(s, out, 0.3, 0.05)


# =============================================================================== hero voice
HF0, HSC = 345.0, 1.17
HKW = dict(tilt=1.15, breath=0.12, jitter=0.004, fmax=9000)


def hv(s, d, rel_f, vowels, amp, p, sc, **kw):
    """Hero vocal: rel_f = [(t, ratio of p)] in seconds."""
    return vocal(s, d, [(t, p * r) for t, r in rel_f], vowels, amp, sc, **{**HKW, **kw})


def hh(s, out, at, d=0.035, g=0.35, fc=2600):
    place(out, breathy(s, d, [(0, fc), (d, fc * 0.9)], [(0, 0), (d * 0.4, 1), (d, 0.5)], 0.9), at, g)


def tclick(s, out, at, g=0.25, lo=2500, hi=7000):
    place(out, click(s, 0.02, lo, hi, 0.0012), at, g)


# (contour, vowel, onset, length, end vowel): "hap!", "hi-yu", "ho", "hae", "teh" ...
ATTACK_SPECS = [("fall", "a", "h", 0.11, "eu"), ("rise", "i", "t", 0.14, "u"), ("late", "o", "none", 0.085, "o"),
                ("flat", "ae", "h", 0.125, "eo"), ("dip", "e", "t", 0.11, "eu"), ("fall", "i", "none", 0.14, "i"),
                ("rise", "a", "h", 0.085, "u"), ("late", "ae", "t", 0.11, "ae"), ("flat", "o", "h", 0.14, "u"),
                ("dip", "a", "none", 0.125, "eo")]


def hero_attack(s, k):
    p = HF0 * u(s, 0.97, 1.04)
    sc = HSC * u(s, 0.98, 1.02)
    cont, v, onset, d, end = ATTACK_SPECS[k % len(ATTACK_SPECS)]
    F = {"fall": [(0, 1.32), (1, 1.0)], "rise": [(0, 1.0), (1, 1.3)], "late": [(0, 1.0), (0.7, 1.36), (1, 1.16)],
         "flat": [(0, 1.4), (1, 1.34)], "dip": [(0, 1.22), (0.5, 1.0), (1, 1.15)]}[cont]
    out = buf(0.6)
    at = 0.0
    if onset == "h":
        hh(s, out, 0.0, 0.03, 0.3)
        at = 0.022
    elif onset == "t":
        tclick(s, out, 0.0, 0.3)
        at = 0.008
    place(out, pk(hv(s, d, [(t * d, r) for t, r in F], [(0, v), (d, end)], [(0, 0), (0.01, 1), (d * 0.7, 0.85), (d, 0)], p, sc)), at, 1.0)
    if k % 3 == 0:
        tclick(s, out, at + d, 0.1, 400, 2500)       # lip closure
    return room(s, out, 0.3, 0.05, 7000)


def hero_hurt(s, k):
    p = HF0 * u(s, 0.97, 1.04)
    sc = HSC * u(s, 0.98, 1.02)
    out = buf(0.8)
    kw = dict(tilt=1.05, breath=0.22, jitter=0.01)
    if k == 0:     # "ow!"
        place(out, pk(hv(s, 0.17, [(0, 1.45), (0.04, 1.55), (0.17, 1.1)], [(0, "o"), (0.17, "u")], [(0, 0), (0.008, 1), (0.17, 0)], p, sc, **kw)), 0.0)
        hh(s, out, 0.16, 0.08, 0.2, 1600)
    elif k == 1:   # "ah-ah!"
        for j, at in enumerate((0.0, 0.13)):
            place(out, pk(hv(s, 0.08, [(0, 1.5 - 0.1 * j), (0.08, 1.3 - 0.1 * j)], "a", [(0, 0), (0.006, 1), (0.08, 0)], p, sc, **kw)), at, 1.0 - 0.25 * j)
    elif k == 2:   # "eek"
        place(out, pk(hv(s, 0.12, [(0, 1.65), (0.03, 1.8), (0.12, 1.55)], "i", [(0, 0), (0.006, 1), (0.12, 0)], p, sc, **kw)), 0.0)
    elif k == 3:   # "uh!" low and punchy
        place(out, pk(hv(s, 0.1, [(0, 1.15), (0.1, 0.95)], [(0, "eo"), (0.1, "eu")], [(0, 0), (0.005, 1), (0.07, 0.8), (0.1, 0)], p, sc, **kw)), 0.0)
        tclick(s, out, 0.1, 0.08, 300, 1500)
    elif k == 4:   # "agh" with rasp
        x = hv(s, 0.22, [(0, 1.4), (0.22, 1.05)], [(0, "a"), (0.22, "eo")], [(0, 0), (0.01, 1), (0.22, 0)], p, sc, **kw)
        x = x + snarl(s, 0.22, [(0, p * 1.4), (0.22, p * 1.05)], "a", [(0, 0), (0.01, 0.6), (0.22, 0)], sc, 2.5, 500, 6000) * 0.25
        place(out, pk(x), 0.0)
    elif k == 5:   # "ouch"
        place(out, pk(hv(s, 0.16, [(0, 1.5), (0.16, 1.15)], [(0, "a"), (0.08, "u")], [(0, 0), (0.01, 1), (0.16, 0.3)], p, sc, **kw)), 0.0)
        place(out, pk(burst(s, 0.08, 2500, 6500, 0.03, 0.005)), 0.15, 0.3)
    elif k == 6:   # "ngh" strained
        n = secs(0.2)
        x = hv(s, 0.2, [(0, 1.2), (0.2, 1.3)], [(0, "n"), (0.2, "eu")], [(0, 0), (0.03, 1), (0.2, 0)], p, sc, **kw) * (1 + 0.3 * np.sin(2 * np.pi * 14 * T(n)))
        place(out, pk(x), 0.0)
    else:          # "hyu!" i -> u up then down
        hh(s, out, 0.0, 0.03, 0.25)
        place(out, pk(hv(s, 0.18, [(0, 1.35), (0.06, 1.6), (0.18, 1.2)], [(0, "i"), (0.18, "u")], [(0, 0), (0.01, 1), (0.18, 0)], p, sc, **kw)), 0.02)
    return room(s, out, 0.3, 0.05, 7000)


def hero_harvest(s, k):
    p = HF0 * u(s, 0.97, 1.03)
    sc = HSC * u(s, 0.98, 1.02)
    out = buf(0.6)
    kw = dict(tilt=1.3, breath=0.15, fmax=7000)
    if k == 0:     # "hmph"
        place(out, pk(hv(s, 0.12, [(0, 1.0), (0.12, 0.92)], "m", [(0, 0), (0.02, 1), (0.12, 0)], p, sc, **kw)), 0.0)
        place(out, pk(burst(s, 0.06, 600, 3000, 0.02)), 0.11, 0.35)
    elif k == 1:   # "eh!"
        place(out, pk(hv(s, 0.09, [(0, 1.15), (0.09, 1.05)], "e", [(0, 0), (0.01, 1), (0.09, 0)], p, sc, **kw)), 0.0)
    elif k == 2:   # "hnn-ah"
        hh(s, out, 0.0, 0.03, 0.25, 1800)
        place(out, pk(hv(s, 0.1, [(0, 1.0), (0.1, 1.05)], "n", [(0, 0), (0.02, 1), (0.1, 0.4)], p, sc, **kw)), 0.02, 0.8)
        place(out, pk(hv(s, 0.1, [(0, 1.15), (0.1, 1.0)], "a", [(0, 0), (0.01, 1), (0.1, 0)], p, sc, **kw)), 0.13, 1.0)
    elif k == 3:   # "heu~" long falling
        hh(s, out, 0.0, 0.04, 0.3, 2000)
        place(out, pk(hv(s, 0.24, [(0, 1.12), (0.24, 0.88)], [(0, "eu"), (0.24, "u")], [(0, 0), (0.02, 1), (0.24, 0)], p, sc, **kw)), 0.03)
    elif k == 4:   # "ut!"
        place(out, pk(hv(s, 0.08, [(0, 1.05), (0.08, 1.12)], "u", [(0, 0), (0.008, 1), (0.08, 0)], p, sc, **kw)), 0.0)
        tclick(s, out, 0.085, 0.25)
    elif k == 5:   # "hah" breathy
        hh(s, out, 0.0, 0.06, 0.45, 1500)
        place(out, pk(hv(s, 0.13, [(0, 1.05), (0.13, 0.95)], "a", [(0, 0), (0.02, 0.8), (0.13, 0)], p, sc, tilt=1.3, breath=0.5)), 0.03)
    elif k == 6:   # "nng" strained rising
        place(out, pk(hv(s, 0.2, [(0, 0.95), (0.2, 1.2)], [(0, "n"), (0.2, "eu")], [(0, 0), (0.04, 1), (0.2, 0)], p, sc, **kw)), 0.0)
    else:          # "ho!"
        hh(s, out, 0.0, 0.025, 0.3, 2200)
        place(out, pk(hv(s, 0.1, [(0, 1.2), (0.1, 1.08)], "o", [(0, 0), (0.008, 1), (0.1, 0)], p, sc, **kw)), 0.018)
    return room(s, out, 0.3, 0.05, 7000)


def hero_eat(s, k):
    p = HF0 * u(s, 0.97, 1.03)
    sc = HSC * u(s, 0.98, 1.02)
    out = buf(0.9)
    kw = dict(tilt=1.5, breath=0.1, fmax=6000)
    if k == 0:     # "nom-nom"
        for j, at in enumerate((0.0, 0.17)):
            place(out, pk(hv(s, 0.13, [(0, 1.05 + 0.08 * j), (0.13, 1.0 + 0.08 * j)], [(0, "n"), (0.03, "o"), (0.1, "m"), (0.13, "m")], [(0, 0), (0.02, 1), (0.13, 0)], p, sc, **kw)), at)
    elif k == 1:   # "mmm-ah"
        place(out, pk(hv(s, 0.25, [(0, 1.0), (0.25, 1.15)], "m", [(0, 0), (0.04, 1), (0.25, 0.6)], p, sc, **kw)), 0.0, 0.8)
        place(out, pk(hv(s, 0.16, [(0, 1.25), (0.16, 1.05)], "a", [(0, 0.3), (0.02, 1), (0.16, 0)], p, sc, tilt=1.15, breath=0.15)), 0.24)
    elif k == 2:   # "yum!"
        place(out, pk(hv(s, 0.24, [(0, 1.15), (0.08, 1.35), (0.24, 1.25)], [(0, "i"), (0.06, "eo"), (0.16, "m"), (0.24, "m")], [(0, 0), (0.02, 1), (0.24, 0)], p, sc, **kw)), 0.0)
    elif k == 3:   # "mm-hm"
        place(out, pk(hv(s, 0.14, [(0, 1.1), (0.14, 0.95)], "m", [(0, 0), (0.03, 1), (0.14, 0)], p, sc, **kw)), 0.0)
        hh(s, out, 0.16, 0.03, 0.2, 1500)
        place(out, pk(hv(s, 0.18, [(0, 1.0), (0.18, 1.25)], "m", [(0, 0), (0.03, 1), (0.18, 0)], p, sc, **kw)), 0.18)
    else:          # "nyam" + chew clicks
        place(out, pk(hv(s, 0.2, [(0, 1.1), (0.2, 1.2)], [(0, "n"), (0.04, "a"), (0.15, "m"), (0.2, "m")], [(0, 0), (0.02, 1), (0.2, 0)], p, sc, **kw)), 0.0)
        for j in range(3):
            tclick(s, out, 0.26 + 0.09 * j, 0.12, 800, 3500)
    return room(s, out, 0.3, 0.05, 7000)


def hero_tired(s, k):
    p = HF0 * u(s, 0.97, 1.03)
    sc = HSC
    out = buf(1.4)
    pant = lambda at, d, g=1.0, voiced=0.5: (place(out, pk(breathy(s, d, [(0, 1500), (d, 1100)], [(0, 0), (0.04, 1), (d, 0)], 0.6)), at, 0.8 * g),  # noqa: E731
                                            place(out, pk(hv(s, d, [(0, 1.02), (d, 0.85)], "a", [(0, 0), (0.04, 0.35), (d, 0)], p, sc, tilt=1.4, breath=0.75)), at, voiced * g))
    if k == 0:     # three quick pants
        for j in range(3):
            pant(j * 0.22, 0.16, 1.0 - 0.15 * j)
    elif k == 1:   # long sigh
        pant(0.0, 0.7, 1.0, 0.6)
    elif k == 2:   # "hff... hff" unvoiced
        for j in range(2):
            place(out, pk(breathy(s, 0.2, [(0, 2200), (0.2, 1500)], [(0, 0), (0.02, 1), (0.2, 0)], 0.7)), j * 0.4, 0.9)
    elif k == 3:   # in-breath, then "huu..."
        place(out, pk(breathy(s, 0.18, [(0, 2400), (0.18, 2900)], [(0, 0), (0.12, 1), (0.18, 0)], 0.5)), 0.0, 0.5)
        place(out, pk(hv(s, 0.45, [(0, 1.0), (0.45, 0.8)], "u", [(0, 0), (0.05, 0.6), (0.45, 0)], p, sc, tilt=1.4, breath=0.6)), 0.25)
    else:          # pant pair + "phew"
        pant(0.0, 0.2)
        pant(0.3, 0.2, 0.8)
        place(out, pk(burst(s, 0.03, 500, 3000, 0.01)), 0.62, 0.3)
        place(out, pk(hv(s, 0.22, [(0, 1.15), (0.22, 0.9)], "eu", [(0, 0), (0.02, 0.8), (0.22, 0)], p, sc, tilt=1.3, breath=0.45)), 0.64)
    return room(s, out, 0.3, 0.05, 7000)


def hero_faint(s, k):
    p = HF0 * u(s, 0.97, 1.03)
    sc = HSC
    out = buf(1.4)
    if k == 0:     # "uuuh..."
        place(out, pk(hv(s, 0.8, [(0, 1.1), (0.8, 0.72)], [(0, "eo"), (0.4, "u"), (0.8, "u")], [(0, 0), (0.05, 1), (0.6, 0.5), (0.8, 0)], p, sc, tilt=1.25, breath=0.35, vib=(4.5, 0.02))), 0.0)
    elif k == 1:   # "oh no..."
        place(out, pk(hv(s, 0.22, [(0, 1.35), (0.22, 1.2)], "o", [(0, 0), (0.02, 1), (0.22, 0.2)], p, sc, tilt=1.2, breath=0.25)), 0.0)
        place(out, pk(hv(s, 0.55, [(0, 1.15), (0.55, 0.78)], [(0, "n"), (0.05, "o"), (0.55, "u")], [(0, 0), (0.05, 0.9), (0.55, 0)], p, sc, tilt=1.2, breath=0.3, vib=(5, 0.015))), 0.3)
    else:          # "mmh..." wobbly + sigh
        n = secs(0.6)
        place(out, pk(hv(s, 0.6, [(0, 1.05), (0.6, 0.8)], "m", [(0, 0), (0.06, 1), (0.6, 0)], p, sc, tilt=1.5, breath=0.2) * (1 + 0.25 * np.sin(2 * np.pi * 6 * T(n)))), 0.0)
        place(out, pk(breathy(s, 0.4, [(0, 1300), (0.4, 800)], [(0, 0.5), (0.4, 0)], 0.8)), 0.55, 0.4)
    return room(s, out, 0.3, 0.05, 7000)


def hero_attack_heavy(s, k):
    p = HF0 * u(s, 0.97, 1.03)
    sc = HSC * u(s, 0.98, 1.02)
    out = buf(0.7)
    if k == 0:     # "hiyaa!"
        hh(s, out, 0.0, 0.03, 0.3)
        place(out, pk(hv(s, 0.08, [(0, 1.2), (0.08, 1.3)], "i", [(0, 0), (0.01, 1), (0.08, 0.6)], p, sc)), 0.02, 0.8)
        place(out, pk(hv(s, 0.26, [(0, 1.35), (0.26, 1.05)], "a", [(0, 0.5), (0.02, 1), (0.26, 0)], p, sc)), 0.1)
    elif k == 1:   # "huaa!" rising
        hh(s, out, 0.0, 0.04, 0.35)
        place(out, pk(hv(s, 0.26, [(0, 1.0), (0.18, 1.38), (0.26, 1.3)], [(0, "u"), (0.08, "a"), (0.26, "a")], [(0, 0), (0.02, 1), (0.26, 0)], p, sc)), 0.03)
    elif k == 2:   # "yaap!"
        place(out, pk(hv(s, 0.2, [(0, 1.25), (0.2, 1.4)], [(0, "i"), (0.04, "a"), (0.2, "a")], [(0, 0), (0.01, 1), (0.18, 0.9), (0.2, 0)], p, sc)), 0.0)
        tclick(s, out, 0.2, 0.18, 400, 2500)
    elif k == 3:   # "hrraa" with rasp
        x = hv(s, 0.3, [(0, 1.1), (0.1, 1.3), (0.3, 1.1)], "a", [(0, 0), (0.02, 1), (0.3, 0)], p, sc)
        x = x + snarl(s, 0.3, [(0, p * 1.1), (0.3, p * 1.1)], "a", [(0, 0), (0.02, 0.8), (0.3, 0)], sc, 2.0, 400, 6000) * 0.3
        place(out, pk(x), 0.0)
    else:          # "toh!" falling
        tclick(s, out, 0.0, 0.35)
        place(out, pk(hv(s, 0.2, [(0, 1.45), (0.2, 1.05)], [(0, "o"), (0.2, "eo")], [(0, 0), (0.008, 1), (0.2, 0)], p, sc)), 0.008)
    return room(s, out, 0.3, 0.05, 7000)


def hero_pickup(s, k):
    p = HF0 * u(s, 0.97, 1.03)
    sc = HSC * u(s, 0.98, 1.02)
    out = buf(0.7)
    if k == 0:     # "ooh~"
        place(out, pk(hv(s, 0.3, [(0, 1.05), (0.3, 1.4)], [(0, "o"), (0.3, "u")], [(0, 0), (0.03, 1), (0.3, 0)], p, sc, vib=(6, 0.02))), 0.0)
    elif k == 1:   # "ah-ha!"
        place(out, pk(hv(s, 0.1, [(0, 1.15), (0.1, 1.1)], "a", [(0, 0), (0.01, 1), (0.1, 0)], p, sc)), 0.0, 0.8)
        hh(s, out, 0.12, 0.03, 0.3)
        place(out, pk(hv(s, 0.13, [(0, 1.3), (0.13, 1.45)], "a", [(0, 0), (0.01, 1), (0.13, 0)], p, sc)), 0.14)
    elif k == 2:   # "eh?" rising
        place(out, pk(hv(s, 0.16, [(0, 1.05), (0.16, 1.45)], "e", [(0, 0), (0.02, 1), (0.16, 0)], p, sc)), 0.0)
    elif k == 3:   # "yay"
        place(out, pk(hv(s, 0.26, [(0, 1.3), (0.12, 1.5), (0.26, 1.42)], [(0, "i"), (0.08, "a"), (0.26, "i")], [(0, 0), (0.02, 1), (0.26, 0)], p, sc)), 0.0)
    elif k == 4:   # "oh-oh" two pulses
        for j, at in enumerate((0.0, 0.14)):
            place(out, pk(hv(s, 0.1, [(0, 1.25 + 0.12 * j), (0.1, 1.3 + 0.12 * j)], "o", [(0, 0), (0.01, 1), (0.1, 0)], p, sc)), at, 1.0)
    else:          # "heh!"
        hh(s, out, 0.0, 0.04, 0.4)
        place(out, pk(hv(s, 0.09, [(0, 1.35), (0.09, 1.2)], "e", [(0, 0), (0.008, 1), (0.09, 0)], p, sc)), 0.03)
    return room(s, out, 0.3, 0.05, 7000)


def hero_dodge(s, k):
    p = HF0 * u(s, 0.97, 1.03)
    sc = HSC * u(s, 0.98, 1.02)
    out = buf(0.5)
    if k == 0:     # "hp" unvoiced
        hh(s, out, 0.0, 0.08, 0.7, 2000)
        tclick(s, out, 0.08, 0.25, 500, 2500)
    elif k == 1:   # "hup" rising
        hh(s, out, 0.0, 0.03, 0.3)
        place(out, pk(hv(s, 0.08, [(0, 1.1), (0.08, 1.35)], "u", [(0, 0), (0.01, 1), (0.08, 0)], p, sc)), 0.025)
    elif k == 2:   # "tsk"
        tclick(s, out, 0.0, 0.5)
        place(out, pk(high(s.noise(secs(0.09)), 4500) * ctl(secs(0.09), [(0, 0), (0.01, 1), (0.09, 0)])), 0.01, 0.5)
    elif k == 3:   # "hih"
        place(out, pk(hv(s, 0.07, [(0, 1.5), (0.07, 1.45)], "i", [(0, 0), (0.008, 1), (0.07, 0)], p, sc)), 0.0)
        hh(s, out, 0.06, 0.05, 0.3, 3000)
    else:          # "hhuh" breath + falling eo
        hh(s, out, 0.0, 0.07, 0.5, 1700)
        place(out, pk(hv(s, 0.09, [(0, 1.2), (0.09, 1.0)], "eo", [(0, 0), (0.01, 0.8), (0.09, 0)], p, sc)), 0.06)
    return room(s, out, 0.3, 0.05, 7000)


REWARD_RUNS = [((1046.5, 1318.5, 1568.0, 1760.0, 1568.0), 0.07), ((698.5, 880.0, 1046.5, 523.3, 784.0, 1046.5), 0.09),
               ((1174.7, 1480.0, 1760.0), 0.04), ((1568.0, 1318.5, 1174.7, 1318.5, 2093.0), 0.08)]


def hero_reward(s, k):
    notes, step = REWARD_RUNS[k % 4]
    out = buf(1.8)
    for j, f in enumerate(notes):
        place(out, pk(C.bell(s, f, 1.0, 0.55, 0.8)), j * step, 0.32 * (0.95 ** j))
    n = secs(0.8)
    up = k % 2 == 0
    place(out, tinkles(s, n, [30, 18, 45, 25][k], 4000, 10000, ctl(n, [(0, 0), (0.25, 1), (0.8, 0)] if up else [(0, 1), (0.8, 0)])), 0.1, 0.5)
    if k == 2:
        m = secs(0.6)
        place(out, pk(nsweep(s, m, ctl(m, [(0, 2500), (0.6, 8000)]), 0.4) * ctl(m, [(0, 0), (0.4, 1), (0.6, 0)])), 0.1, 0.2)
    return room(s, out, 0.8, 0.12, 7000)


LEVEL_RUNS = [((587.3, 740.0, 880.0, 1174.7, 1480.0), (587.3, 740.0, 880.0)),
              ((523.3, 587.3, 659.3, 740.0, 830.6, 932.3), (698.5, 880.0, 1046.5)),
              ((784.0, 1046.5), (523.3, 659.3, 784.0, 1046.5))]


def hero_levelup(s, k):
    run, chord = LEVEL_RUNS[k % 3]
    out = buf(2.2)
    step = [0.08, 0.055, 0.12][k]
    for j, f in enumerate(run):
        place(out, pk(C.bell(s, f, 1.3, 0.75, 0.8)), j * step, 0.3 * (0.94 ** j))
    at = len(run) * step + 0.05
    n = secs(1.0)
    ch = sum(glide(n, f, ((1, 1.0), (2, 0.2))) for f in chord) * ctl(n, [(0, 0), (0.15, 1), (1.0, 0)])
    place(out, pk(ch), at, 0.12)
    place(out, pk(nsweep(s, n, ctl(n, [(0, 2000), (1.0, 8000)] if k != 1 else [(0, 8000), (1.0, 3000)]), 0.4) * ctl(n, [(0, 0), (0.6, 1), (1.0, 0)])), at - 0.05, 0.18)
    place(out, tinkles(s, n, [35, 20, 50][k], 4000, 10000, ctl(n, [(0, 0), (0.5, 1), (1.0, 0)])), at, 0.5)
    return room(s, out, 1.0, 0.14, 7000)


# =============================================================================== registry
def R(*names):
    """Existing reference files of a family (their median st-rms is the target)."""
    return [p for n in names for p in sorted(COMBAT.glob(n))] if names else None


def _refs(d: Path, pattern: str):
    return sorted(p for p in d.glob("*.wav") if re.fullmatch(pattern, p.name))


def ref_of(d: Path, event: str):
    """Median st-rms of the git-tracked takes of <event> (bare + _<n>)."""
    files = [p for p in _refs(d, r"%s(_\d+)?\.wav" % re.escape(event)) if L.git_tracked(p)]
    return files


def families() -> list:
    F = []
    c = lambda ev, n, fn, sr=SR22, ref=None, md=None, **kw: F.append(Fam("combat", COMBAT, ev, n, fn, sr, ref if ref is not None else ref_of(COMBAT, ev), md, **kw))  # noqa: E731
    for w in ("axe", "spear", "fist"):
        c("swing_" + w, 12, swing(w), md=0.7)
        c("swing_%s_heavy" % w, 6, swing_heavy(w), md=0.95)
    c("hit_flesh", 10, hit_flesh, md=0.6)
    c("hit_stone", 10, hit_stone, SR32, md=0.9)
    c("hit_wood", 10, hit_wood, md=0.7)
    c("hit_spirit", 10, hit_spirit, SR32, md=1.2)
    c("block", 6, block, SR32, md=0.9)
    c("dodge", 8, dodge, md=0.8)
    c("critical", 5, critical, SR32, md=1.5)
    c("spawn", 6, spawn, md=1.7)
    c("dissolve", 6, dissolve, SR32, md=1.9)
    c("player_hit", 8, player_hit, md=0.7)
    c("fuel", 5, fuel, md=1.8)
    c("night", 3, night, md=2.25)
    c("dawn", 3, dawn, md=2.25)
    c("harvest_berry", 10, harvest_berry, md=0.6)
    c("harvest_tree", 11, harvest_tree, SR32, md=0.9)
    c("harvest_stone", 11, harvest_stone, SR32, md=1.2)
    c("harvest_fiber", 11, harvest_fiber, SR32, md=0.8)
    swing_ref = ref_of(COMBAT, "swing_axe")
    dodge_ref = ref_of(COMBAT, "dodge")
    fuel_ref = ref_of(COMBAT, "fuel")
    c("whiff", 6, whiff, ref=swing_ref, md=0.9)
    c("equip", 5, equip, ref=dodge_ref, md=0.6)
    c("sputter", 5, sputter, ref=fuel_ref, md=1.1)
    for kind in ("tree", "stone", "fiber", "berry"):
        c("depleted_" + kind, 3, depleted(kind), ref=fuel_ref, md=2.0)
    c("night_warn", 3, night_warn, ref=ref_of(COMBAT, "night"), md=2.2)
    c("cold", 4, cold, ref=dodge_ref, md=1.3)
    c("hunger", 4, hunger, ref=dodge_ref, md=1.3)
    c("ember", 4, ember, ref=dodge_ref, md=1.1)
    c("craft_tool", 4, craft_tool, ref=fuel_ref, md=1.2)
    c("craft_soup", 4, craft_soup, ref=fuel_ref, md=1.3)
    c("craft_bandage", 4, craft_bandage, ref=dodge_ref, md=1.0)
    c("bandage", 4, bandage, ref=dodge_ref, md=1.1)
    F.append(Fam("combat", COMBAT, "campfire_loop", 1, campfire_loop, SR22, [COMBAT / "heartbeat_loop.wav"], None, loop=True))
    h = lambda ev, n, fn, sr=SR22, md=None: F.append(Fam("hero", HERO, ev, n, fn, sr, ref_of(HERO, ev), md))  # noqa: E731
    h("attack", 10, hero_attack, md=0.5)
    h("hurt", 8, hero_hurt, md=0.7)
    h("harvest", 8, hero_harvest, md=0.5)
    h("eat", 5, hero_eat, md=0.8)
    h("tired", 5, hero_tired, md=1.3)
    h("faint", 3, hero_faint, md=1.4)
    h("levelup", 3, hero_levelup, SR32, md=2.2)
    h("attack_heavy", 5, hero_attack_heavy, md=0.6)
    h("pickup", 6, hero_pickup, md=0.6)
    h("dodge", 5, hero_dodge, md=0.5)
    h("reward", 4, hero_reward, SR32, md=1.8)
    try:
        import gen_combat_creatures as GC
        F += GC.families(Fam)
    except ImportError as e:  # pragma: no cover
        print("gen_combat: creatures module unavailable: %s" % e, file=sys.stderr)
    return F


# =============================================================================== runner
_TRACKED_CACHE: dict = {}


def tracked_names(d: Path) -> set:
    if d not in _TRACKED_CACHE:
        r = subprocess.run(["git", "ls-files", "--", str(d)], cwd=str(L.REPO), capture_output=True, text=True)
        _TRACKED_CACHE[d] = {Path(line).name for line in r.stdout.splitlines()}
    return _TRACKED_CACHE[d]


def start_of(f: Fam) -> int:
    if f.start is not None:
        return f.start
    pat = re.compile(r"%s_(\d+)\.wav$" % re.escape(f.event))
    nums = [int(m.group(1)) for name in tracked_names(f.dir) for m in [pat.fullmatch(name)] if m]
    return max(nums, default=0) + 1


def clean_stale(f: Fam, start: int, dry: bool) -> list:
    """Remove this generator's own (untracked) takes numbered past the new range."""
    pat = re.compile(r"%s_(\d+)\.wav$" % re.escape(f.event))
    gone = []
    for p in f.dir.glob("%s_*.wav" % f.event):
        m = pat.fullmatch(p.name)
        if m and int(m.group(1)) >= start + f.n and p.name not in tracked_names(f.dir):
            gone.append(p)
            if not dry:
                p.unlink()
    return gone


def ref_db(f: Fam):
    if f.ref is None:
        return None
    if isinstance(f.ref, (int, float)):
        return float(f.ref)
    if not f.ref:
        raise SystemExit("gen_combat: no reference file for %s/%s" % (f.dir.name, f.event))
    return L.ref_db_of(f.ref)


def render(f: Fam, dry: bool = False) -> list:
    target = ref_db(f)
    if f.loop:
        rng = np.random.default_rng(L.take_seed(f.event, 0, "gen_combat"))
        x = L.remove_dc(to_sr(f.fn(S(rng), 0), f.sr), f.sr, 30.0)
        cut = int(0.15 * f.sr)       # resampler / high-pass edge transients
        x = L.loopify(x[cut:-cut], f.sr, 0.2)
        path = f.dir / ("%s.wav" % f.event)
        if dry:
            return [{"name": path.stem, "bytes": 44 + 2 * x.size, "seconds": x.size / f.sr}]
        d = L.write_take(path, x, f.sr, ref_db=target, finish_kw={"loop": True})
        print(L.family_report([d]))
        return [d]
    start = start_of(f)
    clean_stale(f, start, dry)
    kw = dict(f.finish_kw)
    if f.max_dur:
        kw.setdefault("max_dur", f.max_dur)

    def fn(rng, i):
        return to_sr(f.fn(S(rng), i - start), f.sr)

    return L.make_family(f.dir, f.event, f.n, fn, sr=f.sr, ref_db=target, seed_base="gen_combat", start=start,
                         finish_kw=kw, dry_run=dry)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="groups: combat,hero,creatures,layers,steps")
    ap.add_argument("--family", default="", help="comma list of event names")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    groups = {g for g in a.only.split(",") if g}
    names = {g for g in a.family.split(",") if g}
    fams = [f for f in families() if (not groups or f.group in groups) and (not names or f.event in names)]
    if a.list:
        for f in fams:
            print("%-9s %-10s %-26s %3d takes from %d @ %d Hz" % (f.group, f.dir.name, f.event, f.n, start_of(f) if not f.loop else 0, f.sr))
        return 0
    total = 0
    for f in fams:
        print("== %s/%s" % (f.dir.name, f.event))
        meta = render(f, a.dry_run)
        total += sum(d["bytes"] for d in meta)
    print("gen_combat: %d families, %.2f MB of new takes" % (len(fams), total / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
