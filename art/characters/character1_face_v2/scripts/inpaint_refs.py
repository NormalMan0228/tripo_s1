"""Image-space removal of brows from reference renders: mask = brow-card silhouette (occluded by the head),
dilated to cover the carved relief, then OpenCV inpainting (Telea) on the composited image."""
import cv2, numpy as np, sys, os
R = os.environ.get("REF_DIR", r"C:\lsm26\triphthonS1\art\references\character1_v2_bald_clean")
M = r"C:\lsm26\triphthonS1\art\characters\character1_face_v2\previews\refmask"
names = {'ref_front': '01_front', 'ref_left': '02_left', 'ref_back': '03_back', 'ref_right': '04_right'}
PFX = os.environ.get("RAW_PREFIX", "ref")
DIL = int(sys.argv[1]) if len(sys.argv) > 1 else 14
for k, v in names.items():
    rgba = cv2.imread(os.path.join(R, "raw", f"{PFX}__{k}.png"), cv2.IMREAD_UNCHANGED)
    a = rgba[..., 3:4].astype(np.float32) / 255
    img = (rgba[..., :3].astype(np.float32) * a + 236 * (1 - a)).astype(np.uint8)
    m = cv2.imread(os.path.join(M, f"ref__{k}.png"), cv2.IMREAD_GRAYSCALE)
    m = (m > 127).astype(np.uint8) * 255
    if m.any():
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * DIL + 1, 2 * DIL + 1)))
        img = cv2.inpaint(img, m, 9, cv2.INPAINT_TELEA)
        # soften the filled area so it reads as smooth skin
        blur = cv2.GaussianBlur(img, (0, 0), 6)
        soft = cv2.GaussianBlur(m, (0, 0), 5).astype(np.float32)[..., None] / 255
        img = (img * (1 - soft) + blur * soft).astype(np.uint8)
    cv2.imwrite(os.path.join(R, f"{v}.png"), img)
    print(k, "mask px", int((m > 0).sum()))
