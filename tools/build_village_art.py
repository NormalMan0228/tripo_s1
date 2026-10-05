"""Author a reusable, handcrafted village kit and a playable-map art export.

Runs in Blender 4.5. Retains editable source and individual modules; AI props
remain separately identified. Coordinates here are Blender Z-up, Godot Y-up.
"""
import bpy, math, random, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/detail-map-20261003';DEST=ROOT/'labs/village_art_lab/assets'
DEST.mkdir(parents=True,exist_ok=True);(OUT/'modules').mkdir(parents=True,exist_ok=True)
random.seed(37)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
def mat(name,color,rough=.82):
 color=tuple(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in color)
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Specular IOR Level'].default_value=.25
 return m
grass=mat('Meadow sage',(.32,.48,.20));grass2=mat('Soft grass',(.42,.56,.26));earth=mat('Terrace earth',(.38,.29,.18))
stone=[mat('Warm limestone '+str(i),(.44+i*.025,.43+i*.022,.36+i*.023)) for i in range(6)]
cream=mat('Warm lime plaster',(.86,.80,.62));wood=mat('Aged oak',(.32,.18,.084));woodlight=mat('Cut oak',(.48,.29,.14));dark=mat('Window recess',(.095,.15,.15))
roof=[mat('Patinated teal tile '+str(i),(.08+i*.012,.29+i*.014,.29+i*.009)) for i in range(7)]
metal=mat('Forged iron',(.07,.08,.068),.55);glass=mat('Amber window',(.95,.66,.28),.38)
painted=OUT/'materials/timber_touchup.png'
if painted.exists():
 image=bpy.data.images.load(str(painted));image.colorspace_settings.name='sRGB'
 for material,gain in [(wood,.65),(woodlight,1.0)]:
  nodes=material.node_tree.nodes;links=material.node_tree.links
  tex=nodes.new('ShaderNodeTexImage');tex.image=image;tex.extension='REPEAT'
  mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;mix.inputs[2].default_value=(gain,gain,gain,1)
  links.new(tex.outputs['Color'],mix.inputs[1]);links.new(mix.outputs[0],nodes.get('Principled BSDF').inputs['Base Color'])
leaves=[mat('Orchard foliage '+str(i),(.16+i*.025,.35+i*.023,.13+i*.013)) for i in range(5)]
pink=mat('Rose petals',(.81,.37,.39));yellow=mat('Butter flowers',(.95,.73,.23));white=mat('Linen',(.9,.86,.71));soil=mat('Garden soil',(.24,.16,.085));red=mat('Ripe apples',(.68,.15,.1))
water=mat('River turquoise',(.15,.47,.47),.21)
parts=[]
geometry_cache={}
def register(o,name,material):
 o.name=name
 if material and material.name not in o.data.materials:o.data.materials.append(material)
 parts.append(o);return o
def box(name,loc,scale,material,bevel=.045):
 key=('box',tuple(scale),bevel,material.name if material else '')
 if key in geometry_cache:
  o=bpy.data.objects.new(name,geometry_cache[key]);scene.collection.objects.link(o);o.location=loc;return register(o,name,material)
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=register(bpy.context.object,name,material);o.scale=scale
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  b=o.modifiers.new('Rounded crafted edges','BEVEL');b.width=bevel;b.segments=2
  bpy.ops.object.modifier_apply(modifier=b.name)
  n=o.modifiers.new('Soft normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=n.name)
 geometry_cache[key]=o.data
 return o
def sphere(name,loc,scale,material,detail=1):
 key=('sphere',detail,material.name)
 if key in geometry_cache:
  o=bpy.data.objects.new(name,geometry_cache[key]);scene.collection.objects.link(o);o.location=loc;o.scale=scale;return register(o,name,material)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=detail+1,radius=1,location=loc);o=register(bpy.context.object,name,material);o.scale=scale
 for p in o.data.polygons:p.use_smooth=True
 geometry_cache[key]=o.data
 return o
def beam(name,a,b,r,material,vertices=10):
 a,b=Vector(a),Vector(b);d=b-a
 key=('beam',vertices,material.name)
 if key in geometry_cache:
  o=bpy.data.objects.new(name,geometry_cache[key]);scene.collection.objects.link(o);o.location=(a+b)*.5;register(o,name,material)
 else:
  bpy.ops.mesh.primitive_cone_add(vertices=vertices,radius1=1,radius2=.91,depth=1,location=(a+b)*.5)
  o=register(bpy.context.object,name,material);geometry_cache[key]=o.data
 o.scale=(r,r,d.length);o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
 for p in o.data.polygons:p.use_smooth=True
 return o
def mesh(name,vs,fs,material):
 data=bpy.data.meshes.new(name);data.from_pydata(vs,[],fs);data.update();o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);return register(o,name,material)
def arch(name,x,y,z,width,height,depth,material):
 r=width/2;vs=[];profile=[(-r,0),(r,0)]+[(r*math.cos(t),height-r+r*math.sin(t)) for t in [i*math.pi/12 for i in range(13)]]
 for yy in [-depth/2,depth/2]:vs.extend((x+px,y+yy,z+pz) for px,pz in profile)
 n=len(profile);fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 return mesh(name,vs,fs,material)
def flower(loc,material=pink,size=.12):
 x,y,z=loc;beam('Flower stem',(x,y,z),(x,y,z+.28),.017,leaves[0],6)
 for i in range(5):
  t=i*math.tau/5;sphere('Soft petal',(x+math.cos(t)*size*.55,y+math.sin(t)*size*.55,z+.29),(size*.6,size*.6,.044),material,0)
 sphere('Pollen heart',(x,y,z+.31),(.038,.038,.034),yellow,0)
def planter(x,y,z,w=1.3):
 box('Flower box',(x,y,z),(w,.42,.34),woodlight)
 box('Rich soil',(x,y,z+.17),(w-.08,.33,.025),soil,.008)
 for i in range(7):flower((x-w*.4+i*w*.8/6,y+random.uniform(-.1,.1),z+.18),pink if i%3 else white,.09)
def lamp(x,y,z=0):
 beam('Lamp post',(x,y,z),(x,y,z+2.5),.075,metal)
 beam('Lamp arm',(x,y,z+2.4),(x+.4,y,z+2.4),.055,metal)
 box('Lantern light',(x+.4,y,z+2.05),(.26,.26,.46),glass,.05)
 box('Lantern cap',(x+.4,y,z+2.32),(.36,.36,.09),metal)
 for sx in [-1,1]:
  for sy in [-1,1]:beam('Lantern frame',(x+.4+sx*.13,y+sy*.13,z+1.82),(x+.4+sx*.13,y+sy*.13,z+2.29),.024,metal,6)
def tree(x,y,z=0,scale=1,fruit=False):
 beam('Orchard trunk',(x,y,z),(x+.13*scale,y,z+2.7*scale),.2*scale,wood)
 for i in range(6):
  t=i*2.399;bx=x+math.cos(t)*.85*scale;by=y+math.sin(t)*.85*scale;bz=z+(2.55+random.uniform(-.25,.5))*scale
  beam('Tree bough',(x,y,z+1.8*scale),(bx,by,bz),.085*scale,wood)
  sphere('Rounded leaf crown',(bx,by,bz+.35*scale),(1.05*scale,.9*scale,.95*scale),leaves[i%5],1)
  if fruit:
   for j in range(3):sphere('Apple',(bx+random.uniform(-.5,.5)*scale,by-.72*scale,bz+random.uniform(-.3,.3)*scale),(.11*scale,)*3,red,1)
def cottage():
 box('Limestone plinth',(0,0,.22),(5.2,4.1,.44),stone[3],.1)
 box('Limewashed walls',(0,0,1.8),(4.9,3.85,3.1),cream,.10)
 for x in [-2.4,2.4]:
  for y in [-1.91,1.91]:box('Corner timber',(x,y,1.88),(.23,.23,3.1),wood)
 for z in [.63,3.05]:box('Facade cross beam',(0,-1.98,z),(5.05,.16,.18),wood)
 mesh('Gable front',[(-2.45,-1.93,3.35),(2.45,-1.93,3.35),(0,-1.93,5.2)],[(0,1,2)],cream)
 mesh('Gable back',[(-2.45,1.93,3.35),(0,1.93,5.2),(2.45,1.93,3.35)],[(0,1,2)],cream)
 for y in [-2.04,2.03]:
  beam('Gable timber',(-2.65,y,3.3),(0,y,5.26),.13,woodlight)
  beam('Gable timber',(0,y,5.26),(2.65,y,3.3),.13,woodlight)
  box('Gable central post',(0,y,4.0),(.14,.13,2.1),wood)
 for side in [-1,1]:
  for row in range(9):
   u=(row+.5)/9;x=side*(u*2.8);z=5.22-u*1.98
   for col in range(13):
    y=-2.22+col*.365+(row%2)*.12
    # Rounded individual clay slates overlap along the slope.
    tile=box('Individual scalloped roof tile',(x,y,z),(.48,.385,.10),roof[random.randrange(7)],.075)
    tile.rotation_euler.y=side*math.atan(1.98/2.8)
 beam('Roof ridge cap',(0,-2.5,5.27),(0,2.5,5.27),.18,roof[4],12)
 arch('Door dark reveal',0,-2.025,.4,1.44,2.39,.06,dark)
 arch('Oak arched door',0,-2.075,.43,1.24,2.25,.09,woodlight)
 for x in [-.44,-.22,0,.22,.44]:
  top=2.09+math.sqrt(max(0,.62**2-x*x));box('Door plank seam',(x,-2.135,(.46+top)/2),(.018,.014,top-.46),wood,.005)
 for z in [1.0,1.9]:box('Iron door strap',(-.35,-2.16,z),(.36,.025,.06),metal,.016)
 sphere('Door handle',(.41,-2.19,1.37),(.07,.055,.07),metal,1)
 for x in [-1.65,1.65]:
  arch('Window oak frame',x,-2.04,1.22,1.07,1.25,.12,wood)
  arch('Amber window glass',x,-2.12,1.31,.87,1.08,.05,dark)
  box('Window mullion',(x,-2.16,1.84),(.05,.04,1.0),woodlight,.01)
  box('Window sill',(x,-2.17,1.25),(1.19,.22,.10),stone[3])
  planter(x,-2.28,1.03,1.2)
 box('Front doorstep',(0,-2.31,.21),(1.66,.62,.30),stone[4],.06)
 box('Front second step',(0,-2.62,.07),(1.9,.52,.13),stone[2],.04)
 for k in range(7):
  for i in range(2):box('Chimney brick',(1.61+(i-.5)*.35,1.0+((k%2)*.1),4.33+k*.19),(.36,.6,.19),stone[(k+i)%6],.025)
 box('Chimney crown',(1.61,1.03,5.65),(.92,.84,.16),stone[1])
 lamp(2.8,-2.22)
def bridge():
 for i in range(17):
  y=-2+i*.25;z=.16+.24*(1-(y/2.1)**2)
  box('Bridge oak deck',(0,y,z),(3.3,.235,.17),woodlight,.04)
 for side in [-1,1]:
  for y in [-1.9,-.95,0,.95,1.9]:beam('Bridge timber post',(side*1.6,y,.1),(side*1.6,y,1.13),.085,wood)
  for i in range(4):
   a=-1.9+i*.95;b=a+.95
   beam('Bridge handrail',(side*1.6,a,1.1),(side*1.6,b,1.1),.09,woodlight)
def fence(x,y,length):
 for i in range(int(length/.85)+1):
  xx=x+i*.85;box('Fence picket',(xx,y,.53),(.11,.10,1.06),woodlight,.035)
 for z in [.34,.76]:box('Fence rail',(x+length*.5,y+.025,z),(length+.14,.095,.095),wood)
def export_selected(objects,path):
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_animations=False)
def module(name,fn):
 start=len(parts);fn();objects=parts[start:];export_selected(objects,OUT/'modules'/f'{name}.glb')
 return objects
house=module('teal_cottage',cottage);house_original=[o.matrix_world.copy() for o in house]
def place_copy(objects,position,name):
 result=[]
 for o in objects:
  c=o.copy();c.data=o.data;scene.collection.objects.link(c);c.location+=Vector(position);c.name=name+' '+o.name;parts.append(c);result.append(c)
 return result
# Blender Y points north, converted to Godot -Z.
for o in house:o.location+=Vector((10,14,0))
bridge_objects=module('timber_bridge',bridge)
for o in bridge_objects:o.location.y+=8
sample=module('apple_tree',lambda:tree(0,0,0,1,True))
for o in sample:o.location+=Vector((-12,-8,0))
for x,y,s in [(-16,-6,.85),(-17,3,.95),(-16,7,1.1),(16,-7,1.0),(18,3,.95),(17,10,.8),(-8,16,.85),(-5,17,.9),(0,17,.95),(4,16,.85),(-18,14,.9)]:
 for o in sample:
  c=o.copy();scene.collection.objects.link(c);c.location=(o.location-Vector((-12,-8,0)))*s+Vector((x,y,0));c.scale*=s;parts.append(c)
for y in [-2.7,18]:
 for x in [-18,18]:tree(x,y,0,.7,False)
# River separates southern square and northern orchard.
for y,sy in [(-5.6,22.8),(13.6,8.8)]:box('Meadow base',(0,y,-.26),(44,sy,.5),grass,.20)
box('River bed',(0,8,-.63),(44,3.4,.35),earth,.05)
box('River surface',(0,8,-.38),(44,3.35,.04),water,0)
for bank in [6.35,9.65]:
 for x in range(-22,23):sphere('Riverbank rock',(x,bank,-.21),(random.uniform(.5,.8),.36,.37),stone[random.randrange(6)],1)
# Cobble street and a generous circular plaza.
for x in range(-35,36):
 for y in range(-25,35):
  xx=x*.48+random.uniform(-.03,.03);yy=y*.48+random.uniform(-.02,.02)
  in_plaza=(xx/5.2)**2+((yy+4)/4.0)**2<1
  in_path=(abs(xx)<1.35 and -13<yy<17) or (abs(yy-0)<1.22 and abs(xx)<14) or (abs(yy-13)<1.0 and abs(xx)<14)
  if (in_plaza or in_path) and not 6.2<yy<9.8:
   cobble=box('Worn irregular cobblestone',(xx,yy,.021+random.uniform(0,.022)),(random.choice([.39,.42,.45]),random.choice([.39,.42,.45]),.072),stone[random.randrange(6)],.065)
   cobble.rotation_euler.z=random.uniform(-.09,.09)
# Garden, orchard props and planted banks.
for x in [5.8,7.4,9]:
 for y in [-8.5,-10.1]:
  box('Raised garden frame',(x,y,.16),(1.4,1.35,.28),woodlight,.05)
  box('Garden soil',(x,y,.31),(1.25,1.21,.09),soil,.025)
  for dx in [-.3,.3]:
   for dy in [-.3,.3]:
    sphere('Leafy crop',(x+dx,y+dy,.49),(.26,.26,.17),leaves[4],1)
    sphere('Crop heart',(x+dx,y+dy,.50),(.12,.12,.18),leaves[2],1)
fence(4.6,-11.25,5.7);fence(-16,17.3,12)
for i in range(95):
 x=random.uniform(-19,19);y=random.uniform(-13,18)
 if abs(x)>14 or (abs(x)>3 and 3<y<5):flower((x,y,0),pink if i%2 else yellow,.10)
for x,y in [(-13,-2),(-6,2),(6,2),(13,-2),(-3,12),(5,15),(14,5),(-16,-10)]:
 for j in range(3):sphere('Soft border shrub',(x+(j-1)*.48,y,.42),(.6,.55,.56),leaves[(j+2)%5],1)
for i in range(210):
 x=random.uniform(-19,19);y=random.uniform(-13,18)
 if abs(x)<2 or 6.2<y<9.8 or (abs(y)<1.5 and abs(x)<15):continue
 for j in range(3):beam('Meadow grass blade',(x+j*.05,y,0),(x+j*.05-.07,y+.02,.16+random.random()*.10),.014,leaves[4],4)
for x,y in [(-5,-1),(5,-1),(-2,12),(3,-8),(13,-8)]:lamp(x,y)
for i in range(22):
 x=random.choice([-1,1])*random.uniform(20,26);y=random.uniform(-17,24)
 sphere('Distant rounded hill',(x,y,-.6),(random.uniform(4,6),random.uniform(4,6),random.uniform(2,4)),grass2,2)
for x,y in [(-5,-7),(-2,-10),(12,-5)]:
 box('Bench seat',(x,y,.51),(1.9,.53,.12),woodlight)
 box('Bench back',(x,y+.22,.97),(1.9,.10,.55),woodlight)
 for xx in [x-.67,x+.67]:beam('Bench leg',(xx,y-.12,.05),(xx,y-.12,.52),.065,metal)
# Imported AI market and well. Normalize for reusable local coordinates.
ai_meta=[]
for name,pos,width in [('market-stall',(-6,-6,0),3.3),('garden-well',(0,-4,0),1.9),('teal-cottage',(-13,14,0),5.2)]:
 path=OUT/'tripo/village_map'/name/'model.glb'
 if not path.exists():continue
 before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(path))
 objects=[o for o in bpy.data.objects if o not in before];ms=[o for o in objects if o.type=='MESH']
 points=[o.matrix_world@Vector(v) for o in ms for v in o.bound_box]
 lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
 fac=width/max(hi.x-lo.x,hi.y-lo.y);mid=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
 for o in ms:
  for v in o.data.vertices:v.co=(o.matrix_world@v.co-mid)*fac
  o.parent=None;o.matrix_world.identity();parts.append(o)
  for m in o.data.materials:
   if m and m.use_nodes:
    for n in m.node_tree.nodes:
     if n.type=='BSDF_PRINCIPLED':n.inputs['Roughness'].default_value=.8;n.inputs['Metallic'].default_value=0
 export_selected(ms,OUT/'modules'/f'ai_{name}.glb')
 for o in ms:o.location=pos
 instances=[pos]
 if name=='teal-cottage':
  for extra in [(-9,1,0),(9,1,0)]:
   for o in ms:
    c=o.copy();scene.collection.objects.link(c);c.location=extra;c.rotation_mode='XYZ';c.rotation_euler=(0,0,-math.pi*.75);parts.append(c)
   instances.append(extra)
 ai_meta.append({'name':name,'size_m':list((hi-lo)*fac),'instances':instances,'module_origin':'bottom center at zero'})
 for o in objects:
  if o.type!='MESH':bpy.data.objects.remove(o,do_unlink=True)
# An optional standalone portal is exported for future authored buildings.
# The generated cottages retain their own doors: no unrelated arch is grafted on.
def portal():
 arch('Entrance timber arch',0,-.04,.12,1.42,2.22,.13,wood)
 arch('Entrance oak door',0,-.12,.17,1.17,2.06,.08,woodlight)
 for xx in [-.42,-.21,0,.21,.42]:
  top=1.7+math.sqrt(max(0,.58**2-xx**2));box('Entrance plank seam',(xx,-.17,(.2+top)/2),(.014,.014,top-.2),wood,.003)
 sphere('Entrance handle',(.37,-.19,1.1),(.06,.04,.06),metal,1)
 box('Entrance threshold',(0,-.23,.1),(1.6,.64,.2),stone[2],.06)
entrance=module('cottage_portal',portal)
for o in entrance:
 parts.remove(o);bpy.data.objects.remove(o,do_unlink=True)
# Save editable modular source before batching render surfaces.
scene.render.engine='CYCLES';scene.cycles.samples=48
scene.world.color=(.45,.50,.55)
source=ROOT/'art/source/village_art_20261003.blend';source.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(source))
# Batch by exact material set: retain source objects in .blend, avoid thousands of draw calls.
groups={}
for o in list(parts):
 if o.type=='MESH':groups.setdefault(tuple(m.name if m else '' for m in o.data.materials),[]).append(o)
joined=[]
for key,objects in groups.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 if len(objects)>1:bpy.ops.object.join()
 joined.append(bpy.context.object)
export_selected(joined,DEST/'village.glb')
stats={'source':str(source.relative_to(ROOT)),'modules':[p.name for p in (OUT/'modules').glob('*.glb')],'batched_meshes':len(joined),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in joined),'ai_props':ai_meta,'style_reference':'artifacts/concepts/20261001/set-10/01-village-square.png','coordinate_system':'Blender Z-up exported to Godot Y-up'}
(OUT/'map-manifest.json').write_text(json.dumps(stats,indent=2),encoding='utf-8');print('VILLAGE_EXPORTED',stats)
# Separate reusable roofless interior for an uninterrupted, readable game camera.
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);parts=[];geometry_cache={}
for i in range(19):box('Interior oak floor',(0,-3+i*.34,-.05),(7,.32,.16),woodlight,.025)
for x in [-3.5,3.5]:box('Interior plaster side',(x,0,1.5),(.22,6.5,3),cream,.04)
box('Interior back wall',(0,3.25,1.5),(7,.22,3),cream,.04)
for x in [-3.45,3.45]:box('Interior timber corner',(x,3.13,1.5),(.22,.18,3),wood)
box('Interior skirting',(0,3.09,.22),(7,.12,.22),wood)
box('Woven rug',(0,-.1,.05),(2.8,3.6,.035),white,.12)
for yy in [-1.65,1.45]:box('Rug teal border',(0,yy,.071),(2.6,.13,.015),roof[2],.01)
box('Dining table',(0,1,.85),(1.7,1.1,.16),woodlight,.08)
for x in [-.66,.66]:
 for y in [.6,1.4]:beam('Table leg',(x,y,0),(x,y,.8),.07,wood)
for x in [-1.35,1.35]:
 box('Chair seat',(x,1,.49),(.65,.65,.13),woodlight)
 box('Chair back',(x,1.27,.96),(.64,.10,.65),woodlight)
 for dx in [-.22,.22]:
  for dy in [-.22,.22]:beam('Chair leg',(x+dx,1+dy,0),(x+dx,1+dy,.48),.05,wood)
box('Kitchen cabinet',(-2.25,2.75,.62),(1.65,.85,1.24),wood,.06)
box('Kitchen counter',(-2.25,2.75,1.28),(1.78,.97,.13),stone[4],.05)
for x in [-2.65,-1.85]:box('Cabinet panel',(x,2.29,.66),(.69,.09,.88),woodlight,.035)
for z in [1.75,2.35]:
 box('Wall shelf',(-2.25,3,z),(1.75,.43,.09),woodlight)
 for i in range(5):sphere('Ceramic jar',(-2.85+i*.29,2.95,z+.18),(.1,.1,.16),cream if i%2 else roof[3],1)
arch('Interior window',1.1,3.10,1.1,1.3,1.55,.05,dark)
box('Interior window mullion',(1.1,3.05,1.84),(.065,.06,1.45),woodlight,.01)
planter(2.78,2.4,.55,.75)
box('Bed frame',(2.45,.4,.30),(1.5,2.7,.42),wood)
box('Quilt',(2.45,.3,.6),(1.45,2.5,.28),roof[4],.14)
box('Soft pillow',(2.45,1.21,.79),(1.15,.51,.23),white,.12)
export_selected(parts,DEST/'cottage_interior.glb')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/source/cottage_interior_20261003.blend'))
