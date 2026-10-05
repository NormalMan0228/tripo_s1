import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_tripo_retopo_v14';bpy.ops.wm.open_mainfile(filepath=str(A/'face_retopology_assembly_v14.blend'));o=bpy.data.objects['FACE_Tripo_Smart_Retopo_v14'];bm=bmesh.new();bm.from_mesh(o.data);vol=bm.calc_volume(signed=True)*o.matrix_world.to_3x3().determinant();print('WORLD_SIGNED_VOLUME',vol)
if vol<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(o.data);o.data.update()
bm.free();sc=bpy.context.scene;sc.cycles.samples=24;cam=sc.camera
for n,t,s in [('front',(0,0,0),1.2),('mouth',(0,0,-.10),.33),('eyes',(0,0,.12),.55)]:
 t=Vector(t);cam.location=t+Vector((3,0,0));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=s;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2
bpy.ops.wm.save_as_mainfile(filepath=str(A/'face_retopology_assembly_v14.blend'));bpy.ops.object.select_all(action='DESELECT')
for ob in sc.objects:
 if ob.type=='MESH' and not ob.hide_render:ob.select_set(True)
bpy.context.view_layer.objects.active=o;bpy.ops.export_scene.gltf(filepath=str(A/'face_retopology_assembly_v14.glb'),export_format='GLB',use_selection=True,export_animations=False,export_morph=False)
p=A/'inspection.json';d=json.loads(p.read_text());d.update(imported_winding_corrected=vol<0,quality_status='Review only: nose/lip roughness and neck seam artifacts, 16 nonmanifold edges remain; facial rigging not verified');p.write_text(json.dumps(d,indent=2))
