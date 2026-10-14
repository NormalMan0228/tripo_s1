"""Optional: pack the per-part textures into ONE 4096 atlas for a one-material head (texture step 4, optional).
The separate-material asset (tex_assign.py default) stays the default; this writes an alternative.

Layout (pixels, top-left origin, 4096 x 4096):
  skin    0..4096 x 0..3584   (skin.png squeezed 12.5 % vertically: texel aspect 1 : 0.875)
  eyes    0..1024 x 3584..4096   (eyes.png 2048x1024 -> 1024x512, iris about half as many texels)
  brows   1024..2048 x 3584..4096
  teeth   2048..3072 x 3584..4096   (teeth + gums)
  tongue  3072..3584 x 3584..4096
  free    3584..4096 x 3584..4096
plus atlas_rough.png (same layout, roughness per part, linear) so one material keeps glossy eyes / teeth.
Each part's 'uv_tex' maps into its rectangle as 'uv_atlas' (tex_assign.py --atlas <atlas.json> does it in
Blender). Rect borders get a few pixels of padding from the part textures' own padding.
Usage: python atlas_pack.py <tex_dir>      -> <tex_dir>/atlas.png, atlas_rough.png, atlas.json
"""
import sys, os, json
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_views as rv

TEX = os.path.abspath(sys.argv[1]); A = 4096
R = {'skin': (0, 0, 4096, 3584), 'eyes': (0, 3584, 1024, 512), 'brows': (1024, 3584, 1024, 512),
     'teeth': (2048, 3584, 1024, 512), 'tongue': (3072, 3584, 512, 512)}
ROUGH = {'skin': 0.5, 'eyes': 0.08, 'brows': 0.7, 'teeth': 0.25, 'tongue': 0.35}
OBJ = {'skin': ['face'], 'eyes': ['eyes'], 'brows': ['p2_brows'], 'teeth': ['teeth_up', 'teeth_lo'], 'tongue': ['tongue']}
atlas = np.zeros((A, A, 3), np.float32); rough = np.full((A, A), 0.5, np.float32)
info = {'size': A, 'rects': {}, 'objects': {}}
for part, (x, y, w, h) in R.items():
    p = os.path.join(TEX, part + '.png')
    if not os.path.exists(p): continue
    im = rv.load_rgb(p)
    atlas[y:y + h, x:x + w] = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
    rough[y:y + h, x:x + w] = ROUGH[part]
    if part == 'teeth': rough[y:y + h, x + w // 2:x + w] = 0.35            # gums half
    # uv transform: u' = u0 + u * su, v' = v0 + v * sv (Blender uv, origin bottom-left)
    info['rects'][part] = {'px': [x, y, w, h], 'u0': x / A, 'v0': 1 - (y + h) / A, 'su': w / A, 'sv': h / A,
                           'texels_kept': round(w * h / (im.shape[0] * im.shape[1]), 3)}
    for o in OBJ[part]: info['objects'][o] = part
rv.save_rgb(os.path.join(TEX, 'atlas.png'), atlas)
cv2.imwrite(os.path.join(TEX, 'atlas_rough.png'), (rough * 255 + 0.5).astype(np.uint8))
json.dump(info, open(os.path.join(TEX, 'atlas.json'), 'w'), indent=1)
print('ATLAS', json.dumps(info['rects']))
