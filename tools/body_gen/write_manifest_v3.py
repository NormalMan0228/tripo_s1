"""Record the mon_v3 game GLBs in game/assets/monsters/manifest.json under "monsters_v3".

  python tools/body_gen/write_manifest_v3.py <manifest.json> <glb folder>

The game loads assets/monsters/<species>_<map>.glb by name (monster.gd); this list is the record of
what each file is: species, map, tier, clips, impact time, stride speeds, triangles, size, hash and
Tripo credits. The existing "monsters" list (today's 15 GLBs) is left as it is.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANIM = os.path.join(ROOT, 'art', 'characters', 'body_p2_v1', 'mon_v3', 'anim')
man_path, glb_dir = sys.argv[1], sys.argv[2]
man = json.load(open(man_path, encoding='utf-8'))
cfg = json.load(open(os.path.join(ANIM, 'game_build.json'), encoding='utf-8'))['monsters']
ledger = json.load(open(os.path.join(ROOT, 'art', 'characters', 'body_p2_v1', 'ledger.json'), encoding='utf-8'))
spent = ledger.get('monsters_v3_anim', {}).get('monsters', {})
out = []
for k, v in cfg.items():
    if v.get('kind') == 'npc':
        continue
    cat = v.get('catalog', {})
    name = '%s_%s.glb' % (k, cat.get('map', 'forest'))
    path = os.path.join(glb_dir, name)
    rp = os.path.join(ANIM, 'game', k + '_report.json')
    if not (os.path.exists(path) and os.path.exists(rp)):
        continue
    r = json.load(open(rp, encoding='utf-8'))
    data = open(path, 'rb').read()
    out.append({
        'id': k, 'name': cat.get('name', k), 'map': cat.get('map'), 'tier': cat.get('tier'),
        'file': 'res://assets/monsters/' + name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
        'height_m': r['scale']['height_m'], 'triangles': r.get('triangles'),
        'clips': {c: {'seconds': i['seconds'], 'loop': i['loop']} for c, i in r['clips'].items()},
        'attack_impact_seconds': r.get('attack_impact_seconds'),
        'walk_mps': r['clips'].get('walk', {}).get('ground_speed_mps'),
        'run_mps': r['clips'].get('run', {}).get('ground_speed_mps'),
        'proxy_of': v.get('proxy_of'),
        'tripo_task': v.get('tripo_task'),
        'credits': spent.get(k, {}).get('credits', 0),
        'source': 'Tripo P2 + texture 2K + humanoid rig (Mixamo) + 6 AI motions; tools/body_gen/build_game_monster.py',
    })
man['monsters_v3'] = out
man['monsters_v3_note'] = ('2026-10-16 mon_v3: one GLB per species named <species>_<map>.glb (monster.gd picks a species '
                           'model by name before its stand-in). chimera/dragon are boss bodies borrowed from the minotaur '
                           '/ glacier giant until their own models exist (proxy_of).')
json.dump(man, open(man_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(len(out), 'entries', sum(e['bytes'] for e in out) // 1024 // 1024, 'MB')
