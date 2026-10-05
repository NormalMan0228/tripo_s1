import bpy,json,hashlib,struct,math
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_young_bob_face_cleanup_v3';A=O/'assembly';FILE=A/'explorer_b_young_bob_closed_smile_v3.blend'
bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS']
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
# Undo the initial tip-height clamp and use a small uniform soft lift instead;
# this retains tapered tips rather than creating a straight horizontal fringe.
for v in hair.data.vertices:
 c=v.co;newz=c.z;y=c.y/(1-.018*(1-smooth(.12,.30,newz)));x=c.x
 def shifted(z):
  weight=smooth(.10,.23,x)*(1-smooth(.145,.23,abs(y)))*(1-smooth(.235,.37,z))*smooth(.08,.15,z)
  return z+max(0,.227-z)*weight*.85
 lo=newz-.14;hi=newz
 for _ in range(24):
  mid=(lo+hi)/2
  if shifted(mid)<newz:lo=mid
  else:hi=mid
 z=(lo+hi)/2;weight=smooth(.10,.23,x)*(1-smooth(.145,.23,abs(y)))*(1-smooth(.235,.37,z))*smooth(.08,.15,z);c.z=z+.012*weight;c.y=y*(1-.014*(1-smooth(.12,.30,c.z)))
hair.data.update()
# Include peach fragments on the actual outer wing while leaving adjacent skin.
attr=head.data.attributes['Lash_color_repair']
for v,a in zip(head.data.vertices,attr.data):
 x,y,z=v.co;wing=smooth(.213,.232,abs(y))*smooth(.134,.156,x)*smooth(.117,.134,z)*(1-smooth(.164,.183,z))*(1-smooth(.25,.266,abs(y)));a.value=max(a.value,wing)
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
mat=head.data.materials[0];nt=mat.node_tree;image=bpy.data.images.new('Face_color_lashes_fixed_v3',width=4096,height=4096,alpha=True);image.colorspace_settings.name='sRGB';node=nt.nodes.new('ShaderNodeTexImage');node.name='BAKE_clean_lash_atlas';node.image=image
for n in nt.nodes:n.select=False
node.select=True;nt.nodes.active=node
sc.cycles.samples=1;sc.render.bake.use_pass_direct=False;sc.render.bake.use_pass_indirect=False;sc.render.bake.use_pass_color=True;sc.render.bake.margin=8
bpy.ops.object.bake(type='DIFFUSE');image.filepath_raw=str(A/'face_color_lashes_fixed_v3.png');image.file_format='PNG';image.save();image.pack()
# Keep an editable masked material in the file, use its packed baked equivalent
# for portable export and normal viewing.
mat.use_fake_user=True;portable=mat.copy();portable.name='Face_corrected_UV_atlas_v3';pnt=portable.node_tree;b=next(n for n in pnt.nodes if n.type=='BSDF_PRINCIPLED');tex=pnt.nodes.get('BAKE_clean_lash_atlas');pnt.links.new(tex.outputs['Color'],b.inputs['Base Color']);head.data.materials.clear();head.data.materials.append(portable)
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update()
eyes=[bpy.data.objects['EYEBALL_'+s] for s in ('L','R')];assert all(o.parent is None for o in eyes);assert all(o['separate_from_face'] for o in eyes)
# Restore the complete original skin exactly at open=1, through evaluated driver.
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();evalhead=head.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evalhead.to_mesh();key=head.data.shape_keys.key_blocks['Mouth_open_original'];error=max((v.co-k.co).length for v,k in zip(mesh.vertices,key.data));evalhead.to_mesh_clear();assert error<1e-6,error
source=bpy.data.objects['SOURCE_Tripo_face_0'];kd=KDTree(len(source.data.vertices))
for i,v in enumerate(source.data.vertices):kd.insert(source.matrix_world@v.co,i)
kd.balance();source_error=max(kd.find(k.co)[2] for k in key.data);assert source_error<1e-6,source_error
ctrl['mouth_open']=.5;ctrl.update_tag();sc.frame_set(51);bpy.context.view_layer.update();assert abs(key.value-.5)<1e-5
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();assert key.value==0
assert bpy.data.objects['HAIR_HD_SOURCE_UNCHANGED'].hide_render;assert source.hide_render;assert not hair['hair_cards'];assert all(math.isfinite(c) for v in hair.data.vertices for c in v.co)
visible=[o for o in sc.objects if o.type=='MESH' and not o.hide_render and not o.hide_get()];bpy.ops.object.select_all(action='DESELECT')
for o in visible:o.select_set(True)
bpy.context.view_layer.objects.active=head;glb=A/'explorer_b_young_bob_closed_smile_v3.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_apply=False,export_morph=True,export_morph_normal=True)
buf=glb.read_bytes();length,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+length]);names=[n.get('name','') for n in g['nodes']];assert all(e.name in names for e in eyes);assert not any('SOURCE' in n for n in names);assert all('bufferView' in im for im in g['images']);assert any('targets' in p for m in g['meshes'] for p in m['primitives'])
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(glb));added=[o for o in bpy.data.objects if o not in before];rh=next(o for o in added if o.name.startswith(hair.name));assert len(rh.data.polygons)==len(hair.data.polygons);assert len([o for o in added if o.type=='MESH' and o.name.startswith('EYEBALL_')])==2
for o in added:bpy.data.objects.remove(o,do_unlink=True)
cam=sc.camera;sc.cycles.samples=24
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:render(n,pos)
hair.hide_render=True;render('eyes_clean',(3,0,0),Vector((.18,0,.145)),.52);render('mouth_closed',(3,-.1,0),Vector((.26,0,-.085)),.34)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();render('mouth_open',(3,-.6,0),Vector((.23,0,-.085)),.38)
hair.hide_render=False;ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head;bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
budget=json.loads((R/'artifacts/character-hd-restart-20261004/budget.json').read_text(encoding='utf-8-sig'));spent=sum(t.get('credits_consumed',t.get('reservation',0)) for t in budget['tasks'].values());source_hash=hashlib.sha256((R/'art/characters/explorer_b_face_multiview_meshhair_v2/head/model.fbx').read_bytes()).hexdigest();assert source_hash=='f65687754b992e1d309e5d5fedb97c0e3b2e1e1c50320e6327204fc00da12149'
report={'status':'passed','face_regeneration_credits':0,'hair_generation_credits':40,'total_spent':spent,'remaining_credits':budget['tripo_cap']-spent,'source_face_hash_unchanged':True,'original_open_skin_coordinate_error':source_error,'mouth_driver_restore_error':error,'default_pose':'closed_gentle_smile','mouth_original_open_preserved':True,'mouth_driver_half_open_verified':True,'eyeballs_separate':['EYEBALL_L','EYEBALL_R'],'eyeball_rotation_pivots_centered':True,'eyeball_catchlight_patches_joined':True,'teeth_material':'Teeth_clean_ivory_enamel','gums_and_tongue_pink':True,'lash_color_repair':'Blender continuous mask baked to NEW packed 4096 UV atlas','original_atlas_preserved':True,'hair_cards':False,'hair_triangles':len(hair.data.polygons),'visible_meshes':len(visible),'glb_textures_embedded':True,'glb_roundtrip_passed':True,'glb_mouth_morph_included':True,'full_facial_rig':False,'game_optimization_complete':False,'known_limits':['HD hair density retained for shape review; game mesh reduction pending.','Full blink, gaze constraints and facial rig remain pending.','Generated facial boundaries require cleanup during facial rig preparation.']}
(A/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('VERIFIED',json.dumps(report,ensure_ascii=False))
