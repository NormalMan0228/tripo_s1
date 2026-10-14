"""Deformation-transfer I/O (Blender side).
export: template basis + all shape keys (TemplateHead in template_head.blend) and wrap basis (WrapHead in <wrap.blend>) -> npz
import: npz of transferred key positions -> shape keys on WrapHead, saved to <out.blend>
Usage:
  blender --background template_head.blend --python dt_io.py -- export <wrap.blend> <out.npz>
  blender --background <wrap.blend> --python dt_io.py -- import <dt_out.npz> <out.blend>
"""
import bpy, sys, os
import numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
mode = a[0]
if mode == "export":
    t = bpy.data.objects["TemplateHead"]
    with bpy.data.libraries.load(a[1], link=False) as (df, dt):
        dt.objects = ["WrapHead"]
    w = dt.objects[0]
    me = t.data
    tris = []
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(1, len(vs) - 1):
            tris.append((vs[0], vs[i], vs[i + 1]))
    kb = me.shape_keys.key_blocks
    names = [k.name for k in kb[1:]]
    base = np.array([v.co[:] for v in kb[0].data])
    keys = np.stack([np.array([v.co[:] for v in k.data]) for k in kb[1:]])
    wb = np.array([v.co[:] for v in w.data.vertices])
    assert len(wb) == len(base)
    np.savez(os.path.abspath(a[2]), tris=np.array(tris), src_base=base, src_keys=keys, tgt_base=wb, names=np.array(names))
    print("EXPORTED", len(names), "keys", len(tris), "tris")
else:
    d = np.load(a[1], allow_pickle=True)
    w = bpy.data.objects["WrapHead"]
    if w.data.shape_keys:
        w.shape_key_clear()
    w.shape_key_add(name="Basis", from_mix=False)
    for nm, P in zip(d["names"], d["keys"]):
        k = w.shape_key_add(name=str(nm), from_mix=False)
        k.data.foreach_set("co", P.ravel())
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a[2]))
    print("IMPORTED", len(d["names"]))
