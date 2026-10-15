"""Gap check on the front silhouette written by inspect_body.py.

  python tools/body_gen/gap_check.py <out_dir>

Scans each row of mask_front.png and counts separate runs of body pixels.
In a clean A-pose the rows between the armpits and the finger tips show
arm | torso-or-legs | arm, and the rows from the crotch down to the ankles show
two legs. A row where an arm or a leg merges back into its neighbour is a place
where the parts touch and will drag each other when animated.
Adds "gaps" to stats.json and writes gap_overlay.png (red = touching rows).
"""
import json
import os
import sys

import numpy as np
from PIL import Image

out = sys.argv[1]
mask = np.array(Image.open(os.path.join(out, "mask_front.png")).convert("L")) > 128
h, w = mask.shape
rows = np.where(mask.any(axis=1))[0]
top, bottom = rows[0], rows[-1]
height = bottom - top + 1


def runs(row):
    r, start = [], None
    for x in range(w):
        if row[x] and start is None:
            start = x
        elif not row[x] and start is not None:
            r.append((start, x - 1))
            start = None
    if start is not None:
        r.append((start, w - 1))
    return [s for s in r if s[1] - s[0] >= 2]  # ignore 1-2 px specks


info = [runs(mask[y]) for y in range(h)]
centre = w / 2
# Arms: outermost runs that sit clearly left/right of the body centre column.
# Arms = the longest block of rows with 3+ runs (hair tufts or ears make short blocks).
blocks, cur = [], []
for y in range(top + int(height * 0.12), bottom):
    if len(info[y]) >= 3:
        if cur and y - cur[-1] > 4:
            blocks.append(cur)
            cur = []
        cur.append(y)
if cur:
    blocks.append(cur)
arm_block = max(blocks, key=lambda b: b[-1] - b[0]) if blocks else []
arm_top = arm_block[0] if arm_block else None
arm_bot = arm_block[-1] if arm_block else None
# Legs: lower half rows where the run under the centre splits into two.
leg_rows = []
for y in range(top + height // 2, bottom):
    inner = [s for s in info[y] if abs((s[0] + s[1]) / 2 - centre) < height * 0.16]
    if len(inner) >= 2:
        leg_rows.append(y)
crotch = leg_rows[0] if leg_rows else None

touch_arm, touch_leg, min_arm_gap, min_leg_gap = [], [], None, None
if arm_top is not None:
    for y in range(arm_top, arm_bot + 1):
        r = info[y]
        if len(r) < 3:
            touch_arm.append(int(y))
        else:
            g = min(r[1][0] - r[0][1], r[-1][0] - r[-2][1])
            min_arm_gap = g if min_arm_gap is None else min(min_arm_gap, g)
knee_gap = None
if crotch is not None:
    knee = crotch + int((bottom - crotch) * 0.45)
    kin = [r for r in info[knee] if abs((r[0] + r[1]) / 2 - centre) < height * 0.16]
    knee_gap = kin[1][0] - kin[0][1] if len(kin) >= 2 else 0
    ankle = bottom - int(height * 0.04)
    for y in range(crotch, ankle):
        inner = [s for s in info[y] if abs((s[0] + s[1]) / 2 - centre) < height * 0.16]
        if len(inner) < 2:
            touch_leg.append(int(y))
        else:
            g = inner[1][0] - inner[0][1]
            min_leg_gap = g if min_leg_gap is None else min(min_leg_gap, g)

# Arm-torso gap at fixed points along the arm (the wedge starts at 0 in the armpit).
along = {}
if arm_top is not None:
    for f in (0.25, 0.5, 0.75):
        y = int(arm_top + f * (arm_bot - arm_top))
        r = info[y]
        along[f] = None if len(r) < 3 else min(r[1][0] - r[0][1], r[-1][0] - r[-2][1])
pct = lambda v: None if v is None else round(100 * v / height, 2)
gaps = {
    "armpit_from_top_pct": pct(arm_top - top if arm_top is not None else None),
    "hand_tip_from_top_pct": pct(arm_bot - top if arm_bot is not None else None),
    "crotch_from_top_pct": pct(crotch - top if crotch is not None else None),
    "arm_rows_touching": len(touch_arm), "leg_rows_touching": len(touch_leg),
    "arm_gap_pct_at_25_50_75": [pct(along.get(f)) for f in (0.25, 0.5, 0.75)], "knee_gap_pct_height": pct(knee_gap),
}
narrow = [g for g in gaps["arm_gap_pct_at_25_50_75"][1:] if g is not None and g < 1.5]
gaps["verdict"] = "ok" if (arm_top is not None and crotch is not None and not touch_arm and len(touch_leg) <= 2
                           and not narrow and (gaps["knee_gap_pct_height"] or 0) >= 1.0) else "check"

over = np.stack([mask * 200] * 3, axis=-1).astype(np.uint8)
for y in touch_arm + touch_leg:
    over[y][mask[y]] = (230, 40, 40)
for y, col in ((arm_top, (40, 160, 230)), (crotch, (40, 200, 90))):
    if y is not None:
        over[y, :] = col
Image.fromarray(over).save(os.path.join(out, "gap_overlay.png"))

path = os.path.join(out, "stats.json")
stats = json.load(open(path, encoding="utf-8"))
stats["gaps"] = gaps
json.dump(stats, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(gaps))
