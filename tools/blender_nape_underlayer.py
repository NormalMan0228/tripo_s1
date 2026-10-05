"""Add an editable posterior scalp-conforming hair underlayer; preserve originals."""
import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1'
SOURCE=BASE/'hair_v3_cleanup_v2/character_face_preparation_v2.blend'
OUT=BASE/'hair_v3_nape_v1';OUT.mkdir(exist_ok=True)
source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
hair=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('Hair'))
head=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('01_Face'))
def digest(o):
    data={'v':[v.co[:] for v in o.data.vertices],'f':[p.vertices[:] for p in o.data.polygons]}
    if o.data.shape_keys:data['keys']={k.name:[p.co[:] for p in k.data] for k in o.data.shape_keys.key_blocks}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
original={o.name:digest(o) for o in scene.objects if o.type=='MESH'}
head.data.calc_loop_triangles()
skin=BVHTree.FromPolygons([head.matrix_world@v.co for v in head.data.vertices],[t.vertices[:] for t in head.data.loop_triangles],all_triangles=True)
def radius(theta,z):
    d=Vector((-math.cos(theta),math.sin(theta),0));origin=d*2;origin.z=z
    hit=skin.ray_cast(origin,-d,3)
    if hit[0] is None:raise RuntimeError('No scalp hit at requested nape sample')
    return Vector((hit[0].x,hit[0].y,0)).dot(d)
cols=96;rows=42;verts=[];faces=[]
for j in range(rows+1):
    t=j/rows
    for i in range(cols+1):
        theta=-1.38+2.76*i/cols
        # Nine soft ridges, with a gently scalloped, shorter underlayer hem.
        phase=theta*math.pi/.36
        ridge=(.5+.5*math.cos(phase))**1.6
        bottom=-.175-.04*ridge+.015*(abs(theta)/1.58)**2
        z=.13*(1-t)+bottom*t
        sampled=max(radius(theta+dt,z+dz) for dt in (-.025,0,.025) for dz in (-.015,0,.015))
        section=math.sqrt(max(.01,1-((z-.13)/.47)**2))
        r=max(section/math.sqrt((math.cos(theta)/.395)**2+(math.sin(theta)/.365)**2),sampled)
        # Avoid following the narrowing neck too tightly below the occiput.
        if z<-.06:r=max(r,radius(theta,z+.055)*.98)
        relief=(.003+.005*ridge)*math.sin(math.pi*t)**.7
        r+=.012+relief
        verts.append((-r*math.cos(theta),r*math.sin(theta),z))
for j in range(rows):
    for i in range(cols):
        a=j*(cols+1)+i;b=a+1;c=b+cols+1;d=a+cols+1
        faces.append((a,b,c,d))
mesh=bpy.data.meshes.new('Nape_underlayer_quad_surface');mesh.from_pydata(verts,[],faces);mesh.update()
layer=bpy.data.objects.new('Hair_Nape_Underlayer__editable',mesh)
coll=bpy.data.collections.new('Hair_Nape_Added_Layer');scene.collection.children.link(coll);coll.objects.link(layer)
mesh.materials.append(hair.data.materials[0])
for p in mesh.polygons:p.use_smooth=True
uv=mesh.uv_layers.new(name='Nape_grid_UV')
for p in mesh.polygons:
    for li in p.loop_indices:
        vi=mesh.loops[li].vertex_index;uv.data[li].uv=(vi%(cols+1)/cols,1-(vi//(cols+1))/rows)
solid=layer.modifiers.new('Thin outer shell - scalp clearance preserved','SOLIDIFY');solid.thickness=.006;solid.offset=-1;solid.use_even_offset=False
layer['purpose']='Posterior nape coverage only; editable separate scalp-following layer, not an internal horizontal cap.'
layer['generated_api_asset']=False
bpy.context.view_layer.update()
deps=bpy.context.evaluated_depsgraph_get();evaluated=layer.evaluated_get(deps);em=evaluated.to_mesh();em.calc_loop_triangles()
layer_tree=BVHTree.FromPolygons([layer.matrix_world@v.co for v in em.vertices],[t.vertices[:] for t in em.loop_triangles],all_triangles=True)
overlap_pairs=layer_tree.overlap(skin)
intersections=len(overlap_pairs)
print('OVERLAP_DIAGNOSTIC',intersections,[[list(em.vertices[i].co) for i in em.loop_triangles[a].vertices] for a,b in overlap_pairs[:3]],flush=True)
evaluated.to_mesh_clear()
assert all(digest(bpy.data.objects[n])==h for n,h in original.items()),'Original geometry changed'
assert intersections==0,'Underlayer intersects skin; inspect before saving'
cam=scene.camera;cam.data.ortho_scale=1.4;target=Vector((-.03,0,.05))
def frame(pos):
    cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
frame((-4,-1.4,-.25))
for o in scene.objects:o.select_set(False)
layer.select_set(True);bpy.context.view_layer.objects.active=layer
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.region_3d.view_location=target;s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=2
scene['QUALITY_STATUS']='Added separate nape underlayer; original hair and face untouched. Skin intersection check passed for added layer. No rigging.'
bpy.context.preferences.filepaths.save_version=0
dest=OUT/'character_nape_reinforced.blend';bpy.ops.wm.save_as_mainfile(filepath=str(dest))
for name,pos in [('back',(-4,0,-.3)),('back-angle',(-4,-1.7,-.2)),('side',(0,-4,0)),('front',(4,0,0))]:
    frame(pos);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'source':str(SOURCE),'source_unchanged':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash,'original_meshes_and_shape_keys_unchanged':True,'added_object':layer.name,'added_base_vertices':len(mesh.vertices),'added_base_quads':len(mesh.polygons),'added_layer_skin_triangle_intersections':intersections,'api_credits_used':0,'material':'Reused existing uniform review hair material; no new texture generation','retopology_or_rigging_done':False,'output':str(dest)}
(OUT/'nape-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
