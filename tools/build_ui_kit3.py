"""UI image set, third sheet: the village bag's icons (2026-10-16, item 6).

Generated free with Nano Banana Pro in Tripo Studio's image tool (16:9 4K) with the first kit's
icon sheet (output/ui-kit-20261006/raw/icons.png) attached as the style reference, on flat magenta:

  output/ui-art-20261015/raw/vg_sheet_bag_2.jpg   8 painted icons in a 4 x 2 grid (ICON_GRID)

Icons go to game/assets/ui/icons/<name>.png (128 px, like the other kits), cut the same way as
tools/build_ui_kit2.py (every piece belongs to the cell its centre falls in: the wand's sparkles).

    .tools/art-venv/Scripts/python.exe tools/build_ui_kit3.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_ui_kit as kit  # noqa: E402
from build_ui_kit2 import keyed, square  # noqa: E402

ICON_GRID = ["furniture", "refresh", "pin", "tag",
             "paint", "resize", "use", "magic"]


def main() -> None:
    rgba = keyed("vg_sheet_bag_2.jpg")
    h, w = rgba.shape[:2]
    cells: dict[int, list] = {}
    for box in kit.pieces(rgba, 400):
        x, y, bw, bh = box
        column, row = int((x + bw / 2) / (w / 4)), int((y + bh / 2) / (h / 2))
        cells.setdefault(row * 4 + column, []).append(box)
    if sorted(cells) != list(range(8)):
        raise SystemExit(f"bag icons: cells found {sorted(cells)}")
    for index, name in enumerate(ICON_GRID):
        boxes = cells[index]
        x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
        kit.save(square(kit.crop(rgba, (x0, y0, x1 - x0, y1 - y0), 6), 128), kit.ICONS / f"{name}.png")
    print("bag icons", len(ICON_GRID))


if __name__ == "__main__":
    main()
