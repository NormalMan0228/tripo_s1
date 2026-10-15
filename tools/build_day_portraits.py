"""Dialogue portraits of the 15 day residents (day_folk.gd LOOKS), from generated sheets.

Each resident was drawn on its own (2026-10-16, Tripo Studio image tool, Nano Banana Pro, 3:4 4K,
free) with the Sora standee as the style reference, on flat magenta (redraws use the earlier take
as the reference: a letter for the postman, natural hands for the rest), into
output/ui-art-20261015/portraits/dayp_<id>_<n>.jpg. PICKS names the chosen take per resident
(all fifteen picked by the user, 2026-10-16).

For every resident this writes
  game/assets/ui/standee/day_<id>.png   the background-free standee the dialogue shows
                                        (RpgUi.standee_path of res://assets/ui/day_<id>.png)
  game/assets/ui/day_<id>.png           a framed card (head and shoulders on a soft sky) for places
                                        that show a portrait card, sized like shadow_<id>.png
using tools/build_standees.py's keyer and framing (same height and headroom as the other standees).

    .tools/art-venv/Scripts/python.exe tools/build_day_portraits.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_standees  # noqa: E402
from build_brand_art import raw_dir  # noqa: E402

PICKS = {"postman": 3, "fisher": 1, "farmer": 3, "sweeper": 3, "gentleman": 3, "stargazer": 3, "lamplighter": 4,
         "gardener": 3, "scout": 1, "regular": 4, "miller": 2, "shopkeeper": 1, "kid": 1, "stroller": 2, "poet": 2}
## The two villagers from the first cover art (2026-10-16, user picks and names): 보니 the workshop
## crafter (lavender-blue hair, mallet on her shoulder) and 솔 the gardener girl; id -> (source, take).
EXTRAS = {"boni": ("crafter", 1), "sol": ("cgardener", 3)}
UI = ROOT / "game" / "assets" / "ui"
CARD = (600, 720)


def tidy(rgb: np.ndarray, rgba: np.ndarray) -> np.ndarray:
    """Fixes on top of build_standees.key for these sheets (steam, plum cloth, specks).

    Purple and plum cloth (the poet's beret) reads as magenta spill to the keyer and went
    see-through: well inside the figure (8 px from the backdrop that reaches the border) a pixel is
    as opaque as its distance from the backdrop says, in its own colour. Specks the generator left
    in the air (a fleck over the postman's cap) are dropped: pieces under 0.5% of the figure.
    """
    bg = build_standees.backdrop(rgb)
    dist = np.sqrt(((rgb - bg[None, None, :]) ** 2).sum(-1))
    far = np.clip((dist - build_standees.NEAR) / (build_standees.FAR - build_standees.NEAR), 0, 1)
    open_bg = (far < 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(open_bg, 4)
    edge = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    outside = np.isin(labels, sorted(edge - {0}))  # label 0 is the figure itself
    inside = cv2.distanceTransform((~outside).astype(np.uint8), cv2.DIST_L2, 5) > 8
    # Light pink with full strong channels is white (steam, a glint) over the backdrop: white, as
    # opaque as its weak channel says. Everything else tinted keeps the keyer's answer; untinted
    # cloth (a plum beret) is raised as above.
    strong, weak = bg > 0.5, bg <= 0.5
    spill = rgb[..., strong].min(-1) - rgb[..., weak].max(-1)
    strong_level = rgb[..., strong].min(-1)
    weak_level = rgb[..., weak].max(-1)
    misty = (strong_level > 0.85) & (weak_level > 0.12) & (spill >= 0.12)
    raise_to = np.where(inside & (spill < 0.3) & ~misty, np.maximum(rgba[..., 3], far), rgba[..., 3])
    raised = raise_to > rgba[..., 3] + 1e-3
    out = rgba.copy()
    out[..., 3] = raise_to
    out[..., :3] = np.where(raised[..., None], rgb, rgba[..., :3])
    misty &= (out[..., 3] > 0.0) | inside
    out[..., :3] = np.where(misty[..., None], 1.0, out[..., :3])
    out[..., 3] = np.where(misty, weak_level, out[..., 3])
    solid = (out[..., 3] > 0.3).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    if count > 2:
        biggest = stats[1:, cv2.CC_STAT_AREA].max()
        for index in range(1, count):
            if stats[index, cv2.CC_STAT_AREA] < biggest * 0.005: out[labels == index, 3] = 0.0
    return out


def card(standee: Image.Image) -> Image.Image:
    """Head and shoulders of the standee over a soft dawn sky, the shadow cards' size."""
    w, h = CARD
    sky = Image.new("RGB", CARD)
    top, bottom = np.array([214, 232, 238], float), np.array([246, 228, 196], float)
    rows = np.linspace(0, 1, h)[:, None]
    sky = Image.fromarray(np.repeat((top * (1 - rows) + bottom * rows)[:, None, :], w, 1).astype(np.uint8), "RGB")
    # The figure's top (the hat or hair) sits 48 px under the card's top; the hips fall off the foot.
    alpha = np.asarray(standee.split()[3])
    head = int(np.nonzero(alpha.max(1) > 80)[0][0])
    figure = standee.crop((0, head, standee.width, standee.height))
    scale = w * 1.15 / figure.width
    figure = figure.resize((round(figure.width * scale), round(figure.height * scale)), Image.Resampling.LANCZOS)
    sky.paste(figure, ((w - figure.width) // 2, 48), figure)
    return sky


def main() -> None:
    folder = raw_dir().parent / "portraits"
    (UI / "standee").mkdir(parents=True, exist_ok=True)
    jobs = [(ident, ident, take) for ident, take in PICKS.items()] + [(ident, stem, take) for ident, (stem, take) in EXTRAS.items()]
    for ident, stem, take in jobs:
        source = folder / f"dayp_{stem}_{take}.jpg"
        if not source.exists():
            sys.exit(f"missing {source}")
        rgb = np.asarray(Image.open(source).convert("RGB"), np.float32) / 255.0
        standee = build_standees.frame(tidy(rgb, build_standees.key(rgb)))
        standee.save(UI / "standee" / f"day_{ident}.png", optimize=True)
        card(standee).save(UI / f"day_{ident}.png", optimize=True)
        print(ident, take)


if __name__ == "__main__":
    main()
