import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_tripo_retopo_v14';bpy.ops.wm.open_mainfile(filepath=str(A/'face_retopology_assembly_v14.blend'));sc=bpy.context.scene;head=bpy.data.objects['FACE_Tripo_Smart_Retopo_v14']
materials=[]
for m in head.data.materials:
 if m and m.use_nodes:
  materials.append({'name':m.name,'nodes':[{'type':n.type,'name':n.name} for n in m.node_tree.nodes]})
  for n in m.node_tree.nodes:
   if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=0
   if n.type=='BUMP':n.inputs['Strength'].default_value=0
sc.cycles.samples=24;cam=sc.camera
def render(n,target,scale):
 t=Vector(target);cam.location=t+Vector((3,0,0));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
render('front_no_normal',(0,0,0),1.2);render('mouth_no_normal',(0,0,-.1),.33)
wire=bpy.data.objects.new('TEMP_wire',head.data.copy());sc.collection.objects.link(wire);wire.matrix_world=head.matrix_world
bpy.ops.object.select_all(action='DESELECT');wire.select_set(True);bpy.context.view_layer.objects.active=wire;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
wire.data.materials.clear();m=bpy.data.materials.new('Topology_teal');m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.008,.045,.025,1);wire.data.materials.append(m)
w=wire.modifiers.new('Provider edges','WIREFRAME');w.thickness=.0007;w.offset=1
hair=bpy.data.objects['HAIR_user_brown_v11'];hair.hide_render=True;render('wire',(0,0,.035),.84);hair.hide_render=False
(A/'material-inspection.json').write_text(json.dumps(materials,indent=2));print('RETOPO_REVIEW_COMPLETE')
