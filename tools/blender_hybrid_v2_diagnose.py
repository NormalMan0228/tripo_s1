import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v2';O.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend'))
o=bpy.data.objects['HEAD_P2_CLEANUP'];bm=bmesh.new();bm.from_mesh(o.data)
def stats():return {'v':len(bm.verts),'f':len(bm.faces),'boundary':sum(e.is_boundary for e in bm.edges),'overconnected':sum(len(e.link_faces)>2 for e in bm.edges),'wire':sum(e.is_wire for e in bm.edges)}
print('BEFORE',stats());bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0008);print('WELDED',stats())
seen=set();groups=[]
for f in bm.faces:
    if f in seen:continue
    stack=[f];seen.add(f);g=[]
    while stack:
        a=stack.pop();g.append(a)
        for e in a.edges:
            if len(e.link_faces)==2:
                for b in e.link_faces:
                    if b not in seen:seen.add(b);stack.append(b)
    groups.append(g)
print('MANIFOLD_PATCHES',sorted([len(g) for g in groups],reverse=True)[:40])
for g in groups:
    bmesh.ops.recalc_face_normals(bm,faces=g)
bm.to_mesh(o.data);bm.free()
for ob in bpy.data.objects:
    if ob.type=='MESH' and ob!=o:ob.hide_render=True
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.display.shading.show_cavity=False;s.render.filepath=str(O/'diagnose.png');bpy.ops.render.render(write_still=True)
