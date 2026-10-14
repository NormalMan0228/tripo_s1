"""Remove the brows painted into the Skin base-colour texture (for brow-free Tripo references).

Run on character1_face_v1/03_neutral_candidate.blend (still has the original Tripo Brow.L/R meshes).
Skin texels inside UV triangles of skin faces near the brow meshes are masked if darker than the local skin,
then filled by diffusion from the unmasked surroundings. Writes the new texture PNG and a mask preview.
Usage: blender --background 03_neutral_candidate.blend --python remove_painted_brows.py -- <out_dir>
"""
import bpy, sys, os
import numpy as np
from mathutils.kdtree import KDTree

out = os.path.abspath(sys.argv[sys.argv.index("--") + 1]); os.makedirs(out, exist_ok=True)
skin = bpy.data.objects["Skin"]
img = next(n.image for n in skin.data.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE' and "basecolor" in n.image.name)
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)

bro = np.concatenate([[tuple(o.matrix_world @ v.co) for v in o.data.vertices] for o in (bpy.data.objects["Brow.L"], bpy.data.objects["Brow.R"])])
kd = KDTree(len(bro))
for i, p in enumerate(bro):
    kd.insert(p, i)
kd.balance()

me = skin.data
me.calc_loop_triangles()
uv = me.uv_layers.active.data
region = np.zeros((H, W), bool)
for t in me.loop_triangles:
    c = sum((me.vertices[v].co for v in t.vertices), me.vertices[t.vertices[0]].co * 0) / 3
    if kd.find(skin.matrix_world @ c)[2] > 0.022:
        continue
    P = np.array([[uv[l].uv[0] * W, uv[l].uv[1] * H] for l in t.loops])
    x0, y0 = np.floor(P.min(0)).astype(int); x1, y1 = np.ceil(P.max(0)).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
    if x1 < x0 or y1 < y0:
        continue
    yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    q = np.stack([xx + 0.5, yy + 0.5], -1)
    a, b, c3 = P
    v0, v1 = b - a, c3 - a
    den = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(den) < 1e-9:
        continue
    w1 = ((q[..., 0] - a[0]) * v1[1] - v1[0] * (q[..., 1] - a[1])) / den
    w2 = (v0[0] * (q[..., 1] - a[1]) - (q[..., 0] - a[0]) * v0[1]) / den
    inside = (w1 >= -0.02) & (w2 >= -0.02) & (w1 + w2 <= 1.02)
    region[y0:y1 + 1, x0:x1 + 1] |= inside

lum = px[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
ref = np.median(lum[region]) if region.any() else 0.5
mask = region.copy()            # fill the whole skin area under the brows from its surroundings
# dilate the mask a few texels so soft brow edges go too
for _ in range(3):
    m = mask.copy()
    m[1:] |= mask[:-1]; m[:-1] |= mask[1:]; m[:, 1:] |= mask[:, :-1]; m[:, :-1] |= mask[:, 1:]
    mask = m & region | mask
print("brow region texels", int(region.sum()), "masked", int(mask.sum()))

# diffusion fill (multi-scale: coarse first, then refine)
fill = px[..., :3].copy()
known = ~mask
for it in range(1500):
    acc = np.zeros_like(fill); cnt = np.zeros((H, W, 1), np.float32)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        acc += np.roll(np.roll(fill, dy, 0), dx, 1); cnt += 1
    avg = acc / cnt
    fill[mask] = avg[mask]
# re-add a little of the original skin noise from just outside (keeps the texture from looking flat)
noise = px[..., :3] - np.stack([np.roll(px[..., k], 2, 0) for k in range(3)], -1)
fill[mask] += 0.15 * noise[mask]
newpx = px.copy(); newpx[..., :3] = np.clip(fill, 0, 1)
new = bpy.data.images.new("skin_basecolor_nobrow", W, H, alpha=True)
new.pixels.foreach_set(newpx.ravel())
new.filepath_raw = os.path.join(out, "skin_basecolor_nobrow.png"); new.file_format = 'PNG'; new.save()
mk = bpy.data.images.new("brow_mask", W, H)
mpx = np.zeros((H, W, 4), np.float32); mpx[..., 3] = 1; mpx[mask, 0] = 1; mpx[region & ~mask, 2] = 0.5
mk.pixels.foreach_set(mpx.ravel()); mk.filepath_raw = os.path.join(out, "brow_mask.png"); mk.file_format = 'PNG'; mk.save()
print("WROTE", new.filepath_raw)
