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
    # Night-eligibility tests advance the real reward clock across multiple calendar days.
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100, user_daily_generation_limit=50,
                        session_seconds=7 * 86400, **kw)
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


def test_requests_open_while_the_chair_is_made_and_mokas_after_the_chapter(world):
    app, c, now = world
    h = account(c, 'newcomer')
    first = c.get('/v1/me', headers=h).json()['quests']
    assert first['unlocked'] is False and {q['state'] for q in first['states']} == {'locked'}
    assert accept(c, h, 'moka_pie').json()['detail'] == 'quests_locked'
    # The chapter: letter, 모카's request. Asked, nothing ordered yet: still closed.
    for action in ('read_letter', 'accept'):
        assert c.post('/v1/story/step', headers=h, json=mutation(action=action)).status_code == 200
    assert listing(c, h)['unlocked'] is False
    # The chair is ordered: while it is made every request opens but 모카's own (she is busy).
    craft(app, c, h, '하늘색 쿠션을 얹은 둥근 나무 카페 의자', now)
    waiting = listing(c, h)
    assert waiting['unlocked'] is True
    assert {q['id']: q['state'] for q in waiting['list']}['moka_pie'] == 'locked'
    assert {q['state'] for q in waiting['list'] if q['id'] != 'moka_pie'} == {'available'}
    assert accept(c, h, 'moka_pie').json()['detail'] == 'quests_locked'
    assert accept(c, h, 'sora_outfit').status_code == 200
    # The welcome chair on the terrace ends the chapter: 모카's request opens too (no letter needed).
    chair = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
    done = c.post('/v1/story/gift', headers=h, json=mutation(object_id=chair['id'], version=chair['version'])).json()
    assert done['story']['step'] == 'done'
    open_ = listing(c, h)
    states = {q['id']: q['state'] for q in open_['list']}
    assert open_['unlocked'] is True and states.pop('sora_outfit') == 'active' and set(states.values()) == {'available'}
    # Every resident of the village asks one thing (residents.gd RESIDENTS, the same nineteen).
    assert [q['npc'] for q in open_['list']] == ['regular', 'naru', 'sora', 'moru', 'haeru', 'postman', 'farmer', 'lamplighter', 'fisher',
                                                'sweeper', 'gentleman', 'stargazer', 'gardener', 'scout', 'miller', 'shopkeeper', 'kid',
                                                'stroller', 'poet']
    assert accept(c, h, 'moka_pie').status_code == 200


def local(h, now, hour):
    """The headers of a player whose own clock shows this hour now (the time zone header)."""
    utc = (now[0] % 86400) / 3600
    shift = (hour - utc) % 24
    if shift > 14:
        shift -= 24
    return {**h, 'X-Villagen-UTC-Offset': str(int(round(shift * 60)))}


def reward_hour(now, hour):
    """Advance the server clock to this hour in these accounts' fixed Korea time zone."""
    now[0] += (hour * 3600 - (now[0] + homestead.KST * 3600) % 86400) % 86400


def mine(c, h, name=None, ident=None):
    return next(o for o in c.get('/v1/me', headers=h).json()['objects'] if (name and o['name'] == name) or (ident and o['id'] == ident))


def catch(app, c, h, *kinds):
    """The fish book counts these kinds once more (as a catch does)."""
    c.get('/v1/homestead', headers=h)
    me = c.get('/v1/me', headers=h).json()
    with db(app) as conn:
        user = conn.execute('SELECT id FROM users WHERE username=?', (me['username'],)).fetchone()['id']
        row = conn.execute('SELECT state FROM homesteads WHERE user_id=?', (user,)).fetchone()
        state = json.loads(row['state']) if row else homestead.initial()
        for kind in kinds:
            state['collection'][kind] = state['collection'].get(kind, 0) + 1
        conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state', (user, json.dumps(state)))


def test_every_request_runs_from_offer_to_one_reward(world):
    """Each request: offered, accepted, not ready, done by its own condition, paid once."""
    app, c, now = world
    h = account(c, 'helper')
    free(app)
    total = 0
    lamp = craft(app, c, h, '등불', now)
    toy = craft(app, c, h, '곰인형', now)
    start = shards(c, h)
    for quest_id, rule in quests.QUESTS.items():
        before = quest(c, h, quest_id)
        assert before['state'] == 'available' and before['stars'] == quests.STARS[quest_id], before
        now[0] += 10
        taken = accept(c, h, quest_id)
        assert taken.status_code == 200, taken.text
        assert taken.json()['quest']['state'] == 'active' and taken.json()['quest']['have'] == 0
        assert complete(c, h, quest_id).json()['detail'] == 'quest_not_ready'
        kind = rule['kind']
        now[0] += 10
        if kind == 'bring':
            bag(app, c, h, **{rule['items'][0]: rule['count']})
        elif kind in ('visit', 'talk'):
            for spot in rule['places'][:rule['count']]:
                now[0] += 5
                if rule.get('night'):
                    reward_hour(now, 21)
                r = c.post('/v1/quests/%s/progress' % quest_id, headers=h, json=mutation(place=spot))
                assert r.status_code == 200, r.text
        elif kind == 'outfit':
            look = c.get('/v1/me', headers=h).json()['profile']
            avatar = {**look['avatar'], 'coat': '#336699'}
            assert c.post('/v1/profile', headers=h, json=mutation(version=look['version'], avatar=avatar)).status_code == 200
        elif kind == 'catch':
            catch(app, c, h, 'perch', 'mackerel')
        elif kind == 'gift' and rule.get('to'):
            piece = mine(c, h, ident=toy['id'])
            assert c.post('/v1/objects/%s/placement' % toy['id'], headers=h, json=mutation(version=piece['version'], action='retrieve')).status_code == 200
            piece = mine(c, h, ident=toy['id'])
            assert c.post('/v1/npcs/kid/gift', headers=h, json=mutation(object_id=toy['id'], version=piece['version'])).status_code == 200
        elif kind == 'gift':
            chair = mine(c, h, name='환영의 나무 의자')
            assert c.post('/v1/npcs/postman/gift', headers=h, json=mutation(object_id=chair['id'], version=chair['version'])).status_code == 200
        elif kind == 'arrange':
            piece = mine(c, h, ident=toy['id'])
            r = c.post('/v1/objects/%s/placement' % toy['id'], headers=h, json=mutation(version=piece['version'], room='home', x=1, z=-1))
            assert r.status_code == 200, r.text
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
    # About two cheap crafts in all; small errands pay a little, the two letter requests the most.
    assert len(quests.QUESTS) == 19 and 75 <= sum(quests.STARS.values()) <= 85
    assert all(3 <= v <= 8 for v in quests.STARS.values())
    assert {q for q, v in quests.STARS.items() if v == 8} == {q for q, r in quests.QUESTS.items() if r.get('letter')}
    assert sum(1 for r in quests.QUESTS.values() if r.get('craft')) == 2
    assert {q['state'] for q in listing(c, h)['list']} == {'done'}


def test_new_kinds_count_only_what_happens_after_the_request(world):
    """A catch, a piece at home and a toy for 콩이 count from the request on; other gifts do not."""
    app, c, now = world
    h = account(c, 'kinds')
    free(app)
    catch(app, c, h, 'perch')
    accept(c, h, 'boram_catch')
    # The same kind again counts (one kind), a second kind makes two; the fish may then be sold.
    catch(app, c, h, 'perch', 'perch')
    assert quest(c, h, 'boram_catch')['have'] == 1
    catch(app, c, h, 'crucian')
    assert quest(c, h, 'boram_catch')['state'] == 'ready'
    # A piece already at home does not count; one moved there afterwards does.
    lamp = craft(app, c, h, '등불', now)
    piece = mine(c, h, ident=lamp['id'])
    c.post('/v1/objects/%s/placement' % lamp['id'], headers=h, json=mutation(version=piece['version'], room='home', x=1, z=-1))
    accept(c, h, 'danbi_home')
    assert quest(c, h, 'danbi_home')['have'] == 0
    piece = mine(c, h, ident=lamp['id'])
    c.post('/v1/objects/%s/placement' % lamp['id'], headers=h, json=mutation(version=piece['version'], room='home', x=-1, z=-1))
    assert quest(c, h, 'danbi_home')['state'] == 'ready'
    # 콩이 wants a toy (or an animal), given to her: a chair for her or a toy for someone else is not it.
    accept(c, h, 'kongi_toy')
    chair = mine(c, h, name='환영의 나무 의자')
    c.post('/v1/npcs/kid/gift', headers=h, json=mutation(object_id=chair['id'], version=chair['version']))
    toy = craft(app, c, h, '나무 팽이', now)
    c.post('/v1/npcs/naru/gift', headers=h, json=mutation(object_id=toy['id'], version=toy['version']))
    assert quest(c, h, 'kongi_toy')['have'] == 0
    cat = craft(app, c, h, '고양이 인형', now)
    c.post('/v1/npcs/kid/gift', headers=h, json=mutation(object_id=cat['id'], version=cat['version']))
    assert quest(c, h, 'kongi_toy')['state'] == 'ready'
    # The craft requests never pay more than the cheapest craft.
    assert quests.reward('kongi_toy', 5.0) == quests.CRAFT_FLOOR


def test_night_errands_and_messages(world):
    app, c, now = world
    h = account(c, 'nightowl')
    free(app)
    # The account's fixed clock decides: a forged night header cannot complete a day visit.
    reward_hour(now, 13)
    accept(c, h, 'saebyeok_walk')
    walk = lambda hour: c.post('/v1/quests/saebyeok_walk/progress', headers=local(h, now, hour), json=mutation(place='lighthouse_pier'))
    assert walk(13).json()['detail'] == 'quest_not_night'
    assert walk(21).json()['detail'] == 'quest_not_night'
    reward_hour(now, 21)
    assert walk(13).json()['quest']['state'] == 'ready'
    reward_hour(now, 7)
    accept(c, h, 'haneul_stars')
    stars = lambda hour: c.post('/v1/quests/haneul_stars/progress', headers=local(h, now, hour), json=mutation(place='observatory'))
    assert stars(7).json()['detail'] == 'quest_not_night'
    assert stars(3).json()['detail'] == 'quest_not_night'
    reward_hour(now, 3)
    assert stars(7).json()['quest']['state'] == 'ready'
    # 윤재's regards go to 가람 only.
    accept(c, h, 'yunjae_regards')
    assert visit(c, h, 'sora', 'yunjae_regards').status_code == 422
    assert visit(c, h, 'poet', 'yunjae_regards').json()['quest']['state'] == 'ready'
    assert quest(c, h, 'yunjae_regards')['visited'] == ['poet']

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
        assert complete(c, h, 'hangyeol_turnips').json()['stars'] == 8
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
    assert shown['paid'][0]['quest'] == 'hangyeol_turnips' and shown['paid'][0]['amount'] == 4
    assert admin_cli.main(['quests', 'show', 'nobody', '--data-dir', str(app.state.settings.data_dir)]) == 1


def finish_chapter(c, h):
    """The opening chapter played through and 모카's letter read: the requests open."""
    for action in ('read_letter', 'accept'):
        assert c.post('/v1/story/step', headers=h, json=mutation(action=action)).status_code == 200
    chair = next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['name'] == '환영의 나무 의자')
    done = c.post('/v1/story/gift', headers=h, json=mutation(object_id=chair['id'], version=chair['version'])).json()
    c.post('/v1/letters/read', headers=h, json=mutation(ids=[done['letters'][0]['id']]))
    assert listing(c, h)['unlocked'] is True


def test_reports_wait_while_a_story_reset_closes_the_requests(world):
    app, c, now = world
    h = account(c, 'rehearsal')
    finish_chapter(c, h)
    accept(c, h, 'naru_islands')
    assert visit(c, h, 'square').json()['quest']['have'] == 1
    assert admin_cli.main(['story', 'reset', 'rehearsal', '--data-dir', str(app.state.settings.data_dir)]) == 0
    assert listing(c, h)['unlocked'] is False
    now[0] += 10
    assert visit(c, h, 'fields').json()['detail'] == 'quests_locked'
    accept(c, h, 'haneul_stars')
    assert c.post('/v1/quests/haneul_stars/progress', headers=local(h, now, 22), json=mutation(place='observatory')).json()['detail'] == 'quests_locked'
    # Open again after the chapter: the report made while closed never counted.
    finish_chapter(c, h)
    assert quest(c, h, 'naru_islands')['visited'] == ['square']


def test_a_request_taken_at_its_place_counts_it_at_once(world):
    """하늘 is in her observatory at night: taking her request in there is the visit itself."""
    app, c, now = world
    h = account(c, 'inside')
    c.get('/v1/me', headers=h)  # Fix the account clock before trying forged headers.
    free(app)
    reward_hour(now, 22)
    taken = c.post('/v1/quests/haneul_stars/accept', headers=local(h, now, 13), json=mutation(place='observatory'))
    assert taken.status_code == 200, taken.text
    assert taken.json()['quest']['state'] == 'ready' and taken.json()['quest']['visited'] == ['observatory']
    assert complete(c, h, 'haneul_stars').json()['stars'] == quests.STARS['haneul_stars']
    # By day the place does not count (a night errand), and another request's place never does.
    other = account(c, 'daytime')
    c.get('/v1/me', headers=other)
    free(app)
    reward_hour(now, 13)
    assert c.post('/v1/quests/saebyeok_walk/accept', headers=local(other, now, 21), json=mutation(place='lighthouse_pier')).json()['quest']['state'] == 'active'
    assert c.post('/v1/quests/garam_lookout/accept', headers=other, json=mutation(place='observatory')).json()['quest']['have'] == 0
    assert c.post('/v1/quests/naru_islands/accept', headers=other, json=mutation(place='Square')).status_code == 422
    # Counted at night later as before.
    reward_hour(now, 21)
    walk = c.post('/v1/quests/saebyeok_walk/progress', headers=local(other, now, 21), json=mutation(place='lighthouse_pier'))
    assert walk.json()['quest']['state'] == 'ready'


def test_me_carries_only_the_states_and_a_catalog_digest(world):
    app, c, now = world
    h = account(c, 'poller')
    free(app)
    full = listing(c, h)
    me = c.get('/v1/me', headers=h).json()['quests']
    assert set(me) == {'unlocked', 'catalog', 'states'} and me['catalog'] == full['catalog']
    assert [s['id'] for s in me['states']] == [q['id'] for q in full['list']] and {s['state'] for s in me['states']} == {'available'}
    assert len(json.dumps(me, ensure_ascii=False)) < 1200 < len(json.dumps(full, ensure_ascii=False))
    # A visit counted shows in the states with the same catalog; taking a request changes the catalog.
    accept(c, h, 'naru_islands')
    taken = c.get('/v1/me', headers=h).json()['quests']
    assert taken['catalog'] != me['catalog'] and taken['catalog'] == listing(c, h)['catalog']
    visit(c, h, 'square')
    seen = c.get('/v1/me', headers=h).json()['quests']
    assert seen['catalog'] == taken['catalog']
    assert next(s for s in seen['states'] if s['id'] == 'naru_islands') == {'id': 'naru_islands', 'state': 'active', 'have': 1, 'visited': ['square']}
    # The catch baseline (the whole fish book) stays out of the poll.
    catch(app, c, h, 'perch', 'mackerel')
    accept(c, h, 'boram_catch')
    assert 'since' not in json.dumps(c.get('/v1/me', headers=h).json()['quests']) and 'since' in json.dumps(listing(c, h))


def test_the_light_request_does_not_rescan_every_piece_on_each_poll(world, monkeypatch):
    app, c, now = world
    h = account(c, 'collector')
    free(app)
    box = craft(app, c, h, '나무 상자', now)
    with db(app) as conn:
        row = dict(conn.execute('SELECT * FROM objects WHERE id=?', (box['id'],)).fetchone())
        for n in range(40):
            conn.execute('INSERT INTO objects(id,owner_id,creator_id,asset_id,name,color,version,state,x,z,rotation,created) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                         (str(uuid.uuid4()), row['owner_id'], row['creator_id'], row['asset_id'], row['name'], row['color'], 1, 'placed', n, n, 0, row['created']))
    accept(c, h, 'noeul_light')
    reads = []
    real = quests.design
    monkeypatch.setattr(quests, 'design', lambda conn, asset_id: reads.append(asset_id) or real(conn, asset_id))
    for poll in range(3):
        assert next(s for s in c.get('/v1/me', headers=h).json()['quests']['states'] if s['id'] == 'noeul_light')['state'] == 'active'
    # Forty copies of one design: read at most once, then kept for the next polls.
    assert len(reads) <= 1
    lamp = craft(app, c, h, '등불', now)
    other = craft(app, c, h, '촛대', now)
    with db(app) as conn:
        conn.execute("UPDATE objects SET state='placed',x=20,z=20 WHERE id IN (?,?)", (lamp['id'], other['id']))
    assert next(s for s in c.get('/v1/me', headers=h).json()['quests']['states'] if s['id'] == 'noeul_light')['state'] == 'ready'
    # The count stops at what the request needs.
    with db(app) as conn:
        assert len(quests.lights_set_out(conn, row['owner_id'], 1)) == 1
        assert set(quests.lights_set_out(conn, row['owner_id'])) == {lamp['id'], other['id']}


def test_the_operator_example_states_the_real_totals():
    """ops/production.env.example sizes the rewards for the operator: its totals are STARS's."""
    import pathlib
    text = (pathlib.Path(__file__).resolve().parents[2] / 'ops' / 'production.env.example').read_text(encoding='utf-8')
    total = lambda scale: sum(quests.reward(q, scale) for q in quests.QUESTS)
    assert total(1.0) == 82
    assert ('%d in all at 1.0' % total(1.0)) in text and ('%d at 2.0' % total(2.0)) in text and ('%d at 5' % total(5.0)) in text
