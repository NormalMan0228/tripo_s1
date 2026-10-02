"""Developer environment art: both silhouettes fit the server's circular obstacle."""
import bpy,math,random,json
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/authored-environment';OUT.mkdir(exist_ok=True)
def material(name,color):
    channels=[int(color[i:i+2],16)/255 for i in (0,2,4)]
    channels=[v/12.92 if v<.04045 else ((v+.055)/1.055)**2.4 for v in channels]
    m=bpy.data.materials.new(name);m.diffuse_color=(*channels,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*channels,1);p.inputs['Roughness'].default_value=.82
    return m
M={k:material(k,v) for k,v in {'sandstone':'AD8967','warmstone':'C3A37E','darkstone':'816753','iron':'6B6556','ice':'8DADB8','deepice':'728D9D','snow':'D8E4DA','whitesnow':'E7EADF'}.items()}
def rock(name,at,size,mat,seed=0):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=at)
    obj=bpy.context.object;obj.name=name;obj.scale=size;obj.rotation_euler=(.08*seed,.04*seed,.37*seed);obj.data.materials.append(M[mat]);return obj
def block(name,at,size,mat,angle=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=at);ob=bpy.context.object;ob.name=name;ob.dimensions=size;ob.rotation_euler.z=angle
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);ob.data.materials.append(M[mat])
    bevel=ob.modifiers.new('Worn corners','BEVEL');bevel.width=.055;bevel.segments=2;bpy.ops.object.modifier_apply(modifier=bevel.name)
    return ob
def crystal(at,radius,height,mat,lean):
    points=[];faces=[];n=6
    for radius_scale,z in ((1,0),(.9,height*.75)):
        for i in range(n):
            a=i*math.tau/n;points.append((at[0]+radius*radius_scale*math.cos(a)+lean[0]*z,at[1]+radius*radius_scale*math.sin(a)+lean[1]*z,at[2]+z))
    points.append((at[0]+lean[0]*height,at[1]+lean[1]*height,at[2]+height))
    for i in range(n):faces.extend([(i,(i+1)%n,(i+1)%n+n,i+n),(i+n,(i+1)%n+n,2*n)])
    faces.append(tuple(reversed(range(n))))
    mesh=bpy.data.meshes.new('Ice prism');mesh.from_pydata(points,[],faces);mesh.materials.append(M[mat]);ob=bpy.data.objects.new('Weathered ice spire',mesh);bpy.context.collection.objects.link(ob)
def export(kind):
    # Bake and normalize just the horizontal footprint, leaving authored height.
    bpy.context.view_layer.update()
    radius=max(math.hypot(*(ob.matrix_world@vertex.co)[:2]) for ob in bpy.context.scene.objects if ob.type=='MESH' for vertex in ob.data.vertices)
    factor=.98/radius
    for ob in bpy.context.scene.objects:
        if ob.type!='MESH':continue
        matrix=ob.matrix_world.copy()
        for vertex in ob.data.vertices:
            p=matrix@vertex.co;vertex.co=Vector((p.x*factor,p.y*factor,max(0,p.z)))
        ob.matrix_world=Matrix.Identity(4)
    for mat in M.values():
        objects=[ob for ob in bpy.context.scene.objects if ob.type=='MESH' and ob.data.materials and ob.data.materials[0]==mat]
        if not objects:continue
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects:ob.select_set(True)
        bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();objects[0].name=kind+' '+mat.name
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(kind+'-v1.blend')))
    target=ROOT/'game/assets'/('storybook_'+kind+'_v1.glb')
    bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',export_yup=True,export_animations=False)
    print(json.dumps({'asset':target.name,'radius_max':.98,'meshes':sum(ob.type=='MESH' for ob in bpy.context.scene.objects)}))
for kind in ('quarry_outcrop','frost_outcrop'):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    if kind=='quarry_outcrop':
        rock('Foundation',(.03,0,.3),(.9,.84,.37),'darkstone',2)
        for layer,(z,width,depth,height) in enumerate([(.45,1.55,1.28,.5),(.81,1.35,1.12,.39),(1.13,1.06,.93,.32)]):
            block('Old cut stone ledge',(.05*math.sin(layer),0,z),(width,depth,height),'sandstone' if layer%2 else 'warmstone',.09*(layer-1))
        for i in range(6):
            a=i*math.tau/6;rock('Broken quarry chip',(.69*math.cos(a),.65*math.sin(a),.13),(.28,.23,.18),'warmstone' if i%2 else 'sandstone',i)
        # Recessed iron wedge and carved seams establish an abandoned worked quarry.
        for x in [-.37,.08,.42]:block('Weathered split groove',(x,-.535,.77),(.025,.035,.28),'darkstone')
        block('Old iron splitting wedge',(.24,-.23,1.36),(.08,.07,.29),'iron',.25)
    else:
        rock('Glacial foundation',(0,0,.31),(.88,.8,.41),'deepice',1)
        for i in range(5):
            a=i*math.tau/5
            rock('Ice shoulder',(.5*math.cos(a),.47*math.sin(a),.42),(.43,.4,.48),'ice',i)
            rock('Soft snow cap',(.5*math.cos(a),.47*math.sin(a),.8),(.43,.38,.15),'snow' if i%2 else 'whitesnow',i)
        crystal((-.22,.06,.6),.3,.95,'ice',(-.07,.07))
        crystal((.22,.2,.55),.2,.74,'deepice',(.17,.09))
        crystal((.07,-.32,.45),.17,.65,'ice',(.15,-.09))
        rock('Snow on tallest spire',(-.25,.11,1.46),(.16,.17,.1),'whitesnow',1)
    export(kind)
