"""Replace rejected sheet experiment with individually modeled closed hair locks."""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1'
SOURCE=BASE/'hair_v3_cleanup_v2/character_face_preparation_v2.blend'
OUT=BASE/'hair_v3_nape_locks_v2';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
hair=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('Hair'))
head=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('01_Face'))
def geometry_hash(o):
    data={'v':[v.co[:] for v in o.data.vertices],'f':[p.vertices[:] for p in o.data.polygons]}
    if o.data.shape_keys:data['keys']={k.name:[v.co[:] for v in k.data] for k in o.data.shape_keys.key_blocks}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
original={o.name:geometry_hash(o) for o in scene.objects if o.type=='MESH'}
head.data.calc_loop_triangles()
skin=BVHTree.FromPolygons([head.matrix_world@v.co for v in head.data.vertices],[t.vertices[:] for t in head.data.loop_triangles],all_triangles=True)
def skin_r(theta,z):
    d=Vector((-math.cos(theta),math.sin(theta),0));o=d*2;o.z=z
    point=skin.ray_cast(o,-d,3)[0]
    if point is None:raise RuntimeError('Scalp ray miss')
    return point.dot(d)
coll=bpy.data.collections.new('Nape_hair__individual_3D_locks');scene.collection.children.link(coll)
locks=[];diagnostics=[]
for k in range(9):
    angle=(k-4)*.29
    root_z=.105+.025*math.cos(k*1.7)
    tip_z=-.225+.022*math.sin(k*2.1)+.025*(abs(angle)/1.16)
    rings=34;sides=20
    verts=[];faces=[];samples=[]
    for j in range(rings+1):
        t=j/rings
        theta=angle+.055*math.sin(math.pi*t)*(-1 if k<4 else 1)
        z=root_z+(tip_z-root_z)*t
        profile=math.sin(math.pi*t)**.7
        width=.071*profile*(1-.12*t)
        depth=.021*profile
        spread=width/.30
        # Keep the full cross-section outside the nearby scalp, while retaining
        # a smoothly rounded outer lock and a distinctly tapered free tip.
        r=max(skin_r(theta+da,z+dz) for da in (-spread,-spread/2,0,spread/2,spread) for dz in (-.015,0,.015))
        r+=depth+.021+.014*math.sin(math.pi*t)
        samples.append((theta,z,width,depth,r))
    # Smooth each strand path independently, retaining enough radial clearance.
    radii=[]
    for j in range(rings+1):
        weights=[math.exp(-.5*((q-j)/3.0)**2) for q in range(rings+1)]
        radii.append(sum(w*samples[q][4] for q,w in enumerate(weights))/sum(weights))
    clearance=max(samples[j][4]-radii[j] for j in range(rings+1))+.001
    for j,(theta,z,width,depth,raw_r) in enumerate(samples):
        r=radii[j]+clearance
        radial=Vector((-math.cos(theta),math.sin(theta),0))
        tangent=Vector((math.sin(theta),math.cos(theta),0))
        center=radial*r+Vector((0,0,z))
        if j in (0,rings):
            verts.append(tuple(center));continue
        for i in range(sides):
            phi=2*math.pi*i/sides
            # Lens-like volumetric cross section; not a ribbon or a hair card.
            p=center+tangent*(width*math.cos(phi))+radial*(depth*math.sin(phi))
            verts.append(tuple(p))
    for i in range(sides):faces.append((0,1+(i+1)%sides,1+i))
    for j in range(rings-2):
        a=1+j*sides;b=a+sides
        for i in range(sides):faces.append((a+i,a+(i+1)%sides,b+(i+1)%sides,b+i))
    last=1+(rings-2)*sides;tip=len(verts)-1
    for i in range(sides):faces.append((last+i,last+(i+1)%sides,tip))
    mesh=bpy.data.meshes.new(f'Nape_lock_{k+1:02d}_mesh');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(f'Nape_lock_{k+1:02d}',mesh);coll.objects.link(obj)
    mesh.materials.append(hair.data.materials[0])
    for p in mesh.polygons:p.use_smooth=True
    # Recalculate consistently outward on the closed mesh.
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    uv=mesh.uv_layers.new(name='Lock_UV')
    for p in mesh.polygons:
        for li in p.loop_indices:
            vi=mesh.loops[li].vertex_index
            uv.data[li].uv=(.5,1) if vi==0 else ((.5,0) if vi==tip else (((vi-1)%sides)/sides,1-((vi-1)//sides+1)/rings))
    mesh.calc_loop_triangles()
    tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[t.vertices[:] for t in mesh.loop_triangles],all_triangles=True)
    count=len(tree.overlap(skin))
    diagnostics.append({'object':obj.name,'skin_overlap_pairs':count,'vertices':len(mesh.vertices),'polygons':len(mesh.polygons)})
    obj['purpose']='Closed, individually editable short nape hair lock. No connecting sheet.'
    locks.append(obj)
assert all(d['skin_overlap_pairs']==0 for d in diagnostics),'Check strand/scalp contact before saving'
assert all(geometry_hash(bpy.data.objects[n])==h for n,h in original.items())
assert not any(o.name.startswith('Hair_Nape_Underlayer') for o in scene.objects)
cam=scene.camera;cam.data.ortho_scale=1.4;target=Vector((-.03,0,.05))
def frame(pos):
    cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
frame((-4,-1.4,-.25))
for o in scene.objects:o.select_set(False)
for o in locks:o.select_set(True)
bpy.context.view_layer.objects.active=locks[4]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.region_3d.view_location=target;s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=2
scene['QUALITY_STATUS']='Nine volumetric nape locks replace rejected sheet; original face and hair preserved. User visual review pending.'
bpy.context.preferences.filepaths.save_version=0
dest=OUT/'character_nape_hair_locks.blend';bpy.ops.wm.save_as_mainfile(filepath=str(dest))
for name,pos in [('back',(-4,0,-.3)),('back-angle',(-4,-1.7,-.2)),('side',(0,-4,0)),('front',(4,0,0))]:
    frame(pos);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
for o in scene.objects:
    if o.type=='MESH' and o not in locks:o.hide_render=True
frame((-4,-1.4,-.25));scene.render.filepath=str(OUT/'locks-only.png');bpy.ops.render.render(write_still=True)
report={'input':str(SOURCE),'output':str(dest),'sheet_present':False,'separate_solid_hair_locks':len(locks),'original_geometry_and_shape_keys_unchanged':True,'locks':diagnostics,'api_credits_used':0,'visual_review':'pending'}
(OUT/'nape-locks-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
