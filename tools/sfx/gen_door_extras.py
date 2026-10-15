"""Door sounds the door hooks need beyond each room's open/close takes (game/scripts/door_audio.gd).

Writes mono 16-bit WAVs into game/assets/sfx/doors/:
  locked_<n>.wav  a handle tried against a locked latch: two to four quick metal clacks, each
                  knocking the door body (4 takes)
  swing_<n>.wav   a slow hinge creak for a door leaf swinging open or shut on screen, 1.2-2.4 s:
                  stick-slip pulses through the wooden leaf, gliding in pitch (4 takes)

Levels follow the home door: locked sits 1 dB under home_close.wav, swing 4 dB under
home_open.wav (it plays under the open/close takes, not instead of them).

  $env:SFX_BASE='merge-version-gate'; .tools/art-venv/Scripts/python.exe tools/sfx/gen_door_extras.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DOORS = ROOT / "game/assets/sfx/doors"
SR = 22050


def locked(rng, i):
    jiggles, f_metal, f_wood = L.cycle(i, (2, 3, 4, 3), (2100, 2650, 1850, 2400), (150, 128, 172, 140))
    out = np.zeros(L.secs(0.9, SR))
    t = 0.0
    for k in range(jiggles):
        clack = L.modal(SR, f_metal * rng.uniform(0.94, 1.06), "metal", dur=0.12, rng=rng, tau=0.035, click=0.6)
        body = L.modal(SR, f_wood * rng.uniform(0.92, 1.08), "wood", dur=0.18, rng=rng, tau=0.06)
        grain = L.bp(L.noise(L.secs(0.03, SR), rng, "white"), SR, 1500, 6000) * L.exp_decay(0.03, SR, 0.006)
        g = rng.uniform(0.75, 1.0) * (0.85 if k == jiggles - 1 else 1.0)
        L.place(out, clack, t, SR, 0.55 * g)
        L.place(out, body, t + rng.uniform(0.002, 0.008), SR, 0.8 * g)
        L.place(out, grain, t, SR, 0.25 * g)
        t += rng.uniform(0.07, 0.13)
    return L.reverb(out[: L.secs(t + 0.25, SR)], SR, room=0.18, wet=0.1, rng=rng), {"jiggles": jiggles}


def swing(rng, i):
    dur, f_lo, f_hi, shape = L.cycle(i, (1.6, 2.2, 1.3, 1.9), (38, 52, 30, 45), (110, 85, 140, 95),
                                     ("rise", "fall", "wobble", "rise-fall"))
    dur *= rng.uniform(0.92, 1.08)
    n = L.secs(dur, SR)
    u = np.linspace(0.0, 1.0, n)
    curve = {"rise": u, "fall": 1.0 - u, "wobble": 0.5 + 0.5 * np.sin(2 * np.pi * u * rng.uniform(1.2, 2.0)),
             "rise-fall": np.sin(np.pi * u)}[shape]
    freq = f_lo + (f_hi - f_lo) * curve * (1.0 + 0.06 * np.sin(2 * np.pi * u * rng.uniform(5, 9)))
    phase = np.cumsum(freq) / SR
    pulses = np.zeros(n)
    idx = np.nonzero(np.diff(np.floor(phase)) > 0)[0]
    pulses[idx] = rng.uniform(0.6, 1.0, idx.size)
    leaf = L.resonate(pulses, SR, [f * rng.uniform(0.95, 1.05) for f in (310, 720, 1180, 1960, 2900)],
                      [0.02, 0.014, 0.01, 0.007, 0.005], [1.0, 0.7, 0.5, 0.3, 0.18])
    hiss = L.bp(L.noise(n, rng, "pink"), SR, 900, 4200) * 0.08
    env = np.sin(np.pi * u) ** 0.6 * (0.7 + 0.3 * curve)
    x = (leaf + hiss) * env
    return L.reverb(L.lp(x, SR, 6500), SR, room=0.3, wet=0.14, rng=rng), {"shape": shape, "dur": round(dur, 2)}


def main() -> int:
    ref_close = L.ref_db_of(DOORS / "home_close.wav")
    ref_open = L.ref_db_of(DOORS / "home_open.wav")
    total = 0
    for event, fn, ref in (("locked", locked, ref_close - 1.0), ("swing", swing, ref_open - 4.0)):
        meta = L.make_family(DOORS, event, 4, fn, sr=SR, ref_db=ref, seed_base="doors", verbose=False)
        b = sum(d["bytes"] for d in meta)
        total += b
        print("%-7s 4 takes %6.1f KB  st %.1f..%.1f (ref %.1f)" % (event, b / 1024, min(d["st_db"] for d in meta),
                                                                 max(d["st_db"] for d in meta), ref))
    print("TOTAL %.1f KB" % (total / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
