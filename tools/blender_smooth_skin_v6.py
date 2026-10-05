import bpy, numpy as np
from pathlib import Path
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_animated_v6';f=A/'explorer_b_repaired_rigify_v6.blend'
bpy.ops.wm.open_mainfile(filepath=str(f));h=bpy.data.objects['FACE_skin_eyelids_lashes'];keys=h.data.shape_keys.key_blocks;b=keys[0];pts=np.array([v.co[:] for v in b.data]);tree=KDTree(len(pts))
for i,p in enumerate(pts):tree.insert((0,p[1],p[2]),i)
tree.balance();changed=0
for i,p in enumerate(pts):
 y=abs(p[1]);z=p[2]
 if not (.075<p[0] and .042<y<.26 and .045<z<.235):continue
 u=(y-.139)/.070
 if abs(u)<1:
  s=(1-u*u)**.5;mid=.108+.014*(u+1)/2
  if mid-.047*s**.9-.013<z<mid+.049*s**.9+.013:continue
 rows=[j for _,j,d in tree.find_range((0,p[1],p[2]),.022) if pts[j,0]>.075 and abs(pts[j,0]-p[0])<.05]
 if len(rows)<12:continue
 q=pts[rows]-p;dy=q[:,1];dz=q[:,2];design=np.column_stack([np.ones(len(rows)),dy,dz,dy*dy,dy*dz,dz*dz]);w=np.exp(-(dy*dy+dz*dz)/(.012**2));fit=np.linalg.lstsq(design*w[:,None],pts[rows,0]*w,rcond=None)[0][0];delta=float(np.clip(fit-p[0],-.015,.015))*.85
 for k in keys:k.data[i].co.x+=delta
 changed+=1
pts=np.array([v.co[:] for v in b.data]);neigh=[set() for _ in pts]
for e in h.data.edges:
 a,c=e.vertices;neigh[a].add(c);neigh[c].add(a)
selected={}
for i,p in enumerate(pts):
 y=abs(p[1]);z=p[2];r=((y-.14)**2/.094**2+(z-.122)**2/.061**2)**.5
 if p[0]>.08 and .04<y<.275 and .03<z<.235 and r>1.12:
  selected[i]=max(0,min(1,(r-1.12)/.2))*max(0,min(1,(2.3-r)/.3))
orig=pts.copy()
for _ in range(30):
 prev=pts.copy()
 for i,w in selected.items():
  if neigh[i]:pts[i]=prev[i]+.38*w*(prev[list(neigh[i])].mean(axis=0)-prev[i])
for i in selected:
 delta=pts[i]-orig[i]
 for k in keys:k.data[i].co+=__import__('mathutils').Vector(delta)
bpy.ops.wm.save_as_mainfile(filepath=str(f));print('SMOOTHED_SKIN',changed,len(selected))
