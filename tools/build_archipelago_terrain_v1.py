"""Editable metre-scale terrain from the user's archipelago reference.

Run with Blender --background --python tools/build_archipelago_terrain_v1.py.
The gameplay map is untouched; outputs belong to the independent terrain lab.
"""
import bpy
import math
import random
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/maps/archipelago_terrain_v1'
LAB = ROOT / 'labs/terrain_lab/assets'
OUT.mkdir(parents=True, exist_ok=True)
LAB.mkdir(parents=True, exist_ok=True)
random.seed(105)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1

def linear(v):
    return v / 12.92 if v < .04045 else ((v + .055) / 1.055) ** 2.4

def col(rgb):
    return tuple(linear(v) for v in rgb)

def material(name, rgb, roughness=.8, vertex=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*col(rgb), 1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Specular IOR Level'].default_value = .25
    m.diffuse_color = (*col(rgb), 1)
    if vertex:
        n = m.node_tree.nodes.new('ShaderNodeVertexColor')
        n.layer_name = 'Color'
        m.node_tree.links.new(n.outputs['Color'], p.inputs['Base Color'])
    return m

ground_mat = material('Terrain / soft meadow to warm sand', (.6, .74, .28), vertex=True)
sea_mat = material('Ocean / turquoise shoals', (.05, .62, .8), .28, True)
pond_mat = material('Pond / sheltered turquoise', (.08, .62, .67), .3)
foam_mat = material('Shore / pale broken wash', (.8, .96, .92), .65)
rock_mats = [material('Coastal stone / ' + str(i), (.43+i*.035, .47+i*.035, .47+i*.034)) for i in range(5)]

def water_detail(mat, scale, strength):
    nodes = mat.node_tree.nodes; links = mat.node_tree.links
    noise = nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale
    noise.inputs['Detail'].default_value=2
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=strength
    bump.inputs['Distance'].default_value=.06
    links.new(noise.outputs['Fac'],bump.inputs['Height'])
    links.new(bump.outputs['Normal'],nodes.get('Principled BSDF').inputs['Normal'])
water_detail(sea_mat,.9,.22)
water_detail(pond_mat,1.3,.11)

# Blender +Y is map north. GLB export converts this to Godot -Z.
ISLANDS = [
    dict(id='01_village_meadow', center=(-39, 39), radius=(30, 24), seed=.2, base=1.65, hill=1.2),
    dict(id='02_garden_headland', center=(38, 38), radius=(33, 26), seed=1.6, base=1.75, hill=1.4,
         pond=(45, 42, 8.4, 5.8, 1.02)),
    dict(id='03_town_common', center=(-37, -24), radius=(35, 29), seed=2.4, base=1.7, hill=1.15,
         pond=(-43, -34, 9.5, 6.8, 1.0)),
    dict(id='04_camp_meadow', center=(41, -29), radius=(31, 29), seed=4.1, base=1.65, hill=1.2),
    dict(id='05_lighthouse_islet', center=(-1, -67), radius=(9.3, 7.8), seed=3.2, base=1.45, hill=.35),
]

def boundary(a, s):
    return 1 + .085*math.sin(3*a+s) + .052*math.cos(5*a-2*s) + .024*math.sin(8*a+s)

def pond_boundary(a):
    return 1+.13*math.sin(3*a+.7)+.07*math.cos(5*a-.5)

def pond_radius(x,y,pond):
    px,py,rx,ry,level=pond
    u,v=(x-px)/rx,(y-py)/ry
    return math.hypot(u,v)/pond_boundary(math.atan2(v,u))

def normalized(x, y, island):
    cx, cy = island['center']; rx, ry = island['radius']
    u, v = (x-cx)/rx, (y-cy)/ry
    a = math.atan2(v, u)
    return math.hypot(u, v) / boundary(a, island['seed'])

def smooth(a, b, x):
    t = max(0, min(1, (x-a)/(b-a)))
    return t*t*(3-2*t)

def height(x, y, island):
    r = normalized(x, y, island)
    cx, cy = island['center']; rx, ry = island['radius']
    u, v = (x-cx)/rx, (y-cy)/ry
    # Broad beach at the waterline; rounded grass bank rising into a gentle plateau.
    z = -.62 + 1.04*smooth(1.09, .96, r) + (island['base']-.42)*smooth(.96, .79, r)
    inland = 1-smooth(.65, .92, r)
    z += inland * (island['hill']*math.exp(-((u+.2)**2/.33+(v-.36)**2/.22))
                    + .12*math.sin(x*.18)*math.sin(y*.15))
    if 'pond' in island:
        px, py, prx, pry, level = island['pond']
        q = pond_radius(x,y,island['pond'])
        z = z * smooth(.73, 1.32, q) + (level-.62)*(1-smooth(.73, 1.32, q))
    return z

def ground_color(x, y, island):
    r = normalized(x, y, island)
    grass = (.53, .75, .26)
    sand = (.91, .81, .58)
    wet = (.69, .69, .5)
    t = smooth(.83, .88, r)
    c = tuple(grass[i]*(1-t)+sand[i]*t for i in range(3))
    t = smooth(.97, 1.07, r)
    c = tuple(c[i]*(1-t)+wet[i]*t for i in range(3))
    if 'pond' in island:
        q=pond_radius(x,y,island['pond'])
        t=(1-smooth(1.12,1.25,q))*smooth(.88,1.0,q)
        gravel=(.73,.74,.50)
        c=tuple(c[i]*(1-t)+gravel[i]*t for i in range(3))
    shade = .018*math.sin(x*.38)*math.cos(y*.32)+.012*math.sin(x*.87+y*.6)
    return tuple(max(.01, min(.99, v+shade)) for v in c)

def mesh(name, vertices, faces, mat, colors=None):
    d = bpy.data.meshes.new(name)
    d.from_pydata(vertices, [], faces)
    d.update()
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    d.materials.append(mat)
    if colors:
        attr = d.color_attributes.new(name='Color', type='FLOAT_COLOR', domain='POINT')
        for item, rgb in zip(attr.data, colors): item.color = (*col(rgb), 1)
    for p in d.polygons: p.use_smooth = True
    return o

terrain_objects = []
for island in ISLANDS:
    n, rings = 192, 70
    cx, cy = island['center']; rx, ry = island['radius']
    vertices = [(cx, cy, height(cx, cy, island))]
    colors = [ground_color(cx, cy, island)]
    for j in range(1, rings+1):
        r = 1.1*j/rings
        for k in range(n):
            a = math.tau*k/n; b = boundary(a, island['seed'])
            x, y = cx+rx*r*b*math.cos(a), cy+ry*r*b*math.sin(a)
            vertices.append((x, y, height(x, y, island)))
            colors.append(ground_color(x, y, island))
    faces = [(0, 1+k, 1+(k+1)%n) for k in range(n)]
    for j in range(rings-1):
        for k in range(n):
            a, b = 1+j*n+k, 1+j*n+(k+1)%n
            c, d = a+n, b+n
            faces.extend([(a,c,d), (a,d,b)])
    o = mesh(island['id']+'__ground', vertices, faces, ground_mat, colors)
    terrain_objects.append(o)
    if 'pond' in island:
        px, py, prx, pry, level = island['pond']
        # The pool sits inside a real depressed basin, never above the bank.
        vs = [(px,py,level)]
        for k in range(128):
            a=math.tau*k/128
            # Extend under the ground: its actual shoreline is the water/land
            # intersection, avoiding a visibly raised disc around the pool.
            r=1.29*pond_boundary(a)
            vs.append((px+prx*r*math.cos(a), py+pry*r*math.sin(a), level))
        terrain_objects.append(mesh(island['id']+'__pond',vs,[(0,k+1,(k+1)%128+1) for k in range(128)],pond_mat))

# A shallow shelf naturally lightens water next to land. Vertex colors survive GLB.
vs, cs, fs = [], [], []
steps = 200
for j in range(steps+1):
    y=-115+230*j/steps
    for i in range(steps+1):
        x=-145+290*i/steps
        dist=min((normalized(x,y,d)-1)*min(d['radius']) for d in ISLANDS)
        t=smooth(1, 17, dist)
        shallow=(.17,.8,.83); deep=(.04,.62,.84)
        wave=.008*math.sin(x*.8+y*.5)
        cs.append(tuple(shallow[k]*(1-t)+deep[k]*t+wave for k in range(3)))
        vs.append((x,y,0))
for j in range(steps):
    for i in range(steps):
        a=j*(steps+1)+i
        fs.append((a,a+1,a+steps+2,a+steps+1))
ocean=mesh('Ocean__preview_surface',vs,fs,sea_mat,cs)
terrain_objects.append(ocean)

# Broken, low surf traces follow the shore instead of forming a solid white rim.
for island in ISLANDS:
    cx,cy=island['center'];rx,ry=island['radius']
    vertices=[];faces=[]
    for k in range(384):
        if math.sin(k*.59+island['seed']) < -.05: continue
        a=math.tau*k/384; a2=math.tau*(k+.8)/384
        idx=len(vertices)
        for aa,r in [(a,1.025),(a2,1.025),(a2,1.031),(a,1.031)]:
            b=boundary(aa,island['seed'])
            vertices.append((cx+rx*r*b*math.cos(aa),cy+ry*r*b*math.sin(aa),.022))
        faces.append((idx,idx+1,idx+2,idx+3))
    terrain_objects.append(mesh(island['id']+'__shore_wash',vertices,faces,foam_mat))

# Editable rocks: rounded silhouettes, restrained broad facets, no tiny noisy detail.
rock_objects=[]
for island in ISLANDS:
    cx,cy=island['center'];rx,ry=island['radius']
    clusters=12 if island['id'][0:2]!='05' else 8
    for k in range(clusters):
        a=math.tau*(k+random.uniform(-.28,.28))/clusters+island['seed']*.18
        b=boundary(a,island['seed'])
        r=random.uniform(.97,1.035)
        for j in range(random.randint(2,4)):
            x=cx+rx*r*b*math.cos(a)+random.uniform(-1.5,1.5)
            y=cy+ry*r*b*math.sin(a)+random.uniform(-1.1,1.1)
            size=random.uniform(.65,1.65) if clusters==12 else random.uniform(.65,1.15)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=(x,y,.1+size*.37))
            o=bpy.context.object;o.name=island['id']+'__shore_rock'
            for v in o.data.vertices:
                v.co*=random.uniform(.89,1.12)
            o.scale=(size*1.15,size*.86,size*.9)
            o.rotation_euler=(random.uniform(-.2,.2),random.uniform(-.2,.2),random.uniform(0,math.tau))
            o.data.materials.append(random.choice(rock_mats))
            bevel=o.modifiers.new('Soft stone corners','BEVEL');bevel.width=.08;bevel.segments=2
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            bpy.ops.object.modifier_apply(modifier=bevel.name)
            rock_objects.append(o)

# Anchors mark intended later placement, without introducing buildings at this stage.
anchors=[('Bridge_NW_NE',(-1,40,1.6)),('Bridge_SW_SE',(1,-23,1.6)),
         ('Bridge_SW_lighthouse',(-18,-57,1.6)),('Town_square',(-30,-16,1.7)),
         ('Windmill',(-19,45,2)),('Observatory',(26,50,2)),
         ('Stage',(31,-16,2)),('Lighthouse',(-1,-67,1.7))]
for name,loc in anchors:
    o=bpy.data.objects.new('ANCHOR__'+name,None);scene.collection.objects.link(o)
    o.location=loc;o.empty_display_size=1

world=bpy.data.worlds.new('Soft coastal daylight');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.8,.9,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.65;scene.world=world
bpy.ops.object.light_add(type='SUN',location=(0,0,90))
sun=bpy.context.object;sun.name='Sun';sun.rotation_euler=(.48,-.5,-.4);sun.data.energy=2.3;sun.data.angle=.15
bpy.ops.object.camera_add(location=(0,-155,175))
camera=bpy.context.object;camera.name='Camera__overview'
camera.rotation_euler=(Vector((0,-3,0))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=174;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.cycles.use_denoising=True
try:
    pref=bpy.context.preferences.addons['cycles'].preferences
    pref.compute_device_type='CUDA';pref.get_devices()
    for d in pref.devices:d.use=d.type=='CUDA'
    scene.cycles.device='GPU' if any(d.type=='CUDA' for d in pref.devices) else 'CPU'
except Exception: pass
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=.3
scene.render.resolution_x=1600;scene.render.resolution_y=1250;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'

# Store convenient camera framing in the editable source.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'archipelago_terrain_v1.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in terrain_objects+rock_objects:o.select_set(True)
bpy.context.view_layer.objects.active=terrain_objects[0]
bpy.ops.export_scene.gltf(filepath=str(LAB/'archipelago_terrain_v1.glb'),export_format='GLB',
                          use_selection=True,export_yup=True)
scene.render.filepath=str(OUT/'terrain_overview.png');bpy.ops.render.render(write_still=True)
camera.location=(0,0,210);camera.rotation_euler=(0,0,0);camera.data.ortho_scale=170
scene.render.resolution_x=1500;scene.render.resolution_y=1400
scene.render.filepath=str(OUT/'terrain_top.png');bpy.ops.render.render(write_still=True)
camera.location=(-34,-61,22)
camera.rotation_euler=(Vector((-36,-29,1.2))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='PERSP';camera.data.lens=40
scene.render.resolution_x=1500;scene.render.resolution_y=950
scene.render.filepath=str(OUT/'terrain_shore.png');bpy.ops.render.render(write_still=True)
report=dict(version=1,units='metres',character_height_m=1.7,sea_level_m=0,
    islands=ISLANDS,anchors=[dict(name=n,blender_position=p) for n,p in anchors],
    triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in terrain_objects+rock_objects),
    mesh_objects=len(terrain_objects+rock_objects),
    scope='Terrain art study; buildings, vegetation, bridges, waterfall and production-game integration are subsequent work.',
    references=['map_reference.png','character_reference.png'])
(OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('TERRAIN_READY',json.dumps(report))
