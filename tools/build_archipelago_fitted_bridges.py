"""Author four bridges at their actual bank spans; never stretch a complete asset.
Run with Blender. The reviewed Tripo originals remain available separately.
"""
import json, math, random, shutil
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'labs/terrain_lab'
OUT=ROOT/'art/maps/archipelago_performance_v1'
DEST=LAB/'assets/fitted_bridges'
DEST.mkdir(parents=True,exist_ok=True)
layout=json.loads((LAB/'environment_layout.json').read_text(encoding='utf-8'))
backup=OUT/'layout_before_bridge_rebuild.json'
if not backup.exists():
    backup.write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
reports=[]
designs={'18_bridge_short':(3.15,1.10,'cedar'), '19_bridge_long':(3.45,1.65,'oak'),
         '48_bridge_rope':(2.85,-.35,'rope'),'49_bridge_boardwalk':(3.0,.12,'teal')}
for spec in layout['bridges']:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    width,rise,style=designs[spec['id']]
    span=math.dist(spec['a'],spec['b'])
    ga,gb=spec['bank_heights_m']
    random.seed(spec['id'])
    objects=[]
    def material(name,color,rough=.78):
        m=bpy.data.materials.new(name);m.diffuse_color=(*color,1)
        m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
        return m
    palettes={'cedar':(.54,.29,.105),'oak':(.37,.185,.072),'rope':(.42,.265,.13),'teal':(.48,.31,.16)}
    deck=material('Wood_Deck_'+style,palettes[style]); dark=material('Wood_Support',(.25,.135,.067))
    rail=material('Wood_Rail_'+style, (.12,.40,.38) if style=='teal' else palettes[style])
    cream=material('Wood_Cream',(.87,.79,.56)); rope=material('Rope_Fibre',(.58,.43,.25),.95)
    iron=material('Iron_Fasteners',(.14,.155,.155),.54)
    def height(z):
        t=max(0,min(1,z/span+.5))
        return ga+(gb-ga)*t+.025+rise*math.sin(math.pi*t)**2
    def slope(z):return (height(z+.01)-height(z-.01))/.02
    def finish(obj,mat,bevel=0):
        obj.data.materials.append(mat)
        if bevel:
            mod=obj.modifiers.new('Rounded_Edges','BEVEL');mod.width=bevel;mod.segments=2
            bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=mod.name)
        objects.append(obj)
        return obj
    def block(name,pos,dims,mat,bevel=.025,tilt=0):
        bpy.ops.mesh.primitive_cube_add(size=1,location=pos)
        obj=bpy.context.object;obj.name=name;obj.scale=dims
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        obj.rotation_euler.x=tilt
        return finish(obj,mat,bevel)
    def cylinder(name,pos,radius,depth,mat,segments=12):
        bpy.ops.mesh.primitive_cylinder_add(vertices=segments,radius=radius,depth=depth,location=pos)
        obj=bpy.context.object;obj.name=name
        return finish(obj,mat,.012)
    def curve(name,coords,radius,mat):
        data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=1
        data.bevel_depth=radius;data.bevel_resolution=2
        spline=data.splines.new('POLY');spline.points.add(len(coords)-1)
        for p,c in zip(spline.points,coords):p.co=(*c,1)
        obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.object.convert(target='MESH');finish(obj,mat)
    def curved_beam(name,x,offset,breadth,depth,mat):
        n=max(32,int(span*3));verts=[];faces=[]
        for i in range(n+1):
            z=-span/2+span*i/n;h=height(z)+offset
            verts.extend([(x-breadth/2,-z,h-depth/2),(x+breadth/2,-z,h-depth/2),(x+breadth/2,-z,h+depth/2),(x-breadth/2,-z,h+depth/2)])
        for i in range(n):
            a=i*4;b=a+4
            for j in range(4):faces.append((a+j,a+(j+1)%4,b+(j+1)%4,b+j))
        faces.extend([(3,2,1,0),(n*4,n*4+1,n*4+2,n*4+3)])
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);finish(obj,mat,.018)
    # Godot local +Z equals Blender -Y. All dimensions below are in metres.
    count=math.ceil(span/.42);pitch=span/count
    for i in range(count):
        z=-span/2+(i+.5)*pitch;h=height(z)
        block('Deck_Plank_%03d'%i,(0,-z,h-.10),(width,pitch-.009,.20),deck,.022,-math.atan(slope(z)))
        for side in [-1,1]:
            cylinder('Iron_Peg',(side*(width/2-.18),-z,h+.004),.023,.012,iron,8)
    for side in [-1,1]:
        curved_beam('Main_Curved_Girder',side*(width/2-.23),-.30,.25,.40,dark)
    post_count=math.ceil(span/(2.6 if style=='rope' else 2.25))
    zs=[-span/2+.1+(span-.2)*i/post_count for i in range(post_count+1)]
    for side in [-1,1]:
        x=side*(width/2+.025)
        for k,z in enumerate(zs):
            h=height(z);tall=1.40 if style=='rope' and k in (0,post_count) else 1.05
            block('Railing_Post',(x,-z,h+tall/2),(.18,.18,tall),rail,.035)
            block('Post_Cap',(x,-z,h+tall+.035),(.235,.235,.10),cream if style=='teal' else rail,.035)
        if style=='rope':
            for offset in [.48,.94]:
                for left,right in zip(zs,zs[1:]):
                    coords=[]
                    for j in range(13):
                        t=j/12;z=left+(right-left)*t
                        coords.append((x,-z,height(z)+offset-.14*math.sin(math.pi*t)))
                    curve('Sagging_Rope',coords,.045,rope)
        else:
            for offset in [.48,1.0]:
                curved_beam('Continuous_Rail',x,offset,.135,.13,cream if style=='teal' else rail)
            if style=='cedar':
                for i in range(math.ceil(span/.72)):
                    z=-span/2+.36+i*.72
                    if z<span/2-.2:block('Slender_Baluster',(x,-z,height(z)+.72),(.075,.075,.44),rail,.018)
            if style=='oak':
                for left,right in zip(zs,zs[1:]):
                    for reverse in [False,True]:
                        coords=[]
                        for j in range(9):
                            t=j/8;z=left+(right-left)*t
                            coords.append((x,-z,height(z)+.47+(.50*(1-t) if reverse else .50*t)))
                        curve('Cross_Brace',coords,.055,rail)
    # Posts enter the seabed and span is supported in sensible bays.
    for t in [.17,.5,.83]:
        z=(t-.5)*span;h=height(z)-.28
        block('Cross_Joist',(0,-z,h),(width+.35,.24,.24),dark,.025)
        for side in [-1,1]:
            x=side*(width/2-.24);bottom=-1.1
            cylinder('Timber_Pile',(x,-z,(h+bottom)/2),.19,h-bottom,dark)
            block('Pile_Collar',(x,-z,h-.23),(.46,.39,.16),dark,.02)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
    obj=bpy.context.object;obj.name=spec['id']+'_Authored';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    # Winding and normals are calculated explicitly after joining handmade beams.
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT')
    path=DEST/(spec['id']+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_yup=True,export_materials='EXPORT')
    spec['fitted_model']='res://assets/fitted_bridges/'+path.name
    spec['authored_at_bank_span']=True;spec['width_m']=width+.24;spec['scale_z']=1.0
    spec['deck_width_m']=width;spec['authored_rise_m']=rise
    spec['position']=[(spec['a'][0]+spec['b'][0])/2,0,(spec['a'][1]+spec['b'][1])/2]
    # Physical endpoints are exactly the two surveyed banks.
    spec['yaw_degrees']=math.degrees(math.atan2(spec['b'][0]-spec['a'][0],spec['b'][1]-spec['a'][1]))
    reports.append({'id':spec['id'],'span_m':span,'deck_width_m':width,'rise_m':rise,'style':style,'planks':count,'scale':[1,1,1],'original_tripo_preserved':True,'triangles':sum(len(p.vertices)-2 for p in obj.data.polygons)})
    print('AUTHORED_BRIDGE_READY',spec['id'],span,'scale_one',flush=True)
encoded=json.dumps(layout,ensure_ascii=False,indent=2)
(LAB/'environment_layout.json').write_text(encoded,encoding='utf-8')
(ROOT/layout['output_directory']/'environment_layout.json').write_text(encoded,encoding='utf-8')
(OUT/'bridge_rebuild.json').write_text(json.dumps({'bridges':reports,'policy':'Repeated physical planks, posts and rails; no whole-model stretch. Original Tripo assets retained.'},indent=2),encoding='utf-8')
(DEST/'layout.json').write_text(json.dumps({'bridges':layout['bridges']},ensure_ascii=False,indent=2),encoding='utf-8')
