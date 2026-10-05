"""Publish verified map placement while preserving the fifteen-model review gate."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from PIL import Image
from archipelago_queue import locked_queue

ROOT=Path(__file__).resolve().parents[1]
runtime_manifest=json.loads((ROOT/'labs/terrain_lab/environment_layout.json').read_text(encoding='utf-8'))
OUT=ROOT/runtime_manifest.get('output_directory','art/maps/archipelago_environment_v1')
layout=json.loads((OUT/'environment_layout.json').read_text(encoding='utf-8'))
report=json.loads((OUT/'environment_verification.json').read_text(encoding='utf-8'))
preservation=json.loads((OUT/'source_preservation_verification.json').read_text(encoding='utf-8'))
rocks=json.loads((OUT/'rock_clearance_verification.json').read_text(encoding='utf-8'))
assert report['passed'] and report['graph_connected']
assert report['models']==len(layout['models']) and report['prop_instances']==len(layout['instances'])
assert len(report['bridges'])==4 and all(b['character_walk']['passed'] for b in report['bridges'])
assert preservation['passed'] and preservation['models']==len(layout['models'])
assert rocks['all_ground_water_normals_uv_and_texture_bytes_preserved']
log=(OUT/'final_validation.log').read_text(encoding='utf-8',errors='replace')
assert not re.search(r'SCRIPT ERROR|SHADER ERROR|ERROR:|Parse Error|Traceback',log)
views=['overview','northwest','northeast','southwest','southeast','bridge_north','bridge_center','bridge_east','bridge_lighthouse','camp']
for name in views:
    assert 'ENVIRONMENT_CAPTURE '+name in log
    assert Image.open(OUT/(name+'.png')).size==(1440,1000)
counts=Counter(i['id'] for i in layout['instances'])
counts.update(i['id'] for i in layout['bridges'])
with locked_queue() as queue:
    batch=queue['active_batch']
    assert batch['id']==layout['review_batch'] and batch['status']=='awaiting_user'
    for item in queue['items']:
        if item['id'] in batch['assets']:
            item['placement_status']='preview_placed'
            item['placement_count']=counts[item['id']]
            item['placement_package']=str(OUT.relative_to(ROOT)).replace('\\','/')
    batch['placement_verified']=True
    batch['all_five_islands_connected']=True
    batch['preview_completed_at']=datetime.now(timezone.utc).isoformat()
    batch['remaining_planned_models']=layout['reserved_remaining_models']
print('ENVIRONMENT_PREVIEW_VERIFIED bridges=4 models=',len(layout['models']),'props=',len(layout['instances']),'all_character_crossings_passed=True awaiting_user=True')
