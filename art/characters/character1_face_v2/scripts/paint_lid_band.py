"""Repaint the lid band next to the eye margin with lid-skin colour (removes Tripo's pale rim that would be
stretched over the eye when the lid closes) and flatten the normal map there. Texel rasterisation in UV space.
Usage: blender --background face_lids.blend --python paint_lid_band.py -- <out.blend> [rings]
"""
import bpy, sys, os, json
import numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(a[0]); RINGS = int(a[1]) if len(a) > 1 else 4
w = bpy.data.objects["WrapHead"]; me = w.data
C = json.loads(w["vertex_classes"]); sock = set(C["socket"]); bag = set(C["bag"])
n = len(me.vertices)
nbrs = [[] for _ in range(n)]
for e in me.edges:
    i, j = e.vertices; nbrs[i].append(j); nbrs[j].append(i)
mat = me.materials[0]
img_c = next(nd.image for nd in mat.node_tree.nodes if nd.type == 'TEX_IMAGE' and "basecolor" in nd.image.name)
img_n = next(nd.image for nd in mat.node_tree.nodes if nd.type == 'TEX_IMAGE' and "normal" in nd.image.name)
W, H = img_c.size
pc = np.array(img_c.pixels[:], dtype=np.float32).reshape(H, W, 4)
pn = np.array(img_n.pixels[:], dtype=np.float32).reshape(H, W, 4)
uv = me.uv_layers.active.data
# per-vertex ring distance from each eye margin over non-socket skin
blend = np.zeros(n); ref_ring = set()
for side in ("L", "R"):
    margin = list(w[f"eye_margin_{side}"])
    dist = {v: 0 for v in margin}; frontier = list(margin)
    for k in range(1, RINGS + 4):
        nxt = []
        for v in frontier:
            for u in nbrs[v]:
                if u not in dist and u not in sock and u not in bag:
                    dist[u] = k; nxt.append(u)
        frontier = nxt
    for v, k in dist.items():
        t = np.clip(k / RINGS, 0, 1)
        blend[v] = max(blend[v], 1 - t * t * (3 - 2 * t))
        if RINGS + 1 <= k <= RINGS + 3:
            ref_ring.add(v)
# extend the blend to everything the lid rig moves (bone weights), faded by weight
lidw = np.zeros(n)
for g in w.vertex_groups:
    if g.name.startswith("lid."):
        for v in me.vertices:
            for gg in v.groups:
                if gg.group == g.index:
                    lidw[v.index] += gg.weight
ww = np.clip(lidw / float(os.environ.get("LID_PAINT_W", 0.04)), 0, 1); ww = ww * ww * (3 - 2 * ww)
for i in range(n):
    if i in sock: ww[i] = 1.0
blend = np.maximum(blend, ww)
ref_ring = set(i for i in ref_ring if lidw[i] < 0.05) or ref_ring
# reference lid-skin colour: median texel colour at the loop-corners of reference-ring vertices
samples = []
for p in me.polygons:
    for li in p.loop_indices:
        v = me.loops[li].vertex_index
        if v in ref_ring:
            u_, v_ = uv[li].uv
            samples.append(pc[int(np.clip(v_, 0, .9999) * H), int(np.clip(u_ % 1, 0, .9999) * W), :3])
lid_rgb = np.median(np.array(samples), axis=0)
print("lid colour", np.round(lid_rgb, 3), "from", len(samples), "samples")
# rasterise triangles with any blended vertex
me.calc_loop_triangles()
for t in me.loop_triangles:
    bv = blend[list(t.vertices)]
    if bv.max() <= 0 or all(v in sock for v in t.vertices):
        continue
    P = np.array([[uv[l].uv[0] * W, uv[l].uv[1] * H] for l in t.loops])
    x0, y0 = np.floor(P.min(0)).astype(int) - 1; x1, y1 = np.ceil(P.max(0)).astype(int) + 1
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
    if x1 < x0 or y1 < y0: continue
    yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]; q = np.stack([xx + 0.5, yy + 0.5], -1)
    a_, b_, c_ = P; v0, v1 = b_ - a_, c_ - a_
    den = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(den) < 1e-9: continue
    w1 = ((q[..., 0] - a_[0]) * v1[1] - v1[0] * (q[..., 1] - a_[1])) / den
    w2 = (v0[0] * (q[..., 1] - a_[1]) - (q[..., 0] - a_[0]) * v0[1]) / den
    w0 = 1 - w1 - w2
    ins = (w0 >= -0.05) & (w1 >= -0.05) & (w2 >= -0.05)
    bb = np.clip(w0 * bv[0] + w1 * bv[1] + w2 * bv[2], 0, 1)[ins]
    sl = (yy[ins], xx[ins])
    pc[sl[0], sl[1], :3] = pc[sl[0], sl[1], :3] * (1 - bb[:, None]) + lid_rgb * bb[:, None]
    pn[sl[0], sl[1], :3] = pn[sl[0], sl[1], :3] * (1 - bb[:, None]) + np.array([0.5, 0.5, 1.0]) * bb[:, None]
# pale-rim removal: within PALE_RINGS of the margins, texels much lighter / less saturated than the lid skin
PALE_RINGS = int(os.environ.get("PALE_RINGS", 12))
near = set()
for side in ("L", "R"):
    seen = {v: 0 for v in w[f"eye_margin_{side}"]}; fr = list(seen)
    for k in range(PALE_RINGS):
        nx = []
        for v in fr:
            for u in nbrs[v]:
                if u not in seen and u not in bag:
                    seen[u] = k + 1; nx.append(u)
        fr = nx
    near |= set(seen)
lum_ref = float(lid_rgb @ np.array([0.2126, 0.7152, 0.0722])); sat_ref = float(lid_rgb.max() - lid_rgb.min())
cnt = 0
for t in me.loop_triangles:
    if not all(v in near for v in t.vertices):
        continue
    P = np.array([[uv[l].uv[0] * W, uv[l].uv[1] * H] for l in t.loops])
    x0, y0 = np.floor(P.min(0)).astype(int) - 1; x1, y1 = np.ceil(P.max(0)).astype(int) + 1
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
    if x1 < x0 or y1 < y0: continue
    yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    reg = pc[y0:y1 + 1, x0:x1 + 1, :3]
    lum = reg @ np.array([0.2126, 0.7152, 0.0722]); sat = reg.max(-1) - reg.min(-1)
    pale = np.clip((lum - lum_ref * 1.04) / (lum_ref * 0.12), 0, 1) * np.clip((sat_ref - sat) / (sat_ref * 0.6 + 1e-6), 0, 1)
    pale = np.clip(pale * 1.5, 0, 1)
    pc[y0:y1 + 1, x0:x1 + 1, :3] = reg * (1 - pale[..., None]) + lid_rgb * pale[..., None]
    cnt += int((pale > 0.5).sum())
print("pale texels replaced", cnt)
img_c.pixels.foreach_set(pc.ravel()); img_n.pixels.foreach_set(pn.ravel())
img_c.pack(); img_n.pack()
# lid inner material takes the same colour (slightly darker)
mi = bpy.data.materials.get("M_LidInner")
if mi:
    mi.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*(lid_rgb * 0.8) ** 2.2, 1)
w["lid_rgb"] = [float(x) for x in lid_rgb]
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("PAINTED")
