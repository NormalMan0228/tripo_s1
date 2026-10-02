"""Developer-authored environment asset ONLY. Never imported by player generation.
Keeps a saved Blender source and exports a compact, beveled storybook cottage.
"""
import bpy,math,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/authored-environment';OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
random.seed(731)
def linear(c):return c/12.92 if c<.04045 else ((c+.055)/1.055)**2.4
def mat(name,hex):
    rgb=tuple(linear(int(hex[i:i+2],16)/255) for i in (0,2,4))
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Roughness'].default_value=.82
    return m
M={k:mat(k,v) for k,v in {'plaster':'E1CEA5','timber':'806044','oak':'AC8251','roof':'648A80','roof_light':'78998B','roof_dark':'567B76','stone':'A8A38C','stone_light':'BFB89B','glass':'809F9A','warm':'E8C17A','soil':'605342','leaf':'768753','leaf_light':'9B9F63','pot':'B78861','door':'977249','iron':'534B3B'}.items()}
def cube(name,loc,size,material,bevel=.035,rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc,rotation=rot);o=bpy.context.object;o.name=name;o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(M[material])
    if bevel:
        modifier=o.modifiers.new('Soft crafted edge','BEVEL');modifier.width=bevel;modifier.segments=2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        n=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=n.name)
    return o
def cylinder(name,loc,radius,depth,material,vertices=12,rot=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc,rotation=rot);o=bpy.context.object;o.name=name;o.data.materials.append(M[material]);return o
cube('Stone foundation',(0,0,.14),(4.8,4,.28),'stone',.08)
cube('Lime plaster walls',(0,0,1.45),(4.35,3.6,2.6),'plaster',.08)
# Gable ends are solid geometry, not a floating roof covering an open triangular hole.
verts=[(-2.175,-1.8,2.75),(2.175,-1.8,2.75),(0,-1.8,4.3),(-2.175,1.8,2.75),(2.175,1.8,2.75),(0,1.8,4.3)]
mesh=bpy.data.meshes.new('Gable mesh');mesh.from_pydata(verts,[],[(0,2,1),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)]);mesh.materials.append(M['plaster'])
o=bpy.data.objects.new('Gable plaster',mesh);bpy.context.collection.objects.link(o)
for x in [-2.12,0,2.12]:cube('Front structural timber',(x,-1.84,1.48),(.16,.16,2.7),'timber')
for z in [.35,2.65]:cube('Front cross beam',(0,-1.85,z),(4.5,.17,.16),'timber')
for x in [-2.15,2.15]:
    for y in [-1.7,0,1.7]:cube('Side post',(x,y,1.48),(.15,.15,2.65),'timber')
    for z in [.36,2.65]:cube('Side cross beam',(x,0,z),(.16,3.65,.16),'timber')
angle=math.atan2(1.9,2.7);roof_length=math.hypot(2.7,1.9)
for side in [-1,1]:
    cube('Roof underlay',(side*1.35,0,3.45),(roof_length,4.6,.13),'roof_dark',.04,rot=(0,side*angle,0))
    for course in range(7):
        x=side*(.18+course*.39);z=4.50-abs(x)*1.9/2.7
        for along in range(10):
            y=-2.16+along*.47+(course%2)*.035
            cube('Rounded slate shingle',(x,y,z),(.58,.50,.095),random.choice(['roof','roof','roof_light','roof_dark']),.04,rot=(0,side*angle,random.uniform(-.015,.015)))
    cube('Front carved roof edge',(side*1.36,-2.33,3.42),(roof_length+.14,.15,.18),'timber',.04,rot=(0,side*angle,0))
for y in [-2.15,-1.65,-1.15,-.65,-.15,.35,.85,1.35,1.85,2.2]:
    cylinder('Rounded ridge cap',(0,y,4.46),.12,.53,'roof_dark',rot=(math.pi/2,0,0))
# Arched door, oak slats and a small brass ring.
cube('Door shadow',(0,-1.96,1.2),(1.22,.10,1.9),'iron',.08)
for i in range(7):
    x=(i-3)*.155;top=1.9+math.sqrt(max(0,.55**2-x*x))
    cube('Door oak plank',(x,-2.03,(.28+top)/2),(.149,.09,top-.28),'door',.025)
for x in [-.65,.65]:cube('Door jamb',(x,-2.05,1.18),(.14,.19,1.8),'oak')
for i in range(13):
    a=i*math.pi/12
    cube('Arch stone',(math.cos(a)*.63,-2.01,1.98+math.sin(a)*.63),(.20,.24,.21),'stone_light',.035,rot=(0,math.pi/2-a,0))
for z in [.75,1.55]:cube('Door brace',(0,-2.10,z),(1.05,.06,.10),'timber',.02)
cylinder('Door handle',(.35,-2.16,1.15),.06,.055,'warm',16,(math.pi/2,0,0))
for x in [-1.38,1.38]:
    cube('Window frame',(x,-1.95,1.65),(.82,.15,1.12),'oak',.045)
    cube('Window glass',(x,-2.04,1.66),(.63,.045,.91),'glass',.015)
    cube('Window vertical',(x,-2.075,1.65),(.06,.06,.98),'warm',.01)
    cube('Window horizontal',(x,-2.075,1.65),(.68,.06,.06),'warm',.01)
    cube('Window sill',(x,-2.09,1.07),(.96,.39,.12),'timber')
    for side in [-1,1]:
        cube('Sage shutter',(x+side*.52,-1.99,1.65),(.21,.09,1.10),'roof',.035)
        for z in [1.3,1.65,2]:cube('Shutter rail',(x+side*.52,-2.06,z),(.24,.06,.065),'roof_light',.015)
# Stone chimney and small foundation blocks.
for z in range(6):
    for x in range(2):cube('Chimney masonry',(-1.5+x*.27,.8,3.7+z*.25),(.28,.62,.23),'stone' if (x+z)%2 else 'stone_light',.04)
cube('Chimney coping',(-1.36,.8,5.17),(.78,.83,.13),'timber',.04)
for i in range(12):cube('Front foundation stone',(-2.23+i*.405,-1.96,.21),(.39,.30,.31),'stone_light' if i%3==0 else 'stone',.045)
for i in range(3):cube('Welcome steps',(0,-2.1-i*.34,.18-i*.045),(1.65+i*.2,.45,.16),'stone_light',.065)
for side in [-1,1]:
    cylinder('Terracotta planter',(side*2.13,-2.2,.42),.24,.50,'pot')
    cylinder('Planter soil',(side*2.13,-2.2,.68),.22,.035,'soil')
    for i in range(8):
        a=i*math.tau/8
        bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=4,radius=1,location=(side*2.13+.16*math.cos(a),-2.2+.16*math.sin(a),.84+random.random()*.12))
        o=bpy.context.object;o.name='Round shrub leaves';o.scale=(.19,.17,.22);o.data.materials.append(M['leaf_light' if i%3==0 else 'leaf'])
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'storybook-home-v1.blend'))
# Keep the editable source above; join the export by material to reduce draw calls.
for obj in list(bpy.context.scene.objects):
    bpy.context.view_layer.objects.active=obj
    for modifier in list(obj.modifiers):bpy.ops.object.modifier_apply(modifier=modifier.name)
for material in M.values():
    group=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.materials and o.data.materials[0]==material]
    if not group:continue
    bpy.ops.object.select_all(action='DESELECT')
    for obj in group:obj.select_set(True)
    bpy.context.view_layer.objects.active=group[0]
    if len(group)>1:bpy.ops.object.join()
    group[0].name='Cottage_'+material.name
bpy.ops.export_scene.gltf(filepath=str(ROOT/'game/assets/storybook_home_v1.glb'),export_format='GLB',export_apply=True)
print('AUTHORED_HOME_EXPORTED',len(bpy.data.objects))
