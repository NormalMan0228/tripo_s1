"""Event mail uses the original mailbox and preserves its legacy letter kinds."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings
from server import npc_letters


def mutation(**values):
    return {'request_id': str(uuid.uuid4()), **values}


def timestamp(value):
    return datetime.fromisoformat(value).timestamp()


@pytest.fixture
def world(tmp_path):
    now = [1_800_000_000.0]
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        yield app, client, now


def account(app, client, username):
    response = client.post('/v1/auth/register', json={'username': username, 'password': 'Letters-test-password'})
    assert response.status_code == 200, response.text
    with app.state.db.read() as conn:
        user_id = conn.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()['id']
    return user_id, {'Authorization': 'Bearer ' + response.json()['token']}


def test_event_deduplication_legacy_kinds_and_no_additional_rewards(world):
    app, client, now = world
    user_id, headers = account(app, client, 'alice')
    with app.state.db.transaction() as conn:
        before = tuple(conn.execute('SELECT shards FROM users WHERE id=?', (user_id,)).fetchone())
        objects = conn.execute('SELECT count(*) FROM objects').fetchone()[0]
        for level in (0, 1, 100):
            conn.execute('INSERT INTO npc_letters(id,host_id,npc_id,level,created) VALUES (?,?,?,?,?)',
                         (str(uuid.uuid4()), user_id, 'naru', level, now[0]))
        first = npc_letters.dispatch(conn, user_id, 'naru', 'request_done', 'day1:quest', now[0],
                                     {'quest_id': 'naru_islands', 'type': 'cannot_replace_type'})
        conn.execute('UPDATE npc_letters SET read_at=? WHERE id=?', (now[0], first))
        assert npc_letters.dispatch(conn, user_id, 'naru', 'request_done', 'day1:quest', now[0] + 1,
                                    {'changed': True}) == first
        second = npc_letters.dispatch(conn, user_id, 'naru', 'request_done', 'day2:quest', now[0] + 1)
        assert second != first
        levels = [r[0] for r in conn.execute('SELECT level FROM npc_letters ORDER BY level')]
        assert levels == [0, 1, 100, npc_letters.EVENT_LEVEL_START, npc_letters.EVENT_LEVEL_START + 1]
        assert tuple(conn.execute('SELECT shards FROM users WHERE id=?', (user_id,)).fetchone()) == before
        assert conn.execute('SELECT count(*) FROM objects').fetchone()[0] == objects
        assert conn.execute('SELECT count(*) FROM npc_friendship').fetchone()[0] == 0
    response = client.get('/v1/letters', headers=headers)
    assert response.status_code == 200, response.text
    letters = response.json()['letters']
    event = next(letter for letter in letters if letter['id'] == first)
    assert event['event'] == {'type': 'request_done', 'key': 'day1:quest',
                              'payload': {'quest_id': 'naru_islands', 'type': 'cannot_replace_type'}}
    assert event['read'] and event['created'] == now[0]
    assert event['level'] == 0 and event['gift'] is None and event['quest'] == {'npc': 'naru'}
    assert len([letter for letter in letters if 'story' in letter]) == 1
    assert len([letter for letter in letters if letter['level'] == 1]) == 1
    assert len([letter for letter in letters if 'quest' in letter and 'event' not in letter]) == 1


def test_dispatch_rolls_back_with_event_and_move_hooks_are_distinct(world):
    app, client, now = world
    user_id, headers = account(app, client, 'alice')
    with pytest.raises(RuntimeError):
        with app.state.db.transaction() as conn:
            npc_letters.dispatch(conn, user_id, 'naru', 'request_done', 'rollback', now[0])
            raise RuntimeError('completion failed')
    with app.state.db.transaction() as conn:
        assert conn.execute('SELECT count(*) FROM npc_letters').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM npc_letter_events').fetchone()[0] == 0
        incoming = npc_letters.dispatch(conn, user_id, 'naru', 'move_in', 'residency-1', now[0])
        outgoing = npc_letters.dispatch(conn, user_id, 'naru', 'move_out', 'residency-1', now[0])
        assert incoming != outgoing
        assert npc_letters.dispatch(conn, user_id, 'naru', 'move_in', 'residency-1', now[0]) == incoming
    assert {letter['event']['type'] for letter in client.get('/v1/letters', headers=headers).json()['letters']} == {'move_in', 'move_out'}


def test_anniversary_uses_fixed_server_midnight_and_unread_poll(world):
    app, client, now = world
    now[0] = timestamp('2027-01-08T23:59:59+09:00')
    user_id, headers = account(app, client, 'alice')
    for offset in ('840', '-720'):
        response = client.get('/v1/letters', headers={**headers, 'X-Villagen-UTC-Offset': offset})
        assert response.json() == {'letters': [], 'unread': 0}
    now[0] += 1
    assert client.get('/v1/me', headers=headers).json()['npc_letters_unread'] == 1
    first = client.get('/v1/letters', headers=headers).json()
    assert first['unread'] == 1
    letter = first['letters'][0]
    assert letter['npc'] == 'naru' and letter['level'] == 0 and 'quest' not in letter and 'story' not in letter
    assert letter['event'] == {'type': 'resident_day', 'key': '2027-01-09',
                               'payload': {'date': '2027-01-09', 'occasion': 'village_anniversary'}}
    for offset in ('840', '-720'):
        assert client.get('/v1/letters', headers={**headers, 'X-Villagen-UTC-Offset': offset}).json() == first
    body = mutation(ids=[letter['id']])
    assert client.post('/v1/letters/read', headers=headers, json=body).json() == {'unread': 0}
    assert client.post('/v1/letters/read', headers=headers, json=body).json() == {'unread': 0}
    assert client.get('/v1/me', headers=headers).json()['npc_letters_unread'] == 0


def test_daily_read_all_and_owner_isolation(world):
    app, client, now = world
    now[0] = timestamp('2027-01-09T10:00:00+09:00')
    _, alice = account(app, client, 'alice')
    _, bravo = account(app, client, 'bravo')
    # Read-all is also a delivery trigger: it includes today's letter.
    assert client.post('/v1/letters/read', headers=alice, json=mutation()).json() == {'unread': 0}
    own_letter = client.get('/v1/letters', headers=alice).json()['letters'][0]
    other_letter = client.get('/v1/letters', headers=bravo).json()['letters'][0]
    assert own_letter['read'] and not other_letter['read'] and own_letter['id'] != other_letter['id']
    assert client.post('/v1/letters/read', headers=alice, json=mutation(ids=[other_letter['id']])).json() == {'unread': 0}
    assert client.get('/v1/letters', headers=bravo).json()['unread'] == 1
    assert client.get('/v1/letters').status_code == 401
    assert client.post('/v1/letters/read', json=mutation()).status_code == 401


def test_missed_dates_are_not_replayed_and_next_year_gets_new_letter(world):
    app, client, now = world
    now[0] = timestamp('2027-01-10T10:00:00+09:00')
    _, headers = account(app, client, 'alice')
    assert client.get('/v1/letters', headers=headers).json() == {'letters': [], 'unread': 0}
    now[0] = timestamp('2028-01-09T10:00:00+09:00')
    # Sign in again because the previous session has expired by next year.
    headers = {'Authorization': 'Bearer ' + client.post('/v1/auth/login', json={
        'username': 'alice', 'password': 'Letters-test-password'}).json()['token']}
    first = client.get('/v1/letters', headers=headers).json()['letters'][0]
    now[0] = timestamp('2029-01-09T10:00:00+09:00')
    headers = {'Authorization': 'Bearer ' + client.post('/v1/auth/login', json={
        'username': 'alice', 'password': 'Letters-test-password'}).json()['token']}
    letters = client.get('/v1/letters', headers=headers).json()['letters']
    assert len(letters) == 2 and letters[0]['id'] != first['id']
    assert [letter['event']['key'] for letter in letters] == ['2029-01-09', '2028-01-09']


def test_parallel_daily_reads_deliver_one_letter(world):
    app, client, now = world
    now[0] = timestamp('2027-01-09T10:00:00+09:00')
    _, headers = account(app, client, 'alice')
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.get('/v1/letters', headers=headers), range(8)))
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()['letters'][0]['id'] for response in responses}) == 1
    assert all(response.json()['unread'] == 1 for response in responses)


def test_startup_upgrades_old_mailbox_without_changing_legacy_letters(tmp_path):
    now = 1_800_000_000.0
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, clock=lambda: now, worker_enabled=False)
    with TestClient(app) as client:
        user_id, headers = account(app, client, 'alice')
        with app.state.db.transaction() as conn:
            legacy_id = str(uuid.uuid4())
            conn.execute('INSERT INTO npc_letters(id,host_id,npc_id,level,created) VALUES (?,?,?,?,?)',
                         (legacy_id, user_id, 'naru', 1, now))
            conn.execute('DROP TABLE npc_letter_events')
    app = create_app(settings, clock=lambda: now, worker_enabled=False)
    with TestClient(app) as client:
        letters = client.get('/v1/letters', headers=headers).json()['letters']
        assert len(letters) == 1 and letters[0]['id'] == legacy_id and 'event' not in letters[0]
        with app.state.db.transaction() as conn:
            event_id = npc_letters.dispatch(conn, user_id, 'naru', 'request_done', 'persistent', now)
    app = create_app(settings, clock=lambda: now, worker_enabled=False)
    with TestClient(app) as client:
        with app.state.db.transaction() as conn:
            assert npc_letters.dispatch(conn, user_id, 'naru', 'request_done', 'persistent', now) == event_id
        assert len(client.get('/v1/letters', headers=headers).json()['letters']) == 2


@pytest.mark.parametrize('npc,event,key,payload', [
    ('unknown', 'request_done', 'key', None),
    ('naru', 'unsupported', 'key', None),
    ('naru', 'request_done', '', None),
    ('naru', 'request_done', 'key', []),
])
def test_invalid_internal_events_never_insert_letters(world, npc, event, key, payload):
    app, client, now = world
    user_id, _ = account(app, client, 'alice')
    with app.state.db.transaction() as conn:
        with pytest.raises(ValueError):
            npc_letters.dispatch(conn, user_id, npc, event, key, now[0], payload)
        assert conn.execute('SELECT count(*) FROM npc_letters').fetchone()[0] == 0


def test_dispatch_requires_callers_write_transaction(world):
    app, client, now = world
    user_id, _ = account(app, client, 'alice')
    with app.state.db.read() as conn:
        with pytest.raises(ValueError, match='npc_letter_transaction_required'):
            npc_letters.dispatch(conn, user_id, 'naru', 'request_done', 'key', now[0])
        assert conn.execute('SELECT count(*) FROM npc_letters').fetchone()[0] == 0
