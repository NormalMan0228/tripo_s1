"""Prepare the three paid Tripo outputs for runtime loading and paint testing."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/furniture/paint-test-01'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
specs=[('chair',.95,(.19,.43,.34,1)),('table',.73,(.82,.48,.17,1)),('bookshelf',1.05,(.24,.40,.58,1))]
report={};groups=[]
def material(name,color):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=color
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=color;bs.inputs['Roughness'].default_value=.78
 return m
white=material('Paintable_White',(.73,.75,.72,1))
for idx,(name,height,color) in enumerate(specs):
 before=set(bpy.context.scene.objects)
 bpy.ops.import_scene.gltf(filepath=str(OUT/(name+'-original.glb')))
 imported=[o for o in bpy.context.scene.objects if o not in before];meshes=[o for o in imported if o.type=='MESH']
 bpy.ops.object.select_all(action='DESELECT')
 for o in meshes:
  o.select_set(True);world=o.matrix_world.copy();o.parent=None;o.matrix_world=world
 bpy.context.view_layer.objects.active=meshes[0]
 bpy.ops.object.join();obj=bpy.context.object;obj.name=name
 bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
 # glTF imports use quaternion rotation. Switch modes before assigning Euler.
 obj.rotation_mode='XYZ'
 obj.rotation_euler.z=-math.pi/2
 bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 points=[obj.matrix_world@Vector(v) for v in obj.bound_box]
 lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
 factor=height/(hi.z-lo.z)
 for v in obj.data.vertices:v.co=(v.co-Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z)))*factor
 obj.location=(0,0,0)
 uv_input=bool(obj.data.uv_layers)
 if not uv_input:
  bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.025);bpy.ops.object.mode_set(mode='OBJECT')
 obj.data.materials.clear();obj.data.materials.append(white)
 for poly in obj.data.polygons:poly.material_index=0;poly.use_smooth=True
 # Preserve the generated topology; UV fallback does not regenerate the shape.
 report[name]={'vertices':len(obj.data.vertices),'polygons':len(obj.data.polygons),'uv_from_api':uv_input,'uv_available':bool(obj.data.uv_layers),'uv_added_locally':not uv_input,'height_m':height,'color_test':'uniform material replacement','raw_file':name+'-original.glb','paint_ready_file':name+'-paintable.glb'}
 bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'-paintable.glb')),export_format='GLB',use_selection=True,export_animations=False)
 for helper in imported:
  if helper!=obj and helper.name in bpy.data.objects and helper.type!='MESH':bpy.data.objects.remove(helper,do_unlink=True)
 # Comparison display: neutral back row and locally colored front row.
 obj.location=((idx-1)*1.6,1.1,0)
 colored=obj.copy();colored.data=obj.data.copy();bpy.context.collection.objects.link(colored)
 colored.name=name+'_PaintTest';colored.location=((idx-1)*1.6,-1.1,0)
 colored.data.materials.clear();colored.data.materials.append(material(name+'_Paint',color))
 groups.append((obj,colored))

scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 scene.cycles.device='GPU'
except:pass
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.62,.61,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
floor_mat=material('Stage',(.15,.20,.20,1))
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.008));bpy.context.object.data.materials.append(floor_mat)
target=Vector((0,0,.35))
for name,pos,power,size in [('Key',(0,-4,7),1000,5),('Fill',(-4,-1,4),650,4),('Rim',(3,4,6),900,4)]:
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(2.7,-6.5,5.5));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=6.8;scene.camera=cam
scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.filepath=str(OUT/'furniture-comparison.png');bpy.ops.render.render(write_still=True)
for a in bpy.context.screen.areas if bpy.context.screen else []:
 if a.type=='VIEW_3D':a.spaces.active.region_3d.view_perspective='CAMERA';a.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'furniture-test.blend'))
(OUT/'mesh-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
