# Symmetrise Headshot 3 alignment points ([Target] = our head) and put point 33 on the midline.
# Run: blender -b --factory-startup --python headshot_sym_points.py
# Target F = CC triangle index (FBX polygons in order, quads split v0v1v2/v0v2v3); only tris < SAFE match CC.
import bpy, re, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
SRC=r"C:\lsm26\triphthonS1\art\characters\character1_face_v2\hd\cc5\character1_align35_sym.ini"
OUT=r"C:\lsm26\triphthonS1\art\characters\character1_face_v2\hd\cc5\character1_align35_sym.ini"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"C:\lsm26\triphthonS1\art\characters\character1_face_v2\hd\export\character1_head_headshot.fbx")
o=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]
me=o.data; mw=o.matrix_world
V=np.array([tuple(mw@v.co) for v in me.vertices])
P=[]
for p in me.polygons:
    vs=list(p.vertices)
    if len(vs)==3: P.append(vs)
    else: P.append([vs[0],vs[1],vs[2]]); P.append([vs[0],vs[2],vs[3]])
SAFE=196000
bvh=BVHTree.FromPolygons([Vector(v) for v in V], P[:SAFE])
raw=open(SRC,encoding='utf-8-sig').read()
head,tgt=raw.split('[Target]')
F={int(a):int(b) for a,b in re.findall(r'\nF(\d+) = (\d+)',tgt)}
B={int(a):[float(x) for x in b.split()] for a,b in re.findall(r'\nB(\d+) = "([^"]+)"',tgt)}
X={k:sum(V[P[F[k]][i]]*B[k][i] for i in range(3)) for k in F}
M=np.array([-1,1,1])
pairs=[(1,6),(2,5),(3,4),(7,13),(8,12),(9,11),(10,14),(17,18),(20,22),(25,28),(26,29),(27,30)]
mid=[15,16,19,21,23,24,31,32,33,34,35]
T=dict(X)
for a,b in pairs:
    avg=(X[a]+X[b]*M)/2; T[a]=avg; T[b]=avg*M
for k in mid: T[k]=X[k]*np.array([0,1,1])
T[33]=np.array([0.0,-0.035,0.1265])
def bary(p,tri):
    a,b,c=[V[i] for i in tri]; v0,v1,v2=b-a,c-a,p-a
    d00,d01,d11,d20,d21=v0@v0,v0@v1,v1@v1,v2@v0,v2@v1
    den=d00*d11-d01*d01; v=(d11*d20-d01*d21)/den; w=(d00*d21-d01*d20)/den
    u=1-v-w; bb=np.clip([u,v,w],0,1); return bb/bb.sum()
NF,NB={},{}
for k in sorted(T):
    loc,n,idx,dist=bvh.find_nearest(Vector(T[k]))
    bb=bary(np.array(loc),P[idx]); NF[k]=idx; NB[k]=bb
    newp=sum(V[P[idx]][i]*bb[i] for i in range(3))
    print('pt %2d F %6d->%6d moved %.1f mm snap %.2f mm x %.4f' % (k, F[k], idx, np.linalg.norm(newp-X[k])*1000, dist*1000, newp[0]))
def sub(m):
    k=int(m.group(2))
    if m.group(1)=='F': return 'F%d = %d' % (k, NF[k])
    return 'B%d = "%s"' % (k, ' '.join('%.6f'%x for x in NB[k]))
tgt2=re.sub(r'^(F|B)(\d+) = .*$', sub, tgt, flags=re.M)
open(OUT,'w',encoding='utf-8-sig',newline='\n').write(head+'[Target]'+tgt2)
print('wrote',OUT)
