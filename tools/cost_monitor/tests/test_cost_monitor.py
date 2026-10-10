"""Cost monitor: sources with mocked HTTP, hand-entered balances, the local page server's guards.
No test touches the network or the real Tripo key file."""
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import monitor  # noqa: E402
import sources  # noqa: E402
import store  # noqa: E402

KEYS = ('tripo-test-only-key-one', 'tripo-test-only-key-two')
USAGE_KEY = 'vgu_' + '0123456789abcdef' * 3
SCHOOL = 'https://54-117-10-64.sslip.io'
# Hand-entered times must lie in the past of the real clock, so the tests run near it.
NOW = float(int(time.time()))

USAGE = {
    'schema': 1, 'budget': {'used': 3300, 'total': 4000, 'remaining': 700},
    'limits': {'daily_crafts': 105, 'account_daily_crafts': 3, 'max_credits_per_craft': 35},
    'crafts': {'today': 12, 'last_7_days': 40, 'total': 90, 'pending': 1, 'today_ready': 10, 'today_failed': 1},
    'tripo_credits': {'today': 30, 'last_7_days': 210, 'total': 3200, 'committed': 3300, 'incomplete_bills': 0},
    'llm': {'provider': 'gemini', 'runs': {'today': 14, 'last_7_days': 50, 'total': 120},
            'tokens': {'today': {'input': 1000, 'cached_input': 0, 'output': 200, 'reasoning': 50},
                       'last_7_days': {'input': 9000}, 'total': {'input': 20000}},
            'by_model': [{'provider': 'gemini', 'model': 'gemini-3.5-flash', 'runs': {'today': 14, 'last_7_days': 50, 'total': 120},
                          'tokens': {'today': {'input': 1_000_000, 'cached_input': 200_000, 'output': 100_000, 'reasoning': 100_000},
                                     'last_7_days': {'input': 2_000_000, 'cached_input': 0, 'output': 0, 'reasoning': 0},
                                     'total': {'input': 4_000_000, 'cached_input': 0, 'output': 1_000_000, 'reasoning': 0}}}]},
    'interactions': {'today': 2, 'last_7_days': 5, 'total': 9, 'ready': 8, 'failed': 1},
    'accounts': {'total': 40, 'new_today': 3},
    'daily': [{'day': '2027-01-14', 'tripo_credits': 20, 'models': []},
              {'day': '2027-01-15', 'tripo_credits': 30, 'models': [
                  {'provider': 'gemini', 'model': 'gemini-3.5-flash', 'runs': 1, 'input': 1_000_000, 'cached_input': 0, 'output': 0, 'reasoning': 0}]}],
}


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now


class Network:
    """A fake internet: Tripo balance, a Villagen server; every request is recorded."""

    def __init__(self):
        self.balances = {KEYS[0]: 1500, KEYS[1]: 700}
        self.health = {'ok': True, 'version': '0.10.0', 'studio_llm': 'gemini', 'studio_tripo_enabled': True,
                       'tripo_budget': {'used': 3300, 'total': 4000}}
        self.down = False
        self.tripo_status = 200
        self.seen = []

    def __call__(self, request):
        self.seen.append(request)
        if self.down:
            raise httpx.ConnectError('down', request=request)
        auth = request.headers.get('authorization', '')
        if request.url.host == 'openapi.tripo3d.ai' and request.url.path == '/v3/account/balance':
            key = auth.removeprefix('Bearer ')
            if self.tripo_status != 200 or key not in self.balances:
                return httpx.Response(401, json={'code': 1001, 'message': 'bad key'})
            return httpx.Response(200, json={'code': 0, 'data': {'balance': self.balances[key], 'frozen': 5}})
        if 'sslip.io' in request.url.host and request.url.path == '/health':
            return httpx.Response(200, json=self.health)
        if 'sslip.io' in request.url.host and request.url.path == '/v1/ops/usage':
            if auth != 'Bearer ' + USAGE_KEY:
                return httpx.Response(401, json={'detail': 'usage_key_required'})
            return httpx.Response(200, json=USAGE)
        return httpx.Response(404, json={'detail': 'Not Found'})


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('VILLAGEN_COST_MONITOR_DIR', str(tmp_path / 'data'))
    folder = store.data_dir()
    key_file = tmp_path / 'tripo_key.txt'
    key_file.write_text('\n'.join(KEYS) + '\n', encoding='utf-8')
    config = store.Config(folder)
    config.change_source('tripo_api', {'key_file': str(key_file)})
    config.change_source('judging', {'enabled': False})
    network, clock = Network(), Clock()
    made = monitor.Monitor(folder, clock, httpx.MockTransport(network))
    return made, network, clock, config


def refresh(m, **kw):
    asyncio.run(m.refresh(**kw))
    return {c['id']: c for c in m.state()['cards']}


def test_default_config_lists_known_sources_only():
    defaults = store.Config.defaults()
    assert {s['type'] for s in defaults['sources']} <= set(sources.SOURCE_TYPES)
    assert len({s['id'] for s in defaults['sources']}) == len(defaults['sources'])
    assert 'usage_key' not in json.dumps(defaults)


def test_tripo_balance_sums_keys_once_a_minute_and_never_shows_them(setup):
    m, network, clock, _ = setup
    cards = refresh(m)
    tripo = cards['tripo_api']
    assert tripo['value'] == 2200 and tripo['status'] == 'ok' and tripo['unit'] == '크레딧'
    assert [r['label'] for r in tripo['rows']][:2] == ['키 1', '키 2']
    calls = [r for r in network.seen if r.url.host == 'openapi.tripo3d.ai']
    assert len(calls) == 2 and {r.headers['authorization'] for r in calls} == {'Bearer ' + k for k in KEYS}
    assert all(r.method == 'GET' for r in network.seen)
    # Not again within a minute, even when forced.
    clock.now += 30
    refresh(m)
    refresh(m, force=True)
    assert len([r for r in network.seen if r.url.host == 'openapi.tripo3d.ai']) == 2
    clock.now += 31
    network.balances[KEYS[0]] = 1400
    cards = refresh(m)
    assert cards['tripo_api']['value'] == 2100 and cards['tripo_api']['spent_today'] == 100
    dumped = json.dumps([m.state(), m.public_config()], ensure_ascii=False)
    assert not any(k in dumped for k in KEYS)
    # A restarted monitor keeps the once-a-minute limit.
    again = monitor.Monitor(m.folder, clock, httpx.MockTransport(network))
    asyncio.run(again.refresh(force=True))
    assert len([r for r in network.seen if r.url.host == 'openapi.tripo3d.ai']) == 4


def test_tripo_problems_are_explained_without_the_key(setup, tmp_path):
    m, network, clock, config = setup
    network.tripo_status = 401
    card = refresh(m)['tripo_api']
    assert card['status'] == 'error' and '거절' in card['note']
    assert not any(k in json.dumps(card, ensure_ascii=False) for k in KEYS)
    config.change_source('tripo_api', {'key_file': str(tmp_path / 'missing.txt')})
    clock.now += 61
    card = refresh(m)['tripo_api']
    assert card['status'] == 'error' and '키 파일' in card['note']


def test_low_tripo_balance_warns(setup):
    m, network, clock, config = setup
    config.change_source('tripo_api', {'warn_below': 5000, 'alert_below': 1000})
    assert refresh(m)['tripo_api']['status'] == 'warn'
    assert any(a['id'] == 'tripo_api' and a['level'] == 'warn' for a in m.state()['alerts'])


def test_server_without_usage_key_shows_budget_from_health(setup):
    m, network, _, _ = setup
    school = refresh(m)['school']
    assert school['value'] == 700 and school['total'] == 4000 and school['meter'] == {'used': 3300, 'total': 4000}
    assert school['status'] == 'warn'  # 82.5% of the budget
    assert '사용량 키' in school['note']
    assert not any(r.url.path == '/v1/ops/usage' for r in network.seen)


def test_server_usage_key_goes_only_to_its_server(setup):
    m, network, _, config = setup
    config.change_source('school', {'usage_key': USAGE_KEY})
    cards = refresh(m)
    school = cards['school']
    rows = {r['label']: r['value'] for r in school['rows']}
    assert rows['오늘 제작 / 하루 한도'] == '12 / 105'
    assert school['spent_today'] == 30 and school['spent_7d'] == 210
    assert school['series']['kind'] == 'bars' and school['series']['points'][-1] == ['2027-01-15', 30.0]
    sent = [r for r in network.seen if USAGE_KEY in r.headers.get('authorization', '')]
    assert sent and all(str(r.url).startswith(SCHOOL + '/v1/ops/usage') for r in sent)
    assert USAGE_KEY not in json.dumps([m.state(), m.public_config()])
    assert {'set': True} == m.public_config()['sources'][1]['usage_key']


def test_server_wrong_key_and_server_down(setup):
    m, network, clock, config = setup
    config.change_source('school', {'usage_key': 'vgu_' + 'f' * 48})
    school = refresh(m)['school']
    assert school['status'] == 'warn' and '맞지 않아요' in school['note']
    network.down = True
    clock.now += 61
    school = refresh(m)['school']
    assert school['status'] == 'error' and '연결하지 못했어요' in school['note']


def test_gemini_estimate_uses_the_price_table_and_says_estimated(setup):
    prices = store.Config.defaults()['sources'][3]['prices']
    assert sources.price_for('gemini-3.1-flash-lite', prices)[0] == 'gemini-*flash-lite*'
    assert sources.price_for('gemini-3.5-flash', prices)[0] == 'gemini-*flash*'
    assert sources.price_for('unknown', prices)[0] == '*'
    tokens = {'input': 1_000_000, 'cached_input': 200_000, 'output': 100_000, 'reasoning': 100_000}
    assert sources.token_cost(tokens, {'input': 0.5, 'cached_input': 0.05, 'output': 3.0}) == pytest.approx(1.01)
    m, network, _, config = setup
    assert refresh(m)['gemini']['status'] == 'off'  # no usage key yet
    config.change_source('school', {'usage_key': USAGE_KEY})
    m.fetched.clear()
    gemini = refresh(m)['gemini']
    assert gemini['estimated'] and gemini['money'] and gemini['unit'] == 'USD'
    assert gemini['spent_today'] == pytest.approx(1.01) and gemini['spent_7d'] == pytest.approx(1.0)
    assert gemini['value'] == pytest.approx(2.0 + 3.0)
    assert '추정' in gemini['note']
    assert gemini['series']['points'][-1] == ['2027-01-15', 0.5]


def test_record_command_and_manual_spending(setup, capsys):
    m, _, clock, _ = setup
    day = 86400
    for checked, balance in ((NOW - 3 * day, 600), (NOW - 2 * day, 450), (NOW - day, 900), (NOW - 60, 850)):
        assert monitor.main(['record', '--source', 'scenario', '--balance', str(balance), '--checked', str(checked), '--note', 'test']) == 0
    assert monitor.main(['record', '--source', 'school', '--balance', '5']) == 2
    assert monitor.main(['record', '--source', 'nothing', '--balance', '5']) == 2
    assert monitor.main(['record', '--source', 'scenario', '--balance', '-5']) == 2
    capsys.readouterr()
    scenario = refresh(m)['scenario']
    assert scenario['value'] == 850 and scenario['manual'] and scenario['updated'] == NOW - 60
    assert scenario['spent_7d'] == 200  # 600 -> 450 and 900 -> 850; the top-up to 900 is not spending
    assert scenario['history'][0]['value'] == 850 and scenario['history'][0]['delta'] == -50
    assert scenario['history'][0]['origin'] == 'cli'
    assert monitor.main(['history', '--source', 'scenario', '--days', '30']) == 0
    assert '충전' in capsys.readouterr().out
    clock.now += 9 * day
    m.fetched.clear()
    assert refresh(m)['scenario']['status'] == 'warn'  # checked more than a week ago
    assert refresh(m)['tripo_studio']['status'] == 'off'  # nothing recorded yet


def client_for(m, token='page-token'):
    app = monitor.create_app(m, token, 8850, background=False)
    return TestClient(app, base_url='http://127.0.0.1:8850')


def test_page_server_guards(setup):
    m, *_ = setup
    with client_for(m) as client:
        page = client.get('/')
        assert page.status_code == 200 and 'page-token' in page.text and '__NONCE__' not in page.text
        assert "frame-ancestors 'none'" in page.headers['content-security-policy']
        assert client.get('/api/ping').json()['app'] == 'villagen-cost-monitor'
        assert client.get('/api/state').status_code == 403
        assert client.get('/api/state', headers={'X-Monitor-Token': 'wrong'}).status_code == 403
        token = {'X-Monitor-Token': 'page-token'}
        assert client.get('/api/state', headers=token).status_code == 200
        assert client.post('/api/refresh', headers=token, content='{}').status_code == 415
        assert client.post('/api/refresh', headers={**token, 'Origin': 'https://evil.example'}, json={}).status_code == 403
        assert client.post('/api/refresh', headers=token, json={}).status_code == 200
    with TestClient(monitor.create_app(m, 'page-token', 8850, background=False), base_url='http://evil.example:8850') as other:
        assert other.get('/', headers={'X-Monitor-Token': 'page-token'}).status_code == 403


def test_settings_keep_keys_secret_and_tied_to_their_server(setup):
    m, *_ = setup
    token = {'X-Monitor-Token': 'page-token'}
    with client_for(m) as client:
        bad = client.post('/api/config', headers=token, json={'sources': [{'id': 'school', 'usage_key': 'short'}]})
        assert bad.status_code == 400 and bad.json()['detail'] == 'invalid_key'
        assert client.post('/api/config', headers=token, json={'sources': [{'id': 'school', 'url': 'http://example.com'}]}).status_code == 400
        saved = client.post('/api/config', headers=token, json={'sources': [{'id': 'school', 'usage_key': USAGE_KEY, 'warn_ratio': 0.7}]})
        assert saved.status_code == 200 and USAGE_KEY not in saved.text
        school = next(s for s in saved.json()['config']['sources'] if s['id'] == 'school')
        assert school['usage_key'] == {'set': True} and school['warn_ratio'] == 0.7
        assert USAGE_KEY not in client.get('/api/config', headers=token).text
        moved = client.post('/api/config', headers=token, json={'sources': [{'id': 'school', 'url': 'https://new-school.sslip.io/'}]})
        school = next(s for s in moved.json()['config']['sources'] if s['id'] == 'school')
        assert school['url'] == 'https://new-school.sslip.io' and school['usage_key'] == {'set': False}
        assert moved.json()['messages']
        added = client.post('/api/config', headers=token, json={'add': {'type': 'manual', 'label': 'AWS 크레딧', 'unit': 'USD', 'warn_below': 20}})
        new = next(s for s in added.json()['config']['sources'] if s['label'] == 'AWS 크레딧')
        assert not new['builtin'] and new['type'] == 'manual'
        recorded = client.post('/api/manual', headers=token, json={'source': new['id'], 'balance': 87.5,
                                                                    'checked_at': time.strftime('%Y-%m-%dT%H:%M', time.localtime(NOW - 3600))})
        card = next(c for c in recorded.json()['cards'] if c['id'] == new['id'])
        assert card['value'] == 87.5 and card['history'][0]['origin'] == 'dashboard'
        entry = card['history'][0]['id']
        assert client.post('/api/manual/delete', headers=token, json={'source': new['id'], 'id': entry}).status_code == 200
        assert client.post('/api/config', headers=token, json={'remove': ['scenario']}).status_code == 400
        assert client.post('/api/config', headers=token, json={'remove': [new['id']]}).status_code == 200
        assert all(c['id'] != new['id'] for c in client.get('/api/state', headers=token).json()['cards'])


def test_real_server_usage_reply_fits_the_monitor(setup, tmp_path):
    """Contract: the server's /v1/ops/usage reply, as server/usage_report.py makes it, drives the cards."""
    from server.app import create_app
    from server.config import Settings
    app = create_app(Settings(data_dir=tmp_path / 'server', studio_llm='gemini', gemini_key='test-only',
                              tripo_credit_budget=500, usage_key=USAGE_KEY), clock=lambda: NOW, worker_enabled=False)
    with TestClient(app) as server:
        server.post('/v1/auth/register', json={'username': 'contract_user', 'password': 'Testing-only-12345'})
        with app.state.db.transaction() as conn:
            owner = conn.execute('SELECT id FROM users').fetchone()[0]
            conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,provenance,parts,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                         ('j1', owner, '{}', 'ready', 30, json.dumps({'provider': 'gemini', 'model': 'gemini-3.5-flash', 'geometry': 'tripo',
                                                                     'usage': {'input_tokens': 2_000_000, 'output_tokens': 100_000}}),
                          json.dumps({'whole': {'state': 'ready', 'task': 't', 'credits_consumed': 20}}), NOW - 60, NOW - 60))
        reply = server.get('/v1/ops/usage', headers={'Authorization': 'Bearer ' + USAGE_KEY}).json()
    m, network, _, config = setup
    network.health = {'ok': True, 'version': '0.10.0', 'tripo_budget': {'used': 20, 'total': 500}}
    original = network.__call__

    def real_reply(request):
        if request.url.path == '/v1/ops/usage' and request.headers.get('authorization') == 'Bearer ' + USAGE_KEY:
            network.seen.append(request)
            return httpx.Response(200, json=reply)
        return original(request)
    m.transport = httpx.MockTransport(real_reply)
    config.change_source('school', {'usage_key': USAGE_KEY})
    cards = refresh(m)
    school, gemini = cards['school'], cards['gemini']
    assert school['value'] == 480 and school['spent_today'] == 20 and school['status'] == 'ok'
    rows = {r['label']: r['value'] for r in school['rows']}
    assert rows['오늘 제작 / 하루 한도'].startswith('1 / ')
    assert rows['LLM 설계 (오늘 · 7일 · 전체)'] == '1 · 1 · 1'
    # 2M input at $0.50 + 0.1M output at $3.00 per million tokens.
    assert gemini['spent_today'] == pytest.approx(1.3) and gemini['value'] == pytest.approx(1.3)


def test_config_merge_keeps_user_changes_and_new_defaults(setup, monkeypatch, tmp_path):
    _, _, _, config = setup
    config.change_source('scenario', {'warn_below': 10})
    config.add_source({'id': 'manual_x', 'type': 'manual', 'label': 'X'})
    defaults = store.Config.defaults()
    defaults['sources'].append({'id': 'future', 'type': 'manual', 'label': 'Future service'})
    path = tmp_path / 'defaults.json'
    path.write_text(json.dumps(defaults, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(store, 'DEFAULTS_FILE', path)
    merged = {s['id']: s for s in config.merged()['sources']}
    assert merged['scenario']['warn_below'] == 10 and merged['scenario']['unit'] == 'CU'
    assert merged['future']['builtin'] and not merged['manual_x']['builtin']
    assert list(merged)[-1] == 'manual_x'
