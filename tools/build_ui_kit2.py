"""UI image set, second sheet pair: social/system icons and window parts (2026-10-15).

Generated free with Nano Banana Pro in Tripo Studio's image tool (4K), each with a sheet of
the first kit (output/ui-kit-20261006/raw/icons.png, panel_paper.png) attached as the style
reference, on flat magenta (output/ui-art-20261015/raw/):

  vg_sheet_icons_1.jpg  20 painted icons in a 5 x 4 grid (ICON_GRID, reading order)
  vg_sheet_parts_2.jpg  title plate, red and teal ribbons, three folder tabs, gold and night
                        menu buttons, a leaf divider and four brass corners

Icons go to game/assets/ui/icons/<name>.png (128 px, like the first kit). Parts go to
game/assets/ui/frames/<name>.png at 2x, with their 9-slice margins in frames_v2.json for
RpgUi's FRAMES table. Uses the first kit's helpers (tools/build_ui_kit.py).

    .tools/art-venv/Scripts/python.exe tools/build_ui_kit2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_standees  # noqa: E402
import build_ui_kit as kit  # noqa: E402
from build_brand_art import clean_glow, raw_dir  # noqa: E402

ICON_GRID = ["add_friend", "visit", "invite", "whisper", "more",
             "block", "report", "party", "accept", "decline",
             "leave", "lock", "eye", "bell", "quest",
             "trophy", "online", "shout", "crown", "knock"]
META: dict[str, list] = {}


def keyed(name: str) -> np.ndarray:
    rgb = np.asarray(Image.open(raw_dir() / name).convert("RGB"), np.float32) / 255
    return clean_glow(build_standees.key(rgb, figure=False))


def square(piece: np.ndarray, size: int) -> np.ndarray:
    side = max(piece.shape[:2])
    canvas = np.zeros((side, side, 4), np.float32)
    y0, x0 = (side - piece.shape[0]) // 2, (side - piece.shape[1]) // 2
    canvas[y0:y0 + piece.shape[0], x0:x0 + piece.shape[1]] = piece
    return kit.scale(canvas, size / side)


def build_icons() -> None:
    """Grid cut: every piece belongs to the cell its centre falls in (the party icon is
    four pieces: a banner and three heads)."""
    rgba = keyed("vg_sheet_icons_1.jpg")
    h, w = rgba.shape[:2]
    cells: dict[int, list] = {}
    for box in kit.pieces(rgba, 400):
        x, y, bw, bh = box
        column, row = int((x + bw / 2) / (w / 5)), int((y + bh / 2) / (h / 4))
        cells.setdefault(row * 5 + column, []).append(box)
    if sorted(cells) != list(range(20)):
        raise SystemExit(f"icons: cells found {sorted(cells)}")
    for index, name in enumerate(ICON_GRID):
        boxes = cells[index]
        x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
        kit.save(square(kit.crop(rgba, (x0, y0, x1 - x0, y1 - y0), 6), 128), kit.ICONS / f"{name}.png")
    print("icons", len(ICON_GRID))


def frame(name: str, rgba: np.ndarray, m: list[int], content: list[int] | None = None, pad=(10, 6, 10, 12)) -> None:
    out = kit.shadow(rgba, pad, offset=(0, 4), blur=4.0, strength=0.32)
    kit.save(out, kit.FRAMES / f"{name}.png")
    META[name] = [[m[0] + pad[0], m[1] + pad[1], m[2] + pad[2], m[3] + pad[3]], list(pad), content or []]


def plain(name: str, rgba: np.ndarray) -> None:
    kit.save(rgba, kit.FRAMES / f"{name}.png")
    META[name] = [[0, 0, 0, 0], [0, 0, 0, 0], []]


def split_tabs(strip: np.ndarray) -> list[np.ndarray]:
    """The three tabs touch on the sheet: cut at the thinnest columns near 1/3 and 2/3."""
    coverage = strip[..., 3].sum(0)
    w = strip.shape[1]
    cuts = [int(np.argmin(coverage[int(w * f) - w // 12:int(w * f) + w // 12]) + int(w * f) - w // 12) for f in (1 / 3, 2 / 3)]
    edges = [0] + cuts + [w]
    tabs = []
    for a, b in zip(edges, edges[1:]):
        piece = strip[:, a:b]
        cols = np.nonzero(piece[..., 3].max(0) > 0.3)[0]
        tabs.append(piece[:, cols[0]:cols[-1] + 1])
    return tabs


def build_parts() -> None:
    rgba = keyed("vg_sheet_parts_2.jpg")
    found = kit.pieces(rgba, 2000)
    if len(found) != 11:
        raise SystemExit(f"parts: found {len(found)} pieces, expected 11")
    plate, ribbon_red, ribbon_teal, tabs, corner_tl, corner_tr, gold, night, divider, corner_bl, corner_br = [kit.crop(rgba, b, 4) for b in found]
    # Title plate: the plank as a 3-slice (brass caps stay, wood stretches), the leaf on its own.
    body = kit.trim_crest(plate)
    factor = 84 / body.shape[0]
    kit.crest_piece(plate, factor, "title_plate_crest")
    META["title_plate_crest"] = [[0, 0, 0, 0], [0, 0, 0, 0], []]
    small = kit.scale(body, factor)
    cap = round(small.shape[1] * 0.06)
    # Compact 9-slice sampled a quarter along, away from where the leaf sat.
    m = [cap, 20, cap, 20]
    frame("title_plate", kit.nine(small, m, 24, 0.25), m, [cap + 6, 14, cap + 6, 14])
    # Ribbons: folded tails stay, the band stretches.
    for name, piece in (("banner_red", ribbon_red), ("banner_teal", ribbon_teal)):
        small = kit.scale(piece, 96 / piece.shape[0])
        tail = round(small.shape[1] * 0.2)
        frame(name, small, [tail, 30, tail, 30], [tail - 18, 22, tail - 18, 30])
    # Folder tabs: selected, normal, disabled.
    for name, piece in zip(("tab_on", "tab_off", "tab_disabled"), split_tabs(tabs)):
        small = kit.scale(piece, 64 / piece.shape[0])
        side = round(small.shape[0] * 0.5)
        frame(name, small, [side, 24, side, 12], [side - 10, 12, side - 10, 10], pad=(6, 4, 6, 6))
    # Menu buttons (title screen and big actions) with hover, pressed and disabled states.
    for name, piece in (("btn_menu_gold", gold), ("btn_menu_night", night)):
        small = kit.scale(piece, 104 / piece.shape[0])
        m = [round(small.shape[0] * 0.5)] * 2 + [round(small.shape[0] * 0.5)] * 2
        m = [m[0], 30, m[2], 30]
        compact = kit.nine(small, m, 24, 0.5)
        content = [m[0] - 22, 18, m[2] - 22, 22]
        frame(name + "_normal", compact, m, content)
        frame(name + "_hover", kit.adjust(compact, bright=1.08, sat=1.05), m, content)
        frame(name + "_pressed", kit.adjust(compact, bright=0.9), m, content)
        frame(name + "_disabled", kit.adjust(compact, bright=0.85, sat=0.25, alpha=0.85), m, content)
    plain("divider_leaf", kit.scale(divider, 760 / divider.shape[1]))
    for name, piece in (("corner_tl", corner_tl), ("corner_tr", corner_tr), ("corner_bl", corner_bl), ("corner_br", corner_br)):
        plain(name, kit.scale(piece, 72 / max(piece.shape[:2])))
    out = kit.FRAMES / "frames_v2.json"
    out.write_text(json.dumps({name: {"margins": v[0], "expand": v[1], "content": v[2]} for name, v in META.items()}, indent=1), encoding="utf-8")
    for name, spec in META.items():
        print("frame", name, spec[0])


def main() -> None:
    build_icons()
    build_parts()


if __name__ == "__main__":
    main()
