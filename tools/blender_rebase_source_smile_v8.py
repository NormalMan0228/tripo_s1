"""Use the supplied GLB's mouth pose as the neutral, and retarget MPFB jawOpen."""
import bpy,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_pipeline_v3/01_template_test/mpfb_template_face_test.blend'));donor=bpy.data.objects['Template_Face_Body'];b=donor.data.shape_keys.key_blocks[0];k=donor.data.shape_keys.key_blocks['jawOpen']
def fit(p):
 x,y,z=p;h=float(np.interp(z,[1.40,1.445,1.475,1.515,1.548,1.580,1.69],[.23,.33,.435,.550,.652,.735,1.0]));sx=float(np.interp(z,[1.44,1.475,1.53,1.548,1.59],[3.1,2.65,3.5,4.2,3.5]));return Vector((-y*2-.035,x*sx,h-.535))
ps=[fit(v.co) for v in b.data];ds=[fit(v.co)-p for v,p in zip(k.data,ps)];kd=KDTree(len(ps))
for i,p in enumerate(ps):kd.insert(p,i)
kd.balance();f=A/'user_head_mpfb_rigify_v8.blend';bpy.ops.wm.open_mainfile(filepath=str(f));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update()
for o in sc.objects:
 if o.type!='MESH' or not o.data.shape_keys:continue
 keys=o.data.shape_keys.key_blocks;base=keys[0];op=keys.get('Mouth_open_original')
 if not op:continue
 original=[v.co.copy() for v in op.data];delta=[p-v.co for p,v in zip(original,base.data)]
 for key in keys:
  if key==op:continue
  for v,d in zip(key.data,delta):v.co+=d
 base.name='Basis_source_smile'
 for i,(v,p) in enumerate(zip(op.data,original)):
  if o.name.startswith(('FACE_','TEETH','TONGUE')) and p.x>.07 and p.z<.04:
   near=kd.find_n(p,4);ws=[1/max(.001,d)**2 for _,j,d in near];total=sum(ws);movement=sum((ds[j]*(w/total) for (_,j,d),w in zip(near,ws)),Vector())*.30
   if o.name.startswith('TEETH_upper'):movement*=0
   v.co=p+movement
  else:v.co=p
 op.name='!ex-jawOpen'
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(f));report=json.loads((A/'rig-report.json').read_text());report['rest_mouth']='Original supplied GLB smile / parted lips retained';report['jaw']='MPFB jawOpen spatially retargeted with conservative gain .30';report['MPFB_retarget_units'].append('jawOpen');(A/'rig-report.json').write_text(json.dumps(report,indent=2));print('SOURCE_SMILE_PRESERVED')
sc.render.engine='BLENDER_EEVEE_NEXT';sc.eevee.taa_render_samples=32
for n,frame in [('neutral',1),('happy',95),('concern',195),('determined',295),('surprise',395),('blink_half',45),('blink_closed',47)]:
 sc.frame_set(frame);bpy.context.view_layer.update();sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
