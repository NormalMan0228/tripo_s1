import bpy, json, struct, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'art/characters/explorer_b_face_rig_manual_v1'
path = out / 'explorer_manual_face_rig.glb'
if '--' in sys.argv:
    path=Path(sys.argv[sys.argv.index('--')+1]);out=path.parent
raw = path.read_bytes()
length, kind = struct.unpack_from('<II', raw, 12)
doc = json.loads(raw[20:20+length])
assert kind == 0x4E4F534A
assert doc.get('skins') and doc.get('animations')
assert len(doc['animations']) == 1, 'Face demo must be one synchronized clip'
paths = sorted({c['target']['path'] for a in doc['animations'] for c in a['channels']})
assert 'weights' in paths and 'rotation' in paths
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = 24
bpy.ops.import_scene.gltf(filepath=str(path))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
keys = [o.data.shape_keys for o in meshes if o.data.shape_keys]
assert keys
states = []
for f in (1,18,98,124,240):
    bpy.context.scene.frame_set(f)
    states.append([round(k.value,6) for sk in keys for k in sk.key_blocks[1:]])
assert states[0] != states[1], 'Imported blink does not animate'
assert states[0] != states[2], 'Imported jaw does not animate'
result = {'glb_bytes': len(raw), 'skins': len(doc['skins']), 'animations': len(doc['animations']),
          'animation_target_paths':paths, 'imported_meshes':len(meshes), 'morph_meshes':len(keys),
          'imported_blink_changes':states[0]!=states[1], 'imported_jaw_changes':states[0]!=states[2],
          'scope':'Blender import and morph sampling; Godot playback not tested this turn.'}
(out/'export-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result),flush=True)
