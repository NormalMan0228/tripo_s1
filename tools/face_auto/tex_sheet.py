"""Texture QA sheet: old (per-vertex colour) vs new (per-part image textures).
Grid: columns = poses (combos), rows = for each view an 'old' row and a 'new' row.
Usage: python tex_sheet.py <out.jpg> <old_dir> <new_dir> <title> <view,view> <combo,combo> [--cell 360]
(render file names as render_tex.py writes them: <view>_<combo with + -> _>.png; missing files stay grey)
"""
import sys, os
from PIL import Image, ImageDraw

a = sys.argv[1:]
OUT, OLD, NEW, TITLE = a[0], a[1], a[2], a[3]
VIEWS, COMBOS = a[4].split(','), a[5].split(',')
C = int(a[a.index('--cell') + 1]) if '--cell' in a else 360
LW, TH = 70, 30
sheet = Image.new('RGB', (LW + len(COMBOS) * C, TH + 2 * len(VIEWS) * C), (38, 38, 42))
d = ImageDraw.Draw(sheet)
d.text((8, 8), TITLE, fill=(235, 235, 235))
for j, cb in enumerate(COMBOS):
    d.text((LW + j * C + 6, TH - 14), cb.replace('eyeBlinkLeft+eyeBlinkRight', 'blink').replace('eyeLookInLeft+eyeLookOutRight', 'look right'), fill=(210, 210, 210))
r = 0
for v in VIEWS:
    for tag, base in (('old', OLD), ('new', NEW)):
        y = TH + r * C
        d.text((8, y + C // 2 - 6), f'{tag}\n{v}', fill=(255, 180, 120) if tag == 'old' else (140, 220, 140))
        for j, cb in enumerate(COMBOS):
            p = os.path.join(base, f'{v}_{cb.replace("+", "_")}.png')
            im = Image.open(p).convert('RGB').resize((C, C), Image.LANCZOS) if os.path.exists(p) else Image.new('RGB', (C, C), (90, 90, 90))
            sheet.paste(im, (LW + j * C, y))
        r += 1
sheet.save(OUT, quality=90)
print('SHEET', OUT)
