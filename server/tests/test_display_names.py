"""Display names (user decision: banned words filtered, no duplicates): existing accounts start with
their login id, a name is checked and unique after normalising, it changes once a day, and everyone
who sees a player (presence, visits, invitations, chat) gets the shown name next to the login id."""
import sqlite3
import pytest
from server.display_names import clean, key, NameError_
from server.tests.test_multiplayer import world, post, invite, mutation  # noqa: F401 (fixture)


def save_name(c, h, name):
    return c.post('/v1/profile/name', headers=h, json=mutation(display_name=name))


def test_rules():
    assert clean('  별빛   상점 ') == '별빛 상점' and clean('Ru') == 'Ru' and clean('민트·초코') == '민트·초코'
    for name, code in (('a', 'name_invalid'), ('열세글자가넘는긴이름이에요', 'name_invalid'), ('이름​', 'name_invalid'),
                       ('<b>hi</b>', 'name_invalid'), ('GM_Kim', 'name_reserved'), ('관리자다', 'name_reserved'),
                       ('Admin2', 'name_reserved'), ('운영자 별빛', 'name_reserved'), ('씨발', 'name_refused'), ('나치 깃발', 'name_refused')):
        with pytest.raises(NameError_) as caught:
            clean(name)
        assert str(caught.value) == code, name
    assert key('Ｓｔａｒ Light') == key('starlight')


def test_existing_and_new_accounts_start_with_their_login_id(world):
    app, c, now, hs, _ = world
    me = c.get('/v1/me', headers=hs[0]).json()
    assert me['display_name'] == 'alice' and me['display_name_changeable_at'] == 0


def test_a_name_is_checked_unique_and_changes_once_a_day(world):
    app, c, now, hs, _ = world
    saved = save_name(c, hs[0], '별빛 여행자')
    assert saved.status_code == 200 and saved.json()['display_name'] == '별빛 여행자'
    assert saved.json()['display_name_changeable_at'] == int(now[0] + 86400)
    # Taken after normalising (spaces, case, full width) — and a login id is a name too.
    assert save_name(c, hs[1], '별빛여행자').json()['detail'] == 'name_taken'
    assert save_name(c, hs[1], 'CHARLIE').json()['detail'] == 'name_taken'
    assert save_name(c, hs[1], 'GM 별빛').json()['detail'] == 'name_reserved'
    assert save_name(c, hs[1], '씨발').json()['detail'] == 'name_refused'
    # Refusals do not use up the day's change.
    assert save_name(c, hs[1], '바다 소년').status_code == 200
    again = save_name(c, hs[0], '새 이름')
    assert again.status_code == 429 and again.json()['detail'] == 'name_change_limited' and int(again.headers['Retry-After']) > 0
    # The same name again is not a change; a day later it can change.
    assert save_name(c, hs[0], '별빛 여행자').status_code == 200
    with app.state.db.transaction() as db:
        db.execute('UPDATE users SET name_changed=name_changed-86401')
    assert save_name(c, hs[0], '새 이름').json()['display_name'] == '새 이름'
    # The old name is free again.
    assert save_name(c, hs[2], '별빛 여행자').status_code == 200


def test_a_login_id_cannot_take_someones_display_name(world):
    app, c, now, hs, _ = world
    assert save_name(c, hs[0], 'Moonlight').status_code == 200
    taken = c.post('/v1/auth/register', json={'username': 'moonlight', 'password': 'Test-password-123'})
    assert taken.status_code == 409 and taken.json()['detail'] == 'username_unavailable'


def test_others_see_the_display_name(world):
    app, c, now, hs, _ = world
    assert save_name(c, hs[0], '별빛 주인').status_code == 200
    assert save_name(c, hs[1], '바다 손님').status_code == 200
    visit = invite(c, hs[0], hs[1], 'bravo', 'village')
    assert visit['host_name'] == 'alice' and visit['host_display_name'] == '별빛 주인'
    c.post('/v1/social/presence', headers=hs[0], json={'x': 1, 'z': 1})
    seen = c.post('/v1/social/presence', headers=hs[1], json={'x': 2, 'z': 2}).json()
    players = {p['username']: p for p in seen['space']['players']}
    assert players['alice']['display_name'] == '별빛 주인' and players['bravo']['display_name'] == '바다 손님'


def test_old_databases_get_names_once(tmp_path):
    from server.display_names import migrate
    path = tmp_path / 'old.sqlite3'
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute('CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, shards INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL)')
    conn.execute("INSERT INTO users VALUES ('u1','alice','x',0,1),('u2','bob_2','x',0,1)")
    migrate(conn)
    migrate(conn)
    rows = conn.execute('SELECT username,display_name,display_key,name_changed FROM users ORDER BY id').fetchall()
    assert rows == [('alice', 'alice', 'alice', 0), ('bob_2', 'bob_2', 'bob_2', 0)]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE users SET display_key='alice' WHERE id='u2'")
