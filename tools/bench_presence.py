"""Isolated mixed polling benchmark: TestClient, no listener or external provider.

python tools/bench_presence.py --players 60 --seconds 30 --interval 1
--interval 0 is closed-loop saturation; paced runs skip missed ticks. All fake
accounts, sessions and SQLite files are temporary and confined to this worktree.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import httpx
import sqlite3
import sys
import tempfile
import threading
import time
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextmanager
def isolated_environment():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('TRIPOTHON_', 'TRIPO_', 'VILLAGEN_', 'OPENAI_', 'GEMINI_'))}

    def no_network(*args, **kwargs):
        raise RuntimeError('benchmark_network_disabled')

    with patch.dict(os.environ, env, clear=True), \
            patch.object(httpx.HTTPTransport, 'handle_request', no_network), \
            patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', no_network):
        yield


def seed(app, count, history_users, objects_each):
    from server import homestead
    now = time.time()
    players = []
    with app.state.db.transaction() as conn:
        for i in range(count + history_users):
            uid = str(uuid.uuid5(uuid.NAMESPACE_OID, f'presence-bench-{i}'))
            token = f'benchmark-only-session-{i}'
            conn.execute('INSERT INTO users(id,username,password_hash,shards,created,daily_utc_offset) '
                         'VALUES (?,?,?,80,?,0)', (uid, f'bench_{i:04}', 'disabled', now))
            for j in range(objects_each):
                oid = str(uuid.uuid5(uuid.NAMESPACE_OID, f'presence-bench-object-{i}-{j}'))
                conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,state,x,z,created) "
                             "VALUES (?,?,?,'starter',?,'placed',?,?,?)",
                             (oid, uid, uid, f'chair {j}', 5 + j % 6 * 3, 4 + j // 6 * 3, now))
                conn.execute('INSERT INTO furniture_locations VALUES (?,?)',
                             (oid, 'home' if j % 2 else 'village'))
            if i >= count:
                continue
            conn.execute('INSERT INTO sessions VALUES (?,?,?,?)',
                         (hashlib.sha256(token.encode()).hexdigest(), uid, now + 86400, now))
            life = homestead.initial()
            life['plots'][0].update(crop='turnip', watered=True, ready_at=now + 10)
            conn.execute('INSERT INTO homesteads VALUES (?,?)', (uid, json.dumps(life)))
            job = str(uuid.uuid5(uuid.NAMESPACE_OID, f'presence-bench-job-{i}'))
            conn.execute("INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated) "
                         "VALUES (?,?,'{}','building',10,?,?)", (job, uid, now, now))
            players.append({'id': uid, 'headers': {'Authorization': 'Bearer ' + token},
                            'job': job, 'scene': 'home' if i % 6 < 3 else 'village', 'since': 0})
        for start in range(0, count, 3):
            group = players[start:start + 3]
            host = group[0]['id']
            party = str(uuid.uuid5(uuid.NAMESPACE_OID, f'presence-bench-party-{start}'))
            conn.execute('INSERT INTO mp_parties VALUES (?,?,NULL,?)', (party, host, now))
            for p in group:
                conn.execute('INSERT INTO mp_members VALUES (?,?,?)', (p['id'], party, now))
                if p['id'] != host:
                    conn.execute('INSERT INTO mp_visits VALUES (?,?,?)', (p['id'], host, now + 3600))
                conn.execute('INSERT INTO mp_presence(user_id,host_id,scene,x,z,yaw,seen,home_seen) '
                             'VALUES (?,?,?,0,0,0,?,?)', (p['id'], host, p['scene'], now, now))
    return players


def percentile(values, fraction):
    values = sorted(values)
    return round(values[max(0, math.ceil(len(values) * fraction) - 1)], 3) if values else None


def summarize(records, elapsed):
    latencies = [r[1] for r in records]
    return {'requests': len(records), 'rps': round(len(records) / elapsed, 3),
            'p50_ms': percentile(latencies, .50), 'p95_ms': percentile(latencies, .95),
            'max_ms': round(max(latencies), 3) if latencies else None,
            'errors': sum(r[2] != 200 for r in records),
            'statuses': dict(Counter(str(r[2]) for r in records)),
            'response_bytes': sum(r[3] for r in records)}


def run_phase(client, players, seconds, interval):
    ready = threading.Barrier(len(players) + 1)
    started = [0.0]

    def play(index):
        p, records = players[index], []
        ready.wait()
        due = started[0] + (interval * index / len(players) if interval else 0)
        craft_at = home_at = due
        chat_at = p.get('chat_at', due)
        turn = p.get('turn', 0)
        while True:
            now = time.perf_counter()
            if due >= started[0] + seconds or now >= started[0] + seconds:
                break
            if due > now:
                time.sleep(due - now)
            calls = [('presence', 'POST', '/v1/social/presence',
                      {'scene': p['scene'], 'since': p['since'], 'x': turn % 10, 'z': 2})]
            now = time.perf_counter()
            if now >= craft_at:
                calls.append(('craft', 'GET', '/v1/studio/jobs/' + p['job'], None))
                craft_at = now + 3
            if now >= home_at:
                calls.append(('home', 'GET', '/v1/me', None))
                calls.append(('village', 'GET', '/v1/social/npc-homes/02_timber_house', None))
                home_at = now + 5
            if now >= chat_at:
                calls.append(('chat', 'POST', '/v1/social/messages',
                              {'request_id': str(uuid.uuid4()), 'channel': 'local',
                               'text': f'hello {index} {turn}'}))
                chat_at = now + 10
            for name, method, path, body in calls:
                before = time.perf_counter()
                try:
                    response = client.request(method, path, headers=p['headers'], json=body)
                    records.append((name, (time.perf_counter() - before) * 1000,
                                    response.status_code, len(response.content)))
                    if name == 'presence' and response.status_code == 200:
                        p['since'] = response.json()['chat']['cursor']
                except Exception as error:
                    records.append((name, (time.perf_counter() - before) * 1000,
                                    type(error).__name__, 0))
            turn += 1
            due = max(due + interval, time.perf_counter())
        p.update(chat_at=chat_at, turn=turn)
        return records

    with ThreadPoolExecutor(max_workers=len(players)) as pool:
        futures = [pool.submit(play, i) for i in range(len(players))]
        cpu = time.process_time()
        started[0] = time.perf_counter()
        ready.wait()
        records = [record for future in futures for record in future.result()]
        remaining = started[0] + seconds - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
        elapsed = time.perf_counter() - started[0]
        cpu = time.process_time() - cpu
    by_route = defaultdict(list)
    for record in records:
        by_route[record[0]].append(record)
    return {'elapsed_seconds': round(elapsed, 3), 'process_cpu_seconds': round(cpu, 3),
            'total': summarize(records, elapsed),
            'routes': {route: summarize(rows, elapsed) for route, rows in sorted(by_route.items())}}


def diagnostics(app, client, player):
    """Untimed SQL counts, never SQL text containing tokens or player data."""
    db, statements = app.state.db, []
    original = db.checkout

    def checkout():
        conn = original()
        conn.set_trace_callback(statements.append)
        return conn

    results = {}
    with patch.object(db, 'checkout', checkout):
        for name, method, path, body in (
                ('presence', 'POST', '/v1/social/presence', {'scene': player['scene'], 'since': player['since']}),
                ('craft', 'GET', '/v1/studio/jobs/' + player['job'], None)):
            statements.clear()
            response = client.request(method, path, headers=player['headers'], json=body)
            results[name] = {'status': response.status_code,
                             'statements': dict(Counter(s.split()[0].upper() for s in statements)),
                             'begin_immediate': sum(s.upper() == 'BEGIN IMMEDIATE' for s in statements)}
    for conn in db.idle:
        conn.set_trace_callback(None)
    with db.read() as conn:
        results['sqlite'] = {key: conn.execute('PRAGMA ' + key).fetchone()[0]
                             for key in ('journal_mode', 'busy_timeout', 'synchronous')}
        results['object_plan'] = [r[3] for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM objects WHERE owner_id=? AND state='placed' ORDER BY id",
            (player['id'],))]
    return results


def benchmark(args):
    from fastapi.testclient import TestClient
    from server.app import create_app
    from server.config import Settings
    temp_root = ROOT / '.tools' / 'bench-presence'
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as directory:
        app = create_app(Settings(data_dir=Path(directory), mode='demo', paid_enabled=False,
                                  studio_llm='fixture'), worker_enabled=False)
        try:
            players = seed(app, args.players, args.history_users, args.objects)
            with TestClient(app) as client:
                warmup = run_phase(client, players, args.warmup, args.interval)
                if warmup['total']['errors']:
                    raise RuntimeError('benchmark_warmup_errors: ' + json.dumps(warmup['total']))
                result = run_phase(client, players, args.seconds, args.interval)
                result['diagnostics'] = diagnostics(app, client, players[0])
            result['config'] = {k: v for k, v in vars(args).items() if k != 'output'}
            result['environment'] = {'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
                                     'platform': platform.platform(), 'cpu_count': os.cpu_count(),
                                     'transport': 'TestClient', 'worker_enabled': False}
            result['database_bytes'] = sum(p.stat().st_size for p in Path(directory).glob('world.sqlite3*'))
            return result
        finally:
            app.state.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--players', type=int, choices=range(1, 121), default=60, metavar='1..120')
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--warmup', type=float, default=3)
    parser.add_argument('--interval', type=float, default=1, help='presence seconds; 0 = saturation')
    parser.add_argument('--history-users', type=int, default=300)
    parser.add_argument('--objects', type=int, default=24, help='placed furniture per account, half per room')
    parser.add_argument('--label', default='working-tree')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if any(not math.isfinite(v) for v in (args.seconds, args.warmup, args.interval)) or \
            args.seconds <= 0 or args.warmup <= 0 or args.interval < 0 or args.history_users < 0 or args.objects < 0:
        parser.error('durations must be finite and positive; interval and counts must be nonnegative')
    if args.output and not args.output.resolve().is_relative_to(ROOT):
        parser.error('output must stay inside this worktree')
    with isolated_environment():
        result = benchmark(args)
    report = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding='utf-8')
    print(report)
    return int(result['total']['errors'] > 0)


if __name__ == '__main__':
    raise SystemExit(main())

