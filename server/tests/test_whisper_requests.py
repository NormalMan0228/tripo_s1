"""Consent, proximity and abuse limits for whispers between non-friends."""
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from server import chat
from server.tests.social_world import World

PATH = '/v1/social/whispers/requests'


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


def together(w):
    a, b = w.players('alice', 'bravo')
    w.visit(b, a)
    w.presence(a, x=0, y=0, z=0)
    w.presence(b, x=8, y=0, z=0)
    return a, b


def request(w, a, b, **kwargs):
    return w.call(a, '/v1/social/messages', text='hello privately', channel='whisper', to=b.name, **kwargs)


def answer(w, b, sent, decision='accept', **kwargs):
    return w.call(b, PATH+'/'+sent['request']['id']+'/'+decision, **kwargs)


def test_first_whisper_only_requests_and_consent_allows_both_directions(world):
    w = world
    a, b = together(w)
    stranger = w.player('outsider')
    sent = request(w, a, b)
    assert sent['state'] == 'requested' and 'text' not in sent
    assert w.presence(b, since=0)['chat']['lines'] == []
    inbox = w.get(b, PATH)['requests']
    assert len(inbox) == 1 and inbox[0]['from_name'] == 'alice'
    assert inbox[0]['state'] == 'pending' and 'text' not in inbox[0]
    assert w.get(a, PATH)['requests'] == inbox
    assert w.get(stranger, PATH)['requests'] == []
    assert answer(w, a, sent, status=404)['detail'] == 'whisper_request_unavailable'
    assert answer(w, stranger, sent, status=404)['detail'] == 'whisper_request_unavailable'
    accepted = answer(w, b, sent)
    assert accepted['state'] == 'accepted'
    assert accepted['expires'] == (int(w.now[0]//86400)+1)*86400
    assert w.presence(b, since=0)['chat']['lines'] == []  # discarded first text never flows
    line = w.say(a, 'now accepted', channel='whisper', to=b.name)
    w.say(b, 'reply allowed', channel='whisper', to=a.name)
    assert [r['text'] for r in w.presence(b, since=0)['chat']['lines']] == ['now accepted', 'reply allowed']
    assert w.presence(stranger, since=0)['chat']['lines'] == []
    assert line['channel'] == 'whisper'


@pytest.mark.parametrize('position', [
    {'x': 8.001}, {'x': 0, 'y': 8.001}, {'x': 6, 'z': 6},
    {'scene': 'home'}, {'floor': 1}, {'place': 'workshop'},
    {'scene': 'away', 'place': 'room'},
])
def test_strangers_require_same_space_and_three_dimensional_eight_metres(world, position):
    w = world
    a, b = together(w)
    w.presence(b, **position)
    assert request(w, a, b, status=404)['detail'] == 'whisper_target_unavailable'
    assert w.get(b, PATH)['requests'] == []


def test_different_instances_and_stale_presence_are_unavailable(world):
    w = world
    a, b = w.players('alice', 'bravo')
    w.presence(a)
    w.presence(b)
    request(w, a, b, status=404)  # identical coordinates, different villages
    w.visit(b, a)
    w.presence(a)
    w.presence(b)
    w.tick(9)
    w.presence(a)
    request(w, a, b, status=404)
    w.presence(b)
    w.call(b, '/v1/social/prefs', appear_offline=True)
    request(w, a, b, status=404)


def test_accept_and_later_messages_recheck_proximity(world):
    w = world
    a, b = together(w)
    sent = request(w, a, b)
    w.presence(a, x=30)
    answer(w, b, sent, status=404)
    w.presence(a, z=0)
    answer(w, b, sent)
    w.presence(b, x=30)
    request(w, a, b, status=404)
    w.presence(b)
    assert 'id' in request(w, a, b)


def test_friends_need_no_consent_or_distance_check(world):
    w = world
    a, b = w.players('alice', 'bravo')
    w.befriend(a, b)
    w.presence(b, scene='away', x=100)
    assert 'id' in request(w, a, b)
    assert w.get(b, PATH)['requests'] == []


@pytest.mark.parametrize('decline', [False, True])
def test_ignored_and_declined_requests_cool_down_per_pair(world, decline):
    w = world
    a, b = together(w)
    sent = request(w, a, b)
    if decline:
        assert answer(w, b, sent, 'decline')['state'] == 'declined'
        assert answer(w, b, sent, status=409)['detail'] == 'whisper_request_closed'
    for sender, receiver in ((a, b), (b, a)):
        assert request(w, sender, receiver, status=429)['detail'] == 'whisper_request_limited'
    w.tick(599)
    w.visit(b, a)
    w.presence(b)
    assert request(w, a, b, status=429)['detail'] == 'whisper_request_limited'
    w.tick(1)
    answer(w, b, sent, status=404)
    again = request(w, a, b)
    assert again['request']['id'] != sent['request']['id']


def test_max_five_pending_requests_and_decline_releases_slot(world):
    w = world
    a = w.player('alice')
    peers = w.players(*('peer'+str(i) for i in range(6)))
    # A sender visits six separate hosts; the pending limit is account-wide.
    sent = []
    for i, b in enumerate(peers):
        w.visit(a, b)
        w.presence(a)
        result = request(w, a, b, status=200 if i < 5 else 429)
        sent.append(result)
    assert sent[-1]['detail'] == 'whisper_pending_limit'
    answer(w, peers[0], sent[0], 'decline')
    assert request(w, a, peers[-1])['state'] == 'requested'


@pytest.mark.parametrize('blocker_index', [0, 1])
def test_blocking_revokes_consent_and_hides_requests(world, blocker_index):
    w = world
    a, b = together(w)
    sent = request(w, a, b)
    answer(w, b, sent)
    blocker, blocked = (a, b) if blocker_index == 0 else (b, a)
    w.call(blocker, '/v1/social/blocks', user_id=blocked.id)
    assert w.get(a, PATH)['requests'] == w.get(b, PATH)['requests'] == []
    request(w, a, b, status=404)
    request(w, b, a, status=404)
    answer(w, b, sent, status=404)
    w.call(blocker, '/v1/social/blocks/remove', user_id=blocked.id)
    w.visit(b, a)
    w.presence(a)
    w.presence(b)
    assert request(w, a, b, status=429)['detail'] == 'whisper_request_limited'
    w.tick(600)
    w.visit(b, a)
    w.presence(b)
    assert request(w, a, b)['state'] == 'requested'


def test_request_and_answer_retries_are_idempotent_and_concurrent_requests_are_limited(world):
    w = world
    a, b = together(w)
    ident = str(uuid.uuid4())
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: request(w, a, b, request_id=ident), range(2)))
    assert replies[0] == replies[1]
    assert len(w.get(b, PATH)['requests']) == 1
    assert w.call(a, '/v1/social/messages', status=409, request_id=ident,
                  text='different', channel='whisper', to=b.name)['detail'] == 'request_id_reused'
    decision_id = str(uuid.uuid4())
    first = answer(w, b, replies[0], request_id=decision_id)
    assert answer(w, b, replies[0], request_id=decision_id) == first
    assert answer(w, b, replies[0]) == first


def test_consent_expires_at_utc_midnight_and_expired_rows_are_pruned(world):
    w = world
    a, b = together(w)
    sent = request(w, a, b)
    accepted = answer(w, b, sent)
    w.now[0] = accepted['expires']
    w.visit(b, a)
    w.presence(b)
    assert w.get(b, PATH)['requests'] == []
    assert request(w, a, b)['state'] == 'requested'
    w.tick(601)
    with w.app.state.db.transaction() as conn:
        chat.prune(conn, w.now[0])
        assert conn.execute('SELECT count(*) FROM whisper_requests').fetchone()[0] == 0


def test_request_routes_require_authentication(world):
    assert world.client.get(PATH).status_code == 401
    assert world.client.post(PATH+'/missing/accept', json={'request_id': str(uuid.uuid4())}).status_code == 401


def test_concurrent_distinct_requests_only_create_one_pending_pair(world):
    w = world
    a, b = together(w)
    def send(_):
        return w.client.post('/v1/social/messages', headers=a.headers,
                             json={'request_id': str(uuid.uuid4()), 'text': 'hello', 'channel': 'whisper', 'to': b.name})
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(send, range(2)))
    assert sorted(r.status_code for r in results) == [200, 429]
    assert len(w.get(b, PATH)['requests']) == 1


def test_consent_survives_restart_until_day_expiry(world):
    w = world
    a, b = together(w)
    answer(w, b, request(w, a, b))
    other = World(w.settings.data_dir)
    try:
        other.now[0] = w.now[0]
        assert 'id' in request(other, a, b)
    finally:
        other.close()
