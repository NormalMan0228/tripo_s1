import bpy,numpy as np,math,json
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';FILE=A/'user_head_mpfb_rigify_v8.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update();h=bpy.data.objects['FACE_user_head'];keys=h.data.shape_keys.key_blocks;base=keys[0];pts=np.array([v.co[:] for v in base.data]);neigh=[set() for _ in pts]
for e in h.data.edges:a,b=e.vertices;neigh[a].add(b);neigh[b].add(a)
selected={}
for i,p in enumerate(pts):
 y=abs(p[1]);z=p[2];r=math.hypot((y-.14)/.094,(z-.105)/.058);u=(y-.141)/.056
 if abs(u)<1:
  s=math.sqrt(1-u*u);mid=.109+.008*(u+1)/2
  if mid-.046*s**.9-.010<z<mid+.042*s**.9+.010:continue
 if p[0]>.075 and .036<y<.275 and .010<z<.230 and (r>1.10 or y<.082):selected[i]=max(0,min(1,(2.4-r)/.3))*max(0,min(1,(y-.036)/.02))
original=pts.copy()
for _ in range(34):
 prev=pts.copy()
 for i,w in selected.items():
  if neigh[i]:pts[i]=prev[i]+.35*w*(prev[list(neigh[i])].mean(axis=0)-prev[i])
for i in selected:
 d=Vector(pts[i]-original[i])
 for k in keys:k.data[i].co+=d
bpy.context.view_layer.update()
# Restore the smooth source bob and apply a continuous collision displacement field.
hair=bpy.data.objects['HAIR_sculptural_bob_mesh']
with bpy.data.libraries.load(str(A/'assembled_workbench.blend'),link=False) as (src,dst):dst.meshes=[hair.data.name]
assert dst.meshes[0] and len(dst.meshes[0].vertices)==len(hair.data.vertices)
for v,p in zip(hair.data.vertices,dst.meshes[0].vertices):v.co=p.co
surfaces=[h,bpy.data.objects['EAR_L'],bpy.data.objects['EAR_R']];vv=[];ff=[]
for o in surfaces:
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();start=len(vv);vv.extend(o.matrix_world@v.co for v in me.vertices);ff.extend(tuple(start+i for i in t.vertices) for t in me.loop_triangles);eo.to_mesh_clear()
tree=BVHTree.FromPolygons(vv,ff,all_triangles=True);ps=[hair.matrix_world@v.co for v in hair.data.vertices];ds=[];ids=[]
for i,p in enumerate(ps):
 if not (-.15<p.x and abs(p.y)<.36 and -.20<p.z<.34):continue
 q,n,_,dist=tree.find_nearest(p)
 if q is None or dist>.03:continue
 signed=(p-q).dot(n)
 if -.025<signed<.003:ids.append(i);ds.append(n*(.005-signed))
kt=KDTree(len(ids))
for j,i in enumerate(ids):kt.insert(ps[i],j)
kt.balance();inv=hair.matrix_world.inverted().to_3x3();changed=0
for i,p in enumerate(ps):
 _,j,d=kt.find(p)
 if d>.055:continue
 samples=kt.find_range(p,.055);v=Vector();total=0
 for _,j,dist in samples:w=math.exp(-(dist/.027)**2);v+=ds[j]*w;total+=w
 if total:hair.data.vertices[i].co+=inv@(v/total*max(0,1-(d/.055)**2));changed+=1
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(FILE));(A/'polish-report.json').write_text(json.dumps({'skin_vertices_faired':len(selected),'hair_vertices_faired':changed,'hair_collision_sources':len(ids),'original_source_mouth_pose':True,'credits':0},indent=2))
sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True;sc.render.resolution_x=640;sc.render.resolution_y=720
for n,f in [('neutral',1),('happy',95),('concern',195),('determined',295),('surprise',395),('blink_half',45),('blink_closed',47)]:
 sc.frame_set(f);bpy.context.view_layer.update();sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
print('V8_POLISHED')
