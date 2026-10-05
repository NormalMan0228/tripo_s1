"""Fit closing lids to the complete globe/cornea envelope over the demonstrated gaze range."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';FILE=A/'user_head_mpfb_rigify_v8.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update();head=bpy.data.objects['FACE_user_head'];basis=head.data.shape_keys.key_blocks[0];head.data.calc_loop_triangles();tris=[tuple(t.vertices) for t in head.data.loop_triangles];report={}
for side in ['L','R']:
 eye=bpy.data.objects['EYEBALL_'+side];center=eye.matrix_world.translation.copy();samples=[];faces=[]
 for yaw,pitch in [(0,0),(7,1),(-7,-1),(3,1),(-3,-1)]:
  q=Quaternion(Vector((0,0,1)),math.radians(yaw))@Quaternion(Vector((0,1,0)),math.radians(-pitch))
  for o in [eye,bpy.data.objects['IRIS_PUPIL_'+side]]:
   eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();start=len(samples);samples.extend(center+q@(o.matrix_world@v.co-center) for v in me.vertices);faces.extend(tuple(start+i for i in t.vertices) for t in me.loop_triangles);eo.to_mesh_clear()
 envelope=BVHTree.FromPolygons(samples,faces,all_triangles=True);closed=head.data.shape_keys.key_blocks.get('Blink_'+side) or head.data.shape_keys.key_blocks['!ex-eyeBlink'+('Left' if side=='L' else 'Right')];arc=head.data.shape_keys.key_blocks['Blink_arc_'+side];affected=[i for i,(a,b) in enumerate(zip(basis.data,closed.data)) if (a.co-b.co).length>1e-8];maximum=0
 for i in affected:
  p=closed.data[i].co;hit,*_=envelope.ray_cast(Vector((1,p.y,p.z)),Vector((-1,0,0)))
  if hit is not None:
   delta=max(0,hit.x+.004-p.x);p.x+=delta;maximum=max(maximum,delta)
  mid=basis.data[i].co.lerp(p,.5);hit,*_=envelope.ray_cast(Vector((1,mid.y,mid.z)),Vector((-1,0,0)))
  if hit is not None:arc.data[i].co.x=basis.data[i].co.x+max(0,hit.x+.004-mid.x)
 # Project lashes onto the corrected skin shell, keeping their thin volume intact.
 ct=BVHTree.FromPolygons([v.co for v in closed.data],tris,all_triangles=True);half=[a.co+(b.co-a.co)*.5+(c.co-a.co) for a,b,c in zip(basis.data,closed.data,arc.data)];ht=BVHTree.FromPolygons(half,tris,all_triangles=True);lash=bpy.data.objects['LASH_upper_'+side];lb=lash.data.shape_keys.key_blocks[0];lc=lash.data.shape_keys.key_blocks['Blink_'+side];la=lash.data.shape_keys.key_blocks['Blink_arc_'+side]
 for i,(a,b,c) in enumerate(zip(lb.data,lc.data,la.data)):
  front=(i%4<2) if i<324 else (i-324)<3;offset=.0010 if front else .00020;hit,*_=ct.ray_cast(Vector((1,b.co.y,b.co.z)),Vector((-1,0,0)))
  if hit is not None:b.co.x=hit.x+offset
  mid=a.co.lerp(b.co,.5);hit,*_=ht.ray_cast(Vector((1,mid.y,mid.z)),Vector((-1,0,0)))
  if hit is not None:c.co.x=a.co.x+hit.x+offset-mid.x
 report[side]={'affected_lid_vertices':len(affected),'max_additional_closed_lid_projection':maximum,'gaze_range_degrees':7,'includes_cornea_and_iris_cap':True}
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(FILE));(A/'blink-envelope-report.json').write_text(json.dumps(report,indent=2));print('BLINK_ENVELOPE',json.dumps(report))
