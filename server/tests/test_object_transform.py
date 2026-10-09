"""Free turning (any whole degree) and shape edits (width, depth, height, overall size,
mirror) of placed objects: bounds, owner-only edits, idempotency, versions, the market
lock, visitor lists and released (quarter-turn, shape-less) clients."""
import asyncio
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings


def mutation(**extra):
    return dict(request_id=str(uuid.uuid4()), **extra)


@pytest.fixture
def world(tmp_path):
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app) as client:
        headers = []
        for name in ('alice', 'bravo'):
            response = client.post('/v1/auth/register', json={'username': name, 'password': 'Test-password-123'})
            headers.append({'Authorization': 'Bearer ' + response.json()['token']})
        yield app, client, headers, tmp_path


def starter(c, h):
    return c.get('/v1/me', headers=h).json()['objects'][0]


def mine(c, h, object_id, route='/v1/me'):
    return next(o for o in c.get(route, headers=h).json()['objects'] if o['id'] == object_id)


def crafted(app, c, h):
    job = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt='wooden chest', motion='static')).json()['id']
    asyncio.run(app.state.studio.process(job))
    return c.get('/v1/studio/jobs/' + job, headers=h).json()['object_id']


def test_objects_turn_to_any_whole_degree(world):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    route = '/v1/objects/' + obj['id']
    for bad in (360, -1, 400, 12.5, '90deg'):
        refused = c.post(route, headers=hs[0], json=mutation(version=1, action='place', x=5, z=4, rotation=bad))
        assert refused.status_code == 422, bad
    placed = c.post(route, headers=hs[0], json=mutation(version=1, action='place', x=5, z=4, rotation=37))
    assert placed.status_code == 200 and placed.json()['rotation'] == 37
    assert mine(c, hs[0], obj['id'])['rotation'] == 37
    # A placed village object turns again in one step (no retrieve) through the placement route.
    turned = c.post(route + '/placement', headers=hs[0], json=mutation(version=2, room='village', x=5, z=4, rotation=359))
    assert turned.status_code == 200, turned.text
    assert mine(c, hs[0], obj['id'])['rotation'] == 359
    assert c.post(route + '/placement', headers=hs[0], json=mutation(version=3, room='village', x=5, z=4, rotation=360)).status_code == 422
    # Rooms take any whole degree as well.
    assert c.post(route + '/placement', headers=hs[0], json=mutation(version=3, action='retrieve')).status_code == 200
    home = c.post(route + '/placement', headers=hs[0], json=mutation(version=4, room='home', x=2, z=-2, rotation=203))
    assert home.status_code == 200, home.text
    listed = mine(c, hs[0], obj['id'], '/v1/studio')
    assert listed['rotation'] == 203 and listed['room'] == 'home'
    assert c.post(route + '/placement', headers=hs[0], json=mutation(version=5, room='workshop', x=1, z=-1, rotation=1)).status_code == 200
    assert mine(c, hs[0], obj['id'])['rotation'] == 1


def test_released_clients_keep_working(world):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    route = '/v1/objects/' + obj['id']
    # Quarter turns, and requests without any rotation, as 0.11.2 sends them.
    assert c.post(route, headers=hs[0], json=mutation(version=1, action='place', x=5, z=4, rotation=270)).json()['rotation'] == 270
    assert c.post(route, headers=hs[0], json=mutation(version=2, action='retrieve')).status_code == 200
    assert c.post(route, headers=hs[0], json=mutation(version=3, action='place', x=5, z=4)).json()['rotation'] == 0
    assert c.post(route + '/placement', headers=hs[0], json=mutation(version=4, action='retrieve')).status_code == 200
    assert c.post(route + '/placement', headers=hs[0], json=mutation(version=5, room='home', x=2, z=2, rotation=90)).status_code == 200
    # Object lists keep every field they had; the shape is added (null until reshaped).
    listed = mine(c, hs[0], obj['id'])
    assert {'id', 'name', 'color', 'version', 'state', 'x', 'z', 'rotation', 'room', 'studio', 'runtime_version', 'paint_version'} <= set(listed)
    assert listed['shape'] is None and listed['rotation'] == 90
    studio = mine(c, hs[0], obj['id'], '/v1/studio')
    assert studio['shape'] is None and studio['rotation'] == 90
    # The legacy edit reply is unchanged.
    painted = c.post(route, headers=hs[0], json=mutation(version=6, action='paint', color='#112233')).json()
    assert set(painted) == {'id', 'name', 'color', 'version', 'state', 'x', 'z', 'rotation'}


def test_shape_edits_are_bounded_idempotent_and_versioned(world):
    app, c, hs, data = world
    oid = crafted(app, c, hs[0])
    route = '/v1/objects/' + oid + '/shape'
    assert mine(c, hs[0], oid)['shape'] is None
    body = mutation(width=150, depth=80, height=120, scale=110, mirror=True)
    reply = c.post(route, headers=hs[0], json=body)
    assert reply.status_code == 200, reply.text
    shape = reply.json()
    assert shape == {'width': 150, 'depth': 80, 'height': 120, 'scale': 110, 'mirror': True, 'version': 1}
    # A retried request is answered once; reusing its id for something else is refused.
    assert c.post(route, headers=hs[0], json=body).json() == shape
    assert c.post(route, headers=hs[0], json={**body, 'width': 151}).json()['detail'] == 'request_id_reused'
    assert mine(c, hs[0], oid)['shape'] == shape
    assert mine(c, hs[0], oid, '/v1/studio')['shape'] == shape
    # Bounds: whole percents from 50 to 200, nothing else.
    for field, bad in (('width', 49), ('depth', 201), ('height', 0), ('scale', 1000), ('width', 120.5), ('scale', None),
                       ('mirror', 'sideways'), ('version', -1)):
        refused = c.post(route, headers=hs[0], json=mutation(**{field: bad}))
        assert refused.status_code == 422, (field, bad)
    assert c.post(route, headers=hs[0], json=mutation(stretch=2)).status_code == 422
    edge = c.post(route, headers=hs[0], json=mutation(width=50, depth=200, height=50, scale=200, version=1)).json()
    assert edge['version'] == 2 and (edge['width'], edge['depth'], edge['height'], edge['scale'], edge['mirror']) == (50, 200, 50, 200, False)
    # An edit made from an older shape is refused; one without a version always applies.
    stale = c.post(route, headers=hs[0], json=mutation(width=90, version=1))
    assert stale.status_code == 409 and stale.json()['detail'] == 'stale_shape_version'
    # Reset returns to the made shape, and the version still grows.
    reset = c.post(route, headers=hs[0], json=mutation(reset=True, width=180)).json()
    assert reset == {'width': 100, 'depth': 100, 'height': 100, 'scale': 100, 'mirror': False, 'version': 3}
    assert mine(c, hs[0], oid)['shape'] == reset
    assert c.post(route, headers=hs[0], json=mutation(height=60)).json()['version'] == 4
    with sqlite3.connect(data / 'world.sqlite3') as conn:
        assert conn.execute('SELECT height,version FROM object_shape WHERE object_id=?', (oid,)).fetchone() == (60, 4)
    # Legacy (non-studio) objects can be reshaped too.
    assert c.post('/v1/objects/' + starter(c, hs[0])['id'] + '/shape', headers=hs[0], json=mutation(scale=70)).json()['version'] == 1


def test_only_the_owner_reshapes_and_listed_objects_are_locked(world):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    route = '/v1/objects/' + obj['id'] + '/shape'
    assert c.post(route, json=mutation(width=120)).status_code == 401
    assert c.post(route, headers=hs[1], json=mutation(width=120)).status_code == 404
    assert c.post('/v1/objects/' + str(uuid.uuid4()) + '/shape', headers=hs[0], json=mutation(width=120)).status_code == 404
    assert c.post(route, headers=hs[0], json=mutation(width=120)).status_code == 200
    assert c.post('/v1/market', headers=hs[0], json=mutation(object_id=obj['id'], version=1, price=5)).status_code == 200
    refused = c.post(route, headers=hs[0], json=mutation(width=130))
    assert refused.status_code == 409 and refused.json()['detail'] == 'object_is_listed'
    assert c.post(route, headers=hs[0], json=mutation(reset=True)).status_code == 409
    listing = c.get('/v1/market', headers=hs[1]).json()['listings'][0]
    assert c.post('/v1/market/' + listing['id'] + '/buy', headers=hs[1], json=mutation()).status_code == 200
    # The buyer holds it now (unlisted) and may reshape it; the shape travelled with the object.
    assert mine(c, hs[1], obj['id'])['shape']['width'] == 120
    assert c.post(route, headers=hs[0], json=mutation(width=140)).status_code == 404
    assert c.post(route, headers=hs[1], json=mutation(width=140)).json()['version'] == 2


def test_visitors_see_the_shape_where_they_see_the_object(world):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    own = '/v1/objects/' + obj['id']
    shape = c.post(own + '/shape', headers=hs[0], json=mutation(width=160, height=70, mirror=True)).json()
    assert c.post(own, headers=hs[0], json=mutation(version=1, action='place', x=5, z=4, rotation=123)).status_code == 200
    invite = c.post('/v1/social/invites', headers=hs[0], json=mutation(username='bravo', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=hs[1], json=mutation()).status_code == 200
    space = c.post('/v1/social/presence', headers=hs[1], json={'x': 1, 'z': 2}).json()['village']
    assert [(o['rotation'], o['shape']) for o in space['objects']] == [(123, shape)]
    # Guests cannot reshape the host's furniture.
    assert c.post(own + '/shape', headers=hs[1], json=mutation(width=60)).status_code == 404
    # The owner's later edit reaches the visitor's next poll.
    newer = c.post(own + '/shape', headers=hs[0], json=mutation(scale=180)).json()
    space = c.post('/v1/social/presence', headers=hs[1], json={'x': 1, 'z': 2}).json()['village']
    assert space['objects'][0]['shape'] == newer and newer['version'] == 2
    # A home visit lists it the same way.
    assert c.post(own + '/placement', headers=hs[0], json=mutation(version=2, action='retrieve')).status_code == 200
    assert c.post(own + '/placement', headers=hs[0], json=mutation(version=3, room='home', x=2, z=-2, rotation=301)).status_code == 200
    home = c.post('/v1/social/presence', headers=hs[1], json={'scene': 'home', 'x': 1, 'z': 2}).json()['space']
    assert [(o['rotation'], o['shape']) for o in home['objects']] == [(301, newer)]
