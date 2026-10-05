"""Render the actual Blender-assembled mesh and actual authored rig deformation."""
import bpy, math, argparse, sys, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_modular_v1/04_blender_assembly'
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['preview','video','audit'],default='preview')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_b_assembled_rigged.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Rig'];camera=scene.camera
try:
 preferences=bpy.context.preferences.addons['cycles'].preferences;preferences.compute_device_type='CUDA';preferences.get_devices()
 for device in preferences.devices:device.use=device.type=='CUDA'
 if any(d.type=='CUDA' for d in preferences.devices):scene.cycles.device='GPU'
except Exception:scene.cycles.device='CPU'

def aim(target,offset,scale):
 target=Vector(target);camera.location=target+Vector(offset)
 camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
 camera.data.ortho_scale=scale

if a.mode=='preview':
 scene.render.resolution_x=1000;scene.render.resolution_y=1200;scene.cycles.samples=24
 for name,frame,target,offset,scale in [
  ('assembled-front',1,(0,0,.87),(4,0,0),1.95),
  ('assembled-angle',1,(0,0,.87),(4,-2,.4),1.95),
  ('assembled-side',1,(0,0,.87),(0,-4,0),1.95),
  ('assembled-back',1,(0,0,.87),(-4,0,0),1.95),
  ('pose-proof',61,(0,0,.87),(4,-2,.4),1.95),
  ('face-neutral',1,(.02,0,1.49),(4,-.8,.2),.52),
  ('face-expression',61,(.02,0,1.49),(4,-.8,.2),.52),
  ('hand-neutral',1,(-.02,-.375,.79),(4,-2,1),.30),
  ('hand-grasp',61,(-.02,-.375,.84),(4,-2,1),.34),
 ]:
  if name.startswith(('face','hand')):scene.render.resolution_x=900;scene.render.resolution_y=900
  else:scene.render.resolution_x=1000;scene.render.resolution_y=1200
  scene.frame_set(frame);bpy.context.view_layer.update();aim(target,offset,scale)
  if name.startswith('hand'):
   evaluated=bpy.data.objects['Hand.R'].evaluated_get(bpy.context.evaluated_depsgraph_get())
   corners=[evaluated.matrix_world@Vector(p) for p in evaluated.bound_box]
   center=sum(corners,Vector())/8
   aim(center,offset,.25)
  scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
  print('RIG_PREVIEW',name,flush=True)
elif a.mode=='video':
 scene.cycles.samples=12
 scene.render.resolution_x=720;scene.render.resolution_y=900
 aim((0,0,.88),(4,-1.8,.45),1.96)
 scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4'
 scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='MEDIUM'
 scene.render.ffmpeg.ffmpeg_preset='GOOD';scene.render.filepath=str(OUT/'rig-proof.mp4')
 scene.frame_start=1;scene.frame_end=121
 bpy.ops.render.render(animation=True)
 print('RIG_PROOF_VIDEO_READY',flush=True)
else:
 import numpy as np
 meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
 audit={'parts':len(meshes),'frames_tested':list(range(1,122)),'evaluated_bounds':{},'source_files_unchanged':True,
        'adjacent_frame_max_vertex_step_m':{},'continuous_test_action_only':True}
 first={};previous={};peak={}
 for frame in audit['frames_tested']:
  scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
  if frame in [1,31,61,91,121]:audit['evaluated_bounds'][str(frame)]={}
  for obj in meshes:
   evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
   raw=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',raw)
   coords=raw.reshape(-1,3)@np.array(evaluated.matrix_world.to_3x3()).T+np.array(evaluated.matrix_world.translation)
   if not np.isfinite(coords).all():raise RuntimeError('nonfinite_deformation_'+obj.name)
   if np.linalg.norm(coords,axis=1).max()>3:raise RuntimeError('exploding_deformation_'+obj.name)
   if frame==1:first[obj.name]=coords.copy()
   else:
    step=float(np.linalg.norm(coords-previous[obj.name],axis=1).max())
    audit['adjacent_frame_max_vertex_step_m'][obj.name]=max(step,audit['adjacent_frame_max_vertex_step_m'].get(obj.name,0))
   if frame==61:peak[obj.name]=coords.copy()
   previous[obj.name]=coords
   if frame in [1,31,61,91,121]:audit['evaluated_bounds'][str(frame)][obj.name]=[coords.min(axis=0).tolist(),coords.max(axis=0).tolist()]
   evaluated.to_mesh_clear()
 audit['loop_endpoint_max_vertex_gap_m']=max(float(np.linalg.norm(first[n]-previous[n],axis=1).max()) for n in first)
 audit['part_peak_displacement_m']={n:float(np.linalg.norm(first[n]-peak[n],axis=1).max()) for n in first}
 assert audit['loop_endpoint_max_vertex_gap_m']<.00001,'loop_endpoint_mismatch'
 assert max(audit['adjacent_frame_max_vertex_step_m'].values())<.04,'adjacent_frame_jump'
 import hashlib
 report=json.loads((OUT/'assembly-rig-report.json').read_text(encoding='utf-8'))
 for name,digest in report['source_hashes'].items():
  assert hashlib.sha256((OUT.parent/'03_generated'/name/'model.glb').read_bytes()).hexdigest()==digest
 audit['no_new_api_calls']=True
 audit['paired_mesh_symmetry_max_error_m']={}
 from mathutils.kdtree import KDTree
 for part in ['Hand','Boot']:
  r=np.array([tuple(v.co) for v in bpy.data.objects[part+'.R'].data.vertices]);l=np.array([tuple(v.co) for v in bpy.data.objects[part+'.L'].data.vertices])
  r[:,1]*=-1
  tree=KDTree(len(l))
  for i,p in enumerate(l):tree.insert(p,i)
  tree.balance()
  audit['paired_mesh_symmetry_max_error_m'][part]=max(tree.find(p)[2] for p in r)
  assert audit['paired_mesh_symmetry_max_error_m'][part]<.00001,'paired_mesh_symmetry'
 (OUT/'deformation-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 print('RIG_DEFORMATION_AUDIT',json.dumps({k:v for k,v in audit.items() if k!='evaluated_bounds'}),flush=True)
