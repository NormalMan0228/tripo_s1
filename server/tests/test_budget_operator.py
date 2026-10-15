"""Operator reconciliation and reporting must not erase paid liabilities."""
import json

from server import llm_budget, tripo_budget
from server.admin_cli import main
from server.app import create_app
from server.config import Settings
from server.usage_report import budget_safety_report


NOW = 2_000_000_000.0


def world(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), clock=lambda: NOW, worker_enabled=False)
    return app, app.state.db, app.state.settings


def player(conn, name='operator_test'):
    conn.execute('INSERT INTO users(id,username,password_hash,created) VALUES (?,?,?,?)',
                 (name, name, 'unused-test-hash', NOW))
    return name


def reserve(conn, settings, owner, job='job', credits=10):
    return tripo_budget.reserve_attempt(conn, settings.limits_for({'is_tester': 0}),
                                       job, owner, 'concept', 'whole', credits, 0, NOW)


def test_release_requires_evidence_and_never_erases_a_reported_charge(tmp_path, capsys):
    app, db, settings = world(tmp_path)
    with db.transaction() as conn:
        owner = player(conn)
        unknown = reserve(conn, settings, owner)
        charged = reserve(conn, settings, owner, 'charged')
        tripo_budget.record_task(conn, charged, 'failed-provider-task', NOW)
        tripo_budget.record_result(conn, charged, {'status': 'failed', 'credits_consumed': 10}, NOW)
    args = ['--data-dir', str(tmp_path)]
    assert main(['tripo-reservations', 'release', unknown, *args]) == 1
    assert main(['tripo-reservations', 'release', unknown, '--confirmed-no-charge', *args]) == 1
    evidence = ['--confirmed-no-charge', '--reason', 'Provider support case 123: no charge']
    assert main(['tripo-reservations', 'release', charged, *evidence, *args]) == 1
    assert main(['tripo-reservations', 'release', 'missing', *evidence, *args]) == 1
    capsys.readouterr()
    assert main(['tripo-reservations', 'list', '--state', 'unknown', *args]) == 0
    assert [row['attempt_id'] for row in json.loads(capsys.readouterr().out)] == [unknown]
    assert main(['tripo-reservations', 'release', unknown, *evidence, *args]) == 0
    released = json.loads(capsys.readouterr().out)['attempt']
    assert released['state'] == 'released' and released['released_at']
    assert released['release_reason'] == evidence[-1]
    assert main(['tripo-reservations', 'release', unknown, *evidence, *args]) == 0
    with db.read() as conn:
        assert tripo_budget.committed_credits(conn) == 10
        assert conn.execute('SELECT count(*) FROM tripo_attempts').fetchone()[0] == 2
    db.close()


def test_usage_breakdown_top_ten_and_aggregate_privacy(tmp_path, monkeypatch, capsys):
    app, db, settings = world(tmp_path)
    with db.transaction() as conn:
        for index in range(1, 13):
            owner = player(conn, 'account_%02d' % index)
            attempt = reserve(conn, settings, owner, 'job-%d' % index, index * 5)
            tripo_budget.record_task(conn, attempt, 'task-%d' % index, NOW)
            tripo_budget.record_result(conn, attempt, {'status': 'failed' if index % 2 else 'success',
                                                       'credits_consumed': index * 5}, NOW)
            for call in range(index):
                conn.execute('INSERT INTO llm_call_reservations VALUES (?,?,?,?,?,?,?,?)',
                             ('llm-%d-%d' % (index, call), owner, 'craft_design', 'reference',
                              'openai', 'test-model', 'unknown', NOW))
        reserve(conn, settings, 'account_01', 'unknown', 7)
        pending = reserve(conn, settings, 'account_02', 'pending', 9)
        tripo_budget.record_task(conn, pending, 'pending-task', NOW)
        tripo_budget.hold_build(conn, settings.limits_for({'is_tester': 0}),
                               'job-3', 'account_03', 11, NOW)
        conn.execute('INSERT INTO llm_call_reservations VALUES (?,?,?,?,?,?,?,?)',
                     ('yesterday', 'account_01', 'craft_design', 'reference', 'openai', 'model',
                      'responded', NOW - 86400))
    monkeypatch.setattr('server.admin_cli.time.time', lambda: NOW)
    assert main(['budget-usage', '--data-dir', str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['tripo']['charged'] == 390
    assert report['tripo']['unknown'] == 7
    assert report['tripo']['reserved'] == 9
    assert report['tripo']['unsubmitted'] == 11
    assert report['tripo']['committed'] == 417
    assert report['llm']['calls_today'] == 78
    for key in ('top_10_tripo_accounts', 'top_10_llm_accounts_today'):
        assert len(report[key]) == 10
        assert report[key][0]['username'] == 'account_12'
    with db.read() as conn:
        aggregate = budget_safety_report(conn, NOW)
    assert 'account_' not in json.dumps(aggregate)
    assert 'top_10_tripo_accounts' not in aggregate
    monitor = app.state.usage_report.report(NOW)
    assert monitor['tripo_credits']['total'] == monitor['tripo_credits']['today'] == 390
    assert monitor['limits']['llm_account_daily_calls'] == 20
    assert monitor['limits']['llm_server_daily_calls'] == 1000
    encoded = json.dumps(monitor)
    assert all('account_%02d' % index not in encoded for index in range(1, 13))
    db.close()


def test_account_deletion_retains_new_and_legacy_costs_and_llm_counts(tmp_path, capsys):
    data = tmp_path / 'data'
    app, db, settings = world(data)
    with db.transaction() as conn:
        owner = player(conn)
        attempt = reserve(conn, settings, owner)
        tripo_budget.record_task(conn, attempt, 'provider-task', NOW)
        tripo_budget.record_result(conn, attempt, {'status': 'failed', 'credits_consumed': 10}, NOW)
        conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,parts,provenance,created,updated) '
                     'VALUES (?,?,?,?,?,?,?,?,?)', ('old-job', owner, '{}', 'failed', 20,
                     json.dumps({'whole': {'task': 'old-task', 'credits_consumed': 7}}),
                     json.dumps({'estimated_tripo_credits': 7}), NOW - 2 * 86400, NOW - 2 * 86400))
    llm_budget.reserve(db, settings, lambda: NOW, owner, 'craft_design', 'reference', 'openai', 'model')
    assert main(['delete-accounts', owner, '--yes', '--data-dir', str(data),
                 '--backups', str(tmp_path / 'backups')]) == 0
    with db.read() as conn:
        assert conn.execute('SELECT count(*) FROM users').fetchone()[0] == 0
        report = budget_safety_report(conn, NOW, include_accounts=True)
        assert report['tripo']['committed'] == 17
        assert report['llm']['calls_today'] == 1
        assert report['top_10_tripo_accounts'][0]['deleted'] is True
        assert report['top_10_tripo_accounts'][0]['username'] is None
    monitor = app.state.usage_report.report(NOW)
    assert monitor['tripo_credits']['total'] == 17
    assert monitor['tripo_credits']['today'] == 10
    db.close()
