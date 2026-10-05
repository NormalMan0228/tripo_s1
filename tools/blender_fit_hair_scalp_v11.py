import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_hair_swap_v11';F=A/'original_face_user_hair_v11.blend';bpy.ops.wm.open_mainfile(filepath=str(F))
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
head=bpy.data.objects['FACE_original_user_GLb'];head.data.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in head.data.vertices],[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True);hair=bpy.data.objects['HAIR_user_brown_v11'];moved=0
with bpy.data.libraries.load(str(F.with_suffix('.blend1')),link=False) as (src,dst):dst.meshes=['User_Brown_Hair_Mesh']
original=[v.co.copy() for v in dst.meshes[0].vertices]
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
for v,p0 in zip(hair.data.vertices,original):
 p=p0.copy()
 if p.z<-.22 or p.x>.10:continue
 if p.x<0:p.x*=1+.16*smooth(-.16,.22,p.z)
 q,n,_,dist=tree.find_nearest(p)
 if q is not None and dist<.11 and (p-q).dot(n)<.01:p=q+n*.012;moved+=1
 v.co=p
sc=bpy.context.scene;cam=sc.camera
for label,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0)),('back',(-3,0,0))]:cam.location=Vector(pos);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(A/(label+'.png'));bpy.ops.render.render(write_still=True)
cam.location=(3,0,0);cam.rotation_euler=(Vector()-cam.location).to_track_quat('-Z','Y').to_euler();bpy.ops.wm.save_as_mainfile(filepath=str(F));report=json.loads((A/'hair-swap-report.json').read_text());report['scalp_fit_hair_vertices']=moved;(A/'hair-swap-report.json').write_text(json.dumps(report,indent=2));print('SCALP_HAIR_FITTED',moved)
