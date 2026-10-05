"""Offline developer inspection: never submits a provider task."""
import bpy, json, sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/characters/explorer-b-v5'
source = Path(sys.argv[sys.argv.index('--')+1])
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
points = [o.matrix_world @ Vector(p) for o in meshes for p in o.bound_box]
lo = Vector([min(p[i] for p in points) for i in range(3)])
hi = Vector([max(p[i] for p in points) for i in range(3)])
rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
report = {'bounds': [list(lo), list(hi)], 'meshes': [
    {'name': o.name, 'vertices': len(o.data.vertices), 'faces': len(o.data.polygons),
     'triangles': sum(len(p.vertices)-2 for p in o.data.polygons),
     'uv_layers': len(o.data.uv_layers), 'materials': [m.name for m in o.data.materials]}
    for o in meshes], 'rigs': [
    {'name': o.name, 'bones': [{'name': b.name, 'head': list(b.head_local),
     'tail': list(b.tail_local), 'parent': b.parent.name if b.parent else None}
     for b in o.data.bones]} for o in rigs]}
(OUT / (source.stem + '-inspection.json')).write_text(json.dumps(report, indent=2))
scene = bpy.context.scene; scene.render.engine = 'CYCLES'; scene.cycles.samples = 16
scene.cycles.use_denoising = True
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='CUDA'; prefs.get_devices()
    for d in prefs.devices: d.use=d.type=='CUDA'
    scene.cycles.device='GPU'
except Exception: pass
scene.render.resolution_x=1000; scene.render.resolution_y=1000
scene.render.resolution_percentage=100; scene.view_settings.view_transform='AgX'
scene.world.use_nodes=True; scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.45,.47,.49,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.4
target=(lo+hi)*.5; h=hi.z-lo.z
bpy.ops.mesh.primitive_plane_add(size=30, location=(0,0,lo.z-.001))
m=bpy.data.materials.new('NeutralStage'); m.diffuse_color=(.4,.43,.44,1)
bpy.context.object.data.materials.append(m)
for at,power,size in [((2,-3,4),170,3),((-2,-1,3),90,3),((0,3,4),200,2)]:
    bpy.ops.object.light_add(type='AREA',location=target+Vector(at)*h)
    light=bpy.context.object; light.data.energy=power*h*h; light.data.size=size*h
    light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(); cam=bpy.context.object; scene.camera=cam
cam.data.type='ORTHO'; cam.data.ortho_scale=h*1.2
for name,offset in [('front',(0,-4,.12)),('side',(4,0,.12)),('back',(0,4,.12))]:
    cam.location=target+Vector(offset)*h
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(source.stem+'-'+name+'.png'))
    bpy.ops.render.render(write_still=True)
print('CHARACTER_INSPECTED', json.dumps({'meshes':report['meshes'],'bone_count':sum(len(r['bones']) for r in report['rigs'])}))
