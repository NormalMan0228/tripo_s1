"""Eight player characters (m1..m4, f1..f4): one saved look shared by new games, 0.11.8 games and old worlds."""
import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from server.app import create_app, digest
from server.config import Settings
from server.tests.test_api import account as signed_in, mutation, world

# These tests play a game with the character select screen (0.11.9+); 0.11.8 saves are tested apart.
NEW_GAME = {'x-villagen-version': '0.11.9'}


def account(client, *args, **kwargs):
    return {**signed_in(client, *args, **kwargs), **NEW_GAME}


CHARACTERS = ['m1', 'm2', 'm3', 'm4', 'f1', 'f2', 'f3', 'f4']
DEFAULT = {
    'character': 'f1', 'hair': '#30595b', 'skin': '#e4b587', 'coat': '#dba448', 'pants': '#526552',
    'boots': '#765744', 'accent': '#765744', 'headwear': 'none', 'backpack': True,
}
PARTS = ['hair', 'skin', 'coat', 'pants', 'boots', 'accent']
HEADWEAR = ['none', 'cap', 'beret', 'straw']
RETIRED = {'character_id', 'top', 'bottom', 'shoes', 'accessory', 'hat'}


def profile(client, headers):
    response = client.get('/v1/profile', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def save(client, headers, version, **avatar):
    response = client.post('/v1/profile', headers=headers, json=mutation(version=version, avatar=avatar))
    assert response.status_code == 200, response.text
    assert set(response.json()['avatar']) == set(DEFAULT)
    return response.json()


def test_default_profile_is_shared_by_all_account_endpoints(world):
    app, client, now = world
    credentials = {'username': 'newwalker', 'password': 'Testing-only-12345'}
    registered = client.post('/v1/auth/register', json=credentials)
    assert registered.status_code == 200, registered.text
    headers = {'Authorization': 'Bearer ' + registered.json()['token']}
    expected = registered.json()['profile']
    assert set(expected) == {'avatar', 'version', 'needs_character_select'}
    assert expected == {'avatar': DEFAULT, 'version': 0, 'needs_character_select': True}
    assert not RETIRED & set(expected['avatar'])
    assert profile(client, headers) == expected
    assert client.get('/v1/me', headers=headers).json()['profile'] == expected
    assert client.get('/v1/studio', headers=headers).json()['profile'] == expected
    assert client.post('/v1/auth/login', json=credentials).json()['profile'] == expected
    # The /v1/me catalog lists the same eight ids (0.11.8 games read it, new games use /v1/avatar/catalog).
    choices = client.get('/v1/me', headers=headers).json()['catalog']['characters']
    assert [choice['id'] for choice in choices] == CHARACTERS and all(choice['name'] for choice in choices)
    assert client.get('/v1/profile').status_code == 401


def test_health_announces_the_avatar_contract_and_the_eight_characters(world):
    app, client, now = world
    health = client.get('/health').json()
    assert health['avatar_v2'] == 1 and health['characters'] == CHARACTERS


def test_avatar_catalog_needs_no_sign_in_and_every_default_look_saves(world):
    app, client, now = world
    response = client.get('/v1/avatar/catalog')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['headwear'] == HEADWEAR and data['parts'] == PARTS
    assert [card['id'] for card in data['characters']] == CHARACTERS
    headers = account(client, 'catalogwalker')
    assert client.get('/v1/avatar/catalog', headers=headers).json() == data
    for version, card in enumerate(data['characters']):
        assert set(card) == {'id', 'name', 'description', 'defaults'}
        assert isinstance(card['name'], str) and card['name'] and isinstance(card['description'], str)
        defaults = card['defaults']
        assert set(defaults) == set(DEFAULT) and defaults['character'] == card['id']
        assert defaults['headwear'] in HEADWEAR and isinstance(defaults['backpack'], bool)
        # A starting look is a valid save as it is: the selection screen can send it unchanged.
        saved = save(client, headers, version, **defaults)
        assert saved['avatar'] == defaults and saved['needs_character_select'] is False


@pytest.mark.parametrize('character', CHARACTERS)
def test_all_eight_characters_take_any_hex_colors_the_accent_and_straw(world, character):
    app, client, now = world
    headers = account(client, 'character_' + character)
    avatar = dict(character=character, hair='#012345', skin='#AbCdEf', coat='#123456', pants='#abcdef',
                  boots='#FEDCBA', accent='#987654', headwear='straw', backpack=False)
    result = save(client, headers, 0, **avatar)
    assert result == {'avatar': avatar, 'version': 1, 'needs_character_select': False}
    assert profile(client, headers) == result


def test_cap_and_straw_are_different_hats(world):
    app, client, now = world
    headers = account(client, 'hatwalker')
    for version, hat in enumerate(['cap', 'straw', 'beret', 'none', 'cap']):
        assert save(client, headers, version, headwear=hat)['avatar']['headwear'] == hat
    assert profile(client, headers)['avatar'] == dict(DEFAULT, headwear='cap')


@pytest.mark.parametrize('field', PARTS)
def test_every_color_requires_a_six_digit_hex_value(world, field):
    app, client, now = world
    headers = account(client, 'badcolor')
    before = profile(client, headers)
    for value in ('#abc', '123456', '#12345678', '#12xz45', '#123456\n', '#123456 ', '', None, 2, True):
        response = client.post('/v1/profile', headers=headers, json=mutation(version=0, avatar={field: value}))
        assert response.status_code == 422, (field, value, response.text)
        assert response.json()['detail'] == 'invalid_request'
    assert profile(client, headers) == before


@pytest.mark.parametrize('avatar', [
    {'character': 'm5'}, {'character': 'F1'}, {'character': None}, {'character': ''}, {'character': 'unknown'},
    {'character': 'res://private.glb'}, {'headwear': 'crown'}, {'headwear': 'Straw'}, {'headwear': None},
    {'backpack': 'false'}, {'backpack': 0}, {'backpack': 1}, {'backpack': None}, {'accent': None},
    {'owner_id': 'another-player'}, {'needs_character_select': False}, {'colors': {'hair': '#123456'}},
    # The names Codex drafted are not part of the contract: no aliases, a plain unknown field.
    {'character_id': 'm2'}, {'top': '#123456'}, {'bottom': '#123456'}, {'shoes': '#123456'},
    {'accessory': '#123456'}, {'hat': 'straw'}, {'character': 'm2', 'top': '#123456'},
])
def test_invalid_values_and_unknown_fields_are_refused(world, avatar):
    app, client, now = world
    headers = account(client, 'invalidlook')
    response = client.post('/v1/profile', headers=headers, json=mutation(version=0, avatar=avatar))
    assert response.status_code == 422, response.text
    assert response.json()['detail'] == 'invalid_request'
    assert profile(client, headers) == {'avatar': DEFAULT, 'version': 0, 'needs_character_select': True}


@pytest.mark.parametrize('legacy,expected', [('explorer_b', 'f1'), ('ranger', 'f1'), ('explorer', 'm1'), ('tinker', 'm1')])
def test_old_ids_are_mapped_but_do_not_complete_character_selection(world, legacy, expected):
    app, client, now = world
    headers = account(client, 'legacylook')
    # A 0.11.8 wardrobe sends its whole look: an old id, no accent, cap as cap.
    old = {'character': legacy, 'hair': '#123456', 'coat': '#ABCDEF', 'pants': '#345678', 'boots': '#456789',
           'skin': '#895b43', 'headwear': 'cap', 'backpack': False}
    result = save(client, headers, 0, **old)
    assert result['avatar'] == dict(old, character=expected, accent=DEFAULT['accent'])
    assert result['version'] == 1 and result['needs_character_select'] is True
    assert profile(client, headers) == result


def test_partial_edits_keep_the_saved_look_and_selection_happens_once(world):
    app, client, now = world
    headers = account(client, 'partiallook')
    first = save(client, headers, 0, hair='#010203', coat='#112233', headwear='beret', backpack=False)
    assert first['needs_character_select'] is True
    assert first['avatar'] == dict(DEFAULT, hair='#010203', coat='#112233', headwear='beret', backpack=False)
    selected = save(client, headers, 1, character='m3', pants='#345678')
    expected = dict(first['avatar'], character='m3', pants='#345678')
    assert selected['avatar'] == expected and selected['needs_character_select'] is False
    changed = save(client, headers, 2, accent='#A0B1C2')
    assert changed['avatar'] == dict(expected, accent='#A0B1C2')
    # A 0.11.8 save afterwards: its old id maps (tinker -> m1), the accent it does not know stays,
    # and the select-once prompt does not come back.
    old = {'character': 'tinker', 'hair': '#010203', 'coat': '#445566', 'pants': '#345678', 'boots': '#765744',
           'skin': '#e4b587', 'headwear': 'beret', 'backpack': False}
    legacy = save(client, headers, 3, **old)
    assert legacy['avatar'] == dict(old, character='m1', accent='#A0B1C2')
    assert legacy['needs_character_select'] is False
    assert save(client, headers, 4)['avatar'] == legacy['avatar']  # An empty patch is a valid save.


def test_failed_selection_does_not_clear_the_flag_and_clients_cannot_set_it(world):
    app, client, now = world
    headers = account(client, 'selectonce')
    stale = client.post('/v1/profile', headers=headers, json=mutation(version=1, avatar={'character': 'f4'}))
    assert stale.status_code == 409 and stale.json()['detail'] == 'stale_profile_version'
    injected = client.post('/v1/profile', headers=headers,
                           json=mutation(version=0, avatar={'character': 'f4'}, needs_character_select=False))
    assert injected.status_code == 422
    assert profile(client, headers)['needs_character_select'] is True
    chosen = save(client, headers, 0, character='f1')
    assert chosen['needs_character_select'] is False  # Choosing the default explicitly still counts.


def test_avatar_rate_limit_counts_successes_per_account_and_retries_are_idempotent(world):
    app, client, now = world
    alice = account(client, 'ratelook')
    bob = account(client, 'otherlook')
    first_body = mutation(version=0, avatar={'character': 'm2'})
    first = client.post('/v1/profile', headers=alice, json=first_body)
    assert first.status_code == 200, first.text
    # Replays, failed validation and stale writes do not use up successful-change slots.
    for version in range(1, 10):
        assert client.post('/v1/profile', headers=alice, json=first_body).json() == first.json()
        invalid = client.post('/v1/profile', headers=alice, json=mutation(version=version, avatar={'headwear': 'crown'}))
        assert invalid.status_code == 422
        stale = client.post('/v1/profile', headers=alice, json=mutation(version=0, avatar={'coat': '#123456'}))
        assert stale.status_code == 409 and stale.json()['detail'] == 'stale_profile_version'
        assert save(client, alice, version, coat='#%06x' % version)['version'] == version + 1
    rejected_body = mutation(version=10, avatar={'coat': '#ffffff'})
    limited = client.post('/v1/profile', headers=alice, json=rejected_body)
    assert limited.status_code == 429 and limited.json()['detail'] == 'avatar_rate_limited'
    assert 0 < int(limited.headers['retry-after']) <= 60
    assert profile(client, alice)['version'] == 10
    assert client.post('/v1/profile', headers=alice, json=first_body).json() == first.json()
    reused = client.post('/v1/profile', headers=alice, json={**first_body, 'avatar': {'character': 'f2'}})
    assert reused.status_code == 409 and reused.json()['detail'] == 'request_id_reused'
    assert save(client, bob, 0, character='f2')['version'] == 1
    now[0] += 59
    assert client.post('/v1/profile', headers=alice, json=rejected_body).status_code == 429
    now[0] += 1
    retried = client.post('/v1/profile', headers=alice, json=rejected_body)
    assert retried.status_code == 200 and retried.json()['version'] == 11
    assert profile(client, alice)['needs_character_select'] is False


def test_people_and_friend_rosters_carry_the_current_look(world):
    app, client, now = world
    alice, bob = account(client, 'rosteralice'), account(client, 'rosterbob')
    sent = client.post('/v1/friends/requests', headers=alice, json=mutation(username='rosterbob'))
    assert sent.status_code == 200, sent.text
    accepted = client.post('/v1/friends/requests/' + sent.json()['id'] + '/accept', headers=bob, json=mutation())
    assert accepted.status_code == 200, accepted.text
    for headers in (alice, bob):
        assert client.post('/v1/social/presence', headers=headers, json={}).status_code == 200
    before = client.get('/v1/social/people', headers=bob).json()
    assert next(p for p in before['online'] if p['username'] == 'rosteralice')['avatar'] == DEFAULT
    selected = save(client, alice, 0, character='f4', skin='#ABCDEF', accent='#987654', headwear='straw')
    now[0] += 3  # The public roster refreshes on its existing short cache interval.
    after = client.get('/v1/social/people', headers=bob).json()
    for group in ('online', 'friends'):
        seen = next(p for p in after[group] if p['username'] == 'rosteralice')
        assert seen['avatar'] == selected['avatar'] and seen['avatar_version'] == 1


OLD_SCHEMA = '''
CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 shards INTEGER NOT NULL DEFAULT 0 CHECK(shards>=0), created REAL NOT NULL);
CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 expires REAL NOT NULL, created REAL NOT NULL DEFAULT 0);
CREATE TABLE profiles (user_id TEXT PRIMARY KEY REFERENCES users(id), avatar TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version>=1));
CREATE TABLE homesteads (user_id TEXT PRIMARY KEY REFERENCES users(id), state TEXT NOT NULL);
CREATE TABLE objects (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), creator_id TEXT NOT NULL REFERENCES users(id),
 asset_id TEXT NOT NULL, name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#f6eee0',
 version INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL DEFAULT 'inventory' CHECK(state IN ('inventory','placed','listed','gifted')),
 x REAL, z REAL, rotation INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE ledger (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), amount INTEGER NOT NULL,
 reason TEXT NOT NULL, reference TEXT NOT NULL, created REAL NOT NULL, UNIQUE(user_id, reason, reference));
'''

OLD_MODELS = ('explorer_b', 'explorer', 'ranger', 'tinker', 'broken', 'unmodified')
OLD_HATS = {'explorer_b': 'cap', 'explorer': 'beret', 'ranger': 'none', 'tinker': 'cap'}


def test_old_database_migrates_without_losing_appearance_or_other_player_data(tmp_path):
    from server import homestead

    now = [1_000_000.]
    settings = Settings(data_dir=tmp_path)
    database = tmp_path / 'world.sqlite3'
    raw_profiles = {}
    headers = {}
    with sqlite3.connect(database) as conn:
        conn.executescript(OLD_SCHEMA)
        for index, model in enumerate(OLD_MODELS):
            conn.execute('INSERT INTO users VALUES (?,?,?,?,?)', (model, 'old_' + model, 'unused-password-hash', 123 + index, 42.))
            token = 'session-for-' + model
            conn.execute('INSERT INTO sessions VALUES (?,?,?,?)', (digest(token), model, now[0] + 3600, 42.))
            headers[model] = {'Authorization': 'Bearer ' + token}
            if model == 'unmodified':
                continue  # Accounts that never saved an outfit still require character selection.
            old = {'character': model, 'hair': '#112233', 'skin': '#895b43', 'coat': '#aBcDeF',
                   'pants': '#223344', 'boots': '#334455', 'headwear': OLD_HATS.get(model, 'cap'), 'backpack': False}
            raw = '{broken-json' if model == 'broken' else json.dumps(old, indent=2)
            version = 3 + index
            raw_profiles[model] = (raw, version)
            conn.execute('INSERT INTO profiles VALUES (?,?,?)', (model, raw, version))
        conn.execute('INSERT INTO objects VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                     ('kept-chair', 'explorer_b', 'explorer', 'starter', '오래된 의자', '#aabbcc', 9, 'placed', 7., 8., 90, 42.))
        conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)', ('kept-reward', 'explorer_b', 70, 'reward', 'old-run', 42.))
        life = homestead.initial()
        life.update(coins=543, bag={'turnip': 17}, version=19)
        conn.execute('INSERT INTO homesteads VALUES (?,?)', ('explorer_b', json.dumps(life)))
        preserved = {table: conn.execute('SELECT * FROM ' + table).fetchall() for table in ('objects', 'ledger', 'homesteads')}

    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        for model, expected in (('explorer_b', 'f1'), ('ranger', 'f1'), ('explorer', 'm1'), ('tinker', 'm1')):
            migrated = profile(client, headers[model])
            assert migrated['version'] == raw_profiles[model][1] and migrated['needs_character_select'] is True
            # Old ids map, cap stays cap, the accent is added with its default.
            assert migrated['avatar'] == dict(DEFAULT, character=expected, hair='#112233', skin='#895b43', coat='#aBcDeF',
                                              pants='#223344', boots='#334455', headwear=OLD_HATS[model], backpack=False)
        assert profile(client, headers['broken'])['avatar'] == DEFAULT
        untouched = profile(client, headers['unmodified'])
        assert untouched == {'avatar': DEFAULT, 'version': 0, 'needs_character_select': True}
        with app.state.db.read() as conn:
            backed_up = {row['user_id']: (row['avatar'], row['version']) for row in conn.execute('SELECT * FROM profile_avatar8_backup')}
            assert backed_up == raw_profiles
            for row in conn.execute('SELECT avatar FROM profiles'):
                assert set(json.loads(row['avatar'])) == set(DEFAULT)
            assert [(row['id'], row['shards']) for row in conn.execute('SELECT id,shards FROM users ORDER BY created,rowid')] == [
                (model, 123 + index) for index, model in enumerate(OLD_MODELS)]
            for table, rows in preserved.items():
                assert [tuple(row) for row in conn.execute('SELECT * FROM ' + table)] == rows
        chosen = save(client, headers['explorer_b'], raw_profiles['explorer_b'][1], character='m4', accent='#102938')
        assert chosen['needs_character_select'] is False
        # 0.11.8 wardrobe updates (colors, or an old id) leave another migrated account's prompt in place.
        version = raw_profiles['explorer'][1]
        assert save(client, headers['explorer'], version, coat='#567890')['needs_character_select'] is True
        assert save(client, headers['explorer'], version + 1, character='ranger')['needs_character_select'] is True

    restarted = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(restarted) as client:
        assert profile(client, headers['explorer_b']) == chosen
        assert profile(client, headers['explorer'])['needs_character_select'] is True
        assert profile(client, headers['explorer'])['avatar']['character'] == 'f1'
        assert profile(client, headers['unmodified']) == untouched
        with restarted.state.db.read() as conn:
            assert {row['user_id']: (row['avatar'], row['version']) for row in conn.execute('SELECT * FROM profile_avatar8_backup')} == raw_profiles


def test_rate_limit_and_selected_profile_survive_a_server_restart(tmp_path):
    now = [1_000_000.]
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        headers = account(client, 'restartlook')
        for version in range(10):
            chosen = save(client, headers, version, character='f2', coat='#%06x' % version)
    restarted = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(restarted) as client:
        assert profile(client, headers) == chosen
        response = client.post('/v1/profile', headers=headers, json=mutation(version=10, avatar={'headwear': 'beret'}))
        assert response.status_code == 429 and response.json()['detail'] == 'avatar_rate_limited'
        now[0] += 60
        assert save(client, headers, 10, headwear='beret')['needs_character_select'] is False


def test_pre_upgrade_request_retries_keep_the_old_result_without_new_writes(tmp_path):
    now = [1_000_000.]
    settings = Settings(data_dir=tmp_path)
    request_id = 'f5a899d0-a754-4d99-9aab-3f13ec301873'
    token = 'pre-upgrade-session'
    headers = {'Authorization': 'Bearer ' + token}
    # This is the released Avatar field order, including defaults filled by its model.
    # Build the fixture independently of the new compatibility/fingerprint helper.
    legacy = {'character': 'ranger', 'hair': '#30595b', 'coat': '#ACBD12', 'pants': '#526552',
              'boots': '#765744', 'skin': '#e4b587', 'headwear': 'cap', 'backpack': True}
    full_request = {'request_id': request_id, 'version': 7, 'avatar': legacy}
    partial_request = {'request_id': request_id, 'version': 7,
                       'avatar': {'character': 'ranger', 'coat': '#ACBD12', 'headwear': 'cap'}}
    old_json = json.dumps(full_request, separators=(',', ':'))
    old_fingerprint = hashlib.sha256(old_json.encode()).hexdigest()
    old_result = json.dumps({'avatar': legacy, 'version': 8})
    with sqlite3.connect(tmp_path / 'world.sqlite3') as conn:
        conn.executescript(OLD_SCHEMA)
        conn.execute('CREATE TABLE requests (user_id TEXT NOT NULL, request_id TEXT NOT NULL, operation TEXT NOT NULL, '
                     'fingerprint TEXT NOT NULL, response TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(user_id, request_id))')
        conn.execute('INSERT INTO users VALUES (?,?,?,?,?)', ('old-player', 'old_player', 'unused-password-hash', 456, 42.))
        conn.execute('INSERT INTO sessions VALUES (?,?,?,?)', (digest(token), 'old-player', now[0] + 3600, 42.))
        conn.execute('INSERT INTO profiles VALUES (?,?,?)', ('old-player', json.dumps(legacy), 8))
        conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)',
                     ('old-player', request_id, 'profile_edit', old_fingerprint, old_result, now[0] - 1))

    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        def stored_writes():
            with app.state.db.read() as conn:
                return {table: [tuple(row) for row in conn.execute('SELECT * FROM ' + table)]
                        for table in ('profiles', 'requests', 'profile_edit_events', 'audit')}

        before = stored_writes()
        migrated = profile(client, headers)
        assert migrated['version'] == 8 and migrated['needs_character_select'] is True
        assert migrated['avatar'] == dict(DEFAULT, coat='#ACBD12', headwear='cap')
        for body in (full_request, partial_request):
            response = client.post('/v1/profile', headers=headers, json=body)
            assert response.status_code == 200, response.text
            assert response.json() == migrated
        assert stored_writes() == before
        changed = client.post('/v1/profile', headers=headers,
                              json={**partial_request, 'avatar': {**partial_request['avatar'], 'coat': '#654321'}})
        assert changed.status_code == 409 and changed.json()['detail'] == 'request_id_reused'
        assert stored_writes() == before

        selected = save(client, headers, 8, character='m4', accent='#123456')
        assert selected['version'] == 9 and selected['needs_character_select'] is False
        after_selection = stored_writes()
        for body in (full_request, partial_request):
            retry = client.post('/v1/profile', headers=headers, json=body)
            assert retry.status_code == 200, retry.text
            assert retry.json() == dict(migrated, needs_character_select=False)
        assert profile(client, headers) == selected
        assert stored_writes() == after_selection


@pytest.mark.parametrize('choose_first', [False, True])
def test_an_omitted_character_and_an_explicit_default_are_distinct_requests(world, choose_first):
    app, client, now = world
    headers = account(client, 'requestmeaning')
    first_avatar, other_avatar = ({'character': 'f1'}, {}) if choose_first else ({}, {'character': 'f1'})
    body = mutation(version=0, avatar=first_avatar)
    first = client.post('/v1/profile', headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert first.json()['needs_character_select'] is not choose_first
    changed = client.post('/v1/profile', headers=headers, json={**body, 'avatar': other_avatar})
    assert changed.status_code == 409 and changed.json()['detail'] == 'request_id_reused'
    assert profile(client, headers) == first.json()
    assert client.post('/v1/profile', headers=headers, json=body).json() == first.json()


@pytest.mark.parametrize('initial_avatar', [{'coat': '#ABCDEF'}, {'character': 'ranger', 'coat': '#ABCDEF'}])
def test_cached_new_profile_retries_cannot_restore_the_character_selection_prompt(world, initial_avatar):
    app, client, now = world
    headers = account(client, 'cachedselection')
    body = mutation(version=0, avatar=initial_avatar)
    first = client.post('/v1/profile', headers=headers, json=body)
    assert first.status_code == 200, first.text
    snapshot = first.json()
    assert snapshot['version'] == 1 and snapshot['needs_character_select'] is True
    selected = save(client, headers, 1, character='m4', coat='#654321')
    assert selected['version'] == 2 and selected['needs_character_select'] is False
    with app.state.db.read() as conn:
        before = {table: [tuple(row) for row in conn.execute('SELECT * FROM ' + table)]
                  for table in ('profiles', 'requests', 'profile_edit_events', 'audit')}
    retried = client.post('/v1/profile', headers=headers, json=body)
    assert retried.status_code == 200, retried.text
    assert retried.json() == dict(snapshot, needs_character_select=False)
    assert profile(client, headers) == selected
    with app.state.db.read() as conn:
        after = {table: [tuple(row) for row in conn.execute('SELECT * FROM ' + table)]
                 for table in ('profiles', 'requests', 'profile_edit_events', 'audit')}
    assert after == before


def test_a_released_wardrobe_save_never_completes_the_selection(world):
    """The 0.11.8 wardrobe echoes the id it was given (f1 after the migration) with its 8 old keys and
    no accent: a recolour there keeps the select screen waiting for the new game."""
    app, client, now = world
    old_game = signed_in(client, 'oldgame')
    released = {'character': 'f1', 'hair': '#30595b', 'skin': '#e4b587', 'coat': '#112233', 'pants': '#526552',
                'boots': '#765744', 'headwear': 'none', 'backpack': True}
    saved = client.post('/v1/profile', headers={**old_game, 'x-villagen-version': '0.11.8'}, json=mutation(version=0, avatar=released)).json()
    assert saved['avatar']['coat'] == '#112233' and saved['needs_character_select'] is True
    # The same save without a version header (older builds) is the released wardrobe too.
    saved = client.post('/v1/profile', headers=old_game, json=mutation(version=saved['version'], avatar=released)).json()
    assert saved['needs_character_select'] is True
    # The new game's select screen (it sends accent, and says it is 0.11.9) completes it.
    chosen = client.post('/v1/profile', headers=old_game, json=mutation(version=saved['version'], avatar={'character': 'm3', 'accent': '#ffcc00'})).json()
    assert chosen['avatar']['character'] == 'm3' and chosen['needs_character_select'] is False


def test_released_games_are_served_ids_they_can_draw(world):
    """0.11.8 draws the wardrobe model only for explorer_b (else assets/<id>.glb, none for m1..f4): it
    gets explorer / explorer_b, and its colour-only saves keep the new character the new game chose."""
    app, client, now = world
    new_game = account(client, 'drawer')
    old_game = {k: v for k, v in new_game.items() if k != 'x-villagen-version'}
    old_game['x-villagen-version'] = '0.11.8'
    assert client.get('/v1/me', headers=old_game).json()['profile']['avatar']['character'] == 'explorer_b'
    chosen = client.post('/v1/profile', headers=new_game, json=mutation(version=0, avatar={'character': 'm3', 'accent': '#ffcc00', 'headwear': 'straw'})).json()
    assert chosen['avatar']['character'] == 'm3'
    seen = client.get('/v1/profile', headers=old_game).json()
    assert seen['avatar']['character'] == 'explorer'
    # The old wardrobe echoes what it was served with a new coat colour.
    echo = dict(seen['avatar'], coat='#123456')
    echo.pop('accent', None)
    saved = client.post('/v1/profile', headers=old_game, json=mutation(version=seen['version'], avatar=echo)).json()
    assert saved['avatar']['character'] == 'explorer'
    mine = client.get('/v1/profile', headers=new_game).json()['avatar']
    assert mine['character'] == 'm3' and mine['coat'] == '#123456' and mine['accent'] == '#ffcc00' and mine['headwear'] == 'straw'
