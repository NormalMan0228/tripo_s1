"""The chosen character and colours stay the same through every scene a 0.11.9 game visits: sign in
again, the own village and home, a friend's village and home (both sides see each other), the friends
roster and a co-op expedition (players' looks are the saved ones, not the run-start snapshot). The only
writer is POST /v1/profile; no scene change saves a look."""
from server.tests.test_multiplayer import world, post, invite, prepare_party, mutation  # noqa: F401 (fixture)

NEW = {'x-villagen-version': '0.11.9'}
LOOK = {'character': 'm3', 'hair': '#112233', 'skin': '#c08060', 'coat': '#445566', 'pants': '#778899',
        'boots': '#aabbcc', 'accent': '#ddeeff', 'headwear': 'straw', 'backpack': False}


def game(h):
    return {**h, **NEW}


def choose(c, h, look):
    version = c.get('/v1/profile', headers=game(h)).json()['version']
    saved = c.post('/v1/profile', headers=game(h), json=mutation(version=version, avatar=look)).json()
    assert saved['avatar'] == look and saved['needs_character_select'] is False
    return saved


def test_the_chosen_look_survives_every_scene(world):
    app, c, now, hs, _ = world
    alice, bravo = hs[0], hs[1]
    choose(c, alice, LOOK)
    other = dict(LOOK, character='f2', coat='#010203', headwear='beret')
    choose(c, bravo, other)
    # Signing in again (login reply and /v1/me).
    login = c.post('/v1/auth/login', headers=NEW, json={'username': 'alice', 'password': 'Test-password-123'}).json()
    assert login['profile']['avatar'] == LOOK
    assert c.get('/v1/me', headers=game(alice)).json()['profile']['avatar'] == LOOK
    # Own village, then home: the walker's own look in presence.
    for scene in ('village', 'home', 'village'):
        seen = c.post('/v1/social/presence', headers=game(alice), json={'scene': scene, 'x': 1, 'z': 1}).json()
        me = [p for p in seen['space']['players'] if p['username'] == 'alice']
        assert me and me[0]['avatar'] == LOOK, scene
    # A friend's village and home: each sees the other's saved look.
    invite(c, alice, bravo, 'bravo', 'village')
    for scene in ('village', 'home'):
        c.post('/v1/social/presence', headers=game(alice), json={'scene': scene, 'x': 0, 'z': 3})
        guest = c.post('/v1/social/presence', headers=game(bravo), json={'scene': scene, 'x': 1, 'z': 2}).json()
        looks = {p['username']: p['avatar'] for p in guest['space']['players']}
        assert looks == {'alice': LOOK, 'bravo': other}, scene
    # The friends roster (people) shows the saved looks too.
    post(c, game(alice), '/v1/friends/requests', username='bravo')
    requests = c.get('/v1/social/people', headers=game(bravo)).json()['requests']['incoming']
    if requests:
        post(c, game(bravo), '/v1/friends/requests/' + requests[0]['id'] + '/accept')
        people = c.get('/v1/social/people', headers=game(bravo)).json()
        friends = {f['username']: f['avatar'] for f in people.get('friends', [])}
        assert friends['alice'] == LOOK
    # Still the same after all of it.
    assert c.get('/v1/profile', headers=game(alice)).json()['avatar'] == LOOK
    assert c.get('/v1/profile', headers=game(bravo)).json()['avatar'] == other


def test_a_coop_expedition_shows_the_saved_looks(world):
    app, c, now, hs, _ = world
    for h, character in zip(hs[:3], ('m1', 'f3', 'm4')):
        choose(c, h, dict(LOOK, character=character))
    run_id = prepare_party(c, [game(h) for h in hs])
    state = c.get('/v1/coop/runs/' + run_id, headers=game(hs[0])).json()
    looks = {p['username']: p['avatar']['character'] for p in state['players']}
    assert looks == {'alice': 'm1', 'bravo': 'f3', 'charlie': 'm4'}
    # A look changed during the run shows in the run (live, not the start snapshot).
    choose(c, hs[1], dict(LOOK, character='f4'))
    state = c.get('/v1/coop/runs/' + run_id, headers=game(hs[0])).json()
    assert {p['username']: p['avatar']['character'] for p in state['players']}['bravo'] == 'f4'


def test_released_viewers_get_drawable_ids_and_sign_in_again_keeps_the_look(world):
    """03's checks: a 0.11.8 game sees m3 as explorer and f2 as explorer_b in presence and visits (it
    can draw only those), while the owners' saved looks stay m3/f2 with their colours after logging out
    and in again (login reply and /v1/me)."""
    app, c, now, hs, _ = world
    alice, bravo, old_viewer = hs[0], hs[1], hs[2]
    m3 = dict(LOOK, character='m3')
    f2 = dict(LOOK, character='f2', coat='#010203')
    choose(c, alice, m3)
    choose(c, bravo, f2)
    released = {**old_viewer, 'x-villagen-version': '0.11.8'}
    # Both visit alice's village; the 0.11.8 viewer is there too.
    invite(c, alice, bravo, 'bravo', 'village')
    invite(c, alice, old_viewer, 'charlie', 'village')
    c.post('/v1/social/presence', headers=game(alice), json={'scene': 'village', 'x': 0, 'z': 3})
    c.post('/v1/social/presence', headers=game(bravo), json={'scene': 'village', 'x': 1, 'z': 2})
    seen = c.post('/v1/social/presence', headers=released, json={'scene': 'village', 'x': 2, 'z': 2}).json()
    old = {p['username']: p['avatar'] for p in seen['space']['players']}
    assert old['alice']['character'] == 'explorer' and old['bravo']['character'] == 'explorer_b'
    assert old['alice']['coat'] == m3['coat'] and old['bravo']['coat'] == '#010203'
    # A 0.11.9 game in the same place sees the real ids.
    fresh = c.post('/v1/social/presence', headers=game(bravo), json={'scene': 'village', 'x': 1, 'z': 2}).json()
    assert {p['username']: p['avatar']['character'] for p in fresh['space']['players']}['alice'] == 'm3'
    # Log out and in again: m3 and its colours, never an old id.
    assert c.post('/v1/auth/logout', headers=game(alice), json=mutation()).status_code in (200, 204)
    login = c.post('/v1/auth/login', headers=NEW, json={'username': 'alice', 'password': 'Test-password-123'}).json()
    assert login['profile']['avatar'] == m3
    token = {'Authorization': 'Bearer ' + login['token'], **NEW}
    assert c.get('/v1/me', headers=token).json()['profile']['avatar'] == m3
    assert c.get('/v1/profile', headers=token).json()['avatar'] == m3
