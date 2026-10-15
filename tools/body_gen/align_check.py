"""Check that reference views line up (front / side / back) before 3D generation.

  python tools/body_gen/align_check.py out.png "Label" view1.png view2.png ...
  python tools/body_gen/align_check.py out.png "Label" --sheet turnaround.png

Each view is cut to its non-white silhouette. Views are drawn side by side at the
same pixel scale (all views of one set must come from images of the same size),
with guide lines at the front view's top, 25/50/75 % height and baseline. The
text under each view gives its top and bottom offset from the front view in % of
the front height; a good set stays within about 2 %.
--sheet splits one turnaround image into views at the white gaps between them;
--thirds cuts it into three equal columns (views that touch each other);
--grid2 reads a 2x2 sheet (front | right side / back | left side), compared per cell.
For a front/left/right/back set it also compares the two profiles: the left view
should match the mirrored right view (facing opposite ways); "same" higher than
"mirror" means both profiles face the same way, which breaks the 3D input.
Prints a JSON summary.
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from bgmask import fg_mask


def mask_of(im):
    m = fg_mask(im.convert("RGB"))
    # Drop drawn guide lines: rows that are filled across most of the width.
    m[m.mean(axis=1) > 0.97] = False
    return m


def bbox(m):
    ys, xs = np.where(m)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def main_part(m):
    """Keep the connected blobs that touch the middle 50 % of the crop (drops bits of
    neighbouring views that spill into a --thirds column)."""
    lab, n = ndimage.label(ndimage.binary_closing(m, iterations=2))
    if n <= 1:
        return m
    w = m.shape[1]
    centre = lab[:, int(0.25 * w):int(0.75 * w)]
    keep = [i for i in range(1, n + 1) if (centre == i).sum() > 0.02 * (lab == i).sum()]
    sizes = ndimage.sum(np.ones_like(lab), lab, index=keep) if keep else []
    keep = [k for k, s in zip(keep, sizes) if s > 0.01 * m.sum()]
    return m & np.isin(lab, keep) if keep else m


def symmetry(m, b):
    """Left-right silhouette match (IoU %) about the body's median column: 100 = perfectly mirrored.

    The middle 60 % of the height decides the centre line, so a neighbouring view's
    wing tip at the image edge does not drag it."""
    x0, y0, x1, y1 = b
    band = m[y0 + int(0.2 * (y1 - y0)):y0 + int(0.8 * (y1 - y0))]
    xs = np.where(band)[1]
    if len(xs) == 0:
        return 0.0
    cx = float(np.median(xs))
    ys, xs = np.where(m)
    mx = np.round(2 * cx - xs).astype(int)
    ok = (mx >= 0) & (mx < m.shape[1])
    mirror = np.zeros_like(m)
    mirror[ys[ok], mx[ok]] = True
    inter = np.logical_and(m, mirror).sum()
    union = np.logical_or(m, mirror).sum()
    return round(100 * inter / max(1, union), 1)


def side_pair(a, b):
    """IoU % of two profile masks cropped to their boxes and scaled to one size:
    (left vs mirrored right, left vs right). A correct pair scores higher mirrored."""
    def norm(m):
        x0, y0, x1, y1 = bbox(m)
        return np.asarray(Image.fromarray(m[y0:y1 + 1, x0:x1 + 1].astype(np.uint8) * 255).resize((256, 256))) > 127
    na, nb = norm(a), norm(b)
    iou = lambda p, q: round(100 * np.logical_and(p, q).sum() / max(1, np.logical_or(p, q).sum()), 1)
    return float(iou(na, nb[:, ::-1])), float(iou(na, nb))


def split_sheet(im, min_gap=12):
    m = mask_of(im)
    # drop specks: ignore columns with < 0.3 % filled pixels
    col = m.sum(axis=0) > max(2, int(0.003 * m.shape[0]))
    runs, start, gap = [], None, 0
    for x, filled in enumerate(col):
        if filled:
            if start is None:
                start = x
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                runs.append((start, x - gap))
                start, gap = None, 0
    if start is not None:
        runs.append((start, len(col) - 1))
    runs = [r for r in runs if r[1] - r[0] > im.width * 0.05]
    return [im.crop((max(0, a - 10), 0, min(im.width, b + 10), im.height)) for a, b in runs]


def main():
    args = sys.argv[1:]
    out, label = args[0], args[1]
    if args[2] == "--grid2":
        sheet = Image.open(args[3]).convert("RGB")
        w, h = sheet.width // 2, sheet.height // 2
        cells = {"front": (0, 0), "right": (1, 0), "back": (0, 1), "left": (1, 1)}
        names = ["front", "left", "right", "back"]
        views = [sheet.crop((cells[n][0] * w, cells[n][1] * h, (cells[n][0] + 1) * w, (cells[n][1] + 1) * h)) for n in names]
    elif args[2] == "--thirds":
        sheet = Image.open(args[3]).convert("RGB")
        w = sheet.width // 3
        views = [sheet.crop((i * w, 0, (i + 1) * w, sheet.height)) for i in range(3)]
        names = ["front", "side", "back"]
    elif args[2] == "--sheet":
        views = split_sheet(Image.open(args[3]).convert("RGB"))
        names = ["front", "side", "back", "extra"][:len(views)]
    else:
        views = [Image.open(p).convert("RGB") for p in args[2:]]
        names = ["front", "left", "right", "back"][:len(views)]
    masks = [main_part(mask_of(v)) for v in views]
    boxes = [bbox(m) for m in masks]
    f = boxes[0]
    fh = f[3] - f[1]
    report = []
    for n, b in zip(names, boxes):
        report.append({"view": n, "top_pct": round(100 * (b[1] - f[1]) / fh, 1),
                       "bottom_pct": round(100 * (b[3] - f[3]) / fh, 1),
                       "height_pct": round(100 * (b[3] - b[1]) / fh, 1)})
    for r, m, b in zip(report, masks, boxes):
        if r["view"] in ("front", "back"):
            r["symmetry_pct"] = symmetry(m, b)
    worst = max(max(abs(r["top_pct"]), abs(r["bottom_pct"])) for r in report)
    sides = None
    if "left" in names and "right" in names:
        mir, same = side_pair(masks[names.index("left")], masks[names.index("right")])
        sides = {"mirror_pct": mir, "same_pct": same, "ok": bool(mir > same)}

    # Draw: crop every view to the same vertical window, keep pixel scale.
    top = min(b[1] for b in boxes) - 20
    bot = max(b[3] for b in boxes) + 20
    tiles = []
    for v, b in zip(views, boxes):
        x0, x1 = max(0, b[0] - 20), min(v.width, b[2] + 20)
        tiles.append(v.crop((x0, max(0, top), x1, min(v.height, bot))))
    H = max(t.height for t in tiles)
    scale = min(1.0, 520 / H)
    tiles = [t.resize((max(1, int(t.width * scale)), max(1, int(t.height * scale)))) for t in tiles]
    W = sum(t.width for t in tiles) + 20 * (len(tiles) + 1)
    lab = 70
    canvas = Image.new("RGB", (W, int(H * scale) + lab + 46), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    fb = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 22)
    fs = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 16)
    ok = worst <= 2.0
    d.text((14, 8), f"{label}  ·  최대 어긋남 {worst:.1f}%  ({'맞음' if ok else '어긋남'})", font=fb,
           fill=(45, 125, 70) if ok else (192, 57, 43))
    if sides:
        msg = (f"좌·우 측면: 서로 반대 방향 (거울 일치 {sides['mirror_pct']:.0f}%)" if sides["ok"] else
               f"좌·우 측면: 같은 방향을 봄 → 한쪽 반전 필요 (거울 {sides['mirror_pct']:.0f}% < 그대로 {sides['same_pct']:.0f}%)")
        d.text((W // 2, 10), msg, font=fs, fill=(45, 125, 70) if sides["ok"] else (192, 57, 43))
    x = 20
    oy = 46
    for t in tiles:
        canvas.paste(t, (x, oy))
        x += t.width + 20
    for frac, col, w in ((0, (220, 40, 40), 2), (0.25, (120, 120, 220), 1), (0.5, (120, 120, 220), 1),
                         (0.75, (120, 120, 220), 1), (1.0, (220, 40, 40), 2)):
        y = oy + int((f[1] + frac * fh - top) * scale)
        d.line((10, y, W - 10, y), fill=col, width=w)
    x = 20
    for t, r in zip(tiles, report):
        d.text((x, oy + t.height + 6), f"{r['view']}", font=fb, fill=(42, 38, 34))
        sym = f" · 대칭 {r['symmetry_pct']:.0f}%" if "symmetry_pct" in r else ""
        d.text((x, oy + t.height + 34), f"위 {r['top_pct']:+.1f}% · 아래 {r['bottom_pct']:+.1f}%{sym}", font=fs,
               fill=(42, 38, 34))
        x += t.width + 20
    canvas.save(out)
    print(json.dumps({"label": label, "worst_pct": worst, "sides": sides, "views": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
