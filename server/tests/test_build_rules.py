"""Build mode placement (server/build_rules.py): measured footprints, wall and ceiling pieces,
stacking on top of pieces, retrieve cascade, carrying, and the pose fields in object lists."""
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server import npc_homes, build_rules


def mutation(**kw):
    return {'request_id': str(uuid.uuid4()), **kw}


@pytest.fixture
def world(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    with TestClient(app) as c:
        users = []
        for name in ('alice', 'bravo'):
            r = c.post('/v1/auth/register', json={'username': name, 'password': 'Build-test-password'})
            assert r.status_code == 200
            with app.state.db.read() as conn:
                user_id = conn.execute('SELECT id FROM users WHERE username=?', (name,)).fetchone()[0]
            users.append(({'Authorization': 'Bearer ' + r.json()['token']}, user_id))
        yield app, c, users


def piece(app, user_id, title, size, category='decoration'):
    """A crafted-style piece in the bag whose measured box is exactly size (w, h, d)."""
    preset = {'title': title, 'category': category, 'parts': [('body', 'box', list(size), [0, size[1] / 2, 0], '#c9a46e')]}
    with app.state.db.transaction() as conn:
        return npc_homes.return_gift(conn, app.state.studio.assets, user_id, 'naru', time.time(), preset=preset, key=uuid.uuid4().hex[:12])


class Pieces:
    """Placement calls that keep each piece's version."""

    def __init__(self, c, h):
        self.c, self.h, self.version = c, h, {}

    def place(self, oid, **kw):
        r = self.c.post('/v1/objects/' + oid + '/placement', headers=self.h, json=mutation(version=self.version.get(oid, 1), **kw))
        if r.status_code == 200:
            value = r.json()
            self.version[oid] = value['version']
            for moved in value.get('carried', []):
                self.version[moved['id']] = moved['version']
            for gone in value.get('retrieved', []):
                self.version[gone] = self.version.get(gone, 1) + 1
        return r

    def ok(self, oid, **kw):
        r = self.place(oid, **kw)
        assert r.status_code == 200, r.text
        return r.json()

    def refused(self, oid, code, **kw):
        r = self.place(oid, **kw)
        assert r.status_code == 409 and r.json()['detail'] == code, r.text

    def listed(self, oid, route='/v1/me'):
        return next(o for o in self.c.get(route, headers=self.h).json()['objects'] if o['id'] == oid)


def test_pieces_pack_by_their_measured_footprint(world):
    app, c, [(h, uid), _] = world
    p = Pieces(c, h)
    a, b, close = (piece(app, uid, '컵받침', (0.5, 0.4, 0.5)) for _ in range(3))
    p.ok(a, room='home', x=2, z=0)
    # 1 m apart: the old 2x2 parcel refused this.
    assert p.ok(b, room='home', x=3, z=0)['surface'] == 'floor'
    p.refused(close, 'placement_overlap', room='home', x=2.3, z=0)
    # Turned footprints: a 2 m bench along z leaves room beside it, not along it.
    bench = piece(app, uid, '벤치', (2.0, 0.45, 0.3))
    reply = p.ok(bench, room='home', x=-2, z=0, rotation=90)
    assert (reply['x'], reply['z'], reply['y'], reply['rotation'], reply['parent']) == (-2, 0, 0, 90, None)
    assert reply['carried'] == [] and reply['retrieved'] == []
    p.ok(close, room='home', x=-1.5, z=0)
    side = piece(app, uid, '화분', (0.4, 0.5, 0.4))
    p.refused(side, 'placement_overlap', room='home', x=-2, z=0.9)
    # Released clients' floor rules still hold.
    p.refused(side, 'door_area_reserved', room='home', x=0, z=3)
    p.refused(side, 'outside_room', room='home', x=4.5, z=0)
    # The legacy village route measures too.
    v1, v2 = piece(app, uid, '돌', (0.6, 0.5, 0.6)), piece(app, uid, '돌', (0.6, 0.5, 0.6))
    assert c.post('/v1/objects/' + v1, headers=h, json=mutation(version=1, action='place', x=5, z=4)).status_code == 200
    assert c.post('/v1/objects/' + v2, headers=h, json=mutation(version=1, action='place', x=6, z=4)).status_code == 200
    v3 = piece(app, uid, '돌', (0.6, 0.5, 0.6))
    r = c.post('/v1/objects/' + v3, headers=h, json=mutation(version=1, action='place', x=5.3, z=4.2))
    assert r.status_code == 409 and r.json()['detail'] == 'placement_overlap'


def test_wall_pieces_snap_to_room_walls(world):
    app, c, [(h, uid), _] = world
    p = Pieces(c, h)
    frame, other, side = (piece(app, uid, '그림 액자', (0.8, 0.6, 0.1)) for _ in range(3))
    reply = p.ok(frame, room='home', surface='wall', wall='back', x=1.0, z=2.0, y=1.2, rotation=45)
    assert (reply['x'], reply['z'], reply['y'], reply['rotation'], reply['surface']) == (1.0, -4.93, 1.2, 0, 'wall')
    # Slid along the wall to stay inside; side walls turn the piece to face the room.
    reply = p.ok(other, room='home', surface='wall', wall='left', x=0, z=9, y=1.0)
    assert (reply['x'], reply['z'], reply['rotation']) == (-4.93, 4.55, 90)
    reply = p.ok(side, room='workshop', surface='wall', wall='right', x=0, z=-1, y=1.0)
    assert (reply['x'], reply['z'], reply['rotation']) == (5.18, -1, 270)
    assert p.listed(frame)['surface'] == 'wall' and p.listed(frame)['y'] == 1.2
    # Bulky pieces do not hang; nothing pokes through the ceiling.
    chest = piece(app, uid, '상자', (1.0, 0.7, 0.6))
    p.refused(chest, 'not_wall_piece', room='home', surface='wall', wall='back', x=-2, y=1)
    tall = piece(app, uid, '족자', (0.6, 0.6, 0.1))
    p.refused(tall, 'wall_too_tall', room='home', surface='wall', wall='back', x=-2, y=2.8)
    # Walls belong to rooms; a wall needs its name.
    p.refused(tall, 'surface_not_here', room='village', surface='wall', wall='back', x=5, z=4, y=1)
    p.refused(tall, 'surface_not_here', room='village', surface='ceiling', x=5, z=4)
    assert p.place(tall, room='home', surface='wall', x=-2, y=1).status_code == 422
    # A hung piece collides with what stands below it only where the heights meet.
    shelf = piece(app, uid, '선반', (1.0, 1.0, 2.0))
    p.ok(shelf, room='home', x=-3, z=-4)
    p.refused(tall, 'placement_overlap', room='home', surface='wall', wall='back', x=-3, y=0.5)
    assert p.ok(tall, room='home', surface='wall', wall='back', x=-3, y=1.2)['z'] == -4.93
    p.refused(piece(app, uid, '그림', (0.8, 0.6, 0.1)), 'placement_overlap', room='home', surface='wall', wall='back', x=1.5, y=1.0)


def test_ceiling_pieces_are_hanging_things(world):
    app, c, [(h, uid), _] = world
    p = Pieces(c, h)
    lamp = piece(app, uid, '펜던트 램프', (0.5, 0.6, 0.5), 'lamp')
    reply = p.ok(lamp, room='home', surface='ceiling', x=1, z=1, y=0)
    assert (reply['x'], reply['z'], reply['y'], reply['surface']) == (1, 1, 2.78, 'ceiling')
    fan = piece(app, uid, 'ceiling fan', (1.2, 0.4, 1.2))
    assert p.ok(fan, room='workshop', surface='ceiling', x=0, z=0)['y'] == 3.78
    # Light-tagged pieces hang too (a candle stand).
    assert p.ok(piece(app, uid, '촛대', (0.3, 0.5, 0.3)), room='home', surface='ceiling', x=-1, z=-1)['y'] == 2.88
    p.refused(piece(app, uid, '의자', (0.5, 0.9, 0.5), 'chair'), 'not_ceiling_piece', room='home', surface='ceiling', x=2, z=2)
    p.refused(piece(app, uid, '탁자', (1.2, 0.75, 0.8), 'table'), 'not_ceiling_piece', room='home', surface='ceiling', x=2, z=2)
    p.refused(piece(app, uid, '샹들리에', (1.0, 1.6, 1.0)), 'not_ceiling_piece', room='home', surface='ceiling', x=2, z=2)
    edge = piece(app, uid, '랜턴', (0.4, 0.5, 0.4))
    p.refused(edge, 'outside_room', room='home', surface='ceiling', x=4.9, z=0)
    p.refused(edge, 'placement_overlap', room='home', surface='ceiling', x=1.2, z=1)
    # The door strip is a floor rule only.
    assert p.ok(edge, room='home', surface='ceiling', x=0, z=4.5)['surface'] == 'ceiling'


def test_stacking_on_top_of_pieces(world):
    app, c, [(h, uid), (h2, uid2)] = world
    p = Pieces(c, h)
    table = piece(app, uid, '탁자', (1.2, 0.75, 0.8), 'table')
    p.ok(table, room='home', x=2, z=0)
    cup = piece(app, uid, '컵', (0.2, 0.15, 0.2))
    reply = p.ok(cup, room='home', surface='top', parent=table, x=2.3, z=0.1, y=0.75)
    assert (reply['surface'], reply['parent'], reply['y']) == ('top', table, 0.75)
    loose = piece(app, uid, '컵', (0.2, 0.15, 0.2))
    p.refused(loose, 'not_on_parent', room='home', surface='top', parent=table, x=2.6, z=0, y=0.75)
    p.refused(loose, 'not_on_parent', room='home', surface='top', parent=table, x=1.8, z=0, y=0.9)
    p.refused(loose, 'not_on_parent', room='home', surface='top', parent=table, x=1.8, z=0, y=0.02)
    p.refused(loose, 'placement_overlap', room='home', surface='top', parent=table, x=2.35, z=0.1, y=0.75)
    p.refused(loose, 'not_on_parent', room='workshop', surface='top', parent=table, x=2, z=0, y=0.75)
    p.refused(loose, 'not_on_parent', room='home', surface='top', parent=str(uuid.uuid4()), x=2, z=0, y=0.75)
    assert p.place(loose, room='home', surface='top', x=2, z=0, y=0.75).status_code == 422
    p.refused(piece(app, uid, '큰 상자', (1.5, 0.3, 1.0)), 'too_big_to_stack', room='home', surface='top', parent=table, x=2, z=0, y=0.75)
    # Another player's piece holds nothing of mine.
    theirs = piece(app, uid2, '탁자', (1.2, 0.75, 0.8))
    Pieces(c, h2).ok(theirs, room='home', x=-2, z=0)
    p.refused(loose, 'not_on_parent', room='home', surface='top', parent=theirs, x=-2, z=0, y=0.75)
    # No loops: the table cannot go on the cup that stands on it, nor on itself.
    p.refused(table, 'stack_cycle', room='home', surface='top', parent=cup, x=2.3, z=0.1, y=0.9)
    p.refused(table, 'stack_cycle', room='home', surface='top', parent=table, x=2, z=0, y=0.75)
    # Three supports at most.
    tray, small, tiny, tinier = (piece(app, uid, name, size) for name, size in
                                 (('쟁반', (0.6, 0.1, 0.4)), ('그릇', (0.2, 0.1, 0.2)), ('구슬', (0.1, 0.1, 0.1)), ('씨앗', (0.1, 0.1, 0.1))))
    p.ok(tray, room='home', surface='top', parent=table, x=1.75, z=0, y=0.75)
    p.ok(small, room='home', surface='top', parent=tray, x=1.75, z=0, y=0.8)
    p.ok(tiny, room='home', surface='top', parent=small, x=1.75, z=0, y=0.9)
    p.refused(tinier, 'stack_too_high', room='home', surface='top', parent=tiny, x=1.75, z=0, y=1.0)
    # Wall pieces hold nothing.
    frame = piece(app, uid, '액자', (0.8, 0.6, 0.1))
    p.ok(frame, room='home', surface='wall', wall='back', x=-3, y=1)
    p.refused(tinier, 'not_on_parent', room='home', surface='top', parent=frame, x=-3, z=-4.93, y=1.6)
    # Stacking works in the village too (no reserved-area rule for pieces on top).
    stall = piece(app, uid, '좌판', (1.0, 0.8, 1.0))
    p.ok(stall, room='village', x=5, z=4)
    assert p.ok(tinier, room='village', surface='top', parent=stall, x=5.2, z=4, y=0.8)['parent'] == stall


def test_retrieve_sends_what_stood_on_a_piece_to_the_bag(world):
    app, c, [(h, uid), _] = world
    p = Pieces(c, h)
    table = piece(app, uid, '탁자', (1.2, 0.75, 0.8))
    cup, saucer = piece(app, uid, '컵', (0.2, 0.15, 0.2)), piece(app, uid, '받침', (0.1, 0.1, 0.1))
    p.ok(table, room='home', x=2, z=0)
    p.ok(cup, room='home', surface='top', parent=table, x=2.3, z=0, y=0.75)
    p.ok(saucer, room='home', surface='top', parent=cup, x=2.3, z=0, y=0.9)
    reply = p.ok(table, action='retrieve', room='home')
    assert reply['state'] == 'inventory' and set(reply['retrieved']) == {cup, saucer}
    for oid in (cup, saucer):
        row = p.listed(oid)
        assert (row['state'], row['x'], row['surface'], row['parent'], row['y'], row['version']) == ('inventory', None, 'floor', None, 0, 3)
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM object_mounts').fetchone()[0] == 0
    # The legacy village route cascades as well.
    p.ok(table, room='village', x=5, z=4)
    p.ok(cup, room='village', surface='top', parent=table, x=5, z=4, y=0.75)
    r = c.post('/v1/objects/' + table, headers=h, json=mutation(version=p.version[table], action='retrieve'))
    assert r.status_code == 200 and r.json()['retrieved'] == [cup] and r.json()['state'] == 'inventory'
    assert p.listed(cup)['state'] == 'inventory'


def test_a_piece_given_away_leaves_nothing_floating(world):
    app, c, [(h, uid), _] = world
    p = Pieces(c, h)
    table, cup = piece(app, uid, '탁자', (1.2, 0.75, 0.8)), piece(app, uid, '컵', (0.2, 0.15, 0.2))
    p.ok(table, room='village', x=5, z=4)
    p.ok(cup, room='village', surface='top', parent=table, x=5, z=4, y=0.75)
    r = c.post('/v1/story/gift', headers=h, json=mutation(object_id=table, version=p.version[table]))
    assert r.status_code == 200, r.text
    assert (p.listed(cup)['state'], p.listed(cup)['surface']) == ('inventory', 'floor')


def test_moving_a_piece_carries_what_stands_on_it(world):
    app, c, [(h, uid), _] = world
    p = Pieces(c, h)
    table = piece(app, uid, '탁자', (1.2, 0.75, 0.8))
    cup = piece(app, uid, '컵', (0.2, 0.15, 0.2))
    p.ok(table, room='home', x=2, z=0)
    p.ok(cup, room='home', surface='top', parent=table, x=2.4, z=0.1, y=0.75, rotation=10)
    reply = p.ok(table, room='home', x=-2, z=1, rotation=90)
    [moved] = reply['carried']
    assert (moved['id'], moved['room'], moved['version']) == (cup, 'home', 3)
    assert (moved['x'], moved['z'], moved['y'], moved['rotation']) == pytest.approx((-1.9, 0.6, 0.75, 100))
    row = p.listed(cup)
    assert (row['x'], row['z'], row['rotation']) == pytest.approx((-1.9, 0.6, 100))
    assert (row['surface'], row['parent'], row['version']) == ('top', table, 3)
    # Into another room, the cup comes along (turned back with the table).
    moved = p.ok(table, room='workshop', x=2, z=2)['carried'][0]
    assert (moved['x'], moved['z'], moved['rotation']) == pytest.approx((2.4, 2.1, 10)) and moved['room'] == 'workshop'
    assert p.listed(cup)['room'] == 'workshop'
    # A carried piece may not run into another one: a tall vase under a low chandelier.
    chandelier = piece(app, uid, '샹들리에', (1.0, 1.5, 1.0))
    assert p.ok(chandelier, room='home', surface='ceiling', x=2, z=-2)['y'] == 1.88
    stand = piece(app, uid, '탁자', (1.2, 0.75, 0.8))
    vase = piece(app, uid, '꽃병', (0.3, 1.2, 0.3))
    p.ok(stand, room='home', x=2, z=2)
    p.ok(vase, room='home', surface='top', parent=stand, x=2, z=2, y=0.75)
    p.refused(stand, 'placement_overlap', room='home', x=2, z=-2)
    assert p.ok(stand, room='home', x=2, z=-0.8)['carried'][0]['z'] == -0.8
    # A board taken up to the wall drops what stood on it into the bag.
    board = piece(app, uid, '판자', (0.8, 0.8, 0.1))
    p.ok(board, room='home', x=-3, z=-3)
    p.ok(cup, room='home', surface='top', parent=board, x=-3, z=-3, y=0.8)
    reply = p.ok(board, room='home', surface='wall', wall='back', x=-3, y=1)
    assert reply['retrieved'] == [cup] and reply['carried'] == [] and p.listed(cup)['state'] == 'inventory'
    # Back on the floor: no mount row left.
    p.ok(cup, room='home', x=3, z=3)
    with app.state.db.read() as conn:
        assert conn.execute('SELECT 1 FROM object_mounts WHERE object_id=?', (cup,)).fetchone() is None


def test_object_lists_carry_pose_for_owner_and_visitors(world):
    app, c, [(h, uid), (h2, _)] = world
    p = Pieces(c, h)
    table = piece(app, uid, '탁자', (1.2, 0.75, 0.8))
    cup = piece(app, uid, '컵', (0.2, 0.15, 0.2))
    p.ok(table, room='home', x=2, z=0)
    p.ok(cup, room='home', surface='top', parent=table, x=2, z=0, y=0.75)
    for route in ('/v1/me', '/v1/studio'):
        assert {k: p.listed(cup, route)[k] for k in ('y', 'surface', 'parent')} == {'y': 0.75, 'surface': 'top', 'parent': table}
        assert {k: p.listed(table, route)[k] for k in ('y', 'surface', 'parent')} == {'y': 0, 'surface': 'floor', 'parent': None}
    invite = c.post('/v1/social/invites', headers=h, json=mutation(username='bravo', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=h2, json=mutation()).status_code == 200
    c.post('/v1/social/presence', headers=h, json={'scene': 'home', 'x': 0, 'z': 3})
    guest = c.post('/v1/social/presence', headers=h2, json={'scene': 'home', 'x': 1, 'z': 2}).json()
    seen = {o['id']: o for o in guest['space']['objects']}
    assert (seen[cup]['y'], seen[cup]['surface'], seen[cup]['parent']) == (0.75, 'top', table)
    assert (seen[table]['y'], seen[table]['surface'], seen[table]['parent']) == (0, 'floor', None)
    # A piece whose support stopped standing some other way reads as a floor piece.
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE objects SET state='inventory',x=NULL,z=NULL WHERE id=?", (table,))
    assert {k: p.listed(cup)[k] for k in ('y', 'surface', 'parent')} == {'y': 0, 'surface': 'floor', 'parent': None}


def test_footprint_geometry():
    square = build_rules.footprint(0, 0, (1, 1, 1), 0, 0.01)
    assert build_rules.footprints_meet(square, build_rules.footprint(0.97, 0, (1, 1, 1), 0, 0.01))
    assert not build_rules.footprints_meet(square, build_rules.footprint(0.99, 0, (1, 1, 1), 0, 0.01))
    # A diamond (45 degrees) reaches 0.707 m along x.
    assert build_rules.footprints_meet(square, build_rules.footprint(1.15, 0, (1, 1, 1), 45, 0.01))
    assert not build_rules.footprints_meet(square, build_rules.footprint(1.25, 0, (1, 1, 1), 45, 0.01))
    assert build_rules.turned(1, 0, 90) == pytest.approx((0, -1))
    assert build_rules.half_extent((2, 1, 0.5), 90) == pytest.approx((0.25, 1))
