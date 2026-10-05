"""Embed texture dependencies so editable art sources can move between computers."""
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
for name in ['village_art_20261003.blend','cottage_interior_20261003.blend','open_hand_rigged_20261003.blend','bob-hair_20261003.blend']:
 path=ROOT/'art/source'/name
 bpy.ops.wm.open_mainfile(filepath=str(path));bpy.ops.file.pack_all()
 missing=[image.name for image in bpy.data.images if image.source=='FILE' and image.has_data and not image.packed_file]
 if missing:raise RuntimeError('Unpacked dependencies: '+', '.join(missing))
 bpy.ops.wm.save_as_mainfile(filepath=str(path))
 print('PACKED_SOURCE',name)
