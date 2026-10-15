"""Reward amounts must survive the HTTP boundary without coercion or partial writes."""
import json
import uuid

import pytest

from server import economy, homestead
from server.tests.social_world import World


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


BAD_AMOUNTS = (True, False, 1.0, 1.5, '1', -1, 2**100, float('nan'), float('inf'), -float('inf'))


def post_amount(w, player, path, **body):
    # Raw JSON also exercises non-finite values that httpx's json= encoder refuses.
    return w.client.post(path, headers={**player.headers, 'Content-Type': 'application/json'},
                         content=json.dumps({'request_id': str(uuid.uuid4()), **body}))


def save_life(w, player, state):
    with w.db() as conn:
        conn.execute('INSERT INTO homesteads VALUES (?,?)', (player.id, json.dumps(state)))


def test_buy_and_sell_reject_coerced_or_unbounded_quantities(world):
    w = world
    p = w.player('amount_farmer')
    state = homestead.initial()
    state['bag']['turnip'] = 5
    save_life(w, p, state)
    before = w.get(p, '/v1/homestead')
    for action, item in (('buy', 'bait'), ('sell', 'turnip')):
        for quantity in (*BAD_AMOUNTS, 0, 21):
            response = post_amount(w, p, '/v1/homestead', action=action, item=item,
                                   version=0, quantity=quantity)
            assert response.status_code == 422, (quantity, response.text)
    assert w.get(p, '/v1/homestead') == before
    with w.db() as conn:
        assert conn.execute('SELECT count(*) FROM requests').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 0


def test_admin_leaf_grants_reject_coerced_or_unbounded_amounts(world):
    w = world
    p = w.player('amount_admin', role='admin')
    for coins in (*BAD_AMOUNTS, 100001):
        response = post_amount(w, p, '/v1/admin/grant', coins=coins, shards=1)
        assert response.status_code == 422, (coins, response.text)
    assert w.get(p, '/v1/homestead')['coins'] == 12
    with w.db() as conn:
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM homesteads').fetchone()[0] == 0


def test_market_price_must_be_an_integer_before_any_listing_is_created(world):
    w = world
    p = w.player('amount_seller')
    object_id = str(uuid.uuid4())
    with w.db() as conn:
        conn.execute('INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) VALUES (?,?,?,?,?,?)',
                     (object_id, p.id, p.id, 'starter', 'test stool', w.now[0]))
    for price in (*BAD_AMOUNTS, 0, 10001):
        response = post_amount(w, p, '/v1/market', object_id=object_id, version=1, price=price)
        assert response.status_code == 422, (price, response.text)
    with w.db() as conn:
        assert conn.execute('SELECT count(*) FROM listings').fetchone()[0] == 0
        assert tuple(conn.execute('SELECT state,version FROM objects WHERE id=?', (object_id,)).fetchone()) == ('inventory', 1)
    assert 'id' in w.call(p, '/v1/market', object_id=object_id, version=1, price=1)


@pytest.mark.parametrize('balance,code', [(2**63-1, 'coin_balance_overflow'),
                                         (-1, 'invalid_coin_balance'),
                                         (True, 'invalid_coin_balance'),
                                         (1.0, 'invalid_coin_balance')])
def test_invalid_leaf_balance_rolls_back_admin_shards_and_sales(world, balance, code):
    w = world
    p = w.player('broken_coins', role='admin')
    state = homestead.initial()
    state['coins'] = balance
    state['bag']['turnip'] = 5
    save_life(w, p, state)
    assert w.refused(p, '/v1/admin/grant', 409, shards=1, coins=1) == code
    assert w.refused(p, '/v1/homestead', 409, version=0, action='sell', item='turnip') == code
    with w.db() as conn:
        assert json.loads(conn.execute('SELECT state FROM homesteads WHERE user_id=?', (p.id,)).fetchone()[0]) == state
        assert conn.execute('SELECT count(*) FROM requests').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 0
        # The ledger writer flags a broken balance for review (economy_flags + its security event).
        assert economy.ledger_check(conn) == []


def test_admin_leaf_grant_replay_is_atomic_and_idempotent(world):
    w = world
    p = w.player('leaf_retry', role='admin')
    request_id = str(uuid.uuid4())
    first = w.call(p, '/v1/admin/grant', request_id=request_id, shards=2, coins=3)
    assert first == {'shards': 2, 'coins': 15}
    assert w.call(p, '/v1/admin/grant', request_id=request_id, shards=2, coins=3) == first
    assert w.refused(p, '/v1/admin/grant', 409, request_id=request_id, shards=2, coins=4) == 'request_id_reused'
    assert w.get(p, '/v1/homestead')['coins'] == 15
    with w.db() as conn:
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 1
        assert economy.ledger_check(conn) == []
