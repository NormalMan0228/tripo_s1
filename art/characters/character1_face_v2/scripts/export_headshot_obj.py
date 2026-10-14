"""OBJ variant of the Headshot input for RLPy.RHeadshot.ImportHeadFromObj: head mesh only, lip seam welded,
symmetric decimation to TARGET tris, centimetres (head top-to-chin HEAD_CM), Y-up with the face toward +Z.
Usage: blender --background head_a_full.blend --python export_headshot_obj.py -- <out.obj> [target_tris]"""
import bpy, bmesh, sys, os, json
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(a[0]); TARGET = int(a[1]) if len(a) > 1 else 200000
HEAD_CM = float(os.environ.get("HEAD_CM", 24.0))
head = bpy.data.objects["Head"]
for o in list(bpy.data.objects):
    if o is not head: bpy.data.objects.remove(o)
X = np.array([v.co[:] for v in head.data.vertices])
chin_z = float(X[(X[:, 1] < -0.22) & (np.abs(X[:, 0]) < 0.03) & (X[:, 2] > 0.2), 2].min())
s = HEAD_CM / (X[:, 2].max() - chin_z)                       # centimetres per model unit (1 Blender unit = 1 cm in the OBJ)
head.data.transform(Matrix.Scale(s, 4))
bm = bmesh.new(); bm.from_mesh(head.data)
bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v.is_boundary], dist=1e-5)
bm.to_mesh(head.data); bm.free()
bpy.context.view_layer.objects.active = head
d = head.modifiers.new("dec", 'DECIMATE'); d.ratio = min(1, TARGET / len(head.data.polygons)); d.use_symmetry = True; d.symmetry_axis = 'X'
bpy.ops.object.modifier_apply(modifier="dec")
bm = bmesh.new(); bm.from_mesh(head.data)
bad = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
if bad:
    bmesh.ops.delete(bm, geom=list({f for e in bad for f in e.link_faces}), context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=16)
    bm.to_mesh(head.data)
bm.free()
head.vertex_groups.clear()
for o in bpy.data.objects: o.select_set(o is head)
bpy.ops.wm.obj_export(filepath=OUT, export_selected_objects=True, forward_axis='Y', up_axis='Z', export_materials=False,
                      export_uv=False, export_normals=True, global_scale=1.0, apply_modifiers=True)
# reorient on disk: Blender Z-up / -Y front  ->  OBJ Y-up / +Z front  (x' = x, y' = z, z' = -y)
lines = open(OUT).read().splitlines()
outl = []
for l in lines:
    if l.startswith("v ") or l.startswith("vn "):
        t = l.split(); x, y, z = map(float, t[1:4]); outl.append(f"{t[0]} {x:.6f} {z:.6f} {-y:.6f}")
    else:
        outl.append(l)
open(OUT, "w").write("\n".join(outl) + "\n")
V = np.array([list(map(float, l.split()[1:4])) for l in outl if l.startswith("v ")])
rep = {"cm_per_unit": s, "tris": len(head.data.polygons), "verts": len(V), "bbox_min": V.min(0).round(2).tolist(), "bbox_max": V.max(0).round(2).tolist(),
       "nose_tip": V[np.argmax(V[:, 2])].round(2).tolist(), "bytes": os.path.getsize(OUT)}
json.dump(rep, open(OUT.replace(".obj", "_obj_report.json"), "w"), indent=1)
print("OBJ", json.dumps(rep))
