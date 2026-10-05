"""Check the first prop review package and leave it pending human approval."""
from pathlib import Path
import hashlib
import json
import re
import struct
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/maps/archipelago_objects_v1'
OUT = BASE / '01_cafe'
for name in ['blender_prepare.log','godot_import.log','godot_capture.log']:
    log = (OUT/name).read_text(encoding='utf-8',errors='replace')
    assert not re.search(r'SCRIPT ERROR|SHADER ERROR|ERROR:|Parse Error|Traceback',log),name
assert 'OBJECT_REVIEW_CAPTURE_COMPLETE' in (OUT/'godot_capture.log').read_text(encoding='utf-8')
mesh = json.loads((OUT/'mesh_verification.json').read_text(encoding='utf-8'))
api = json.loads((OUT/'generation-result.json').read_text(encoding='utf-8'))
assert api['status'] == 'success' and mesh['uv_available']
assert abs(mesh['dimensions_m'][2]-8.0) < .01
assert any(texture['size'] == [8192,8192] for texture in mesh['textures'])
blob = (OUT/'cafe.glb').read_bytes()
assert blob[:4] == b'glTF' and struct.unpack_from('<I',blob,8)[0] == len(blob)
doc_length = struct.unpack_from('<I',blob,12)[0]
doc = json.loads(blob[20:20+doc_length])
assert doc['asset']['version'] == '2.0'
assert all('bufferView' in image and 'uri' not in image for image in doc['images'])
views = {}
for name in ['cafe_front','cafe_back','cafe_side','cafe_entrance']:
    with Image.open(OUT/(name+'.png')) as image:
        assert image.size == (1152,800)
        views[name] = list(image.size)
report = {'asset':'01_cafe', 'review_status':'awaiting_user', 'views':views,
          'runtime_errors':0, 'credits_consumed':api['credits_consumed'],
          'height_m':8.0, 'character_reference_height_m':1.7,
          'base_color_texture_size':[8192,8192], 'embedded_pbr_textures':True,
          'source_sha256':hashlib.sha256((OUT/'tripo-original.glb').read_bytes()).hexdigest(),
          'local_repairs':mesh['local_repairs'],
          'next_object_submitted':False, 'interior_authored':False}
(OUT/'review_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
queue_path = BASE/'queue.json'
queue = json.loads(queue_path.read_text(encoding='utf-8'))
queue['items'][0]['review_status'] = 'awaiting_user'
queue['items'][0]['review_package'] = 'art/maps/archipelago_objects_v1/01_cafe'
assert all(item['review_status']=='planned' for item in queue['items'][1:])
queue_path.write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf-8')
print('FIRST_OBJECT_REVIEW_READY',json.dumps(report),flush=True)
