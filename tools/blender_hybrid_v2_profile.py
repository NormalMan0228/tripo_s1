import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend'))
o=bpy.data.objects['HEAD_P2_CLEANUP']
for z in [i/1000 for i in range(-155,-29,5)]:
 hit,loc,n,idx=o.ray_cast(Vector((2,0,z)),Vector((-1,0,0)));print(round(z,3),round(loc.x,5) if hit else None)
