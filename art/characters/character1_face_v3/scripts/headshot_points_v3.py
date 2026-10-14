"""Complete and symmetrise the Headshot 3 35-point alignment for the v3 Tripo head.
CC's auto detection gives points 1-24; this adds 25-35 from the mesh (ears, crown, back, under-chin, lip seam),
re-places the eye corners and lids (7-14) on the real lid rim,
mirrors left/right pairs, puts midline points on x=0 and writes [Target] (F = triangle index, all-tri mesh).
Usage: blender -b --factory-startup -P headshot_points_v3.py -- <auto.ini> <out.ini> [meta.json]
"""
import bpy, re, sys, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], a[1]
FBX = r"C:\lsm26\triphthonS1\art\characters\character1_face_v3\hd\character1_v3_head_headshot.fbx"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX)
o = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mw = o.matrix_world
V = np.array([tuple(mw @ v.co) for v in o.data.vertices])
P = [list(p.vertices) for p in o.data.polygons]
assert all(len(p) == 3 for p in P)
bvh = BVHTree.FromPolygons([Vector(v) for v in V], P)
raw = open(SRC, encoding='utf-8-sig').read()
head, tgt = raw.split('[Target]')
F = {int(k): int(v) for k, v in re.findall(r'\nF(\d+) = (\d+)', tgt)}
B = {int(k): [float(x) for x in v.split()] for k, v in re.findall(r'\nB(\d+) = "([^"]+)"', tgt)}
X = {k: sum(V[P[F[k]][i]] * B[k][i] for i in range(3)) for k in F}

def ray(org, d):
    loc, n, idx, dist = bvh.ray_cast(Vector(org), Vector(d).normalized())
    assert loc is not None, (org, d)
    return np.array(loc)

# ears: (y, z) in metres picked on the side view; ray from outside toward the head
EAR = {25: (0.007, 0.233), 26: (0.0025, 0.186), 27: (0.034, 0.245)}
for k, (y, z) in EAR.items():
    X[k] = ray((-0.4, y, z), (1, 0, 0))          # character right = -X
    X[k + 3] = ray((0.4, y, z), (-1, 0, 0))
# eyes: auto detection squeezes 7-10/11-14 into the upper half of the big cartoon eye, which leaves a ledge
# under the CC eyeball; use the real lid rim read off a front close-up (x, z for the character-right eye)
EYE = {7: (-0.0703, 0.2290), 8: (-0.0480, 0.2398), 9: (-0.0258, 0.2153), 10: (-0.0480, 0.2133)}
MIR = {7: 13, 8: 12, 9: 11, 10: 14}
for k, (x, z) in EYE.items():
    X[k] = ray((x, -0.4, z), (0, 1, 0))
    X[MIR[k]] = ray((-x, -0.4, z), (0, 1, 0))
mid = np.abs(V[:, 0]) < 0.003
X[31] = V[mid][np.argmax(V[mid][:, 2])]
X[32] = ray((0, 0.4, 0.235), (0, -1, 0))
# under-chin corner: midplane rays from inside the head, max distance below the chin->neck chord
c0 = np.array([0, 0.0, 0.17])
hits = [ray(c0, (0, -np.sin(t), -np.cos(t))) for t in np.radians(np.arange(0, 70, 0.5))]
hits = np.array(hits)
chin = X[24]; neck = hits[np.argmin(np.abs(hits[:, 2] - 0.09) + 10 * (hits[:, 1] > 0))]
sel = hits[(hits[:, 2] < chin[2]) & (hits[:, 2] > neck[2]) & (hits[:, 1] < 0)]
ab = (neck - chin)[1:]; ab /= np.linalg.norm(ab)
dist = [abs(ab[0] * (p - chin)[2] - ab[1] * (p - chin)[1]) for p in sel]
X[33] = sel[int(np.argmax(dist))]
# lip seam: deepest midline groove near mouth-corner height; 23 (auto lands in the chin crease) moves to the
# lower-lip bottom edge, halfway between the lower-lip bulge and the groove under it
def front(z): return ray((0, -0.4, z), (0, 1, 0))
zc = (X[20][2] + X[22][2]) / 2
zs = np.arange(zc - 0.003, X[21][2] - 0.002, 0.0002)
fr = np.array([front(z) for z in zs]); seam = fr[np.argmax(fr[:, 1])]
lo = np.array([front(z) for z in np.arange(seam[2] - 0.025, seam[2] - 0.002, 0.0002)])
bulge = lo[(lo[:, 2] > seam[2] - 0.012)]; bulge = bulge[np.argmin(bulge[:, 1])]
sulc = lo[(lo[:, 2] < bulge[2])]; sulc = sulc[np.argmax(sulc[:, 1])]
X[23] = front((bulge[2] + sulc[2]) / 2)
X[34] = front(seam[2] + 0.0008)
X[35] = front(seam[2] - 0.0008)
print('lower lip bulge z %.4f sulcus z %.4f' % (bulge[2], sulc[2]))
print('seam z %.4f y %.4f | chin-neck corner %s' % (seam[2], seam[1], np.round(X[33] * 100, 2)))

M = np.array([-1, 1, 1])
pairs = [(1, 6), (2, 5), (3, 4), (7, 13), (8, 12), (9, 11), (10, 14), (17, 18), (20, 22), (25, 28), (26, 29), (27, 30)]
mids = [15, 16, 19, 21, 23, 24, 31, 32, 33, 34, 35]
T = dict(X)
for p, q in pairs:
    if X[p][0] > X[q][0]: print('WARN pair order', p, q)
    avg = (X[p] + X[q] * M) / 2; T[p] = avg; T[q] = avg * M
for k in mids: T[k] = X[k] * np.array([0, 1, 1])

def bary(p, tri):
    a, b, c = [V[i] for i in tri]; v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01; v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
    bb = np.clip([1 - v - w, v, w], 0, 1); return bb / bb.sum()
lines = ['PointCount = 35']; final = {}
for k in range(1, 36):
    loc, n, idx, d = bvh.find_nearest(Vector(T[k]))
    bb = bary(np.array(loc), P[idx]); final[k] = sum(V[P[idx][i]] * bb[i] for i in range(3))
    lines += ['F%d = %d' % (k, idx), 'B%d = "%s"' % (k, ' '.join('%.6f' % x for x in bb))]
    print('pt %2d cm %s moved %.1f mm' % (k, np.round(final[k] * 100, 2), np.linalg.norm(final[k] - X[k]) * 1000))
open(OUT, 'w', encoding='utf-8-sig', newline='\n').write(head + '[Target]\n' + '\n'.join(lines) + '\n')
if len(a) > 2:
    m = json.load(open(a[2])); m['points'] = {str(k): v.tolist() for k, v in final.items()}; json.dump(m, open(a[2], 'w'))
print('wrote', OUT)
