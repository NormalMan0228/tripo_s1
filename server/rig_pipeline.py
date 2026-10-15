"""One durable rig/animation transition per studio worker tick."""
import hashlib
import json

from . import rig_rules
from .provider import ProviderError
from .rigged_glb import merge_clips
from .stored_assets import read_glb

RIG_STATES = ('rig_pending', 'rigging', 'animation_pending', 'animating', 'animation_merge')


def rig_bill_entries(part):
    return [entry for entry in [part.get('rig', {}), *part.get('anims', {}).values()] if entry.get('task')]


async def advance_rig(studio, job, body, parts, part_id, provenance):
    entry = parts[part_id]
    provider = studio.provider_for(entry.get('key'))
    state = entry['state']
    def save(**changes):
        entry.update(changes)
        studio.update(job['id'], state='building', parts=json.dumps(parts), provenance=json.dumps(provenance), error=None)
    if state == 'animation_merge':
        return merge_clips({clip: read_glb(studio.assets, entry['anims'][clip]['file'], entry['anims'][clip]['sha256'])
                            for clip in rig_rules.CLIPS}, allow_textures=body.material == 'textured')
    if state in ('rig_pending', 'animation_pending'):
        if state == 'rig_pending':
            route, payload = '/animations/rig', rig_rules.rig_payload(entry['task'])
            task_entry = entry.setdefault('rig', {})
            next_state = 'rigging'
        else:
            clip = next(c for c in rig_rules.CLIPS if entry.get('anims', {}).get(c, {}).get('state') != 'ready')
            task_entry = entry.setdefault('anims', {}).setdefault(clip, {})
            route, payload = '/animations/retarget', rig_rules.animation_payload(entry['rig']['task'], clip)
            next_state = 'animating'
        # The same provider key owns the whole dependency chain. The complete estimate was
        # reserved at confirmation, before even the first mesh POST.
        studio.reserve_build(job, parts, provenance)
        studio.update(job['id'], state='submitting', parts=json.dumps(parts), provenance=json.dumps(provenance))
        result = await provider.request('POST', route, payload)
        task = result.get('task_id')
        if not isinstance(task, str) or not task or len(task) > 200 or '/' in task:
            raise ProviderError('upstream_schema', uncertain=True)
        task_entry.update(task=task, state='running')
        entry.pop('progress', None)
        save(state=next_state, submitted=studio.clock())
        return None
    if state == 'rigging':
        task_entry = entry['rig']
    else:
        clip = next(c for c, a in entry['anims'].items() if a.get('state') != 'ready')
        task_entry = entry['anims'][clip]
    studio.overdue(parts)
    result = await provider.task(task_entry['task'])
    if result.get('credits_consumed') is not None:
        task_entry['credits_consumed'] = result['credits_consumed']
        studio.record_build_bill(job, parts)
        save()
    status = result.get('status')
    if status in ('queued', 'running'):
        from .asset_studio import track
        track(entry, result)
        save()
        return None
    if status in ('failed', 'cancelled', 'banned', 'expired'):
        task_entry['state'] = 'failed'
        save()
        raise ProviderError('rig_failed' if state == 'rigging' else 'animation_failed')
    if status != 'success':
        raise ProviderError('upstream_schema', uncertain=True)
    if state == 'rigging':
        task_entry['state'] = 'ready'
        save(state='animation_pending', submitted=studio.clock())
        return None
    # Download failures retry this task, never generate/pay for it again.
    blob = await provider.download(result.get('output', {}).get('model_url', ''),
                                   allow_textures=body.material == 'textured', rigged=True)
    filename = job['id'] + '-' + part_id + '-' + clip + '.glb'
    target = studio.assets / filename
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(blob); temporary.replace(target)
    task_entry.update(state='ready', file=filename, sha256=hashlib.sha256(blob).hexdigest())
    complete = all(entry['anims'].get(c, {}).get('state') == 'ready' for c in rig_rules.CLIPS)
    save(state='animation_merge' if complete else 'animation_pending', submitted=studio.clock())
    return None
