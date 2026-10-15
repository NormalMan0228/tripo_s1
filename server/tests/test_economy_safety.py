import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from server import economy, homestead
from server.admin_cli import main
from server.tests.social_world import World


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


def stock(w, player, count=200):
    state = homestead.initial()
    state['bag']['turnip'] = count
    with w.db() as conn:
        conn.execute('INSERT INTO homesteads VALUES (?,?)', (player.id,json.dumps(state)))


def sell(w, player, quantity=15):
    state = w.get(player, '/v1/homestead')
    return w.call(player, '/v1/homestead', version=state['version'], action='sell', item='turnip', quantity=quantity)


def test_offset_cycling_cannot_reset_cap_and_restart_preserves_pin(world):
    w = world
    p = w.player('farmer')
    w.now[0] = 10*86400+12*3600
    p.headers['X-Villagen-UTC-Offset'] = '-720'
    stock(w,p)
    assert sell(w,p)['stars'] == 15
    for offset in (840,540,0,-720,840):
        p.headers['X-Villagen-UTC-Offset'] = str(offset)
        assert sell(w,p)['stars'] == 0
        assert w.get(p,'/v1/homestead')['sell_stars']['today'] == 15
    with w.db() as conn:
        assert conn.execute('SELECT daily_utc_offset FROM users WHERE id=?',(p.id,)).fetchone()[0] == -720
        assert economy.ledger_check(conn) == []
    # A new server instance uses the same durable pin, not the new device's header.
    other = World(w.settings.data_dir)
    try:
        other.now[0] = w.now[0]
        assert sell(other,p)['stars'] == 0
    finally:
        other.close()
    w.tick(86400)
    assert sell(w,p)['stars'] == 15
    p.headers['X-Villagen-UTC-Offset'] = '-720'
    assert sell(w,p)['stars'] == 0


def test_first_auth_requests_race_to_one_pin(world):
    w = world
    p = w.player('first_race')
    def query(offset):
        return w.client.get('/v1/homestead',headers={**p.headers,'X-Villagen-UTC-Offset':str(offset)}).status_code
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(query,(-720,840))) == [200,200]
    with w.db() as conn:
        assert conn.execute('SELECT daily_utc_offset FROM users WHERE id=?',(p.id,)).fetchone()[0] in (-720,840)


def test_helper_atomicity_validation_and_reconciliation(world):
    w = world
    p = w.player('ledger')
    with w.db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        economy.change_shards(conn,p.id,20,'test','one',w.now[0])
        with pytest.raises(sqlite3.IntegrityError):
            economy.change_shards(conn,p.id,5,'test','one',w.now[0])
        with pytest.raises(HTTPException,match='insufficient_shards'):
            economy.change_shards(conn,p.id,-21,'test','debit',w.now[0])
        for amount in (1.5,True,'3',2**63,-(2**63)-1):
            with pytest.raises(economy.EconomyRejected):
                economy.change_shards(conn,p.id,amount,'test','bad',w.now[0])
        with pytest.raises(economy.EconomyRejected,match='shard_balance_overflow'):
            economy.change_shards(conn,p.id,2**63-1,'test','overflow',w.now[0])
        assert economy.ledger_check(conn) == []
        assert conn.execute('SELECT shards FROM users WHERE id=?',(p.id,)).fetchone()[0] == 20
        conn.execute("CREATE TEMP TRIGGER refuse_balance BEFORE UPDATE OF shards ON users BEGIN SELECT RAISE(ABORT, 'balance_write_failed'); END")
        with pytest.raises(sqlite3.IntegrityError,match='balance_write_failed'):
            economy.change_shards(conn,p.id,5,'test','update_failure',w.now[0])
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 1
        assert economy.ledger_check(conn) == []
        conn.rollback()
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 0
        assert conn.execute('SELECT shards FROM users WHERE id=?',(p.id,)).fetchone()[0] == 0
        with pytest.raises(RuntimeError,match='currency_transaction_required'):
            economy.change_shards(conn,p.id,1,'test','no_transaction',w.now[0])


def test_admin_cap_rejection_survives_rollback(world,caplog):
    w = world
    p = w.player('operator',role='admin')
    for _ in range(2):
        w.call(p,'/v1/admin/grant',shards=100000)
    assert w.call(p,'/v1/admin/grant',429,shards=1,coins=100)['detail'] == 'admin_grant_limit'
    with w.db() as conn:
        assert conn.execute('SELECT shards FROM users WHERE id=?',(p.id,)).fetchone()[0] == 200000
        assert economy.ledger_check(conn) == []
        assert conn.execute("SELECT code FROM economy_flags WHERE user_id=?",(p.id,)).fetchone()[0] == 'admin_grant_limit'
        assert conn.execute("SELECT count(*) FROM security_events WHERE kind='economy_suspicious'").fetchone()[0] == 1
    assert 'economy_suspicious' in caplog.text
    assert w.get(p,'/v1/homestead')['coins'] == homestead.initial()['coins']


def test_sell_grants_enforce_ledger_cap_and_flag_boundary_bursts(world):
    w = world
    p = w.player('boundary')
    with w.db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for i in range(10):
            economy.change_shards(conn,p.id,1,'sell_reward',str(i),86400-5+i,sell_daily=15,offset=0)
        assert conn.execute('SELECT code FROM economy_flags WHERE user_id=?',(p.id,)).fetchone()[0] == 'boundary_sell_burst'
        with pytest.raises(economy.EconomyRejected,match='sell_reward_limit'):
            economy.change_shards(conn,p.id,11,'sell_reward','over',86405,sell_daily=15,offset=0)
        assert economy.ledger_check(conn) == []
        conn.commit()


def test_ledger_check_lists_and_flags_mismatch_and_negative_balance(world,capsys,caplog):
    w = world
    p = w.player('corrupt')
    with w.db() as conn:
        conn.execute('PRAGMA ignore_check_constraints=ON')
        conn.execute('UPDATE users SET shards=-1 WHERE id=?',(p.id,))
        conn.execute('BEGIN IMMEDIATE')
        with pytest.raises(economy.EconomyRejected,match='invalid_shard_balance'):
            economy.change_shards(conn,p.id,10,'test','one',w.now[0])
        conn.rollback()
    assert main(['ledger-check','--data-dir',str(w.settings.data_dir)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['mismatches'] == [{'user_id':p.id,'username':'corrupt','shards':-1,'ledger_sum':0}]
    assert result['flags'][0]['code'] == 'ledger_mismatch'
    assert 'ledger_mismatch' in caplog.text
    with w.db() as conn:
        conn.execute('UPDATE users SET shards=0 WHERE id=?',(p.id,))
    assert main(['ledger-check','--data-dir',str(w.settings.data_dir)]) == 0
    assert json.loads(capsys.readouterr().out)['mismatches'] == []


def test_corrupt_daily_counter_cannot_bypass_ledger_cap(world):
    w = world
    p = w.player('counter')
    stock(w, p)
    assert sell(w, p)['stars'] == 15
    with w.db() as conn:
        state = json.loads(conn.execute('SELECT state FROM homesteads WHERE user_id=?', (p.id,)).fetchone()[0])
        state['star_day'] = -1
        conn.execute('UPDATE homesteads SET state=? WHERE user_id=?', (json.dumps(state), p.id))
    response = w.call(p, '/v1/homestead', 429, version=state['version'], action='sell', item='turnip', quantity=1)
    assert response['detail'] == 'sell_reward_limit'
    with w.db() as conn:
        after = json.loads(conn.execute('SELECT state FROM homesteads WHERE user_id=?', (p.id,)).fetchone()[0])
        assert after == state
        assert conn.execute('SELECT code FROM economy_flags WHERE user_id=?', (p.id,)).fetchone()[0] == 'sell_reward_limit'
        assert economy.ledger_check(conn) == []


def test_negative_balance_rejection_is_flagged_after_http_rollback(world):
    w = world
    p = w.player('negative', role='admin')
    with w.db() as conn:
        conn.execute('PRAGMA ignore_check_constraints=ON')
        conn.execute('UPDATE users SET shards=-1 WHERE id=?', (p.id,))
    for _ in range(2):
        assert w.call(p, '/v1/admin/grant', 409, shards=1)['detail'] == 'invalid_shard_balance'
    with w.db() as conn:
        row = conn.execute('SELECT code,occurrences FROM economy_flags WHERE user_id=?', (p.id,)).fetchone()
        assert tuple(row) == ('invalid_shard_balance', 2)
        assert conn.execute('SELECT count(*) FROM ledger WHERE user_id=?', (p.id,)).fetchone()[0] == 0


def test_operator_grants_use_atomic_ledger_and_keep_reference_idempotency(world):
    from tools.grant_starseeds import grant
    w = world
    p = w.player('operator_target')
    database = w.settings.data_dir/'world.sqlite3'
    assert grant(database, p.name, 30, 'ticket-1')['balance'] == 30
    assert grant(database, p.name, 30, 'ticket-1')['already_applied']
    with pytest.raises(ValueError, match='grant_reference_conflict'):
        grant(database, p.name, 31, 'ticket-1')
    for bad in (True, 1.5, 0, 100001):
        with pytest.raises(ValueError, match='invalid_grant_request'):
            grant(database, p.name, bad, 'ticket-2')
    with w.db() as conn:
        assert economy.ledger_check(conn) == []
        assert conn.execute('SELECT count(*) FROM ledger WHERE user_id=?', (p.id,)).fetchone()[0] == 1


def test_ledger_check_missing_database_does_not_create_one(tmp_path, capsys):
    assert main(['ledger-check', '--data-dir', str(tmp_path)]) == 1
    assert 'No world database' in capsys.readouterr().out
    assert not (tmp_path/'world.sqlite3').exists()


@pytest.mark.parametrize('amount', [True, 1.0, '3', -1, 100001])
def test_admin_api_rejects_non_integer_or_out_of_range_grants(world, amount):
    w = world
    p = w.player('strict_admin', role='admin')
    w.call(p, '/v1/admin/grant', 422, shards=amount)
    with w.db() as conn:
        assert economy.ledger_check(conn) == []
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 0
