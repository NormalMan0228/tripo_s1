import bpy,json
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_young_bob_face_cleanup_v3';A=O/'assembly'
bpy.ops.wm.open_mainfile(filepath=str(A/'face_local_cleanup.blend'));sc=bpy.context.scene
old=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(O/'hair/model.glb'));hair=next(o for o in bpy.data.objects if o not in old and o.type=='MESH');hair.data.transform(hair.matrix_world);hair.parent=None;hair.matrix_world=Matrix.Identity(4);hair.name='HAIR_HD_SOURCE_UNCHANGED'
lo=Vector([min(v.co[j] for v in hair.data.vertices) for j in range(3)]);hi=Vector([max(v.co[j] for v in hair.data.vertices) for j in range(3)]);print('HAIR_BOUNDS',list(lo),list(hi),len(hair.data.polygons));(A/'hair-bounds.json').write_text(json.dumps({'lo':list(lo),'hi':list(hi),'vertices':len(hair.data.vertices),'faces':len(hair.data.polygons)}),encoding='utf-8')
# Initial fit matches the original reference's compact crown and chin-length tips.
for v in hair.data.vertices:v.co=Vector((v.co.x*.95-.025,v.co.y*.80,v.co.z*1.02+.102))
m=bpy.data.materials.new('Hair_chocolate_satin');m.use_nodes=True;bs=m.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.035,.016,.008,1);bs.inputs['Roughness'].default_value=.65;bs.inputs['Specular IOR Level'].default_value=.13;hair.data.materials.clear();hair.data.materials.append(m)
for p in hair.data.polygons:p.use_smooth=True
sc.cycles.samples=12;cam=sc.camera
def render(n,pos):
 target=Vector((0,0,.04));cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.20;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(A/'hair_initial_probe.blend'));render('hair_initial_front',(3,0,0));render('hair_initial_side',(0,-3,0));render('hair_initial_angle',(3,-2,0))
# Numeric lash footprint for precise correction of peach-colored tip polygons.
head=bpy.data.objects['FACE_skin_eyelids_lashes'];polys=[p for p in head.data.polygons if p.material_index==1]
print('LASH_FOOTPRINT',len(polys),[[min(p.center[j] for p in polys),max(p.center[j] for p in polys)] for j in range(3)])
