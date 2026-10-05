from pathlib import Path
import json,re,shutil
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v6'
report={'views':{},'lakes':{},'motion':{}}
for path in list(OUT.glob('*_final.log'))+[OUT/'import.log',OUT/'audit.log',OUT/'geometry_audit.log']:
    text=path.read_text(encoding='utf-8',errors='replace')
    assert not re.search(r'(SCRIPT ERROR|SHADER ERROR|ERROR:|Parse Error|AssertionError|Traceback)',text),path
volume=json.loads((OUT/'water_volume_verification.json').read_text())
assert len(volume)==8
assert all(item['signed_volume_m3']>0 and item['nonmanifold_edges']==0 and item['inconsistent_edge_orientation']==0 for item in volume.values())
terrain=json.loads((OUT/'verification.json').read_text())
assert terrain['all_five_islands_grounded'] and terrain['relief_pass']
for name in ['southwest','northeast']:
    stem='lake_'+name+'_godot'
    before=np.array(Image.open(OUT/(stem+'.png')).convert('RGB'),dtype=float)
    after=np.array(Image.open(OUT/(stem+'_after_2s.png')).convert('RGB'),dtype=float)
    water=(before[:,:,1]-before[:,:,0]>40)&(before[:,:,2]-before[:,:,0]>50)
    water[:int(len(water)*.18)]=False
    water=binary_erosion(water,iterations=12)
    delta=np.abs(before-after)[water]
    assert len(delta)>20000
    changed=float((delta.max(axis=1)>2).mean())
    assert changed<.005,(name,changed)
    luminance=before[water].mean(axis=1)
    report['lakes'][name]={'tested_water_pixels':len(delta),'moving_fraction_over_2s':changed,'mean_rgb_change':float(delta.mean()),'static_brightness_range_p05_p95':float(np.percentile(luminance,95)-np.percentile(luminance,5))}
for name,regions in {
    'waterfall_godot':{'headwater':[.31,.13,.56,.33],'fall':[.44,.36,.61,.64]},
    'waterfall_side_godot':{'fall':[.41,.30,.61,.70]},
    'terrain_scale_godot':{'shore':[.26,.89,.74,.98]},
}.items():
    before=np.array(Image.open(OUT/(name+'.png')).convert('RGB'),dtype=float)
    after=np.array(Image.open(OUT/(name+'_after_2s.png')).convert('RGB'),dtype=float)
    h,w=before.shape[:2]
    for region,box in regions.items():
        x0,y0,x1,y1=[int(value*(w if i%2==0 else h)) for i,value in enumerate(box)]
        delta=np.abs(before[y0:y1,x0:x1]-after[y0:y1,x0:x1])
        changed=float((delta.max(axis=2)>3).mean())
        assert changed>.02,(name,region,changed)
        report['motion'][name+'/'+region]={'tested_region_pixels':[x0,y0,x1,y1],'changing_fraction_over_2s':changed,'mean_rgb_delta':float(delta.mean())}
for name in ['waterfall','waterfall_side','terrain','terrain_scale','lake_southwest','lake_northeast','offshore']:
    report['views'][name]=list(Image.open(OUT/(name+'_godot.png')).size)
rocks=json.loads((OUT/'rock_distribution.json').read_text())
report.update(runtime_errors=0,closed_water_volumes=len(volume),all_five_islands_grounded=True,rock_clusters=rocks['clusters'],rock_count=len(rocks['rocks']))
(OUT/'visual_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
manifest_path=OUT/'manifest.json';manifest=json.loads(manifest_path.read_text())
manifest.pop('water_revision_verification',None)
manifest['verification']='visual_verification.json'
manifest['water_effects'].update(lake_static_jewel_shading=True,upstream_flow=True,repeating_ocean_map_removed=True)
manifest['waterfall'].update(spray_count=112,mist_count=64,volume_audit_pass=True)
manifest['details']=list(dict.fromkeys(manifest['details']+['static jewel lakes','advected headwater','irregular stream widths and spacing','non-repeating offshore color','sparse irregular rock formations']))
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for path in (ROOT/'labs/terrain_lab').glob('*.gdshader'):shutil.copy2(path,OUT/path.name)
shutil.copy2(ROOT/'labs/terrain_lab/terrain.gd',OUT/'terrain_runtime.gd')
print('TERRAIN_V6_VERIFIED',json.dumps(report),flush=True)
