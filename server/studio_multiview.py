"""One approved character reference -> consistent four views -> one 3D mesh."""
import base64
import json
from . import rig_rules, tripo_budget
from .provider import ProviderError
from .craft_moderation import Refused

CREDITS = 10
VIEWS = ('front', 'left', 'back', 'right')
STATES = ('multiview_generating', 'multiview_ready')


def cost(body, count=1, source=True):
    return CREDITS if (body.multiview and body.geometry == 'tripo' and count == 1
                       and source and rig_rules.character_like(body.prompt)) else 0


def output_views(output):
    # The live API nests this object; the documentation also shows a flat output.
    value = output.get('generate_multiview_image', output) if isinstance(output, dict) else {}
    if not isinstance(value, dict):raise ProviderError('upstream_schema', uncertain=True)
    urls = {view: value.get(view+'_view_url') for view in VIEWS}
    if not all(isinstance(url, str) and url for url in urls.values()):
        raise ProviderError('upstream_schema', uncertain=True)
    return urls


def local_image(studio, filename):
    path = studio.assets / filename
    if path.parent.resolve() != studio.assets.resolve() or not path.is_file() or path.stat().st_size > 6*1024*1024:
        raise ProviderError('multiview_reference_missing')
    return 'data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()


async def advance(studio, job, body, parts, part_id, quote):
    """True when this worker tick handled a view step; false when mesh work may proceed."""
    entry = parts[part_id]
    source = bool(entry.get('use_concept') and entry.get('concept_task') or body.image)
    if not cost(body, len(parts), source) or entry['state'] == 'multiview_ready':return False
    if entry['state'] in ('pending', 'image_ready'):
        # A retained successful task survives a mesh retry; never pay for the views twice.
        if entry.get('multiview_task') and entry.get('multiview_files'):
            entry['state'] = 'multiview_ready'
            return False
        studio.guard_tripo_cap(job, parts)
        needed = studio.remaining_build(job, parts)
        provider = studio.provider_for(entry['key']) if entry.get('key') else await studio.pick_provider(needed)
        if await provider.balance()-needed < studio.settings.credit_reserve:
            raise ProviderError('insufficient_provider_credit')
        entry['key'] = getattr(provider, 'fingerprint', '')
        if entry.get('use_concept'):
            reference = local_image(studio, quote.get('concept', {}).get('file', ''))
        elif entry.get('image_task'):
            reference = local_image(studio, entry.get('refined_file', ''))
        else:reference = body.image
        uploaded = await provider.upload_image(reference)
        attempt = studio.reserve_build(job, parts, quote, part_id, 'multiview', CREDITS, provider)
        data = await provider.request('POST', '/generation/image-to-multiview', {'input': uploaded})
        task = data.get('task_id')
        if not isinstance(task, str) or not task or len(task)>200 or '/' in task:
            raise ProviderError('upstream_schema', uncertain=True)
        with studio.db.transaction() as conn:tripo_budget.record_task(conn, attempt, task, studio.clock())
        entry.update(state='multiview_generating', multiview_task=task, submitted=studio.clock())
        entry.pop('progress', None)
        quote['multiview'] = {'enabled': True, 'views': list(VIEWS), 'estimated_credits': CREDITS}
        studio.update(job['id'], state='building', parts=json.dumps(parts), provenance=json.dumps(quote))
        return True
    if entry['state'] != 'multiview_generating':return False
    provider = studio.provider_for(entry.get('key'))
    result = await provider.task(entry['multiview_task'])
    studio.record_attempt(entry.get('multiview_attempt'), result)
    if result.get('credits_consumed') is not None:
        entry['multiview_credits_consumed'] = result['credits_consumed']
        studio.record_build_bill(job, parts)
    if result.get('status') in ('queued', 'running'):
        from .asset_studio import track
        track(entry, result);studio.overdue(parts)
    elif result.get('status') == 'banned':raise Refused('other')
    elif result.get('status') in ('failed', 'cancelled', 'expired'):
        raise ProviderError('multiview_failed')
    elif result.get('status') != 'success':raise ProviderError('upstream_schema', uncertain=True)
    else:
        urls = output_views(result.get('output'))
        files = entry.setdefault('multiview_files', {})
        # Download through the provider's allowlist/size checks, retaining local images for restart.
        for view, url in urls.items():
            if view in files and (studio.assets/files[view]).is_file():continue
            blob = await provider.fetch_image(url)
            name = job['id']+'-'+part_id+'-'+view+'.jpg'
            target = studio.assets/name
            temporary = target.with_suffix('.tmp');temporary.write_bytes(blob);temporary.replace(target)
            files[view] = name
            studio.update(job['id'], parts=json.dumps(parts))
        entry.update(state='multiview_ready');entry.pop('progress', None)
    studio.update(job['id'], state='building', parts=json.dumps(parts))
    return True


async def mesh_inputs(studio, provider, entry):
    # File tokens avoid signed result URL expiry and work with H and P series alike.
    return [{view: await provider.upload_image(local_image(studio, entry['multiview_files'][view]))}
            for view in VIEWS]
