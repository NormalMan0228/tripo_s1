import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.security import clean_text

PASSWORD = 'Testing-only-12345'
WRONG = 'Wrong-password-1'


@pytest.fixture
def world(tmp_path):
    now = [1000000.]
    app = create_app(Settings(data_dir=tmp_path, daily_generation_limit=100), clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        yield app, client, now


def register(c, name, password=PASSWORD):
    return c.post('/v1/auth/register', json={'username': name, 'password': password})


def login(c, name, password=PASSWORD):
    return c.post('/v1/auth/login', json={'username': name, 'password': password})


def bearer(token):
    return {'Authorization': 'Bearer ' + token}


def mutation(**extra):
    return dict(request_id=str(uuid.uuid4()), **extra)


def events(app, kind):
    with app.state.db.read() as db:
        return [dict(r) for r in db.execute('SELECT * FROM security_events WHERE kind=? ORDER BY id', (kind,))]


def user_id(app, name):
    with app.state.db.read() as db:
        return db.execute('SELECT id FROM users WHERE username=?', (name,)).fetchone()[0]


# 1. Login brute-force protection ------------------------------------------------

def test_five_failures_lock_the_username_for_fifteen_minutes(world):
    app, c, now = world
    assert register(c, 'alice').status_code == 200
    for _ in range(5):
        r = login(c, 'alice', WRONG)
        assert r.status_code == 401 and r.json()['detail'] == 'invalid_credentials'
    locked = login(c, 'alice')  # Even the right password is refused while locked.
    assert locked.status_code == 429 and locked.json() == {'detail': 'login_locked'}
    assert 0 < int(locked.headers['retry-after']) <= 900
    # The lock is per username: other accounts keep working.
    assert register(c, 'bob').status_code == 200 and login(c, 'bob').status_code == 200
    now[0] += 899
    assert login(c, 'alice').json()['detail'] == 'login_locked'
    now[0] += 1
    assert login(c, 'alice').status_code == 200
    failed = events(app, 'login_failed')
    assert len(failed) == 5 and all(e['user_id'] == user_id(app, 'alice') for e in failed)
    assert json.loads(failed[0]['detail'])['username'] == 'alice'
    assert len(events(app, 'login_locked')) == 2


def test_successful_login_resets_the_failure_count(world):
    app, c, now = world
    register(c, 'alice')
    for _ in range(4):
        assert login(c, 'alice', WRONG).status_code == 401
    assert login(c, 'alice').status_code == 200
    for _ in range(4):
        assert login(c, 'alice', WRONG).status_code == 401
    assert login(c, 'alice').status_code == 200  # Would be locked without the reset.
    with app.state.db.read() as db:
        assert db.execute("SELECT count(*) FROM login_attempts WHERE username='alice'").fetchone()[0] == 0


def test_failures_spread_beyond_the_window_do_not_lock(world):
    app, c, now = world
    register(c, 'alice')
    for _ in range(4):
        assert login(c, 'alice', WRONG).status_code == 401
    now[0] += 901
    for _ in range(4):
        assert login(c, 'alice', WRONG).status_code == 401
    assert login(c, 'alice').status_code == 200
    # Stale attempt rows are purged once they can no longer affect any lock.
    assert login(c, 'ghost', WRONG).status_code == 401
    now[0] += 1801
    assert login(c, 'other', WRONG).status_code == 401
    with app.state.db.read() as db:
        assert db.execute("SELECT count(*) FROM login_attempts WHERE username='ghost'").fetchone()[0] == 0


def test_unknown_usernames_are_indistinguishable_and_still_hashed(world, monkeypatch):
    app, c, now = world
    register(c, 'alice')
    calls = []
    original = PasswordHasher.verify
    monkeypatch.setattr(PasswordHasher, 'verify', lambda self, *a: calls.append(1) or original(self, *a))
    replies = {}
    for name in ('alice', 'ghost'):
        replies[name] = [login(c, name, WRONG) for _ in range(6)]
        assert [(r.status_code, r.json()) for r in replies[name]] == \
            [(401, {'detail': 'invalid_credentials'})] * 5 + [(429, {'detail': 'login_locked'})]
    # Both names ran the (dummy) hash for every unlocked attempt and none while locked.
    assert len(calls) == 10
    for a, b in zip(replies['alice'], replies['ghost']):
        assert sorted(a.headers.keys()) == sorted(b.headers.keys())
    assert [e['user_id'] for e in events(app, 'login_failed')][5:] == [None] * 5


def test_parallel_guesses_cannot_exceed_the_limit(world):
    app, c, now = world
    register(c, 'alice')
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: login(c, 'alice', WRONG).status_code, range(10)))
    assert sorted(codes) == [401] * 5 + [429] * 5


# 2. Session hygiene ---------------------------------------------------------------

def test_sessions_are_capped_purged_and_logout_still_works(world):
    app, c, now = world
    bob = register(c, 'bob').json()['token']
    tokens = [register(c, 'alice').json()['token']] + [login(c, 'alice').json()['token'] for _ in range(6)]
    assert [c.get('/v1/me', headers=bearer(t)).status_code for t in tokens] == [401, 401, 200, 200, 200, 200, 200]
    assert c.get('/v1/me', headers=bearer(bob)).status_code == 200  # Other accounts are untouched.
    with app.state.db.read() as db:
        assert db.execute('SELECT count(*) FROM sessions WHERE user_id=?', (user_id(app, 'alice'),)).fetchone()[0] == 5
    assert c.post('/v1/auth/logout', headers=bearer(tokens[-1])).json() == {'ok': True}
    assert c.get('/v1/me', headers=bearer(tokens[-1])).status_code == 401
    assert c.get('/v1/me', headers=bearer(tokens[-2])).status_code == 200
    now[0] += app.state.settings.session_seconds + 1
    fresh = login(c, 'bob').json()['token']
    with app.state.db.read() as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 1
    assert c.get('/v1/me', headers=bearer(fresh)).status_code == 200


# 3. Reserved usernames -------------------------------------------------------------

def test_staff_looking_names_are_reserved_but_operators_still_log_in(world):
    app, c, now = world
    for name in ('admin', 'Administrator', 'ROOT_user', 'gm7', 'Operator', 'system_bot', 'MODERATOR', 'polytech1', 'PolyTech9'):
        r = register(c, name)
        assert (r.status_code, r.json()) == (422, {'detail': 'username_reserved'}), name
    for name in ('bob_admin', 'groot', 'agm'):  # Only a leading prefix is reserved.
        assert register(c, name).status_code == 200, name
    assert [json.loads(e['detail'])['username'] for e in events(app, 'register')] == ['bob_admin', 'groot', 'agm']
    # Operator accounts are provisioned directly (tools/admin_accounts.py) and log in as usual.
    hashed = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1).hash('operator-only-pw')
    with app.state.db.transaction() as db:
        db.execute("INSERT INTO users(id,username,password_hash,shards,created,role) VALUES (?,?,?,?,?,'admin')",
                   (str(uuid.uuid4()), 'polytech1', hashed, 0, now[0]))
    r = login(c, 'PolyTech1', 'operator-only-pw')
    assert r.status_code == 200 and r.json()['role'] == 'admin'


# 4. Security response headers ------------------------------------------------------

def test_security_headers_on_every_response_including_models(world):
    app, c, now = world
    h = bearer(register(c, 'alice').json()['token'])
    item = c.get('/v1/me', headers=h).json()['objects'][0]
    responses = {
        'health': c.get('/health'),
        'me': c.get('/v1/me', headers=h),
        'invalid': c.post('/v1/auth/login', json={}),
        'too_large': c.post('/v1/auth/login', content=b'x' * 9000),
        'admin': c.post('/v1/admin/grant', headers=h, json=mutation(shards=1)),
        'missing': c.get('/v1/nowhere'),
        'model': c.get('/v1/objects/' + item['id'] + '/model', headers=h),
    }
    for _ in range(25):
        limited = c.post('/v1/auth/logout')
        if limited.status_code == 429:
            break
    responses['rate_limited'] = limited
    assert limited.json() == {'detail': 'rate_limited'}
    for name, r in responses.items():
        assert r.headers.get_list('x-content-type-options') == ['nosniff'], name
        assert r.headers.get_list('x-frame-options') == ['DENY'], name
        assert r.headers.get_list('referrer-policy') == ['no-referrer'], name
        assert r.headers.get_list('cache-control') == ['no-store'], name
    model = responses['model']
    assert model.status_code == 200 and model.content[:4] == b'glTF'
    assert model.headers['content-type'] == 'model/gltf-binary'
    assert responses['too_large'].status_code == 413 and responses['admin'].status_code == 403


# 5. Security events and the admin grant cap ---------------------------------------

def test_admin_grants_are_capped_per_utc_day_and_logged(world):
    app, c, now = world
    h = bearer(register(c, 'opsuser').json()['token'])
    assert events(app, 'register')[0]['user_id'] == user_id(app, 'opsuser')
    with app.state.db.transaction() as db:
        db.execute("UPDATE users SET role='admin' WHERE username='opsuser'")
    first = mutation(shards=100000)
    grant = lambda **kw: c.post('/v1/admin/grant', headers=h, json=mutation(**kw))
    assert c.post('/v1/admin/grant', headers=h, json=first).status_code == 200
    assert grant(shards=99999, coins=5).status_code == 200
    over = grant(shards=2)
    assert (over.status_code, over.json()) == (429, {'detail': 'admin_grant_limit'})
    assert grant(shards=1).status_code == 200  # Exactly 200000 today.
    assert grant(coins=100).status_code == 200  # Leaf coins are not Starseeds.
    assert c.post('/v1/admin/grant', headers=h, json=first).status_code == 200  # Idempotent replay.
    assert c.get('/v1/me', headers=h).json()['shards'] == 80 + 200000
    logged = events(app, 'admin_grant')
    assert len(logged) == 4 and {e['user_id'] for e in logged} == {user_id(app, 'opsuser')}
    assert json.loads(logged[0]['detail']) == {'shards': 100000, 'coins': 0, 'request_id': first['request_id']}
    with app.state.db.read() as db:
        assert db.execute("SELECT count(*) FROM ledger WHERE reason='admin_grant'").fetchone()[0] == 3
    now[0] = (now[0] // 86400 + 1) * 86400  # Next UTC day.
    assert grant(shards=100000).status_code == 200


# 6. Chat and display-name sanitising ----------------------------------------------

def test_clean_text_strips_controls_and_bidi_but_keeps_text():
    assert clean_text('hi‮\x07 there⁦!\x7f') == 'hi there!'
    assert clean_text(' ‏‪ \x85ok\t\n ') == 'ok'
    assert clean_text('모닥불로 모이세요 🔥') == '모닥불로 모이세요 🔥'


def test_chat_messages_are_sanitised_and_rejected_when_empty(world):
    app, c, now = world
    h = bearer(register(c, 'alice').json()['token'])
    assert c.post('/v1/social/messages', headers=h, json=mutation(text='hi‮\x07 there⁦!')).status_code == 200
    assert [m['text'] for m in c.get('/v1/social', headers=h).json()['messages']] == ['hi there!']
    now[0] += 2
    empty = c.post('/v1/social/messages', headers=h, json=mutation(text='‮\x1b⁧ \r\n'))
    assert (empty.status_code, empty.json()) == (422, {'detail': 'message_empty'})
    assert len(c.get('/v1/social', headers=h).json()['messages']) == 1


def test_generated_object_names_drop_control_characters(world):
    app, c, now = world
    h = bearer(register(c, 'alice').json()['token'])
    job = c.post('/v1/generations', headers=h, json=mutation(prompt='red ‮stool\x07 chair')).json()
    asyncio.run(app.state.process_job(job['id']))
    names = [o['name'] for o in c.get('/v1/me', headers=h).json()['objects']]
    assert '샘플 · red stool chair' in names
