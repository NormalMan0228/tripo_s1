"""Paint the shadow folk dialogue portraits as 2D illustration cards.

The cast's dialogue portraits (tools/build_dialogue_portraits.py) are 600x720
painted cards on cream paper. The shadow folk get the same card: cream paper with
grain, a watercolour wash in the role's tint (FOLK[].tint in shadow_folk.gd) with
pooled pigment edges, and the figure as an ink-wash silhouette with a rough brush
edge, a hand-inked outline and the glowing white eyes.

The figure comes from the transparent 960x1200 renders written by
game/tests/shadow_folk_portraits.gd (artifacts/shadow-folk-portraits/<id>.png). When a
render is missing, the previous card game/assets/ui/shadow_<id>.png is used as the
source (the dark figure is keyed out of it); the first run backs those cards up to
artifacts/shadow-folk-portraits/cards/ so re-runs stay stable.

    .tools/art-venv/Scripts/python.exe tools/shadow_folk_portraits.py [out_dir]
"""
import re
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RENDERS = ROOT / "artifacts" / "shadow-folk-portraits"
BACKUP = RENDERS / "cards"
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "game" / "assets" / "ui"
SIZE = (600, 720)
PAPER = np.array([251, 239, 220], np.float32) / 255.0
INK = np.array([0.105, 0.098, 0.165], np.float32)


def tints() -> dict:
    text = (ROOT / "game" / "scripts" / "shadow_folk.gd").read_text(encoding="utf-8")
    found = {}
    for ident, tint in re.findall(r'\{"id":"(\w+)".*?"tint":"([0-9a-f]{6})"', text):
        found[ident] = np.array([int(tint[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)
    return found


def noise(shape, scale, seed):
    rng = np.random.default_rng(seed)
    h, w = shape
    small = rng.random((max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def figure_masks(ident: str):
    """(figure alpha, eye alpha) at SIZE from the render or the old card."""
    render = RENDERS / f"{ident}.png"
    if render.exists():
        rgba = np.asarray(Image.open(render).convert("RGBA").resize((480, 600), Image.LANCZOS), np.float32) / 255.0
        lum = rgba[..., :3].mean(-1)
        body = rgba[..., 3] * (lum < 0.5)
        eyes = rgba[..., 3] * (lum >= 0.5)
    else:
        card = BACKUP / f"shadow_{ident}.png"
        rgba = np.asarray(Image.open(card).convert("RGBA"), np.float32) / 255.0
        lum = rgba[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
        body = np.clip((0.30 - lum) / 0.12, 0, 1) * (rgba[..., 3] > 0.05)
        solid = (body > 0.5).astype(np.uint8)
        filled = solid.copy()
        contours, _ = cv2.findContours(solid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(filled, contours, -1, 1, thickness=-1)
        eyes = np.clip((lum - 0.75) / 0.15, 0, 1) * (filled > 0) * (1 - solid)
        eyes = cv2.erode(eyes, np.ones((2, 2), np.uint8))
        # The old card faded the figure's feet into the box; restore a solid base.
        fade_rows = int(600 * 0.18)
        for y in range(600 - fade_rows, 600):
            body[y] = np.maximum(body[y], (body[600 - fade_rows - 1] > 0.5) * 1.0)
    # 480x600 (4:5) -> a 600x720 (5:6) bust like the cast cards: scale by 1.5 and
    # crop to the head and shoulders.
    def place(a):
        big = cv2.resize(a, (720, 900), interpolation=cv2.INTER_CUBIC)
        return np.clip(big[70:790, 60:660], 0, 1)
    return place(body), place(eyes)


def paint(ident: str, tint) -> Image.Image:
    w, h = SIZE
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    seed = sum(map(ord, ident))
    # Cream paper with fibre grain.
    grain = noise((h, w), 2, seed) * 0.5 + noise((h, w), 9, seed + 1) * 0.5
    colour = PAPER[None, None, :] * (0.965 + grain[..., None] * 0.05)
    # Watercolour wash: blotchy tinted cloud behind the figure, darker at its rim.
    cloud = noise((h, w), 70, seed + 2) * 0.6 + noise((h, w), 26, seed + 3) * 0.4
    centre = np.sqrt(((x - w * 0.5) / (w * 0.55)) ** 2 + ((y - h * 0.42) / (h * 0.5)) ** 2)
    wash = np.clip((1.05 - centre) * 1.6 + (cloud - 0.5) * 1.1, 0, 1)
    wash = cv2.GaussianBlur(wash, (0, 0), 3)
    rim = np.clip(1 - np.abs(wash - 0.35) / 0.12, 0, 1) * 0.35
    pigment = tint * 0.75 + PAPER * 0.25
    amount = (wash * 0.55 + rim)[..., None]
    colour = colour * (1 - amount) + pigment[None, None, :] * amount * (0.9 + grain[..., None] * 0.15)
    # A few dry-brush strokes and speckles of the tint in the corners.
    strokes = noise((h, w), 4, seed + 4)
    speck = (strokes > 0.93) * np.clip(centre - 0.85, 0, 1)
    colour = colour * (1 - speck[..., None] * 0.5) + pigment * speck[..., None] * 0.5
    body, eyes = figure_masks(ident)
    # Brushy silhouette edge: warp the mask with noise, then soften slightly.
    jitter_x = (noise((h, w), 14, seed + 5) - 0.5) * 3.5
    jitter_y = (noise((h, w), 14, seed + 6) - 0.5) * 3.5
    map_x = (x + jitter_x).astype(np.float32)
    map_y = (y + jitter_y).astype(np.float32)
    body = cv2.remap(body, map_x, map_y, cv2.INTER_LINEAR)
    body = cv2.GaussianBlur(body, (0, 0), 1.1)
    # Soft tinted shadow wash behind the figure.
    halo = cv2.GaussianBlur(body, (0, 0), 14) * 0.35
    colour = colour * (1 - halo[..., None]) + (pigment * 0.55)[None, None, :] * halo[..., None]
    # Ink-wash fill: a little lighter where the brush ran dry, darker at the edge.
    dry = noise((h, w), 3, seed + 7)
    fill = INK * (0.92 + dry[..., None] * 0.25) + tint * 0.06
    inner = cv2.erode((body > 0.5).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(np.float32)
    inner = cv2.GaussianBlur(inner, (0, 0), 4)
    fill = fill * (0.82 + inner[..., None] * 0.18)
    colour = colour * (1 - body[..., None]) + fill * body[..., None]
    # Hand-inked outline with pressure variation.
    edge = cv2.dilate((body > 0.35).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32) - (body > 0.6)
    edge = np.clip(cv2.GaussianBlur(edge, (0, 0), 0.9), 0, 1) * (0.55 + noise((h, w), 12, seed + 8) * 0.45)
    colour = colour * (1 - edge[..., None] * 0.9) + (INK * 0.6) * edge[..., None] * 0.9
    # Eyes: warm white with a faint glow.
    glow = cv2.GaussianBlur(eyes, (0, 0), 6) * 0.35
    colour = colour * (1 - glow[..., None]) + np.array([1.0, 0.97, 0.86]) * glow[..., None]
    colour = colour * (1 - eyes[..., None]) + np.array([1.0, 0.985, 0.94]) * eyes[..., None]
    # Gentle vignette, like the cast's paper.
    v = np.clip(np.sqrt(((x - w / 2) / (w * 0.7)) ** 2 + ((y - h / 2) / (h * 0.7)) ** 2) - 0.6, 0, 1)
    colour = colour * (1 - v[..., None] * 0.18)
    return Image.fromarray((np.clip(colour, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


def main() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    palette = tints()
    TARGET.mkdir(parents=True, exist_ok=True)
    for card in sorted((ROOT / "game" / "assets" / "ui").glob("shadow_*.png")):
        backup = BACKUP / card.name
        if not backup.exists(): shutil.copy2(card, backup)
    for backup in sorted(BACKUP.glob("shadow_*.png")):
        ident = backup.stem.removeprefix("shadow_")
        out = paint(ident, palette.get(ident, np.array([0.8, 0.8, 0.85], np.float32)))
        path = TARGET / f"shadow_{ident}.png"
        out.save(path, optimize=True)
        print(path.name, path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
