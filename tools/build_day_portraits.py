"""Dialogue portraits of the 15 day residents (day_folk.gd LOOKS), from generated sheets.

Each resident was drawn on its own (2026-10-16, Tripo Studio image tool, Nano Banana Pro, 3:4 4K,
free) with the Sora standee as the style reference, on flat magenta, into
output/ui-art-20261015/portraits/dayp_<id>_<n>.jpg. PICKS names the chosen take per resident.

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

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_standees  # noqa: E402
from build_brand_art import raw_dir  # noqa: E402

PICKS = {"postman": 1, "fisher": 1, "farmer": 1, "sweeper": 1, "gentleman": 1, "stargazer": 1, "lamplighter": 1,
         "gardener": 1, "scout": 1, "regular": 1, "miller": 1, "shopkeeper": 1, "kid": 1, "stroller": 1, "poet": 1}
UI = ROOT / "game" / "assets" / "ui"
CARD = (600, 720)


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
    for ident, take in PICKS.items():
        source = folder / f"dayp_{ident}_{take}.jpg"
        if not source.exists():
            sys.exit(f"missing {source}")
        rgb = np.asarray(Image.open(source).convert("RGB"), np.float32) / 255.0
        standee = build_standees.frame(build_standees.key(rgb))
        standee.save(UI / "standee" / f"day_{ident}.png", optimize=True)
        card(standee).save(UI / f"day_{ident}.png", optimize=True)
        print(ident, take)


if __name__ == "__main__":
    main()
