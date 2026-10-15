"""Markdown table of every built monster/NPC from its build report (for docs and handoff notes).

  python tools/body_gen/report_table.py > table.md
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANIM = os.path.join(ROOT, 'art', 'characters', 'body_p2_v1', 'mon_v3', 'anim')
cfg = json.load(open(os.path.join(ANIM, 'game_build.json'), encoding='utf-8'))['monsters']
MAPV = {'forest': 'forest', 'quarry': 'quarry', 'frost': 'frost'}
print('| id | 이름 | 맵·티어 | 게임 파일 | 키 m | 클립 길이 (초) | 타격 초 | 걷기/달리기 m/s | 최대 회전 °/프레임 | 경고 |')
print('|---|---|---|---|---|---|---|---|---|---|')
for k, v in cfg.items():
    rp = os.path.join(ANIM, 'game', k + '_report.json')
    if not os.path.exists(rp):
        continue
    r = json.load(open(rp, encoding='utf-8'))
    cat = v.get('catalog', {})
    if v.get('kind') == 'npc':
        name, where, file = {'boni': ('보니', '마을 공방'), 'sol': ('솔', '마을 정원')}.get(k, (k, '')) + ('assets/npc/%s.glb' % k,)
    else:
        name, where = cat.get('name', k), '%s · %s' % (cat.get('map', ''), cat.get('tier', ''))
        file = 'assets/monsters/%s_%s.glb' % (k, MAPV.get(cat.get('map', ''), 'forest'))
    clips = ' '.join('%s %.2f' % (c, i['seconds']) for c, i in r['clips'].items())
    speeds = '%s / %s' % (r['clips'].get('walk', {}).get('ground_speed_mps', '-'), r['clips'].get('run', {}).get('ground_speed_mps', '-'))
    pop = max(i['max_bone_deg_per_frame'] for i in r['clips'].values())
    print('| %s | %s | %s | %s | %.1f | %s | %s | %s | %.0f | %s |' % (
        k, name, where, file, r['scale']['height_m'], clips, r.get('attack_impact_seconds', '-'), speeds, pop,
        '; '.join(r['warnings'])[:80] or '-'))
