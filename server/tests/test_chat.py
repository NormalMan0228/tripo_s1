"""Chat v2 (server/chat.py) and the presence migration (server/multiplayer.py)."""
import json
import sqlite3
import pytest
from server.tests.social_world import World
from server import chat as chat_module


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


@pytest.fixture
def make_world(tmp_path):
    made = []

    def make(**overrides):
        made.append(World(tmp_path/str(len(made)), **overrides))
        return made[-1]
    yield make
    for w in made:
        w.close()


def chat_of(w, who, since=0, **body):
    return w.presence(who, since=since, **body)['chat']


def texts(block):
    return [line['text'] for line in block['lines']]


def test_released_clients_keep_the_old_messages_field_and_room(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    w.visit(bravo, alice)
    assert w.say(alice, 'hello')['ok']
    old = w.presence(bravo)
    assert 'chat' not in old and 'social' not in old
    assert [set(m) for m in old['messages']] == [{'id', 'username', 'text', 'created'}]
    assert old['messages'][0]['username'] == 'alice' and old['messages'][0]['text'] == 'hello'
    # No channel: the party room when in a party, as before chat v2.
    w.call(alice, '/v1/party')
    w.say(alice, 'party line')
    assert [m['text'] for m in w.get(alice, '/v1/social')['messages']] == ['party line']
    assert [m['text'] for m in w.presence(bravo)['messages']] == ['hello']


def test_cursor_history_then_only_newer_lines(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    w.visit(bravo, alice)
    for text in ('one', 'two', 'three'):
        w.say(alice, text, channel='local')
    first = chat_of(w, bravo, since=0)
    assert first['history'] and texts(first) == ['one', 'two', 'three'] and not first['more']
    assert first['lines'][0]['channel'] == 'local' and first['lines'][0]['username'] == 'alice'
    w.say(bravo, 'four', channel='local')
    later = chat_of(w, bravo, since=first['cursor'])
    assert not later['history'] and texts(later) == ['four']
    assert texts(chat_of(w, bravo, since=later['cursor'])) == [] and chat_of(w, bravo, since=later['cursor'])['cursor'] == later['cursor']
    # A cursor from a newer database (a restored backup) starts over with history.
    assert chat_of(w, bravo, since=later['cursor']+1000)['history']


def test_history_and_delivery_are_bounded_and_old_lines_never_come(world):
    w = world
    alice = w.player('alice')
    with w.db() as conn:
        for i in range(80):
            conn.execute("INSERT INTO mp_messages(room,user_id,text,created,channel) VALUES (?,?,?,?,'local')", ('village:'+alice.id, alice.id, 'line %d' % i, w.now[0]-3700+i*0 if i < 5 else w.now[0]))
    history = chat_of(w, alice, since=0)
    assert len(history['lines']) == chat_module.HISTORY_LINES and history['lines'][-1]['text'] == 'line 79'
    page = chat_of(w, alice, since=1)
    assert len(page['lines']) == chat_module.DELIVERY_LINES and page['more']
    assert page['lines'][0]['text'] == 'line 5'  # lines 0..4 are over an hour old
    rest = chat_of(w, alice, since=page['cursor'])
    assert texts(rest)[-1] == 'line 79' and not rest['more'] and len(rest['lines']) == 75-chat_module.DELIVERY_LINES


def test_channels_merge_in_order_and_stay_private(world):
    w = world
    alice, bravo, charlie, delta = w.players('alice', 'bravo', 'charlie', 'delta')
    w.visit(bravo, alice)
    w.call(alice, '/v1/party')
    invite = w.call(alice, '/v1/social/invites', username='charlie', kind='party')
    w.call(charlie, '/v1/social/invites/'+invite['id']+'/accept')
    w.befriend(alice, delta)
    w.presence(delta, scene='away')
    w.say(alice, 'village hi', channel='local')
    w.say(alice, 'party hi', channel='party')
    w.say(delta, 'everyone hi', channel='global')
    w.say(alice, 'psst', channel='whisper', to='delta')
    seen = {p.name: chat_of(w, p, since=0) for p in (alice, bravo, charlie, delta)}
    assert texts(seen['alice']) == ['village hi', 'party hi', 'everyone hi', 'psst']
    assert [l['channel'] for l in seen['alice']['lines']] == ['local', 'party', 'global', 'whisper']
    assert texts(seen['bravo']) == ['village hi', 'everyone hi']
    assert texts(seen['charlie']) == ['party hi', 'everyone hi']  # charlie's village is his own
    assert texts(seen['delta']) == ['everyone hi', 'psst']
    whisper = seen['delta']['lines'][-1]
    assert whisper['to_name'] == 'delta' and whisper['username'] == 'alice'


def test_channel_errors(make_world):
    w = make_world(global_chat=False)
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    assert w.say(alice, 'x', 409, channel='party')['detail'] == 'not_in_party'
    assert w.say(alice, 'x', 403, channel='global')['detail'] == 'global_chat_off'
    assert w.get(alice, '/health')['global_chat'] is False
    # Not a friend, offline friend, unknown name, self, blocked: one answer.
    w.presence(bravo)
    assert w.say(alice, 'x', 404, channel='whisper', to='bravo')['detail'] == 'whisper_target_unavailable'
    w.befriend(alice, charlie)
    assert w.say(alice, 'x', 404, channel='whisper', to='charlie')['detail'] == 'whisper_target_unavailable'
    w.presence(charlie)
    assert w.say(alice, 'ok now', channel='whisper', to='charlie')['ok']
    for name in ('nobody_here', 'alice'):
        assert w.say(alice, 'x', 404, channel='whisper', to=name)['detail'] == 'whisper_target_unavailable'
    assert w.say(alice, 'x', 404, channel='whisper')['detail'] == 'whisper_target_unavailable'
    w.call(charlie, '/v1/social/prefs', appear_offline=True)
    assert w.say(alice, 'x', 404, channel='whisper', to='charlie')['detail'] == 'whisper_target_unavailable'


def test_rate_limits(make_world):
    w = make_world(chat_ip_per_minute=12)
    alice, bravo = w.players('alice', 'bravo')
    assert w.call(alice, '/v1/social/messages', text='a1')['ok']
    response = w.client.post('/v1/social/messages', headers=alice.headers, json={'request_id': '00000000-0000-4000-8000-000000000001', 'text': 'a2'})
    assert response.status_code == 429 and response.json()['detail'] == 'message_rate_limited' and response.headers['retry-after'] == '1'
    for i in range(4):
        w.say(alice, 'b%d' % i)
    assert w.say(alice, 'burst', 429)['detail'] == 'message_rate_limited'  # 5 lines in 10 s
    w.tick(10)
    w.say(alice, 'same')
    assert w.say(alice, 'same', 429)['detail'] == 'message_repeated'
    w.tick(30)
    w.say(alice, 'same')
    w.say(alice, 'to everyone', channel='global')
    assert w.say(alice, 'again everyone', 429, channel='global')['detail'] == 'global_chat_slow'
    # One address (a school shares one): 12 lines a minute here.
    for i in range(4):
        w.say(bravo, 'c%d' % i)
    assert w.say(bravo, 'over', 429)['detail'] == 'chat_ip_limited'


def test_the_whole_server_everyone_channel_has_a_ceiling(make_world):
    w = make_world(chat_ip_per_minute=1000)
    people = w.players(*('p%02d' % i for i in range(22)))
    results = [w.call(p, '/v1/social/messages', 200 if i < chat_module.GLOBAL_SERVER_LINES else 429, text='hi %d' % i, channel='global')
               for i, p in enumerate(people)]
    assert results[-1]['detail'] == 'global_chat_busy'


def test_filter_masks_lines_and_mutes_after_three(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    w.visit(bravo, alice)
    sent = w.say(alice, '아 시 발 진짜', channel='local')
    assert sent['masked'] and sent['text'] == '아 * * 진짜'
    assert texts(chat_of(w, bravo))[-1] == '아 * * 진짜'
    # A match split by a space is masked but does not count towards the mute.
    w.say(alice, 'ㅅㅂ 또', channel='local')
    assert 'muted_until' not in w.say(alice, 'fuck', channel='local')
    third = w.say(alice, 'shit 또', channel='local')
    assert third['muted_until'] == pytest.approx(w.now[0]+300)
    w.tick(2)
    response = w.client.post('/v1/social/messages', headers=alice.headers, json={'request_id': '00000000-0000-4000-8000-000000000002', 'text': '안녕'})
    assert response.status_code == 403 and response.json()['detail'] == 'chat_muted' and int(response.headers['retry-after']) > 290
    assert w.presence(alice, since=0)['social']['muted_until'] == pytest.approx(third['muted_until'])
    w.tick(300)
    assert w.say(alice, '안녕')['ok']
    with w.db() as conn:
        assert conn.execute("SELECT count(*) FROM security_events WHERE kind='chat_auto_mute'").fetchone()[0] == 1


def test_school_phrases_are_never_masked_and_never_mute(world):
    w = world
    alice = w.player('alice')
    for i, text in enumerate(['몇 시 발표야?', '국어 시 발표 언제야', '이 시 발표해', '지금 몇 시 발견했어', '씨 발라', '우리 개 새끼 낳았어']):
        sent = w.say(alice, text, channel='local')
        assert not sent['masked'] and sent['text'] == text and 'muted_until' not in sent
        w.tick(5)
    for _ in range(3):
        w.tick(31)
        assert not w.say(alice, '몇 시 발표야?', channel='local')['masked']
    with w.db() as conn:
        assert conn.execute("SELECT count(*) FROM security_events WHERE kind IN ('chat_masked','chat_auto_mute')").fetchone()[0] == 0


def test_a_retried_line_is_kept_once_and_chat_writes_no_request_or_audit_rows(world):
    w = world
    alice = w.player('alice')
    with w.db() as conn:
        before = [conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('requests', 'audit')]
    body = {'request_id': '00000000-0000-4000-8000-0000000000aa', 'text': '모닥불로 모이세요'}
    first = w.client.post('/v1/social/messages', headers=alice.headers, json=body).json()
    again = w.client.post('/v1/social/messages', headers=alice.headers, json=body).json()
    assert first == again and first['id']
    assert w.client.post('/v1/social/messages', headers=alice.headers, json={**body, 'text': 'other'}).json()['detail'] == 'request_id_reused'
    with w.db() as conn:
        assert conn.execute('SELECT count(*) FROM mp_messages').fetchone()[0] == 1
        assert [conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('requests', 'audit')] == before


def test_blocks_hide_chat_both_ways(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    w.visit(bravo, alice)
    w.visit(charlie, alice)
    w.say(bravo, 'from bravo', channel='local')
    w.say(charlie, 'from charlie', channel='local')
    w.call(charlie, '/v1/social/blocks', user_id=bravo.id)
    assert texts(chat_of(w, charlie)) == ['from charlie']
    assert texts(chat_of(w, bravo)) == ['from bravo']
    assert texts(chat_of(w, alice)) == ['from bravo', 'from charlie']
    assert [m['text'] for m in w.presence(bravo)['messages']] == ['from bravo']  # released clients too
    players = {p['username'] for p in w.presence(charlie, x=1)['village']['players']}
    assert 'bravo' not in players and 'alice' in players


def test_operators_remove_lines_and_mute(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    boss = w.player('teacher_x', role='admin')
    w.visit(bravo, alice)
    line = w.say(alice, 'bad line', channel='local')
    cursor = chat_of(w, bravo)['cursor']
    assert w.refused(alice, '/v1/admin/chat/delete', 403, message_ids=[line['id']]) == 'admin_only'
    assert w.call(boss, '/v1/admin/chat/delete', message_ids=[line['id']])['removed'] == 1
    block = chat_of(w, bravo, since=cursor)
    assert block['removed'] == [line['id']] and texts(chat_of(w, bravo)) == []
    w.call(boss, '/v1/admin/chat/mute', user_id=alice.id, minutes=10)
    assert w.say(alice, 'hi', 403)['detail'] == 'chat_muted'
    w.call(boss, '/v1/admin/chat/mute', user_id=alice.id, minutes=0)
    assert w.say(alice, 'hi')['ok']
    w.tick(chat_module.REMOVAL_SECONDS+1)
    assert 'removed' not in chat_of(w, bravo, since=cursor)


def test_retention_keeps_social_tables_bounded(world):
    w = world
    alice = w.player('alice')
    old = w.now[0]-40*86400
    with w.db() as conn:
        for op in ('social_message', 'social_invite', 'invite:x:accept', 'friend_answer:y:accept', 'friend_request', 'studio_job', 'claim:z'):
            conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)', (alice.id, op+'-id', op, 'f', '{}', old))
            conn.execute('INSERT INTO audit(user_id,action,target,outcome,created) VALUES (?,?,?,?,?)', (alice.id, op, None, 'accepted', old))
        conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)', (alice.id, 'fresh', 'social_invite', 'f', '{}', w.now[0]))
        conn.execute("INSERT INTO mp_messages(room,user_id,text,created) VALUES ('village:x',?,'old',?)", (alice.id, w.now[0]-25*3600))
        conn.execute("INSERT INTO mp_invites VALUES ('i1',?,?,'village',NULL,'accept',?,?)", (alice.id, alice.id, old, old))
        conn.execute("INSERT INTO social_requests VALUES ('r1',?,?,'declined',?,?)", (alice.id, alice.id, old, old))
        conn.execute("INSERT INTO social_requests VALUES ('r2',?,?,'pending',?,?)", (alice.id, alice.id, old, old))
    removed = w.app.state.multiplayer.chat.maybe_prune()
    assert removed['requests'] == 5 and removed['audit'] == 5 and removed['mp_messages'] == 1 and removed['mp_invites'] == 1
    with w.db() as conn:
        assert sorted(r[0] for r in conn.execute('SELECT operation FROM requests')) == ['claim:z', 'social_invite', 'studio_job']
        assert sorted(r[0] for r in conn.execute('SELECT action FROM audit')) == ['claim:z', 'studio_job']
        assert [tuple(r) for r in conn.execute('SELECT id,state FROM social_requests')] == [('r2', 'expired')]
    assert w.app.state.multiplayer.chat.maybe_prune() is None  # at most every PRUNE_SECONDS
    w.tick(chat_module.PRUNE_SECONDS)
    assert w.app.state.multiplayer.chat.maybe_prune() is not None


def test_chat_delivery_reads_after_the_presence_write_committed(world, monkeypatch):
    w = world
    alice = w.player('alice')
    chat = w.app.state.multiplayer.chat
    original, free = chat.deliver, []

    def deliver(conn, *args):
        probe = sqlite3.connect(w.settings.data_dir/'world.sqlite3', timeout=0, isolation_level=None)
        try:
            probe.execute('BEGIN IMMEDIATE')
            probe.execute('ROLLBACK')
            free.append(True)
        except sqlite3.OperationalError:
            free.append(False)
        finally:
            probe.close()
        return original(conn, *args)
    monkeypatch.setattr(chat, 'deliver', deliver)
    assert w.presence(alice, since=0)['chat']['history']
    assert free == [True]


def test_presence_migration_from_a_released_world_is_safe_and_repeatable(tmp_path):
    # The 0.11.5 tables, with a player and a line in them.
    from server.database import Database
    Database(tmp_path/'world.sqlite3', 'demo')
    with sqlite3.connect(tmp_path/'world.sqlite3') as conn:
        conn.executescript('''
CREATE TABLE mp_presence (user_id TEXT PRIMARY KEY REFERENCES users(id), host_id TEXT NOT NULL REFERENCES users(id),
 scene TEXT NOT NULL, x REAL NOT NULL, z REAL NOT NULL, y REAL NOT NULL DEFAULT 0, yaw REAL NOT NULL, seen REAL NOT NULL,
 vx REAL NOT NULL DEFAULT 0, vz REAL NOT NULL DEFAULT 0, ct REAL);
CREATE TABLE mp_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id),
 text TEXT NOT NULL, created REAL NOT NULL);
INSERT INTO users(id,username,password_hash,shards,created) VALUES ('u1','olduser','x',0,1);
INSERT INTO mp_presence VALUES ('u1','u1','village',1,2,0,0,999999,0,0,NULL);
INSERT INTO mp_messages(room,user_id,text,created) VALUES ('village:u1','u1','old line',999999);''')
    for _ in range(2):
        w = World(tmp_path)
        with w.db() as conn:
            assert {'place', 'floor', 'ix'} <= {r[1] for r in conn.execute('PRAGMA table_info(mp_presence)')}
            assert {'channel', 'to_id', 'request_id'} <= {r[1] for r in conn.execute('PRAGMA table_info(mp_messages)')}
            assert tuple(conn.execute('SELECT x,z FROM mp_presence').fetchone()) == (1, 2)
            assert tuple(conn.execute('SELECT text,channel FROM mp_messages').fetchone()) == ('old line', None)
            assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name IN ('social_friends','social_blocks','social_prefs','social_requests','social_reports')").fetchone()[0] == 5
        w.close()


def test_new_presence_fields_and_the_422_that_names_them(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    w.visit(bravo, alice)
    sitting = {'k': 'seat', 'p': 'hold', 'c': 'sit_basic', 't0': 12.5, 'o': 'obj:1234', 's': 'seat_0', 'h': .05}
    reply = w.presence(bravo, since=0, place='village', ix=sitting)
    assert set(reply['social']) == {'v', 'requests', 'knocks', 'friends_online', 'poll'} and 'messages' not in reply
    seen = {p['username']: p for p in w.presence(alice, place='village')['village']['players']}
    assert seen['bravo']['ix'] == sitting and 'ix' not in seen['alice']
    w.presence(bravo)
    assert 'ix' not in {p['username']: p for p in w.presence(alice)['village']['players']}['bravo']
    bad = w.client.post('/v1/social/presence', headers=bravo.headers, json={'since': 0, 'ix': {'k': 'Seat!', 'p': 'hold', 't0': 1}})
    assert bad.status_code == 422 and bad.json() == {'detail': 'invalid_request', 'fields': ['ix']}
    unknown = w.client.post('/v1/social/presence', headers=bravo.headers, json={'mood': 'happy', 'place': 'moon'})
    assert unknown.json()['fields'] == ['mood', 'place']


def test_health_advertises_the_social_layer(world):
    health = world.client.get('/health').json()
    assert health['multiplayer_protocol'] == 1
    assert set(health['social_features']) == {'chat2', 'place', 'people', 'friends', 'visit', 'report'}
    assert health['global_chat'] is True and health['interaction_sync'] == 1
    assert health['social_poll'] == {'presence_together': .25, 'presence_alone': 1, 'people': 5, 'presence_budget': 60}


def test_presence_advice_slows_clients_down_under_load_and_recovers(make_world):
    w = make_world(presence_budget=10)
    people = w.players(*('p%02d' % i for i in range(10)))
    assert w.presence(people[0], since=0)['social']['poll'] == {'together': .25, 'alone': 1}
    for step in range(240):                # ten players at 4 Hz (40 polls a second) for six seconds
        w.tick(.025)
        advice = w.presence(people[step % 10], since=0)['social']['poll']
    assert advice['together'] >= .25*3 and advice['alone'] <= 4 and advice['together'] <= 1
    for _ in range(6):                     # one poll every two seconds
        w.tick(2.01)
        advice = w.presence(people[0], since=0)['social']['poll']
    assert advice == {'together': .25, 'alone': 1}


def test_presence_advice_ignores_strangers_one_greedy_account_and_released_clients(make_world):
    w = make_world(presence_budget=10)
    alice, bravo = w.players('alice', 'bravo')
    # A script without an account: every poll is refused and none is counted.
    for _ in range(300):
        w.tick(.01)
        response = w.client.post('/v1/social/presence', headers={'Authorization': 'Bearer nope'}, json={'since': 0})
        assert response.status_code == 401
    # One account polling at 50 Hz counts as one player at the advised 4 Hz.
    for _ in range(300):
        w.tick(.02)
        w.presence(alice, since=0)
    # Released clients (no since) ignore the advice: their fixed 4 Hz does not count either.
    for _ in range(300):
        w.tick(.02)
        w.presence(bravo)
    assert w.presence(alice, since=0)['social']['poll'] == {'together': .25, 'alone': 1}
    assert w.app.state.friends.meter.factor == 1.0
