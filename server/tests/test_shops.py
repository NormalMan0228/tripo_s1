"""Shop migrations, economy invariants, services and request replay across API versions."""
import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from server import economy, homestead, story
from server.shop_catalog import SHOPS
from server.tests.social_world import World
from server.tests.test_api import account, mutation


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


def seed(w, p, coins=100, bag=None, opened=True):
    state = homestead.initial()
    state['coins'] = coins
    state['bag'].update(bag or {})
    with w.app.state.db.transaction() as conn:
        conn.execute('INSERT INTO homesteads VALUES (?,?)', (p.id, json.dumps(state)))
        if opened:
            story.move_in_danbi(conn, p.id, w.now[0])
    return state


def life(w, p):
    return w.get(p, '/v1/homestead')


def trade(w, p, action, item, quantity=1, shop='general_store', status=200, **extra):
    return w.call(p, f'/v1/shops/{shop}/{action}', status,
                  version=life(w, p)['version'], item=item, quantity=quantity, **extra)


def service(w, p, shop, name, status=200, **extra):
    return w.call(p, f'/v1/shops/{shop}/service', status,
                  version=life(w, p)['version'], service=name, **extra)


def test_buy_sell_and_both_ledgers(world):
    w = world; p = w.player('trader'); seed(w, p, bag={'turnip': 3})
    bought = trade(w, p, 'buy', 'turnip_seed', 2)
    assert bought['coins'] == 96 and bought['bag']['turnip_seed'] == 5
    sold = trade(w, p, 'sell', 'turnip', 2)
    assert sold['coins'] == 102 and sold['bag']['turnip'] == 1 and sold['shards'] == 2
    with w.db() as conn:
        assert [tuple(r) for r in conn.execute('SELECT amount,reason FROM leaf_ledger ORDER BY rowid')] == [
            (100, 'opening_balance'), (-4, 'shop_buy'), (6, 'shop_sell')]
        assert tuple(conn.execute('SELECT amount,reason FROM ledger').fetchone()) == (2, 'sell_reward')
        assert economy.ledger_check(conn) == []


def test_closed_until_story_completion_and_no_client_flag_setter(world):
    w = world
    h = account(w.client, 'newcomer')
    assert not w.client.get('/v1/shops/general_store', headers=h).json()['open']
    body = mutation(version=0, item='bait')
    assert w.client.post('/v1/shops/general_store/buy', headers=h, json=body).json()['detail'] == 'shop_closed'
    assert w.client.post('/v1/shops/general_store/buy', headers=h, json={**body, 'danbi_moved_in': True}).status_code == 422
    obj = w.client.get('/v1/me', headers=h).json()['objects'][0]
    gift = mutation(object_id=obj['id'], version=obj['version'])
    result = w.client.post('/v1/story/gift', headers=h, json=gift)
    assert result.status_code == 200, result.text
    assert result.json()['story']['flags'] == {'danbi_moved_in': True}
    assert w.client.get('/v1/shops/general_store', headers=h).json()['open']
    assert w.client.post('/v1/shops/general_store/buy', headers=h, json=body).status_code == 200
    with w.app.state.db.transaction() as conn:
        user_id = conn.execute("SELECT id FROM users WHERE username='newcomer'").fetchone()[0]
        story.reset(conn, user_id, w.now[0])
    assert not w.client.get('/v1/shops/general_store', headers=h).json()['open']


def test_failed_trades_leave_money_inventory_requests_and_stock_unchanged(world):
    w = world; p = w.player('poor'); seed(w, p, coins=1)
    before = life(w, p)
    assert trade(w, p, 'buy', 'turnip_seed', status=409)['detail'] == 'life_not_enough_coins'
    assert trade(w, p, 'sell', 'turnip', status=409)['detail'] == 'life_missing_items'
    offer = next(i for i in w.get(p, '/v1/shops/general_store')['buy'] if i['kind'] == 'decoration')
    assert trade(w, p, 'buy', offer['id'], status=409)['detail'] == 'life_not_enough_coins'
    assert life(w, p) == before
    with w.db() as conn:
        for table in ('leaf_ledger', 'ledger', 'requests', 'shop_usage'):
            assert conn.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0


def test_request_replay_conflicts_and_concurrent_duplicate(world):
    w = world; p = w.player('replay'); seed(w, p)
    body = mutation(version=0, item='carrot_seed', quantity=2)
    def buy(_):
        return w.client.post('/v1/shops/general_store/buy', headers=p.headers, json=body)
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(buy, range(2)))
    assert [r.status_code for r in replies] == [200, 200]
    assert replies[0].json() == replies[1].json()
    assert life(w, p)['coins'] == 94
    for path, change in [('/general_store/buy', {'quantity': 1}), ('/farm_stall/buy', {}), ('/general_store/sell', {})]:
        result = w.client.post('/v1/shops' + path, headers=p.headers, json={**body, **change})
        assert result.json()['detail'] == 'request_id_reused'
    # Replay is still the original receipt even after day rollover and a later purchase.
    w.tick(86400)
    trade(w, p, 'buy', 'bait')
    assert buy(0).json() == replies[0].json()
    with w.db() as conn:
        assert conn.execute("SELECT count(*) FROM leaf_ledger WHERE reason='shop_buy'").fetchone()[0] == 2


def test_two_distinct_concurrent_purchases_require_fresh_version(world):
    w = world; p = w.player('racing'); seed(w, p)
    def buy(_):
        return w.client.post('/v1/shops/general_store/buy', headers=p.headers,
                             json=mutation(version=0, item='bait')).status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(buy, range(2))) == [200, 409]
    assert life(w, p)['coins'] == 99


def test_daily_rotation_stock_is_per_account_persistent_and_creates_real_objects(world):
    w = world; p = w.player('decorator'); q = w.player('neighbor')
    seed(w, p); seed(w, q)
    catalog = w.get(p, '/v1/shops/general_store')
    offer = next(i for i in catalog['buy'] if i['kind'] == 'decoration')
    other = next(i for i in SHOPS['general_store']['buy'] if i in ('flower_pot', 'table_lamp') and i != offer['id'])
    assert trade(w, p, 'buy', other, status=409)['detail'] == 'shop_item_unavailable'
    assert trade(w, p, 'buy', offer['id'], 2, status=409)['detail'] == 'shop_daily_limit'
    result = trade(w, p, 'buy', offer['id'])
    assert len(result['object_ids']) == 1
    objects = w.get(p, '/v1/me')['objects']
    assert any(o['id'] == result['object_ids'][0] and o['state'] == 'inventory' for o in objects)
    assert w.client.get('/v1/objects/' + result['object_ids'][0] + '/model', headers=p.headers).status_code == 200
    assert trade(w, p, 'buy', offer['id'], status=409)['detail'] == 'shop_daily_limit'
    trade(w, q, 'buy', offer['id'])
    restarted = World(w.settings.data_dir)
    try:
        assert trade(restarted, p, 'buy', offer['id'], status=409)['detail'] == 'shop_daily_limit'
    finally:
        restarted.close()
    w.now[0] = catalog['resets_at']
    trade(w, p, 'buy', other)
    w.tick(86400)
    trade(w, p, 'buy', offer['id'])


def test_cafe_effect_expires_does_not_stack_and_day_pin_cannot_be_changed(world):
    w = world; p = w.player('tea'); seed(w, p)
    p.headers['X-Villagen-UTC-Offset'] = '-720'
    for _ in range(3):
        result = service(w, p, 'cafe', 'herb_tea')
        assert result['effects'] == {'cafe_mood': {'mood': 'cozy', 'expires_at': w.now[0] + 600}}
        assert result['shards'] == 0
    p.headers['X-Villagen-UTC-Offset'] = '840'
    assert service(w, p, 'cafe', 'herb_tea', 409)['detail'] == 'shop_daily_limit'
    assert life(w, p)['coins'] == 91
    w.tick(600)
    assert w.get(p, '/v1/shops/cafe')['effects'] == {}
    w.now[0] = w.get(p, '/v1/shops/cafe')['resets_at']
    service(w, p, 'cafe', 'herb_tea')


def test_farmer_order_shares_legacy_day_limit_and_never_pays_stars(world):
    w = world; p = w.player('delivery'); seed(w, p, bag={'turnip': 4, 'perch': 2})
    result = service(w, p, 'farm_stall', 'daily_order')
    assert result['coins'] == 120 and result['shards'] == 0
    assert w.call(p, '/v1/homestead', 409, version=result['version'], action='order')['detail'] == 'life_order_completed'
    w.tick(86400)
    result = w.call(p, '/v1/homestead', version=result['version'], action='order')
    assert result['coins'] == 140
    assert service(w, p, 'farm_stall', 'daily_order', 409)['detail'] == 'life_order_completed'
    with w.db() as conn:
        assert conn.execute("SELECT SUM(amount) FROM leaf_ledger WHERE reason='daily_order'").fetchone()[0] == 40
        assert conn.execute('SELECT count(*) FROM ledger').fetchone()[0] == 0


def test_fisher_and_all_sale_routes_share_original_prices_carry_and_star_cap(world):
    w = world; p = w.player('fishseller'); seed(w, p, bag={'perch': 20, 'apple': 20})
    result = service(w, p, 'fishing_shack', 'sell_fish', item='perch', quantity=1)
    assert result['coins'] == 104 and result['stars'] == 1 and result['sell_stars']['carry'] == 1
    result = trade(w, p, 'sell', 'apple', 1)
    assert result['stars'] == 1 and result['sell_stars']['carry'] == 0
    result = w.call(p, '/v1/homestead', version=result['version'], action='sell', item='perch', quantity=19)
    assert result['stars'] == 13 and result['sell_stars']['today'] == 15
    assert trade(w, p, 'sell', 'apple')['stars'] == 0
    assert service(w, p, 'fishing_shack', 'sell_fish', 409, item='apple')['detail'] == 'life_invalid_item'
    assert trade(w, p, 'sell', 'turnip_seed', status=409)['detail'] == 'life_invalid_item'
    with w.db() as conn:
        assert conn.execute("SELECT SUM(amount) FROM ledger WHERE reason='sell_reward'").fetchone()[0] == 15


def test_legacy_seed_price_inventory_and_request_migration(world):
    w = world; p = w.player('legacy'); before = seed(w, p, opened=False)
    body = mutation(version=0, action='buy', item='pumpkin_seed', quantity=2)
    # A persisted receipt written by the pre-shop API must still replay verbatim.
    from server.app import digest
    from server.models import LifeAction
    receipt = {'version': 1, 'coins': 92, 'bag': {'pumpkin_seed': 3}}
    with w.db() as conn:
        conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)',
                     (p.id, body['request_id'], 'homestead', digest(LifeAction(**body).model_dump_json()), json.dumps(receipt), w.now[0]))
    assert w.client.post('/v1/homestead', headers=p.headers, json=body).json() == receipt
    assert life(w, p)['coins'] == before['coins']
    for item, price in homestead.SHOP.items():
        current = life(w, p)
        result = w.call(p, '/v1/homestead', version=current['version'], action='buy', item=item)
        assert result['coins'] == current['coins'] - price
        assert result['bag'][item] == current['bag'].get(item, 0) + 1
    catalog = w.get(p, '/v1/shops/farm_stall')
    assert {i['id']: i['coins'] for i in catalog['buy']} == homestead.SHOP
    assert trade(w, p, 'buy', 'bait', shop='farm_stall')['coins'] == result['coins'] - 1
    with w.db() as conn:
        assert conn.execute("SELECT count(*) FROM leaf_ledger WHERE reason='opening_balance'").fetchone()[0] == 1
        assert conn.execute('SELECT SUM(amount) FROM leaf_ledger').fetchone()[0] == life(w, p)['coins']


@pytest.mark.parametrize('change', [{'quantity': 0}, {'quantity': 21}, {'quantity': True}, {'quantity': 1.0},
                                  {'quantity': '1'}, {'coins': 0}, {'owner_id': 'someone'}, {'version': True}])
def test_trade_validation_and_auth(world, change):
    w = world; p = w.player('validation'); seed(w, p)
    body = mutation(version=0, item='bait')
    assert w.client.get('/v1/shops/general_store').status_code == 401
    assert w.client.post('/v1/shops/general_store/buy', json=body).status_code == 401
    assert w.client.post('/v1/shops/general_store/buy', headers=p.headers, json={**body, **change}).status_code == 422
    assert w.get(p, '/v1/shops/missing', 404)['detail'] == 'shop_not_found'


def test_mixed_price_insufficient_stars_rolls_back_coins_and_stock(world, monkeypatch):
    w = world; p = w.player('mixed'); seed(w, p)
    spec = dict(SHOPS['general_store']['buy']['bait'], shards=2, daily_limit=2)
    monkeypatch.setitem(SHOPS['general_store']['buy'], 'bait', spec)
    assert trade(w, p, 'buy', 'bait', status=409)['detail'] == 'insufficient_shards'
    assert life(w, p)['coins'] == 100
    with w.app.state.db.transaction() as conn:
        assert conn.execute('SELECT count(*) FROM leaf_ledger').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM shop_usage').fetchone()[0] == 0
        economy.change_shards(conn, p.id, 2, 'test', 'fund', w.now[0])
    result = trade(w, p, 'buy', 'bait')
    assert result['shards'] == 0 and result['coins'] == 99


def test_leaf_helper_savepoint_rolls_back_duplicate_and_storage_failure(world):
    w = world; p = w.player('atomic'); state = seed(w, p)
    with w.app.state.db.transaction() as conn:
        economy.change_coins(conn, p.id, state, -3, 'test', 'once', w.now[0])
        with pytest.raises(sqlite3.IntegrityError):
            economy.change_coins(conn, p.id, state, -3, 'test', 'once', w.now[0])
        conn.execute("CREATE TEMP TRIGGER refuse_leaf BEFORE UPDATE ON homesteads BEGIN SELECT RAISE(ABORT,'no_write'); END")
        with pytest.raises(sqlite3.IntegrityError):
            economy.change_coins(conn, p.id, state, -3, 'test', 'storage', w.now[0])
        assert state['coins'] == 97
        assert conn.execute('SELECT SUM(amount) FROM leaf_ledger').fetchone()[0] == 97
        conn.execute('DROP TRIGGER refuse_leaf')
        for value in (True, 1.0, '3', 2**63):
            with pytest.raises(economy.EconomyRejected):
                economy.change_coins(conn, p.id, state, value, 'test', 'bad', w.now[0])
        with pytest.raises(HTTPException, match='life_not_enough_coins'):
            economy.change_coins(conn, p.id, state, -98, 'test', 'poor', w.now[0])


def test_completed_old_story_backfills_flag_on_upgrade_once(world):
    w = world; p = w.player('old_story'); seed(w, p, opened=False)
    with w.app.state.db.transaction() as conn:
        story.begin(conn, p.id, w.now[0])
        conn.execute("UPDATE story_progress SET step='done',completed=? WHERE user_id=?", (w.now[0], p.id))
    restarted = World(w.settings.data_dir)
    try:
        assert restarted.get(p, '/v1/shops/general_store')['open']
        trade(restarted, p, 'buy', 'bait')
    finally:
        restarted.close()
    with w.db() as conn:
        assert conn.execute('SELECT count(*) FROM story_flags WHERE user_id=?', (p.id,)).fetchone()[0] == 1


def test_sell_service_and_tea_retries_do_not_duplicate_money_or_effect(world):
    w = world; p = w.player('service_replay'); seed(w, p, bag={'perch': 2})
    for shop, args in [('fishing_shack', {'service': 'sell_fish', 'item': 'perch'}),
                       ('cafe', {'service': 'herb_tea'})]:
        body = mutation(version=life(w, p)['version'], **args)
        path = '/v1/shops/' + shop + '/service'
        first = w.client.post(path, headers=p.headers, json=body)
        assert first.status_code == 200, first.text
        w.tick(1)
        assert w.client.post(path, headers=p.headers, json=body).json() == first.json()
    assert life(w, p)['coins'] == 101
    assert life(w, p)['bag']['perch'] == 1
    with w.db() as conn:
        assert conn.execute("SELECT count(*) FROM leaf_ledger WHERE reason!='opening_balance'").fetchone()[0] == 2
        assert conn.execute("SELECT SUM(amount) FROM ledger WHERE reason='sell_reward'").fetchone()[0] == 1


def test_configured_sell_daily_limit_and_service_cannot_bypass_it(world, monkeypatch):
    w = world; p = w.player('sell_limit'); seed(w, p, bag={'perch': 5})
    monkeypatch.setitem(SHOPS['fishing_shack']['sell'], 'perch',
                        dict(SHOPS['fishing_shack']['sell']['perch'], daily_limit=2))
    trade(w, p, 'sell', 'perch', 2, shop='fishing_shack')
    assert service(w, p, 'fishing_shack', 'sell_fish', 409, item='perch')['detail'] == 'shop_daily_limit'
    assert life(w, p)['bag']['perch'] == 3
    w.tick(86400)
    service(w, p, 'fishing_shack', 'sell_fish', item='perch')


def test_invalid_service_arguments_leave_state_unchanged(world):
    w = world; p = w.player('bad_service'); seed(w, p)
    before = life(w, p)
    assert service(w, p, 'cafe', 'herb_tea', 422, quantity=2)['detail'] == 'shop_invalid_service_arguments'
    assert service(w, p, 'cafe', 'herb_tea', 422, item='bait')['detail'] == 'shop_invalid_service_arguments'
    assert service(w, p, 'cafe', 'missing', 404)['detail'] == 'shop_service_not_found'
    assert life(w, p) == before
