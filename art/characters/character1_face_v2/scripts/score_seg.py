"""Score + render Tripo segmentation outputs against the geometric part labels from seg_masks.py.

For each job: import tripo/<job>/model_url.glb, rotate Tripo-native (+X front) to -Y front, fit the bbox onto the labelled
head (seg/<ref>_facelabels.npz), label every output face by its nearest labelled face centre, then per output part report
faces / majority label / purity.  Renders parts in distinct colours (front, 3/4, side, close-up of the face).
Usage: blender --background --python score_seg.py -- <job>:<open|closed> [...]
Writes previews/segref_<job>.png and seg/score_<job>.json, prints a summary line per job.
"""
import bpy, sys, os, json, math, colorsys
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[sys.argv.index("--") + 1:]
SIG = 30          # parts below this many faces count as fragments


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def colour(i):
    h = (i * 0.618034) % 1.0; s = 0.55 + 0.4 * ((i * 7) % 3) / 2; v = 0.95 - 0.25 * ((i * 5) % 2)
    return (*colorsys.hsv_to_rgb(h, s, v), 1)


def render(objs, path, views):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_cavity = False
    sc.render.resolution_x, sc.render.resolution_y = 640, 640
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new("w"); w.color = (0.05, 0.05, 0.05); sc.world = w
    cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'
    cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
    tiles = []
    for k, (az, el, cz, osc) in enumerate(views):
        cd.ortho_scale = osc
        d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)), -math.cos(math.radians(az)) * math.cos(math.radians(el)),
                    math.sin(math.radians(el))))
        cam.location = Vector((0, 0, cz)) + d * 3
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = path.replace(".png", f"_v{k}.png")
        bpy.ops.render.render(write_still=True); tiles.append(sc.render.filepath)
    return tiles


summary = {}
for spec in args:
    job, ref = spec.split(":")
    reset()
    L = np.load(os.path.join(HERE, "seg", f"{ref}_facelabels.npz")); LC, LL = L["c"], L["l"]
    bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "tripo", job, "model_url.glb"))
    objs = [o for o in bpy.data.objects if o.type == 'MESH']
    R = Matrix.Rotation(math.radians(-90), 4, 'Z')
    for o in objs:
        o.data.transform(R @ o.matrix_world); o.parent = None; o.matrix_world = Matrix()
    for o in [o for o in bpy.data.objects if o.type != 'MESH']: bpy.data.objects.remove(o)
    P = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in objs])
    lo, hi = P.min(0), P.max(0); llo, lhi = LC.min(0), LC.max(0)
    s = float(np.median((lhi - llo) / (hi - lo))); t = (llo + lhi) / 2 - s * (lo + hi) / 2
    for o in objs:
        o.data.transform(Matrix.Translation(Vector(t)) @ Matrix.Scale(s, 4))
    kd = KDTree(len(LC))
    for i, c in enumerate(LC): kd.insert(Vector(c.tolist()), i)
    kd.balance()
    parts = []
    for i, o in enumerate(sorted(objs, key=lambda o: -len(o.data.polygons))):
        labs = [LL[kd.find(pg.center)[1]] for pg in o.data.polygons]
        u, c = np.unique(labs, return_counts=True); order = np.argsort(-c)
        parts.append({"name": o.name, "faces": len(labs), "major": str(u[order[0]]), "purity": float(c[order[0]] / len(labs)),
                      "mix": {str(u[k]): int(c[k]) for k in order[:4]},
                      "centre": [round(x, 3) for x in np.mean([pg.center[:] for pg in o.data.polygons], 0)]})
        o.color = colour(i)
    tot = sum(p["faces"] for p in parts)
    sig = [p for p in parts if p["faces"] >= SIG]
    # per label: how many significant parts carry it as majority, and share of the label held by its best part
    lab_tot = {}
    for p in parts:
        for l, n in p["mix"].items(): lab_tot[l] = lab_tot.get(l, 0) + n
    per_label = {}
    for l in sorted(lab_tot):
        best = max((p["mix"].get(l, 0) for p in parts), default=0)
        per_label[l] = {"parts_majority": sum(1 for p in sig if p["major"] == l), "best_part_share": round(best / max(lab_tot[l], 1), 3)}
    res = {"job": job, "parts": len(parts), "significant_parts": len(sig), "fragment_faces": tot - sum(p["faces"] for p in sig),
           "faces": tot, "weighted_purity": round(sum(p["purity"] * p["faces"] for p in parts) / tot, 3), "per_label": per_label,
           "parts_detail": parts[:60]}
    json.dump(res, open(os.path.join(HERE, "seg", f"score_{job}.json"), "w"), indent=1)
    out = os.path.join(HERE, "previews", f"segref_{job}.png")
    render(objs, out, [(0, 0, 0.5, 1.15), (35, 8, 0.5, 1.15), (90, 0, 0.5, 1.15), (0, 0, 0.55, 0.55), (25, -20, 0.45, 0.5)])
    summary[job] = {k: res[k] for k in ("parts", "significant_parts", "fragment_faces", "faces", "weighted_purity")}
    print("SCORE", job, json.dumps(summary[job]), "| sig parts:",
          "; ".join(f'{p["major"]}:{p["faces"]}:{p["purity"]:.2f}' for p in sig[:40]))
