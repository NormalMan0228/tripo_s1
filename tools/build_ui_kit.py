"""The dedicated UI image set, cut from AI-painted sheets into the game's frames.

Seven sheets were generated with GPT Image 2 on Scenario (2026-10-06, 12 CU each) on a
flat magenta backdrop (output/ui-kit-20261006/raw/):

  panel_night.png  teal-navy window with gold filigree corners
  panel_paper.png  parchment window in a honey-wood frame with brass corners
  dialogue.png     wide dialogue box + teal name ribbon
  buttons.png      gold / green / parchment / night buttons
  slots.png        night slot, paper slot, portrait ring, minimap ring, round key, key cap
  bars.png         bar track, red/green/gold fills, toast pill, paper tooltip, checkboxes, chevron
  icons.png        20 painted menu icons

This keys out the backdrop, finds each piece, and writes the frames RpgUi already uses by
name (game/assets/ui/frames/<name>.png, 2x pixels shown at half size): each 9-slice frame
is rebuilt compact (its four corners, short edge strips taken away from any centre crest,
and a small centre) with a soft drop shadow baked in. States (hover, pressed, disabled,
focus) are derived from the base piece. Margins go to frames.json and to the FRAMES table
in game/scripts/rpg_ui.gd. Icons go to game/assets/ui/icons/<name>.png and replace the
SVG icons of the same name.

    .tools/art-venv/Scripts/python.exe tools/build_ui_kit.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_standees  # noqa: E402  (shared backdrop keyer)

RAW = ROOT / "output" / "ui-kit-20261006" / "raw"
FRAMES = ROOT / "game" / "assets" / "ui" / "frames"
ICONS = ROOT / "game" / "assets" / "ui" / "icons"
RPG_UI = ROOT / "game" / "scripts" / "rpg_ui.gd"

ICON_NAMES = ["bag", "craft", "map", "chest", "wardrobe",
              "expedition", "gear", "people", "chat", "mail",
              "home", "heart", "clock", "book", "leaf",
              "starseed", "fire", "cold", "hunger", "stamina"]


# ------------------------------------------------------------------ pixels

def sheet(name: str) -> np.ndarray:
    rgb = np.asarray(Image.open(RAW / f"{name}.png").convert("RGB"), np.float32) / 255.0
    return build_standees.key(rgb, figure=False)


def pieces(rgba: np.ndarray, min_area: int = 300) -> list[tuple[int, int, int, int]]:
    """Bounding boxes (x, y, w, h) of the separate pieces, in reading order."""
    solid = cv2.morphologyEx((rgba[..., 3] > 0.5).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    boxes = [tuple(int(v) for v in stats[i, :4]) for i in range(1, count) if stats[i, 4] > min_area]
    # Rows: pieces whose vertical centres are close share a row.
    boxes.sort(key=lambda b: b[1] + b[3] / 2)
    rows: list[list] = []
    for box in boxes:
        centre = box[1] + box[3] / 2
        if rows and abs(centre - (rows[-1][0][1] + rows[-1][0][3] / 2)) < 90: rows[-1].append(box)
        else: rows.append([box])
    return [box for row in rows for box in sorted(row)]


def crop(rgba: np.ndarray, box, pad: int = 3) -> np.ndarray:
    x, y, w, h = box
    y0, y1 = max(0, y - pad), min(rgba.shape[0], y + h + pad)
    x0, x1 = max(0, x - pad), min(rgba.shape[1], x + w + pad)
    return rgba[y0:y1, x0:x1].copy()


def resize(rgba: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Premultiplied resize, so edges do not pick up dark or magenta fringes."""
    pre = rgba.copy()
    pre[..., :3] *= pre[..., 3:4]
    out = cv2.resize(pre, size, interpolation=cv2.INTER_AREA if size[0] < rgba.shape[1] else cv2.INTER_CUBIC)
    out = np.clip(out, 0, 1)
    out[..., :3] /= np.maximum(out[..., 3:4], 1e-4)
    return np.clip(out, 0, 1)


def scale(rgba: np.ndarray, factor: float) -> np.ndarray:
    return resize(rgba, (max(1, round(rgba.shape[1] * factor)), max(1, round(rgba.shape[0] * factor))))


def save(rgba: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path, optimize=True)


def fill_colour(rgba: np.ndarray) -> np.ndarray:
    h, w = rgba.shape[:2]
    return np.median(rgba[h * 2 // 5:h * 3 // 5, w * 2 // 5:w * 3 // 5, :3].reshape(-1, 3), axis=0)


def margins(rgba: np.ndarray, reach: float = 0.3) -> list[int]:
    """Left, top, right, bottom widths covering the border and the corner ornaments."""
    h, w = rgba.shape[:2]
    fill = fill_colour(rgba)
    off = (np.sqrt(((rgba[..., :3] - fill) ** 2).sum(-1)) > 0.12) | (rgba[..., 3] < 0.9)
    # Close the small gaps inside filigree so an ornament reads as one solid run.
    off = cv2.dilate(off.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)

    def run(line: np.ndarray) -> int:
        inside = np.nonzero(~line)[0]
        return int(inside[0]) if inside.size else len(line)

    bl, br = run(off[h // 2, :]), run(off[h // 2, ::-1])
    bt, bb = run(off[:, w // 3]), run(off[::-1, w // 3])
    rx, ry = int(w * reach), int(h * reach)
    # Rows just inside the top/bottom borders show how far corner ornaments reach sideways.
    rows = list(range(bt + 10, ry)) + list(range(h - ry, h - bb - 10))
    cols = list(range(bl + 10, rx)) + list(range(w - rx, w - br - 10))
    left = max([bl] + [min(run(off[y, :]), rx) for y in rows])
    right = max([br] + [min(run(off[y, ::-1]), rx) for y in rows])
    top = max([bt] + [min(run(off[:, x]), ry) for x in cols])
    bottom = max([bb] + [min(run(off[::-1, x]), ry) for x in cols])
    return [left + 2, top + 2, right + 2, bottom + 2]


def nine(rgba: np.ndarray, m: list[int], centre: int = 24, at: float = 0.28) -> np.ndarray:
    """Compact 9-slice: corners, edge strips sampled at `at` along each edge (away from a
    centre crest) and a small centre patch."""
    h, w = rgba.shape[:2]
    l, t, r, b = m
    cw, ch = centre, centre
    x0 = l + int((w - l - r - cw) * at)
    y0 = t + int((h - t - b - ch) * at)
    xm = (w - cw) // 2
    ym = (h - ch) // 2
    out = np.zeros((t + ch + b, l + cw + r, 4), np.float32)
    out[:t, :l] = rgba[:t, :l]
    out[:t, l + cw:] = rgba[:t, w - r:]
    out[t + ch:, :l] = rgba[h - b:, :l]
    out[t + ch:, l + cw:] = rgba[h - b:, w - r:]
    out[:t, l:l + cw] = rgba[:t, x0:x0 + cw]
    out[t + ch:, l:l + cw] = rgba[h - b:, x0:x0 + cw]
    out[t:t + ch, :l] = rgba[y0:y0 + ch, :l]
    out[t:t + ch, l + cw:] = rgba[y0:y0 + ch, w - r:]
    out[t:t + ch, l:l + cw] = rgba[ym:ym + ch, xm:xm + cw]
    return out


def shadow(rgba: np.ndarray, pad=(12, 8, 12, 16), offset=(0, 5), blur=5.0, strength=0.38) -> np.ndarray:
    """Pads the piece and draws a soft drop shadow under it (pad becomes expand margins)."""
    l, t, r, b = pad
    h, w = rgba.shape[:2]
    out = np.zeros((h + t + b, w + l + r, 4), np.float32)
    a = np.zeros(out.shape[:2], np.float32)
    a[t + offset[1]:t + offset[1] + h, l + offset[0]:l + offset[0] + w] = rgba[..., 3]
    a = cv2.GaussianBlur(a, (0, 0), blur) * strength
    out[..., :3] = 0.04
    out[..., 3] = a
    top = np.zeros_like(out)
    top[t:t + h, l:l + w] = rgba
    alpha = top[..., 3:4] + out[..., 3:4] * (1 - top[..., 3:4])
    colour = (top[..., :3] * top[..., 3:4] + out[..., :3] * out[..., 3:4] * (1 - top[..., 3:4])) / np.maximum(alpha, 1e-4)
    return np.dstack([colour, alpha[..., 0]])


def adjust(rgba: np.ndarray, bright=1.0, sat=1.0, alpha=1.0, tint=None, tint_amount=0.0) -> np.ndarray:
    out = rgba.copy()
    rgb = out[..., :3]
    grey = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    rgb = grey[..., None] + (rgb - grey[..., None]) * sat
    rgb = rgb * bright
    if tint is not None: rgb = rgb * (1 - tint_amount) + np.array(tint, np.float32) * tint_amount
    out[..., :3] = np.clip(rgb, 0, 1)
    out[..., 3] *= alpha
    return out


def hue_shift(rgba: np.ndarray, degrees: float, sat=1.0) -> np.ndarray:
    rgb8 = (np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(rgb8, cv2.COLOR_RGB2HSV_FULL).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + degrees / 360 * 256) % 256
    hsv[..., 1] = np.clip(hsv[..., 1] * sat, 0, 255)
    out = rgba.copy()
    out[..., :3] = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB_FULL).astype(np.float32) / 255
    return out


def recolour(rgba: np.ndarray, target_rgb=(0.70, 0.36, 0.23), hue_range=(150, 240)) -> np.ndarray:
    """Turns the teal/blue fabric of a piece into another colour, leaving gold trim alone."""
    rgb8 = (np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(rgb8, cv2.COLOR_RGB2HSV_FULL).astype(np.float32)
    hue = hsv[..., 0] / 256 * 360
    mask = ((hue >= hue_range[0]) & (hue <= hue_range[1]) & (hsv[..., 1] > 40)).astype(np.float32)
    mask = cv2.GaussianBlur(mask, (0, 0), 0.8)[..., None]
    target = np.array(target_rgb, np.float32)
    # Keep the fabric's shading, normalised so its typical brightness lands on the target.
    value = rgba[..., :3].max(-1, keepdims=True)
    typical = float(np.median(value[mask[..., 0] > 0.5])) if (mask > 0.5).any() else 1.0
    shifted = np.clip(target[None, None, :] * value / max(typical, 1e-3), 0, 1)
    out = rgba.copy()
    out[..., :3] = rgba[..., :3] * (1 - mask) + shifted * mask
    return out


def flatten(rgba: np.ndarray, keep: float = 0.25) -> np.ndarray:
    """Removes the interior's broad light falloff (keeps fine texture), so stretched centres
    do not show a lighter box inside the frame."""
    fill = fill_colour(rgba)
    near = np.sqrt(((rgba[..., :3] - fill) ** 2).sum(-1)) < 0.16
    inside = cv2.erode(near.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(np.float32)
    inside = cv2.GaussianBlur(inside, (0, 0), 6)[..., None]
    broad = cv2.GaussianBlur(rgba[..., :3], (0, 0), 28)
    flat = np.clip(fill[None, None, :] + (rgba[..., :3] - broad) + (broad - fill[None, None, :]) * keep, 0, 1)
    out = rgba.copy()
    out[..., :3] = rgba[..., :3] * (1 - inside) + flat * inside
    return out


def remove_tail(rgba: np.ndarray, at_bottom: float = 0.18) -> np.ndarray:
    """Paints out a speech-bubble tail under the bottom edge's centre by copying the edge beside it."""
    h, w = rgba.shape[:2]
    out = rgba.copy()
    band = int(w * at_bottom)
    x0 = w // 2 - band // 2
    rows = slice(h // 2, h)
    out[rows, x0:x0 + band] = rgba[rows, x0 - band:x0]
    # Rows below the body's bottom edge (the tail tip) become transparent.
    body = rgba[:, int(w * 0.25), 3] > 0.5
    last = int(np.nonzero(body)[0].max()) if body.any() else h - 1
    out[last + 1:] = 0
    return out[:last + 2]


# ------------------------------------------------------------------ frames

META: dict[str, list] = {}


def frame(name: str, rgba: np.ndarray, m: list[int], content: list[int], pad=(12, 8, 12, 16), with_shadow=True) -> None:
    """Writes a 9-slice frame; m are the 2x texture margins of the unpadded piece."""
    if with_shadow:
        rgba = shadow(rgba, pad)
        m = [m[0] + pad[0], m[1] + pad[1], m[2] + pad[2], m[3] + pad[3]]
        expand = list(pad)
    else:
        expand = [0, 0, 0, 0]
    save(rgba, FRAMES / f"{name}.png")
    META[name] = [m, expand, content]


def plain(name: str, rgba: np.ndarray) -> None:
    save(rgba, FRAMES / f"{name}.png")


def trim_crest(src: np.ndarray) -> np.ndarray:
    """Drops the rows above the top border that only a centre crest reaches into."""
    column = src[:, src.shape[1] * 3 // 10, 3]
    top = int(np.argmax(column > 0.5))
    return src[max(0, top - 2):]


def panel(src: np.ndarray, target_margin: int, centre: int = 32) -> tuple[np.ndarray, list[int], float]:
    src = flatten(trim_crest(src))
    m = margins(src)
    factor = target_margin / max(m)
    small = scale(src, factor)
    m = [max(4, round(v * factor) + 2) for v in m]
    return nine(small, m, centre), m, factor


def crest_piece(box: np.ndarray, factor: float, name: str) -> None:
    """The top-centre crest on its own: only what rises above the border line, at the
    box's scale (its bottom row sits on the box's top edge)."""
    w = box.shape[1]
    border_top = int(np.argmax(box[:, w * 3 // 10, 3] > 0.5))
    crest = box[:border_top + 2, int(w * 0.40):int(w * 0.60)]
    cols = np.nonzero(crest[..., 3].max(0) > 0.05)[0]
    rows = np.nonzero(crest[..., 3].max(1) > 0.05)[0]
    if cols.size and rows.size:
        crest = crest[rows[0]:, max(0, cols[0] - 2):cols[-1] + 3]
        save(scale(crest, factor), FRAMES / f"{name}.png")


def build_panels() -> None:
    night = sheet("panel_night")
    piece = crop(night, pieces(night)[0])
    body, m, factor = panel(piece, 66)
    content = [m[0] - 14, m[1] - 18, m[2] - 14, m[3] - 18]
    crest_piece(piece, factor, "window_crest")
    frame("panel_night", body, m, content)
    frame("panel_night_plain", body, m, content)
    paper = sheet("panel_paper")
    piece = crop(paper, pieces(paper)[0])
    body, m, _ = panel(piece, 62)
    content = [m[0] - 12, m[1] - 16, m[2] - 12, m[3] - 16]
    frame("panel_paper", body, m, content)
    frame("panel_paper_plain", body, m, content)


def build_dialogue() -> None:
    rgba = sheet("dialogue")
    found = pieces(rgba)
    box = crop(rgba, found[0])
    body, m, factor = panel(box, 64, centre=40)
    frame("dialogue_box", body, m, [m[0] - 10, m[1] - 10, m[2] - 10, m[3] - 10])
    crest_piece(box, factor, "dialogue_crest")
    ribbon = crop(rgba, found[1])
    factor = 84 / ribbon.shape[0]
    small = scale(ribbon, factor)
    sh, sw = small.shape[:2]
    m = [int(sw * 0.16), 22, int(sw * 0.16), 22]
    teal = nine(small, m, centre=24, at=0.5)
    frame("ribbon_teal", teal, m, [m[0] - 6, 8, m[2] - 6, 12], pad=(6, 4, 6, 8))
    warm = recolour(teal)
    frame("ribbon", warm, m, [m[0] - 6, 8, m[2] - 6, 12], pad=(6, 4, 6, 8))


def build_buttons() -> None:
    rgba = sheet("buttons")
    found = pieces(rgba)
    for name, box in zip(["gold", "green", "paper", "night"], found):
        piece = crop(rgba, box)
        factor = 84 / piece.shape[0]
        small = scale(piece, factor)
        r = 30
        base = nine(small, [r, 24, r, 26], centre=20, at=0.5)
        m = [r, 24, r, 26]
        content = [18, 9, 18, 13]
        frame(f"btn_{name}_normal", base, m, content, pad=(6, 4, 6, 9))
        frame(f"btn_{name}_hover", adjust(base, bright=1.10, sat=1.05), m, content, pad=(6, 4, 6, 9))
        frame(f"btn_{name}_pressed", adjust(base, bright=0.88), m, [18, 12, 18, 10], pad=(6, 4, 6, 9))
        frame(f"btn_{name}_disabled", adjust(base, bright=0.85, sat=0.25, alpha=0.8), m, content, pad=(6, 4, 6, 9))


def build_slots() -> None:
    rgba = sheet("slots")
    found = pieces(rgba)
    night, paper, ring, mapring, roundkey, cap = [crop(rgba, b) for b in found[:6]]
    for name, src in [("night", night), ("paper", paper)]:
        factor = 104 / src.shape[0]
        small = scale(src, factor)
        m = [30, 30, 30, 30]
        base = nine(small, m, centre=24, at=0.5)
        frame(f"slot_{name}", base, m, [10, 10, 10, 10], pad=(4, 3, 4, 7))
        frame(f"slot_{name}_hover", adjust(base, bright=1.13), m, [10, 10, 10, 10], pad=(4, 3, 4, 7))
        if name == "night":
            frame("slot_night_pressed", adjust(base, bright=0.85), m, [10, 10, 10, 10], pad=(4, 3, 4, 7))
            frame("slot_night_primary", adjust(base, bright=1.08, tint=(0.95, 0.72, 0.30), tint_amount=0.16), m, [10, 10, 10, 10], pad=(4, 3, 4, 7))
            fm = [22, 22, 22, 22]
            field = nine(scale(src, 64 / src.shape[0]), fm, centre=20, at=0.5)
            frame("field_night", field, fm, [14, 9, 14, 9], with_shadow=False)
            frame("field_night_focus", adjust(field, bright=1.18, tint=(1.0, 0.85, 0.45), tint_amount=0.08), fm, [14, 9, 14, 9], with_shadow=False)
        else:
            frame("slot_paper_empty", adjust(base, alpha=0.72), m, [10, 10, 10, 10], pad=(4, 3, 4, 7))
            fm = [22, 22, 22, 22]
            field = nine(scale(src, 64 / src.shape[0]), fm, centre=20, at=0.5)
            frame("field_paper", field, fm, [14, 9, 14, 9], with_shadow=False)
            frame("field_paper_focus", adjust(field, bright=1.06, tint=(1.0, 0.85, 0.45), tint_amount=0.10), fm, [14, 9, 14, 9], with_shadow=False)
    # Portrait ring: square canvas centred on the ring's circle (the gem hangs below).
    w = ring.shape[1]
    side = int(w * 1.1)
    canvas = np.zeros((side, side, 4), np.float32)
    ox, oy = (side - w) // 2, (side - w) // 2
    hh = min(ring.shape[0], side - oy)
    canvas[oy:oy + hh, ox:ox + w] = ring[:hh]
    plain("portrait_ring", scale(canvas, 168 / side))
    # Minimap ring: same idea, star ornament above.
    w = mapring.shape[1]
    star = mapring.shape[0] - w
    side = w + 2 * star
    canvas = np.zeros((side, side, 4), np.float32)
    canvas[0:mapring.shape[0], star:star + w] = mapring
    plain("minimap_ring", scale(canvas, 512 / side))
    plain("round_night", scale(roundkey, 96 / roundkey.shape[0]))
    small = scale(cap, 48 / cap.shape[0])
    km = [14, 14, 14, 16]
    frame("keycap", nine(small, km, centre=12, at=0.5), km, [6, 1, 6, 3], with_shadow=False)


def build_bars() -> None:
    rgba = sheet("bars")
    found = pieces(rgba)
    track, red, green, gold, toast, tip, off, on, chevron = [crop(rgba, b, 2) for b in found[:9]]
    small = scale(track, 28 / track.shape[0])
    m = [16, 12, 16, 12]
    frame("bar_bg", nine(small, m, centre=8, at=0.5), m, [], with_shadow=False)
    for name, src in [("bar_fill", green), ("bar_fill_red", red), ("bar_fill_green", green), ("bar_fill_gold", gold)]:
        small = scale(src, 28 / src.shape[0])
        piece = nine(small, m, centre=8, at=0.5)
        if name == "bar_fill":
            # Tinted at runtime (meter colours): a bright neutral glossy fill.
            piece = adjust(piece, bright=1.45, sat=0.0)
        frame(name, piece, m, [], with_shadow=False)
    small = scale(toast, 72 / toast.shape[0])
    m = [52, 30, 52, 30]
    pill = nine(small, m, centre=16, at=0.5)
    frame("pill_night", pill, m, [26, 9, 26, 9], pad=(8, 5, 8, 10))
    tm = [40, 22, 40, 22]
    frame("tooltip", nine(scale(toast, 56 / toast.shape[0]), tm, centre=12, at=0.5), tm, [22, 9, 22, 9], pad=(6, 4, 6, 8))
    paper = remove_tail(tip)
    small = scale(paper, 72 / paper.shape[0])
    pm = [34, 30, 34, 30]
    frame("pill_paper", nine(small, pm, centre=16, at=0.5), pm, [22, 9, 22, 9], pad=(8, 5, 8, 10))
    plain("check_off", scale(off, 44 / off.shape[0]))
    plain("check_on", scale(on, 44 / on.shape[0]))
    c = scale(chevron, 26 / chevron.shape[1])
    canvas = np.zeros((32, 32, 4), np.float32)
    y0, x0 = (32 - c.shape[0]) // 2, (32 - c.shape[1]) // 2
    canvas[y0:y0 + c.shape[0], x0:x0 + c.shape[1]] = c
    plain("arrow_down", canvas)
    plain("arrow_down_light", adjust(canvas, bright=1.25, sat=0.6))


def build_icons() -> None:
    rgba = sheet("icons")
    found = pieces(rgba)
    if len(found) != len(ICON_NAMES):
        raise SystemExit(f"icons: found {len(found)} pieces, expected {len(ICON_NAMES)}")
    for name, box in zip(ICON_NAMES, found):
        piece = crop(rgba, box, 4)
        side = max(piece.shape[:2])
        canvas = np.zeros((side, side, 4), np.float32)
        y0, x0 = (side - piece.shape[0]) // 2, (side - piece.shape[1]) // 2
        canvas[y0:y0 + piece.shape[0], x0:x0 + piece.shape[1]] = piece
        save(scale(canvas, 128 / side), ICONS / f"{name}.png")


# ------------------------------------------------------------------ table

def write_tables() -> None:
    meta_path = FRAMES / "frames.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for name, (m, expand, content) in META.items():
        image = Image.open(FRAMES / f"{name}.png")
        meta[name] = {"size": list(image.size), "margins": m, "expand": expand, "content": content}
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    text = RPG_UI.read_text(encoding="utf-8")
    start = text.index("const FRAMES := {")
    end = text.index("\n}\n", start) + 3
    lines = ["const FRAMES := {"]
    for name, spec in meta.items():
        content = spec.get("content") or []
        lines.append(f'\t"{name}":[{spec["margins"]},{spec["expand"]},{content}],')
    lines.append("}\n")
    RPG_UI.write_text(text[:start] + "\n".join(lines) + text[end:], encoding="utf-8", newline="")


def main() -> None:
    build_panels()
    build_dialogue()
    build_buttons()
    build_slots()
    build_bars()
    build_icons()
    write_tables()
    for name in META: print("frame", name, META[name][0])
    print("icons", len(ICON_NAMES))


if __name__ == "__main__":
    main()
