import asyncio
import httpx
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.asset_assembly import fixture_glb
from server.provider import TripoProvider, key_fingerprint
from server.tests.test_studio import mutation, account


def tripo_accounts(balances, seen):
    """A mock Tripo API whose answers depend on which key (account) asks."""
    tasks = {}
    def handle(request):
        key = request.headers.get('authorization', '').removeprefix('Bearer ')
        if request.url.host.endswith('.tripo3d.ai') and request.url.path == '/models/chair.glb':
            assert 'authorization' not in request.headers  # asset downloads never carry a key
            return httpx.Response(200, content=fixture_glb('box'))
        seen.append((request.method, request.url.path, key))
        if key not in balances:
            return httpx.Response(401, json={'code': 1})
        if request.url.path.endswith('/account/balance'):
            return httpx.Response(200, json={'code': 0, 'data': {'balance': balances[key]}})
        if request.url.path.endswith('/generation/text-to-model'):
            task = 'task-' + str(len(tasks) + 1)
            tasks[task] = key
            return httpx.Response(200, json={'code': 0, 'data': {'task_id': task}})
        if '/tasks/' in request.url.path:
            task = request.url.path.rsplit('/', 1)[1]
            if tasks.get(task) != key:
                return httpx.Response(404, json={'code': 2})  # a task only exists for its own account
            return httpx.Response(200, json={'code': 0, 'data': {'status': 'success', 'credits_consumed': 10,
                                  'output': {'model_url': 'https://assets.tripo3d.ai/models/chair.glb'}}})
        return httpx.Response(404, json={'code': 3})
    return httpx.MockTransport(handle)


def test_crafts_use_the_first_key_with_credit_and_keep_it_for_the_task(tmp_path):
    seen = []
    balances = {'poor-key': 50, 'rich-key': 5000}
    settings = Settings(data_dir=tmp_path, paid_enabled=True, tripo_key='poor-key', tripo_keys=('poor-key', 'broken-key', 'rich-key'),
                        daily_generation_limit=100, studio_credit_rate=.1)
    provider = TripoProvider(settings, tripo_accounts(balances, seen))
    app = create_app(settings, provider=provider, worker_enabled=False)
    with TestClient(app) as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='wooden chair', geometry='tripo', motion='static',
                                                                mesh_model='v3.1-20260211')).json()['id']
        asyncio.run(app.state.studio.process(job))
        assert c.post('/v1/studio/jobs/' + job + '/confirm', headers=a, json=mutation()).status_code == 200
        for _ in range(4):
            asyncio.run(app.state.studio.process(job))
        status = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert status['state'] == 'ready', status
        # The poor key was skipped, the broken key did not stop the search, the rich key did the work.
        submissions = [key for method, path, key in seen if path.endswith('/generation/text-to-model')]
        polls = [key for method, path, key in seen if '/tasks/' in path]
        assert submissions == ['rich-key'] and polls and set(polls) == {'rich-key'}
        assert 'rich-key' not in str(status)
        with app.state.db.transaction() as conn:
            parts = conn.execute('SELECT parts FROM studio_jobs WHERE id=?', (job,)).fetchone()[0]
        assert key_fingerprint('rich-key') in parts and 'rich-key"' not in parts
    assert c.get('/health').json()['tripo_keys'] == 3


def test_no_key_with_enough_credit_refunds_the_craft(tmp_path):
    seen = []
    settings = Settings(data_dir=tmp_path, paid_enabled=True, tripo_key='a-key', tripo_keys=('a-key', 'b-key'),
                        daily_generation_limit=100, studio_credit_rate=.1)
    provider = TripoProvider(settings, tripo_accounts({'a-key': 30, 'b-key': 40}, seen))
    app = create_app(settings, provider=provider, worker_enabled=False)
    with TestClient(app) as c:
        a = account(c, 'bob')
        before = c.get('/v1/me', headers=a).json()['shards']
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='stool', geometry='tripo', motion='static',
                                                                mesh_model='v3.1-20260211')).json()['id']
        asyncio.run(app.state.studio.process(job))
        c.post('/v1/studio/jobs/' + job + '/confirm', headers=a, json=mutation())
        asyncio.run(app.state.studio.process(job))
        status = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert status['state'] == 'failed' and status['error'] == 'insufficient_provider_credit'
        assert c.get('/v1/me', headers=a).json()['shards'] == before
        assert not [p for m, p, k in seen if p.endswith('/generation/text-to-model')]
