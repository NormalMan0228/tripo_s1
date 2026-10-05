"""Rebuild terrain topology and a continuous, gravity-curved waterfall in Blender."""
import bpy, json, math, random
import numpy as np
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v4'
LAB=ROOT/'labs/terrain_lab/assets'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art/maps/archipelago_terrain_v3/archipelago_terrain_v3.blend'))
scene=bpy.context.scene
random.seed(41)
for o in list(scene.objects):
    if o.type=='MESH' and any(s in o.name for s in ['__ground','Ocean__','__shore_wash','__foam_curl','__reef_foam','Waterfall__']):
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
    return o

grounds=[]
manifest=json.loads((ROOT/'art/maps/archipelago_terrain_v3/manifest.json').read_text())
for island in manifest['islands']:
    data=np.load(OUT/(island['id']+'.npz'))
    material=bpy.data.materials[island['id']+' / high resolution meadow and sand']
    ground=mesh(island['id']+'__ground',data['vertices'].tolist(),data['faces'].tolist(),material,data['bounds'])
    ground.data.normals_split_custom_set_from_vertices(data['normals'].tolist())
    grounds.append(ground)
    print('CONFORMING_GROUND_READY',island['id'],flush=True)

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

# The feeder surface and falling sheet are a single continuous mesh.
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
# Ballistic trajectory: horizontal initial velocity, gravity accelerates the fall.
duration=math.sqrt(2*(level-.065)/9.81)
for t in np.linspace(0,duration,100):
    p=lip+direction*1.35*t;z=level-.5*9.81*t*t
    q=t/duration;width=2.2-.28*math.sin(q*math.pi)+.23*q*q
    rows.append((p,z,width,side,q))
for j,(p,z,width,s,q) in enumerate(rows):
    for i in range(49):
        u=i/48;edge=abs(u-.5)*2
        uneven=math.sin(u*15+q*4)*.025+math.sin(u*39-q*7)*.012
        point=p+s*((u-.5)*width)+direction*uneven*max(q,0)
        v.append((point[0],point[1],z+uneven*.3));uv.append((u,1-q))
        if j and i:
            a=j*49+i;f.append((a-50,a-1,a,a-49))
mesh('Waterfall__continuous_sheet',v,f,pond,uvs=uv)

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
v=[(*impact,.055)];uv=[(.5,.5)]
for a in np.linspace(0,math.tau,129)[:-1]:
    v.append((impact[0]+3.0*math.cos(a),impact[1]+2.2*math.sin(a),.055))
    uv.append((.5+.5*math.cos(a),.5+.5*math.sin(a)))
mesh('Waterfall__impact_foam',v,[(0,k+1,(k+1)%128+1) for k in range(128)],foam,uvs=uv)

scene.render.filepath=str(OUT/'source_overview.png')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'archipelago_terrain_v4.blend'))
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
bpy.ops.export_scene.gltf(filepath=str(LAB/'archipelago_terrain_v4.glb'),export_format='GLB',use_selection=True,export_yup=True)
manifest.update(version=4,source='archipelago_terrain_v4.blend',glb='labs/terrain_lab/assets/archipelago_terrain_v4.glb',
    terrain_topology='contour-conforming Delaunay with submerged skirt',coast_sample_spacing_m=.2,
    waterfall={'height_m':level,'gravity_m_s2':9.81,'initial_velocity_m_s':1.35,'flight_duration_s':duration,'impact_blender_xy':impact.tolist(),'continuous_feeder_and_fall':True},
    ocean_extent_m=4400,mesh_objects=len(meshes),triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),
    details=['contour-conforming coast','continuous gravity-curved waterfall','local current field','depth-based shore surf','tiled surface detail','extended ocean'])
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('TERRAIN_V4_READY',json.dumps(manifest),flush=True)
