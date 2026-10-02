"""Small developer-authored props. Blender never runs for player generation."""
import bpy,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/authored-environment';OUT.mkdir(exist_ok=True)

def material(name,color,metallic=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    rgb=[int(color[i:i+2],16)/255 for i in (0,2,4)]
    rgb=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb]
    p=m.node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Roughness'].default_value=.68;p.inputs['Metallic'].default_value=metallic
    return m

def cylinder(name,z,radius,depth,mat,vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=(0,0,z))
    o=bpy.context.object;o.name=name;o.data.materials.append(mat)
    mod=o.modifiers.new('Rounded ends','BEVEL');mod.width=.003;mod.segments=2;bpy.ops.object.modifier_apply(modifier=mod.name)
    for face in o.data.polygons:face.use_smooth=True
    return o

def blade(name,outline,width,mat):
    n=len(outline);verts=[(x,y,z) for y in [-width/2,width/2] for x,z in outline]
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.materials.append(mat)
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);bpy.context.view_layer.objects.active=o;o.select_set(True)
    bevel=o.modifiers.new('Soft forged edge','BEVEL');bevel.width=.006;bevel.segments=2;bpy.ops.object.modifier_apply(modifier=bevel.name)
    normals=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=normals.name)
    o.select_set(False)

for kind in ['axe','spear']:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    wood=material('Warm ash wood','9E754B');wrap=material('Forest green binding','687B65');steel=material('Satin forged steel','A8B9B0',.25);edge=material('Polished edge','D4DACE',.4)
    cylinder('Tapered wood handle',0,.018,1.0,wood)
    cylinder('Grip leather',-.08,.021,.19,wrap)
    for z in [-.175,-.125,-.075,-.025,.015]:cylinder('Grip seam',z,.022,.008,wood)
    cylinder('Handle cap',-.49,.023,.035,wrap)
    if kind=='axe':
        blade('Curved axe head',[(-.07,.39),(-.055,.49),(.045,.49),(.14,.54),(.24,.56),(.265,.52),(.28,.45),(.27,.37),(.245,.31),(.14,.34),(.055,.39)],.072,steel)
        blade('Sharpened curved blade',[(.24,.56),(.265,.52),(.28,.45),(.27,.37),(.245,.31),(.22,.335),(.24,.40),(.247,.46),(.23,.515)],.028,edge)
        cylinder('Head collar',.39,.028,.095,wrap)
    else:
        cylinder('Upper haft',.56,.016,.25,wood)
        blade('Leaf spearhead',[(0,.98),(.073,.78),(.055,.71),(0,.67),(-.055,.71),(-.073,.78)],.035,steel)
        blade('Center ridge',[(0,.97),(.012,.75),(0,.68),(-.012,.75)],.045,edge)
        cylinder('Spear socket',.66,.022,.12,wrap)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/f'{kind}-v1.blend'))
    bpy.ops.export_scene.gltf(filepath=str(ROOT/f'game/assets/authored_{kind}_v1.glb'),export_format='GLB',export_animations=False,export_yup=True)
    print('AUTHORED_TOOL',kind)
