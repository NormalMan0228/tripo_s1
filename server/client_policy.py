"""Client versions and maintenance notices that an operator changes while the server runs.

<data>/client_policy.json holds them. ops/notice.sh writes it through this module's command line
(no restart, no redeploy); the server notices a change within CHECK_SECONDS. Every key is
optional and no file means everything is off, so a server nobody configured (the judging
server) answers exactly as before.

  min_client_version     games older than this get 426 client_update_required
  latest_client_version  a newer game is published: games show a gentle banner
  client_download_url    where players get it (https only)
  notice                 scheduled maintenance {"id", "starts_at" (unix s), "minutes",
                         "message", "hold"}: announced ahead, and from starts_at every route
                         except /health and /v1/client answers 503 server_maintenance, until
                         starts_at + minutes, or with hold until an operator cancels it.

Games send X-Villagen-Version (api.gd); released games up to 0.11.2 send none and count as older
than any minimum. Old games print an error's detail instead of parsing new codes, so the 426 and
503 details are short Korean sentences (with the download link) and the code travels in "code".
Every reply carries X-Villagen-Notice-Version, so a running game notices a change for free.

    python -m server.client_policy show
    python -m server.client_policy maintenance --in 30 --minutes 10 [--message TEXT] [--hold]
    python -m server.client_policy cancel
    python -m server.client_policy release 0.11.4 https://...   (latest version + download link)
    python -m server.client_policy min 0.11.4 | latest 0.11.4 | url https://... (each also: off)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders

from .config import ROOT
from .security import clean_text

FILE_NAME = 'client_policy.json'
CHECK_SECONDS = 2.0
NOTICE_HEADER = 'x-villagen-notice-version'
# Always open: the light check and the download information.
OPEN_PATHS = frozenset(('/health', '/v1/client', '/v1/ops/usage'))
# Released games (no version header) may still sign in: they open the player's room next, and the
# room prints an error's detail after its own prefix, so the update sentence reaches them there.
LEGACY_OPEN_PATHS = frozenset(('/v1/auth/login', '/v1/auth/register', '/v1/auth/logout'))
MAX_MESSAGE = 120
MAX_MINUTES = 24 * 60
DEFAULT_MESSAGE = '서버 점검이 있어요.'
KOREA = 9 * 3600
VERSION = re.compile(r'v?(\d{1,4}(?:\.\d{1,4}){0,3})(?:[-+][0-9A-Za-z.-]{0,32})?')
URL = re.compile(r'https://[A-Za-z0-9.-]+(?::\d{1,5})?(?:/[\x21-\x7e]*)?')


def parse_version(value):
    """'0.11.10' -> (0, 11, 10, 0); a leading v and a suffix (-school) are ignored; None if unreadable."""
    if not isinstance(value, str):
        return None
    match = VERSION.fullmatch(value.strip())
    if not match:
        return None
    parts = [int(p) for p in match.group(1).split('.')]
    return tuple(parts + [0] * (4 - len(parts)))


def canonical(value):
    match = VERSION.fullmatch(value.strip()) if isinstance(value, str) else None
    return match.group(1) if match else ''


def older(version, minimum):
    """True when version is below minimum. No minimum: never; no or unreadable version: always."""
    floor = parse_version(minimum)
    if floor is None:
        return False
    mine = parse_version(version)
    return mine is None or mine < floor


def valid_url(value):
    return isinstance(value, str) and len(value) <= 300 and bool(URL.fullmatch(value))


def clean(raw):
    """The file's settings with anything unreadable dropped (that part is then off)."""
    out = {'min_client_version': '', 'latest_client_version': '', 'client_download_url': '', 'notice': None}
    if not isinstance(raw, dict):
        return out
    for key in ('min_client_version', 'latest_client_version'):
        out[key] = canonical(raw.get(key))
    if valid_url(raw.get('client_download_url')):
        out['client_download_url'] = raw['client_download_url']
    notice = raw.get('notice')
    if isinstance(notice, dict):
        try:
            starts, minutes = float(notice['starts_at']), int(notice['minutes'])
            if math.isfinite(starts) and 0 < minutes <= MAX_MINUTES:
                out['notice'] = {'id': clean_text(str(notice.get('id', '')))[:40] or str(int(starts)),
                                 'starts_at': starts, 'minutes': minutes,
                                 'message': clean_text(str(notice.get('message', '')))[:MAX_MESSAGE] or DEFAULT_MESSAGE,
                                 'hold': bool(notice.get('hold', False))}
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    return out


def public_notice(notice, now):
    """What players see of a notice; None once a notice without hold is over."""
    if not notice:
        return None
    start = notice['starts_at']
    end = start + notice['minutes'] * 60
    active = start <= now and (notice['hold'] or now < end)
    if not active and now >= end:
        return None
    return {'id': notice['id'], 'message': notice['message'], 'minutes': notice['minutes'],
            'starts_at': int(start), 'ends_at': int(end),
            'starts_in': max(0, math.ceil(start - now)), 'ends_in': max(0, math.ceil(end - now)),
            'active': active, 'hold': notice['hold']}


def update_sentence(state):
    target = state['latest_client_version']
    if not target or older(target, state['min_client_version']):
        target = state['min_client_version']
    url = state['client_download_url']
    return '새 버전(%s)이 나왔어요. 게임을 새로 받아 주세요%s' % (target, ': ' + url if url else '.')


def maintenance_sentence(notice):
    left = math.ceil(notice['ends_in'] / 60)
    if left >= 1:
        return '서버 점검 중이에요. 약 %d분 뒤에 다시 들어와 주세요.' % left
    return '서버 점검 중이에요. 곧 끝나요. 잠시 뒤 다시 들어와 주세요.'


class ClientPolicy:
    """Reads <data>/client_policy.json, again whenever it changed (checked every few seconds)."""

    def __init__(self, path, clock=time.time, check_seconds=CHECK_SECONDS):
        self.path = Path(path)
        self.clock = clock
        self.check_seconds = check_seconds
        self._checked = -math.inf
        self._signature = None
        self._state = clean(None)

    def state(self):
        tick = time.monotonic()
        if tick - self._checked < self.check_seconds:
            return self._state
        self._checked = tick
        try:
            stat = self.path.stat()
        except OSError:
            self._signature, self._state = None, clean(None)
            return self._state
        signature = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        if signature != self._signature:
            try:
                raw = json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError, UnicodeError, ValueError):
                # A half-written or broken file keeps the last good settings (never drops a minimum).
                return self._state
            self._signature, self._state = signature, clean(raw)
        return self._state

    def public(self, now=None):
        now = self.clock() if now is None else now
        state = self.state()
        return {'client': {'min': state['min_client_version'], 'latest': state['latest_client_version'],
                           'download_url': state['client_download_url']},
                'notice': public_notice(state['notice'], now),
                'notice_version': self.tag(now), 'server_time': int(now)}

    def tag(self, now=None):
        """Changes whenever what players should see changes (also when maintenance starts)."""
        now = self.clock() if now is None else now
        state = self.state()
        notice = public_notice(state['notice'], now)
        if not notice and not any(state[k] for k in ('min_client_version', 'latest_client_version', 'client_download_url')):
            return '0'
        mark = [state['min_client_version'], state['latest_client_version'], state['client_download_url'],
                notice and [notice['id'], notice['starts_at'], notice['minutes'], notice['message'], notice['active']]]
        return hashlib.sha256(json.dumps(mark, ensure_ascii=False).encode()).hexdigest()[:12]

    def refusal(self, path, version, now=None):
        """(status, body, headers) when this request may not go on, else None."""
        if path in OPEN_PATHS:
            return None
        now = self.clock() if now is None else now
        state = self.state()
        notice = public_notice(state['notice'], now)
        if notice and notice['active']:
            return 503, {'detail': maintenance_sentence(notice), 'code': 'server_maintenance', 'notice': notice}, \
                {'Retry-After': str(max(30, notice['ends_in']))}
        if older(version, state['min_client_version']) and not (version is None and path in LEGACY_OPEN_PATHS):
            client = self.public(now)['client']
            return 426, {'detail': update_sentence(state), 'code': 'client_update_required', 'client': client,
                         'version': version or ''}, {}
        return None


class ClientGate:
    """ASGI layer: the notice header on every reply; 503 during maintenance, 426 for old games."""

    def __init__(self, app, policy):
        self.app, self.policy = app, policy

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        now = self.policy.clock()
        value = dict(scope.get('headers') or []).get(b'x-villagen-version', b'').decode('latin-1').strip()
        refusal = self.policy.refusal(scope.get('path', ''), value[:40] or None, now)
        tag = self.policy.tag(now)

        async def tagged(message):
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message)[NOTICE_HEADER] = tag
            await send(message)

        if refusal:
            status, body, headers = refusal
            return await JSONResponse(body, status, headers=headers)(scope, receive, tagged)
        await self.app(scope, receive, tagged)


# ------------------------------------------------------------------ operator commands

def data_dir():
    return Path(os.getenv('TRIPOTHON_DATA_DIR', str(ROOT / 'server-data')))


def read_file(path):
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        return raw if isinstance(raw, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def write_file(path, data):
    path = Path(path)
    data = {k: v for k, v in data.items() if v not in ('', None)}
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def korea_time(seconds):
    return time.strftime('%m-%d %H:%M', time.gmtime(seconds + KOREA))


def describe(path, now=None):
    now = time.time() if now is None else now
    state = clean(read_file(path))
    lines = ['최소 버전: ' + (state['min_client_version'] + ' (이보다 오래된 게임은 접속할 수 없어요)' if state['min_client_version'] else '없음 (모든 버전 접속 가능)'),
             '최신 버전: ' + (state['latest_client_version'] or '없음'),
             '받는 곳:   ' + (state['client_download_url'] or '없음')]
    notice = public_notice(state['notice'], now)
    if not notice:
        lines.append('점검 공지: 없음')
    else:
        when = '%s ~ %s (한국 시간, %d분)' % (korea_time(notice['starts_at']), korea_time(notice['ends_at']), notice['minutes'])
        if notice['active']:
            status = '지금 점검 중' + (' · 직접 끝낼 때까지 (sudo bash ops/notice.sh cancel)' if notice['hold'] else '')
        else:
            status = '%d분 %02d초 뒤 시작' % divmod(notice['starts_in'], 60)
        lines.append('점검 공지: %s · %s · "%s"' % (when, status, notice['message']))
    return '\n'.join(lines)


def version_value(text):
    if text.lower() in ('off', 'none', '-'):
        return ''
    if not parse_version(text):
        raise SystemExit('버전은 0.11.4 처럼 숫자와 점으로 적어 주세요: ' + text)
    return canonical(text)


def url_value(text):
    if text.lower() in ('off', 'none', '-'):
        return ''
    if not valid_url(text):
        raise SystemExit('받는 곳은 https:// 로 시작하는 주소여야 해요: ' + text)
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m server.client_policy', description='Client versions and maintenance notices')
    parser.add_argument('--data-dir', default=None)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('show')
    maintenance = commands.add_parser('maintenance')
    maintenance.add_argument('--in', dest='start_in', type=float, required=True, help='minutes until it starts')
    maintenance.add_argument('--minutes', type=int, required=True, help='expected length in minutes')
    maintenance.add_argument('--message', default=DEFAULT_MESSAGE)
    maintenance.add_argument('--hold', action='store_true', help='stay in maintenance until cancel')
    commands.add_parser('cancel')
    for name in ('min', 'latest', 'url'):
        commands.add_parser(name).add_argument('value')
    release = commands.add_parser('release')
    release.add_argument('version')
    release.add_argument('url', nargs='?', default=None)
    args = parser.parse_args(argv)
    path = (Path(args.data_dir) if args.data_dir else data_dir()) / FILE_NAME
    data = read_file(path)
    if args.command == 'maintenance':
        if not 0 <= args.start_in <= 7 * 24 * 60:
            raise SystemExit('시작까지 남은 시간은 0~10080분이어야 해요.')
        if not 1 <= args.minutes <= MAX_MINUTES:
            raise SystemExit('점검 시간은 1~1440분이어야 해요.')
        message = clean_text(args.message)[:MAX_MESSAGE] or DEFAULT_MESSAGE
        starts = time.time() + args.start_in * 60
        data['notice'] = {'id': 'n%d' % int(starts), 'starts_at': int(starts), 'minutes': args.minutes,
                          'message': message, 'hold': bool(args.hold)}
    elif args.command == 'cancel':
        data.pop('notice', None)
    elif args.command == 'min':
        data['min_client_version'] = version_value(args.value)
    elif args.command == 'latest':
        data['latest_client_version'] = version_value(args.value)
    elif args.command == 'url':
        data['client_download_url'] = url_value(args.value)
    elif args.command == 'release':
        data['latest_client_version'] = version_value(args.version)
        if args.url is not None:
            data['client_download_url'] = url_value(args.url)
    if args.command != 'show':
        state = clean(data)
        if state['min_client_version'] and state['latest_client_version'] and older(state['latest_client_version'], state['min_client_version']):
            data['latest_client_version'] = state['min_client_version']
        write_file(path, data)
        print('저장했어요. 게임에는 몇 초 안에 반영돼요.')
    print(describe(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
