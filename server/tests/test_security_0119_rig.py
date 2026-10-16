"""Regression checks for the 0.11.9 rig budget and feature-gate audit."""
import asyncio
import json

import pytest

from server import tripo_budget
from server.app import create_app
from server.config import Settings
from server.provider import ProviderError
from server.tests.test_rigging import finish, mutation, queue, start, world  # noqa: F401


def legacy_parts(*, rig_bill=25):
    rig = {'task': 'old-rig'}
    if rig_bill is not None:
        rig['credits_consumed'] = rig_bill
    return {'whole': {'task': 'old-mesh', 'credits_consumed': 10, 'rig': rig,
                      'anims': {clip: {'task': 'old-' + clip, 'credits_consumed': 10}
                                for clip in ('idle', 'walk')}}}


def add_legacy_job(conn, state, parts, quote=55):
    conn.execute('INSERT INTO users(id,username,password_hash,created) VALUES (?,?,?,0)',
                 ('old-owner', 'oldowner', 'unused-test-password-hash'))
    conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated,parts,provenance) '
                 'VALUES (?,?,?,?,0,0,0,?,?)',
                 ('old-rig-job', 'old-owner', '{"geometry":"tripo","animate":true}', state,
                  json.dumps(parts), json.dumps({'estimated_tripo_credits': quote})))


@pytest.mark.parametrize('state', ['ready', 'failed', 'unknown'])
def test_legacy_rig_and_both_clips_count_before_and_after_adoption(tmp_path, state):
    app = create_app(Settings(data_dir=tmp_path, tripo_credit_budget=60), worker_enabled=False)
    limits = app.state.settings.limits_for(None)
    with app.state.db.transaction() as conn:
        add_legacy_job(conn, state, legacy_parts())
        assert tripo_budget.committed_credits(conn) == 55
        with pytest.raises(ProviderError, match='tripo_budget_exhausted'):
            tripo_budget.reserve_attempt(conn, limits, 'new-job', 'new-owner', 'mesh', 'whole', 10, 0, 1)
        tripo_budget.manage_job(conn, 'old-rig-job', 'old-owner', False, 2)
        assert tripo_budget.committed_credits(conn) == 55
        row = conn.execute("SELECT * FROM tripo_attempts WHERE job_id='old-rig-job'").fetchone()
        assert row['actual_credits'] == 55 and row['reserved_credits'] == 55
        with pytest.raises(ValueError, match='charged_attempt_cannot_be_released'):
            tripo_budget.release_attempt(conn, row['attempt_id'], 'Mesh bill was already recorded', 3)


@pytest.mark.parametrize('state', ['ready', 'failed'])
def test_legacy_missing_rig_bill_keeps_the_full_quote(tmp_path, state):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    with app.state.db.transaction() as conn:
        add_legacy_job(conn, state, legacy_parts(rig_bill=None))
        assert tripo_budget.committed_credits(conn) == 55
        tripo_budget.manage_job(conn, 'old-rig-job', 'old-owner', False, 1)
        assert tripo_budget.committed_credits(conn) == 55
        row = conn.execute('SELECT * FROM tripo_attempts').fetchone()
        assert row['actual_credits'] == 30 and row['reserved_credits'] == 55


def test_legacy_tester_rig_overrun_survives_adoption(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    with app.state.db.transaction() as conn:
        add_legacy_job(conn, 'failed', legacy_parts(rig_bill=180))
        conn.execute("INSERT INTO tester_credit_spend VALUES ('old-rig-job:build',55)")
        assert tripo_budget.committed_credits(conn) == 210
        assert tripo_budget.committed_credits(conn, tester=True) == 210
        # Current account roles are not historical billing evidence: only the
        # legacy tester reference assigns old craft liabilities to this pool.
        conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated,parts) '
                     "VALUES ('normal-rig-job','old-owner','{}','ready',0,0,0,?)", (json.dumps(legacy_parts()),))
        assert tripo_budget.committed_credits(conn) == 265
        assert tripo_budget.committed_credits(conn, tester=True) == 210
        limits = Settings(mode='live', tester_credit_budget=210).limits_for({'is_tester': 1})
        with pytest.raises(ProviderError, match='tester_credit_budget_exhausted'):
            tripo_budget.reserve_attempt(conn, limits, 'new-job', 'new-owner', 'mesh', 'whole', 1, 0, 1)
        tripo_budget.manage_job(conn, 'old-rig-job', 'old-owner', False, 1)
        assert tripo_budget.committed_credits(conn) == 265
        assert tripo_budget.committed_credits(conn, tester=True) == 210
        row = conn.execute('SELECT * FROM tripo_attempts').fetchone()
        assert row['actual_credits'] == 210 and row['reserved_credits'] == 210


@pytest.mark.parametrize('stage', ['rig', 'retarget'])
def test_uncertain_rig_submission_keeps_tester_and_server_holds_after_restart(world, stage):
    app, client, headers, calls, faults = world
    with app.state.db.transaction() as conn:
        conn.execute('UPDATE users SET is_tester=1')
    faults['uncertain'] = stage
    job, _ = start(world)
    status, _ = finish(world, job)
    assert status['state'] == 'unknown'
    count = len(calls)
    restarted = create_app(app.state.settings, provider=app.state.studio.provider, worker_enabled=False)
    asyncio.run(restarted.state.studio.process(job))
    assert len(calls) == count
    with restarted.state.db.read() as conn:
        assert tripo_budget.committed_credits(conn) == 55
        assert tripo_budget.committed_credits(conn, tester=True) == 55
        unknown = conn.execute("SELECT * FROM tripo_attempts WHERE state='unknown'").fetchall()
        assert len(unknown) == 1 and unknown[0]['task_id'] is None
        assert unknown[0]['reserved_credits'] == (25 if stage == 'rig' else 10)
    assert client.get('/v1/studio/jobs/' + job, headers=headers).json()['state'] == 'unknown'


def test_disabled_rig_flag_rejects_already_quoted_confirmation(world):
    app, client, headers, calls, _ = world
    job = queue(world).json()['id']
    asyncio.run(app.state.studio.process(job))
    before = client.get('/v1/me', headers=headers).json()['shards']
    app.state.settings.rig_anim_enabled = False
    response = client.post('/v1/studio/jobs/' + job + '/confirm', headers=headers, json=mutation())
    assert response.status_code == 503 and response.json()['detail'] == 'rigging_disabled'
    assert client.get('/v1/studio/jobs/' + job, headers=headers).json()['state'] == 'awaiting_confirmation'
    assert client.get('/v1/me', headers=headers).json()['shards'] == before
    assert calls == []
