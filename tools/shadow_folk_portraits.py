"""Compose the shadow folk dialogue portraits.

Reads the transparent 960x1200 renders from game/tests/shadow_folk_portraits.gd
(artifacts/shadow-folk-portraits/<id>.png) and writes 480x600 portraits to
game/assets/ui/shadow_<id>.png: the dark figure on a soft card tinted per role,
a pale spotlight behind the head, and a bottom edge that fades into the dialogue
box. Tints follow FOLK[].tint in game/scripts/shadow_folk.gd.

    .tools/art-venv/Scripts/python.exe tools/shadow_folk_portraits.py
"""
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "shadow-folk-portraits"
TARGET = ROOT / "game" / "assets" / "ui"
SIZE = (480, 600)


def tints() -> dict:
    text = (ROOT / "game" / "scripts" / "shadow_folk.gd").read_text(encoding="utf-8")
    found = {}
    for ident, tint in re.findall(r'\{"id":"(\w+)".*?"tint":"([0-9a-f]{6})"', text):
        found[ident] = tuple(int(tint[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return found


def card(tint) -> Image.Image:
    w, h = SIZE
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    tint = np.array(tint, np.float32)
    paper = np.array([0.96, 0.95, 0.92], np.float32)
    top = paper * 0.55 + tint * 0.45
    bottom = paper * 0.25 + tint * 0.55
    t = (y / h)[..., None]
    colour = top * (1 - t) + bottom * t
    # Spotlight behind the head, like a stage light finding the culprit.
    d = np.sqrt(((x - w * 0.5) / (w * 0.42)) ** 2 + ((y - h * 0.36) / (h * 0.34)) ** 2)[..., None]
    colour = colour + (1 - np.clip(d, 0, 1)) ** 1.6 * 0.22
    # Soft vignette at the corners.
    v = np.sqrt(((x - w * 0.5) / (w * 0.62)) ** 2 + ((y - h * 0.45) / (h * 0.62)) ** 2)[..., None]
    colour = colour * (1 - np.clip(v - 0.75, 0, 1) * 0.35)
    rgb = np.clip(colour * 255, 0, 255).astype(np.uint8)
    # Rounded card; the lowest 18% fades into the dialogue box.
    alpha = np.ones((h, w), np.float32)
    radius = 38.0
    for cx, cy in ((radius, radius), (w - radius, radius)):
        corner = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - radius
        mask = ((x < radius) if cx == radius else (x > w - radius)) & (y < radius)
        alpha[mask] = np.clip(1 - corner[mask], 0, 1)
    alpha *= np.clip((h - y) / (h * 0.18), 0, 1)
    return Image.fromarray(np.dstack([rgb, (alpha * 255).astype(np.uint8)]), "RGBA")


def main() -> None:
    palette = tints()
    for render in sorted(SOURCE.glob("*.png")):
        ident = render.stem
        figure = Image.open(render).convert("RGBA").resize(SIZE, Image.LANCZOS)
        base = card(palette.get(ident, (0.8, 0.8, 0.85)))
        # A faint dark halo grounds the figure on the light card.
        halo = figure.split()[3].filter(ImageFilter.GaussianBlur(10)).point(lambda a: int(a * 0.28))
        shade = Image.new("RGBA", SIZE, (20, 22, 40, 0))
        shade.putalpha(halo)
        out = Image.alpha_composite(base, shade)
        out = Image.alpha_composite(out, figure)
        # Keep the card's own alpha (rounded top, faded bottom) over everything.
        final_alpha = np.minimum(np.array(out.split()[3]), np.array(base.split()[3]))
        out.putalpha(Image.fromarray(final_alpha))
        path = TARGET / f"shadow_{ident}.png"
        out.save(path, optimize=True)
        print(path.relative_to(ROOT), path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
