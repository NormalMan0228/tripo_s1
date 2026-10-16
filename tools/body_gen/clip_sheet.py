"""Contact sheet of render_clips.py output: one row per clip, Korean labels.

  python tools/body_gen/clip_sheet.py <frames dir> <out.png> <title> [report.json]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

d, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
rep = json.load(open(sys.argv[4], encoding='utf-8')) if len(sys.argv) > 4 else {}
meta = json.load(open(os.path.join(d, 'clips.json')))
KO = {'idle': '대기', 'walk': '걷기', 'run': '달리기', 'attack': '공격', 'hurt': '피격', 'death': '쓰러짐',
      'hover': '부유', 'fly': '비행', 'work': '작업'}
ORDER = [c for c in rep.get('clip_order', [])] or sorted(meta['clips'])
fb = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 26)
fm = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 19)
fs = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
T = 210
per = len(meta['clips'][ORDER[0]]['frames'])
W = 180 + per * (T + 6) + 10
H = 60 + len(ORDER) * (T + 12)
c = Image.new('RGB', (W, H), 'white')
dr = ImageDraw.Draw(c)
dr.text((16, 12), title, font=fb, fill=(40, 36, 32))
y = 60
for clip in ORDER:
    info = meta['clips'][clip]
    r = rep.get('clips', {}).get(clip, {})
    src = r.get('source', '')
    kind = 'AI 생성' if src and not any(k in src for k in ('run.', 'hit_to_body', 'tripo:run')) else 'Tripo 프리셋'
    if src.startswith('proc:'):
        kind = '절차 생성'  # tools/body_gen/proc_motion.py (Blender script, no AI)
    dr.text((16, y + 10), KO.get(clip, clip), font=fm, fill=(40, 36, 32))
    dr.text((16, y + 40), clip, font=fs, fill=(110, 104, 96))
    dr.text((16, y + 62), '%.2f초' % info['seconds'] + (' · 반복' if r.get('loop') else ''), font=fs, fill=(110, 104, 96))
    dr.text((16, y + 84), kind, font=fs, fill={'AI 생성': (30, 110, 60), '절차 생성': (150, 90, 20)}.get(kind, (40, 90, 150)))
    if clip == 'attack' and 'attack_impact_seconds' in rep:
        dr.text((16, y + 106), '타격 %.2f초' % rep['attack_impact_seconds'], font=fs, fill=(170, 60, 40))
    x = 180
    for i, fr in enumerate(info['frames']):
        im = Image.open(os.path.join(d, '%s_%d.png' % (clip, i))).convert('RGB').resize((T, T), Image.LANCZOS)
        c.paste(im, (x, y))
        dr.text((x + 6, y + 4), '%.2fs' % fr['seconds'], font=fs, fill=(60, 60, 60))
        x += T + 6
    y += T + 12
c.save(out)
print(c.size)
