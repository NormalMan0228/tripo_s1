"""Fit the approved Tripo hair guide without changing the original assets."""
import bpy,json
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1'
bpy.ops.wm.open_mainfile(filepath=str(O/'head/explorer_b_integrated_face_open_workbench.blend'))
sc=bpy.context.scene;old=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(O/'hair/model.glb'))
hair=next(o for o in bpy.data.objects if o not in old and o.type=='MESH')
hair.data.transform(hair.matrix_world);hair.parent=None;hair.matrix_world=Matrix.Identity(4)
hair.name='HAIR_Tripo_HD_form_guide'
c=bpy.data.collections.new('02_HD_hair_form');sc.collection.children.link(c)
for co in list(hair.users_collection):co.objects.unlink(hair)
c.objects.link(hair)
for v in hair.data.vertices:v.co=Vector((v.co.x*.82-.025,v.co.y*.76,v.co.z*.96+.135))
for p in hair.data.polygons:p.use_smooth=True
m=bpy.data.materials.new('HD_guide_chocolate_brown');m.use_nodes=True
bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.048,.027,.017,1);bs.inputs['Roughness'].default_value=.42
hair.data.materials.clear();hair.data.materials.append(m)
cam=sc.camera
def view(pos,scale=1.15):
 cam.location=Vector(pos);cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
view((3,0,0));bpy.ops.wm.save_as_mainfile(filepath=str(O/'hair/fitted_form.blend'))
for n,p in [('fit_front',(3,0,0)),('fit_angle',(3,-2,0)),('fit_side',(0,-3,0))]:
 view(p);sc.render.filepath=str(O/'hair'/(n+'.png'));bpy.ops.render.render(write_still=True)
