import bpy, numpy as np
for o in bpy.data.objects:
    if o.type == 'MESH':
        P = np.array([o.matrix_world @ v.co for v in o.data.vertices]); print("OBJ", o.name, len(P), P.min(0).round(3), P.max(0).round(3), "hide", o.hide_render, o.hide_viewport, o.hide_get())
