"""Source-based face reconstruction: stitched eyelids, oral opening and deformation keys.
This is a facial study, not a claim of completed production retopology.
"""
import bpy,bmesh,json,math,hashlib,sys
import numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'art/characters/explorer_b_hd_restart_v1'
OUT=ROOT/'art/characters/explorer_b_face_refined_v2';OUT.mkdir(exist_ok=True)
FAST='--draft' in sys.argv
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene
log={'source_model':'existing Tripo HD head and hair','api_credits_spent':0,'production_retopology':False,'steps':[]}
def col(name):
    c=bpy.data.collections.new(name);scene.collection.children.link(c);return c
facecol=col('01_FACE_AND_EYES');haircol=col('02_HAIR');oralcol=col('03_ORAL_PARTS');ctrlcol=col('04_FACE_CONTROLS');studio=col('05_STUDIO')
def load(part,collection):
    p=SRC/part/f'{part}_HD.blend'
    log[part+'_source_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    with bpy.data.libraries.load(str(p),link=False) as (a,b):b.objects=[n for n in a.objects if n.startswith('HD_'+part+'_')]
    o=b.objects[0];collection.objects.link(o);return o
def arrays(o):
    m=o.data;m.calc_loop_triangles()
    v=np.empty(len(m.vertices)*3,dtype=np.float32);m.vertices.foreach_get('co',v)
    f=np.empty(len(m.loop_triangles)*3,dtype=np.int32);m.loop_triangles.foreach_get('vertices',f)
    return v.reshape(-1,3),f.reshape(-1,3)
def activate(o):
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
def mat(name,color,rough=.5):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
    return m
def smooth01(t):
    t=np.clip(t,0,1);return t*t*(3-2*t)
skin=mat('Skin_Warm_Neutral',(.53,.285,.16),.5)
skin.node_tree.nodes.get('Principled BSDF').inputs['Subsurface Weight'].default_value=.035
hairmat=mat('Hair_Chestnut',(.035,.014,.006),.57)
hairmat.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.25
lashmat=mat('Lash_DarkBrown',(.018,.009,.004),.46)
oralmat=mat('Oral_Cavity',(.065,.012,.015),.72)
gummat=mat('Gums',(.33,.095,.090),.5)
toothmat=mat('Teeth_WarmIvory',(.78,.73,.63),.30)
tonguemat=mat('Tongue',(.38,.11,.115),.48)

head=load('head',facecol);head.name='Face_Skin'
source_v,source_f=arrays(head)
bvh=BVHTree.FromPolygons(source_v.tolist(),source_f.tolist(),all_triangles=True)
def surface(y,z):
    hit=bvh.ray_cast(Vector((1,float(abs(y)),float(z))),Vector((-1,0,0)))
    return float(hit[0].x) if hit[0] else .25
activate(head)
dec=head.modifiers.new('Working density reduction','DECIMATE');dec.ratio=.16
bpy.ops.object.modifier_apply(modifier=dec.name)
# Use one generated side as the bilateral base, rather than fitting independent eyes.
bm=bmesh.new();bm.from_mesh(head.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.00001,plane_co=(0,0,0),plane_no=(0,1,0),clear_inner=True,clear_outer=False)
bm.to_mesh(head.data);bm.free()
mirror=head.modifiers.new('Bilateral source symmetry','MIRROR');mirror.use_axis[0]=False;mirror.use_axis[1]=True;mirror.use_clip=True;mirror.merge_threshold=.00005
bpy.ops.object.modifier_apply(modifier=mirror.name)
v,f=arrays(head)
c=v[f].mean(1)
eyeC=.169
eye_regions=[]
for sign in [1,-1]:
    region=((c[:,1]-sign*eyeC)/.146)**2+((c[:,2]+.008)/.112)**2
    eye_regions.append((region<1)&(c[:,0]>.115))
mouth_region=((c[:,1]/.164)**2+((c[:,2]+.273)/.058)**2<1)&(c[:,0]>.22)
keep=~(eye_regions[0]|eye_regions[1]|mouth_region)
ret=f[keep]
# Delete detached scraps of the old lashes and generated eye surface.
parent=np.arange(len(v),dtype=np.int32)
def root(i):
    while parent[i]!=i:
        parent[i]=parent[parent[i]];i=parent[i]
    return i
for a,b,c in ret:
    a,b,c=root(a),root(b),root(c)
    parent[b]=a;parent[c]=a
roots=np.array([root(i) for i in range(len(v))]);u,cnt=np.unique(roots[ret].ravel(),return_counts=True)
main=u[np.argmax(cnt)];ret=ret[roots[ret[:,0]]==main]
used,inv=np.unique(ret,return_inverse=True)
v=v[used].astype(float);f=inv.reshape(-1,3)
edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
edges,counts=np.unique(edges,axis=0,return_counts=True)
boundary=edges[counts==1]
adj={}
for a,b in boundary:
    adj.setdefault(int(a),[]).append(int(b));adj.setdefault(int(b),[]).append(int(a))
loops=[];remaining=set(adj)
while remaining:
    start=min(remaining);order=[start];prev=-1;cur=start
    for iteration in range(len(adj)+1):
        choices=[i for i in adj[cur] if i!=prev]
        if not choices:break
        nxt=choices[0]
        if nxt==start:break
        if nxt in order:break
        order.append(nxt);prev,cur=cur,nxt
    remaining.difference_update(order)
    loops.append(np.array(order,dtype=int))
log['cut_boundary_lengths']=[len(x) for x in loops]
print('BOUNDARIES',log['cut_boundary_lengths'],flush=True)
if '--diagnose' in sys.argv:
    for loop in loops:
        center=v[loop].mean(0)
        if center[2]<-.17:angle=np.arctan2((v[loop,2]+.273)/.058,v[loop,1]/.164)
        else:angle=np.arctan2((v[loop,2]+.008)/.100,(np.sign(center[1])*v[loop,1]-eyeC)/.128)
        diff=np.diff(np.unwrap(np.r_[angle,angle[0]]))
        print('LOOP',len(loop),'CENTER',center,'POS_NEG',sum(diff>0),sum(diff<0),'DIFFMAX',max(abs(diff)),flush=True)
    raise SystemExit(0)

verts=v.tolist();faces=f.tolist();material_ids=[0]*len(f)
# Per-vertex anatomy tags allow corrections to stay local.
tags=[None]*len(v)
def eye_front(y,z,sign):
    dy=y-sign*eyeC;dz=z+.005
    q=1-(dy/.130)**2-(dz/.112)**2
    return .170+.100*math.sqrt(max(0,q))-.40*sign*dy
def eye_inner(theta,sign,blink=0):
    y=sign*(eyeC+.103*math.cos(theta));q=math.cos(theta);s=math.sin(theta)
    middle=-.030+.26*.103*q
    opened=middle+(.081*s if s>=0 else .040*s)
    closed=middle+.008*(1-q*q)
    z=opened+(closed-opened)*blink
    return np.array([eye_front(y,z,sign)+.003,y,z])
def addface(indices,material=0):faces.append(list(map(int,indices)));material_ids.append(material)
def regular_angles(values):
    """Keep cyclic boundary order while removing backwards angular folds."""
    raw=np.unwrap(values)
    direction=1 if raw[-1]>raw[0] else -1
    targets=np.r_[raw*direction,raw[0]*direction+2*math.pi]
    blocks=[]
    for i,value in enumerate(targets):
        weight=1e6 if i in [0,len(targets)-1] else 1.0
        blocks.append([i,i,float(value),weight])
        while len(blocks)>1 and blocks[-2][2]>blocks[-1][2]:
            b=blocks.pop();a=blocks.pop();w=a[3]+b[3]
            blocks.append([a[0],b[1],(a[2]*a[3]+b[2]*b[3])/w,w])
    result=np.empty(len(targets))
    for a,b,value,_ in blocks:result[a:b+1]=value
    result+=np.arange(len(result))*.0005
    result=(result-result[0])*(2*math.pi/(result[-1]-result[0]))+targets[0]
    return result[:-1]*direction
eye_metadata={}
for sign in [1,-1]:
    candidates=[loop for loop in loops if np.mean(v[loop,0])>.1 and np.mean(v[loop,2])>-.14 and sign*np.mean(v[loop,1])>.06]
    loop=max(candidates,key=len)
    theta=regular_angles(np.arctan2((v[loop,2]+.008)/.112,(sign*v[loop,1]-eyeC)/.146))
    # Boundary vertices stay shared with the surrounding face.
    for j,index in enumerate(loop):
        y=sign*(eyeC+.146*math.cos(theta[j]));z=-.008+.112*math.sin(theta[j])
        verts[index]=[surface(y,z),y,z]
    outer=np.array([verts[i] for i in loop]);prev=loop.copy();innerloop=None
    for ring in range(1,11):
        t=ring/10;current=[]
        for j,ang in enumerate(theta):
            inner=eye_inner(ang,sign)
            p=outer[j]*(1-t)+inner*t
            p[0]+=.007*math.sin(math.pi*t)
            inside=1-((p[1]-sign*eyeC)/.130)**2-((p[2]+.005)/.112)**2
            if inside>0:p[0]=max(p[0],eye_front(p[1],p[2],sign)+.002)
            index=len(verts);verts.append(p.tolist());tags.append(('eye',sign,float(t),float(ang),outer[j].tolist()))
            current.append(index)
        current=np.array(current)
        for j in range(len(loop)):
            k=(j+1)%len(loop);addface([prev[j],prev[k],current[k],current[j]])
        prev=current
    eye_metadata[str(sign)]={'inner_loop':prev.tolist(),'outer_loop':loop.tolist()}

mouth_candidates=[loop for loop in loops if np.mean(v[loop,0])>.22 and np.mean(v[loop,2])<-.17]
mouth_loop=max(mouth_candidates,key=len)
mouth_theta=regular_angles(np.arctan2((v[mouth_loop,2]+.273)/.058,v[mouth_loop,1]/.164))
for j,index in enumerate(mouth_loop):
    y=.164*math.cos(mouth_theta[j]);z=-.273+.058*math.sin(mouth_theta[j]);verts[index]=[surface(y,z),y,z]
outer=np.array([verts[i] for i in mouth_loop]);prev=mouth_loop.copy()
for ring in range(1,11):
    t=ring/10;current=[]
    for j,ang in enumerate(mouth_theta):
        y=.139*math.cos(ang);s=math.sin(ang);z=-.274+1.5*y*y+.0012*s
        inner=np.array([.346-2.75*y*y,y,z]);p=outer[j]*(1-t)+inner*t
        p[0]+=(.007 if s<0 else .005)*math.exp(-((t-.76)/.22)**2)
        index=len(verts);verts.append(p.tolist());tags.append(('mouth',float(t),float(ang)))
        current.append(index)
    current=np.array(current)
    for j in range(len(prev)):
        k=(j+1)%len(prev);addface([prev[j],prev[k],current[k],current[j]])
    prev=current
lip_loop=prev.copy()
# Connected lip thickness and oral bag: no opaque closed mouth wall remains.
for ring in range(1,7):
    t=ring/6;current=[]
    for j,ang in enumerate(mouth_theta):
        rim=np.array(verts[lip_loop[j]])
        rear=np.array([.175,.115*math.cos(ang),-.276+.064*math.sin(ang)])
        p=rim*(1-t)+rear*t
        current.append(len(verts));verts.append(p.tolist());tags.append(('oral',float(ang)))
    for j in range(len(prev)):
        k=(j+1)%len(prev);addface([prev[j],prev[k],current[k],current[j]],1)
    prev=np.array(current)
backcenter=len(verts);verts.append([.168,0,-.276]);tags.append(('oral',0.0))
for j in range(len(prev)):addface([prev[j],prev[(j+1)%len(prev)],backcenter],1)

mesh=bpy.data.meshes.new('Face_Skin_Stitched_Geometry');mesh.from_pydata(verts,[],faces);mesh.update()
old=head.data;head.data=mesh;bpy.data.meshes.remove(old)
mesh.materials.append(skin);mesh.materials.append(oralmat)
for p,mid in zip(mesh.polygons,material_ids):p.material_index=mid;p.use_smooth=True
bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
base=np.array(verts,dtype=np.float32)
# Smooth a narrow mask across the shared patch borders, keeping silhouette and rims.
edge_array=np.empty(len(mesh.edges)*2,dtype=np.int32);mesh.edges.foreach_get('vertices',edge_array);edge_array=edge_array.reshape(-1,2)
re=np.sqrt(((np.abs(base[:,1])-eyeC)/.146)**2+((base[:,2]+.008)/.112)**2)
rm=np.sqrt((base[:,1]/.164)**2+((base[:,2]+.273)/.058)**2)
mask=np.maximum(np.exp(-((re-1)/.17)**4)*(base[:,0]>.12),np.exp(-((rm-1)/.24)**4)*(base[:,0]>.22))
for i,tag in enumerate(tags):
    if tag and tag[0]=='oral':mask[i]=0
    if tag and tag[0] in ['eye','mouth']:
        t=tag[2] if tag[0]=='eye' else tag[1]
        mask[i]*=1-float(smooth01((t-.25)/.25))
degree=np.bincount(edge_array.ravel(),minlength=len(base))
for iteration in range(12):
    sums=np.zeros_like(base);np.add.at(sums,edge_array[:,0],base[edge_array[:,1]]);np.add.at(sums,edge_array[:,1],base[edge_array[:,0]])
    avg=sums/np.maximum(degree,1)[:,None];base+=(avg-base)*mask[:,None]*.48
mesh.vertices.foreach_set('co',base.ravel());mesh.update()

# Pigment masks are sampled from the approved head image, not rough rectangles.
ref=bpy.data.images.load(str(ROOT/'art/references/explorer_b_modular_v1/final_images/01_head.png'))
iw,ih=ref.size;pixels=np.empty(iw*ih*4,dtype=np.float32);ref.pixels.foreach_get(pixels);pixels=pixels.reshape(ih,iw,4)[::-1]
py=np.clip(np.rint(562-922*base[:,2]).astype(int),0,ih-1)
px=np.clip(np.rint(655+911*base[:,1]).astype(int),0,iw-1)
sample=pixels[py,px,:3]
lum=sample.mean(1)
for ox,oy in [(-6,0),(6,0),(0,-6),(0,6),(-4,-4),(4,4),(-4,4),(4,-4)]:
    lum=np.minimum(lum,pixels[np.clip(py+oy,0,ih-1),np.clip(px+ox,0,iw-1),:3].mean(1))
browmask=smooth01((.54-lum)/.21)*((py>390)&(py<493)&(base[:,0]>.15)&(np.abs(base[:,1])>.060))
browmask*=base[:,2]>.095
for i,tag in enumerate(tags):
    if tag and tag[0]=='eye':browmask[i]=0
colors=np.tile(np.array([.53,.285,.16,1],dtype=np.float32),(len(base),1))
colors[:,:3]=colors[:,:3]*(1-browmask[:,None])+np.array([.038,.016,.007])*browmask[:,None]
blush=np.exp(-((np.abs(base[:,1])-.23)/.09)**2-((base[:,2]+.14)/.09)**2)*(base[:,0]>.1)*.12
colors[:,:3]=colors[:,:3]*(1-blush[:,None])+np.array([.57,.225,.145])*blush[:,None]
for i,tag in enumerate(tags):
    if tag and tag[0]=='mouth':
        t,ang=tag[1:];w=float(smooth01((t-.48)/.40))*.55
        colors[i,:3]=colors[i,:3]*(1-w)+np.array([.40,.155,.105])*w
    elif tag and tag[0]=='eye':
        t=tag[2];w=max(0,(t-.9)/.1)*.30
        colors[i,:3]=colors[i,:3]*(1-w)+np.array([.43,.17,.12])*w
attribute=mesh.color_attributes.new(name='FacePigment',type='FLOAT_COLOR',domain='POINT');attribute.data.foreach_set('color',colors.ravel())
node=skin.node_tree.nodes.new('ShaderNodeVertexColor');node.layer_name='FacePigment'
skin.node_tree.links.new(node.outputs['Color'],skin.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])

controls=bpy.data.objects.new('FACE_CONTROLS',None);ctrlcol.objects.link(controls);controls.empty_display_type='CIRCLE';controls.empty_display_size=.03
controls.location=(0,-.24,.09)
for name in ['Blink_L','Blink_R','Jaw_Open','Smile','Brow_Raise']:
    controls[name]=0.0;controls.id_properties_ui(name).update(min=0,max=1,description=name+' / 0 neutral, 1 full test range')
def shape(o,name,coords):
    if not o.data.shape_keys:o.shape_key_add(name='Basis')
    key=o.shape_key_add(name=name);key.data.foreach_set('co',np.array(coords,dtype=np.float32).ravel());return key
def driver(key,prop,expression='v'):
    d=key.driver_add('value').driver;d.type='SCRIPTED';var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=controls;var.targets[0].data_path='["'+prop+'"]';d.expression=expression
def blink_coordinates(value,sign):
    result=base.copy()
    for i,tag in enumerate(tags):
        if not tag or tag[0]!='eye' or tag[1]!=sign:continue
        _,_,t,ang,out=tag;out=np.array(out);inner=eye_inner(ang,sign,value)
        p=out*(1-t)+inner*t;p[0]+=.007*math.sin(math.pi*t)
        inside=1-((p[1]-sign*eyeC)/.130)**2-((p[2]+.005)/.112)**2
        if inside>0:p[0]=max(p[0],eye_front(p[1],p[2],sign)+.002)
        opened=eye_inner(ang,sign,0);original=out*(1-t)+opened*t;original[0]+=.007*math.sin(math.pi*t)
        inside0=1-((original[1]-sign*eyeC)/.130)**2-((original[2]+.005)/.112)**2
        if inside0>0:original[0]=max(original[0],eye_front(original[1],original[2],sign)+.002)
        result[i]=base[i]+p-original
    return result
for sign,side in [(1,'L'),(-1,'R')]:
    closed=blink_coordinates(1,sign);half=blink_coordinates(.5,sign)
    driver(shape(head,'Blink_'+side,closed),'Blink_'+side)
    driver(shape(head,'BlinkArc_'+side,base+half-(base+closed)/2),'Blink_'+side,'4*v*(1-v)')
def jaw_rotate(coords,weights):
    p=np.array(coords,dtype=float);pivot=np.array([-.065,0,-.205]);angle=math.radians(12)
    rot=np.array([[math.cos(angle),0,math.sin(angle)],[0,1,0],[-math.sin(angle),0,math.cos(angle)]])
    moved=(p-pivot)@rot.T+pivot
    return p+(moved-p)*np.asarray(weights)[:,None]
seam=-.274+1.5*np.minimum(np.abs(base[:,1]),.14)**2
jawweights=smooth01((seam-base[:,2])/.062)*smooth01((base[:,0]-.02)/.22)*(1-smooth01((-.395-base[:,2])/.09))
for i,tag in enumerate(tags):
    if tag and tag[0]=='mouth':
        t,ang=tag[1:];inner=max(0,-math.sin(ang))**.55
        jawweights[i]=jawweights[i]*(1-t)+inner*t
    elif tag and tag[0]=='oral':jawweights[i]=max(0,-math.sin(tag[1]))**.55
driver(shape(head,'Jaw_Open',jaw_rotate(base,jawweights)),'Jaw_Open')
smile=base.copy();w=np.exp(-((np.abs(base[:,1])-.127)/.068)**2-((base[:,2]+.255)/.065)**2)*smooth01((base[:,0]-.15)/.15)
smile[:,1]+=np.sign(base[:,1])*.012*w;smile[:,2]+=.016*w
driver(shape(head,'Smile',smile),'Smile')
browup=base.copy();w=np.exp(-((np.abs(base[:,1])-.175)/.12)**4-((base[:,2]-.145)/.075)**4)*smooth01((base[:,0]-.12)/.12)
browup[:,2]+=.024*w;driver(shape(head,'Brow_Raise',browup),'Brow_Raise')

# Eyes: smooth independent sclera with a shaded iris, pupil and limbal ring.
eyemat=mat('Eye_Brown_Iris',(.85,.83,.75),.22)
n=eyemat.node_tree.nodes;l=eyemat.node_tree.links
tex=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tex.outputs['Generated'],sep.inputs[0])
def mathnode(op,a,b=None):
    m=n.new('ShaderNodeMath');m.operation=op
    for i,x in enumerate([a,b]):
        if x is None:continue
        if hasattr(x,'node'):l.new(x,m.inputs[i])
        else:m.inputs[i].default_value=x
    return m.outputs[0]
y=mathnode('SUBTRACT',sep.outputs['Y'],.5);z=mathnode('SUBTRACT',sep.outputs['Z'],.5)
r=mathnode('SQRT',mathnode('ADD',mathnode('MULTIPLY',y,y),mathnode('MULTIPLY',z,z)))
ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='EASE'
stops=[(0,(.005,.003,.002,1)),(.105,(.005,.003,.002,1)),(.125,(.095,.034,.008,1)),(.17,(.19,.08,.025,1)),(.235,(.062,.022,.006,1)),(.255,(.012,.006,.003,1)),(.270,(.83,.82,.74,1)),(1,(.83,.82,.74,1))]
for e in list(ramp.color_ramp.elements)[2:]:ramp.color_ramp.elements.remove(e)
ramp.color_ramp.elements[0].position=stops[0][0];ramp.color_ramp.elements[0].color=stops[0][1]
ramp.color_ramp.elements[1].position=stops[-1][0];ramp.color_ramp.elements[1].color=stops[-1][1]
for pos,color in stops[1:-1]:ramp.color_ramp.elements.new(pos).color=color
l.new(r,ramp.inputs[0])
angle=mathnode('ARCTAN2',z,y);striations=mathnode('SINE',mathnode('ADD',mathnode('MULTIPLY',angle,105),mathnode('MULTIPLY',r,40)))
factor=mathnode('ADD',.90,mathnode('MULTIPLY',striations,.10))
factor=mathnode('ADD',1,mathnode('MULTIPLY',mathnode('SUBTRACT',factor,1),mathnode('LESS_THAN',r,.26)))
mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.8;l.new(ramp.outputs[0],mix.inputs[1]);l.new(factor,mix.inputs[2])
l.new(mix.outputs[0],n.get('Principled BSDF').inputs['Base Color'])
def meshobject(name,vertices,polygons,collection,material):
    m=bpy.data.meshes.new(name+'_Geometry');m.from_pydata(vertices,[],polygons);m.update();o=bpy.data.objects.new(name,m);collection.objects.link(o);m.materials.append(material)
    for p in m.polygons:p.use_smooth=True
    return o
for sign,side in [(1,'L'),(-1,'R')]:
    ev=[];ef=[];rings=80;segments=160
    for a in range(rings+1):
        theta=math.pi*a/rings
        for j in range(segments):
            phi=2*math.pi*j/segments;dy=.130*math.sin(theta)*math.cos(phi);dz=.112*math.sin(theta)*math.sin(phi)
            ev.append([.170+.100*math.cos(theta)-.40*sign*dy,sign*eyeC+dy,-.005+dz])
    for a in range(rings):
        for j in range(segments):
            k=(j+1)%segments;ef.append([a*segments+j,a*segments+k,(a+1)*segments+k,(a+1)*segments+j])
    eye=meshobject('Eye_'+side,ev,ef,facecol,eyemat)
    # Transfer the procedural pigment to vertex colors for portable GLB materials.
    e=np.array(ev);ey=(e[:,1]-sign*eyeC)/.260;ez=(e[:,2]+.005)/.224
    radius=np.sqrt(ey*ey+ez*ez);rgb=np.zeros((len(e),4),dtype=np.float32);rgb[:,3]=1
    for k in range(len(stops)-1):
        lo,ca=stops[k];hi,cb=stops[k+1];mask=(radius>=lo)&(radius<=hi)
        weight=smooth01((radius[mask]-lo)/(hi-lo))[:,None]
        rgb[mask]=np.array(ca)*(1-weight)+np.array(cb)*weight
    detail=.90+.10*np.sin(np.arctan2(ez,ey)*105+radius*40)
    detail=np.where(radius<.26,.2+.8*detail,1)
    rgb[:,:3]*=detail[:,None]
    pigment=eye.data.color_attributes.new(name='EyePigment',type='FLOAT_COLOR',domain='POINT');pigment.data.foreach_set('color',rgb.ravel())
    if 'Eye_Pigment_Portable' not in bpy.data.materials:
        portable=mat('Eye_Pigment_Portable',(.8,.8,.75),.22)
        node=portable.node_tree.nodes.new('ShaderNodeVertexColor');node.layer_name='EyePigment'
        portable.node_tree.links.new(node.outputs['Color'],portable.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    eye.data.materials.clear();eye.data.materials.append(bpy.data.materials['Eye_Pigment_Portable'])
    # Upper lash follows the same anatomical edge and blink arc.
    def lashcoords(blink):
        points=[]
        for j in range(97):
            angle=math.pi*j/96;inner=eye_inner(angle,sign,blink)
            oy=sign*(eyeC+.146*math.cos(angle));oz=-.008+.112*math.sin(angle)
            outer=np.array([surface(oy,oz),oy,oz])
            width=(.20*math.sin(angle)**.5+.020)*(1-.65*blink)
            for edge in [0,1]:
                t=1-width*edge;q=outer*(1-t)+inner*t;q[0]+=.007*math.sin(math.pi*t)
                inside=1-((q[1]-sign*eyeC)/.130)**2-((q[2]+.005)/.112)**2
                if inside>0:q[0]=max(q[0],eye_front(q[1],q[2],sign)+.002)
                q[0]+=.0015
                points.append(q.tolist())
        return np.array(points)
    lv=lashcoords(0);lf=[[j*2,j*2+1,j*2+3,j*2+2] for j in range(96)]
    lash=meshobject('Upper_Lash_'+side,lv.tolist(),lf,facecol,lashmat)
    full=lashcoords(1);half=lashcoords(.5)
    driver(shape(lash,'Blink_'+side,full),'Blink_'+side)
    driver(shape(lash,'BlinkArc_'+side,lv+half-(lv+full)/2),'Blink_'+side,'4*v*(1-v)')

# Reusable upper/lower dental arches, not an array of identical boxes.
def relocate(o,collection):
    for c in list(o.users_collection):c.objects.unlink(o)
    collection.objects.link(o)
def ellipsoid(name,p,r,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=p)
    o=bpy.context.object;o.name=name;o.scale=r;activate(o);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);relocate(o,oralcol);o.data.materials.append(material)
    for f in o.data.polygons:f.use_smooth=True
    return o
lowerparts=[]
for upper in [True,False]:
    label='Upper' if upper else 'Lower';z=-.247 if upper else -.296
    arch=ellipsoid(label+'_Gum',(.258,0,z),(.045,.106,.017),gummat)
    if not upper:lowerparts.append(arch)
    pieces=[]
    for i in range(8):
        y=(i-3.5)*.0235;x=.318-4.1*y*y
        width=.023 if i in [3,4] else .0205
        height=.027 if upper else .023
        bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,z+(-.013 if upper else .012)))
        o=bpy.context.object;o.scale=(.018,width,height);activate(o);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        o.rotation_euler.z=-math.atan(8.2*y)
        bevel=o.modifiers.new('Soft enamel corners','BEVEL');bevel.width=.004;bevel.segments=4;bpy.ops.object.modifier_apply(modifier=bevel.name)
        o.data.materials.append(toothmat);relocate(o,oralcol);pieces.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in pieces:o.select_set(True)
    bpy.context.view_layer.objects.active=pieces[0];bpy.ops.object.join();pieces[0].name=label+'_Dental_Arch'
    if not upper:lowerparts.append(pieces[0])
tongue=ellipsoid('Tongue',(.265,0,-.316),(.046,.072,.012),tonguemat);lowerparts.append(tongue)
for o in lowerparts:
    # Apply object location into the mesh, so all jaw transforms use the same pivot.
    activate(o);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    ov,_=arrays(o);driver(shape(o,'Jaw_Open',jaw_rotate(ov,np.ones(len(ov)))),'Jaw_Open')

# Conform the actual hair shell to the scalp; no smooth cover cap is added.
hair=load('hair',haircol);hair.name='Hair_Fitted'
hv,hf=arrays(hair);hv=hv*np.array([1.25,1.035,1.02])+np.array([.020,0,.110])
center=Vector((-.11,0,.12));changed=0
for i,p in enumerate(hv):
    if p[2]<-.14:continue
    d=Vector(p)-center;r=d.length
    if r<1e-6:continue
    d.normalize();hit=bvh.ray_cast(center,d)
    if not hit[0]:continue
    target=hit[3]+.018
    delta=r-target
    newr=target+.022*math.log1p(math.exp(min(30,delta/.022)))
    weight=float(smooth01((p[2]+.14)/.22))
    if (newr-r)*weight>.0003:changed+=1
    hv[i]=np.array(center+d*(r+(newr-r)*weight))
hair.data.vertices.foreach_set('co',hv.astype(np.float32).ravel());hair.data.update();hair.data.materials.clear();hair.data.materials.append(hairmat)
log['hair_vertices_conformed']=changed

# Work in head-local units until all shape keys are built. Uniform object scale is reusable.
SCALE=.3477
for o in list(facecol.objects)+list(haircol.objects)+list(oralcol.objects):
    o.location*=SCALE;o.scale*=SCALE;o.hide_select=False;o.hide_set(False)
    o['asset_stage']='Facial reconstruction and deformation study v2'
head['production_retopology']=False
head['new_geometry']='Connected eyelid quad bands, lip bands, lip thickness and oral bag'
controls.hide_render=True

# Timeline: neutral -> blink -> left wink -> jaw opening -> smile -> neutral.
events={1:{},14:{},19:{'Blink_L':1,'Blink_R':1},24:{},38:{},44:{'Blink_L':1},50:{},64:{},84:{'Jaw_Open':.80,'Brow_Raise':.25},98:{'Jaw_Open':.80,'Brow_Raise':.25},112:{},127:{'Smile':.8,'Brow_Raise':.22},136:{'Smile':.8,'Brow_Raise':.22},144:{}}
for frame,values in events.items():
    for name in ['Blink_L','Blink_R','Jaw_Open','Smile','Brow_Raise']:
        controls[name]=values.get(name,0.0);controls.keyframe_insert(data_path='["'+name+'"]',frame=frame)
scene.frame_start=1;scene.frame_end=144;scene.render.fps=24;scene.frame_set(1)
for frame,label in [(1,'Neutral'),(19,'Blink'),(44,'Left wink'),(84,'Jaw open'),(127,'Smile'),(144,'Neutral / loop')]:scene.timeline_markers.new(label,frame=frame)

scene.render.engine='CYCLES';scene.cycles.samples=24 if FAST else 48;scene.cycles.use_denoising=True
try:
    pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='CUDA';pref.get_devices()
    for d in pref.devices:d.use=d.type=='CUDA'
    if any(d.use for d in pref.devices):scene.cycles.device='GPU'
except Exception:pass
world=bpy.data.worlds.new('Neutral_Studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.32,.37,.42,1);world.node_tree.nodes['Background'].inputs[1].default_value=.35;scene.world=world
target=Vector((.01,0,.0))
for name,position,power,size in [('Key',(1,-.9,1.3),75,.75),('Fill',(1,1,.4),35,1.0),('Rim',(-.6,.6,1),65,.6)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.size=size;o=bpy.data.objects.new(name,data);studio.objects.link(o);o.location=position;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();o.hide_select=True;o.hide_set(True)
cam=bpy.data.objects.new('Review_Camera',bpy.data.cameras.new('Review_Camera'));studio.objects.link(cam);cam.data.type='ORTHO';scene.camera=cam;cam.hide_select=True;cam.hide_set(True)
scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
def camera(offset,scale=.405):
    cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name,offset=(3,0,0),frame=1,hair_visible=True):
    scene.frame_set(frame);hair.hide_render=not hair_visible;camera(offset)
    scene.render.resolution_x=800 if FAST else 1200;scene.render.resolution_y=scene.render.resolution_x;scene.render.resolution_percentage=100
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
render('front-neutral')
render('front-bare',hair_visible=False)
render('angle-neutral',(3,-1.4,.1))
render('side-neutral',(.12,-3,0))
render('blink-closed',frame=19,hair_visible=False)
render('mouth-open',frame=84,hair_visible=False)
render('angle-mouth-open',(3,-1.4,.1),frame=84)
hair.hide_render=False;scene.frame_set(1);camera((3,-.9,.05));activate(head)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_floor=False
            sp.region_3d.view_location=target;sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_distance=.8;sp.region_3d.view_perspective='ORTHO'
        if area.type=='PROPERTIES':area.spaces.active.context='DATA'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_b_face_refined_v2.blend'))
log.update({'face_vertices':len(head.data.vertices),'face_polygons':len(head.data.polygons),'shape_keys':[k.name for k in head.data.shape_keys.key_blocks],'objects':[o.name for o in scene.objects if o.type=='MESH'],
 'notes':['Working skin outside new loop bands remains triangulated; not final production retopology.','New mouth opening and interior are connected to the facial skin.','Source head and hair files are unchanged.','No body assembly or Godot deployment in this face study.']})
(OUT/'build-report.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
np.savez_compressed(OUT/'deformation-check-data.npz',base=base,jaw=jaw_rotate(base,jawweights),**{'blink'+str(s):blink_coordinates(1,s) for s in [1,-1]})
print('FACE_V2_READY',flush=True)
