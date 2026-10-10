"""Villagen cost monitor: a dashboard on this PC for API balances and game-server usage.

  monitor.py open        start the dashboard if needed and open it in the browser (open_monitor.cmd)
  monitor.py serve       run the dashboard in this window (127.0.0.1 only, port 8850)
  monitor.py record --source tripo_studio --balance 1234 [--note "..."] [--checked "2026-10-11 14:30"]
  monitor.py status      print every card as text
  monitor.py history --source scenario [--days 30]
  monitor.py stop        stop the background dashboard
  monitor.py shortcut    put a "Villagen 비용 모니터" icon on the desktop
  monitor.py paths       show where settings and history are kept

Settings, server usage keys and history stay in %LOCALAPPDATA%\\Villagen\\cost_monitor, never in
the repository. The page server listens on 127.0.0.1 only, accepts only its own Host names and
needs the page's per-launch token on every API call, so other web pages cannot read or change it.
Run it with the server venv: .tools\\server-venv\\Scripts\\python.exe (FastAPI, uvicorn, httpx).
"""
import argparse
import asyncio
import base64
import json
import logging
import logging.handlers
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
from contextlib import asynccontextmanager, suppress
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import httpx  # noqa: E402
import store  # noqa: E402
import sources  # noqa: E402
from sources import SOURCE_TYPES, number  # noqa: E402

APP = 'villagen-cost-monitor'
VERSION = 1
SHORTCUT_NAME = 'Villagen 비용 모니터'
ROOT = HERE.parents[1]
log = logging.getLogger('cost_monitor')

COMMON_FIELDS = (('label', '이름', 'text', ''),)
SETTINGS_FIELDS = (('refresh_seconds', '화면 새로고침 (초)', 'number', '15 ~ 600'),
                   ('idle_exit_minutes', '창을 닫은 뒤 모니터를 끄기까지 (분)', 'number', '0 = 끄지 않음'),
                   ('krw_per_usd', '환율 (원 / 1달러)', 'number', '달러 금액 옆의 원화 어림값'))
SETTINGS_RANGES = {'refresh_seconds': (15, 600), 'idle_exit_minutes': (0, 1440), 'krw_per_usd': (100, 10000)}


class BadRequest(ValueError):
    pass


# --- settings values ------------------------------------------------------------------------

def clean_text(value, limit=60, empty=False):
    value = str(value if value is not None else '').strip()
    if (not value and not empty) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise BadRequest('invalid_text')
    return value


def clean_url(value):
    """A server's base address: https (or a local http address), no user, path, query or fragment."""
    parts = urllib.parse.urlsplit(str(value or '').strip())
    local = parts.hostname in ('127.0.0.1', 'localhost')
    if parts.scheme not in ('https', 'http') or (parts.scheme == 'http' and not local) or not parts.hostname:
        raise BadRequest('invalid_url')
    if parts.username or parts.password or parts.path not in ('', '/') or parts.query or parts.fragment:
        raise BadRequest('invalid_url')
    return f'{parts.scheme}://{parts.netloc.lower()}'


def clean_link(value):
    value = str(value or '').strip()
    if not value:
        return ''
    parts = urllib.parse.urlsplit(value)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or len(value) > 300:
        raise BadRequest('invalid_link')
    return value


def clean_secret(value):
    value = str(value or '').strip()
    if not 32 <= len(value) <= 2048 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise BadRequest('invalid_key')
    return value


def clean_number(value, low=0.0, high=1e12):
    if value is None or value == '':
        return None
    value = number(value)
    if value is None or not low <= value <= high:
        raise BadRequest('invalid_number')
    return value


def clean_list(value):
    items = value if isinstance(value, list) else str(value or '').split(',')
    items = [str(i).strip() for i in items if str(i).strip()]
    if len(items) > 12 or not all(re.fullmatch(r'[A-Za-z0-9_-]{1,40}', i) for i in items):
        raise BadRequest('invalid_list')
    return items


def clean_prices(value):
    if not isinstance(value, dict) or not 0 < len(value) <= 24:
        raise BadRequest('invalid_prices')
    out = {}
    for pattern, price in value.items():
        if not re.fullmatch(r'[A-Za-z0-9.*_-]{1,64}', str(pattern)) or not isinstance(price, dict):
            raise BadRequest('invalid_prices')
        entry = {}
        for name in ('input', 'cached_input', 'output'):
            amount = clean_number(price.get(name), 0, 1000)
            if amount is None and name != 'cached_input':
                raise BadRequest('invalid_prices')
            if amount is not None:
                entry[name] = amount
        out[str(pattern)] = entry
    return out


CLEANERS = {'text': clean_text, 'url': clean_url, 'link': clean_link, 'path': lambda v: clean_text(v, 400),
            'number': clean_number, 'ratio': lambda v: clean_number(v, 0.05, 1), 'bool': bool,
            'list': clean_list, 'prices': clean_prices}


def parse_checked(value, now):
    """'2026-10-11 14:30', '2026-10-11T14:30', '14:30' (today) or epoch seconds, in this PC's time."""
    if value in (None, ''):
        return now
    if isinstance(value, (int, float)):
        moment = float(value)
    else:
        text = str(value).strip()
        moment = None
        with suppress(ValueError):
            moment = float(text)
        for pattern in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            with suppress(ValueError):
                moment = time.mktime(time.strptime(text, pattern))
                break
        if moment is None and re.fullmatch(r'\d{1,2}:\d{2}', text):
            hour, minute = map(int, text.split(':'))
            t = time.localtime(now)
            moment = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, 0, 0, -1))
        if moment is None:
            raise BadRequest('invalid_time')
    if not now - 400 * 86400 <= moment <= now + 600:
        raise BadRequest('invalid_time')
    return moment


def record_manual(config, history, source, balance, checked=None, note='', origin='cli', now=None):
    now = now or time.time()
    entry = next((s for s in config.merged()['sources'] if s['id'] == source), None)
    if entry is None or entry.get('type') != 'manual':
        manual = [s['id'] for s in config.merged()['sources'] if s.get('type') == 'manual']
        raise BadRequest('직접 입력 항목이 아니에요: %s (가능: %s)' % (source, ', '.join(manual)))
    value = clean_number(balance, 0, 1e12)
    if value is None:
        raise BadRequest('invalid_number')
    note = ''.join(c for c in str(note or '') if ord(c) >= 32).strip()[:200]
    return history.add_manual(source, value, parse_checked(checked, now), note, origin, now)


# --- the monitor ----------------------------------------------------------------------------

class Monitor:
    def __init__(self, folder=None, clock=time.time, transport=None):
        self.folder = Path(folder) if folder else store.data_dir()
        self.config = store.Config(self.folder)
        self.history = store.History(self.folder / 'history.sqlite3')
        self.clock, self.transport = clock, transport
        self.readings, self.raw, self.fetched = {}, {}, {}
        # The last readings survive a restart, and so does the once-a-minute Tripo limit.
        for source, (fetched_at, reading, raw) in self.history.latest().items():
            self.readings[source], self.fetched[source] = reading, fetched_at
            if raw is not None:
                self.raw[source] = raw
        self.lock = asyncio.Lock()
        self.last_seen = clock()
        self.exit = None

    def touch(self):
        self.last_seen = self.clock()

    def build(self):
        cfg = self.config.merged()
        names = {s['id']: s.get('label') or s['id'] for s in cfg['sources']}
        ctx = sources.Context(self.history, self.clock, self.transport, self.raw, {**cfg['settings'], 'names': names})
        built, unknown = [], []
        for entry in cfg['sources']:
            if not entry.get('enabled', True):
                continue
            kind = SOURCE_TYPES.get(entry.get('type'))
            if kind is None:
                unknown.append(entry)
            else:
                built.append(kind(entry, ctx))
        return built, unknown

    async def refresh(self, force=False, only=None):
        async with self.lock:
            built, unknown = self.build()
            now = self.clock()

            def due(source):
                if only is not None and source.id not in only:
                    return False
                gap = now - self.fetched.get(source.id, float('-inf'))
                return gap >= (source.min_interval if force or only is not None else source.every)

            first = [s for s in built if not s.depends() and due(s)]
            await asyncio.gather(*(self.run(s, now) for s in first))
            changed = {s.id for s in first}
            for source in built:
                if source.depends() and (due(source) or changed & set(source.depends())):
                    await self.run(source, now)
            for entry in unknown:
                self.readings[entry['id']] = sources.Reading(
                    id=entry['id'], name=entry.get('label') or entry['id'], type=str(entry.get('type')), status='error',
                    note='이 모니터가 모르는 종류예요. 모니터를 업데이트해 주세요.').to_dict()

    async def run(self, source, now):
        self.fetched[source.id] = now
        try:
            reading, raw = await source.read()
        except Exception as error:  # a broken source must never stop the others
            log.warning('source %s failed: %s', source.id, type(error).__name__)
            reading, raw = source.failed('읽는 중 오류가 났어요. 잠시 뒤 다시 읽어요.'), None
        data = reading.to_dict()
        self.readings[source.id] = data
        if raw is not None:
            self.raw[source.id] = raw
        self.history.save_latest(source.id, now, data, self.raw.get(source.id))

    async def loop(self):
        while True:
            try:
                await self.refresh()
            except Exception as error:
                log.warning('refresh failed: %s', type(error).__name__)
            idle = number(self.config.merged()['settings'].get('idle_exit_minutes'), 0)
            if idle and self.exit and self.clock() - self.last_seen > idle * 60:
                log.warning('no page for %s minutes: stopping', idle)
                self.exit()
                return
            await asyncio.sleep(5)

    def state(self):
        cfg = self.config.merged()
        settings = cfg['settings']
        cards = []
        for entry in cfg['sources']:
            if not entry.get('enabled', True):
                continue
            reading = self.readings.get(entry['id'])
            label = entry.get('label') or entry['id']
            if reading is None:
                reading = sources.Reading(id=entry['id'], name=label, type=str(entry.get('type')), status='off',
                                          note='읽는 중이에요...').to_dict()
            cards.append({**reading, 'name': label})
        alerts = [{'id': c['id'], 'level': 'alert' if c.get('status') in ('alert', 'error') else 'warn',
                   'name': c['name'], 'text': c.get('note') or c.get('caption') or ''}
                  for c in cards if c.get('status') in ('warn', 'alert', 'error')]
        return {'app': APP, 'version': VERSION, 'generated': self.clock(),
                'refresh_seconds': number(settings.get('refresh_seconds'), 30),
                'krw_per_usd': number(settings.get('krw_per_usd'), 0), 'cards': cards, 'alerts': alerts,
                'data_dir': str(self.folder)}

    def public_config(self):
        """Settings for the form. Secret values never leave: only whether one is set."""
        cfg = self.config.merged()
        types = {name: {'title': kind.title,
                        'fields': [dict(zip(('name', 'label', 'kind', 'hint'), f)) for f in COMMON_FIELDS + kind.fields]}
                 for name, kind in SOURCE_TYPES.items()}
        items = []
        for entry in cfg['sources']:
            kind = SOURCE_TYPES.get(entry.get('type'))
            item = {'id': entry['id'], 'type': entry.get('type'), 'builtin': entry.get('builtin', False),
                    'enabled': entry.get('enabled', True), 'label': entry.get('label') or entry['id']}
            for name, _, field_kind, _ in (kind.fields if kind else ()):
                item[name] = {'set': bool(entry.get(name))} if field_kind == 'secret' else entry.get(name)
            items.append(item)
        return {'settings': {name: cfg['settings'].get(name) for name, *_ in SETTINGS_FIELDS},
                'settings_fields': [dict(zip(('name', 'label', 'kind', 'hint'), f)) for f in SETTINGS_FIELDS],
                'types': types, 'sources': items, 'data_dir': str(self.folder)}

    def apply_config(self, body):
        if not isinstance(body, dict):
            raise BadRequest('invalid_body')
        merged = {s['id']: s for s in self.config.merged()['sources']}
        messages = []
        settings = body.get('settings') or {}
        if not isinstance(settings, dict):
            raise BadRequest('invalid_settings')
        changes = {}
        for name, value in settings.items():
            if name not in SETTINGS_RANGES:
                raise BadRequest('unknown_setting')
            amount = clean_number(value, *SETTINGS_RANGES[name])
            if amount is None:
                raise BadRequest('invalid_number')
            changes[name] = amount
        prepared = []
        for change in body.get('sources') or []:
            current = merged.get(change.get('id')) if isinstance(change, dict) else None
            kind = SOURCE_TYPES.get((current or {}).get('type'))
            if not kind:
                raise BadRequest('unknown_source')
            fields = {name: field_kind for name, _, field_kind, _ in COMMON_FIELDS + kind.fields}
            updates, cleared = {}, []
            for name, value in change.items():
                if name in ('id', 'clear'):
                    continue
                if name == 'enabled':
                    updates['enabled'] = bool(value)
                elif name not in fields:
                    raise BadRequest('unknown_field')
                elif fields[name] == 'secret':
                    if value:
                        updates[name] = clean_secret(value)
                else:
                    updates[name] = CLEANERS[fields[name]](value)
            for name in change.get('clear') or []:
                if fields.get(name) == 'secret':
                    cleared.append(name)
            # A usage key only ever goes to the server it was made for.
            if 'url' in updates and updates['url'] != current.get('url') and current.get('usage_key') \
                    and 'usage_key' not in updates and 'usage_key' not in cleared:
                cleared.append('usage_key')
                messages.append(f"{current.get('label') or current['id']}: 주소가 바뀌어서 사용량 키를 지웠어요. 새 서버의 키를 넣어 주세요.")
            prepared.append((current, updates, cleared))
        added = None
        if body.get('add'):
            add = body['add']
            if not isinstance(add, dict) or add.get('type', 'manual') != 'manual':
                raise BadRequest('only_manual_sources_can_be_added')
            added = {'id': 'manual_' + secrets.token_hex(3), 'type': 'manual', 'label': clean_text(add.get('label')),
                     'unit': clean_text(add.get('unit') or '', 16, empty=True),
                     'warn_below': clean_number(add.get('warn_below')), 'stale_days': 7,
                     'link': clean_link(add.get('link'))}
        removed = []
        for source_id in body.get('remove') or []:
            current = merged.get(source_id)
            if not current or current.get('builtin'):
                raise BadRequest('only_added_sources_can_be_removed')
            removed.append(source_id)
        # Everything is valid: write.
        if changes:
            self.config.change_settings(changes)
        for current, updates, cleared in prepared:
            self.config.change_source(current['id'], updates, cleared)
        if added:
            self.config.add_source(added)
            messages.append(f"'{added['label']}' 항목을 만들었어요. 카드의 [잔액 입력]으로 값을 넣어 주세요.")
        for source_id in removed:
            self.config.remove_source(source_id)
            self.readings.pop(source_id, None)
        # Read again soon; the Tripo key keeps its once-a-minute limit.
        for source_id in list(self.fetched):
            if merged.get(source_id, {}).get('type') != 'tripo_api':
                self.fetched.pop(source_id, None)
        return self.public_config(), messages


# --- the page server --------------------------------------------------------------------------

def create_app(monitor, token, port, background=True):
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

    hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    origins = {'http://' + h for h in hosts}
    page = (HERE / 'dashboard.html').read_text(encoding='utf-8')
    icon = ROOT / 'game' / 'assets' / 'villagen.ico'

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(monitor.loop()) if background else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def guard(request, call_next):
        # Another site's page (or a DNS-rebinding name) never gets an answer.
        if request.headers.get('host', '') not in hosts:
            return JSONResponse({'detail': 'host_not_allowed'}, 403)
        path = request.url.path
        if path.startswith('/api/') and path != '/api/ping':
            given = request.headers.get('x-monitor-token', '')
            if not secrets.compare_digest(given.encode(), token.encode()):
                return JSONResponse({'detail': 'token_required'}, 403)
            origin = request.headers.get('origin')
            if origin is not None and origin not in origins:
                return JSONResponse({'detail': 'origin_not_allowed'}, 403)
            if request.method == 'POST' and 'application/json' not in request.headers.get('content-type', ''):
                return JSONResponse({'detail': 'json_required'}, 415)
        if path != '/api/ping':
            monitor.touch()
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer'})
        return response

    async def body_of(request):
        try:
            return await request.json()
        except ValueError:
            raise BadRequest('invalid_json') from None

    @app.exception_handler(BadRequest)
    async def bad_request(request, error):
        return JSONResponse({'detail': str(error)}, 400)

    @app.get('/')
    def index():
        nonce = secrets.token_urlsafe(16)
        html = page.replace('__MONITOR_TOKEN__', token).replace('__NONCE__', nonce)
        policy = (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; connect-src 'self'; "
                  "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        return HTMLResponse(html, headers={'Content-Security-Policy': policy})

    @app.get('/favicon.ico')
    def favicon():
        if icon.is_file():
            return FileResponse(icon, media_type='image/x-icon')
        return JSONResponse({'detail': 'not_found'}, 404)

    @app.get('/api/ping')
    def ping():
        return {'app': APP, 'version': VERSION}

    @app.get('/api/state')
    def state():
        return monitor.state()

    @app.post('/api/refresh')
    async def refresh():
        await monitor.refresh(force=True)
        return monitor.state()

    @app.get('/api/config')
    def get_config():
        return monitor.public_config()

    @app.post('/api/config')
    async def set_config(request: Request):
        config, messages = monitor.apply_config(await body_of(request))
        await monitor.refresh()
        return {'config': config, 'messages': messages, 'state': monitor.state()}

    @app.post('/api/manual')
    async def manual(request: Request):
        body = await body_of(request)
        if not isinstance(body, dict):
            raise BadRequest('invalid_body')
        source = str(body.get('source') or '')
        record_manual(monitor.config, monitor.history, source, body.get('balance'), body.get('checked_at'),
                      body.get('note'), 'dashboard', monitor.clock())
        await monitor.refresh(only={source})
        return monitor.state()

    @app.post('/api/manual/delete')
    async def manual_delete(request: Request):
        body = await body_of(request)
        if not isinstance(body, dict) or not isinstance(body.get('id'), int):
            raise BadRequest('invalid_body')
        source = str(body.get('source') or '')
        if not monitor.history.delete_manual(source, body['id']):
            raise BadRequest('entry_not_found')
        await monitor.refresh(only={source})
        return monitor.state()

    @app.post('/api/shutdown')
    def shutdown():
        if monitor.exit:
            monitor.exit()
        return {'ok': True}

    return app


# --- command line -----------------------------------------------------------------------------

def setup_logging(folder, console):
    handler = (logging.StreamHandler() if console else
               logging.handlers.RotatingFileHandler(folder / 'server.log', maxBytes=256 * 1024, backupCount=1, encoding='utf-8'))
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)


def port_of(folder, value=None):
    return int(value or number(store.Config(folder).merged()['settings'].get('port'), 8850))


def ping(port):
    try:
        reply = httpx.get(f'http://127.0.0.1:{port}/api/ping', timeout=1.5)
        return reply.status_code == 200 and reply.json().get('app') == APP
    except (httpx.HTTPError, ValueError):
        return False


def server_info(folder):
    try:
        return json.loads((folder / 'server.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def cmd_serve(args):
    import uvicorn
    folder = store.data_dir()
    port = port_of(folder, args.port)
    setup_logging(folder, console=sys.stdout is not None and not args.quiet)
    token = secrets.token_urlsafe(32)
    monitor = Monitor(folder)
    app = create_app(monitor, token, port)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning', access_log=False,
                                           log_config=None, lifespan='on'))
    monitor.exit = lambda: setattr(server, 'should_exit', True)
    info = folder / 'server.json'
    store.write_json(info, {'pid': os.getpid(), 'port': port, 'token': token, 'started': time.time()})
    if sys.stdout is not None and not args.quiet:
        print(f'비용 모니터: http://127.0.0.1:{port}/  (끄려면 Ctrl+C)')
    try:
        server.run()
    finally:
        current = server_info(folder)
        if current and current.get('pid') == os.getpid():
            with suppress(OSError):
                info.unlink()
    return 0


def cmd_open(args):
    folder = store.data_dir()
    port = port_of(folder, args.port)
    url = f'http://127.0.0.1:{port}/'
    if not ping(port):
        windowless = Path(sys.executable).with_name('pythonw.exe')
        python = windowless if windowless.is_file() else Path(sys.executable)
        flags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0  # detached, own process group
        subprocess.Popen([str(python), str(HERE / 'monitor.py'), 'serve', '--port', str(port), '--quiet'],
                         cwd=str(folder), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        for _ in range(60):
            if ping(port):
                break
            time.sleep(0.25)
        else:
            print(f'모니터를 시작하지 못했어요. 포트 {port}을(를) 다른 프로그램이 쓰고 있는지 확인해 주세요.')
            print(f'기록: {folder / "server.log"}')
            return 1
    if not args.no_browser:
        import webbrowser
        webbrowser.open(url)
    print(f'비용 모니터: {url}')
    return 0


def cmd_stop(args):
    folder = store.data_dir()
    info = server_info(folder)
    if not info:
        print('실행 중인 모니터가 없어요.')
        return 0
    port = info.get('port', 8850)
    with suppress(httpx.HTTPError):
        httpx.post(f'http://127.0.0.1:{port}/api/shutdown', json={}, timeout=3,
                   headers={'X-Monitor-Token': info.get('token', '')})
    for _ in range(40):
        if not ping(port):
            print('모니터를 껐어요.')
            return 0
        time.sleep(0.25)
    with suppress(OSError, ValueError):
        os.kill(int(info['pid']), 15)
    print('모니터를 껐어요.')
    return 0


def cmd_record(args):
    folder = store.data_dir()
    monitor_config, history = store.Config(folder), store.History(folder / 'history.sqlite3')
    try:
        record_manual(monitor_config, history, args.source, args.balance, args.checked, args.note or '', 'cli')
    except BadRequest as error:
        print(f'기록하지 못했어요: {error}', file=sys.stderr)
        return 2
    entries = history.manual(args.source)
    last = entries[-1]
    before = entries[-2]['balance'] if len(entries) > 1 else None
    change = '' if before is None else f' (지난 기록보다 {last["balance"] - before:+,.0f})'
    print(f'{args.source}: {last["balance"]:,.0f} 기록했어요{change}.')
    return 0


def describe(card, krw):
    unit = card.get('unit') or ''
    value = card.get('value')
    if value is None:
        shown = '-'
    elif card.get('money'):
        shown = f'${value:,.2f}' + (f' (약 {value * krw:,.0f}원)' if krw else '')
    else:
        shown = f'{value:,.0f} {unit}'.strip()
    parts = [f"[{card.get('status')}] {card.get('name')}: {shown}" + (' (추정)' if card.get('estimated') else '')]
    spent = [f'{label} {card[key]:,.2f}' if card.get('money') else f'{label} {card[key]:,.0f}'
             for key, label in (('spent_today', '오늘'), ('spent_7d', '7일')) if card.get(key) is not None]
    if spent:
        parts.append('사용 ' + ' · '.join(spent))
    if card.get('updated'):
        parts.append(time.strftime('%m-%d %H:%M', time.localtime(card['updated'])))
    line = ' | '.join(parts)
    if card.get('note'):
        line += '\n    ' + card['note']
    for row in card.get('rows') or []:
        line += f"\n    - {row.get('label')}: {row.get('value')}"
    return line


def cmd_status(args):
    folder = store.data_dir()
    info = server_info(folder)
    state = None
    if info and ping(info.get('port', 8850)):
        with suppress(httpx.HTTPError, ValueError):
            state = httpx.get(f"http://127.0.0.1:{info['port']}/api/state", timeout=5,
                              headers={'X-Monitor-Token': info.get('token', '')}).json()
    if state is None or 'cards' not in state:
        monitor = Monitor(folder)
        asyncio.run(monitor.refresh())
        state = monitor.state()
    for card in state['cards']:
        print(describe(card, state.get('krw_per_usd') or 0))
    return 0


def cmd_history(args):
    folder = store.data_dir()
    history = store.History(folder / 'history.sqlite3')
    since = time.time() - args.days * 86400
    entries = [e for e in history.manual(args.source) if e['checked_at'] >= since]
    if entries:
        previous = None
        for e in entries:
            delta = '' if previous is None else f' ({e["balance"] - previous:+,.0f})'
            note = f'  {e["note"]}' if e['note'] else ''
            print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(e['checked_at']))}  {e['balance']:,.0f}{delta}{note}")
            previous = e['balance']
        points = [(e['checked_at'], e['balance']) for e in entries]
    else:
        points = history.series(args.source, since)
        for ts, value in points:
            print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))}  {value:,.2f}")
    if not points:
        print('기록이 없어요.')
        return 0
    print(f'{args.days}일 동안 사용: {store.spend(points, since):,.0f} · 충전: {store.topped_up(points, since):,.0f}')
    return 0


def cmd_shortcut(args):
    if os.name != 'nt':
        print('바탕화면 아이콘은 Windows에서만 만들어요.')
        return 1

    def quoted(path):
        return "'" + str(path).replace("'", "''") + "'"
    icon = ROOT / 'game' / 'assets' / 'villagen.ico'
    script = '\n'.join([
        "$desktop = [Environment]::GetFolderPath('Desktop')",
        f"$path = Join-Path $desktop {quoted(SHORTCUT_NAME + '.lnk')}",
        '$link = (New-Object -ComObject WScript.Shell).CreateShortcut($path)',
        f'$link.TargetPath = {quoted(HERE / "open_monitor.cmd")}',
        f'$link.WorkingDirectory = {quoted(HERE)}',
        f'$link.IconLocation = {quoted(str(icon) + ",0")}' if icon.is_file() else '',
        '$link.WindowStyle = 7',
        f"$link.Description = {quoted('Villagen API 요금과 서버 사용량')}",
        '$link.Save()',
        'Write-Output $path'])
    encoded = base64.b64encode(script.encode('utf-16-le')).decode()
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            capture_output=True)
    if result.returncode:
        print('아이콘을 만들지 못했어요.', file=sys.stderr)
        return 1
    print(f'바탕화면에 "{SHORTCUT_NAME}" 아이콘을 만들었어요.')
    return 0


def cmd_paths(args):
    folder = store.data_dir()
    print(f'설정과 기록: {folder}')
    print(f'  설정 파일: {folder / "config.json"}')
    print(f'  기록 DB:   {folder / "history.sqlite3"}')
    print(f'기본 설정 (저장소): {store.DEFAULTS_FILE}')
    return 0


def main(argv=None):
    with suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(errors='replace')
        sys.stderr.reconfigure(errors='replace')
    parser = argparse.ArgumentParser(prog='monitor.py', description='Villagen 비용 모니터')
    commands = parser.add_subparsers(dest='command')
    serve = commands.add_parser('serve', help='이 창에서 대시보드 실행')
    serve.add_argument('--port', type=int)
    serve.add_argument('--quiet', action='store_true')
    opener = commands.add_parser('open', help='대시보드를 켜고 브라우저로 열기')
    opener.add_argument('--port', type=int)
    opener.add_argument('--no-browser', action='store_true')
    record = commands.add_parser('record', help='웹 계정 잔액 기록 (Tripo Studio, Scenario 등)')
    record.add_argument('--source', required=True)
    record.add_argument('--balance', required=True)
    record.add_argument('--note', default='')
    record.add_argument('--checked', help='확인한 시각: "2026-10-11 14:30" 또는 "14:30" (기본: 지금)')
    history = commands.add_parser('history', help='기록 보기')
    history.add_argument('--source', required=True)
    history.add_argument('--days', type=int, default=30)
    commands.add_parser('status', help='모든 카드를 글로 보기')
    commands.add_parser('stop', help='백그라운드 대시보드 끄기')
    commands.add_parser('shortcut', help='바탕화면 아이콘 만들기')
    commands.add_parser('paths', help='설정과 기록 위치')
    args = parser.parse_args(argv)
    handlers = {'serve': cmd_serve, 'open': cmd_open, 'record': cmd_record, 'history': cmd_history,
                'status': cmd_status, 'stop': cmd_stop, 'shortcut': cmd_shortcut, 'paths': cmd_paths}
    if args.command is None:
        args = parser.parse_args(['open'])
    return handlers[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
