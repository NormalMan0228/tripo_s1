"""Mouth components for the clean closed head from the mask-segmented open-mouth HD (segref_hdopen).

* parts are mapped into the closed head's frame with the similarity ICP (open_to_closed.json)
* each open shell -> closed clean mesh: merge, drop islands, solidify (inward), voxel remesh, Taubin smooth, decimate,
  then exact symmetrize
* lower parts (lower teeth + gum, tongue) rotate about the jaw pivot toward closing until the lower teeth just clear the
  upper teeth (bite gap BITE_DEG)
* containment: every component vertex must be inside the head surface (ray parity); report counts
Usage: blender --background head_seam.blend --python hd_components.py -- <parts.blend> <icp.json> <out.blend>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--") + 1:]
PARTS, ICP, OUT = [os.path.abspath(x) for x in a[:3]]
PIVOT = Vector((0.0, float(os.environ.get("PIV_Y", -0.03)), float(os.environ.get("PIV_Z", 0.53))))
BITE_DEG = float(os.environ.get("BITE_DEG", 0.5))
SPEC = {  # name: (source parts, solidify thickness, voxel, target faces)
    "TeethUpper": (["part_008", "part_016"], 0.004, 0.0007, 24000),
    "TeethLower": (["part_007"], 0.004, 0.0007, 24000),
    "Tongue": (["part_006"], 0.010, 0.0010, 16000),
}
rep = {}
M = Matrix(json.load(open(ICP))["matrix"])
head = bpy.data.objects["Head"]
with bpy.data.libraries.load(PARTS) as (df, dt):
    dt.objects = sorted({p for v in SPEC.values() for p in v[0]})
src = {o.name: o for o in dt.objects}


def taubin(me, it=10):
    X = np.array([v.co[:] for v in me.vertices]); E = np.array([e.vertices[:] for e in me.edges]); n = len(X)
    deg = np.maximum(np.bincount(E.ravel(), minlength=n), 1)
    def lap(X):
        acc = np.zeros_like(X); np.add.at(acc, E[:, 0], X[E[:, 1]]); np.add.at(acc, E[:, 1], X[E[:, 0]]); return acc / deg[:, None] - X
    for _ in range(it):
        X = X + 0.5 * lap(X); X = X - 0.53 * lap(X)
    me.vertices.foreach_set("co", X.ravel()); me.update()


def apply_mods(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)


objs = {}
for name, (parts, thick, voxel, target) in SPEC.items():
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    for p in parts:
        t = src[p].data.copy(); t.transform(M @ src[p].matrix_world); bm.from_mesh(t); bpy.data.meshes.remove(t)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    # drop small islands
    bm.verts.ensure_lookup_table(); comp = {}; cid = 0
    for v in bm.verts:
        if v.index in comp: continue
        st = [v]; comp[v.index] = cid
        while st:
            u = st.pop()
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in comp: comp[w.index] = cid; st.append(w)
        cid += 1
    sizes = np.bincount(list(comp.values()))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if sizes[comp[v.index]] < 0.02 * sizes.max()], context='VERTS')
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    sol = o.modifiers.new("sol", 'SOLIDIFY'); sol.thickness = thick; sol.offset = -1; sol.use_even_offset = True
    rm = o.modifiers.new("rm", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = voxel; rm.use_smooth_shade = True
    apply_mods(o)
    # keep the largest closed piece
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); comp = {}; cid = 0
    for v in bm.verts:
        if v.index in comp: continue
        st = [v]; comp[v.index] = cid
        while st:
            u = st.pop()
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in comp: comp[w.index] = cid; st.append(w)
        cid += 1
    sizes = np.bincount(list(comp.values())); keep = int(np.argmax(sizes))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if comp[v.index] != keep], context='VERTS'); bm.to_mesh(me); bm.free()
    taubin(me, 12)
    dec = o.modifiers.new("dec", 'DECIMATE'); dec.ratio = min(1.0, target / max(1, len(me.polygons))); dec.use_symmetry = True; dec.symmetry_axis = 'X'
    apply_mods(o)
    bpy.context.view_layer.objects.active = o
    for ob in bpy.context.selected_objects: ob.select_set(False)
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.symmetrize(direction='POSITIVE_X', threshold=1e-5); bpy.ops.mesh.remove_doubles(threshold=1e-6)
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in me.polygons: p.use_smooth = True
    objs[name] = o
    rep[name] = {"faces": len(me.polygons)}
for p in dt.objects: bpy.data.objects.remove(p)


def bvh(o, P=None):
    P = np.array([v.co[:] for v in o.data.vertices]) if P is None else P
    return BVHTree.FromPolygons([tuple(p) for p in P], [tuple(p.vertices) for p in o.data.polygons])


def rot(P, deg):
    R = np.array(Matrix.Rotation(math.radians(deg), 3, 'X')); c = np.array(PIVOT); return (P - c) @ R.T + c


# jaw closing: negative X rotation lifts the chin (front is -Y); find the first angle where the lower teeth touch
TU = bvh(objs["TeethUpper"])
PL = {k: np.array([v.co[:] for v in objs[k].data.vertices]) for k in ("TeethLower", "Tongue")}
close = 0.0
for dg in np.arange(0, 35.01, 0.25):
    if TU.overlap(bvh(objs["TeethLower"], rot(PL["TeethLower"], -dg))):
        close = max(0.0, dg - 0.25 - BITE_DEG); break
else:
    close = 35.0
for k in ("TeethLower", "Tongue"):
    objs[k].data.vertices.foreach_set("co", rot(PL[k], -close).ravel()); objs[k].data.update()
rep["jaw_close_deg"] = close
# tongue must not cut the teeth
rep["tongue_x_teeth_overlap"] = {k: len(bvh(objs["Tongue"]).overlap(bvh(objs[k]))) for k in ("TeethUpper", "TeethLower")}

# containment in the head (ray parity along +Y and +Z, both must say inside)
HX = np.array([v.co[:] for v in head.data.vertices])
HT = BVHTree.FromPolygons([tuple(p) for p in HX], [tuple(p.vertices) for p in head.data.polygons])


def inside(p):
    votes = 0
    for d in (Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((0.3, 0.2, 0.93)).normalized()):
        c = 0; o = Vector(p)
        while True:
            h = HT.ray_cast(o, d, 5)
            if h[0] is None: break
            c += 1; o = h[0] + d * 1e-6
        votes += c % 2
    return votes >= 2


for k, o in objs.items():
    P = np.array([v.co[:] for v in o.data.vertices])
    out = [i for i in range(0, len(P), 3) if not inside(P[i])]
    rep[k]["outside_head_samples"] = len(out); rep[k]["samples"] = len(range(0, len(P), 3))
    if out: rep[k]["outside_example"] = P[out[0]].round(4).tolist()
    rep[k]["x_head_overlap"] = len(HT.overlap(bvh(o)))
    mat = bpy.data.materials.new(f"M_{k}"); mat.diffuse_color = {"TeethUpper": (1, 1, 0.92, 1), "TeethLower": (0.95, 0.95, 0.88, 1), "Tongue": (0.85, 0.35, 0.4, 1)}[k]
    o.data.materials.append(mat)
head["jaw_pivot"] = list(PIVOT)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("COMP", json.dumps(rep))
