"""Overview of every built monster (and NPC): three frames per character cut from its clip sheet.

  python tools/body_gen/roster_sheet.py <out.png>

Reads art/characters/body_p2_v1/mon_v3/anim/sheets/<id>_clips.png (made by clip_sheet.py: one row per
clip, 6 frames) and game/<id>_report.json, and shows idle / attack (or work) / death (or walk) with the
attack impact time.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANIM = os.path.join(ROOT, 'art', 'characters', 'body_p2_v1', 'mon_v3', 'anim')
KO = {'goblin': '고블린', 'werewolf': '늑대인간', 'troll': '트롤', 'cyclops': '사이클롭스', 'treant': '고목 거인',
      'skeleton': '해골 기사', 'lizardman': '리자드맨', 'minotaur': '미노타우로스', 'mummy_king': '미라 왕',
      'ghoul': '구울', 'ice_shardling': '얼음 정령', 'draugr': '얼어붙은 전사', 'yeti': '예티', 'wendigo': '웬디고',
      'frost_hag': '서리 마녀', 'frost_knight': '서리 망령 기사', 'ice_golem': '얼음 골렘', 'glacier_giant': '빙하 거인',
      'boni': '보니 (NPC)', 'sol': '솔 (NPC)'}
MAP = {'goblin': '숲·튜토리얼', 'werewolf': '숲', 'troll': '숲', 'cyclops': '숲', 'treant': '숲 보스',
       'skeleton': '사막', 'lizardman': '사막', 'minotaur': '사막', 'mummy_king': '사막',
       'ghoul': '서리', 'ice_shardling': '서리', 'draugr': '서리', 'yeti': '서리', 'wendigo': '서리',
       'frost_hag': '서리', 'frost_knight': '서리', 'ice_golem': '서리', 'glacier_giant': '서리', 'boni': '마을 공방', 'sol': '마을 정원'}
CELL, PITCH_X, X0, Y0, PITCH_Y = 210, 216, 180, 60, 222  # clip_sheet.py layout

cfg = json.load(open(os.path.join(ANIM, 'game_build.json'), encoding='utf-8'))['monsters']
ids = [k for k in cfg if os.path.exists(os.path.join(ANIM, 'sheets', k + '_clips.png'))]
fb = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 28)
fm = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 17)
fs = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 14)
T = 150
cols = 4
cw = 3 * T + 16
rows = (len(ids) + cols - 1) // cols
W = 20 + cols * (cw + 14)
H = 70 + rows * (T + 56)
out = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(out)
d.text((20, 16), '1범주 몬스터 18종 + 표지 NPC 2명 — 몬스터별 전용 AI 동작 (대기 · 공격 · 쓰러짐 / NPC: 대기 · 작업 · 걷기)',
       font=fb, fill=(40, 36, 32))
for n, k in enumerate(ids):
    sheet = Image.open(os.path.join(ANIM, 'sheets', k + '_clips.png')).convert('RGB')
    rep = json.load(open(os.path.join(ANIM, 'game', k + '_report.json'), encoding='utf-8'))
    order = rep.get('clip_order', list(rep['clips']))
    if 'attack' in order:
        picks = [('idle', 0, '대기'), ('attack', 2, '공격'), ('death', 5, '쓰러짐')]
    else:
        picks = [('idle', 0, '대기'), ('work', 2, '작업'), ('walk', 2, '걷기')]
    x = 20 + (n % cols) * (cw + 14)
    y = 70 + (n // cols) * (T + 56)
    title = '%s · %s' % (KO.get(k, k), MAP.get(k, ''))
    if 'attack_impact_seconds' in rep:
        title += ' · 타격 %.2fs' % rep['attack_impact_seconds']
    d.text((x, y), title, font=fm, fill=(40, 36, 32))
    for i, (clip, frame, label) in enumerate(picks):
        if clip not in order:
            continue
        r = order.index(clip)
        box = (X0 + frame * PITCH_X, Y0 + r * PITCH_Y, X0 + frame * PITCH_X + CELL, Y0 + r * PITCH_Y + CELL)
        im = sheet.crop(box).resize((T, T), Image.LANCZOS)
        out.paste(im, (x + i * (T + 8), y + 26))
        d.text((x + i * (T + 8) + 4, y + 28), label, font=fs, fill=(30, 30, 30))
out.save(sys.argv[1])
print(sys.argv[1], out.size, len(ids))
