"""Residents' requests (부탁): one per resident the player knows, each paying a few starseeds once.

After the opening story chapter (server/story.py) is over and 모카's letter is read, or right away
for an account that never had the chapter, each of these residents has one small request. The
player hears it in the resident's usual conversation ("부탁 들어주기"), does it, and tells the
resident; the starseeds come once per account, through the ledger like every other star
(reason 'quest_reward', the quest id as reference), and 모카 and 노을 also send a thank-you letter
to the village mailbox.

The server checks every condition it can see from its own data:
  bring   items in the player's homestead bag (server/homestead.py), taken from it at the hand-over
  outfit  the saved look (profiles.version) changed after the request was accepted
  gift    a gift to any village resident (npc_gifts) after the request was accepted
  light   a piece that glows (its interaction, its library family, or a lamp by its name) is set
          down in the village
and trusts the game only for what it cannot see, with limits:
  visit   standing at the signposts of different islands; one report per island, at least
          VISIT_GAP seconds apart.

Rewards: STARS below (5-15 per request, about one craft in all). TRIPOTHON_QUEST_STARS_SCALE
(server/config.py, default 1.0) multiplies them; 0 turns the rewards off (the requests still run and
pay nothing). A request that may need a new craft never pays more than the cheapest craft costs.
"""
import json
import math
import uuid
from fastapi import HTTPException, Request
from pydantic import Field
from .models import Mutation
from . import homestead, npc_homes, archetypes

# Starseeds per request (before TRIPOTHON_QUEST_STARS_SCALE). Change the amounts here.
STARS = {
    'moka_pie': 8,
    'naru_islands': 6,
    'sora_outfit': 5,
    'moru_soup': 6,
    'haeru_fish': 6,
    'daon_gift': 5,
    'hangyeol_turnips': 5,
    'noeul_light': 8,
}

# Island keys (game/scripts/guide.gd island_key, field_objects.gd signposts).
ISLANDS = ('square', 'fields', 'garden', 'camp', 'lighthouse')
# Sea fish, cheapest first: a hand-over takes the cheapest the bag has.
SEA_FISH = tuple(fish for fish, data in sorted(homestead.FISH.items(), key=lambda kv: (kv[1]['price'], kv[0])) if 'sea' in data['spots'])
# The cheapest craft in starseeds (asset_studio.price: a still one-mesh piece).
CRAFT_FLOOR = 20
# Seconds between two counted signpost reports.
VISIT_GAP = 3.0
# Interaction kinds that make a piece glow (server/interactions.py KINDS).
GLOW_KINDS = ('glow', 'flicker', 'pulse', 'hue')
GLOW_FAMILIES = ('light', 'flame')

# npc: the resident's id (game/scripts/residents.gd); count: how much the condition needs.
QUESTS = {
    # 모카 · 카페 주인: an apple pie for the terrace's guests (her tips name the orchard).
    'moka_pie': {'npc': 'regular', 'kind': 'bring', 'items': ('apple',), 'count': 3, 'letter': True},
    # 나루 · 길잡이: learn the islands by their signposts.
    'naru_islands': {'npc': 'naru', 'kind': 'visit', 'places': ISLANDS, 'count': 3},
    # 소라 · 재단사: a new outfit from her wardrobe.
    'sora_outfit': {'npc': 'sora', 'kind': 'outfit', 'count': 1},
    # 모루 · 야영 전문가: mushrooms for a camp soup.
    'moru_soup': {'npc': 'moru', 'kind': 'bring', 'items': ('mushroom', 'gold_mushroom'), 'count': 2},
    # 해루 · 낚시꾼: a fish from the sea for supper.
    'haeru_fish': {'npc': 'haeru', 'kind': 'bring', 'items': SEA_FISH, 'count': 1},
    # 다온 · 우편배달부: a gift is a letter without words; give one to any resident.
    'daon_gift': {'npc': 'postman', 'kind': 'gift', 'count': 1},
    # 한결 · 농부: the first turnips of the sunny field.
    'hangyeol_turnips': {'npc': 'farmer', 'kind': 'bring', 'items': ('turnip',), 'count': 2},
    # 노을 · 등불지기: something that glows set down in the village (may need a craft).
    'noeul_light': {'npc': 'lamplighter', 'kind': 'light', 'count': 1, 'craft': True, 'letter': True},
}
assert set(QUESTS) == set(STARS)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS quest_progress (
 user_id TEXT NOT NULL REFERENCES users(id), quest_id TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('active','done')), accepted REAL NOT NULL,
 baseline TEXT NOT NULL DEFAULT '{}', progress TEXT NOT NULL DEFAULT '{}',
 completed REAL, stars INTEGER, letter_id TEXT, PRIMARY KEY(user_id,quest_id));
'''


class QuestReport(Mutation):
    place: str = Field(max_length=24, pattern=r'^[a-z_]+$')


def fail(code, status=409):
    raise HTTPException(status, code)


def reward(quest_id, scale):
    """Starseeds this request pays now (the scale applied; a craft request capped)."""
    amount = int(math.floor(STARS[quest_id] * scale + 0.5))
    if QUESTS[quest_id].get('craft'):
        amount = min(amount, CRAFT_FLOOR)
    return max(0, amount)


def unlocked(conn, user_id):
    """Requests wait for the opening chapter: none without it, else after it is done and 모카's
    letter has been read (the chapter's last line on the tracker)."""
    row = conn.execute('SELECT step,letter_id FROM story_progress WHERE user_id=?', (user_id,)).fetchone()
    if not row:
        return True
    if row['step'] != 'done':
        return False
    letter = conn.execute('SELECT read_at FROM npc_letters WHERE id=?', (row['letter_id'],)).fetchone()
    return not letter or letter['read_at'] is not None


def life_state(conn, user_id):
    row = conn.execute('SELECT state FROM homesteads WHERE user_id=?', (user_id,)).fetchone()
    return homestead.normalise(json.loads(row['state'])) if row else homestead.initial()


def profile_version(conn, user_id):
    row = conn.execute('SELECT version FROM profiles WHERE user_id=?', (user_id,)).fetchone()
    return row['version'] if row else 0


def glows(conn, obj):
    """True for a piece that gives light: its interaction (glow, flicker...), its library type's
    family (light, flame), or a lamp, lantern or candle by its name or design."""
    row = conn.execute('SELECT spec FROM object_interactions WHERE object_id=?', (obj['id'],)).fetchone()
    if row:
        spec = json.loads(row['spec'])
        if any(str(p.get('kind', '')) in GLOW_KINDS for p in spec.get('presets', []) if isinstance(p, dict)):
            return True
    studio = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
    manifest = json.loads(studio['manifest']) if studio else {}
    kind = archetypes.BY_ID.get(str(manifest.get('provenance', {}).get('archetype', '')))
    if kind and kind.get('family') in GLOW_FAMILIES:
        return True
    plan = manifest.get('plan', {})
    return 'light' in npc_homes.item_tags(obj['name'], plan.get('title'), plan.get('category'))


def lights_set_out(conn, user_id):
    """The player's glowing pieces standing in the village (not in a room)."""
    rows = conn.execute("SELECT o.* FROM objects o LEFT JOIN furniture_locations f ON f.object_id=o.id "
                        "WHERE o.owner_id=? AND o.state='placed' AND COALESCE(f.room,'village')='village'", (user_id,)).fetchall()
    return [r['id'] for r in rows if glows(conn, r)]


def have(conn, user_id, quest_id, row, bag=None):
    """How much of the condition is met now (0..count)."""
    quest = QUESTS[quest_id]
    kind, need = quest['kind'], quest['count']
    if kind == 'bring':
        bag = bag if bag is not None else life_state(conn, user_id)['bag']
        count = sum(int(bag.get(item, 0)) for item in quest['items'])
    elif kind == 'visit':
        count = len(json.loads(row['progress']).get('places', []))
    elif kind == 'outfit':
        count = int(profile_version(conn, user_id) > int(json.loads(row['baseline']).get('profile', 0)))
    elif kind == 'gift':
        count = conn.execute('SELECT count(*) FROM npc_gifts WHERE host_id=? AND created>=? AND npc_id IN (%s)' % ','.join('?' * len(npc_homes.NPCS)),
                             (user_id, row['accepted'], *npc_homes.NPCS)).fetchone()[0]
    else:
        count = len(lights_set_out(conn, user_id))
    return min(need, count)


def entry(conn, user_id, quest_id, row, scale, open_, bag=None):
    quest = QUESTS[quest_id]
    out = {'id': quest_id, 'npc': quest['npc'], 'kind': quest['kind'], 'need': quest['count'], 'have': 0,
           'stars': reward(quest_id, scale), 'letter': bool(quest.get('letter')), 'craft': bool(quest.get('craft'))}
    if quest['kind'] == 'bring':
        out['items'] = list(quest['items'])
    if quest['kind'] == 'visit':
        out['places'] = list(quest['places'])
        out['visited'] = json.loads(row['progress']).get('places', []) if row else []
    if row is None:
        out['state'] = 'available' if open_ else 'locked'
        return out
    out['accepted'] = row['accepted']
    if row['state'] == 'done':
        out.update(state='done', have=quest['count'], stars=row['stars'] or 0, completed=row['completed'])
        return out
    if quest['kind'] == 'outfit':
        out['since'] = int(json.loads(row['baseline']).get('profile', 0))
    out['have'] = have(conn, user_id, quest_id, row, bag)
    out['state'] = 'ready' if out['have'] >= quest['count'] else 'active'
    return out


def public(conn, user_id, settings):
    """Every request as the game shows it: {unlocked, scale, list}."""
    rows = {r['quest_id']: r for r in conn.execute('SELECT * FROM quest_progress WHERE user_id=?', (user_id,))}
    open_ = unlocked(conn, user_id)
    bag = life_state(conn, user_id)['bag'] if any(QUESTS[q]['kind'] == 'bring' and r['state'] == 'active' for q, r in rows.items() if q in QUESTS) else None
    return {'unlocked': open_, 'scale': settings.quest_stars_scale,
            'list': [entry(conn, user_id, quest_id, rows.get(quest_id), settings.quest_stars_scale, open_, bag) for quest_id in QUESTS]}


def describe(conn, user_id):
    """Operator view (admin_cli quests show)."""
    return {'progress': [dict(r) for r in conn.execute('SELECT * FROM quest_progress WHERE user_id=? ORDER BY accepted', (user_id,))],
            'paid': [dict(r) for r in conn.execute("SELECT reference AS quest,amount,created FROM ledger WHERE user_id=? AND reason='quest_reward' ORDER BY created", (user_id,))]}


class Quests:
    def __init__(self, app, db, settings, clock, auth, mutate, money, host_for):
        self.settings = settings
        with db.read() as conn:
            conn.executescript(SCHEMA)

        def quest_of(quest_id):
            if quest_id not in QUESTS:
                fail('quest_not_found', 404)
            return QUESTS[quest_id]

        def own_village(conn, user):
            if host_for(conn, user['id']) != user['id']:
                fail('quest_own_village_only')

        def active(conn, user, quest_id):
            row = conn.execute('SELECT * FROM quest_progress WHERE user_id=? AND quest_id=?', (user['id'], quest_id)).fetchone()
            if row and row['state'] == 'done':
                fail('quest_already_done')
            if not row:
                fail('quest_not_active')
            return row

        def reply(conn, user, quest_id, **extra):
            listing = public(conn, user['id'], settings)
            return {'quest': next(q for q in listing['list'] if q['id'] == quest_id), 'quests': listing, **extra}

        @app.get('/v1/quests')
        def read(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                return {'quests': public(conn, user['id'], settings)}

        @app.post('/v1/quests/{quest_id}/accept')
        def accept(quest_id: str, body: Mutation, request: Request):
            quest = quest_of(quest_id)

            def apply(conn, user):
                own_village(conn, user)
                if not unlocked(conn, user['id']):
                    fail('quests_locked')
                row = conn.execute('SELECT state FROM quest_progress WHERE user_id=? AND quest_id=?', (user['id'], quest_id)).fetchone()
                if row and row['state'] == 'done':
                    fail('quest_already_done')
                if not row:
                    # What the condition is measured from (a new look counts from now on).
                    baseline = {'profile': profile_version(conn, user['id'])} if quest['kind'] == 'outfit' else {}
                    conn.execute('INSERT INTO quest_progress(user_id,quest_id,state,accepted,baseline) VALUES (?,?,?,?,?)',
                                 (user['id'], quest_id, 'active', clock(), json.dumps(baseline)))
                return reply(conn, user, quest_id)
            return mutate(request, body, 'quest_accept:' + quest_id, apply)

        @app.post('/v1/quests/{quest_id}/progress')
        def progress(quest_id: str, body: QuestReport, request: Request):
            quest = quest_of(quest_id)

            def apply(conn, user):
                own_village(conn, user)
                row = active(conn, user, quest_id)
                if quest['kind'] != 'visit':
                    fail('quest_wrong_kind')
                if body.place not in quest['places']:
                    fail('quest_bad_place', 422)
                state = json.loads(row['progress'])
                places = state.get('places', [])
                now = clock()
                if body.place not in places and len(places) < quest['count']:
                    if now - float(state.get('last', 0)) < VISIT_GAP:
                        fail('quest_too_fast', 429)
                    places.append(body.place)
                    conn.execute('UPDATE quest_progress SET progress=? WHERE user_id=? AND quest_id=?',
                                 (json.dumps({'places': places, 'last': now}), user['id'], quest_id))
                return reply(conn, user, quest_id)
            return mutate(request, body, 'quest_progress:' + quest_id, apply)

        @app.post('/v1/quests/{quest_id}/complete')
        def complete(quest_id: str, body: Mutation, request: Request):
            quest = quest_of(quest_id)

            def apply(conn, user):
                own_village(conn, user)
                if not unlocked(conn, user['id']):
                    fail('quests_locked')
                row = active(conn, user, quest_id)
                now = clock()
                extra = {}
                if quest['kind'] == 'bring':
                    life = life_state(conn, user['id'])
                    if have(conn, user['id'], quest_id, row, life['bag']) < quest['count']:
                        fail('quest_not_ready')
                    # The hand-over: from the bag, cheapest kinds first.
                    left, taken = quest['count'], {}
                    for item in quest['items']:
                        n = min(left, int(life['bag'].get(item, 0)))
                        if n:
                            homestead.spend(life, item, n)
                            taken[item], left = n, left - n
                        if not left:
                            break
                    life['version'] = life.get('version', 0) + 1
                    conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state',
                                 (user['id'], json.dumps(life)))
                    extra = {'taken': taken, 'homestead': homestead.public(life, now)}
                elif have(conn, user['id'], quest_id, row) < quest['count']:
                    fail('quest_not_ready')
                # Once per account: the ledger has at most one reward per request.
                if conn.execute("SELECT 1 FROM ledger WHERE user_id=? AND reason='quest_reward' AND reference=?", (user['id'], quest_id)).fetchone():
                    fail('quest_already_done')
                stars = reward(quest_id, settings.quest_stars_scale)
                if stars:
                    money(conn, user['id'], stars, 'quest_reward', quest_id)
                letter_id = None
                if quest.get('letter'):
                    # A thank-you letter in the mailbox (one per resident's request, written once).
                    letter_id = str(uuid.uuid4())
                    if not conn.execute('INSERT OR IGNORE INTO npc_letters(id,host_id,npc_id,level,created) VALUES (?,?,?,?,?)',
                                        (letter_id, user['id'], quest['npc'], npc_homes.QUEST_LETTER_LEVEL, now)).rowcount:
                        letter_id = None
                conn.execute("UPDATE quest_progress SET state='done',completed=?,stars=?,letter_id=? WHERE user_id=? AND quest_id=?",
                             (now, stars, letter_id, user['id'], quest_id))
                shards = conn.execute('SELECT shards FROM users WHERE id=?', (user['id'],)).fetchone()[0]
                letters = [letter for letter in npc_homes.letters(conn, user['id']) if letter['id'] == letter_id] if letter_id else []
                return reply(conn, user, quest_id, stars=stars, shards=shards, letters=letters, **extra)
            return mutate(request, body, 'quest_complete:' + quest_id, apply)

    def public_for(self, conn, user_id):
        return public(conn, user_id, self.settings)
