"""Reduce transferred high-poly normal noise; never change native geometry."""
import json
import argparse
import sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--part', choices=['fullbody', 'hair'], default='fullbody')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
part = args.part
FOLDER = ROOT / 'art/characters/explorer_b_fullbody_v2/06_textured_parts' / part
bpy.ops.wm.open_mainfile(filepath=str(FOLDER / f'{part}_textured.blend'))
obj = next(o for o in bpy.data.objects if o.type == 'MESH')
for material in obj.data.materials:
    for node in material.node_tree.nodes:
        if node.type == 'NORMAL_MAP':
            node.inputs['Strength'].default_value = 0
scene = bpy.context.scene
lo = Vector([min((obj.matrix_world@v.co)[i] for v in obj.data.vertices) for i in range(3)])
hi = Vector([max((obj.matrix_world@v.co)[i] for v in obj.data.vertices) for i in range(3)])
center, radius = (lo+hi)/2, max(hi-lo)
for view, offset in [('front',(4,0,0)),('angle',(4,-2,.5)),('back',(-4,0,0))]:
    camera = scene.camera
    camera.location = center+Vector(offset)*radius
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath = str(FOLDER / f'preview-{view}.png')
    bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(FOLDER / f'{part}_textured.blend'))
path = FOLDER / 'texture-transfer.json'
report = json.loads(path.read_text(encoding='utf-8'))
report['normal_strength'] = 0
report['normal_review_note'] = 'Transferred donor normal detail exaggerated mesh differences; normal map kept for editing but disabled on '+part+'.'
path.write_text(json.dumps(report, indent=2), encoding='utf-8')
