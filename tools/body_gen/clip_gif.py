"""Animated GIF of all clips side by side (render_clips.py output made with frames_per_clip < 0).

  python tools/body_gen/clip_gif.py <frames dir> <out.gif> <title> [fps] [seconds]

Every panel loops its own clip; the GIF runs `seconds` (default: the longest clip).
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

d, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
fps = float(sys.argv[4]) if len(sys.argv) > 4 else 10
meta = json.load(open(os.path.join(d, 'clips.json')))
KO = {'idle': '대기', 'walk': '걷기', 'run': '달리기', 'attack': '공격', 'hurt': '피격', 'death': '쓰러짐',
      'hover': '부유', 'fly': '비행', 'work': '작업'}
ORDER = [c for c in ('idle', 'walk', 'run', 'work', 'attack', 'hurt', 'death', 'hover', 'fly') if c in meta['clips']]
ORDER += [c for c in meta['clips'] if c not in ORDER]
seconds = float(sys.argv[5]) if len(sys.argv) > 5 else max(meta['clips'][c]['seconds'] for c in ORDER)
fb = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 20)
fm = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 17)
T = 240
cols = 3
rows = (len(ORDER) + cols - 1) // cols
W, H = cols * T, 40 + rows * T
panels = {c: [Image.open(os.path.join(d, '%s_%d.png' % (c, i))).convert('RGB').resize((T, T), Image.LANCZOS)
              for i in range(len(meta['clips'][c]['frames']))] for c in ORDER}
frames = []
for k in range(int(round(seconds * fps))):
    im = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(im)
    dr.text((10, 8), title, font=fb, fill=(40, 36, 32))
    for n, c in enumerate(ORDER):
        x, y = (n % cols) * T, 40 + (n // cols) * T
        seq = panels[c]
        # one-shot clips hold their last frame; loops wrap
        i = k % len(seq) if meta['clips'][c].get('loop', c in ('idle', 'walk', 'run', 'hover', 'fly')) else min(k, len(seq) - 1)
        im.paste(seq[i], (x, y))
        dr.text((x + 8, y + 6), KO.get(c, c), font=fm, fill=(30, 30, 30))
    frames.append(im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
frames[0].save(out, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=True)
print(out, len(frames), os.path.getsize(out))
