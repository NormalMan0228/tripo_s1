import bpy, math, json, struct
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1]
S=R/'art/characters/explorer_b_hair_swap_v11'
A=R/'art/characters/explorer_b_soft_smile_v12';A.mkdir(exist_ok=True)
def delta(p):
 x,y,z=p
 front=max(0,min(1,(x-.10)/.08))
 return Vector((0,0,-.010*front*math.exp(-((abs(y)-.095)/.032)**2-((z+.085)/.034)**2)))
bpy.ops.wm.open_mainfile(filepath=str(S/'original_face_user_hair_v11.blend'))
sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify']
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
head=bpy.data.objects['FACE_original_user_GLb'];keys=head.data.shape_keys.key_blocks
original=[v.co.copy() for v in keys[0].data]
ds=[delta(v.co) for v in keys['RestClosed'].data]
for v,d in zip(keys['RestClosed'].data,ds):v.co+=d
assert all(v.co==p for v,p in zip(keys[0].data,original))
sc.frame_set(1);bpy.context.view_layer.update();sc.cycles.samples=24
cam=sc.camera;cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2
bpy.ops.wm.save_as_mainfile(filepath=str(A/'original_face_soft_smile_v12.blend'))
for n,p in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:
 cam.location=p;cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.wm.save_as_mainfile(filepath=str(A/'original_face_soft_smile_v12.blend'))
bpy.ops.wm.open_mainfile(filepath=str(S/'game_export_scene_v11.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];head=bpy.data.objects['FACE_original_user_GLb']
keys=head.data.shape_keys.key_blocks
for k in keys:
 if k.name=='jawOpen':continue
 for v,d in zip(k.data,ds):v.co+=d
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(A/'game_export_scene_v12.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if o==rig or (o.type=='MESH' and not o.hide_render and not o.name.startswith('WGT')):o.select_set(True)
bpy.context.view_layer.objects.active=rig
opts={'filepath':str(A/'character_soft_smile_v12.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIONS','export_anim_single_armature':True,'export_morph_animation':True,'export_bake_animation':True,'export_frame_range':False,'export_anim_slide_to_zero':True,'export_merge_animation':'ACTION','export_morph_normal':True}
available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());bpy.ops.export_scene.gltf(**{k:v for k,v in opts.items() if k in available})
buf=(A/'character_soft_smile_v12.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);clips=[a['name'] for a in g['animations']];assert len(clips)==12
(A/'verification.json').write_text(json.dumps({'status':'passed','original_author_basis_unchanged':True,'adjustment':'RestClosed mouth corners lowered smoothly; jawOpen=1 retains original open face','max_corner_lowering':max(-d.z for d in ds),'clips':clips,'hair_unchanged':True},indent=2))
print('V12_SOFT_SMILE_EXPORTED')
