import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_tripo_retopo_v14'
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_mesh_reset_v13/original_mesh_with_user_hair_v13.blend'));sc=bpy.context.scene
source=bpy.data.objects['FACE_original_user_GLb'];preserved={o.name:[v.co.copy() for v in o.data.vertices] for o in sc.objects if o.type=='MESH' and o!=source}
probe=json.loads((A/'output-probe.json').read_text(encoding='utf-8'))
with bpy.data.libraries.load(str(A/'tripo_raw_retopology.blend'),link=False) as (s,d):d.objects=[p['name'] for p in probe['parts']]
new=[]
for o in d.objects:
 if o and o.type=='MESH':sc.collection.objects.link(o);new.append(o)
def bounds(objs):
 pts=[o.matrix_world@v.co for o in objs for v in o.data.vertices]
 return Vector([min(p[i] for p in pts) for i in range(3)]),Vector([max(p[i] for p in pts) for i in range(3)])
sb=bounds([source]);nb=bounds(new)
ratios=[(sb[1]-sb[0])[i]/(nb[1]-nb[0])[i] for i in range(3)];assert max(ratios)-min(ratios)<.002,('Output axis mismatch',ratios)
scale=ratios[2];shift=(sb[0]+sb[1])/2-(nb[0]+nb[1])/2*scale
restore=Matrix.Translation(shift)@Matrix.Scale(scale,4)
for o in new:o.matrix_world=restore@o.matrix_world
# Keep the provider's geometry and transforms; no sculpting or projection corrections.
bpy.ops.object.select_all(action='DESELECT')
for o in new:o.select_set(True)
bpy.context.view_layer.objects.active=new[0]
if len(new)>1:bpy.ops.object.join()
head=bpy.context.object;head.name='FACE_Tripo_Smart_Retopo_v14'
tree=BVHTree.FromObject(source,bpy.context.evaluated_depsgraph_get());distances=[]
for v in head.data.vertices:
 q=source.matrix_world.inverted()@(head.matrix_world@v.co);hit=tree.find_nearest(q)
 if hit:distances.append(hit[3])
def stats(o):
 import bmesh
 bm=bmesh.new();bm.from_mesh(o.data);s={'vertices':len(o.data.vertices),'faces':len(o.data.polygons),'quads':sum(len(p.vertices)==4 for p in o.data.polygons),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_nonboundary_edges':sum(not e.is_manifold and not e.is_boundary for e in bm.edges),'uv_layers':len(o.data.uv_layers)};bm.free();return s
report={'source':stats(source),'result':stats(head),'other_parts_unchanged':{n:all(v.co==p for v,p in zip(bpy.data.objects[n].data.vertices,ps)) for n,ps in preserved.items()},'distance_to_original_surface':{'mean':sum(distances)/len(distances),'max':max(distances)},'provider':'Tripo /mesh/decimate v2.0 quad=true bake=true','facial_deformation_verified':False,'originals_preserved':True,'provider_normalization_restored':{'uniform_scale':scale,'translation':list(shift)}}
assert all(report['other_parts_unchanged'].values());source.hide_render=True;source.hide_set(True);source.name='SOURCE_original_face_hidden'
for p in head.data.polygons:p.use_smooth=True
sc.cycles.samples=24
cam=sc.camera
def render(n,target,scale):
 t=Vector(target);cam.location=t+Vector((3,0,0));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
render('front',(0,0,0),1.2);render('mouth',(0,0,-.10),.33);render('eyes',(0,0,.12),.55)
# Topology overlay comes directly from the provider's mesh edges.
wire=bpy.data.objects.new('TEMP_wire_overlay',head.data.copy());sc.collection.objects.link(wire);wire.matrix_world=head.matrix_world;wire.data.materials.clear();mat=bpy.data.materials.new('Wire_teal');mat.diffuse_color=(.015,.08,.065,1);wire.data.materials.append(mat)
w=wire.modifiers.new('Topology lines','WIREFRAME');w.thickness=.00045;w.offset=1
hair=bpy.data.objects['HAIR_user_brown_v11'];hair.hide_render=True
render('wire',(0,0,.035),.84);hair.hide_render=False;bpy.data.objects.remove(wire,do_unlink=True)
cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2
bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if o.type=='MESH' and not o.hide_render:o.select_set(True)
bpy.context.view_layer.objects.active=head
bpy.ops.wm.save_as_mainfile(filepath=str(A/'face_retopology_assembly_v14.blend'))
bpy.ops.export_scene.gltf(filepath=str(A/'face_retopology_assembly_v14.glb'),export_format='GLB',use_selection=True,export_animations=False,export_morph=False)
(A/'inspection.json').write_text(json.dumps(report,indent=2));print('V14_ASSEMBLED',json.dumps(report))
