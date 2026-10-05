import bpy,json,numpy as np,struct
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_hair_swap_v11';SRC=R/'art/characters/explorer_b_game_face_v10';bpy.ops.wm.open_mainfile(filepath=str(SRC/'original_preserved_face_rig_v10.blend'));snapshot={}
for o in bpy.context.scene.objects:
 if o.type=='MESH' and not o.name.startswith(('HAIR','WGT')) and not o.hide_render:snapshot[o.name]={'v':np.array([v.co for v in o.data.vertices]),'keys':{k.name:np.array([v.co for v in k.data]) for k in o.data.shape_keys.key_blocks} if o.data.shape_keys else {},'uv':np.array([v.uv for v in o.data.uv_layers.active.data]),'mat':[m.name for m in o.data.materials]}
bpy.ops.wm.open_mainfile(filepath=str(A/'original_face_user_hair_v11.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];checks={}
for name,b in snapshot.items():
 o=bpy.data.objects[name];ok=np.array_equal(b['v'],np.array([v.co for v in o.data.vertices])) and np.array_equal(b['uv'],np.array([v.uv for v in o.data.uv_layers.active.data])) and b['mat']==[m.name for m in o.data.materials]
 for namekey,keydata in b['keys'].items():ok &= np.array_equal(keydata,np.array([v.co for v in o.data.shape_keys.key_blocks[namekey].data]))
 checks[name]=bool(ok);assert ok,name
cam=sc.camera
for name,p in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:cam.location=Vector(p);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2;sc.render.filepath=str(A/(name+'.png'));bpy.ops.render.render(write_still=True)
cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();sc.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
for b in rig.data.bones:b.select=b.name=='head'
rig.data.bones.active=rig.data.bones['head'];bpy.ops.object.mode_set(mode='POSE');bpy.ops.wm.save_as_mainfile(filepath=str(A/'original_face_user_hair_v11.blend'))
# Replace hair in the closed-default runtime copy, keeping its existing baked morphs and clips.
bpy.ops.wm.open_mainfile(filepath=str(SRC/'game_export_scene_v10.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];old=bpy.data.objects['HAIR_sculptural_bob_mesh'];bpy.data.objects.remove(old,do_unlink=True)
with bpy.data.libraries.load(str(A/'original_face_user_hair_v11.blend'),link=False) as (src,dst):dst.meshes=['User_Brown_Hair_Mesh']
hair=bpy.data.objects.new('HAIR_user_brown_v11',dst.meshes[0]);sc.collection.objects.link(hair);hair.parent=rig;g=hair.vertex_groups.new(name='DEF-head');g.add(list(range(len(hair.data.vertices))),1.,'REPLACE');m=hair.modifiers.new('Rigify_head','ARMATURE');m.object=rig
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(A/'game_export_scene_v11.blend'));bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if o==rig or (o.type=='MESH' and not o.hide_render and not o.name.startswith('WGT')):o.select_set(True)
bpy.context.view_layer.objects.active=rig;opts={'filepath':str(A/'character_user_hair_v11.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIONS','export_anim_single_armature':True,'export_morph_animation':True,'export_bake_animation':True,'export_frame_range':False,'export_anim_slide_to_zero':True,'export_merge_animation':'ACTION','export_morph_normal':True};available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());bpy.ops.export_scene.gltf(**{k:v for k,v in opts.items() if k in available});buf=(A/'character_user_hair_v11.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);data=json.loads(buf[20:20+n]);clips=[a['name'] for a in data['animations']];assert set(clips)=={c['name'] for c in json.loads((SRC/'expression-clips.json').read_text())};assert all('bufferView' in i for i in data['images']);report=json.loads((A/'hair-swap-report.json').read_text());report.update(face_and_all_shape_keys_unchanged=checks,exported_clips=clips,embedded_textures=True,hair_normal_strength=.12,status='passed');(A/'hair-swap-report.json').write_text(json.dumps(report,indent=2));print('V11_HAIR_AND_FACE_VERIFIED')
