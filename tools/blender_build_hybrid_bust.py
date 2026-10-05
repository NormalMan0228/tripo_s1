"""Review assembly from preserved Tripo sources and UV-mapped alpha cards."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v1'
REF=R/'art/references/explorer_b_hybrid_hair_hd_v1'
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
def collect(name):
    c=bpy.data.collections.new(name);sc.collection.children.link(c);return c
headcol=collect('01_P2_Head_Review');haircol=collect('02_HD_Hair_Review');cardcol=collect('03_UV_Brows_Lashes');sourcecol=collect('90_Original_Tripo_Sources')
def move(o,c):
    for old in list(o.users_collection):old.objects.unlink(o)
    c.objects.link(o)
def imported(path,name,c):
    old=set(bpy.data.objects)
    if path.suffix=='.fbx':bpy.ops.import_scene.fbx(filepath=str(path),use_anim=False)
    else:bpy.ops.import_scene.gltf(filepath=str(path))
    meshes=[o for o in set(bpy.data.objects)-old if o.type=='MESH']
    for o in meshes:
        mat=o.matrix_world.copy();o.parent=None;o.data.transform(mat);o.matrix_world=Matrix.Identity(4)
        move(o,c)
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    if len(meshes)>1:bpy.ops.object.join()
    o=bpy.context.object;o.name=name
    src=o.copy();src.data=o.data.copy();sourcecol.objects.link(src);src.name=name+'_ORIGINAL';src.hide_render=True;src.hide_set(True)
    return o
head=imported(O/'head/model.fbx','HEAD_P2_CLEANUP',headcol)
hair=imported(O/'hair/model.glb','HAIR_HD_FITTED',haircol)
def bounds(o):return [[min(v.co[i] for v in o.data.vertices),max(v.co[i] for v in o.data.vertices)] for i in range(3)]
rawbounds={'head':bounds(head),'hair':bounds(hair)}
# Remove the generated pedestal below the approved clavicle silhouette.
bm=bmesh.new();bm.from_mesh(head.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.00001,plane_co=(0,0,-.365),plane_no=(0,0,1),clear_inner=True,clear_outer=False)
edge=[e for e in bm.edges if e.is_boundary and all(abs(v.co.z+.365)<.0001 for v in e.verts)]
if edge:bmesh.ops.holes_fill(bm,edges=edge,sides=0)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
# P2 contains inconsistent patch winding. Orient each disconnected component
# outward without changing the generated positions or forcing a voxel remesh.
bm.verts.ensure_lookup_table();seen=set();groups=[]
for v in bm.verts:
    if v.index in seen:continue
    stack=[v];seen.add(v.index);g=[]
    while stack:
        a=stack.pop();g.append(a)
        for e in a.link_edges:
            b=e.other_vert(a)
            if b.index not in seen:seen.add(b.index);stack.append(b)
    groups.append(g)
for g in groups:
    faces=set(f for v in g for f in v.link_faces)
    center=sum((v.co for v in g),Vector())/len(g)
    for f in faces:
        c=f.calc_center_median()
        if len(g)>10000:
            if c.z<-.3649:out=Vector((0,0,-1))
            elif c.z<-.19:out=Vector((c.x+.08,c.y,0))
            else:out=c-Vector((-.015,0,.15))
        else:out=c-center
        if f.normal.dot(out)<0:f.normal_flip()
bm.to_mesh(head.data);bm.free()
for o in [head,hair]:
    bpy.context.view_layer.objects.active=o
    if o.data.has_custom_normals:bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in o.data.polygons:p.use_smooth=True
    o.data.update()
# Fit the generated hair envelope to the skull, retaining the original HD copy.
hb=bounds(hair);width=hb[1][1]-hb[1][0];scale=.84/width
center=Vector([(a+b)/2 for a,b in hb]);top=hb[2][1]
for v in hair.data.vertices:
    v.co=(v.co-center)*scale
    v.co.z+=.60-(top-center.z)*scale
    v.co.x=v.co.x*1.12-.015
hair.data.update()
def mat(name,color,rough=.5):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
    return m
skin=mat('Skin_preview_front_projection_NOT_final_UV',(.59,.31,.19),.55)
nodes=skin.node_tree.nodes;links=skin.node_tree.links;p=nodes.get('Principled BSDF')
tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(REF/'01_head_neck_clavicle_smartmesh.png'));tex.extension='EXTEND'
uv=head.data.uv_layers.new(name='Reference_Front_Preview')
for poly in head.data.polygons:
    for li in poly.loop_indices:
        co=head.data.vertices[head.data.loops[li].vertex_index].co
        u=(284+(co.y+.31958)/.63916*(1026-284))/1312
        v=1-(67+(.499756-co.z)/(.499756+.365)*(1072-67))/1199
        uv.data[li].uv=(u,v)
uvnode=nodes.new('ShaderNodeUVMap');uvnode.uv_map=uv.name;links.new(uvnode.outputs['UV'],tex.inputs['Vector'])
geom=nodes.new('ShaderNodeNewGeometry');sep=nodes.new('ShaderNodeSeparateXYZ');links.new(geom.outputs['Normal'],sep.inputs[0])
ramp=nodes.new('ShaderNodeMapRange');links.new(sep.outputs['X'],ramp.inputs['Value']);ramp.inputs['From Min'].default_value=.15;ramp.inputs['From Max'].default_value=.65
mix=nodes.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.59,.31,.19,1);links.new(ramp.outputs['Result'],mix.inputs[0]);links.new(tex.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],p.inputs['Base Color'])
head.data.materials.clear();head.data.materials.append(skin)
pos=nodes.new('ShaderNodeSeparateXYZ');links.new(geom.outputs['Position'],pos.inputs[0])
neckfade=nodes.new('ShaderNodeMapRange');neckfade.inputs['From Min'].default_value=-.285;neckfade.inputs['From Max'].default_value=-.34;links.new(pos.outputs['Z'],neckfade.inputs['Value'])
neckmix=nodes.new('ShaderNodeMixRGB');neckmix.inputs[2].default_value=(.78,.49,.34,1);links.new(mix.outputs[0],neckmix.inputs[1]);links.new(neckfade.outputs[0],neckmix.inputs[0]);links.new(neckmix.outputs[0],p.inputs['Base Color'])
hairmat=mat('Hair_chocolate_preview',(.045,.016,.007),.62);hairmat.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value=.22;hair.data.materials.clear();hair.data.materials.append(hairmat)
# Atlas is preserved RGBA; UV coordinates isolate each row, no raster edits.
atlas=bpy.data.images.load(str(REF/'production_inputs/brow_lash_atlas.png'))
cardsmat=mat('Brow_Lash_RGBA_Atlas',(.075,.025,.009),.72)
nodes=cardsmat.node_tree.nodes;links=cardsmat.node_tree.links;p=nodes.get('Principled BSDF')
tex=nodes.new('ShaderNodeTexImage');tex.image=atlas;tex.extension='CLIP';links.new(tex.outputs['Color'],p.inputs['Base Color']);links.new(tex.outputs['Alpha'],p.inputs['Alpha'])
cardsmat.surface_render_method='DITHERED';cardsmat.use_transparency_overlap=False
head.data.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in head.data.vertices],[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True)
def surface(y,z):
    hit=tree.ray_cast(Vector((2,y,z)),Vector((-1,0,0)))
    return hit[0].x if hit[0] is not None else .2
def card(name,rect,yrange,zrange,flip=False):
    verts=[];faces=[];uvs=[];nx=16;ny=4
    for j in range(ny+1):
        t=j/ny;z=zrange[0]+(zrange[1]-zrange[0])*t
        for i in range(nx+1):
            s=i/nx;y=yrange[0]+(yrange[1]-yrange[0])*s
            x=surface(y,z)+.0025
            verts.append((x,y,z));u=(rect[0]+s*(rect[2]-rect[0]))/1254
            py=rect[1]+(t if flip else 1-t)*(rect[3]-rect[1]);uvs.append((u,1-py/1254))
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new(name,mesh);cardcol.objects.link(o);mesh.materials.append(cardsmat)
    uv=mesh.uv_layers.new(name='HairAtlas')
    for p in mesh.polygons:
        p.use_smooth=True
        for li in p.loop_indices:uv.data[li].uv=uvs[mesh.loops[li].vertex_index]
    mirror=o.modifiers.new('Mirror_to_opposite_side','MIRROR');mirror.use_axis=(False,True,False);mirror.use_clip=False;mirror.use_mirror_merge=False
    o['authoring']='One side, mirrored Y; apply mirror before independent left/right facial skinning.'
    o['rigging_status']='Static fit only; bind to forehead or corresponding eyelid during facial rigging.'
    return o
brow=card('BROW_master_mirrored',(60,45,1225,445),(.056,.253),(.200,.279))
upper=card('LASH_UPPER_master_mirrored',(60,450,1230,920),(.064,.240),(.132,.211),True)
lower=card('LASH_LOWER_master_mirrored',(150,950,1150,1240),(.068,.240),(.038,.084))
# Review scene, neutral closed mouth; no synthetic facial animation.
sc.world=bpy.data.worlds.new('Studio');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.32,.36,.4,1);sc.world.node_tree.nodes['Background'].inputs[1].default_value=.5
sc.render.engine='CYCLES';sc.cycles.samples=32;sc.cycles.use_denoising=True
sc.render.resolution_x=900;sc.render.resolution_y=1000;sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'
def area(name,loc,power,size):
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,0,.1))-o.location).to_track_quat('-Z','Y').to_euler()
area('Key',(2,-2,3),220,2);area('Fill',(1,2,1),100,2);area('Rim',(-1,0,2),160,1.5)
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=1.18;sc.camera=cam
target=Vector((0,0,.08))
def view(offset):cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
view((3,0,.02))
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            s=a.spaces.active;s.shading.type='MATERIAL';s.overlay.show_extras=False;s.overlay.show_floor=False;s.overlay.show_axis_x=False;s.overlay.show_axis_y=False
            s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_location=target;s.region_3d.view_distance=1.7;s.region_3d.view_perspective='ORTHO'
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
sc['STATUS']='Generation and static fitting review; no facial rig yet. Head front color is a reference projection, not final texturing. HD hair requires retopology.'
bpy.context.preferences.filepaths.save_version=0
for img in bpy.data.images:
    if img.source=='FILE':img.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'explorer_b_hybrid_bust_v1.blend'))
report={'raw_bounds':rawbounds,'fitted_bounds':{'head':bounds(head),'hair':bounds(hair)},'mesh_stats':{o.name:{'verts':len(o.data.vertices),'polygons':len(o.data.polygons)} for o in [head,hair,brow,upper,lower]},'head_cleanup':'Removed generated pedestal below clavicle; corrected inconsistent patch winding with component-aware outward orientation. Source preserved.','textures':'RGBA brow/lash atlas packed. Head preview reference projection only. Hair uniform preview material.','rigged':False,'production_ready':False,'api_credits':140,'known_limitations':['Generated P2 topology still needs facial deformation review; no blink or mouth rig installed.','HD hair is a source mesh, not a game-ready retopologized asset.','Head reference projection is for appearance review; final UV/texture work remains.','Hair fit and lash attachment require user review before rigging.']}
(O/'assembly-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for name,offset in [('front',(3,0,.02)),('angle',(3,-2,.15)),('side',(0,-3,.02))]:
    view(offset);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True;view((3,0,.02));sc.render.filepath=str(O/'face_cards.png');bpy.ops.render.render(write_still=True)
print(json.dumps(report),flush=True)
