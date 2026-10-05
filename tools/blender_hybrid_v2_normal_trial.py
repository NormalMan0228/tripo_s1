import bpy,bmesh,numpy as np
from mathutils import Vector,kdtree
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v2'
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend'))
o=bpy.data.objects['HEAD_P2_CLEANUP'];m=o.data;co=np.array([v.co[:] for v in m.vertices]);kd=kdtree.KDTree(len(co))
for i,c in enumerate(co):kd.insert(c,i)
kd.balance();normals=[]
for i,c in enumerate(co):
 near=[j for _,j,d in kd.find_n(c,18)];pts=co[near];p=pts-pts.mean(0);_,vec=np.linalg.eigh(p.T@p);n=vec[:,0]
 out=c-np.array([-.03,0,.15])
 if c[2]<-.19:out=np.array([c[0]+.08,c[1],0])
 if c[0]>.16:out=np.array([1.,.2*c[1],0])
 if n@out<0:n=-n
 normals.append(n.tolist())
bm=bmesh.new();bm.from_mesh(m);bm.verts.ensure_lookup_table()
for f in bm.faces:
 target=sum((Vector(normals[v.index]) for v in f.verts),Vector())
 if f.normal.dot(target)<0:f.normal_flip()
bm.to_mesh(m);bm.free();m.update();m.normals_split_custom_set_from_vertices(normals)
for ob in bpy.data.objects:
 if ob.type=='MESH' and ob!=o:ob.hide_render=True
sc=bpy.context.scene;sc.cycles.samples=16;sc.render.filepath=str(O/'normal_smooth_trial.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(O/'normal_smooth_trial.blend'))
