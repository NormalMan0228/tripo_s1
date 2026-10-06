"""Generate, auto-rig and animate the survival monsters with Tripo (user-approved, capped).

Roster: 5 species x 3 regional variants (forest / quarry / frost) = 15 separate P2 generations.
Chain per monster (each step is its own paid or free Tripo task):
  gen      POST /generation/text-to-model   (P2 textured, ~110 credits)
  rigcheck POST /animations/rig-check       (free)
  rig      POST /animations/rig             (25 credits; biped -> rig v1.0, quadruped -> rig v2.5)
  anim_<clip> POST /animations/retarget     (10 credits, ONE preset per task; Blender merges the clips)

Safety rules (same as tools/generate_interior_assets.py):
- An intent file is written before every POST; a step with an intent but no task id is never
  resubmitted automatically (ambiguous state). Certain rejections are marked; an operator may retry
  them explicitly with --retry-rejected.
- Any provider error during a submission stops all further submissions (in-flight tasks are still
  polled and downloaded; polling is a free GET).
- A credit ledger (actual credits for finished tasks, reservations for in-flight/uncertain ones)
  must stay within --max-credits before a new task is submitted. A cost above the reservation stops
  the run.
- At most --concurrency (<=3) paid tasks run at once.
- The API key is read only via server.config.read_tripo_key and never logged; task output URLs are
  never written to disk (only their host name).

State: artifacts/monsters/jobs/<id>/<step>/{request,intent,task,result}.json
Raw downloads: --raw-dir (default: output/monsters_raw, gitignored); safe to delete, `--redownload`
fetches them again for free while the Tripo tasks still exist.
Local Blender/Godot processing is separate: tools/build_monsters.py.
"""
import argparse
import asyncio
import hashlib
import json
import re
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import Settings, read_tripo_key  # noqa: E402
from server.provider import TripoProvider, ProviderError, validate_glb  # noqa: E402

OUT_ART = ROOT / 'artifacts/monsters'
JOBS = OUT_ART / 'jobs'
PREVIEWS = OUT_ART / 'tripo_previews'
LOG = OUT_ART / 'log.jsonl'

P2 = 'P2-20260801'
RIG_BIPED = 'v1.0-20240301'      # biped only, 90+ presets
RIG_CREATURE = 'v2.5-20260210'   # quadruped & other creatures, preset:quadruped:walk only
STEPS = ('gen', 'rigcheck', 'rig', 'anim')  # 'anim' expands to one retarget task per clip: anim_<clip>
# A multi-preset retarget task bills every preset but its model_url holds only the LAST clip (verified on
# brute_forest 2026-10-06: 5 presets, 50 credits, GLB contained only angry_01). So: one clip per task.
TERMINAL = ('success', 'failed', 'cancelled', 'banned', 'expired')
# Measured on this account (interior run 2026-10-06, Haeru rig, explorer retarget): P2 textured 110,
# rig 25, rig-check 0, retarget 10 per preset.
EXPECTED = {'gen': 110, 'rigcheck': 0, 'rig': 25, 'anim_per_clip': 10}
RESERVE = {'gen': 130, 'rigcheck': 5, 'rig': 30, 'anim_per_clip': 12}

STYLE = ('Single isolated game-ready 3D creature character for a cozy colorful storybook island adventure game. '
         'Smooth stylized 3D cartoon sculpt like a Nintendo creature: soft rounded chunky forms, a big readable '
         'silhouette, clean solid geometry, warm hand-painted matte textures with subtle brush grain. A mischievous, '
         'cute-spooky night monster from the Forest of Seven Nights with big bright glowing eyes. Exactly one creature, '
         'full body, centered. No ground, base, scenery or background, no text, no props or weapons. ')
POSE = {
    'quadruped': ('Standing still on all four straight legs, slightly apart, in a neutral side-on rigging stance, '
                  'head level looking forward, mouth closed, tail extended straight back. '),
    'biped': ('Standing upright facing forward in a neutral A-pose for rigging: arms held out away from the body at '
              '45 degrees, legs apart, hands open. '),
}
NEGATIVE = ('ground plane, base, pedestal, scenery, background, text, logo, weapon, rider, saddle, armor, '
            'multiple creatures, realistic photo, gore, blood, horror, floating detached parts')

SPECIES = {
    'wolf': dict(
        name='그림자 늑대', rig='quadruped', faces=12000, height=1.25,
        anims=[('walk', 'preset:quadruped:walk')],
        text=('A shadow wolf: a lean fox-like wolf about 1.2m tall, oversized pointed ears, a soft tufted mane, a long '
              'fluffy tail, a short snout and oversized paws. '),
        variants={
            'forest': 'Dark indigo-charcoal fur with patches of soft green moss on its back and shoulders, a few small '
                      'green leaves in its mane, glowing amber-yellow eyes.',
            'quarry': 'Sooty charcoal-black fur with glowing orange ember cracks across its back and legs, ash-grey '
                      'tufts, a smouldering orange-tipped tail, glowing orange eyes.',
            'frost': 'Pale blue-grey frosted fur, a fluffy white frosted mane, a row of small clear ice crystals along '
                     'its spine, glowing ice-blue eyes.',
        }),
    'boar': dict(
        name='가시 멧돼지', rig='quadruped', faces=12000, height=1.1,
        anims=[('walk', 'preset:quadruped:walk')],
        text=('A thorny boar: a stocky round-bodied wild boar about 1.0m tall at the shoulder, short sturdy legs, a big '
              'flat snout, two short curved tusks, small ears and a ridge of thick spiky bristles along its back. '),
        variants={
            'forest': 'Dark brown-violet hide, a mossy green back with thorny bramble spikes and a few leaves along '
                      'the bristle ridge, glowing amber-yellow eyes.',
            'quarry': 'Rough charcoal rock-like hide with glowing orange ember cracks, a ridge of black obsidian shard '
                      'bristles, ash-grey tusks, glowing orange eyes.',
            'frost': 'Shaggy pale grey-blue fur, a ridge of blunt icicle spikes along its back, frosted white tusks, '
                     'glowing ice-blue eyes.',
        }),
    'brute': dict(
        name='이끼 수호자', rig='biped', faces=14000, height=2.4,
        anims=[('idle', 'preset:biped:idle'), ('walk', 'preset:biped:walk'), ('attack', 'preset:biped:chop'),
               ('hurt', 'preset:biped:hurt'), ('roar', 'preset:biped:angry_01')],
        text=('A moss guardian golem: a big heavy stone golem about 2.4m tall with a hunched broad chest, huge long '
              'arms ending in chunky stone fists, short stumpy legs and a small head sunk between the shoulders. '),
        variants={
            'forest': 'Mossy grey-green boulder body bound by gnarled tree roots, thick moss and small ferns on its '
                      'shoulders, glowing amber-yellow eyes and a small glowing rune on its chest.',
            'quarry': 'Dark basalt rock body with glowing orange magma cracks, dusty ash, charred roots wrapped '
                      'around its arms, glowing orange eyes.',
            'frost': 'Pale blue-grey stone body dusted with snow, clusters of clear ice crystals on its shoulders and '
                     'back, frosted roots, glowing ice-blue eyes.',
        }),
    'wisp': dict(
        name='불씨 도깨비', rig='biped', faces=10000, height=1.1,
        anims=[('idle', 'preset:biped:idle'), ('walk', 'preset:biped:walk'), ('run', 'preset:biped:run'),
               ('attack', 'preset:biped:cast_a_spell'), ('hurt', 'preset:biped:hurt')],
        text=('A mischievous little fire goblin imp (Korean dokkaebi) about 1.1m tall: a round chubby body, a big '
              'round head with one stubby horn, pointy ears and a cheeky fanged grin, short stubby arms and legs, a '
              'big flame-shaped tuft of hair. '),
        variants={
            'forest': 'Dark indigo-violet skin, a skirt of green leaves, a glowing golden-orange flame tuft, glowing '
                      'yellow eyes.',
            'quarry': 'Charcoal-red skin with glowing orange ember cracks, a bright glowing orange flame tuft, an '
                      'ash-grey loincloth, glowing yellow eyes.',
            'frost': 'Pale icy-blue skin, a glowing cyan blue-fire flame tuft, little frost crystals on its '
                     'shoulders, glowing white-blue eyes.',
        }),
    'shroom': dict(
        name='버섯 망령', rig='biped', faces=8000, height=0.95,
        anims=[('idle', 'preset:biped:idle'), ('walk', 'preset:biped:walk'), ('run', 'preset:biped:run'),
               ('attack', 'preset:jump'), ('hurt', 'preset:biped:hurt')],
        text=('A mushroom ghost: a small chubby mushroom creature about 0.9m tall with a huge round spotted mushroom '
              'cap as its head, a cute spooky face under the cap with big glowing eyes, a stubby stem body, tiny '
              'arms and short legs. '),
        variants={
            'forest': 'Dusky plum-violet cap with glowing pale yellow-green spots and moss on the rim, a pale '
                      'lavender stem body, glowing yellow-green eyes.',
            'quarry': 'Charred dark brown cap with glowing orange ember spots and cracks, an ash-grey stem body, '
                      'glowing orange eyes.',
            'frost': 'Pale icy-blue cap with frosted white spots and small icicles hanging from the rim, a white stem '
                     'body, glowing ice-blue eyes.',
        }),
}
VARIANTS = ('forest', 'quarry', 'frost')
MONSTERS = [dict(id='%s_%s' % (species, variant), species=species, variant=variant)
            for variant in VARIANTS for species in SPECIES]
BY_ID = {m['id']: m for m in MONSTERS}


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def log(event, **fields):
    OUT_ART.mkdir(parents=True, exist_ok=True)
    entry = {'time': now(), 'event': event, **fields}
    with LOG.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(json.dumps(entry, ensure_ascii=False), flush=True)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def prompt_for(monster):
    spec = SPECIES[monster['species']]
    prompt = STYLE + POSE[spec['rig']] + spec['text'] + spec['variants'][monster['variant']]
    if len(prompt) > 1024:
        raise ValueError('prompt_too_long:%s:%d' % (monster['id'], len(prompt)))
    if len(NEGATIVE) > 255:
        raise ValueError('negative_prompt_too_long')
    return prompt


def steps_for(monster, until='anim'):
    steps = list(STEPS[:3]) + ['anim_' + clip for clip, _ in SPECIES[monster['species']]['anims']]
    limit = STEPS.index(until)
    return [s for s in steps if STEPS.index('anim' if s.startswith('anim') else s) <= limit]


def preset_for(step, monster):
    return dict(SPECIES[monster['species']]['anims'])[step[5:]]


def reservation(step, monster):
    if step.startswith('anim'):
        return RESERVE['anim_per_clip'] * (5 if step == 'anim' else 1)
    return RESERVE[step]


def expected(step, monster):
    if step.startswith('anim'):
        return EXPECTED['anim_per_clip'] * (5 if step == 'anim' else 1)
    return EXPECTED[step]


def payload_for(step, monster, source_task=None):
    spec = SPECIES[monster['species']]
    if step == 'gen':
        return {'model': P2, 'prompt': prompt_for(monster), 'negative_prompt': NEGATIVE,
                'face_limit': spec['faces'], 'quad': False, 'texture': True, 'pbr': True, 'export_uv': True}
    if step == 'rigcheck':
        return {'input': source_task}
    if step == 'rig':
        biped = spec['rig'] == 'biped'
        return {'input': source_task, 'model': RIG_BIPED if biped else RIG_CREATURE, 'rig_type': spec['rig'],
                'spec': 'tripo', 'out_format': 'glb'}
    return {'input': source_task, 'animation': preset_for(step, monster), 'out_format': 'glb',
            'bake_animation': True, 'export_with_geometry': True, 'animate_in_place': True}


def route_for(step):
    return {'gen': '/generation/text-to-model', 'rigcheck': '/animations/rig-check',
            'rig': '/animations/rig'}.get(step, '/animations/retarget')


# ---------------------------------------------------------------- credit ledger
def step_spend(folder, fallback):
    total = 0.0
    for sub in [folder, *sorted(folder.glob('attempt-*'))] if folder.exists() else []:
        result, intent = sub / 'result.json', sub / 'intent.json'
        if result.exists():
            credits = load(result).get('credits_consumed')
            total += float(credits) if isinstance(credits, (int, float)) else fallback
        elif intent.exists():
            data = load(intent)
            if not data.get('certain_rejection'):
                total += float(data.get('reservation', fallback))
    return total


class Ledger:
    def __init__(self, cap):
        self.cap = cap
        self.committed = sum(step_spend(JOBS / m['id'] / step, reservation(step, m))
                             for m in MONSTERS for step in steps_for(m) + ['anim'])

    def try_reserve(self, amount):
        if self.committed + amount > self.cap:
            return False
        self.committed += amount
        return True

    def settle(self, reserved, actual):
        self.committed += (actual if isinstance(actual, (int, float)) else reserved) - reserved

    def release(self, reserved):
        self.committed -= reserved


# ---------------------------------------------------------------- downloads + validation
def approved(url):
    parsed = urlparse(url or '')
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and parsed.port in (None, 443) and not parsed.username and not parsed.password
            and (host == 'tripo3d.ai' or host.endswith('.tripo3d.ai') or host == 'tripo-data.rg1.data.tripo3d.com'
                 or host.endswith('.tripo3d.com')))


async def fetch(url, limit):
    """GET an asset from an approved Tripo host without forwarding the API key."""
    if not approved(url):
        raise ProviderError('unapproved_asset_host')
    chunks, size = [], 0
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            async with client.stream('GET', url) as response:
                if response.status_code != 200:
                    raise ProviderError('asset_download_failed')
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ProviderError('asset_too_large')
                    chunks.append(chunk)
    except httpx.HTTPError:
        raise ProviderError('asset_download_failed') from None
    return b''.join(chunks)


def glb_json(blob):
    if len(blob) < 28:
        raise ProviderError('invalid_model')
    magic, version, length = struct.unpack_from('<III', blob)
    if magic != 0x46546C67 or version != 2 or length != len(blob):
        raise ProviderError('invalid_model')
    size, kind = struct.unpack_from('<II', blob, 12)
    if kind != 0x4E4F534A:
        raise ProviderError('invalid_model')
    return json.loads(blob[20:20 + size])


def validate_rigged(blob, want_animations=0):
    """Structural check for skinned/animated GLBs (validate_glb deliberately rejects skins/animations)."""
    doc = glb_json(blob)

    def walk(value, depth=0):
        if depth > 40:
            raise ProviderError('invalid_model')
        if isinstance(value, dict):
            if 'uri' in value:
                raise ProviderError('invalid_model')
            for item in value.values():
                walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)
    walk(doc)
    if doc.get('asset', {}).get('version') != '2.0' or len(doc.get('buffers', [])) != 1:
        raise ProviderError('invalid_model')
    if not doc.get('skins') or not doc.get('meshes'):
        raise ProviderError('missing_skin')
    if len(doc.get('animations', [])) < want_animations:
        raise ProviderError('missing_animations')
    return {'bones': len(doc['skins'][0].get('joints', [])), 'animations': [a.get('name') for a in doc.get('animations', [])],
            'images': len(doc.get('images', [])), 'bytes': len(blob)}


# ---------------------------------------------------------------- one step
async def run_step(step, monster, source_task, provider, ledger, stop, semaphore, args):
    """Run one Tripo step for one monster. Returns (ok, task_id, task_output)."""
    folder = JOBS / monster['id'] / step
    folder.mkdir(parents=True, exist_ok=True)
    intent_path, task_path, result_path = folder / 'intent.json', folder / 'task.json', folder / 'result.json'
    if result_path.exists():
        result = load(result_path)
        if result.get('status') == 'success':
            return True, result['task_id'], result
        if not args.retry_failed:
            return False, result.get('task_id'), result
        archive = folder / ('attempt-%d' % (len(list(folder.glob('attempt-*'))) + 1))
        archive.mkdir()
        for name in ('intent.json', 'task.json', 'result.json', 'request.json'):
            if (folder / name).exists():
                (folder / name).rename(archive / name)
        log('archived_failed_attempt', item=monster['id'], step=step, folder=archive.name)
    reserved = reservation(step, monster)
    async with semaphore:
        if not task_path.exists():
            if intent_path.exists():
                intent = load(intent_path)
                if intent.get('certain_rejection') and args.retry_rejected:
                    archive = folder / ('attempt-%d' % (len(list(folder.glob('attempt-*'))) + 1))
                    archive.mkdir()
                    for name in ('intent.json', 'request.json'):
                        if (folder / name).exists():
                            (folder / name).rename(archive / name)
                else:
                    log('ambiguous_intent_no_resubmit', item=monster['id'], step=step,
                        certain_rejection=intent.get('certain_rejection'))
                    return False, None, {'error': 'ambiguous_intent_no_resubmit'}
            if stop.is_set():
                return False, None, {'error': 'not_submitted_after_stop'}
            if not ledger.try_reserve(reserved):
                log('budget_cap_reached', item=monster['id'], step=step, committed=ledger.committed, cap=ledger.cap)
                return False, None, {'error': 'budget_cap'}
            payload = payload_for(step, monster, source_task)
            save(folder / 'request.json', payload)
            with intent_path.open('x', encoding='utf-8') as handle:
                json.dump({'time': time.time(), 'step': step, 'reservation': reserved, 'automatic_resubmit': False},
                          handle)
            log('submit_request', item=monster['id'], step=step, route=route_for(step),
                committed_with_reservation=ledger.committed,
                **({'prompt_chars': len(payload['prompt']),
                    'prompt_sha256': hashlib.sha256(payload['prompt'].encode()).hexdigest()} if step == 'gen' else
                   {'source_task': source_task}))
            try:
                data = await provider.request('POST', route_for(step), payload)
            except ProviderError as error:
                stop.set()
                if not error.uncertain:
                    intent = load(intent_path)
                    intent['certain_rejection'] = error.code
                    save(intent_path, intent)
                    ledger.release(reserved)
                log('submit_error_stopping', item=monster['id'], step=step, code=error.code, uncertain=error.uncertain)
                return False, None, {'error': error.code, 'uncertain': error.uncertain}
            task_id = data.get('task_id', '')
            if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', task_id):
                stop.set()
                log('submit_schema_error_stopping', item=monster['id'], step=step)
                return False, None, {'error': 'upstream_schema', 'uncertain': True}
            save(task_path, {'task_id': task_id})
            log('submit_response', item=monster['id'], step=step, task_id=task_id)
        task_id = load(task_path)['task_id']
        task, last, failures, state = None, None, 0, None
        for _ in range(900):
            try:
                task = await provider.task(task_id)
                failures = 0
            except ProviderError as error:
                failures += 1
                log('poll_error', item=monster['id'], step=step, code=error.code, consecutive=failures)
                if failures >= 12:
                    stop.set()
                    return False, task_id, {'error': 'poll_failed_resume_later'}
                await asyncio.sleep(10)
                continue
            state = task.get('status')
            if (state, task.get('progress')) != last and (state != 'running' or (task.get('progress') or 0) % 25 == 0):
                log('poll', item=monster['id'], step=step, status=state, progress=task.get('progress'))
            last = (state, task.get('progress'))
            if state in TERMINAL:
                break
            await asyncio.sleep(5)
        else:
            log('poll_timeout_resume_later', item=monster['id'], step=step, task_id=task_id)
            return False, task_id, {'error': 'poll_timeout_resume_later'}
    credits = task.get('credits_consumed')
    output = task.get('output') if isinstance(task.get('output'), dict) else {}
    log('task_final', item=monster['id'], step=step, task_id=task_id, status=state, credits_consumed=credits,
        output_fields=sorted(output), error_code=task.get('error_code'))
    ledger.settle(reserved, credits)
    if isinstance(credits, (int, float)) and credits > reserved:
        stop.set()
        log('cost_anomaly_stopping', item=monster['id'], step=step, credits_consumed=credits, reservation=reserved)
    result = {'id': monster['id'], 'step': step, 'task_id': task_id, 'status': state, 'credits_consumed': credits,
              'source_task': source_task, 'expected_credits': expected(step, monster)}
    if step == 'rigcheck':
        result.update(riggable=output.get('riggable'), rig_type=output.get('rig_type'))
    if state == 'success' and step != 'rigcheck':
        result.update(await download_outputs(step, monster, output, args))
    save(result_path, result)
    return state == 'success', task_id, result


async def download_outputs(step, monster, output, args):
    """Download model (+ preview for gen) into the raw dir; never store URLs."""
    info = {}
    url = output.get('model_url') or ''
    raw = args.raw_dir / monster['id']
    raw.mkdir(parents=True, exist_ok=True)
    try:
        blob = await fetch(url, 150 * 1024 * 1024)
        info['download_host'] = urlparse(url).hostname
        info['raw_bytes'] = len(blob)
        info['raw_sha256'] = hashlib.sha256(blob).hexdigest()
        if step == 'gen':
            stats = {}
            try:
                validate_glb(blob, allow_textures=True, stats=stats)
                info['validate_glb'] = 'ok'
                info.update({k: stats.get(k) for k in ('vertices', 'draw_calls', 'texture_pixels')})
            except ProviderError as error:
                info['validate_glb'] = error.code
        (raw / (step + '.glb')).write_bytes(blob)
        info['raw_file'] = (raw / (step + '.glb')).name
        if step != 'gen':
            try:
                info['rig_validation'] = validate_rigged(blob)
            except ProviderError as error:
                info['rig_validation'] = {'error': error.code}
    except ProviderError as error:
        info['download_error'] = error.code
        log('download_error_resume_safe', item=monster['id'], step=step, code=error.code)
    if step == 'gen':
        preview = output.get('rendered_image_url') or output.get('generated_image_url')
        if preview:
            try:
                image = await fetch(preview, 16 * 1024 * 1024)
                extension = {b'RIFF': 'webp', b'\x89PNG': 'png'}.get(image[:4], 'jpg')
                PREVIEWS.mkdir(parents=True, exist_ok=True)
                (PREVIEWS / ('%s.%s' % (monster['id'], extension))).write_bytes(image)
                info['preview'] = 'tripo_previews/%s.%s' % (monster['id'], extension)
            except ProviderError as error:
                log('preview_download_error', item=monster['id'], code=error.code)
    return info


async def run_chain(monster, provider, ledger, stop, semaphore, args):
    source = None
    summary = {'id': monster['id'], 'steps': {}}
    steps = steps_for(monster, args.until)
    for step in [s for s in steps if not s.startswith('anim')]:
        ok, task_id, result = await run_step(step, monster, source, provider, ledger, stop, semaphore, args)
        summary['steps'][step] = {'ok': ok, 'credits': result.get('credits_consumed'), 'error': result.get('error')}
        if not ok:
            summary['stopped_at'] = step
            return summary
        if step == 'rigcheck':
            if not result.get('riggable'):
                log('not_riggable', item=monster['id'], rig_type=result.get('rig_type'))
                summary['stopped_at'] = 'rigcheck_not_riggable'
                return summary
            if result.get('rig_type') and result['rig_type'] != SPECIES[monster['species']]['rig']:
                log('rig_type_suggestion_differs', item=monster['id'], suggested=result['rig_type'],
                    planned=SPECIES[monster['species']]['rig'])
            continue  # rig uses the generation task, not the check task
        source = task_id
    anims = [s for s in steps if s.startswith('anim')]
    # Every clip retargets the same rig task independently.
    outcomes = await asyncio.gather(*(run_step(step, monster, source, provider, ledger, stop, semaphore, args)
                                      for step in anims))
    for step, (ok, task_id, result) in zip(anims, outcomes):
        summary['steps'][step] = {'ok': ok, 'credits': result.get('credits_consumed'), 'error': result.get('error')}
    summary['complete'] = all(v['ok'] for v in summary['steps'].values())
    return summary


async def redownload(selected, provider, args):
    """Fetch raw outputs again for finished tasks (free GETs)."""
    for monster in selected:
        for step in ['gen', 'rig'] + [s for s in steps_for(monster) if s.startswith('anim')]:
            result_path = JOBS / monster['id'] / step / 'result.json'
            if not result_path.exists() or load(result_path).get('status') != 'success':
                continue
            if (args.raw_dir / monster['id'] / (step + '.glb')).exists():
                continue
            task = await provider.task(load(result_path)['task_id'])
            output = task.get('output') if isinstance(task.get('output'), dict) else {}
            info = await download_outputs(step, monster, output, args)
            result = load(result_path)
            result.update({k: v for k, v in info.items() if k != 'preview'})
            result.pop('download_error', None) if 'download_error' not in info else None
            save(result_path, result)
            log('redownloaded', item=monster['id'], step=step, bytes=info.get('raw_bytes'), error=info.get('download_error'))


def credit_table():
    rows, total = [], 0.0
    for monster in MONSTERS:
        row = {'id': monster['id']}
        for step in steps_for(monster) + ['anim']:
            path = JOBS / monster['id'] / step / 'result.json'
            if not path.exists() and step == 'anim':
                continue
            value = load(path).get('credits_consumed') if path.exists() else None
            row[step] = value
            total += float(value or 0)
        rows.append(row)
    return rows, total


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--key-file', type=Path, default=Path.home() / 'Desktop/tripo_key.txt')
    parser.add_argument('--only', nargs='+', choices=sorted(BY_ID))
    parser.add_argument('--variant', nargs='+', choices=VARIANTS)
    parser.add_argument('--until', choices=STEPS, default='anim')
    parser.add_argument('--max-credits', type=float, default=3000)
    parser.add_argument('--concurrency', type=int, default=3, choices=(1, 2, 3))
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'output/monsters_raw')
    parser.add_argument('--dry-run', action='store_true', help='print plan and projected credits; no API calls')
    parser.add_argument('--retry-failed', action='store_true', help='resubmit steps whose task finished as failed')
    parser.add_argument('--retry-rejected', action='store_true', help='resubmit certainly rejected (never created) steps')
    parser.add_argument('--redownload', action='store_true', help='re-fetch raw outputs of finished tasks (free)')
    parser.add_argument('--credits', action='store_true', help='print the per-step credit table from disk')
    args = parser.parse_args()
    args.raw_dir = args.raw_dir.resolve()
    selected = [BY_ID[i] for i in args.only] if args.only else list(MONSTERS)
    if args.variant:
        selected = [m for m in selected if m['variant'] in args.variant]
    for monster in selected:
        prompt_for(monster)
    if args.credits:
        rows, total = credit_table()
        for row in rows:
            print(json.dumps(row))
        print(json.dumps({'total_credits_consumed': total}))
        return
    planned = sum(expected(s, m) for m in selected for s in steps_for(m, args.until)
                  if not (JOBS / m['id'] / s / 'result.json').exists())
    worst = sum(reservation(s, m) for m in selected for s in steps_for(m, args.until)
                if not (JOBS / m['id'] / s / 'result.json').exists())
    if args.dry_run:
        for monster in selected:
            spec = SPECIES[monster['species']]
            todo = [s for s in steps_for(monster, args.until) if not (JOBS / monster['id'] / s / 'result.json').exists()]
            print(json.dumps({'id': monster['id'], 'rig': spec['rig'], 'faces': spec['faces'],
                              'prompt_chars': len(prompt_for(monster)), 'todo': {s: expected(s, monster) for s in todo}},
                             ensure_ascii=False))
        print(json.dumps({'monsters': len(selected), 'until': args.until, 'expected_new_credits': planned,
                          'worst_case_reserved': worst, 'already_committed': Ledger(args.max_credits).committed,
                          'cap': args.max_credits}))
        return
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(args.key_file)))
    if args.redownload:
        await redownload(selected, provider, args)
        return
    ledger = Ledger(args.max_credits)
    balance_start = await provider.balance()
    log('run_start', items=[m['id'] for m in selected], until=args.until, expected_credits=planned,
        worst_case=worst, cap=args.max_credits, already_committed=ledger.committed, balance=balance_start,
        concurrency=args.concurrency)
    if balance_start < worst + 100:
        log('balance_too_low_abort', balance=balance_start, needed=worst + 100)
        return
    stop = asyncio.Event()
    semaphore = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*(run_chain(m, provider, ledger, stop, semaphore, args) for m in selected))
    balance_end = await provider.balance()
    rows, total = credit_table()
    summary = {'results': results, 'ledger_committed_total': ledger.committed, 'credits_consumed_all_runs': total,
               'balance_start': balance_start, 'balance_end': balance_end,
               'balance_delta_shared_account': balance_start - balance_end, 'stopped_early': stop.is_set()}
    log('run_end', **summary)
    save(OUT_ART / 'run-summary.json', summary)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (ProviderError, ValueError) as error:
        print(json.dumps({'error': error.code if isinstance(error, ProviderError) else str(error),
                          'automatic_resubmit': False}), flush=True)
        sys.exit(1)
