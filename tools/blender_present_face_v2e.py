import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_face_rig_manual_v2e';FILE=O/'explorer_face_contours_v2e.blend'
bpy.ops.wm.open_mainfile(filepath=str(FILE));s=bpy.context.scene;s.frame_set(1);h=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
m=h.modifiers.get('Surface finish') or h.modifiers.new('Surface finish','SUBSURF');m.levels=1;m.render_levels=1
c=s.camera
def camera(target,offset,scale):
 t=Vector(target);c.location=t+Vector(offset);c.rotation_euler=(t-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=scale
def render(name):s.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
hidden=[]
for o in s.objects:
 if o.type=='MESH' and o.name.startswith(('Hair','Nape')) and not o.hide_render:o.hide_render=True;hidden.append(o)
for f,label in [(1,'open'),(15,'half'),(18,'closed')]:
 s.frame_set(f)
 camera((.20,-.149,.07),(4,-.4,0),.30);render('eye-'+label+'-front')
 camera((.20,-.149,.07),(1.3,-4,.08),.34);render('eye-'+label+'-side')
s.frame_set(1);camera((.25,0,-.17),(4,0,0),.38);render('mouth-front')
camera((.24,0,-.16),(.25,-4,0),.48);render('mouth-profile')
for o in hidden:o.hide_render=False
camera((.1,0,0),(4,-.35,.12),1.3);render('neutral')
# Check the evaluated subdivided head through the existing demo, not just cage coordinates.
first=None;maxstep=0;last=None
for f in range(1,241):
 s.frame_set(f);ev=h.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();a=np.array([v.co[:] for v in me.vertices]);ev.to_mesh_clear();assert np.isfinite(a).all()
 if first is None:first=a.copy()
 if last is not None:maxstep=max(maxstep,float(np.linalg.norm(a-last,axis=1).max()))
 last=a
assert np.abs(first-last).max()<1e-7
s.frame_set(1)
report=json.loads((O/'correction-report.json').read_text());report['surface_finish']={'type':'non-destructive subdivision','level':1,'evaluated_head_frames':240,'loop_max_difference':float(np.abs(first-last).max()),'max_frame_displacement':maxstep}
(O/'correction-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.region_3d.view_location=(.14,0,-.015);sp.region_3d.view_rotation=c.rotation_euler.to_quaternion();sp.region_3d.view_distance=1.15;sp.region_3d.view_perspective='ORTHO'
   sp.overlay.show_overlays=False
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
print('FINAL_BLEND_SAVED',flush=True)
# Actual Blender-rendered blink, front and three-quarter inspection.
frames=O/'blink_frames';frames.mkdir(exist_ok=True)
s.render.resolution_x=512;s.render.resolution_y=512;s.cycles.samples=8
for o in hidden:o.hide_render=True
for i in range(40):
 phase=i%20;time=12+12*(phase/19)
 s.frame_set(int(time),subframe=time-int(time))
 camera((.20,-.149,.07),(4,-.4,0) if i<20 else (1.3,-4,.08),.34)
 s.render.filepath=str(frames/(f'{i:03d}.png'));bpy.ops.render.render(write_still=True)
print('BLINK_FRAMES_DONE',flush=True)
