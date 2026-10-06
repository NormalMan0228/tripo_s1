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
