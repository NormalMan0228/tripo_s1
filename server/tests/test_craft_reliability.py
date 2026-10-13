"""Crafts never hang: two-letter names, a craft window wording of its own, a deadline on every Tripo
part, held (unknown) submissions that stop nobody, the steps and progress the window shows, and the
craft under way in /v1/me so the village follows it again after a relaunch."""
import asyncio
import sqlite3
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.asset_assembly import fixture_glb
from server.operations import refund_studio_not_submitted
from server.provider import ProviderError
from server.tests.test_studio import mutation, account


class SlowProvider:
    """Tripo that accepts tasks and then keeps them running (or unreachable) until told otherwise."""
    def __init__(self):
        self.calls = []
        self.status = 'running'
        self.progress = 40
        self.unreachable = False
        self.uncertain = False
    async def balance(self): return 10000
    async def request(self, method, path, payload):
        self.calls.append(path)
        if self.uncertain: raise ProviderError('upstream_unreachable', uncertain=True)
        return {'task_id': 'task-%d' % len(self.calls)}
    async def task(self, task):
        if self.unreachable: raise ProviderError('upstream_unreachable')
        if self.status != 'success': return {'status': self.status, 'progress': self.progress}
        return {'status': 'success', 'credits_consumed': 10, 'output': {'model_url': 'private-test-model'}}
    async def download(self, url, allow_textures=False): return fixture_glb('box', allow_textures)


def paid(tmp_path, provider, now):
    settings = Settings(data_dir=tmp_path, paid_enabled=True, tripo_key='private-test-key', daily_generation_limit=100,
                        studio_credit_rate=.1, studio_part_deadline=600)
    app = create_app(settings, clock=lambda: now[0], provider=provider, worker_enabled=False)
    return app, TestClient(app)


def run(app, job, times=1):
    for _ in range(times): asyncio.run(app.state.studio.process(job))


def started(app, c, headers, prompt='stool'):
    """A confirmed Tripo craft whose part is now generating."""
    job = c.post('/v1/studio/jobs', headers=headers, json=mutation(prompt=prompt, geometry='tripo', motion='static')).json()['id']
    run(app, job)
    assert c.post('/v1/studio/jobs/' + job + '/confirm', headers=headers, json=mutation()).status_code == 200
    run(app, job)
    return job


def test_two_letter_names_and_craft_wording(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, daily_generation_limit=100), worker_enabled=False)
    with TestClient(app) as c:
        a = account(c, 'alice')
        assert c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='의자', motion='static')).status_code == 200
        short = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='의'))
        assert short.status_code == 422 and short.json()['detail'] == 'invalid_craft_request'
        # Every other form keeps its own code (the login card words it).
        login = c.post('/v1/auth/register', json={'username': 'x', 'password': 'Studio-test-password'})
        assert login.status_code == 422 and login.json()['detail'] == 'invalid_request'


def test_a_stuck_tripo_part_fails_at_its_deadline_and_refunds(tmp_path):
    now = [1_000_000.0]; provider = SlowProvider(); app, client = paid(tmp_path, provider, now)
    with client as c:
        a = account(c, 'alice'); b = account(c, 'bob')
        shards = c.get('/v1/me', headers=a).json()['shards']
        job = started(app, c, a)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'building' and value['stage'] == 'mesh' and value['progress'] is None
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'building' and value['progress'] == 0.4
        assert c.get('/v1/me', headers=a).json()['pending_craft'] == {'id': job, 'state': 'building'}
        # Meanwhile only one craft uses Tripo.
        assert c.post('/v1/studio/jobs', headers=b, json=mutation(prompt='lamp', geometry='tripo', motion='static')).json()['detail'] == 'provider_busy'
        now[0] += 599; run(app, job)
        assert c.get('/v1/studio/jobs/' + job, headers=a).json()['state'] == 'building'
        now[0] += 2; run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'failed' and value['error'] == 'generation_timeout' and value['stage'] == 'failed'
        assert c.get('/v1/me', headers=a).json()['shards'] == shards and c.get('/v1/me', headers=a).json()['pending_craft'] is None
        # Never submitted again, and Tripo is free for the next craft.
        run(app, job, 3)
        assert provider.calls == ['/generation/text-to-model']
        assert c.post('/v1/studio/jobs', headers=b, json=mutation(prompt='lamp', geometry='tripo', motion='static')).status_code == 200


def test_an_unreachable_tripo_waits_then_fails_at_the_deadline(tmp_path):
    now = [1_000_000.0]; provider = SlowProvider(); app, client = paid(tmp_path, provider, now)
    with client as c:
        a = account(c, 'alice')
        shards = c.get('/v1/me', headers=a).json()['shards']
        job = started(app, c, a)
        provider.unreachable = True
        now[0] += 300; run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'building' and value['error'] == 'upstream_unreachable'
        # Tripo answers again in time: the same task finishes the craft.
        provider.unreachable = False; provider.status = 'success'
        run(app, job)
        assert c.get('/v1/studio/jobs/' + job, headers=a).json()['state'] == 'ready'
        provider.unreachable = True; provider.status = 'running'
        second = started(app, c, a, 'table')
        now[0] += 601; run(app, second)
        value = c.get('/v1/studio/jobs/' + second, headers=a).json()
        assert value['state'] == 'failed' and value['error'] == 'generation_timeout'
        assert len(provider.calls) == 2
        # Only the finished craft was paid for.
        assert c.get('/v1/me', headers=a).json()['shards'] == shards - 20


def test_parts_submitted_before_deadlines_start_counting_on_upgrade(tmp_path):
    now = [1_000_000.0]; provider = SlowProvider(); app, client = paid(tmp_path, provider, now)
    with client as c:
        a = account(c, 'alice')
        job = started(app, c, a)
        with app.state.db.transaction() as conn:
            conn.execute("UPDATE studio_jobs SET parts=json_remove(parts,'$.whole.submitted') WHERE id=?", (job,))
        now[0] += 5000; run(app, job)
        assert c.get('/v1/studio/jobs/' + job, headers=a).json()['state'] == 'building'
        now[0] += 601; run(app, job)
        assert c.get('/v1/studio/jobs/' + job, headers=a).json()['error'] == 'generation_timeout'


def test_a_held_craft_stops_nobody_and_keeps_the_operator_refund(tmp_path):
    now = [1_000_000.0]; provider = SlowProvider(); app, client = paid(tmp_path, provider, now)
    with client as c:
        a = account(c, 'alice'); b = account(c, 'bob')
        provider.uncertain = True
        held = started(app, c, a)
        value = c.get('/v1/studio/jobs/' + held, headers=a).json()
        assert value['state'] == 'unknown' and value['stage'] == 'unknown'
        assert c.get('/v1/me', headers=a).json()['pending_craft'] is None
        provider.uncertain = False; provider.status = 'success'
        # Other players craft (Tripo is not held by it) ...
        other = started(app, c, b, 'lamp'); run(app, other)
        assert c.get('/v1/studio/jobs/' + other, headers=b).json()['state'] == 'ready'
        # ... and so does its owner, while the held craft keeps its starseeds for the operator.
        mine = started(app, c, a, 'table'); run(app, mine)
        assert c.get('/v1/studio/jobs/' + mine, headers=a).json()['state'] == 'ready'
        assert c.get('/v1/studio/jobs/' + held, headers=a).json()['state'] == 'unknown'
        # The held request still counts toward the account's Tripo requests until an operator clears it.
        from server.asset_studio import tripo_requests
        with app.state.db.transaction() as conn:
            user = conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
            assert tripo_requests(conn, user) == 2
        before = c.get('/v1/me', headers=a).json()['shards']
        assert refund_studio_not_submitted(app.state.db, held, 'case-held-1', verified=True)['amount'] == 20
        assert c.get('/v1/me', headers=a).json()['shards'] == before + 20


def test_only_one_live_craft_per_player_even_with_a_held_one(tmp_path):
    now = [1_000_000.0]; provider = SlowProvider(); app, client = paid(tmp_path, provider, now)
    with client as c:
        a = account(c, 'alice')
        provider.uncertain = True
        started(app, c, a)
        provider.uncertain = False
        assert c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='table', geometry='tripo', motion='static')).status_code == 200
        assert c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='chair', geometry='tripo', motion='static')).json()['detail'] == 'generation_pending'


def test_old_worlds_get_the_new_pending_index(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, daily_generation_limit=100), worker_enabled=False)
    with app.state.db.transaction() as conn:
        conn.execute('DROP INDEX studio_pending')
        conn.execute("CREATE UNIQUE INDEX studio_pending ON studio_jobs(owner_id) WHERE state NOT IN ('ready','failed','cancelled')")
    create_app(Settings(data_dir=tmp_path, daily_generation_limit=100), worker_enabled=False)
    with sqlite3.connect(tmp_path / 'world.sqlite3') as db:
        assert "'unknown'" in db.execute("SELECT sql FROM sqlite_master WHERE name='studio_pending'").fetchone()[0]


def test_the_window_steps_follow_the_craft(tmp_path):
    from server.tests.test_concept import Provider, world, craft
    provider = Provider(); app, client = world(tmp_path, provider)
    with client as c:
        a = account(c, 'alice'); b = account(c, 'bob')
        # A photo craft has no picture step.
        photo = c.post('/v1/studio/jobs', headers=b, json=craft(image=PNG)).json()['id']
        assert c.get('/v1/studio/jobs/' + photo, headers=b).json()['stages'] == ['design', 'mesh', 'done']
        assert c.post('/v1/studio/jobs/' + photo + '/cancel', headers=b, json=mutation()).status_code == 200
        job = c.post('/v1/studio/jobs', headers=a, json=craft()).json()['id']
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['stage'] == 'design' and value['stages'] == ['design', 'concept', 'mesh', 'done']
        asyncio.run(app.state.studio.process(job))
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['stage'] == 'confirm' and value['stages'] == ['design', 'concept', 'mesh', 'done']
        c.post('/v1/studio/jobs/' + job + '/redraw', headers=a, json=mutation())
        assert c.get('/v1/studio/jobs/' + job, headers=a).json()['stage'] == 'concept'


def _png():
    import base64, io
    from PIL import Image
    raw = io.BytesIO(); Image.new('RGB', (32, 32), 'orange').save(raw, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode()


PNG = _png()
