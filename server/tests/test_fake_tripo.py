import asyncio
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.asset_studio import tripo_credits_committed
from server.config import Settings
from server.fake_tripo import FAKE_KEY, transport
from server.provider import TripoProvider


def staging_settings(tmp_path, **changes):
    return Settings(data_dir=tmp_path, mode='live', paid_enabled=True, fake_tripo=True, environment='staging',
                    registration_code='test-only-invitation-123456', tripo_credit_budget=30, **changes)


def test_fake_tripo_crafts_the_whole_way_without_credits(tmp_path):
    settings = staging_settings(tmp_path)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        health = client.get('/health').json()
        assert health['tripo_fake'] is True and health['environment'] == 'staging' and health['studio_tripo_enabled']
        token = client.post('/v1/auth/register', json={'username': 'dev_user', 'password': 'Test-password-123',
                                                       'invitation': settings.registration_code}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        with app.state.db.transaction() as db:
            db.execute('UPDATE users SET shards=500')
        # Two crafts in a row: the fake bills 0 credits, so a 30-credit budget covers both (10 + 25).
        for material, concept in (('mesh', False), ('textured', True)):
            job = client.post('/v1/studio/jobs', headers=headers, json={
                'request_id': str(uuid.uuid4()), 'prompt': 'tiny mushroom stool', 'motion': 'static', 'material': material, 'concept': concept,
                'mesh_model': 'v3.1-20260211', 'designer': 'simple', 'geometry': 'tripo'})
            assert job.status_code == 200, job.json()
            job_id = job.json()['id']
            asyncio.run(app.state.studio.process(job_id))
            confirm = client.post('/v1/studio/jobs/' + job_id + '/confirm', headers=headers,
                                  json={'request_id': str(uuid.uuid4()), 'use_concept': concept})
            assert confirm.status_code == 200, confirm.json()
            for _ in range(4):
                asyncio.run(app.state.studio.process(job_id))
            status = client.get('/v1/studio/jobs/' + job_id, headers=headers).json()
            assert status['state'] == 'ready', status
            assert status['provenance']['tripo_credits_consumed'] == 0
            assert bool(status.get('concept')) == concept  # the picture step went through the fake too
        with app.state.db.transaction() as db:
            assert tripo_credits_committed(db) == 0


def test_fake_tripo_never_runs_with_a_real_key(tmp_path):
    with pytest.raises(ValueError, match='without real Tripo keys'):
        create_app(staging_settings(tmp_path, tripo_key='a-real-looking-key'), worker_enabled=False)
    settings = staging_settings(tmp_path)
    settings.validate()
    assert settings.tripo_keys == (FAKE_KEY,)


def test_fake_tasks_can_take_time_and_survive_a_restart(tmp_path):
    now = [1000.0]
    settings = staging_settings(tmp_path)
    settings.validate()
    provider = TripoProvider(settings, transport(10, clock=lambda: now[0]))

    async def run():
        task = (await provider.request('POST', '/generation/text-to-model', {'prompt': 'stool', 'texture': False}))['task_id']
        first = await provider.task(task)
        now[0] += 11
        # A new transport (a restarted server) still knows the task from its id.
        later = TripoProvider(settings, transport(10, clock=lambda: now[0]))
        done = await later.task(task)
        blob = await later.download(done['output']['model_url'])
        return first, done, blob
    first, done, blob = asyncio.run(run())
    assert first['status'] == 'running' and done['status'] == 'success' and done['credits_consumed'] == 0
    assert blob[:4] == b'glTF'
    # Only the fake key is answered; nothing here can reach the network.
    stranger = TripoProvider(Settings(data_dir=tmp_path, tripo_key='other'), transport())
    with pytest.raises(Exception):
        asyncio.run(stranger.balance())
    assert isinstance(transport(), httpx.MockTransport)
