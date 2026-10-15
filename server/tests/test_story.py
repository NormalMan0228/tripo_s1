"""The opening story chapter "마을의 첫 선물" (server/story.py): letter -> café -> 모카's request ->
any crafted piece on the café terrace at once -> thank-you letter with a return gift; relogin, the
operator reset and accounts made before the chapter."""
import asyncio
import json
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server import admin_cli, story
from server.npc_homes import SLOT_BY_ID


def mutation(**kw):
    return {'request_id': str(uuid.uuid4()), **kw}


def account(c, name, password='Story-test-password'):
    r = c.post('/v1/auth/register', json={'username': name, 'password': password})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


def login(c, name, password='Story-test-password'):
    r = c.post('/v1/auth/login', json={'username': name, 'password': password})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


@pytest.fixture
def world(tmp_path):
    now = [1_800_000_000.0]
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100, user_daily_generation_limit=50)
    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as c:
        yield app, c, now


def db(app):
    conn = sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn


def craft(app, c, h, prompt, now):
    with db(app) as conn:
        conn.execute('UPDATE users SET shards=500')
    now[0] += 5
    reply = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt=prompt))
    assert reply.status_code == 200, reply.text
    job = reply.json()['id']
    asyncio.run(app.state.studio.process(job))
    result = c.get('/v1/studio/jobs/' + job, headers=h).json()
    assert result['state'] == 'ready', result
    return next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['id'] == result['object_id'])


def state(c, h):
    return c.get('/v1/story', headers=h).json()['story']


def step(c, h, action, **kw):
    r = c.post('/v1/story/step', headers=h, json=mutation(action=action, **kw))
    assert r.status_code == 200, r.text
    return r.json()['story']


def give(c, h, item):
    return c.post('/v1/story/gift', headers=h, json=mutation(object_id=item['id'], version=item['version']))


def test_a_new_account_walks_the_chapter_and_the_chair_stands_on_the_terrace(world):
    app, c, now = world
    h = account(c, 'maker')
    first = c.get('/v1/me', headers=h).json()['story']
    assert first['step'] == 'letter' and first['chapter'] == 'first_gift' and first['run'] == 1 and first['greeted'] == []
    assert step(c, h, 'read_letter')['step'] == 'cafe'
    # Residents greet once each; a repeat or an unknown name changes nothing.
    assert step(c, h, 'greet', npc='postman')['greeted'] == ['postman']
    assert step(c, h, 'greet', npc='postman')['greeted'] == ['postman']
    assert c.post('/v1/story/step', headers=h, json=mutation(action='greet', npc='nobody')).status_code == 422
    assert c.post('/v1/story/step', headers=h, json=mutation(action='greet', npc='Bad-Name')).status_code == 422
    asked = step(c, h, 'accept')
    assert asked['step'] == 'craft' and asked['made'] == [] and asked['crafting'] is False
    # The welcome chair was in the bag before 모카 asked: not offered first.
    chair = craft(app, c, h, '카페 테라스에 둘 나무 의자', now)
    made = state(c, h)['made']
    assert [m['id'] for m in made] == [chair['id']]
    reply = give(c, h, chair)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body['sittable'] is True and body['story']['step'] == 'done' and body['story']['gift']['sittable'] is True
    slot = SLOT_BY_ID['cafe_terrace']['terrace']
    assert body['placed']['id'] == chair['id'] and (body['placed']['x'], body['placed']['z']) == (slot['x'], slot['z'])
    # Out of the bag at once, on the terrace for good (no random delay).
    assert chair['id'] not in [o['id'] for o in c.get('/v1/me', headers=h).json()['objects']]
    terrace = c.get('/v1/social/npc-homes/cafe_terrace', headers=h).json()
    assert [i['id'] for i in terrace['items']] == [chair['id']] and terrace['items'][0]['npc'] == 'regular'
    assert c.get('/v1/social/village/objects/' + chair['id'] + '/assembly', headers=h).status_code == 200
    # 모카's thank-you letter with a present, in the mailbox.
    letter = body['letters'][0]
    assert letter['npc'] == 'regular' and letter['name'] == '모카' and letter['level'] == 0
    assert letter['story'] == {'chapter': 'first_gift', 'object': chair['name'], 'sittable': True}
    present = letter['gift']
    assert present and '모카의 답례' in present['name']
    bag = {o['id']: o for o in c.get('/v1/me', headers=h).json()['objects']}
    assert bag[present['id']]['studio'] and bag[present['id']]['state'] == 'inventory'
    mail = c.get('/v1/letters', headers=h).json()
    assert mail['unread'] == 1 and mail['letters'][0]['id'] == letter['id']
    assert c.get('/v1/me', headers=h).json()['npc_letters_unread'] == 1
    c.post('/v1/letters/read', headers=h, json=mutation(ids=[letter['id']]))
    assert state(c, h)['letter']['read'] is True
    # Done is done: no second gift.
    other = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['state'] == 'inventory')
    assert give(c, h, other).status_code == 409


def test_any_piece_is_welcome_and_a_lamp_decorates_the_terrace(world):
    app, c, now = world
    h = account(c, 'lamper')
    step(c, h, 'read_letter')
    step(c, h, 'accept')
    lamp = craft(app, c, h, '등불', now)
    reply = give(c, h, lamp).json()
    assert reply['sittable'] is False and reply['story']['gift'] == {'id': lamp['id'], 'name': lamp['name'], 'sittable': False}
    assert reply['letters'][0]['story']['sittable'] is False
    assert [i['id'] for i in c.get('/v1/social/npc-homes/cafe_terrace', headers=h).json()['items']] == [lamp['id']]


def test_a_placed_piece_and_the_welcome_chair_count_and_the_story_never_stalls(world):
    app, c, now = world
    h = account(c, 'placer')
    # Given straight from the first step (talking to 모카 before reading the letter), and a piece
    # already set down in the village: both fine.
    welcome = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
    placed = c.post('/v1/objects/' + welcome['id'], headers=h, json=mutation(action='place', x=4.0, z=4.0, rotation=0, version=welcome['version']))
    assert placed.status_code == 200, placed.text
    moved = placed.json()
    assert moved['state'] == 'placed'
    reply = give(c, h, moved)
    assert reply.status_code == 200, reply.text
    assert reply.json()['sittable'] is True and reply.json()['story']['step'] == 'done'
    with db(app) as conn:
        assert conn.execute('SELECT count(*) FROM furniture_locations WHERE object_id=?', (welcome['id'],)).fetchone()[0] == 0


def test_refusals_stale_versions_listed_pieces_and_visits(world):
    app, c, now = world
    h = account(c, 'refuser')
    guest = account(c, 'visitor')
    step(c, h, 'accept')
    lamp = craft(app, c, h, '등불', now)
    assert give(c, h, {**lamp, 'version': lamp['version'] + 1}).status_code == 409
    assert give(c, guest, lamp).status_code == 404
    listed = c.post('/v1/market', headers=h, json=mutation(object_id=lamp['id'], version=lamp['version'], price=10))
    assert listed.status_code == 200, listed.text
    again = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['id'] == lamp['id'])
    assert give(c, h, again).json()['detail'] == 'object_is_listed'
    # While visiting a friend, the gift waits for the player's own village.
    invite = c.post('/v1/social/invites', headers=h, json=mutation(username='visitor', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=guest, json=mutation()).json()['visiting']
    welcome = next(o for o in c.get('/v1/me', headers=guest).json()['objects'] if o['name'] == '환영의 나무 의자')
    assert give(c, guest, welcome).json()['detail'] == 'gift_own_village_only'


def test_a_visitor_sees_the_hosts_terrace(world):
    app, c, now = world
    host = account(c, 'hosting')
    guest = account(c, 'guesting')
    step(c, host, 'accept')
    chair = craft(app, c, host, '의자', now)
    assert give(c, host, chair).status_code == 200
    invite = c.post('/v1/social/invites', headers=host, json=mutation(username='guesting', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=guest, json=mutation()).json()['visiting']
    seen = c.get('/v1/social/npc-homes/cafe_terrace', headers=guest).json()
    assert [i['id'] for i in seen['items']] == [chair['id']]
    assert c.get('/v1/social/village/objects/' + chair['id'] + '/assembly', headers=guest).status_code == 200
    # The guest's own chapter is theirs.
    assert state(c, guest)['step'] == 'letter'


def test_progress_survives_signing_in_again_and_a_restart(world, tmp_path):
    app, c, now = world
    h = account(c, 'returner')
    step(c, h, 'read_letter')
    step(c, h, 'greet', npc='naru')
    step(c, h, 'accept')
    c.post('/v1/auth/logout', headers=h)
    again = login(c, 'returner')
    kept = c.get('/v1/me', headers=again).json()['story']
    assert kept['step'] == 'craft' and kept['greeted'] == ['naru']
    restarted = create_app(app.state.settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(restarted) as fresh:
        assert fresh.get('/v1/story', headers=login(fresh, 'returner')).json()['story']['step'] == 'craft'


def test_accounts_from_before_the_chapter_and_switched_off_servers_never_see_it(world, tmp_path):
    app, c, now = world
    h = account(c, 'veteran')
    with db(app) as conn:
        conn.execute('DELETE FROM story_progress')
    assert c.get('/v1/me', headers=h).json()['story'] is None
    assert c.post('/v1/story/step', headers=h, json=mutation(action='read_letter')).status_code == 404
    off = create_app(Settings(data_dir=tmp_path / 'off', story_enabled=False), clock=lambda: now[0], worker_enabled=False)
    with TestClient(off) as other:
        assert other.get('/v1/story', headers=account(other, 'quiet')).json()['story'] is None


def test_the_operator_reset_starts_again_and_keeps_everything_else(world, capsys):
    app, c, now = world
    h = account(c, 'rehearsal')
    step(c, h, 'read_letter')
    step(c, h, 'greet', npc='kid')
    step(c, h, 'accept')
    chair = craft(app, c, h, '의자', now)
    first = give(c, h, chair).json()
    present = first['letters'][0]['gift']['id']
    data = str(app.state.settings.data_dir)
    assert admin_cli.main(['story', 'show', 'rehearsal', '--data-dir', data]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown['progress']['step'] == 'done' and shown['terrace'][0]['object_id'] == chair['id']
    assert admin_cli.main(['story', 'reset', 'rehearsal', '--data-dir', data]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['ok'] and result['run'] == 2 and result['returned_to_bag'] == [chair['id']]
    fresh = state(c, h)
    assert fresh['step'] == 'letter' and fresh['run'] == 2 and fresh['greeted'] == []
    # The chair is back in the bag (newer version), the present and the letter stay; the terrace is empty.
    bag = {o['id']: o for o in c.get('/v1/me', headers=h).json()['objects']}
    assert bag[chair['id']]['state'] == 'inventory' and bag[chair['id']]['version'] == chair['version'] + 2
    assert present in bag and len(c.get('/v1/letters', headers=h).json()['letters']) == 1
    assert c.get('/v1/social/npc-homes/cafe_terrace', headers=h).json()['items'] == []
    # The second run gives the same chair again and writes its own letter.
    now[0] += 60
    step(c, h, 'read_letter')
    step(c, h, 'accept')
    second = give(c, h, bag[chair['id']])
    assert second.status_code == 200, second.text
    assert second.json()['letters'][0]['level'] == 0 and len(c.get('/v1/letters', headers=h).json()['letters']) == 2
    # An account made before the chapter starts it through the same reset.
    veteran = account(c, 'olduser')
    with db(app) as conn:
        conn.execute("DELETE FROM story_progress WHERE user_id=(SELECT id FROM users WHERE username='olduser')")
    assert state(c, veteran) is None
    assert admin_cli.main(['story', 'reset', 'olduser', '--data-dir', data]) == 0
    assert json.loads(capsys.readouterr().out)['run'] == 1 and state(c, veteran)['step'] == 'letter'
    assert admin_cli.main(['story', 'reset', 'nobody_here', '--data-dir', data]) == 1


def test_the_offline_designer_makes_a_real_chair():
    plan, _ = __import__('server.archetypes', fromlist=['fixture_design']).fixture_design('나무 의자')
    assert plan['category'] == 'seat' and len(plan['parts']) == 6
    assert story.RETURN_GIFT['parts'] and story.SENDER == 'regular'


def test_the_epilogue_daon_then_the_forest_gate_once_each_and_reset_clears_it(world, tmp_path, capsys):
    app, c, now = world
    h = account(c, 'epilogue')
    assert state(c, h)['events'] == []
    event = lambda name: c.post('/v1/story/step', headers=h, json=mutation(action='event', event=name))
    # Not before 모카 has her gift.
    assert event('forest_told').json()['detail'] == 'story_not_done'
    step(c, h, 'read_letter')
    step(c, h, 'accept')
    chair = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
    assert give(c, h, chair).status_code == 200
    assert event('forest_gate').json()['detail'] == 'story_event_order'
    assert event('lava_cave').status_code == 422
    assert event('forest_told').json()['story']['events'] == ['forest_told']
    now[0] += 3
    # A second report changes nothing; the gate comes after.
    assert event('forest_told').json()['story']['events'] == ['forest_told']
    assert event('forest_gate').json()['story']['events'] == ['forest_told', 'forest_gate']
    assert c.get('/v1/me', headers=h).json()['story']['events'] == ['forest_told', 'forest_gate']
    data = str(app.state.settings.data_dir)
    assert admin_cli.main(['story', 'show', 'epilogue', '--data-dir', data]) == 0
    assert [e['event'] for e in json.loads(capsys.readouterr().out)['events']] == ['forest_told', 'forest_gate']
    assert admin_cli.main(['story', 'reset', 'epilogue', '--data-dir', data]) == 0
    capsys.readouterr()
    assert state(c, h)['events'] == [] and state(c, h)['step'] == 'letter'


def test_epilogue_rescue_and_shop_unlock_share_the_completed_chapter(world):
    app, c, now = world
    app.state.settings.resident_moves = True
    h = account(c, 'rescuer')
    # Fetch directly so the gift route must initialize residency before setting done.
    with app.state.db.read() as conn:
        user = conn.execute("SELECT id FROM users WHERE username='rescuer'").fetchone()[0]
        chair = dict(conn.execute('SELECT id,version FROM objects WHERE owner_id=? LIMIT 1', (user,)).fetchone())
    assert c.get('/v1/shops/general_store', headers=h).json()['open'] is False
    for event in story.EVENTS:
        response = c.post('/v1/story/step', headers=h, json=mutation(action='event', event=event))
        assert response.status_code == 409 and response.json()['detail'] == 'story_not_done'
    assert give(c, h, chair).status_code == 200
    assert c.get('/v1/village/residency', headers=h).json()['residents'][0]['state'] == 'away'
    assert state(c, h)['flags'][story.DANBI_FLAG] is True
    # The patch's shop flag is an unlock, while the residency timer starts at rescue.
    assert c.get('/v1/shops/general_store', headers=h).json()['open'] is True
    early = c.post('/v1/story/step', headers=h, json=mutation(action='event', event='danbi_rescued'))
    assert early.json()['detail'] == 'story_event_order'
    for index, event in enumerate(story.EVENTS):
        body = mutation(action='event', event=event)
        response = c.post('/v1/story/step', headers=h, json=body)
        assert response.status_code == 200, response.text
        assert response.json()['story']['events'] == list(story.EVENTS[:index + 1])
        assert c.post('/v1/story/step', headers=h, json=body).json() == response.json()
    resident = c.get('/v1/village/residency', headers=h).json()['residents'][0]
    assert resident['state'] == 'arriving' and resident['memory']['met'] is True
    now[0] = resident['due_at']
    settled = c.get('/v1/village/residency', headers=h).json()
    assert settled['residents'][0]['state'] == 'home'
    assert [event['kind'] for event in settled['news']].count('moved_in') == 1


@pytest.mark.parametrize('reader', ['server', 'operator'])
def test_movein_story_event_timestamp_is_upgraded_without_losing_events(world, capsys, reader):
    app, c, now = world
    h = account(c, 'old_events')
    with app.state.db.transaction() as conn:
        user = conn.execute("SELECT id FROM users WHERE username='old_events'").fetchone()[0]
        conn.execute("UPDATE story_progress SET step='done' WHERE user_id=?", (user,))
        for event in story.EVENTS:
            conn.execute('INSERT INTO story_events VALUES (?,?,?)', (user, event, now[0]))
        conn.execute('ALTER TABLE story_events RENAME COLUMN at TO created')
    if reader == 'operator':
        assert admin_cli.main(['story', 'show', 'old_events', '--data-dir', str(app.state.settings.data_dir)]) == 0
        assert [event['event'] for event in json.loads(capsys.readouterr().out)['events']] == list(story.EVENTS)
    else:
        restarted = create_app(app.state.settings, clock=lambda: now[0], worker_enabled=False)
        with TestClient(restarted) as fresh:
            assert state(fresh, h)['events'] == list(story.EVENTS)
            assert state(fresh, h)['flags'][story.DANBI_FLAG] is True
        restarted.state.db.close()
    with app.state.db.read() as conn:
        columns = {row[1] for row in conn.execute('PRAGMA table_info(story_events)')}
        assert 'at' in columns and 'created' not in columns
