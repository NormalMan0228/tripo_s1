"""Provider substitutes only: every request boundary must preserve its liability."""
import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server import tripo_budget
from server.app import create_app
from server.asset_assembly import demo_design
from server.config import Settings
from server.provider import ProviderError
from server.tests.test_account_limits import register, run, confirm, world as legacy_world
from server.tests.test_concept import Provider as ConceptProvider, craft, world
from server.tests.test_studio import FurnitureProvider, account, mutation


@pytest.mark.parametrize('cap,server_cap,error', [
    (200,0,'craft_over_trial_limit'), (0,200,'tripo_budget_exhausted'),
    (200,200,'craft_over_trial_limit'),
])
def test_normal_overbill_blocks_second_part_and_refunds(tmp_path, cap, server_cap, error):
    class Provider(FurnitureProvider):
        async def task(self, task):
            result = await super().task(task)
            result['credits_consumed'] = 150
            return result
    class Designer:
        async def generate(self, *args):
            return (*demo_design('chest'), {'provider':'mock'})
    provider = Provider()
    settings = Settings(data_dir=tmp_path, mode='live', registration_code='test-only-invitation-123456',
                        paid_enabled=True, tripo_key='test-only-key', studio_llm='openai', llm_key='test-only-llm-key',
                        studio_credit_rate=.1, max_credits_per_craft=cap, tripo_credit_budget=server_cap)
    app = create_app(settings, provider=provider, designer=Designer(), worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as client:
        headers = register(client, app, 'alice')
        before = client.get('/v1/me', headers=headers).json()['shards']
        reply = client.post('/v1/studio/jobs', headers=headers, json=mutation(prompt='wooden chest',
                            geometry='tripo', designer='llm', model='gpt-6-luna', effort='high'))
        assert reply.status_code == 200, reply.text
        job = reply.json()['id']; run(app, job)
        assert confirm(client, headers, job).status_code == 200
        run(app, job, 4)
        status = client.get('/v1/studio/jobs/'+job, headers=headers).json()
        assert status['state'] == 'failed' and status['error'] == error
        assert len(provider.calls) == 1
        assert client.get('/v1/me', headers=headers).json()['shards'] == before
        with app.state.db.read() as conn:
            rows = conn.execute('SELECT * FROM tripo_attempts').fetchall()
            assert len(rows) == 1 and rows[0]['actual_credits'] == 150
            assert rows[0]['task_id'] == 'task-1'
            assert tripo_budget.committed_credits(conn) == 150


def test_five_successes_and_five_failed_charges_are_ten_attempts(tmp_path):
    class Provider(ConceptProvider):
        async def task(self, task):
            result = await super().task(task)
            result['credits_consumed'] = 5
            return result
    provider = Provider(); app, client = world(tmp_path, provider)
    with client as c:
        headers = account(c, 'alice')
        with app.state.db.transaction() as conn:
            conn.execute('UPDATE users SET is_tester=1')
        for _ in range(5):
            provider.fail_concept = False
            job = c.post('/v1/studio/jobs', headers=headers, json=craft()).json()['id']; run(app, job)
            assert c.post('/v1/studio/jobs/'+job+'/redraw', headers=headers, json=mutation()).status_code == 200
            provider.fail_concept = True; run(app, job)
            assert c.post('/v1/studio/jobs/'+job+'/cancel', headers=headers, json=mutation()).status_code == 200
        with app.state.db.read() as conn:
            rows = conn.execute('SELECT * FROM tripo_attempts').fetchall()
            assert len(rows) == 10
            assert len({row['task_id'] for row in rows}) == 10
            assert all(row['actual_credits'] == 5 for row in rows)
            assert tripo_budget.committed_credits(conn) == 50
            assert tripo_budget.committed_credits(conn, tester=True) == 50


def test_failed_redraw_preserves_approved_picture_task(tmp_path):
    provider = ConceptProvider(); app, client = world(tmp_path, provider)
    with client as c:
        headers = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=headers, json=craft()).json()['id']; run(app, job)
        assert c.post('/v1/studio/jobs/'+job+'/redraw', headers=headers, json=mutation()).status_code == 200
        provider.fail_concept = True; run(app, job)
        assert confirm(c, headers, job).status_code == 200
        run(app, job, 3)
        assert provider.calls[-1][1]['input'] == 'concept-1'
        with app.state.db.read() as conn:
            assert {row[0] for row in conn.execute("SELECT task_id FROM tripo_attempts WHERE kind='concept'")} == {'concept-1','concept-2'}


def test_crash_between_post_and_task_save_keeps_unknown_after_restart(tmp_path):
    class ProcessCrash(BaseException):
        pass
    class Provider(ConceptProvider):
        async def request(self, *args):
            result = await super().request(*args)
            # Simulate acceptance followed by process death before response handling.
            raise ProcessCrash(result['task_id'])
    provider = Provider(); app, client = world(tmp_path, provider)
    with client as c:
        headers = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=headers, json=craft()).json()['id']
        with pytest.raises(ProcessCrash):
            run(app, job)
        with app.state.db.read() as conn:
            row = conn.execute('SELECT * FROM tripo_attempts').fetchone()
            assert row['state'] == 'unknown' and row['task_id'] is None
            assert tripo_budget.committed_credits(conn) == 5
    restarted, client = world(tmp_path, provider)
    with client as c:
        assert c.get('/v1/studio/jobs/'+job, headers=headers).json()['state'] == 'failed'
        with restarted.state.db.read() as conn:
            assert tripo_budget.committed_credits(conn) == 5
            assert conn.execute('SELECT state FROM tripo_attempts').fetchone()[0] == 'unknown'
    assert len(provider.calls) == 1


def test_atomic_attempt_includes_remaining_estimates_and_release_requires_evidence(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, tripo_credit_budget=300), worker_enabled=False)
    limits = app.state.settings.limits_for(None)
    def reserve(job):
        try:
            with app.state.db.transaction() as conn:
                return tripo_budget.reserve_attempt(conn, limits, job, job, 'mesh', 'body', 100, 100, 1)
        except ProviderError as error:
            assert error.code == 'tripo_budget_exhausted'
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(reserve, ('one','two')))
    assert sum(item is not None for item in result) == 1
    attempt = next(item for item in result if item)
    with app.state.db.transaction() as conn:
        assert tripo_budget.committed_credits(conn) == 200
        job = conn.execute('SELECT job_id FROM tripo_attempts').fetchone()[0]
        tripo_budget.clear_hold(conn, job)
        tripo_budget.record_result(conn, attempt, {'status':'failed','credits_consumed':0}, 2)
        assert tripo_budget.committed_credits(conn) == 100
        with pytest.raises(ValueError, match='release_reason_required'):
            tripo_budget.release_attempt(conn, attempt, '', 3)
        assert tripo_budget.release_attempt(conn, attempt, 'Provider confirmed no charge', 3)
        assert tripo_budget.committed_credits(conn) == 0
        assert not tripo_budget.release_attempt(conn, attempt, 'Provider confirmed no charge', 4)
        # A late positive bill must still count, even after an operator reconciliation.
        tripo_budget.record_result(conn, attempt, {'credits_consumed':150}, 5)
        assert tripo_budget.committed_credits(conn) == 150
        with pytest.raises(ValueError, match='charged_attempt_cannot_be_released'):
            tripo_budget.release_attempt(conn, attempt, 'old evidence', 6)


def test_refine_overbill_blocks_mesh_post(tmp_path):
    class Provider(ConceptProvider):
        async def upload_image(self, image):
            return 'test-file'
        async def task(self, task):
            return {'status':'success', 'credits_consumed':150}
    provider = Provider()
    app, client = world(tmp_path, provider, mode='live', registration_code='test-only-invitation-123456',
                        max_credits_per_craft=200, llm_key='test-only-key', studio_credit_rate=.1)
    raw = io.BytesIO(); Image.new('RGB',(32,32),'white').save(raw,'PNG')
    image = 'data:image/png;base64,'+base64.b64encode(raw.getvalue()).decode()
    with client as c:
        headers = register(c, app, 'alice')
        reply = c.post('/v1/studio/jobs', headers=headers, json=mutation(prompt='wooden chest', geometry='tripo',
                       designer='llm', motion='static', model='gpt-6-luna', effort='high', image=image, image_mode='refine'))
        assert reply.status_code == 200, reply.text
        job = reply.json()['id']; run(app, job)
        assert confirm(c, headers, job).status_code == 200
        run(app, job, 3)
        status = c.get('/v1/studio/jobs/'+job, headers=headers).json()
        assert status['error'] == 'craft_over_trial_limit' and status['state'] == 'failed'
        assert [call[0] for call in provider.calls] == ['/generation/image-to-image']
        with app.state.db.read() as conn:
            row = conn.execute('SELECT * FROM tripo_attempts').fetchone()
            assert row['kind'] == 'refine' and row['actual_credits'] == 150
            assert tripo_budget.committed_credits(conn) == 150


@pytest.mark.parametrize('kind', ['mesh','refine'])
def test_build_crash_leaves_one_durable_attempt_and_cannot_resubmit(tmp_path, kind):
    class ProcessCrash(BaseException):
        pass
    class Provider(FurnitureProvider):
        async def upload_image(self, image):
            return 'test-file'
        async def request(self, *args):
            with app.state.db.read() as conn:
                row = conn.execute('SELECT * FROM tripo_attempts').fetchone()
                assert row['kind'] == kind and row['state'] == 'unknown'
                stored = conn.execute('SELECT state,parts FROM studio_jobs').fetchone()
                assert stored['state'] == 'submitting'
                assert any(part.get(kind+'_attempt') == row['attempt_id'] for part in json.loads(stored['parts']).values())
            await super().request(*args)
            raise ProcessCrash()
    class Designer:
        async def generate(self, *args):
            return (*demo_design('chest'), {'provider':'mock'})
    provider = Provider()
    settings = Settings(data_dir=tmp_path, paid_enabled=True, tripo_key='test-only-key', studio_credit_rate=.1, studio_llm='openai')
    app = create_app(settings, provider=provider, designer=Designer(), worker_enabled=False)
    with TestClient(app) as c:
        headers = account(c, 'alice')
        fields = {}
        if kind == 'refine':
            raw = io.BytesIO(); Image.new('RGB',(32,32),'white').save(raw,'PNG')
            fields = dict(designer='llm', motion='static', image_mode='refine',
                          image='data:image/png;base64,'+base64.b64encode(raw.getvalue()).decode())
        reply = c.post('/v1/studio/jobs', headers=headers, json=mutation(prompt='wooden chest', geometry='tripo', **fields))
        job = reply.json()['id']; run(app, job)
        assert confirm(c, headers, job).status_code == 200
        with pytest.raises(ProcessCrash):
            run(app, job)
    restarted = create_app(settings, provider=provider, worker_enabled=False)
    run(restarted, job)
    with restarted.state.db.read() as conn:
        assert conn.execute('SELECT state FROM studio_jobs').fetchone()[0] == 'unknown'
        row = conn.execute('SELECT * FROM tripo_attempts').fetchone()
        assert row['state'] == 'unknown' and row['reserved_credits'] == (100 if kind == 'mesh' else 5)
        assert tripo_budget.committed_credits(conn) == (100 if kind == 'mesh' else 5)
    assert len(provider.calls) == 1


def test_legacy_adoption_keeps_known_charge_and_cannot_release_it(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    with TestClient(app) as c:
        headers = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=headers, json=mutation(prompt='chair')).json()['id']
        with app.state.db.transaction() as conn:
            conn.execute('DELETE FROM tripo_job_holds WHERE job_id=?', (job,))
            conn.execute("UPDATE studio_jobs SET state='failed',parts=?,provenance=? WHERE id=?",
                         (json.dumps({'body':{'task':'old-task','credits_consumed':7}}), '{}', job))
            owner = conn.execute('SELECT owner_id FROM studio_jobs WHERE id=?',(job,)).fetchone()[0]
            tripo_budget.manage_job(conn,job,owner,False,1)
            row = conn.execute('SELECT * FROM tripo_attempts').fetchone()
            assert row['actual_credits'] == 7 and tripo_budget.committed_credits(conn) == 7
            with pytest.raises(ValueError, match='charged_attempt_cannot_be_released'):
                tripo_budget.release_attempt(conn,row['attempt_id'],'old evidence',2)


def test_old_tester_reservations_count_for_server_without_duplicate_studio_costs(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    with TestClient(app) as c:
        headers = account(c, 'alice')
        with app.state.db.transaction() as conn:
            owner = conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
            for job, parts in (
                ('old-build', {'whole':{'task':'mesh-task','credits_consumed':100}}),
                ('old-concepts', {'whole':{'concept_task':'concept-success','concept_credits_consumed':5}}),
                ('old-overrun', {'whole':{'task':'overrun-task','credits_consumed':150}}),
            ):
                conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated,parts) '
                             'VALUES (?,?,?,\'failed\',0,0,0,?)',
                             (job,owner,'{"geometry":"tripo"}',json.dumps(parts)))
            conn.executemany('INSERT INTO tester_credit_spend VALUES (?,?)', [
                ('old-build:build',100),
                ('old-concepts:concept:success',5), ('old-concepts:concept:failed',5),
                ('old-overrun:build',100), ('deleted-job:legacy',20), ('orphan-reference',7),
            ])
            # Build is counted once, the failed picture remains, the orphaned
            # reservations remain, and the larger actual overrun also remains.
            assert tripo_budget.committed_credits(conn) == 287
            assert tripo_budget.committed_credits(conn, tester=True) == 237
            assert tripo_budget.committed_credits(conn, 'old-build') == 187
            assert tripo_budget.committed_credits(conn, 'old-concepts') == 277
            assert tripo_budget.committed_credits(conn, 'deleted-job') == 267
            assert tripo_budget.committed_credits(conn, 'old-concepts', tester=True) == 227

            # Adoption moves the old tester rows to the durable attempt ledger
            # without changing either total or forgetting their tester origin.
            tripo_budget.manage_job(conn, 'old-concepts', owner, False, 1)
            assert tripo_budget.committed_credits(conn) == 287
            assert tripo_budget.committed_credits(conn, tester=True) == 237
            assert tripo_budget.committed_credits(conn, 'old-concepts') == 277
            assert tripo_budget.committed_credits(conn, 'old-concepts', tester=True) == 227
            conn.execute("DELETE FROM studio_jobs WHERE id='old-concepts'")
            assert tripo_budget.committed_credits(conn) == 287
            assert tripo_budget.committed_credits(conn, tester=True) == 237


def test_old_deleted_tester_reservation_blocks_new_normal_account_submission(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, tripo_credit_budget=100), worker_enabled=False)
    limits = app.state.settings.limits_for(None)
    with app.state.db.transaction() as conn:
        conn.execute("INSERT INTO tester_credit_spend VALUES ('deleted-job:legacy',100)")
        with pytest.raises(ProviderError) as denied:
            tripo_budget.reserve_attempt(conn, limits, 'new-job', 'new-owner', 'mesh', 'whole', 1, 0, 1)
        assert denied.value.code == 'tripo_budget_exhausted'
        assert conn.execute('SELECT count(*) FROM tripo_attempts').fetchone()[0] == 0
        assert tripo_budget.committed_credits(conn) == 100


@pytest.mark.parametrize('submitted', [False, True])
def test_legacy_restart_clears_only_unsubmitted_hold(tmp_path, submitted):
    app, client, provider = legacy_world(tmp_path)
    with client as c:
        headers = register(c, app, 'alice')
        reply = c.post('/v1/generations', headers=headers, json=mutation(prompt='wooden chair'))
        assert reply.status_code == 200, reply.text
        job = reply.json()['id']
        with app.state.db.transaction() as conn:
            user = conn.execute("SELECT * FROM users WHERE username='alice'").fetchone()
            conn.execute("UPDATE jobs SET state='submitting' WHERE id=?", (job,))
            if submitted:
                tripo_budget.reserve_attempt(conn, app.state.settings.limits_for(user), job, user['id'],
                                             'legacy', '', 100, 0, 1)
            assert tripo_budget.committed_credits(conn) == 100
    restarted = create_app(app.state.settings, provider=provider, worker_enabled=False)
    with restarted.state.db.read() as conn:
        assert conn.execute('SELECT state FROM jobs WHERE id=?', (job,)).fetchone()[0] == 'unknown'
        assert conn.execute('SELECT credits FROM tripo_job_holds WHERE job_id=?', (job,)).fetchone()[0] == 0
        assert tripo_budget.committed_credits(conn) == (100 if submitted else 0)
        assert conn.execute('SELECT count(*) FROM tripo_attempts').fetchone()[0] == int(submitted)
    assert not provider.calls
