"""Keep source PNG resolution, use high quality GPU block compression in Godot."""
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'labs/terrain_lab'
OUT=ROOT/'art/maps/archipelago_performance_v1'
OUT.mkdir(exist_ok=True,parents=True)
report=[]
# Vector fields and signed distance masks keep their exact data values.
data_maps={'current_field','coast_field','shore_distance','headland_normals'}
for path in (LAB/'assets').rglob('*.png.import'):
    if any(name in path.name for name in data_maps):
        continue
    source=path.read_text(encoding='utf-8')
    edited=re.sub(r'(?m)^compress/mode=.*$', 'compress/mode=2',source)
    edited=re.sub(r'(?m)^compress/high_quality=.*$', 'compress/high_quality=true',edited)
    # Keep RGB for custom shaders which sample the full normal texture.
    edited=re.sub(r'(?m)^compress/normal_map=.*$', 'compress/normal_map=2',edited)
    edited=re.sub(r'(?m)^mipmaps/generate=.*$', 'mipmaps/generate=true',edited)
    if edited != source:
        report.append({'file':str(path.relative_to(ROOT)),'previous':source})
        path.write_text(edited,encoding='utf-8')
record=OUT/'texture_import_changes.json'
if not record.exists():
    record.write_text(json.dumps({'resolution_changed':False,'source_images_changed':False,'gpu_compression':'BPTC high quality','changes':report},indent=2),encoding='utf-8')
print('TEXTURE_GPU_COMPRESSION_CONFIGURED count=',len(report),'resolution_unchanged=True')
