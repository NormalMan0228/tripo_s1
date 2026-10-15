"""Fix a 2x2 turnaround sheet before normalize_views.py.

  python tools/body_gen/sheet_prep.py sheet.png out.png [--grid G] [--ext CELL:L:R:T:B ...]

Re-tile a 2x2 sheet: optional white-out of grid lines at the midlines (--grid G = half band px),
and per-cell extension into neighbours (--ext tr:L:R:T:B) so parts that cross a cell border are kept.
Each extended region is scaled to fit its cell (normalize_views rescales every view to one height anyway)."""
import sys
from PIL import Image, ImageDraw
src, out = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
im = Image.open(src).convert("RGB")
W = im.width; w = W // 2
if "--grid" in args:
    g = int(args[args.index("--grid") + 1])
    d = ImageDraw.Draw(im)
    d.rectangle((w - g, 0, w + g, W), fill=(255, 255, 255))
    d.rectangle((0, w - g, W, w + g), fill=(255, 255, 255))
ext = {}
for i, a in enumerate(args):
    if a == "--ext":
        c, *v = args[i + 1].split(":")
        ext[c] = [int(x) for x in v]
res = Image.new("RGB", (W, W), (255, 255, 255))
for c, (cx, cy) in {"tl": (0, 0), "tr": (1, 0), "bl": (0, 1), "br": (1, 1)}.items():
    L, R, T, B = ext.get(c, (0, 0, 0, 0))
    box = (max(0, cx * w - L), max(0, cy * w - T), min(W, (cx + 1) * w + R), min(W, (cy + 1) * w + B))
    reg = im.crop(box)
    s = min(w / reg.width, w / reg.height)
    if s < 1:
        reg = reg.resize((int(reg.width * s), int(reg.height * s)), Image.LANCZOS)
    cell = Image.new("RGB", (w, w), (255, 255, 255))
    # keep the soles' baseline: align bottom, centre horizontally
    cell.paste(reg, ((w - reg.width) // 2, w - reg.height))
    res.paste(cell, (cx * w, cy * w))
res.save(out)
print("ok", out)
