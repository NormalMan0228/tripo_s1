"""The opening story chapter "마을의 첫 선물" (the village's first gift), per player and kept here.

A workshop maker has just moved to the island. Every new account starts the chapter (accounts made
before it existed never see it; an operator can start or restart it with
`python -m server.admin_cli story reset USERNAME`):

  letter  a welcome letter lies on the desk at home (game/scripts/studio.gd shows it)
  cafe    the letter is read: go and say hello at the café '빨간 지붕'
  craft   모카, the café owner (day_folk.gd 'regular'), asked for a chair for strollers to rest on;
          the player crafts something with the ordinary craft window and brings it
  done    the piece was given: it stands on the café terrace for good, 모카 wrote a thank-you letter
          with a small return gift (the residents' letters, server/npc_homes.py)

Any piece is accepted, so the chapter never stalls: a seat (rest 'sit', the seating family, or a
seat by its name) is set out for strollers to sit on, anything else becomes the terrace's
decoration. The terrace is an outdoor "home" of 모카's in npc_homes (home_id 'cafe_terrace', one
fixed slot in village coordinates): the piece turns 'gifted' and stands there at once (no random
delay, unlike ordinary gifts), and visitors read it through the same guest routes as the
residents' rooms.
"""
import json
import uuid
from typing import Literal
from fastapi import HTTPException, Request
from pydantic import Field
from .models import Mutation
from . import npc_homes, archetypes, build_rules

CHAPTER = 'first_gift'
STEPS = ('letter', 'cafe', 'craft', 'done')
# 모카 · 카페 주인 (game/scripts/day_folk.gd, shadow_folk.gd 'regular').
SENDER = 'regular'
TERRACE = 'cafe_terrace'
SLOT = 'terrace'
# Residents who may greet the newcomer once (shadow_folk.gd FOLK ids and the cast villagers).
GREETERS = {'postman', 'fisher', 'farmer', 'sweeper', 'gentleman', 'stargazer', 'lamplighter', 'gardener', 'scout',
            'miller', 'shopkeeper', 'kid', 'stroller', 'poet', 'naru', 'sora', 'moru', 'haeru'}
# 모카's thank-you present: a procedural piece like the residents' return gifts (no generation).
RETURN_GIFT = {'title': '카페 머그잔', 'category': 'mug', 'parts': [
    ('saucer', 'ellipsoid', [0.34, 0.04, 0.34], [0, 0.02, 0], '#f2ead8'),
    ('cup', 'ellipsoid', [0.22, 0.22, 0.22], [0, 0.14, 0], '#d9826b'),
    ('handle', 'ellipsoid', [0.07, 0.12, 0.04], [0.13, 0.14, 0], '#c86f58'),
    ('coffee', 'ellipsoid', [0.17, 0.03, 0.17], [0, 0.245, 0], '#6b4226')]}

SCHEMA = '''
CREATE TABLE IF NOT EXISTS story_progress (
 user_id TEXT PRIMARY KEY REFERENCES users(id), chapter TEXT NOT NULL,
 step TEXT NOT NULL CHECK(step IN ('letter','cafe','craft','done')), run INTEGER NOT NULL DEFAULT 1,
 greeted TEXT NOT NULL DEFAULT '[]', requested_at REAL, gift_object_id TEXT, sittable INTEGER, letter_id TEXT,
 started REAL NOT NULL, updated REAL NOT NULL, completed REAL);
'''
# Crafts that are over (asset_studio.py states).
ENDED = ('ready', 'failed', 'cancelled', 'unknown')


class StoryStep(Mutation):
    action: Literal['read_letter', 'accept', 'greet']
    npc: str = Field(default='', max_length=24, pattern=r'^[a-z_]*$')


class StoryGift(Mutation):
    object_id: uuid.UUID
    version: int = Field(ge=1)


def fail(code, status=409):
    raise HTTPException(status, code)


def begin(conn, user_id, now):
    """A new account starts the chapter at its first step."""
    conn.execute('INSERT OR IGNORE INTO story_progress(user_id,chapter,step,started,updated) VALUES (?,?,?,?,?)',
                 (user_id, CHAPTER, 'letter', now, now))


def sittable(conn, obj):
    """True for a piece someone can sit on: its interaction's rest, else its library type's, else
    a seat by its name or design (the welcome chair and other one-mesh pieces)."""
    row = conn.execute('SELECT spec FROM object_interactions WHERE object_id=?', (obj['id'],)).fetchone()
    rest = json.loads(row['spec']).get('rest', '') if row else ''
    if rest:
        return rest == 'sit'
    studio = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
    manifest = json.loads(studio['manifest']) if studio else {}
    kind = archetypes.BY_ID.get(str(manifest.get('provenance', {}).get('archetype', '')))
    if kind and kind.get('rest'):
        return kind['rest'] == 'sit'
    plan = manifest.get('plan', {})
    return 'seat' in npc_homes.item_tags(obj['name'], plan.get('title'), plan.get('category'))


def public(conn, user_id):
    """The chapter as the game shows it, or None for an account without it."""
    row = conn.execute('SELECT * FROM story_progress WHERE user_id=?', (user_id,)).fetchone()
    if not row:
        return None
    out = {'chapter': row['chapter'], 'step': row['step'], 'run': row['run'], 'greeted': json.loads(row['greeted']),
           'terrace': TERRACE, 'sender': SENDER}
    if row['step'] == 'craft':
        # Pieces made since 모카 asked, newest first (in the bag or set down; listed and given ones are not).
        out['made'] = [{'id': r['id'], 'name': r['name'], 'version': r['version'], 'state': r['state']} for r in conn.execute(
            "SELECT id,name,version,state FROM objects WHERE owner_id=? AND state IN ('inventory','placed') AND created>? "
            "ORDER BY created DESC,rowid DESC LIMIT 6", (user_id, row['requested_at'] or 0))]
        out['crafting'] = conn.execute('SELECT 1 FROM studio_jobs WHERE owner_id=? AND state NOT IN (%s) LIMIT 1' % ','.join('?' * len(ENDED)),
                                       (user_id, *ENDED)).fetchone() is not None
    if row['step'] == 'done':
        gift = conn.execute('SELECT name FROM objects WHERE id=?', (row['gift_object_id'],)).fetchone()
        out['gift'] = {'id': row['gift_object_id'], 'name': gift['name'] if gift else '', 'sittable': bool(row['sittable'])}
        letter = conn.execute('SELECT read_at FROM npc_letters WHERE id=?', (row['letter_id'],)).fetchone()
        out['letter'] = {'id': row['letter_id'], 'read': bool(letter and letter['read_at'] is not None)}
    return out


def reset(conn, user_id, now):
    """Back to the first step for a rehearsal (or the first time, for an account made before the
    chapter). Nothing is deleted but the terrace's placement: the piece on the café terrace goes
    back to the player's bag; letters, return gifts and every other piece stay. The caller has the
    tables (npc_homes.SCHEMA, SCHEMA) and the transaction."""
    returned = []
    for item in conn.execute('SELECT object_id FROM npc_items WHERE host_id=? AND home_id=?', (user_id, TERRACE)).fetchall():
        conn.execute("UPDATE objects SET state='inventory',x=NULL,z=NULL,version=version+1 WHERE id=? AND owner_id=? AND state='gifted'",
                     (item['object_id'], user_id))
        returned.append(item['object_id'])
    conn.execute('DELETE FROM npc_items WHERE host_id=? AND home_id=?', (user_id, TERRACE))
    conn.execute('UPDATE npc_homes SET version=version+1,updated=? WHERE host_id=? AND home_id=?', (now, user_id, TERRACE))
    row = conn.execute('SELECT run FROM story_progress WHERE user_id=?', (user_id,)).fetchone()
    if row:
        conn.execute("UPDATE story_progress SET chapter=?,step='letter',run=run+1,greeted='[]',requested_at=NULL,gift_object_id=NULL,"
                     "sittable=NULL,letter_id=NULL,started=?,updated=?,completed=NULL WHERE user_id=?", (CHAPTER, now, now, user_id))
    else:
        begin(conn, user_id, now)
    return {'step': 'letter', 'run': (row['run'] + 1) if row else 1, 'returned_to_bag': returned}


def describe(conn, user_id):
    """Operator view (admin_cli story show)."""
    row = conn.execute('SELECT * FROM story_progress WHERE user_id=?', (user_id,)).fetchone()
    terrace = [dict(r) for r in conn.execute('SELECT i.object_id,o.name,i.state,i.slot FROM npc_items i JOIN objects o ON o.id=i.object_id '
                                             'WHERE i.host_id=? AND i.home_id=?', (user_id, TERRACE))]
    return {'progress': dict(row) if row else None, 'terrace': terrace}


class Story:
    def __init__(self, app, db, settings, clock, auth, mutate, host_for, assets):
        self.db, self.settings, self.clock = db, settings, clock
        with db.read() as conn:
            conn.executescript(SCHEMA)

        def progress(conn, user_id):
            row = conn.execute('SELECT * FROM story_progress WHERE user_id=?', (user_id,)).fetchone()
            if not row:
                fail('story_not_started', 404)
            return row

        @app.get('/v1/story')
        def read(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                return {'story': public(conn, user['id'])}

        @app.post('/v1/story/step')
        def step(body: StoryStep, request: Request):
            def apply(conn, user):
                row = progress(conn, user['id'])
                now = clock()
                if body.action == 'read_letter' and row['step'] == 'letter':
                    conn.execute("UPDATE story_progress SET step='cafe',updated=? WHERE user_id=?", (now, user['id']))
                elif body.action == 'accept' and row['step'] in ('letter', 'cafe'):
                    # 모카 asked: what the player makes from now on is offered first.
                    conn.execute("UPDATE story_progress SET step='craft',requested_at=?,updated=? WHERE user_id=?", (now, now, user['id']))
                elif body.action == 'greet':
                    if body.npc not in GREETERS:
                        fail('unknown_resident', 422)
                    greeted = json.loads(row['greeted'])
                    if body.npc not in greeted:
                        greeted.append(body.npc)
                        conn.execute('UPDATE story_progress SET greeted=?,updated=? WHERE user_id=?', (json.dumps(greeted), now, user['id']))
                return {'story': public(conn, user['id'])}
            return mutate(request, body, 'story_step', apply)

        @app.post('/v1/story/gift')
        def gift(body: StoryGift, request: Request):
            def give(conn, user):
                # In the player's own village only (a visit shows the host's terrace).
                if host_for(conn, user['id']) != user['id']:
                    fail('gift_own_village_only')
                row = progress(conn, user['id'])
                if row['step'] == 'done':
                    fail('story_already_done')
                now = clock()
                obj = conn.execute('SELECT * FROM objects WHERE id=? AND owner_id=?', (str(body.object_id), user['id'])).fetchone()
                if not obj or obj['state'] == 'gifted':
                    fail('object_not_found', 404)
                if obj['version'] != body.version:
                    fail('stale_object_version')
                if obj['state'] == 'listed':
                    fail('object_is_listed')
                # The piece's box, measured the way the residents' rooms measure gifts.
                studio = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
                shape = conn.execute('SELECT width,depth,height,scale FROM object_shape WHERE object_id=?', (obj['id'],)).fetchone()
                shape = dict(shape) if shape else None
                if studio:
                    manifest = json.loads(studio['manifest'])
                    runtime = conn.execute('SELECT bindings FROM studio_runtime WHERE object_id=?', (obj['id'],)).fetchone()
                    size = npc_homes.measured_size(manifest, json.loads(runtime['bindings']) if runtime else {}, shape)
                    plan = manifest.get('plan', {})
                    tags = npc_homes.item_tags(obj['name'], plan.get('title'), plan.get('category'))
                else:
                    tags = npc_homes.item_tags(obj['name'])
                    size = npc_homes.legacy_size(conn, assets, obj, tags, shape)
                seat = sittable(conn, obj)
                # From the bag or from where it stood, exactly once.
                if conn.execute("UPDATE objects SET state='gifted',x=NULL,z=NULL,version=version+1 WHERE id=? AND owner_id=? "
                                "AND state IN ('inventory','placed') AND version=?", (obj['id'], user['id'], body.version)).rowcount != 1:
                    fail('stale_object_version')
                conn.execute('DELETE FROM furniture_locations WHERE object_id=?', (obj['id'],))
                # Pieces that stood on it go back to the bag (server/build_rules.py).
                build_rules.retrieve(conn, obj['id'])
                # Out on the terrace at once (an earlier piece, if any, goes into 모카's storage).
                conn.execute("UPDATE npc_items SET state='stored',slot=NULL WHERE host_id=? AND home_id=? AND state='placed'", (user['id'], TERRACE))
                conn.execute('INSERT INTO npc_items(object_id,host_id,npc_id,home_id,state,slot,yaw,fresh,size,tags,gifted,placed_at) '
                             "VALUES (?,?,?,?,'placed',?,?,0,?,?,?,?)",
                             (obj['id'], user['id'], SENDER, TERRACE, SLOT, npc_homes.SLOT_BY_ID[TERRACE][SLOT]['yaw'],
                              json.dumps(size), json.dumps(tags), now, now))
                conn.execute('INSERT OR IGNORE INTO npc_homes(host_id,home_id,seed,updated) VALUES (?,?,?,?)', (user['id'], TERRACE, 1, now))
                conn.execute('UPDATE npc_homes SET version=version+1,next_change_at=NULL,updated=? WHERE host_id=? AND home_id=?', (now, user['id'], TERRACE))
                conn.execute('INSERT INTO npc_gifts VALUES (?,?,?,?,?,?,?)', (str(uuid.uuid4()), user['id'], SENDER, obj['id'], 'love' if seat else 'like', 0, now))
                # 모카's thank-you letter with a small present, in the village mailbox. Each run of the
                # chapter writes its own (levels 0, -1, ... so a rehearsal never collides with an older one).
                letter_id = str(uuid.uuid4())
                present = npc_homes.return_gift(conn, assets, user['id'], SENDER, now, preset=RETURN_GIFT, key='cafe')
                conn.execute('INSERT INTO npc_letters(id,host_id,npc_id,level,gift_object_id,created) VALUES (?,?,?,?,?,?)',
                             (letter_id, user['id'], SENDER, 1 - row['run'], present, now))
                conn.execute("UPDATE story_progress SET step='done',requested_at=COALESCE(requested_at,?),gift_object_id=?,sittable=?,"
                             'letter_id=?,completed=?,updated=? WHERE user_id=?', (now, obj['id'], int(seat), letter_id, now, now, user['id']))
                home = conn.execute('SELECT version FROM npc_homes WHERE host_id=? AND home_id=?', (user['id'], TERRACE)).fetchone()
                placed = [item for item in npc_homes.placed_items(conn, user['id'], TERRACE) if item['id'] == obj['id']]
                return {'story': public(conn, user['id']), 'object_id': obj['id'], 'name': obj['name'], 'sittable': seat,
                        'placed': placed[0] if placed else None, 'home': TERRACE, 'home_version': home['version'],
                        'letters': [letter for letter in npc_homes.letters(conn, user['id']) if letter['id'] == letter_id]}
            return mutate(request, body, 'story_gift', give)

    def begin(self, conn, user_id, now):
        begin(conn, user_id, now)

    def public_for(self, conn, user_id):
        return public(conn, user_id)
