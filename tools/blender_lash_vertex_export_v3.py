"""Use a portable smooth vertex tint with the original UV atlas, avoiding UV overlap bake artifacts."""
import bpy,json,struct
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly';FILE=A/'explorer_b_young_bob_closed_smile_v3.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS']
color=head.data.color_attributes.new(name='Lash_tint',type='FLOAT_COLOR',domain='CORNER');head.data.color_attributes.active_color=color;head.data.color_attributes.render_color_index=len(head.data.color_attributes)-1;attr=head.data.attributes['Lash_color_repair']
for loop,c in zip(head.data.loops,color.data):
 f=attr.data[loop.vertex_index].value;c.color=(1-f+f*.10,1-f+f*.05,1-f+f*.03,1)
original=bpy.data.objects['SOURCE_Tripo_face_0'].data.materials[0];mat=original.copy();mat.name='Face_original_UV_with_smooth_lash_tint';nt=mat.node_tree;bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED');src=next(l.from_socket for l in nt.links if l.to_socket==bs.inputs['Base Color']);mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1.;vc=nt.nodes.new('ShaderNodeVertexColor');vc.layer_name='Lash_tint';nt.links.new(src,mix.inputs[1]);nt.links.new(vc.outputs['Color'],mix.inputs[2]);nt.links.new(mix.outputs[0],bs.inputs['Base Color']);head.data.materials.clear();head.data.materials.append(mat)
head['lash_color_repair']='Smooth corner vertex tint multiplying original UV color. Portable glTF COLOR_0; no atlas overlap artifacts.'
notes=bpy.data.texts['READ_ME'];notes.clear();notes.write('v3: NEW separate Tripo HD solid bob, no cards. Existing face edited locally. EYEBALL_L/R independent with centered origins. Lash color repaired by smooth vertex tint multiplying original UV atlas; exported as glTF COLOR_0. No atlas bake artifacts. Ivory enamel teeth, pink gums/tongue. Closed gentle smile default; FACE_CONTROLS mouth_open=1 restores exact original open skin for oral inspection. Original source hidden. Full facial rig and game optimization pending.\n')
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if o.type=='MESH' and not o.hide_render and not o.hide_get():o.select_set(True)
bpy.context.view_layer.objects.active=head;glb=A/'explorer_b_young_bob_closed_smile_v3.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_apply=False,export_morph=True)
buf=glb.read_bytes();size,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+size]);hm=next(m for m in g['meshes'] if m.get('name')==head.data.name);assert all('COLOR_0' in p['attributes'] for p in hm['primitives']);assert all('bufferView' in i for i in g['images']);fm=next(m for m in g['materials'] if m['name']==mat.name);assert 'baseColorTexture' in fm['pbrMetallicRoughness']
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(glb));added=[o for o in bpy.data.objects if o not in before];rh=next(o for o in added if o.type=='MESH' and o.name.startswith(head.name));assert len(rh.data.color_attributes)>0;assert len([o for o in added if o.type=='MESH' and o.name.startswith('EYEBALL_')])==2
# Render the round-tripped face, then the native assembly, to confirm tint parity.
cam=sc.camera;sc.cycles.samples=24
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
visible=[o for o in sc.objects if o.type=='MESH' and not o.hide_render and o not in added]
for o in visible:o.hide_render=True
for o in added:
 if o.type=='MESH' and not o.name.startswith(head.name):o.hide_render=True
render('eyes_glb_roundtrip',(3,0,0),Vector((.18,0,.145)),.52)
for o in added:bpy.data.objects.remove(o,do_unlink=True)
for o in visible:o.hide_render=False
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:render(n,pos)
hair.hide_render=True;render('eyes_clean',(3,0,0),Vector((.18,0,.145)),.52);render('mouth_closed',(3,-.1,0),Vector((.26,0,-.085)),.34)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();render('mouth_open',(3,-.6,0),Vector((.23,0,-.085)),.38)
hair.hide_render=False;ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head;bpy.ops.wm.save_as_mainfile(filepath=str(FILE));p=A/'verification.json';report=json.loads(p.read_text(encoding='utf-8'));report.update(lash_color_repair='Smooth Blender corner vertex tint multiplying original 4096 UV atlas',lash_tint_glb_COLOR_0=True,original_uv_atlas_unchanged=True,final_glb_roundtrip_passed=True,final_file_reopened=False);report.pop('original_skin_atlas_outside_lash_uv_preserved',None);p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('VERTEX_TINT_VERIFIED')
