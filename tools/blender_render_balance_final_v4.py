import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_balance_v4/assembly';FILE=A/'explorer_b_balanced_face_v4.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];ctrl=bpy.data.objects['FACE_CONTROLS'];cam=sc.camera;sc.cycles.samples=32
def render(n,pos,target=Vector((0,0,.04)),scale=1.23):
 cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
render('front',(3,0,0));hair.hide_render=True;render('mouth_front',(3,0,0),Vector((.26,0,-.092)),.34);render('mouth_closed',(3,-.6,0),Vector((.26,0,-.092)),.34);hair.hide_render=False
# Confirm the complete GLB export uses the same eye color, hierarchy and rest.
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(A/'explorer_b_balanced_face_v4.glb'));added=[o for o in bpy.data.objects if o not in before];hidden=[o for o in sc.objects if o.type=='MESH' and o not in added and not o.hide_render]
for o in hidden:o.hide_render=True
render('glb_roundtrip_front',(3,0,0))
for o in added:bpy.data.objects.remove(o,do_unlink=True)
for o in hidden:o.hide_render=False
target=Vector((0,0,.04));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.23;bpy.ops.wm.save_as_mainfile(filepath=str(FILE));p=A/'verification.json';d=json.loads(p.read_text(encoding='utf-8'));d['final_file_reopened']=True;d['whole_glb_roundtrip_render']='glb_roundtrip_front.png';p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('FINAL_V4_RENDERED')
