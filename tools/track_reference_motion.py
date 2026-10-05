"""Extract measured pose landmarks from the three existing Scenario videos.

MediaPipe Heavy runs locally. Raw predictions and overlays are retained so the
retargeting result is traceable to each input, rather than relabelled presets.
"""
from pathlib import Path
import json
import hashlib
import cv2
import mediapipe as mp
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/production-lab-20261003/videos'
OUT = ROOT / 'artifacts/video-motion-20261003'
OUT.mkdir(exist_ok=True)
MODEL = ROOT / '.tools/motion-models/pose_landmarker_heavy.task'
CONNECTIONS = [(11,12),(11,23),(12,24),(23,24),(11,13),(13,15),(12,14),(14,16),
               (23,25),(25,27),(27,29),(29,31),(24,26),(26,28),(28,30),(30,32)]

for name in ('seedance2','pixverse6','kling3'):
    target = OUT / name
    target.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(str(SOURCE / (name + '.mp4')))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        min_pose_detection_confidence=.35, min_pose_presence_confidence=.35,
        min_tracking_confidence=.35)
    frames=[]
    with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
        i=0
        while True:
            ok,bgr=cap.read()
            if not ok:break
            rgb = cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
            # Reduce input size without changing the reference aspect ratio.
            if height>1280:
                rgb=cv2.resize(rgb,(round(width*1280/height),1280))
            result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),round(i/fps*1000))
            item={'time_s':i/fps,'image':None,'world':None}
            if result.pose_landmarks:
                item['image']=[[p.x,p.y,p.z,p.visibility,p.presence] for p in result.pose_landmarks[0]]
                item['world']=[[p.x,p.y,p.z,p.visibility] for p in result.pose_world_landmarks[0]]
            frames.append(item)
            if i%12==0:
                overlay=bgr.copy()
                if item['image']:
                    points=item['image']
                    for a,b in CONNECTIONS:
                        color=(80,230,80) if min(points[a][3],points[b][3])>.5 else (0,150,255)
                        cv2.line(overlay,(round(points[a][0]*width),round(points[a][1]*height)),
                                 (round(points[b][0]*width),round(points[b][1]*height)),color,4)
                    for n in (11,12,13,14,15,16,23,24,25,26,27,28):
                        x,y=round(points[n][0]*width),round(points[n][1]*height)
                        cv2.circle(overlay,(x,y),6,(255,80,80),-1)
                        cv2.putText(overlay,str(n),(x+7,y),cv2.FONT_HERSHEY_SIMPLEX,.5,(30,30,30),2)
                cv2.imwrite(str(target/f'track-{i:03}.jpg'),overlay)
            i+=1
    cap.release()
    valid=sum(f['image'] is not None for f in frames)
    report={'source_video':str(SOURCE/(name+'.mp4')),'source_sha256':hashlib.sha256((SOURCE/(name+'.mp4')).read_bytes()).hexdigest(),
            'pose_model':'MediaPipe Pose Landmarker Heavy float16','pose_model_sha256':hashlib.sha256(MODEL.read_bytes()).hexdigest(),
            'mediapipe_version':mp.__version__,'fps':fps,'width':width,'height':height,
            'duration_s':len(frames)/fps,'frame_count':len(frames),'detected_frames':valid,
            'frames':frames,'provider_calls':0}
    (target/'landmarks-raw.json').write_text(json.dumps(report),encoding='utf-8')
    print('TRACKED',name,valid,len(frames),flush=True)
