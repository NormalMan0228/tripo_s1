import bpy, bmesh, numpy as np, json, sys, os
out = os.path.abspath(sys.argv[sys.argv.index("--")+1])
info = {}
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    sides = {}
    for f in bm.faces: sides[len(f.verts)] = sides.get(len(f.verts), 0) + 1
    bnd = sum(e.is_boundary for e in bm.edges)
    co = np.array([o.matrix_world @ v.co for v in me.vertices]) if len(me.vertices) else np.zeros((1,3))
    info[o.name] = dict(verts=len(me.vertices), faces=len(me.polygons), sides=sides, boundary_edges=bnd,
        dims=[round(d,3) for d in o.dimensions], bbmin=co.min(0).round(3).tolist(), bbmax=co.max(0).round(3).tolist(),
        keys=len(me.shape_keys.key_blocks) if me.shape_keys else 0,
        keynames=[k.name for k in me.shape_keys.key_blocks][:70] if me.shape_keys else [],
        groups=len(o.vertex_groups), mods=[m.type for m in o.modifiers])
    bm.free()
json.dump(info, open(out, "w"), indent=1)
for k, v in info.items(): print(k, v['verts'], v['faces'], v['sides'], 'bnd', v['boundary_edges'], v['dims'], 'keys', v['keys'], v['mods'])
