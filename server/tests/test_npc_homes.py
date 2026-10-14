"""Gifts to village residents and their homes (server/npc_homes.py)."""
import asyncio
import json
import re
import sqlite3
import threading
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings, ROOT
from server.database import Database
from server import npc_homes
from server.npc_homes import NPCS, SLOTS, fits, item_tags


def mutation(**kw):
    return {'request_id': str(uuid.uuid4()), **kw}


def account(c, name, path='/v1/auth/register'):
    r = c.post(path, json={'username': name, 'password': 'Gift-test-password'})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


@pytest.fixture
def world(tmp_path):
    now = [1_800_000_000.0]
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100, user_daily_generation_limit=50,
                        npc_place_min=10, npc_place_max=20, npc_shuffle_min=100, npc_shuffle_max=200, npc_seed=7)
    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as c:
        yield app, c, now


def craft(app, c, h, prompt):
    with sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3') as db:
        db.execute('UPDATE users SET shards=500')
    reply = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt=prompt))
    assert reply.status_code == 200, reply.text
    job = reply.json()['id']
    asyncio.run(app.state.studio.process(job))
    result = c.get('/v1/studio/jobs/' + job, headers=h).json()
    assert result['state'] == 'ready', result
    return obj(c, h, result['object_id'])


def obj(c, h, object_id):
    return next((o for o in c.get('/v1/me', headers=h).json()['objects'] if o['id'] == object_id), None)


def give(c, h, npc, item, **kw):
    return c.post(f'/v1/npcs/{npc}/gift', headers=h, json=mutation(object_id=item['id'], version=item['version'], **kw))


def home(c, h, home_id, version=None):
    reply = c.get('/v1/social/npc-homes/' + home_id + ('' if version is None else f'?version={version}'), headers=h)
    assert reply.status_code == 200, reply.text
    return reply.json()


def visit(c, host, guest, guest_name):
    invite = c.post('/v1/social/invites', headers=host, json=mutation(username=guest_name, kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=guest, json=mutation()).json()['visiting']


def test_gift_moves_a_crafted_piece_out_of_the_bag_exactly_once(world):
    app, c, now = world
    h = account(c, 'alice')
    chest = craft(app, c, h, 'wooden chest')
    options = c.get('/v1/npcs/naru/gift', headers=h).json()
    assert options['can_gift'] and options['home'] == '02_timber_house' and [i['id'] for i in options['items']] == [chest['id']]
    body = mutation(object_id=chest['id'], version=chest['version'])
    first = c.post('/v1/npcs/naru/gift', headers=h, json=body)
    assert first.status_code == 200, first.text
    reply = first.json()
    assert reply['object_id'] == chest['id'] and reply['mood'] in ('love', 'like', 'thanks') and reply['friendship']['gifts'] == 1
    # A replay of the same request is the same answer, not a second gift.
    assert c.post('/v1/npcs/naru/gift', headers=h, json=body).json() == reply
    assert c.get('/v1/npcs/naru/gift', headers=h).json()['friendship']['gifts'] == 1
    # Gone from the bag, the studio list and every owner route; never offered again.
    assert obj(c, h, chest['id']) is None
    assert chest['id'] not in [o['id'] for o in c.get('/v1/studio', headers=h).json()['objects']]
    assert c.get('/v1/npcs/sora/gift', headers=h).json()['items'] == []
    for path in ('/model', '/assembly'):
        assert c.get('/v1/objects/' + chest['id'] + path, headers=h).status_code == 404
    gifted = {**chest, 'version': chest['version'] + 1}
    assert c.post('/v1/objects/' + chest['id'] + '/placement', headers=h, json=mutation(version=gifted['version'], room='home', x=1, z=1)).status_code == 404
    assert c.post('/v1/market', headers=h, json=mutation(object_id=chest['id'], version=gifted['version'], price=5)).status_code == 404
    again = give(c, h, 'sora', gifted)
    assert again.status_code == 404 and again.json()['detail'] == 'object_not_found'
    with sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3') as db:
        assert db.execute('SELECT state FROM objects WHERE id=?', (chest['id'],)).fetchone()[0] == 'gifted'
        assert db.execute('SELECT count(*) FROM npc_items WHERE object_id=?', (chest['id'],)).fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM npc_gifts').fetchone()[0] == 1


def test_gift_validation(world):
    app, c, now = world
    h, other = account(c, 'alice'), account(c, 'bravo')
    starter = c.get('/v1/me', headers=h).json()['objects'][0]
    assert give(c, h, 'nobody', starter).status_code == 404
    assert give(c, h, 'naru', starter).json()['detail'] == 'gift_needs_crafted_furniture'
    chest = craft(app, c, h, 'wooden chest')
    assert give(c, h, 'naru', {**chest, 'version': chest['version'] + 1}).json()['detail'] == 'stale_object_version'
    assert give(c, other, 'naru', chest).json()['detail'] == 'object_not_found'
    placed = c.post('/v1/objects/' + chest['id'] + '/placement', headers=h, json=mutation(version=chest['version'], room='home', x=1, z=1))
    assert placed.status_code == 200, placed.text
    chest = obj(c, h, chest['id'])
    assert give(c, h, 'naru', chest).json()['detail'] == 'object_not_in_inventory'
    c.post('/v1/objects/' + chest['id'] + '/placement', headers=h, json=mutation(version=chest['version'], action='retrieve', room='home'))
    chest = obj(c, h, chest['id'])
    listed = c.post('/v1/market', headers=h, json=mutation(object_id=chest['id'], version=chest['version'], price=5))
    assert listed.status_code == 200, listed.text
    assert give(c, h, 'naru', obj(c, h, chest['id'])).json()['detail'] == 'object_not_in_inventory'
    # A visitor cannot give to the host's residents (homes are per village owner).
    lamp = craft(app, c, other, 'flower lamp')
    visit(c, h, other, 'bravo')
    assert not c.get('/v1/npcs/naru/gift', headers=other).json()['can_gift']
    assert give(c, other, 'naru', lamp).json()['detail'] == 'gift_own_village_only'


def test_concurrent_gifts_of_one_piece_only_one_wins(world):
    app, c, now = world
    h = account(c, 'alice')
    chest = craft(app, c, h, 'wooden chest')
    results = []

    def send(npc):
        results.append(give(c, h, npc, chest).status_code)
    threads = [threading.Thread(target=send, args=(npc,)) for npc in ('naru', 'sora', 'moru', 'haeru')]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results).count(200) == 1
    with sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM npc_items').fetchone()[0] == 1


def test_resident_puts_the_gift_up_after_the_delay(world):
    app, c, now = world
    h = account(c, 'alice')
    chest = craft(app, c, h, 'wooden chest')
    assert give(c, h, 'naru', chest).status_code == 200
    first = home(c, h, '02_timber_house')
    assert first['items'] == []
    assert home(c, h, '02_timber_house', first['version']) == {'home': '02_timber_house', 'version': first['version'], 'unchanged': True}
    now[0] += 9  # before the shortest delay
    assert home(c, h, '02_timber_house', first['version']).get('unchanged')
    now[0] += 12  # past the longest delay
    after = home(c, h, '02_timber_house', first['version'])
    assert after['version'] == first['version'] + 1
    [item] = after['items']
    slot = npc_homes.SLOT_BY_ID['02_timber_house'][item['slot']]
    assert item['id'] == chest['id'] and item['npc'] == 'naru' and fits(slot, item['size']) is not None
    assert item['floor'] == slot['floor'] and item['studio'] and item['runtime_version'] is not None
    # The owner's poll carries the version; the owner and the guest route read the piece.
    assert c.get('/v1/me', headers=h).json()['npc_homes'] == {'02_timber_house': after['version']}
    assert c.get('/v1/social/village/objects/' + chest['id'] + '/assembly', headers=h).status_code == 200


def test_same_seed_same_rooms(tmp_path):
    def run(folder):
        now = [1_800_000_000.0]
        settings = Settings(data_dir=folder, daily_generation_limit=100, user_daily_generation_limit=50,
                            npc_place_min=10, npc_place_max=20, npc_shuffle_min=100, npc_shuffle_max=200, npc_seed=11)
        app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
        with TestClient(app) as c:
            h = account(c, 'alice')
            for prompt in ('wooden chest', 'flower lamp', 'wooden crate'):
                assert give(c, h, 'naru', craft(app, c, h, prompt)).status_code == 200
            seen = []
            for _ in range(8):
                now[0] += 150
                seen.append(sorted((i['name'], i['slot']) for i in home(c, h, '02_timber_house')['items']))
            return seen
    assert run(tmp_path / 'a') == run(tmp_path / 'b')


def test_later_changes_put_back_bring_out_and_move(world):
    app, c, now = world
    h = account(c, 'alice')
    names = {}
    for prompt in ('wooden chest', 'flower lamp', 'wooden crate', 'blue chest'):
        piece = craft(app, c, h, prompt)
        names[piece['id']] = prompt
        assert give(c, h, 'naru', piece).status_code == 200
    now[0] += 4 * 20 + 1  # every gift's first turn
    layouts, versions = [], []
    for _ in range(40):
        reply = home(c, h, '02_timber_house')
        slots = [i['slot'] for i in reply['items']]
        assert len(slots) == len(set(slots))  # one piece per slot
        for item in reply['items']:
            assert fits(npc_homes.SLOT_BY_ID['02_timber_house'][item['slot']], item['size']) is not None
        layouts.append(tuple(sorted((i['id'], i['slot']) for i in reply['items'])))
        versions.append(reply['version'])
        now[0] += 201  # at least one rearrangement each time
    assert len(set(layouts)) >= 4
    assert versions == sorted(versions) and versions[-1] > versions[0]
    placed_counts = {len(layout) for layout in layouts}
    assert len(placed_counts) >= 2  # pieces went back into storage and came out again
    with sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3') as db:
        assert db.execute("SELECT count(*) FROM npc_items WHERE state='stored'").fetchone()[0] + \
            db.execute("SELECT count(*) FROM npc_items WHERE state='placed'").fetchone()[0] == 4


def test_long_absence_catches_up_and_skips_ahead(world):
    app, c, now = world
    h = account(c, 'alice')
    assert give(c, h, 'naru', craft(app, c, h, 'wooden chest')).status_code == 200
    now[0] += 365 * 86400
    h = account(c, 'alice', '/v1/auth/login')  # sessions last 12 hours
    reply = home(c, h, '02_timber_house')
    assert len(reply['items']) == 1
    with sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3') as db:
        assert db.execute('SELECT next_change_at FROM npc_homes').fetchone()[0] > now[0]


def test_homes_are_per_player_and_visitors_see_the_host_rooms(world):
    app, c, now = world
    alice, bravo = account(c, 'alice'), account(c, 'bravo')
    chest = craft(app, c, alice, 'wooden chest')
    lamp = craft(app, c, alice, 'flower lamp')
    assert give(c, alice, 'naru', chest).status_code == 200
    now[0] += 21
    assert len(home(c, alice, '02_timber_house')['items']) == 1
    assert give(c, alice, 'naru', lamp).status_code == 200  # still in storage for a while
    # Bravo's own village: Naru's house is empty, and his poll has no homes.
    assert home(c, bravo, '02_timber_house')['items'] == []
    assert c.get('/v1/me', headers=bravo).json()['npc_homes'] == {}
    # Visiting Alice: the guest route shows Alice's rooms; only pieces standing out are readable.
    visit(c, alice, bravo, 'bravo')
    seen = home(c, bravo, '02_timber_house')
    assert [i['id'] for i in seen['items']] == [chest['id']] and seen['host_id'] != c.get('/v1/social', headers=bravo).json()['self_id']
    assert c.get('/v1/social/village/objects/' + chest['id'] + '/assembly', headers=bravo).status_code == 200
    assert c.get('/v1/social/village/objects/' + lamp['id'] + '/assembly', headers=bravo).status_code == 404
    presence = c.post('/v1/social/presence', headers=bravo, json={'scene': 'village', 'x': 0, 'z': 0, 'yaw': 0})
    assert presence.status_code == 200, presence.text
    assert presence.json()['npc_homes'] == {'02_timber_house': seen['version']}
    # The lamp's turn comes while Bravo polls: both see the same new version.
    now[0] += 21
    assert c.post('/v1/social/presence', headers=bravo, json={'scene': 'village', 'x': 0, 'z': 0, 'yaw': 0}).json()['npc_homes']['02_timber_house'] == seen['version'] + 1
    assert len(home(c, bravo, '02_timber_house')['items']) == len(home(c, alice, '02_timber_house')['items']) == 2


def test_friendship_counts_the_first_gift_of_the_day_most(world):
    app, c, now = world
    h = account(c, 'alice')
    first = give(c, h, 'naru', craft(app, c, h, 'wooden chest')).json()
    second = give(c, h, 'naru', craft(app, c, h, 'wooden crate')).json()
    assert not first['again'] and second['again'] and second['gain'] == npc_homes.GAIN_AGAIN
    assert second['friendship']['points'] == first['gain'] + second['gain']
    now[0] += 86400
    h = account(c, 'alice', '/v1/auth/login')
    third = give(c, h, 'naru', craft(app, c, h, 'blue chest')).json()
    assert not third['again'] and third['gain'] >= npc_homes.GAIN['thanks']


def test_tags_slots_and_fit():
    assert {'light', 'plant'} <= set(item_tags('꽃 조명', 'flower_lamp'))
    assert 'sea' not in item_tags('oak cabinet') and 'storage' in item_tags('oak cabinet')
    wall = {'kind': 'wall', 'yaw': 90, 'max': (0.8, 0.9, 0.3)}
    assert fits(wall, [0.6, 0.6, 0.1]) == 90 and fits(wall, [0.3, 0.3, 0.3]) is None
    floor = {'kind': 'floor', 'yaw': 0, 'max': (1.0, 2.0, 1.4)}
    assert fits(floor, [0.8, 1, 1.2]) == 0 and fits(floor, [1.3, 1, 0.9]) == 90 and fits(floor, [0.5, 2.5, 0.5]) is None


def test_residents_and_slots_match_the_client():
    """The giftable residents live where residents.gd says, and every slot lies on its floor."""
    residents = (ROOT / 'game/scripts/residents.gd').read_text(encoding='utf-8')
    for npc_id, npc in NPCS.items():
        assert re.search(r'"id":"%s",[^}]*"home":"%s"' % (npc_id, npc['home']), residents), npc_id
    interiors = (ROOT / 'game/scripts/interiors.gd').read_text(encoding='utf-8')
    for home_id, slots in SLOTS.items():
        plan = re.search(r'"%s":\[(.*)\],?\n' % home_id, interiors).group(1)
        floors = [(float(w), float(d)) for w, d in re.findall(r'"w":([0-9.]+),"d":([0-9.]+)', plan)]
        assert {s['id'] for s in slots} == set(npc_homes.SLOT_BY_ID[home_id]) and len(slots) == len(set(s['id'] for s in slots))
        for s in slots:
            w, d = floors[s['floor']]
            margin = 0 if s['kind'] == 'wall' else 0.3
            assert abs(s['x']) <= w / 2 - margin and abs(s['z']) <= d / 2 - margin, (home_id, s['id'])


def test_old_worlds_gain_the_gifted_state(tmp_path):
    path = tmp_path / 'world.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO metadata VALUES ('mode','demo');
CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 shards INTEGER NOT NULL DEFAULT 0 CHECK(shards>=0), created REAL NOT NULL);
INSERT INTO users VALUES ('u1','old','x',3,1.0);
CREATE TABLE objects (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), creator_id TEXT NOT NULL REFERENCES users(id),
 asset_id TEXT NOT NULL, name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#f6eee0',
 version INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL DEFAULT 'inventory' CHECK(state IN ('inventory','placed','listed')),
 x REAL, z REAL, rotation INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
INSERT INTO objects(id,owner_id,creator_id,asset_id,name,state,x,z,created) VALUES ('o1','u1','u1','starter','chair','placed',1,2,1.0);
CREATE TABLE listings (id TEXT PRIMARY KEY, object_id TEXT NOT NULL REFERENCES objects(id), seller_id TEXT NOT NULL REFERENCES users(id),
 price INTEGER NOT NULL CHECK(price>0), state TEXT NOT NULL CHECK(state IN('open','sold','cancelled')), buyer_id TEXT REFERENCES users(id), created REAL NOT NULL);
INSERT INTO listings VALUES ('l1','o1','u1',5,'cancelled',NULL,1.0);
''')
    Database(path, 'demo')
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        assert "'gifted'" in db.execute("SELECT sql FROM sqlite_master WHERE name='objects'").fetchone()[0]
        assert db.execute('SELECT id,state,x,z FROM objects').fetchall() == [('o1', 'placed', 1.0, 2.0)]
        db.execute("UPDATE objects SET state='gifted' WHERE id='o1'")
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    Database(path, 'demo')  # a second start leaves it alone


def test_operator_view(world, capsys):
    app, c, now = world
    h = account(c, 'alice')
    assert give(c, h, 'naru', craft(app, c, h, 'wooden chest')).status_code == 200
    from server import admin_cli
    assert admin_cli.main(['npc-homes', 'alice', '--data-dir', str(app.state.settings.data_dir)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown['items'][0]['npc_id'] == 'naru' and shown['items'][0]['state'] == 'stored'
    assert shown['homes'][0]['home_id'] == '02_timber_house' and shown['friendship'][0]['gifts'] == 1
