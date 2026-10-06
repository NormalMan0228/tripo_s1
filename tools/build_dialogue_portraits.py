"""Dialogue portraits from the cast's 2D concept sheets.

The character reference library (output/character-reference-library-20261005-v4)
holds each villager's concept sheet with a painted "2D 대화 일러스트" panel. This cuts
that panel out, removes text painted over it (Moru's vignette), and writes a clean
portrait card for the dialogue box to game/assets/portraits/<id>.png (local art,
gitignored like the rest of the cast). The old 3D-render faces are kept as
<id>_render.png the first time.

    .tools/art-venv/Scripts/python.exe tools/build_dialogue_portraits.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "output" / "character-reference-library-20261005-v4"
OUT = ROOT / "game" / "assets" / "portraits"

# Crop boxes (x0, y0, x1, y1) of the 2D dialogue illustration on each 1448x1086 sheet,
# and rectangles of hand-lettered text to paint out inside that crop (sheet coordinates).
CAST = {
    "naru": {"dir": "03_naru_나루", "box": (40, 200, 526, 644), "text": []},
    "sora": {"dir": "01_sora_소라", "box": (22, 250, 648, 764), "text": []},
    "moru": {"dir": "02_moru_모루", "box": (334, 44, 728, 630), "text": [(584, 252, 742, 336), (660, 318, 700, 352)]},
    "haeru": {"dir": "04_haeru_해루", "box": (30, 32, 444, 518), "text": []},
}
SIZE = (600, 720)  # portrait card the dialogue box shows at about 300 x 360


def fit_cover(image: Image.Image, size: tuple[int, int], anchor_y: float) -> Image.Image:
    """Scale to cover `size`, keeping the face (upper part) when trimming height."""
    w, h = image.size
    scale = max(size[0] / w, size[1] / h)
    resized = image.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = int((resized.height - size[1]) * anchor_y)
    return resized.crop((left, top, left + size[0], top + size[1]))


def build(cast_id: str, spec: dict) -> Path:
    # cv2.imread cannot open non-ASCII Windows paths (the folders carry Korean names).
    raw = np.fromfile(LIBRARY / spec["dir"] / "04_original-concept.png", dtype=np.uint8)
    sheet = cv2.imdecode(raw, cv2.IMREAD_COLOR) if raw.size else None
    if sheet is None:
        raise SystemExit(f"missing concept sheet for {cast_id}")
    if spec["text"]:
        mask = np.zeros(sheet.shape[:2], np.uint8)
        for x0, y0, x1, y1 in spec["text"]:
            region = sheet[y0:y1, x0:x1]
            # Only the dark lettering strokes, not the painting under them.
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            strokes = (gray < 150).astype(np.uint8) * 255
            mask[y0:y1, x0:x1] = cv2.dilate(strokes, np.ones((5, 5), np.uint8))
        sheet = cv2.inpaint(sheet, mask, 6, cv2.INPAINT_TELEA)
    x0, y0, x1, y1 = spec["box"]
    crop = Image.fromarray(cv2.cvtColor(sheet[y0:y1, x0:x1], cv2.COLOR_BGR2RGB))
    card = fit_cover(crop, SIZE, 0.15)
    # The sheet is about 2x smaller than the card: a light unsharp mask keeps line art crisp.
    card = card.filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2))
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{cast_id}.png"
    backup = OUT / f"{cast_id}_render.png"
    if target.exists() and not backup.exists():
        shutil.copy2(target, backup)
    card.save(target, optimize=True)
    return target


def main() -> None:
    for cast_id, spec in CAST.items():
        print("portrait", build(cast_id, spec))


if __name__ == "__main__":
    main()
