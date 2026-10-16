"""0.11.9 weak-link benchmark. Only 127.0.0.1; no provider credentials.
Reuses run_local safety helpers and test_multiplayer_load.seed fixtures.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import random
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from run_local import safe_env, loopback_guard
from metrics import stop_process_tree
from slow_proxy import SlowProxy


def serve(root, port):
    sys.addaudithook(loopback_guard)
    sys.path.insert(0, str(root))
    import uvicorn
    uvicorn.run('server.app:create_app', factory=True, host='127.0.0.1', port=port,
                workers=1, access_log=False, proxy_headers=False, log_level='warning')


def make_glb():
    """Three copies total <48 MiB; each is a valid <20 MiB textured GLB."""
    target = HERE / '.tmp' / 'lownet-textured-1360x3.glb'
    if target.exists():
        return target.read_bytes()
    from PIL import Image
    picture = Image.frombytes('RGB', (1360, 1360), random.Random(119).randbytes(1360 * 1360 * 3))
    stream = io.BytesIO()
    picture.save(stream, 'PNG', compress_level=0)
    vertices = struct.pack('<9f', -.5, 0, -.5, .5, 0, -.5, 0, 1, .5)
    uv = struct.pack('<6f', 0, 0, 1, 0, .5, 1)
    binary = vertices + uv + stream.getvalue()
    doc = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'TEXCOORD_0': 1}, 'material': 0}]}],
        'materials': [{'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}],
        'textures': [{'source': 0}], 'images': [{'bufferView': 2, 'mimeType': 'image/png'}],
        'buffers': [{'byteLength': len(binary)}], 'bufferViews': [
            {'buffer': 0, 'byteOffset': 0, 'byteLength': len(vertices)},
            {'buffer': 0, 'byteOffset': len(vertices), 'byteLength': len(uv)},
            {'buffer': 0, 'byteOffset': len(vertices)+len(uv), 'byteLength': stream.tell()}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [-.5, 0, -.5], 'max': [.5, 1, .5]},
                      {'bufferView': 1, 'componentType': 5126, 'count': 3, 'type': 'VEC2'}]}
    for index in range(1, 3):
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': stream.tell()})
        binary += stream.getvalue()
        doc['images'].append({'bufferView': 2+index, 'mimeType': 'image/png'})
        doc['textures'].append({'source': index})
        doc['materials'].append({'pbrMetallicRoughness': {'baseColorTexture': {'index': index}}})
        doc['meshes'][0]['primitives'].append({'attributes': {'POSITION': 0, 'TEXCOORD_0': 1}, 'material': index})
    doc['buffers'][0]['byteLength'] = len(binary)
    header = json.dumps(doc, separators=(',', ':')).encode()
    header += b' ' * (-len(header) % 4)
    binary += b'\0' * (-len(binary) % 4)
    result = struct.pack('<III', 0x46546C67, 2, 28+len(header)+len(binary))
    result += struct.pack('<II', len(header), 0x4E4F534A)+header+struct.pack('<II', len(binary), 0x004E4942)+binary
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(result)
    return result


def seed_world(root, data, blob, optimized):
    sys.path.insert(0, str(ROOT / 'tools'))
    from test_multiplayer_load import seed
    people = seed(data / 'world.sqlite3', 6, 0, 5, 24, 119)
    sys.path.insert(0, str(root))
    from server.asset_assembly import simple_plan
    from server.provider import validate_glb
    validate_glb(blob, allow_textures=True)
    digests = []
    asset, obj = str(uuid.uuid4()), str(uuid.uuid4())
    plan = simple_plan('low network benchmark stool')
    first = plan['parts'][0]
    plan['parts'] = []
    for index in range(3):
        file = asset + '-part' + str(index) + '.glb'
        # Distinct valid UVs prevent the actual Godot SHA-based part cache from
        # deduplicating this three-part fixture into one download.
        part_blob = bytearray(blob)
        binary_start = 28 + struct.unpack_from('<I', blob, 12)[0]
        struct.pack_into('<f', part_blob, binary_start+36, index*.01)
        part_blob = bytes(part_blob)
        validate_glb(part_blob, allow_textures=True)
        digest = hashlib.sha256(part_blob).hexdigest()
        digests.append(digest)
        (data / 'assets' / file).write_bytes(part_blob)
        plan['parts'].append({**first, 'id': 'part'+str(index), 'file': file, 'sha256': digest})
        if optimized:
            from server.asset_delivery import prepare_low_variant
            if not prepare_low_variant(data / 'assets', file, digest, part_blob):
                raise RuntimeError('fixture_low_variant_failed')
    program = {'version': 1, 'state': {}, 'functions': {}, 'events': {}}
    manifest = {'schema': 1, 'plan': plan, 'program': program, 'provenance': {'geometry': 'tripo'}}
    with sqlite3.connect(data / 'world.sqlite3') as conn:
        conn.execute('INSERT INTO assets VALUES (?,?,?,?)', (asset, plan['parts'][0]['file'], digests[0], 'studio'))
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,state,created) VALUES (?,?,?,?,?,'inventory',?)",
                     (obj, people[0]['id'], people[0]['id'], asset, 'lownet fixture', time.time()))
        conn.execute('INSERT INTO studio_assets VALUES (?,?)', (asset, json.dumps(manifest)))
        conn.execute("INSERT INTO studio_runtime(object_id,state) VALUES (?, '{}')", (obj,))
        for index in range(30):
            conn.execute('INSERT INTO mp_messages(room,user_id,text,created,channel) VALUES (?,?,?,?,?)',
                         ('village:'+people[0]['id'], people[0]['id'], f'seeded chat line {index:02d}', time.time(), 'local'))
        job = str(uuid.uuid4())
        conn.execute("INSERT INTO studio_jobs(id,owner_id,request,state,cost,plan,program,provenance,parts,created,updated) VALUES (?,?,?,'planning',1,?,?,?,'{}',?,?)",
            (job, people[1]['id'], '{}', json.dumps(plan), json.dumps(program), '{}', time.time(), time.time()))
        conn.execute('INSERT INTO studio_leases VALUES (?,?,?)', (job, 'lownet-fixture-worker', time.time()+3600))
        conn.commit()
    if len(set(digests)) != 3:
        raise RuntimeError('fixture_part_hashes_must_be_unique')
    return people, obj, digests, job


def source_digest(root):
    files = sorted((root / 'server').glob('*.py'))
    return hashlib.sha256(b''.join(p.name.encode()+b'\0'+p.read_bytes() for p in files)).hexdigest()


async def run(args):
    import httpx
    sys.addaudithook(loopback_guard)
    root = (HERE / '.baseline') if args.mode == 'before' else ROOT
    data = HERE / '.tmp' / (args.mode+'-'+uuid.uuid4().hex[:8])
    data.mkdir(parents=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = (data / 'server.log').open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-B', str(__file__), '--serve', str(port), '--server-root', str(root)],
        cwd=data, env=safe_env(data, 'fixture'), stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    proxy = SlowProxy(port)
    clients = {}
    host_task = None
    direct = httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=20)
    try:
        for _ in range(150):
            try:
                response = await direct.get('/health')
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if process.poll() is not None:
                raise RuntimeError('server_exited: '+str(data / 'server.log'))
            await asyncio.sleep(.1)
        else:
            raise RuntimeError('server_start_timeout')
        blob = make_glb()
        people, obj, original_digest, job = seed_world(root, data, blob, args.mode != 'before')
        host, guest = people[:2]
        for category in ('presence', 'chat', 'social', 'studio', 'asset'):
            shaped_port = await proxy.listen(category)
            clients[category] = httpx.AsyncClient(base_url=f'http://127.0.0.1:{shaped_port}', trust_env=False,
                timeout=httpx.Timeout(600, connect=10), limits=httpx.Limits(keepalive_expiry=3), headers={**guest['headers'],
                'Accept-Encoding': 'identity' if args.mode == 'before' else 'gzip, deflate'})
        stop_host = asyncio.Event()

        async def host_heartbeat():
            while not stop_host.is_set():
                response = await direct.post('/v1/social/presence', headers=host['headers'], json={
                    'scene': 'village', 'place': 'village', 'x': 0, 'z': 0, 'since': 1})
                response.raise_for_status()
                try:
                    await asyncio.wait_for(stop_host.wait(), timeout=3)
                except TimeoutError:
                    pass

        host_task = asyncio.create_task(host_heartbeat())
        await asyncio.sleep(.1)
        cursor, etags, cached = 0, {}, {}
        rows = []

        async def request(category, method, path, payload=None):
            nonlocal cursor
            headers = {}
            if args.mode != 'before' and method == 'GET':
                headers['X-Villagen-Cache'] = '1'
                if path in etags:
                    headers['If-None-Match'] = etags[path]
            start = time.perf_counter()
            response = await clients[category].request(method, path, json=payload, headers=headers)
            if response.status_code not in (200, 304):
                raise RuntimeError(f'{category} {path}: {response.status_code} {response.text[:300]}')
            value = cached.get(path, {}) if response.status_code == 304 else response.json()
            if response.headers.get('etag'):
                etags[path], cached[path] = response.headers['etag'], value
            if category == 'presence':
                cursor = value.get('chat', {}).get('cursor', cursor)
            rows.append((start, time.perf_counter(), category, response.status_code, len(response.content)))
            return value

        async def presence():
            return await request('presence', 'POST', '/v1/social/presence', {
                'scene': 'village', 'place': 'village', 'floor': 0, 'x': 2, 'z': 2,
                'y': 0, 'yaw': 0, 'vx': 0, 'vz': 0, 't': round(time.perf_counter()%100000, 3), 'since': cursor})

        await presence()
        for category, path in (('social', '/v1/social/people'), ('chat', '/v1/social/whispers/requests'), ('studio', '/v1/studio'), ('studio', '/v1/studio/jobs/'+job)):
            await request(category, 'GET', path)
        rows.clear()
        start = time.perf_counter()
        deadline = start + args.seconds

        async def periodic(interval, action, after_response=False):
            while time.perf_counter() < deadline:
                tick = time.perf_counter()
                await action()
                await asyncio.sleep(min(interval if after_response else max(0, interval-(time.perf_counter()-tick)), max(0, deadline-time.perf_counter())))

        intervals = {'presence': 1.0 if args.mode == 'policy' else .25, 'chat': 4,
                     'social': 5, 'studio': 20, 'studio_job_after_response': 2}
        await asyncio.gather(periodic(intervals['presence'], presence),
            periodic(intervals['chat'], lambda: request('chat', 'GET', '/v1/social/whispers/requests')),
            periodic(intervals['social'], lambda: request('social', 'GET', '/v1/social/people')),
            periodic(intervals['studio'], lambda: request('studio', 'GET', '/v1/studio')),
            periodic(2, lambda: request('studio', 'GET', '/v1/studio/jobs/'+job), True))
        end = time.perf_counter()
        polling = proxy.report(start, end)
        for category in polling:
            selected = [row for row in rows if row[2] == category]
            polling[category].update(requests=len(selected), requests_per_minute=round(len(selected)*60/(end-start), 2),
                decoded_response_bytes=sum(row[4] for row in selected), statuses=dict(Counter(str(row[3]) for row in selected)))
        result = {'completed': bool(args.skip_asset), 'mode': args.mode, 'server_source_sha256': source_digest(root),
            'baseline_commit': '5f7c6c1', 'settings': {'bits_per_second_each_direction': 1_500_000,
            'rtt_ms': 300, 'modeled_segment_loss': .01, 'seed': 119, 'poll_intervals_seconds': intervals},
            'poll_seconds': round(end-start, 3), 'polling': polling, 'asset_original_bytes': 3*len(blob),
            'asset_part_original_bytes': len(blob), 'asset_original_sha256_per_part': original_digest}
        print(json.dumps({'mode': args.mode, 'polling': polling}), flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        if not args.skip_asset:
            placed = time.perf_counter()
            response = await direct.post(f'/v1/objects/{obj}/placement', headers=host['headers'], json={
                'request_id': str(uuid.uuid4()), 'version': 1, 'action': 'place', 'room': 'village', 'x': 16, 'z': 12, 'rotation': 0})
            if response.status_code != 200:
                raise RuntimeError('placement: '+response.text)
            await asyncio.sleep(intervals['presence']/2)
            state = await presence()
            if obj not in json.dumps(state):
                raise RuntimeError('placed_object_not_visible_in_presence')
            discovered = time.perf_counter()
            print(json.dumps({'mode': args.mode, 'placed_discovered_seconds': discovered-placed}), flush=True)
            assembly = await request('asset', 'GET', f'/v1/social/village/objects/{obj}/assembly')
            deadline = float('inf')
            asset_pollers = [asyncio.create_task(periodic(intervals['presence'], presence)),
                asyncio.create_task(periodic(4, lambda: request('chat', 'GET', '/v1/social/whispers/requests'))),
                asyncio.create_task(periodic(5, lambda: request('social', 'GET', '/v1/social/people'))),
                asyncio.create_task(periodic(20, lambda: request('studio', 'GET', '/v1/studio'))),
                asyncio.create_task(periodic(2, lambda: request('studio', 'GET', '/v1/studio/jobs/'+job), True))]
            downloaded = 0
            checksums, lods, part_seconds = [], [], []
            for part in assembly['plan']['parts']:
                path = f'/v1/social/village/objects/{obj}/parts/'+part['id']
                part_start = time.perf_counter()
                response = await clients['asset'].get(path+('?lod=low' if args.mode != 'before' else ''))
                response.raise_for_status()
                part_seconds.append(round(time.perf_counter()-part_start, 3))
                downloaded += len(response.content)
                checksums.append(hashlib.sha256(response.content).hexdigest())
                lods.append(response.headers.get('x-asset-lod', 'original'))
                if args.mode == 'before' and checksums[-1] != part['sha256']:
                    raise RuntimeError('download_integrity_mismatch')
            finished = time.perf_counter()
            deadline = finished
            for task in asset_pollers:
                task.cancel()
            outcomes = await asyncio.gather(*asset_pollers, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    raise outcome
            result['appearance'] = {'seconds_to_discover': round(discovered-placed, 3),
                'seconds_to_download_complete': round(finished-placed, 3), 'download_bytes': downloaded,
                'download_sha256_per_part': checksums, 'lod_per_part': lods, 'seconds_per_part': part_seconds,
                'wire': proxy.report(placed, finished), 'asset_http_requests': len(checksums)+1,
                'asset_http_requests_per_minute': round((len(checksums)+1)*60/(finished-placed), 2),
                'render_included': False}
        result['completed'] = True
        stop_host.set()
        await host_task
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'result': str(args.output), 'appearance': result.get('appearance')}), flush=True)
    finally:
        if host_task and not host_task.done():
            host_task.cancel()
            await asyncio.gather(host_task, return_exceptions=True)
        await asyncio.gather(*(client.aclose() for client in clients.values()), return_exceptions=True)
        await direct.aclose()
        await proxy.close()
        stop_process_tree(process)
        log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('before', 'after', 'policy'), default='before')
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--skip-asset', action='store_true')
    parser.add_argument('--output', type=Path, default=HERE / 'results' / 'lownet-before.json')
    parser.add_argument('--serve', type=int)
    parser.add_argument('--server-root', type=Path)
    args = parser.parse_args()
    if args.serve:
        serve(args.server_root, args.serve)
    else:
        asyncio.run(run(args))
