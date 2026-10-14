"""Gifts to village residents and the homes they decorate with them.

Every player owns their own village, so every resident's home is per player: the rows here are
keyed by the village owner (host_id). Visitors read the host's rows through the guest route.

A gift moves one crafted piece from the player's bag into the resident's storage: the object
row keeps its owner (the village owner) but turns 'gifted', so the bag, the market and every
owner route stop offering it, in the same transaction that files it under the resident.

The resident decorates its home building on its own, at times the server picks, so every device
and every visitor sees the same rooms:

* each home (host, building) keeps a seed, a step counter and next_change_at;
* whenever a home is read or polled, the changes that are due run in order (lazily: there is no
  timer), each drawn from Random("seed:step"), so the rooms depend only on the gifts and the clock;
* a fresh gift goes up after a random delay (settings.npc_place_min..max); later the resident
  sometimes brings a stored piece out, moves one, swaps one or puts one back
  (settings.npc_shuffle_min..max), weighted by its taste;
* pieces stand at fixed slots (floor, wall, table top) with size limits and taste tags, chosen by
  rules; a piece that fits no free slot stays in storage.

Clients cache a home by its version; /v1/me (owner) and the visit presence carry the versions.
"""
import json
import math
import random
import re
import secrets
import uuid
from fastapi import HTTPException, Request
from pydantic import Field
from .models import Mutation
from .asset_assembly import extent
from . import homestead, object_paint, object_shape

SCHEMA = '''
CREATE TABLE IF NOT EXISTS npc_homes (
 host_id TEXT NOT NULL REFERENCES users(id), home_id TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, seed INTEGER NOT NULL, step INTEGER NOT NULL DEFAULT 0,
 next_change_at REAL, updated REAL NOT NULL, PRIMARY KEY(host_id,home_id));
CREATE INDEX IF NOT EXISTS npc_homes_due ON npc_homes(host_id,next_change_at);
CREATE TABLE IF NOT EXISTS npc_items (
 object_id TEXT PRIMARY KEY REFERENCES objects(id), host_id TEXT NOT NULL REFERENCES users(id),
 npc_id TEXT NOT NULL, home_id TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('stored','placed')),
 slot TEXT, yaw INTEGER NOT NULL DEFAULT 0, fresh INTEGER NOT NULL DEFAULT 1 CHECK(fresh IN (0,1)),
 size TEXT NOT NULL, tags TEXT NOT NULL, gifted REAL NOT NULL, placed_at REAL);
CREATE INDEX IF NOT EXISTS npc_items_home ON npc_items(host_id,home_id,state);
CREATE UNIQUE INDEX IF NOT EXISTS npc_items_one_per_slot ON npc_items(host_id,home_id,slot) WHERE state='placed';
CREATE TABLE IF NOT EXISTS npc_friendship (
 host_id TEXT NOT NULL REFERENCES users(id), npc_id TEXT NOT NULL, points INTEGER NOT NULL DEFAULT 0,
 gifts INTEGER NOT NULL DEFAULT 0, last_day INTEGER, PRIMARY KEY(host_id,npc_id));
CREATE TABLE IF NOT EXISTS npc_gifts (
 id TEXT PRIMARY KEY, host_id TEXT NOT NULL REFERENCES users(id), npc_id TEXT NOT NULL,
 object_id TEXT NOT NULL REFERENCES objects(id), mood TEXT NOT NULL, points INTEGER NOT NULL, created REAL NOT NULL);
'''

# Who takes gifts: every resident whose bed is in a house (game/scripts/residents.gd, same homes).
# Shop and workplace owners sleep in back rooms of working buildings and are left out for now.
# personality picks the client's reaction lines; taste weights the item tags below.
NPCS = {
    'naru': {'home': '02_timber_house', 'personality': 'cheerful', 'taste': {'travel': 3, 'light': 2, 'nature': 1}},
    'scout': {'home': '02_timber_house', 'personality': 'calm', 'taste': {'travel': 2, 'storage': 2, 'nature': 1}},
    'sora': {'home': '11_purple_house', 'personality': 'elegant', 'taste': {'art': 3, 'cozy': 2, 'seat': 1}},
    'gentleman': {'home': '11_purple_house', 'personality': 'elegant', 'taste': {'clock': 3, 'book': 2, 'music': 1}},
    'poet': {'home': '11_purple_house', 'personality': 'dreamy', 'taste': {'book': 3, 'plant': 2, 'light': 1}},
    'moru': {'home': '16_blue_cottage', 'personality': 'calm', 'taste': {'light': 3, 'storage': 2, 'seat': 1}},
    'lamplighter': {'home': '16_blue_cottage', 'personality': 'calm', 'taste': {'light': 3, 'clock': 1}},
    'haeru': {'home': '17_lighthouse', 'personality': 'cheerful', 'taste': {'sea': 3, 'clock': 1, 'storage': 1}},
    'stroller': {'home': '17_lighthouse', 'personality': 'dreamy', 'taste': {'sea': 2, 'light': 2, 'plant': 1}},
    'postman': {'home': '12_blue_house', 'personality': 'cheerful', 'taste': {'storage': 3, 'clock': 2}},
    'sweeper': {'home': '12_blue_house', 'personality': 'calm', 'taste': {'plant': 3, 'cozy': 1}},
    'fisher': {'home': '06_orange_cottage', 'personality': 'calm', 'taste': {'sea': 3, 'kitchen': 2}},
    'kid': {'home': '06_orange_cottage', 'personality': 'playful', 'taste': {'toy': 3, 'animal': 2, 'music': 1}},
}

# Item tags from the piece's name and its design title/category. English words match whole-word
# prefixes ("lamp" matches "lamps", not "clamp"); Korean words match anywhere in the text.
TAG_WORDS = {
    'light': ('lamp', 'lantern', 'light', 'candle', 'torch', '램프', '등불', '조명', '랜턴', '촛대', '양초', '스탠드'),
    'plant': ('plant', 'flower', 'tree', 'cactus', 'bonsai', 'planter', '화분', '꽃', '나무', '식물', '선인장'),
    'seat': ('chair', 'stool', 'sofa', 'bench', 'seat', 'armchair', '의자', '소파', '벤치', '방석', '걸상'),
    'table': ('table', 'desk', '탁자', '책상', '테이블'),
    'storage': ('chest', 'box', 'shelf', 'cabinet', 'drawer', 'crate', 'basket', 'trunk', '상자', '선반', '서랍', '바구니', '궤짝', '수납'),
    'clock': ('clock', 'watch', 'hourglass', '시계'),
    'book': ('book', 'scroll', 'journal', 'notebook', '책', '두루마리', '일기'),
    'art': ('picture', 'frame', 'painting', 'statue', 'vase', 'mirror', 'sculpture', '그림', '액자', '조각', '꽃병', '거울'),
    'music': ('music', 'piano', 'guitar', 'drum', 'bell', 'gramophone', 'harp', '악기', '피아노', '기타', '오르골', '축음기', '하프'),
    'sea': ('fish', 'boat', 'ship', 'anchor', 'shell', 'wave', 'buoy', 'lighthouse', '물고기', '돛단배', '닻', '조개', '그물', '등대', '바다'),
    'toy': ('toy', 'doll', 'ball', 'robot', 'teddy', 'kite', 'puzzle', '장난감', '인형', '로봇', '곰인형', '팽이'),
    'cozy': ('rug', 'cushion', 'blanket', 'pillow', 'bed', 'quilt', '러그', '쿠션', '담요', '베개', '침대', '이불'),
    'travel': ('map', 'compass', 'globe', 'backpack', 'tent', 'telescope', '지도', '나침반', '지구본', '배낭', '텐트', '망원경'),
    'kitchen': ('cup', 'pot', 'kettle', 'teapot', 'plate', 'bread', 'oven', 'mug', '컵', '주전자', '접시', '빵', '냄비', '머그'),
    'animal': ('cat', 'dog', 'bird', 'rabbit', 'animal', 'bear', '고양이', '강아지', '토끼', '동물', '새장'),
    'nature': ('stone', 'rock', 'wood', 'log', 'leaf', 'mushroom', 'moss', '바위', '통나무', '나뭇잎', '버섯', '이끼'),
}

# Rearrangement odds once every gift has had its first turn (higher = more often).
SHUFFLE_WEIGHTS = {'bring_out': 3, 'move': 2, 'swap': 2, 'put_back': 1}
# Changes one read may catch up on; a home left alone longer skips ahead from now.
MAX_CATCH_UP = 24
# Friendship points for the hearts (0..4) and per gift: the first gift of the player's day counts
# fully (more for a piece the resident loves), later ones that day a little.
LEVELS = (0, 30, 80, 160, 300)
GAIN = {'love': 20, 'like': 15, 'thanks': 10}
GAIN_AGAIN = 2


def _slots(*rows):
    return [dict(id=r[0], floor=r[1], kind=r[2], x=r[3], z=r[4], y=r[5], yaw=r[6], max=r[7], tags=r[8]) for r in rows]


# Slots per home building: (id, floor, kind, x, z, y, yaw, (max width, height, depth), tags).
# Coordinates are the interior floor's (game/scripts/interiors.gd: centre origin, back wall at
# -depth/2, door at the front): free floor between the fixed furniture, bare wall between the
# windows (y = the piece's bottom edge; yaw = the way it faces), and table tops (y = nominal top;
# the client sets the piece on the real table's top). Floor pieces may turn 90 degrees to fit.
SLOTS = {
    '02_timber_house': _slots(
        ('hearth_side', 0, 'floor', -1.75, -3.75, 0.0, 0, (1.3, 1.1, 1.3), ('cozy', 'book')),
        ('front_corner', 0, 'floor', -2.8, 2.6, 0.0, 0, (1.6, 2.2, 1.4), ('cozy', 'travel', 'seat')),
        ('stair_side', 0, 'floor', 4.0, 1.2, 0.0, 0, (1.0, 2.0, 1.0), ('light', 'plant')),
        ('table', 0, 'table', 2.15, 1.45, 0.78, 0, (0.7, 0.7, 0.7), ('kitchen', 'plant', 'light')),
        ('wall', 0, 'wall', 4.75, 3.25, 1.45, -90, (0.8, 0.9, 0.3), ('art', 'clock')),
        ('loft', 1, 'floor', 1.75, 2.0, 0.0, 0, (1.4, 1.8, 1.1), ('cozy', 'toy')),
    ),
    '06_orange_cottage': _slots(
        ('bedroom_front', 0, 'floor', 2.5, 2.5, 0.0, 0, (1.2, 1.8, 0.9), ('cozy', 'toy')),
        ('bedroom_window', 0, 'floor', 3.2, -0.4, 0.0, 0, (1.0, 1.1, 1.0), ('sea', 'plant')),
        ('kitchen_back', 0, 'floor', -0.25, -2.55, 0.0, 0, (1.1, 1.1, 1.0), ('kitchen', 'plant')),
        ('table', 0, 'table', -1.33, 0.6, 0.78, 0, (0.7, 0.6, 0.5), ('kitchen', 'plant')),
        ('kitchen_wall', 0, 'wall', -4.0, -1.95, 1.25, 90, (0.8, 0.9, 0.3), ('art', 'clock', 'kitchen')),
        ('bedroom_wall', 0, 'wall', 4.0, 2.6, 1.3, -90, (0.6, 0.8, 0.3), ('art', 'toy')),
    ),
    '11_purple_house': _slots(
        ('study_middle', 0, 'floor', 2.6, -1.9, 0.0, 0, (1.6, 1.8, 1.4), ('book', 'music', 'clock')),
        ('study_front', 0, 'floor', 2.55, 2.6, 0.0, 0, (1.3, 1.8, 1.1), ('art', 'plant')),
        ('parlour_back', 0, 'floor', -1.55, -3.3, 0.0, 0, (1.0, 1.05, 1.0), ('music', 'plant')),
        ('tea_table', 0, 'table', -2.55, 0.8, 0.76, 0, (0.45, 0.5, 0.45), ('kitchen', 'plant', 'light')),
        ('parlour_wall', 0, 'wall', -4.5, 0.8, 1.35, 90, (1.2, 0.8, 0.25), ('art', 'clock')),
        ('study_wall', 0, 'wall', 4.5, 2.35, 1.35, -90, (0.7, 0.8, 0.3), ('art', 'clock', 'book')),
    ),
    '12_blue_house': _slots(
        ('bedroom_side', 0, 'floor', -3.2, -0.3, 0.0, 0, (1.1, 1.05, 1.0), ('cozy', 'storage')),
        ('bath_middle', 0, 'floor', 2.2, -1.45, 0.0, 0, (1.4, 1.8, 1.4), ('plant', 'sea', 'storage')),
        ('table', 0, 'table', -0.37, 1.75, 0.76, 0, (0.45, 0.5, 0.45), ('kitchen', 'plant', 'light')),
        ('bed_wall', 0, 'wall', -2.35, -3.5, 1.35, 0, (1.0, 0.9, 0.25), ('art', 'clock')),
        ('bath_wall', 0, 'wall', 0.56, -1.3, 1.3, 90, (0.8, 0.8, 0.25), ('art', 'sea')),
    ),
    '16_blue_cottage': _slots(
        ('living_side', 0, 'floor', -3.3, 1.1, 0.0, 0, (1.2, 1.5, 1.2), ('light', 'travel', 'storage')),
        ('living_front', 0, 'floor', -0.1, 2.2, 0.0, 0, (0.9, 1.8, 1.0), ('light', 'plant')),
        ('bedroom_middle', 0, 'floor', 2.75, -0.5, 0.0, 0, (1.1, 1.8, 1.1), ('cozy', 'storage')),
        ('chest_top', 0, 'table', 1.53, -1.3, 0.6, 0, (0.6, 0.5, 0.4), ('light', 'plant')),
        ('bed_wall', 0, 'wall', 2.49, -3.75, 1.3, 0, (0.9, 0.8, 0.25), ('art', 'clock')),
        ('living_wall', 0, 'wall', -4.25, -2.3, 1.25, 90, (0.7, 0.8, 0.25), ('art', 'light')),
    ),
    '17_lighthouse': _slots(
        ('store_corner', 0, 'floor', -1.5, 1.7, 0.0, 0, (0.9, 1.5, 0.9), ('sea', 'storage')),
        ('map_table', 0, 'table', 1.95, 0.85, 0.85, 0, (0.5, 0.5, 0.5), ('sea', 'travel', 'light')),
        ('keeper_desk', 1, 'table', 0.75, -2.2, 0.8, 0, (0.45, 0.45, 0.4), ('book', 'light', 'clock')),
    ),
}
SLOT_BY_ID = {home: {s['id']: s for s in slots} for home, slots in SLOTS.items()}


class Gift(Mutation):
    object_id: uuid.UUID
    version: int = Field(ge=1)


def fail(code, status=409):
    raise HTTPException(status, code)


def item_tags(*texts):
    low = ' '.join(str(t) for t in texts if t).casefold()
    words = re.findall(r'[a-z]+', low)
    found = []
    for tag, keys in TAG_WORDS.items():
        if any((any(w.startswith(k) for w in words) if k.isascii() else k in low) for k in keys):
            found.append(tag)
    return found


def measured_size(manifest, bindings, shape):
    """The piece's box in metres (width, height, depth) as the game builds it: the designed parts
    with the owner's part fits, stretched by the owner's shape edit."""
    parts = [{**p, **{k: v for k, v in bindings.get(p['id'], {}).items() if k in ('position', 'size')}}
             for p in manifest['plan']['parts']]
    size = extent(parts)
    if shape:
        scale = shape['scale'] / 100
        size = [size[0] * shape['width'] / 100 * scale, size[1] * shape['height'] / 100 * scale, size[2] * shape['depth'] / 100 * scale]
    return [round(v, 3) for v in size]


def fits(slot, size):
    """The facing (degrees) a piece of this size takes in the slot, or None when it does not fit."""
    w, h, d = size
    width, height, depth = slot['max']
    if h > height:
        return None
    if slot['kind'] == 'wall':
        # Only flat pieces hang on a wall, never turned.
        return slot['yaw'] if w <= width and d <= depth and d * 2 <= min(w, h) else None
    if w <= width and d <= depth:
        return slot['yaw']
    if d <= width and w <= depth:
        return (slot['yaw'] + 90) % 360
    return None


def position(slot, size):
    x, z = slot['x'], slot['z']
    if slot['kind'] == 'wall':
        # The piece's back touches the wall; it hangs out by half its depth.
        turn = math.radians(slot['yaw'])
        push = size[2] / 2 + 0.02
        x, z = x + math.sin(turn) * push, z + math.cos(turn) * push
    return round(x, 3), round(slot['y'], 3), round(z, 3)


def taste(item):
    weights = NPCS.get(item['npc_id'], {}).get('taste', {})
    return sum(weights.get(tag, 0) for tag in item['tags'])


def slot_weight(slot, item):
    weight = 1 + 2 * len(set(slot['tags']) & set(item['tags']))
    return weight + {'wall': 3, 'table': 1}.get(slot['kind'], 0)


def pick(rng, entries, weights):
    return entries[0] if len(entries) == 1 else rng.choices(entries, weights=weights)[0]


def friendship(conn, host_id, npc_id):
    row = conn.execute('SELECT points,gifts FROM npc_friendship WHERE host_id=? AND npc_id=?', (host_id, npc_id)).fetchone()
    points = row['points'] if row else 0
    level = sum(1 for threshold in LEVELS[1:] if points >= threshold)
    return {'points': points, 'gifts': row['gifts'] if row else 0, 'level': level,
            'next': LEVELS[level + 1] if level + 1 < len(LEVELS) else None}


def versions(conn, host_id):
    return {r['home_id']: r['version'] for r in conn.execute('SELECT home_id,version FROM npc_homes WHERE host_id=?', (host_id,))}


def due(conn, host_id, now, home_id=None):
    if home_id:
        return conn.execute('SELECT 1 FROM npc_homes WHERE host_id=? AND home_id=? AND next_change_at<=?', (host_id, home_id, now)).fetchone() is not None
    return conn.execute('SELECT 1 FROM npc_homes WHERE host_id=? AND next_change_at<=? LIMIT 1', (host_id, now)).fetchone() is not None


def load_items(conn, host_id, home_id):
    items = [dict(r) for r in conn.execute('SELECT * FROM npc_items WHERE host_id=? AND home_id=? ORDER BY gifted,rowid', (host_id, home_id))]
    for item in items:
        item['size'], item['tags'] = json.loads(item['size']), json.loads(item['tags'])
    return items


def change(conn, home_id, items, rng, at):
    """One rearrangement at time `at`. Returns True when the room looks different."""
    slots = SLOTS[home_id]
    by_id = SLOT_BY_ID[home_id]

    def free():
        taken = {i['slot'] for i in items if i['state'] == 'placed'}
        return [s for s in slots if s['id'] not in taken]

    def options(item):
        return [(s, yaw) for s in free() if (yaw := fits(s, item['size'])) is not None]

    def put(item, slot, yaw):
        item.update(state='placed', slot=slot['id'], yaw=yaw, fresh=0)
        conn.execute("UPDATE npc_items SET state='placed',slot=?,yaw=?,fresh=0,placed_at=? WHERE object_id=?",
                     (slot['id'], yaw, at, item['object_id']))

    def store(item):
        item.update(state='stored', slot=None, yaw=0)
        conn.execute("UPDATE npc_items SET state='stored',slot=NULL,yaw=0 WHERE object_id=?", (item['object_id'],))

    def place_somewhere(item):
        choices = options(item)
        slot, yaw = pick(rng, choices, [slot_weight(s, item) for s, _ in choices])
        put(item, slot, yaw)

    placed = [i for i in items if i['state'] == 'placed']
    stored = [i for i in items if i['state'] == 'stored']
    fresh = [i for i in stored if i['fresh']]
    if fresh:
        # A new gift goes up first; when no free slot fits, the least loved piece whose slot fits
        # makes room. Pieces that fit nowhere stay in storage.
        gift = fresh[0]
        if options(gift):
            place_somewhere(gift)
            return True
        room = [(p, yaw) for p in placed if (yaw := fits(by_id[p['slot']], gift['size'])) is not None]
        if room:
            old, yaw = pick(rng, room, [1 / (1 + taste(p)) for p, _ in room])
            slot = by_id[old['slot']]
            store(old)
            put(gift, slot, yaw)
            return True
        gift['fresh'] = 0
        conn.execute('UPDATE npc_items SET fresh=0 WHERE object_id=?', (gift['object_id'],))
        return False
    possible = {
        'bring_out': [i for i in stored if options(i)],
        'move': [i for i in placed if options(i)],
        'swap': [(p, s) for p in placed for s in stored if fits(by_id[p['slot']], s['size']) is not None],
        'put_back': placed if len(placed) >= 2 else [],
    }
    actions = [a for a in SHUFFLE_WEIGHTS if possible[a]]
    if not actions:
        return False
    action = pick(rng, actions, [SHUFFLE_WEIGHTS[a] for a in actions])
    entries = possible[action]
    if action == 'bring_out':
        place_somewhere(pick(rng, entries, [1 + taste(i) for i in entries]))
    elif action == 'move':
        item = pick(rng, entries, [1] * len(entries))
        choices = options(item)
        slot, yaw = pick(rng, choices, [slot_weight(s, item) for s, _ in choices])
        put(item, slot, yaw)
    elif action == 'swap':
        old, new = pick(rng, entries, [(1 + taste(s)) / (1 + taste(p)) for p, s in entries])
        slot = by_id[old['slot']]
        store(old)
        put(new, slot, fits(slot, new['size']))
    else:
        store(pick(rng, entries, [1 / (1 + taste(i)) for i in entries]))
    return True


def interval(rng, items, settings):
    if any(i['state'] == 'stored' and i['fresh'] for i in items):
        return rng.uniform(settings.npc_place_min, settings.npc_place_max)
    if items:
        return rng.uniform(settings.npc_shuffle_min, settings.npc_shuffle_max)
    return None


def resolve(conn, host_id, home_id, now, settings):
    """Runs every change of this home that is due by `now` (inside the caller's write transaction)."""
    row = conn.execute('SELECT * FROM npc_homes WHERE host_id=? AND home_id=?', (host_id, home_id)).fetchone()
    if not row or row['next_change_at'] is None or row['next_change_at'] > now:
        return
    items = load_items(conn, host_id, home_id)
    step, at, changed = row['step'], row['next_change_at'], False
    for _ in range(MAX_CATCH_UP):
        if at is None or at > now:
            break
        rng = random.Random(f"{row['seed']}:{step}")
        step += 1
        changed = change(conn, home_id, items, rng, at) or changed
        wait = interval(rng, items, settings)
        at = at + wait if wait is not None else None
    if at is not None and at <= now:
        # Away for a long time: the room changed as much as it will show; carry on from now.
        wait = interval(random.Random(f"{row['seed']}:{step}"), items, settings)
        step += 1
        at = now + wait if wait is not None else None
    conn.execute('UPDATE npc_homes SET version=version+?,step=?,next_change_at=?,updated=? WHERE host_id=? AND home_id=?',
                 (int(changed), step, at, now, host_id, home_id))


def resolve_all(conn, host_id, now, settings):
    for (home_id,) in conn.execute('SELECT home_id FROM npc_homes WHERE host_id=? AND next_change_at<=?', (host_id, now)).fetchall():
        resolve(conn, host_id, home_id, now, settings)


def placed_items(conn, host_id, home_id):
    """What a visitor (or the owner) sees in a home: the pieces standing at their slots."""
    rows = conn.execute(
        "SELECT i.object_id AS id,i.npc_id AS npc,i.slot,i.yaw,i.size,o.name,o.color,o.version,"
        "(SELECT version FROM studio_runtime WHERE object_id=o.id) AS runtime_version,"
        + object_paint.version_column('o.id') + " AS paint_version," + object_shape.column('o.id') + " AS shape "
        "FROM npc_items i JOIN objects o ON o.id=i.object_id WHERE i.host_id=? AND i.home_id=? AND i.state='placed' "
        "ORDER BY i.slot", (host_id, home_id)).fetchall()
    out = []
    for r in rows:
        slot = SLOT_BY_ID[home_id].get(r['slot'])
        if not slot:
            continue
        size = json.loads(r['size'])
        x, y, z = position(slot, size)
        out.append(object_shape.listed({'id': r['id'], 'npc': r['npc'], 'slot': r['slot'], 'kind': slot['kind'], 'floor': slot['floor'],
                    'x': x, 'y': y, 'z': z, 'rotation': r['yaw'], 'size': size, 'name': r['name'], 'color': r['color'],
                    'version': r['version'], 'state': 'placed', 'studio': True, 'runtime_version': r['runtime_version'],
                    'paint_version': r['paint_version'], 'shape': r['shape']}))
    return out


def describe(conn, host_id):
    """Operator view (admin_cli npc-homes): homes, every gift and where it is, friendship."""
    return {'homes': [dict(r) for r in conn.execute('SELECT home_id,version,step,next_change_at,updated FROM npc_homes WHERE host_id=? ORDER BY home_id', (host_id,))],
            'items': [dict(r) for r in conn.execute('SELECT i.object_id,o.name,i.npc_id,i.home_id,i.state,i.slot,i.fresh,i.size,i.tags,i.gifted,i.placed_at '
                                                    'FROM npc_items i JOIN objects o ON o.id=i.object_id WHERE i.host_id=? ORDER BY i.gifted', (host_id,))],
            'friendship': [dict(r) for r in conn.execute('SELECT npc_id,points,gifts,last_day FROM npc_friendship WHERE host_id=? ORDER BY npc_id', (host_id,))]}


class NpcHomes:
    def __init__(self, app, db, settings, clock, auth, mutate, host_for):
        self.db, self.settings, self.clock = db, settings, clock
        with db.read() as conn:
            conn.executescript(SCHEMA)

        def resident(npc_id):
            if npc_id not in NPCS:
                fail('npc_not_found', 404)
            return NPCS[npc_id]

        @app.get('/v1/npcs/{npc_id}/gift')
        def gift_options(npc_id: str, request: Request):
            npc = resident(npc_id)
            with db.read() as conn:
                user = auth(conn, request)
                # Only crafted pieces in the bag: placed, listed and gifted ones are not offered.
                items = [dict(r) for r in conn.execute(
                    "SELECT o.id,o.name,o.color,o.version FROM objects o JOIN studio_assets s ON s.asset_id=o.asset_id "
                    "WHERE o.owner_id=? AND o.state='inventory' ORDER BY o.created DESC LIMIT 24", (user['id'],))]
                return {'npc': npc_id, 'home': npc['home'], 'personality': npc['personality'],
                        'can_gift': host_for(conn, user['id']) == user['id'],
                        'friendship': friendship(conn, user['id'], npc_id), 'items': items}

        @app.post('/v1/npcs/{npc_id}/gift')
        def gift(npc_id: str, body: Gift, request: Request):
            npc = resident(npc_id)

            def give(conn, user):
                # Gifts go to the residents of your own village only.
                if host_for(conn, user['id']) != user['id']:
                    fail('gift_own_village_only')
                now = clock()
                obj = conn.execute('SELECT * FROM objects WHERE id=? AND owner_id=?', (str(body.object_id), user['id'])).fetchone()
                if not obj or obj['state'] == 'gifted':
                    fail('object_not_found', 404)
                if obj['version'] != body.version:
                    fail('stale_object_version')
                if obj['state'] != 'inventory':
                    fail('object_not_in_inventory')
                studio = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
                if not studio:
                    fail('gift_needs_crafted_furniture')
                manifest = json.loads(studio['manifest'])
                runtime = conn.execute('SELECT bindings FROM studio_runtime WHERE object_id=?', (obj['id'],)).fetchone()
                shape = conn.execute('SELECT width,depth,height,scale FROM object_shape WHERE object_id=?', (obj['id'],)).fetchone()
                size = measured_size(manifest, json.loads(runtime['bindings']) if runtime else {}, dict(shape) if shape else None)
                plan = manifest.get('plan', {})
                tags = item_tags(obj['name'], plan.get('title'), plan.get('category'))
                # The move itself: only a bag piece at this version leaves the bag, exactly once.
                if conn.execute("UPDATE objects SET state='gifted',x=NULL,z=NULL,version=version+1 WHERE id=? AND owner_id=? "
                                "AND state='inventory' AND version=?", (obj['id'], user['id'], body.version)).rowcount != 1:
                    fail('stale_object_version')
                conn.execute('DELETE FROM furniture_locations WHERE object_id=?', (obj['id'],))
                home_id = npc['home']
                resolve(conn, user['id'], home_id, now, settings)
                conn.execute('INSERT INTO npc_items(object_id,host_id,npc_id,home_id,state,size,tags,gifted) VALUES (?,?,?,?,?,?,?,?)',
                             (obj['id'], user['id'], npc_id, home_id, 'stored', json.dumps(size), json.dumps(tags), now))
                conn.execute('INSERT OR IGNORE INTO npc_homes(host_id,home_id,seed,updated) VALUES (?,?,?,?)',
                             (user['id'], home_id, settings.npc_seed or secrets.randbits(31), now))
                home = conn.execute('SELECT * FROM npc_homes WHERE host_id=? AND home_id=?', (user['id'], home_id)).fetchone()
                # The resident puts the gift up after a short random wait (sooner if a change is already due).
                rng = random.Random(f"{home['seed']}:{home['step']}")
                at = now + rng.uniform(settings.npc_place_min, settings.npc_place_max)
                if home['next_change_at'] is not None:
                    at = min(at, home['next_change_at'])
                conn.execute('UPDATE npc_homes SET step=step+1,next_change_at=?,updated=? WHERE host_id=? AND home_id=?',
                             (at, now, user['id'], home_id))
                score = sum(npc['taste'].get(t, 0) for t in tags)
                mood = 'love' if score >= 3 else 'like' if score >= 1 else 'thanks'
                day = homestead.local_day(now)
                before = conn.execute('SELECT last_day FROM npc_friendship WHERE host_id=? AND npc_id=?', (user['id'], npc_id)).fetchone()
                again = bool(before and before['last_day'] == day)
                gain = GAIN_AGAIN if again else GAIN[mood]
                conn.execute('INSERT INTO npc_friendship(host_id,npc_id,points,gifts,last_day) VALUES (?,?,?,1,?) '
                             'ON CONFLICT(host_id,npc_id) DO UPDATE SET points=points+excluded.points,gifts=gifts+1,last_day=excluded.last_day',
                             (user['id'], npc_id, gain, day))
                conn.execute('INSERT INTO npc_gifts VALUES (?,?,?,?,?,?,?)', (str(uuid.uuid4()), user['id'], npc_id, obj['id'], mood, gain, now))
                return {'npc': npc_id, 'object_id': obj['id'], 'name': obj['name'], 'mood': mood, 'again': again, 'gain': gain,
                        'personality': npc['personality'], 'home': home_id, 'home_version': home['version'],
                        'friendship': friendship(conn, user['id'], npc_id)}
            return mutate(request, body, 'npc_gift:' + npc_id, give)

        # The owner and visitors read a home the same way: the host is whoever's village the
        # caller is in (a visit), else the caller. ?version=N answers "unchanged" while N is current.
        @app.get('/v1/social/npc-homes/{home_id}')
        def home(home_id: str, request: Request, version: int = -1):
            if home_id not in SLOTS:
                fail('home_not_found', 404)
            with db.read() as conn:
                user = auth(conn, request)
                host = host_for(conn, user['id'])
                pending = due(conn, host, clock(), home_id)
            if pending:
                with db.transaction() as conn:
                    resolve(conn, host, home_id, clock(), settings)
            with db.read() as conn:
                row = conn.execute('SELECT version FROM npc_homes WHERE host_id=? AND home_id=?', (host, home_id)).fetchone()
                current = row['version'] if row else 0
                if version == current:
                    return {'home': home_id, 'version': current, 'unchanged': True}
                return {'home': home_id, 'version': current, 'host_id': host, 'items': placed_items(conn, host, home_id)}

    def versions_for(self, host_id):
        """Home versions for /v1/me, settling due changes first (a write only when one is due)."""
        with self.db.read() as conn:
            pending = due(conn, host_id, self.clock())
        if pending:
            with self.db.transaction() as conn:
                resolve_all(conn, host_id, self.clock(), self.settings)
        with self.db.read() as conn:
            return versions(conn, host_id)

    def versions_in(self, conn, host_id):
        """The same inside a caller's write transaction (the visit presence)."""
        resolve_all(conn, host_id, self.clock(), self.settings)
        return versions(conn, host_id)
