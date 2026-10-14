"""Transfer a Tripo segmentation result (made from our uploaded GLB) back onto the source quad head.

* geometry fidelity: distance of every output vertex to the source surface after undoing the orientation and bbox fit
* each source face takes the part of the nearest output face centre -> material slot per part + vertex groups SEG_<n>
* symmetry agreement: for each part P, its mirror image should land in one part Q (itself, or its L/R twin);
  agreement = share of faces whose mirror face lies in Q(P) (area weighted)
Usage: blender --background <source.blend> --python transfer_seg.py -- <job> <out.blend>
"""
import bpy, sys, os, json, math, colorsys
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
job, OUT = sys.argv[sys.argv.index("--") + 1:][:2]
OUT = os.path.abspath(OUT)
KEEP = ["Body", "Eye.L", "Eye.R", "TeethUpper", "TeethLower", "Tongue", "MouthLower"]
src = [bpy.data.objects[n] for n in KEEP]
for o in src:
    o.data.transform(o.matrix_basis); o.matrix_basis = Matrix()
    if o.data.shape_keys: o.shape_key_clear()
# source face table (all objects)
SC, SO, SI, SA = [], [], [], []
for oi, o in enumerate(src):
    for pg in o.data.polygons: SC.append(pg.center[:]); SO.append(oi); SI.append(pg.index); SA.append(pg.area)
SC = np.array(SC); SO = np.array(SO); SA = np.array(SA)
SV = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in src])
SF, off = [], 0
for o in src:
    SF += [tuple(i + off for i in pg.vertices) for pg in o.data.polygons]; off += len(o.data.vertices)
SBVH = BVHTree.FromPolygons([tuple(p) for p in SV], SF)
# import result into a scratch collection
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "tripo", job, "model_url.glb"))
new = [o for o in bpy.data.objects if o not in before]
parts = [o for o in new if o.type == 'MESH']
R = Matrix.Rotation(math.radians(-90), 4, 'Z')
for o in parts:
    o.data.transform(R @ o.matrix_world); o.parent = None; o.matrix_world = Matrix()
P = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in parts])
lo, hi = P.min(0), P.max(0); llo, lhi = SV.min(0), SV.max(0)
s = float(np.median((lhi - llo) / (hi - lo))); t = (llo + lhi) / 2 - s * (lo + hi) / 2
OC, OP = [], []
dists = []
parts.sort(key=lambda o: -len(o.data.polygons))
for pi, o in enumerate(parts):
    o.data.transform(Matrix.Translation(Vector(t)) @ Matrix.Scale(s, 4))
    for v in list(o.data.vertices)[::3]:
        dists.append((SBVH.find_nearest(v.co)[0] - v.co).length)
    for pg in o.data.polygons: OC.append(pg.center[:]); OP.append(pi)
OP = np.array(OP)
dists = np.array(dists) * 1000
kd = KDTree(len(OC))
for i, c in enumerate(OC): kd.insert(c, i)
kd.balance()
lab = np.array([OP[kd.find(Vector(c))[1]] for c in SC])
# mirror agreement
mir = np.array([OP[kd.find(Vector((-c[0], c[1], c[2])))[1]] for c in SC])
agree_w, tot_w, pair = 0.0, 0.0, {}
for p in np.unique(lab):
    m = lab == p
    q, cnt = np.unique(mir[m], return_counts=True); qbest = q[np.argmax(cnt)]; pair[int(p)] = int(qbest)
    agree_w += SA[m & (mir == qbest)].sum(); tot_w += SA[m].sum()
# body-only agreement (the face skin is what matters for rigging)
mb = SO == 0
agree_b = sum(SA[mb & (lab == p) & (mir == pair[int(p)])].sum() for p in np.unique(lab[mb])) / SA[mb].sum()
rep = {"job": job, "output_parts": len(parts), "parts_on_source": int(len(np.unique(lab))),
       "geom_dist_mm": {"median": round(float(np.median(dists)), 3), "p99": round(float(np.percentile(dists, 99)), 3), "max": round(float(dists.max()), 3)},
       "mirror_agreement_all": round(agree_w / tot_w, 3), "mirror_agreement_body": round(float(agree_b), 3),
       "body_parts": int(len(np.unique(lab[mb]))), "body_parts_ge1pct": int(sum(SA[mb & (lab == p)].sum() > 0.01 * SA[mb].sum() for p in np.unique(lab[mb])))}
for o in new: bpy.data.objects.remove(o)
# write parts onto the source objects
pal = {}
def mat(p):
    if p not in pal:
        h = (p * 0.618034) % 1.0
        m = bpy.data.materials.new(f"SEG_{p:03d}"); m.diffuse_color = (*colorsys.hsv_to_rgb(h, 0.65, 0.9), 1); pal[p] = m
    return pal[p]
for oi, o in enumerate(src):
    sel = SO == oi; ids = lab[sel]
    o.data.materials.clear()
    uniq = sorted(set(ids.tolist()))
    for p in uniq: o.data.materials.append(mat(p))
    idx = {p: k for k, p in enumerate(uniq)}
    for pg, p in zip(o.data.polygons, ids): pg.material_index = idx[p]
    if oi == 0:
        for p in uniq:
            vg = o.vertex_groups.new(name=f"SEG_{p:03d}")
            vs = sorted({v for pg, q in zip(o.data.polygons, ids) if q == p for v in pg.vertices})
            vg.add(vs, 1.0, 'REPLACE')
bpy.context.scene["seg_job"] = job
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("TRANSFER", json.dumps(rep))
