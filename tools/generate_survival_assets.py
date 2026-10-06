"""Generate the survival map prop set with Tripo text-to-model (user-approved, hard-capped).

Same paid-call safety rules as tools/generate_interior_assets.py, whose pure helpers this reuses:
- An intent file is written before every paid POST; an item with an intent but no task id is never
  resubmitted automatically (ambiguous state). Certain rejections are marked so that an operator may
  retry them explicitly with --retry-rejected.
- Any provider error during submission stops all further submissions (in-flight tasks are still polled
  and downloaded; polling is a free GET).
- A credit ledger (actual credits for finished tasks, reservations for in-flight/uncertain ones) must stay
  within --max-credits (default 2000, this batch's cap) before a new task is submitted.
- The API key is read only via server.config.read_tripo_key and never logged.

Raw downloads land in artifacts/survival-assets/jobs/<id>/tripo-original.glb (local, deletable: a finished
task can be fetched again with --refetch while it exists). tools/build_survival_assets.py then turns them
into the game set under game/maps/survival/assets/ (gitignored; the manifest is tracked).
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import Settings, read_tripo_key  # noqa: E402
from server.provider import TripoProvider, ProviderError, validate_glb  # noqa: E402

_spec = importlib.util.spec_from_file_location('interior_tools', ROOT / 'tools/generate_interior_assets.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

OUT_ART = ROOT / 'artifacts/survival-assets'
JOBS = OUT_ART / 'jobs'
PREVIEWS = OUT_ART / 'previews'
LOG = OUT_ART / 'log.jsonl'

H3, P2 = base.H3, base.P2
EXPECTED = {H3: 20, P2: 110}
RESERVE = {H3: 30, P2: 130}

STYLE = ('Single isolated game-ready 3D object for a colorful storybook island survival adventure game with adult '
         '1.70m cartoon people, seen from above at an angle. High quality smooth 3D cartoon sculpt like Animal '
         'Crossing and Zelda Wind Waker: rounded bevels, chunky friendly proportions, clean solid geometry, warm '
         'hand-painted matte materials with subtle grain. One complete object, centered and upright. No ground '
         'plane, no terrain base, no background, no people, no text, letters, numbers or logos. ')
NEGATIVE = ('ground plane, terrain, floor, scenery, background, humans, text, letters, numbers, logos, thin paper '
            'surfaces, flat billboard leaves, jagged low poly, holes, floating parts, multiple separate objects')

# id, map, model, faces, size (x, y, z metres), measure, description
ITEMS = [
    # ---------------------------------------------------------------- forest (솔바람 숲)
    dict(id='pine_tall', map='forest', model=H3, faces=10000, size=(3.4, 7.0, 3.4), measure=('height', 7.0),
         text='A tall storybook pine tree, 7m tall. A straight warm brown trunk visible at the base, five overlapping '
              'tiers of drooping rounded needle boughs in deep forest green with lighter moss-green tips, slightly '
              'asymmetric scalloped tier edges, dense full volume and a soft rounded top point. Solid volumetric '
              'foliage, no flat cards, no snow, no cones on the ground.'),
    dict(id='oak_broad', map='forest', model=H3, faces=10000, size=(5.5, 6.0, 5.5), measure=('height', 6.0),
         text='A big old broadleaf oak tree, 6m tall with a wide crown. A thick gnarled warm brown trunk with soft '
              'green moss patches and a few short spreading roots, sturdy curved branches holding a broad clustered '
              'crown of many rounded dense leaf masses in deep green, olive and fresh green. Softly sculpted leafy '
              'clumps, large clean silhouette, trunk visible beneath. Solid volumetric foliage, no flat leaf cards.'),
    dict(id='birch_slim', map='forest', model=H3, faces=8000, size=(2.8, 5.5, 2.8), measure=('height', 5.5),
         text='A slender storybook birch tree, 5.5m tall. A white bark trunk with dark horizontal marks that forks '
              'into two thin upward branches, an airy rounded crown of clustered leaf masses in warm yellow-green, '
              'light green and a few golden tips. Solid volumetric foliage, no flat leaf cards.'),
    dict(id='bush_round', map='forest', model=H3, faces=4000, size=(1.6, 1.1, 1.6), measure=('height', 1.1),
         text='A dense rounded forest bush, 1.1m tall and 1.6m wide, made of clustered rounded leaf masses in deep '
              'green and fresh green with lighter tips. Solid volumetric leaves, no flowers, no berries.'),
    dict(id='berry_bush', map='forest', model=H3, faces=6000, size=(1.4, 1.2, 1.4), measure=('height', 1.2),
         text='A round wild berry bush, 1.2m tall and 1.4m wide. Dense dark green rounded leaf clusters dotted all over '
              'with many plump glossy bright red berries in small bunches, clearly visible on top and sides. Solid '
              'volumetric leaves, chunky berries.'),
    dict(id='fiber_grass', map='forest', model=H3, faces=5000, size=(1.0, 1.1, 1.0), measure=('height', 1.1),
         text='A tall clump of wild flax and fibrous grass, 1.1m tall. Many thick long gently curved blades in sage '
              'green and straw gold growing from one base, a few round seed heads on top, and a small twine-tied '
              'bundle of cut stems leaning at the base. Thick sculpted blades, no flat cards.'),
    dict(id='stone_pile', map='forest', model=H3, faces=5000, size=(1.6, 0.9, 1.4), measure=('longest_horizontal', 1.6),
         text='A pile of loose gatherable stones, 0.9m tall and 1.6m wide: several chunky rounded light grey granite '
              'rocks stacked together, a few flat slate pieces and pale flint chips, small moss specks. Solid chunky '
              'rocks.'),
    dict(id='fern_clump', map='forest', model=H3, faces=4000, size=(1.1, 0.7, 1.1), measure=('longest_horizontal', 1.1),
         text='A lush forest fern clump, 0.7m tall and 1.1m wide: arching thick sculpted fronds in fresh green and '
              'deep green radiating from the centre, curled fiddlehead tips. Solid fronds, no flat cards.'),
    dict(id='mushroom_cluster', map='forest', model=H3, faces=4000, size=(0.7, 0.5, 0.7), measure=('height', 0.5),
         text='A cluster of storybook forest mushrooms, 0.5m tall: three chunky mushrooms with rounded glossy red caps '
              'with cream spots and three smaller tan brown caps, thick cream stems, growing from a small mossy root.'),
    dict(id='fallen_log', map='forest', model=H3, faces=6000, size=(3.2, 0.7, 0.8), measure=('longest_horizontal', 3.2),
         text='A fallen mossy tree log lying on its side, 3.2m long and 0.6m thick. Warm brown furrowed bark, soft '
              'green moss patches on top, two small mushrooms and a broken branch stub, round cut ends showing pale '
              'tree rings. Solid log, not hollow.'),
    dict(id='tree_stump', map='forest', model=H3, faces=5000, size=(0.9, 0.6, 0.9), measure=('longest_horizontal', 0.9),
         text='A freshly cut tree stump, 0.55m tall and 0.8m diameter. A flat pale cut top showing tree rings, thick '
              'warm brown bark, a few short roots spreading at the base, a small patch of moss and two tiny '
              'mushrooms. Solid stump.'),
    dict(id='mossy_boulder', map='forest', model=H3, faces=6000, size=(3.0, 2.0, 2.6), measure=('longest_horizontal', 3.0),
         text='A large mossy granite boulder group, 2m tall and 3m wide: two big rounded grey rocks leaning together '
              'with one smaller rock, thick soft green moss caps on their tops, a few small ferns in the gaps. Solid '
              'massive rocks.'),
    dict(id='signpost', map='forest', model=H3, faces=3000, size=(1.0, 1.9, 0.6), measure=('height', 1.9),
         text='A rustic wooden direction signpost, 1.9m tall: one sturdy round post with three blank arrow-shaped '
              'plank signs pointing different directions, iron nails, and a small hanging lantern hook. Blank '
              'boards, no writing.'),
    dict(id='log_bench', map='forest', model=H3, faces=4000, size=(1.8, 0.5, 0.6), measure=('longest_horizontal', 1.8),
         text='A simple camp log bench, 1.8m long and 0.45m tall: a split half log seat with a flat pale top resting on '
              'two short round log stumps, warm brown bark.'),
    dict(id='camp_supplies', map='forest', model=H3, faces=6000, size=(1.6, 1.0, 1.0), measure=('longest_horizontal', 1.6),
         text="An explorer's camp supply pile, 1.6m wide and 1m tall: two wooden crates, a rolled green bedroll tied "
              'with straps, a canvas backpack with a tin cup, a small black cooking pot and a coil of rope. No labels.'),
    dict(id='firewood_pile', map='forest', model=H3, faces=5000, size=(1.4, 0.8, 0.8), measure=('longest_horizontal', 1.4),
         text='A neat stack of split firewood logs, 1.4m long and 0.8m tall, pale split faces and brown bark, with a '
              'small hatchet stuck in a round chopping block beside the stack.'),
    dict(id='forest_ruin', map='forest', model=P2, faces=16000, size=(4.0, 3.4, 1.4), measure=('longest_horizontal', 4.0),
         text='An ancient overgrown stone ruin archway, 3.4m tall and 4m wide: two weathered mossy grey stone pillars '
              'joined by a rounded carved arch with a keystone, a few fallen stone blocks at the base, ivy vines and '
              'soft moss draping over the top, tiny blue flowers in the cracks. Solid stones, no symbols.'),
    # ---------------------------------------------------------------- quarry (노을 채석장)
    dict(id='sandstone_cliff', map='quarry', model=H3, faces=8000, size=(4.0, 3.0, 3.0), measure=('longest_horizontal', 4.0),
         text='A terraced sandstone rock outcrop, 3m tall and 4m wide: stacked horizontal layers of warm orange, peach '
              'and terracotta sandstone with rounded weathered ledges, deep shadowed cracks between the strata and a '
              'flat top. One solid massive rock formation.'),
    dict(id='sandstone_boulder', map='quarry', model=H3, faces=5000, size=(2.0, 1.4, 1.7), measure=('longest_horizontal', 2.0),
         text='A rounded weathered red sandstone boulder, 1.4m tall and 2m wide, with soft horizontal strata lines in '
              'rust, peach and cream, a few chips and pebbles at its base. Solid rock.'),
    dict(id='cut_blocks', map='quarry', model=H3, faces=5000, size=(2.0, 1.4, 1.4), measure=('longest_horizontal', 2.0),
         text='A stack of cut quarry stone blocks, 2m wide and 1.4m tall: four big rectangular cream and peach '
              'sandstone blocks with chisel marks stacked unevenly, one wooden wedge and a short rope sling.'),
    dict(id='mine_cart', map='quarry', model=H3, faces=6000, size=(1.0, 1.1, 1.6), measure=('longest_horizontal', 1.6),
         text='A wooden mine cart on a short straight piece of rail track, 1.6m long and 1.1m tall: a chunky wooden '
              'plank body with dark iron corner bands and four iron wheels, filled with grey stones and glowing '
              'orange ore chunks.'),
    dict(id='quarry_crane', map='quarry', model=P2, faces=16000, size=(3.0, 5.0, 3.0), measure=('height', 5.0),
         text='A wooden quarry derrick crane, 5m tall: a sturdy timber A-frame tower with crossed braces and iron '
              'bolts, a long angled wooden boom arm with a rope pulley and hook lifting one cut sandstone block, and a '
              'hand-crank winch drum with coiled rope at the base.'),
    dict(id='dead_tree', map='quarry', model=H3, faces=6000, size=(2.8, 4.5, 2.8), measure=('height', 4.5),
         text='A bare twisted dead tree, 4.5m tall: smooth silver-grey and pale brown weathered wood, a gnarled trunk '
              'splitting into a few thick curling leafless branches, short dry roots. Chunky smooth branches.'),
    dict(id='dry_shrub', map='quarry', model=H3, faces=4000, size=(1.2, 0.8, 1.2), measure=('longest_horizontal', 1.2),
         text='A dry hardy desert shrub, 0.8m tall and 1.2m wide: a rounded tangle of short woody twigs with dense '
              'clusters of small rusty orange, ochre and olive leaves. Solid volumetric leaf clusters.'),
    dict(id='ember_rock', map='quarry', model=H3, faces=5000, size=(1.8, 1.2, 1.6), measure=('longest_horizontal', 1.8),
         text='A dark volcanic basalt rock cluster, 1.2m tall and 1.8m wide: rough charcoal black stone split by bright '
              'glowing orange and red lava cracks, small ember-coloured crystals in the seams. Solid rock.'),
    dict(id='tool_rack', map='quarry', model=H3, faces=6000, size=(1.6, 1.6, 0.8), measure=('longest_horizontal', 1.6),
         text="A quarry workers' tool station, 1.6m wide: a wooden A-frame rack holding two pickaxes, a shovel and a "
              'sledgehammer, a small open wooden crate of chisels in front and a brass lantern hanging from the top.'),
    # ---------------------------------------------------------------- frost (서리빛 분지)
    dict(id='snow_pine', map='frost', model=H3, faces=10000, size=(3.4, 6.5, 3.4), measure=('height', 6.5),
         text='A storybook snowy pine tree, 6.5m tall: tiers of drooping deep teal-green needle boughs, each tier '
              'topped with thick soft rounded white snow caps, a short brown trunk at the base and a snow-covered '
              'top point. Solid volumetric foliage and snow, no flat cards.'),
    dict(id='ice_crystal', map='frost', model=H3, faces=5000, size=(1.2, 1.6, 1.2), measure=('height', 1.6),
         text='A cluster of large ice crystals, 1.6m tall: six chunky faceted pale cyan and light blue crystal spikes of '
              'different heights growing from a small frosted grey rock base, bright cool highlights.'),
    dict(id='snow_boulder', map='frost', model=H3, faces=5000, size=(2.4, 1.6, 2.0), measure=('longest_horizontal', 2.4),
         text='A large grey granite boulder, 1.6m tall and 2.4m wide, with a thick smooth rounded white snow cap on top '
              'and a few short icicles along one edge. Solid rock.'),
    dict(id='frost_shrub', map='frost', model=H3, faces=4000, size=(1.2, 0.9, 1.2), measure=('longest_horizontal', 1.2),
         text='A frosty winter shrub, 0.9m tall and 1.2m wide: rounded clusters of pale blue-green leaves dusted with '
              'snow on top and bunches of bright blue frost berries. Solid volumetric leaves.'),
    dict(id='snowman', map='frost', model=H3, faces=4000, size=(0.9, 1.5, 0.9), measure=('height', 1.5),
         text='A cheerful storybook snowman, 1.5m tall: three stacked snowballs, a carrot nose, coal eyes, a coal smile '
              'and buttons, two stick arms, a knitted red scarf and a small dark bucket hat.'),
    dict(id='sled', map='frost', model=H3, faces=5000, size=(0.8, 0.9, 1.6), measure=('longest_horizontal', 1.6),
         text="A wooden explorer's sled, 1.6m long, with curved front runners, loaded with a strapped canvas bundle, a "
              'small wooden crate, a hanging lantern and a pair of round snowshoes.'),
    # The first sled came back with a small figure riding it; this one asks for an empty sled.
    dict(id='sled_empty', map='frost', model=H3, faces=5000, size=(0.8, 0.7, 1.6), measure=('longest_horizontal', 1.6),
         text="An empty wooden explorer's cargo sled, 1.6m long, with two curved front runners, loaded only with a "
              'strapped canvas bundle, a small wooden crate and a pair of round snowshoes. Nobody on it: no person, '
              'no figure, no doll, no animal, no lantern pole.'),
    dict(id='snow_fence', map='frost', model=H3, faces=4000, size=(2.4, 1.1, 0.4), measure=('longest_horizontal', 2.4),
         text='A weathered wooden snow fence section, 2.4m long and 1.1m tall: vertical grey-brown slats tied to two '
              'rails with rope, soft snow piled along the top rail.'),
    dict(id='frost_shrine', map='frost', model=P2, faces=16000, size=(1.6, 3.0, 1.6), measure=('height', 3.0),
         text='An ancient frozen stone lantern shrine, 3m tall: a stacked grey stone lantern pagoda with a curved '
              'rounded roof cap heavy with snow, icicles hanging from the eaves, a lantern window, pale blue ice '
              'crystals growing at its base and one small stone step. Solid stone, no symbols.'),
]
BY_ID = {item['id']: item for item in ITEMS}
TERMINAL = base.TERMINAL


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def log(event, **fields):
    OUT_ART.mkdir(parents=True, exist_ok=True)
    entry = {'time': now(), 'event': event, **fields}
    with LOG.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(json.dumps(entry, ensure_ascii=False), flush=True)


save, load = base.save, base.load


def prompt_for(item):
    prompt = STYLE + item['text']
    if len(prompt) > 1024:
        raise ValueError('prompt_too_long:' + item['id'])
    return prompt


def payload_for(item):
    payload = {'model': item['model'], 'prompt': prompt_for(item), 'face_limit': item['faces'],
               'quad': False, 'texture': True, 'pbr': True, 'export_uv': True}
    if item['model'] == P2:
        payload['negative_prompt'] = NEGATIVE
    return payload


def recorded_spend(item_id):
    job = JOBS / item_id
    total = 0.0
    for folder in [job, *sorted(job.glob('attempt-*'))] if job.exists() else []:
        result, intent = folder / 'result.json', folder / 'intent.json'
        if result.exists():
            credits = load(result).get('credits_consumed')
            total += float(credits) if isinstance(credits, (int, float)) else 0.0
        elif intent.exists():
            data = load(intent)
            if not data.get('certain_rejection'):
                total += float(data.get('reservation', RESERVE[P2]))
    return total


class Ledger(base.Ledger):
    def __init__(self, cap):
        self.cap = cap
        self.committed = sum(recorded_spend(item['id']) for item in ITEMS)


def finalize_raw(item, raw, result):
    """Validate the raw provider GLB (no game copy yet: build_survival_assets.py processes it)."""
    stats = {}
    try:
        doc = validate_glb(raw, allow_textures=True, stats=stats)
    except ProviderError as error:
        log('validate_failed', item=item['id'], code=error.code, bytes=len(raw))
        result.update(status='invalid_model', bytes=len(raw))
        return False
    extent, triangles = base.scene_bounds(doc)
    result.update(raw_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), vertices=stats.get('vertices'),
                  texture_pixels=stats.get('texture_pixels'), triangles=triangles, source_extent=extent)
    log('validated_raw', item=item['id'], bytes=len(raw), triangles=triangles, extent=extent)
    return True


async def run_item(item, provider, ledger, stop, semaphore, args):
    item_id = item['id']
    job = JOBS / item_id
    job.mkdir(parents=True, exist_ok=True)
    intent_path, task_path, result_path = job / 'intent.json', job / 'task.json', job / 'result.json'
    if result_path.exists():
        previous = load(result_path)
        if previous.get('status') == 'success':
            return {'id': item_id, 'ok': True, 'skipped': 'already_generated'}
        if not args.retry_failed:
            return {'id': item_id, 'ok': False, 'error': 'previous_' + str(previous.get('status'))}
        archive = job / ('attempt-%d' % (len(list(job.glob('attempt-*'))) + 1))
        archive.mkdir()
        for name in ('intent.json', 'task.json', 'result.json', 'request.json'):
            if (job / name).exists():
                (job / name).rename(archive / name)
        log('archived_failed_attempt', item=item_id, folder=archive.name)
    async with semaphore:
        reservation = RESERVE[item['model']]
        if not task_path.exists():
            if intent_path.exists():
                intent = load(intent_path)
                if intent.get('certain_rejection') and args.retry_rejected:
                    archive = job / ('attempt-%d' % (len(list(job.glob('attempt-*'))) + 1))
                    archive.mkdir()
                    for name in ('intent.json', 'request.json'):
                        if (job / name).exists():
                            (job / name).rename(archive / name)
                else:
                    log('ambiguous_intent_no_resubmit', item=item_id)
                    return {'id': item_id, 'ok': False, 'error': 'ambiguous_intent_no_resubmit'}
            # A 429 is a certain, uncharged rejection (the account's concurrent-task limit is shared with
            # other batches): archive it, back off and submit again. Every other error stops the run.
            for rate_attempt in range(8):
                if stop.is_set():
                    return {'id': item_id, 'ok': False, 'error': 'not_submitted_after_stop'}
                if not ledger.try_reserve(reservation):
                    log('budget_cap_reached', item=item_id, committed=ledger.committed, cap=ledger.cap)
                    return {'id': item_id, 'ok': False, 'error': 'budget_cap'}
                payload = payload_for(item)
                save(job / 'request.json', payload)
                with intent_path.open('x', encoding='utf-8') as handle:
                    json.dump({'time': time.time(), 'model': item['model'], 'reservation': reservation,
                               'automatic_resubmit': False}, handle)
                log('submit_request', item=item_id, model=item['model'], face_limit=item['faces'],
                    prompt_chars=len(payload['prompt']), committed_with_reservation=ledger.committed)
                try:
                    data = await provider.request('POST', '/generation/text-to-model', payload)
                    break
                except ProviderError as error:
                    if not error.uncertain:
                        intent = load(intent_path)
                        intent['certain_rejection'] = error.code
                        save(intent_path, intent)
                        ledger.release(reservation)
                    if error.code == 'upstream_rate_limit' and not error.uncertain and rate_attempt < 7:
                        archive = job / ('attempt-%d' % (len(list(job.glob('attempt-*'))) + 1))
                        archive.mkdir()
                        for name in ('intent.json', 'request.json'):
                            if (job / name).exists():
                                (job / name).rename(archive / name)
                        log('rate_limited_backoff', item=item_id, attempt=rate_attempt + 1)
                        await asyncio.sleep(40 + 20 * rate_attempt)
                        continue
                    stop.set()
                    log('submit_error_stopping', item=item_id, code=error.code, uncertain=error.uncertain)
                    return {'id': item_id, 'ok': False, 'error': error.code, 'uncertain': error.uncertain}
            task_id = data.get('task_id', '')
            if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', task_id):
                stop.set()
                log('submit_schema_error_stopping', item=item_id)
                return {'id': item_id, 'ok': False, 'error': 'upstream_schema', 'uncertain': True}
            save(task_path, {'task_id': task_id})
            log('submit_response', item=item_id, task_id=task_id)
        task_id = load(task_path)['task_id']
        last, failures, task, state = None, 0, None, None
        for _ in range(720):
            try:
                task = await provider.task(task_id)
                failures = 0
            except ProviderError as error:
                failures += 1
                log('poll_error', item=item_id, code=error.code, consecutive=failures)
                if failures >= 12:
                    stop.set()
                    return {'id': item_id, 'ok': False, 'error': 'poll_failed_resume_later', 'task_id': task_id}
                await asyncio.sleep(10)
                continue
            state = task.get('status')
            if (state, task.get('progress')) != last:
                last = (state, task.get('progress'))
                if state in TERMINAL or task.get('progress') in (0, 50, 100):
                    log('poll', item=item_id, status=state, progress=task.get('progress'))
            if state in TERMINAL:
                break
            await asyncio.sleep(5)
        else:
            log('poll_timeout_resume_later', item=item_id, task_id=task_id)
            return {'id': item_id, 'ok': False, 'error': 'poll_timeout_resume_later', 'task_id': task_id}
    credits = task.get('credits_consumed')
    output = task.get('output') if isinstance(task.get('output'), dict) else {}
    log('task_final', item=item_id, task_id=task_id, status=state, credits_consumed=credits,
        error_code=task.get('error_code'))
    ledger.settle(reservation, credits)
    if isinstance(credits, (int, float)) and credits > reservation:
        stop.set()
        log('cost_anomaly_stopping', item=item_id, credits_consumed=credits, reservation=reservation)
    result = {'id': item_id, 'task_id': task_id, 'status': state, 'model': item['model'], 'credits_consumed': credits}
    if state != 'success':
        save(result_path, result)
        return {'id': item_id, 'ok': False, 'error': 'task_' + str(state), 'credits_consumed': credits}
    try:
        raw = await base.fetch(output.get('model_url', ''), 64 * 1024 * 1024)
    except ProviderError as error:
        log('download_error_resume_safe', item=item_id, code=error.code)
        return {'id': item_id, 'ok': False, 'error': 'download_' + error.code, 'task_id': task_id}
    (job / 'tripo-original.glb').write_bytes(raw)
    if not finalize_raw(item, raw, result):
        save(result_path, result)
        return {'id': item_id, 'ok': False, 'error': 'invalid_model', 'credits_consumed': credits}
    preview_url = output.get('rendered_image_url') or output.get('generated_image_url')
    if preview_url:
        try:
            image = await base.fetch(preview_url, 16 * 1024 * 1024)
            extension = {b'RIFF': 'webp', b'\x89PNG': 'png'}.get(image[:4], 'jpg')
            PREVIEWS.mkdir(parents=True, exist_ok=True)
            (PREVIEWS / ('%s.%s' % (item_id, extension))).write_bytes(image)
            result['preview'] = 'previews/%s.%s' % (item_id, extension)
        except ProviderError as error:
            log('preview_download_error', item=item_id, code=error.code)
    save(result_path, result)
    return {'id': item_id, 'ok': True, 'model': item['model'], 'credits_consumed': credits}


async def refetch(items, provider):
    """Download raw GLBs again for finished tasks (free GETs) after local copies were deleted."""
    for item in items:
        result_path = JOBS / item['id'] / 'result.json'
        if not result_path.exists() or (JOBS / item['id'] / 'tripo-original.glb').exists():
            continue
        result = load(result_path)
        if result.get('status') != 'success':
            continue
        task = await provider.task(result['task_id'])
        output = task.get('output') if isinstance(task.get('output'), dict) else {}
        raw = await base.fetch(output.get('model_url', ''), 64 * 1024 * 1024)
        (JOBS / item['id'] / 'tripo-original.glb').write_bytes(raw)
        log('refetched', item=item['id'], bytes=len(raw))


def ledger_report():
    rows = []
    for item in ITEMS:
        path = JOBS / item['id'] / 'result.json'
        if path.exists():
            data = load(path)
            rows.append({'id': item['id'], 'map': item['map'], 'model': 'P2' if item['model'] == P2 else 'H3',
                         'status': data.get('status'), 'credits': data.get('credits_consumed'),
                         'task_id': data.get('task_id')})
    total = sum(float(r['credits'] or 0) for r in rows)
    committed = sum(recorded_spend(item['id']) for item in ITEMS)
    return {'items': rows, 'credits_consumed': total, 'ledger_committed': committed}


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--key-file', type=Path, default=Path.home() / 'Desktop/tripo_key.txt')
    parser.add_argument('--only', nargs='+', choices=sorted(BY_ID))
    parser.add_argument('--max-credits', type=float, default=2000)
    parser.add_argument('--concurrency', type=int, default=3, choices=(1, 2, 3))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--retry-rejected', action='store_true')
    parser.add_argument('--refetch', action='store_true', help='re-download raw GLBs of finished tasks (free)')
    parser.add_argument('--report', action='store_true', help='print the credit ledger only')
    args = parser.parse_args()
    if args.max_credits > 2000:
        raise ValueError('cap_above_approved_2000')
    selected = [BY_ID[i] for i in args.only] if args.only else ITEMS
    for item in selected:
        payload_for(item)
    if args.report:
        print(json.dumps(ledger_report(), indent=1))
        return
    planned = sum(EXPECTED[item['model']] for item in selected)
    worst = sum(RESERVE[item['model']] for item in selected)
    if args.dry_run:
        for item in selected:
            print(json.dumps({'id': item['id'], 'map': item['map'], 'model': item['model'], 'faces': item['faces'],
                              'prompt_chars': len(prompt_for(item))}))
        print(json.dumps({'items': len(selected), 'expected_credits': planned, 'worst_case_reserved': worst,
                          'already_committed': Ledger(args.max_credits).committed, 'cap': args.max_credits}))
        return
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(args.key_file)))
    if args.refetch:
        await refetch(selected, provider)
        return
    ledger = Ledger(args.max_credits)
    balance_start = await provider.balance()
    log('run_start', items=[item['id'] for item in selected], expected_credits=planned, cap=args.max_credits,
        already_committed=ledger.committed, balance=balance_start, concurrency=args.concurrency)
    if balance_start < worst + 100:
        log('balance_too_low_abort', balance=balance_start, needed=worst + 100)
        return
    stop = asyncio.Event()
    semaphore = asyncio.Semaphore(args.concurrency)
    order = sorted(selected, key=lambda item: item['model'] != P2)
    results = await asyncio.gather(*(run_item(item, provider, ledger, stop, semaphore, args) for item in order))
    balance_end = await provider.balance()
    spent = sum(float(r.get('credits_consumed') or 0) for r in results)
    summary = {'results': results, 'credits_consumed_this_run': spent, 'ledger_committed_total': ledger.committed,
               'balance_start': balance_start, 'balance_end': balance_end, 'stopped_early': stop.is_set()}
    log('run_end', **summary)
    save(OUT_ART / 'run-summary.json', summary)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (ProviderError, ValueError) as error:
        print(json.dumps({'error': error.code if isinstance(error, ProviderError) else str(error),
                          'automatic_resubmit': False}), flush=True)
        sys.exit(1)
