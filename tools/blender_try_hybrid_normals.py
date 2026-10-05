import bpy,bmesh
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v1'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_hybrid_bust_v1.blend'))
o=bpy.data.objects['HEAD_P2_CLEANUP'];bm=bmesh.new();bm.from_mesh(o.data)
count=0
for f in bm.faces:
    c=f.calc_center_median();out=Vector((c.x,c.y,c.z-.09))
    if f.normal.dot(out)<0:f.normal_flip();count+=1
bm.to_mesh(o.data);bm.free();o.data.update();print('flipped',count)
for a in bpy.data.objects:
    if a.type=='MESH' and a!=o:a.hide_render=True
sc=bpy.context.scene;sc.render.engine='BLENDER_WORKBENCH';sc.display.shading.show_cavity=False
sc.render.filepath=str(O/'normal_trial.png');bpy.ops.render.render(write_still=True)
