"""Turn a Tripo GLB head into a Reallusion Headshot (mesh mode) source FBX.

Keeps the Tripo triangle order (CC indexes alignment points by triangle), so no symmetrize/decimate here.
Steps: drop stray pieces, repair the few non-manifold spots and holes, scale so chin-to-top is HEAD_CM,
put the base at the origin facing -Y, export binary FBX like character1_face_v2/scripts/export_headshot.py.
Usage: blender -b --factory-startup -P prep_headshot_source.py -- <in.glb> <out.fbx>
"""
import bpy, bmesh, sys, os, json
import numpy as np
from mathutils import Matrix

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
HEAD_CM = float(os.environ.get("HEAD_CM", 24.0))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
for o in list(bpy.context.scene.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o)
head = meshes[0]
head.data.transform(head.matrix_world); head.matrix_world = Matrix(); head.name = "Head"
rep = {"source": os.path.basename(SRC)}

bm = bmesh.new(); bm.from_mesh(head.data)
# stray components
bm.verts.ensure_lookup_table(); seen = set(); comps = []
for v in bm.verts:
    if v in seen: continue
    st = [v]; seen.add(v); c = []
    while st:
        x = st.pop(); c.append(x)
        for e in x.link_edges:
            y = e.other_vert(x)
            if y not in seen: seen.add(y); st.append(y)
    comps.append(c)
comps.sort(key=len, reverse=True)
stray = [v for c in comps[1:] for v in c]
bmesh.ops.delete(bm, geom=stray, context='VERTS')
rep["stray_verts_removed"] = len(stray)
# non-manifold edges: drop their faces, then fill every hole except the neck opening (largest loop)
bad = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
bmesh.ops.delete(bm, geom=list({f for e in bad for f in e.link_faces}), context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
rep["nonmanifold_fixed"] = len(bad)
bnd = [e for e in bm.edges if e.is_boundary]
loops, seen = [], set()
for e in bnd:
    if e in seen: continue
    st = [e]; seen.add(e); c = []
    while st:
        x = st.pop(); c.append(x)
        for v in x.verts:
            for y in v.link_edges:
                if y.is_boundary and y not in seen: seen.add(y); st.append(y)
    loops.append(c)
loops.sort(key=len, reverse=True)
small = [e for c in loops[1:] for e in c] if loops and len(loops[0]) > 40 else [e for c in loops for e in c]
if small:
    bmesh.ops.holes_fill(bm, edges=small, sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
rep["holes_filled_edges"] = len(small)
bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
bm.to_mesh(head.data); bm.free()

X = np.array([v.co[:] for v in head.data.vertices])
front = (X[:, 1] < -0.2) & (np.abs(X[:, 0]) < 0.03)
chin_z = float(X[front, 2].min())
scale = (HEAD_CM / 100.0) / (X[:, 2].max() - chin_z)
head.data.transform(Matrix.Translation((-0.5 * (X[:, 0].max() + X[:, 0].min()), 0, -X[:, 2].min())))
head.data.transform(Matrix.Scale(scale, 4))
rep.update({"chin_z_model": chin_z, "metres_per_unit": scale, "head_cm": HEAD_CM,
            "bust_height_cm": scale * 100 * (X[:, 2].max() - X[:, 2].min())})
bm = bmesh.new(); bm.from_mesh(head.data)
rep["head"] = {"tris": len(bm.faces), "verts": len(bm.verts), "sizes": sorted({len(f.verts) for f in bm.faces}),
               "boundary_edges": sum(e.is_boundary for e in bm.edges),
               "nonmanifold": sum((not e.is_manifold) and not e.is_boundary for e in bm.edges),
               "degenerate": sum(f.calc_area() < 1e-12 for f in bm.faces)}
bm.free()
for o in bpy.data.objects: o.select_set(o == head)
bpy.context.view_layer.objects.active = head
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
                         mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False, path_mode='STRIP')
rep["fbx_bytes"] = os.path.getsize(OUT)
json.dump(rep, open(os.path.splitext(OUT)[0] + "_report.json", "w"), indent=1)
print("PREP", json.dumps(rep))
