"""Shared LLM budgets count irreversible attempts, independently of star refunds."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from server import llm_budget
from server.app import create_app
from server.asset_assembly import demo_design
from server.config import Settings
from server.database import Database
from server.design_provider import DesignProvider
from server.provider import ProviderError


NOW = 86400 * 20000 + 100


def database(tmp_path):
    return Database(tmp_path / 'budget.sqlite3', 'demo')


def rows(db):
    with db.read() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM llm_call_reservations ORDER BY rowid')]


def run_design(db, settings, designer, owner='alice', source='craft_design', clock=lambda: NOW):
    return asyncio.run(llm_budget.generate(db, settings, clock, owner, source, str(uuid.uuid4()),
                                          designer, 'chest', 'gpt-6-luna', 'high', None, None))


def response(raw):
    return httpx.Response(200, json={'status': 'completed',
                                   'output': [{'content': [{'type': 'output_text', 'text': raw}]}]})


def test_repair_reserves_each_call_before_transport(tmp_path):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, studio_llm='openai', llm_key='test-key')
    plan, program = demo_design('chest')
    seen = []

    def handle(request):
        seen.append(request)
        attempts = rows(db)
        assert len(attempts) == len(seen)
        assert attempts[-1]['state'] == 'unknown'
        return response('{}' if len(seen) == 1 else json.dumps({'plan': plan, 'program': program}))

    run_design(db, settings, DesignProvider(settings, httpx.MockTransport(handle)))
    assert len(seen) == 2
    assert all(row['state'] == 'responded' for row in rows(db))
    assert len({row['id'] for row in rows(db)}) == 2
    db.close()


def test_cap_stops_validation_repair_before_second_request(tmp_path):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, studio_llm='openai', llm_key='test-key', llm_user_daily_call_limit=1)
    seen = []

    def handle(request):
        seen.append(request)
        return response('{}')

    with pytest.raises(ProviderError, match='llm_account_daily_limit'):
        run_design(db, settings, DesignProvider(settings, httpx.MockTransport(handle)))
    assert len(seen) == len(rows(db)) == 1
    db.close()


def test_gemini_model_fallbacks_and_retry_share_the_cap(tmp_path):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, studio_llm='gemini', gemini_key='test-key',
                        gemini_models=('busy', 'gone'), llm_user_daily_call_limit=3)
    seen = []

    def handle(request):
        seen.append(request.url.path)
        return httpx.Response(404 if 'gone' in request.url.path else 503)

    designer = DesignProvider(settings, httpx.MockTransport(handle))
    designer.retry_pause = 0
    with pytest.raises(ProviderError, match='llm_account_daily_limit'):
        run_design(db, settings, designer)
    assert len(seen) == 3
    assert [row['model'] for row in rows(db)] == ['busy', 'gone', 'busy']
    db.close()


@pytest.mark.parametrize('interrupt', [httpx.ReadTimeout('ambiguous response'), asyncio.CancelledError()])
def test_uncertain_or_cancelled_call_survives_restart(tmp_path, interrupt):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, studio_llm='openai', llm_key='test-key', llm_user_daily_call_limit=1)

    def handle(request):
        raise interrupt

    with pytest.raises((ProviderError, asyncio.CancelledError)):
        run_design(db, settings, DesignProvider(settings, httpx.MockTransport(handle)))
    assert rows(db)[0]['state'] == 'unknown'
    db.close()
    reopened = database(tmp_path)
    with pytest.raises(ProviderError, match='llm_account_daily_limit'):
        run_design(reopened, settings, DesignProvider(settings, httpx.MockTransport(handle)))
    assert len(rows(reopened)) == 1
    reopened.close()


def test_reserved_call_survives_crash_before_send_and_account_deletion(tmp_path):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, llm_server_daily_call_limit=1)
    with db.transaction() as conn:
        conn.execute("INSERT INTO users(id,username,password_hash,created) VALUES ('alice','alice','unused',?)", (NOW,))
    llm_budget.reserve(db, settings, lambda: NOW, 'alice', 'craft_design', 'job', 'openai', 'model')
    with db.transaction() as conn:
        conn.execute("DELETE FROM users WHERE id='alice'")
    db.close()
    reopened = database(tmp_path)
    with pytest.raises(ProviderError, match='llm_server_daily_limit'):
        llm_budget.reserve(reopened, settings, lambda: NOW, 'bobby', 'interaction_describe', 'other', 'openai', 'model')
    assert rows(reopened)[0]['state'] == 'reserved'
    reopened.close()


def test_daily_cap_rolls_over_at_utc_midnight(tmp_path):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, llm_user_daily_call_limit=1)
    midnight = (NOW // 86400 + 1) * 86400
    llm_budget.reserve(db, settings, lambda: midnight - 1, 'alice', 'craft_design', 'before', 'openai', 'model')
    with pytest.raises(ProviderError, match='llm_account_daily_limit'):
        llm_budget.reserve(db, settings, lambda: midnight - .1, 'alice', 'craft_design', 'denied', 'openai', 'model')
    llm_budget.reserve(db, settings, lambda: midnight, 'alice', 'craft_design', 'after', 'openai', 'model')
    assert len(rows(db)) == 2
    db.close()


@pytest.mark.parametrize('account_cap', [False, True])
def test_last_call_reservation_is_atomic_across_database_instances(tmp_path, account_cap):
    first, second = database(tmp_path), database(tmp_path)
    settings = Settings(data_dir=tmp_path, llm_user_daily_call_limit=1 if account_cap else 20,
                        llm_server_daily_call_limit=1000 if account_cap else 1)
    barrier = Barrier(2)

    def compete(db, owner):
        barrier.wait()
        try:
            llm_budget.reserve(db, settings, lambda: NOW, owner, 'craft_design', owner, 'openai', 'model')
            return 'reserved'
        except ProviderError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(compete, first, 'alice')
        b = pool.submit(compete, second, 'alice' if account_cap else 'bobby')
        result = sorted((a.result(), b.result()))
    assert result == sorted(('reserved', 'llm_account_daily_limit' if account_cap else 'llm_server_daily_limit'))
    assert len(rows(first)) == 1
    first.close()
    second.close()


def test_concurrent_designer_contexts_keep_account_attribution(tmp_path):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, studio_llm='openai', llm_key='test-key')

    async def handle(request):
        await asyncio.sleep(0)
        return response('{}')

    designer = DesignProvider(settings, httpx.MockTransport(handle))

    async def both():
        return await asyncio.gather(*(
            llm_budget.generate(db, settings, lambda: NOW, owner, source, reference, designer,
                                'chest', 'gpt-6-luna', 'high', None, None)
            for owner, source, reference in (('alice', 'craft_design', 'craft'),
                                             ('bobby', 'interaction_describe', 'interaction'))),
            return_exceptions=True)

    assert all(isinstance(error, ProviderError) for error in asyncio.run(both()))
    assert {(r['owner_id'], r['source'], r['reference']) for r in rows(db)} == {
        ('alice', 'craft_design', 'craft'), ('bobby', 'interaction_describe', 'interaction')}
    assert len(rows(db)) == 4
    assert sum(r['owner_id'] == 'alice' for r in rows(db)) == 2
    assert sum(r['owner_id'] == 'bobby' for r in rows(db)) == 2
    db.close()


def mutation(**values):
    return {'request_id': str(uuid.uuid4()), **values}


@pytest.mark.parametrize('tester', [False, True])
def test_failed_craft_and_describe_share_cap_despite_star_refunds(tmp_path, tester):
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100, llm_user_daily_call_limit=3)
    app = create_app(settings, worker_enabled=False)

    class Broken:
        calls = 0

        async def generate(self, *args):
            self.calls += 1
            raise ProviderError('llm_request_failed')

    broken = Broken()
    with TestClient(app) as client:
        registered = client.post('/v1/auth/register', json={'username': 'alice', 'password': 'Budget-test-password'}).json()
        headers = {'Authorization': 'Bearer ' + registered['token']}
        fixture = client.post('/v1/studio/jobs', headers=headers, json=mutation(prompt='chest')).json()
        asyncio.run(app.state.studio.process(fixture['id']))
        ready = client.get('/v1/studio/jobs/' + fixture['id'], headers=headers).json()
        assert ready['state'] == 'ready'
        assert rows(app.state.db) == []
        with app.state.db.transaction() as conn:
            conn.execute('UPDATE users SET is_tester=?', (int(tester),))
        settings.studio_llm = 'openai'
        app.state.studio.designer = broken
        balance = client.get('/v1/me', headers=headers).json()['shards']

        craft = client.post('/v1/studio/jobs', headers=headers,
                            json=mutation(prompt='failure design', designer='llm')).json()
        asyncio.run(app.state.studio.process(craft['id']))
        assert client.get('/v1/studio/jobs/' + craft['id'], headers=headers).json()['state'] == 'failed'
        route = '/v1/objects/' + ready['object_id'] + '/interaction/describe'
        for index in range(4):
            result = client.post(route, headers=headers, json=mutation(text='failure description ' + str(index))).json()
            assert result['state'] == 'failed'
            assert result['error'] == ('llm_request_failed' if index < 2 else 'llm_account_daily_limit')
            assert result['shards'] == balance
        assert broken.calls == 3
        assert len(rows(app.state.db)) == 3
        assert {r['source'] for r in rows(app.state.db)} == {'craft_design', 'interaction_describe'}


def test_learned_craft_and_description_do_not_reserve_calls(tmp_path):
    settings = Settings(data_dir=tmp_path, studio_llm='openai', daily_generation_limit=100,
                        llm_user_daily_call_limit=2)

    class Designer:
        calls = 0

        async def generate(self, prompt, *args):
            self.calls += 1
            plan, program = demo_design('chest')
            if 'PLAN TO RETURN UNCHANGED: ' in prompt:
                plan = json.loads(prompt.split('PLAN TO RETURN UNCHANGED: ', 1)[1].split('\n', 1)[0])
            return plan, program, {'provider': 'openai'}

    designer = Designer()
    app = create_app(settings, worker_enabled=False, designer=designer)
    with TestClient(app) as client:
        registration = client.post('/v1/auth/register', json={
            'username': 'alice', 'password': 'Budget-test-password'}).json()
        headers = {'Authorization': 'Bearer ' + registration['token']}

        def craft():
            job = client.post('/v1/studio/jobs', headers=headers,
                              json=mutation(prompt='wooden chest', designer='llm')).json()
            asyncio.run(app.state.studio.process(job['id']))
            result = client.get('/v1/studio/jobs/' + job['id'], headers=headers).json()
            assert result['state'] == 'ready', result
            return result['object_id']

        object_id = craft()
        route = '/v1/objects/' + object_id + '/interaction/describe'
        first = client.post(route, headers=headers, json=mutation(text='open the lid')).json()
        assert first['state'] == 'ready', first
        assert len(rows(app.state.db)) == designer.calls == 2
        craft()
        learned = client.post(route, headers=headers, json=mutation(text='open the lid')).json()
        assert learned['state'] == 'ready' and learned['cost'] == 0
        assert len(rows(app.state.db)) == designer.calls == 2


@pytest.mark.parametrize('field', ['llm_user_daily_call_limit', 'llm_server_daily_call_limit'])
@pytest.mark.parametrize('value', [-1, 1000001, 1.5, True])
def test_invalid_daily_limits_are_rejected(tmp_path, field, value):
    with pytest.raises(ValueError, match='Invalid LLM daily call limits'):
        Settings(data_dir=tmp_path, **{field: value}).validate()


@pytest.mark.parametrize('field', ['llm_user_daily_call_limit', 'llm_server_daily_call_limit'])
def test_zero_limit_disables_llm_calls(tmp_path, field):
    db = database(tmp_path)
    settings = Settings(data_dir=tmp_path, **{field: 0})
    settings.validate()
    with pytest.raises(ProviderError, match='llm_.*_daily_limit'):
        llm_budget.reserve(db, settings, lambda: NOW, 'alice', 'craft_design', 'job', 'openai', 'model')
    assert rows(db) == []
    db.close()
