"""Contour-conforming terrain and local current fields. Runs in art-venv."""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import Delaunay, cKDTree
from scipy.ndimage import gaussian_filter

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v5'
OUT.mkdir(parents=True,exist_ok=True)
DATA=json.loads((ROOT/'art/maps/archipelago_terrain_v3/manifest.json').read_text())

def ss(a,b,x):
    t=np.clip((x-a)/(b-a),0,1); return t*t*(3-2*t)

def noise(x,y,s=1,seed=0):
    x=x*s+seed*17.1;y=y*s+seed*9.7
    ix=np.floor(x);iy=np.floor(y);fx=ss(0,1,x-ix);fy=ss(0,1,y-iy)
    def h(a,b):return np.mod(np.sin(a*127.1+b*311.7+seed*74.7)*43758.5453,1)
    return (h(ix,iy)*(1-fx)+h(ix+1,iy)*fx)*(1-fy)+(h(ix,iy+1)*(1-fx)+h(ix+1,iy+1)*fx)*fy

def catmull(points):
    p=np.asarray(points,float); result=[]
    for i in range(len(p)):
        a,b,c,d=[p[j%len(p)] for j in (i-1,i,i+1,i+2)]
        for t in np.linspace(0,1,32,endpoint=False):
            result.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t**3))
    return np.asarray(result)

def distance(x,y,line,closed=True):
    result=np.full(np.broadcast(x,y).shape,1e6);inside=np.zeros(result.shape,bool)
    for a,b in zip(line,np.roll(line,-1,axis=0) if closed else line[1:]):
        v=b-a; t=np.clip(((x-a[0])*v[0]+(y-a[1])*v[1])/max(np.dot(v,v),1e-10),0,1)
        result=np.minimum(result,np.hypot(x-a[0]-t*v[0],y-a[1]-t*v[1]))
        if closed:
            inside^=((a[1]>y)!=(b[1]>y)) & (x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1]+1e-20)+a[0])
    return np.where(inside,result,-result) if closed else result

def pondq(x,y,p):
    px,py,rx,ry,level=p;u=(x-px)/rx;v=(y-py)/ry;a=np.arctan2(v,u)
    return np.hypot(u,v)/(1+.09*np.sin(3*a+.7)+.05*np.cos(5*a))

def height(x,y,island,d):
    # A broad submerged skirt prevents exposed grid cutoffs at the waterline.
    z=-8+6.4*ss(-30,-4,d)+1.85*ss(-4,.8,d)+(island['base']-.25)*ss(.8,4.7,d)
    cx,cy=island['center']
    z+=ss(1,6,d)*(.46*np.exp(-((x-cx+6)**2/240+(y-cy-9)**2/160))
        +.13*(noise(x,y,.065,2)-.5)+.07*(noise(x,y,.28,3)-.5))
    if 'pond' in island:
        q=pondq(x,y,island['pond']);m=ss(.87,1.25,q)
        z=z*m+(island['pond'][4]-.75)*(1-m)
    if island['id'].startswith('03'):
        plateau=np.hypot((x+2.6)/4.8,(y-10.3)/3.6)
        # The outside of the raised area must remain BELOW the submerged skirt.
        # A zero outside value would clamp every negative coast vertex to sea level.
        raised=-8.0+11.83*(1-ss(1.03,1.75,plateau))
        z=.5*(z+raised+np.sqrt((z-raised)**2+.24**2))
        q=np.hypot((x+3)/2.85,(y-10)/1.9)
        carve=1-ss(.79,1.23,q);z=z*(1-carve)+2.95*carve
        lip=distance(x,y,np.array([[-2.3,10.4],[-.9,9.7],[.2,8.7]]),False)
        inset=1-ss(.93,1.43,lip);z=z*(1-inset)+3.08*inset
        downstream=(x-.2)*.72-(y-8.7)*.69
        lateral=(x-.2)*.69+(y-8.7)*.72
        cut=ss(-.08,.30,downstream)*(1-ss(1.18,2.0,np.abs(lateral)))
        z=z*(1-cut)-.8*cut
    return z

contours=[];statistics=[]
for island in DATA['islands']:
    c=catmull(island['outline']);contours.append(c)
    if '--fields-only' in sys.argv:continue
    if '--headland-only' in sys.argv and not island['id'].startswith('03'):continue
    closed=np.vstack([c,c[0]])
    lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(closed,axis=0),axis=1))]
    n=int(np.ceil(lengths[-1]/.20))
    u=np.linspace(0,lengths[-1],n,endpoint=False)
    ring=np.stack([np.interp(u,lengths,closed[:,axis]) for axis in (0,1)],axis=1)
    tangent=np.roll(ring,-1,axis=0)-np.roll(ring,1,axis=0)
    normals=np.stack((tangent[:,1],-tangent[:,0]),axis=1)
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    if distance(np.asarray(ring[0,0]+normals[0,0]),np.asarray(ring[0,1]+normals[0,1]),c)>0:normals=-normals
    # Explicit contour samples make the mesh conform to the coast rather than a grid.
    points=[ring+normals*offset for offset in [-5,-4,-3,-2,-1.5,-1,-.65,-.3,0,.3,.65,1,1.5,2,3,4,5,6,8,12,18,24,30,36]]
    lo=c.min(axis=0)-6;hi=c.max(axis=0)+6
    gx,gy=np.meshgrid(np.arange(lo[0],hi[0],.85),np.arange(lo[1],hi[1],.85))
    sd=distance(gx,gy,c);points.append(np.stack((gx[sd>5.5],gy[sd>5.5]),axis=1))
    # Fill the broad bathymetry between contour rings to avoid large triangular
    # depth/color patches through the water at concave bays.
    bx,by=np.meshgrid(np.arange(c[:,0].min()-37,c[:,0].max()+37,2.0),np.arange(c[:,1].min()-37,c[:,1].max()+37,2.0))
    bd=distance(bx,by,c);mask=(bd < -3.8)&(bd > -36)
    points.append(np.stack((bx[mask],by[mask]),axis=1))
    if 'pond' in island:
        px,py,rx,ry,_=island['pond']
        gx,gy=np.meshgrid(np.arange(px-rx*1.6,px+rx*1.6,.32),np.arange(py-ry*1.6,py+ry*1.6,.32))
        points.append(np.stack((gx.ravel(),gy.ravel()),axis=1))
    if island['id'].startswith('03'):
        gx,gy=np.meshgrid(np.arange(-8,5,.12),np.arange(4,16,.12))
        points.append(np.stack((gx.ravel(),gy.ravel()),axis=1))
    p=np.unique(np.round(np.concatenate(points),5),axis=0)
    sd=distance(p[:,0],p[:,1],c);p=p[sd>-37];sd=sd[sd>-37]
    z=height(p[:,0],p[:,1],island,sd)
    # Analytic surface normals avoid thin Delaunay triangles leaving pointed
    # lighting/material artifacts along a smooth bank.
    _,nearest=cKDTree(c).query(p)
    best=np.full(len(p),1e10);closest=np.zeros_like(p);fallback=np.zeros_like(p)
    area=np.sum(c[:,0]*np.roll(c[:,1],-1)-np.roll(c[:,0],-1)*c[:,1])
    for offset in [-2,-1,0,1]:
        a=c[(nearest+offset)%len(c)];b=c[(nearest+offset+1)%len(c)];v=b-a
        t=np.clip(np.sum((p-a)*v,axis=1)/np.maximum(np.sum(v*v,axis=1),1e-10),0,1)
        q=a+v*t[:,None];d=np.linalg.norm(p-q,axis=1);mask=d<best
        best[mask]=d[mask];closest[mask]=q[mask]
        inward=np.stack((-v[:,1],v[:,0]),axis=1)*(1 if area>0 else -1)
        inward/=np.maximum(np.linalg.norm(inward,axis=1)[:,None],1e-8)
        fallback[mask]=inward[mask]
    gradient=(p-closest)/np.maximum(best[:,None],1e-8)*np.sign(sd)[:,None]
    gradient[np.abs(sd)<.015]=fallback[np.abs(sd)<.015]
    e=.035
    dx=(height(p[:,0]+e,p[:,1],island,sd+gradient[:,0]*e)-height(p[:,0]-e,p[:,1],island,sd-gradient[:,0]*e))/(2*e)
    dy=(height(p[:,0],p[:,1]+e,island,sd+gradient[:,1]*e)-height(p[:,0],p[:,1]-e,island,sd-gradient[:,1]*e))/(2*e)
    normals=np.column_stack((-dx,-dy,np.ones(len(p))))
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    faces=Delaunay(p).simplices
    centers=p[faces].mean(axis=1)
    faces=faces[distance(centers[:,0],centers[:,1],c)>-36.5]
    # Force upwards facing triangles independently of Delaunay's ordering.
    ab=p[faces[:,1]]-p[faces[:,0]];ac=p[faces[:,2]]-p[faces[:,0]]
    flip=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]<0
    faces[flip]=faces[flip][:,[0,2,1]]
    np.savez_compressed(OUT/(island['id']+'.npz'),vertices=np.column_stack((p,z)),faces=faces,normals=normals,bounds=np.r_[c.min(axis=0)-3,c.max(axis=0)+3])
    statistics.append({'island':island['id'],'vertices':len(p),'triangles':len(faces),'coast_sample_spacing_m':.2})
    print('CONTOUR_TERRAIN',statistics[-1],flush=True)

# Current vectors in Godot world X,Z coordinates, plus coast distance and inward wave normal.
n=512;x,z=np.meshgrid(np.linspace(-130,130,n),np.linspace(-110,115,n))
signed=np.full(x.shape,-1e5)
for c in contours:signed=np.maximum(signed,distance(x,-z,c))
gz,gx=np.gradient(gaussian_filter(signed,1.2),225/(n-1),260/(n-1))
mag=np.maximum(np.hypot(gx,gz),1e-5);inward=np.stack((gx/mag,gz/mag),axis=-1)
vx=np.full(x.shape,.21);vz=np.full(x.shape,.13)
routes=[(np.array([[0,-65],[1,-42],[3,-23],[5,-6],[6,2],[7,10],[6,20],[3,32],[2,45],[2,58],[0,68],[-8,77],[-9,88],[-4,103]]),.9,4.3),
        (np.array([[3,60],[15,68],[22,78],[22,90],[14,105]]),.46,6.0),
        (np.array([[.996,-7.937],[1.8,-7.1],[2.4,-5.3],[3.2,-2],[5,3],[7,10],[6,20]]),1.5,2.4)]
for route,speed,width in routes:
    best=np.full(x.shape,1e5);dx=np.zeros(x.shape);dz=np.zeros(x.shape)
    for a,b in zip(route[:-1],route[1:]):
        v=b-a;t=np.clip(((x-a[0])*v[0]+(z-a[1])*v[1])/np.dot(v,v),0,1)
        d=np.hypot(x-a[0]-t*v[0],z-a[1]-t*v[1]);mask=d<best;best=np.minimum(best,d)
        dx[mask]=v[0]/np.linalg.norm(v);dz[mask]=v[1]/np.linalg.norm(v)
    weight=np.exp(-(best/width)**2)
    vx=vx*(1-weight)+dx*speed*weight;vz=vz*(1-weight)+dz*speed*weight
# Currents turn along banks; incoming shore waves are a separate field.
near=1-ss(1,5,np.abs(signed));normal_speed=vx*inward[:,:,0]+vz*inward[:,:,1]
vx-=normal_speed*inward[:,:,0]*near*.94;vz-=normal_speed*inward[:,:,1]*near*.94
speed=np.hypot(vx,vz);direction=np.stack((vx,vz),axis=-1)/np.maximum(speed[...,None],.001)
rgba=np.dstack((direction*.5+.5,np.clip(speed/2,0,1),np.clip((-signed)/16,0,1)))
Image.fromarray(np.uint8(np.clip(rgba,0,1)*255),'RGBA').save(OUT/'textures/current_field.png')
rgba=np.dstack((inward*.5+.5,np.clip((-signed)/16,0,1),np.ones(x.shape)))
Image.fromarray(np.uint8(np.clip(rgba,0,1)*255),'RGBA').save(OUT/'textures/coast_field.png')

# World-tiled detail textures complement the island-wide 2K color paintings.
n=1024;x,y=np.meshgrid(np.linspace(0,4,n),np.linspace(0,4,n))
grain=noise(x,y,85,7);macro=noise(x,y,7,3);vein=noise(x,y,24,9)
for name,color,h in [
    ('grass_detail',np.stack((.43+.14*macro,.60+.13*macro,.20+.07*vein),-1),.012*grain+.022*vein),
    ('sand_detail',np.stack((.83+.07*macro,.72+.055*macro,.48+.04*macro),-1),.004*grain),
    ('rock_detail',np.stack((.40+.13*macro,.45+.12*macro,.47+.12*macro),-1),.013*vein+.004*grain)]:
    pixels=color*(.95+.08*grain[...,None])
    if name=='rock_detail':
        mean=pixels.mean((0,1),keepdims=True);pixels=mean+(pixels-mean)*.32
    Image.fromarray(np.uint8(np.clip(pixels,0,1)*255)).save(OUT/'textures'/f'{name}.png')
    dy,dx=np.gradient(h,4/(n-1),4/(n-1));normal=np.stack((-dx,-dy,np.ones_like(dx)),-1)
    normal/=np.linalg.norm(normal,axis=-1)[...,None]
    Image.fromarray(np.uint8((normal*.5+.5)*255)).save(OUT/'textures'/f'{name}_normal.png')
if statistics:
    stats_path=OUT/'mesh_statistics.json'
    if '--headland-only' in sys.argv and stats_path.exists():
        old=json.loads(stats_path.read_text());updated={item['island']:item for item in statistics}
        statistics=[updated.get(item['island'],item) for item in old]
    stats_path.write_text(json.dumps(statistics,indent=2))
print('V5_FIELDS_READY',flush=True)
