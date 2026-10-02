"""Small developer-authored camp prop, no runtime player Blender dependency."""
import bpy,math,random
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/authored-environment';OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
random.seed(801)
def material(name,color):
    values=[int(color[i:i+2],16)/255 for i in (0,2,4)]
    values=[v/12.92 if v<.04045 else ((v+.055)/1.055)**2.4 for v in values]
    m=bpy.data.materials.new(name);m.diffuse_color=(*values,1);m.use_nodes=True
    shader=m.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=(*values,1);shader.inputs['Roughness'].default_value=.87
    return m
M={k:material(k,v) for k,v in {'stone':'929486','light_stone':'B2AC95','bark':'76533C','cut':'C39860','ring':'A87943','coal':'383B32','iron':'4D554E','brass':'BC9A5E','soup':'CEAD6B'}.items()}
def cylinder(name,a,b,r,mat,vertices=12):
    a,b=Vector(a),Vector(b);d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=d.length,location=(a+b)/2)
    ob=bpy.context.object;ob.name=name;ob.rotation_euler=d.to_track_quat('Z','Y').to_euler();ob.data.materials.append(M[mat])
    return ob
def torus(name,loc,major,minor,mat,rotation=(0,0,0)):
    bpy.ops.mesh.primitive_torus_add(major_segments=24,minor_segments=6,location=loc,rotation=rotation,major_radius=major,minor_radius=minor)
    ob=bpy.context.object;ob.name=name;ob.data.materials.append(M[mat]);return ob
for i in range(12):
    angle=math.tau*i/12
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=(.8*math.cos(angle),.8*math.sin(angle),.14))
    ob=bpy.context.object;ob.name='Rounded hearth stone';ob.scale=(.22+random.random()*.025,.17,.145+random.random()*.04)
    ob.rotation_euler.z=angle;ob.data.materials.append(M['light_stone' if i%3==0 else 'stone'])
for i in range(3):
    angle=i*math.pi/3+.2;z=.17+i*.06
    a=Vector((-.52*math.cos(angle),-.52*math.sin(angle),z));b=-Vector((a.x,a.y,0))+Vector((0,0,z))
    cylinder('Split firewood bark',a,b,.115,'bark')
    direction=(b-a).normalized()
    for endpoint,side in ((a,-1),(b,1)):
        center=endpoint+direction*.008*side
        cylinder('Honey endgrain',center-direction*.003,center+direction*.003,.102,'cut')
        ring=torus('Endgrain growth ring',center,.056,.009,'ring')
        ring.rotation_euler=direction.to_track_quat('Z','Y').to_euler()
for i in range(9):
    angle=i*math.tau/9
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.09,location=(math.cos(angle)*.37,math.sin(angle)*.37,.11))
    bpy.context.object.name='Charcoal';bpy.context.object.data.materials.append(M['coal'])
# Slender cooking tripod lies entirely within the existing camp collider.
for angle in [math.pi/2,math.pi/2+math.tau/3,math.pi/2+2*math.tau/3]:
    cylinder('Cooking tripod',(.65*math.cos(angle),.65*math.sin(angle),.12),(.06*math.cos(angle),.06*math.sin(angle),1.48),.027,'iron',8)
for i in range(5):
    torus('Hanging chain',(0,0,1.42-i*.075),.033,.009,'iron',(math.pi/2,0,0 if i%2 else math.pi/2))
# Open bowl, deliberately separate inner/outer surface; no solid cap over soup.
vertices=[];faces=[];segments=24
profile=[(.12,.57),(.24,.61),(.29,.77),(.28,.85),(.255,.85),(.265,.77),(.215,.635),(.12,.62)]
for radius,z in profile:
    for j in range(segments):
        a=j*math.tau/segments;vertices.append((radius*math.cos(a),radius*math.sin(a),z))
for ring in range(len(profile)-1):
    for j in range(segments):faces.append((ring*segments+j,ring*segments+(j+1)%segments,(ring+1)*segments+(j+1)%segments,(ring+1)*segments+j))
mesh=bpy.data.meshes.new('Pot shell');mesh.from_pydata(vertices,[],faces);mesh.materials.append(M['iron'])
ob=bpy.data.objects.new('Camp cooking pot',mesh);bpy.context.collection.objects.link(ob)
cylinder('Soup surface',(0,0,.755),(0,0,.761),.251,'soup',24)
torus('Pot rim',(0,0,.84),.274,.02,'brass')
for i in range(13):
    angle=math.pi*i/12
    a=(.265*math.cos(angle),0,.845+.265*math.sin(angle))
    b=(.265*math.cos(angle+math.pi/12),0,.845+.265*math.sin(angle+math.pi/12))
    if i<12:cylinder('Pot bail handle',a,b,.014,'iron',8)
# Merge by material to keep the prop compact and reduce draw calls.
for mat in M.values():
    objects=[ob for ob in bpy.context.scene.objects if ob.type=='MESH' and len(ob.data.materials)==1 and ob.data.materials[0]==mat]
    if not objects:continue
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();objects[0].name='Camp '+mat.name
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'storybook-camp-v1.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'game/assets/storybook_camp_v1.glb'),export_format='GLB',export_yup=True,export_animations=False)
print('AUTHORED_CAMP_EXPORTED',len([o for o in bpy.context.scene.objects if o.type=='MESH']))
