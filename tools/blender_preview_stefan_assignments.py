"""Study renders of example geometry; source Blend files are never saved."""
import bpy
import json
from mathutils import Vector
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/stefan-course-audit-20261004'
records=json.loads((out/'assignment-assets.json').read_text(encoding='utf8'))
targets=[('character','Sculpt.blend'),('character','Sculpt_complete.blend'),
         ('character','Uv_complete.blend'),('character','rig.blend'),('character','rig_complete.blend'),
         ('environment','lesson5.blend'),('environment','lesson5(complete).blend')]
dest=out/'previews';dest.mkdir(exist_ok=True)
for course,name in targets:
 rec=next(r for r in records if r['course']==course and Path(r['path']).name==name)
 bpy.ops.wm.open_mainfile(filepath=rec['path'],load_ui=False,use_scripts=False)
 scene=bpy.context.scene
 scene.frame_set(1)
 mesh=[o for o in scene.objects if o.type=='MESH' and o.name.lower() not in ['floor','shadows']]
 for o in scene.objects:
  if o.type=='MESH' and o not in mesh:o.hide_render=True
 pts=[o.matrix_world@Vector(v) for o in mesh for v in o.bound_box]
 lower=Vector([min(p[i] for p in pts) for i in range(3)])
 upper=Vector([max(p[i] for p in pts) for i in range(3)])
 center=(lower+upper)/2;size=max(upper-lower)
 data=bpy.data.cameras.new('CourseAuditCamera');cam=bpy.data.objects.new('CourseAuditCamera',data);scene.collection.objects.link(cam)
 direction=Vector((1,-2,1.1) if course=='environment' else (0.45,-2,0.4)).normalized()
 cam.location=center+direction*size*3
 cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
 data.type='ORTHO';data.ortho_scale=size*1.3;scene.camera=cam
 scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
 scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
 shading=scene.display.shading;shading.light='STUDIO';shading.color_type='MATERIAL';shading.show_shadows=True;shading.show_cavity=True;shading.cavity_type='BOTH';shading.background_type='WORLD'
 scene.world.color=(0.055,0.065,0.08)
 frames=[1,30,60,90] if name=='rig_complete.blend' else [1]
 for frame in frames:
  scene.frame_set(frame);scene.render.filepath=str(dest/f'{course}-{Path(name).stem}-{frame}.png')
  bpy.ops.render.render(write_still=True)
 print('PREVIEW',course,name,flush=True)
