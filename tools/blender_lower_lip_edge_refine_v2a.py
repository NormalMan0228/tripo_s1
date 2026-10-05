"""Small additive edit of the V2 lower-lip underside; no topology replacement."""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1]
SRC=R/'art/characters/explorer_b_face_rig_manual_v2/explorer_manual_face_rig_v2.blend'
OUT=R/'art/characters/explorer_b_face_rig_manual_v2a';OUT.mkdir(exist_ok=True)
sha=hashlib.sha256(SRC.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SRC));sc=bpy.context.scene;sc.frame_set(1)
head=bpy.data.objects['01_Face_skin_neck'];ks=head.data.shape_keys.key_blocks
original=[v.co.copy() for v in ks['jawOpen'].data];old=[v.co.copy() for v in ks['Basis'].data]
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
deltas=[]
for p in original:
 x,y,z=p;center=-.238+.036*(y/.08)**2
 w=math.exp(-((z-center)/.013)**2)*math.exp(-(y/.062)**4)*smooth(.215,.27,x)
 w*=smooth(-.261,-.248,z)*(1-smooth(center+.008,center+.024,z))
 # Lift the lower edge, soften its projection, keep the lip opening and chin fixed.
 deltas.append(Vector((-.0045*w,0,.015*w)))
cam=sc.camera
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
sc.render.resolution_x=900;sc.render.resolution_y=650;sc.render.resolution_percentage=100;sc.cycles.samples=24
def render(name):
 sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
def wire():
 ev=head.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 cu=bpy.data.curves.new('Temporary local wire inspection','CURVE');cu.dimensions='3D';cu.bevel_depth=.00019;cu.bevel_resolution=0;cu.resolution_u=1
 for edge in mesh.edges:
  a,b=[mesh.vertices[i].co for i in edge.vertices];c=(a+b)*.5
  if c.x>.24 and abs(c.y)<.15 and -.27<c.z<-.075:
   s=cu.splines.new('POLY');s.points.add(1)
   for dst,p in zip(s.points,[a,b]):dst.co=(p.x+.00065,p.y,p.z,1)
 ev.to_mesh_clear();obj=bpy.data.objects.new('TEMP_WIRE',cu);sc.collection.objects.link(obj)
 m=bpy.data.materials.get('Inspection wire') or bpy.data.materials.new('Inspection wire');m.diffuse_color=(.013,.012,.010,1);m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=m.diffuse_color;cu.materials.append(m)
 return obj
camera((.25,0,-.16),(4,0,0),.43)
render('before-shaded');w=wire();render('before-wire');bpy.data.objects.remove(w,do_unlink=True)
for key in ks:
 for i,v in enumerate(key.data):v.co+=deltas[i]
for i,v in enumerate(head.data.vertices):v.co=old[i]+deltas[i]
head.data.update();head.update_tag();sc.frame_set(2);sc.frame_set(1);bpy.context.view_layer.update()
group=head.vertex_groups.new(name='EDIT_lower_lip_U_curve')
edited=[i for i,d in enumerate(deltas) if d.length>.0001]
for i in edited:group.add([i],min(1,deltas[i].length/.015),'REPLACE')
render('after-shaded');w=wire();render('after-wire');bpy.data.objects.remove(w,do_unlink=True)
sc.frame_set(98);render('open-mouth-after')
sc.frame_set(1);camera((.18,0,-.15),(3,-3,.03),.70);render('after-angle')
camera((.1,0,0),(4,-.35,.12),1.30);sc.render.resolution_x=800;sc.render.resolution_y=800;render('after-full')
# Check the additive edit stays constant across shapes; head outline stays fixed.
assert all(d.length<1e-10 for p,d in zip(original,deltas) if p.z<=-.265 or abs(p.y)>=.15 or p.z>=-.09)
for key in ks:
 assert all(math.isfinite(c) for v in key.data for c in v.co)
sc.frame_set(1)
for o in sc.objects:o.select_set(False)
head.select_set(True);bpy.context.view_layer.objects.active=head;head.active_shape_key_index=0
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active;s.region_3d.view_location=(.22,0,-.15);s.region_3d.view_rotation=Vector((-1,0,0)).to_track_quat('-Z','Y');s.region_3d.view_distance=.85;s.region_3d.view_perspective='ORTHO';s.overlay.show_extras=False
report={'source':str(SRC),'source_unchanged':sha==hashlib.sha256(SRC.read_bytes()).hexdigest(),'topology_replaced':False,'vertices':len(head.data.vertices),'faces':len(head.data.polygons),'edited_vertices_over_0_0001':len(edited),
 'max_lift':max(d.z for d in deltas),'max_inward_move':max(-d.x for d in deltas),'preserved_chin_and_upper_face':True,'same_additive_delta_all_shape_keys':True,'api_credits':0}
assert report['source_unchanged']
sc['RIG_STATUS']='V2a: local lower-lip underside U-edge refinement, based on V2. No V3 mouth replacement.'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_face_lower_lip_v2a.blend'))
(OUT/'lower-lip-edit-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('LOWER_LIP_REFINED',json.dumps(report),flush=True)
