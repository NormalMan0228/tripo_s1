"""Bake only the repaired lash UV islands onto a copy of the original atlas."""
import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly';FILE=A/'explorer_b_young_bob_closed_smile_v3.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS']
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
with bpy.data.libraries.load(str(A/'face_local_cleanup.blend'),link=False) as (src,dst):dst.objects=['FACE_skin_eyelids_lashes']
probe=dst.objects[0];seeds=[p for p in probe.data.polygons if p.material_index==1];kd=KDTree(len(seeds))
for i,p in enumerate(seeds):kd.insert(p.center,i)
kd.balance();values=[]
for v in head.data.vertices:
 c=v.co;_,_,d=kd.find(c);outer=smooth(.18,.225,abs(c.y));radius=.006+outer*.023;f=1-smooth(radius*.18,radius,d);f*=smooth(.125,.145,c.x)*smooth(.07,.08,abs(c.y))*(1-smooth(.248,.262,abs(c.y)))*smooth(.10,.11,c.z)*(1-smooth(.185,.205,c.z));values.append(f)
bpy.data.objects.remove(probe,do_unlink=True);adj=[set() for _ in values]
for e in head.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
for _ in range(2):
 old=values.copy()
 for i in range(len(values)):
  if adj[i]:values[i]=old[i]*.75+sum(old[j] for j in adj[i])/len(adj[i])*.25
for a,f in zip(head.data.attributes['Lash_color_repair'].data,values):a.value=f
masked=bpy.data.materials['Face_atlas_with_smooth_lash_color_repair'];orig=next(n.image for n in masked.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and n.image.name=='Color');image=orig.copy();image.name='Face_color_local_lashes_fixed_v3';image.filepath_raw=str(A/'face_color_lashes_fixed_v3.png');image.file_format='PNG'
dup=head.copy();dup.data=head.data.copy();sc.collection.objects.link(dup);dup.name='TEMP_lash_bake_region';dup.data.materials.clear();dup.data.materials.append(masked);dup.shape_key_clear()
bm=bmesh.new();bm.from_mesh(dup.data);bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table();delete=[f for f in bm.faces if max(values[v.index] for v in f.verts)<.0001];bmesh.ops.delete(bm,geom=delete,context='FACES');bm.to_mesh(dup.data);bm.free()
nt=masked.node_tree;node=nt.nodes.new('ShaderNodeTexImage');node.image=image
for n in nt.nodes:n.select=False
node.select=True;nt.nodes.active=node;bpy.ops.object.select_all(action='DESELECT');dup.select_set(True);bpy.context.view_layer.objects.active=dup;sc.cycles.samples=16;sc.render.bake.use_clear=False;sc.render.bake.margin=1;sc.render.bake.use_pass_direct=False;sc.render.bake.use_pass_indirect=False;sc.render.bake.use_pass_color=True;bpy.ops.object.bake(type='DIFFUSE');image.save();image.pack();bpy.data.objects.remove(dup,do_unlink=True)
portable=head.data.materials[0];pnt=portable.node_tree;b=next(n for n in pnt.nodes if n.type=='BSDF_PRINCIPLED');new=pnt.nodes.new('ShaderNodeTexImage');new.image=image;pnt.links.new(new.outputs['Color'],b.inputs['Base Color'])
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();cam=sc.camera;sc.cycles.samples=24
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:render(n,pos)
hair.hide_render=True;render('eyes_clean',(3,0,0),Vector((.18,0,.145)),.52);render('mouth_closed',(3,-.1,0),Vector((.26,0,-.085)),.34)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();render('mouth_open',(3,-.6,0),Vector((.23,0,-.085)),.38)
hair.hide_render=False;ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if o.type=='MESH' and not o.hide_render and not o.hide_get():o.select_set(True)
bpy.context.view_layer.objects.active=head;bpy.ops.export_scene.gltf(filepath=str(A/'explorer_b_young_bob_closed_smile_v3.glb'),export_format='GLB',use_selection=True,export_animations=False,export_apply=False,export_morph=True)
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.ops.wm.save_as_mainfile(filepath=str(FILE));print('LOCAL_LASH_UV_BAKE_COMPLETE')
