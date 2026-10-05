import bpy,json,itertools,math
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_face_rig_manual_v2f';F=O/'explorer_orbit_gaze_v2f.blend'
bpy.ops.wm.open_mainfile(filepath=str(F));sc=bpy.context.scene;sc.frame_set(1);rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];h=bpy.data.objects['01_Face_skin_neck']
action=rig.animation_data.action;rig.animation_data.action=None
props=['blink_L','blink_R','jaw_open','smile','frown','pucker','brow_up','brow_frown','look_lr','look_ud']
def pose(lr,ud,blink,headangle):
 for p in props:rig[p]=0.
 rig['look_lr']=lr;rig['look_ud']=ud;rig['blink_L']=blink;rig['blink_R']=blink
 rig.pose.bones['head'].rotation_mode='XYZ';rig.pose.bones['head'].rotation_euler=(0,headangle,headangle*.5)
 rig.update_tag();bpy.context.view_layer.update()
def coords(obj,deps,inv):
 ev=obj.evaluated_get(deps);me=ev.to_mesh();p=[inv@v.co for v in me.vertices];faces=[list(f.vertices) for f in me.polygons];ev.to_mesh_clear();return p,faces
baseline={};worst=0.;maxpenetration=0.;penetrating=0;cases=0;examples=[]
tests=[(0,0,0,0)]+list(itertools.product([-1,0,1],[-1,0,1],[0,.5,1],[0,.20]))
for lr,ud,blink,ha in tests:
 pose(lr,ud,blink,ha);deps=bpy.context.evaluated_depsgraph_get();M=rig.pose.bones['head'].matrix@rig.data.bones['head'].matrix_local.inverted();inv=M.inverted()
 hp,hf=coords(h,deps,inv);bvh=BVHTree.FromPolygons(hp,hf)
 for side,sign in [('L',1),('R',-1)]:
  center=np.array([.185,.149*sign,.061]);radii=np.array([.066,.083,.085])
  for name in ['Eye_white.'+side,'Iris_pupil.'+side]:
   points,_=coords(bpy.data.objects[name],deps,inv);arr=np.array(points);assert np.isfinite(arr).all();radius=np.linalg.norm((arr-center)/radii,axis=1)
   if name not in baseline:baseline[name]=radius
   error=float(np.max(np.abs(radius-baseline[name])));worst=max(worst,error)
   for p in points:
    if p.x<.19:continue
    hit=bvh.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)),2)[0]
    if hit is not None and hit.x>.16:
     pen=p.x-hit.x;maxpenetration=max(maxpenetration,pen)
     if pen>.0005:
      penetrating+=1
      if len(examples)<8:examples.append([name,lr,ud,blink,ha,list(p),list(hit),pen])
 cases+=1
print('ENVELOPE',worst,'PENETRATION',maxpenetration,penetrating,examples,flush=True)
assert worst<.00003, 'Eye envelope changes under gaze or posed head transform'
pose(0,0,0,0);rig.animation_data.action=action;sc.frame_set(1)
# Verify that all mouth/chin rest vertices remain exactly from the approved V2e source.
with bpy.data.libraries.load(str(R/'art/characters/explorer_b_face_rig_manual_v2e/explorer_face_contours_v2e.blend')) as (a,b):b.objects=['01_Face_skin_neck']
source=b.objects[0]
def mouthset(obj):return {tuple(round(c,7) for c in v.co) for v in obj.data.shape_keys.key_blocks['Basis'].data if v.co.z<-.065}
assert mouthset(source)==mouthset(h)
bpy.data.objects.remove(source,do_unlink=True)
report=json.loads((O/'orbit-gaze-report.json').read_text());report['verification']={'pose_cases':cases,'head_rotation_tested':True,'max_normalized_eye_radius_change':worst,'max_frontal_skin_penetration':maxpenetration,'skin_penetration_samples_over_0_0005':penetrating,'examples':examples,'mouth_and_chin_basis_unchanged':True,'scope':'Discrete gaze/blink grid; vertex-to-frontal-skin ray tests, not a continuous triangle collision proof.'}
(O/'orbit-gaze-report.json').write_text(json.dumps(report,indent=2))
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS') or bpy.data.texts.new('READ_ME_FACE_CONTROLS');txt.clear();txt.write('V2f orbit and gaze revision\nBroad eye-socket depression filled, five local overlapping skin patches repaired. Approved mouth/chin and neutral lashes preserved.\nGaze uses normalized-sphere rotation followed by ellipsoid scaling in the posed head frame. These live Geometry Nodes must be baked or reproduced when exporting animation to Godot; this file is the Blender source.\nControls: select FACE_RIG__select_Custom_Properties; blink_L/R, look_lr/ud. Space plays the comparison. Unlink the demo action for manual posing.\nV2e is preserved. No API credits spent.\n')
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(F));print('ORBIT_VALIDATED',flush=True)
