"""Is the caruncle hidden when the eye is closed? Blink t (eyeBlink<S> = t, eyeBlinkMid<S> = 4 t (1 - t) on 'face'; the
caruncle's own eyeBlink<S> = t): orthographic rays from the front (0, 1, 0) and the 3/4 view (-0.5, 0.86, 0) (left
eye; mirrored for the right) through a 0.1 mm grid over the caruncle's projected area; a ray whose first hit (face,
eyes, caruncle) is the caruncle counts as a visible sample. Also the caruncle faces with any visible sample.
Usage: blender -b <prev.blend> -P caruncle_qa.py -- <out.json> [t ...]   (default t = 0, 0.5, 1)
"""
import bpy, sys, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index('--') + 1:]; OUT = a[0]; TS = [float(x) for x in a[1:]] or [0.0, 0.5, 1.0]
face = bpy.data.objects['face']; eyes = bpy.data.objects.get('eyes'); car = bpy.data.objects.get('caruncle')
out = {}
if car is None:
    json.dump({'caruncle': None}, open(OUT, 'w')); print('CARQA', json.dumps({'caruncle': None})); sys.exit(0)
if face.data.shape_keys and face.data.shape_keys.animation_data: face.data.shape_keys.animation_data_clear()


def setk(obj, name, v):
    if obj.data.shape_keys and obj.data.shape_keys.key_blocks.get(name): obj.data.shape_keys.key_blocks[name].value = v


def mesh(obj):
    dg = bpy.context.evaluated_depsgraph_get(); m = obj.evaluated_get(dg).to_mesh()
    V = np.array([tuple(v.co) for v in m.vertices]); m.calc_loop_triangles(); T = np.array([tuple(t.vertices) for t in m.loop_triangles])
    P = np.array([p.index for p in m.loop_triangles]) if False else np.array([t.polygon_index for t in m.loop_triangles])
    obj.evaluated_get(dg).to_mesh_clear(); return V, T, P


for t in TS:
    for S in ('Left',):
        for kb in (face.data.shape_keys.key_blocks[1:] if face.data.shape_keys else []): kb.value = 0.0
        setk(face, 'eyeBlink' + S, t); setk(face, 'eyeBlinkMid' + S, 4 * t * (1 - t)); setk(car, 'eyeBlink' + S, t)
        bpy.context.view_layer.update()
        parts = [mesh(o) for o in (face, eyes, car) if o is not None]
        V = np.vstack([p[0] for p in parts]); off = np.cumsum([0] + [len(p[0]) for p in parts])
        T = np.vstack([p[1] + off[i] for i, p in enumerate(parts)]); owner = np.concatenate([np.full(len(p[1]), i) for i, p in enumerate(parts)])
        cpoly = parts[-1][2]
        bvh = BVHTree.FromPolygons([tuple(p) for p in V], [tuple(tr) for tr in T])
        CV = parts[-1][0]; side = CV[:, 0] > 0
        res = {}
        for vn, d in (('front', (0, 1, 0)), ('34', (-0.5, 0.86, 0))):
            d = np.array(d, float); d /= np.linalg.norm(d); e1 = np.cross(d, [0, 0, 1.0]); e1 /= np.linalg.norm(e1); e2 = np.cross(e1, d)
            Q = CV[side]; U_, W_ = Q @ e1, Q @ e2; hits = 0; tot = 0; faces = set()
            for x in np.arange(U_.min() - 0.0003, U_.max() + 0.0003, 0.0001):
                for z in np.arange(W_.min() - 0.0003, W_.max() + 0.0003, 0.0001):
                    o = e1 * x + e2 * z - d * 1.0; h = bvh.ray_cast(Vector(tuple(o)), Vector(tuple(d)))
                    if h[0] is None: continue
                    tot += 1
                    if owner[h[2]] == len(parts) - 1: hits += 1; faces.add(int(cpoly[h[2] - off[-2] if False else h[2] - len(np.vstack([p[1] for p in parts[:-1]]))]))
            res[vn] = {'visible_samples': hits, 'visible_mm2': round(hits * 0.01, 3), 'visible_faces': len(faces)}
        out['t%.2f' % t] = res
json.dump(out, open(OUT, 'w'), indent=1)
print('CARQA', json.dumps(out))
