import asyncio
import sqlite3
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.admin_cli import main
from server.tests.test_studio import mutation, account


def test_delete_accounts_dry_run_then_backup_and_remove_only_matches(tmp_path, capsys):
    data = tmp_path / 'data'
    app = create_app(Settings(data_dir=data, daily_generation_limit=100), worker_enabled=False)
    with TestClient(app) as c:
        owners = {name: account(c, name) for name in ('qa_a1b2c3', 'qa_d4e5f6', 'real_player')}
        for name, headers in owners.items():
            job = c.post('/v1/studio/jobs', headers=headers, json=mutation(prompt='wooden chest', motion='static')).json()['id']
            asyncio.run(app.state.studio.process(job))
            assert c.get('/v1/studio/jobs/' + job, headers=headers).json()['state'] == 'ready'
    database = data / 'world.sqlite3'
    def count(sql, *args):
        with sqlite3.connect(database) as conn:
            return conn.execute(sql, args).fetchone()[0]
    files_before = len(list((data / 'assets').glob('*')))
    assert main(['delete-accounts', '--pattern', '^qa_[0-9a-f]{6}$', '--data-dir', str(data), '--backups', str(tmp_path / 'backups')]) == 0
    out = capsys.readouterr().out
    assert 'qa_a1b2c3' in out and 'qa_d4e5f6' in out and 'real_player' not in out and 'Dry run' in out
    assert count('SELECT count(*) FROM users') == 3
    assert main(['delete-accounts', '--pattern', '^qa_[0-9a-f]{6}$', '--yes', '--data-dir', str(data), '--backups', str(tmp_path / 'backups')]) == 0
    assert list((tmp_path / 'backups').iterdir())  # a verified backup came first
    assert count('SELECT count(*) FROM users') == 1
    real = count("SELECT id FROM users WHERE username='real_player'")
    assert count('SELECT count(*) FROM objects WHERE owner_id!=?', real) == 0
    assert count('SELECT count(*) FROM objects WHERE owner_id=?', real) >= 2  # welcome chair + crafted chest
    assert count('SELECT count(*) FROM studio_jobs WHERE owner_id!=?', real) == 0
    assert count('SELECT count(*) FROM sessions WHERE user_id!=?', real) == 0
    assert len(list((data / 'assets').glob('*'))) == files_before - 2  # the two qa chests' model files
    # The remaining player still works.
    app = create_app(Settings(data_dir=data, daily_generation_limit=100), worker_enabled=False)
    with TestClient(app) as c:
        login = c.post('/v1/auth/login', json={'username': 'real_player', 'password': 'Studio-test-password'})
        assert login.status_code == 200


def test_delete_accounts_removes_social_rows_on_both_sides(tmp_path, capsys):
    from server.tests.social_world import World
    w = World(tmp_path / 'data')
    qa, real = w.players('qa_0a0b0c', 'real_one')
    w.befriend(qa, real)
    w.call(real, '/v1/social/blocks', user_id=qa.id)      # qa only appears as blocked_id
    w.call(qa, '/v1/friends/requests', username='real_one')
    w.call(real, '/v1/social/report', user_id=qa.id, reason='spam')
    w.close()
    data = tmp_path / 'data'
    assert main(['delete-accounts', 'qa_0a0b0c', '--yes', '--data-dir', str(data), '--backups', str(tmp_path / 'backups')]) == 0
    with sqlite3.connect(data / 'world.sqlite3') as conn:
        for table in ('social_blocks', 'social_friends', 'social_requests', 'social_reports'):
            assert conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0, table
        assert conn.execute("SELECT count(*) FROM users WHERE username='real_one'").fetchone()[0] == 1


def test_chat_and_report_moderation_commands(tmp_path, capsys):
    import json
    from server.tests.social_world import World
    w = World(tmp_path / 'data')
    alice, bravo = w.players('alice', 'bravo')
    w.visit(bravo, alice)
    line = w.say(bravo, 'rude words here', channel='local')
    w.say(bravo, 'hello', channel='local')
    w.call(alice, '/v1/social/report', user_id=bravo.id, message_id=line['id'], reason='abuse')
    args = ['--data-dir', str(tmp_path / 'data')]
    capsys.readouterr()
    assert main(['chat', 'list', '--username', 'bravo', '--grep', 'rude', *args]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [l['text'] for l in listed] == ['rude words here'] and listed[0]['channel'] == 'local'
    assert main(['chat', 'delete', str(line['id']), *args]) == 0
    assert json.loads(capsys.readouterr().out)['removed'] == 1
    assert 'removed' in w.presence(alice, since=0)['chat']
    assert main(['chat', 'mute', 'bravo', '15', *args]) == 0
    capsys.readouterr()
    w.tick(2)
    # The operator's mute runs on the wall clock, far after this test's clock: muted.
    assert w.say(bravo, 'still here?', 403)['detail'] == 'chat_muted'
    assert main(['chat', 'mute', 'bravo', '0', *args]) == 0
    assert w.say(bravo, 'back again')['ok']
    capsys.readouterr()
    assert main(['reports', 'list', *args]) == 0
    reports = json.loads(capsys.readouterr().out)
    assert reports[0]['reported'] == 'bravo' and reports[0]['message'] == 'rude words here'
    assert main(['reports', 'close', str(reports[0]['id']), *args]) == 0
    capsys.readouterr()
    assert main(['reports', 'list', *args]) == 0
    assert json.loads(capsys.readouterr().out) == []
    w.close()
