"""Render immutable HD meshes and save individually selectable Blender scenes."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/characters/explorer_b_hd_restart_v1'
parser = argparse.ArgumentParser()
parser.add_argument('--parts', nargs='+', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])

for part in args.parts:
    folder = BASE/part
    source = folder/'model.glb'
    if not source.exists():
        raise RuntimeError('Source has not downloaded: '+part)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type=='MESH']
    points = [o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    center, radius = (lo+hi)/2, max(hi-lo)
    report = {'part': part, 'source': str(source.relative_to(ROOT)),
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'model': 'v3.1-20260211', 'mode': 'HD_Ultra', 'texture': False,
              'geometry_edited': False, 'assembled': False, 'rigged': False,
              'mesh_objects': [], 'bounds': {'min':list(lo),'max':list(hi)},
              'geometry_review': 'awaiting_user', 'pair_and_fit_review': 'pending'}
    clay = bpy.data.materials.new('HD_Geometry_Review_Clay')
    clay.use_nodes = True
    bsdf = clay.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (.42,.46,.51,1)
    bsdf.inputs['Roughness'].default_value = .7
    for i,obj in enumerate(meshes):
        obj.name = f'HD_{part}_{i+1:02d}'
        mesh = obj.data
        mesh.calc_loop_triangles()
        report['mesh_objects'].append({'name':obj.name,'vertices':len(mesh.vertices),
                                      'polygons':len(mesh.polygons),'triangles':len(mesh.loop_triangles),
                                      'polygon_sides':dict(Counter(len(p.vertices) for p in mesh.polygons)),
                                      'uv_layers':len(mesh.uv_layers)})
        mesh.materials.clear()
        mesh.materials.append(clay)
        obj.hide_select = False
        obj.hide_viewport = False
        obj.hide_set(False)
    report['vertices'] = sum(o['vertices'] for o in report['mesh_objects'])
    report['triangles'] = sum(o['triangles'] for o in report['mesh_objects'])
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type='CUDA'
        prefs.get_devices()
        for device in prefs.devices:
            device.use = device.type=='CUDA'
        if any(d.type=='CUDA' for d in prefs.devices):
            scene.cycles.device='GPU'
    except Exception:
        pass
    world=bpy.data.worlds.new('HD Review World')
    world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.83,.88,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.45
    scene.world=world
    studio=bpy.data.collections.new('Review Studio')
    scene.collection.children.link(studio)
    for name,offset,power,size in [('Key',(3,-3,4),700,3),('Fill',(2,3,1),280,3),('Rim',(-3,0,3),500,2)]:
        data=bpy.data.lights.new(name,'AREA')
        data.energy, data.size=power*radius*radius,size*radius
        obj=bpy.data.objects.new(name,data)
        studio.objects.link(obj)
        obj.location=center+Vector(offset)*radius
        obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
        obj.hide_select=True
        obj.hide_set(True)
    camera=bpy.data.objects.new('HD Review Camera',bpy.data.cameras.new('HD Review Camera'))
    studio.objects.link(camera)
    camera.hide_select=True
    camera.hide_set(True)
    camera.data.type='ORTHO'
    camera.data.clip_start=radius/1000
    camera.data.clip_end=radius*100
    scene.camera=camera
    scene.render.resolution_x=1000
    scene.render.resolution_y=1400 if part=='fullbody' else 1000
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    for view,offset in [('front',(4,0,0)),('angle',(4,-2,.6)),('side',(0,-4,0)),('back',(-4,0,0))]:
        camera.location=center+Vector(offset)*radius
        camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        basis=camera.rotation_euler.to_matrix().transposed()
        projected=[basis@(p-center) for p in points]
        w=max(p.x for p in projected)-min(p.x for p in projected)
        h=max(p.y for p in projected)-min(p.y for p in projected)
        camera.data.ortho_scale=radius
        frame=camera.data.view_frame(scene=scene)
        fw=max(p.x for p in frame)-min(p.x for p in frame)
        fh=max(p.y for p in frame)-min(p.y for p in frame)
        camera.data.ortho_scale*=max(w/fw,h/fh)*1.18
        scene.render.filepath=str(folder/f'preview-{view}.png')
        bpy.ops.render.render(write_still=True)
        print('HD_RENDERED',part,view,flush=True)
    camera.location=center+Vector((4,-2,.6))*radius
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.select_all(action='DESELECT')
    meshes[0].select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.shading.type='MATERIAL'
                area.spaces.active.region_3d.view_location=center
                area.spaces.active.region_3d.view_distance=radius*2
                area.spaces.active.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/f'{part}_HD.blend'))
    (folder/'mesh-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('HD_SOURCE_READY',part,report['triangles'],flush=True)
