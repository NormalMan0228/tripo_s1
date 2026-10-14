import bpy, json, numpy as np
w = bpy.data.objects["WrapHead"]; me = w.data
kb = me.shape_keys.key_blocks
X0 = np.array([v.co[:] for v in kb["Basis"].data]); X1 = np.array([v.co[:] for v in kb["eyeBlinkLeft"].data])
moved = set(np.where(np.linalg.norm(X1 - X0, axis=1) > 1e-4)[0])
cnt = {}
for p in me.polygons:
    if any(v in moved for v in p.vertices):
        cnt[p.material_index] = cnt.get(p.material_index, 0) + 1
print("MATS", [m.name for m in me.materials], cnt)
for m in me.materials:
    b = m.node_tree.nodes.get("Principled BSDF")
    if b: print(m.name, "rough", b.inputs["Roughness"].default_value, "metal", b.inputs["Metallic"].default_value, "spec", b.inputs.get("Specular IOR Level").default_value if b.inputs.get("Specular IOR Level") else None, "coat", b.inputs["Coat Weight"].default_value, "trans", b.inputs["Transmission Weight"].default_value)
