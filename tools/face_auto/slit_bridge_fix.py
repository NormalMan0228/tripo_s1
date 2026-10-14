"""Finish the lip slit where loop_organs left the lips joined: delete the faces that hold vertices of both lips.

loop_organs rips the mouth along an existing edge path. Where that path steps like a staircase near a corner (P f09, about
a quarter mouth width in from each corner), a few faces just off the slit keep vertices of the upper lip (mouth_u in
(0, 0.5)) and of the lower lip (mouth_u in (0.5, 1)) together, so the lips stay joined there: on jawOpen a strip of lower
lip rises to the upper lip and the opening pinches shut short of the corner. Those faces (skin and lip roll, rings
1..slit+2, between the corners; any face touching the corner column, mouth_u 0 / 0.5, is kept) are deleted with the edges that then join
the two lips; no vertex is removed or moved, so indices, attributes and the rest shape stay exactly as they were
(the closed lips hide the hairline gap at rest).
Usage: blender -b <eyes.blend> -P slit_bridge_fix.py -- <eyes_mouth.json> <out.blend>   (in place is fine)
Prints BRIDGE {faces, edges, x_mm}; writes <out>_bridge.json.
"""
import bpy, bmesh, sys, os, json
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]; MJ, OUT = a[0], os.path.abspath(a[1])
SL = int(json.load(open(MJ)).get('rings', 12))
F = bpy.data.objects['face']; me = F.data
rg = np.array([d.value for d in me.attributes['mouth_ring'].data]); uu = np.array([d.value for d in me.attributes['mouth_u'].data])
corner = np.minimum(uu % 0.5, 0.5 - uu % 0.5) < 1e-6
side = np.where(corner | (rg <= 0), 0, np.where((uu % 1.0) < 0.5, 1, -1))
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table()
sl = np.where(rg == SL)[0]; X = np.array([tuple(v.co) for v in me.vertices])
xc = float(np.abs(X[sl[corner[sl]], 0]).max()) if corner[sl].any() else float(np.abs(X[sl, 0]).max())
# only between the mouth corners: beyond a corner the upper and lower BFS rings meet along a seam in the cheek skin
# (faces there carry both labels and are ordinary skin)
bad = []
for f in bm.faces:
    if abs(f.calc_center_median().x) >= 0.97 * xc: continue
    vs = [v.index for v in f.verts]
    if any(corner[i] for i in vs) or any(not (1 <= rg[i] <= SL + 2) for i in vs): continue
    s = {int(side[i]) for i in vs}
    if 1 in s and -1 in s: bad.append(f)
xs = sorted({round(abs(f.calc_center_median().x) * 1000, 1) for f in bad})
ed = set()
for f in bad:
    for e in f.edges:
        a_, b_ = e.verts
        if side[a_.index] * side[b_.index] == -1 and all(g in bad for g in e.link_faces): ed.add(e)
bmesh.ops.delete(bm, geom=bad, context='FACES_ONLY')
ed = [e for e in ed if e.is_valid and not e.link_faces]
if ed: bmesh.ops.delete(bm, geom=ed, context='EDGES')
nv = len(bm.verts); bm.to_mesh(me); bm.free(); me.update()
assert nv == len(rg), 'vertex count changed'
qa = {'faces_deleted': len(bad), 'edges_deleted': len(ed), 'x_mm': xs, 'corner_x_mm': round(xc * 1000, 2), 'slit_ring': SL}
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(qa, open(os.path.splitext(OUT)[0] + '_bridge.json', 'w'), indent=0)
print('BRIDGE', json.dumps(qa))
