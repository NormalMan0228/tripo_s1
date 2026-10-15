"""Daily board contracts: server limits, atomic rewards/mail and retriable requests."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server import economy, homestead, npc_letters, quest_board, quests
from server.app import create_app
from server.tests.social_world import World


@pytest.fixture
def world(tmp_path):
    world = World(tmp_path)
    world.now[0] = datetime(2027, 2, 1, 12, tzinfo=quest_board.ZONE).timestamp()
    yield world
    world.close()


def board(w, player):
    return w.get(player, '/v1/quest_board')['board']


def route(w, quest_id, action, day=None):
    return f'/v1/quest_board/{day or quest_board.board_day(w.now[0])}/{quest_id}/{action}'


def offer(w, quest_id):
    for _ in range(len(quests.QUESTS)):
        if quest_id in quest_board.offers(w.now[0]):
            return
        w.tick(86400)
    raise AssertionError('quest never offered')


def fill_bag(w, player, **items):
    with w.app.state.db.transaction() as conn:
        life = quests.life_state(conn, player.id)
        life['bag'].update(items)
        conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state',
                     (player.id, json.dumps(life)))


def test_daily_catalog_rotation_reuses_every_resident_and_scale(world):
    w = world
    a, b = w.players('alice', 'bravo')
    seen = set()
    previous = None
    for _ in range(len(quests.QUESTS)):
        current = board(w, a)
        ids = {q['id'] for q in current['list']}
        assert len(ids) == quest_board.BOARD_SIZE
        assert ids != previous
        assert current == board(w, b)
        for q in current['list']:
            template = quests.QUESTS[q['id']]
            assert q['npc'] == template['npc'] and q['kind'] == template['kind']
            assert q['stars'] == quests.reward(q['id'], w.settings.quest_stars_scale)
            assert q['letter'] is True
        seen |= ids
        previous = ids
        w.tick(86400)
    assert seen == set(quests.QUESTS)


def test_accept_limit_and_clock_headers_cannot_refresh_it(world):
    w = world
    a, b = w.players('alice', 'bravo')
    catalog = board(w, a)
    ids = [q['id'] for q in catalog['list']]
    for q in ids[:3]:
        w.call(a, route(w, q, 'accept'))
    # A fresh request id for an active offer does not consume a fourth slot.
    w.call(a, route(w, ids[0], 'accept'))
    assert w.refused(a, route(w, ids[3], 'accept'), 429) == 'quest_board_daily_limit'
    for offset in (-720, 840):
        response = w.client.get('/v1/quest_board', headers={**a.headers, 'X-Villagen-UTC-Offset': str(offset)})
        assert response.json()['board']['day'] == catalog['day']
        assert response.json()['board']['remaining_accepts'] == 0
    assert board(w, b)['accepted'] == 0
    w.now[0] = catalog['resets_at']
    assert board(w, a)['accepted'] == 0
    assert w.refused(a, route(w, ids[0], 'complete', catalog['day']), 409) == 'quest_board_expired'


def test_completion_is_atomic_idempotent_and_separate_from_one_time_requests(world):
    w = world
    a = w.player('alice')
    offer(w, 'moka_pie')
    fill_bag(w, a, apple=9)
    accepted_id, completed_id = str(uuid.uuid4()), str(uuid.uuid4())
    accepted = w.call(a, route(w, 'moka_pie', 'accept'), request_id=accepted_id)
    assert w.call(a, route(w, 'moka_pie', 'accept'), request_id=accepted_id) == accepted
    done = w.call(a, route(w, 'moka_pie', 'complete'), request_id=completed_id)
    assert w.call(a, route(w, 'moka_pie', 'complete'), request_id=completed_id) == done
    assert done['taken'] == {'apple': 3} and done['stars'] == 8
    assert done['letters'][0]['event'] == {'type': 'request_done',
        'key': quest_board.board_day(w.now[0]) + ':moka_pie',
        'payload': {'quest_id': 'moka_pie', 'day': quest_board.board_day(w.now[0])}}
    assert w.refused(a, route(w, 'moka_pie', 'complete'), 409) == 'quest_already_done'
    assert w.refused(a, route(w, 'moka_pie', 'accept'), 409) == 'quest_already_done'
    with w.app.state.db.read() as conn:
        assert quests.life_state(conn, a.id)['bag']['apple'] == 6
        assert conn.execute("SELECT COUNT(*) FROM ledger WHERE reason='quest_board_reward'").fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM quest_progress').fetchone()[0] == 0
        assert economy.ledger_check(conn) == []
    w.call(a, '/v1/quests/moka_pie/accept')
    assert w.call(a, '/v1/quests/moka_pie/complete')['stars'] == 8
    with w.app.state.db.read() as conn:
        assert economy.ledger_check(conn) == []


def test_failed_conditions_do_not_consume_id_or_items(world):
    w = world
    a = w.player('alice')
    offer(w, 'moka_pie')
    w.call(a, route(w, 'moka_pie', 'accept'))
    request_id = str(uuid.uuid4())
    assert w.refused(a, route(w, 'moka_pie', 'complete'), 409, request_id=request_id) == 'quest_not_ready'
    fill_bag(w, a, apple=3)
    assert w.call(a, route(w, 'moka_pie', 'complete'), request_id=request_id)['quest']['state'] == 'done'


def test_letter_failure_rolls_back_inventory_reward_and_request(world, monkeypatch):
    w = world
    a = w.player('alice')
    offer(w, 'moka_pie')
    fill_bag(w, a, apple=3)
    w.call(a, route(w, 'moka_pie', 'accept'))
    request_id = str(uuid.uuid4())
    original = npc_letters.dispatch
    def broken(*args, **kwargs):
        raise HTTPException(503, 'letter_unavailable')
    monkeypatch.setattr(npc_letters, 'dispatch', broken)
    w.call(a, route(w, 'moka_pie', 'complete'), status=503, request_id=request_id)
    with w.app.state.db.read() as conn:
        assert quests.life_state(conn, a.id)['bag']['apple'] == 3
        assert conn.execute('SELECT COUNT(*) FROM ledger').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM requests WHERE request_id=?', (request_id,)).fetchone()[0] == 0
    monkeypatch.setattr(npc_letters, 'dispatch', original)
    assert w.call(a, route(w, 'moka_pie', 'complete'), request_id=request_id)['stars'] == 8


def test_request_ids_cannot_be_reused_for_other_actions_or_dates(world):
    w = world
    a = w.player('alice')
    q = board(w, a)['list'][0]['id']
    request_id = str(uuid.uuid4())
    original_day = quest_board.board_day(w.now[0])
    accepted = w.call(a, route(w, q, 'accept'), request_id=request_id)
    assert w.refused(a, route(w, q, 'complete'), 409, request_id=request_id) == 'request_id_reused'
    assert w.refused(a, route(w, q, 'accept'), 409, request_id=request_id, place='square') == 'request_id_reused'
    w.tick(86400)
    # Exact lost-response retries retain their original reply after midnight.
    assert w.call(a, route(w, q, 'accept', original_day), request_id=request_id) == accepted
    assert w.refused(a, route(w, q, 'accept'), 409, request_id=request_id) == 'request_id_reused'


def test_concurrent_accepts_cannot_exceed_daily_limit(world):
    w = world
    a = w.player('alice')
    ids = [q['id'] for q in board(w, a)['list']]
    def accept(q):
        return w.client.post(route(w, q, 'accept'), headers=a.headers, json={'request_id': str(uuid.uuid4())}).status_code
    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses = list(pool.map(accept, ids))
    assert sorted(statuses) == [200, 200, 200, 429, 429]
    assert board(w, a)['accepted'] == 3


@pytest.mark.parametrize('same_id', [True, False])
def test_concurrent_completion_pays_and_sends_mail_once(world, same_id):
    w = world
    a = w.player('alice')
    offer(w, 'moka_pie')
    fill_bag(w, a, apple=6)
    w.call(a, route(w, 'moka_pie', 'accept'))
    ident = str(uuid.uuid4())
    def complete(_):
        return w.client.post(route(w, 'moka_pie', 'complete'), headers=a.headers,
                             json={'request_id': ident if same_id else str(uuid.uuid4())})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(complete, range(2)))
    assert sorted(r.status_code for r in responses) == ([200, 200] if same_id else [200, 409])
    if same_id:
        assert responses[0].json() == responses[1].json()
    with w.app.state.db.read() as conn:
        assert quests.life_state(conn, a.id)['bag']['apple'] == 3
        assert conn.execute("SELECT COUNT(*) FROM ledger WHERE reason='quest_board_reward'").fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM npc_letter_events').fetchone()[0] == 1
        assert economy.ledger_check(conn) == []


def test_progress_checks_places_gap_night_and_request_kind(world):
    w = world
    a = w.player('alice')
    offer(w, 'naru_islands')
    q = 'naru_islands'
    w.call(a, route(w, q, 'accept'), place='square')
    assert w.refused(a, route(w, q, 'progress'), 422, place='poet') == 'quest_bad_place'
    assert w.refused(a, route(w, q, 'progress'), 429, place='fields') == 'quest_too_fast'
    w.tick(quests.VISIT_GAP)
    w.call(a, route(w, q, 'progress'), place='fields')
    w.tick(quests.VISIT_GAP)
    assert w.call(a, route(w, q, 'progress'), place='lighthouse')['quest']['state'] == 'ready'
    assert w.call(a, route(w, q, 'complete'))['stars'] == 5
    offer(w, 'haneul_stars')
    w.call(a, route(w, 'haneul_stars', 'accept'))
    assert w.refused(a, route(w, 'haneul_stars', 'progress'), 409, place='observatory') == 'quest_not_night'
    w.tick(9 * 3600)
    assert w.call(a, route(w, 'haneul_stars', 'progress'), place='observatory')['quest']['state'] == 'ready'


def test_server_baseline_and_story_and_own_village_gates(world):
    w = world
    a, b = w.players('alice', 'bravo')
    offer(w, 'sora_outfit')
    w.call(a, route(w, 'sora_outfit', 'accept'))
    assert w.refused(a, route(w, 'sora_outfit', 'complete'), 409) == 'quest_not_ready'
    assert w.refused(a, route(w, 'sora_outfit', 'progress'), 409, place='square') == 'quest_wrong_kind'
    with w.app.state.db.transaction() as conn:
        conn.execute("INSERT INTO profiles(user_id,avatar,version) VALUES (?,'{}',1)", (a.id,))
    assert w.call(a, route(w, 'sora_outfit', 'complete'))['stars'] == 3
    with w.app.state.db.transaction() as conn:
        w.app.state.story.begin(conn, b.id, w.now[0])
    assert board(w, b)['unlocked'] is False
    assert w.refused(b, route(w, 'sora_outfit', 'accept'), 409) == 'quests_locked'
    with w.app.state.db.transaction() as conn:
        conn.execute('DELETE FROM story_progress WHERE user_id=?', (b.id,))
    w.visit(b, a)
    assert w.refused(b, route(w, 'sora_outfit', 'accept'), 409) == 'quest_own_village_only'


def test_persistence_and_next_rotation_repeats_without_extra_rewards(world):
    w = world
    a = w.player('alice')
    offer(w, 'moka_pie')
    fill_bag(w, a, apple=6)
    w.call(a, route(w, 'moka_pie', 'accept'))
    first = w.call(a, route(w, 'moka_pie', 'complete'))
    saved = board(w, a)
    app = create_app(w.settings, clock=lambda: w.now[0], worker_enabled=False)
    with TestClient(app) as client:
        assert client.get('/v1/quest_board', headers=a.headers).json()['board'] == saved
    app.state.db.close()
    w.tick(86400)
    offer(w, 'moka_pie')
    w.call(a, route(w, 'moka_pie', 'accept'))
    second = w.call(a, route(w, 'moka_pie', 'complete'))
    assert first['letters'][0]['id'] != second['letters'][0]['id']
    assert first['stars'] == second['stars'] == 8


def test_zero_reward_scale_still_completes_and_sends_letter(world):
    w = world
    w.settings.quest_stars_scale = 0
    a = w.player('alice')
    offer(w, 'moka_pie')
    fill_bag(w, a, apple=3)
    w.call(a, route(w, 'moka_pie', 'accept'))
    done = w.call(a, route(w, 'moka_pie', 'complete'))
    assert done['stars'] == 0 and done['shards'] == 0 and len(done['letters']) == 1
    with w.app.state.db.read() as conn:
        assert conn.execute('SELECT COUNT(*) FROM ledger').fetchone()[0] == 0


def test_authentication_and_invalid_offer_or_body(world):
    w = world
    a = w.player('alice')
    q = board(w, a)['list'][0]['id']
    assert w.client.get('/v1/quest_board').status_code == 401
    for action in ('accept', 'complete', 'progress'):
        body = {'request_id': str(uuid.uuid4()), **({'place': 'square'} if action == 'progress' else {})}
        assert w.client.post(route(w, q, action), json=body).status_code == 401
    assert w.client.post(route(w, q, 'accept'), headers=a.headers, json={'request_id': 'bad'}).status_code == 422
    assert w.client.post(route(w, q, 'complete'), headers=a.headers,
                         json={'request_id': str(uuid.uuid4()), 'stars': 999}).status_code == 422
    assert w.refused(a, route(w, 'unknown', 'accept'), 404) == 'quest_not_found'
    absent = next(q for q in quests.QUESTS if q not in quest_board.offers(w.now[0]))
    assert w.refused(a, route(w, absent, 'accept'), 404) == 'quest_board_not_offered'
    assert w.refused(a, route(w, q, 'complete'), 409) == 'quest_not_active'


def test_completed_requests_do_not_free_daily_slots(world):
    w = world
    a = w.player('alice')
    for _ in range(len(quests.QUESTS)):
        offered = quest_board.offers(w.now[0])
        bring = [q for q in offered if quests.QUESTS[q]['kind'] == 'bring']
        if len(bring) >= quest_board.DAILY_LIMIT:
            break
        w.tick(86400)
    else:
        raise AssertionError('expected a board with three delivery requests')
    for q in bring[:quest_board.DAILY_LIMIT]:
        template = quests.QUESTS[q]
        fill_bag(w, a, **{template['items'][0]: template['count']})
        w.call(a, route(w, q, 'accept'))
        w.call(a, route(w, q, 'complete'))
    current = board(w, a)
    assert current['accepted'] == current['completed'] == 3
    assert current['remaining_accepts'] == current['remaining_completions'] == 0
    extra = next(q for q in offered if q not in bring[:quest_board.DAILY_LIMIT])
    assert w.refused(a, route(w, extra, 'accept'), 429) == 'quest_board_daily_limit'
    with w.app.state.db.read() as conn:
        assert conn.execute("SELECT COUNT(*),SUM(amount) FROM ledger WHERE reason='quest_board_reward'").fetchone()[0] == 3
        assert economy.ledger_check(conn) == []
