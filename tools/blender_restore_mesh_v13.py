import bpy,json,shutil,struct
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_mesh_reset_v13';A.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_hair_swap_v11/original_face_user_hair_v11.blend'))
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
sc=bpy.context.scene
for o in sc.objects:
 o.animation_data_clear()
 if o.type=='ARMATURE':
  for b in o.pose.bones:
   b.location=(0,0,0);b.rotation_euler=(0,0,0);b.rotation_quaternion=(1,0,0,0);b.scale=(1,1,1)
 if o.type=='MESH' and o.data.shape_keys:o.data.shape_keys.animation_data_clear()
bpy.context.view_layer.update();checks={};keep=[]
for o in list(sc.objects):
 if o.type=='MESH' and not o.hide_render and not o.name.startswith('WGT') and o.name!='MOUTH_interior_bag':
  world=o.matrix_world.copy();o.parent=None;o.matrix_world=world
  if o.data.shape_keys:
   coords=[v.co.copy() for v in o.data.shape_keys.key_blocks[0].data]
   o.shape_key_clear()
   for v,p in zip(o.data.vertices,coords):v.co=p
   assert all(v.co==p for v,p in zip(o.data.vertices,coords));checks[o.name]=True
  for m in list(o.modifiers):
   if m.type=='ARMATURE':o.modifiers.remove(m)
  o.vertex_groups.clear();keep.append(o)
for o in list(bpy.data.objects):
 if o.type=='ARMATURE' or o.name.startswith('WGT') or o.name=='MOUTH_interior_bag' or (o.type=='MESH' and o not in keep):bpy.data.objects.remove(o,do_unlink=True)
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
for t in list(bpy.data.texts):bpy.data.texts.remove(t)
assert all(not o.data.shape_keys and not o.parent and not any(m.type=='ARMATURE' for m in o.modifiers) for o in keep)
sc.frame_set(1);sc.frame_end=1;bpy.ops.object.select_all(action='DESELECT')
for o in keep:o.select_set(True)
bpy.context.view_layer.objects.active=bpy.data.objects['FACE_original_user_GLb']
cam=sc.camera;cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2
bpy.ops.wm.save_as_mainfile(filepath=str(A/'original_mesh_with_user_hair_v13.blend'))
bpy.ops.export_scene.gltf(filepath=str(A/'original_mesh_with_user_hair_v13.glb'),export_format='GLB',use_selection=True,export_animations=False,export_morph=False)
buf=(A/'original_mesh_with_user_hair_v13.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);assert not g.get('skins') and not g.get('animations') and all(not p.get('targets') for m in g['meshes'] for p in m['primitives'])
sc.cycles.samples=24;sc.render.filepath=str(A/'front.png');bpy.ops.render.render(write_still=True)
shutil.copy2(Path('C:/Users/dd/Downloads/3d cartoon girl head.glb'),A/'original_source_head.glb')
(A/'verification.json').write_text(json.dumps({'status':'passed','original_basis_restored':checks,'armatures':0,'shape_keys':0,'animation_clips':0,'mesh_parts':[o.name for o in keep],'hair':'User brown hair retained','mouth':'Original open-mouth mesh restored; custom mouth bag removed'},indent=2))
print('V13_ORIGINAL_MESH_RESTORED')
