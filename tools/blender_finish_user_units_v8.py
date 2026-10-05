import bpy,numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';f=A/'user_head_mpfb_rigify_v8.blend';bpy.ops.wm.open_mainfile(filepath=str(f));sc=bpy.context.scene;head=bpy.data.objects['FACE_user_head'];neigh=[set() for _ in head.data.vertices]
for e in head.data.edges:a,b=e.vertices;neigh[a].add(b);neigh[b].add(a)
base=head.data.shape_keys.key_blocks[0]
for k in head.data.shape_keys.key_blocks:
 if not k.name.startswith('!ex-'):continue
 ds=np.array([(v.co-b.co)[:] for v,b in zip(k.data,base.data)])
 for _ in range(6):
  prev=ds.copy()
  for i in range(len(ds)):
   if neigh[i]:ds[i]=prev[i]*.70+prev[list(neigh[i])].mean(axis=0)*.30
 gain=1.5 if k.name.startswith('!ex-brow') else 1.
 for i,(v,b) in enumerate(zip(k.data,base.data)):v.co=b.co+Vector(ds[i]*gain)
for name in ['BROW_L','BROW_R']:
 o=bpy.data.objects[name];b=o.data.shape_keys.key_blocks[0]
 for k in o.data.shape_keys.key_blocks:
  if k.name.startswith('!ex-brow'):
   for v,p in zip(k.data,b.data):v.co=p.co+(v.co-p.co)*1.5
for name,shift in [('TEETH_GUMS_lower',(-.003,0,-.014)),('TONGUE',(-.003,0,-.010))]:
 o=bpy.data.objects[name];b=o.data.shape_keys.key_blocks[0];k=o.data.shape_keys.key_blocks['!ex-jawOpen']
 for v,p in zip(k.data,b.data):v.co=p.co+Vector(shift)
sc.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(f));sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True
for n,frame in [('neutral',1),('happy',95),('concern',195),('determined',295),('surprise',395),('blink_half',45),('blink_closed',47)]:
 sc.frame_set(frame);sc.render.filepath=str(A/(n+'.png'));bpy.ops.render.render(write_still=True)
print('V8_FACEUNITS_FINISHED')
