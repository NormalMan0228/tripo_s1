"""Owner-only homes (server/home_access.py), the carried item and the wallet in presence."""
from server import home_access
from server.tests.test_multiplayer import world, post, invite  # noqa: F401  (fixture)


def poll(c, h, **body):
    response = c.post('/v1/social/presence', headers=h, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def names(reply):
    return {p['username'] for p in (reply['space'] or {}).get('players', [])}


def test_guests_enter_only_while_the_owner_is_home(world):
    app, c, now, hs, _ = world
    invite(c, hs[0], hs[1], 'bravo', 'village')
    poll(c, hs[0], scene='village', x=0, z=3)
    # The owner is outdoors: the door stays shut and the guest is drawn nowhere.
    refused = poll(c, hs[1], scene='home', x=1, z=2)
    assert refused['home'] == {'open': False, 'owner': False, 'locked': False, 'owner_in': False, 'reason': 'owner_away'}
    assert refused['space'] is None and refused['village'] is None
    assert 'bravo' not in names(poll(c, hs[0], scene='village', x=0, z=3))
    assert c.get('/v1/home/access', headers=hs[1]).json()['reason'] == 'owner_away'
    # The owner goes in: now the guest may follow, and both see each other inside.
    host = poll(c, hs[0], scene='home', x=0, z=3)
    assert host['home'] == {'open': True, 'owner': True, 'locked': False}
    guest = poll(c, hs[1], scene='home', x=1, z=2)
    assert guest['home']['open'] and guest['space']['scene'] == 'home'
    assert names(guest) == {'alice', 'bravo'}
    # The owner walks out: the guest may stay a moment to follow, then is sent out too.
    poll(c, hs[0], scene='village', x=0, z=3)
    now[0] += home_access.OWNER_GRACE - 2
    assert poll(c, hs[1], scene='home', x=1, z=2)['home']['open']
    now[0] += 3
    late = poll(c, hs[1], scene='home', x=1, z=2)
    assert late['home']['reason'] == 'owner_away' and late['space'] is None
    # Leaving is always free.
    assert poll(c, hs[1], scene='village', x=1, z=2)['village'] is not None


def test_lock_keeps_new_guests_out_but_not_the_ones_inside(world):
    app, c, now, hs, _ = world
    invite(c, hs[0], hs[1], 'bravo', 'village')
    invite(c, hs[0], hs[2], 'charlie', 'village')
    poll(c, hs[0], scene='home', x=0, z=3)
    assert poll(c, hs[1], scene='home', x=1, z=2)['home']['open']
    assert post(c, hs[0], '/v1/home/lock', locked=True) == {'locked': True}
    assert poll(c, hs[0], scene='home', x=0, z=3)['home']['locked'] is True
    assert poll(c, hs[2], scene='home', x=1, z=1)['home']['reason'] == 'locked'
    inside = poll(c, hs[1], scene='home', x=1, z=2)
    assert inside['home']['open'] and inside['home']['locked']
    assert names(poll(c, hs[0], scene='home', x=0, z=3)) == {'alice', 'bravo'}
    post(c, hs[0], '/v1/home/lock', locked=False)
    assert poll(c, hs[2], scene='home', x=1, z=1)['home']['open']


def test_owner_sends_one_guest_out_of_the_home_only(world):
    app, c, now, hs, _ = world
    invite(c, hs[0], hs[1], 'bravo', 'village')
    poll(c, hs[0], scene='home', x=0, z=3)
    poll(c, hs[1], scene='home', x=1, z=2)
    guest_id = c.get('/v1/social', headers=hs[1]).json()['self_id']
    out = post(c, hs[0], '/v1/home/eject', user_id=guest_id)
    assert out['was_inside'] is True
    # Gone from the owner's home at once, refused on the guest's next poll, still visiting the village.
    assert names(poll(c, hs[0], scene='home', x=0, z=3)) == {'alice'}
    refused = poll(c, hs[1], scene='home', x=1, z=2)
    assert refused['home']['reason'] == 'ejected' and refused['home']['until'] > now[0]
    village = poll(c, hs[1], scene='village', x=1, z=2)
    assert village['visiting'] and village['host_name'] == 'alice'
    # The owner cannot send themselves out.
    assert c.post('/v1/home/eject', headers=hs[0], json={'request_id': '5b4a1e0e-4c1f-4b62-9a33-9a6a1c4bd001', 'user_id': c.get('/v1/social', headers=hs[0]).json()['self_id']}).status_code == 409
    now[0] += home_access.EJECT_SECONDS + 1
    poll(c, hs[0], scene='home', x=0, z=3)
    assert poll(c, hs[1], scene='home', x=1, z=2)['home']['open']


def test_presence_carries_the_held_item_and_the_wallet(world):
    app, c, now, hs, _ = world
    health = c.get('/health').json()
    assert health['home_access'] == 1 and health['presence_held'] == 1
    invite(c, hs[0], hs[1], 'bravo', 'village')
    me = poll(c, hs[0], scene='village', x=0, z=3, held='umbrella')
    assert isinstance(me['shards'], int)
    seen = {p['username']: p for p in poll(c, hs[1], scene='village', x=1, z=2)['village']['players']}
    assert seen['alice']['held'] == 'umbrella' and 'held' not in seen['bravo']
    poll(c, hs[0], scene='village', x=0, z=3, held='')
    seen = {p['username']: p for p in poll(c, hs[1], scene='village', x=1, z=2)['village']['players']}
    assert 'held' not in seen['alice']
    assert c.post('/v1/social/presence', headers=hs[0], json={'scene': 'village', 'held': 'Big Sword!'}).status_code == 422
