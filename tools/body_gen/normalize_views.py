"""Cut a 2x2 turnaround sheet into four aligned view images for multiview 3D input.

  python tools/body_gen/normalize_views.py sheet.png out_dir [--size 2048]

The sheet layout is front | right side / back | left side (Nano Banana prompt
in docs). Each cell's silhouette is found (non-white pixels, largest blobs near
the cell centre). Every view is then scaled to the front view's height, cut out of its
background and placed on a white square with the soles on the same baseline (90 % of the height), and
centred on the body's median column (front/back) or on the whole silhouette
(side views, so tails are not cut off). That makes front, side and back line up
exactly, which the image model alone does not guarantee (rows drift by 4-12 %).
Writes front.png, left.png, right.png, back.png.

The right view must face right and the left view left (Tripo's convention). When
the image model draws both profiles facing the same way, pick the source cell per
side and mirror it with a trailing ~, e.g. --right br~ --left br (cells: tl, tr,
bl, br). For a symmetric monster the mirrored profile is the true opposite side.
--bg-sat / --bg-light tune the background cut (bgmask.fg_mask): lower --bg-sat (e.g. 8)
keeps pale grey stone or skin highlights that the default (22) would treat as background;
the lowest 6 % of the silhouette (--bg-foot 0.15 for 15 %) keeps the default so contact
shadows are still removed.
--bg-out R,G,B paints the output background in that colour instead of white (use a light
grey such as 208,208,208 for white or pale monsters, so Tripo can still see their outline).
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from bgmask import fg_mask, fg_mask_strict


BG = {}  # fg_mask overrides from --bg-sat / --bg-light
BG_OUT = (255, 255, 255)  # --bg-out R,G,B: output background (light grey for white/pale monsters)


def silhouette(cell):
    if "sat" in BG:
        m = fg_mask_strict(cell.convert("RGB"), **BG)
    else:
        m = fg_mask(cell.convert("RGB"), **BG)
    lab, n = ndimage.label(ndimage.binary_closing(m, iterations=2))
    if n > 1:
        w = m.shape[1]
        centre = lab[:, int(0.2 * w):int(0.8 * w)]
        keep = [i for i in range(1, n + 1) if (centre == i).any()]
        sizes = ndimage.sum(np.ones_like(lab), lab, index=keep) if keep else []
        keep = [k for k, s in zip(keep, sizes) if s > 0.002 * m.size]
        if keep:
            m = m & np.isin(lab, keep)
    ys, xs = np.where(m)
    return m, (xs.min(), ys.min(), xs.max(), ys.max())


def main():
    sheet = Image.open(sys.argv[1]).convert("RGB")
    out = sys.argv[2]
    size = int(sys.argv[sys.argv.index("--size") + 1]) if "--size" in sys.argv else 2048
    os.makedirs(out, exist_ok=True)
    w, h = sheet.width // 2, sheet.height // 2
    global BG_OUT
    if "--bg-out" in sys.argv:
        BG_OUT = tuple(int(x) for x in sys.argv[sys.argv.index("--bg-out") + 1].split(","))
    for flag, key in (("--bg-sat", "sat"), ("--bg-light", "light"), ("--bg-foot", "foot_band")):
        if flag in sys.argv:
            val = sys.argv[sys.argv.index(flag) + 1]
            BG[key] = float(val) if key == "foot_band" else int(val)
    pos = {"tl": (0, 0), "tr": (1, 0), "bl": (0, 1), "br": (1, 1)}
    src = {"front": "tl", "right": "tr", "back": "bl", "left": "br"}
    for side in ("right", "left"):
        if f"--{side}" in sys.argv:
            src[side] = sys.argv[sys.argv.index(f"--{side}") + 1]
    data = {}
    for name, spec in src.items():
        cx, cy = pos[spec.rstrip("~")]
        cell = sheet.crop((cx * w, cy * h, (cx + 1) * w, (cy + 1) * h))
        if spec.endswith("~"):
            cell = cell.transpose(Image.FLIP_LEFT_RIGHT)
        m, b = silhouette(cell)
        data[name] = (cell, m, b)
    # One shared height for all views; shrink it if the widest view (wings, a long
    # tail in profile) would not fit the canvas.
    target_h = size * 0.8
    for _, _, (x0, y0, x1, y1) in data.values():
        need = (x1 - x0) * target_h / max(1, (y1 - y0))
        if need > size * 0.94:
            target_h *= size * 0.94 / need
    for name, (cell, m, b) in data.items():
        x0, y0, x1, y1 = b
        crop = cell.crop((x0, y0, x1 + 1, y1 + 1))
        mcrop = m[y0:y1 + 1, x0:x1 + 1]
        s = target_h / max(1, (y1 - y0))  # every view gets the same height
        nw, nh = max(1, int(crop.width * s)), max(1, int(crop.height * s))
        crop = crop.resize((nw, nh), Image.LANCZOS)
        # Paint the background (grey gradient, contact shadow) pure white, soft edge.
        alpha = Image.fromarray((ndimage.binary_closing(mcrop, iterations=2) * 255).astype(np.uint8))
        alpha = alpha.resize((nw, nh), Image.LANCZOS)
        crop = Image.composite(crop, Image.new("RGB", (nw, nh), BG_OUT), alpha)
        if name in ("front", "back"):
            # symmetric views: centre on the body's middle column
            band = mcrop[int(0.2 * mcrop.shape[0]):int(0.8 * mcrop.shape[0])]
            mid = float(np.median(np.where(band)[1])) if band.any() else mcrop.shape[1] / 2
        else:
            # side views: centre the whole silhouette so a long tail or snout stays on the canvas
            mid = mcrop.shape[1] / 2
        canvas = Image.new("RGB", (size, size), BG_OUT)
        px = int(size / 2 - mid * s)
        px = min(max(px, 0), size - nw)  # never push any part off the canvas
        py = int(size * 0.9) - nh
        canvas.paste(crop, (px, py))
        canvas.save(os.path.join(out, f"{name}.png"))
    print("ok", out)


if __name__ == "__main__":
    main()
