"""MediaPipe Face Landmarker on one image (runs in .tools/landmark-venv). Output: [[u, v], ...] normalised, or []."""
import sys, json
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
from PIL import Image

img, model, out = sys.argv[1:4]
det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
    base_options=mpt.BaseOptions(model_asset_path=model), num_faces=1,
    min_face_detection_confidence=0.2, min_face_presence_confidence=0.2))
im = Image.open(img).convert('RGB')
res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(im)))
json.dump([[p.x, p.y] for p in res.face_landmarks[0]] if res.face_landmarks else [], open(out, 'w'))
