import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings, configured_secret


def test_live_secret_files_never_enter_settings_repr(tmp_path, monkeypatch):
    key = tmp_path / 'openai-key'
    key.write_text('test-private-value\n', encoding='utf-8')
    monkeypatch.setenv('OPENAI_API_KEY_FILE', str(key))
    assert configured_secret('OPENAI_API_KEY') == 'test-private-value'
    assert 'test-private-value' not in repr(Settings())
    monkeypatch.setenv('OPENAI_API_KEY', 'another-value')
    with pytest.raises(ValueError, match='configure_only_one_openai_api_key_source'):
        configured_secret('OPENAI_API_KEY')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    key.write_text('bad\nsecond-line', encoding='utf-8')
    with pytest.raises(ValueError) as error:
        configured_secret('OPENAI_API_KEY')
    assert str(error.value) == 'invalid_openai_api_key_file'


def test_live_starts_without_paid_keys_and_blocks_legacy_generation(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', registration_code='test-only-invitation-123456')
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='http://testserver') as client:
        assert client.get('/health').json()['detail'] == 'https_required'
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={
            'username': 'live_user', 'password': 'Test-password-123',
            'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        assert client.get('/v1/me', headers=headers).json()['generation_enabled'] is False
        response = client.post('/v1/generations', headers=headers, json={
            'request_id': str(uuid.uuid4()), 'prompt': 'chair'})
        assert response.status_code == 403
        assert response.json()['detail'] == 'legacy_generation_disabled'


def test_paid_live_requires_the_secrets_its_designers_use(tmp_path):
    with pytest.raises(ValueError, match='Tripo server secret'):
        create_app(Settings(data_dir=tmp_path, mode='live', paid_enabled=True,
                            registration_code='test-only-invitation-123456'), worker_enabled=False)
    with pytest.raises(ValueError, match='OpenAI server secret'):
        create_app(Settings(data_dir=tmp_path, mode='live', paid_enabled=True, studio_llm='openai',
                            tripo_key='test-only-key', registration_code='test-only-invitation-123456'),
                   worker_enabled=False)


def test_paid_live_with_only_tripo_offers_the_simple_craft(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        registration_code='test-only-invitation-123456')
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={
            'username': 'simple_user', 'password': 'Test-password-123',
            'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        # Live accounts start without Starseeds; survival rewards pay for crafts.
        with app.state.db.transaction() as db:
            db.execute('UPDATE users SET shards=100')

        def request(**changes):
            return client.post('/v1/studio/jobs', headers=headers, json={
                'request_id': str(uuid.uuid4()), 'prompt': 'tiny mushroom stool', 'motion': 'static', 'mesh_model': 'v3.1-20260211',
                'geometry': 'tripo', **changes})

        assert request(designer='llm').json()['detail'] == 'llm_not_configured'
        assert request(designer='simple', motion='dynamic').json()['detail'] == 'simple_requires_static_text'
        assert request(designer='fixture').status_code == 403
        job = request(designer='simple')
        assert job.status_code == 200, job.json()
        asyncio.run(app.state.studio.process(job.json()['id']))
        status = client.get('/v1/studio/jobs/' + job.json()['id'], headers=headers).json()
        assert status['state'] == 'awaiting_confirmation'
        assert status['provenance']['provider'] == 'direct_prompt'
        assert status['provenance']['estimated_tripo_credits'] == 10 and len(status['parts']) == 1


def test_paid_live_limits_user_and_model_before_any_provider_call(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='openai', llm_key='test-only-key',
                        registration_code='test-only-invitation-123456',
                        daily_generation_limit=5, user_daily_generation_limit=1)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={
            'username': 'paid_user', 'password': 'Test-password-123',
            'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        with app.state.db.transaction() as db:
            db.execute('UPDATE users SET shards=200')

        def request(**changes):
            return client.post('/v1/studio/jobs', headers=headers, json={
                'request_id': str(uuid.uuid4()), 'prompt': 'wooden chair',
                'designer': 'llm', 'geometry': 'tripo', **changes})

        assert request(model='gpt-6-astra').status_code == 403
        assert request(effort='xhigh').status_code == 403
        accepted = request()
        assert accepted.status_code == 200
        with app.state.db.transaction() as db:
            db.execute("UPDATE studio_jobs SET state='failed' WHERE id=?", (accepted.json()['id'],))
        denied = request()
        assert denied.status_code == 429
        assert denied.json()['detail'] == 'user_daily_generation_limit'


def test_judging_server_welcome_stars_and_lifetime_craft_limit(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='gemini', gemini_key='test-only-key',
                        registration_code='test-only-invitation-123456',
                        daily_generation_limit=100, user_daily_generation_limit=50,
                        user_total_generation_limit=2, welcome_stars=150)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={
            'username': 'judge_one', 'password': 'Test-password-123',
            'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        with app.state.db.transaction() as db:
            assert db.execute("SELECT shards FROM users WHERE username='judge_one'").fetchone()[0] == 150

        def request():
            return client.post('/v1/studio/jobs', headers=headers, json={
                'request_id': str(uuid.uuid4()), 'prompt': 'wooden chair', 'designer': 'llm', 'geometry': 'tripo'})

        for i in range(2):
            accepted = request()
            assert accepted.status_code == 200, accepted.json()
            with app.state.db.transaction() as db:
                db.execute("UPDATE studio_jobs SET state='ready' WHERE id=?", (accepted.json()['id'],))
        denied = request()
        assert denied.status_code == 429 and denied.json()['detail'] == 'user_total_generation_limit'


def test_open_registration_without_code_is_limited_per_address_and_day(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', registration_code='test-only-invitation-123456',
                        open_registration=True, signups_per_ip_day=2, signups_per_day=3, welcome_stars=150)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        def register(name, invitation=''):
            return client.post('/v1/auth/register', json={
                'username': name, 'password': 'Test-password-123', 'invitation': invitation})
        assert client.get('/health').json()['open_registration'] is True
        assert register('open_one').status_code == 200
        assert register('open_two').status_code == 200
        third = register('open_three')
        assert third.status_code == 429 and third.json()['detail'] == 'too_many_registrations'
        # The invitation code still works and is not counted against the open limits.
        assert register('invited_one', settings.registration_code).status_code == 200
        with app.state.db.transaction() as db:
            assert db.execute("SELECT shards FROM users WHERE username='open_one'").fetchone()[0] == 150


def test_open_registration_daily_ceiling_and_default_stays_invite_only(tmp_path):
    settings = Settings(data_dir=tmp_path / 'open', mode='live', registration_code='test-only-invitation-123456',
                        open_registration=True, signups_per_ip_day=50, signups_per_day=1)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        body = {'password': 'Test-password-123', 'invitation': ''}
        assert client.post('/v1/auth/register', json={'username': 'day_one', **body}).status_code == 200
        closed = client.post('/v1/auth/register', json={'username': 'day_two', **body})
        assert closed.status_code == 429 and closed.json()['detail'] == 'registration_closed_today'
    closed_settings = Settings(data_dir=tmp_path / 'closed', mode='live', registration_code='test-only-invitation-123456')
    with TestClient(create_app(closed_settings, worker_enabled=False), base_url='https://testserver') as client:
        denied = client.post('/v1/auth/register', json={'username': 'no_code', 'password': 'Test-password-123', 'invitation': ''})
        assert denied.status_code == 403 and denied.json()['detail'] == 'invalid_invitation'
        assert client.get('/health').json()['open_registration'] is False


def test_trial_credit_cap_allows_only_the_cheapest_craft(tmp_path):
    from server.asset_assembly import demo_design

    class ManyParts:
        async def generate(self, prompt, model, effort, image=None):
            plan, program = demo_design('flower')  # eight parts
            return plan, program, {'provider': 'gemini', 'model': 'test'}

    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='gemini', gemini_key='test-only-key', registration_code='test-only-invitation-123456',
                        daily_generation_limit=100, user_daily_generation_limit=100, max_credits_per_craft=10)
    app = create_app(settings, worker_enabled=False, designer=ManyParts())
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={'username': 'trial_judge', 'password': 'Test-password-123',
                                                        'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        with app.state.db.transaction() as db:
            db.execute('UPDATE users SET shards=500')
        assert client.get('/v1/studio', headers=headers).json()['max_tripo_credits'] == 10

        def request(**changes):
            body = {'request_id': str(uuid.uuid4()), 'prompt': 'wooden chair', 'designer': 'llm', 'geometry': 'tripo',
                    'material': 'mesh', 'motion': 'static', 'mesh_model': 'v3.1-20260211', **changes}
            return client.post('/v1/studio/jobs', headers=headers, json=body)

        for changes in ({'material': 'textured'}, {'motion': 'dynamic'}, {'mesh_model': 'P2-20260801'}, {'mesh_model': 'configured'}):
            refused = request(**changes)
            assert refused.status_code == 403 and refused.json()['detail'] == 'craft_over_trial_limit', changes
        # The cheapest craft: the eight-part design is merged into one static mesh = 10 credits.
        accepted = request()
        assert accepted.status_code == 200, accepted.json()
        asyncio.run(app.state.studio.process(accepted.json()['id']))
        job = client.get('/v1/studio/jobs/' + accepted.json()['id'], headers=headers).json()
        assert job['state'] == 'awaiting_confirmation' and job['provenance']['estimated_tripo_credits'] == 10


def test_trial_credit_cap_fails_and_refunds_a_design_over_the_cap(tmp_path):
    from server.asset_assembly import demo_design

    class ManyParts:
        async def generate(self, prompt, model, effort, image=None):
            plan, program = demo_design('flower')
            return plan, program, {'provider': 'gemini', 'model': 'test'}

    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='gemini', gemini_key='test-only-key', registration_code='test-only-invitation-123456',
                        daily_generation_limit=100, user_daily_generation_limit=100, max_credits_per_craft=25)
    app = create_app(settings, worker_enabled=False, designer=ManyParts())
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={'username': 'trial_two', 'password': 'Test-password-123',
                                                        'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        with app.state.db.transaction() as db:
            db.execute('UPDATE users SET shards=500')
        job = client.post('/v1/studio/jobs', headers=headers, json={
            'request_id': str(uuid.uuid4()), 'prompt': 'flower lamp', 'designer': 'llm', 'geometry': 'tripo',
            'material': 'mesh', 'motion': 'dynamic', 'mesh_model': 'v3.1-20260211'})
        assert job.status_code == 200, job.json()
        asyncio.run(app.state.studio.process(job.json()['id']))
        status = client.get('/v1/studio/jobs/' + job.json()['id'], headers=headers).json()
        assert status['state'] == 'failed' and status['error'] == 'craft_over_trial_limit'
        with app.state.db.transaction() as db:
            assert db.execute("SELECT shards FROM users WHERE username='trial_two'").fetchone()[0] == 500


def test_trial_cap_counts_every_tripo_request_failed_ones_included(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='gemini', gemini_key='test-only-key',
                        registration_code='test-only-invitation-123456',
                        daily_generation_limit=100, user_daily_generation_limit=50,
                        user_total_generation_limit=3, welcome_stars=150)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={
            'username': 'judge_two', 'password': 'Test-password-123',
            'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}

        def request():
            return client.post('/v1/studio/jobs', headers=headers, json={
                'request_id': str(uuid.uuid4()), 'prompt': 'wooden chair', 'designer': 'llm', 'geometry': 'tripo'})

        def finish(job_id, state, sent=True):
            parts = '{"whole": {"state": "generating", "task": "task-%s"}}' % job_id if sent else '{"whole": {"state": "pending"}}'
            with app.state.db.transaction() as db:
                db.execute('UPDATE studio_jobs SET state=?, parts=? WHERE id=?', (state, parts, job_id))

        # Two crafts reached Tripo and then failed: the old count (non-failed jobs) missed them.
        for i in range(2):
            accepted = request()
            assert accepted.status_code == 200, accepted.json()
            finish(accepted.json()['id'], 'failed')
        # A design that failed before Tripo does not use the cap.
        early = request()
        finish(early.json()['id'], 'failed', sent=False)
        studio = client.get('/v1/studio', headers=headers).json()
        assert studio['tripo_requests_used'] == 2 and studio['tripo_requests_limit'] == 3

        # The third request waits for confirmation; meanwhile a third Tripo request is recorded
        # (as an old client in another room could have done), so confirming is refused.
        third = request().json()['id']
        with app.state.db.transaction() as db:
            db.execute("UPDATE studio_jobs SET state='awaiting_confirmation', provenance=? WHERE id=?",
                       ('{"estimated_tripo_credits": 10, "quoted_game_cost": 20}', third))
            db.execute("INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated,parts) SELECT 'extra',owner_id,request,'failed',0,created,updated,'{\"whole\": {\"task\": \"t\"}}' FROM studio_jobs WHERE id=?", (third,))
        denied = client.post(f'/v1/studio/jobs/{third}/confirm', headers=headers, json={'request_id': str(uuid.uuid4())})
        assert denied.status_code == 429 and denied.json()['detail'] == 'user_total_generation_limit'
        client.post(f'/v1/studio/jobs/{third}/cancel', headers=headers, json={'request_id': str(uuid.uuid4())})
        # Three Tripo requests used: a fourth craft cannot even start.
        fourth = request()
        assert fourth.status_code == 429 and fourth.json()['detail'] == 'user_total_generation_limit'
        assert client.get('/v1/studio', headers=headers).json()['tripo_requests_used'] == 3

        # The worker checks again right before sending to Tripo.
        from server.provider import ProviderError
        with app.state.db.transaction() as db:
            job = dict(db.execute('SELECT * FROM studio_jobs WHERE id=?', (third,)).fetchone())
        with pytest.raises(ProviderError) as stopped:
            app.state.studio.guard_tripo_cap(job, {'whole': {'state': 'pending'}})
        assert str(stopped.value) == 'user_total_generation_limit'


def test_used_up_trial_reads_well_in_released_room_and_village_clients(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='gemini', gemini_key='test-only-key',
                        registration_code='test-only-invitation-123456',
                        daily_generation_limit=100, user_daily_generation_limit=50,
                        user_total_generation_limit=3, welcome_stars=150)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={
            'username': 'judge_three', 'password': 'Test-password-123',
            'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        with app.state.db.transaction() as db:
            user = db.execute("SELECT id FROM users WHERE username='judge_three'").fetchone()[0]
            for i in range(3):
                db.execute("INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated,parts) VALUES (?,?,?,?,?,?,?,?)",
                           (f'used-{i}', user, '{"geometry": "tripo"}', 'failed', 0, 0, 0, '{"whole": {"task": "t%d"}}' % i))
        # 0.10.2 village window (main.gd CRAFT_REQUEST): the code, which it words in three languages.
        village = client.post('/v1/studio/jobs', headers=headers, json={
            'request_id': str(uuid.uuid4()), 'prompt': 'wooden chair', 'material': 'mesh', 'motion': 'static',
            'designer': 'llm', 'geometry': 'tripo', 'mesh_model': 'v3.1-20260211', 'model': 'gpt-6-luna', 'effort': 'high'})
        assert village.status_code == 429 and village.json()['detail'] == 'user_total_generation_limit'
        # 0.10.2 room studio (studio.gd generate): a sentence it shows after "생성을 시작하지 못했어요 · ".
        room = client.post('/v1/studio/jobs', headers=headers, json={
            'request_id': str(uuid.uuid4()), 'prompt': 'wooden chair', 'material': 'mesh', 'motion': 'static',
            'designer': 'llm', 'geometry': 'tripo', 'model': 'gpt-6-luna', 'effort': 'high', 'image': '',
            'mesh_model': 'v3.1-20260211', 'image_mode': 'original'})
        assert room.status_code == 429 and room.json()['detail'] == '체험판 제작 3회를 모두 썼어요. 만든 물건으로 마을을 꾸며 보세요!'
        # Its message() only rewrites snake_case codes; the sentence has none, so it is shown as is.
        import re
        assert not re.search(r'[a-z][a-z0-9]*_[a-z0-9_]+', room.json()['detail'])


def test_server_tripo_budget_stops_crafting_when_used_up(tmp_path):
    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='gemini', gemini_key='test-only-key',
                        registration_code='test-only-invitation-123456',
                        daily_generation_limit=100, user_daily_generation_limit=50,
                        max_credits_per_craft=30, tripo_credit_budget=50, welcome_stars=500)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={
            'username': 'school_one', 'password': 'Test-password-123',
            'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}

        def request(material='textured'):
            return client.post('/v1/studio/jobs', headers=headers, json={
                'request_id': str(uuid.uuid4()), 'prompt': 'wooden chair', 'designer': 'llm', 'geometry': 'tripo',
                'material': material, 'motion': 'static', 'mesh_model': 'v3.1-20260211'})

        # A coloured craft (20 credits) fits the 30-credit cap; Tripo reported 20 for it.
        first = request()
        assert first.status_code == 200, first.json()
        with app.state.db.transaction() as db:
            db.execute("UPDATE studio_jobs SET state='ready', parts=?, provenance=? WHERE id=?",
                       ('{"whole": {"state": "ready", "task": "t1", "credits_consumed": 20}}', '{"estimated_tripo_credits": 20}', first.json()['id']))
        # A second one is quoted (20) and confirmed: 40 committed of 50.
        second = request().json()['id']
        with app.state.db.transaction() as db:
            db.execute("UPDATE studio_jobs SET state='awaiting_confirmation', provenance=? WHERE id=?",
                       ('{"estimated_tripo_credits": 20, "quoted_game_cost": 40}', second))
        confirmed = client.post(f'/v1/studio/jobs/{second}/confirm', headers=headers, json={'request_id': str(uuid.uuid4())})
        assert confirmed.status_code == 200, confirmed.json()
        studio = client.get('/v1/studio', headers=headers).json()
        assert studio['tripo_budget'] == 50 and studio['tripo_budget_used'] == 40
        # 40 + 20 > 50: the next coloured craft is refused; a 10-credit one still fits.
        with app.state.db.transaction() as db:
            db.execute("UPDATE studio_jobs SET state='ready', parts=? WHERE id=?",
                       ('{"whole": {"state": "ready", "task": "t2", "credits_consumed": 20}}', second))
        refused = request()
        assert refused.status_code == 429 and refused.json()['detail'] == 'tripo_budget_exhausted'
        assert request('mesh').status_code == 200


def test_health_reports_the_tripo_budget_only_when_set(tmp_path):
    base = dict(mode='live', registration_code='test-only-invitation-123456')
    with TestClient(create_app(Settings(data_dir=tmp_path / 'a', tripo_credit_budget=2000, **base), worker_enabled=False), base_url='https://testserver') as client:
        assert client.get('/health').json()['tripo_budget'] == {'used': 0, 'total': 2000}
    with TestClient(create_app(Settings(data_dir=tmp_path / 'b', **base), worker_enabled=False), base_url='https://testserver') as client:
        assert 'tripo_budget' not in client.get('/health').json()
