"""Residents' requests (부탁): one per village resident, each paying a few starseeds once.

Once the chair of the opening story chapter (server/story.py) is ordered (모카's own request after
the chapter is done), or right away for an account that never had the chapter, every resident (the four cast villagers, 모카 and the
fourteen day villagers / shadow folk) has one small request. The player hears it in the
resident's usual conversation ("부탁 들어주기"), does it, and tells the resident; the starseeds
come once per account, through the ledger like every other star (reason 'quest_reward', the quest
id as reference), and 모카 and 노을 also send a thank-you letter to the village mailbox.

The server checks every condition it can see from its own data:
  bring    items in the player's homestead bag (server/homestead.py), taken from it at the hand-over
  catch    fish of different kinds caught after the request was accepted (the bag's fish book)
  outfit   the saved look (profiles.version) changed after the request was accepted
  gift     a gift (to anyone, or to one resident and of a kind by its tags) after the request
  light    a piece that glows (its interaction, its library family, or a lamp by its name) set down
           in the village
  arrange  a piece set down (or moved) in the player's own home after the request was accepted
and trusts the game only for what it cannot see, with limits:
  visit    standing at a place (a signpost, the lookout, a pier) or entering a room: one report per
           place, from a fixed list, at least VISIT_GAP seconds apart; night requests only while it
           is night by the player's clock (homestead.night, the time zone header); a request taken
           while standing at its place (하늘 in her observatory) counts that place at once
  talk     passing a message on to another resident (that resident only, once).

Rewards: STARS below (3-8 per request, 82 in all: about two cheap crafts). TRIPOTHON_QUEST_STARS_SCALE
(server/config.py, default 1.0) multiplies them; 0 turns the rewards off (the requests still run and
pay nothing). A request that may need a new craft never pays more than the cheapest craft costs.

/v1/me carries brief(): each request's state and how far it is, and a digest of the rest (who asks,
what for, the reward); the game asks /v1/quests for the full list when the digest changes.
"""
import hashlib
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
    'naru_islands': 5,
    'sora_outfit': 3,
    'moru_soup': 4,
    'haeru_fish': 5,
    'daon_gift': 3,
    'hangyeol_turnips': 4,
    'noeul_light': 8,
    'boram_catch': 5,
    'miso_flowers': 3,
    'yunjae_regards': 3,
    'haneul_stars': 4,
    'chorok_herbs': 3,
    'bau_pinecones': 4,
    'dure_carrots': 4,
    'danbi_home': 3,
    'kongi_toy': 6,
    'saebyeok_walk': 4,
    'garam_lookout': 3,
}

# Island keys (game/scripts/guide.gd island_key, field_objects.gd signposts).
ISLANDS = ('square', 'fields', 'garden', 'camp', 'lighthouse')
# Sea fish, cheapest first: a hand-over takes the cheapest the bag has.
SEA_FISH = tuple(fish for fish, data in sorted(homestead.FISH.items(), key=lambda kv: (kv[1]['price'], kv[0])) if 'sea' in data['spots'])
# The cheapest craft in starseeds (asset_studio.price: a still one-mesh piece).
CRAFT_FLOOR = 20
# Seconds between two counted place reports of one request.
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
    # 보람 · 낚시꾼 (the quiet one): two kinds of fish for the fish book (pond and sea differ).
    'boram_catch': {'npc': 'fisher', 'kind': 'catch', 'count': 2},
    # 미소 · 청소부: wildflowers by the square's benches.
    'miso_flowers': {'npc': 'sweeper', 'kind': 'bring', 'items': ('flower',), 'count': 3},
    # 윤재 · 산책하는 신사: his regards to the poet 가람.
    'yunjae_regards': {'npc': 'gentleman', 'kind': 'talk', 'places': ('poet',), 'count': 1},
    # 하늘 · 별지기 (out at night only): come up to the observatory after dark.
    'haneul_stars': {'npc': 'stargazer', 'kind': 'visit', 'places': ('observatory',), 'count': 1, 'night': True},
    # 초록 · 정원사: herbs for a scent pouch.
    'chorok_herbs': {'npc': 'gardener', 'kind': 'bring', 'items': ('herb',), 'count': 3},
    # 바우 · 탐험가: pinecones to kindle the camp fire.
    'bau_pinecones': {'npc': 'scout', 'kind': 'bring', 'items': ('pinecone',), 'count': 3},
    # 두레 · 방앗간지기: carrots for a carrot cake.
    'dure_carrots': {'npc': 'miller', 'kind': 'bring', 'items': ('carrot',), 'count': 2},
    # 단비 · 잡화점 주인: a housewarming look; something set out at home.
    'danbi_home': {'npc': 'shopkeeper', 'kind': 'arrange', 'count': 1},
    # 콩이 · 꼬마: a toy (or an animal-shaped piece) for the treasure box (may need a craft).
    'kongi_toy': {'npc': 'kid', 'kind': 'gift', 'to': 'kid', 'tags': ('toy', 'animal'), 'count': 1, 'craft': True},
    # 새벽 · 산책자 (out at night only): walk to the end of the lighthouse pier after dark.
    'saebyeok_walk': {'npc': 'stroller', 'kind': 'visit', 'places': ('lighthouse_pier',), 'count': 1, 'night': True},
    # 가람 · 시인: look out over the five islands from the observatory's lookout.
    'garam_lookout': {'npc': 'poet', 'kind': 'visit', 'places': ('lookout',), 'count': 1},
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


class QuestAccept(Mutation):
    # Where the player stands as they take the request (a visit request's place counts at once).
    place: str | None = Field(default=None, max_length=24, pattern=r'^[a-z_]+$')


def fail(code, status=409):
    raise HTTPException(status, code)


def reward(quest_id, scale):
    """Starseeds this request pays now (the scale applied; a craft request capped)."""
    amount = int(math.floor(STARS[quest_id] * scale + 0.5))
    if QUESTS[quest_id].get('craft'):
        amount = min(amount, CRAFT_FLOOR)
    return max(0, amount)


# Requests the opening chapter holds back until it is done (모카 is busy with the chapter).
STORY_HELD = ('moka_pie',)


def unlocked(conn, user_id, quest_id=None):
    """Requests wait for the opening chapter: all open without it or once it is done; while the
    chair is being made (모카 asked and a craft was ordered since) every request but 모카's own opens,
    so the wait has something to do. quest_id=None asks about the requests in general."""
    row = conn.execute('SELECT step,requested_at FROM story_progress WHERE user_id=?', (user_id,)).fetchone()
    if not row or row['step'] == 'done':
        return True
    if row['step'] != 'craft' or quest_id in STORY_HELD:
        return False
    return conn.execute('SELECT 1 FROM studio_jobs WHERE owner_id=? AND created>=? LIMIT 1',
                        (user_id, row['requested_at'] or 0)).fetchone() is not None


def held(conn, user_id, settings=None):
    """The requests still held back by the opening chapter (none once it is done or absent)."""
    row = conn.execute('SELECT step FROM story_progress WHERE user_id=?', (user_id,)).fetchone()
    waiting = set(STORY_HELD) if row and row['step'] != 'done' else set()
    if settings is not None:
        from .village_residents import absent
        missing = absent(conn, user_id, settings)
        waiting.update(q for q, spec in QUESTS.items() if spec['npc'] in missing)
    return waiting


def life_state(conn, user_id):
    row = conn.execute('SELECT state FROM homesteads WHERE user_id=?', (user_id,)).fetchone()
    return homestead.normalise(json.loads(row['state'])) if row else homestead.initial()


def profile_version(conn, user_id):
    row = conn.execute('SELECT version FROM profiles WHERE user_id=?', (user_id,)).fetchone()
    return row['version'] if row else 0


# What a design says about a piece. Studio manifests are written once (asset_studio, npc_homes),
# so the answers keep between polls: asset id -> its manifest's facts, and (asset id, name) ->
# whether it is a light by its design or name.
_DESIGNS = {}
_LIT = {}
_KEEP = 4096


def _kept(cache, key, make):
    if key not in cache:
        if len(cache) >= _KEEP:
            cache.clear()
        cache[key] = make()
    return cache[key]


def design(conn, asset_id):
    """A piece's library type and its plan's title and category (empty for non-studio assets)."""
    def read():
        studio = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (asset_id,)).fetchone()
        manifest = json.loads(studio['manifest']) if studio else {}
        plan = manifest.get('plan', {})
        return {'archetype': str(manifest.get('provenance', {}).get('archetype', '')),
                'title': plan.get('title'), 'category': plan.get('category')}
    return _kept(_DESIGNS, asset_id, read)


def lit_by_design(conn, asset_id, name):
    """A lamp, lantern or candle by its library type's family (light, flame), its name or design."""
    def judge():
        facts = design(conn, asset_id)
        kind = archetypes.BY_ID.get(facts['archetype'])
        if kind and kind.get('family') in GLOW_FAMILIES:
            return True
        return 'light' in npc_homes.item_tags(name, facts['title'], facts['category'])
    return _kept(_LIT, (asset_id, name), judge)


def lit_by_interaction(spec):
    """Its interaction makes it glow (glow, flicker, pulse, hue)."""
    if not spec:
        return False
    presets = json.loads(spec).get('presets', [])
    return any(str(p.get('kind', '')) in GLOW_KINDS for p in presets if isinstance(p, dict))


def lights_set_out(conn, user_id, enough=None):
    """The player's glowing pieces standing in the village (not in a room), up to `enough`. One
    query brings the pieces with their interactions; the designs' answers are kept (above)."""
    found = []
    for r in conn.execute("SELECT o.id,o.name,o.asset_id,i.spec FROM objects o LEFT JOIN furniture_locations f ON f.object_id=o.id "
                          "LEFT JOIN object_interactions i ON i.object_id=o.id "
                          "WHERE o.owner_id=? AND o.state='placed' AND COALESCE(f.room,'village')='village'", (user_id,)):
        if lit_by_interaction(r['spec']) or lit_by_design(conn, r['asset_id'], r['name']):
            found.append(r['id'])
            if enough is not None and len(found) >= enough:
                break
    return found


def home_pieces(conn, user_id):
    """{object id: version} of the pieces standing in the player's own home."""
    return {r['id']: r['version'] for r in conn.execute(
        "SELECT o.id,o.version FROM objects o JOIN furniture_locations f ON f.object_id=o.id "
        "WHERE o.owner_id=? AND o.state='placed' AND f.room='home'", (user_id,))}


def gift_kinds(conn, object_id, tags):
    """A gift's kinds: its item tags (npc_homes.item_tags) and 'toy' for a piece of the library's
    toys and hobbies room (a "장난감 로봇" may be designed as any of them)."""
    kinds = set(json.loads(tags or '[]'))
    row = conn.execute('SELECT asset_id FROM objects WHERE id=?', (object_id,)).fetchone()
    if row:
        kind = archetypes.BY_ID.get(design(conn, row['asset_id'])['archetype'])
        if kind and kind.get('room') == 'toys':
            kinds.add('toy')
    return kinds


def baseline_for(conn, user_id, quest):
    """What a request's condition is measured from, taken when it is accepted."""
    if quest['kind'] == 'outfit':
        return {'profile': profile_version(conn, user_id)}
    if quest['kind'] == 'catch':
        return {'caught': dict(life_state(conn, user_id).get('collection', {}))}
    if quest['kind'] == 'arrange':
        return {'home': home_pieces(conn, user_id)}
    return {}


def have(conn, user_id, quest_id, row, bag=None, life=None):
    """How much of the condition is met now (0..count)."""
    quest = QUESTS[quest_id]
    kind, need = quest['kind'], quest['count']
    base = json.loads(row['baseline'])
    if kind == 'bring':
        bag = bag if bag is not None else (life or life_state(conn, user_id))['bag']
        count = sum(int(bag.get(item, 0)) for item in quest['items'])
    elif kind in ('visit', 'talk'):
        count = len(json.loads(row['progress']).get('places', []))
    elif kind == 'outfit':
        count = int(profile_version(conn, user_id) > int(base.get('profile', 0)))
    elif kind == 'catch':
        # Kinds whose fish-book count went up since the request (eating or selling them later
        # does not undo a catch).
        caught = (life or life_state(conn, user_id)).get('collection', {})
        before = base.get('caught', {})
        count = sum(1 for fish, n in caught.items() if int(n) > int(before.get(fish, 0)))
    elif kind == 'gift':
        to = (quest['to'],) if quest.get('to') else tuple(npc_homes.NPCS)
        rows = conn.execute('SELECT g.object_id,i.tags FROM npc_gifts g LEFT JOIN npc_items i ON i.object_id=g.object_id '
                            'WHERE g.host_id=? AND g.created>=? AND g.npc_id IN (%s)' % ','.join('?' * len(to)),
                            (user_id, row['accepted'], *to)).fetchall()
        wanted = set(quest.get('tags', ()))
        count = 0
        for r in rows:
            if not wanted or wanted & gift_kinds(conn, r['object_id'], r['tags']):
                count += 1
                if count >= need:
                    break
    elif kind == 'arrange':
        before = base.get('home', {})
        count = sum(1 for piece, version in home_pieces(conn, user_id).items() if piece not in before or version > before[piece])
    else:
        count = len(lights_set_out(conn, user_id, need))
    return min(need, count)


def entry(conn, user_id, quest_id, row, scale, open_, bag=None, life=None):
    quest = QUESTS[quest_id]
    out = {'id': quest_id, 'npc': quest['npc'], 'kind': quest['kind'], 'need': quest['count'], 'have': 0,
           'stars': reward(quest_id, scale), 'letter': bool(quest.get('letter')), 'craft': bool(quest.get('craft')),
           'night': bool(quest.get('night'))}
    if quest['kind'] == 'bring':
        out['items'] = list(quest['items'])
    if quest['kind'] in ('visit', 'talk'):
        out['places'] = list(quest['places'])
        out['visited'] = json.loads(row['progress']).get('places', []) if row else []
    if quest.get('to'):
        out['to'] = quest['to']
    if row is None:
        out['state'] = 'available' if open_ else 'locked'
        return out
    out['accepted'] = row['accepted']
    if row['state'] == 'done':
        out.update(state='done', have=quest['count'], stars=row['stars'] or 0, completed=row['completed'])
        return out
    base = json.loads(row['baseline'])
    if quest['kind'] == 'outfit':
        out['since'] = int(base.get('profile', 0))
    if quest['kind'] == 'catch':
        # The game counts new kinds from its own fish book as the catches come in.
        out['since'] = base.get('caught', {})
    out['have'] = have(conn, user_id, quest_id, row, bag, life)
    out['state'] = 'ready' if out['have'] >= quest['count'] else 'active'
    return out


# What changes from one poll to the next. The rest of an entry changes only when a request is
# taken or handed over (or with the operator's scale): the catalog digest covers it.
LIVE = ('state', 'have', 'visited')


def public(conn, user_id, settings):
    """Every request as the game shows it: {unlocked, scale, catalog, list}."""
    rows = {r['quest_id']: r for r in conn.execute('SELECT * FROM quest_progress WHERE user_id=?', (user_id,))}
    open_ = unlocked(conn, user_id)
    waiting = held(conn, user_id, settings)
    life = life_state(conn, user_id) if any(QUESTS[q]['kind'] in ('bring', 'catch') and r['state'] == 'active' for q, r in rows.items() if q in QUESTS) else None
    listing = [entry(conn, user_id, quest_id, rows.get(quest_id), settings.quest_stars_scale, open_ and quest_id not in waiting, life['bag'] if life else None, life)
               for quest_id in QUESTS]
    from .village_residents import absent
    missing = absent(conn, user_id, settings)
    for item in listing:
        if item['npc'] in missing and item['state'] != 'done':
            item['state'] = 'locked'
    fixed = [{k: v for k, v in item.items() if k not in LIVE} for item in listing]
    catalog = hashlib.sha1(json.dumps(fixed, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]
    return {'unlocked': open_, 'scale': settings.quest_stars_scale, 'catalog': catalog, 'list': listing}


def brief(listing):
    """The poll's share of a listing (/v1/me): each request's state, how far it is and the places
    counted. The game keeps the rest from the last full list with the same catalog (quests.gd)."""
    states = []
    for item in listing['list']:
        short = {'id': item['id'], 'state': item['state']}
        if item['have']:
            short['have'] = item['have']
        if item.get('visited'):
            short['visited'] = item['visited']
        states.append(short)
    return {'unlocked': listing['unlocked'], 'catalog': listing['catalog'], 'states': states}


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
            app.state.village_residents.residents_for(user['id'])
            with db.read() as conn:
                return {'quests': public(conn, user['id'], settings)}

        @app.post('/v1/quests/{quest_id}/accept')
        def accept(quest_id: str, body: QuestAccept, request: Request):
            quest = quest_of(quest_id)

            def apply(conn, user):
                own_village(conn, user)
                app.state.village_residents.sync_in(conn, user['id'], clock())
                if not unlocked(conn, user['id'], quest_id) or quest_id in held(conn, user['id'], settings):
                    fail('quests_locked')
                row = conn.execute('SELECT state FROM quest_progress WHERE user_id=? AND quest_id=?', (user['id'], quest_id)).fetchone()
                if row and row['state'] == 'done':
                    fail('quest_already_done')
                if not row:
                    # What the condition is measured from (a new look, a catch, a piece at home count from now on).
                    baseline = baseline_for(conn, user['id'], quest)
                    now = clock()
                    # Taken at its place (하늘 asks inside her observatory at night): that place counts
                    # now, by the report's rules (a night errand only while it is night).
                    progress = {}
                    if quest['kind'] == 'visit' and body.place in quest['places'] and (not quest.get('night') or homestead.night(now)):
                        progress = {'places': [body.place], 'last': now}
                    conn.execute('INSERT INTO quest_progress(user_id,quest_id,state,accepted,baseline,progress) VALUES (?,?,?,?,?,?)',
                                 (user['id'], quest_id, 'active', now, json.dumps(baseline), json.dumps(progress)))
                return reply(conn, user, quest_id)
            return mutate(request, body, 'quest_accept:' + quest_id, apply)

        @app.post('/v1/quests/{quest_id}/progress')
        def progress(quest_id: str, body: QuestReport, request: Request):
            quest = quest_of(quest_id)

            def apply(conn, user):
                own_village(conn, user)
                # Closed again after a story reset (admin_cli story reset): nothing counts until they reopen.
                app.state.village_residents.sync_in(conn, user['id'], clock())
                if not unlocked(conn, user['id'], quest_id) or quest_id in held(conn, user['id'], settings):
                    fail('quests_locked')
                row = active(conn, user, quest_id)
                if quest['kind'] not in ('visit', 'talk'):
                    fail('quest_wrong_kind')
                if body.place not in quest['places']:
                    fail('quest_bad_place', 422)
                state = json.loads(row['progress'])
                places = state.get('places', [])
                now = clock()
                # A night errand counts only while it is night by the player's clock (the time zone
                # header, as for night fish).
                if quest.get('night') and body.place not in places and not homestead.night(now):
                    fail('quest_not_night')
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
                app.state.village_residents.sync_in(conn, user['id'], clock())
                if not unlocked(conn, user['id'], quest_id) or quest_id in held(conn, user['id'], settings):
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

    def brief_for(self, conn, user_id):
        """/v1/me's share (brief above)."""
        return brief(public(conn, user_id, self.settings))
