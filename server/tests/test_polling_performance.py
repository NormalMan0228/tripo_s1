"""Polling regressions: upgrades, writer contention, batching and crop freshness."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import uuid

import pytest

from server import homestead
from server.app import create_app
from server.config import Settings
from server.database import Database
from server.migrations import POLLING_INDEXES, migrate_polling_indexes
from server.tests.social_world import World


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    try:
        yield w
    finally:
        w.close()
        w.app.state.db.close()


def test_polling_index_upgrade_preserves_data_and_is_idempotent(world):
    w = world
    player = w.player('upgrade')
    with w.app.state.db.transaction() as conn:
        for name, _ in POLLING_INDEXES:
            conn.execute('DROP INDEX ' + name)
        conn.execute("DELETE FROM metadata WHERE key='migration:0118_polling_indexes'")
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) VALUES (?,?,?,'starter','kept',0)",
                     ('upgrade-object', player.id, player.id))
    upgraded = create_app(Settings(data_dir=w.settings.data_dir), worker_enabled=False)
    try:
        with upgraded.state.db.read() as conn:
            assert conn.execute("SELECT name FROM objects WHERE id='upgrade-object'").fetchone()[0] == 'kept'
            assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
            expected = {name for name, _ in POLLING_INDEXES}
            indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            assert expected <= indexes
            checks = (
                ("SELECT id FROM objects WHERE owner_id=? AND state='placed' ORDER BY id", (player.id,), 'objects_owner_state_id'),
                ('SELECT user_id FROM mp_visits WHERE host_id=? AND expires>?', (player.id, 0), 'mp_visits_host_expires'),
                ('SELECT user_id FROM mp_presence WHERE host_id=? AND scene=? AND seen>?',
                 (player.id, 'village', 0), 'mp_presence_host_scene_seen'))
            for sql, args, index in checks:
                plan = ' '.join(r[3] for r in conn.execute('EXPLAIN QUERY PLAN ' + sql, args))
                assert 'SEARCH' in plan and index in plan
        migrate_polling_indexes(upgraded.state.db)
        with upgraded.state.db.read() as conn:
            assert conn.execute("SELECT count(*) FROM metadata WHERE key='migration:0118_polling_indexes'").fetchone()[0] == 1
    finally:
        upgraded.state.db.close()


def test_failed_index_migration_rolls_back_marker_and_indexes(tmp_path):
    # Base schema deliberately has no multiplayer tables yet.
    import sqlite3
    db = Database(tmp_path / 'incomplete.sqlite3', 'demo')
    try:
        with pytest.raises(sqlite3.OperationalError):
            migrate_polling_indexes(db)
        with db.read() as conn:
            assert not conn.execute("SELECT 1 FROM metadata WHERE key='migration:0118_polling_indexes'").fetchone()
            assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='objects_owner_state_id'").fetchone()
    finally:
        db.close()


@pytest.mark.parametrize('kind', ['studio', 'legacy'])
def test_job_poll_reads_committed_state_without_waiting_for_writer(world, kind):
    w = world
    player, other = w.players('crafter', 'outsider')
    from server import economy
    with w.app.state.db.transaction() as conn:
        economy.change_shards(conn, player.id, 100, 'demo_welcome', player.id, w.now[0])
    path = '/v1/studio/jobs' if kind == 'studio' else '/v1/generations'
    job = w.call(player, path, prompt='wooden chair')['id']
    route = path + '/' + job
    w.get(player, route)  # Pin the account timezone before the contention test.
    with ThreadPoolExecutor(max_workers=1) as pool:
        with w.app.state.db.transaction() as conn:
            table = 'studio_jobs' if kind == 'studio' else 'jobs'
            conn.execute(f"UPDATE {table} SET state='failed' WHERE id=?", (job,))
            # The uncommitted writer must not block this WAL reader or expose its state.
            response = pool.submit(w.get, player, route).result(timeout=2)
            assert response['state'] == 'queued'
    assert w.get(player, route)['state'] == 'failed'
    w.get(other, route, status=404)
    assert w.client.get(route).status_code == 401
    w.client.post('/v1/auth/logout', headers=player.headers)
    w.get(player, route, status=401)


@pytest.mark.parametrize('raw_kind', ['missing', 'legacy', 'current'])
def test_crop_projection_matches_existing_public_contract(raw_kind):
    state = homestead.initial()
    state['plots'][0].update(crop='turnip', watered=True, ready_at=150)
    state['plots'][1].update(crop='carrot', watered=False)
    state['fishing'] = {'catch': 'private', 'size': 100, 'bite_at': 90, 'ends_at': 110}
    if raw_kind == 'legacy':
        for plot in state['plots']:
            plot.pop('x')
            plot.pop('z')
    raw = None if raw_kind == 'missing' else json.dumps(state)
    for now in (100, 150, 200):
        full = homestead.public(json.loads(raw) if raw else homestead.initial(), now)
        projected = homestead.public_crops(raw, now)
        assert projected == {k: full[k] for k in ('version', 'plots', 'server_time')}
        projected['plots'][0]['x'] = 999
        assert homestead.public_crops(raw, now)['plots'][0]['x'] != 999


def test_crop_cache_is_bounded_and_does_not_retain_large_saves():
    homestead._cached_crop_source.cache_clear()
    state = homestead.initial()
    for version in range(140):
        state['version'] = version
        homestead.public_crops(json.dumps(state), 100)
    assert homestead._cached_crop_source.cache_info().currsize == 128
    state['private_history'] = 'x' * 65537
    before = homestead._cached_crop_source.cache_info()
    assert set(homestead.public_crops(json.dumps(state), 100)) == {'version', 'plots', 'server_time'}
    assert homestead._cached_crop_source.cache_info() == before
    homestead._cached_crop_source.cache_clear()


def test_presence_crop_cache_follows_writes_rollback_clock_and_host(world):
    w = world
    host, guest = w.players('gardener', 'visitor')
    w.visit(guest, host)
    state = homestead.initial()
    state['plots'][0].update(crop='turnip', watered=True, ready_at=w.now[0] + 5)

    def save(conn, owner, value):
        conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state',
                     (owner, json.dumps(value)))

    with w.app.state.db.transaction() as conn:
        save(conn, host.id, state)
    first = w.presence(guest)['village']['crops']
    assert first['plots'][0]['remaining'] == 5
    w.tick(6)
    assert w.presence(guest)['village']['crops']['plots'][0]['ready']
    # Content changes must invalidate even if a restore retains the version number.
    changed = copy.deepcopy(state)
    changed['plots'][0]['crop'] = 'carrot'
    with w.app.state.db.transaction() as conn:
        save(conn, host.id, changed)
    assert w.presence(guest)['village']['crops']['plots'][0]['crop'] == 'carrot'
    with pytest.raises(RuntimeError):
        with w.app.state.db.transaction() as conn:
            save(conn, host.id, state)
            raise RuntimeError('rollback')
    assert w.presence(guest)['village']['crops']['plots'][0]['crop'] == 'carrot'
    w.call(guest, '/v1/social/home')
    assert 'crop' not in w.presence(guest)['village']['crops']['plots'][0]
    assert w.presence(host, scene='home')['space']['crops'] is None


def test_party_batched_presence_preserves_missing_and_expired_members(world):
    from server import coop
    w = world
    a, b, c = w.players('party_a', 'party_b', 'party_c')
    party = str(uuid.uuid4())
    with w.app.state.db.transaction() as conn:
        conn.execute('INSERT INTO mp_parties VALUES (?,?,NULL,?)', (party, a.id, w.now[0]))
        for i, p in enumerate((a, b, c)):
            conn.execute('INSERT INTO mp_members VALUES (?,?,?)', (p.id, party, w.now[0] + i))
        for p, seen in ((a, w.now[0]), (b, w.now[0] - coop.PRESENCE_SECONDS)):
            conn.execute("INSERT INTO mp_presence(user_id,host_id,scene,x,z,yaw,seen) VALUES (?,?,'village',0,0,0,?)",
                         (p.id, p.id, seen))
    members = w.get(a, '/v1/social')['party']['members']
    assert [m['id'] for m in members] == [a.id, b.id, c.id]
    assert [m['online'] for m in members] == [True, False, False]
    assert all(set(m) == {'id', 'username', 'joined', 'online'} for m in members)


def test_presence_connection_restores_full_durability_after_failure(tmp_path):
    db = Database(tmp_path / 'durability.sqlite3', 'demo')
    try:
        for fail_after_commit in (False, True):
            with pytest.raises(RuntimeError):
                with db.write_then_read(durable=False) as phase:
                    assert phase.conn.execute('PRAGMA synchronous').fetchone()[0] == 1
                    if fail_after_commit:
                        phase.commit()
                    raise RuntimeError('poll failed')
            with db.read() as conn:
                assert not conn.in_transaction
                assert conn.execute('PRAGMA synchronous').fetchone()[0] == 2
                assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
                assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == 15000
    finally:
        db.close()
