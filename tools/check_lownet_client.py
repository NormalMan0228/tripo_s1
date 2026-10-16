"""Run Godot's real gzip/304 transport smoke against a loopback-only fixture."""
from __future__ import annotations

import argparse
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    events: list[tuple[str, str, tuple[str, int]]] = []

    class Fixture(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_args):
            pass

        def respond(self, status: int, value: dict | None):
            data = gzip.compress(json.dumps(value).encode(), mtime=0) if value is not None else b''
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('ETag', 'W/"wire-fixture"')
            self.send_header('X-Villagen-Notice-Version', '42')
            if value is not None:
                self.send_header('Content-Encoding', 'gzip')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            events.append((self.path, self.headers.get('Accept-Encoding', ''), self.client_address))
            if self.path != '/v1/studio':
                self.respond(404, {'detail': 'not_found'})
            elif self.headers.get('If-None-Match') == 'W/"wire-fixture"':
                self.respond(304, None)
            else:
                self.respond(200, {'wire': 'studio', 'padding': 'x' * 4096})

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            events.append((self.path, self.headers.get('Accept-Encoding', ''), self.client_address))
            self.respond(200, {'wire': 'presence', 'padding': 'x' * 4096})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    scratch = root / '.codex-tmp'
    scratch.mkdir(exist_ok=True)
    environment = dict(os.environ, LOWNET_TEST_PORT=str(server.server_port))
    try:
        result = subprocess.run(
            [str(args.godot), '--headless', '--path', str(root / 'game'), '--script',
             'res://tests/net_policy_http_check.gd', '--log-file', str(scratch / 'lownet-http.log')],
            cwd=root, env=environment, timeout=30, capture_output=True, text=True, encoding='utf-8',
            errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    print(result.stdout)
    if result.returncode:
        print(result.stderr)
        return result.returncode
    presence = [event for event in events if event[0] == '/v1/social/presence']
    checked = (len(events) == 4 and len(presence) == 2
               and presence[0][2] == presence[1][2]
               and all('gzip' in event[1] for event in events))
    print(f'LOOPBACK_WIRE_RESULT requests={len(events)} presence_reused={checked}')
    return 0 if checked else 1


if __name__ == '__main__':
    raise SystemExit(main())
