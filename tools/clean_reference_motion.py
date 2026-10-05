"""Smooth measured landmarks and derive separate sagittal motion channels."""
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import gaussian_filter1d, median_filter
from scipy.interpolate import PchipInterpolator

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/video-motion-20261003'

for name in ('seedance2','pixverse6','kling3'):
    data=json.loads((OUT/name/'landmarks-raw.json').read_text())
    fps=data['fps']; times=np.arange(data['frame_count'])/fps
    points=np.array([f['image'] for f in data['frames']])
    xy=points[:,:,:2].copy();xy[:,:,0]*=data['width']/data['height']
    # Remove isolated detector spikes; retain measured timing and stride differences.
    xy=median_filter(xy,size=(3,1,1),mode='nearest')
    xy=gaussian_filter1d(xy,sigma=1.15,axis=0,mode='nearest')
    def direction(a,b):
        v=xy[:,b]-xy[:,a]
        angle=np.unwrap(np.arctan2(-v[:,1],v[:,0]))
        return gaussian_filter1d(angle,1.4)
    channels={}
    for side,shoulder,elbow,wrist,hip,knee,ankle,heel,toe in (
        ('L',11,13,15,23,25,27,29,31),('R',12,14,16,24,26,28,30,32)):
        channels[side+'_thigh']=direction(hip,knee)
        channels[side+'_calf']=direction(knee,ankle)
        channels[side+'_upperarm']=direction(shoulder,elbow)
        channels[side+'_forearm']=direction(elbow,wrist)
        foot=direction(heel,toe)
        neutral=np.median(np.r_[foot[:10],foot[-10:]])
        channels[side+'_foot_pitch']=np.clip(foot-neutral,np.radians(-35),np.radians(35))
    hip=(xy[:,23]+xy[:,24])*.5;shoulder=(xy[:,11]+xy[:,12])*.5
    lean=np.arctan2(shoulder[:,0]-hip[:,0],hip[:,1]-shoulder[:,1])
    channels['torso_pitch']=np.clip(gaussian_filter1d(lean,2),np.radians(-12),np.radians(12))
    # Preserve subtle head tilt only; no new face geometry or facial animation.
    ear=(xy[:,7]+xy[:,8])*.5
    head=np.arctan2(ear[:,0]-shoulder[:,0],shoulder[:,1]-ear[:,1])
    channels['head_pitch']=np.clip(gaussian_filter1d(head-np.median(head[:10]),2),-.09,.09)
    # Stance observations are retained as evidence and for loop selection.
    ankles=xy[:,[27,28],:]
    ankle_gap=ankles[:,0,0]-ankles[:,1,0]
    from scipy.signal import find_peaks
    peaks,_=find_peaks(ankle_gap,prominence=.028,distance=round(fps*.5))
    troughs,_=find_peaks(-ankle_gap,prominence=.028,distance=round(fps*.5))
    # Same-foot stride candidates, not an arbitrary repeated procedural cycle.
    candidates=[(a,b) for extrema in (peaks,troughs) for a,b in zip(extrema[:-1],extrema[1:])
                if .7<(b-a)/fps<3.5]
    if candidates:
        # Avoid startup/stop sections and prefer visibly developed steps.
        start,end=max(candidates,key=lambda ab:float(np.ptp(ankle_gap[ab[0]:ab[1]+1])))
        loop={'start_s':float(times[start]),'end_s':float(times[end]),'source':'measured same-foot extrema'}
    else:
        loop=None
    result={'source':name,'source_sha256':data['source_sha256'],'pose_model':data['pose_model'],
            'mediapipe_version':data['mediapipe_version'],'fps':fps,'times_s':times.tolist(),
            'duration_s':float(times[-1]),'channels':{k:v.tolist() for k,v in channels.items()},
            'loop_segment':loop,'all_frames_detected':data['detected_frames']==data['frame_count'],
            'mean_visibility':{str(i):float(points[:,i,3].mean()) for i in [13,14,15,16,25,26,27,28]},
            'method':'Measured sagittal landmark directions; confidence-aware review, temporal filtering, fixed depth lanes; Blender FK and sole correction',
            'limitations':['Single side-view does not recover precise depth','Occluded joints are estimated','No finger or facial capture'],
            'provider_calls':0}
    (OUT/name/'motion-channels.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('CHANNELS',name,'loop',loop,'ankle_gap',float(np.ptp(ankle_gap)),flush=True)
