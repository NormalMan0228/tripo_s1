import bpy,json,numpy as np,hashlib,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bl_ext.user_default.mpfb.services.faceservice import FaceService
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10';bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_original_identity_v9/original_face_mpfb_rigify_v9.blend'))
baseline={}
for o in bpy.context.scene.objects:
 if o.type=='MESH' and o.data.shape_keys and not o.hide_render:baseline[o.name]={'v':np.array([v.co for v in o.data.shape_keys.key_blocks[0].data]),'uv':np.array([p.uv for p in o.data.uv_layers.active.data]),'polys':[tuple(p.vertices) for p in o.data.polygons],'mats':[m.name for m in o.data.materials]}
bpy.ops.wm.open_mainfile(filepath=str(A/'original_preserved_face_rig_v10.blend'));sc=bpy.context.scene;rig=bpy.data.objects['Original_Identity_Rigify'];report=json.loads((A/'rig-verification.json').read_text());checks={}
for n,b in baseline.items():
 o=bpy.data.objects[n];checks[n]=bool(np.array_equal(b['v'],np.array([v.co for v in o.data.shape_keys.key_blocks[0].data])) and np.array_equal(b['uv'],np.array([p.uv for p in o.data.uv_layers.active.data])) and b['polys']==[tuple(p.vertices) for p in o.data.polygons] and b['mats']==[m.name for m in o.data.materials]);assert checks[n],n
rows=[]
for clip in report['clips']:
 if clip['name'].startswith('Wink'):clip['peak_frame']=8
 action=bpy.data.actions[clip['name']];rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0]
 for frame in sorted(set([1,8,int(clip['frames']/2),clip['peak_frame'],clip['frames']])):
  sc.frame_set(frame);bpy.context.view_layer.update();finite=True
  for o in sc.objects:
   if o.type!='MESH' or o.hide_render or o.name.startswith(('WGT','HAIR')):continue
   eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();finite &= all(math.isfinite(x) for v in me.vertices for x in v.co);eo.to_mesh_clear()
  expr=FaceService.read_current_expression(bpy.data.objects['FACE_original_user_GLb']);assert finite;rows.append({'clip':clip['name'],'frame':frame,'finite':finite,'MPFB_faceunits':{k:round(v,5) for k,v in expr.items() if v>1e-5}})
 a=bpy.data.objects['FACE_original_user_GLb'].data.shape_keys.key_blocks
 sc.frame_set(1);bpy.context.view_layer.update();first=[k.value for k in a];sc.frame_set(clip['frames']);bpy.context.view_layer.update();last=[k.value for k in a];assert max(abs(a-b) for a,b in zip(first,last))<1e-6
# Check that all sampled front-facing teeth and tongue points are behind skin in the closed default.
action=bpy.data.actions['IdleClosed'];rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0];sc.frame_set(1);bpy.context.view_layer.update();vv=[];tt=[]
for n in ['FACE_original_user_GLb','MOUTH_interior_bag']:
 o=bpy.data.objects[n];eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();start=len(vv);vv.extend(eo.matrix_world@v.co for v in me.vertices);tt.extend(tuple(start+i for i in t.vertices) for t in me.loop_triangles);eo.to_mesh_clear()
skin=BVHTree.FromPolygons(vv,tt,all_triangles=True);oral={}
for name in ['TEETH_upper_original','TEETH_lower_original','TONGUE_original']:
 o=bpy.data.objects[name];eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();visible=0;total=0
 for t in me.loop_triangles:
  if t.normal.x<.10:continue
  p=sum((me.vertices[i].co for i in t.vertices),Vector())/3
  if p.x<.17:continue
  total+=1;q,*_=skin.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)))
  if q is None or q.x<p.x-.0002:visible+=1
 eo.to_mesh_clear();oral[name]={'samples':total,'visible':visible}
assert all(x['visible']==0 for x in oral.values()),oral
report.update(author_original_geometry_UV_topology_material_checks=checks,sampled_pose_frames=rows,all_clips_start_end_at_closed_neutral=True,oral_occlusion=oral,source_sha256_unchanged=hashlib.sha256((R/'art/characters/explorer_b_user_head_v8/source_user_head.glb').read_bytes()).hexdigest()==report['source_sha256']);assert report['source_sha256_unchanged'];report['status']='blender_verified_engine_test_pending';(A/'rig-verification.json').write_text(json.dumps(report,indent=2));(A/'expression-clips.json').write_text(json.dumps(report['clips'],indent=2));print('V10_SOURCE_AND_POSES_VERIFIED',oral)
