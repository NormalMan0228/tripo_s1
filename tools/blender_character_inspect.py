"""Run in Blender background; inspect and render the imported character."""
import bpy,json,sys,math
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parents[1]/'artifacts/characters/explorer-b-v1'
stage=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'rig'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/(stage+'-original.glb')))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
points=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
report={'bounds':[list(lo),list(hi)],'meshes':[{'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons),'materials':[m.name for m in o.data.materials]} for o in meshes],'actions':[a.name for a in bpy.data.actions],'rigs':[]}
for o in bpy.context.scene.objects:
 if o.type=='ARMATURE':report['rigs'].append({'name':o.name,'matrix':[list(row) for row in o.matrix_world],'bones':[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(b.head_local),'tail':list(b.tail_local)} for b in o.data.bones]})
(OUT/(stage+'-inspection.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('INSPECTION',json.dumps(report))
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 scene.cycles.device='GPU'
except:pass
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.world.color=(.25,.25,.25)
target=(lo+hi)*.5;h=hi.z-lo.z
for name,offset,power,size in [('Key',(2,-3,4),900,4),('Fill',(-3,-1,2),650,3),('Rim',(1,3,3),1100,3)]:
 bpy.ops.object.light_add(type='AREA',location=target+Vector(offset)*h/2)
 light=bpy.context.object;light.name=name;light.data.energy=power;light.data.shape='DISK';light.data.size=size
 light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=max(h,hi.x-lo.x)*1.15
for i,offset in enumerate([(0,-4,1),(4,0,1),(0,4,1),(-4,0,1)]):
 cam.location=target+Vector(offset)*h;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
 scene.render.filepath=str(OUT/(stage+'-view-'+str(i)+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(stage+'-inspection.blend')))
