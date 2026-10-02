"""Explicitly authorized Tripo preset experiment; never resubmit ambiguous jobs."""
import argparse
import json
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import read_tripo_key
OUT = ROOT / 'artifacts/characters/explorer-b-tripo-walk'
BASE = 'https://openapi.tripo3d.ai/v3'

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('operation', choices=['submit', 'poll', 'download', 'balance'])
    p.add_argument('--key-file', type=Path, required=True)
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90, follow_redirects=False, headers={'Authorization': 'Bearer ' + read_tripo_key(args.key_file)}) as client:
        def request(method, path, **kwargs):
            response = client.request(method, BASE + path, **kwargs)
            if response.status_code != 200:
                raise RuntimeError('http_' + str(response.status_code))
            if 'application/json' not in response.headers.get('content-type', ''):
                raise RuntimeError('non_json')
            body = response.json()
            if body.get('code') != 0:
                raise RuntimeError('provider_code_' + str(body.get('code')))
            return body['data']
        def balance(filename):
            body = request('GET', '/account/balance')
            safe = {k: body.get(k) for k in ('balance', 'frozen')}
            save(filename, safe)
            return safe
        if args.operation == 'balance':
            print(json.dumps(balance('balance-after.json')))
            return
        if args.operation == 'submit':
            if (OUT / 'task.json').exists():
                print('Existing task retained; use poll.')
                return
            before = balance('balance-before.json')
            if before['balance'] < 10:
                raise RuntimeError('insufficient_balance')
            source = json.loads((ROOT / 'artifacts/characters/explorer-b-v1/rig-task.json').read_text())['task_id']
            payload = {'input': source, 'animation': 'preset:biped:walk', 'out_format': 'glb', 'bake_animation': True, 'export_with_geometry': True, 'animate_in_place': True}
            save('request.json', payload)
            with (OUT / 'intent.json').open('x', encoding='utf-8') as f:
                json.dump({'submitted_at': time.time(), 'expected_credits': 10}, f)
            task = request('POST', '/animations/retarget', json=payload)
            save('task.json', {'task_id': task['task_id']})
            print(json.dumps({'submitted': True, 'task_id': task['task_id']}))
            return
        task_id = json.loads((OUT / 'task.json').read_text())['task_id']
        if not isinstance(task_id, str) or '/' in task_id:
            raise RuntimeError('invalid_task_id')
        body = request('GET', '/tasks/' + task_id)
        safe = {k: body[k] for k in ('task_id', 'status', 'progress', 'credits_consumed', 'error_code') if k in body}
        safe['output_fields'] = list(body.get('output', {}))
        save('status.json', safe)
        print(json.dumps(safe))
        if args.operation == 'download':
            if body.get('status') != 'success':
                raise RuntimeError('task_not_complete')
            output = body.get('output', {})
            url = output.get('model_url') or output.get('model')
            if not isinstance(url, str):
                raise RuntimeError('missing_model_url')
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.hostname not in ('cdn.tripo3d.ai', 'tripo-data.rg1.data.tripo3d.com'):
                raise RuntimeError('unapproved_download_host')
            with httpx.Client(timeout=120, follow_redirects=False) as downloader:
                with downloader.stream('GET', url) as response:
                    if response.status_code != 200:
                        raise RuntimeError('download_http_' + str(response.status_code))
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 150 * 1024 * 1024:
                            raise RuntimeError('asset_too_large')
            if data[:4] != b'glTF' or struct.unpack_from('<I', data, 8)[0] != len(data):
                raise RuntimeError('invalid_glb')
            (OUT / 'tripo-walk-original.glb').write_bytes(data)
            print(json.dumps({'saved': 'tripo-walk-original.glb', 'bytes': len(data)}))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        allowed = ('http_', 'non_json', 'provider_code_', 'insufficient_', 'invalid_', 'task_', 'missing_', 'unapproved_', 'download_', 'asset_')
        label = str(exc) if isinstance(exc, RuntimeError) and str(exc).startswith(allowed) else type(exc).__name__
        print(json.dumps({'error': label, 'automatic_resubmit': False}))
        sys.exit(1)
