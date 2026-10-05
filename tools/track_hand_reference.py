"""Local hand landmark experiment on the fictional generated open-hand reference."""
import json, urllib.request
import numpy as np
from PIL import Image
from pathlib import Path
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
ROOT=Path(__file__).resolve().parents[1];MODELS=ROOT/'.tools/mocap-models';MODELS.mkdir(parents=True,exist_ok=True)
model=MODELS/'hand_landmarker.task'
if not model.exists():
 urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task',model)
options=vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(model)),num_hands=1,min_hand_detection_confidence=.35,min_hand_presence_confidence=.35)
with vision.HandLandmarker.create_from_options(options) as detector:
 result=detector.detect(mp.Image.create_from_file(str(ROOT/'art/references/character_detail_20261003/hand-open.png')))
 if not result.hand_landmarks:raise SystemExit('No hand detected; do not invent joint positions')
 output={'points':[[p.x,p.y,p.z] for p in result.hand_landmarks[0]],'handedness':[{'label':c.category_name,'score':c.score} for c in result.handedness[0]],'input':'art/references/character_detail_20261003/hand-open.png','interpretation':'2D joints detected; depth and mesh fitting still need inspection'}
 arr=np.asarray(Image.open(ROOT/output['input']).convert('RGB'),dtype=np.int16)
 mask=(arr[:,:,0]>arr[:,:,1]+12)&(arr[:,:,1]>arr[:,:,2]+10)
 yy,xx=np.nonzero(mask);output['skin_bbox_px']=[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())];output['image_size']=[arr.shape[1],arr.shape[0]]
 path=ROOT/'artifacts/detail-map-20261003/character/hand-landmarks.json';path.write_text(json.dumps(output,indent=2));print('HAND_LANDMARKS',len(output['points']),output['handedness'])
