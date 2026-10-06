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
