"""Local (no API) build of the survival monster GLBs from Tripo outputs of tools/generate_monsters.py.

For every monster whose Tripo chain is complete: run Blender (tools/blender_build_monster.py) to merge
the rig + per-clip retarget GLBs into game/assets/monsters/<species>_<variant>.glb, validate it, and
write game/assets/monsters/manifest.json (credits per step, Tripo task ids, clips and lengths, scale,
facing, emission cover). Raw downloads come from --raw-dir (see generate_monsters.py --redownload).
"""
import argparse
import hashlib
import io
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import catalog  # noqa: E402
from tools.generate_monsters import (BY_ID, JOBS, MONSTERS, OUT_ART, P2, RIG_BIPED, RIG_CREATURE, SPECIES,  # noqa: E402
                                     load, prompt_for, steps_for)

BLENDER = ROOT / '.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe'
OUT_GAME = ROOT / 'game/assets/monsters'
MANIFEST = OUT_GAME / 'manifest.json'
REPORTS = OUT_ART / 'build'
CLIPS = ['idle', 'walk', 'run', 'attack', 'hurt', 'death']
BUILD = {
    'wolf': dict(tail=True, run_speed=1.8),
    'boar': dict(tail=False, run_speed=2.1),
    'brute': dict(attack_impact=2.2, attack_follow=0.9, extras=['roar'], idle_seconds=4.0),
    'wisp': dict(attack_impact=1.2, attack_follow=0.8, idle_seconds=4.0),
    'shroom': dict(attack_impact=1.0, attack_follow=0.5, idle_seconds=4.0),
}
# Per-monster overrides found by visual review of artifacts/monsters/sheets (2026-10-06): Tripo labelled the
# wolf_quarry rig back to front (left/right and front/hind limbs agree with each other, but the head is at -X).
OVERRIDES = {'wolf_quarry': {'flip_facing': True}}


def glb_doc(blob):
    magic, version, length = struct.unpack_from('<III', blob)
    if magic != 0x46546C67 or version != 2 or length != len(blob):
        raise ValueError('bad_glb_header')
    size, kind = struct.unpack_from('<II', blob, 12)
    if kind != 0x4E4F534A:
        raise ValueError('bad_glb_json')
    doc = json.loads(blob[20:20 + size])
    offset = 20 + size
    bsize, bkind = struct.unpack_from('<II', blob, offset)
    return doc, blob[offset + 8:offset + 8 + bsize]


def validate_game_glb(blob, expected_clips):
    """Bounded, embedded, skinned GLB with every expected clip and textures <= 1024 px."""
    from PIL import Image
    doc, binary = glb_doc(blob)
    text = json.dumps(doc)
    if '"uri"' in text:
        raise ValueError('external_uri')
    if doc.get('extensionsRequired'):
        raise ValueError('required_extension')
    if len(doc.get('buffers', [])) != 1 or len(doc.get('skins', [])) != 1:
        raise ValueError('expected_one_buffer_one_skin')
    names = [a.get('name') for a in doc.get('animations', [])]
    missing = [c for c in expected_clips if c not in names]
    if missing:
        raise ValueError('missing_clips:' + ','.join(missing))
    sizes = []
    for image in doc.get('images', []):
        view = doc['bufferViews'][image['bufferView']]
        raw = binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']]
        with Image.open(io.BytesIO(raw)) as im:
            if max(im.size) > 1024:
                raise ValueError('texture_too_large')
            sizes.append(list(im.size))
    triangles = 0
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            triangles += doc['accessors'][primitive['indices']]['count'] // 3
    return {'animations': names, 'texture_sizes': sizes, 'triangles': triangles,
            'bones': len(doc['skins'][0]['joints']), 'bytes': len(blob)}


def chain_complete(monster):
    return all((JOBS / monster['id'] / s / 'result.json').exists() and
               load(JOBS / monster['id'] / s / 'result.json').get('status') == 'success'
               for s in steps_for(monster))


def build(monster, raw_dir):
    spec = SPECIES[monster['species']]
    raw = raw_dir / monster['id']
    clips = {step[5:]: str(raw / (step + '.glb')) for step in steps_for(monster) if step.startswith('anim_')}
    missing = [p for p in [str(raw / 'rig.glb'), *clips.values()] if not Path(p).exists()]
    if missing:
        return {'id': monster['id'], 'ok': False, 'error': 'raw_missing_run_generate_monsters_redownload'}
    stats = catalog.ENEMIES[monster['species']]
    config = dict(id=monster['id'], species=monster['species'], variant=monster['variant'], rig=spec['rig'],
                  height=spec['height'], windup=stats['windup'], base=str(raw / 'rig.glb'), clips=clips,
                  out=str(OUT_GAME / (monster['id'] + '.glb')), report=str(REPORTS / (monster['id'] + '.json')),
                  **BUILD[monster['species']], **OVERRIDES.get(monster['id'], {}))
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT_GAME.mkdir(parents=True, exist_ok=True)
    config_path = REPORTS / (monster['id'] + '.config.json')
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    started = time.time()
    proc = subprocess.run([str(BLENDER), '-b', '--factory-startup', '--python',
                           str(ROOT / 'tools/blender_build_monster.py'), '--', str(config_path)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    if 'BUILD_OK' not in proc.stdout:
        tail = [l for l in (proc.stdout + proc.stderr).splitlines() if 'Error' in l or 'Traceback' in l or 'line' in l][-12:]
        return {'id': monster['id'], 'ok': False, 'error': 'blender_failed', 'detail': tail}
    blob = (OUT_GAME / (monster['id'] + '.glb')).read_bytes()
    expected = CLIPS + list(BUILD[monster['species']].get('extras', []))
    try:
        check = validate_game_glb(blob, expected)
    except ValueError as error:
        return {'id': monster['id'], 'ok': False, 'error': 'validate:' + str(error)}
    report = json.loads((REPORTS / (monster['id'] + '.json')).read_text(encoding='utf-8'))
    report.update(validation=check, sha256=hashlib.sha256(blob).hexdigest(), build_seconds=round(time.time() - started, 1))
    (REPORTS / (monster['id'] + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'id': monster['id'], 'ok': True, 'bytes': len(blob), 'clips': check['animations']}


def clip_source(name, report):
    tripo = report.get('tripo_clips', {})
    if name in tripo:
        return 'tripo:' + tripo[name]['tripo_name'] + (' (cropped/eased in Blender)' if name in ('idle', 'attack', 'hurt') else '')
    if name == 'run':
        return 'tripo:' + tripo['walk']['tripo_name'] + ' re-timed in Blender'
    return 'blender: keyframed on the Tripo skeleton'


def write_manifest():
    entries, totals = [], {'gen': 0.0, 'rigcheck': 0.0, 'rig': 0.0, 'anim': 0.0}
    for monster in MONSTERS:
        report_path = REPORTS / (monster['id'] + '.json')
        glb = OUT_GAME / (monster['id'] + '.glb')
        spec = SPECIES[monster['species']]
        steps = {}
        for step in steps_for(monster) + ['anim']:
            path = JOBS / monster['id'] / step / 'result.json'
            if not path.exists():
                continue
            result = load(path)
            steps[step] = {'task_id': result.get('task_id'), 'credits': result.get('credits_consumed'),
                           'status': result.get('status')}
            if step.startswith('anim'):
                steps[step]['preset'] = load(JOBS / monster['id'] / step / 'request.json').get(
                    'animation') or load(JOBS / monster['id'] / step / 'request.json').get('animations')
                if result.get('note'):
                    steps[step]['note'] = result['note']
            totals['anim' if step.startswith('anim') else step] += float(result.get('credits_consumed') or 0)
        report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
        if 'validation' not in report or not glb.exists():
            entries.append({'id': monster['id'], 'species': monster['species'], 'variant': monster['variant'],
                            'built': False, 'tripo': steps})
            continue
        entries.append({
            'id': monster['id'], 'species': monster['species'], 'variant': monster['variant'],
            'name': spec['name'], 'built': True,
            'file': 'res://assets/monsters/%s.glb' % monster['id'],
            'bytes': glb.stat().st_size, 'sha256': report.get('sha256'),
            'rig': {'type': spec['rig'], 'model': RIG_BIPED if spec['rig'] == 'biped' else RIG_CREATURE,
                    'bones': report['validation']['bones'], 'root': report['bones']['root']},
            'generation_model': P2, 'triangles': report['validation']['triangles'],
            'texture_sizes': report['validation']['texture_sizes'],
            'clips': {name: {**info, 'source': clip_source(name, report)} for name, info in report['clips'].items()},
            'attack_impact_seconds': report.get('attack_impact_seconds'),
            'scale_reference': {'measure': 'height', 'metres': spec['height'], **report['scale']},
            'facing': report['facing'], 'emission': report.get('emission'),
            'warnings': report.get('warnings', []),
            'tripo': steps,
            'credits': round(sum(float(v.get('credits') or 0) for v in steps.values()), 2),
            'prompt_sha256': hashlib.sha256(prompt_for(monster).encode()).hexdigest(),
        })
    OUT_GAME.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        'version': 1, 'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'source': 'Tripo P2 text-to-model + Tripo auto-rig + Tripo retarget via tools/generate_monsters.py; '
                  'merged/authored in Blender by tools/build_monsters.py',
        'notes': ('glTF +Y up, creature faces +Z, feet on y=0, already scaled to scale_reference.metres (height). '
                  'Variant = survival map (forest/quarry/frost). Loop clips: idle, walk, run. attack: the strike '
                  'lands at attack_impact_seconds (= server wind-up). death ends lying down. Clips sourced '
                  '"blender" were keyframed procedurally on the Tripo skeleton (Tripo has only a walk preset for '
                  'quadrupeds, and no death preset).'),
        'credits_by_step': {k: round(v, 2) for k, v in totals.items()},
        'total_credits_consumed': round(sum(totals.values()), 2),
        'monsters': entries,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sheets(selected, frames=6):
    """Per-monster clip sheets (rows = clips) + one contact sheet, rendered in Blender Workbench."""
    import re
    import shutil
    import tempfile
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 13)
    except OSError:
        font = ImageFont.load_default()
    out_dir = OUT_ART / 'sheets'
    out_dir.mkdir(parents=True, exist_ok=True)
    order = ['idle', 'walk', 'run', 'attack', 'hurt', 'death', 'roar']
    firsts = []
    for monster in selected:
        glb = OUT_GAME / (monster['id'] + '.glb')
        if not glb.exists():
            continue
        tmp = Path(tempfile.mkdtemp(prefix='monster_sheet_'))
        subprocess.run([str(BLENDER), '-b', '--factory-startup', '--python', str(ROOT / 'tools/blender_monster_sheet.py'),
                        '--', str(glb), str(tmp / monster['id']), str(frames)], capture_output=True, timeout=900)
        rows = {}
        for f in sorted(tmp.glob('*.png')):
            m = re.match(r'.*_([a-z]+)_(\d\d)\.png$', f.name)
            if m:
                rows.setdefault(m.group(1), []).append(f)
        clips = [c for c in order if c in rows] + sorted(c for c in rows if c not in order)
        if not clips:
            shutil.rmtree(tmp, ignore_errors=True)
            continue
        w = Image.open(rows[clips[0]][0]).width
        sheet = Image.new('RGB', (80 + w * frames, w * len(clips) + 24), (34, 38, 44))
        draw = ImageDraw.Draw(sheet)
        draw.text((6, 4), monster['id'] + '  ' + SPECIES[monster['species']]['name'], fill=(240, 220, 170), font=font)
        for r, clip in enumerate(clips):
            draw.text((6, 24 + r * w + w // 2), clip, fill=(230, 230, 230), font=font)
            for i, f in enumerate(rows[clip][:frames]):
                sheet.paste(Image.open(f).convert('RGB'), (80 + i * w, 24 + r * w))
        sheet.save(out_dir / (monster['id'] + '.jpg'), quality=85)
        firsts.append((monster, Image.open(rows['idle'][0] if 'idle' in rows else rows[clips[0]][0]).convert('RGB'),
                       Image.open(rows['attack'][len(rows['attack']) // 2]).convert('RGB') if 'attack' in rows else None))
        shutil.rmtree(tmp, ignore_errors=True)
    if firsts:
        w = firsts[0][1].width
        columns = 5
        rows_n = (len(firsts) + columns - 1) // columns
        contact = Image.new('RGB', (columns * w * 2, rows_n * (w + 30)), (34, 38, 44))
        draw = ImageDraw.Draw(contact)
        for i, (monster, idle, attack) in enumerate(firsts):
            x, y = (i % columns) * w * 2, (i // columns) * (w + 30)
            contact.paste(idle, (x, y))
            if attack:
                contact.paste(attack, (x + w, y))
            draw.text((x + 6, y + w + 6), '%s  %s  (idle | attack)' % (monster['id'], SPECIES[monster['species']]['name']),
                      fill=(240, 220, 170), font=font)
        contact.save(OUT_ART / 'contact_sheet.jpg', quality=88)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+', choices=sorted(BY_ID))
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'output/monsters_raw')
    parser.add_argument('--manifest-only', action='store_true')
    parser.add_argument('--sheets', action='store_true', help='render clip sheets + contact sheet only')
    args = parser.parse_args()
    if args.sheets:
        sheets([BY_ID[i] for i in args.only] if args.only else MONSTERS)
        return
    if not args.manifest_only:
        selected = [BY_ID[i] for i in args.only] if args.only else MONSTERS
        for monster in selected:
            if not chain_complete(monster):
                print(json.dumps({'id': monster['id'], 'ok': False, 'error': 'tripo_chain_incomplete'}), flush=True)
                continue
            print(json.dumps(build(monster, args.raw_dir.resolve()), ensure_ascii=False), flush=True)
    write_manifest()
    print(json.dumps({'manifest': str(MANIFEST.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
