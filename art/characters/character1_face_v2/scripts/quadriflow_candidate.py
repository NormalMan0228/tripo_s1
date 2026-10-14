"""Candidate D: Blender QuadriFlow remesh of the P2 skin (eyes kept separate). Usage: ... target.blend -- <out.blend> <faces>"""
import bpy, sys, os
a = sys.argv[sys.argv.index("--")+1:]; out = os.path.abspath(a[0]); faces = int(a[1])
body = bpy.data.objects["Body"]
q = body.copy(); q.data = body.data.copy(); q.name = "QFHead"; bpy.context.scene.collection.objects.link(q)
for o in bpy.context.selected_objects: o.select_set(False)
bpy.context.view_layer.objects.active = q; q.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.remove_doubles(threshold=1e-5); bpy.ops.object.mode_set(mode='OBJECT')
q.data.remesh_voxel_size = 0.003; bpy.ops.object.voxel_remesh()
print('voxel', len(q.data.vertices))
r = bpy.ops.object.quadriflow_remesh(target_faces=faces, use_preserve_sharp=False, use_preserve_boundary=True, use_mesh_symmetry=False, smooth_normals=True, seed=1)
print("QF", r, len(q.data.vertices), len(q.data.polygons))
body.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=out)
