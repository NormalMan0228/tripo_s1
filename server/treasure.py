"""Treasure chests (보물상자): starseeds found once per account, at home and around the islands.

A new maker finds one chest in their own home (the ground floor, against the back wall) and ten
more around the five islands, two per island, tucked behind a tree, under the windmill, on the
lighthouse rocks and so on (the game places them: game/scripts/treasure.gd CHESTS, the same ids).
Pressing E next to one opens it: the lid swings open, warm light and sparkles, and the stars fly
into the starseed counter. Each chest pays once per account, through the ledger like every other
star (reason 'chest_reward', the chest id as reference), and stays open for good (no respawn).

The server keeps which chests an account opened and pays them; it trusts the game for where the
walker stands (a chest is a short walk from a road, nothing else to check), with limits:
  own village only    a visitor in a friend's village (or a friend's home) cannot open theirs
  once                a second open is refused (chest_already_open), the ledger checked too
  CHEST_GAP           at least this many seconds between two opens (nobody walks faster)

Rewards: STARS below (home 10, field chests 3-5, 45 in all). TRIPOTHON_CHEST_STARS_SCALE
(server/config.py, default 1.0) multiplies them; 0 turns the rewards off (chests still open and
pay nothing). Chests are independent of the opening story chapter: admin_cli story reset leaves
them as they are.

/v1/me carries brief(): the ids already opened, so the game draws those open from the first frame.
"""
import math
from fastapi import HTTPException, Request
from .models import Mutation

# Starseeds per chest (before TRIPOTHON_CHEST_STARS_SCALE). Change the amounts here.
STARS = {
    # 나의 집: the first room after signing in.
    'home': 10,
    # 물결빛 광장
    'square_cape': 3,
    'square_backyard': 3,
    # 풍차 들판 (the café chest is a few steps from 모카's terrace: the demo opens it while a craft runs)
    'fields_cafe': 4,
    'fields_windmill': 3,
    # 정원 언덕
    'garden_pond': 4,
    'garden_gazebo': 3,
    # 캠프 초원
    'camp_tents': 4,
    'camp_cottage': 3,
    # 등대섬
    'lighthouse_rocks': 5,
    'lighthouse_cape': 3,
}

# Island keys (game/scripts/guide.gd island_key); 'home' is the player's own home.
ISLANDS = ('square', 'fields', 'garden', 'camp', 'lighthouse')
# Seconds between two opens of one account.
CHEST_GAP = 2.0


def place_of(chest_id):
    """'home' or the chest's island (the id's first word)."""
    return 'home' if chest_id == 'home' else chest_id.split('_')[0]


assert all(place_of(c) in ISLANDS + ('home',) for c in STARS)
assert all(sum(1 for c in STARS if place_of(c) == island) == 2 for island in ISLANDS)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS chest_opened (
 user_id TEXT NOT NULL REFERENCES users(id), chest_id TEXT NOT NULL,
 opened REAL NOT NULL, stars INTEGER NOT NULL, PRIMARY KEY(user_id,chest_id));
'''


def fail(code, status=409):
    raise HTTPException(status, code)


def reward(chest_id, scale):
    """Starseeds this chest pays now (the scale applied)."""
    return max(0, int(math.floor(STARS[chest_id] * scale + 0.5)))


def opened_rows(conn, user_id):
    return {r['chest_id']: r for r in conn.execute('SELECT * FROM chest_opened WHERE user_id=?', (user_id,))}


def public(conn, user_id, settings):
    """Every chest as the game shows it: {scale, opened, found, total, list}."""
    rows = opened_rows(conn, user_id)
    listing = []
    for chest_id in STARS:
        row = rows.get(chest_id)
        entry = {'id': chest_id, 'place': place_of(chest_id), 'open': row is not None,
                 'stars': row['stars'] if row else reward(chest_id, settings.chest_stars_scale)}
        if row:
            entry['opened'] = row['opened']
        listing.append(entry)
    opened = [chest_id for chest_id in STARS if chest_id in rows]
    return {'scale': settings.chest_stars_scale, 'opened': opened, 'found': len(opened), 'total': len(STARS), 'list': listing}


def brief(conn, user_id):
    """The poll's share (/v1/me): the ids already opened and how many chests there are."""
    rows = opened_rows(conn, user_id)
    return {'opened': [chest_id for chest_id in STARS if chest_id in rows], 'total': len(STARS)}


def describe(conn, user_id):
    """Operator view (admin_cli chests show)."""
    rows = opened_rows(conn, user_id)
    return {'opened': [dict(r) for r in sorted(rows.values(), key=lambda r: r['opened'])],
            'left': [chest_id for chest_id in STARS if chest_id not in rows],
            'paid': [dict(r) for r in conn.execute("SELECT reference AS chest,amount,created FROM ledger WHERE user_id=? AND reason='chest_reward' ORDER BY created", (user_id,))]}


class Treasure:
    def __init__(self, app, db, settings, clock, auth, mutate, money, host_for):
        self.settings = settings
        with db.read() as conn:
            conn.executescript(SCHEMA)

        @app.get('/v1/chests')
        def read(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                return {'chests': public(conn, user['id'], settings)}

        @app.post('/v1/chests/{chest_id}/open')
        def open_chest(chest_id: str, body: Mutation, request: Request):
            if chest_id not in STARS:
                fail('chest_not_found', 404)

            def apply(conn, user):
                # A visitor stands in a friend's village (or home): those chests are the friend's.
                if host_for(conn, user['id']) != user['id']:
                    fail('chest_own_village_only')
                if conn.execute('SELECT 1 FROM chest_opened WHERE user_id=? AND chest_id=?', (user['id'], chest_id)).fetchone():
                    fail('chest_already_open')
                # Once per account: the ledger has at most one reward per chest.
                if conn.execute("SELECT 1 FROM ledger WHERE user_id=? AND reason='chest_reward' AND reference=?", (user['id'], chest_id)).fetchone():
                    fail('chest_already_open')
                now = clock()
                last = conn.execute('SELECT MAX(opened) FROM chest_opened WHERE user_id=?', (user['id'],)).fetchone()[0]
                if last is not None and now - float(last) < CHEST_GAP:
                    fail('chest_too_fast', 429)
                stars = reward(chest_id, settings.chest_stars_scale)
                if stars:
                    money(conn, user['id'], stars, 'chest_reward', chest_id)
                conn.execute('INSERT INTO chest_opened(user_id,chest_id,opened,stars) VALUES (?,?,?,?)', (user['id'], chest_id, now, stars))
                shards = conn.execute('SELECT shards FROM users WHERE id=?', (user['id'],)).fetchone()[0]
                listing = public(conn, user['id'], settings)
                return {'chest': next(c for c in listing['list'] if c['id'] == chest_id), 'stars': stars, 'shards': shards,
                        'chests': {'opened': listing['opened'], 'total': listing['total']}}
            return mutate(request, body, 'chest_open:' + chest_id, apply)

    def brief_for(self, conn, user_id):
        """/v1/me's share (brief above)."""
        return brief(conn, user_id)
