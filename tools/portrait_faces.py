"""Blink and talk overlays for dialogue standees (no new art pipeline, free Tripo image tool).

For a standee game/assets/portraits/standee/<name>.png (or assets/ui/standee/<id>.png) the 03
session redraws it on flat magenta with only the eyes closed and with only the mouth a little open
(output/ui-art-20261015/faces/<name>_{eyes,mouth}_<n>.jpg). This script lines each redraw up with
the standee (ECC affine alignment), keeps only what changed inside the face (the top of the figure),
feathers it, and writes a full-size overlay beside the standee:

  <name>_blink.png   closed eyes over the neutral face (RpgUi.face_frames shows it for ~0.1 s)
  <name>_talk.png    the open mouth, toggled while a line types (RpgUi._talk_loop)

Of the takes it keeps the one that changed the least outside the face (the redraw that stayed
truest to the original).

    .tools/art-venv/Scripts/python.exe tools/portrait_faces.py haeru moru naru sora
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_standees  # noqa: E402

FACES = Path(r"C:/lsm26/triphthonS1/output/ui-art-20261015/faces")
STANDEES = [ROOT / "game" / "assets" / "portraits" / "standee", ROOT / "game" / "assets" / "ui" / "standee"]


def standee_of(name: str) -> Path:
    for folder in STANDEES:
        if (folder / f"{name}.png").exists(): return folder / f"{name}.png"
    raise SystemExit(f"no standee for {name}")


def aligned(take: Path, size: tuple[int, int], base_gray: np.ndarray) -> np.ndarray:
    rgb = np.asarray(Image.open(take).convert("RGB"), np.float32) / 255.0
    rgba = build_standees.key(rgb)
    rgba = cv2.resize(rgba, size, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor((rgba[..., :3] * rgba[..., 3:4]).astype(np.float32), cv2.COLOR_RGB2GRAY)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        _, warp = cv2.findTransformECC(base_gray, gray, warp, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-5), None, 5)
    except cv2.error:
        pass
    return cv2.warpAffine(rgba, warp, size, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)


def overlay(base: np.ndarray, take: np.ndarray) -> tuple[np.ndarray, float]:
    """The changed part inside the face, and how much changed outside it (lower is truer)."""
    alpha = base[..., 3]
    ys = np.nonzero(alpha.max(1) > 0.5)[0]
    top, bottom = ys.min(), ys.max()
    face = np.zeros(alpha.shape, bool)
    face[top:top + int((bottom - top) * 0.36)] = True
    diff = np.abs(take[..., :3] - base[..., :3]).max(-1) * np.minimum(alpha, take[..., 3])
    changed = (diff > 0.14).astype(np.uint8)
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    outside = float((changed.astype(bool) & ~face).mean())
    keep = changed.astype(bool) & face
    count, labels, stats, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8), 8)
    mask = np.zeros(alpha.shape, np.float32)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= 30: mask[labels == index] = 1.0
    mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
    mask = cv2.GaussianBlur(mask, (0, 0), 2.0) * alpha
    out = np.dstack([take[..., :3], np.clip(mask, 0, 1)])
    return out, outside


def main(names: list[str]) -> None:
    for name in names:
        path = standee_of(name)
        base = np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255.0
        size = (base.shape[1], base.shape[0])
        base_gray = cv2.cvtColor((base[..., :3] * base[..., 3:4]).astype(np.float32), cv2.COLOR_RGB2GRAY)
        for part, suffix in (("eyes", "blink"), ("mouth", "talk")):
            takes = sorted(FACES.glob(f"{name}_{part}_*.jpg"))
            best = None
            for take in takes:
                layer, outside = overlay(base, aligned(take, size, base_gray))
                if layer[..., 3].max() < 0.5: continue
                if best is None or outside < best[1]: best = (layer, outside, take.name)
            if best is None:
                print(name, part, "no usable take")
                continue
            Image.fromarray((np.clip(best[0], 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path.with_name(f"{name}_{suffix}.png"), optimize=True)
            print(name, suffix, best[2], "outside %.4f" % best[1])


if __name__ == "__main__":
    main(sys.argv[1:])
