"""Background-free dialogue illustrations ("standees") from flat-colour generations.

GPT Image 2 on Scenario cannot return a transparent background, so each villager is
generated on one flat colour (magenta #FF00FF unless noted) and keyed out here:

  output/standees-20261006/raw/<id>_<mood>.png   (Scenario downloads, mood: neutral|happy|curious)
  -> game/assets/portraits/standee/<id>.png            (neutral)
     game/assets/portraits/standee/<id>_<mood>.png     (other moods)

The key estimates the backdrop from the border, turns colour distance into a soft
alpha, un-mixes the backdrop from edge pixels (no magenta fringe), keeps the figure's
connected body and trims to a common framing: every standee is scaled so the figure
is FIGURE_HEIGHT tall on a CANVAS with the same headroom, which keeps the four
villagers' heads the same size in the dialogue window. Art stays local (gitignored).

    .tools/art-venv/Scripts/python.exe tools/build_standees.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "output" / "standees-20261006" / "raw"
OUT = ROOT / "game" / "assets" / "portraits" / "standee"
CANVAS = (720, 960)
FIGURE_HEIGHT = 900   # top of the hair to the bottom crop
NEAR, FAR = 0.10, 0.24  # colour distance (0..~1.7) where alpha ramps from 0 to 1


def backdrop(rgb: np.ndarray) -> np.ndarray:
    """Median colour of a 6 px border ring."""
    h, w, _ = rgb.shape
    ring = np.concatenate([rgb[:6].reshape(-1, 3), rgb[-6:].reshape(-1, 3), rgb[:, :6].reshape(-1, 3), rgb[:, -6:].reshape(-1, 3)])
    return np.median(ring, axis=0)


def key(rgb: np.ndarray, figure: bool = True) -> np.ndarray:
    """RGBA float image with the flat backdrop removed (figure=False keeps every piece of a sheet)."""
    bg = backdrop(rgb)
    dist = np.sqrt(((rgb - bg[None, None, :]) ** 2).sum(-1))
    alpha = np.clip((dist - NEAR) / (FAR - NEAR), 0, 1)
    # How much of the backdrop's hue a pixel carries (magenta pockets between hair strands):
    # the backdrop's strong channels above its weak ones (magenta: min(R,B) - G), so a red
    # or a purple that lacks one of the strong channels does not count as spill.
    strong, weak = bg > 0.5, bg <= 0.5
    spill = rgb[..., strong].min(-1) - rgb[..., weak].max(-1)
    # Keep the figure: the biggest connected solid region plus big separate parts.
    solid_mask = (alpha > 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid_mask, 8)
    if figure and count > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        keep = (labels == biggest).astype(np.uint8)
        for index in range(1, count):
            if index != biggest and stats[index, cv2.CC_STAT_AREA] > 2500: keep[labels == index] = 1
        alpha = alpha * cv2.dilate(keep, np.ones((9, 9), np.uint8))
    # Solid figure pixels: far from the backdrop and not tinted by it.
    solid = ((alpha > 0.95) & (spill < 0.15)).astype(np.float32)
    # Local figure colour next to each pixel (the dark outline at edges).
    weight = cv2.GaussianBlur(solid, (0, 0), 2.0)[..., None]
    near = cv2.GaussianBlur(rgb * solid[..., None], (0, 0), 2.0) / np.maximum(weight, 1e-4)
    # Coverage of mixed pixels: where C sits on the line from the backdrop B to the
    # figure colour F, C = a*F + (1-a)*B.
    span = near - bg[None, None, :]
    coverage = ((rgb - bg[None, None, :]) * span).sum(-1) / np.maximum((span ** 2).sum(-1), 1e-3)
    coverage = np.clip(coverage, 0, 1) * (weight[..., 0] > 0.02)
    mixed = solid < 1
    alpha = np.where(mixed, np.minimum(alpha, coverage), 1.0)
    fore = np.where(mixed[..., None], near, rgb)
    alpha = np.clip((alpha - 0.15) / 0.85, 0, 1)
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), 0.5)
    return np.dstack([fore, alpha])


def frame(rgba: np.ndarray) -> Image.Image:
    """Scale the figure to FIGURE_HEIGHT and place it bottom-centred on CANVAS."""
    alpha = rgba[..., 3]
    ys, xs = np.nonzero(alpha > 0.3)
    top, bottom = ys.min(), ys.max()
    left, right = xs.min(), xs.max()
    image = Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").crop((left, top, right + 1, bottom + 1))
    scale = FIGURE_HEIGHT / image.height
    image = image.resize((round(image.width * scale), FIGURE_HEIGHT), Image.Resampling.LANCZOS)
    if image.width > CANVAS[0]:
        trim = (image.width - CANVAS[0]) // 2
        image = image.crop((trim, 0, trim + CANVAS[0], image.height))
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.paste(image, ((CANVAS[0] - image.width) // 2, CANVAS[1] - image.height), image)
    return canvas


def build(path: Path) -> Path:
    rgb = np.asarray(Image.open(path).convert("RGB"), np.float32) / 255.0
    standee = frame(key(rgb))
    ident, _, mood = path.stem.partition("_")
    target = OUT / (f"{ident}.png" if mood in ("", "neutral") else f"{ident}_{mood}.png")
    OUT.mkdir(parents=True, exist_ok=True)
    standee.save(target, optimize=True)
    return target


def main() -> None:
    sources = [Path(p) for p in sys.argv[1:]] or sorted(RAW.glob("*.png"))
    if not sources:
        raise SystemExit(f"no generations in {RAW}")
    for path in sources:
        print("standee", build(path))


if __name__ == "__main__":
    main()
