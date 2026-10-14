"""Export the clean head for Reallusion Headshot (mesh mode), following its source-mesh guidance:
single head mesh only (eyes, teeth, gums, tongue are NOT merged - exported separately), mouth closed, no bones,
facing straight forward, base at the world origin, CC-like scale (head top-to-chin HEAD_CM centimetres),
FBX binary 7.4 (Headshot accepts FBX older than 2018).
The lip seam is welded for this export (a closed-mouth surface is what Headshot expects); eye openings stay open.
Usage: blender --background head_a_full.blend --python export_headshot.py -- <out_dir> [target_tris]
"""
import bpy, bmesh, sys, os, json
import numpy as np
from mathutils import Matrix

a = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(a[0]); os.makedirs(OUT, exist_ok=True)
TARGET = int(a[1]) if len(a) > 1 else 200000
HEAD_CM = float(os.environ.get("HEAD_CM", 24.0))
head = bpy.data.objects["Head"]
X = np.array([v.co[:] for v in head.data.vertices])
front = (X[:, 1] < -0.22) & (np.abs(X[:, 0]) < 0.03) & (X[:, 2] > 0.2)     # chin front (neck/chest sit further back)
chin_z = float(X[front, 2].min())
scale = (HEAD_CM / 100.0) / (X[:, 2].max() - chin_z)             # metres per model unit
rep = {"chin_z_model": chin_z, "metres_per_unit": scale, "head_cm": HEAD_CM, "bust_height_cm": scale * 100}

sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 1.0
for o in list(bpy.data.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o)
S = Matrix.Scale(scale, 4)
for o in bpy.data.objects:
    o.data.transform(S @ o.matrix_world); o.matrix_world = Matrix()
    o.vertex_groups.clear()
    for k in list(o.keys()): del o[k]
# head: weld the lip seam, decimate symmetric to TARGET tris
bm = bmesh.new(); bm.from_mesh(head.data)
bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v.is_boundary], dist=1e-7)
bm.to_mesh(head.data); bm.free()
if len(head.data.polygons) > TARGET:
    bpy.context.view_layer.objects.active = head
    d = head.modifiers.new("dec", 'DECIMATE'); d.ratio = TARGET / len(head.data.polygons); d.use_symmetry = True; d.symmetry_axis = 'X'
    bpy.ops.object.modifier_apply(modifier="dec")
bm = bmesh.new(); bm.from_mesh(head.data)
bad = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
if bad:
    bmesh.ops.delete(bm, geom=list({f for e in bad for f in e.link_faces}), context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=16)
    bm.to_mesh(head.data)
rep["nonmanifold_fixed"] = len(bad)
rep["head"] = {"tris": len(head.data.polygons), "verts": len(head.data.vertices),
               "boundary_loops_edges": sum(1 for e in bm.edges if e.is_boundary),
               "nonmanifold": sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)}
bm.free()


def export(objs, path):
    for o in bpy.data.objects: o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
                             mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False, path_mode='STRIP')
    return os.path.getsize(path)


rep["files"] = {}
p = os.path.join(OUT, "character1_head_headshot.fbx"); rep["files"][os.path.basename(p)] = export([head], p)
parts = [bpy.data.objects[n] for n in ("Eye.L", "Eye.R", "TeethUpper", "TeethLower", "GumUpper", "GumLower", "Tongue") if n in bpy.data.objects]
p = os.path.join(OUT, "character1_eyes_mouth_parts.fbx"); rep["files"][os.path.basename(p)] = export(parts, p)
json.dump(rep, open(os.path.join(OUT, "export_report.json"), "w"), indent=1)
print("EXPORT", json.dumps(rep))
