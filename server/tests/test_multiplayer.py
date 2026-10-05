import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings


def mutation(**extra):
    return dict(request_id=str(uuid.uuid4()), **extra)


@pytest.fixture
def world(tmp_path):
    now = [1000000.]
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        headers = []
        for name in ('alice', 'bravo', 'charlie', 'delta'):
            response = client.post('/v1/auth/register', json={'username': name, 'password': 'test-password-123'})
            headers.append({'Authorization': 'Bearer '+response.json()['token']})
        yield app, client, now, headers, settings


def post(c, h, path, **extra):
    response = c.post(path, headers=h, json=mutation(**extra))
    assert response.status_code == 200, response.text
    return response.json()


def invite(c, sender, recipient, username, kind):
    item = post(c, sender, '/v1/social/invites', username=username, kind=kind)
    return post(c, recipient, '/v1/social/invites/'+item['id']+'/accept')


def prepare_party(c, hs, count=3):
    post(c, hs[0], '/v1/party')
    for index in range(1, count):
        invite(c, hs[0], hs[index], ('alice', 'bravo', 'charlie')[index], 'party')
    for h in hs[:count]:
        assert c.post('/v1/social/presence', headers=h, json={}).status_code == 200
    return post(c, hs[0], '/v1/party/runs')['id']


def edit_state(app, run_id, edit):
    with app.state.db.transaction() as db:
        state = json.loads(db.execute('SELECT state FROM coop_runs WHERE id=?', (run_id,)).fetchone()[0])
        edit(state)
        db.execute('UPDATE coop_runs SET state=? WHERE id=?', (json.dumps(state), run_id))


def test_village_invitation_privacy_revocation_and_capacity(world):
    app, c, now, hs, _ = world
    own = c.get('/v1/me', headers=hs[0]).json()['objects'][0]
    private = c.get('/v1/me', headers=hs[1]).json()['objects'][0]
    post(c, hs[0], '/v1/objects/'+own['id'], version=1, action='place', x=5, z=4)
    route = '/v1/social/village/objects/'+own['id']+'/model'
    assert c.get(route, headers=hs[1]).status_code == 404
    result = invite(c, hs[0], hs[1], 'bravo', 'village')
    assert result['visiting'] and result['host_name'] == 'alice'
    assert c.get(route, headers=hs[1]).content[:4] == b'glTF'
    assert c.get('/v1/objects/'+own['id']+'/model', headers=hs[1]).status_code == 404
    assert c.post('/v1/objects/'+own['id'], headers=hs[1], json=mutation(action='retrieve', version=2)).status_code == 404
    snapshot = c.post('/v1/social/presence', headers=hs[1], json={'x': 1, 'z': 2}).json()
    assert [o['id'] for o in snapshot['village']['objects']] == [own['id']]
    assert private['id'] not in str(snapshot['village'])
    assert 'bag' not in snapshot['village']['crops']
    invite(c, hs[0], hs[2], 'charlie', 'village')
    fourth = post(c, hs[0], '/v1/social/invites', username='delta', kind='village')
    assert c.post('/v1/social/invites/'+fourth['id']+'/accept', headers=hs[3], json=mutation()).json()['detail'] == 'village_full'
    visitor_id = result['self_id']
    post(c, hs[0], '/v1/social/eject', user_id=visitor_id)
    assert c.get(route, headers=hs[1]).status_code == 404
    assert not c.get('/v1/social', headers=hs[1]).json()['visiting']


def test_visitors_enter_the_host_home_but_not_the_workshop(world):
    app, c, now, hs, _ = world
    own = c.get('/v1/me', headers=hs[0]).json()['objects'][0]
    post(c, hs[0], '/v1/objects/'+own['id']+'/placement', version=1, room='home', x=2, z=-2)
    route = '/v1/social/village/objects/'+own['id']+'/model'
    assert c.get(route, headers=hs[1]).status_code == 404
    invite(c, hs[0], hs[1], 'bravo', 'village')
    assert c.get(route, headers=hs[1]).content[:4] == b'glTF'
    host = c.post('/v1/social/presence', headers=hs[0], json={'scene': 'home', 'x': 0, 'z': 3}).json()
    guest = c.post('/v1/social/presence', headers=hs[1], json={'scene': 'home', 'x': 1, 'z': 2}).json()
    assert guest['village'] is None and guest['space']['scene'] == 'home'
    assert [o['id'] for o in guest['space']['objects']] == [own['id']]
    assert {p['username'] for p in guest['space']['players']} == {'alice', 'bravo'}
    assert guest['space']['crops'] is None
    # Someone outdoors in the village does not appear inside the home.
    outdoors = c.post('/v1/social/presence', headers=hs[1], json={'scene': 'village', 'x': 1, 'z': 2}).json()
    assert own['id'] not in str(outdoors['village']['objects'])
    host = c.post('/v1/social/presence', headers=hs[0], json={'scene': 'home', 'x': 0, 'z': 3}).json()
    assert {p['username'] for p in host['space']['players']} == {'alice'}
    post(c, hs[0], '/v1/objects/'+own['id']+'/placement', version=2, room='workshop', x=2, z=2)
    assert c.get(route, headers=hs[1]).status_code == 404


def test_visitor_assembly_render_data_and_revoked_part_access(world):
    app, c, now, hs, _ = world
    job = post(c, hs[0], '/v1/studio/jobs', prompt='flower')
    asyncio.run(app.state.studio.process(job['id']))
    result = c.get('/v1/studio/jobs/'+job['id'], headers=hs[0]).json()
    assert result['state'] == 'ready'
    oid = result['object_id']
    own = '/v1/objects/'+oid
    guest = '/v1/social/village/objects/'+oid
    post(c, hs[0], own+'/placement', version=1, room='village', x=5, z=4)
    invite(c, hs[0], hs[1], 'bravo', 'village')
    value = c.get(guest+'/assembly', headers=hs[1]).json()
    assert value['schema'] == 1 and value['program']
    assert value['provenance'] == {'geometry': 'procedural_proxy'}
    assert set(value) == {'schema', 'plan', 'program', 'provenance', 'runtime', 'object_version'}
    assert c.get(own+'/assembly', headers=hs[1]).status_code == 404
    assert c.post(own+'/colors', headers=hs[1], json=mutation(version=1, color='#abcdef')).status_code == 404
    for part in value['plan']['parts']:
        response = c.get(guest+'/parts/'+part['id'], headers=hs[1])
        assert response.status_code == 200 and response.content[:4] == b'glTF'
    post(c, hs[1], '/v1/social/home')
    assert c.get(guest+'/assembly', headers=hs[1]).status_code == 404
    assert c.get(guest+'/parts/'+part['id'], headers=hs[1]).status_code == 404


def test_invite_target_expiry_party_race_and_leader_transfer(world):
    app, c, now, hs, _ = world
    post(c, hs[0], '/v1/party')
    invite(c, hs[0], hs[1], 'bravo', 'party')
    now[0] += .01
    invitations = [post(c, hs[0], '/v1/social/invites', username=name, kind='party') for name in ('charlie', 'delta')]
    route = '/v1/social/invites/'+invitations[0]['id']+'/accept'
    assert c.post(route, headers=hs[3], json=mutation()).status_code == 404
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda pair: c.post('/v1/social/invites/'+pair[0]['id']+'/accept', headers=pair[1], json=mutation()), zip(invitations, hs[2:])))
    assert sorted(r.status_code for r in results) == [200, 409]
    post(c, hs[0], '/v1/party/leave')
    assert c.get('/v1/social', headers=hs[1]).json()['party']['leader_id'] == c.get('/v1/social', headers=hs[1]).json()['self_id']
    old = post(c, hs[0], '/v1/social/invites', username='bravo', kind='village')
    now[0] += 601
    assert c.post('/v1/social/invites/'+old['id']+'/accept', headers=hs[1], json=mutation()).status_code == 404


def test_shared_world_clock_resources_fire_and_personal_inventory(world):
    app, c, now, hs, _ = world
    run = prepare_party(c, hs)
    path = '/v1/coop/runs/'+run
    snapshots = [c.get(path, headers=h).json() for h in hs[:3]]
    assert len({s['id'] for s in snapshots}) == 1
    assert len(snapshots[0]['players']) == 3
    assert c.get(path, headers=hs[3]).status_code == 404
    assert c.post('/v1/runs', headers=hs[0], json=mutation()).json()['detail'] == 'party_expedition_active'
    assert c.post('/v1/party/leave', headers=hs[1], json=mutation()).json()['detail'] == 'leave_expedition_first'
    now[0] += .2
    for h in hs[:3]:
        assert c.post(path+'/input', headers=h, json={'sequence': 1}).status_code == 200
    snapshot = c.get(path, headers=hs[0]).json()
    assert snapshot['elapsed'] == pytest.approx(.2)  # not .6 for three callers
    assert c.post(path+'/input', headers=hs[0], json={'sequence': 1}).json()['detail'] == 'stale_input'
    ids = [s['self_id'] for s in snapshots]
    def place(state):
        for actor in state['players'].values():
            actor.update(x=1.8, z=0)
        state['world']['nodes'][0]['quantity'] = 1
    edit_state(app, run, place)
    now[0] += .4
    for h in hs[:2]:
        c.post(path+'/input', headers=h, json={'sequence': 2, 'action': 'harvest', 'target': 'n0'})
    a, b = [c.get(path, headers=h).json() for h in hs[:2]]
    assert a['nodes'][0]['quantity'] == b['nodes'][0]['quantity'] == 0
    assert a['inventory']['wood'] == 4 and b['inventory']['wood'] == 3
    now[0] += .2
    c.get(path, headers=hs[0])
    now[0] += .2
    c.post(path+'/input', headers=hs[0], json={'sequence': 3, 'action': 'fire'})
    a, b = [c.get(path, headers=h).json() for h in hs[:2]]
    assert a['fire_remaining'] == b['fire_remaining'] == 30
    assert a['inventory']['wood'] == 2 and b['inventory']['wood'] == 3


def test_disconnect_stale_intent_restart_rewards_exactly_once(world):
    app, c, now, hs, settings = world
    run = prepare_party(c, hs)
    route = '/v1/coop/runs/'+run
    c.post(route+'/input', headers=hs[0], json={'sequence': 1, 'dx': 1})
    moving_id = c.get(route, headers=hs[0]).json()['self_id']
    initial_x = c.get(route, headers=hs[0]).json()['x']
    now[0] += .2
    moved = c.post(route+'/input', headers=hs[1], json={'sequence': 1}).json()
    x = next(p['x'] for p in moved['players'] if p['id'] == moving_id)
    assert x > initial_x
    now[0] += 20
    paused = c.get(route, headers=hs[0]).json()
    assert paused['elapsed'] == pytest.approx(.2)
    c.post(route+'/input', headers=hs[1], json={'sequence': 2})
    now[0] += .2
    resumed = c.post(route+'/input', headers=hs[1], json={'sequence': 3}).json()
    assert resumed['elapsed'] == pytest.approx(.4)
    assert next(p['x'] for p in resumed['players'] if p['id'] == moving_id) == x
    restarted = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(restarted) as second:
        assert second.get(route, headers=hs[0]).json()['id'] == run
        def near_win(state):
            state['world'].update(elapsed=settings.day_seconds*7-.1, fire_until=10000)
            for actor in state['players'].values():
                actor['last_seen'] = now[0]
        edit_state(app, run, near_win)
        now[0] += .2
        assert second.get(route, headers=hs[0]).json()['status'] == 'won'
        balances = [second.get('/v1/me', headers=h).json()['shards'] for h in hs[:3]]
        payload = mutation()
        with ThreadPoolExecutor(3) as pool:
            results = list(pool.map(lambda _: second.post(route+'/claim', headers=hs[0], json=payload), range(3)))
        assert all(r.status_code == 200 for r in results)
        reward = results[0].json()['reward']
        assert second.get('/v1/me', headers=hs[0]).json()['shards'] == balances[0]+reward
        assert second.post(route+'/claim', headers=hs[0], json=mutation()).status_code == 409
        for index in (1, 2):
            assert post(second, hs[index], route+'/claim')['reward'] == reward
            assert second.get('/v1/me', headers=hs[index]).json()['shards'] == balances[index]+reward


def test_personal_withdrawal_does_not_end_teammates_and_no_reward(world):
    app, c, now, hs, _ = world
    run = prepare_party(c, hs)
    route = '/v1/coop/runs/'+run
    post(c, hs[0], route+'/abandon')
    assert c.get(route, headers=hs[0]).json()['status'] == 'abandoned'
    assert c.get(route, headers=hs[1]).json()['status'] == 'active'
    assert c.post(route+'/input', headers=hs[0], json={'sequence': 1}).status_code == 409
    post(c, hs[0], '/v1/party/leave')
    post(c, hs[1], route+'/abandon')
    post(c, hs[2], route+'/abandon')
    assert c.get(route, headers=hs[2]).json()['status'] == 'abandoned'
    assert c.post(route+'/claim', headers=hs[0], json=mutation()).status_code == 409


def test_authenticated_rate_limits_separate_users_on_same_ip(world):
    app, c, now, hs, _ = world
    # Same public IP: each account gets its own rolling window.
    for _ in range(610):
        for h in hs[:2]:
            assert c.get('/health', headers=h).status_code == 200
    for _ in range(600):
        response = c.get('/health', headers=hs[0])
    assert response.status_code == 429
    assert c.get('/health', headers=hs[1]).status_code == 200


def test_party_messages_are_private_and_idempotent(world):
    app, c, now, hs, _ = world
    prepare_party(c, hs)
    payload = mutation(text='모닥불로 모이세요')
    for _ in range(2):
        assert c.post('/v1/social/messages', headers=hs[0], json=payload).status_code == 200
    assert len(c.get('/v1/social', headers=hs[1]).json()['messages']) == 1
    assert c.get('/v1/social', headers=hs[3]).json()['messages'] == []
    assert c.post('/v1/social/messages', headers=hs[0], json=mutation(text='again')).status_code == 429


def test_shared_enemy_hits_target_once_and_defeated_player_spectates(world):
    app, c, now, hs, _ = world
    run = prepare_party(c, hs)
    route = '/v1/coop/runs/'+run
    ids = [c.get(route, headers=h).json()['self_id'] for h in hs[:3]]
    def windup(state):
        state['world'].update(elapsed=40, spawned_night=1, fire_until=0)
        for index, actor_id in enumerate(ids):
            state['players'][actor_id].update(x=(index-1)*1.3, z=2)
        state['world']['enemies'] = [dict(id='strike', kind='wolf', x=-1.3, z=3.4, hp=30, max_hp=30,
            phase='windup', phase_until=40.1, target_x=-1.3, target_z=2, target_user=ids[0], damage=8, impact=1.35)]
    edit_state(app, run, windup)
    now[0] += .2
    views = [c.get(route, headers=h).json() for h in hs[:3]]
    assert views[0]['hp'] < views[1]['hp']-7.9
    assert views[1]['hp'] == views[2]['hp']
    assert all(s['enemies'][0]['phase'] == 'recover' for s in views)
    assert all(s['elapsed'] == pytest.approx(40.2) for s in views)
    edit_state(app, run, lambda s: s['players'][ids[0]].update(hp=0))
    c.post(route+'/input', headers=hs[0], json={'sequence':1, 'dx':1, 'action':'eat'})
    now[0] += .2
    spectator = c.get(route, headers=hs[0]).json()
    assert spectator['hp'] == 0 and spectator['x'] == views[0]['x']
    assert spectator['status'] == 'active'  # teammates are still alive
    edit_state(app, run, lambda s: [p.update(hp=0) for p in s['players'].values()])
    now[0] += .2
    assert c.get(route, headers=hs[1]).json()['status'] == 'lost'


def test_presence_expiry_and_logout_remove_visible_player(world):
    app, c, now, hs, _ = world
    invite(c, hs[0], hs[1], 'bravo', 'village')
    c.post('/v1/social/presence', headers=hs[1], json={'y':1.5})
    host = c.post('/v1/social/presence', headers=hs[0], json={}).json()
    assert len(host['village']['players']) == 2
    assert any(p['y'] == 1.5 for p in host['village']['players'])
    now[0] += 11
    host = c.post('/v1/social/presence', headers=hs[0], json={}).json()
    assert len(host['village']['players']) == 1
    c.post('/v1/social/presence', headers=hs[1], json={})
    c.post('/v1/auth/logout', headers=hs[1])
    assert c.post('/v1/social/presence', headers=hs[1], json={}).status_code == 401
    assert len(c.post('/v1/social/presence', headers=hs[0], json={}).json()['village']['players']) == 1
