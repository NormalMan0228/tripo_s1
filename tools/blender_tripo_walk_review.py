"""Render the unedited Tripo preset on the same stage as the custom motion."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/characters/explorer-b-tripo-walk'
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'artifacts/characters/explorer-b-v1/explorer-b-custom.blend'))
for obj in list(bpy.data.objects):
    if obj.type == 'ARMATURE' or (obj.type == 'MESH' and obj.name != 'Review_Floor'):
        bpy.data.objects.remove(obj, do_unlink=True)
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action)
scene = bpy.context.scene
scene.render.fps = 24
bpy.ops.import_scene.gltf(filepath=str(OUT / 'tripo-walk-original.glb'))
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
actions = list(bpy.data.actions)
assert len(actions) >= 1
action = rig.animation_data.action or actions[0]
rig.animation_data.action = action
start, end = action.frame_range
scene.frame_start = int(start)
scene.frame_end = int(math.ceil(end)) - 1
assert scene.frame_end > scene.frame_start
meshes = [o for o in scene.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
assert meshes
root_bone = rig.pose.bones['Hip']
def root_position():
    return rig.matrix_world @ root_bone.matrix.translation
samples = []
poses = []
for frame in (start, start + (end-start)*.25, start + (end-start)*.5, start + (end-start)*.75):
    scene.frame_set(int(frame), subframe=frame % 1)
    graph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in meshes:
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
        evaluated.to_mesh_clear()
    assert all(math.isfinite(v) for p in points for v in p)
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    samples.append({'frame': frame, 'bounds': [low, high], 'root_world': list(root_position())})
    poses.append([v for b in rig.pose.bones for row in b.matrix for v in row])
assert max(abs(a-b) for a,b in zip(poses[0], poses[1])) > .01
report = {'source': 'Tripo API preset:biped:walk', 'animation_modified': False,
          'fps': 24, 'seconds': (end-start)/24, 'frame_range': [start,end],
          'actions': [a.name for a in actions], 'bones': len(rig.pose.bones),
          'finite_evaluated_vertices': True, 'pose_changes_verified': True,
          'sampled_bounds': samples,
          'preview_camera': 'Follows horizontal Hip motion; animation data is unmodified.',
          'note': 'animate_in_place=true was requested but forward displacement remains in the output.'}
(OUT / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.cycles.samples = 12
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'CUDA'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'CUDA'
    scene.cycles.device = 'GPU'
except Exception:
    pass
scene.frame_set(int(start), subframe=start % 1)
initial_root = root_position().copy()
camera_origin = scene.camera.location.copy()
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'tripo-walk-review.blend'))
frames = OUT / 'frames'
frames.mkdir(exist_ok=True)
for i in range(1, round(end-start) + 1):
    frame = start + i - 1
    scene.frame_set(int(frame), subframe=frame % 1)
    delta = root_position() - initial_root
    delta.z = 0
    scene.camera.location = camera_origin + delta
    scene.render.filepath = str(frames / f'{i:04d}.png')
    bpy.ops.render.render(write_still=True)
print('TRIPO_REVIEW_COMPLETE', json.dumps(report), flush=True)
