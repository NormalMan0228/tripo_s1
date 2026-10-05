"""Rebuild terrain topology and a continuous, gravity-curved waterfall in Blender."""
import bpy, bmesh, json, math, random
import numpy as np
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v6'
DATA=ROOT/'art/maps/archipelago_terrain_v5'
LAB=ROOT/'labs/terrain_lab/assets'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art/maps/archipelago_terrain_v3/archipelago_terrain_v3.blend'))
scene=bpy.context.scene
random.seed(41)
rock_templates=[]
seen=set()
for o in scene.objects:
    if '__shore_rock' in o.name and o.data.name not in seen:
        seen.add(o.data.name);rock_templates.append(o.data.copy())
for o in list(scene.objects):
    if o.type=='MESH' and any(s in o.name for s in ['__ground','Ocean__','__shore_wash','__shore_rock','__beach_pebble','__foam_curl','__reef_foam','Waterfall__']):
        bpy.data.objects.remove(o,do_unlink=True)

def mesh(name,vertices,faces,material,bounds=None,uvs=None):
    data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.update()
    o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);data.materials.append(material)
    for p in data.polygons:p.use_smooth=True
    if bounds is not None or uvs is not None:
        layer=data.uv_layers.new(name='SurfaceMap')
        for p in data.polygons:
            for i in p.loop_indices:
                idx=data.loops[i].vertex_index
                if uvs is not None:uv=uvs[idx]
                else:
                    v=data.vertices[idx].co;uv=((v.x-bounds[0])/(bounds[2]-bounds[0]),(v.y-bounds[1])/(bounds[3]-bounds[1]))
                layer.data[i].uv=uv
    if name=='Waterfall__water_volume' or name.startswith('Waterfall__stream_volume_'):
        bm=bmesh.new();bm.from_mesh(data)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
        bm.to_mesh(data);bm.free();data.update()
    return o

grounds=[]
manifest=json.loads((DATA/'manifest.json').read_text())
terrain_data={}
for island in manifest['islands']:
    data=np.load(DATA/(island['id']+'.npz'))
    terrain_data[island['id']]=data
    material=bpy.data.materials[island['id']+' / high resolution meadow and sand']
    ground=mesh(island['id']+'__ground',data['vertices'].tolist(),data['faces'].tolist(),material,data['bounds'])
    ground.data.normals_split_custom_set_from_vertices(data['normals'].tolist())
    grounds.append(ground)
    print('CONFORMING_GROUND_READY',island['id'],flush=True)

# Place asymmetric formations with broad empty stretches between them.
# Independent random arc positions replace evenly spaced contour stations.
import ast
namespace={'np':np,'math':math}
source=(ROOT/'tools/prepare_archipelago_v5.py').read_text()
functions=[ast.get_source_segment(source,node) for node in ast.parse(source).body if isinstance(node,ast.FunctionDef)]
exec('\n\n'.join(functions),namespace)
placements=[]
rock_rng=random.Random(62819)
def place_rock(name,x,y,size,ground_z):
    data=rock_rng.choice(rock_templates)
    o=bpy.data.objects.new(name,data);scene.collection.objects.link(o)
    o.scale=(size*rock_rng.uniform(.65,1.40),size*rock_rng.uniform(.55,1.25),size*rock_rng.uniform(.65,1.50))
    o.rotation_euler=(rock_rng.uniform(-.21,.21),rock_rng.uniform(-.18,.18),rock_rng.uniform(0,math.tau))
    basis=o.rotation_euler.to_matrix()
    bottom=min((basis@Vector((v.co.x*o.scale.x,v.co.y*o.scale.y,v.co.z*o.scale.z))).z for v in data.vertices)
    o.location=(x,y,ground_z-bottom-size*.22)
    placements.append({'name':name,'xy':[x,y],'size_m':size,'base_ground_m':ground_z})

cluster_count=0
for island in manifest['islands']:
    data=terrain_data[island['id']];verts=data['vertices']
    contour=namespace['catmull'](island['outline'])
    def floor(x,y):
        x=np.asarray(x);y=np.asarray(y)
        return namespace['height'](x,y,island,namespace['distance'](x,y,contour))
    count=rock_rng.randint(7,11) if not island['id'].startswith('05') else 3
    anchors=[]
    attempts=0
    while len(anchors)<count and attempts<500:
        attempts+=1;idx=rock_rng.randrange(len(contour));p=contour[idx]
        if np.linalg.norm(p-np.array([.2,8.7]))<9.0:continue
        if any(np.linalg.norm(p-other)<rock_rng.uniform(5,10) for other in anchors):continue
        anchors.append(p.copy());cluster_count+=1
        tangent=contour[(idx+2)%len(contour)]-contour[(idx-2)%len(contour)]
        tangent/=np.linalg.norm(tangent)
        outward=np.array([tangent[1],-tangent[0]])
        if namespace['distance'](np.array(p[0]+outward[0]),np.array(p[1]+outward[1]),contour)>0:outward=-outward
        group_size=rock_rng.randint(2,7)
        footprint=rock_rng.uniform(1.4,4.5)
        for k in range(group_size):
            q=p+tangent*rock_rng.gauss(0,footprint)+outward*rock_rng.uniform(-1.6,1.4)
            if np.linalg.norm(q-np.array([.2,8.7]))<8.8:continue
            h=float(floor(*q));size=rock_rng.uniform(.55,1.80) if k>1 else rock_rng.uniform(1.4,2.9)
            if h<-2.8:continue
            place_rock(island['id']+'__shore_rock',*q,size,h)
        # Small gravel belongs to these formations, with occasional isolated
        # pieces in the beach interior, rather than another contour ring.
        for k in range(rock_rng.randint(2,5)):
            q=p+tangent*rock_rng.gauss(0,footprint*1.7)-outward*rock_rng.uniform(.5,4.0)
            if np.linalg.norm(q-np.array([.2,8.7]))<8.8:continue
            h=float(floor(*q))
            if h>.02:place_rock(island['id']+'__beach_pebble',*q,rock_rng.uniform(.10,.28),h)
(OUT/'rock_distribution.json').write_text(json.dumps({'clusters':cluster_count,'rocks':placements},indent=2))

water=bpy.data.materials['Water / painted azure wave facets']
pond=bpy.data.materials['Pond / jewel blue']
foam=bpy.data.materials['Foam / pearl white']
# A detailed central ocean patch and a distant skirt; no visible rectangular edge.
n=321;xx,yy=np.meshgrid(np.linspace(-160,160,n),np.linspace(-160,160,n))
v=np.stack((xx,yy,np.zeros(xx.shape)),axis=-1).reshape(-1,3).tolist()
f=[(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(n-1) for i in range(n-1)]
mesh('Ocean__central_surface',v,f,water,(-130,-115,130,110))
v=[(-160,-160,0),(160,-160,0),(160,160,0),(-160,160,0),(-2200,-2200,0),(2200,-2200,0),(2200,2200,0),(-2200,2200,0)]
mesh('Ocean__distant_surface',v,[(4,5,1,0),(5,6,2,1),(6,7,3,2),(7,4,0,3)],water,(-130,-115,130,110))
bottom=bpy.data.materials.new('Seabed / muted turquoise');bottom.diffuse_color=(.04,.19,.21,1)
mesh('Ocean__seabed', [(-2200,-2200,-8),(2200,-2200,-8),(2200,2200,-8),(-2200,2200,-8)],[(0,1,2,3)],bottom)

# A closed water volume connects the headwater, rounded lip and falling body.
lip=np.array((.2,8.7));direction=np.array((.72,-.69));direction/=np.linalg.norm(direction)
side=np.array((-direction[1],direction[0]));level=3.34
v=[];f=[];uv=[];rows=[]
# Hermite approach: centerline has exactly the same tangent at the lip.
start=np.array((-5.7,11.2));end=lip
for t in np.linspace(0,1,100,endpoint=False):
    m0=np.array((6.0,-1.4));m1=direction*3.0
    p=(2*t**3-3*t*t+1)*start+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*end+(t**3-t*t)*m1
    tangent=(6*t*t-6*t)*start+(3*t*t-4*t+1)*m0+(-6*t*t+6*t)*end+(3*t*t-2*t)*m1
    tangent/=np.linalg.norm(tangent);s=np.array((-tangent[1],tangent[0]))
    width=.015+2.185*math.sin(t*math.pi*.5)**.6+1.7*math.sin(t*math.pi)
    rows.append((p,level,width,s,-.85*(1-t)))
# Travel-time coordinates preserve the speed through the join and accelerate
# the visible flow down the gravity curve. Negative times are upstream.
centers=np.array([row[0] for row in rows]+[lip])
lengths=np.linalg.norm(np.diff(centers,axis=0),axis=1)
remaining=np.cumsum(lengths[::-1])[::-1]/1.35
rows=[(row[0],row[1],row[2],row[3],-remaining[i]) for i,row in enumerate(rows)]
# Ballistic trajectory: horizontal initial velocity, gravity accelerates the fall.
duration=math.sqrt(2*(level-.065)/9.81)
for t in np.linspace(0,duration,100):
    p=lip+direction*1.35*t;z=level-.5*9.81*t*t
    q=t/duration;width=2.2-.28*math.sin(q*math.pi)+.23*q*q
    rows.append((p,z,width,side,t))
for j,(p,z,width,s,q) in enumerate(rows):
    for i in range(49):
        u=i/48;fraction=max(q/duration,0)
        uneven=math.sin(u*15+fraction*4)*.055+math.sin(u*39-fraction*7)*.022
        thickness=.035+.085*min(fraction,1)
        point=p+s*((u-.5)*width)+direction*(uneven*min(fraction*3,1)+thickness*math.sin(u*math.pi))
        v.append((point[0],point[1],z+uneven*.14));uv.append((u,1-q))
        if j and i:
            a=j*49+i;f.append((a-50,a-1,a,a-49))
count=len(v)
for j,(p,z,width,s,q) in enumerate(rows):
    fraction=max(q/duration,0)
    tangent=np.array([1.35*direction[0],1.35*direction[1],-9.81*max(q,0)])
    tangent/=np.linalg.norm(tangent)
    normal=np.cross(tangent,np.array([s[0],s[1],0]));normal/=np.linalg.norm(normal)
    if normal[2]<0:normal=-normal
    for i in range(49):
        original=np.array(v[j*49+i]);thickness=.16+.08*min(fraction,1)
        back=original-normal*thickness
        v.append(tuple(back));uv.append((i/48,1-q))
        if j and i:
            a=count+j*49+i;f.append((a-50,a-49,a,a-1))
for j in range(len(rows)-1):
    a=j*49;b=(j+1)*49
    f.append((a,b,b+count,a+count));a+=48;b+=48
    f.append((a+count,b+count,b,a))
for i in range(48):
    f.append((i+1,i,i+count,i+count+1))
    a=(len(rows)-1)*49+i;f.append((a,a+1,a+1+count,a+count))
mesh('Waterfall__water_volume',v,[tuple(reversed(face)) for face in f],pond,uvs=uv)

# Individually rounded streams occupy different depths and trajectories.
# Each starts within the main body upstream and merges into the impact plume.
stream_specs=[(-.94,.090,1.41),(-.67,.035,1.74),(-.55,.052,1.25),(-.13,.125,1.48),(.28,.039,1.91),(.44,.067,1.34),(.89,.046,1.62)]
for index,(offset,radius,launch) in enumerate(stream_specs):
    vertices=[];faces=[];coords=[]
    times=np.linspace(-.08,duration,100)
    for j,time in enumerate(times):
        falling=max(time,0);fraction=falling/duration
        spread=offset*(1+.06*fraction)+math.sin(fraction*(5.7+index*.43)+index*2.38)*.11*fraction
        position=lip+side*spread+direction*(launch*time+.025+.15*fraction+.06*math.sin(index*2.2)*fraction)
        z=level-.5*9.81*falling*falling
        tangent=np.array([launch*direction[0],launch*direction[1],-9.81*falling]);tangent/=np.linalg.norm(tangent)
        lateral=np.array([side[0],side[1],0]);normal=np.cross(tangent,lateral);normal/=np.linalg.norm(normal)
        taper=.45+.55*min(1,(time+.08)/.16)
        r=radius*taper*(.85+.20*fraction+.28*math.sin(fraction*(8.2+index*.77)+index*1.83)+.10*math.sin(fraction*22+index*2.14))
        for i in range(12):
            angle=i*math.tau/12;point=np.array([*position,z])+lateral*math.cos(angle)*r+normal*math.sin(angle)*r*(.40+.30*math.sin(index*1.37)**2)
            vertices.append(tuple(point));coords.append((i/12,1-time))
            if j:
                a=j*12+i;b=j*12+(i+1)%12;faces.append((a-12,a,b,b-12))
    faces.append(tuple(range(11,-1,-1)));faces.append(tuple((len(times)-1)*12+i for i in range(12)))
    mesh('Waterfall__stream_volume_'+str(index),vertices,[tuple(reversed(face)) for face in faces],pond,uvs=coords)

# The rounded headwater, neck and falling sheet now share one topology and
# material. There is no overlapping pool/ribbon rectangle or shading seam.

stone=bpy.data.materials['Granite / warm face 2']
# Bevelled asymmetrical ledges frame the fall without hiding its connection.
for index,(s,d,scale) in enumerate([(-1.9,-.15,(1.6,1.7,2.65)),(1.8,-.12,(1.35,1.55,2.5)),(-2.2,1.1,(1.6,1.1,1.6)),(2.1,1.4,(1.1,1.4,1.4)),(-2.0,-1.9,(2.2,1.4,1.1)),(2.1,-1.8,(1.5,1.5,1.2))]):
    p=lip+side*s+direction*d
    bpy.ops.mesh.primitive_cube_add(size=1,location=(p[0],p[1],scale[2]*.46))
    o=bpy.context.object;o.name='Waterfall__cliff_rock_'+str(index)
    for vert in o.data.vertices:
        vert.co.x+=random.uniform(-.15,.15);vert.co.y+=random.uniform(-.12,.12)
        if vert.co.z>0:vert.co.z+=random.uniform(-.08,.14)
    o.scale=scale;o.rotation_euler.z=random.uniform(-.35,.35)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=o.modifiers.new('Rounded erosion','BEVEL');bevel.width=.16;bevel.segments=3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    for poly in o.data.polygons:poly.use_smooth=True
    weighted=o.modifiers.new('Large face normals','WEIGHTED_NORMAL');weighted.keep_sharp=True
    bpy.ops.object.modifier_apply(modifier=weighted.name);o.data.materials.append(stone)

impact=lip+direction*(1.35*duration)
v=[];uv=[];faces=[]
for j in range(25):
    r=j/24
    for i in range(128):
        angle=i*math.tau/128
        v.append((impact[0]+2.4*r*math.cos(angle),impact[1]+1.8*r*math.sin(angle),.05+.19*math.exp(-r*r*9)))
        uv.append((.5+.5*r*math.cos(angle),.5+.5*r*math.sin(angle)))
        if j:
            a=j*128+i;b=j*128+(i+1)%128;faces.append((a-128,a,b,b-128))
mesh('Waterfall__impact_foam',v,faces,foam,uvs=uv)

scene.render.filepath=str(OUT/'source_overview.png')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'archipelago_terrain_v6.blend'))
# Batch retained small details, while keeping the surfaces available to engine shaders.
groups={}
for o in list(scene.objects):
    if o.type!='MESH' or any(s in o.name for s in ['__ground','Ocean__','__pond','Waterfall__']):continue
    key=tuple(m.name for m in o.data.materials);groups.setdefault(key,[]).append(o)
for key,group in groups.items():
    if len(group)<2:continue
    group[0].data=group[0].data.copy();bpy.ops.object.select_all(action='DESELECT')
    for o in group:o.select_set(True)
    bpy.context.view_layer.objects.active=group[0];bpy.ops.object.join()
    group[0].name='Coast__shore_rock_clusters' if key[0].startswith('Granite') else 'Details__'+key[0].split('/')[0].strip()
bpy.ops.object.select_all(action='DESELECT');meshes=[o for o in scene.objects if o.type=='MESH']
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=grounds[0]
bpy.ops.export_scene.gltf(filepath=str(LAB/'archipelago_terrain_v6.glb'),export_format='GLB',use_selection=True,export_yup=True)
manifest.update(version=6,runtime_revision='6',source='archipelago_terrain_v6.blend',glb='labs/terrain_lab/assets/archipelago_terrain_v6.glb',
    terrain_topology='contour-conforming Delaunay with submerged skirt',coast_sample_spacing_m=.2,
    waterfall={'height_m':level,'gravity_m_s2':9.81,'initial_velocity_m_s':1.35,'flight_duration_s':duration,'impact_blender_xy':impact.tolist(),'closed_water_volume':True,'rounded_stream_volumes':7,'uv_units':'travel seconds'},
    ocean_extent_m=4400,rock_clusters=cluster_count,waterfall_stream_specs=stream_specs,mesh_objects=len(meshes),triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),
    details=['contour-conforming coast','smoothly joined headland height field','closed gravity-curved waterfall volume','seven rounded stream volumes','travel-time flow animation','local current field','physical shoreline distance surf','seamless isotropic foam and circular bubbles','tiled surface detail','extended ocean'])
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('TERRAIN_V6_READY',json.dumps(manifest),flush=True)
