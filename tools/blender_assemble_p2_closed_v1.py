"""P2 bust with latest refined HD hair, fitted eye assets, closed rest and original open morph."""
import bpy,bmesh,math,json,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_closed_assembly_v1';O.mkdir(exist_ok=True)
P=R/'art/characters/explorer_b_open_mouth_p2_v1';REF=R/'art/references/explorer_b_hybrid_hair_hd_v1'
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene
def col(name):
 c=bpy.data.collections.new(name);sc.collection.children.link(c);return c
headcol=col('01_Head_closed_rest');eyeCol=col('02_Eyes');haircol=col('03_Latest_HD_hair');cardscol=col('04_Brows_lashes');oralcol=col('05_Original_P2_oral_parts');srcCol=col('90_Preserved_sources');studio=col('99_Studio')
def move(o,c):
 for old in list(o.users_collection):old.objects.unlink(o)
 c.objects.link(o)
def mat(name,c,rough=.5):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*c,1);p=m.node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;return m
skin=mat('Skin_neutral_peach_preview',(.63,.37,.245),.48)
skin.node_tree.nodes['Principled BSDF'].inputs['Subsurface Weight'].default_value=.045
lip=mat('Lips_soft_rose',(.48,.185,.14),.42)
mucosa=mat('Oral_mucosa',(.18,.025,.035),.48);enamel=mat('Enamel_ivory',(.83,.80,.69),.25);tonguemat=mat('Tongue',(.38,.075,.09),.45)
def meshobj(name,vs,fs,collection,material):
 m=bpy.data.meshes.new(name);m.from_pydata(vs,[],fs);m.update();o=bpy.data.objects.new(name,m);collection.objects.link(o)
 if material:m.materials.append(material)
 for p in m.polygons:p.use_smooth=True
 return o
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def tree(o):
 o.data.calc_loop_triangles();return BVHTree.FromPolygons([v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
bpy.ops.import_scene.fbx(filepath=str(P/'model.fbx'),use_anim=False)
raw=next(o for o in sc.objects if o.type=='MESH');raw.name='P2_OPEN_SOURCE_UNCHANGED';move(raw,srcCol)
raw.data.transform(raw.matrix_world);raw.matrix_world=Matrix.Identity(4);raw.hide_render=True;raw.hide_set(True);raw.hide_select=True
bm=bmesh.new();bm.from_mesh(raw.data);bm.verts.ensure_lookup_table();seen=set();groups=[]
for v in bm.verts:
 if v.index in seen:continue
 stack=[v];seen.add(v.index);g=[]
 while stack:
  a=stack.pop();g.append(a)
  for e in a.link_edges:
   b=e.other_vert(a)
   if b.index not in seen:seen.add(b.index);stack.append(b)
 groups.append(g)
groups.sort(key=len,reverse=True);parts=[];eye_centers=[]
for g in groups:
 coords=[v.co.copy() for v in g];lo=Vector([min(v[i] for v in coords) for i in range(3)]);hi=Vector([max(v[i] for v in coords) for i in range(3)])
 center=(lo+hi)/2
 if len(g)>10000:name='HEAD_closed_rest';collection=headcol;material=skin
 elif center.z<-.25:continue
 elif center.z>0:
  if len(g)>500:eye_centers.append((center, (hi-lo).length/3**.5/2))
  continue
 elif center.z>-.09:name='TEETH_upper_P2';collection=oralcol;material=enamel
 elif len(g)>180:name='TEETH_lower_P2';collection=oralcol;material=enamel
 else:name='TONGUE_P2';collection=oralcol;material=tonguemat
 ids={v.index:i for i,v in enumerate(g)};faces=set(f for v in g for f in v.link_faces)
 o=meshobj(name,[tuple(v.co) for v in g],[tuple(ids[v.index] for v in f.verts) for f in faces],collection,material);parts.append(o)
bm.free();head=bpy.data.objects['HEAD_closed_rest']
# Remove only generated material below the clavicle base, before adding shape keys.
bm=bmesh.new();bm.from_mesh(head.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,plane_co=(0,0,-.365),plane_no=(0,0,1),clear_inner=True)
es=[e for e in bm.edges if e.is_boundary and all(abs(v.co.z+.365)<.00001 for v in e.verts)]
if es:bmesh.ops.holes_fill(bm,edges=es,sides=0)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(head.data);bm.free();head.data.update()
opened=np.array([v.co[:] for v in head.data.vertices]);surface=tree(head)
def front(y,z):
 p,*_=surface.ray_cast(Vector((2,y,z)),Vector((-1,0,0)));return p.x if p else -.3
# Measure the actual open lip aperture at many lateral positions.
ys=np.linspace(-.07,.07,141);upper=[];lower=[];ux=[];lx=[]
for y in ys:
 zz=np.linspace(-.14,-.045,381);gap=[z for z in zz if front(y,z)<.15]
 if gap:
  b=min(gap)-.0005;a=max(gap)+.0005
 else:a=b=-.081
 upper.append(a);lower.append(b);ux.append(front(y,a));lx.append(front(y,b))
def profile(arr,y):return float(np.interp(y,ys,arr))
def jaw(c):
 pivot=Vector((-.09,0,-.025));return pivot+Matrix.Rotation(-.070,3,'Y')@(Vector(c)-pivot)
closed=[];lipweights=[]
for c in opened:
 x,y,z=c;q=Vector(c);a=profile(upper,y);b=profile(lower,y);gap=max(0,a-b)
 depth=smooth(.15,.23,x)
 if abs(y)<.07 and gap>.0005:
  seam=a-.24*gap
  if z<(a+b)/2:
   w=smooth(-.245,-.15,z)*depth
   q.z+=(seam-b+.00025)*w
   q.x+=(profile(ux,y)-.004-profile(lx,y))*math.exp(-((z-b)/.031)**4)*depth*smooth(0,.012,gap)
  else:
   w=(1-smooth(a+.017,a+.048,z))*depth
   q.z+=(seam-a-.00025)*w;q.x-=.006*w
 closed.append(q)
 topweight=math.exp(-((z-(a+.010))/.014)**4)
 botweight=math.exp(-((z-(b-.013))/.018)**4)
 lipweights.append(max(topweight,botweight)*smooth(.23,.28,x)*(1-smooth(.055,.075,abs(y))))
head.data.materials.append(mucosa)
for p in head.data.polygons:
 c=sum((Vector(opened[i]) for i in p.vertices),Vector())/len(p.vertices);x,y,z=c
 if False:p.material_index=1  # Keep outer and inner head skin consistent until final UV painting.
color=head.data.color_attributes.new(name='LipTint',type='FLOAT_COLOR',domain='POINT')
for v,w in zip(color.data,lipweights):v.color=(w,w,w,1)
nd=skin.node_tree.nodes;lk=skin.node_tree.links;att=nd.new('ShaderNodeVertexColor');att.layer_name='LipTint';mix=nd.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.63,.37,.245,1);mix.inputs[2].default_value=(.48,.185,.14,1);lk.new(att.outputs['Color'],mix.inputs[0]);lk.new(mix.outputs[0],nd['Principled BSDF'].inputs['Base Color'])
# Relax only the moved lower-face surface; keep the lip contact band fixed.
adj=[set() for _ in closed]
for e in head.data.edges:
 a,b=e.vertices;adj[a].add(b);adj[b].add(a)
for iteration in range(10):
 previous=[p.copy() for p in closed]
 for i,c in enumerate(opened):
  x,y,z=c
  if x<.20 or abs(y)>.135 or not -.245<z<-.050 or not adj[i]:continue
  a=profile(upper,y);b=profile(lower,y);seam=a-.24*max(0,a-b)
  if abs(previous[i].z-seam)<.015 and abs(y)<.062:continue
  weight=.24*smooth(.20,.24,x)*(1-smooth(.10,.135,abs(y)))
  avg=sum((previous[k] for k in adj[i]),Vector())/len(adj[i]);closed[i]=previous[i].lerp(avg,weight)
for v,q in zip(head.data.vertices,closed):v.co=q
ctrl=bpy.data.objects.new('FACE_CONTROLS',None);oralcol.objects.link(ctrl);ctrl.empty_display_size=.025;ctrl.location=(.45,0,-.25)
ctrl['mouth_open']=0.;ctrl.id_properties_ui('mouth_open').update(min=0,max=1,description='0: closed rest. 1: original Tripo open mouth. Inspection morph; full facial rig pending.')
def morph(o,original):
 o.shape_key_add(name='Basis_closed');key=o.shape_key_add(name='Mouth_open_original')
 for v,c in zip(key.data,original):v.co=c
 d=key.driver_add('value').driver;d.expression='op';v=d.variables.new();v.name='op';v.type='SINGLE_PROP';v.targets[0].id=ctrl;v.targets[0].data_path='["mouth_open"]'
morph(head,opened)
for name in ['TEETH_lower_P2','TONGUE_P2']:
 o=bpy.data.objects[name];original=[v.co.copy() for v in o.data.vertices]
 for v in o.data.vertices:v.co=jaw(v.co)
 morph(o,original)
# Latest locally refined hair, not earlier generated hair.
with bpy.data.libraries.load(str(R/'art/characters/explorer_b_hybrid_bust_v2/explorer_b_hybrid_bust_v2.blend'),link=False) as (a,b):b.objects=['HAIR_HD_FITTED']
hair=b.objects[0];haircol.objects.link(hair);hair.name='HAIR_latest_v2_fitted_to_P2';hair.hide_render=False;hair.hide_set(False)
hair['source']='explorer_b_hybrid_bust_v2 / HAIR_HD_FITTED'
hair.data=hair.data.copy()
# Similar normalized head proportions; slight expansion around the new temples.
for v in hair.data.vertices:v.co.y*=1.015;v.co.z+=.008
hair.data.update()
# Smooth separate eyeballs. Their centers are derived from generated eye components.
white=mat('Sclera_warm_white',(.82,.85,.80),.22);white.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value=.45
iris=mat('Iris_brown_radial_fibers',(.20,.085,.024),.25);ip=iris.node_tree.nodes['Principled BSDF'];ip.inputs['Coat Weight'].default_value=.6;ip.inputs['Coat Roughness'].default_value=.1
nodes=iris.node_tree.nodes;links=iris.node_tree.links
uv=nodes.new('ShaderNodeTexCoord');mul=nodes.new('ShaderNodeVectorMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=(110,5,1);links.new(uv.outputs['UV'],mul.inputs[0])
noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=2;noise.inputs['Detail'].default_value=3;links.new(mul.outputs['Vector'],noise.inputs['Vector'])
ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.15;ramp.color_ramp.elements[0].color=(.026,.010,.003,1);ramp.color_ramp.elements[1].position=.83;ramp.color_ramp.elements[1].color=(.36,.17,.044,1);links.new(noise.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs[0],ip.inputs['Base Color'])
pupil=mat('Pupil_deep_brown',(.0015,.001,.0005),.16);pupil.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value=.5
limbus=mat('Iris_outer_dark_ring',(.018,.009,.004),.23)
eyes=[]
for center,r in eye_centers:
 side='L' if center.y>0 else 'R';center.x+=.008;radius=r*1.015
 bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=40,radius=radius,location=center)
 eye=bpy.context.object;eye.name='EYEBALL_'+side;move(eye,eyeCol);eye.data.materials.append(white)
 for f in eye.data.polygons:f.use_smooth=True
 eyes.append(eye)
 verts=[];faces=[];uvs=[];N=96;M=20;ir=.052
 for j in range(M+1):
  rr=max(.00001,ir*j/M)
  for i in range(N+1):
   a=2*math.pi*i/N;verts.append((center.x+math.sqrt(radius*radius-rr*rr)+.00035,center.y+rr*math.cos(a),center.z+rr*math.sin(a)));uvs.append((i/N,j/M))
 for j in range(M):
  for i in range(N):
   k=j*(N+1)+i;faces.append((k,k+1,k+N+2,k+N+1))
 disc=meshobj('IRIS_PUPIL_'+side,verts,faces,eyeCol,iris);disc.data.materials.append(pupil);disc.data.materials.append(limbus);layer=disc.data.uv_layers.new(name='Radial_fibers')
 for p in disc.data.polygons:
  ring=p.index//N;p.material_index=1 if ring<7 else (2 if ring>=19 else 0)
  for li in p.loop_indices:layer.data[li].uv=uvs[disc.data.loops[li].vertex_index]
 disc.parent=eye;disc.matrix_parent_inverse=eye.matrix_world.inverted()
 eye['purpose']='Separate smooth eye for later gaze rig; generated eye relief removed from working copy.'
# Alpha atlas reused without modifying its image, with root-following curved UV strips.
atlas=bpy.data.images.load(str(REF/'production_inputs/brow_lash_atlas.png'))
cardmat=mat('Brow_lash_alpha_clean',(.055,.018,.008),.62);nd=cardmat.node_tree.nodes;lk=cardmat.node_tree.links;bs=nd['Principled BSDF']
tex=nd.new('ShaderNodeTexImage');tex.image=atlas;tex.extension='CLIP';lk.new(tex.outputs['Color'],bs.inputs['Base Color'])
th=nd.new('ShaderNodeMapRange');th.clamp=True;th.inputs['From Min'].default_value=.20;th.inputs['From Max'].default_value=.85;lk.new(tex.outputs['Alpha'],th.inputs['Value'])
attr=nd.new('ShaderNodeVertexColor');attr.layer_name='EdgeFade';multiply=nd.new('ShaderNodeMath');multiply.operation='MULTIPLY';lk.new(th.outputs[0],multiply.inputs[0]);lk.new(attr.outputs['Color'],multiply.inputs[1]);lk.new(multiply.outputs[0],bs.inputs['Alpha']);cardmat.surface_render_method='DITHERED';cardmat.use_transparency_overlap=False
pixels=np.array(atlas.pixels[:]).reshape(atlas.size[1],atlas.size[0],4)[::-1];alpha=pixels[:,:,3]
closedtree=tree(head)
def skinx(y,z):
 p,*_=closedtree.ray_cast(Vector((2,y,z)),Vector((-1,0,0)));return p.x if p else .2
# Use the actual P2 aperture, not the previous model's eyelid curve.
sample_y=np.linspace(.066,.196,49);bottom=[];top=[]
for y in sample_y:
 zz=np.linspace(.055,.19,271);gap=[z for z in zz if front(y,z)<.145]
 if gap:bottom.append(min(gap)-.001);top.append(max(gap)+.001)
 else:bottom.append(.117);top.append(.119)
def root(side,s,up):
 y=.069+.124*s;z=float(np.interp(y,sample_y,top if up else bottom));x=skinx(y,z)
 return Vector((x+.0009,side*y,z))
lash_stats=[]
for up in [True,False]:
 nx=48;ny=4;xs=np.linspace(120,925,nx+1) if up else np.linspace(205,1070,nx+1);roots=[]
 for x in xs:
  lo,hi=(450,900) if up else (970,1200);ix=int(x);score=(alpha[lo:hi,max(0,ix-4):ix+5]>.85).sum(1);roots.append(int(np.argmax(np.convolve(score,np.ones(7),mode='same')))+lo)
 roots=np.convolve(np.pad(roots,(2,2),mode='edge'),np.ones(5)/5,mode='valid')
 for side in [-1,1]:
  vs=[];fs=[];uvs=[];fades=[]
  for j in range(ny+1):
   t=j/ny
   for i,px in enumerate(xs):
    s=i/nx;r=root(side,s,up);length=((.008+.026*s) if up else (.003+.006*s))*math.sin(math.pi*s)**.4
    q=r+Vector((.010*t,side*.005*t*s,(1 if up else -1)*length*t));q.x=max(q.x,skinx(abs(q.y),q.z)+.002);vs.append(q)
    uvs.append((px/1254,1-(roots[i]-2+t*(175 if up else 62))/1254));fades.append(min(1,s*9,(1-s)*12))
  for j in range(ny):
   for i in range(nx):k=j*(nx+1)+i;fs.append((k,k+1,k+nx+2,k+nx+1))
  o=meshobj('LASH_'+('upper' if up else 'lower')+('_L' if side>0 else '_R'),vs,fs,cardscol,cardmat)
  o.data.uv_layers.new(name='HairAtlas');o.data.color_attributes.new(name='EdgeFade',type='FLOAT_COLOR',domain='CORNER');uv=o.data.uv_layers['HairAtlas'];fade=o.data.color_attributes['EdgeFade']
  for p in o.data.polygons:
   for li in p.loop_indices:
    vi=o.data.loops[li].vertex_index;uv.data[li].uv=uvs[vi];fade.data[li].color=(fades[vi],)*3+(1,)
  lash_stats.append({'object':o.name,'root_offset':.0009,'quads':len(fs)})
for side in [-1,1]:
 nx=64;ny=12;vs=[];fs=[];uvs=[]
 for j in range(ny+1):
  t=j/ny
  for i in range(nx+1):
   s=i/nx;y=.067+.15*s;z=.204+.025*math.sin(math.pi*s)-.018*s+(t-.5)*.052
   vs.append((skinx(y,z)+.0025,side*y,z));uvs.append(((60+1165*s)/1254,1-(45+400*(1-t))/1254))
 for j in range(ny):
  for i in range(nx):k=j*(nx+1)+i;fs.append((k,k+1,k+nx+2,k+nx+1))
 o=meshobj('BROW_'+('L' if side>0 else 'R'),vs,fs,cardscol,cardmat);o.data.uv_layers.new(name='HairAtlas');o.data.color_attributes.new(name='EdgeFade',type='FLOAT_COLOR',domain='CORNER');uv=o.data.uv_layers['HairAtlas'];fade=o.data.color_attributes['EdgeFade']
 for p in o.data.polygons:
  for li in p.loop_indices:
   vi=o.data.loops[li].vertex_index;uv.data[li].uv=uvs[vi];fade.data[li].color=(1,1,1,1)
# Inspection studio and editable default state.
sc.world=bpy.data.worlds.new('Studio');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.23,.28,.35,1);sc.world.node_tree.nodes['Background'].inputs[1].default_value=.35
sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 if any(d.type=='CUDA' for d in prefs.devices):sc.cycles.device='GPU'
except Exception:pass
for name,loc,power,size in [('Key',(2,-2,2.5),150,1.5),('Fill',(2,2,1),90,1.8),('Rim',(-1,0,2),180,1.5)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);studio.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,.12))-o.location).to_track_quat('-Z','Y').to_euler();o.hide_set(True)
cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));studio.objects.link(cam);cam.data.type='ORTHO';sc.camera=cam;cam.hide_set(True)
sc.render.resolution_x=900;sc.render.resolution_y=1000;sc.render.resolution_percentage=100;sc.view_settings.view_transform='AgX'
def view(offset,target=(0,0,.08),scale=1.14):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
view((3,0,0));ctrl['mouth_open']=0.;sc.frame_set(1);bpy.context.view_layer.update()
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.shading.type='MATERIAL';s.overlay.show_extras=False;s.overlay.show_floor=False;s.overlay.show_axis_x=False;s.overlay.show_axis_y=False
   s.region_3d.view_location=(0,0,.08);s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.6;s.region_3d.view_perspective='ORTHO'
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
for img in bpy.data.images:
 if img.source=='FILE':img.pack()
text=bpy.data.texts.new('READ_ME');text.write('Default is closed mouth. Select FACE_CONTROLS > custom properties > mouth_open (0..1) to restore original Tripo opening. Head, lower teeth and tongue follow. This is not a full facial rig.\nLatest refined HD hair from hybrid_bust_v2. Separate eyeballs/irises, eyebrow/lash UV cards. Skin is a neutral preview material, not projected photo texture.\nOriginal Tripo open head preserved in hidden source collection.\n')
target=O/'explorer_b_P2_closed_assembly_v1.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target))
for name,pos in [('front',(3,0,0)),('angle',(3,-2,.05)),('side',(0,-3,0))]:
 view(pos);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True;view((3,0,0),(0,0,.04),.66);sc.render.filepath=str(O/'face_detail.png');bpy.ops.render.render(write_still=True)
view((3,-.3,0),(.20,0,-.075),.32);sc.render.filepath=str(O/'mouth_closed.png');bpy.ops.render.render(write_still=True)
ctrl['mouth_open']=1.;sc.frame_set(2);bpy.context.view_layer.update();sc.render.filepath=str(O/'mouth_open.png');bpy.ops.render.render(write_still=True)
report={'output':str(target),'api_credits':0,'hair_source':'explorer_b_hybrid_bust_v2/HAIR_HD_FITTED','default_mouth_open':0,'source_open_morph_preserved':True,'full_face_rig':False,'head_vertices':len(head.data.vertices),'head_faces':len(head.data.polygons),'eyeballs':[o.name for o in eyes],'lash_cards':lash_stats,'oral_objects':[o.name for o in oralcol.objects],'skin':'neutral procedural preview material; no face image projection','lips_profile':{'y':ys.tolist(),'upper':upper,'lower':lower}}
(O/'assembly-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ASSEMBLY_SAVED',str(target))
