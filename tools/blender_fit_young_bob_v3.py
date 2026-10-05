"""Keep approved Tripo sculptural locks as a solid mesh, with a smooth scalp fit."""
import bpy,math,json,hashlib,numpy as np,sys
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];SOURCE=R/'art/characters/explorer_b_young_bob_face_cleanup_v3';OUT=R/'art/characters/explorer_b_face_multiview_meshhair_v2/mesh_hair_preview';OUT.mkdir(parents=True,exist_ok=True)
input_blend=SOURCE/'assembly/explorer_b_integrated_face_haircards_v1.blend';new_face=False
if '--' in sys.argv:
 args=sys.argv[sys.argv.index('--')+1:];input_blend=Path(args[0]).resolve();OUT=Path(args[1]).resolve();OUT.mkdir(parents=True,exist_ok=True);new_face=True
bpy.ops.wm.open_mainfile(filepath=str(input_blend));sc=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0
for collection_name in ['03_Hair_cards_GAME','92_Editable_hair_guides','02_HD_hair_form']:
 c=bpy.data.collections.get(collection_name)
 if c:
  for ob in list(c.objects):bpy.data.objects.remove(ob,do_unlink=True)
  bpy.data.collections.remove(c)
head=bpy.data.objects['FACE_skin_eyelids_lashes'];head.data.calc_loop_triangles()
skin=BVHTree.FromPolygons([v.co for v in head.data.vertices],[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True)
old=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(SOURCE/'hair/model.glb'));raw=next(o for o in bpy.data.objects if o not in old and o.type=='MESH')
raw.data.transform(raw.matrix_world);raw.parent=None;raw.matrix_world=Matrix.Identity(4);raw.name='HAIR_HD_SOURCE_UNCHANGED'
sourcecol=bpy.data.collections.new('90_HAIR_HD_source');sc.collection.children.link(sourcecol)
for c in list(raw.users_collection):c.objects.unlink(raw)
sourcecol.objects.link(raw);raw.hide_set(True);raw.hide_render=True;raw.hide_select=True
haircol=bpy.data.collections.new('02_MESH_hair_grouped_locks');sc.collection.children.link(haircol)
hair=raw.copy();hair.data=raw.data.copy();haircol.objects.link(hair);hair.name='HAIR_sculptural_bob_mesh';hair.hide_render=False;hair.hide_set(False);hair.hide_select=False
for v in hair.data.vertices:v.co=Vector((v.co.x*1.00-.018,v.co.y*.80,v.co.z*1.00+.205))
hair.data.update();hair.data.calc_loop_triangles();form=BVHTree.FromPolygons([v.co for v in hair.data.vertices],[tuple(t.vertices) for t in hair.data.loop_triangles],all_triangles=True)
center=Vector((-.045,0,.21));NP=80;NT=52;theta_max=2.28;delta=np.zeros((NT,NP));valid=np.zeros((NT,NP),dtype=bool)
def direction(phi,theta):return Vector((math.cos(phi)*math.sin(theta),math.sin(phi)*math.sin(theta),math.cos(theta)))
# Compare the inner wig surface to the scalp, then apply one smooth displacement
# to the complete lock thickness. Projecting every vertex onto skin crushes locks.
for j in range(NT):
 theta=.012+(theta_max-.012)*j/(NT-1)
 for i in range(NP):
  phi=-math.pi+2*math.pi*i/NP;d=direction(phi,theta)
  h,*_=skin.ray_cast(center+d*2,-d,3)
  p,*_=form.ray_cast(center,d,2)
  if h is None or p is None or h.z<.12 or (p-center).dot(d)<.08:continue
  excess=max(0,(h-center).length+.010-(p-center).length)
  delta[j,i]=min(.055,excess);valid[j,i]=True
for _ in range(12):
 prior=delta.copy()
 for j in range(NT):
  for i in range(NP):
   neighbors=[prior[j,(i-1)%NP],prior[j,(i+1)%NP],prior[max(0,j-1),i],prior[min(NT-1,j+1),i]]
   delta[j,i]=prior[j,i]*.66+sum(neighbors)*.085
for v in hair.data.vertices:
 q=v.co-center;r=q.length
 if r<.04:continue
 d=q/r;theta=math.acos(max(-1,min(1,d.z)))
 if theta>theta_max:continue
 phi=math.atan2(d.y,d.x);u=(phi+math.pi)/(2*math.pi)*NP;vi=(theta-.012)/(theta_max-.012)*(NT-1);vi=max(0,min(NT-1,vi));j=min(NT-2,int(vi));i=int(u)%NP;fu=u-math.floor(u);fv=vi-j
 shift=((1-fu)*delta[j,i]+fu*delta[j,(i+1)%NP])*(1-fv)+((1-fu)*delta[j+1,i]+fu*delta[j+1,(i+1)%NP])*fv
 v.co+=d*float(shift)
for p in hair.data.polygons:p.use_smooth=True
hair.data.update()
material=bpy.data.materials.new('Sculpted_chocolate_brown');material.use_nodes=True;bs=material.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.035,.016,.008,1);bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=.65;bs.inputs['Specular IOR Level'].default_value=.10
hair.data.materials.clear();hair.data.materials.append(material)
hair['source']='Approved separate four-view Tripo HD source, fitted copy';hair['hair_cards']=False;hair['scalp_fit']='Smoothed inner-surface clearance field, preserves thickness of complete hair locks'
hair['geometry_status']='HD sculptural mesh preview; mesh reduction and final bake deferred until new face fit is accepted'
ctrl=bpy.data.objects.get('FACE_CONTROLS')
if ctrl:ctrl['mouth_open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update()
sc.cycles.samples=16;cam=sc.camera
def view(pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
view((3,0,0))
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   sp=a.spaces.active;sp.region_3d.view_location=(0,0,.08);sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_distance=1.6;sp.region_3d.view_perspective='ORTHO'
notes=bpy.data.texts.get('READ_ME');notes.clear();notes.write('Solid mesh hair requested by user, no cards. Approved Tripo HD source preserved hidden. Hair fitted as volumetric grouped locks using inner-surface scalp clearance field. '+('Face is the NEW approved front/left/right multiview Tripo generation. Original open mouth retained for oral and jaw geometry review; no face reshaping applied. ' if new_face else 'Face is the PREVIOUS generation pending new front/side multiview generation; lower face is not finalized. ')+'No new Tripo cost for this hair refit. HD workbench, mesh reduction and full facial rigging pending.\n')
bpy.ops.object.select_all(action='DESELECT');hair.select_set(True);bpy.context.view_layer.objects.active=hair
blend=OUT/('explorer_b_young_bob_closed_smile_v3.blend' if new_face else 'explorer_b_mesh_hair_preview_v2.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for n,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:
 view(pos);sc.render.filepath=str(OUT/(n+'.png'));bpy.ops.render.render(write_still=True)
report={'status':'solid_mesh_hair_on_new_multiview_face' if new_face else 'solid_mesh_hair_preview_on_previous_face','blend':str(blend),'input_blend':str(input_blend),'hair_cards':False,'vertices':len(hair.data.vertices),'triangles':len(hair.data.polygons),'source_sha256':hashlib.sha256((SOURCE/'hair/model.glb').read_bytes()).hexdigest(),'source_preserved':True,'max_smoothed_clearance_displacement':float(delta.max()),'new_hair_API_credits':0,'face_is_previous_generation':not new_face,'low_poly_final':False}
(OUT/'hair-fit-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('MESH_HAIR_FIT',json.dumps(report))

