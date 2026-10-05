import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_clean_edges_v5/assembly';bpy.ops.wm.open_mainfile(filepath=str(A/'explorer_b_clean_edges_v5.blend'));sc=bpy.context.scene;o=bpy.data.objects['FACE_skin_eyelids_lashes'];groups=json.loads((A/'lash-uv-islands.json').read_text());keep={0,6,12,14,17};faces={i for j,g in enumerate(groups) if j in keep for i in g['indices']}
for p in o.data.polygons:p.material_index=1 if p.index in faces else 0
o['lash_color_repair']='Dark material on upper lash surface UV charts only; tear-duct and eyelid skin charts retain original skin texture'
report=json.loads((A/'refinement-report.json').read_text());report.update(lash_faces=len(faces),lash_uv_charts=len(keep),excluded_skin_charts=sorted(set(range(len(groups)))-keep));(A/'refinement-report.json').write_text(json.dumps(report,indent=2))
bpy.data.objects['HAIR_sculptural_bob_mesh'].hide_render=True;cam=sc.camera;sc.cycles.samples=20
def render(n,pos,target,scale):
 cam.location=Vector(target)+Vector(pos);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
render('eyes_detail',(3,0,0),(.18,0,.145),.53);render('eye_angle_L',(3,-2,0),(.18,-.12,.145),.28);render('eye_angle_R',(3,2,0),(.18,.12,.145),.28)
bpy.data.objects['HAIR_sculptural_bob_mesh'].hide_render=False;target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23;bpy.ops.wm.save_as_mainfile(filepath=str(A/'explorer_b_clean_edges_v5.blend'));print('BOUNDARY_SAVED')
