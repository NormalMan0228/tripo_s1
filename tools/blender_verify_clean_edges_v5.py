import bpy,json,struct,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_clean_edges_v5/assembly';FILE=A/'explorer_b_clean_edges_v5.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS'];key=head.data.shape_keys.key_blocks['Mouth_open_original'];assert ctrl['mouth_open']==0 and key.value==0;assert not head.data.has_custom_normals;assert not head.data.color_attributes.get('Lash_tint')
deps=bpy.context.evaluated_depsgraph_get();verts=[];tris=[]
for o in sc.objects:
 if o.type!='MESH' or o.hide_render or o.hide_get() or o.name.startswith('TOOTH_'):continue
 eo=o.evaluated_get(deps);me=eo.to_mesh();me.calc_loop_triangles();offset=len(verts);verts.extend(o.matrix_world@v.co for v in me.vertices);tris.extend(tuple(offset+i for i in t.vertices) for t in me.loop_triangles);eo.to_mesh_clear()
tree=BVHTree.FromPolygons(verts,tris,all_triangles=True);visibility={}
for name,pos in [('front',(3,0,.04)),('front_low',(3,0,-.02)),('angle_L',(3,-2,.04)),('angle_R',(3,2,.04)),('side_L',(0,-3,.04)),('side_R',(0,3,.04))]:
 cam=Vector(pos);count=0;total=0
 for o in sc.objects:
  if not o.name.startswith('TOOTH_') or o.hide_render:continue
  eo=o.evaluated_get(deps);me=eo.to_mesh()
  for p in me.polygons:
   point=o.matrix_world@p.center;d=point-cam;hit,n,idx,dist=tree.ray_cast(cam,d.normalized(),d.length+.002);total+=1
   if hit is None or dist>d.length-.0003:count+=1
  eo.to_mesh_clear()
 visibility[name]={'sampled_tooth_faces':total,'exposed_tooth_faces':count}
assert all(v['exposed_tooth_faces']==0 for v in visibility.values()),visibility
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();eo=head.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();error=max((v.co-k.co).length for v,k in zip(me.vertices,key.data));eo.to_mesh_clear();assert error<1e-6
for value in [.5,0.]:ctrl['mouth_open']=value;ctrl.update_tag();sc.frame_set(1+int(value*100));bpy.context.view_layer.update();assert abs(key.value-value)<1e-6
visible=[o for o in sc.objects if o.type=='MESH' and not o.hide_render and not o.hide_get()];assert all(math.isfinite(c) for o in visible for v in o.data.vertices for c in v.co);assert not hair['hair_cards'];bpy.ops.object.select_all(action='DESELECT')
for o in visible:o.select_set(True)
bpy.context.view_layer.objects.active=head;glb=A/'explorer_b_clean_edges_v5.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_apply=False,export_morph=True)
buf=glb.read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);names=[v.get('name','') for v in g['nodes']];assert not any(v.startswith('SOURCE') for v in names);assert all('EYEBALL_'+s in names and 'IRIS_PUPIL_'+s in names for s in ('L','R'));assert all('bufferView' in i for i in g['images']);assert any('targets' in p for m in g['meshes'] for p in m['primitives']);assert any(m.get('name','')=='Lash_geometry_dark_brown_v5' for m in g['materials'])
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(glb));added=[o for o in bpy.data.objects if o not in before];assert len([o for o in added if o.type=='MESH' and o.name.startswith('EYEBALL_')])==2
for o in visible:o.hide_render=True
sc.cycles.samples=24;sc.render.filepath=str(A/'glb_roundtrip_front.png');bpy.ops.render.render(write_still=True)
for o in visible:o.hide_render=False
for o in added:bpy.data.objects.remove(o,do_unlink=True)
# Re-render final beauty views after the narrower lash material assignment.
cam=sc.camera
for name,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0))]:
 target=Vector((0,0,.04));cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23;sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head;bpy.ops.wm.save_as_mainfile(filepath=str(FILE));report=json.loads((A/'refinement-report.json').read_text());report.update(status='passed',default_mouth_open=0,original_open_coordinate_error=error,tooth_visibility_rays=visibility,glb_roundtrip_passed=True,texture_images_embedded=True,game_renderer='Godot Compatibility/OpenGL',full_face_rig=False,game_optimization_complete=False)
(A/'verification.json').write_text(json.dumps(report,indent=2));print('V5_VERIFIED',json.dumps(report))
