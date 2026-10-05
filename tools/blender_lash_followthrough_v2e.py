"""Tuck the lash band toward its lid attachment as the eyelid closes."""
import bpy,collections,json,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_face_rig_manual_v2e';F=O/'explorer_face_contours_v2e.blend'
bpy.ops.wm.open_mainfile(filepath=str(F));s=bpy.context.scene;s.frame_set(1);head=bpy.data.objects['01_Face_skin_neck'];ks=head.data.shape_keys.key_blocks
edges=collections.Counter(tuple(sorted((a,b))) for p in head.data.polygons for a,b in zip(list(p.vertices),list(p.vertices)[1:]+list(p.vertices)[:1]));boundary={i for e,n in edges.items() if n==1 for i in e}
for side,lname in [('L','08_Upper_lash_candidate_posY'),('R','07_Upper_lash_candidate_negY')]:
 sign=1 if side=='L' else -1
 ids=[i for i in boundary if .06<ks['Basis'].data[i].co.y*sign<.24 and .05<ks['Basis'].data[i].co.z<.13]
 ids.sort(key=lambda i:ks['Basis'].data[i].co.y);o=bpy.data.objects[lname]
 for k in range(1,5):
  amount=k/4;points=[ks['IntegratedBlink_'+side+'_'+str(k*25)].data[i].co.copy() for i in ids];ys=[p.y for p in points]
  for v in o.data.shape_keys.key_blocks['Blink_'+str(k*25)].data:
   p=v.co;anchor=Vector((float(np.interp(p.y,ys,[p.x for p in points])),p.y,float(np.interp(p.y,ys,[p.z for p in points]))))
   p.x=anchor.x+(p.x-anchor.x)*(1-.60*amount)
   p.z=anchor.z+(p.z-anchor.z)*(1-.50*amount)
 o.data.update()
c=s.camera
def camera(offset):
 t=Vector((.20,-.149,.07));c.location=t+Vector(offset);c.rotation_euler=(t-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=.34
hidden=[]
for o in s.objects:
 if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
for frame,label in [(15,'half'),(18,'closed')]:
 s.frame_set(frame)
 for offset,view in [((4,-.4,0),'front'),((1.3,-4,.08),'side')]:
  camera(offset);s.render.filepath=str(O/('lash-follow-'+label+'-'+view+'.png'));bpy.ops.render.render(write_still=True)
if '--save' in sys.argv:
 for o in hidden:o.hide_render=False
 s.frame_set(1);t=Vector((.1,0,0));c.location=t+Vector((4,-.35,.12));c.rotation_euler=(t-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=1.3
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(F))
 report=json.loads((O/'correction-report.json').read_text());report['lash_followthrough']='During closure the band offset tucks toward the actual edge to avoid a tall folded wing. Neutral original lashes unchanged.';(O/'correction-report.json').write_text(json.dumps(report,indent=2))
 print('LASH_FINISH_SAVED',flush=True)
 first=None;last=None;maxstep=0.
 for f in range(1,241):
  s.frame_set(f);deps=bpy.context.evaluated_depsgraph_get();points=[]
  for name in ['08_Upper_lash_candidate_posY','07_Upper_lash_candidate_negY']:
   ev=bpy.data.objects[name].evaluated_get(deps);mesh=ev.to_mesh();points.extend([v.co[:] for v in mesh.vertices]);ev.to_mesh_clear()
  a=np.array(points);assert np.isfinite(a).all()
  if first is None:first=a.copy()
  if last is not None:maxstep=max(maxstep,float(np.linalg.norm(a-last,axis=1).max()))
  last=a
 assert np.abs(first-last).max()<1e-7
 report['final_lash_validation']={'frames':240,'loop_difference':float(np.abs(first-last).max()),'max_frame_step':maxstep}
 (O/'correction-report.json').write_text(json.dumps(report,indent=2))
 s.render.resolution_x=512;s.render.resolution_y=512;s.cycles.samples=8
 for o in hidden:o.hide_render=True
 frames=O/'blink_final_frames';frames.mkdir(exist_ok=True)
 for i in range(40):
  phase=i%20;time=12+12*(phase/19);s.frame_set(int(time),subframe=time-int(time));camera((4,-.4,0) if i<20 else (1.3,-4,.08))
  s.render.filepath=str(frames/(f'{i:03d}.png'));bpy.ops.render.render(write_still=True)
 print('FINAL_BLINK_DONE',flush=True)
print('LASH_FINISH_PREVIEW',flush=True)
