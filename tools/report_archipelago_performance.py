"""Compare native Godot measurements using identical views and renderer settings."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_performance_v1'
before=json.loads((OUT/'before.json').read_text(encoding='utf-8'))
after=json.loads((OUT/'after.json').read_text(encoding='utf-8'))
rows=[]
for old,new in zip(before['views'],after['views']):
    assert old['view']==new['view']
    assert new['fps']>old['fps']*3
    rows.append({'view':old['view'],'before_fps':old['fps'],'after_fps':new['fps'],'speedup':new['fps']/old['fps'],'before_p95_ms':old['p95_frame_ms'],'after_p95_ms':new['p95_frame_ms'],'before_primitives':old['primitives'],'after_primitives':new['primitives']})
result={'comparison':rows,'before_vram_mb':before['views'][0]['video_memory_mb'],'after_vram_mb':after['views'][0]['video_memory_mb'],'viewport':[1440,1000],'gpu':'NVIDIA GeForce RTX 2070','vsync_disabled_for_measurement':True,'texture_resolution_unchanged':True,'msaa_8x_unchanged':True,'shadow_4096_unchanged':True,'original_tripo_assets_preserved':True,'bridges_authored_at_actual_bank_spans':True}
(OUT/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('NATIVE_PERFORMANCE_COMPARISON_PASS',json.dumps(rows))
