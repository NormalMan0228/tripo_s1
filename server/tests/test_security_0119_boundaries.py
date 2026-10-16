"""Offline 0.11.9 audit: upgrade copies, visit revocation and private replies."""
import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from server import app as app_module, homestead, multiplayer
from server.asset_studio import SCHEMA as STUDIO_SCHEMA
from server.config import Settings
from server.database import Database
from server.tests.social_world import World
from server.tests.test_avatar8 import OLD_SCHEMA


def test_0118_memory_copy_upgrades_and_restarts_without_losing_saved_data(tmp_path, monkeypatch):
    # An independent source and SQLite backup, never an operator's real database.
    source = sqlite3.connect(':memory:', isolation_level=None)
    memory_uri = 'file:audit0119_' + uuid.uuid4().hex + '?mode=memory&cache=shared'
    anchor = sqlite3.connect(memory_uri, uri=True, isolation_level=None)
    source.executescript(OLD_SCHEMA + multiplayer.SCHEMA + STUDIO_SCHEMA)
    raw_avatar = json.dumps({'character': 'ranger', 'coat': '#aAbBcC'}, indent=2)
    source.execute("INSERT INTO users VALUES ('old-user','old_walker','unused',77,42)")
    source.execute('INSERT INTO profiles VALUES (?,?,?)', ('old-user', raw_avatar, 8))
    life = homestead.initial()
    life.update(coins=93, version=7, bag={'apple': 3, 'turnip_seed': 2})
    raw_life = json.dumps(life)
    source.execute('INSERT INTO homesteads VALUES (?,?)', ('old-user', raw_life))
    source.execute("INSERT INTO ledger VALUES ('old-ledger','old-user',77,'reward','old-run',42)")
    source.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) "
                   "VALUES ('old-chair','old-user','old-user','starter','kept',42)")
    source.execute("INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated) "
                   "VALUES ('old-craft','old-user','{}','ready',25,42,42)")
    source.execute("INSERT INTO mp_presence(user_id,host_id,scene,x,z,yaw,seen) "
                   "VALUES ('old-user','old-user','village',1,2,0,42)")
    source.execute("INSERT INTO mp_messages(room,user_id,text,created) "
                   "VALUES ('village:old-user','old-user','old message',42)")
    source.backup(anchor)

    class MemoryDatabase(Database):
        def connect(self):
            conn = sqlite3.connect(memory_uri, uri=True, isolation_level=None, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            return conn

    monkeypatch.setattr(app_module, 'Database', MemoryDatabase)
    try:
        for _ in range(2):
            app = app_module.create_app(Settings(data_dir=tmp_path), clock=lambda: 1_000_000., worker_enabled=False)
            try:
                with TestClient(app) as client:
                    assert client.get('/health').status_code == 200
                with app.state.db.read() as conn:
                    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
                    assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                    profile = conn.execute('SELECT * FROM profiles').fetchone()
                    assert json.loads(profile['avatar'])['character'] == 'f1'
                    assert json.loads(profile['avatar'])['coat'] == '#aAbBcC'
                    assert profile['version'] == 8 and profile['needs_character_select'] == 1
                    assert tuple(conn.execute('SELECT avatar,version FROM profile_avatar8_backup').fetchone()) == (raw_avatar, 8)
                    user = conn.execute('SELECT * FROM users').fetchone()
                    assert user['shards'] == 77 and user['role'] == 'player' and user['is_tester'] == 0
                    assert user['display_name'] == user['display_key'] == 'old_walker'
                    assert conn.execute('SELECT state FROM homesteads').fetchone()[0] == raw_life
                    assert conn.execute('SELECT amount FROM ledger').fetchone()[0] == 77
                    assert conn.execute("SELECT name FROM objects WHERE id='old-chair'").fetchone()[0] == 'kept'
                    assert conn.execute('SELECT state FROM studio_jobs').fetchone()[0] == 'ready'
                    assert conn.execute('SELECT text FROM mp_messages').fetchone()[0] == 'old message'
                    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    assert {'tripo_attempts', 'tripo_job_holds', 'llm_call_reservations', 'quest_board_progress',
                            'npc_letter_events', 'village_residents', 'leaf_ledger'} <= tables
            finally:
                app.state.db.close()
        # The pre-upgrade source is unchanged.
        assert [r[1] for r in source.execute('PRAGMA table_info(profiles)')] == ['user_id', 'avatar', 'version']
        assert source.execute('SELECT avatar FROM profiles').fetchone()[0] == raw_avatar
    finally:
        anchor.close()
        source.close()


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    try:
        yield w
    finally:
        w.close()
        w.app.state.db.close()


@pytest.mark.parametrize('revocation', ['lock', 'eject', 'owner_away', 'expired', 'block'])
def test_every_home_asset_route_rechecks_access_without_renewing_visits(world, revocation):
    w = world
    host, guest = w.players('host', 'guest')
    item = str(uuid.uuid4())
    with w.app.state.db.transaction() as conn:
        asset = conn.execute("SELECT * FROM assets WHERE id='starter'").fetchone()
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,state,created) "
                     "VALUES (?,?,?,'starter','private chair','placed',0)", (item, host.id, host.id))
        conn.execute("INSERT INTO furniture_locations VALUES (?,'home')", (item,))
        manifest = {'schema': 1, 'plan': {'parts': [{'id': 'whole', 'file': asset['relative_path'], 'sha256': asset['digest']}]},
                    'program': {'version': 1, 'state': {}, 'functions': {}, 'events': {}}}
        conn.execute('INSERT INTO studio_assets VALUES (?,?)', ('starter', json.dumps(manifest)))
        conn.execute("INSERT INTO studio_runtime(object_id,state) VALUES (?,'{}')", (item,))
    w.visit(guest, host)
    w.presence(host, scene='home')
    w.presence(guest, scene='home')
    prefix = '/v1/social/village/objects/' + item + '/'
    for suffix in ('model', 'assembly', 'parts/whole'):
        assert w.client.get(prefix + suffix, headers=guest.headers).status_code == 200
    with w.app.state.db.read() as conn:
        expires = conn.execute('SELECT expires FROM mp_visits WHERE user_id=?', (guest.id,)).fetchone()[0]
    w.tick(1)
    assert w.client.get(prefix + 'model', headers=guest.headers).status_code == 200
    with w.app.state.db.read() as conn:
        assert conn.execute('SELECT expires FROM mp_visits WHERE user_id=?', (guest.id,)).fetchone()[0] == expires
    if revocation == 'lock':
        w.call(host, '/v1/home/lock', locked=True)
        # Locking preserves access for a guest already inside, until they leave.
        assert w.client.get(prefix + 'model', headers=guest.headers).status_code == 200
        w.presence(guest, scene='village')
    elif revocation == 'eject':
        w.call(host, '/v1/home/eject', user_id=guest.id)
    elif revocation == 'owner_away':
        w.presence(host, scene='village')
        w.tick(11)
        w.presence(host, scene='village')
    elif revocation == 'expired':
        w.tick(multiplayer.VISIT_SECONDS + 1)
    else:
        w.call(host, '/v1/social/blocks', user_id=guest.id)
    for suffix in ('model', 'assembly', 'parts/whole', 'paint'):
        response = w.client.get(prefix + suffix, headers=guest.headers)
        assert response.status_code == 404, (revocation, suffix, response.text)
        assert response.json()['detail'] == 'object_not_found'
    assert w.client.get(prefix + 'model', headers=host.headers).status_code == 200


def test_presence_contains_public_crops_and_looks_but_no_host_wallet_or_inventory(world):
    w = world
    host, guest = w.players('host', 'guest')
    state = homestead.initial()
    state.update(coins=987654, bag={'private_bag_marker': 37})
    with w.app.state.db.transaction() as conn:
        conn.execute('INSERT INTO homesteads VALUES (?,?)', (host.id, json.dumps(state)))
        conn.execute('UPDATE users SET shards=54321 WHERE id=?', (host.id,))
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) "
                     "VALUES ('secret-inventory',?,?,'starter','private inventory',0)", (host.id, host.id))
    w.visit(guest, host)
    reply = w.presence(guest, since=0)
    encoded = json.dumps(reply)
    assert reply['shards'] == 0
    assert all(secret not in encoded for secret in ('987654', '54321', 'private_bag_marker', 'secret-inventory', 'password_hash', 'token_hash'))
    assert all('shards' not in player and 'coins' not in player for player in reply['space']['players'])


def test_player_cannot_use_admin_or_tester_endpoints(world):
    w = world
    player = w.player('ordinary')
    assert w.refused(player, '/v1/admin/grant', 403, shards=1, coins=1) == 'admin_only'
    assert w.get(player, '/v1/admin/reports', 403)['detail'] == 'admin_only'
    assert w.refused(player, '/v1/admin/chat/mute', 403, user_id=player.id, minutes=1) == 'admin_only'
    assert w.refused(player, '/v1/admin/chat/delete', 403, message_ids=[1]) == 'admin_only'
    assert w.refused(player, '/v1/admin/reports/1/close', 403) == 'admin_only'
    assert w.client.post('/v1/dev/time_override', headers=player.headers, json={'time_override': 'night'}).status_code == 403
    assert w.client.get('/v1/ops/usage', headers=player.headers).status_code == 404
