"""Validate one review package without changing any prior approval."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from PIL import Image
from archipelago_queue import assert_authorized, locked_queue

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/maps/archipelago_objects_v1'
parser = argparse.ArgumentParser()
parser.add_argument('--asset',required=True)
args = parser.parse_args()
queue_path = BASE/'queue.json'
queue = json.loads(queue_path.read_text(encoding='utf-8'))
index = next(i for i,item in enumerate(queue['items']) if item['id']==args.asset)
item = queue['items'][index]
assert_authorized(queue,args.asset)
OUT = BASE/item['id']
stem = item['id'].split('_',1)[1]
logs=['blender_prepare.log','godot_import.log','godot_capture.log']
logs += [p.name for p in OUT.glob('blender_*repair.log')]
for name in logs:
    log = (OUT/name).read_text(encoding='utf-8',errors='replace')
    assert not re.search(r'SCRIPT ERROR|SHADER ERROR|ERROR:|Parse Error|Traceback|\w+(?:Error|Exception):',log),name
assert 'OBJECT_REVIEW_CAPTURE_COMPLETE' in (OUT/'godot_capture.log').read_text(encoding='utf-8')
mesh = json.loads((OUT/'mesh_verification.json').read_text(encoding='utf-8'))
api = json.loads((OUT/'generation-result.json').read_text(encoding='utf-8'))
assert api['status']=='success' and mesh['uv_available']
assert abs(mesh['dimensions_m'][2]-item['target_height_m'])<.01
assert any(texture['size']==[8192,8192] for texture in mesh['textures'])
blob = (OUT/(stem+'.glb')).read_bytes()
assert blob[:4]==b'glTF' and struct.unpack_from('<I',blob,8)[0]==len(blob)
doc_length = struct.unpack_from('<I',blob,12)[0]
doc = json.loads(blob[20:20+doc_length])
assert doc['asset']['version']=='2.0'
assert all('bufferView' in image and 'uri' not in image for image in doc['images'])
views = {}
for angle in ['front','back','side','entrance']:
    name = stem+'_'+angle
    with Image.open(OUT/(name+'.png')) as image:
        assert image.size==(1152,800)
        views[name] = list(image.size)
report = {'asset':item['id'],'review_status':'awaiting_user','review_camera_version':2,'views':views,
          'runtime_errors':0,'credits_consumed':api['credits_consumed'],
          'height_m':item['target_height_m'],'character_reference_height_m':1.7,
          'base_color_texture_size':[8192,8192],'embedded_pbr_textures':True,
          'source_sha256':hashlib.sha256((OUT/'tripo-original.glb').read_bytes()).hexdigest(),
          'local_repairs':mesh['local_repairs'],'review_batch':queue.get('active_batch',{}).get('id'),
          'interior_authored':False}
(OUT/'review_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
with locked_queue() as latest:
    entry=next(entry for entry in latest['items'] if entry['id']==args.asset)
    entry['review_status']='awaiting_user'
    entry['review_package']=str(OUT.relative_to(ROOT)).replace('\\','/')
print('OBJECT_REVIEW_READY',json.dumps(report),flush=True)
