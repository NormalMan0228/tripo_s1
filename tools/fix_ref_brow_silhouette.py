"""Repair the blurred brow-removal patch on side-view references (character1_v2_bald_clean 02_left / 04_right).

The brow cards were inpainted with a blur, leaving a soft, semi-transparent silhouette and a brown smear at the brow ridge.
Tripo reads the soft silhouette as a thin fin on the forehead.  Fix: rebuild a crisp front contour across the band rows
(cubic fit through the clean contour above and below), set everything outside it to the flat background and inpaint the
soft zone + smear inside it from the surrounding skin.
Usage: python fix_ref_brow_silhouette.py <src.png> <dst.png> <facing left|right> <y0> <y1> [smear_depth_px]
"""
import sys
import numpy as np, cv2

src, dst, facing, y0, y1 = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
depth = int(sys.argv[6]) if len(sys.argv) > 6 else 100
im = cv2.imread(src)
if facing == 'right':
    im = im[:, ::-1].copy()
bg = im[5, 5].astype(int)
d = np.abs(im.astype(int) - bg).sum(2)
H, W = d.shape


def contour(y, thr=30):
    xs = np.where(d[y] > thr)[0]
    return xs.min() if len(xs) else W


ys_fit = [y for y in range(y0 - 50, y0 - 4, 2)] + [y for y in range(y1 + 4, y1 + 40, 2)]
cf = np.polyfit(ys_fit, [contour(y) for y in ys_fit], 3)
mask = np.zeros((H, W), np.uint8)
out = im.copy()
# background next to the face is replaced by the row's skin colour so inpainting only samples skin
xcs = {}
for y in range(y0 - 60, y1 + 61):
    xcs[y] = int(round(np.polyval(cf, y))) if y0 <= y <= y1 else contour(y)
    xs = min(xcs[y] + 4, W - 1) if not (y0 <= y <= y1) else None
    if xs is not None: out[y, :xcs[y] + 2] = out[y, xs]
for y in range(y0, y1 + 1):
    mask[y, :xcs[y] + depth] = 255
mask[:, :0] = 0
# do not inpaint the eye opening (bright/dark pixels unlike skin)
# fill: per column, vertical linear blend between the clean rows just above and below the band; feather the inner edge
out2 = out.copy().astype(float)
top = cv2.GaussianBlur(out[y0 - 8:y0 - 1].astype(np.float32).mean(0, keepdims=True), (0, 0), sigmaX=8, sigmaY=0.1)[0]
bot = cv2.GaussianBlur(out[y1 + 2:y1 + 9].astype(np.float32).mean(0, keepdims=True), (0, 0), sigmaX=10, sigmaY=0.1)[0]
for y in range(y0, y1 + 1):
    t = (y - y0 + 1) / (y1 - y0 + 2); t = t * t * (3 - 2 * t)
    fill = (1 - t) * top + t * bot
    xe = xcs[y] + depth
    for x in range(0, min(xe, W)):
        a = 1.0 if x < xe - 25 else (xe - x) / 25.0
        out2[y, x] = a * fill[x] + (1 - a) * out[y, x]
out2 = np.clip(out2, 0, 255).astype(np.uint8)
for y in range(y0 - 60, y1 + 61):                # restore background outside the (new) contour
    out2[y, :xcs[y]] = bg if y0 <= y <= y1 else im[y, :xcs[y]]
    if not (y0 <= y <= y1): out2[y, xcs[y]:xcs[y] + 2] = im[y, xcs[y]:xcs[y] + 2]
if facing == 'right':
    out2 = out2[:, ::-1]
cv2.imwrite(dst, out2)
print('fixed', dst, 'contour fit', np.round(cf, 6).tolist())
