from pathlib import Path
import json,re,shutil
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v5/water_revision_01'
report={'lakes':{},'coastal_regions':{}}
for name in ['southwest','northeast']:
    stem='lake_'+name+'_godot'
    before=np.array(Image.open(OUT/(stem+'.png')).convert('RGB'),dtype=float)
    after=np.array(Image.open(OUT/(stem+'_after_2s.png')).convert('RGB'),dtype=float)
    water=(before[:,:,1]-before[:,:,0]>40)&(before[:,:,2]-before[:,:,0]>50)
    water[:int(len(water)*.18)]=False
    water=binary_erosion(water,iterations=12)
    assert water.sum()>20000,(name,water.sum())
    delta=np.abs(before-after)[water]
    moving=float((delta.max(axis=1)>2).mean())
    report['lakes'][name]={'water_interior_pixels':int(water.sum()),'mean_rgb_change_over_2s':float(delta.mean()),'fraction_pixels_changed_above_2':moving}
    assert moving<.005,(name,moving)
paths=[OUT/'coast_regions_godot.png']+[OUT/('coast_regions_godot_%02ds.png'%i) for i in range(1,9)]
frames=np.stack([np.array(Image.open(path).convert('RGB'),dtype=float) for path in paths])
regions={
    'northwest_south':[220,313,400,333],
    'northeast_east':[1088,220,1118,312],
    'northeast_north':[760,92,930,118],
    'southwest_west':[55,470,92,580],
    'southwest_south':[280,677,430,709],
    'southeast_south':[820,675,975,708],
}
signals=[]
for name,box in regions.items():
    x0,y0,x1,y1=box
    pixels=frames[:,y0:y1,x0:x1]
    sea=((pixels[:,:,:,2]-pixels[:,:,:,0]).max(axis=0)>35)&((pixels[:,:,:,1]-pixels[:,:,:,0]).max(axis=0)>20)
    assert sea.sum()>30,(name,sea.sum())
    red=pixels[:,:,:,0][:,sea]
    signal=np.maximum(red-red.min(axis=0)-4,0).mean(axis=1)
    span=float(np.ptp(signal))
    report['coastal_regions'][name]={'sea_pixels':int(sea.sum()),'foam_brightness_samples_1s':signal.tolist(),'brightness_range':span,'strongest_sample_index':int(np.argmax(signal))}
    signals.append(signal)
correlations=np.corrcoef(np.array(signals))
report['regional_correlations']=correlations.tolist()
report['region_order']=list(regions)
active=[entry for entry in report['coastal_regions'].values() if entry['brightness_range']>1]
# Some sectors deliberately stay quiet during this short observation.
# Check independent timing among the visibly active sectors, rather than
# requiring every shoreline to produce a crest during the same eight seconds.
assert len(active)>=3,len(active)
peaks={entry['strongest_sample_index'] for entry in active}
report['distinct_peak_times']=sorted(peaks)
assert len(peaks)>=3,peaks
report['capture_times_s']=json.loads((OUT/'coast_regions_godot_timing.json').read_text())
for path in OUT.glob('*.log'):
    text=path.read_text(encoding='utf-8',errors='replace')
    assert not re.search(r'(SCRIPT ERROR|SHADER ERROR|ERROR:|Parse Error)',text),path
report['runtime_errors']=0
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
manifest_path=OUT.parent/'manifest.json'
manifest=json.loads(manifest_path.read_text())
manifest['runtime_revision']='5.1'
manifest['water_effects']={'interior_lake_waves':False,'interior_lake_foam':False,'coast_regional_timing':True,'coast_regional_strength':True}
manifest['water_revision_verification']='water_revision_01/verification.json'
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for name in ['terrain.gd','water_surface.gdshader']:
    shutil.copy2(ROOT/'labs/terrain_lab'/name,OUT/'after'/name)
print('WATER_REVISION_01_VERIFIED',json.dumps(report),flush=True)
