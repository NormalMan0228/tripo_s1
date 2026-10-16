"""Offline regressions for display-name/avatar boundaries in the 0.11.9 audit."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from server.display_names import NameError_, check_policy, clean, key
from server.tests.test_multiplayer import mutation, world  # noqa: F401


@pytest.mark.parametrize('name', [
    'ad.min', 'a-d-m-i-n', 'аdmin', 'ádmin', 'adмin', 'ＡＤＭＩＮ', 'ΑDΜΙΝ',
    'adm1n', 'G M', 'staff123', 'root', 'polytech', 'ㅈㅣㅇㅔㅁ', 'ㅇㅜㄴㅇㅕㅇㅈㅏ',
])
def test_staff_titles_cannot_be_disguised(name):
    with pytest.raises(NameError_, match='^name_reserved$'):
        clean(name)


@pytest.mark.parametrize('name', [
    'fu ck', 'fu.ck', 'fu-ck', 'fuсk', 'fυck', 'fúck', 'ｆｕｃｋ',
    'ㅆ ㅣ ㅂ ㅏ ㄹ', '씨 발', '시.발',
])
def test_banned_name_fragments_and_lookalikes_cannot_bypass_policy(name):
    with pytest.raises(NameError_, match='^name_refused$'):
        clean(name)


@pytest.mark.parametrize('name', [
    'al\u200bice', 'al\u200dice', 'al\u202eice', '\u3164\u3164', '\u115f\u1160',
    '[b]Alice', '<b>Alice',
])
def test_invisible_names_and_markup_are_rejected(name):
    with pytest.raises(NameError_, match='^name_invalid$'):
        clean(name)


@pytest.mark.parametrize('name,expected', [
    ('  별빛   상점 ', '별빛 상점'), ('민트·초코', '민트·초코'), ("O'Neil", "O'Neil"),
    ('Renée', 'Renée'), ('Мария', 'Мария'), ('Modern', 'Modern'), ('Ｓｔａｒ Light', 'Star Light'),
    ('Stafford', 'Stafford'), ('supporter', 'supporter'), ('officially', 'officially'),
])
def test_ordinary_spelling_and_duplicate_key_contract_stay_intact(name, expected):
    assert clean(name) == expected
    assert key(name) == key(expected)


def test_registration_policy_keeps_the_existing_login_length_contract(world):
    app, client, now, headers, settings = world
    username = 'ordinarylongplayername'
    assert len(username) > 12
    assert check_policy(username) is None
    result = client.post('/v1/auth/register', json={'username': username, 'password': 'Testing-only-12345'})
    assert result.status_code == 200, result.text
    auth = {'Authorization': 'Bearer ' + result.json()['token']}
    assert client.get('/v1/me', headers=auth).json()['display_name'] == username


@pytest.mark.parametrize('username,detail', [
    ('staff', 'username_reserved'), ('bob_admin', 'username_reserved'),
    ('ad_min', 'username_reserved'), ('fuck', 'invalid_request'), ('fu_ck', 'invalid_request'),
])
def test_registration_cannot_bypass_the_initial_display_name_policy(world, username, detail):
    app, client, now, headers, settings = world
    result = client.post('/v1/auth/register', json={'username': username, 'password': 'Testing-only-12345'})
    assert (result.status_code, result.json()) == (422, {'detail': detail})
    with app.state.db.read() as conn:
        assert conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone() is None


def test_concurrent_normalized_name_claim_has_one_winner(world):
    app, client, now, headers, settings = world
    barrier = Barrier(2)

    def claim(item):
        auth, name = item
        barrier.wait(timeout=10)
        return client.post('/v1/profile/name', headers=auth, json=mutation(display_name=name))

    with ThreadPoolExecutor(max_workers=2) as workers:
        replies = list(workers.map(claim, [(headers[0], 'Moon Light'), (headers[1], 'ＭｏｏｎＬｉｇｈｔ')]))
    assert sorted(r.status_code for r in replies) == [200, 409]
    assert next(r for r in replies if r.status_code == 409).json()['detail'] == 'name_taken'
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM users WHERE display_key=?', ('moonlight',)).fetchone()[0] == 1


def test_changing_a_display_name_does_not_release_the_login_identity(world):
    app, client, now, headers, settings = world
    first = client.post('/v1/profile/name', headers=headers[0], json=mutation(display_name='Moonlight'))
    assert first.status_code == 200
    for disguised in ('alice', 'a l i c e', 'ＡＬＩＣＥ'):
        taken = client.post('/v1/profile/name', headers=headers[1], json=mutation(display_name=disguised))
        assert (taken.status_code, taken.json()) == (409, {'detail': 'name_taken'})
    # The original owner can still return to their own login name after the cooldown.
    now[0] += 86400
    signed_in = client.post('/v1/auth/login', json={'username': 'alice', 'password': 'Test-password-123'})
    assert signed_in.status_code == 200
    refreshed = {'Authorization': 'Bearer ' + signed_in.json()['token']}
    restored = client.post('/v1/profile/name', headers=refreshed, json=mutation(display_name='alice'))
    assert restored.status_code == 200


def test_concurrent_renames_cannot_bypass_daily_limit(world):
    app, client, now, headers, settings = world
    barrier = Barrier(2)

    def rename(name):
        barrier.wait(timeout=10)
        return client.post('/v1/profile/name', headers=headers[0], json=mutation(display_name=name))

    with ThreadPoolExecutor(max_workers=2) as workers:
        replies = list(workers.map(rename, ['Moonwalker', 'Starwalker']))
    assert sorted(r.status_code for r in replies) == [200, 429]
    limited = next(r for r in replies if r.status_code == 429)
    assert limited.json()['detail'] == 'name_change_limited'
    assert int(limited.headers['retry-after']) == 86400


def test_profile_payload_and_ownership_boundaries(world):
    app, client, now, headers, settings = world
    with app.state.db.read() as conn:
        target = conn.execute("SELECT id FROM users WHERE username='bravo'").fetchone()[0]
    before = client.get('/v1/profile', headers=headers[1]).json()
    for injected in ({'user_id': target}, {'owner_id': target}):
        result = client.post('/v1/profile', headers=headers[0],
                             json=mutation(version=0, avatar={'character': 'm2'}, **injected))
        assert result.status_code == 422
    oversized = client.post('/v1/profile', headers=headers[0],
                            json=mutation(version=0, avatar={'character': 'x' * 9000}))
    assert (oversized.status_code, oversized.json()) == (413, {'detail': 'body_too_large'})
    assert client.get('/v1/profile', headers=headers[1]).json() == before
    assert client.get('/v1/profile', headers=headers[0]).json()['version'] == 0


def test_concurrent_avatar_updates_preserve_version_and_event_limit(world):
    app, client, now, headers, settings = world
    barrier = Barrier(2)

    def save(character):
        barrier.wait(timeout=10)
        return client.post('/v1/profile', headers=headers[0],
                           json=mutation(version=0, avatar={'character': character}))

    with ThreadPoolExecutor(max_workers=2) as workers:
        replies = list(workers.map(save, ['m2', 'f3']))
    assert sorted(r.status_code for r in replies) == [200, 409]
    assert next(r for r in replies if r.status_code == 409).json()['detail'] == 'stale_profile_version'
    assert client.get('/v1/profile', headers=headers[0]).json()['version'] == 1
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM profile_edit_events').fetchone()[0] == 1
