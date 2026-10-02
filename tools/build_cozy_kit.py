"""Authored environment kit: furnished wall shell and ivy-covered departure arch.

Fixed decor stays outside the server's placement cells and workshop reserved area.
Coordinates use Blender X=game X, Y=-game Z, Z=game Y.
"""
import bpy, math, random, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import build_village_landmarks as kit
random.seed(6301)
palette={**kit.COLORS,'sage':'89977C','ink':'454F53','blue':'7E9B9C','rose':'B9877F','cloth':'DED2B6','floor_a':'B69268','floor_b':'C5A578','floor_c':'AA825C','moss':'70896A','paper':'EBDFBA','gold':'C3A061'}
def box(name,at,size,mat,bevel=.025,rotation=(0,0,0)):return kit.box(name,at,size,mat,bevel,rotation)
def cyl(name,at,r,h,mat,n=12,rotation=(0,0,0)):return kit.cyl(name,at,r,h,mat,n,rotation)
def ball(name,at,size,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=.5,location=at)
    o=bpy.context.object;o.name=name;o.scale=size;o.data.materials.append(kit.M[mat])
    for p in o.data.polygons:p.use_smooth=True
    return o
def fresh(kind):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    kit.M={k:kit.material(kind+'_'+k,v) for k,v in palette.items()}
def export(kind):
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/source'/f'{kind}.blend'),compress=True)
    for material in kit.M.values():
        group=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.materials and o.data.materials[0]==material]
        if len(group)<2:continue
        bpy.ops.object.select_all(action='DESELECT')
        for o in group:o.select_set(True)
        bpy.context.view_layer.objects.active=group[0];bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'game/assets'/f'{kind}.glb'),export_format='GLB',export_apply=True)
    print('COZY_KIT_EXPORTED',kind)
def curtain(x):
    # Soft folds have a real silhouette; no flat painted curtain plane.
    for side in [-1,1]:
        for i in range(5):
            cx=x+side*(.79+i*.063)
            cyl('Curtain fold',(cx,4.43,2.12),.053,1.68,'cloth',8)
        box('Curtain tie',(x+side*.93,4.33,1.67),(.27,.07,.055),'gold',.02)
    cyl('Curtain rod',(x,4.4,3.05),.034,2.5,'timber',8,(0,math.pi/2,0))
    for side in [-1,1]:ball('Rod finial',(x+side*1.26,4.4,3.05),(.12,.12,.12),'gold')
def plant(at):
    x,y,z=at
    cyl('Clay planter',(x,y,z+.13),.16,.26,'rose',12);cyl('Pot rim',(x,y,z+.28),.185,.07,'rose',12)
    for i in range(7):
        a=i*2.4;leaf=ball('Soft plant leaf',(x+math.cos(a)*.1,y+math.sin(a)*.1,z+.42),(.15,.08,.31),'leaf');leaf.rotation_euler=(math.sin(a)*.45,math.cos(a)*.45,a)
def interior(kind):
    fresh(kind);workshop=kind=='cozy_workshop'
    box('Raised floor frame',(0,0,-.18),(10.4,10.4,.32),'timber',.08)
    # Staggered planks, each with a small bevel; join by palette for efficient rendering.
    for col in range(20):
        x=-4.75+col*.5;offset=(col%3)*1.2
        stops=sorted(set([-5,5]+[max(-5,min(5,-5+offset+j*3.33)) for j in range(5)]))
        for a,b in zip(stops,stops[1:]):
            if b-a<.05:continue
            box('Staggered oak plank',(x,(a+b)/2,-.015),(.492,b-a-.012,.075),['floor_a','floor_b','floor_c'][(col+int(a*3))%3],.012)
            for py in (a+.12,b-.12):
                if b-a>.35:
                    for dx in [-.15,.15]:cyl('Small oak peg',(x+dx,py,.025),.012,.012,'timber',6)
    box('Back plaster wall',(0,5,1.73),(10.35,.20,3.48),'white',.025)
    box('Left plaster wall',(-5,0,1.73),(.20,10.35,3.48),'cream',.025)
    for x in [-5,-1.15,1.15,5]:box('Back timber stud',(x,4.82,1.75),(.14,.15,3.50),'timber')
    for y in [-5,-1.3,1.4,5]:box('Left timber stud',(-4.82,y,1.75),(.15,.14,3.50),'timber')
    for z in [.12,.34,3.25,3.43]:
        box('Back moulding',(0,4.79,z),(10.15,.18,.11),'oak')
        box('Left moulding',(-4.79,0,z),(.18,10.15,.11),'oak')
    for x in [-2.6,2.6]:
        box('Deep window frame',(x,4.76,2.10),(2.03,.30,1.84),'timber',.05)
        box('Morning glass',(x,4.56,2.10),(1.76,.06,1.54),'glass',.025)
        for side in [-1,1]:
            box('Ivory sash',(x+side*.87,4.47,2.10),(.075,.09,1.58),'white')
            box('Ivory sash',(x,4.47,2.10+side*.79),(1.8,.09,.075),'white')
        box('Window muntin',(x,4.44,2.10),(.07,.10,1.57),'white')
        box('Window muntin',(x,4.44,2.10),(1.8,.10,.07),'white')
        box('Wide window sill',(x,4.42,1.28),(2.28,.52,.13),'oak',.04)
        curtain(x)
        plant((x-.65,4.35,1.35))
    box('Wall shelf',(-4.56,1.55,2.36),(.43,2.1,.10),'oak')
    for i in range(11):
        y=.64+i*.155
        o=box('Books with linen covers',(-4.52,y,2.61),(.29,.13,.42+random.random()*.13),['sage','rose','blue','paper'][i%4],.012)
        o.rotation_euler.x=random.uniform(-.06,.06)
        box('Book spine band',(-4.35,y,2.64),(.015,.14,.025),'gold',.004)
    # Small geometric landscape in a deep wooden frame, not a generated bitmap.
    box('Picture frame',(-4.7,-2.3,2.12),(.16,1.55,1.20),'timber',.055)
    box('Picture paper',(-4.59,-2.3,2.12),(.04,1.35,1.0),'paper')
    for i in range(5):ball('Landscape hills',(-4.55,-2.76+i*.23,1.96),(.035,.55,.36),['sage','blue','moss'][i%3])
    ball('Painted sun',(-4.55,-2.07,2.37),(.035,.18,.18),'gold')
    # Woven rug has inset border and a stitched edge; all geometry lies flat.
    box('Woven sage rug',(0,0,.035),(3.8,3.2,.018),'sage',.065)
    for x in [-1.73,1.73]:box('Rug border',(x,0,.048),(.065,3.0,.013),'cloth',.01)
    for y in [-1.43,1.43]:box('Rug border',(0,y,.048),(3.5,.065,.013),'cloth',.01)
    for i in range(36):
        x=-1.7+i*.096
        for side in [-1,1]:box('Rug fringe',(x,side*1.62,.04),(.025,.10,.012),'cloth',.004)
    box('Clear door threshold',(0,-4.8,.04),(2.6,.45,.10),'oak',.025)
    for x in [-1.25,1.25]:box('Cutaway doorpost',(x,-5,.34),(.18,.2,.7),'timber')
    if workshop:
        box('Fixed artisan bench',(-3.7,3.1,.85),(1.8,1,.16),'oak',.045)
        for x in [-4.4,-3]:
            for y in [2.7,3.5]:box('Workbench leg',(x,y,.4),(.12,.12,.8),'timber')
        box('Workbench lower shelf',(-3.7,3.1,.24),(1.6,.85,.10),'oak')
        for i in range(4):cyl('Paint pot',(-4.25+i*.34,3.3,1.05),.11,.26,['rose','blue','gold','leaf'][i],12)
        for i in range(3):box('Brush handle',(-3.2+i*.055,3.4,1.38),(.015,.015,.58),'timber',.003,(-.12,.12*i,0))
        box('Folded linen',(-3.85,2.92,.97),(.6,.38,.05),'cloth')
    export(kind)
def arch():
    fresh('departure_arch')
    for side in [-1,1]:
        box('Stone footing',(side*1.30,0,.16),(.91,1.0,.32),'stone',.07)
        for row in range(5):
            box('Weathered pillar block',(side*1.29,random.uniform(-.02,.02),.43+row*.41),(.65,.75,.39),'stone' if row%3 else 'slate',.045,(0,0,random.uniform(-.035,.035)))
    for i in range(13):
        a0=i*math.pi/13+.012;a1=(i+1)*math.pi/13-.012
        verts=[(math.cos(a)*r,y,2.29+math.sin(a)*r) for y in [-.42,.42] for r in [1.0,1.65] for a in [a0,a1]]
        faces=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
        mesh=bpy.data.meshes.new('Arch stone');mesh.from_pydata(verts,[],faces);mesh.update()
        o=bpy.data.objects.new('Radial carved voussoir',mesh);bpy.context.collection.objects.link(o);mesh.materials.append(kit.M['stone' if i%3 else 'cream'])
        bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Chipped edges','BEVEL');mod.width=.035;mod.segments=2;bpy.ops.object.modifier_apply(modifier=mod.name)
        mod=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=mod.name)
    for i in range(31):
        z=.43+i*.098;x=-1.55+math.sin(i*.8)*.16
        leaf=ball('Climbing ivy',(x,-.45,z),(.27,.12,.22),'leaf' if i%3 else 'moss');leaf.rotation_euler.y=math.sin(i)*.8
    box('Hanging trail sign',(0,-.55,3.50),(1.3,.13,.35),'oak',.055)
    for x in [-.45,.45]:cyl('Rope sign hanger',(x,-.55,3.78),.025,.4,'rope')
    # A seed-shaped inset, recognizable from the game currency icon.
    ball('Trail seed emblem',(0,-.64,3.51),(.14,.025,.22),'gold')
    export('departure_arch')
def fishing_rod():
    fresh('fishing_rod')
    # Shaft bends subtly toward its tip; grip origin is the player's palm.
    for i in range(12):
        z=-.18+i*.15;x=.024*max(0,(z-.75))**2
        radius=.018*(1-i*.045)
        cyl('Tapered bamboo section',(x,0,z+.075),radius,.152,'oak' if i<3 else 'gold',10)
        if i<4:cyl('Cork grip band',(x,0,z+.025),radius+.003,.018,'timber',10)
    for z in [.45,.88,1.3,1.59]:
        bpy.ops.mesh.primitive_torus_add(major_radius=.031,minor_radius=.006,major_segments=12,minor_segments=5,location=(.044,0,z),rotation=(0,math.pi/2,0))
        o=bpy.context.object;o.name='Rod line guide';o.data.materials.append(kit.M['ink'])
    cyl('Reel spindle',(.07,0,-.005),.064,.105,'teal_dark',16,(0,math.pi/2,0))
    for x in [.018,.122]:cyl('Reel rim',(x,0,-.005),.08,.015,'slate',16,(0,math.pi/2,0))
    box('Reel attachment',(.043,0,.075),(.078,.022,.13),'ink',.012)
    box('Reel crank',(.145,-.025,-.005),(.018,.095,.018),'slate',.006)
    cyl('Crank knob',(.16,-.07,-.005),.021,.045,'timber',10,(0,math.pi/2,0))
    export('fishing_rod')
def rowboat():
    fresh('shore_rowboat')
    # Open clinker hull, with nested rings so the boat has a visible interior.
    n=32;verts=[]
    for rx,ry,z in [(.65,1.55,.60),(.36,1.26,.12),(.54,1.39,.58),(.32,1.17,.22)]:
        for i in range(n):
            a=i*math.tau/n;verts.append((math.cos(a)*rx,math.sin(a)*ry,z+.09*abs(math.sin(a))**5))
    faces=[]
    for a,b in [(0,1),(0,2),(2,3)]:
        for i in range(n):j=(i+1)%n;faces.append((a*n+i,a*n+j,b*n+j,b*n+i))
    mesh=bpy.data.meshes.new('Open clinker hull');mesh.from_pydata(verts,[],faces);mesh.update();mesh.materials.append(kit.M['teal'])
    obj=bpy.data.objects.new('Open painted hull',mesh);bpy.context.collection.objects.link(obj)
    mod=obj.modifiers.new('Soft boat edges','BEVEL');mod.width=.015;mod.segments=2;bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=mod.name)
    for i in range(n):
        a=i*math.tau/n;b=(i+1)*math.tau/n
        p=Vector((math.cos(a)*.645,math.sin(a)*1.545,.63+.09*abs(math.sin(a))**5))
        q=Vector((math.cos(b)*.645,math.sin(b)*1.545,.63+.09*abs(math.sin(b))**5))
        o=cyl('Oak gunwale',(p+q)/2,.035,(q-p).length,'oak',8);o.rotation_euler=(q-p).to_track_quat('Z','Y').to_euler()
    for y in [-.6,.35]:box('Rowing bench',(0,y,.5),(1.06,.27,.08),'oak',.025)
    for x in [-.27,0,.27]:box('Interior floorboard',(x,0,.24),(.255,2.24,.05),'floor_a',.014)
    cyl('Oar handle',(.02,.16,.69),.024,2.43,'timber',10,(math.pi/2,0,-.20))
    box('Oar blade',(-.19,1.28,.69),(.15,.47,.035),'oak',.035,(0,0,.2))
    export('shore_rowboat')
for kind in ['cozy_home','cozy_workshop']:interior(kind)
arch()
fishing_rod()
from mathutils import Vector
rowboat()
