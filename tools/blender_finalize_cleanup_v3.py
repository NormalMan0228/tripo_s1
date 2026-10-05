"""Smooth, UV-preserving lash color correction and compact bob finishing."""
import bpy,math,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly';FILE=A/'explorer_b_young_bob_closed_smile_v3.blend'
bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh']
def smooth(a,b,t):
 t=max(0,min(1,(t-a)/(b-a)));return t*t*(3-2*t)
# Recolor with a continuous vertex mask instead of abrupt polygon boundaries.
seed=[p for p in head.data.polygons if p.material_index==1];kd=KDTree(len(seed))
for i,p in enumerate(seed):kd.insert(p.center,i)
kd.balance();attr=head.data.attributes.new('Lash_color_repair','FLOAT','POINT');values=[]
for v in head.data.vertices:
 c=v.co;_,_,d=kd.find(c);outer=smooth(.18,.225,abs(c.y));radius=.006+outer*.023
 f=1-smooth(radius*.18,radius,d)
 f*=smooth(.125,.145,c.x)*smooth(.07,.08,abs(c.y))*(1-smooth(.248,.262,abs(c.y)))*smooth(.10,.11,c.z)*(1-smooth(.185,.205,c.z))
 values.append(f)
adj=[set() for _ in values]
for e in head.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
for _ in range(2):
 old=values.copy()
 for i in range(len(values)):
  if adj[i]:values[i]=old[i]*.75+sum(old[j] for j in adj[i])/len(adj[i])*.25
for a,f in zip(attr.data,values):a.value=f
base=head.data.materials[0];clean=base.copy();clean.name='Face_atlas_with_smooth_lash_color_repair';nt=clean.node_tree;b=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED');old=next(l.from_socket for l in nt.links if l.to_socket==b.inputs['Base Color']);nt.links.remove(next(l for l in nt.links if l.to_socket==b.inputs['Base Color']))
mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[2].default_value=(.010,.004,.002,1);mask=nt.nodes.new('ShaderNodeAttribute');mask.attribute_name=attr.name;nt.links.new(mask.outputs['Fac'],mix.inputs[0]);nt.links.new(old,mix.inputs[1]);nt.links.new(mix.outputs[0],b.inputs['Base Color']);head.data.materials.clear();head.data.materials.append(clean)
for p in head.data.polygons:p.material_index=0
head['lash_color_repair']='Continuous point attribute mask; original UV color unchanged; no rectangular face-color seams'
# Open both eyes under the sweeping bangs while retaining the original broad locks.
for v in hair.data.vertices:
 c=v.co
 weight=smooth(.10,.23,c.x)*(1-smooth(.145,.23,abs(c.y)))*(1-smooth(.235,.37,c.z))*smooth(.08,.15,c.z)
 c.z+=max(0,.227-c.z)*weight*.85
 # Narrow the round outer side silhouette slightly, leaving the crown compact.
 c.y*=1-.018*(1-smooth(.12,.30,c.z))
hair.data.update();hair['source']='New approved four-view compact bob, Tripo task bec78fb4-f468-4e12-be63-d5fa27d1f09c';hair['new_generation_credits']=40
ctrl=bpy.data.objects['FACE_CONTROLS'];ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update()
notes=bpy.data.texts.get('READ_ME');notes.clear();notes.write('v3: NEW separate Tripo HD solid bob, matching approved four-view references. No cards. Face locally cleaned in Blender. EYEBALL_L/R are independent objects with centered rotation pivots; UV iris and catchlights preserved. Lash color is corrected by smooth material mask without changing the original atlas. Teeth are ivory, gums and tongue pink. Default closed gentle smile; FACE_CONTROLS mouth_open 0 to 1 switches to exact original open-mouth face geometry, preserving oral inspection. Original Tripo head and hair kept hidden. Full facial rig and game optimization pending.\n')
cam=sc.camera;sc.cycles.samples=24
def view(pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 view(pos,target,scale);sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
view((3,0,0))
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   sp=a.spaces.active;sp.region_3d.view_location=(0,0,.08);sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_distance=1.55;sp.region_3d.view_perspective='ORTHO';sp.shading.type='MATERIAL';sp.overlay.show_extras=False
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:render(n,pos)
hair.hide_render=True;render('eyes_clean',(3,0,0),Vector((.18,0,.145)),.52);render('mouth_closed',(3,-.1,0),Vector((.26,0,-.085)),.34)
ctrl['mouth_open']=1.;ctrl.update_tag();sc.frame_set(101);bpy.context.view_layer.update();render('mouth_open',(3,-.6,0),Vector((.23,0,-.085)),.38)
hair.hide_render=False;ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update();view((3,0,0));bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
(A/'smooth-lash-report.json').write_text(json.dumps({'attribute':attr.name,'mask_nonzero_vertices':sum(v>1e-4 for v in values),'original_uv_atlas_unchanged':True,'hard_face_color_boundaries':False,'hair_generation_credits':40}),encoding='utf-8');print('FINALIZED',FILE)
