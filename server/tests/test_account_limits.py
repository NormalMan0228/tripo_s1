import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from server.account_limits import reserve_tester_credits, tester_credits as committed_credits
from server.admin_cli import main
from server.app import create_app
from server.config import Settings
from server.provider import ProviderError
from server.tests.test_studio import FurnitureProvider, mutation


PASSWORD = 'Test-account-password'


class Provider(FurnitureProvider):
    async def submit(self, prompt):
        return (await self.request('POST', '/generation/text-to-model', {'prompt': prompt}))['task_id']


def world(path, **overrides):
    options = dict(mode='live', registration_code='test-only-invitation-123456',
                   paid_enabled=True, tripo_key='test-only-key', daily_generation_limit=100,
                   legacy_generation_enabled=True)
    settings = Settings(data_dir=path, **{**options, **overrides})
    provider = Provider()
    app = create_app(settings, provider=provider, worker_enabled=False)
    return app, TestClient(app, base_url='https://testserver'), provider


def register(c, app, name):
    r = c.post('/v1/auth/register', json=dict(username=name, password=PASSWORD,
               invitation=app.state.settings.registration_code))
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


def create_tester(c, path, name, monkeypatch):
    monkeypatch.setenv('TRIPOTHON_TESTER_PASSWORD', PASSWORD)
    assert main(['tester', 'create', name, '--data-dir', str(path)]) == 0
    r = c.post('/v1/auth/login', json=dict(username=name, password=PASSWORD))
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


def craft(c, h, **overrides):
    return c.post('/v1/studio/jobs', headers=h, json=mutation(**{
        'prompt': 'wooden stool', 'motion': 'static', 'geometry': 'tripo',
        'designer': 'simple', **overrides}))


def run(app, job, times=1):
    for _ in range(times):
        asyncio.run(app.state.studio.process(job))


def confirm(c, h, job, **fields):
    return c.post('/v1/studio/jobs/' + job + '/confirm', headers=h, json=mutation(**fields))


def test_policy_defaults_and_names_never_grant_privileges(monkeypatch):
    for key in ('TRIPO_USER_DAILY_REQUEST_LIMIT', 'TRIPOTHON_WELCOME_STARS',
                'TRIPOTHON_MAX_STARS_PER_CRAFT', 'TRIPOTHON_TESTER_WELCOME_STARS',
                'TRIPOTHON_TESTER_CREDIT_BUDGET'):
        monkeypatch.delenv(key, raising=False)
    s = Settings(mode='live')
    normal = s.limits_for({'username': 'tripo1', 'role': 'admin'})
    assert (normal.user_daily_generation_limit, normal.welcome_stars, normal.max_stars_per_craft) == (5, 150, 200)
    testing = s.limits_for({'is_tester': 1})
    assert (testing.daily_generation_limit, testing.user_daily_generation_limit, testing.user_total_generation_limit) == (0, 0, 0)
    assert (testing.welcome_stars, testing.tester_credit_budget, testing.max_stars_per_craft) == (1500, 10000, 200)


def test_welcome_only_new_live_accounts(tmp_path):
    app, client, _ = world(tmp_path)
    with client as c:
        h = register(c, app, 'alice')
        assert c.get('/v1/me', headers=h).json()['shards'] == 150
        with app.state.db.transaction() as conn:
            conn.execute('UPDATE users SET shards=17')
    app, client, _ = world(tmp_path)
    with client as c:
        r = c.post('/v1/auth/login', json=dict(username='alice', password=PASSWORD))
        assert c.get('/v1/me', headers={'Authorization': 'Bearer ' + r.json()['token']}).json()['shards'] == 17
        h = register(c, app, 'bravo')
        assert c.get('/v1/me', headers=h).json()['shards'] == 150


def test_daily_five_shared_across_endpoints_and_resets_at_utc_day(tmp_path):
    app, client, provider = world(tmp_path)
    with client as c:
        h = register(c, app, 'alice')
        for _ in range(4):
            job = craft(c, h).json()['id']
            assert c.post('/v1/studio/jobs/' + job + '/cancel', headers=h, json=mutation()).status_code == 200
        legacy = c.post('/v1/generations', headers=h, json=mutation(prompt='chair'))
        assert legacy.status_code == 200
        asyncio.run(app.state.process_job(legacy.json()['id']))
        assert craft(c, h).json()['detail'] == 'user_daily_generation_limit'
        assert c.post('/v1/generations', headers=h, json=mutation(prompt='chair')).json()['detail'] == 'user_daily_generation_limit'
        with app.state.db.transaction() as conn:
            conn.execute('UPDATE studio_jobs SET created=0')
            conn.execute('UPDATE jobs SET created=0')
        assert craft(c, h).status_code == 200
        assert len(provider.calls) == 1


def test_tester_daily_and_lifetime_exemption_does_not_use_normal_pool(tmp_path, monkeypatch):
    app, client, _ = world(tmp_path, daily_generation_limit=1, user_daily_generation_limit=1,
                           user_total_generation_limit=1)
    with client as c:
        h = create_tester(c, tmp_path, 'tripo1', monkeypatch)
        for _ in range(6):
            job = craft(c, h).json()['id']
            c.post('/v1/studio/jobs/' + job + '/cancel', headers=h, json=mutation())
        legacy = c.post('/v1/generations', headers=h, json=mutation(prompt='chair'))
        assert legacy.status_code == 200
        asyncio.run(app.state.process_job(legacy.json()['id']))
        h2 = register(c, app, 'alice')
        job = craft(c, h2).json()['id']
        c.post('/v1/studio/jobs/' + job + '/cancel', headers=h2, json=mutation())
        assert craft(c, h2).json()['detail'] == 'daily_generation_limit'
        assert craft(c, h).status_code == 200


@pytest.mark.parametrize('rate,allowed', [(2, True), (2.01, False)])
def test_final_star_quote_boundary(tmp_path, monkeypatch, rate, allowed):
    app, client, provider = world(tmp_path, studio_credit_rate=rate)
    with client as c:
        h = create_tester(c, tmp_path, 'tripo1', monkeypatch)
        job = craft(c, h).json()['id']
        run(app, job)
        result = confirm(c, h, job)
        assert result.status_code == (200 if allowed else 403), result.text
        if allowed:
            assert result.json()['cost'] == 200
            assert c.get('/v1/me', headers=h).json()['shards'] == 1300
        else:
            assert result.json()['detail'] == 'craft_star_limit_exceeded'
            assert c.get('/v1/me', headers=h).json()['shards'] == 1480
            assert c.post('/v1/studio/jobs/' + job + '/cancel', headers=h, json=mutation()).status_code == 200
            assert c.get('/v1/me', headers=h).json()['shards'] == 1500
        assert not provider.calls


def test_initial_star_cap_checks_both_endpoints(tmp_path):
    app, client, _ = world(tmp_path, max_stars_per_craft=19)
    with client as c:
        h = register(c, app, 'alice')
        assert craft(c, h).json()['detail'] == 'craft_star_limit_exceeded'
        assert c.post('/v1/generations', headers=h, json=mutation(prompt='chair')).json()['detail'] == 'craft_star_limit_exceeded'
        assert c.get('/v1/me', headers=h).json()['shards'] == 150


def test_shared_budget_confirm_race_restart_failure_and_deletion(tmp_path, monkeypatch, capsys):
    app, client, provider = world(tmp_path, tester_credit_budget=100)
    with client as c:
        h1 = create_tester(c, tmp_path, 'tripo1', monkeypatch)
        h2 = create_tester(c, tmp_path, 'tripo2', monkeypatch)
        j1 = craft(c, h1).json()['id']; run(app, j1)
        j2 = craft(c, h2).json()['id']; run(app, j2)
        assert confirm(c, h1, j1).status_code == 200
        provider.uncertain = True
        run(app, j1)
        assert confirm(c, h2, j2).json()['detail'] == 'tester_credit_budget_exhausted'
        run(app, j1)
        assert len(provider.calls) == 1
        assert c.get('/v1/studio', headers=h2).json()['tester_budget_used'] == 100
    app, client, _ = world(tmp_path, tester_credit_budget=100)
    with client as c:
        r = c.post('/v1/auth/login', json=dict(username='tripo2', password=PASSWORD))
        h2 = {'Authorization': 'Bearer ' + r.json()['token']}
        assert confirm(c, h2, j2).json()['detail'] == 'tester_credit_budget_exhausted'
        assert main(['delete-accounts', 'tripo1', '--yes', '--data-dir', str(tmp_path),
                     '--backups', str(tmp_path.parent / (tmp_path.name + '-backups'))]) == 0
        with app.state.db.read() as conn:
            assert committed_credits(conn) == 100
        assert confirm(c, h2, j2).json()['detail'] == 'tester_credit_budget_exhausted'


def test_legacy_and_studio_share_tester_budget(tmp_path, monkeypatch):
    app, client, _ = world(tmp_path, tester_credit_budget=100)
    with client as c:
        h1 = create_tester(c, tmp_path, 'tripo1', monkeypatch)
        h2 = create_tester(c, tmp_path, 'tripo2', monkeypatch)
        r = c.post('/v1/generations', headers=h1, json=mutation(prompt='chair'))
        assert r.status_code == 200
        asyncio.run(app.state.process_job(r.json()['id']))
        assert craft(c, h2).json()['detail'] == 'tester_credit_budget_exhausted'
        assert c.post('/v1/generations', headers=h2, json=mutation(prompt='chair')).json()['detail'] == 'tester_credit_budget_exhausted'


def test_operator_create_grant_list_and_public_spoofing(tmp_path, monkeypatch, capsys):
    app, client, _ = world(tmp_path)
    with client as c:
        for spoof in ({'is_tester': True}, {'role': 'tester'}):
            r = c.post('/v1/auth/register', json=dict(username='tripo1', password=PASSWORD,
                       invitation=app.state.settings.registration_code, **spoof))
            assert r.status_code == 422
        h = register(c, app, 'tripo1')
        assert c.get('/v1/studio', headers=h).json()['tester_budget'] == 0
        assert c.post('/v1/admin/tester', headers=h, json=mutation(username='tripo1')).status_code == 404
        args = ['--data-dir', str(tmp_path)]
        assert main(['tester', 'grant', 'tripo1', *args]) == 0
        assert main(['tester', 'grant', 'tripo1', *args]) == 0
        assert c.get('/v1/me', headers=h).json()['shards'] == 150  # no backfill on grant
        h2 = create_tester(c, tmp_path, 'tripo2', monkeypatch)
        assert c.get('/v1/me', headers=h2).json()['shards'] == 1500
        assert main(['tester', 'create', 'tripo2', *args]) == 1
        assert main(['tester', 'grant', 'alice', *args]) == 1
        assert main(['tester', 'create', 'tripo6', *args]) == 1
        capsys.readouterr()
        assert main(['tester', 'list', *args]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result['accounts'] == [{'username': 'tripo1', 'stars': 150}, {'username': 'tripo2', 'stars': 1500}]
        with app.state.db.read() as conn:
            assert all(r['role'] == 'player' for r in conn.execute('SELECT role FROM users'))
            assert conn.execute("SELECT count(*) FROM ledger WHERE reason='tester_welcome'").fetchone()[0] == 1


def test_atomic_budget_reservations_and_replay(tmp_path):
    app, _, _ = world(tmp_path, tester_credit_budget=100)
    limits = app.state.settings.limits_for({'is_tester': 1})
    def reserve(reference):
        try:
            with app.state.db.transaction() as conn:
                reserve_tester_credits(conn, limits, reference, 100)
            return True
        except ProviderError as error:
            assert error.code == 'tester_credit_budget_exhausted'
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, ('one', 'two'))) == [False, True]
    with app.state.db.transaction() as conn:
        reference = conn.execute('SELECT reference FROM tester_credit_spend').fetchone()[0]
        reserve_tester_credits(conn, limits, reference, 100)
        assert committed_credits(conn) == 100


def test_concepts_redraw_and_failed_pictures_keep_credit_reservations(tmp_path, monkeypatch):
    from server.tests.test_concept import Provider as ConceptProvider, world as concept_world, craft as concept_craft
    provider = ConceptProvider()
    app, client = concept_world(tmp_path, provider, tester_credit_budget=40)
    with client as c:
        h = create_tester(c, tmp_path, 'tripo1', monkeypatch)
        job = c.post('/v1/studio/jobs', headers=h, json=concept_craft()).json()['id']
        run(app, job)
        assert c.get('/v1/studio', headers=h).json()['tester_budget_used'] == 5
        redraw = '/v1/studio/jobs/' + job + '/redraw'
        assert c.post(redraw, headers=h, json=mutation()).status_code == 200
        provider.fail_concept = True
        run(app, job)
        assert c.get('/v1/studio', headers=h).json()['tester_budget_used'] == 10
        provider.fail_concept = False
        assert c.post(redraw, headers=h, json=mutation()).status_code == 200
        run(app, job)
        assert c.get('/v1/studio', headers=h).json()['tester_budget_used'] == 15
        assert confirm(c, h, job).json()['detail'] == 'tester_credit_budget_exhausted'
        # Choosing text instead uses 20 mesh credits and fits; concepts stay charged.
        assert confirm(c, h, job, use_concept=False).status_code == 200
        assert c.get('/v1/studio', headers=h).json()['tester_budget_used'] == 35


def test_actual_overrun_is_recorded_before_next_part_is_submitted(tmp_path, monkeypatch):
    from server.tests.test_studio import paid_world
    class OverbillingProvider(Provider):
        async def task(self, task):
            result = await super().task(task)
            result['credits_consumed'] = 150
            return result
    provider = OverbillingProvider()
    app, client = paid_world(tmp_path, provider)
    app.state.settings.tester_credit_budget = 200
    with client as c:
        h = create_tester(c, tmp_path, 'tripo1', monkeypatch)
        # A moving chest has two P2 meshes quoted at 100 each.
        job = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt='wooden chest', geometry='tripo')).json()['id']
        run(app, job)
        assert confirm(c, h, job).status_code == 200
        run(app, job, 4)
        status = c.get('/v1/studio/jobs/' + job, headers=h).json()
        assert status['error'] == 'tester_credit_budget_exhausted'
        assert len(provider.calls) == 1


def test_no_server_wide_daily_limit_keeps_each_accounts_five(tmp_path):
    # The main server (2026-10-16): TRIPO_DAILY_REQUEST_LIMIT=0 means no server-wide daily count; the
    # Tripo credit budget is the limit, and every account still has its own five a day.
    app, client, provider = world(tmp_path, daily_generation_limit=0)
    with client as c:
        for name in ('alice', 'bravo'):
            h = register(c, app, name)
            for _ in range(5):
                job = craft(c, h).json()['id']
                assert c.post('/v1/studio/jobs/' + job + '/cancel', headers=h, json=mutation()).status_code == 200
            assert craft(c, h).json()['detail'] == 'user_daily_generation_limit'
    Settings(data_dir=tmp_path, daily_generation_limit=0).validate()
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, daily_generation_limit=-1).validate()
