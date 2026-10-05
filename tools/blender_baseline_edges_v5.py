import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_clean_edges_v5/assembly'
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_face_balance_v4/assembly/explorer_b_balanced_face_v4.blend'));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh']
for c in head.data.color_attributes['Lash_tint'].data:c.color=(1,1,1,1)
head.data.normals_split_custom_set([(0,0,0)]*len(head.data.loops))
rows=[]
for y in np.linspace(-.18,.18,73):
 cs=[v.co for v in head.data.vertices if abs(v.co.y-y)<.006 and v.co.x>.035 and -.32<v.co.z<-.155]
 if cs:rows.append([float(y),min(v.z for v in cs)])
(A/'chin-wide-before.json').write_text(json.dumps(rows,indent=2))
sc.render.resolution_x=900;sc.render.resolution_y=800;sc.cycles.samples=20;cam=sc.camera
def render(n,pos,target,scale):
 cam.location=Vector(target)+Vector(pos);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
hair.hide_render=True;render('baseline_eyes',(3,0,0),(.18,0,.145),.53);render('baseline_eye_angle',(3,-2,0),(.18,-.12,.145),.27);render('baseline_chin',(3,0,0),(.18,0,-.11),.37)
hair.hide_render=False;bpy.ops.wm.save_as_mainfile(filepath=str(A/'baseline.blend'))
print('BASELINE_READY')
