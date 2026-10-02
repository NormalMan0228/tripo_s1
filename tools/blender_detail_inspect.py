import bpy, json
from pathlib import Path
from mathutils import Vector, Matrix
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/characters/explorer-b-detailed-v2'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'artifacts/characters/explorer-b-v1/explorer-b-custom.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
rig.animation_data_clear()
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update()
mesh=bpy.data.objects['Explorer_B_SkinnedMesh']
data={'vertices':[list(mesh.matrix_world@v.co) for v in mesh.data.vertices], 'polygons':[list(p.vertices) for p in mesh.data.polygons], 'bones':{b.name:{'head':list(b.head_local),'tail':list(b.tail_local),'matrix':[list(r) for r in b.matrix_local]} for b in rig.data.bones}}
(OUT/'geometry.json').write_text(json.dumps(data),encoding='utf-8')
scene=bpy.context.scene;scene.cycles.samples=16;scene.render.resolution_x=1000;scene.render.resolution_y=1000
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU'
cam=scene.camera
for name,target,offset,scale in [('face_front',(0,0,.84),(3,0,0),.33),('hand_top',(0,.325,.70),(0,0,3),.15),('hand_front',(0,.325,.70),(3,0,0),.15),('rest',(0,0,.5),(3,-2,1),1.2)]:
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
 scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'inspection.blend'))
