"""Reference-led, textured archipelago terrain. Run using the bundled Blender."""
import bpy, math, json, random, sys
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v3'
LAB=ROOT/'labs/terrain_lab/assets'
CACHED_TEXTURES='--reuse-textures' in sys.argv
OUT.mkdir(parents=True,exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
random.seed(206)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC'
scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True

def ss(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)
def lin(c):
    c=np.asarray(c);return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
def noise(x,y,s=1,seed=0):
    x=x*s+seed*17.1;y=y*s+seed*9.7
    ix=np.floor(x);iy=np.floor(y);fx=ss(0,1,x-ix);fy=ss(0,1,y-iy)
    def h(a,b):return np.mod(np.sin(a*127.1+b*311.7+seed*74.7)*43758.5453,1)
    return (h(ix,iy)*(1-fx)+h(ix+1,iy)*fx)*(1-fy)+(h(ix,iy+1)*(1-fx)+h(ix+1,iy+1)*fx)*fy
def catmull(points,closed=False,steps=12):
    p=[np.array(a,dtype=float) for a in points];result=[]
    for i in range(len(p) if closed else len(p)-1):
        a=p[(i-1)%len(p)] if closed or i else p[0]
        b=p[i];c=p[(i+1)%len(p)]
        d=p[(i+2)%len(p)] if closed else p[min(i+2,len(p)-1)]
        for t in np.linspace(0,1,steps,endpoint=False):
            result.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t**3))
    if not closed:result.append(p[-1])
    return np.array(result)
def distance(x,y,line,closed=False):
    result=np.full(np.broadcast(x,y).shape,1e6);inside=np.zeros(result.shape,dtype=bool)
    pairs=zip(line,np.roll(line,-1,axis=0)) if closed else zip(line[:-1],line[1:])
    for a,b in pairs:
        v=b-a;den=np.dot(v,v)
        t=np.clip(((x-a[0])*v[0]+(y-a[1])*v[1])/max(den,1e-8),0,1)
        result=np.minimum(result,np.hypot(x-a[0]-t*v[0],y-a[1]-t*v[1]))
        if closed:
            cross=((a[1]>y)!=(b[1]>y)) & (x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1]+1e-20)+a[0])
            inside^=cross
    return np.where(inside,result,-result) if closed else result
def upsample(a,n):
    old=np.linspace(0,1,a.shape[1]);new=np.linspace(0,1,n)
    temp=np.array([np.interp(new,old,row) for row in a])
    return np.array([np.interp(new,np.linspace(0,1,a.shape[0]),row) for row in temp.T]).T
def texture(name,rgb,noncolor=False):
    path=OUT/'textures'/f'{name}.png'
    if CACHED_TEXTURES and path.exists():
        image=bpy.data.images.load(str(path),check_existing=True)
        if noncolor:image.colorspace_settings.name='Non-Color'
        image.pack();return image
    rgb=np.clip(rgb,0,1).astype(np.float32)
    image=bpy.data.images.new(name,width=rgb.shape[1],height=rgb.shape[0],alpha=True)
    if noncolor:image.colorspace_settings.name='Non-Color'
    rgba=np.dstack((rgb,np.ones(rgb.shape[:2],dtype=np.float32)))
    image.pixels.foreach_set(rgba.ravel());image.filepath_raw=str(OUT/'textures'/f'{name}.png')
    image.file_format='PNG';image.save();image.pack();return image
def normal_texture(name,height,bounds):
    xmin,ymin,xmax,ymax=bounds
    dy,dx=np.gradient(height,(ymax-ymin)/(height.shape[0]-1),(xmax-xmin)/(height.shape[1]-1))
    normals=np.stack((-dx,-dy,np.ones_like(dx)),axis=-1)
    normals/=np.linalg.norm(normals,axis=-1)[...,None]
    return texture(name,normals*.5+.5,True)
def add_normal(material,image,strength=1):
    nodes=material.node_tree.nodes;links=material.node_tree.links
    tex=nodes.new('ShaderNodeTexImage');tex.image=image
    normal=nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=strength
    links.new(tex.outputs['Color'],normal.inputs['Color'])
    links.new(normal.outputs['Normal'],nodes.get('Principled BSDF').inputs['Normal'])
def mat(name,color,rough=.8,image=None):
    m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*lin(color),1);p.inputs['Roughness'].default_value=rough
    p.inputs['Specular IOR Level'].default_value=.25;m.diffuse_color=(*lin(color),1)
    if image:
        tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
        m.node_tree.links.new(tex.outputs['Color'],p.inputs['Base Color'])
    return m
def mesh(name,vs,fs,material,uv_bounds=None,smooth=True):
    d=bpy.data.meshes.new(name);d.from_pydata(vs,[],fs);d.update()
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);d.materials.append(material)
    for p in d.polygons:p.use_smooth=smooth
    if uv_bounds:
        xmin,ymin,xmax,ymax=uv_bounds;layer=d.uv_layers.new(name='SurfaceMap')
        for p in d.polygons:
            for j in p.loop_indices:
                v=d.vertices[d.loops[j].vertex_index].co
                layer.data[j].uv=((v.x-xmin)/(xmax-xmin),(v.y-ymin)/(ymax-ymin))
    return o

ISLANDS=[
 dict(id='01_village_meadow',center=(-42,42),base=2.05,outline=[(-81,35),(-73,51),(-56,63),(-35,67),(-16,62),(-5,48),(-6,32),(-19,19),(-43,17),(-63,20),(-77,26)],
      paths=[[(-73,30),(-57,33),(-45,34),(-29,43),(-7,44)],[(-48,34),(-56,42),(-55,53)],[(-28,42),(-25,30),(-37,24)]]),
 dict(id='02_garden_headland',center=(46,34),base=2.35,outline=[(9,43),(17,57),(35,66),(56,63),(74,54),(85,36),(87,20),(79,7),(58,1),(39,2),(19,9),(9,23)],pond=(51,43,9,7,1.35),
      paths=[[(10,43),(27,40),(36,32),(43,19),(62,11),(80,12)],[(27,40),(26,51),(40,57)],[(36,32),(50,29),(63,36),(70,47)]]),
 dict(id='03_town_common',center=(-40,-29),base=2.65,outline=[(-84,-35),(-80,-17),(-67,-5),(-46,1),(-27,5),(-13,9),(-9,16),(-3,15),(2,7),(-3,-6),(0,-19),(-7,-33),(-15,-47),(-19,-61),(-35,-71),(-54,-70),(-73,-58),(-83,-44)],pond=(-48,-44,12,9,1.18),
      paths=[[(-65,-55),(-58,-28),(-46,-23),(-30,-23),(-14,-28),(-3,-20)],[(-30,-23),(-31,-9),(-39,-2)],[(-30,-23),(-18,-37),(-20,-51),(-25,-62)],[(-11,-1),(-17,-13),(-25,-22)]]),
 dict(id='04_camp_meadow',center=(49,-37),base=1.8,outline=[(19,-15),(16,-7),(12,0),(7,8),(8,16),(14,16),(21,6),(27,-7),(43,-9),(60,-7),(77,-16),(87,-31),(86,-50),(75,-64),(55,-70),(36,-66),(20,-54),(13,-38),(9,-28),(13,-21)],
      paths=[[(11,13),(15,3),(23,-12),(22,-25),(27,-39),(44,-48),(66,-57)],[(22,-25),(34,-19),(48,-20),(62,-30)],[(44,-48),(58,-36),(70,-32)]]),
 dict(id='05_lighthouse_islet',center=(7,-78),base=1.7,outline=[(-4,-76),(0,-69),(9,-69),(17,-75),(18,-83),(10,-88),(1,-86),(-5,-81)],
      paths=[[(0,-74),(5,-76),(8,-80)]]),
]
for island in ISLANDS:
    island['paths']=[]
    island['contour']=catmull(island['outline'],True)
    island['lines']=[catmull(p) for p in island['paths']]

def pondq(x,y,p):
    px,py,rx,ry,level=p;u=(x-px)/rx;v=(y-py)/ry;a=np.arctan2(v,u)
    return np.hypot(u,v)/(1+.09*np.sin(3*a+.7)+.05*np.cos(5*a))
def terrain_height(x,y,island,d=None):
    if d is None:d=distance(np.asarray(x),np.asarray(y),island['contour'],True)
    z=-.7+.95*ss(-1.5,.65,d)+(island['base']-.25)*ss(.8,4.3,d)
    cx,cy=island['center']
    z+=(1-ss(6,1,d))*(.46*np.exp(-((x-cx+6)**2/240+(y-cy-9)**2/160))
            +.12*(noise(x,y,.07,2)-.5)+.09*(noise(x,y,.35,3)-.5)+.025*(noise(x,y,1.6,8)-.5))
    if 'pond' in island:
        q=pondq(x,y,island['pond']);mix=ss(.86,1.25,q)
        z=z*mix+(island['pond'][4]-.75)*(1-mix)
    if island['id'].startswith('03'):
        # A raised rocky headland and a compact round spring replace the long strip.
        plateau=np.hypot((x+2.5)/4.5,(y-10.3)/3.4)
        z=np.maximum(z,3.72*(1-ss(.83,1.13,plateau)))
        q=np.hypot((x+3)/2.8,(y-10)/1.9)
        carve=1-ss(.74,1.2,q)
        z=z*(1-carve)+2.95*carve
        # Only the short curved outlet is inset. The receiving channel is cut
        # below sea level so the fall does not terminate on a sand slope.
        lip_line=np.array([[-1.3,9.8],[.2,8.7]])
        lip_distance=distance(np.asarray(x),np.asarray(y),lip_line)
        inset=1-ss(.83,1.24,lip_distance)
        z=z*(1-inset)+3.02*inset
        downstream=(x-.2)*.72-(y-8.7)*.69
        lateral=(x-.2)*.69+(y-8.7)*.72
        cut=ss(-.03,.16,downstream)*(1-ss(1.15,1.9,np.abs(lateral)))
        z=z*(1-cut)-.5*cut
    return z

objects=[];grounds=[]
for island in ISLANDS:
    contour=island['contour'];lo=contour.min(axis=0)-3;hi=contour.max(axis=0)+3
    nx=int((hi[0]-lo[0])/.46)+1;ny=int((hi[1]-lo[1])/.46)+1
    gx,gy=np.meshgrid(np.linspace(lo[0],hi[0],nx),np.linspace(lo[1],hi[1],ny))
    sd=distance(gx,gy,contour,True);gz=terrain_height(gx,gy,island,sd)
    vs=np.stack((gx,gy,gz),axis=-1).reshape(-1,3).tolist();fs=[]
    for j in range(ny-1):
        for i in range(nx-1):
            if sd[j:j+2,i:i+2].max()<-2:continue
            a=j*nx+i;fs.extend([(a,a+1,a+nx+1),(a,a+nx+1,a+nx)])
    # A real UV surface texture replaces the blurry ring of vertex colours.
    n=2048;tx,ty=np.meshgrid(np.linspace(lo[0],hi[0],n),np.linspace(lo[1],hi[1],n))
    td=np.array([np.interp(np.linspace(lo[1],hi[1],n),np.linspace(lo[1],hi[1],ny),row) for row in
          np.array([np.interp(np.linspace(lo[0],hi[0],n),np.linspace(lo[0],hi[0],nx),row) for row in sd]).T]).T
    mottled=noise(tx,ty,.22,4)*.6+noise(tx,ty,.85,2)*.3+noise(tx,ty,3.2,7)*.1
    grass=np.stack((.46+.20*mottled,.67+.15*mottled,.19+.12*mottled),axis=-1)
    sand=np.stack((.91+.025*noise(tx,ty,4),.78+.045*noise(tx,ty,3),.51+.06*noise(tx,ty,2)),axis=-1)
    edge=ss(2.8,4.0,td+(noise(tx,ty,1.2,3)-.5)*.7)
    rgb=sand*(1-edge[...,None])+grass*edge[...,None]
    if 'pond' in island:
        q=pondq(tx,ty,island['pond']);edgepond=1-ss(1.04,1.20,q)
        soil=np.stack((.48+.06*mottled,.53+.08*mottled,.28+.04*mottled),axis=-1)
        rgb=rgb*(1-edgepond[...,None])+soil*edgepond[...,None]
    image=texture(island['id']+'_ground_color',rgb)
    gm=mat(island['id']+' / high resolution meadow and sand',(1,1,1),.9,image)
    microheight=(.045*noise(tx,ty,7,3)+.016*noise(tx,ty,18,7))*edge
    microheight+=(1-edge)*(.004*noise(tx,ty,15,9))
    add_normal(gm,normal_texture(island['id']+'_ground_normal',microheight,(*lo,*hi)),.7)
    obj=mesh(island['id']+'__ground',vs,fs,gm,(*lo,*hi));objects.append(obj);grounds.append(obj)
    print('GROUND_READY',island['id'],flush=True)

# World-space surface paintings contain both broad blue facets and small bright ripples.
sea_bounds=(-130,-115,130,110)
nx=220;ny=192
gx,gy=np.meshgrid(np.linspace(-130,130,nx),np.linspace(-115,110,ny))
shore=np.full(gx.shape,1e3)
for island in ISLANDS:shore=np.minimum(shore,np.abs(distance(gx,gy,island['contour'],True)))
n=4096;x,y=np.meshgrid(np.linspace(-130,130,n),np.linspace(-115,110,n))
ds=np.array([np.interp(np.linspace(-115,110,n),np.linspace(-115,110,ny),row) for row in
       np.array([np.interp(np.linspace(-130,130,n),np.linspace(-130,130,nx),row) for row in shore]).T]).T
facets=noise(x,y,.65,4)*.55+noise(x,y,1.6,8)*.30+noise(x,y,3.2,1)*.15
ripples=ss(.66,.93,noise(x+y*.35,y-x*.15,2.1,2))
crests=ss(.90,.998,.5+.5*np.sin(x*4.2+y*2.6+noise(x,y,.7,3)*14)) * ss(.44,.71,noise(x,y,1.0,9))
caustic=(1-ss(.025,.09,np.abs(np.sin(x*2.6+y*1.8+noise(x,y,.65)*7))))*.6
coast=1-ss(.2,8,ds)
rgb=np.stack((.035+.055*facets+.025*coast+.035*ripples,
              .55+.17*facets+.11*coast+.055*ripples+.025*caustic,
              .86+.10*facets+.025*ripples),axis=-1)
rgb=rgb*(1-crests[...,None]*.44)+np.array((.35,.91,1.0))*crests[...,None]*.44
wave_image=texture('ocean_surface_color',rgb)
water_mat=mat('Water / painted azure wave facets',(1,1,1),.27,wave_image)
wave_height=.085*np.sin(x*1.8+y*1.2+noise(x,y,.3,2)*3)*np.cos(x*.55-y*1.7)+.055*(noise(x,y,4.0,5)-.5)
add_normal(water_mat,normal_texture('ocean_surface_normal',wave_height,sea_bounds),.8)
vs=np.stack((gx,gy,np.zeros(gx.shape)),axis=-1).reshape(-1,3).tolist()
fs=[(j*nx+i,j*nx+i+1,(j+1)*nx+i+1,(j+1)*nx+i) for j in range(ny-1) for i in range(nx-1)]
objects.append(mesh('Ocean__textured_surface',vs,fs,water_mat,sea_bounds))
foam=mat('Foam / pearl white',(.85,.98,1),.75)
stone_mats=[mat('Granite / warm face '+str(i),(.49+i*.04,.53+i*.035,.55+i*.028),.86) for i in range(5)]

def curve_strip(name,line,z,width,material):
    vs=[];fs=[]
    for i,p in enumerate(line):
        tangent=line[min(i+1,len(line)-1)]-line[max(0,i-1)];tangent/=max(np.linalg.norm(tangent),1e-6)
        n=np.array([-tangent[1],tangent[0]])
        for sign in [-1,1]:vs.append((*list(p+n*width*.5*sign),z))
        if i:fs.append((2*i-2,2*i-1,2*i+1,2*i))
    return mesh(name,vs,fs,material)

# White curl shapes follow the coast; short secondary arcs create a foamy wash.
for island in ISLANDS:
    c=island['contour'];vs=[];fs=[]
    for i,p in enumerate(c):
        previous=c[(i-1)%len(c)];nxt=c[(i+1)%len(c)];t=nxt-previous;t/=np.linalg.norm(t)
        normal=np.array([t[1],-t[0]])
        # Determine outward normal independently of outline winding.
        if distance(np.asarray(p[0]+normal[0]),np.asarray(p[1]+normal[1]),c,True)>0:normal=-normal
        phase=i*.63;offset=.33+.13*math.sin(phase)
        if i%11 not in (7,8):
            q=p+normal*offset;half=.033+.012*math.sin(phase*1.3);idx=len(vs)
            for pp in [q-normal*half,q+normal*half,nxt+normal*(offset+half),nxt+normal*(offset-half)]:vs.append((*pp,.035))
            fs.append((idx,idx+1,idx+2,idx+3))
        if i%9==0:
            line=[]
            for a in np.linspace(-1,1,12):
                point=p+normal*(.8+.2*math.cos(a*math.pi))+t*a*.75;line.append(point)
            objects.append(curve_strip(island['id']+'__foam_curl',np.array(line),.04,.045,foam))
        if i%3==0:
            for j in range(3):
                q=p+normal*random.uniform(.3,1.1)+t*random.uniform(-.45,.45)
                radius=random.uniform(.035,.095);idx=len(vs)
                vs.append((*q,.043))
                for a in np.linspace(0,math.tau,9)[:-1]:vs.append((q[0]+radius*math.cos(a),q[1]+radius*math.sin(a),.043))
                for j in range(8):fs.append((idx,idx+j+1,idx+(j+1)%8+1))
    objects.append(mesh(island['id']+'__shore_wash',vs,fs,foam))

rock_meshes=[]
def rock(name,x,y,size,z=.0):
    # Chamfered vertical granite blocks match the reference's large planar faces.
    if len(rock_meshes)<4:
        bpy.ops.mesh.primitive_cube_add(size=1)
        template=bpy.context.object
        for v in template.data.vertices:
            v.co.x+=random.uniform(-.12,.12);v.co.y+=random.uniform(-.08,.08)
            if v.co.z>0:v.co.z+=random.uniform(-.18,.18)
        bevel=template.modifiers.new('Weathered corners','BEVEL');bevel.width=.15;bevel.segments=1
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        for m in stone_mats:template.data.materials.append(m)
        for p in template.data.polygons:p.material_index=random.randrange(5)
        data=template.data;data.use_fake_user=True;rock_meshes.append(data)
        bpy.data.objects.remove(template,do_unlink=True)
    o=bpy.data.objects.new(name,random.choice(rock_meshes));scene.collection.objects.link(o)
    o.location=(x,y,z+size*.47)
    o.scale=(size*random.uniform(.85,1.2),size*random.uniform(.7,1),size*random.uniform(.8,1.3))
    o.rotation_euler.z=random.uniform(0,math.tau)
    objects.append(o);return o

for island in ISLANDS:
    c=island['contour'];count=18 if not island['id'].startswith('05') else 8
    for k in range(count):
        idx=int((k+random.uniform(-.2,.2))*len(c)/count)%len(c);p=c[idx]
        for j in range(random.randint(3,6)):
            size=random.uniform(.65,2.0)
            rock(island['id']+'__shore_rock',p[0]+random.uniform(-1.6,1.6),p[1]+random.uniform(-1.4,1.4),size)
    # Gravel flecks along beaches, clustered rather than regularly spaced.
    for k in range(90 if count==18 else 20):
        p=c[random.randrange(len(c))];p=p*.98+np.array(island['center'])*.02
        z=float(terrain_height(p[0],p[1],island))
        rock(island['id']+'__beach_pebble',p[0],p[1],random.uniform(.10,.24),max(z,0))

for k,(x,y,size) in enumerate([(-98,58,2.7),(-86,83,3),(-13,83,2.5),(99,65,2.6),(95,-82,2.2),
    (100,-15,3),(-91,-76,2.2),(-99,-21,2),(-68,82,2.7),(-100,8,2.1),(94,0,2.2),(70,-92,2.3)]):
    for j in range(4):rock('Offshore__reef_rock',x+random.uniform(-1.5,1.5),y+random.uniform(-1.5,1.5),size*random.uniform(.45,1))
    a=np.linspace(0,math.tau,96)
    r=1+.09*np.sin(a*3+.5)+.055*np.cos(a*7)
    line=np.stack((x+(size*1.5)*r*np.cos(a),y+(size*1.1)*r*np.sin(a)),axis=-1)
    objects.append(curve_strip('Offshore__reef_foam',line,.04,.065,foam))

pxgrid,pygrid=np.meshgrid(np.linspace(0,18,2048),np.linspace(0,18,2048))
pn=noise(pxgrid,pygrid,.9,3)*.65+noise(pxgrid,pygrid,2.7,5)*.35
pond_rgb=np.stack((.025+.035*pn,.58+.15*pn,.80+.16*pn),axis=-1)
pond_image=texture('pond_surface_color',pond_rgb)
pond_water=mat('Pond / jewel blue',(1,1,1),.22,pond_image)
pond_height=.045*np.sin(pxgrid*2+pygrid*1.6)*np.cos(pxgrid*.7-pygrid*2.1)
add_normal(pond_water,normal_texture('pond_surface_normal',pond_height,(0,0,18,18)),.75)
leaf=mat('Plants / deep leaf',(.18,.46,.17))
leaf_light=mat('Plants / sunlit leaf',(.36,.61,.2))
reed_mat=mat('Reeds / fresh green',(.39,.56,.14))
flower=mat('Flowers / warm white',(.99,.94,.77))
pollen=mat('Flowers / golden heart',(.98,.77,.08))
pink=mat('Flowers / coral petals',(.93,.46,.41))

def ico(name,loc,scale,material,detail=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=detail,radius=1,location=loc)
    o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(material)
    for p in o.data.polygons:p.use_smooth=True
    objects.append(o);return o
def lily(x,y,z,r=.4):
    vs=[(x,y,z)]+[(x+r*math.cos(a),y+r*math.sin(a),z) for a in np.linspace(.13,math.tau-.13,20)]
    return mesh('Pond__lily_pad',vs,[(0,i,i+1) for i in range(1,len(vs)-1)],leaf_light)

for island in ISLANDS:
    if 'pond' not in island:continue
    px,py,rx,ry,level=island['pond']
    angles=np.linspace(0,math.tau,129)[:-1];vs=[(px,py,level)]
    for a in angles:
        r=1.30*(1+.09*math.sin(3*a+.7)+.05*math.cos(5*a));vs.append((px+rx*r*math.cos(a),py+ry*r*math.sin(a),level))
    objects.append(mesh(island['id']+'__pond',vs,[(0,k+1,(k+1)%128+1) for k in range(128)],pond_water,(px-rx*1.4,py-ry*1.4,px+rx*1.4,py+ry*1.4)))
    for i in range(22):
        a=random.uniform(0,math.tau);r=random.uniform(.35,.83);x=px+rx*r*math.cos(a);y=py+ry*r*math.sin(a)
        objects.append(lily(x,y,level+.026,random.uniform(.2,.46)))
        if i%5==0:
            for a in np.linspace(0,math.tau,6)[:-1]:
                ico('Pond__water_lily',(x+.1*math.cos(a),y+.1*math.sin(a),level+.075),(.1,.06,.045),pollen)
    for i in range(16):
        a=math.tau*i/16;r=1.18*(1+.09*math.sin(3*a+.7)+.05*math.cos(5*a))
        x=px+rx*r*math.cos(a);y=py+ry*r*math.sin(a);z=float(terrain_height(x,y,island))
        for j in range(5):
            h=random.uniform(.65,1.25);dx=random.uniform(-.3,.3);dy=random.uniform(-.3,.3)
            vertices=[(x+dx-.04,y+dy,z),(x+dx+.04,y+dy,z),(x+dx+random.uniform(-.3,.3),y+dy,h+z)]
            objects.append(mesh('Pond__reed_blade',vertices,[(0,1,2)],reed_mat,smooth=False))
        if i%3==0:
            for j in range(3):rock('Pond__bank_rock',x+random.uniform(-.4,.4),y+random.uniform(-.4,.4),random.uniform(.45,.95),z-.2)

# Water emerges from a compact spring behind a rock lip, then drops toward
# the channel. No long rectangular stream mesh is created.
spring_center=(-3,10);level=3.34
vs=[(*spring_center,level)]
for a in np.linspace(0,math.tau,97)[:-1]:
    r=1+.06*math.sin(a*3)
    vs.append((-3+2.65*r*math.cos(a),10+1.8*r*math.sin(a),level))
objects.append(mesh('Waterfall__spring_pool',vs,[(0,k+1,(k+1)%96+1) for k in range(96)],pond_water,(-6,8,0,12)))
lip_center=np.array((.2,8.7));direction=np.array((.72,-.69));side=np.array((.69,.72))
vs=[];fs=[]
for j in range(12):
    t=j/11;p=np.array((-1.3,9.8))*(1-t)+lip_center*t
    width=1.5+.65*t
    for i in range(12):
        u=i/11;q=p+side*(u-.5)*width
        vs.append((*q,level-.035*t))
        if i and j:a=j*12+i;fs.append((a-13,a-12,a,a-1))
objects.append(mesh('Waterfall__rounded_lip',vs,fs,pond_water,(-3,7,3,13)))
vs=[];fs=[];uvs=[]
for j in range(36):
    t=j/35;z=(level-.035)*(1-t)
    p=lip_center+direction*(.10+.75*t*t)
    width=2.15+.35*t+.10*math.sin(t*math.pi)
    for i in range(24):
        u=i/23;q=p+side*(u-.5)*width
        q+=direction*(.027*math.sin(u*math.tau*3+t*10))
        vs.append((*q,z));uvs.append((u,t))
        if i and j:a=j*24+i;fs.append((a-25,a-24,a,a-1))
fall=mesh('Waterfall__curtain',vs,fs,pond_water)
layer=fall.data.uv_layers.new(name='FallFlow')
for poly in fall.data.polygons:
    for index in poly.loop_indices:layer.data[index].uv=uvs[fall.data.loops[index].vertex_index]
objects.append(fall)
# Pale narrow strands make the editable source read as falling water as well.
for i in range(9):
    u=(i+.5)/9;p=lip_center+side*(u-.5)*2.05
    end=p+direction*.83
    objects.append(mesh('Waterfall__source_white_strand',[(p[0],p[1],3.26),(p[0]+.03,p[1]+.03,3.26),(end[0]+.03,end[1]+.03,.14),(end[0],end[1],.14)],[(0,1,2,3)],foam))
for x,y,size in [(-1.4,7.4,2.6),(-1.0,10.9,2.7),(.2,6.9,2.1),(1.7,10.2,2.0),(-3.8,7.3,2.2)]:
    rock('Waterfall__cliff_rock',x,y,size,.25)
impact_center=lip_center+direction*.86
vs=[(*impact_center,.052)];uvs=[(.5,.5)]
for a in np.linspace(0,math.tau,97)[:-1]:
    r=2.4*(1+.07*math.sin(a*5))
    vs.append((impact_center[0]+r*math.cos(a),impact_center[1]+r*.82*math.sin(a),.052))
    uvs.append((.5+.5*math.cos(a),.5+.5*math.sin(a)))
impact=mesh('Waterfall__impact_foam',vs,[(0,k+1,(k+1)%96+1) for k in range(96)],foam)
layer=impact.data.uv_layers.new(name='SplashFlow')
for poly in impact.data.polygons:
    for index in poly.loop_indices:layer.data[index].uv=uvs[impact.data.loops[index].vertex_index]
objects.append(impact)

star_mat=mat('Beach / red starfish',(.91,.30,.20))
for x,y in [(-65,-63),(-53,-68),(-30,-67),(71,-64),(82,-49)]:
    island=min(ISLANDS,key=lambda d:np.linalg.norm(np.array(d['center'])-np.array((x,y))))
    z=float(terrain_height(x,y,island))+.025
    if z<.15:continue
    vs=[(x,y,z+.08)]+[(x+( .32 if i%2==0 else .13)*math.cos(i*math.pi/5),y+(.32 if i%2==0 else .13)*math.sin(i*math.pi/5),z) for i in range(10)]
    objects.append(mesh('Beach__starfish',vs,[(0,i+1,(i+1)%10+1) for i in range(10)],star_mat))

# Batch small details by material after retaining named collections in the .blend.
world=bpy.data.worlds.new('Coastal sky');world.use_nodes=True;scene.world=world
world.node_tree.nodes['Background'].inputs[0].default_value=(.64,.8,.94,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.55
bpy.ops.object.light_add(type='SUN',location=(-40,-50,100));sun=bpy.context.object
sun.rotation_euler=(.55,-.5,-.35);sun.data.energy=2.2;sun.data.angle=.12
bpy.ops.object.camera_add(location=(0,-170,210));camera=bpy.context.object
camera.rotation_euler=(Vector((0,-6,0))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=203;scene.camera=camera
scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=-.55
scene.render.resolution_x=1760;scene.render.resolution_y=1170;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
try:
    pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='CUDA';pref.get_devices()
    for d in pref.devices:d.use=d.type=='CUDA'
    scene.cycles.device='GPU' if any(d.type=='CUDA' for d in pref.devices) else 'CPU'
except Exception:pass
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'archipelago_terrain_v3.blend'))
groups={}
for o in objects:
    if '__ground' in o.name or 'Ocean__' in o.name or '__pond' in o.name or o.name.startswith('Waterfall__'):continue
    key=tuple(m.name for m in o.data.materials);groups.setdefault(key,[]).append(o)
for key,group in groups.items():
    if len(group)<2:continue
    # Joining into a shared prototype would modify the separate cliff instances.
    group[0].data=group[0].data.copy()
    bpy.ops.object.select_all(action='DESELECT')
    for o in group:o.select_set(True)
    bpy.context.view_layer.objects.active=group[0];bpy.ops.object.join()
    group[0].name='Details__'+key[0].split('/')[0].strip()
    if key[0].startswith('Granite'):group[0].name='Coast__shore_rock_clusters'
meshes=[o for o in scene.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=grounds[0]
bpy.ops.export_scene.gltf(filepath=str(LAB/'archipelago_terrain_v3.glb'),export_format='GLB',use_selection=True,export_yup=True)
scene.render.filepath=str(OUT/'terrain_overview.png');bpy.ops.render.render(write_still=True)
camera.location=(-35,-76,29);camera.rotation_euler=(Vector((-43,-42,1))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='PERSP';camera.data.lens=42
scene.render.resolution_x=1500;scene.render.resolution_y=1000
scene.render.filepath=str(OUT/'terrain_shore.png');bpy.ops.render.render(write_still=True)
camera.location=(-61,-90,10)
camera.rotation_euler=(Vector((-56,-65,1))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.lens=42
scene.render.filepath=str(OUT/'terrain_coast_detail.png');bpy.ops.render.render(write_still=True)
report=dict(version=3,character_height_m=1.7,units='metres',islands=[{k:v for k,v in d.items() if k not in ('contour','lines')} for d in ISLANDS],
    mesh_objects=len(meshes),triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),
    texture_resolution={'ground':2048,'ocean':4096,'pond':2048},paths_removed=True,rectangular_stream_removed=True,
    details=['unbroken meadow','high resolution grass and sand','flowing water shader','vertical waterfall curtain','compact spring','impact foam and spray','rocky headland','pond banks','offshore reefs'],
    source='archipelago_terrain_v3.blend',glb='labs/terrain_lab/assets/archipelago_terrain_v3.glb')
(OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('TERRAIN_V3_READY',json.dumps(report),flush=True)
