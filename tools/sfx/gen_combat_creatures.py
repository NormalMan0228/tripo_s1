"""Monster take families for gen_combat.py: region-neutral voices per species x event, region colour
layers (played under them at runtime), locomotion steps, and the boar's charge / dazed cues.

  creatures/<species>_<event>_<n>.wav          7 structurally different takes per species x event
  creatures/layer_<region>_<accent|bed>_<n>.wav forest moss/twigs, quarry embers, frost ice
  creatures/step_<paw|hoof|stomp|squelch|flutter>_<n>.wav
  creatures/boar_charge_<n>.wav, boar_dazed_<n>.wav

Each take is one archetype (k % 7 for the voices) with its own count of calls, contour, length and
extra layer, built from the make_creature_sfx.py helpers (vocal formant voice, snarl, breathy noise,
thud, debris, flame, bloop ...). Levels follow make_creature_sfx.CREATURE_DB.
"""
from __future__ import annotations

import numpy as np

from gen_combat_kit import (C, L, SR, SR22, V, band, bloop, breathy, buf, burst, click, ctl, debris, fire, glide,  # noqa: F401
                            high, low, modal, norm, nsweep, pk, place, pops, rel, rock, room, rustle, scrape, secs,
                            shaped, snarl, thud, tinkles, tok, u, vocal, T)

CREAT = L.SFX_ROOT / "creatures"
TAKES = 7
EVENT_DB = dict(C.CREATURE_DB)            # idle -21, alert -16.5, windup -17.5, strike -16, hurt -17, death -16.5
MAX_LEN = dict(C.MAX_LEN)
MAX_LEN["death"] = 1.95


def P(s):
    return u(s, 0.97, 1.03)


# =============================================================================== wolf
def wolf_parts(s):
    def sniff(d=0.09, f=(2600, 3500)):
        return pk(breathy(s, d, [(0, f[0]), (d, f[1])], [(0, 0), (0.015, 1), (d * 0.55, 0.7), (d, 0)], 0.45))

    def growl(d, f0a, f0b, va="eu", vb="o", g_snarl=0.3, flutter=0.4):
        x = vocal(s, d, [(0, f0a), (d * 0.5, (f0a + f0b) * 0.55), (d, f0b)], [(0, va), (d, vb)], [(0, 0), (d * 0.15, 0.8), (d * 0.7, 0.9), (d, 0)],
                  0.8, tilt=1.1, breath=0.25, sub=0.35, flutter=flutter, fmax=5000)
        x = x + snarl(s, d, [(0, f0a), (d, f0b)], va, [(0, 0), (d * 0.25, 0.6), (d, 0)], 0.8, 4) * g_snarl
        return pk(x)

    def bark(f, d=0.15):
        f0 = [(0, f * 0.7), (0.035, f), (d, f * 0.58)]
        return pk(vocal(s, d, f0, [(0, "eu"), (0.04, "a"), (d, "o")], [(0, 0), (0.012, 1), (0.08, 0.8), (d, 0)], 0.88, tilt=0.9, breath=0.15, sub=0.25, fmax=6500)
                  + snarl(s, d, f0, "a", [(0, 0), (0.01, 1), (d, 0)], 0.88, 2.5, 400, 6000) * 0.45)

    def howl(d, pts, vowels=((0, "u"), (0.3, "o"), (0.75, "o"), (1.0, "u"))):
        return pk(vocal(s, d, [(t * d, f) for t, f in pts], [(t * d, v) for t, v in vowels], [(0, 0), (0.08, 0.9), (d * 0.6, 1.0), (d, 0)], 0.92,
                        tilt=1.25, breath=0.28, vib=(5.5, 0.012), fmax=6000))

    def whine(d, pts):
        return pk(vocal(s, d, [(t * d, f) for t, f in pts], [(0, "i"), (d, "u")], [(0, 0), (0.03, 1), (d * 0.7, 0.7), (d, 0)], 1.0, tilt=1.1, breath=0.3, vib=(7, 0.02), fmax=7000))

    def yelp(f, d=0.2, vowels=("i", "a", "u")):
        f0 = [(0, f * 0.7), (0.03, f), (d, f * 0.57)]
        return pk(vocal(s, d, f0, [(0, vowels[0]), (d * 0.4, vowels[1]), (d, vowels[2])], [(0, 0), (0.01, 1), (d * 0.4, 0.9), (d, 0)], 1.0, tilt=1.0, breath=0.2, fmax=8000))

    def snap(f=1750):
        return pk(np.asarray(modal([f, f * 1.66, f * 2.4], [0.012, 0.008, 0.005], [1, 0.6, 0.35], 0.08, s.rng)) + click(s, 0.03, 2000, 9000, 0.0015))

    def under(d, pts, fc=170):
        return pk(C.shadow_under(s, d, pts, fc))

    return sniff, growl, bark, howl, whine, yelp, snap, under


def wolf(s, ev, k):
    p = P(s)
    sniff, growl, bark, howl, whine, yelp, snap, under = wolf_parts(s)
    a = k % TAKES
    if ev == "idle":
        out = buf(1.4)
        if a == 0:     # two sniffs, long growl
            for at in (0.0, 0.14):
                place(out, sniff(), at + u(s, 0, 0.02), 0.5)
            place(out, growl(0.75, 80 * p, 72 * p), 0.32, 0.8)
        elif a == 1:   # three pants, growl tail
            for j in range(3):
                place(out, pk(breathy(s, 0.13, [(0, 1500), (0.13, 1100)], [(0, 0), (0.02, 1), (0.13, 0)], 0.6)), j * 0.2, 0.6)
                place(out, pk(vocal(s, 0.1, [(0, 180 * p), (0.1, 150 * p)], "a", [(0, 0), (0.02, 0.5), (0.1, 0)], 0.85, breath=0.7)), j * 0.2, 0.3)
            place(out, growl(0.4, 76 * p, 70 * p), 0.7, 0.55)
        elif a == 2:   # rising-falling growl, snort
            place(out, growl(0.95, 74 * p, 68 * p, "o", "eu", 0.45, 0.6), 0.0, 0.85)
            place(out, sniff(0.12, (1800, 1200)), 1.0, 0.45)
        elif a == 3:   # soft whine + sniff
            place(out, whine(0.55, [(0, 560 * p), (0.4, 640 * p), (1, 470 * p)]), 0.0, 0.6)
            place(out, sniff(0.08), 0.62, 0.4)
            place(out, sniff(0.08), 0.75, 0.35)
        elif a == 4:   # four quick sniffs + huff
            for j in range(4):
                place(out, sniff(0.06, (2900, 3600)), j * 0.09 + u(s, 0, 0.015), 0.45)
            place(out, pk(breathy(s, 0.22, [(0, 900), (0.22, 600)], [(0, 0), (0.02, 1), (0.22, 0)], 0.8)), 0.45, 0.6)
        elif a == 5:   # chuff + wobbling growl
            place(out, pk(breathy(s, 0.1, [(0, 1100), (0.1, 800)], [(0, 0), (0.008, 1), (0.1, 0)], 0.7)), 0.0, 0.6)
            n = secs(0.6)
            place(out, growl(0.6, 86 * p, 78 * p) * (1 + 0.3 * np.sin(2 * np.pi * 9 * T(n))), 0.15, 0.7)
        else:          # low yawn "aouh" + teeth click
            place(out, pk(vocal(s, 0.7, [(0, 120 * p), (0.3, 170 * p), (0.7, 95 * p)], [(0, "a"), (0.35, "o"), (0.7, "u")], [(0, 0), (0.15, 0.8), (0.7, 0)], 0.85, breath=0.45, fmax=5000)), 0.0, 0.7)
            place(out, snap(1500) * 0.5, 0.75, 0.4)
        place(out, under(1.2, [(0, 0), (0.4, 0.2), (1.2, 0)]), 0.0, 0.2)
        return out
    if ev == "alert":
        out = buf(1.5)
        if a == 0:     # long rising howl
            place(out, howl(1.1, [(0, 300 * p), (0.2, 480 * p), (0.7, 520 * p), (1, 380 * p)]), 0.0)
        elif a == 1:   # three barks
            for j, at in enumerate((0.0, 0.2, 0.42)):
                place(out, bark(410 * p * (1 - 0.05 * j)), at, 1.0 - 0.12 * j)
        elif a == 2:   # bark + falling howl
            place(out, bark(430 * p), 0.0)
            place(out, howl(0.8, [(0, 520 * p), (0.3, 540 * p), (1, 330 * p)]), 0.22, 0.9)
        elif a == 3:   # growl -> bark -> snap
            place(out, growl(0.45, 90 * p, 110 * p), 0.0, 0.7)
            place(out, bark(380 * p, 0.18), 0.42)
            place(out, snap(), 0.66, 0.7)
        elif a == 4:   # short yip-howl (two-step pitch)
            place(out, howl(0.75, [(0, 420 * p), (0.25, 600 * p), (0.45, 600 * p), (0.55, 470 * p), (1, 450 * p)], ((0, "o"), (1.0, "u"))), 0.0)
        elif a == 5:   # one big bark + growl
            place(out, bark(360 * p, 0.2), 0.0)
            place(out, growl(0.55, 96 * p, 82 * p, "e", "eu"), 0.3, 0.65)
        else:          # sniff, then a low questioning howl
            place(out, sniff(), 0.0, 0.4)
            place(out, howl(0.9, [(0, 260 * p), (0.5, 330 * p), (1, 300 * p)], ((0, "o"), (0.5, "u"), (1.0, "u"))), 0.15)
        place(out, under(1.2, [(0, 0), (0.3, 0.35), (1.2, 0)]), 0.0, 0.2)
        return out
    if ev == "windup":     # server wind-up 0.6 s
        out = buf(0.85)
        d = 0.6 * [1.0, 0.92, 1.08, 1.0, 0.95, 1.05, 1.0][a]
        if a == 0:     # rising snarl to a sharp intake
            place(out, growl(d, 88 * p, 140 * p, "eu", "ae", 0.6), 0.0)
            place(out, pk(breathy(s, 0.09, [(0, 2200), (0.09, 3200)], [(0, 0), (0.04, 1), (0.09, 0)], 0.5)), d - 0.05, 0.45)
        elif a == 1:   # snarl + teeth clack
            place(out, growl(d, 100 * p, 120 * p, "e", "ae", 0.8), 0.0)
            place(out, snap(1600) * 0.6, d * 0.45, 0.45)
            place(out, snap(1700) * 0.6, d * 0.78, 0.55)
        elif a == 2:   # stuttered growl: three bursts, rising
            for j in range(3):
                place(out, growl(d * 0.28, (84 + 18 * j) * p, (92 + 18 * j) * p, "eu", "a", 0.5), j * d * 0.33, 0.7 + 0.15 * j)
        elif a == 3:   # deep rumble, then intake
            place(out, growl(d * 0.8, 66 * p, 82 * p, "o", "eu", 0.35, 0.7), 0.0, 0.9)
            place(out, pk(breathy(s, 0.15, [(0, 1800), (0.15, 3000)], [(0, 0), (0.12, 1), (0.15, 0)], 0.5)), d * 0.78, 0.55)
        elif a == 4:   # high whine-snarl
            place(out, whine(d, [(0, 420 * p), (1, 560 * p)]), 0.0, 0.5)
            place(out, growl(d, 110 * p, 150 * p, "e", "i", 0.7), 0.0, 0.7)
        elif a == 5:   # crouched huff-huff then snarl
            for j in range(2):
                place(out, pk(breathy(s, 0.09, [(0, 1300), (0.09, 900)], [(0, 0), (0.01, 1), (0.09, 0)], 0.7)), j * 0.13, 0.6)
            place(out, growl(d * 0.6, 100 * p, 145 * p, "eu", "ae", 0.6), d * 0.4, 0.9)
        else:          # snarl with a falling-then-rising contour
            n = secs(d)
            place(out, pk(vocal(s, d, [(0, 120 * p), (d * 0.4, 90 * p), (d, 150 * p)], [(0, "a"), (d, "ae")], [(0, 0), (0.1, 0.6), (d - 0.05, 1), (d, 0)], 0.85,
                                breath=0.3, sub=0.4, flutter=0.5, fmax=5500)
                          + snarl(s, d, [(0, 120 * p), (d, 150 * p)], "ae", [(0, 0), (0.1, 0.5), (d, 0)], 0.85, 3.5) * 0.6), 0.0)
        return out
    if ev == "strike":
        out = buf(0.9)
        lunge = lambda g=0.4, d=0.14: place(out, pk(breathy(s, d, [(0, 500), (d, 1600)], [(0, 0), (d * 0.7, 1), (d, 0)], 0.8)), 0.0, g)  # noqa: E731
        if a == 0:     # lunge, double snap, "rrah"
            lunge()
            place(out, snap(1750 * p), 0.11)
            place(out, snap(1900 * p) * 0.6, 0.17)
            place(out, bark(300 * p, 0.24), 0.1, 0.7)
        elif a == 1:   # single bite + growl hold
            lunge(0.3)
            place(out, snap(1600 * p), 0.1)
            place(out, growl(0.4, 110 * p, 95 * p, "e", "eu", 0.6), 0.12, 0.75)
        elif a == 2:   # bite and tear: head-shake rustle
            place(out, snap(1800 * p), 0.0)
            n = secs(0.35)
            place(out, pk(band(s.noise(n), 800, 4000) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 7 * T(n)))) * ctl(n, [(0, 0), (0.03, 1), (0.35, 0)])), 0.04, 0.5)
            place(out, growl(0.35, 120 * p, 100 * p), 0.04, 0.6)
        elif a == 3:   # snap + yip
            lunge(0.35, 0.1)
            place(out, snap(2000 * p), 0.08)
            place(out, yelp(620 * p, 0.12, ("a", "a", "u")), 0.12, 0.5)
        elif a == 4:   # heavy pounce: body thud + snap
            lunge(0.45, 0.18)
            place(out, pk(thud(s, 95, 0.25, 0.05, grit=0.6)), 0.15, 0.8)
            place(out, snap(1650 * p), 0.16, 0.8)
        elif a == 5:   # snap-snap-snap
            for j in range(3):
                place(out, snap((1700 + 150 * j) * p), j * 0.075, 1.0 - 0.18 * j)
            place(out, growl(0.3, 105 * p, 95 * p), 0.05, 0.4)
        else:          # whoosh + bite + grunt
            place(out, pk(shaped(s, 0.2, [(0, 400), (0.6, 1800), (1, 700)], [(0, 0), (0.6, 1), (1, 0)], 0.6)), 0.0, 0.5)
            place(out, snap(1550 * p), 0.13)
            place(out, pk(vocal(s, 0.14, [(0, 160 * p), (0.14, 120 * p)], "eo", [(0, 0), (0.01, 1), (0.14, 0)], 0.85, breath=0.3, sub=0.3)), 0.15, 0.6)
        return out
    if ev == "hurt":
        out = buf(0.75)
        if a == 0:
            place(out, yelp(1150 * p), 0.0)
        elif a == 1:   # yelp-yelp
            place(out, yelp(1100 * p, 0.12), 0.0)
            place(out, yelp(1000 * p, 0.14), 0.15, 0.8)
        elif a == 2:   # yelp + whimper
            place(out, yelp(1050 * p, 0.16), 0.0)
            place(out, whine(0.25, [(0, 560 * p), (1, 470 * p)]), 0.2, 0.5)
        elif a == 3:   # high yip
            place(out, yelp(1500 * p, 0.1, ("i", "i", "e")), 0.0)
        elif a == 4:   # growl into yelp
            place(out, growl(0.14, 110 * p, 140 * p), 0.0, 0.6)
            place(out, yelp(1000 * p, 0.17), 0.1)
        elif a == 5:   # "kai" short, falling hard
            place(out, pk(vocal(s, 0.14, [(0, 1300 * p), (0.14, 700 * p)], [(0, "a"), (0.14, "i")], [(0, 0), (0.008, 1), (0.14, 0)], 1.0, breath=0.2, fmax=8000)), 0.0)
        else:          # three short yips descending
            for j in range(3):
                place(out, yelp((1250 - 120 * j) * p, 0.08), j * 0.11, 1.0 - 0.2 * j)
        return out
    if ev == "death":
        out = buf(1.95)
        body = lambda at, g=0.8, f=75: place(out, pk(thud(s, f, 0.35, 0.08, grit=0.5)), at, g)  # noqa: E731
        if a == 0:     # falling whine -> whimper -> drop
            place(out, whine(0.7, [(0, 820 * p), (0.07, 940 * p), (0.65, 520 * p), (1, 380 * p)]), 0.0)
            place(out, whine(0.35, [(0, 420 * p), (1, 330 * p)]), 0.75, 0.5)
            body(0.55)
        elif a == 1:   # yelp, collapse, long sigh
            place(out, yelp(1000 * p, 0.22), 0.0)
            body(0.25, 0.9)
            place(out, pk(breathy(s, 0.6, [(0, 900), (0.6, 500)], [(0, 0), (0.05, 1), (0.6, 0)], 0.7)), 0.35, 0.5)
        elif a == 2:   # dwindling howl
            place(out, howl(1.1, [(0, 500 * p), (0.2, 560 * p), (1, 240 * p)], ((0, "o"), (0.5, "u"), (1.0, "u"))), 0.0)
            body(0.95, 0.6, 70)
        elif a == 3:   # whimpers x3 fading
            for j in range(3):
                place(out, whine(0.22, [(0, (620 - 60 * j) * p), (1, (500 - 60 * j) * p)]), j * 0.3, 0.9 - 0.25 * j)
            body(0.2, 0.7)
        elif a == 4:   # gurgling growl fading out
            n = secs(0.9)
            place(out, growl(0.9, 90 * p, 55 * p, "o", "u", 0.5, 0.8) * (1 + 0.4 * np.sin(2 * np.pi * 11 * T(n))), 0.0)
            body(0.6)
        elif a == 5:   # sharp cry, thud, shadow drains
            place(out, yelp(1300 * p, 0.3, ("i", "a", "u")), 0.0)
            body(0.3, 1.0, 68)
            place(out, under(1.2, [(0, 0), (0.25, 0.9), (1.2, 0)], 140), 0.3, 0.45)
        else:          # last breath: sigh + soft whine
            place(out, pk(breathy(s, 0.4, [(0, 1300), (0.4, 800)], [(0, 0), (0.04, 1), (0.4, 0)], 0.6)), 0.0, 0.6)
            place(out, whine(0.5, [(0, 700 * p), (1, 420 * p)]), 0.3, 0.7)
            body(0.85, 0.6)
        place(out, under(1.1, [(0, 0), (0.25, 0.8), (1.1, 0)], 140), 0.4, 0.25)
        return out
    raise KeyError(ev)


# =============================================================================== boar
def boar_parts(s):
    def grunt(d=0.13, f=105.0, g="eu"):
        f0 = [(0, f * 0.9), (0.03, f * 1.12), (d, f * 0.85)]
        return pk(vocal(s, d, f0, [(0, "m"), (0.03, g), (d, "u")], [(0, 0), (0.015, 1), (d * 0.6, 0.8), (d, 0)], 0.75, tilt=0.8, breath=0.15, sub=0.5, flutter=0.5, fmax=4500)
                  + snarl(s, d, f0, g, [(0, 0), (0.015, 0.6), (d, 0)], 0.75, 2.0, 200, 3500) * 0.5)

    def snort(d=0.16, hi=1800):
        return pk(breathy(s, d, [(0, hi * 0.5), (0.04, hi), (d, hi * 0.72)], [(0, 0), (0.008, 1), (0.05, 0.6), (d, 0)], 0.9)
                  + snarl(s, d, [(0, 60), (d, 45)], "u", [(0, 0), (0.01, 0.7), (d, 0)], 1.0, 6, 300, 3000) * 0.6)

    def squeal(d, f_pts, amp=None):
        n = secs(d)
        f0 = ctl(n, [(t * d, f) for t, f in f_pts])
        F = C.tracks(n, [(0, "i"), (d * 0.3, "e"), (d, "ae")], 1.05)
        a = ctl(n, amp or [(0, 0), (0.015, 1), (d * 0.75, 0.85), (d, 0)])
        return pk(C.voice(s, n, f0, F, a, tilt=0.8, breath=0.25, flutter=0.3, fmax=9000) + C.rasp(s, n, f0, F, 2.0, 600, 9000) * a * 0.5)

    def hoof(f=85):
        return pk(thud(s, f, 0.18, 0.035, grit=0.7))

    def tusk(f=1250):
        return pk(np.asarray(modal([f, f * 1.71, f * 2.64], [0.02, 0.012, 0.008], [1, 0.6, 0.3], 0.1, s.rng)) + click(s, 0.03, 1500, 7000, 0.002))

    return grunt, snort, squeal, hoof, tusk


def boar(s, ev, k):
    p = P(s)
    grunt, snort, squeal, hoof, tusk = boar_parts(s)
    a = k % TAKES
    if ev == "idle":
        out = buf(1.3)
        if a == 0:     # grunt-grunt-grunt (even)
            for j in range(3):
                place(out, grunt(u(s, 0.11, 0.14), 100 * p, "eu" if j % 2 == 0 else "o"), j * 0.2 + u(s, 0, 0.02), 1.0 - 0.12 * j)
        elif a == 1:   # snuffling nose only
            for j in range(6):
                place(out, pk(breathy(s, 0.06, [(0, 2400), (0.06, 1900)], [(0, 0), (0.01, 1), (0.06, 0)], 0.6)), j * 0.085 + u(s, 0, 0.015), 0.5)
            place(out, grunt(0.12, 95 * p), 0.6, 0.6)
        elif a == 2:   # long low grumble
            place(out, grunt(0.45, 88 * p, "o"), 0.0, 0.9)
            place(out, snort(0.14), 0.55, 0.5)
        elif a == 3:   # snort + two quick grunts
            place(out, snort(), 0.0, 0.8)
            for j in range(2):
                place(out, grunt(0.09, 118 * p, "a"), 0.25 + j * 0.12, 0.8)
        elif a == 4:   # rooting: hoof scrape + grunts
            place(out, pk(scrape(s, 0.25, 200, 2500)), 0.0, 0.5)
            place(out, grunt(0.14, 105 * p), 0.2, 0.9)
            place(out, grunt(0.16, 98 * p, "o"), 0.55, 0.8)
        elif a == 5:   # squeaky contented grunt
            place(out, grunt(0.12, 140 * p, "e"), 0.0, 0.9)
            place(out, squeal(0.14, [(0, 600 * p), (0.5, 720 * p), (1, 640 * p)]), 0.18, 0.35)
        else:          # irregular grunts (fast-slow)
            for j, at in enumerate((0.0, 0.1, 0.45, 0.52)):
                place(out, grunt(0.08, (105 + 10 * (j % 2)) * p), at, 0.85)
        return out
    if ev == "alert":
        out = buf(1.3)
        if a == 0:     # high falling squeal, then stamp-stamp
            place(out, squeal(0.32, [(0, 1250 * p), (0.3, 1150 * p), (1, 700 * p)]), 0.0)
            place(out, hoof(80), 0.4, 0.6)
            place(out, hoof(90), 0.55, 0.5)
            place(out, snort(0.12, 2100), 0.62, 0.5)
        elif a == 1:   # double squeal
            for j, at in enumerate((0.0, 0.22)):
                place(out, squeal(0.18, [(0, 800 * p), (0.3, 1150 * p * (1 - 0.08 * j)), (1, 850 * p)]), at, 1.0 - 0.15 * j)
        elif a == 2:   # roar-grunt then stamp-stamp
            place(out, grunt(0.3, 125 * p, "a"), 0.0, 1.0)
            place(out, hoof(85), 0.35, 0.6)
            place(out, hoof(78), 0.52, 0.55)
        elif a == 3:   # snort-snort, squeal rising
            place(out, snort(0.12, 2000), 0.0, 0.7)
            place(out, snort(0.12, 1700), 0.15, 0.7)
            place(out, squeal(0.3, [(0, 600 * p), (1, 1200 * p)]), 0.32)
        elif a == 4:   # tusk clack + squeal
            place(out, tusk(1300 * p), 0.0, 0.7)
            place(out, tusk(1200 * p), 0.08, 0.5)
            place(out, squeal(0.28, [(0, 900 * p), (0.2, 1250 * p), (1, 700 * p)]), 0.18)
        elif a == 5:   # deep bellow
            place(out, grunt(0.45, 95 * p, "o"), 0.0, 1.0)
            place(out, snort(0.18, 1500), 0.48, 0.6)
        else:          # short squeal + grunt + scrape
            place(out, squeal(0.18, [(0, 700 * p), (0.3, 1100 * p), (1, 900 * p)]), 0.0)
            place(out, grunt(0.16, 120 * p, "a"), 0.22, 0.9)
            place(out, pk(scrape(s, 0.15, 300, 3000)), 0.42, 0.25)
        return out
    if ev == "windup":     # 0.8 s
        out = buf(1.05)
        d = 0.8 * [1.0, 0.94, 1.06, 1.0, 0.9, 1.1, 1.0][a]
        if a == 0:     # three paw scrapes building + grunt
            for j in range(3):
                place(out, pk(scrape(s, 0.18, 200, 2600)), j * d * 0.32, 0.45 + 0.15 * j)
                place(out, hoof(95) * 0.5, j * d * 0.32 + 0.02, 0.3 + 0.1 * j)
            place(out, grunt(0.2, 120 * p, "a"), d * 0.75, 0.9)
        elif a == 1:   # snorts accelerating
            for j, at in enumerate((0.0, 0.3, 0.5, 0.62)):
                place(out, snort(0.12, 1600 + 150 * j), at * d / 0.8, 0.5 + 0.12 * j)
        elif a == 2:   # rising squeal-growl
            place(out, squeal(d, [(0, 400 * p), (1, 900 * p)], [(0, 0), (0.2, 0.4), (d - 0.05, 1), (d, 0)]), 0.0, 0.8)
            place(out, grunt(d * 0.5, 110 * p, "eu"), 0.0, 0.5)
        elif a == 3:   # hoof stamps x4
            for j in range(4):
                place(out, hoof(90 - 4 * j), j * d * 0.22, 0.5 + 0.12 * j)
            place(out, snort(0.15), d * 0.7, 0.7)
        elif a == 4:   # low rumble grunt-chain
            for j in range(5):
                place(out, grunt(0.1, (95 + 6 * j) * p), j * d * 0.18, 0.55 + 0.08 * j)
        elif a == 5:   # snort + long scrape + tusk clack
            place(out, snort(0.18), 0.0, 0.7)
            place(out, pk(scrape(s, d * 0.6, 250, 3000)), 0.15, 0.6)
            place(out, tusk(1250 * p), d * 0.85, 0.6)
        else:          # breath in, hold, grunt
            place(out, pk(breathy(s, 0.35, [(0, 1200), (0.35, 2400)], [(0, 0), (0.3, 1), (0.35, 0)], 0.6)), 0.0, 0.6)
            place(out, grunt(0.25, 130 * p, "a"), d * 0.65, 1.0)
        return out
    if ev == "strike":
        out = buf(0.9)
        if a == 0:     # charge impact + tusk + squeal
            place(out, pk(thud(s, 70, 0.4, 0.09, body=1.2, grit=0.7)), 0.08)
            place(out, tusk(1250 * p), 0.085, 0.6)
            place(out, squeal(0.22, [(0, 520 * p), (0.2, 900 * p), (1, 600 * p)]), 0.1, 0.65)
        elif a == 1:   # gore: two tusk jabs
            for j, at in enumerate((0.0, 0.14)):
                place(out, tusk((1200 + 100 * j) * p), at)
                place(out, grunt(0.1, 130 * p, "a"), at, 0.6)
        elif a == 2:   # heavy ram + grunt
            place(out, pk(thud(s, 62, 0.45, 0.11, body=1.3, grit=0.8)), 0.0)
            place(out, grunt(0.25, 115 * p, "o"), 0.02, 0.8)
        elif a == 3:   # squeal-first lunge
            place(out, squeal(0.2, [(0, 900 * p), (0.3, 1200 * p), (1, 800 * p)]), 0.0, 0.8)
            place(out, pk(thud(s, 80, 0.3, 0.07, grit=0.7)), 0.15)
        elif a == 4:   # skid + slam
            place(out, pk(scrape(s, 0.2, 250, 3000)), 0.0, 0.6)
            place(out, pk(thud(s, 75, 0.35, 0.08, body=1.2, grit=0.7)), 0.17)
            place(out, tusk(1300 * p), 0.18, 0.5)
        elif a == 5:   # headbutt toss: whoosh up + grunt
            place(out, pk(shaped(s, 0.2, [(0, 300), (1, 1300)], [(0, 0), (0.7, 1), (1, 0)], 0.7)), 0.0, 0.6)
            place(out, pk(thud(s, 95, 0.25, 0.05, grit=0.6)), 0.12, 0.9)
            place(out, grunt(0.18, 140 * p, "a"), 0.14, 0.8)
        else:          # bite-snap + snort
            place(out, tusk(1450 * p), 0.0)
            place(out, snort(0.16, 2100), 0.06, 0.7)
            place(out, pk(thud(s, 100, 0.2, 0.04, grit=0.5)), 0.0, 0.5)
        return out
    if ev == "hurt":
        out = buf(0.7)
        if a == 0:     # grunt first, then a rising squeal
            place(out, grunt(0.12, 125 * p, "a"), 0.0, 0.8)
            place(out, squeal(0.2, [(0, 800 * p), (1, 1350 * p)]), 0.11)
        elif a == 1:   # short high squeak
            place(out, squeal(0.12, [(0, 1300 * p), (0.3, 1600 * p), (1, 1250 * p)]), 0.0)
        elif a == 2:   # grunt-oink
            place(out, grunt(0.12, 150 * p, "a"), 0.0)
            place(out, grunt(0.1, 125 * p, "o"), 0.13, 0.7)
        elif a == 3:   # double squeal down
            for j in range(2):
                place(out, squeal(0.12, [(0, (1200 - 150 * j) * p), (1, (900 - 150 * j) * p)]), j * 0.15, 1.0 - 0.2 * j)
        elif a == 4:   # snort + squeal
            place(out, snort(0.1, 2200), 0.0, 0.6)
            place(out, squeal(0.18, [(0, 1000 * p), (1, 1300 * p)]), 0.08)
        elif a == 5:   # long grunt with squeal tip
            place(out, grunt(0.22, 120 * p, "eu"), 0.0)
            place(out, squeal(0.1, [(0, 1100 * p), (1, 900 * p)]), 0.2, 0.6)
        else:          # wheeze squeal
            place(out, squeal(0.28, [(0, 800 * p), (0.5, 1000 * p), (1, 650 * p)], [(0, 0), (0.05, 0.6), (0.2, 1), (0.28, 0)]), 0.0)
        return out
    if ev == "death":
        out = buf(1.95)
        flop = lambda at, g=1.0: (place(out, pk(thud(s, 62, 0.45, 0.11, body=1.3, grit=0.6)), at, g), place(out, pops(s, secs(0.45), 60, 2500, 8000), at + 0.02, 0.5 * g))  # noqa: E731
        if a == 0:     # short rise-fall squeal, early flop, long breath out
            place(out, squeal(0.45, [(0, 700 * p), (0.4, 1200 * p), (1, 500 * p)]), 0.0)
            flop(0.45)
            place(out, pk(breathy(s, 0.8, [(0, 1600), (0.8, 600)], [(0, 0), (0.08, 0.7), (0.8, 0)], 0.8)), 0.6, 0.6)
        elif a == 1:   # squeal-squeal, flop
            for j in range(2):
                place(out, squeal(0.25, [(0, (1100 - 200 * j) * p), (1, (700 - 150 * j) * p)]), j * 0.3, 1.0 - 0.2 * j)
            flop(0.6)
        elif a == 2:   # slow grunt down, wheeze
            place(out, grunt(0.6, 100 * p, "o"), 0.0)
            flop(0.4, 0.8)
            place(out, pk(breathy(s, 0.5, [(0, 1400), (0.5, 700)], [(0, 0), (0.05, 0.6), (0.5, 0)], 0.8)), 0.7, 0.5)
        elif a == 3:   # stumble: hoof-hoof, flop, squeal
            place(out, hoof(90), 0.0, 0.6)
            place(out, hoof(80), 0.12, 0.6)
            flop(0.3)
            place(out, squeal(0.4, [(0, 800 * p), (1, 420 * p)]), 0.35, 0.8)
        elif a == 4:   # high squeal cut short
            place(out, squeal(0.4, [(0, 1100 * p), (0.3, 1300 * p), (1, 1000 * p)]), 0.0)
            flop(0.42)
        elif a == 5:   # grunts fading x3
            for j in range(3):
                place(out, grunt(0.16, (110 - 10 * j) * p, "o"), j * 0.28, 1.0 - 0.25 * j)
            flop(0.9, 0.8)
        else:          # snort, long falling squeal, rattle
            place(out, snort(0.15), 0.0, 0.6)
            place(out, squeal(0.9, [(0, 1000 * p), (1, 330 * p)]), 0.15)
            flop(1.0, 0.7)
        return out
    raise KeyError(ev)


# =============================================================================== brute (stone / moss golem)
def brute_parts(s):
    def groan(d, f_pts, amp_pts=None, vowels=("o", "u")):
        n = secs(d)
        f0 = ctl(n, [(t * d, f) for t, f in f_pts])
        F = C.tracks(n, [(0, vowels[0]), (d, vowels[1])], 0.68)
        a = ctl(n, amp_pts or [(0, 0), (d * 0.25, 0.9), (d * 0.75, 0.8), (d, 0)])
        return pk(C.voice(s, n, f0, F, a, tilt=0.7, breath=0.18, sub=0.55, flutter=0.5, fmax=3500, bw=1.3) + C.rasp(s, n, f0, F, 2.5, 120, 2500) * a * 0.35)

    def grind(d, amp_pts=None):
        n = secs(d)
        a = ctl(n, amp_pts or [(0, 0), (d * 0.3, 0.8), (d, 0)])
        x = norm(band(s.noise(n), 60, 420)) * (0.6 + 0.4 * np.clip(C.wander(s, n, 9, 1), -1, 1))
        return pk(x * a + pops(s, n, 50, 700, 3500, a, (0.002, 0.006)) * 0.8)

    def crack(g=1.0):
        return pk(click(s, 0.05, 1500, 9000, 0.003) * 1.2 + rock(s, 1.3) + rock(s, 0.8) * 0.6) * g

    def slam(f=52):
        return pk(thud(s, f, 0.7, 0.16, drop=0.5, body=1.5, grit=0.8))

    return groan, grind, crack, slam


def brute(s, ev, k):
    p = P(s)
    groan, grind, crack, slam = brute_parts(s)
    a = k % TAKES
    rub = lambda n_s, cnt, st, spread, sizes=(0.3, 0.6), g=0.3: debris(s, secs(n_s), cnt, st, spread, sizes, g)  # noqa: E731
    if ev == "idle":
        out = buf(1.4)
        if a == 0:     # grind + long groan
            place(out, grind(1.2), 0.0, 0.6)
            place(out, groan(0.9, [(0, 46 * p), (0.5, 52 * p), (1, 44 * p)]), 0.2, 0.8)
        elif a == 1:   # mossy exhale + short groan
            place(out, pk(breathy(s, 0.6, [(0, 380), (0.6, 260)], [(0, 0), (0.2, 1), (0.6, 0)], 0.6)), 0.0, 0.7)
            place(out, groan(0.45, [(0, 52 * p), (1, 46 * p)]), 0.5, 0.6)
        elif a == 2:   # pebbles trickle + creak
            place(out, rub(1.3, 9, 0.1, 1.0), 0.0, 1.0)
            place(out, pk(V.creak(s, 0.5, 45, 60, body=(90, 210, 430), q=6, rough=0.3, wobble=4, swell=0.2, release=0.15)), 0.3, 0.5)
        elif a == 3:   # two low hums
            for j in range(2):
                place(out, groan(0.4, [(0, (44 + 6 * j) * p), (1, (48 + 6 * j) * p)], vowels=("u", "u")), j * 0.55, 0.75)
        elif a == 4:   # stone shift: thud + grind
            place(out, pk(thud(s, 70, 0.4, 0.1, grit=0.6)), 0.0, 0.6)
            place(out, grind(0.8, [(0, 0), (0.1, 1), (0.8, 0)]), 0.05, 0.6)
        elif a == 5:   # rising "hmm?" groan
            place(out, groan(0.8, [(0, 42 * p), (0.7, 58 * p), (1, 56 * p)], vowels=("m", "o")), 0.0, 0.85)
        else:          # grumble chain of 3
            for j in range(3):
                place(out, groan(0.25, [(0, 55 * p), (1, 48 * p)], vowels=("a", "o")), j * 0.33, 0.7)
        place(out, rub(1.4, 4, 0.3, 0.9), 0.0, 0.8)
        return out
    if ev == "alert":
        out = buf(1.5)
        if a == 0:     # groan rising to a question, crack at the end
            place(out, groan(0.9, [(0, 42 * p), (0.6, 60 * p), (1, 72 * p)], vowels=("m", "a")), 0.0)
            place(out, crack(), 0.85, 0.8)
            place(out, rub(1.5, 6, 0.85, 0.4), 0.0, 0.9)
        elif a == 1:   # roar rising high
            place(out, groan(0.9, [(0, 55 * p), (0.6, 82 * p), (1, 75 * p)], vowels=("o", "a")), 0.0)
            place(out, rub(1.5, 8, 0.1, 0.8, (0.4, 1.0), 0.45), 0.0, 1.0)
        elif a == 2:   # chest pound x2 + groan
            for j in range(2):
                place(out, slam(64 + 6 * j), j * 0.22, 0.7)
            place(out, groan(0.7, [(0, 60 * p), (1, 50 * p)]), 0.42, 0.9)
        elif a == 3:   # grinding awake, then bellow
            place(out, grind(0.5, [(0, 0), (0.4, 1), (0.5, 0)]), 0.0, 0.7)
            place(out, groan(0.7, [(0, 48 * p), (0.3, 72 * p), (1, 60 * p)], vowels=("a", "o")), 0.4)
        elif a == 4:   # two short barks of stone
            for j in range(2):
                place(out, groan(0.28, [(0, (70 - 8 * j) * p), (1, (58 - 8 * j) * p)], vowels=("a", "u")), j * 0.36, 1.0 - 0.15 * j)
                place(out, crack(0.5), j * 0.36, 0.5)
        elif a == 5:   # low long "ooo" + debris shower
            place(out, groan(1.2, [(0, 40 * p), (1, 44 * p)], vowels=("u", "o")), 0.0)
            place(out, rub(1.5, 14, 0.2, 1.0, (0.4, 1.1), 0.5), 0.0, 1.0)
        else:          # crack-crack, groan falling
            place(out, crack(), 0.0, 0.8)
            place(out, crack(0.7), 0.12, 0.7)
            place(out, groan(0.8, [(0, 75 * p), (1, 46 * p)], vowels=("o", "u")), 0.2)
        return out
    if ev == "windup":     # 1.1 s
        out = buf(1.3)
        d = 1.1 * [1.0, 0.94, 1.04, 1.0, 0.92, 1.06, 1.0][a]
        if a == 0:     # grind and creak first, the groan joins late and rises
            place(out, grind(d, [(0, 0), (0.15, 1.0), (d * 0.5, 0.6), (d, 0)]), 0.0, 0.8)
            place(out, pk(V.creak(s, d * 0.5, 60, 45, body=(90, 210, 430, 800), q=6, rough=0.3, wobble=4.0, swell=0.1, release=0.1)), 0.0, 0.6)
            place(out, groan(d * 0.55, [(0, 60 * p), (1, 95 * p)], [(0, 0), (d * 0.3, 1.0), (d * 0.55, 0)], ("o", "a")), d * 0.45, 0.9)
        elif a == 1:   # inhale-roar: breath rising, then a short groan
            place(out, pk(breathy(s, d * 0.7, [(0, 300), (d * 0.7, 900)], [(0, 0), (d * 0.6, 1), (d * 0.7, 0)], 0.7)), 0.0, 0.7)
            place(out, groan(d * 0.35, [(0, 70 * p), (1, 90 * p)], vowels=("a", "a")), d * 0.65, 1.0)
        elif a == 2:   # arms lift: three stone clunks + grind
            for j in range(3):
                place(out, crack(0.6), j * d * 0.3, 0.6)
            place(out, grind(d, [(0, 0), (d, 1)]), 0.0, 0.6)
            place(out, groan(d * 0.5, [(0, 60 * p), (1, 80 * p)]), d * 0.5, 0.7)
        elif a == 3:   # long rising creak only + pebbles
            place(out, pk(V.creak(s, d, 30, 75, body=(80, 190, 400, 760), q=7, rough=0.35, wobble=3.0, swell=0.4, release=0.1)), 0.0, 0.9)
            place(out, rub(d, 10, 0.1, d * 0.8), 0.0, 1.0)
        elif a == 4:   # stuttering groans rising
            for j in range(4):
                place(out, groan(d * 0.2, [(0, (50 + 9 * j) * p), (1, (56 + 9 * j) * p)], vowels=("o", "a")), j * d * 0.24, 0.6 + 0.1 * j)
        elif a == 5:   # grind with heavy breath, cut by a crack
            place(out, grind(d, [(0, 0), (d * 0.8, 1), (d, 0)]), 0.0, 0.8)
            place(out, pk(breathy(s, d, [(0, 250), (d, 500)], [(0, 0), (d * 0.8, 1), (d, 0)], 0.6)), 0.0, 0.5)
            place(out, crack(), d * 0.92, 0.7)
        else:          # falling then rising groan (gathering)
            place(out, groan(d, [(0, 60 * p), (0.4, 44 * p), (1, 80 * p)], vowels=("o", "a")), 0.0, 0.9)
            place(out, rub(d, 6, 0.3, 0.6), 0.0, 0.8)
        return out
    if ev == "strike":
        out = buf(1.0)
        if a == 0:     # ground slam
            place(out, pk(breathy(s, 0.12, [(0, 300), (0.12, 900)], [(0, 0), (0.1, 1), (0.12, 0)], 0.9)), 0.0, 0.35)
            place(out, slam(), 0.1)
            place(out, crack(), 0.1, 0.9)
            place(out, rub(1.0, 22, 0.12, 0.7, (0.4, 1.3), 0.6), 0.0, 1.0)
        elif a == 1:   # double fist slam
            for j, at in enumerate((0.0, 0.2)):
                place(out, slam(58 + 8 * j), at, 0.75 - 0.15 * j)
                place(out, crack(0.6), at, 0.5)
            place(out, grind(0.6, [(0, 0), (0.05, 1), (0.6, 0)]), 0.02, 0.5)
            place(out, rub(1.0, 14, 0.03, 0.6, (0.4, 1.0), 0.5), 0.0, 1.0)
        elif a == 2:   # swipe: whoosh + rock crack
            place(out, pk(shaped(s, 0.3, [(0, 200), (0.6, 800), (1, 300)], [(0, 0), (0.6, 1), (1, 0)], 0.8, body=1.0)), 0.0, 0.6)
            place(out, crack(), 0.22)
            place(out, rub(0.8, 8, 0.24, 0.4), 0.0, 0.8)
        elif a == 3:   # slam + groan grunt
            place(out, slam(50), 0.0)
            place(out, groan(0.3, [(0, 70 * p), (1, 55 * p)], vowels=("a", "u")), 0.0, 0.7)
            place(out, rub(1.0, 14, 0.04, 0.6), 0.0, 0.9)
        elif a == 4:   # shockwave: low boom + crumble long
            place(out, slam(44), 0.0)
            place(out, grind(0.7, [(0, 0), (0.05, 1), (0.7, 0)]), 0.02, 0.6)
            place(out, rub(1.0, 30, 0.05, 0.85, (0.3, 1.0), 0.5), 0.0, 1.0)
        elif a == 5:   # stomp + pebble rain (late)
            place(out, slam(60), 0.0, 0.9)
            place(out, rub(1.0, 16, 0.25, 0.6, (0.3, 0.7), 0.5), 0.0, 1.0)
        else:          # crack first, then slam
            place(out, crack(), 0.0, 0.8)
            place(out, slam(54), 0.08)
            place(out, groan(0.25, [(0, 80 * p), (1, 62 * p)], vowels=("a", "o")), 0.1, 0.6)
        return out
    if ev == "hurt":
        out = buf(0.75)
        if a == 0:
            place(out, crack(), 0.0)
            place(out, groan(0.3, [(0, 62 * p), (1, 50 * p)], [(0, 0), (0.04, 0.9), (0.3, 0)], ("a", "o")), 0.03, 0.8)
            place(out, rub(0.65, 7, 0.03, 0.4), 0.0, 1.0)
        elif a == 1:   # chip chip + grunt
            for j in range(2):
                place(out, pk(rock(s, 0.7)), j * 0.07, 0.7)
            place(out, groan(0.22, [(0, 75 * p), (1, 60 * p)], vowels=("u", "u")), 0.05, 0.8)
        elif a == 2:   # deep "hoo" + crumble
            place(out, groan(0.35, [(0, 55 * p), (0.3, 66 * p), (1, 48 * p)], vowels=("o", "u")), 0.0)
            place(out, rub(0.7, 10, 0.08, 0.5), 0.0, 1.0)
        elif a == 3:   # crack + grind
            place(out, crack(1.0), 0.0)
            place(out, grind(0.35, [(0, 0), (0.05, 1), (0.35, 0)]), 0.02, 0.7)
        elif a == 4:   # stagger thud + groan
            place(out, pk(thud(s, 70, 0.3, 0.07, grit=0.7)), 0.0, 0.8)
            place(out, groan(0.3, [(0, 68 * p), (1, 54 * p)], vowels=("a", "a")), 0.05, 0.85)
        elif a == 5:   # high-ish crack, small grunt
            place(out, pk(click(s, 0.05, 2500, 10000, 0.002)), 0.0, 0.8)
            place(out, pk(rock(s, 0.6)), 0.0, 0.7)
            place(out, groan(0.18, [(0, 80 * p), (1, 70 * p)], vowels=("e", "o")), 0.03, 0.7)
        else:          # moss tear + groan
            place(out, pk(rustle(s, secs(0.25), ctl(secs(0.25), [(0, 0), (0.02, 1), (0.25, 0)]))), 0.0, 0.5)
            place(out, groan(0.3, [(0, 58 * p), (1, 46 * p)]), 0.04, 0.9)
        return out
    if ev == "death":
        out = buf(1.95)
        if a == 0:     # collapse into rubble
            place(out, groan(1.0, [(0, 64 * p), (0.3, 58 * p), (1, 34 * p)], [(0, 0), (0.08, 1.0), (0.6, 0.6), (1.0, 0)]), 0.0, 0.9)
            for j, at in enumerate((0.35, 0.62, 0.8, 1.02)):
                place(out, slam(58 - 5 * j), at, 0.9 - 0.12 * j)
            place(out, rub(1.95, 30, 0.35, 1.1, (0.3, 1.2), 0.5), 0.0, 1.0)
        elif a == 1:   # topple: long creak, one huge slam
            place(out, pk(V.creak(s, 0.8, 70, 35, body=(80, 190, 400), q=7, rough=0.3, swell=0.1, release=0.2)), 0.0, 0.7)
            place(out, slam(46), 0.85)
            place(out, rub(1.95, 20, 0.85, 0.8, (0.4, 1.2), 0.5), 0.0, 1.0)
        elif a == 2:   # crumble from the top (cascade)
            place(out, crack(), 0.0, 0.8)
            place(out, rub(1.95, 40, 0.0, 1.4, (0.3, 1.0), 0.5, ), 0.0, 1.0)
            place(out, groan(0.6, [(0, 55 * p), (1, 38 * p)]), 0.1, 0.6)
        elif a == 3:   # groan fading + two slams + dust
            place(out, groan(0.7, [(0, 70 * p), (1, 45 * p)], vowels=("a", "u")), 0.0)
            place(out, slam(55), 0.6, 0.9)
            place(out, slam(50), 0.85, 0.7)
            place(out, pk(breathy(s, 0.7, [(0, 1500), (0.7, 2500)], [(0, 0), (0.15, 0.4), (0.7, 0)], 1.0)), 0.95, 0.35)
        elif a == 4:   # shatter: bright cracks + scattering
            for j in range(3):
                place(out, crack(1.0 - 0.2 * j), j * 0.09, 1.0)
            place(out, rub(1.95, 34, 0.05, 1.0, (0.25, 0.8), 0.5, ), 0.0, 1.0)
            place(out, slam(60), 0.4, 0.6)
        elif a == 5:   # sink into the ground: grind down + low groan
            place(out, grind(1.3, [(0, 0), (0.2, 1), (1.3, 0)]), 0.0, 0.8)
            place(out, groan(1.2, [(0, 50 * p), (1, 30 * p)], vowels=("u", "u")), 0.05, 0.8)
            place(out, slam(48), 1.1, 0.5)
        else:          # three stumbling steps, fall
            for j in range(3):
                place(out, slam(66 - 4 * j), j * 0.3, 0.6)
            place(out, groan(0.5, [(0, 66 * p), (1, 40 * p)]), 0.3, 0.7)
            place(out, slam(46), 1.05)
            place(out, rub(1.95, 18, 1.05, 0.6), 0.0, 0.9)
        return out
    raise KeyError(ev)


# =============================================================================== wisp (ember imp)
def wisp_parts(s):
    def blip(d, f_pts, vowels="i", breath=0.12):
        return pk(vocal(s, d, [(t * d, f) for t, f in f_pts], vowels, [(0, 0), (0.008, 1), (d * 0.5, 0.8), (d, 0)], 1.55, tilt=1.1, breath=breath, fmax=11000))

    def flame(d, amp_pts=None, lo=200, hi=2600):
        x = fire(s, d, lo, hi, 9)
        return pk(x * ctl(x.size, amp_pts or [(0, 0), (d * 0.2, 0.6), (d * 0.8, 0.5), (d, 0)]))

    def fwoosh(d, f_pts, amp_pts):
        n = secs(d)
        return pk(nsweep(s, n, ctl(n, [(t * d, f) for t, f in f_pts]), 0.6) * ctl(n, [(t * d, v) for t, v in amp_pts]))

    def crackles(d, density, env_pts=None):
        n = secs(d)
        return pops(s, n, density, 1500, 7000, ctl(n, env_pts) if env_pts else None)

    return blip, flame, fwoosh, crackles


def wisp(s, ev, k):
    p = P(s)
    blip, flame, fwoosh, crackles = wisp_parts(s)
    a = k % TAKES
    if ev == "idle":
        out = buf(1.3)
        place(out, flame(1.1), 0.0, 0.5)
        if a == 0:     # 4 rising blips
            for j in range(4):
                f = (900 + 120 * j) * p
                place(out, blip(0.055, [(0, f), (1, f * 1.12)]), 0.3 + j * 0.085, 0.7)
        elif a == 1:   # 2 falling "tee-too"
            for j in range(2):
                f = (1300 - 250 * j) * p
                place(out, blip(0.09, [(0, f * 1.05), (1, f * 0.9)], [(0, "i"), (0.09, "u" if j else "i")]), 0.25 + j * 0.16, 0.75)
        elif a == 2:   # hum + crackle burst
            place(out, blip(0.4, [(0, 700 * p), (0.5, 760 * p), (1, 680 * p)], "m", 0.3), 0.2, 0.6)
            place(out, crackles(0.4, 70, [(0, 1), (0.4, 0)]), 0.7, 0.8)
        elif a == 3:   # trill (fast 6 blips alternating)
            for j in range(6):
                f = (1100 if j % 2 == 0 else 1250) * p
                place(out, blip(0.04, [(0, f), (1, f)]), 0.3 + j * 0.055, 0.55)
        elif a == 4:   # giggle-sigh: blip then breath
            place(out, blip(0.07, [(0, 1200 * p), (1, 1350 * p)]), 0.25, 0.7)
            place(out, pk(breathy(s, 0.3, [(0, 3000), (0.3, 2000)], [(0, 0), (0.05, 1), (0.3, 0)], 0.6)), 0.35, 0.4)
        elif a == 5:   # flare-up whoosh, no voice
            place(out, fwoosh(0.5, [(0, 400), (0.5, 1500), (1, 600)], [(0, 0), (0.4, 1), (1, 0)]), 0.3, 0.8)
            place(out, crackles(0.6, 40), 0.3, 0.6)
        else:          # questioning "hm?" blip rising
            place(out, blip(0.18, [(0, 800 * p), (1, 1200 * p)], [(0, "m"), (0.18, "i")], 0.2), 0.3, 0.75)
        place(out, crackles(1.1, 14), 0.0, 0.5)
        return out
    if ev == "alert":
        out = buf(1.15)
        notes_sets = [[(1180, 0.09), (1050, 0.06), (1320, 0.09), (1000, 0.2)], [(1400, 0.06), (1250, 0.06), (1100, 0.06), (950, 0.15)],
                      [(1000, 0.12), (1500, 0.12)], [(900, 0.05), (1000, 0.05), (1100, 0.05), (1200, 0.05), (1300, 0.05), (1500, 0.12)],
                      [(1250, 0.2)], [(1100, 0.08), (1100, 0.08), (1400, 0.18)], [(1300, 0.07), (900, 0.07), (1300, 0.07), (900, 0.14)]]
        place(out, flame(0.5, [(0, 0), (0.08, 1), (0.5, 0)], 300, 3000), 0.0, 0.5)
        at = 0.05
        notes = notes_sets[a]
        for j, (f, d) in enumerate(notes):
            place(out, pk(breathy(s, 0.03, [(0, 3500), (0.03, 3000)], [(0, 0), (0.008, 1), (0.03, 0)], 0.6)), at, 0.22)
            last = j == len(notes) - 1
            place(out, blip(d, [(0, f * p * 0.95), (0.3, f * p * 1.06), (1, f * p * (1.12 if last else 0.98))], [(0, "i"), (d, "e" if last else "i")]), at + 0.015, 0.85)
            at += d + 0.035
        return out
    if ev == "windup":     # 0.85 s
        out = buf(1.1)
        d = 0.85 * [1.0, 0.93, 1.07, 1.0, 0.95, 1.05, 1.0][a]
        n = secs(d)
        rise = ctl(n, [(0, 0), (d * 0.85, 1), (d, 0)])
        if a == 0:     # fire inhale + charging hum
            place(out, fwoosh(d, [(0, 300), (1, 2600)], [(0, 0), (0.85, 1), (1, 0)]), 0.0, 0.8)
            place(out, pk(glide(n, ctl(n, [(0, 220 * p), (d, 780 * p)]), ((1, 1.0), (2, 0.3), (3, 0.12))) * rise), 0.0, 0.3)
        elif a == 1:   # crackle swelling, giggle at the top
            place(out, crackles(d, 110, [(0, 0.1), (d * 0.9, 1), (d, 0)]), 0.0, 1.0)
            place(out, blip(0.1, [(0, 1200 * p), (1, 1450 * p)]), d * 0.75, 0.6)
        elif a == 2:   # pulsing flame (3 pulses) growing
            for j in range(3):
                place(out, fwoosh(d * 0.3, [(0, 500 + 300 * j), (1, 1200 + 400 * j)], [(0, 0), (0.6, 1), (1, 0)]), j * d * 0.32, 0.5 + 0.2 * j)
        elif a == 3:   # whistling rise
            place(out, pk(glide(n, ctl(n, [(0, 600 * p), (d, 2200 * p)]), ((1, 1.0), (2, 0.15))) * rise), 0.0, 0.4)
            place(out, fwoosh(d, [(0, 800), (1, 3000)], [(0, 0), (0.9, 0.7), (1, 0)]), 0.0, 0.6)
        elif a == 4:   # "mmm" building hum + sparks
            place(out, blip(d, [(0, 500 * p), (1, 900 * p)], "m", 0.3), 0.0, 0.6)
            place(out, crackles(d, 60, [(0, 0), (d, 1)]), 0.0, 0.8)
        elif a == 5:   # roar of flame, low
            place(out, flame(d, [(0, 0), (d * 0.9, 1), (d, 0)], 120, 1400), 0.0, 0.9)
            place(out, pk(thud(s, 120, 0.15, 0.03, grit=0.3)), d * 0.88, 0.4)
        else:          # hiss in + pop
            place(out, pk(high(s.noise(n), 3000) * rise), 0.0, 0.5)
            place(out, pk(click(s, 0.04, 900, 6000, 0.004)), d * 0.9, 0.7)
            place(out, fwoosh(d, [(0, 400), (1, 1500)], [(0, 0), (0.85, 0.7), (1, 0)]), 0.0, 0.5)
        return out
    if ev == "strike":
        out = buf(0.85)
        if a == 0:     # "ha!" first, then a rising fire spit and a late pop
            place(out, blip(0.09, [(0, 1100 * p), (1, 1300 * p)], "a", 0.3), 0.0, 0.7)
            place(out, fwoosh(0.35, [(0, 600), (1, 3000)], [(0, 0), (0.7, 1), (1, 0)]), 0.06)
            place(out, pk(click(s, 0.04, 900, 6000, 0.004)), 0.4, 0.6)
        elif a == 1:   # double fireball
            for j, at in enumerate((0.0, 0.16)):
                place(out, fwoosh(0.25, [(0, 2800 - 400 * j), (1, 700)], [(0, 0), (0.05, 1), (1, 0)]), at, 1.0 - 0.2 * j)
        elif a == 2:   # flame lash (up-sweep) + crackle
            place(out, fwoosh(0.3, [(0, 500), (1, 3500)], [(0, 0), (0.7, 1), (1, 0)]), 0.0, 0.9)
            place(out, crackles(0.5, 80, [(0, 0), (0.25, 1), (0.5, 0)]), 0.15, 0.9)
        elif a == 3:   # burst: thud + embers shower
            place(out, pk(thud(s, 110, 0.2, 0.04, grit=0.5)), 0.0, 0.8)
            place(out, crackles(0.6, 90, [(0, 1), (0.6, 0)]), 0.0, 1.0)
            place(out, blip(0.07, [(0, 1500 * p), (1, 1300 * p)], "i"), 0.03, 0.5)
        elif a == 4:   # giggle + spit
            place(out, blip(0.06, [(0, 1300 * p), (1, 1450 * p)]), 0.0, 0.6)
            place(out, fwoosh(0.35, [(0, 2500), (1, 600)], [(0, 0), (0.05, 1), (1, 0)]), 0.08, 0.9)
        elif a == 5:   # sizzling blast (long hiss)
            n = secs(0.55)
            place(out, pk(band(s.noise(n), 2000, 9000) * ctl(n, [(0, 0), (0.02, 1), (0.55, 0)])), 0.0, 0.7)
            place(out, pk(thud(s, 160, 0.12, 0.025, grit=0.3)), 0.0, 0.5)
        else:          # three fire flicks
            for j in range(3):
                place(out, fwoosh(0.12, [(0, 2000 + 300 * j), (1, 900)], [(0, 0), (0.1, 1), (1, 0)]), j * 0.09, 0.8)
        return out
    if ev == "hurt":
        out = buf(0.65)
        if a == 0:     # sizzle first, falling squeak inside it
            place(out, pk(breathy(s, 0.2, [(0, 4500), (0.2, 6000)], [(0, 0), (0.01, 1), (0.2, 0)], 0.8)), 0.0, 0.5)
            place(out, blip(0.18, [(0, 1750 * p), (1, 1000 * p)], [(0, "e"), (0.18, "u")], 0.15), 0.05)
        elif a == 1:   # "eep-eep"
            for j in range(2):
                place(out, blip(0.07, [(0, (1600 - 150 * j) * p), (1, (1400 - 150 * j) * p)]), j * 0.1, 0.9)
        elif a == 2:   # low "oof" blip + puff
            place(out, blip(0.12, [(0, 800 * p), (1, 600 * p)], [(0, "o"), (0.12, "u")], 0.25), 0.0)
            place(out, fwoosh(0.2, [(0, 1500), (1, 600)], [(0, 0), (0.05, 1), (1, 0)]), 0.0, 0.5)
        elif a == 3:   # flicker-out-then-back crackle
            place(out, crackles(0.3, 120, [(0, 1), (0.3, 0)]), 0.0, 1.0)
            place(out, blip(0.08, [(0, 1700 * p), (1, 1500 * p)]), 0.02, 0.7)
        elif a == 4:   # ouchy wobble
            n = secs(0.2)
            place(out, blip(0.2, [(0, 1400 * p), (1, 1100 * p)], [(0, "a"), (0.2, "i")]) * (1 + 0.35 * np.sin(2 * np.pi * 22 * T(n))), 0.0)
        elif a == 5:   # spark crack + squeak up
            place(out, pk(click(s, 0.04, 2000, 9000, 0.002)), 0.0, 0.8)
            place(out, blip(0.11, [(0, 1100 * p), (1, 1700 * p)]), 0.03, 0.8)
        else:          # steam hiss with a blip in the middle
            n = secs(0.4)
            place(out, pk(high(s.noise(n), 4000) * ctl(n, [(0, 0), (0.03, 1), (0.4, 0)])), 0.0, 0.5)
            place(out, blip(0.09, [(0, 1500 * p), (1, 1250 * p)], "e"), 0.06, 0.8)
        return out
    if ev == "death":
        out = buf(1.6)
        if a == 0:     # puff first, short falling squeak, rising steam
            place(out, pk(thud(s, 160, 0.12, 0.025, grit=0.3)), 0.0, 0.5)
            place(out, blip(0.35, [(0, 1500 * p), (1, 600 * p)], [(0, "i"), (0.35, "o")], 0.25), 0.04)
            n = secs(0.8)
            place(out, pk(nsweep(s, n, ctl(n, [(0, 2500), (0.8, 7000)]), 0.6) * ctl(n, [(0, 0), (0.4, 1), (0.8, 0)])), 0.35, 0.5)
        elif a == 1:   # pop! and embers rain
            place(out, pk(click(s, 0.05, 700, 5000, 0.005)), 0.0, 1.0)
            place(out, pk(thud(s, 130, 0.18, 0.04, grit=0.4)), 0.0, 0.6)
            place(out, crackles(1.2, 70, [(0, 1), (1.2, 0)]), 0.02, 1.0)
            place(out, blip(0.3, [(0, 1100 * p), (1, 700 * p)], "u"), 0.1, 0.5)
        elif a == 2:   # sad descending three-note sigh
            for j, f in enumerate((1300, 1100, 850)):
                place(out, blip(0.16, [(0, f * p), (1, f * p * 0.93)], [(0, "i"), (0.16, "u")]), j * 0.2, 0.9 - 0.15 * j)
            place(out, fwoosh(0.7, [(0, 1500), (1, 400)], [(0, 0.5), (1, 0)]), 0.5, 0.5)
        elif a == 3:   # flame gutters (sputter x3) and goes out
            for j in range(3):
                place(out, fwoosh(0.2, [(0, 900), (1, 400)], [(0, 0), (0.1, 1), (1, 0)]), j * 0.25, 0.8 - 0.2 * j)
                place(out, crackles(0.2, 60), j * 0.25, 0.5 - 0.1 * j)
            place(out, pk(high(s.noise(secs(0.5)), 4000) * ctl(secs(0.5), [(0, 0), (0.05, 0.5), (0.5, 0)])), 0.8, 0.4)
        elif a == 4:   # long wail falling, steam
            place(out, blip(0.9, [(0, 1500 * p), (0.2, 1400 * p), (1, 350 * p)], [(0, "a"), (0.5, "o"), (0.9, "u")], 0.3), 0.0)
            place(out, pk(breathy(s, 0.6, [(0, 5000), (0.6, 3500)], [(0, 0), (0.1, 0.8), (0.6, 0)], 0.7)), 0.5, 0.4)
        elif a == 5:   # implode: sweep in + thud + silence of ash
            place(out, fwoosh(0.4, [(0, 4000), (1, 300)], [(0, 0.2), (0.8, 1), (1, 0)]), 0.0, 0.9)
            place(out, pk(thud(s, 100, 0.3, 0.06, grit=0.4)), 0.38, 0.8)
            place(out, crackles(0.6, 25, [(0, 1), (0.6, 0)]), 0.42, 0.6)
        else:          # giggle turning into a fizz
            place(out, blip(0.07, [(0, 1200 * p), (1, 1300 * p)]), 0.0, 0.7)
            place(out, blip(0.07, [(0, 1100 * p), (1, 1150 * p)]), 0.11, 0.6)
            n = secs(0.9)
            place(out, pk(band(s.noise(n), 3000, 9000) * ctl(n, [(0, 0), (0.05, 1), (0.9, 0)]) * (0.6 + 0.4 * np.clip(C.wander(s, n, 50, 1), -1, 1))), 0.2, 0.6)
        return out
    raise KeyError(ev)


# =============================================================================== shroom (mushroom wraith)
def shroom_parts(s):
    def hum(d, f_pts, vowels=("m", "u"), breath=0.5, vib=(4.5, 0.02)):
        return pk(vocal(s, d, [(t * d, f) for t, f in f_pts], [(0, vowels[0]), (d, vowels[1])], [(0, 0), (d * 0.2, 1), (d * 0.7, 0.8), (d, 0)], 1.1,
                        tilt=1.4, breath=breath, vib=vib, fmax=6000))

    def puff(d=0.35, fc=1800):
        n = secs(d)
        x = nsweep(s, n, ctl(n, [(0, fc), (d, fc * 0.6)]), 1.0) * ctl(n, [(0, 0), (0.01, 1), (0.08, 0.5), (d, 0)])
        place(x, bloop(s, 260, 160, 0.1, 0.4), 0.0, 0.5)
        return pk(x)

    def bl(f0, f1, d=0.11, wet=0.3):
        return pk(bloop(s, f0, f1, d, wet))

    def squish(d=0.08):
        return pk(norm(low(s.noise(secs(d)), 1800)) * np.exp(-T(secs(d)) / 0.02))

    def spores(d=0.6):
        n = secs(d)
        return pk(high(s.noise(n), 6000) * ctl(n, [(0, 0), (0.05, 0.3), (d, 0)]))

    return hum, puff, bl, squish, spores


def shroom(s, ev, k):
    p = P(s)
    hum, puff, bl, squish, spores = shroom_parts(s)
    a = k % TAKES
    if ev == "idle":
        out = buf(1.3)
        if a == 0:     # three bloops + hum
            for j in range(3):
                f0 = u(s, 220, 380) * p
                place(out, bl(f0, f0 * 1.6), j * 0.17 + u(s, 0, 0.03), 0.6)
            place(out, hum(0.6, [(0, 250 * p), (0.5, 270 * p), (1, 235 * p)]), 0.45, 0.7)
        elif a == 1:   # long hum with wobble only
            place(out, hum(1.0, [(0, 230 * p), (0.5, 210 * p), (1, 240 * p)], ("u", "o"), 0.55, (3.5, 0.04)), 0.0, 0.8)
        elif a == 2:   # squelchy shuffle (bloops down) + puff
            for j in range(4):
                place(out, bl((420 - 50 * j) * p, (260 - 30 * j) * p, 0.09, 0.5), j * 0.11, 0.6)
            place(out, puff(0.3, 3500), 0.55, 0.3)
        elif a == 3:   # "ooh-hoo" two hums
            for j in range(2):
                place(out, hum(0.32, [(0, (300 - 40 * j) * p), (1, (280 - 40 * j) * p)], ("o", "u")), j * 0.4, 0.75)
        elif a == 4:   # spore sneeze: inhale + puff
            place(out, pk(breathy(s, 0.3, [(0, 1200), (0.3, 2200)], [(0, 0), (0.25, 1), (0.3, 0)], 0.6)), 0.0, 0.5)
            place(out, puff(0.35, 2400), 0.32, 0.8)
            place(out, spores(0.5), 0.36, 0.4)
        elif a == 5:   # drips: high bloops sparse
            for at in (0.0, 0.3, 0.42, 0.8):
                f0 = u(s, 500, 700) * p
                place(out, bl(f0, f0 * 1.4, 0.07, 0.2), at, 0.5)
            place(out, hum(0.4, [(0, 200 * p), (1, 190 * p)]), 0.5, 0.5)
        else:          # rubbery creak + hum
            place(out, pk(V.creak(s, 0.4, 150, 220, body=(220, 520, 1100), q=5, rough=0.12, wobble=8, swell=0.15, release=0.1)), 0.0, 0.45)
            place(out, hum(0.5, [(0, 260 * p), (1, 300 * p)], ("u", "o")), 0.35, 0.7)
        return out
    if ev == "alert":
        out = buf(1.25)
        if a == 0:     # descending "ooh" then two bloops
            place(out, pk(vocal(s, 0.6, [(0, 460 * p), (0.6, 320 * p)], [(0, "u"), (0.6, "o")], [(0, 0), (0.08, 1), (0.6, 0)], 1.1,
                                tilt=1.35, breath=0.6, vib=(7, 0.03), fmax=6000)), 0.0)
            place(out, bl(330, 200, 0.12), 0.62, 0.6)
            place(out, bl(300, 180, 0.12), 0.78, 0.5)
        elif a == 1:   # two short "hoo!" pops
            for j in range(2):
                place(out, bl(220, 380, 0.1), j * 0.3, 0.6)
                place(out, hum(0.2, [(0, (380 + 60 * j) * p), (1, (420 + 60 * j) * p)], ("o", "o"), 0.4), j * 0.3 + 0.03, 0.9)
        elif a == 2:   # wobbling cap: rubber creak + puff
            place(out, pk(V.creak(s, 0.5, 180, 260, body=(250, 600, 1200), q=5, rough=0.15, wobble=10, swell=0.1, release=0.1)), 0.0, 0.6)
            place(out, puff(0.3, 2000), 0.45, 0.8)
        elif a == 3:   # ghostly falling "aah"
            place(out, hum(0.7, [(0, 480 * p), (0.3, 440 * p), (1, 300 * p)], ("a", "u"), 0.65, (6, 0.03)), 0.0)
        elif a == 4:   # bloop chain rising + "hm!"
            for j in range(4):
                place(out, bl((200 + 70 * j) * p, (300 + 90 * j) * p, 0.08), j * 0.08, 0.6)
            place(out, hum(0.25, [(0, 350 * p), (1, 420 * p)], ("m", "m"), 0.3), 0.35, 0.8)
        elif a == 5:   # spore hiss + hum
            place(out, spores(0.6), 0.0, 0.7)
            place(out, hum(0.5, [(0, 320 * p), (1, 360 * p)], ("u", "o")), 0.1, 0.8)
        else:          # high giggle-ish "hee hee" hums
            for j in range(3):
                place(out, hum(0.12, [(0, (520 - 30 * j) * p), (1, (480 - 30 * j) * p)], ("i", "i"), 0.5, (0, 0)), j * 0.15, 0.7)
        return out
    if ev == "windup":     # 0.8 s
        out = buf(1.05)
        d = 0.8 * [1.0, 0.93, 1.07, 1.0, 0.95, 1.05, 1.0][a]
        n = secs(d)
        if a == 0:     # fast-wobbling intake alone, then a short high hum
            wob = 0.5 + 0.5 * np.sin(2 * np.pi * 13 * T(n))
            place(out, pk(nsweep(s, n, ctl(n, [(0, 900), (d, 2500)]), 0.6) * ctl(n, [(0, 0), (d * 0.6, 1), (d, 0)]) * wob), 0.0, 0.8)
            place(out, hum(d * 0.35, [(0, 420 * p), (1, 480 * p)], ("o", "o"), 0.4), d * 0.65, 0.8)
        elif a == 1:   # pulsing swell (3 breaths)
            for j in range(3):
                place(out, pk(breathy(s, d * 0.28, [(0, 600 + 300 * j), (d * 0.28, 900 + 300 * j)], [(0, 0), (d * 0.2, 1), (d * 0.28, 0)], 0.7)), j * d * 0.32, 0.5 + 0.15 * j)
            place(out, hum(d * 0.4, [(0, 300 * p), (1, 420 * p)]), d * 0.6, 0.7)
        elif a == 2:   # balloon squeak rising
            place(out, pk(V.creak(s, d, 140, 320, body=(250, 600, 1300), q=6, rough=0.1, wobble=6, swell=0.2, release=0.08)), 0.0, 0.8)
            place(out, hum(d, [(0, 250 * p), (1, 300 * p)], ("u", "u"), 0.6), 0.0, 0.4)
        elif a == 3:   # bubbling rise
            for j in range(7):
                place(out, bl((180 + 50 * j) * p, (260 + 60 * j) * p, 0.08), j * d * 0.13, 0.4 + 0.07 * j)
        elif a == 4:   # held "mmm" with tremble, puff at end
            place(out, hum(d * 0.9, [(0, 280 * p), (1, 330 * p)], ("m", "m"), 0.3, (9, 0.04)), 0.0)
            place(out, puff(0.15, 2500), d * 0.9, 0.4)
        elif a == 5:   # sucking intake (reverse puff)
            place(out, pk(nsweep(s, n, ctl(n, [(0, 3000), (d, 900)]), 0.9) * ctl(n, [(0, 0), (d * 0.95, 1), (d, 0)]) ** 1.5), 0.0, 0.8)
            place(out, bl(300, 200, 0.12), d * 0.95, 0.4)
        else:          # wobble hum falling then rising
            place(out, hum(d, [(0, 320 * p), (0.4, 260 * p), (1, 400 * p)], ("o", "u"), 0.5, (7, 0.035)), 0.0)
        return out
    if ev == "strike":
        out = buf(0.85)
        if a == 0:     # spore puff
            place(out, puff(0.5, 1600), 0.0)
            place(out, spores(0.6), 0.05, 0.6)
        elif a == 1:   # double puff
            place(out, puff(0.25, 2000), 0.0, 0.9)
            place(out, puff(0.3, 1500), 0.17, 0.8)
        elif a == 2:   # sneeze-burst "pshh"
            place(out, pk(burst(s, 0.4, 1500, 8000, 0.09, 0.004)), 0.0, 0.9)
            place(out, bl(300, 140, 0.1), 0.0, 0.6)
        elif a == 3:   # cap slam (squish + thud) + spores
            place(out, squish(0.1), 0.0, 0.9)
            place(out, pk(thud(s, 120, 0.2, 0.04, grit=0.3)), 0.0, 0.7)
            place(out, spores(0.5), 0.04, 0.7)
        elif a == 4:   # low whump + rising spores
            m = secs(0.4)
            place(out, pk(nsweep(s, m, ctl(m, [(0, 300), (0.4, 1200)]), 0.9) * ctl(m, [(0, 0), (0.02, 1), (0.4, 0)])), 0.0, 0.9)
            place(out, pk(high(s.noise(secs(0.6)), 5000) * ctl(secs(0.6), [(0, 0), (0.3, 0.6), (0.6, 0)])), 0.1, 0.5)
        elif a == 5:   # "hah!" + puff
            place(out, hum(0.12, [(0, 450 * p), (1, 380 * p)], ("a", "a"), 0.5, (0, 0)), 0.0, 0.7)
            place(out, puff(0.4, 1800), 0.08)
        else:          # bloop-bloop-puff
            place(out, bl(400, 250, 0.08), 0.0, 0.6)
            place(out, bl(350, 200, 0.08), 0.09, 0.6)
            place(out, puff(0.4, 1700), 0.17)
        return out
    if ev == "hurt":
        out = buf(0.65)
        if a == 0:     # "u-u" and a late squish
            for j in range(2):
                place(out, pk(vocal(s, 0.1, [(0, (760 - 80 * j) * p), (0.1, (640 - 80 * j) * p)], "u", [(0, 0), (0.01, 1), (0.1, 0)], 1.15, tilt=1.2, breath=0.3)), j * 0.13, 0.9)
            place(out, squish(), 0.28, 0.7)
        elif a == 1:   # "oo!" short + squish
            place(out, hum(0.12, [(0, 700 * p), (1, 600 * p)], ("o", "u"), 0.3, (0, 0)), 0.0)
            place(out, squish(0.06), 0.1, 0.7)
        elif a == 2:   # double squish + whimper
            place(out, squish(0.07), 0.0, 0.9)
            place(out, squish(0.07), 0.08, 0.6)
            place(out, hum(0.2, [(0, 520 * p), (1, 450 * p)], ("u", "u"), 0.6), 0.12, 0.7)
        elif a == 3:   # cap dent: rubber creak short + bloop
            place(out, pk(V.creak(s, 0.15, 260, 180, body=(260, 600, 1200), q=5, rough=0.1, swell=0.01, release=0.05)), 0.0, 0.7)
            place(out, bl(500, 300, 0.1), 0.05, 0.6)
        elif a == 4:   # spore cough
            place(out, puff(0.15, 2600), 0.0, 0.7)
            place(out, puff(0.12, 2200), 0.13, 0.6)
        elif a == 5:   # high squeak
            place(out, hum(0.14, [(0, 900 * p), (1, 1050 * p)], ("i", "i"), 0.3, (0, 0)), 0.0)
        else:          # squelch + falling "ooh"
            place(out, bl(500, 200, 0.12, 0.6), 0.0, 0.7)
            place(out, hum(0.25, [(0, 650 * p), (1, 450 * p)], ("o", "u")), 0.05, 0.8)
        return out
    if ev == "death":
        out = buf(1.8)
        if a == 0:     # spore puff first, then a wheeze that rises and sinks
            place(out, puff(0.4, 1800), 0.0, 0.9)
            place(out, pk(vocal(s, 0.8, [(0, 260 * p), (0.3, 380 * p), (0.8, 170 * p)], [(0, "u"), (0.8, "o")], [(0, 0), (0.1, 1), (0.8, 0)], 1.1,
                                tilt=1.4, breath=0.65, vib=(4, 0.04), fmax=6000)), 0.3)
        elif a == 1:   # pop + spore cloud long
            place(out, bl(500, 150, 0.15, 0.7), 0.0, 0.9)
            place(out, puff(0.8, 2000), 0.05)
            place(out, spores(1.0), 0.2, 0.6)
        elif a == 2:   # melting: bloops descending x5
            for j in range(5):
                place(out, bl((450 - 60 * j) * p, (300 - 40 * j) * p, 0.12, 0.5), j * 0.18, 0.8 - 0.1 * j)
            place(out, hum(0.5, [(0, 250 * p), (1, 150 * p)], ("u", "u"), 0.7), 0.4, 0.5)
        elif a == 3:   # sad "oh-oh-ooo" falling
            for j, f in enumerate((450, 380, 300)):
                place(out, hum(0.25 + 0.15 * j, [(0, f * p), (1, f * p * 0.85)], ("o", "u")), j * 0.3, 0.9 - 0.15 * j)
        elif a == 4:   # collapse: squish + thud + air leak
            place(out, squish(0.12), 0.0, 0.9)
            place(out, pk(thud(s, 110, 0.3, 0.06, grit=0.3)), 0.05, 0.8)
            n = secs(0.9)
            place(out, pk(nsweep(s, n, ctl(n, [(0, 2500), (0.9, 900)]), 0.5) * ctl(n, [(0, 0), (0.1, 0.7), (0.9, 0)])), 0.15, 0.6)
        elif a == 5:   # long ghostly wail fading with wobble
            place(out, hum(1.2, [(0, 500 * p), (0.3, 520 * p), (1, 200 * p)], ("a", "u"), 0.7, (5, 0.05)), 0.0)
        else:          # sneeze-out: three puffs shrinking
            for j in range(3):
                place(out, puff(0.3 - 0.06 * j, 2200 - 300 * j), j * 0.28, 0.9 - 0.2 * j)
            place(out, bl(260, 140, 0.18, 0.6), 0.9, 0.5)
        return out
    raise KeyError(ev)


SPECIES_FN = {"wolf": wolf, "boar": boar, "brute": brute, "wisp": wisp, "shroom": shroom}
EVENTS = ["idle", "alert", "windup", "strike", "hurt", "death"]


def voice_take(species, ev):
    def fn(s, k):
        x = SPECIES_FN[species](s, ev, k)
        if species == "brute" and ev in ("idle", "alert", "windup"):
            x = low(x, 3800, 2)
        return room(s, x, 0.6, 0.1, 5000)
    return fn


# =============================================================================== region layers (runtime colour)
def layer(region, kind):
    def fn(s, k):
        out = buf(1.1)
        if region == "forest":
            snap = lambda at, g=1.0, f=None: place(out, pk(np.asarray(modal([f or u(s, 1300, 1600), (f or 1450) * 1.64, (f or 1450) * 2.64], [0.01, 0.007, 0.005], [1, 0.5, 0.3], 0.06, s.rng))  # noqa: E731
                                                          + click(s, 0.03, 1200, 6000, 0.002)), at, g)
            leaves = lambda at, d, g=0.6, pts=None: place(out, pk(rustle(s, secs(d), ctl(secs(d), rel(d, pts or [(0, 0), (0.15, 1), (1, 0)])), 0.45)), at, g)  # noqa: E731
            if kind == "accent":
                [lambda: (snap(0.0), leaves(0.02, 0.35)),
                 lambda: (place(out, pk(np.asarray(modal([780, 1290, 2050], [0.025, 0.015, 0.01], [1, 0.6, 0.3], 0.12, s.rng)) + click(s, 0.04, 600, 4000, 0.004)), 0.0, 1.0),
                          place(out, pk(V.crackle(s, 0.2, 120, 0.005)), 0.02, 0.6)),
                 lambda: leaves(0.0, 0.45, 0.9, [(0, 0), (0.05, 1), (0.4, 0.5), (1, 0)]),
                 lambda: (snap(0.0), [place(out, pk(rustle(s, secs(0.05), np.ones(secs(0.05)), 0.4)), 0.1 + 0.08 * j, 0.3) for j in range(4)]),
                 lambda: (place(out, pk(V.crackle(s, 0.3, 90, 0.01)), 0.0, 0.7), leaves(0.05, 0.3, 0.4)),
                 lambda: (place(out, pk(shaped(s, 0.15, [(0, 800), (1, 2500)], [(0, 0), (0.7, 1), (1, 0)], 0.5)), 0.0, 0.5), snap(0.13, 0.8))][k % 6]()
            else:
                d = [0.7, 0.9, 0.55, 1.0][k % 4]
                n = secs(d)
                if k % 4 == 0:     # leaf rustle swell
                    leaves(0.0, d, 1.0, [(0, 0), (0.3, 1), (1, 0)])
                elif k % 4 == 1:   # moss squish: low, soft
                    place(out, pk(norm(band(s.noise(n), 300, 1400)) * (0.5 + 0.5 * np.abs(C.wander(s, n, 6, 1))) * ctl(n, [(0, 0), (d * 0.2, 0.7), (d * 0.5, 0.3), (d * 0.75, 1), (d, 0)])), 0.0, 0.9)
                elif k % 4 == 2:   # sparse twig crackle
                    place(out, pops(s, n, 30, 900, 5000, ctl(n, [(0, 1), (d, 0.2)]), (0.002, 0.005)), 0.0, 1.0)
                    leaves(0.0, d, 0.3, [(0, 0), (0.1, 1), (1, 0)])
                else:              # pine needle hiss with flutter
                    place(out, pk(high(s.noise(n), 4000) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 11 * T(n)))) * ctl(n, [(0, 0), (d * 0.8, 1), (d, 0)])), 0.0, 0.8)
        elif region == "quarry":
            flare = lambda at, d=0.5, g=0.7, up=True: place(out, pk(nsweep(s, secs(d), ctl(secs(d), [(0, 400), (d, 1800)] if up else [(0, 1800), (d, 500)]), 0.8)  # noqa: E731
                                                                    * ctl(secs(d), [(0, 0), (0.05, 1), (d, 0)])), at, g)
            crack = lambda at, d, dens, g=1.0, pts=None: place(out, pops(s, secs(d), dens, 1200, 7500, ctl(secs(d), pts or [(0, 1), (d, 0)]), (0.0015, 0.006)), at, g)  # noqa: E731
            if kind == "accent":
                [lambda: (flare(0.0), crack(0.0, 0.5, 70)),
                 lambda: (flare(0.0, 0.25, 0.7), flare(0.2, 0.3, 0.6, False)),
                 lambda: crack(0.0, 0.4, 160),
                 lambda: (place(out, pk(high(s.noise(secs(0.4)), 3500) * ctl(secs(0.4), [(0, 0), (0.03, 1), (0.4, 0)])), 0.0, 0.5), crack(0.0, 0.4, 50)),
                 lambda: (place(out, pk(thud(s, 90, 0.25, 0.06, grit=0.2)), 0.0, 0.6), crack(0.03, 0.5, 60, 1.0, [(0, 0.3), (0.1, 1), (0.5, 0)])),
                 lambda: (place(out, pk(band(s.noise(secs(0.6)), 2500, 8000) * ctl(secs(0.6), [(0, 0), (0.05, 1), (0.6, 0)]) * (0.6 + 0.4 * np.clip(C.wander(s, secs(0.6), 40, 1), -1, 1))), 0.0, 0.6),
                          crack(0.1, 0.3, 30))][k % 6]()
            else:
                d = [0.7, 0.9, 0.55, 1.0][k % 4]
                place(out, pk(fire(s, d, 150, 1400, [4, 7, 10, 5][k % 4])) * ctl(secs(d), [(0, 0), (d * [0.3, 0.6, 0.15, 0.8][k % 4], 1), (d, 0)])[: secs(d)], 0.0, 0.6)
                crack(0.0, d, [30, 55, 80, 20][k % 4], 0.9, [(0, 0.2), (d * 0.5, 1), (d, 0)])
        else:  # frost
            ice = lambda at, g=1.0: place(out, pk(click(s, 0.04, 2500, 10000, 0.002)), at, g)  # noqa: E731
            glint = lambda at, d, dens, g=0.8, lo=3500: place(out, tinkles(s, secs(d), dens, lo, 9500, ctl(secs(d), [(0, 1), (d, 0)])), at, g)  # noqa: E731
            if kind == "accent":
                [lambda: (ice(0.0), glint(0.01, 0.4, 40)),
                 lambda: (ice(0.0), ice(0.05, 0.7), glint(0.06, 0.3, 30)),
                 lambda: glint(0.0, 0.5, 110, 1.0, 3000),
                 lambda: (place(out, pk(V.creak(s, 0.3, 1100, 800, body=(1300, 2600, 4400), q=8, rough=0.15, swell=0.02, release=0.1)), 0.0, 0.6), ice(0.25, 0.6)),
                 lambda: [place(out, pk(L.modal(SR, f, "glass", dur=0.5, rng=s.rng)), 0.03 * j, 0.5) for j, f in enumerate((2637, 3136, 3951))],
                 lambda: (place(out, pops(s, secs(0.25), 200, 2000, 9000, ctl(secs(0.25), [(0, 1), (0.25, 0)]), (0.001, 0.003)), 0.0, 1.0), glint(0.05, 0.3, 20))][k % 6]()
            else:
                d = [0.7, 0.9, 0.55, 1.0][k % 4]
                n = secs(d)
                place(out, pk(nsweep(s, n, [6500, 5000, 8000, 4500][k % 4], 0.5) * ctl(n, [(0, 0), (d * [0.3, 0.6, 0.15, 0.8][k % 4], 1), (d, 0)])), 0.0, 0.5)
                glint(0.0, d, [12, 25, 40, 8][k % 4], 0.9)
        return room(s, out, [0.55, 0.8, 1.05][["forest", "quarry", "frost"].index(region)], 0.12, [5000, 3800, 8500][["forest", "quarry", "frost"].index(region)])
    return fn


# =============================================================================== locomotion
# Every take is its own footfall: contact count and spacing, body pitch (>= 15 % apart), claw or
# hoof click, and a surface layer, so two takes never differ by pitch alone.
PAW = [  # pad Hz, contact gaps (s), claws, layer, pad decay
    (150, (), 0, "", 0.018), (190, (), 1, "scuff", 0.014), (120, (0.07,), 0, "", 0.022), (235, (), 2, "leaves", 0.012),
    (165, (0.045, 0.05), 0, "", 0.016), (178, (), 0, "gravel", 0.035), (210, (0.04,), 1, "scuff", 0.014), (100, (), 0, "drag", 0.02)]
HOOF = [  # click Hz, gaps, body Hz, layer
    (600, (), 105, ""), (760, (0.09,), 115, ""), (480, (), 95, "gravel"), (920, (), 120, "scrape"),
    (650, (0.05, 0.08), 110, ""), (0, (), 85, "dirt"), (1100, (), 78, "ring"), (840, (0.04,), 100, "dirt")]
STOMP = [  # body Hz, decay, gaps, layer
    (55, 0.08, (), ""), (48, 0.12, (), "debris"), (62, 0.06, (), "rumble"), (72, 0.05, (), "crack"),
    (52, 0.09, (0.13,), "creak"), (44, 0.14, (), "late"), (68, 0.07, (0.1,), "moss"), (58, 0.1, (), "click")]


def step(gait):
    def fn(s, k):
        out = buf(0.6)
        if gait == "paw":
            f, gaps, claws, lay, tau = PAW[k % len(PAW)]
            ats = [0.0] + list(np.cumsum(gaps))
            for j, at in enumerate(ats):
                place(out, pk(thud(s, f * u(s, 0.97, 1.03) * (1 + 0.06 * j), 0.1, tau, drop=0.3, grit=0.5)), at, 1.0 - 0.2 * j)
            for j in range(claws):
                place(out, pk(click(s, 0.015, 3000, 8000, 0.0008)), 0.004 + 0.025 * j, 0.45)
            if lay == "scuff":
                place(out, pk(burst(s, 0.08, 400, 3000, 0.025, 0.005)), 0.01, 0.4)
            elif lay == "leaves":
                place(out, pk(rustle(s, secs(0.12), ctl(secs(0.12), [(0, 0), (0.01, 1), (0.12, 0)]))), 0.0, 0.5)
            elif lay == "gravel":
                place(out, pops(s, secs(0.12), 260, 800, 5000, ctl(secs(0.12), [(0, 1), (0.12, 0)]), (0.001, 0.003)), 0.02, 1.0)
            elif lay == "drag":
                place(out, pk(scrape(s, 0.14, 250, 2500)), 0.02, 0.5)
        elif gait == "hoof":
            fc, gaps, fb, lay = HOOF[k % len(HOOF)]
            ats = [0.0] + list(np.cumsum(gaps))
            for j, at in enumerate(ats):
                g = 1.0 - 0.2 * j
                if fc:
                    place(out, tok(s, fc * u(s, 0.97, 1.03) * (1 + 0.05 * j), 0.03 if lay == "ring" else 0.015, (1.0, 2.1, 3.3)), at, 0.7 * g)
                place(out, pk(thud(s, fb * u(s, 0.97, 1.03), 0.12, 0.025, grit=0.7)), at, g)
            if lay == "gravel":
                place(out, pops(s, secs(0.15), 160, 800, 5000, ctl(secs(0.15), [(0, 1), (0.15, 0)]), (0.001, 0.004)), 0.01, 1.0)
            elif lay == "scrape":
                place(out, pk(scrape(s, 0.12, 300, 3000)), 0.02, 0.45)
            elif lay == "dirt":
                place(out, pk(burst(s, 0.1, 300, 2500, 0.03, 0.004)), 0.005, 0.6)
        elif gait == "stomp":
            fb, tau, gaps, lay = STOMP[k % len(STOMP)]
            ats = [0.0] + list(np.cumsum(gaps))
            for j, at in enumerate(ats):
                place(out, pk(thud(s, fb * u(s, 0.97, 1.03), 0.35, tau, drop=0.4, body=1.4, grit=0.8)), at, 1.0 - 0.25 * j)
            if lay == "debris":
                place(out, debris(s, secs(0.45), 8, 0.02, 0.3, (0.3, 0.6), 0.6), 0.0, 1.0)
            elif lay == "rumble":
                place(out, pk(band(s.noise(secs(0.35)), 60, 400) * ctl(secs(0.35), [(0, 0), (0.03, 1), (0.35, 0)])), 0.0, 0.7)
            elif lay == "crack":
                place(out, pk(rock(s, 1.4)), 0.0, 0.7)
                place(out, pk(click(s, 0.04, 1500, 8000, 0.002)), 0.0, 0.5)
            elif lay == "creak":
                place(out, pk(V.creak(s, 0.25, 50, 42, body=(90, 200, 420), q=6, rough=0.3, swell=0.02, release=0.08)), 0.02, 0.6)
            elif lay == "late":
                place(out, debris(s, secs(0.55), 5, 0.12, 0.3, (0.4, 0.8), 0.7), 0.0, 1.0)
            elif lay == "moss":
                place(out, pk(rustle(s, secs(0.22), ctl(secs(0.22), [(0, 0), (0.02, 1), (0.22, 0)]), 0.3)), 0.0, 0.6)
            elif lay == "click":
                place(out, pk(click(s, 0.04, 800, 4000, 0.004)), 0.0, 0.55)
                place(out, pk(rock(s, 0.8)), 0.01, 0.4)
                place(out, pk(band(s.noise(secs(0.25)), 70, 500) * ctl(secs(0.25), [(0, 0), (0.02, 1), (0.25, 0)])), 0.0, 0.5)
        elif gait == "squelch":
            arch = k % 8
            [lambda: place(out, pk(bloop(s, u(s, 300, 360), u(s, 140, 170), 0.12, 0.6)), 0.0),
             lambda: (place(out, pk(bloop(s, 420, 200, 0.08, 0.5)), 0.0), place(out, pk(bloop(s, 360, 180, 0.08, 0.5)), 0.06, 0.6)),
             lambda: place(out, pk(norm(low(s.noise(secs(0.1)), 1400)) * np.exp(-T(secs(0.1)) / 0.025)), 0.0),
             lambda: (place(out, pk(bloop(s, 200, 380, 0.1, 0.3)), 0.0), place(out, pk(norm(low(s.noise(secs(0.06)), 2000)) * np.exp(-T(secs(0.06)) / 0.015)), 0.0, 0.6)),
             lambda: place(out, pk(bloop(s, u(s, 520, 600), u(s, 260, 300), 0.07, 0.4)), 0.0),
             lambda: (place(out, pk(thud(s, 130, 0.12, 0.03, grit=0.2)), 0.0, 0.7), place(out, pk(bloop(s, 300, 160, 0.1, 0.5)), 0.01, 0.6)),
             lambda: [place(out, pk(bloop(s, u(s, 250, 450), u(s, 150, 250), 0.06, 0.4)), 0.035 * j, 0.6) for j in range(3)],
             lambda: place(out, pk(bloop(s, 240, 120, 0.18, 0.7)), 0.0)][arch]()
        else:  # flutter: hovering flame
            arch = k % 6
            d = [0.3, 0.36, 0.26, 0.4, 0.32, 0.34][arch]
            hz = [14, 9, 20, 11, 16, 7][arch]
            fc = [[(0, 600), (1, 1400)], [(0, 1300), (1, 500)], [(0, 700), (0.5, 1600), (1, 700)], [(0, 900), (1, 900)], [(0, 400), (1, 1100)], [(0, 1600), (0.5, 700), (1, 1200)]][arch]
            place(out, pk(shaped(s, d, fc, [(0, 0), (0.4, 1), (1, 0)], 0.7, (hz, 0.75))), 0.0)
            if arch % 2:
                place(out, pops(s, secs(d), 40, 1500, 7000), 0.0, 0.5)
        return room(s, out, 0.4, 0.06)
    return fn


def boar_charge(s, k):
    grunt, snort, squeal, hoof, tusk = boar_parts(s)
    p = P(s)
    out = buf(1.3)
    count, gap, voice = [(5, 0.11, "squeal"), (6, 0.095, "grunt"), (4, 0.13, "snort"), (7, 0.085, "roar"), (5, 0.1, "none"), (6, 0.12, "squeal2")][k % 6]
    for j in range(count):
        at = j * gap * u(s, 0.92, 1.08)
        place(out, hoof(u(s, 80, 100)), at, 0.6 + 0.4 * j / count)
        if j % 2:
            place(out, pk(burst(s, 0.06, 300, 2500, 0.02)), at + 0.01, 0.25)    # dirt kicked up
    if voice == "squeal":
        place(out, squeal(0.4, [(0, 600 * p), (0.3, 1100 * p), (1, 900 * p)]), 0.05, 0.8)
    elif voice == "grunt":
        for j in range(3):
            place(out, grunt(0.1, (120 + 10 * j) * p, "a"), j * 0.19, 0.7)
    elif voice == "snort":
        place(out, snort(0.2, 2000), 0.0, 0.8)
    elif voice == "roar":
        place(out, grunt(0.5, 115 * p, "a"), 0.0, 0.9)
    elif voice == "squeal2":
        place(out, squeal(0.2, [(0, 900 * p), (1, 1200 * p)]), 0.1, 0.7)
        place(out, squeal(0.25, [(0, 1000 * p), (1, 800 * p)]), 0.4, 0.6)
    place(out, pk(shaped(s, count * gap, [(0, 300), (1, 900)], [(0, 0), (0.7, 1), (1, 0)], 0.7, body=0.6)), 0.0, 0.35)
    return room(s, out, 0.6, 0.1, 5000)


def boar_dazed(s, k):
    grunt, snort, squeal, hoof, tusk = boar_parts(s)
    p = P(s)
    out = buf(1.4)
    n = secs(0.6)
    wob = 1 + 0.12 * np.sin(2 * np.pi * u(s, 4, 6) * T(n))
    a = k % 6
    woozy = lambda f0, f1, g=0.9: place(out, pk(vocal(s, 0.6, [(0, f0 * p), (0.6, f1 * p)], [(0, "o"), (0.6, "u")], [(0, 0), (0.05, 1), (0.6, 0)], 0.75,  # noqa: E731
                                                    tilt=0.8, breath=0.3, sub=0.5, flutter=0.5, fmax=4500) * wob), 0.0, g)
    shake = lambda at, g=0.5: place(out, pk(band(s.noise(secs(0.35)), 700, 4000) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 8 * T(secs(0.35)))))  # noqa: E731
                                            * ctl(secs(0.35), [(0, 0), (0.05, 1), (0.35, 0)])), at, g)
    if a == 0:         # woozy falling grunt
        woozy(130, 85)
    elif a == 1:       # snort + head shake rattle
        place(out, snort(0.15), 0.0, 0.8)
        shake(0.18)
    elif a == 2:       # wobbly squeal
        place(out, squeal(0.4, [(0, 700 * p), (0.5, 600 * p), (1, 650 * p)]) * (1 + 0.2 * np.sin(2 * np.pi * 7 * T(secs(0.4)))), 0.0, 0.7)
    elif a == 3:       # three grunts sliding down
        for j in range(3):
            place(out, grunt(0.12, (125 - 15 * j) * p, "o"), j * 0.17, 0.8 - 0.15 * j)
    elif a == 4:       # long wheezy snort
        place(out, snort(0.4, 1300), 0.0, 0.8)
        place(out, pk(breathy(s, 0.4, [(0, 1100), (0.4, 600)], [(0, 0), (0.05, 0.7), (0.4, 0)], 0.8)), 0.35, 0.5)
    else:              # high woozy + shake
        woozy(170, 120, 0.7)
        shake(0.5, 0.45)
    stars = [(1568.0, 1975.5), (2093.0, 1760.0, 2093.0), (1318.5, 1568.0), (1760.0,), (2349.0, 1975.5), (1975.5, 2349.0, 1975.5)][k % 6]
    for j, f in enumerate(stars):
        place(out, pk(C.bell(s, f, 0.5, 0.25, 0.6)), 0.35 + j * 0.15, 0.22)
    return room(s, out, 0.6, 0.1, 6000)


def families(Fam) -> list:
    F = []
    for sp in SPECIES_FN:
        for ev in EVENTS:
            F.append(Fam("creatures", CREAT, "%s_%s" % (sp, ev), TAKES, voice_take(sp, ev), SR22, float(EVENT_DB[ev]), MAX_LEN[ev], start=1))
    for region in ("forest", "quarry", "frost"):
        F.append(Fam("layers", CREAT, "layer_%s_accent" % region, 6, layer(region, "accent"), SR22, -21.0, 1.1, start=1))
        F.append(Fam("layers", CREAT, "layer_%s_bed" % region, 4, layer(region, "bed"), SR22, -21.0, 1.2, start=1))
    for gait, n in (("paw", 8), ("hoof", 8), ("stomp", 8), ("squelch", 8), ("flutter", 6)):
        F.append(Fam("steps", CREAT, "step_" + gait, n, step(gait), SR22, -22.0, 0.6, start=1))
    F.append(Fam("creatures", CREAT, "boar_charge", 6, boar_charge, SR22, -16.5, 1.3, start=1))
    F.append(Fam("creatures", CREAT, "boar_dazed", 6, boar_dazed, SR22, -17.0, 1.4, start=1))
    return F
