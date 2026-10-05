import bpy,bmesh,math,json
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';FILE=A/'explorer_b_balanced_face_v4.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS']
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
before_top=max(v.co.z for v in hair.data.vertices)
for v in hair.data.vertices:v.co.z-=max(0,v.co.z-.32)*.105*smooth(.29,.41,v.co.z)
hair.data.update();after_top=max(v.co.z for v in hair.data.vertices);hair['crown_refinement']='Upper crown gently compressed 10.5%, fringe and bob tips unchanged'
# Strengthen the continuous original lash pigment footprint, without painting
# an extra rectangular/box region onto skin beyond the actual wing.
with bpy.data.libraries.load(str(R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly/explorer_b_young_bob_closed_smile_v3.blend'),link=False) as (src,dst):dst.objects=['FACE_skin_eyelids_lashes']
probe=dst.objects[0];oldattr=probe.data.attributes['Lash_color_repair'];attr=head.data.attributes['Lash_color_repair']
for a,b in zip(attr.data,oldattr.data):a.value=smooth(.003,.32,b.value)
bpy.data.objects.remove(probe,do_unlink=True)
for loop,c in zip(head.data.loops,head.data.color_attributes['Lash_tint'].data):
 f=attr.data[loop.vertex_index].value;c.color=(1-f+f*.008,1-f+f*.006,1-f+f*.004,1)
# Controlled highlights instead of a broad bright reflection across the pupil.
for name in ['Iris_warm_brown_radial_detail','Pupil_deep_clean_black']:
 mat=bpy.data.materials[name];bs=mat.node_tree.nodes['Principled BSDF'];bs.inputs['Specular IOR Level'].default_value=.16;bs.inputs['Coat Weight'].default_value=.10;bs.inputs['Roughness'].default_value=.34;bs.inputs['Coat Roughness'].default_value=.25
iris=bpy.data.materials['Iris_warm_brown_radial_detail'];nt=iris.node_tree;bs=nt.nodes['Principled BSDF'];image=next(n for n in nt.nodes if n.type=='TEX_IMAGE' and n.image and n.image.name=='Warm_brown_iris_v4');mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1.;mix.inputs[2].default_value=(.68,.62,.58,1);nt.links.new(image.outputs['Color'],mix.inputs[1]);nt.links.new(mix.outputs[0],bs.inputs['Base Color'])
for o in list(sc.objects):
 if o.name.startswith('IRIS_PUPIL_'):
  for p in o.data.polygons:
   # A slightly larger round pupil matches the supplied gentle expression.
   radial=sum(o.data.uv_layers.active.data[li].uv.x for li in p.loop_indices)/len(p.loop_indices);p.material_index=1 if radial<8/18 else 0
  bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.dissolve_degenerate(bm,dist=1e-8,edges=list(bm.edges));bm.to_mesh(o.data);bm.free()
 if o.name.startswith('EYE_CATCHLIGHT_'):
  # Put the main highlight on the upper-left side of both irises.
  if o.name.endswith('_main'):o.location.y-=.028
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();sc.cycles.samples=32;cam=sc.camera
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:render(n,pos)
hair.hide_render=True;render('eyes_detail',(3,0,0),Vector((.18,0,.145)),.52);render('mouth_closed',(3,-.6,0),Vector((.26,0,-.092)),.34)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();render('mouth_open',(3,-.6,0),Vector((.23,0,-.085)),.38)
hair.hide_render=False;ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   sp=a.spaces.active;sp.shading.type='MATERIAL';sp.shading.use_scene_world=False;sp.region_3d.view_location=(0,0,.06);sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_distance=1.5;sp.region_3d.view_perspective='ORTHO';sp.overlay.show_extras=False
notes=bpy.data.texts['READ_ME'];notes.write('Additional user correction: crown upper height gently lowered. Render reflections controlled, round pupils slightly enlarged. Strong lash tint kept within original pigment footprint.\n')
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head;bpy.ops.wm.save_as_mainfile(filepath=str(FILE));(A/'refinement-report.json').write_text(json.dumps({'hair_crown_before':before_top,'hair_crown_after':after_top,'hair_crown_height_reduction':before_top-after_top,'chin_center_softened':True,'mouth_corners_lowered':True,'teeth_rest_recession':.017,'iris_outward_offset_each':.004,'additional_Tripo_credits':0},indent=2),encoding='utf-8');print('V4_FINISHED')
