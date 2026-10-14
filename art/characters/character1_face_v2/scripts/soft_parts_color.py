"""Bake the soft part weights (W_* groups) of Body into a blended colour attribute 'soft_parts' (material palette colours),
save the file, then render it. Usage: blender -b open/segmented.blend -P soft_parts_color.py -- <out.png>"""
import bpy, sys, os, numpy as np
OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
b = bpy.data.objects["Body"]; me = b.data; nV = len(me.vertices)
C = np.zeros((nV, 3)); S = np.zeros(nV)
for vg in b.vertex_groups:
    if not vg.name.startswith("W_"): continue
    col = np.array(bpy.data.materials[f"P_{vg.name[2:]}"].diffuse_color[:3])
    for v in me.vertices:
        for g in v.groups:
            if g.group == vg.index: C[v.index] += g.weight * col; S[v.index] += g.weight
C /= np.maximum(S, 1e-9)[:, None]
ca = me.color_attributes.get("soft_parts") or me.color_attributes.new("soft_parts", 'FLOAT_COLOR', 'POINT')
ca.data.foreach_set("color", np.c_[C, np.ones(nV)].ravel()); me.color_attributes.active_color = ca
bpy.ops.wm.save_mainfile()
sc = bpy.context.scene; sc.display.shading.color_type = 'VERTEX'
sys.argv = [sys.argv[0], "--", OUT]
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_matcol.py")).read())
