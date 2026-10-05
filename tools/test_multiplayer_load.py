"""Bounded, local-only three-user HTTP load test; never contacts a paid provider.

Creates an isolated temporary DB and an owned Uvicorn process. Includes a night
when run for 60+ seconds. This does not establish Google Cloud VM capacity.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


async def exercise(url, duration):
    measurements, failures = [], []
    async with httpx.AsyncClient(base_url=url, timeout=12, limits=httpx.Limits(max_keepalive_connections=0)) as client:
        users = []
        async def post(path, headers=None, **body):
            response = await client.post(path, headers=headers, json={'request_id':str(uuid.uuid4()), **body})
            response.raise_for_status()
            return response.json()
        for index in range(3):
            name = f'load_{index}_{secrets.token_hex(3)}'
            response = await client.post('/v1/auth/register', json={'username':name, 'password':secrets.token_urlsafe(20)+'Aa!'})
            response.raise_for_status()
            users.append((name, {'Authorization':'Bearer '+response.json()['token']}))
        await post('/v1/party', users[0][1])
        for name, headers in users[1:]:
            invitation = await post('/v1/social/invites', users[0][1], username=name, kind='party')
            await post('/v1/social/invites/'+invitation['id']+'/accept', headers)
        for _, headers in users:
            response = await client.post('/v1/social/presence', headers=headers, json={})
            response.raise_for_status()
        run = await post('/v1/party/runs', users[0][1], difficulty='relaxed')
        started = time.perf_counter()
        summaries = []
        async def player(index, headers):
            sequence = 0
            snapshot = None
            next_input = time.perf_counter()
            while time.perf_counter()-started < duration:
                await asyncio.sleep(max(0, next_input-time.perf_counter()))
                next_input += .2
                sequence += 1
                body = {'sequence':sequence}
                # Keep camp lit using the real inventory, then exercise hunger.
                if index == 0 and sequence in (1, 160): body['action'] = 'fire'
                if snapshot and snapshot['hunger'] < 70 and snapshot['inventory']['berry'] > 0: body['action'] = 'eat'
                before = time.perf_counter()
                try:
                    response = await client.post('/v1/coop/runs/'+run['id']+'/input', headers=headers, json=body)
                    measurements.append((time.perf_counter()-before)*1000)
                    if response.status_code != 200:
                        failures.append({'player':index, 'status':response.status_code, 'error':response.json().get('detail')})
                    else:
                        snapshot = response.json()
                        sequence = snapshot['sequence']
                except httpx.HTTPError as error:
                    failures.append({'player':index, 'error':type(error).__name__})
                if sequence % 10 == 0:
                    response = await client.post('/v1/social/presence', headers=headers, json={'scene':'away'})
                    if response.status_code != 200: failures.append({'player':index, 'presence_status':response.status_code})
                # Never accumulate an unbounded catch-up burst after a slow request.
                next_input = max(next_input, time.perf_counter())
            summaries.append({'player':index, 'elapsed':snapshot.get('elapsed') if snapshot else None,
                              'status':snapshot.get('status') if snapshot else None})
        await asyncio.gather(*(player(i, h) for i, (_, h) in enumerate(users)))
        ordered = sorted(measurements)
        return dict(environment='isolated Windows localhost; not production capacity', users=3,
                    duration_seconds=round(time.perf_counter()-started, 2), survival_requests=len(ordered),
                    failures=failures, mean_ms=round(statistics.mean(ordered), 2),
                    p95_ms=round(ordered[min(len(ordered)-1, int(len(ordered)*.95))], 2),
                    max_ms=round(max(ordered), 2), players=summaries)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=65)
    parser.add_argument('--output', default=str(ROOT/'artifacts/multiplayer-load.json'))
    args = parser.parse_args()
    if not 5 <= args.seconds <= 120:
        parser.error('seconds must be between 5 and 120')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='tripothon-load-') as data:
        env = {k:v for k,v in os.environ.items() if not k.startswith(('TRIPOTHON_', 'TRIPO_', 'OPENAI_API_KEY'))}
        env.update(TRIPOTHON_MODE='demo', TRIPOTHON_DATA_DIR=data, TRIPO_ENABLE_PAID='false', TRIPOTHON_STUDIO_LLM='fixture')
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server.app:create_app', '--factory', '--host', '127.0.0.1', '--port', str(port), '--workers', '1', '--no-access-log', '--no-proxy-headers'], cwd=ROOT, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        url = f'http://127.0.0.1:{port}'
        try:
            for attempt in range(50):
                try:
                    response = httpx.get(url+'/health', timeout=.5)
                    if response.status_code == 200: break
                except httpx.HTTPError:
                    pass
                if process.poll() is not None: raise RuntimeError('isolated_server_exited')
                time.sleep(.1)
            else: raise RuntimeError('isolated_server_not_ready')
            report = asyncio.run(exercise(url, args.seconds))
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
            return bool(report['failures'])
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == '__main__':
    raise SystemExit(main())
