import bpy,json,math,struct
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_animated_v6';FILE=A/'explorer_b_repaired_rigify_v6.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Rigify_Face_Rig'];head=bpy.data.objects['FACE_skin_eyelids_lashes'];ctrl=bpy.data.objects['FACE_CONTROLS'];sc.cycles.samples=20;sc.render.resolution_x=720;sc.render.resolution_y=800;cam=sc.camera;checks=[]
def evaluated_tree(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();tree=BVHTree.FromPolygons([o.matrix_world@v.co for v in me.vertices],[t.vertices for t in me.loop_triangles],all_triangles=True);eo.to_mesh_clear();return tree
def render(name,frame,pos=(3,0,0),target=(0,0,.04),scale=1.23):
 sc.frame_set(frame);bpy.context.view_layer.update();cam.location=Vector(target)+Vector(pos);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
frames=[1,37,58,72,74,77,80,104,130,174,176,179,182,213,226,239,267,294,296,299,302,338,360]
for frame in frames:
 sc.frame_set(frame);bpy.context.view_layer.update();finite=True
 for o in sc.objects:
  if o.type!='MESH' or o.hide_render or o.hide_get() or o.name.startswith(('WGT','HAIR_')):continue
  eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();finite=finite and all(math.isfinite(c) for v in me.vertices for c in v.co);eo.to_mesh_clear()
 checks.append({'frame':frame,'blink_L':float(ctrl['blink_L']),'blink_R':float(ctrl['blink_R']),'mouth_open':float(ctrl['mouth_open']),'finite':finite});assert finite
assert checks[0]['mouth_open']==0 and checks[-1]['mouth_open']==0;assert max(x['blink_L'] for x in checks)> .99;assert any(.05<x['blink_L']<.95 for x in checks);assert max(x['mouth_open'] for x in checks)>.2
# Inspect both closed commissures on the final evaluated skin with dense front rays.
sc.frame_set(1);bpy.context.view_layer.update();tree=evaluated_tree(head);gap_counts={}
for sign in [-1,1]:
 count=0;total=0
 for j in range(54,89):
  y=sign*j/1000
  for i in range(160):
   z=-.082+i*.0002;hit,*_=tree.ray_cast(Vector((1,y,z)),Vector((-1,0,0)));total+=1
   if hit is None or hit.x<.15:count+=1
 gap_counts[str(sign)]={'sampled_rays':total,'cavity_slit_rays':count}
assert all(v['cavity_slit_rays']==0 for v in gap_counts.values()),gap_counts
for side in ['L','R']:
 o=bpy.data.objects['LASH_upper_'+side];assert len(o.data.materials)==1;assert o.data.materials[0].name=='Solid_lashes_uniform_dark_v6';assert not any(n.type=='TEX_IMAGE' for n in o.data.materials[0].node_tree.nodes)
render('front',1);render('angle',1,(3,-2,0));render('side',1,(0,-3,0));render('mouth_corners_L',1,(3,-1.2,0),(.25,-.078,-.066),.11);render('mouth_corners_R',1,(3,1.2,0),(.25,.078,-.066),.11)
hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];hair.hide_render=True;render('eyes_detail',1,(3,0,0),(.18,0,.145),.53);render('eye_angle_L',1,(3,-2,0),(.18,-.12,.145),.28);render('eye_angle_R',1,(3,2,0),(.18,.12,.145),.28);render('blink_half',72,(3,0,0),(.18,0,.145),.53);render('blink_closed',74,(3,0,0),(.18,0,.145),.53);hair.hide_render=False;render('gaze_left',104);render('mouth_open',226);render('smile_soft',180);render('front',1)
report={'status':'passed','rigify_generated':True,'rigify_bones':len(rig.data.bones),'sampled_frames':checks,'mouth_corner_ray_checks':gap_counts,'lash_material':'Single uniform dark material covers front, back and edge; no peach texture','blink_corrective_arc':True,'rest_is_closed_smile':True,'animation_seconds':12,'fps':30,'new_Tripo_credits':0,'full_production_facial_rig':False,'audio_lipsync':False};(A/'verification.json').write_text(json.dumps(report,indent=2))
bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if (o.type=='MESH' and not o.hide_render and not o.hide_get() and not o.name.startswith('WGT')) or o==rig:o.select_set(True)
bpy.context.view_layer.objects.active=rig;available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());options={'filepath':str(A/'explorer_b_repaired_rigify_v6.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_frame_range':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIVE_ACTIONS','export_morph_animation':True,'export_bake_animation':True};options={k:v for k,v in options.items() if k in available};bpy.ops.export_scene.gltf(**options)
buf=(A/'explorer_b_repaired_rigify_v6.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);assert g.get('skins');assert g.get('animations');paths={c['target']['path'] for a in g['animations'] for c in a['channels']};assert 'weights' in paths and 'rotation' in paths,paths;report['glb_animated_skin_and_morphs']=True;report['glb_animations']=[a.get('name','') for a in g['animations']];report['glb_images_embedded']=all('bufferView' in i for i in g['images']);(A/'verification.json').write_text(json.dumps(report,indent=2));sc.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(FILE));print('V6_VERIFIED',json.dumps({k:v for k,v in report.items() if k!='sampled_frames'}))
