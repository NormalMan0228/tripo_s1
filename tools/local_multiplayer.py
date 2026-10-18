"""Run two isolated local Villagen players and a loopback fixture server."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def request(base, path, payload=None, token=''):
    headers = {'Content-Type': 'application/json', 'x-villagen-version': '0.11.9.5'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=20) as response:
        return json.load(response)


def mutate(base, path, token, **fields):
    return request(base, path, dict(request_id=str(uuid.uuid4()), **fields), token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--players', type=int, choices=(2, 3), default=2)
    parser.add_argument('--seconds', type=int, default=0, help='Automatic smoke-test duration after both clients join')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--pack', type=Path)
    args = parser.parse_args()
    data = ROOT / 'artifacts' / 'school-demo'
    data.mkdir(parents=True, exist_ok=True)
    # Refuse a second launcher: never reuse or stop someone else's server.
    lock = data / 'running.lock'
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit('Another demo is running. Close its game windows first. If it crashed, remove artifacts/school-demo/running.lock after checking the processes.')
    os.close(lock_fd)
    processes, handles, clients = [], [], []
    try:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        env = os.environ.copy()
        env['TRIPOTHON_STORY'] = 'off'
        env['TRIPOTHON_MODE'] = 'demo'

        def spawn(command, label, child_env):
            output = open(data / (label + '.log'), 'w', encoding='utf8')
            handles.append(output)
            process = subprocess.Popen(command, cwd=ROOT, env=child_env, stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            processes.append(process)
            return process

        server = spawn([sys.executable, str(ROOT / 'tools/demo_server.py'), '--port', str(port), '--data-dir', str(data / 'server')], 'server', env)
        for attempt in range(120):
            if server.poll() is not None:
                raise RuntimeError('Demo server stopped; see artifacts/school-demo/server.log')
            try:
                health = request(base, '/health')
                if health.get('service') == 'tripothon':
                    break
            except (OSError, ValueError):
                time.sleep(.25)
        else:
            raise RuntimeError('Demo server did not become ready')

        credentials_path = data / 'accounts.json'
        if credentials_path.exists():
            credentials = json.loads(credentials_path.read_text(encoding='utf8'))
        else:
            credentials = [{'username': f'demo_player{i+1}', 'password': secrets.token_urlsafe(24)} for i in range(3)]
            credentials_path.write_text(json.dumps(credentials), encoding='utf8')
        tokens = []
        for i, account in enumerate(credentials[:args.players]):
            try:
                auth = request(base, '/v1/auth/login', account)
            except urllib.error.HTTPError as error:
                if error.code != 401:
                    raise
                auth = request(base, '/v1/auth/register', account)
                profile = auth.get('profile', {})
                look = dict(profile.get('avatar', {}), character=['m1', 'f2', 'm3'][i])
                mutate(base, '/v1/profile', auth['token'], version=profile.get('version', 0), avatar=look)
            tokens.append(auth['token'])
            # Windows Godot resolves user:// from APPDATA (verified with this engine).
            # Thus settings, NPC data, logs and patch state all stay separate.
            profile_root = data / f'player{i+1}'
            user_dir = profile_root / 'Godot/app_userdata/Tripothon — Seven Nights'
            user_dir.mkdir(parents=True, exist_ok=True)
            settings = user_dir / 'settings.cfg'
            if not settings.exists():
                settings.write_text('[game]\nlanguage="ko"\n[graphics]\npreset="low"\nfps_cap=30\nwindow_mode="windowed"\n[audio]\nbackground_mute=true\n', encoding='utf8')
            ready = profile_root / 'ready.json'
            ready.unlink(missing_ok=True)
            child_env = dict(env, APPDATA=str(profile_root), VILLAGEN_DEMO_USER=account['username'],
                             VILLAGEN_DEMO_PASSWORD=account['password'], VILLAGEN_DEMO_READY=str(ready))
            # The hardened release template forbids external bootstrap scripts.
            # Use the existing editor runtime to run the exact release PCK with this
            # local-only login helper; normal Villagen.exe remains hardened.
            engine = ROOT / '.tools/godot/Godot_v4.7.2-stable_win64_console.exe'
            if not engine.is_file():
                raise RuntimeError('The matching game executable was not found')
            command = [str(engine)]
            if args.headless:
                command += ['--headless']
            command += ['--main-pack', str(args.pack.resolve())] if args.pack else ['--path', str(ROOT / 'game')]
            command += ['--script', str(ROOT / 'game/tests/demo_client.gd'), '--windowed', '--resolution', '960x640',
                        '--position', f'{30+i*650},{40+i*40}', '--', '--no-patch', f'--server={base}', '--hour=14']
            if i > 0:
                command += ['--mute']
            client = spawn(command, f'player{i+1}', child_env)
            clients.append(client)
            # Loading one village at a time avoids doubling peak load on the PC.
            for attempt in range(900):
                if client.poll() is not None:
                    raise RuntimeError(f'Player {i+1} stopped; see its log')
                if ready.exists():
                    break
                time.sleep(.2)
            else:
                raise RuntimeError(f'Player {i+1} login timed out')

        for i in range(1, args.players):
            invitation = mutate(base, '/v1/social/invites', tokens[0], username=credentials[i]['username'], kind='village')
            mutate(base, '/v1/social/invites/' + invitation['id'] + '/accept', tokens[i])
        # The guest clients pick up their new village on their normal social poll.
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            states = [request(base, '/v1/social', token=token) for token in tokens]
            if states[0].get('host_id') and all(state.get('host_id') == states[0]['host_id'] for state in states):
                break
            time.sleep(.5)
        else:
            raise RuntimeError('Players did not join the same village')
        if not args.headless:
            time.sleep(3)
            for i in range(args.players):
                (data / f'player{i+1}' / 'capture.request').write_text('capture', encoding='utf8')
        (data / 'last-run.json').write_text(json.dumps({'version':health.get('version'), 'players':args.players,
            'same_village':True, 'profiles':[str(data / f'player{i+1}') for i in range(args.players)],
            'server':base, 'headless':args.headless}, indent=2), encoding='utf8')
        print('READY: two independent game windows share a local village. Use Alt+Tab to switch; K opens party controls.', flush=True)
        started = time.monotonic()
        while any(client.poll() is None for client in clients):
            if args.seconds and time.monotonic() - started >= args.seconds:
                break
            if server.poll() is not None:
                raise RuntimeError('Demo server stopped unexpectedly')
            time.sleep(.5)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for handle in handles:
            handle.close()
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
