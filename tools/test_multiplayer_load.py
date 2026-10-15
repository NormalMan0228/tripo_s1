"""Local multiplayer load tests against an owned, isolated server; never contacts a paid provider.

    .tools\\server-venv\\Scripts\\python.exe tools\\test_multiplayer_load.py                 (social, 60 players, 180 s)
    .tools\\server-venv\\Scripts\\python.exe tools\\test_multiplayer_load.py --adaptive      (alone = 1 Hz presence)
    .tools\\server-venv\\Scripts\\python.exe tools\\test_multiplayer_load.py --legacy-share 1 --server-root <old checkout>
    .tools\\server-venv\\Scripts\\python.exe tools\\test_multiplayer_load.py --scenario coop  (three-player expedition)

social: a classroom. Players sit in small villages (a host and two guests, one of them indoors),
alone in their village, in the workshop, or on a survival expedition, and poll presence the way
the game does (village/home 4 Hz, workshop heartbeat, survival input 5 Hz). Clients with chat v2
send the cursor and the place, chat on the village, everyone and whisper channels, and a third of
them keep the social window open (/v1/social/people every 5 s). Released clients (--legacy-share)
use the old presence and messages. Reports latency per route, chat delivery time, the server
process's CPU and memory, and database growth.

The server is one uvicorn worker on port 8867 (the production command line, demo mode, WAL
SQLite) with a temporary data directory that is deleted afterwards. Accounts, sessions, villages,
visits, friendships and placed objects are seeded straight into SQLite (sign-up is rate limited).
This measures this PC; docs/design/SOCIAL_API.md explains the t4g.small estimate.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = 8867
WARMUP_SECONDS = 10


# --- the server process ------------------------------------------------------------------------
def process_tree(pid):
    """pid and its descendants (on Windows a venv python.exe is a launcher with a child)."""
    if sys.platform != 'win32':
        return [pid]
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD),
                    ('szExeFile', ctypes.c_wchar * 260)]
    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    parents = {}
    ok = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
    while ok:
        parents[entry.th32ProcessID] = entry.th32ParentProcessID
        ok = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    kernel.CloseHandle(snapshot)
    tree, grew = {pid}, True
    while grew:
        grew = False
        for child, parent in parents.items():
            if parent in tree and child not in tree:
                tree.add(child)
                grew = True
    return sorted(tree)


def cpu_and_memory(pids):
    """(CPU seconds, resident bytes, peak resident bytes) summed over the processes."""
    cpu = rss = peak = 0
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
        kernel, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        kernel.OpenProcess.restype = wintypes.HANDLE
        for pid in pids:
            handle = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
            if not handle:
                continue
            times = [wintypes.FILETIME() for _ in range(4)]
            if kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                cpu += sum((t.dwHighDateTime << 32 | t.dwLowDateTime) / 1e7 for t in times[2:])
            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                rss += counters.WorkingSetSize
                peak += counters.PeakWorkingSetSize
            kernel.CloseHandle(handle)
        return cpu, rss, peak
    for pid in pids:
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            cpu += (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
            status = Path(f'/proc/{pid}/status').read_text()
            rss += int(re.search(r'VmRSS:\s+(\d+)', status).group(1)) * 1024
            peak += int(re.search(r'VmHWM:\s+(\d+)', status).group(1)) * 1024
        except (OSError, AttributeError):
            pass
    return cpu, rss, peak


def start_server(server_root, data, port, extra_env):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('TRIPOTHON_', 'TRIPO_', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'VILLAGEN_'))}
    env.update(TRIPOTHON_MODE='demo', TRIPOTHON_DATA_DIR=str(data), TRIPO_ENABLE_PAID='false', TRIPOTHON_STUDIO_LLM='fixture', **extra_env)
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server.app:create_app', '--factory', '--host', '127.0.0.1', '--port', str(port),
                                '--workers', '1', '--no-access-log', '--no-proxy-headers'], cwd=server_root, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    url = f'http://127.0.0.1:{port}'
    for _ in range(150):
        try:
            response = httpx.get(url+'/health', timeout=.5)
            if response.status_code == 200:
                return process, url, response.json()
        except httpx.HTTPError:
            pass
        if process.poll() is not None:
            raise RuntimeError('isolated_server_exited')
        time.sleep(.1)
    process.terminate()
    raise RuntimeError('isolated_server_not_ready')


def stop_server(process):
    pids = process_tree(process.pid)
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
    if sys.platform == 'win32':
        for pid in pids[1:]:
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- seeding -----------------------------------------------------------------------------------
def seed(database, users, legacy_share, friends_each, objects_each, seed_value):
    """Accounts with sessions, villages with guests, friendships and placed furniture."""
    rng = random.Random(seed_value)
    conn = sqlite3.connect(database, timeout=30, isolation_level=None)
    conn.execute('PRAGMA busy_timeout=30000')
    now = time.time()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    people = []
    conn.execute('BEGIN IMMEDIATE')
    for index in range(users):
        user_id, token = str(uuid.uuid4()), secrets.token_urlsafe(24)
        name = f'load_{index:03d}'
        conn.execute('INSERT INTO users(id,username,password_hash,shards,created) VALUES (?,?,?,?,?)', (user_id, name, 'x', 0, now))
        conn.execute('INSERT INTO sessions(token_hash,user_id,expires,created) VALUES (?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user_id, now+86400, now))
        for k in range(objects_each):
            conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,state,x,z,created) VALUES (?,?,?,'starter',?,'placed',?,?,?)",
                         (str(uuid.uuid4()), user_id, user_id, 'chair %d' % k, -20+4*(k % 10), -20+4*(k//10), now))
        people.append({'index': index, 'id': user_id, 'name': name, 'headers': {'Authorization': 'Bearer '+token}})
    # Roles: villages of three (host outdoors, one guest outdoors, one indoors), then alone in the
    # village, the workshop, and survival expeditions.
    groups = int(users * .75) // 3
    for g in range(groups):
        host, a, b = people[3*g:3*g+3]
        host['role'], a['role'], b['role'] = 'host', 'guest', 'guest_home'
        for guest in (a, b):
            guest['host'] = host['id']
            conn.execute('INSERT INTO mp_visits VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET host_id=excluded.host_id', (guest['id'], host['id'], now+3600))
    rest = people[3*groups:]
    for i, p in enumerate(rest):
        p['role'] = ('alone', 'alone', 'alone', 'workshop', 'survival')[i % 5]
    for p in people:
        p['legacy'] = rng.random() < legacy_share
        p['friends'] = []
    if 'social_friends' in tables:
        for p in people:
            for other in rng.sample(people, min(friends_each, users-1)):
                if other is not p and other['id'] not in p['friends']:
                    p['friends'].append(other['id'])
                    other['friends'].append(p['id'])
                    conn.execute('INSERT OR IGNORE INTO social_friends VALUES (?,?,?)', (p['id'], other['id'], now))
                    conn.execute('INSERT OR IGNORE INTO social_friends VALUES (?,?,?)', (other['id'], p['id'], now))
    conn.execute('COMMIT')
    conn.close()
    names = {p['id']: p['name'] for p in people}
    for p in people:
        p['friend_names'] = [names[f] for f in p['friends']]
    return people


def database_size(data):
    return sum(f.stat().st_size for f in Path(data).glob('world.sqlite3*'))


def row_counts(database):
    with sqlite3.connect(database, timeout=30) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {t: conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
                for t in ('mp_messages', 'requests', 'audit', 'security_events', 'mp_invites', 'social_requests') if t in tables}


# --- the classroom -----------------------------------------------------------------------------
class Stats:
    def __init__(self, started):
        self.started = started
        self.latency, self.status, self.errors = {}, {}, []
        self.sent, self.arrivals = {}, []
        self.rate_limited = 0

    def record(self, route, ms, status):
        if time.perf_counter()-self.started < WARMUP_SECONDS:
            return
        self.latency.setdefault(route, []).append(ms)
        key = f'{route} {status}'
        self.status[key] = self.status.get(key, 0)+1

    def summary(self, seconds):
        out = {}
        for route, values in sorted(self.latency.items()):
            ordered = sorted(values)
            pick = lambda q: round(ordered[min(len(ordered)-1, int(len(ordered)*q))], 1)
            out[route] = {'requests': len(ordered), 'per_second': round(len(ordered)/seconds, 1), 'p50_ms': pick(.5),
                          'p95_ms': pick(.95), 'p99_ms': pick(.99), 'max_ms': round(ordered[-1], 1)}
        return out


async def classroom(url, people, seconds, health, chat_every, adaptive, together_s, alone_s, people_s, seed_value):
    features = set(health.get('social_features') or [])
    chat2 = 'chat2' in features
    global_chat = bool(health.get('global_chat'))
    limits = httpx.Limits(max_connections=len(people)+20, max_keepalive_connections=len(people)+20)
    started = time.perf_counter()
    stats = Stats(started)
    deadline = started+seconds+WARMUP_SECONDS
    rng = random.Random(seed_value+1)
    tag = re.compile(r'^load (\d+) ')
    counter = [0]
    async with httpx.AsyncClient(base_url=url, timeout=10, limits=limits) as client:

        async def call(route, method, path, headers, body=None):
            before = time.perf_counter()
            try:
                if method == 'GET':
                    response = await client.get(path, headers=headers)
                else:
                    response = await client.post(path, headers=headers, json=body)
            except httpx.HTTPError as error:
                stats.errors.append({'route': route, 'error': type(error).__name__})
                return None
            stats.record(route, (time.perf_counter()-before)*1000, response.status_code)
            if response.status_code == 429:
                stats.rate_limited += 1
            elif response.status_code != 200 and len(stats.errors) < 50:
                stats.errors.append({'route': route, 'status': response.status_code, 'detail': response.text[:120]})
            return response

        async def presence_loop(p):
            modern = chat2 and not p['legacy']
            role = p['role']
            scene = {'host': 'village', 'guest': 'village', 'guest_home': 'home', 'alone': 'village'}.get(role, 'away')
            place = {'workshop': 'workshop', 'survival': 'expedition'}.get(role, scene)
            in_village = role in ('host', 'guest', 'guest_home', 'alone')
            interval = (1.0 if modern else 3.0) if role == 'workshop' else 2.0 if role == 'survival' else together_s
            cursor = 0
            await asyncio.sleep(rng.random()*interval)
            while time.perf_counter() < deadline:
                tick = time.perf_counter()
                body = {'scene': scene, 'x': rng.uniform(-5, 5), 'z': rng.uniform(-5, 5), 'yaw': 0, 'vx': 0.5, 'vz': 0, 't': tick}
                if modern:
                    body.update(since=cursor, place=place)
                response = await call('presence', 'POST', '/v1/social/presence', p['headers'], body)
                together = True
                if response is not None and response.status_code == 200:
                    reply = response.json()
                    space = reply.get('space') or {}
                    together = len(space.get('players') or []) > 1
                    block = reply.get('chat')
                    if block:
                        cursor = block['cursor']
                        if not block['history']:
                            now = time.perf_counter()
                            for line in block['lines']:
                                found = tag.match(line['text'])
                                if found and line['user_id'] != p['id'] and int(found.group(1)) in stats.sent and now-started > WARMUP_SECONDS:
                                    stats.arrivals.append((now-stats.sent[int(found.group(1))])*1000)
                wait = (alone_s if adaptive and not together else together_s) if in_village else interval
                await asyncio.sleep(max(0, tick+wait-time.perf_counter()))

        async def chat_loop(p):
            modern = chat2 and not p['legacy']
            await asyncio.sleep(min(rng.uniform(0, chat_every), seconds))
            while time.perf_counter() < deadline:
                counter[0] += 1
                number = counter[0]
                text = f'load {number} 안녕 반가워요'
                if rng.random() < .02:
                    text = f'load {number} 아 시발 렉'
                body = {'request_id': str(uuid.uuid4()), 'text': text}
                if modern:
                    roll = rng.random()
                    if roll < .15 and global_chat:
                        body['channel'] = 'global'
                    elif roll < .25 and p['friend_names']:
                        body.update(channel='whisper', to=rng.choice(p['friend_names']))
                    else:
                        body['channel'] = 'local'
                stats.sent[number] = time.perf_counter()
                await call('messages', 'POST', '/v1/social/messages', p['headers'], body)
                await asyncio.sleep(min(rng.expovariate(1/chat_every), max(0, deadline-time.perf_counter())))

        async def people_loop(p):
            await asyncio.sleep(rng.uniform(0, people_s))
            while time.perf_counter() < deadline:
                tick = time.perf_counter()
                await call('people', 'GET', '/v1/social/people', p['headers'])
                await asyncio.sleep(max(0, tick+people_s-time.perf_counter()))

        async def survival_loop(p):
            response = await call('runs_start', 'POST', '/v1/runs', p['headers'], {'request_id': str(uuid.uuid4()), 'difficulty': 'relaxed'})
            if response is None or response.status_code != 200:
                return
            run = response.json()['id']
            sequence = 0
            while time.perf_counter() < deadline:
                tick = time.perf_counter()
                sequence += 1
                response = await call('survival_input', 'POST', '/v1/runs/'+run+'/input', p['headers'], {'sequence': sequence, 'dx': .3})
                if response is not None and response.status_code == 200:
                    sequence = response.json().get('sequence', sequence)
                await asyncio.sleep(max(0, tick+.2-time.perf_counter()))

        tasks = []
        for p in people:
            tasks.append(presence_loop(p))
            if chat_every > 0:
                tasks.append(chat_loop(p))
            if chat2 and not p['legacy'] and p['index'] % 3 == 0:
                tasks.append(people_loop(p))
            if p['role'] == 'survival':
                tasks.append(survival_loop(p))
        await asyncio.gather(*tasks)
    arrivals = sorted(stats.arrivals)
    pick = lambda q: round(arrivals[min(len(arrivals)-1, int(len(arrivals)*q))]) if arrivals else None
    return {'routes': stats.summary(seconds), 'statuses': stats.status, 'rate_limited_429': stats.rate_limited,
            'errors': stats.errors[:20], 'error_count': len(stats.errors),
            'chat_delivery_ms': {'deliveries': len(arrivals), 'p50': pick(.5), 'p95': pick(.95), 'max': pick(.999)}}


def social_scenario(args):
    server_root = Path(args.server_root).resolve() if args.server_root else ROOT
    data = Path(tempfile.mkdtemp(prefix='villagen-load-'))
    env = {'VILLAGEN_GLOBAL_CHAT': 'on' if args.global_chat == 'on' else 'off'}
    process = None
    try:
        process, url, health = start_server(server_root, data, args.port, env)
        people = seed(data/'world.sqlite3', args.users, args.legacy_share, args.friends, args.objects, args.seed)
        size_before = database_size(data)
        tree = process_tree(process.pid)
        wall = time.perf_counter()

        async def run():
            task = asyncio.create_task(classroom(url, people, args.seconds, health, args.chat_every, args.adaptive,
                                                 args.together, args.alone, args.people_every, args.seed))
            # The CPU window starts after the warm-up, like the latency figures.
            await asyncio.sleep(WARMUP_SECONDS)
            mark = (cpu_and_memory(tree)[0], time.perf_counter(), time.process_time())
            return await task, mark
        result, (cpu_mark, wall_mark, own_mark) = asyncio.run(run())
        cpu_after, rss, peak = cpu_and_memory(tree)
        measured = time.perf_counter()-wall_mark
        roles = {}
        for p in people:
            roles[p['role']] = roles.get(p['role'], 0)+1
        total = sum(r['requests'] for r in result['routes'].values())
        return {
            'environment': f'isolated localhost, {os.cpu_count()} logical CPUs ({sys.platform}); one uvicorn worker; not the VM',
            'server': 'this checkout' if server_root == ROOT else str(server_root),
            'social_features': sorted(health.get('social_features') or []), 'global_chat': health.get('global_chat'),
            'users': args.users, 'roles': roles, 'legacy_clients': sum(p['legacy'] for p in people),
            'adaptive_presence': args.adaptive, 'presence_together_s': args.together, 'presence_alone_s': args.alone,
            'chat_every_s': args.chat_every, 'people_every_s': args.people_every, 'measured_seconds': round(measured, 1),
            'requests_per_second': round(total/measured, 1),
            'server_cpu_percent_of_one_core': round((cpu_after-cpu_mark)/measured*100, 1),
            'server_cpu_ms_per_request': round((cpu_after-cpu_mark)*1000/max(1, total), 3),
            'server_memory_mb': round(rss/2**20, 1), 'server_peak_memory_mb': round(peak/2**20, 1),
            'load_generator_cpu_percent': round((time.process_time()-own_mark)/measured*100, 1),
            'database_bytes_before': size_before, 'database_bytes_after': database_size(data),
            'database_growth_kb_per_minute': round((database_size(data)-size_before)/1024/((time.perf_counter()-wall)/60), 1),
            'rows_after': row_counts(data/'world.sqlite3'), **result}
    finally:
        if process:
            stop_server(process)
        shutil.rmtree(data, ignore_errors=True)


# --- the original three-player expedition test -----------------------------------------------------
async def expedition(url, duration):
    measurements, failures = [], []
    async with httpx.AsyncClient(base_url=url, timeout=12, limits=httpx.Limits(max_keepalive_connections=0)) as client:
        users = []

        async def post(path, headers=None, **body):
            response = await client.post(path, headers=headers, json={'request_id': str(uuid.uuid4()), **body})
            response.raise_for_status()
            return response.json()
        for index in range(3):
            name = f'load_{index}_{secrets.token_hex(3)}'
            response = await client.post('/v1/auth/register', json={'username': name, 'password': secrets.token_urlsafe(20)+'Aa!'})
            response.raise_for_status()
            users.append((name, {'Authorization': 'Bearer '+response.json()['token']}))
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
                body = {'sequence': sequence}
                # Keep camp lit using the real inventory, then exercise hunger.
                if index == 0 and sequence in (1, 160): body['action'] = 'fire'
                if snapshot and snapshot['hunger'] < 70 and snapshot['inventory']['berry'] > 0: body['action'] = 'eat'
                before = time.perf_counter()
                try:
                    response = await client.post('/v1/coop/runs/'+run['id']+'/input', headers=headers, json=body)
                    measurements.append((time.perf_counter()-before)*1000)
                    if response.status_code != 200:
                        failures.append({'player': index, 'status': response.status_code, 'error': response.json().get('detail')})
                    else:
                        snapshot = response.json()
                        sequence = snapshot['sequence']
                except httpx.HTTPError as error:
                    failures.append({'player': index, 'error': type(error).__name__})
                if sequence % 10 == 0:
                    response = await client.post('/v1/social/presence', headers=headers, json={'scene': 'away'})
                    if response.status_code != 200: failures.append({'player': index, 'presence_status': response.status_code})
                # Never accumulate an unbounded catch-up burst after a slow request.
                next_input = max(next_input, time.perf_counter())
            summaries.append({'player': index, 'elapsed': snapshot.get('elapsed') if snapshot else None,
                              'status': snapshot.get('status') if snapshot else None})
        await asyncio.gather(*(player(i, h) for i, (_, h) in enumerate(users)))
        ordered = sorted(measurements)
        return dict(environment='isolated localhost; not production capacity', users=3,
                    duration_seconds=round(time.perf_counter()-started, 2), survival_requests=len(ordered),
                    failures=failures, mean_ms=round(statistics.mean(ordered), 2),
                    p95_ms=round(ordered[min(len(ordered)-1, int(len(ordered)*.95))], 2),
                    max_ms=round(max(ordered), 2), players=summaries)


def coop_scenario(args):
    data = Path(tempfile.mkdtemp(prefix='villagen-load-'))
    process = None
    try:
        process, url, _ = start_server(ROOT, data, args.port, {})
        report = asyncio.run(expedition(url, args.seconds))
        report['failures_found'] = bool(report['failures'])
        return report
    finally:
        if process:
            stop_server(process)
        shutil.rmtree(data, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--scenario', choices=('social', 'coop'), default='social')
    parser.add_argument('--seconds', type=int, default=180, help='measured seconds (after a 10 s warm-up)')
    parser.add_argument('--users', type=int, default=60)
    parser.add_argument('--legacy-share', type=float, default=0.0, help='share of released (0.11.x) clients, 0..1')
    parser.add_argument('--adaptive', action='store_true', help='players alone poll at --alone seconds')
    parser.add_argument('--together', type=float, default=.25, help='presence interval with others around (s)')
    parser.add_argument('--alone', type=float, default=1.0, help='presence interval alone with --adaptive (s)')
    parser.add_argument('--chat-every', type=float, default=20, help="mean seconds between one player's lines (0: no chat)")
    parser.add_argument('--people-every', type=float, default=5, help='social window refresh (s)')
    parser.add_argument('--friends', type=int, default=8, help='friendships seeded per player')
    parser.add_argument('--objects', type=int, default=12, help='placed furniture per village')
    parser.add_argument('--global-chat', choices=('on', 'off'), default='on')
    parser.add_argument('--server-root', help='run another checkout of the server (a baseline)')
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--output', help='JSON report path (default artifacts/multiplayer-load-<scenario>.json)')
    args = parser.parse_args()
    if not 5 <= args.seconds <= 900 or not 3 <= args.users <= 300 or not 0 <= args.legacy_share <= 1:
        parser.error('seconds 5..900, users 3..300, legacy share 0..1')
    report = social_scenario(args) if args.scenario == 'social' else coop_scenario(args)
    output = Path(args.output or ROOT/'artifacts'/f'multiplayer-load-{args.scenario}.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return bool(report.get('error_count') or report.get('failures_found'))


if __name__ == '__main__':
    raise SystemExit(main())
