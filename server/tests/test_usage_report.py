"""The cost monitor's read-only usage route: off without a key, bearer-only, aggregates only."""
import json
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings

USAGE_KEY = 'test-only-usage-key-0123456789abcdefghij'
NOW = 2_000_000_000.0
DAY = 86400


def make(tmp_path, **extra):
    options = dict(data_dir=tmp_path, studio_llm='gemini', gemini_key='test-only-gemini',
                   tripo_credit_budget=100, daily_generation_limit=50, **extra)
    app = create_app(Settings(**options), clock=lambda: NOW, worker_enabled=False)
    return app


def register(client, name):
    r = client.post('/v1/auth/register', json={'username': name, 'password': 'Testing-only-12345'})
    assert r.status_code == 200, r.text


def seed(app):
    with app.state.db.transaction() as conn:
        alice, bob = [conn.execute('SELECT id FROM users WHERE username=?', (n,)).fetchone()[0] for n in ('alice_usage', 'bob_usage')]

        def job(job_id, owner, state, created, provenance, parts):
            conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,provenance,parts,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                         (job_id, owner, json.dumps({'prompt': 'SECRET-PROMPT ' + job_id, 'geometry': 'tripo'}), state, 30,
                          json.dumps(provenance), json.dumps(parts), created, created))

        job('job-today-ready', alice, 'ready', NOW - 60,
            {'provider': 'gemini', 'model': 'gemini-3.5-flash', 'geometry': 'tripo', 'estimated_tripo_credits': 30,
             'usage': {'input_tokens': 1000, 'cached_input_tokens': 200, 'output_tokens': 300, 'reasoning_output_tokens': 100}},
            {'body': {'state': 'ready', 'task': 't1', 'credits_consumed': 20}, 'lid': {'state': 'ready', 'task': 't2', 'credits_consumed': 10}})
        # A rejected Gemini design records the request's OpenAI model name: reported as unknown.
        job('job-3-days-failed', bob, 'failed', NOW - 3 * DAY,
            {'provider': 'gemini', 'model': 'gpt-6-luna', 'usage': {'input_tokens': 500, 'output_tokens': 50}}, {})
        job('job-10-days-simple', bob, 'ready', NOW - 10 * DAY, {'provider': 'direct_prompt', 'geometry': 'tripo'},
            {'whole': {'state': 'ready', 'task': 't3', 'credits_consumed': 10, 'concept_task': 'c1', 'concept_credits_consumed': 5}})
        job('job-today-building', alice, 'building', NOW - 30,
            {'provider': 'gemini', 'model': 'gemini-3.5-flash', 'geometry': 'tripo', 'estimated_tripo_credits': 35, 'usage': {}},
            {'whole': {'state': 'generating', 'task': 't4'}})

        def described(design_id, state, created, provenance):
            conn.execute('INSERT INTO interaction_designs(id,owner_id,object_id,text,state,cost,provenance,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                         (design_id, alice, 'object-x', 'SECRET-DESCRIBE ' + design_id, state, 5, json.dumps(provenance), created, created))

        described('design-today-ready', 'ready', NOW - 50,
                  {'provider': 'gemini', 'model': 'gemini-3.1-flash-lite', 'usage': {'input_tokens': 400, 'output_tokens': 40}, 'live': True})
        # Failed interaction designs keep only the usage: the server's provider is assumed.
        described('design-today-failed', 'failed', NOW - 40, {'usage': {'input_tokens': 100}})
        described('design-old-fixture', 'ready', NOW - 20 * DAY, {'provider': 'authored_fixture', 'presets': []})
        return alice, bob


def test_route_is_off_without_a_usage_key(tmp_path):
    with TestClient(make(tmp_path)) as client:
        assert client.get('/v1/ops/usage').status_code == 404
        assert client.get('/v1/ops/usage', headers={'Authorization': 'Bearer ' + USAGE_KEY}).status_code == 404


def test_route_needs_the_usage_key_as_bearer(tmp_path):
    with TestClient(make(tmp_path, usage_key=USAGE_KEY)) as client:
        register(client, 'alice_usage')
        player = client.post('/v1/auth/login', json={'username': 'alice_usage', 'password': 'Testing-only-12345'}).json()['token']
        for headers in ({}, {'Authorization': 'Bearer wrong-key'}, {'Authorization': USAGE_KEY},
                        {'Authorization': 'Basic ' + USAGE_KEY}, {'Authorization': 'Bearer ' + player}):
            response = client.get('/v1/ops/usage', headers=headers)
            assert response.status_code == 401, headers
            assert USAGE_KEY not in response.text
        ok = client.get('/v1/ops/usage', headers={'Authorization': 'Bearer ' + USAGE_KEY})
        assert ok.status_code == 200 and ok.headers['cache-control'] == 'no-store'
        assert USAGE_KEY not in ok.text


def test_usage_totals_are_aggregates_without_personal_data(tmp_path):
    app = make(tmp_path, usage_key=USAGE_KEY)
    with TestClient(app) as client:
        register(client, 'alice_usage')
        register(client, 'bob_usage')
        ids = seed(app)
        response = client.get('/v1/ops/usage', headers={'Authorization': 'Bearer ' + USAGE_KEY})
    assert response.status_code == 200
    text = response.text
    for private in ('alice_usage', 'bob_usage', 'SECRET', 'job-', 'design-', 'object-x', 'Testing-only', *ids):
        assert private not in text, private
    data = response.json()
    assert data['budget'] == {'used': 80, 'total': 100, 'remaining': 20}
    assert data['limits']['daily_crafts'] == 50 and data['limits']['describe_daily_per_account'] == 10
    crafts = data['crafts']
    assert (crafts['today'], crafts['last_7_days'], crafts['total'], crafts['pending']) == (2, 3, 4, 1)
    assert (crafts['today_ready'], crafts['today_failed'], crafts['accounts_today']) == (1, 0, 1)
    credits = data['tripo_credits']
    assert (credits['today'], credits['last_7_days'], credits['total'], credits['committed']) == (30, 30, 45, 80)
    llm = data['llm']
    assert llm['provider'] == 'gemini' and llm['models_configured']
    assert llm['craft_runs'] == {'today': 2, 'last_7_days': 3, 'total': 3}
    assert llm['interaction_runs'] == {'today': 2, 'last_7_days': 2, 'total': 2}
    assert llm['tokens']['today'] == {'input': 1500, 'cached_input': 200, 'output': 340, 'reasoning': 100}
    assert llm['tokens']['total'] == {'input': 2000, 'cached_input': 200, 'output': 390, 'reasoning': 100}
    models = {m['model']: m for m in llm['by_model']}
    assert set(models) == {'gemini-3.5-flash', 'gemini-3.1-flash-lite', 'unknown'}
    assert models['unknown']['runs']['total'] == 2 and models['gemini-3.5-flash']['runs']['today'] == 2
    assert data['interactions'] == {'today': 2, 'last_7_days': 2, 'total': 3, 'ready': 2, 'failed': 1, 'in_progress': 0}
    assert data['accounts'] == {'total': 2, 'new_today': 2}
    daily = data['daily']
    assert len(daily) == 14 and daily[-1]['crafts'] == 2 and daily[-1]['tripo_credits'] == 30
    assert daily[-1]['llm_runs'] == 4 and daily[-1]['interactions'] == 2
    assert daily[-4]['crafts'] == 1 and daily[-4]['failed'] == 1
    assert sum(m['runs'] for m in daily[-1]['models']) == 4


def test_usage_key_settings(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, usage_key='short').validate()
    key_file = tmp_path / 'usage-key'
    key_file.write_text(USAGE_KEY + '\n')
    monkeypatch.setenv('TRIPOTHON_USAGE_KEY_FILE', str(key_file))
    settings = Settings(data_dir=tmp_path)
    settings.validate()
    assert settings.usage_key == USAGE_KEY and USAGE_KEY not in repr(settings)
