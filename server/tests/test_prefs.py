import uuid
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings


def test_settings_follow_the_account(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    with TestClient(app) as client:
        token = client.post('/v1/auth/register', json={'username': 'prefs_one', 'password': 'Test-password-123', 'invitation': ''}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        assert client.get('/v1/prefs', headers=headers).json() == {'prefs': {}, 'updated': None}
        prefs = {'audio': {'master': 55, 'mute_all': False}, 'input': {'interact': [71, 0]},
                 'game': {'language': 'en'}, 'shadow_folk': {'mira_walk': '2026-10-08'}}
        saved = client.post('/v1/prefs', headers=headers, json={'request_id': str(uuid.uuid4()), 'prefs': prefs})
        assert saved.status_code == 200, saved.json()
        assert client.get('/v1/prefs', headers=headers).json()['prefs'] == prefs
        # A second login (a fresh install elsewhere) reads the same settings.
        again = client.post('/v1/auth/login', json={'username': 'prefs_one', 'password': 'Test-password-123'}).json()['token']
        assert client.get('/v1/prefs', headers={'Authorization': 'Bearer ' + again}).json()['prefs'] == prefs
        # Oversized or nested payloads are refused.
        big = client.post('/v1/prefs', headers=headers, json={'request_id': str(uuid.uuid4()), 'prefs': {'a': {'k': 'x' * 500}}})
        assert big.status_code == 422
        nested = client.post('/v1/prefs', headers=headers, json={'request_id': str(uuid.uuid4()), 'prefs': {'a': {'k': {'deep': 1}}}})
        assert nested.status_code == 422
        assert client.get('/v1/prefs').status_code == 401
