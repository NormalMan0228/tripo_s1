"""Repair lash pigment by actual UV seams; fair the closed-rest chin surface."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_clean_edges_v5/assembly';bpy.ops.wm.open_mainfile(filepath=str(A/'baseline.blend'));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS'];basis=head.data.shape_keys.key_blocks[0]
bpy.context.preferences.filepaths.save_version=0
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
# Color actual lash surface charts, never interpolate pigment across skin vertices.
groups=json.loads((A/'lash-uv-islands.json').read_text());keep={0,6,12,14,17};exclude=set(range(len(groups)))-keep;faces={i for j,g in enumerate(groups) if j in keep for i in g['indices']}
skin=bpy.data.objects['SOURCE_Tripo_face_0'].data.materials[0].copy();skin.name='Face_original_atlas_clean_edges';head.data.materials.clear();head.data.materials.append(skin)
for n in skin.node_tree.nodes:
 if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=.35
lash=bpy.data.materials.new('Lash_geometry_dark_brown_v5');lash.use_nodes=True;b=lash.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(.010,.0045,.0025,1);b.inputs['Roughness'].default_value=.55;b.inputs['Specular IOR Level'].default_value=.22;head.data.materials.append(lash)
for p in head.data.polygons:p.material_index=1 if p.index in faces else 0
for c in head.data.color_attributes['Lash_tint'].data:c.color=(1,1,1,1)
head.data.color_attributes.remove(head.data.color_attributes['Lash_tint'])
if head.data.attributes.get('Lash_color_repair'):head.data.attributes.remove(head.data.attributes['Lash_color_repair'])
# Fair broad lower-face geometry with a continuous falloff; leave mouth seam and neck intact.
original=[v.co.copy() for v in basis.data];coords=[c.copy() for c in original];adj=[set() for v in coords]
for e in head.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
weights=[smooth(.06,.135,c.x)*(1-smooth(.12,.18,abs(c.y)))*(1-smooth(-.165,-.125,c.z))*smooth(-.25,-.215,c.z) for c in original]
for _ in range(32):
 old=[c.copy() for c in coords]
 for i,w in enumerate(weights):
  if w<=0 or not adj[i]:continue
  avg=sum((old[j] for j in adj[i]),Vector())/len(adj[i]);coords[i]=old[i].lerp(avg,.48*w)
for v,k,c in zip(head.data.vertices,basis.data,coords):v.co=c;k.co=c
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
if head.data.has_custom_normals:bpy.ops.mesh.customdata_custom_splitnormals_clear()
head['lash_color_repair']='Uniform pigment on five upper-lash surface charts; eyelid and tear-duct skin retain original atlas; no skin vertex-paint interpolation';head['chin_v5']='32 fairing passes, broad lower-face falloff; neck and mouth seam retained'
report={'lash_faces':len(faces),'lash_uv_charts':len(groups)-len(exclude),'excluded_skin_charts':sorted(exclude),'chin_vertices_changed':sum((a-b).length>1e-7 for a,b in zip(original,coords)),'chin_max_displacement':max((a-b).length for a,b in zip(original,coords)),'head_custom_normals_cleared':not head.data.has_custom_normals,'skin_normal_strength':.35,'new_vertices':0,'new_Tripo_credits':0}
(A/'refinement-report.json').write_text(json.dumps(report,indent=2));print('CLEAN_EDGE_REPAIR',report)
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();sc.render.resolution_x=900;sc.render.resolution_y=1000;sc.cycles.samples=24;cam=sc.camera
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=Vector(target)+Vector(pos);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True;render('eyes_detail',(3,0,0),(.18,0,.145),.53);render('eye_angle_L',(3,-2,0),(.18,-.12,.145),.28);render('eye_angle_R',(3,2,0),(.18,.12,.145),.28);render('mouth_front',(3,0,0),(.18,0,-.10),.37);render('mouth_closed',(3,-.6,0),(.26,0,-.092),.34)
hair.hide_render=False
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:render(n,pos)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();hair.hide_render=True;render('mouth_open',(3,-.6,0),(.23,0,-.085),.38);hair.hide_render=False
ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23
bpy.ops.wm.save_as_mainfile(filepath=str(A/'explorer_b_clean_edges_v5.blend'));print('V5_SAVED')
