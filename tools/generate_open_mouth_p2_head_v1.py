"""User-approved open-mouth P2 head, one paid task with resumable polling."""
import argparse, asyncio, hashlib, json, re, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from generate_dev_character import upload
from generate_modular_character_parts import single_batch
from generate_hd_character_restart import save
import generate_fullbody_base as native

OUT = ROOT / 'art/characters/explorer_b_open_mouth_p2_v1'
REF = ROOT / 'art/references/explorer_b_open_mouth_v1/01_head_open_mouth_front.png'
LEDGER = ROOT / 'artifacts/character-hd-restart-20261004/budget.json'
NAME = 'open_mouth_p2_head_v1'
RESERVATION = 140

def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def rel(path): return path.relative_to(ROOT).as_posix()

async def run(operation):
    OUT.mkdir(parents=True, exist_ok=True)
    data = read(LEDGER)
    entry = data['tasks'].get(NAME)
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(Path.home() / 'Desktop/tripo_key.txt')))
    if operation == 'submit':
        if entry or (OUT / 'generation-intent.json').exists():
            if not entry or not entry.get('task_id'): raise ProviderError('ambiguous_intent_no_resubmit')
            print(json.dumps({'state': 'existing_task_preserved', 'task_id': entry['task_id']})); return
        approval = read(OUT / 'production-plan.json')
        digest = hashlib.sha256(REF.read_bytes()).hexdigest()
        if not approval['reference_approved'] or approval['reference_sha256'] != digest:
            raise ProviderError('approved_reference_changed')
        committed = sum(float(t.get('credits_consumed', t['reservation'])) for t in data['tasks'].values())
        if committed + RESERVATION > data['tripo_cap']: raise ProviderError('budget_exhausted')
        balance = await provider.balance()
        if balance < RESERVATION: raise ProviderError('insufficient_balance')
        payload = {'model': 'P2-20260801', 'face_limit': 15000, 'quad': True,
                   'texture': False, 'pbr': False, 'export_uv': True,
                   'enable_image_autofix': False, 'model_seed': 2026100410}
        request = {**payload, 'route': '/generation/image-to-model', 'reference': rel(REF),
                   'reference_sha256': digest, 'reservation': RESERVATION, 'expected_credits': 100,
                   'user_authorization': approval['user_authorization'], 'automatic_resubmit': False,
                   'scope': 'Head-neck-clavicle only. Smart Mesh P2 -> oral/topology inspection -> targeted cleanup -> texture -> facial rig. HD source retained for comparison.'}
        save(OUT / 'generation-request.json', request)
        payload['input'] = await upload(provider, REF)
        entry = {'state': 'intent', 'reservation': RESERVATION, 'created': time.time(),
                 'balance_before': balance, 'request_record': rel(OUT / 'generation-request.json'),
                 'automatic_resubmit': False}
        save(OUT / 'generation-intent.json', entry)
        data['tasks'][NAME] = entry; save(LEDGER, data)
        result = await provider.request('POST', '/generation/image-to-model', payload)
        tid = result.get('task_id')
        if not isinstance(tid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', tid):
            raise ProviderError('upstream_schema', uncertain=True)
        entry.update(state='submitted', task_id=tid)
        save(LEDGER, data); save(OUT / 'generation-task.json', {'task_id': tid})
        print(json.dumps({'status': 'submitted', 'task_id': tid})); return
    if not entry or not entry.get('task_id'): raise ProviderError('no_task')
    task = await provider.task(entry['task_id'])
    safe = {'task_id': entry['task_id'], 'status': task.get('status'), 'progress': task.get('progress'),
            'credits_consumed': task.get('credits_consumed')}
    if safe['status'] in ('success', 'failed', 'cancelled'):
        entry['state'] = safe['status']
        if isinstance(safe['credits_consumed'], (int, float)): entry['credits_consumed'] = safe['credits_consumed']
        save(LEDGER, data)
        safe['budget_remaining'] = data['tripo_cap'] - sum(float(t.get('credits_consumed', t['reservation'])) for t in data['tasks'].values())
        if safe['status'] == 'success':
            existing = [OUT / ('model.' + e) for e in ('glb', 'fbx', 'zip') if (OUT / ('model.' + e)).exists()]
            native.OUT = OUT
            file = existing[0] if existing else await native.download_native(task.get('output', {}).get('model_url', ''))
            safe.update(file=rel(file), bytes=file.stat().st_size, sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                        rigged=False, texture_generated=False, retopologized=False)
        save(OUT / 'generation-result.json', safe)
    else: save(OUT / 'generation-status.json', safe)
    print(json.dumps(safe))

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('operation', choices=['submit', 'poll']); a = p.parse_args()
    try:
        with single_batch(): asyncio.run(run(a.operation))
    except Exception as e:
        print(json.dumps({'error': e.code if isinstance(e, ProviderError) else type(e).__name__, 'automatic_resubmit': False})); sys.exit(1)
