"""Import the Tripo candidates, normalise them into character1's frame and inventory their structure.

Each candidate is scaled/translated so its bounding box matches the original character1 bust
(height 1.0, bottom at z=0, centred in x, face toward -Y). Objects are joined per candidate into a collection.
Writes candidates.blend and candidates_inventory.json.
Usage: blender --background --python import_candidates.py -- <tripo_dir> <out_dir>
"""
import bpy, bmesh, sys, os, json, glob
import numpy as np
from mathutils import Vector, Matrix

a = sys.argv[sys.argv.index("--") + 1:]
TD, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
bpy.ops.wm.read_factory_settings(use_empty=True)
inv = {}
for job in sorted(os.listdir(TD)):
    files = glob.glob(os.path.join(TD, job, "model_url.*"))
    if not files:
        continue
    f = files[0]
    before = set(bpy.data.objects)
    if f.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=f)
    else:
        bpy.ops.import_scene.fbx(filepath=f)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    coll = bpy.data.collections.new(job); bpy.context.scene.collection.children.link(coll)
    for o in new:
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
    # apply transforms into mesh data (bake world matrix), clear parents
    for o in meshes:
        mw = o.matrix_world.copy(); o.parent = None; o.data.transform(mw); o.matrix_world = Matrix()
    for o in new:
        if o.type != 'MESH':
            bpy.data.objects.remove(o)
    pts = np.concatenate([[v.co[:] for v in o.data.vertices] for o in meshes])
    mn, mx = pts.min(0), pts.max(0)
    # detect up axis: the tallest extent among y/z should be the bust height; Tripo GLB is Y-up but importer converts to Z-up
    h = mx[2] - mn[2]
    s = 1.0 / h
    T = Matrix.Translation((-(mn[0] + mx[0]) / 2 * s, -(mn[1] + mx[1]) / 2 * s, -mn[2] * s)) @ Matrix.Scale(s, 4)
    for o in meshes:
        o.data.transform(T)
    # Tripo output faces +X after import (FBX and GLB alike; verified from the separate eyeball parts)
    # orientation: put the two eyeball components (2nd/3rd largest pieces, similar size) at -Y; default -90 deg
    angle = -np.pi / 2
    allp = np.concatenate([[v.co[:] for v in o.data.vertices] for o in meshes])
    bm0 = bmesh.new()
    for o in meshes:
        bm0.from_mesh(o.data)
    bm0.verts.ensure_lookup_table()
    par = list(range(len(bm0.verts)))
    def fnd(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for e in bm0.edges:
        u, w = fnd(e.verts[0].index), fnd(e.verts[1].index)
        if u != w: par[u] = w
    groups = {}
    for v in bm0.verts:
        groups.setdefault(fnd(v.index), []).append(v.index)
    cos0 = np.array([v.co[:] for v in bm0.verts]); bm0.free()
    gl = sorted(groups.values(), key=len, reverse=True)
    if len(gl) >= 3 and 0.7 < len(gl[1]) / len(gl[2]) < 1.4 and len(gl[1]) > 200:
        ec = (cos0[gl[1]].mean(0) + cos0[gl[2]].mean(0)) / 2 - cos0[gl[0]].mean(0)
        angle = -np.pi / 2 - np.arctan2(ec[1], ec[0])
    R = Matrix.Rotation(angle, 4, "Z")
    for o in meshes:
        o.data.transform(R)
    pts = np.concatenate([[v.co[:] for v in o.data.vertices] for o in meshes])
    mn, mx = pts.min(0), pts.max(0)
    for o in meshes:
        o.data.transform(Matrix.Translation((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2])))
    info = {"file": os.path.basename(f), "objects": []}
    for o in meshes:
        o.name = f"{job}:{o.name}"
        me = o.data
        bm = bmesh.new(); bm.from_mesh(me)
        sides = {}
        for fc in bm.faces:
            k = min(len(fc.verts), 5); sides[k] = sides.get(k, 0) + 1
        parent = list(range(len(bm.verts)))
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for e in bm.edges:
            u, w = find(e.verts[0].index), find(e.verts[1].index)
            if u != w: parent[u] = w
        comps = {}
        for v in bm.verts:
            comps.setdefault(find(v.index), []).append(v.index)
        co = np.array([v.co[:] for v in me.vertices])
        clist = sorted(comps.values(), key=len, reverse=True)
        info["objects"].append(dict(name=o.name, verts=len(me.vertices), faces=len(me.polygons), sides=sides,
            boundary=sum(e.is_boundary for e in bm.edges), nonmanifold=sum((not e.is_manifold) and not e.is_boundary for e in bm.edges),
            components=len(comps), uv=[u.name for u in me.uv_layers], materials=[m.name for m in me.materials if m],
            comp_top=[dict(n=len(c), centroid=co[c].mean(0).round(3).tolist(), mn=co[c].min(0).round(3).tolist(), mx=co[c].max(0).round(3).tolist()) for c in clist[:12]]))
        bm.free()
    inv[job] = info
    print("CAND", job, [(o["name"], o["verts"], o["faces"], o["sides"], o["components"]) for o in info["objects"]])
json.dump(inv, open(os.path.join(OUT, "candidates_inventory.json"), "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "candidates.blend"))
