"""Residents' requests (server/quests.py): offered after the opening chapter (or at once without it),
each condition checked from the server's own data where it can be, one reward per account through
the ledger, the operator's scale/off switch and the refusals."""
import asyncio
import json
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server import admin_cli, homestead, quests


def mutation(**kw):
    return {'request_id': str(uuid.uuid4()), **kw}


def account(c, name, password='Quest-test-password'):
    r = c.post('/v1/auth/register', json={'username': name, 'password': password})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


def make(tmp_path, now, **kw):
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100, user_daily_generation_limit=50, **kw)
    return create_app(settings, clock=lambda: now[0], worker_enabled=False)


@pytest.fixture
def world(tmp_path):
    now = [1_800_000_000.0]
    app = make(tmp_path, now)
    with TestClient(app) as c:
        yield app, c, now


def db(app):
    conn = sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn


def free(app):
    """An account outside the opening chapter (made before it existed)."""
    with db(app) as conn:
        conn.execute('DELETE FROM story_progress')


def listing(c, h):
    return c.get('/v1/quests', headers=h).json()['quests']


def quest(c, h, quest_id):
    return next(q for q in listing(c, h)['list'] if q['id'] == quest_id)


def accept(c, h, quest_id):
    return c.post('/v1/quests/%s/accept' % quest_id, headers=h, json=mutation())


def complete(c, h, quest_id, body=None):
    return c.post('/v1/quests/%s/complete' % quest_id, headers=h, json=body or mutation())


def visit(c, h, place, quest_id='naru_islands'):
    return c.post('/v1/quests/%s/progress' % quest_id, headers=h, json=mutation(place=place))


def shards(c, h):
    return c.get('/v1/me', headers=h).json()['shards']


def paid(app, quest_id=None):
    with db(app) as conn:
        rows = conn.execute("SELECT reference,amount FROM ledger WHERE reason='quest_reward'").fetchall()
    return [(r['reference'], r['amount']) for r in rows if quest_id in (None, r['reference'])]


def bag(app, c, h, **items):
    """Puts these items in the player's homestead bag."""
    c.get('/v1/homestead', headers=h)
    me = c.get('/v1/me', headers=h).json()
    with db(app) as conn:
        user = conn.execute('SELECT id FROM users WHERE username=?', (me['username'],)).fetchone()['id']
        row = conn.execute('SELECT state FROM homesteads WHERE user_id=?', (user,)).fetchone()
        state = json.loads(row['state']) if row else homestead.initial()
        state['bag'].update(items)
        conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state', (user, json.dumps(state)))


def life(c, h):
    return c.get('/v1/homestead', headers=h).json()


def craft(app, c, h, prompt, now):
    with db(app) as conn:
        conn.execute('UPDATE users SET shards=shards+500')
    now[0] += 5
    reply = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt=prompt))
    assert reply.status_code == 200, reply.text
    job = reply.json()['id']
    asyncio.run(app.state.studio.process(job))
    result = c.get('/v1/studio/jobs/' + job, headers=h).json()
    assert result['state'] == 'ready', result
    return next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['id'] == result['object_id'])


def place(c, h, item, x, z):
    r = c.post('/v1/objects/' + item['id'], headers=h, json=mutation(version=item['version'], action='place', x=x, z=z))
    assert r.status_code == 200, r.text
    return r.json()


def test_requests_wait_for_the_opening_chapter_and_its_letter(world):
    app, c, now = world
    h = account(c, 'newcomer')
    first = c.get('/v1/me', headers=h).json()['quests']
    assert first['unlocked'] is False and {q['state'] for q in first['list']} == {'locked'}
    assert accept(c, h, 'moka_pie').json()['detail'] == 'quests_locked'
    # The chapter: letter, 모카's request, the welcome chair on the terrace.
    for action in ('read_letter', 'accept'):
        assert c.post('/v1/story/step', headers=h, json=mutation(action=action)).status_code == 200
    chair = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
    done = c.post('/v1/story/gift', headers=h, json=mutation(object_id=chair['id'], version=chair['version'])).json()
    assert done['story']['step'] == 'done'
    # Done, but 모카's letter is still unread: the chapter's last line comes first.
    assert listing(c, h)['unlocked'] is False
    c.post('/v1/letters/read', headers=h, json=mutation(ids=[done['letters'][0]['id']]))
    open_ = listing(c, h)
    assert open_['unlocked'] is True and {q['state'] for q in open_['list']} == {'available'}
    assert [q['npc'] for q in open_['list']] == ['regular', 'naru', 'sora', 'moru', 'haeru', 'postman', 'farmer', 'lamplighter']
    assert accept(c, h, 'moka_pie').status_code == 200


def test_every_request_runs_from_offer_to_one_reward(world):
    """Each request: offered, accepted, not ready, done by its own condition, paid once."""
    app, c, now = world
    h = account(c, 'helper')
    free(app)
    start = shards(c, h)
    total = 0
    lamp = craft(app, c, h, '등불', now)
    start = shards(c, h)
    for quest_id in quests.QUESTS:
        before = quest(c, h, quest_id)
        assert before['state'] == 'available' and before['stars'] == quests.STARS[quest_id], before
        now[0] += 10
        taken = accept(c, h, quest_id)
        assert taken.status_code == 200, taken.text
        assert taken.json()['quest']['state'] == 'active' and taken.json()['quest']['have'] == 0
        assert complete(c, h, quest_id).json()['detail'] == 'quest_not_ready'
        kind = quests.QUESTS[quest_id]['kind']
        now[0] += 10
        if kind == 'bring':
            need = quests.QUESTS[quest_id]['count']
            bag(app, c, h, **{quests.QUESTS[quest_id]['items'][0]: need})
        elif kind == 'visit':
            for island in ('square', 'fields', 'camp'):
                now[0] += 5
                assert visit(c, h, island).status_code == 200
        elif kind == 'outfit':
            look = c.get('/v1/me', headers=h).json()['profile']
            avatar = {**look['avatar'], 'coat': '#336699'}
            assert c.post('/v1/profile', headers=h, json=mutation(version=look['version'], avatar=avatar)).status_code == 200
        elif kind == 'gift':
            chair = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
            assert c.post('/v1/npcs/postman/gift', headers=h, json=mutation(object_id=chair['id'], version=chair['version'])).status_code == 200
        else:
            place(c, h, lamp, 20, 20)
        ready = quest(c, h, quest_id)
        assert ready['state'] == 'ready' and ready['have'] == ready['need'], ready
        body = mutation()
        reply = complete(c, h, quest_id, body)
        assert reply.status_code == 200, reply.text
        result = reply.json()
        assert result['stars'] == quests.STARS[quest_id] and result['quest']['state'] == 'done'
        total += result['stars']
        assert result['shards'] == start + total
        # The same request again changes nothing (the replay answers as before).
        assert complete(c, h, quest_id, body).json() == result
        assert complete(c, h, quest_id).json()['detail'] == 'quest_already_done'
        assert accept(c, h, quest_id).json()['detail'] == 'quest_already_done'
        assert paid(app, quest_id) == [(quest_id, quests.STARS[quest_id])]
    assert shards(c, h) == start + total == start + sum(quests.STARS.values())
    # About one craft in all.
    assert 35 <= sum(quests.STARS.values()) <= 60 and all(5 <= v <= 15 for v in quests.STARS.values())
    assert {q['state'] for q in listing(c, h)['list']} == {'done'}


def test_bring_takes_the_items_from_the_bag_cheapest_first(world):
    app, c, now = world
    h = account(c, 'angler')
    free(app)
    accept(c, h, 'haeru_fish')
    # Pond fish do not count; a sea fish does.
    bag(app, c, h, perch=3)
    assert quest(c, h, 'haeru_fish')['state'] == 'active'
    bag(app, c, h, tuna=1, mackerel=1)
    version = life(c, h)['version']
    reply = complete(c, h, 'haeru_fish').json()
    assert reply['taken'] == {'mackerel': 1}
    after = life(c, h)
    assert after['bag'].get('mackerel') == 0 and after['bag']['tuna'] == 1 and after['bag']['perch'] == 3
    assert after['version'] == version + 1 and reply['homestead']['version'] == after['version']
    # Mushrooms: plain ones go before the golden one.
    accept(c, h, 'moru_soup')
    bag(app, c, h, mushroom=1, gold_mushroom=2)
    assert complete(c, h, 'moru_soup').json()['taken'] == {'mushroom': 1, 'gold_mushroom': 1}
    assert life(c, h)['bag']['gold_mushroom'] == 1


def test_visits_count_each_island_once_with_a_gap(world):
    app, c, now = world
    h = account(c, 'walker')
    free(app)
    assert visit(c, h, 'square').json()['detail'] == 'quest_not_active'
    accept(c, h, 'naru_islands')
    assert visit(c, h, 'moon').status_code == 422
    assert visit(c, h, 'Square').status_code == 422
    assert visit(c, h, 'square').json()['quest']['have'] == 1
    # Too soon after the last one; the same island again counts once.
    assert visit(c, h, 'fields').status_code == 429
    now[0] += quests.VISIT_GAP
    assert visit(c, h, 'square').json()['quest']['have'] == 1
    assert visit(c, h, 'fields').json()['quest']['visited'] == ['square', 'fields']
    now[0] += 10
    assert visit(c, h, 'lighthouse').json()['quest']['state'] == 'ready'
    now[0] += 10
    assert visit(c, h, 'camp').json()['quest']['have'] == 3
    # Reports go to visit requests only.
    accept(c, h, 'moka_pie')
    assert visit(c, h, 'square', 'moka_pie').json()['detail'] == 'quest_wrong_kind'


def test_outfit_and_gift_count_only_after_the_request(world):
    app, c, now = world
    h = account(c, 'dresser')
    free(app)
    look = c.get('/v1/me', headers=h).json()['profile']
    assert c.post('/v1/profile', headers=h, json=mutation(version=look['version'], avatar={**look['avatar'], 'coat': '#aa3355'})).status_code == 200
    accept(c, h, 'sora_outfit')
    assert quest(c, h, 'sora_outfit')['state'] == 'active'
    look = c.get('/v1/me', headers=h).json()['profile']
    c.post('/v1/profile', headers=h, json=mutation(version=look['version'], avatar={**look['avatar'], 'coat': '#225588'}))
    assert quest(c, h, 'sora_outfit')['state'] == 'ready'
    # A gift made before 다온 asked does not count.
    lamp = craft(app, c, h, '등불', now)
    assert c.post('/v1/npcs/naru/gift', headers=h, json=mutation(object_id=lamp['id'], version=lamp['version'])).status_code == 200
    now[0] += 5
    accept(c, h, 'daon_gift')
    assert quest(c, h, 'daon_gift')['have'] == 0
    now[0] += 5
    chair = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
    c.post('/v1/npcs/kid/gift', headers=h, json=mutation(object_id=chair['id'], version=chair['version']))
    assert quest(c, h, 'daon_gift')['state'] == 'ready'


def test_a_light_must_glow_and_stand_in_the_village(world):
    app, c, now = world
    h = account(c, 'lighter')
    free(app)
    accept(c, h, 'noeul_light')
    chair = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
    place(c, h, chair, 20, 20)
    assert quest(c, h, 'noeul_light')['state'] == 'active'
    lamp = craft(app, c, h, '등불', now)
    # In the bag it lights nothing; in the player's own room neither.
    assert quest(c, h, 'noeul_light')['state'] == 'active'
    with db(app) as conn:
        conn.execute("UPDATE objects SET state='placed',x=1,z=1 WHERE id=?", (lamp['id'],))
        conn.execute("INSERT INTO furniture_locations VALUES (?,'home')", (lamp['id'],))
    assert quest(c, h, 'noeul_light')['state'] == 'active'
    with db(app) as conn:
        conn.execute("UPDATE furniture_locations SET room='village' WHERE object_id=?", (lamp['id'],))
    assert quest(c, h, 'noeul_light')['state'] == 'ready'
    reply = complete(c, h, 'noeul_light').json()
    assert reply['stars'] == 8 and reply['letters'][0]['npc'] == 'lamplighter'
    assert reply['letters'][0]['quest'] == {'npc': 'lamplighter'} and reply['letters'][0]['name'] == '노을'
    # The lamp stays where it stands.
    assert next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['id'] == lamp['id'])['state'] == 'placed'


def test_thank_you_letters_come_once(world):
    app, c, now = world
    h = account(c, 'baker')
    free(app)
    accept(c, h, 'moka_pie')
    bag(app, c, h, apple=5)
    reply = complete(c, h, 'moka_pie').json()
    letter = reply['letters'][0]
    assert letter['npc'] == 'regular' and letter['name'] == '모카' and letter['quest'] == {'npc': 'regular'} and letter['level'] == 0
    assert life(c, h)['bag']['apple'] == 2
    mail = c.get('/v1/letters', headers=h).json()
    assert mail['unread'] == 1 and mail['letters'][0]['id'] == letter['id'] and 'story' not in mail['letters'][0]
    # Other requests send no letter.
    accept(c, h, 'hangyeol_turnips')
    bag(app, c, h, turnip=2)
    assert complete(c, h, 'hangyeol_turnips').json()['letters'] == []


def test_the_operator_scale_and_off_switch(tmp_path):
    now = [1_800_000_000.0]
    off = make(tmp_path / 'off', now, quest_stars_scale=0)
    with TestClient(off) as c:
        h = account(c, 'unpaid')
        free(off)
        assert quest(c, h, 'moka_pie')['stars'] == 0 and listing(c, h)['scale'] == 0
        accept(c, h, 'moka_pie')
        bag(off, c, h, apple=3)
        before = shards(c, h)
        reply = complete(c, h, 'moka_pie').json()
        assert reply['stars'] == 0 and reply['quest']['state'] == 'done' and shards(c, h) == before
        assert paid(off) == []
    double = make(tmp_path / 'double', now, quest_stars_scale=2.0)
    with TestClient(double) as c:
        h = account(c, 'doubled')
        free(double)
        accept(c, h, 'hangyeol_turnips')
        bag(double, c, h, turnip=2)
        assert complete(c, h, 'hangyeol_turnips').json()['stars'] == 10
    # A request that may need a craft never pays more than the cheapest craft.
    assert quests.reward('noeul_light', 5.0) == quests.CRAFT_FLOOR and quests.reward('moka_pie', 5.0) == 40
    assert quests.reward('moka_pie', 0.5) == 4 and quests.reward('daon_gift', 0) == 0
    for bad in (-1, 6, float('nan')):
        with pytest.raises(ValueError):
            Settings(data_dir=tmp_path / 'bad', quest_stars_scale=bad).validate()


def test_refusals(world):
    app, c, now = world
    h = account(c, 'refused')
    guest = account(c, 'visiting')
    free(app)
    assert c.post('/v1/quests/nobody/accept', headers=h, json=mutation()).status_code == 404
    assert complete(c, h, 'moka_pie').json()['detail'] == 'quest_not_active'
    assert c.get('/v1/quests').status_code == 401
    assert c.post('/v1/quests/moka_pie/accept', headers=h, json={'request_id': 'x'}).status_code == 422
    assert visit(c, h, 'a' * 30).status_code == 422
    # Accepting twice keeps the first (the outfit's starting look too).
    first = accept(c, h, 'sora_outfit').json()['quest']['accepted']
    now[0] += 50
    assert accept(c, h, 'sora_outfit').json()['quest']['accepted'] == first
    # While visiting a friend's village the requests wait for the player's own.
    invite = c.post('/v1/social/invites', headers=h, json=mutation(username='visiting', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=guest, json=mutation()).json()['visiting']
    with db(app) as conn:
        conn.execute("DELETE FROM story_progress")
    assert accept(c, guest, 'moka_pie').json()['detail'] == 'quest_own_village_only'
    # A request id reused for another request is refused.
    body = mutation()
    assert c.post('/v1/quests/moka_pie/accept', headers=h, json=body).status_code == 200
    assert c.post('/v1/quests/naru_islands/accept', headers=h, json=body).json()['detail'] == 'request_id_reused'


def test_the_operator_can_see_a_players_requests(world, capsys):
    app, c, now = world
    h = account(c, 'shown')
    free(app)
    accept(c, h, 'hangyeol_turnips')
    bag(app, c, h, turnip=2)
    complete(c, h, 'hangyeol_turnips')
    assert admin_cli.main(['quests', 'show', 'shown', '--data-dir', str(app.state.settings.data_dir)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown['progress'][0]['quest_id'] == 'hangyeol_turnips' and shown['progress'][0]['state'] == 'done'
    assert shown['paid'][0]['quest'] == 'hangyeol_turnips' and shown['paid'][0]['amount'] == 5
    assert admin_cli.main(['quests', 'show', 'nobody', '--data-dir', str(app.state.settings.data_dir)]) == 1
