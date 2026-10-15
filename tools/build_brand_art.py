"""The game's logo, title key art and loading-card backdrops, from generated sources.

Sources were generated free with Nano Banana Pro in Tripo Studio's image tool (16:9, 4K
option, 4096x2272) on 2026-10-15 and live outside git in output/ui-art-20261015/raw/:

  vg_logo_<n>.jpg          "Villagen" wordmark on flat magenta (keyed out here)
  vg_start_<n>.jpg         the island village from the sea at sunrise (first load)
  vg_morning|golden|evening_<n>.jpg   the three title key arts widened to 16:9
  vg_3d_<place>_<n>.jpg    loading backdrops: square (village), interior (rooms),
                           forest, quarry, frost (expedition regions)

PICKS names the chosen source for every game asset; change a line and re-run to swap one.
Outputs (git-tracked, imported by Godot):

  game/assets/ui/logo.png                 keyed logo, LOGO_WIDTH wide, transparent
  game/assets/ui/loading_cover.jpg        first-load cover (same path as before)
  game/assets/title_<time>.jpg            title key art (same paths as before)
  game/assets/ui/loading/<place>.jpg      place backdrops (transition.gd BACKDROPS)

    .tools/art-venv/Scripts/python.exe tools/build_brand_art.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_standees import key  # noqa: E402  (flat-backdrop key with edge un-mixing)

PICKS = {
    "logo": "vg_logo_3.jpg",
    "cover": "vg_start_1.jpg",
    "title_morning": "vg_morning_1.jpg",
    "title_golden": "vg_golden_1.jpg",
    "title_evening": "vg_evening_1.jpg",
    "village": "vg_3d_square_2.jpg",
    "room": "vg_3d_interior_1.jpg",
    "forest": "vg_3d_forest_1.jpg",
    "quarry": "vg_3d_quarry_1.jpg",
    "frost": "vg_3d_frost_2.jpg",
}
LOGO_WIDTH = 900      # shown at up to ~430 logical px; the import makes mipmaps for the rest
HERO_WIDTH = 2560     # title and cover: the first things the player sees, sharp at 1440p
BACKDROP_WIDTH = 1600 # place cards are dimmed under the name, so less is enough
QUALITY = 90


def raw_dir() -> Path:
    """output/ is git-ignored and shared: a worktree reads the main checkout's copy."""
    local = ROOT / "output" / "ui-art-20261015" / "raw"
    if local.exists():
        return local
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    return Path(common).parent / "output" / "ui-art-20261015" / "raw"


def save_jpg(src: Path, dst: Path, width: int) -> None:
    im = Image.open(src).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=QUALITY, optimize=True, progressive=False)
    print(f"{dst.relative_to(ROOT)}  {im.width}x{im.height}  {dst.stat().st_size // 1024} KB")


def clean_glow(rgba: np.ndarray) -> np.ndarray:
    """Drops the generator's pink-tinted glow around the star: light pixels whose blue is not
    below their green, but only where they connect to the empty outside (the letters' own
    white highlights sit inside the dark outline and stay)."""
    r, g, b, al = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    luma = 0.3 * r + 0.59 * g + 0.11 * b
    glow = (b > g - 0.04) & (r > g - 0.02) & (luma > 0.45) & (al > 0.02)
    open_ = (glow | (al < 0.5)).astype(np.uint8)
    _, lab = cv2.connectedComponents(open_, connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    outside = np.isin(lab, list(border))
    kill = cv2.dilate((glow & outside).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~((al > 0.5) & ~glow)
    al = np.where(kill, 0, al)
    solid = (al > 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    keep = np.zeros_like(solid)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] > 240:
            keep[labels == index] = 1
    keep = cv2.GaussianBlur(cv2.dilate(keep, np.ones((9, 9), np.uint8)).astype(np.float32), (0, 0), 1.2)
    out = rgba.copy()
    out[..., 3] = al * keep
    return out


def build_logo(src: Path, dst: Path) -> None:
    rgb = np.asarray(Image.open(src).convert("RGB"), np.float32) / 255
    rgba = clean_glow(key(rgb, figure=False))
    ys, xs = np.where(rgba[..., 3] > 0.05)
    pad = 24
    rgba = rgba[max(ys.min() - pad, 0):ys.max() + pad, max(xs.min() - pad, 0):xs.max() + pad]
    # Premultiplied resize so the edges keep no dark or magenta fringe.
    pm = np.dstack([rgba[..., :3] * rgba[..., 3:], rgba[..., 3:]])
    height = round(rgba.shape[0] * LOGO_WIDTH / rgba.shape[1])
    small = np.asarray(Image.fromarray((pm * 255).round().astype(np.uint8), "RGBA").resize((LOGO_WIDTH, height), Image.LANCZOS), np.float32) / 255
    alpha = small[..., 3:]
    colour = np.where(alpha > 1e-3, small[..., :3] / np.maximum(alpha, 1e-3), 0)
    Image.fromarray((np.dstack([colour, alpha]) * 255).clip(0, 255).round().astype(np.uint8), "RGBA").save(dst, optimize=True)
    print(f"{dst.relative_to(ROOT)}  {LOGO_WIDTH}x{height}  {dst.stat().st_size // 1024} KB")


def main() -> None:
    raw = raw_dir()
    missing = [name for name in PICKS.values() if not (raw / name).exists()]
    if missing:
        sys.exit(f"missing sources in {raw}: {missing}")
    assets = ROOT / "game" / "assets"
    build_logo(raw / PICKS["logo"], assets / "ui" / "logo.png")
    save_jpg(raw / PICKS["cover"], assets / "ui" / "loading_cover.jpg", HERO_WIDTH)
    for time in ("morning", "golden", "evening"):
        save_jpg(raw / PICKS["title_" + time], assets / f"title_{time}.jpg", HERO_WIDTH)
    for place in ("village", "room", "forest", "quarry", "frost"):
        save_jpg(raw / PICKS[place], assets / "ui" / "loading" / f"{place}.jpg", BACKDROP_WIDTH)


if __name__ == "__main__":
    main()
