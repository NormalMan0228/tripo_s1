import bpy,math,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';FILE=A/'user_head_mpfb_rigify_v8.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update();head=bpy.data.objects['FACE_user_head'];keys=head.data.shape_keys.key_blocks;start=len(head.data.vertices)-2048
for side,offset in [('R',0),('L',1024)]:
 eye=bpy.data.objects['EYEBALL_'+side];eo=eye.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();tree=BVHTree.FromPolygons([eye.matrix_world@v.co for v in me.vertices],[tuple(t.vertices) for t in me.loop_triangles],all_triangles=True);eo.to_mesh_clear()
 for k in range(8):
  for j in range(128):
   i=start+offset+k*128+j;theta=2*math.pi*j/128;sin=math.sin(theta);p=keys[0].data[i].co.copy();q=p.copy();q.z+=(-.003 if sin>=0 else .013)*abs(sin)**.9*((k+1)/8)**2;hit,*_=tree.ray_cast(Vector((1,q.y,q.z)),Vector((-1,0,0)))
   if hit is not None:q.x=max(q.x,hit.x+.003)
   delta=q-p
   for key in keys:
    if key.name not in {'!ex-eyeBlinkLeft','!ex-eyeBlinkRight'}:key.data[i].co+=delta
# Refit the upper lash rest surface to the adjusted lid.
head.data.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in keys[0].data],[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True)
for side in ['L','R']:
 o=bpy.data.objects['LASH_upper_'+side];ks=o.data.shape_keys.key_blocks
 for i,v in enumerate(ks[0].data):
  p=v.co.copy();q=p.copy()
  if i<324:q.z-=.003*math.sin(math.pi*(i//4)/80)**.9
  hit,*_=tree.ray_cast(Vector((1,q.y,q.z)),Vector((-1,0,0)))
  if hit is not None:q.x=hit.x+(.0010 if (i%4<2 if i<324 else i-324<3) else .00020)
  for key in ks:
   if key.name!='Blink_'+side:key.data[i].co+=q-p
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(FILE));print('REST_EYE_APERTURE_SOFTENED')
