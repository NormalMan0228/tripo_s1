import bpy,bmesh,json,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v1'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_hybrid_bust_v1.blend'))
print('OBJECTS',[(o.name,o.type,o.hide_render) for o in bpy.data.objects])
o=bpy.data.objects['HEAD_P2_CLEANUP'];m=o.data
bm=bmesh.new();bm.from_mesh(m);bm.verts.ensure_lookup_table()
seen=set();groups=[]
for v in bm.verts:
    if v.index in seen:continue
    stack=[v];seen.add(v.index);g=[]
    while stack:
        a=stack.pop();g.append(a)
        for e in a.link_edges:
            b=e.other_vert(a)
            if b.index not in seen:seen.add(b.index);stack.append(b)
    groups.append(g)
print('COMPONENTS',[(len(g),[[min(v.co[i] for v in g),max(v.co[i] for v in g)] for i in range(3)]) for g in sorted(groups,key=len,reverse=True)[:15]])
coords=collections.Counter(tuple(round(a,6) for a in v.co) for v in bm.verts)
print('DUP_COORDS',sum(n-1 for n in coords.values()),'FACES',collections.Counter(len(f.verts) for f in bm.faces),'NONMANIFOLD',sum(not e.is_manifold for e in bm.edges))
bm.free()
for source in bpy.data.collections['90_Original_Tripo_Sources'].objects:source.hide_render=True
for o in bpy.data.objects:
    if o.type=='MESH' and o.name!='HEAD_P2_CLEANUP':o.hide_render=True
bpy.context.scene.render.engine='BLENDER_WORKBENCH';bpy.context.scene.display.shading.show_cavity=False
bpy.context.scene.render.filepath=str(O/'diagnosis.png');bpy.ops.render.render(write_still=True)
