import json
import sqlite3

from server import admin_cli
from server.tests.test_api import world, account, mutation


def db(tmp_path):
    conn = sqlite3.connect(tmp_path / 'world.sqlite3', isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def test_demo_prep_resets_the_story_tops_up_and_copies_spare_pieces(world, tmp_path, capsys):
    app, c, now = world
    judge = account(c, 'judge01')
    account(c, 'showcase')
    data = str(tmp_path)
    with db(tmp_path) as conn:
        maker = conn.execute("SELECT id FROM users WHERE username='showcase'").fetchone()['id']
        # The showcase account's lamp: an interaction program and a shape that must come along.
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) VALUES ('lamp-00000001',?,?,'starter','달빛 스탠드 조명',1)", (maker, maker))
        conn.execute("INSERT INTO object_interactions(object_id,spec,compiled,version,updated) VALUES ('lamp-00000001','{\"light\":1}','{}',3,1)")
        conn.execute("INSERT INTO object_shape(object_id,width,depth,height,updated) VALUES ('lamp-00000001',80,80,120,1)")
    # The judge already walked the story to 모카 in a rehearsal.
    for action in ('read_letter', 'accept'):
        assert c.post('/v1/story/step', headers=judge, json=mutation(action=action)).status_code == 200
    assert admin_cli.main(['demo', 'list', 'showcase', '--data-dir', data]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert '달빛 스탠드 조명' in [p['name'] for p in listed]
    assert admin_cli.main(['demo', 'prep', 'judge01', '--stars', '300', '--copy-from', 'showcase', '--pick', '조명', '--data-dir', data]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['story']['step'] == 'letter' and result['shards'] == 300 and result['copied'][0]['name'] == '달빛 스탠드 조명'
    me = c.get('/v1/me', headers=judge).json()
    assert me['shards'] == 300 and me['story']['step'] == 'letter'
    copy = next(o for o in me['objects'] if o['name'] == '달빛 스탠드 조명')
    assert copy['state'] == 'inventory' and copy['id'] != 'lamp-00000001'
    with db(tmp_path) as conn:
        row = conn.execute('SELECT creator_id,owner_id FROM objects WHERE id=?', (copy['id'],)).fetchone()
        assert row['creator_id'] == maker and row['owner_id'] != maker
        assert conn.execute('SELECT spec,version FROM object_interactions WHERE object_id=?', (copy['id'],)).fetchone()[:] == ('{"light":1}', 3)
        assert conn.execute('SELECT height FROM object_shape WHERE object_id=?', (copy['id'],)).fetchone()[0] == 120
        # The source keeps its lamp; the top-up is one ledger line and never lowers a balance.
        assert conn.execute("SELECT owner_id FROM objects WHERE id='lamp-00000001'").fetchone()[0] == maker
        assert [r[0] for r in conn.execute("SELECT amount FROM ledger WHERE reason='demo_topup'")] == [result['topped_up']] and result['topped_up'] > 0
    assert admin_cli.main(['demo', 'prep', 'judge01', '--stars', '100', '--data-dir', data]) == 0
    again = json.loads(capsys.readouterr().out)
    assert again['topped_up'] == 0 and again['shards'] == 300 and again['story']['run'] == 3


def test_demo_prep_refuses_unknown_pieces_and_accounts_without_changes(world, tmp_path, capsys):
    app, c, now = world
    account(c, 'judge02')
    account(c, 'showcase2')
    data = str(tmp_path)
    assert admin_cli.main(['demo', 'prep', 'judge02', '--stars', '50', '--copy-from', 'showcase2', '--pick', '없는물건', '--data-dir', data]) == 1
    assert 'no piece matches' in capsys.readouterr().out
    with db(tmp_path) as conn:
        assert conn.execute("SELECT count(*) FROM ledger WHERE reason='demo_topup'").fetchone()[0] == 0
    assert admin_cli.main(['demo', 'prep', 'nobody', '--data-dir', data]) == 1
    assert admin_cli.main(['demo', 'prep', 'judge02', '--stars', '20000', '--data-dir', data]) == 1
