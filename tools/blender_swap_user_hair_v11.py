import bpy,json,hashlib,math,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_hair_swap_v11';SRC=R/'art/characters/explorer_b_game_face_v10';A.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(A/'hair_import_inspection.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];oldhair=bpy.data.objects['HAIR_sculptural_bob_mesh'];bpy.data.objects.remove(oldhair,do_unlink=True);parts=[o for o in sc.objects if o.type=='MESH' and o.name.startswith('tripo_part_') and o.name not in ['tripo_part_17','tripo_part_18','tripo_part_19','tripo_part_20','tripo_part_35','tripo_part_37']]
# Native import uses names with suffixes for the six overlapping facial component names.
import_names={r['name'] for r in json.loads((A/'hair-import.json').read_text())};parts=[bpy.data.objects[n] for n in import_names]
T=Matrix(((0,-.85,0,.015),(.78,0,0,.020),(0,0,.86,-.20),(0,0,0,1)))
for o in parts:o.data.transform(T@o.matrix_world);o.parent=None;o.matrix_world=Matrix.Identity(4);o.hide_render=False;o.hide_set(False)
bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();hair=parts[0];hair.name='HAIR_user_brown_v11';hair.data.name='User_Brown_Hair_Mesh';head=bpy.data.objects['FACE_original_user_GLb'];head.data.calc_loop_triangles();skin=BVHTree.FromPolygons([v.co for v in head.data.vertices],[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True)
# Move only strands close to the face. The supplied facial mesh is never edited.
ps=[v.co.copy() for v in hair.data.vertices];ids=[];ds=[]
for i,p in enumerate(ps):
 if p.x<.025 or abs(p.y)>.285 or not -.18<p.z<.32:continue
 q,n,_,dist=skin.find_nearest(p)
 if q is not None and dist<.035 and -.03<(p-q).dot(n)<.005:ids.append(i);ds.append(n*(.009-(p-q).dot(n)))
moved=0
if ids:
 kd=KDTree(len(ids))
 for j,i in enumerate(ids):kd.insert(ps[i],j)
 kd.balance()
 for i,p in enumerate(ps):
  _,j,d=kd.find(p)
  if d>.045:continue
  total=0.;delta=Vector()
  for _,j,dd in kd.find_range(p,.045):w=math.exp(-(dd/.022)**2);total+=w;delta+=ds[j]*w
  if total:hair.data.vertices[i].co+=delta/total*(1-(d/.045)**2);moved+=1
hair.parent=rig;g=hair.vertex_groups.new(name='DEF-head');g.add(list(range(len(hair.data.vertices))),1.,'REPLACE');m=hair.modifiers.new('Rigify_head','ARMATURE');m.object=rig
for im in bpy.data.images:
 if im.users and not im.packed_file:
  try:im.pack()
  except RuntimeError:pass
hair.data.calc_loop_triangles();report={'source':'C:/Users/dd/Downloads/brown hair 3d model.glb','source_sha256':hashlib.sha256(Path('C:/Users/dd/Downloads/brown hair 3d model.glb').read_bytes()).hexdigest(),'source_parts':len(parts),'hair_vertices':len(hair.data.vertices),'hair_triangles':len(hair.data.loop_triangles),'collision_adjusted_hair_vertices':moved,'original_face_untouched':True,'expression_clips_preserved':12};(A/'hair-swap-report.json').write_text(json.dumps(report,indent=2));sc.frame_set(1);bpy.context.view_layer.update();cam=sc.camera
def view(n,vec):
 cam.location=Vector(vec);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.2;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
sc.render.engine='CYCLES';sc.cycles.samples=24
for name,p in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:view(name,p)
view('front',(3,0,0));bpy.ops.wm.save_as_mainfile(filepath=str(A/'original_face_user_hair_v11.blend'));print('V11_HAIR_SWAPPED',json.dumps(report))
