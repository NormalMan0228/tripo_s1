import bpy,bmesh,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1];bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend'))
bm=bmesh.new();bm.from_mesh(bpy.data.objects['HEAD_P2_CLEANUP'].data)
for cy in [-.042,.042]:
 fs=set(f for f in bm.faces if (c:=f.calc_center_median()).x>.23 and ((c.y-cy)/.024)**2+((c.z-.013)/.025)**2<1)
 es=set(e for f in fs for e in f.edges if sum(g in fs for g in e.link_faces)==1)
 deg=collections.Counter(v for e in es for v in e.verts)
 print('PATCH',cy,'faces',len(fs),'edges',len(es),'degrees',collections.Counter(deg.values()))
