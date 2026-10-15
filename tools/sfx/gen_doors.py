"""gen_doors: three more takes of every room's door sounds (Villagen sound variety).

    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_doors.py                       # all rooms
    .tools\\art-venv\\Scripts\\python.exe tools\\sfx\\gen_doors.py --room 01_cafe --root <scratch>

The existing game/assets/sfx/doors/<room>_<open|close>.wav (tools/make_village_sfx.py, git-tracked)
stays as it is and is take 0; this writes <room>_<kind>_1..3.wav next to it. Each take is the same
door played another way: the latch is worked once, twice or fumbled, the hinge creak runs the other
way / stutters / drags, the door swings slower or faster, it bounces in its frame or is eased shut,
and the bells over the cafe, bakery, parlour and shop doors ring in another order and count. Every
take is levelled to the original's st-rms (120 ms, 150 Hz high-pass) so Transition.play_door keeps
its mix. 22050 Hz mono (the originals are 32 kHz; the doors carry little above 11 kHz).
Helpers come from tools/make_village_sfx.py (imported; its main() overwrites and is never run).
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
import make_village_sfx as V  # noqa: E402  (helpers only)

SR = L.DEFAULT_SR
TAKES = 3
SEED_BASE = "doors"
DOORS = L.SFX_ROOT / "doors"
ROOMS = V.ROOMS


def arr(x):
    return np.asarray(x, dtype=float)


class Kit:
    """make_village_sfx parts on one take's rng, at SR, plus the take's variant knobs."""

    def __init__(self, rng, v):
        V.SR = SR
        self.s = V.Synth(0)
        self.s.rng = rng
        self.rng = rng
        self.v = v            # 0, 1, 2: which way this take works the door
        self.out = np.zeros(L.secs(2.6, SR))
        self.p = V.door_parts(self.s)

    def at(self, sig, t, g=1.0):
        V.place(self.out, arr(sig), max(0.0, t), g)

    def pick(self, *choices):
        return choices[self.v % len(choices)]

    # ---- the knobs every room shares
    def latch(self, kind, f, g, t0=0.0):
        """Latch worked once (v0), rattled twice (v1) or fumbled: a slip, then the real click (v2)."""
        part = self.p[kind]
        if self.v == 0:
            self.at(part(f * 1.04, g), t0)
            return t0
        if self.v == 1:
            self.at(part(f, g), t0)
            self.at(part(f * 0.88, g * 0.6), t0 + self.rng.uniform(0.03, 0.045))
            self.at(part(f * 1.1, g * 0.35), t0 + self.rng.uniform(0.08, 0.1))
            return t0 + 0.06
        self.at(part(f * 0.92, g * 0.45), t0)
        self.at(part(f * 1.06, g), t0 + self.rng.uniform(0.12, 0.16))
        return t0 + 0.14

    def creak(self, length, f0, f1, g=1.0, t=0.0, **kw):
        """Hinge creak: reversed contour (v0), stuttering in grabs (v1), long low drag (v2)."""
        r = self.rng
        if self.v == 0:
            self.at(V.creak(self.s, length * r.uniform(0.9, 1.0), f1, f0, **kw), t, g)
        elif self.v == 1:
            n = 3
            for k in range(n):
                seg = length / n * r.uniform(0.75, 0.95)
                fa = f0 + (f1 - f0) * k / n
                fb = f0 + (f1 - f0) * (k + 1) / n
                self.at(V.creak(self.s, seg, fa * 1.05, fb * 1.05, **{**kw, "swell": 0.02, "release": seg * 0.4}), t + k * length / n, g * (1 - 0.12 * k))
        else:
            kw2 = dict(kw)
            kw2["wobble"] = kw.get("wobble", 9.0) * 0.5
            kw2["rough"] = kw.get("rough", 0.18) * 1.3
            self.at(V.creak(self.s, length * 1.35, f0 * 0.86, f1 * 0.8, **kw2), t, g * 0.9)

    def swing(self, length, g, t):
        self.at(self.p["swing"](length * self.pick(0.75, 1.0, 1.3), g), t)

    def shut(self, f0, length, tau, t, g=1.0, **kw):
        """Door meets the frame: one thud (v0), a thud and a bounce (v1), eased shut, softer (v2)."""
        if self.v == 2:
            self.at(V.thud(self.s, f0 * 1.1, length * 0.8, tau * 0.7, **kw), t + 0.08, g * 0.7)
            return t + 0.08
        self.at(V.thud(self.s, f0, length, tau, **kw), t, g)
        if self.v == 1:
            self.at(V.thud(self.s, f0 * 1.15, length * 0.6, tau * 0.6, **kw), t + self.rng.uniform(0.09, 0.12), g * 0.45)
        return t


def bell_order(k: Kit, notes, count):
    """Another order of the same bells for each take."""
    idx = list(range(len(notes)))
    k.rng.shuffle(idx)
    seq = [notes[idx[j % len(idx)]] for j in range(count)]
    return seq


def door_take(room: str, kind: str, v: int, rng) -> tuple:
    k = Kit(rng, v)
    s, p, r = k.s, k.p, rng
    rt, wet, early, tone = 0.3, 0.12, (), 5000
    if room == "home":
        rt, wet = 0.35, 0.13
        if kind == "open":
            t = k.latch("metal_latch", 2100, 0.55)
            k.creak(0.55, 230, 330, 0.9, t + 0.07, rough=0.14)
            k.swing(0.45, 0.25, t + 0.12)
        else:
            if v == 0:   # latch held down while the door is pulled to, then let go
                k.at(p["metal_latch"](2300, 0.5), 0.0)
                k.at(V.thud(s, 98, 0.3, 0.05), 0.12)
                k.at(p["metal_latch"](1950, 0.65), 0.38)
            else:
                k.swing(0.25, 0.3, 0.0)
                t = k.shut(92, 0.32, 0.06, 0.2)
                k.latch("metal_latch", 2200, 0.6, t + 0.015)
    elif room == "workshop":
        rt, wet, tone = 0.95, 0.24, 3800
        ring = lambda f, g: V.modal([f, f * 1.59, f * 2.55, f * 3.68], [0.09, 0.07, 0.05, 0.03], [1, .6, .4, .2], 0.3, s.rng) * g
        if kind == "open":
            k.at(ring(k.pick(700, 860, 780), 0.7), 0.0)
            if v == 1:
                k.at(ring(820, 0.45), 0.09)           # the iron ring knocks twice
            k.at(V.click(s, 0.05, 700, 3000, 0.006), 0.0, 0.6)
            k.creak(0.85, 125, 190, 1.0, 0.08, body=(140, 330, 610, 1100, 1900), rough=0.2)
            if v != 1:
                k.at(V.creak(s, 0.7 * k.pick(0.8, 1, 1.2), 150, 215, body=(160, 360, 680, 1250), rough=0.22), k.pick(0.45, 0.3, 0.2), 0.75)
            k.swing(0.8, 0.35, 0.15)
        else:
            k.swing(0.35, 0.35, 0.0)
            t = k.shut(68, 0.45, 0.1, 0.22, body=1.2)
            if v != 2:
                k.at(V.thud(s, 74, 0.4, 0.09, body=1.0), t + k.pick(0.07, 0.2, 0.12), 0.85)   # second leaf
            k.at(ring(780, 0.45), t + 0.14)
    elif room == "01_cafe":
        rt, wet = 0.4, 0.14
        notes = [1046.5, 1318.5, 1568.0, 1760.0, 2093.0]
        if kind == "open":
            t = k.latch("metal_latch", 2400, 0.45)
            k.creak(0.35, 260, 320, 0.5, t + 0.05, rough=0.12)
            count = k.pick(4, 3, 5)
            gap = k.pick(0.07, 0.16, 0.09)
            for j, f in enumerate(bell_order(k, k.pick(notes[:3], notes[1:4], notes[2:]), count)):
                k.at(V.tube(s, f, 1.4, 0.85), t + 0.07 + j * gap + r.uniform(0, 0.02), 0.32 * (0.9 ** j))
        else:
            t = k.shut(95, 0.3, 0.055, 0.0, 0.85)
            k.latch("metal_latch", 2300, 0.45, t + 0.012)
            for j, f in enumerate(bell_order(k, notes, k.pick(2, 5, 3))):
                k.at(V.tube(s, f, 1.1, 0.7), t + 0.03 + j * k.pick(0.09, 0.05, 0.12), 0.22 * (0.85 ** j))
    elif room == "02_timber_house":
        rt, wet = 0.32, 0.12
        if kind == "open":
            t = k.latch("wood_latch", 640, 1.0)
            k.creak(0.6, 165, 255, 1.0, t + 0.1, body=(170, 380, 700, 1250, 2100), rough=0.25)
            k.swing(0.5, 0.3, t + 0.14)
        else:
            k.swing(0.22, 0.3, 0.0)
            t = k.shut(80, 0.35, 0.07, 0.17, grit=0.5)
            k.latch("wood_latch", 600, 0.9, t + 0.02)
    elif room == "03_teal_cottage":
        rt, wet = 0.3, 0.11
        hollow = [620, 740, 830, 990, 1110]
        if kind == "open":
            t = k.latch("metal_latch", 2500, 0.4)
            k.creak(0.3, 280, 340, 0.45, t + 0.04, rough=0.1)
            for j in range(k.pick(5, 9, 4)):
                f = r.choice(hollow)
                k.at(V.wood_block(s, f, 0.3, 0.07), t + 0.08 + j * k.pick(0.07, 0.045, 0.1) + r.uniform(0, 0.03), 0.35 * (0.85 ** j))
        else:
            first = 0.0 if v != 0 else 0.22
            if v == 0:
                for j in range(3):
                    k.at(V.wood_block(s, r.choice(hollow[2:]), 0.3, 0.07), j * 0.06, 0.26 * (0.85 ** j))
            t = k.shut(100, 0.28, 0.05, first, 0.8)
            for j in range(k.pick(1, 6, 2)):
                k.at(V.wood_block(s, r.choice(hollow[:4]), 0.3, 0.07), t + 0.04 + j * k.pick(0.09, 0.055, 0.12), 0.28 * (0.8 ** j))
    elif room == "04_windmill":
        rt, wet, tone = 0.6, 0.18, 3500
        if kind == "open":
            t = k.latch("wood_latch", 430, 1.0)
            k.creak(1.0, 105, 160, 1.0, t + 0.15, body=(120, 280, 520, 980, 1700), rough=0.28, wobble=5.0)
            k.at(V.wind(s, k.pick(1.1, 1.45, 1.7), 260, 1300, k.pick(0.2, 0.35, 0.6), 0.7), k.pick(0.0, 0.1, 0.3), k.pick(0.55, 0.35, 0.45))
        else:
            k.at(V.wind(s, k.pick(0.4, 0.7, 0.55), 260, 1300, 0.08, 0.35), 0.0, k.pick(0.5, 0.3, 0.4))
            t = k.shut(70, 0.45, 0.1, 0.2, body=1.2, grit=0.5)
            k.latch("wood_latch", 400, 1.0, t + 0.13)
    elif room == "05_observatory":
        rt, wet, tone = 0.7, 0.16, 6000
        ring = lambda g, f=420: V.modal([f, f * 2.7, f * 4.88, f * 7.71], [0.5, 0.35, 0.22, 0.14], [0.6, 0.45, 0.3, 0.15], 1.0, s.rng) * g
        clunk = lambda f: V.modal([f, f * 2.45, f * 4.9], [0.05, 0.035, 0.02], [1, .6, .3], 0.2, s.rng) + V.click(s, 0.2, 600, 4000, 0.004)
        if kind == "open":
            hiss_at = k.pick(0.0, 0.16, 0.06)
            clunk_at = k.pick(0.3, 0.0, 0.0)
            k.at(clunk(k.pick(280, 340, 300)), clunk_at, 0.9)
            if v == 1:
                k.at(clunk(360), 0.11, 0.6)
            k.at(V.hiss(s, k.pick(0.35, 0.75, 1.0), 1800, k.pick(0.01, 0.02, 0.08), k.pick(0.1, 0.22, 0.35)), hiss_at, 0.55)
            k.at(ring(0.3, k.pick(350, 470, 520)), clunk_at + 0.02)
            k.creak(0.4, 330, 410, 0.25, 0.25, body=(420, 1135, 2050), q=12, rough=0.08, metal=True)
        else:
            k.at(V.hiss(s, k.pick(0.25, 0.35, 0.5), 2400, 0.01, k.pick(0.06, 0.09, 0.15)), 0.0, 0.5)
            t = k.shut(78, 0.3, 0.05, 0.16, 0.85, grit=0.25)
            k.at(clunk(k.pick(330, 310, 290)), t + 0.005, 0.8)
            k.at(ring(0.35, k.pick(360, 480, 520)), t + 0.005)
            if v == 2:   # the seal settles: a second short release of air
                k.at(V.hiss(s, 0.3, 3000, 0.01, 0.08), t + 0.45, 0.35)
    elif room == "06_orange_cottage":
        rt, wet = 0.34, 0.12
        if kind == "open":
            t = k.latch("metal_latch", 2150, 0.45)
            k.creak(0.4, 240, 300, 0.55, t + 0.05, rough=0.12)
            if v == 0:     # shaken: a quick tremolo of the clapper
                for j in range(10):
                    k.at(V.bell(s, 1175, 0.9, decay=0.35, bright=1.5), t + 0.08 + j * 0.032, 0.3 * 0.9 ** j)
            elif v == 1:   # the bell and its little partner bell answer each other
                for j, (f, g) in enumerate([(1175, 0.4), (1480, 0.32), (1175, 0.22), (1480, 0.15)]):
                    k.at(V.bell(s, f, 1.2, decay=0.7, bright=0.6), t + 0.08 + j * 0.15, g)
            else:          # caught by hand: one short tunk
                k.at(V.bell(s, 1175, 0.6, decay=0.18, bright=0.4), t + 0.1, 0.5)
                k.at(V.thud(s, 160, 0.1, 0.02, grit=0.3), t + 0.11, 0.2)
        else:
            t = k.shut(95, 0.3, 0.055, 0.0 if v != 2 else 0.24, 0.85)
            k.latch("metal_latch", 2200, 0.45, t + 0.012)
            if v == 0:
                k.at(V.bell(s, 1175, 0.6, decay=0.2, bright=0.4), t + 0.03, 0.4)
            elif v == 1:
                for j, f in enumerate([1480, 1175]):
                    k.at(V.bell(s, f, 1.0, decay=0.6, bright=0.5), t + 0.03 + j * 0.12, 0.26 * 0.75 ** j)
            else:          # the swinging door knocks the bell before it shuts
                k.at(V.bell(s, 1175, 1.0, decay=0.6, bright=0.9), 0.0, 0.3)
                k.at(V.bell(s, 1175, 0.9, decay=0.45, bright=0.7), 0.11, 0.18)
    elif room == "07_greenhouse":
        rt, wet, tone = 0.45, 0.14, 7000
        pane = [0.84, 1.14, 1.3][v % 3]
        glass = lambda g: V.modal([2630 * pane, 4120 * pane, 6310 * pane, 8120 * pane], [0.18, 0.12, 0.08, 0.05], [0.5, 0.4, 0.25, 0.12], 0.6, s.rng) * g
        if kind == "open":
            k.at(V.click(s, 0.04, 1500, 6000, 0.004), 0.0, 0.5)
            slide = k.pick(0.45, 0.62, 0.85)
            if v == 1:   # sticks halfway, then runs on
                k.at(V.rumble(s, 0.3, 70, 340, 8), 0.03, 0.9)
                k.at(glass(0.15), 0.33)
                k.at(V.rumble(s, 0.35, 70, 340, 9), 0.42, 0.9)
                end = 0.79
            else:
                k.at(V.rumble(s, slide, 70, 340, int(slide * 26)), 0.03, 0.9)
                end = slide + 0.03
            k.at(V.thud(s, 140, 0.18, 0.025, grit=0.3), end, 0.45)
            k.at(glass(k.pick(0.2, 0.25, 0.12)), end + 0.005)
        else:
            slide = k.pick(0.35, 0.5, 0.7)
            if v == 1:   # sticks, then is pushed home
                k.at(V.rumble(s, 0.3, 70, 340, 8), 0.0, 0.9)
                k.at(V.rumble(s, 0.28, 90, 380, 7), 0.42, 0.9)
                slide = 0.7
            else:
                k.at(V.rumble(s, slide, 70, 340, int(slide * 26)), 0.0, 0.9)
            t = k.shut(120, 0.22, 0.03, slide, 0.6, grit=0.35)
            k.at(glass(0.3), t + 0.005)
            k.at(V.click(s, 0.04, 1500, 6000, 0.004), t + 0.06, 0.4)
    elif room == "11_purple_house":
        rt, wet = 0.42, 0.14
        pair = k.pick((523.3, 659.3), (659.3, 784.0, 523.3), (784.0, 659.3))
        if kind == "open":
            t = k.latch("metal_latch", 2250, 0.5)
            k.creak(0.4, 250, 310, 0.45, t + 0.05, rough=0.12)
            for j, f in enumerate(pair):
                k.at(V.tube(s, f, 1.4, 0.95), t + 0.06 + j * k.pick(0.36, 0.25, 0.42), 0.45)
        else:
            t = k.shut(92, 0.3, 0.055, 0.0, 0.85)
            k.latch("metal_latch", 2250, 0.5, t + 0.012)
            closing = k.pick((659.3,), (784.0, 523.3), (392.0,))
            for j, f in enumerate(closing):
                k.at(V.tube(s, f, 1.2, 0.7), t + 0.04 + j * 0.16, 0.22 * 0.7 ** j)
    elif room == "12_blue_house":
        rt, wet = 0.28, 0.1
        if kind == "open":
            t = k.latch("metal_latch", 2600, 0.4)
            k.creak(0.35, 300, 370, 0.35, t + 0.1, rough=0.09)
            k.swing(0.4, 0.2, t + 0.1)
        else:
            k.swing(0.3, 0.3, 0.0)
            t = k.shut(110, 0.18, 0.035, 0.24, 0.5, grit=0.2)
            k.latch("metal_latch", 2600, 0.45, t + 0.01)
    elif room == "13_shop":
        rt, wet = 0.36, 0.12
        hits = k.pick([0.0, 0.1], [0.0, 0.15, 0.27, 0.36, 0.43, 0.48, 0.52, 0.55], [0.0, 0.09, 0.2, 0.28, 0.4])
        decay = k.pick(0.22, 0.5, 0.7)
        bells = k.pick((2210,), (2210,), (2210, 2630))
        boing = lambda d: V.modal([170, 340], [d * 0.4, d * 0.25], [1, .4], d, s.rng) * (1 + 0.5 * np.sin(np.linspace(0, 2 * np.pi * 7 * d, V.secs(d))))
        if v == 1:
            decay = 0.35
        if kind == "open":
            t = k.latch("metal_latch", 2300, 0.4)
            if v == 1:
                k.at(boing(0.8), t + 0.04, 0.5)
            for j, at in enumerate(hits):
                k.at(V.bell(s, bells[j % len(bells)], 1.1, decay=decay, bright=k.pick(0.6, 1.3, 0.9)), t + 0.05 + at, 0.48 * (0.75 ** j))
            k.creak(0.3, 260, 320, 0.3, t + 0.06, rough=0.1)
        else:
            t = k.shut(96, 0.3, 0.055, 0.0, 0.8)
            if v == 1:
                k.at(boing(0.7), t + 0.02, 0.5)
            for j, at in enumerate(hits[: k.pick(1, 7, 3)]):
                k.at(V.bell(s, bells[j % len(bells)], 1.0, decay=decay), t + 0.02 + at, 0.4 * (0.72 ** j))
    elif room == "16_blue_cottage":
        rt, wet = 0.33, 0.12
        if kind == "open":
            t = k.latch("wood_latch", 700, 0.8)
            k.creak(0.5, 200, 280, 0.8, t + 0.06, rough=0.18)
            k.at(V.low(V.crackle(s, k.pick(0.8, 1.1, 1.3), k.pick(22, 40, 30)), 5000), k.pick(0.35, 0.2, 0.45), 0.55)
            if v == 2:
                k.at(V.thud(s, 60, 0.3, 0.07, grit=0.6), 0.75, 0.3)   # a log settles in the hearth
        else:
            if v == 0:
                t = k.shut(72, 0.4, 0.08, 0.0, grit=0.6)
                k.latch("wood_latch", 600, 0.8, t + 0.03)
                k.at(V.low(V.crackle(s, 0.9, 45, 0.1), 4000), 0.15, 0.7)
            else:
                k.at(V.low(V.crackle(s, k.pick(0.3, 0.6, 0.45), k.pick(20, 34, 26)), 2200), 0.0, 0.45)
                t = k.shut(88, 0.32, 0.06, k.pick(0.08, 0.16, 0.12))
                k.latch("wood_latch", 680, 0.8, t + 0.015)
    elif room == "17_lighthouse":
        rt, wet, tone = 1.5, 0.3, 3000
        early = k.pick(((0.06, 0.3), (0.13, 0.2), (0.21, 0.13)), ((0.09, 0.26), (0.18, 0.18), (0.3, 0.12), (0.45, 0.07)),
                       ((0.07, 0.28), (0.16, 0.2), (0.27, 0.12)))
        iron = lambda g, f=345: V.modal([f, f * 2.52, f * 4.29, f * 6.7, f * 9.1], [0.35, 0.22, 0.14, 0.09, 0.05],
                                        [1, .7, .45, .25, .12], 1.0, s.rng) * g
        if kind == "open":
            if v == 0:     # the bolt is drawn: three short iron scrapes, then the door
                for j in range(3):
                    k.at(iron(0.4, 520 + 40 * j) + V.click(s, 0.3, 900, 5000, 0.004) * 0.6, j * 0.09)
                k.creak(0.7, 72, 104, 0.9, 0.3, body=(110, 250, 520, 980), q=9, rough=0.22, metal=True)
            elif v == 1:   # two heavy pulls
                k.at(iron(0.7, 380) + V.click(s, 1.0, 900, 5000, 0.005) * 0.8, 0.0)
                k.at(iron(0.45, 470), 0.12)
                k.creak(0.9, 72, 104, 1.0, 0.25, body=(110, 250, 520, 980), q=9, rough=0.22, metal=True)
            else:          # unbolted: the door swings and its ring knocks the wall
                k.creak(0.6, 72, 104, 1.0, 0.0, body=(110, 250, 520, 980), q=9, rough=0.22, metal=True)
                k.at(iron(0.6, 300) + V.click(s, 0.5, 900, 5000, 0.004) * 0.6, 0.62)
            k.swing(0.7, 0.3, 0.15)
        else:
            if v == 2:     # pulled to slowly against its weight
                k.creak(0.5, 104, 80, 0.8, 0.0, body=(110, 250, 520, 980), q=9, rough=0.22, metal=True)
                t = 0.5
                k.at(V.thud(s, 62, 0.4, 0.1, body=1.0, grit=0.4), t, 0.7)
            else:
                k.swing(0.3, 0.35, 0.0)
                t = k.shut(58, 0.5, 0.12, 0.2, body=1.3, grit=0.5)
            k.at(iron(0.55, k.pick(300, 360, 390)), t + 0.005)
            if v == 0:     # the bolt shot home
                for j in range(2):
                    k.at(iron(0.35, 520 - 40 * j) + V.click(s, 0.3, 900, 5000, 0.004), t + 0.25 + j * 0.08)
            else:
                k.at(iron(0.35, 410) + V.click(s, 1.0, 900, 5000, 0.004), t + k.pick(0.12, 0.2, 0.3))
    else:
        raise KeyError(room)
    out = V.reverb(s, k.out, rt, wet, 0.01, tone, early)
    return out


def cap(x, max_s=1.8, fade=0.35):
    n = L.secs(max_s, SR)
    if x.size <= n:
        return x
    y = x[:n].copy()
    k = L.secs(fade, SR)
    y[n - k:] *= np.cos(0.5 * np.pi * np.arange(k) / k) ** 2
    return y


def run(root: Path, rooms, quiet=False) -> list:
    metas = []
    for room in rooms:
        for kind in ("open", "close"):
            original = DOORS / ("%s_%s.wav" % (room, kind))
            ref = L.ref_db_of(original)
            fn = (lambda rm, kd: (lambda rng, i: (cap(door_take(rm, kd, i - 1, rng)), {"variant": i - 1})))(room, kind)
            meta = L.make_family(root / "doors", "%s_%s" % (room, kind), TAKES, fn, sr=SR, ref_db=ref, seed_base=SEED_BASE,
                                 verbose=not quiet)
            metas.extend(meta)
    return metas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--room", help="comma list of rooms (default: all of make_village_sfx.ROOMS)")
    ap.add_argument("--root", help="output root instead of game/assets/sfx (trial runs in scratch)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    rooms = args.room.split(",") if args.room else ROOMS
    root = Path(args.root) if args.root else L.SFX_ROOT
    metas = run(root, rooms, args.quiet)
    total = sum(m["bytes"] for m in metas)
    print("gen_doors: %d files, %.1f KB (%.2f MB) under %s" % (len(metas), total / 1024.0, total / 1048576.0, root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
