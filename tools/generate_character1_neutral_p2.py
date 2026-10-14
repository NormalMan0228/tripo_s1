"""Optional P2 multiview generation of character1 in its neutral closed-mouth pose (gated, resumable).

Inputs are the front/left/right renders of the rigged neutral face in
art/references/character1_neutral_v1 (left = nose pointing image-left, as in prior approved sets).

Gates (no paid call happens unless all pass):
  * production-plan.json: reference_approved == true, and user_authorization filled in by the user
  * reference SHA-256 must match the reviewed files
  * the plan's own credit cap (separate from older ledgers) must cover the reservation
Operations: balance (free, read-only) | submit | poll.  No automatic resubmission.
"""
import argparse, asyncio, hashlib, json, re, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(R), str(R / 'tools')]
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from generate_dev_character import upload
from generate_hd_character_restart import save
import generate_fullbody_base as native

O = R / 'art/characters/character1_face_v1/tripo_neutral_p2'
REF = R / 'art/references/character1_neutral_v1'
PLAN = REF / 'production-plan.json'
VIEWS = [('front', '0_front.png'), ('left', '0_left.png'), ('right', '0_right.png')]
RESERVATION, EXPECTED = 150, 120


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


async def run(op):
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(Path.home() / 'Desktop/tripo_key.txt')))
    if op == 'balance':
        print(json.dumps({'balance': await provider.balance()})); return
    O.mkdir(parents=True, exist_ok=True)
    plan = read(PLAN)
    state_p = O / 'generation-state.json'
    state = read(state_p) if state_p.exists() else {}
    if op == 'submit':
        if state.get('task_id') or (O / 'generation-intent.json').exists():
            if not state.get('task_id'):
                raise ProviderError('ambiguous_intent_no_resubmit')
            print(json.dumps({'status': 'existing_task_preserved', 'task_id': state['task_id']})); return
        if not plan.get('reference_approved') or not plan.get('user_authorization'):
            raise ProviderError('reference_not_approved')
        refs = [(v, REF / f) for v, f in VIEWS]
        for v, p in refs:
            if hashlib.sha256(p.read_bytes()).hexdigest() != plan['reference_sha256_by_view'][v]:
                raise ProviderError('approved_reference_changed')
        if RESERVATION > float(plan['credit_cap']):
            raise ProviderError('budget_exhausted')
        balance = await provider.balance()
        if balance < RESERVATION:
            raise ProviderError('insufficient_balance')
        payload = {'model': 'P2-20260801', 'quad': True, 'face_limit': 20000, 'texture': True, 'pbr': True,
                   'export_uv': True, 'texture_quality': 'detailed', 'texture_version': 'v3.5-20260815',
                   'delight': True, 'texture_alignment': 'original_image', 'orientation': 'align_image',
                   'model_seed': 2026100501, 'texture_seed': 2026100501}
        save(O / 'generation-request.json', {**payload, 'route': '/generation/multiview-to-model',
             'references': [{'view': v, 'path': p.relative_to(R).as_posix()} for v, p in refs],
             'reservation': RESERVATION, 'expected_credits': EXPECTED,
             'user_authorization': plan['user_authorization'], 'automatic_resubmit': False})
        tokens = [(v, await upload(provider, p)) for v, p in refs]
        payload['inputs'] = [{v: t} for v, t in tokens]
        state = {'state': 'intent', 'created': time.time(), 'balance_before': balance}
        save(O / 'generation-intent.json', state); save(state_p, state)
        res = await provider.request('POST', '/generation/multiview-to-model', payload)
        tid = res.get('task_id')
        if not isinstance(tid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', tid):
            raise ProviderError('upstream_schema', uncertain=True)
        state.update(state='submitted', task_id=tid); save(state_p, state)
        print(json.dumps({'status': 'submitted', 'task_id': tid})); return
    if not state.get('task_id'):
        raise ProviderError('no_task')
    task = await provider.task(state['task_id'])
    safe = {'task_id': state['task_id'], 'status': task.get('status'), 'progress': task.get('progress'),
            'credits_consumed': task.get('credits_consumed')}
    if safe['status'] == 'success':
        native.OUT = O
        f = next((O / ('model.' + e) for e in ('fbx', 'glb', 'zip') if (O / ('model.' + e)).exists()), None) \
            or await native.download_native(task.get('output', {}).get('model_url', ''))
        safe.update(file=f.relative_to(R).as_posix(), bytes=f.stat().st_size)
    state.update(state=safe['status'], credits_consumed=safe['credits_consumed']); save(state_p, state)
    save(O / 'generation-status.json', safe); print(json.dumps(safe))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('operation', choices=['balance', 'submit', 'poll'])
    a = ap.parse_args()
    try:
        asyncio.run(run(a.operation))
    except Exception as e:
        print(json.dumps({'error': e.code if isinstance(e, ProviderError) else type(e).__name__, 'automatic_resubmit': False}))
        sys.exit(1)
