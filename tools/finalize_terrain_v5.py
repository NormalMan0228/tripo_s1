from pathlib import Path
import json,shutil,re
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v5'
LAB=ROOT/'labs/terrain_lab'
volumes=json.loads((OUT/'water_volume_verification.json').read_text())
assert len(volumes)==8
assert all(item['signed_volume_m3']>0 and item['nonmanifold_edges']==0 and item['inconsistent_edge_orientation']==0 for item in volumes.values())
terrain=json.loads((OUT/'verification.json').read_text())
assert terrain['all_five_islands_grounded'] and terrain['relief_pass']
logs=list(OUT.glob('*_final.log'))+[OUT/'import.log',OUT/'audit.log']
for path in logs:
    text=path.read_text(encoding='utf-8',errors='replace')
    assert not re.search(r'(SCRIPT ERROR|SHADER ERROR|ERROR:|Parse Error|AssertionError)',text),path
result={'closed_water_volumes':len(volumes),'all_five_islands_grounded':True,'runtime_errors':0,'animated_regions':{},'views':{},'performance':{}}
for name,regions in {
    'waterfall_godot':{'falling_water':[.44,.36,.61,.64],'impact':[.43,.62,.62,.75]},
    'waterfall_side_godot':{'falling_water':[.41,.30,.61,.70]},
    'terrain_scale_godot':{'shore_surf':[.26,.89,.74,.98]},
}.items():
    before=np.array(Image.open(OUT/(name+'.png')).convert('RGB'),dtype=float)
    after=np.array(Image.open(OUT/(name+'_after_2s.png')).convert('RGB'),dtype=float)
    for region,coords in regions.items():
        h,w=before.shape[:2]
        x0,y0,x1,y1=[int(value*(w if i%2==0 else h)) for i,value in enumerate(coords)]
        delta=np.abs(before[y0:y1,x0:x1]-after[y0:y1,x0:x1])
        changed=(delta.max(axis=2)>4).mean()
        assert changed>.08,(name,region,changed)
        result['animated_regions'][name+'/'+region]={'time_between_captures_s':2.0,'region_pixels':[x0,y0,x1,y1],'mean_rgb_delta_0_255':float(delta.mean()),'pixels_changed_above_4':float(changed)}
for name in ['waterfall','waterfall_side','headland_back','terrain_scale','terrain','terrain_camera','terrain_camera_perspective']:
    image_path=OUT/(name+'_godot.png')
    assert image_path.exists(),image_path
    result['views'][name]=list(Image.open(image_path).size)
for path in sorted(OUT.glob('*_performance.json')):
    performance=json.loads(path.read_text())
    capture=path.with_name(path.name.replace('_performance.json','.png'))
    if capture.exists():performance['captured_frame_size_pixels']=list(Image.open(capture).size)
    result['performance'][path.stem]=performance
(OUT/'visual_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
manifest=json.loads((OUT/'manifest.json').read_text())
manifest['details']=['contour-conforming coast','smoothly joined headland height field','continuous height material bands','closed gravity-curved waterfall volume','seven rounded stream volumes','travel-time flow animation','local current field','physical shoreline distance surf','seamless isotropic foam and circular bubbles','tiled surface detail','extended ocean']
manifest['texture_resolution'].update(shore_distance=2048,organic_foam=1024,headland_normals=768)
manifest['waterfall'].update(spray_count=112,mist_count=64,volume_audit_pass=True)
manifest['verification']='visual_verification.json'
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for path in LAB.glob('*.gdshader'):shutil.copy2(path,OUT/path.name)
shutil.copy2(LAB/'terrain.gd',OUT/'terrain_runtime.gd')
print('TERRAIN_V5_VERIFIED',json.dumps(result),flush=True)
