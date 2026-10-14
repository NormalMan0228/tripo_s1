import bpy, bmesh, numpy as np
body = bpy.data.objects["Template_Face_Body"]
me = body.data
mask = [m for m in body.modifiers if m.type == 'MASK']
print("mask modifiers:", [(m.vertex_group, m.invert_vertex_group) for m in mask])
vg = {g.index: g.name for g in body.vertex_groups}
print("groups sample:", [g.name for g in body.vertex_groups][:40])
co = np.array([v.co[:] for v in me.vertices])
# mouth region: sagittal slice
sel = np.where((np.abs(co[:, 0]) < 0.004) & (co[:, 2] > 1.40) & (co[:, 2] < 1.50))[0]
print("sagittal verts near mouth:", len(sel))
for i in sel[np.argsort(co[sel, 2])]:
    print("  y %.4f z %.4f" % (co[i, 1], co[i, 2]))
