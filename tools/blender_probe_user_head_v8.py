import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';A.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_expressions_v7/explorer_b_expressions_v7.blend'))
for o in bpy.context.view_layer.objects:
 if o.type in {'MESH','ARMATURE'}:o.hide_render=True;o.hide_set(True)
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath='C:/Users/dd/Downloads/3d cartoon girl head.glb');objects=[o for o in bpy.data.objects if o not in before];report=[]
for o in objects:
 if o.type!='MESH':continue
 ps=[o.matrix_world@v.co for v in o.data.vertices];report.append({'name':o.name,'vertices':len(ps),'polygons':len(o.data.polygons),'min':[min(p[k] for p in ps) for k in range(3)],'max':[max(p[k] for p in ps) for k in range(3)],'materials':[m.name for m in o.data.materials],'keys':[k.name for k in o.data.shape_keys.key_blocks] if o.data.shape_keys else [],'uv':[u.name for u in o.data.uv_layers]})
(A/'import-report.json').write_text(json.dumps(report,indent=2));print('USER_HEAD',json.dumps(report));ps=[o.matrix_world@v.co for o in objects if o.type=='MESH' for v in o.data.vertices];center=Vector([(min(p[k] for p in ps)+max(p[k] for p in ps))/2 for k in range(3)]);extent=max(max(p[k] for p in ps)-min(p[k] for p in ps) for k in range(3));sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=640;sc.render.resolution_y=640;sc.eevee.taa_render_samples=32;cam=sc.camera
for name,vec in [('x',(3,0,0)),('y',(0,-3,0)),('angle',(3,-2,0))]:
 cam.location=center+Vector(vec)*extent;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=extent*1.2;sc.render.filepath=str(A/('import_'+name+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(A/'import_inspection.blend'))
