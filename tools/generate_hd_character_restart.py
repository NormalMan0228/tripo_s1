"""Seven independent HD sources; bounded budget, resumable, no secret logging.

prepare is offline. submit and poll operate on explicit parts. A submitted or
ambiguous intent is never resubmitted. Originals and runtime assets are untouched.
"""
import argparse
import asyncio
import hashlib
import json
import math
import re
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from generate_dev_character import upload
from generate_modular_character_parts import single_batch

OUT = ROOT / 'art/characters/explorer_b_hd_restart_v1'
ACCOUNTING = ROOT / 'artifacts/character-hd-restart-20261004'
LEDGER = ACCOUNTING / 'budget.json'
MANIFEST = OUT / 'generation-manifest.json'
REF = ROOT / 'art/references/explorer_b_modular_v1/final_images'
BODY_REF = ROOT / 'art/references/explorer_b_fullbody_v2'
MODEL = 'v3.1-20260211'
UNIT_ESTIMATE = 40
UNIT_RESERVATION = 60
SETTINGS_BY_PART = {
    'fullbody': ('전체 신체(속옷 포함)', 2000000, [BODY_REF/'front.png', BODY_REF/'back.png']),
    'head': ('머리', 1000000, [REF/'01_head.png']),
    'hair': ('머리카락', 500000, [REF/'04_hair.png']),
    'hand': ('손', 750000, [REF/'03_hand.png']),
    'upper_clothing': ('상의', 1000000, [REF/'05_jacket.png']),
    'lower_clothing': ('하의', 1000000, [REF/'07_pants.png']),
    'footwear': ('신발', 750000, [REF/'08_boots.png']),
}

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def relative(path):
    return path.relative_to(ROOT).as_posix()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_references():
    selection = read(REF.parent/'final_images_selection.json')
    for item in selection['assets']:
        if sha(REF/item['file']) != item['sha256']:
            raise ProviderError('approved_part_reference_changed')
    for item in read(BODY_REF/'generation-record.json')['images']:
        if sha(BODY_REF/item['file']) != item['sha256']:
            raise ProviderError('approved_fullbody_reference_changed')

def common_request(faces):
    return {'model': MODEL, 'geometry_quality': 'detailed', 'face_limit': faces,
            'texture': False, 'pbr': False, 'quad': False, 'smart_low_poly': False,
            'generate_parts': False, 'export_uv': False, 'auto_size': False,
            'model_seed': 202610047}

def prepare():
    verify_references()
    if not LEDGER.exists():
        save(LEDGER, {'date': '2026-10-04', 'scope': 'developer_character_HD_restart',
                     'user_authorization': '추가 1000크레딧', 'tripo_cap': 1000,
                     'separate_from_old_character_and_map_budgets': True,
                     'tasks': {}, 'automatic_resubmit': False})
    manifest = read(MANIFEST) if MANIFEST.exists() else {
        'date': '2026-10-04', 'model': MODEL, 'mode': 'HD_Ultra', 'geometry_quality': 'detailed',
        'scope': 'seven_independent_developer_sources_before_fit_UV_textures_rigging',
        'budget_file': relative(LEDGER), 'cap': 1000, 'expected_credits': 280,
        'texture': False, 'pbr': False, 'UV_unwrap': 'deferred_to_reviewed_texture_stage',
        'design_changed': False, 'assembled': False, 'rigged': False, 'imported_to_game': False,
        'parts': {}, 'actual_credits': 0,
        'sources': ['https://developers.tripo3d.ai/en/models/v3-1',
                    'https://developers.tripo3d.ai/en/docs/generation-image-to-model/standard',
                    'https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/standard'],
        'generation_notes': [
            'Fullbody includes the opaque white underlayer top and shorts from approved front/back images.',
            'Upper clothing is the approved jacket; white inner top is already included on the body base.',
            'Lower clothing uses approved trousers with pockets and waistband details.',
            'One hand and one boot are generated from approved single-side references; pair mirroring needs later review.',
            'No separate belt task: seven requested generation groups are retained. Belt detail/fitting belongs to lower clothing review.',
            'Polycount limits are upper bounds, not proof of good anatomy, topology or symmetry.'
        ]}
    for part, (label, faces, refs) in SETTINGS_BY_PART.items():
        folder = OUT/part
        folder.mkdir(parents=True, exist_ok=True)
        request = common_request(faces)
        route = '/generation/multiview-to-model' if part == 'fullbody' else '/generation/image-to-model'
        if part != 'fullbody':
            request['enable_image_autofix'] = False
        safe = {'route': route, **request, 'reference_files': [relative(p) for p in refs],
                'reference_sha256': [sha(p) for p in refs], 'expected_credits': UNIT_ESTIMATE,
                'reservation_credits': UNIT_RESERVATION, 'automatic_resubmit': False}
        path = folder/'generation-request.json'
        if path.exists() and read(path) != safe:
            raise ProviderError('existing_HD_request_mismatch')
        save(path, safe)
        manifest['parts'].setdefault(part, {'label': label, 'state': 'prepared',
                                            'request_file': relative(path), 'face_limit': faces})
    save(MANIFEST, manifest)
    return manifest

def committed(data):
    return sum(float(t.get('credits_consumed', t['reservation'])) for t in data['tasks'].values())

async def download_source(url, path):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    if parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username or parsed.password or not (
        host == 'tripo3d.ai' or host.endswith('.tripo3d.ai') or host == 'tripo-data.rg1.data.tripo3d.com'):
        raise ProviderError('unsafe_HD_asset_url')
    chunks, total = [], 0
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        async with client.stream('GET', url) as response:
            if response.status_code != 200:
                raise ProviderError('HD_asset_download_failed')
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > 160*1024*1024:
                    raise ProviderError('HD_asset_too_large')
                chunks.append(chunk)
    blob = b''.join(chunks)
    if len(blob) < 28 or blob[:4] != b'glTF':
        raise ProviderError('HD_asset_not_GLB')
    magic, version, length = struct.unpack_from('<III', blob)
    if version != 2 or length != len(blob):
        raise ProviderError('HD_asset_bad_header')
    size, kind = struct.unpack_from('<II', blob, 12)
    if kind != 0x4E4F534A or size > 10*1024*1024 or 20+size > len(blob):
        raise ProviderError('HD_asset_bad_json_chunk')
    doc = json.loads(blob[20:20+size])
    def no_external_refs(value):
        if isinstance(value, dict):
            if 'uri' in value:
                raise ProviderError('HD_asset_external_reference')
            for child in value.values():
                no_external_refs(child)
        elif isinstance(value, list):
            for child in value:
                no_external_refs(child)
    no_external_refs(doc)
    if doc.get('skins') or doc.get('animations') or not doc.get('meshes'):
        raise ProviderError('unexpected_HD_asset_schema')
    if doc.get('images') or doc.get('textures'):
        raise ProviderError('unexpected_HD_textures')
    temp = path.with_suffix('.download')
    temp.write_bytes(blob)
    temp.replace(path)

async def run(operation, parts):
    manifest = prepare()
    if operation == 'prepare':
        print(json.dumps({'state': 'prepared', 'parts': list(SETTINGS_BY_PART),
                          'model': MODEL, 'expected_credits': 280, 'cap': 1000})); return
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/'Desktop/tripo_key.txt')))
    if operation == 'balance':
        print(json.dumps({'balance': await provider.balance(), 'cap': read(LEDGER)['tripo_cap']})); return
    for part in parts:
        data = read(LEDGER)
        entry = data['tasks'].get(part)
        folder = OUT/part
        safe = read(folder/'generation-request.json')
        if operation == 'submit':
            if entry or (folder/'generation-intent.json').exists():
                print(json.dumps({'part': part, 'state': 'existing_intent_preserved',
                                  'task_id': entry.get('task_id') if entry else None}), flush=True)
                continue
            if committed(data)+UNIT_RESERVATION > data['tripo_cap']:
                raise ProviderError('new_HD_budget_exhausted')
            balance = await provider.balance()
            if balance < UNIT_RESERVATION:
                raise ProviderError('insufficient_HD_balance')
            refs = SETTINGS_BY_PART[part][2]
            tokens = [await upload(provider, path) for path in refs]
            payload = common_request(SETTINGS_BY_PART[part][1])
            if part == 'fullbody':
                payload['inputs'] = [{'front': tokens[0]}, {'back': tokens[1]}]
            else:
                payload.update(input=tokens[0], enable_image_autofix=False)
            entry = {'state': 'intent', 'created': time.time(), 'reservation': UNIT_RESERVATION,
                     'expected_credits': UNIT_ESTIMATE, 'balance_before': balance,
                     'request_record': relative(folder/'generation-request.json'),
                     'automatic_resubmit': False}
            save(folder/'generation-intent.json', entry)
            data['tasks'][part] = entry
            save(LEDGER, data)
            try:
                response = await provider.request('POST', safe['route'], payload)
                task_id = response.get('task_id')
                if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', task_id):
                    raise ProviderError('HD_task_schema', uncertain=True)
                entry.update(state='submitted', task_id=task_id)
            except ProviderError as error:
                entry.update(state='ambiguous_or_rejected_intent', safe_error=error.code,
                             uncertain=error.uncertain)
                save(LEDGER, data)
                raise
            save(LEDGER, data)
            save(folder/'generation-task.json', {'task_id': task_id})
            manifest['parts'][part].update(state='submitted', task_id=task_id)
            save(MANIFEST, manifest)
            print(json.dumps({'part': part, 'state': 'submitted', 'task_id': task_id}), flush=True)
        elif operation == 'poll':
            if not entry or not entry.get('task_id'):
                print(json.dumps({'part': part, 'state': 'not_submitted'}), flush=True); continue
            task = await provider.task(entry['task_id'])
            status = task.get('status')
            credits = task.get('credits_consumed')
            result = {'part': part, 'task_id': entry['task_id'], 'status': status,
                      'progress': task.get('progress'), 'credits_consumed': credits}
            if status in ('success','failed','cancelled'):
                entry['state'] = status
                if isinstance(credits, (int,float)) and math.isfinite(credits) and credits >= 0:
                    entry['credits_consumed'] = credits
                save(LEDGER, data)
                manifest['parts'][part].update(state=status, credits_consumed=entry.get('credits_consumed'))
                if status == 'success':
                    target = folder/'model.glb'
                    if not target.exists():
                        await download_source(task.get('output',{}).get('model_url',''), target)
                    result.update(file=relative(target), sha256=sha(target), bytes=target.stat().st_size,
                                  assembled=False, rigged=False, imported_to_game=False,
                                  geometry_review='pending')
                    manifest['parts'][part].update(model_file=relative(target), sha256=sha(target))
                save(folder/'generation-result.json', result)
                manifest['actual_credits'] = sum(float(t.get('credits_consumed',0)) for t in data['tasks'].values())
                manifest['state'] = 'geometry_awaiting_user_review' if all(p['state']=='success' for p in manifest['parts'].values()) else 'in_progress'
                save(MANIFEST, manifest)
            else:
                save(folder/'generation-status.json', result)
            print(json.dumps(result), flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['prepare','balance','submit','poll'])
    p.add_argument('--parts', nargs='+', choices=list(SETTINGS_BY_PART), default=list(SETTINGS_BY_PART))
    args = p.parse_args()
    try:
        with single_batch():
            asyncio.run(run(args.operation, args.parts))
    except (ProviderError, ValueError, OSError, httpx.HTTPError):
        error = sys.exc_info()[1]
        print(json.dumps({'error': error.code if isinstance(error,ProviderError) else 'HD_safe_operation_failed',
                          'automatic_resubmit': False}), flush=True)
        sys.exit(1)
