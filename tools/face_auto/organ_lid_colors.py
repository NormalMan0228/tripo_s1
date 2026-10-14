"""겹침생성 · eyelid colours for ring lids after project_texture.py.

The front projection paints part of the lid rings with the eye itself (the image's eye and the 3D rim never match
exactly, and the part of the upper lid that unrolls in a blink is tucked under the fold at rest), so a closed eye
shows iris and sclera smears. Each lid column (same eye_u) takes its skin colour from rings 2-3 (outside the eye):
inner lid rings get that skin colour, the two margin rows keep their colour only where it is dark (lash line),
and the lid edge (tuck rings) is darkened toward a lash line.
Irregular rings (loop_organs.py, u not on a column grid): the columns are 64 bins of u, empty bins interpolated.
Usage: blender -b <tex.blend> -P organ_lid_colors.py -- <out.blend>
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
face = bpy.data.objects['face']; me = face.data
X = np.array([tuple(d.co) for d in (me.shape_keys.key_blocks[0].data if me.shape_keys else me.vertices)])
ring = np.array([d.value for d in me.attributes['eye_ring'].data]); u = np.array([d.value for d in me.attributes['eye_u'].data])
col = me.color_attributes['ref_color']; Ccol = np.array([tuple(d.color) for d in col.data])
me.calc_loop_triangles() if hasattr(me, 'calc_loop_triangles') else None
Nrm = np.array([tuple(v.normal) for v in me.vertices])
polys = [list(p.vertices) for p in me.polygons]
bvh = BVHTree.FromPolygons([tuple(p) for p in X], polys)
E = bpy.data.objects.get('eyes')
bvhE = BVHTree.FromPolygons([tuple(E.matrix_world @ v.co) for v in E.data.vertices], [list(p.vertices) for p in E.data.polygons]) if E else None
view = np.array([0.0, -1.0, 0.0])
def visible(i):
    p = X[i]
    if Nrm[i] @ view < 0.15: return False
    o = Vector(tuple(p + view * 0.5)); d = Vector(tuple(-view))
    for b in (bvh, bvhE):
        if b is None: continue
        h = b.ray_cast(o, d)
        if h[0] is not None and h[3] < 0.5 - 0.0004: return False
    return True
K = int(np.abs(ring).max()) - 2
M = int(round(1.0 / np.min(np.diff(np.unique(np.round(u[ring != 0], 6))))))
ul = u[ring != 0]; REG = M <= 1024 and float(np.abs(ul * M - np.rint(ul * M)).max()) < 1e-3
if not REG: M = 64                                      # irregular rings (loop_organs.py): columns = 64 bins of u
cols = np.rint(u * M).astype(int) % M
rep = {'lid_skin': 0, 'lash_kept': 0, 'edge': 0}
lum = lambda c: float(c[:3] @ np.array([0.3, 0.59, 0.11]))
for sg in (1, -1):
    Sc = np.full((M, 4), np.nan)
    for c in range(M):
        sk = np.where((np.sign(ring) == sg) & (cols == c) & np.isin(np.abs(ring), (2, 3)))[0]
        if len(sk): Sc[c] = np.median(Ccol[sk], 0)
    good = ~np.isnan(Sc[:, 0])
    if REG: Sc[~good] = np.nanmedian(Sc[good], 0)
    else:                                              # empty bins: periodic interpolation between the filled ones
        g = np.where(good)[0]
        for j in range(4): Sc[~good, j] = np.interp(np.where(~good)[0], np.r_[g - M, g, g + M], np.tile(Sc[g, j], 3))
    for _ in range(6): Sc = (np.roll(Sc, 1, 0) + 2 * Sc + np.roll(Sc, -1, 0)) / 4      # neighbouring columns alike
    for c in range(M):
        ids = np.where((np.sign(ring) == sg) & (cols == c) & (np.abs(ring) >= 2))[0]
        S = Sc[c]; upper = c < M // 2
        for i in ids:
            k = abs(ring[i])
            if 3 < k <= K - 2: Ccol[i] = S; rep['lid_skin'] += 1
            elif K - 2 < k <= K:                           # margin rows: keep a dark lash line, else skin
                if lum(Ccol[i]) < 0.6 * lum(S): rep['lash_kept'] += 1
                else: Ccol[i] = np.r_[S[:3] * 0.92, 1.0]; rep['lid_skin'] += 1
            elif k > K: Ccol[i] = np.r_[S[:3] * (0.5 if upper else 0.7), 1.0]; rep['edge'] += 1
col.data.foreach_set('color', Ccol.ravel()); me.update()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('LIDCOL', json.dumps(rep))
