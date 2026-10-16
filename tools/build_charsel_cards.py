"""Character select pictures (31): the eight new player characters' front images, cut from the 05
session's sheets (art/characters/body_p2_v1/charsel/charsel2_male.jpg and charsel2_female.jpg,
four figures each on a light backdrop, Tripo free image, 4K).

For every character this writes
  game/assets/ui/charsel/<id>.png        the whole figure, background removed (the preview stand-in
                                         until the 3D model arrives)
  game/assets/ui/charsel/<id>_card.png   head to waist on a soft card backdrop (the select card)
keyed against the light backdrop that reaches the sheet's border (light parts inside stay).

    .tools/art-venv/Scripts/python.exe tools/build_charsel_cards.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

SHEETS = ROOT.parent.parent / "lsm26" / "triphthonS1" / "art" / "characters" / "body_p2_v1" / "charsel"
if not SHEETS.exists():
    SHEETS = Path(r"C:/lsm26/triphthonS1/art/characters/body_p2_v1/charsel")
ORDER = {"charsel2_male.jpg": ["m1_adventurer", "m2_artisan", "m3_fisher", "m4_smith"],
         "charsel2_female.jpg": ["f1_adventurer", "f2_herbalist", "f3_inventor", "f4_sailor"]}
OUT = ROOT / "game" / "assets" / "ui" / "charsel"
FIGURE_H = 900
CARD = (300, 360)


def key_light(rgb: np.ndarray) -> np.ndarray:
    """The light backdrop that reaches the border goes; light parts inside the figure (a white
    collar, socks) stay. Soft edge from the colour distance."""
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, 0)
    dist = np.sqrt(((rgb - bg[None, None, :]) ** 2).sum(-1))
    near = (dist < 0.09).astype(np.uint8)
    count, labels = cv2.connectedComponents(near, 4)
    edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    outside = np.isin(labels, sorted(edge))
    # A soft rim: pixels just inside the figure fade by their distance from the backdrop.
    rim = cv2.dilate(outside.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~outside
    alpha = np.where(outside, 0.0, 1.0)
    alpha = np.where(rim, np.clip((dist - 0.04) / 0.14, 0, 1), alpha)
    keep = (alpha > 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(keep, 8)
    if count > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        alpha = alpha * cv2.dilate((labels == biggest).astype(np.uint8), np.ones((7, 7), np.uint8))
    return np.dstack([rgb, alpha.astype(np.float32)])


def figure(rgb: np.ndarray) -> Image.Image:
    rgba = key_light(rgb)
    alpha = rgba[..., 3]
    ys, xs = np.nonzero(alpha > 0.3)
    image = Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    image = image.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    scale = FIGURE_H / image.height
    return image.resize((round(image.width * scale), FIGURE_H), Image.Resampling.LANCZOS)


def card(full: Image.Image) -> Image.Image:
    """Head to waist, centred, on a warm paper gradient."""
    w, h = CARD
    top, bottom = np.array([247, 236, 210], float), np.array([228, 208, 170], float)
    rows = np.linspace(0, 1, h)[:, None]
    sky = Image.fromarray(np.repeat((top * (1 - rows) + bottom * rows)[:, None, :], w, 1).astype(np.uint8), "RGB").convert("RGBA")
    upper = full.crop((0, 0, full.width, int(full.height * 0.5)))
    scale = (w * 0.95) / max(upper.width, 1)
    scale = min(scale, (h - 16) / upper.height)
    upper = upper.resize((round(upper.width * scale), round(upper.height * scale)), Image.Resampling.LANCZOS)
    sky.alpha_composite(upper, ((w - upper.width) // 2, 16))
    return sky


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for sheet, ids in ORDER.items():
        rgb = np.asarray(Image.open(SHEETS / sheet).convert("RGB"), np.float32) / 255.0
        quarter = rgb.shape[1] // 4
        for i, ident in enumerate(ids):
            part = rgb[:, i * quarter:(i + 1) * quarter]
            full = figure(part)
            full.save(OUT / f"{ident}.png", optimize=True)
            card(full).save(OUT / f"{ident}_card.png", optimize=True)
            print(ident, full.size)


if __name__ == "__main__":
    main()
