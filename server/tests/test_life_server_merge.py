"""Combined residency, daily requests, event mail and shop currency contracts."""
import json
import uuid
from collections import Counter
from datetime import datetime

import pytest

from server import economy, homestead, quest_board, quests, story, village_residents
from server.shop_catalog import SHOPS
from server.tests.social_world import World


@pytest.fixture
def world(tmp_path):
    world = World(tmp_path, resident_moves=True)
    world.now[0] = datetime(2027, 2, 1, 12, tzinfo=quest_board.ZONE).timestamp()
    yield world
    world.close()


def offer(world, quest_id):
    for _ in range(len(quests.QUESTS)):
        if quest_id in quest_board.offers(world.now[0]):
            return
        world.tick(86400)
    raise AssertionError('quest never offered')


def route(world, quest_id, action):
    return f'/v1/quest_board/{quest_board.board_day(world.now[0])}/{quest_id}/{action}'


def request_entry(world, player, quest_id):
    board = world.get(player, '/v1/quest_board')['board']
    return next(entry for entry in board['list'] if entry['id'] == quest_id)


def move(world, player, entering):
    with world.app.state.db.transaction() as conn:
        assert village_residents.move_in(
            conn, player.id, 'shopkeeper', world.now[0], world.settings, entering=entering)


def test_returning_resident_keeps_friendship_and_daily_request(world):
    player = world.player('returning_friend')
    offer(world, 'danbi_home')
    # Accounts predating the story start at home, without receiving a new-arrival letter.
    assert world.get(player, '/v1/village/residency')['residents'][0]['state'] == 'home'
    with world.app.state.db.transaction() as conn:
        conn.execute('INSERT INTO npc_friendship VALUES (?,?,?,?,?)', (player.id, 'shopkeeper', 85, 3, 20))
        village_residents.remember(conn, player.id, 'shopkeeper', world.now[0])
        bond = dict(conn.execute('SELECT * FROM npc_friendship WHERE host_id=?', (player.id,)).fetchone())
    before = world.get(player, '/v1/village/residency')['residents'][0]
    world.call(player, route(world, 'danbi_home', 'accept'))
    with world.app.state.db.read() as conn:
        progress = dict(conn.execute('SELECT * FROM quest_board_progress WHERE user_id=?', (player.id,)).fetchone())

    move(world, player, False)
    world.tick(world.settings.resident_leave_seconds)
    # Reading the board itself must settle a due departure and hide this resident's request.
    assert request_entry(world, player, 'danbi_home')['state'] == 'locked'
    for action in ('accept', 'progress', 'complete'):
        extra = {'place': 'village'} if action == 'progress' else {}
        assert world.refused(player, route(world, 'danbi_home', action), 409, **extra) == 'quests_locked'

    move(world, player, True)
    world.tick(world.settings.resident_arrive_seconds)
    # No residency poll: an accepted-request retry with a new ID must settle the arrival.
    resumed = world.call(player, route(world, 'danbi_home', 'accept'))
    assert resumed['quest']['state'] in ('active', 'ready')
    assert resumed['board']['accepted'] == 1
    returned = world.get(player, '/v1/village/residency')['residents'][0]
    assert returned['state'] == 'home' and returned['back'] and returned['hearts'] == 2
    assert returned['memory'] == before['memory']
    with world.app.state.db.read() as conn:
        assert dict(conn.execute('SELECT * FROM npc_friendship WHERE host_id=?', (player.id,)).fetchone()) == bond
        assert dict(conn.execute('SELECT * FROM quest_board_progress WHERE user_id=?', (player.id,)).fetchone()) == progress


def test_move_mail_has_one_event_and_one_news_reference_per_transition(world):
    player = world.player('move_mail')
    world.get(player, '/v1/village/residency')
    move(world, player, False)
    world.tick(world.settings.resident_leave_seconds)
    world.get(player, '/v1/quest_board')
    move(world, player, True)
    world.tick(world.settings.resident_arrive_seconds)
    first = world.get(player, '/v1/letters')
    assert world.get(player, '/v1/letters') == first
    letters = [letter for letter in first['letters'] if letter.get('move')]
    assert [letter['move']['kind'] for letter in letters] == ['back', 'out']
    assert [letter['event']['type'] for letter in letters] == ['move_in', 'move_out']
    assert all(letter['move']['npc'] == 'shopkeeper' for letter in letters)
    with world.app.state.db.read() as conn:
        linked = conn.execute(
            'SELECT n.letter_id,e.letter_id FROM village_news n '
            'JOIN npc_letter_events e ON e.letter_id=n.letter_id '
            "WHERE n.host_id=? AND n.kind IN ('returned','moved_out')", (player.id,)).fetchall()
        assert len(linked) == 2
        assert {row[0] for row in linked} == {letter['id'] for letter in letters}
        assert conn.execute('SELECT COUNT(*) FROM npc_letter_events WHERE host_id=?', (player.id,)).fetchone()[0] == 2
        assert conn.execute('SELECT COUNT(*) FROM ledger WHERE user_id=?', (player.id,)).fetchone()[0] == 0


@pytest.mark.parametrize('star_price', [0, 3])
def test_quest_reward_then_purchase_keeps_both_ledgers_and_retries(world, monkeypatch, star_price):
    player = world.player('quest_trader')
    offer(world, 'moka_pie')
    state = homestead.initial()
    state['coins'] = 20
    state['bag']['apple'] = 6
    with world.app.state.db.transaction() as conn:
        conn.execute('INSERT INTO homesteads VALUES (?,?)', (player.id, json.dumps(state)))
        story.move_in_danbi(conn, player.id, world.now[0])
    # Exercise the configured coin-only catalog and its supported mixed-currency price.
    monkeypatch.setitem(SHOPS['general_store']['buy']['turnip_seed'], 'shards', star_price)
    world.call(player, route(world, 'moka_pie', 'accept'))
    complete_id = str(uuid.uuid4())
    completed = world.call(player, route(world, 'moka_pie', 'complete'), request_id=complete_id)
    assert completed['stars'] == completed['shards'] == 8
    purchase = {'request_id': str(uuid.uuid4()), 'version': world.get(player, '/v1/homestead')['version'],
                'item': 'turnip_seed', 'quantity': 2}
    bought = world.call(player, '/v1/shops/general_store/buy', **purchase)
    assert bought['coins'] == 16 and bought['shards'] == 8 - 2 * star_price
    assert bought['bag']['apple'] == 3
    assert bought['bag']['turnip_seed'] == state['bag']['turnip_seed'] + 2
    assert world.call(player, '/v1/shops/general_store/buy', **purchase) == bought
    assert world.call(player, route(world, 'moka_pie', 'complete'), request_id=complete_id) == completed
    assert world.refused(player, '/v1/shops/general_store/buy', 409,
                         **{**purchase, 'request_id': complete_id}) == 'request_id_reused'
    assert world.refused(player, route(world, 'moka_pie', 'complete'), 409,
                         request_id=purchase['request_id']) == 'request_id_reused'
    with world.app.state.db.read() as conn:
        ledger = [tuple(row) for row in conn.execute(
            'SELECT amount,reason FROM ledger WHERE user_id=? ORDER BY rowid', (player.id,))]
        assert ledger == [(8, 'quest_board_reward')] + ([(-2 * star_price, 'shop_buy')] if star_price else [])
        assert [tuple(row) for row in conn.execute(
            'SELECT amount,reason FROM leaf_ledger WHERE user_id=? ORDER BY rowid', (player.id,))] == [
                (20, 'opening_balance'), (-4, 'shop_buy')]
        assert conn.execute('SELECT SUM(amount) FROM leaf_ledger WHERE user_id=?', (player.id,)).fetchone()[0] == bought['coins']
        assert conn.execute('SELECT shards FROM users WHERE id=?', (player.id,)).fetchone()[0] == bought['shards']
        assert economy.ledger_check(conn) == []
        assert conn.execute("SELECT COUNT(*) FROM npc_letter_events WHERE host_id=? AND event='request_done'",
                            (player.id,)).fetchone()[0] == 1


def test_combined_routes_are_registered_once(world):
    registered = Counter(
        (method, route.path) for route in world.app.routes for method in getattr(route, 'methods', ())
    )
    assert {key: count for key, count in registered.items() if count > 1} == {}
    expected = {
        ('POST', '/v1/story/step'), ('POST', '/v1/story/gift'),
        ('GET', '/v1/letters'), ('GET', '/v1/village/residency'),
        ('GET', '/v1/quest_board'), ('POST', '/v1/quest_board/{day}/{quest_id}/accept'),
        ('POST', '/v1/quest_board/{day}/{quest_id}/complete'),
        ('GET', '/v1/shops/{shop_id}'), ('POST', '/v1/shops/{shop_id}/buy'),
        ('POST', '/v1/shops/{shop_id}/sell'), ('POST', '/v1/shops/{shop_id}/service'),
    }
    assert expected <= registered.keys()
