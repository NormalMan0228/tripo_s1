"""Picking up where the player left off (server/last_spot.py, items 55-56)."""
from server import last_spot
from server.tests.test_multiplayer import world, post, invite  # noqa: F401  (fixture)

PASSWORD = 'Test-password-123'


def poll(c, h, **body):
    response = c.post('/v1/social/presence', headers=h, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def sign_in(c, name):
    response = c.post('/v1/auth/login', json={'username': name, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    data = response.json()
    return data['resume'], {'Authorization': 'Bearer '+data['token']}


def test_first_sign_in_has_nothing_to_resume(world):
    app, c, now, hs, _ = world
    resume, _ = sign_in(c, 'alice')
    assert resume is None


def test_logout_in_the_village_resumes_on_that_spot(world):
    app, c, now, hs, _ = world
    poll(c, hs[0], scene='village', x=4.5, z=-7.25, y=0.5, yaw=1.2, place='village')
    assert c.post('/v1/auth/logout', headers=hs[0]).status_code in (200, 204)
    now[0] += 120
    resume, h = sign_in(c, 'alice')
    assert resume['spot'] == {'scene': 'village', 'place': 'village', 'floor': None, 'x': 4.5, 'z': -7.25, 'y': 0.5, 'yaw': 1.2}
    assert resume['away_seconds'] == 120 and resume['wake'] is False
    assert c.get('/v1/social/resume', headers=h).json()['resume'] == resume


def test_long_away_or_ending_at_home_wakes_in_bed(world):
    app, c, now, hs, _ = world
    poll(c, hs[0], scene='village', x=1, z=2, place='village')
    c.post('/v1/social/offline', headers=hs[0])
    now[0] += last_spot.WAKE_AFTER
    resume, _ = sign_in(c, 'alice')
    assert resume['wake'] is True and resume['spot']['scene'] == 'village'
    # Quit inside the home (the room itself, not the workshop): wake up in bed even a minute later.
    _, h = sign_in(c, 'bravo')
    poll(c, h, scene='home', x=0, z=3, place='home', floor=1)
    c.post('/v1/social/offline', headers=h)
    now[0] += 60
    resume, _ = sign_in(c, 'bravo')
    assert resume['wake'] is True and resume['spot']['floor'] == 1
    _, h = sign_in(c, 'charlie')
    poll(c, h, scene='home', x=0, z=3, place='workshop')
    c.post('/v1/social/offline', headers=h)
    resume, _ = sign_in(c, 'charlie')
    assert resume['wake'] is False and resume['spot']['place'] == 'workshop'


def test_a_crashed_game_resumes_from_its_last_poll(world):
    app, c, now, hs, _ = world
    poll(c, hs[0], scene='village', x=9, z=9, place='village')
    c.post('/v1/social/offline', headers=hs[0])
    now[0] += 30
    # Signed in again, walked on, and the game died without saying goodbye.
    _, h = sign_in(c, 'alice')
    poll(c, h, scene='village', x=-3, z=5, place='village')
    now[0] += 30
    resume, _ = sign_in(c, 'alice')
    assert (resume['spot']['x'], resume['spot']['z']) == (-3, 5)


def test_a_friends_village_or_an_expedition_gives_no_spot(world):
    app, c, now, hs, _ = world
    invite(c, hs[0], hs[1], 'bravo', 'village')
    poll(c, hs[0], scene='village', x=0, z=3)
    poll(c, hs[1], scene='village', x=1, z=2, place='village')
    c.post('/v1/social/offline', headers=hs[1])
    resume, _ = sign_in(c, 'bravo')
    assert resume['spot'] is None and resume['wake'] is False
    poll(c, hs[2], scene='away', x=0, z=0, place='expedition')
    c.post('/v1/social/offline', headers=hs[2])
    resume, _ = sign_in(c, 'charlie')
    assert resume['spot'] is None
