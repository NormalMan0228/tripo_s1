import bpy,bmesh
from mathutils import Matrix,Vector
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/characters/explorer_b_modular_v1/04_blender_assembly'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(OUT.parent/'03_generated/body/model.glb'))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
matrix=obj.matrix_world.copy();obj.parent=None;obj.matrix_world=Matrix.Identity(4)
for v in obj.data.vertices:v.co=matrix@v.co
obj.data.update()
bpy.context.view_layer.objects.active=obj
bpy.ops.mesh.customdata_custom_splitnormals_clear()
bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-5);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(obj.data);bm.free()
mat=bpy.data.materials.new('Skin');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.64,.405,.285,1)
obj.data.materials.clear();obj.data.materials.append(mat)
for p in obj.data.polygons:p.material_index=0;p.use_smooth=True
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.samples=8;sc.cycles.use_denoising=True
sc.render.resolution_x=600;sc.render.resolution_y=900
world=bpy.data.worlds.new('W');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[1].default_value=.7;sc.world=world
ld=bpy.data.lights.new('L','AREA');ld.energy=300;ld.size=2;lo=bpy.data.objects.new('L',ld);sc.collection.objects.link(lo);lo.location=(2,-2,3);lo.rotation_euler=(-lo.location).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.objects.new('Cam',bpy.data.cameras.new('Cam'));sc.collection.objects.link(cam);cam.location=(4,-1,0);cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.16;sc.camera=cam
def render(name):
 print(name,len(obj.data.vertices),len(obj.data.polygons),flush=True)
 sc.render.filepath=str(OUT/('probe-'+name+'.png'));bpy.ops.render.render(write_still=True)
render('weld')
obj.data.remesh_voxel_size=.0035;bpy.ops.object.voxel_remesh();render('voxel')
bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=(0,0,0),plane_no=(0,1,0),clear_outer=True,dist=.00001);bm.to_mesh(obj.data);bm.free()
mir=obj.modifiers.new('Mir','MIRROR');mir.use_axis=(False,True,False);bpy.ops.object.modifier_apply(modifier=mir.name);render('mirror')
