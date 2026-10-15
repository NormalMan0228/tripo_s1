"""Build mode: where a placed piece may be and how much room it takes.

A piece stands on the floor (as before), hangs on a room wall or from a room ceiling, or sits on top
of another placed piece (a cup on a table). Pieces pack by their measured size instead of the old
2x2 parcel: the box the residents' homes measure for a gift (npc_homes.py), its width x depth
turned by the piece's facing on the ground and its height above y. Two placed pieces of one room
(or the village) collide when both their footprints and their heights overlap by more than OVERLAP.

How a placed piece is held lives in object_mounts; no row means on the floor at y 0, so older saves
and released clients are unchanged. A piece on top names its support (parent): moving the support
carries everything on it along, and retrieving it (or giving it away) sends those pieces to the bag.
Object lists carry y, surface and parent; a top piece whose support no longer stands reads as a
floor piece at y 0.

Rooms mirror the client's interiors (ROOMS): origin at the room centre, back wall at z=-depth/2,
the front wall with the door at z=+depth/2 (no wall pieces there). A model faces +z at rotation 0;
rotation is whole degrees about +Y (Godot rotation_degrees.y).
"""
import json
import math
from fastapi import HTTPException
from . import npc_homes, room_budget
from .homestead import village_inside, village_reserved
from .provider import ProviderError

SCHEMA = '''
CREATE TABLE IF NOT EXISTS object_mounts (
 object_id TEXT PRIMARY KEY REFERENCES objects(id), surface TEXT NOT NULL DEFAULT 'floor',
 y REAL NOT NULL DEFAULT 0, parent_id TEXT, wall TEXT);
CREATE INDEX IF NOT EXISTS object_mounts_parent ON object_mounts(parent_id);
'''

# Interior width (x), depth (z) and ceiling height, metres.
ROOMS = {'home': (10.0, 10.0, 3.4), 'workshop': (10.5, 10.5, 4.2)}
ROOM_LIMIT = 30
OVERLAP = 0.02   # pieces may touch or graze; overlapping deeper than this collides
GAP = 0.02       # a hung piece's back stays this far off its wall or the ceiling
EDGE = 0.05      # clearance to the side walls and the ceiling
ON_TOP = 0.05    # a piece on top keeps its centre this far inside its support's edge
MAX_STACK = 3    # supports below the highest piece of a stack
WALL_DEPTH = 0.5
CEILING_MAX = (2.0, 1.5, 2.0)
# A ceiling piece reads as a hanging thing: tagged 'light' (npc_homes.item_tags) or its lower-cased
# name, design title or category contains one of these.
CEILING_WORDS = ('조명', '전등', '램프', '등불', '랜턴', '샹들리에', '펜던트', '모빌', '선풍기', '실링팬', '풍경', '행잉', '매달', '걸이', '별',
                 'lamp', 'light', 'lantern', 'chandelier', 'pendant', 'mobile', 'fan', 'chime', 'hanging')

# An object list's mount column (JSON text, NULL for a floor piece); listed()/public() decode it.
MOUNT_SQL = ("(SELECT json_object('surface',m.surface,'y',m.y,'parent',m.parent_id,'held',"
             "EXISTS(SELECT 1 FROM objects p WHERE p.id=m.parent_id AND p.state='placed')) "
             "FROM object_mounts m WHERE m.object_id={})")
PLACED_SQL = ("SELECT o.id,o.asset_id,o.name,o.version,o.x,o.z,o.rotation,COALESCE(l.room,'village') AS room,"
              "m.surface,m.y,m.parent_id FROM objects o LEFT JOIN furniture_locations l ON l.object_id=o.id "
              "LEFT JOIN object_mounts m ON m.object_id=o.id WHERE o.owner_id=? AND o.state='placed'")
TOP_CHILDREN = ("SELECT m.object_id FROM object_mounts m JOIN objects o ON o.id=m.object_id "
                "WHERE m.parent_id=? AND m.surface='top' AND o.state='placed'")


def fail(code, status=409):
    raise HTTPException(status, code)


def column(object_column):
    return MOUNT_SQL.format(object_column)


def public(text, state='placed'):
    """y, surface and parent of a listed object (floor at y 0 unless it is placed and mounted)."""
    value = json.loads(text) if text and state == 'placed' else None
    if not value or (value['surface'] == 'top' and not value['held']):
        return {'y': 0.0, 'surface': 'floor', 'parent': None}
    return {'y': float(value['y']), 'surface': value['surface'], 'parent': value['parent'] if value['surface'] == 'top' else None}


def listed(row):
    """An object list row (dict) with its 'mount' column turned into y, surface and parent."""
    row.update(public(row.pop('mount', None), row.get('state', 'placed')))
    return row


def measure(conn, assets, obj):
    """(box [w,h,d] in metres, texts) of a piece, measured the way a resident's gift is (npc_homes.py)."""
    studio = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
    shape = conn.execute('SELECT width,depth,height,scale FROM object_shape WHERE object_id=?', (obj['id'],)).fetchone()
    shape = dict(shape) if shape else None
    if studio:
        manifest = json.loads(studio['manifest'])
        runtime = conn.execute('SELECT bindings FROM studio_runtime WHERE object_id=?', (obj['id'],)).fetchone()
        plan = manifest.get('plan', {})
        texts = (obj['name'], plan.get('title'), plan.get('category'))
        return npc_homes.measured_size(manifest, json.loads(runtime['bindings']) if runtime else {}, shape), texts
    texts = (obj['name'],)
    return npc_homes.legacy_size(conn, assets, obj, npc_homes.item_tags(*texts), shape), texts


def object_size(conn, assets, obj, memo=None):
    """A piece's [w,h,d] in metres; memo (a dict) keeps each piece measured once per request."""
    memo = {} if memo is None else memo
    if obj['id'] not in memo:
        memo[obj['id']] = measure(conn, assets, obj)
    return memo[obj['id']][0]


def hangs(texts):
    low = ' '.join(str(t) for t in texts if t).casefold()
    return 'light' in npc_homes.item_tags(*texts) or any(word in low for word in CEILING_WORDS)


# Ground geometry. A footprint is (x, z, width axis, depth axis, half width, half depth); at facing r
# the model's +x points along (cos r, -sin r) and its +z along (sin r, cos r) on the (x, z) ground.
def axes(rotation):
    turn = math.radians(rotation)
    return (math.cos(turn), -math.sin(turn)), (math.sin(turn), math.cos(turn))


def footprint(x, z, size, rotation, shrink=0.0):
    u, v = axes(rotation)
    return (x, z, u, v, max(0.0, size[0] / 2 - shrink), max(0.0, size[2] / 2 - shrink))


def _reach(f, n):
    return f[4] * abs(f[2][0] * n[0] + f[2][1] * n[1]) + f[5] * abs(f[3][0] * n[0] + f[3][1] * n[1])


def footprints_meet(a, b):
    """Separating-axis test of two turned rectangles."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    return all(abs(dx * n[0] + dz * n[1]) < _reach(a, n) + _reach(b, n) for n in (a[2], a[3], b[2], b[3]))


def heights_meet(y1, h1, y2, h2):
    return min(y1 + h1, y2 + h2) - max(y1, y2) > OVERLAP


def inside(f, x, z, margin):
    dx, dz = x - f[0], z - f[1]
    return abs(dx * f[2][0] + dz * f[2][1]) <= f[4] - margin and abs(dx * f[3][0] + dz * f[3][1]) <= f[5] - margin


def half_extent(size, rotation):
    """Half the room-axis (x, z) extent of a turned footprint."""
    u, v = axes(rotation)
    return abs(u[0]) * size[0] / 2 + abs(v[0]) * size[2] / 2, abs(u[1]) * size[0] / 2 + abs(v[1]) * size[2] / 2


def turned(dx, dz, degrees):
    """A ground offset turned by degrees about +Y."""
    turn = math.radians(degrees)
    return dx * math.cos(turn) + dz * math.sin(turn), -dx * math.sin(turn) + dz * math.cos(turn)


def descendants(conn, object_id):
    """Every placed piece standing (directly or higher up) on this one."""
    found, todo = [], [object_id]
    while todo and len(found) < 500:
        for (child,) in conn.execute(TOP_CHILDREN, (todo.pop(),)).fetchall():
            if child != object_id and child not in found:
                found.append(child)
                todo.append(child)
    return found


def release_children(conn, object_id):
    """Sends everything standing on this piece to the bag; returns their ids."""
    ids = descendants(conn, object_id)
    for child in ids:
        conn.execute("UPDATE objects SET state='inventory',x=NULL,z=NULL,version=version+1 WHERE id=? AND state='placed'", (child,))
        conn.execute('DELETE FROM object_mounts WHERE object_id=?', (child,))
    return ids


def retrieve(conn, object_id):
    """The piece leaves its spot (to the bag, a resident...): no mount, nothing left on it."""
    ids = release_children(conn, object_id)
    conn.execute('DELETE FROM object_mounts WHERE object_id=?', (object_id,))
    return ids


def mount(conn, object_id, surface, y=0.0, parent=None, wall=None):
    if surface == 'floor':
        conn.execute('DELETE FROM object_mounts WHERE object_id=?', (object_id,))
    else:
        conn.execute('INSERT INTO object_mounts VALUES (?,?,?,?,?) ON CONFLICT(object_id) DO UPDATE SET '
                     'surface=excluded.surface,y=excluded.y,parent_id=excluded.parent_id,wall=excluded.wall',
                     (object_id, surface, y, parent, wall))


class Build:
    """One request's view of an owner's placed pieces: each measured once, supports resolved."""

    def __init__(self, conn, assets, owner_id):
        self.conn, self.assets, self.memo = conn, assets, {}
        self.placed = {r['id']: dict(r) for r in conn.execute(PLACED_SQL, (owner_id,)).fetchall()}
        for p in self.placed.values():
            p['y'] = float(p['y'] or 0)
            p['surface'] = p['surface'] or 'floor'
            if p['surface'] != 'top' or p['parent_id'] not in self.placed:
                p['parent_id'] = None
            if p['surface'] == 'top' and not p['parent_id']:
                p.update(surface='floor', y=0.0)

    def size(self, obj):
        return object_size(self.conn, self.assets, obj, self.memo)

    def texts(self, obj):
        self.size(obj)
        return self.memo[obj['id']][1]

    def children(self, object_id):
        return [p['id'] for p in self.placed.values() if p['parent_id'] == object_id]

    def tree(self, object_id):
        found, todo = [], [object_id]
        while todo:
            for child in self.children(todo.pop()):
                if child != object_id and child not in found:
                    found.append(child)
                    todo.append(child)
        return found

    def supports(self, object_id):
        chain, here = [], self.placed.get(object_id)
        while here and here['parent_id'] and len(chain) < 16:
            chain.append(here['parent_id'])
            here = self.placed.get(here['parent_id'])
        return chain

    def height(self, object_id):
        """Levels of pieces stacked on this one (0: nothing on it)."""
        tree = self.tree(object_id)
        return max((len(self.supports(c)) - len(self.supports(object_id)) for c in tree), default=0)

    def collides(self, room, x, z, y, rotation, size, skip):
        mine = footprint(x, z, size, rotation, OVERLAP / 2)
        for p in self.placed.values():
            if p['room'] != room or p['id'] in skip or p['x'] is None or p['z'] is None:
                continue
            other = self.size(p)
            if heights_meet(y, size[1], p['y'], other[1]) and footprints_meet(mine, footprint(p['x'], p['z'], other, p['rotation'] or 0, OVERLAP / 2)):
                return True
        return False


def overlaps(conn, assets, owner_id, room, obj, x, z, rotation):
    """A floor piece at (x, z) would collide with a placed piece (the legacy village route)."""
    build = Build(conn, assets, owner_id)
    return build.collides(room, x, z, 0.0, rotation, build.size(obj), {obj['id']})


def floor_rules(body):
    if body.room == 'village':
        if not village_inside(body.x, body.z):
            fail('outside_room')
    elif abs(body.x) > 4 or abs(body.z) > 4:
        fail('outside_room')
    if body.room != 'village' and abs(body.x) < 1.5 and body.z > 2.5:
        fail('door_area_reserved')
    if body.room == 'workshop' and body.x < -1.8 and body.z < -1.5:
        fail('workbench_area_reserved')
    if body.room == 'village' and village_reserved(body.x, body.z):
        fail('reserved_area')


def clamp(value, reach):
    if reach < 0:
        fail('outside_room')
    return round(max(-reach, min(reach, value)), 3)


def on_wall(body, size, room):
    """(x, z, rotation): the piece's back against the chosen wall, slid along it to stay inside."""
    width, depth, ceiling = room
    w, h, d = size
    if d > WALL_DEPTH or d * 2 > max(w, h):
        fail('not_wall_piece')
    if body.y + h > ceiling - EDGE:
        fail('wall_too_tall')
    if body.wall == 'back':
        return clamp(body.x, width / 2 - EDGE - w / 2), round(-depth / 2 + d / 2 + GAP, 3), 0
    side = -1 if body.wall == 'left' else 1
    return round(side * (width / 2 - d / 2 - GAP), 3), clamp(body.z, depth / 2 - EDGE - w / 2), 90 if side < 0 else 270


def on_ceiling(build, obj, body, size, room):
    """The piece's height below the ceiling, when it may hang there at (x, z)."""
    width, depth, ceiling = room
    if any(v > most for v, most in zip(size, CEILING_MAX)) or not hangs(build.texts(obj)):
        fail('not_ceiling_piece')
    rx, rz = half_extent(size, body.rotation)
    if abs(body.x) + rx > width / 2 - EDGE or abs(body.z) + rz > depth / 2 - EDGE:
        fail('outside_room')
    return round(ceiling - size[1] - GAP, 3)


def on_top(build, obj, body, size, tree):
    """The support the piece sits on, when it fits there."""
    parent = str(body.parent)
    if parent == obj['id'] or parent in tree:
        fail('stack_cycle')
    p = build.placed.get(parent)
    if not p or p['room'] != body.room or p['surface'] not in ('floor', 'top'):
        fail('not_on_parent')
    if len(build.supports(parent)) + 1 + build.height(obj['id']) > MAX_STACK:
        fail('stack_too_high')
    below = build.size(p)
    if size[0] * size[2] > below[0] * below[2]:
        fail('too_big_to_stack')
    if not inside(footprint(p['x'], p['z'], below, p['rotation'] or 0), body.x, body.z, ON_TOP):
        fail('not_on_parent')
    if not p['y'] + ON_TOP - 1e-6 <= body.y <= p['y'] + below[1] + OVERLAP + 1e-6:
        fail('not_on_parent')
    if body.room == 'village':
        if not village_inside(body.x, body.z):
            fail('outside_room')
    elif abs(body.x) > ROOMS[body.room][0] / 2 - EDGE or abs(body.z) > ROOMS[body.room][1] / 2 - EDGE:
        fail('outside_room')
    return p


def budget(conn, assets, owner_id, room, obj, others):
    """room_budget.check for the piece plus the pieces it brings in from another room."""
    try:
        value = room_budget.check(conn, assets, owner_id, room, obj['id'], obj['asset_id'])
        if others:
            used = dict(value['used'])
            for asset_id in others:
                for key, amount in room_budget.measured(conn, assets, asset_id).items():
                    used[key] += amount
            if any(used[key] > limit for key, limit in room_budget.LIMITS.items()):
                raise ProviderError('room_render_budget_exceeded')
    except ProviderError as error:
        fail(error.code, 409 if error.code == 'room_render_budget_exceeded' else 503)


def place(conn, assets, owner_id, obj, body):
    """Checks and stores a placement (asset_studio Placement); returns the reply's pose fields."""
    build = Build(conn, assets, owner_id)
    oid, room = obj['id'], ROOMS.get(body.room)
    size = build.size(obj)
    old = build.placed.get(oid)
    tree = build.tree(oid) if old else []
    x, z, y, rotation, parent, wall = body.x, body.z, 0.0, body.rotation, None, None
    if body.surface in ('wall', 'ceiling') and not room:
        fail('surface_not_here')
    if body.surface == 'floor':
        floor_rules(body)
    elif body.surface == 'wall':
        x, z, rotation = on_wall(body, size, room)
        y, wall = body.y, body.wall
    elif body.surface == 'ceiling':
        y = on_ceiling(build, obj, body, size, room)
    else:
        parent, y = on_top(build, obj, body, size, tree)['id'], body.y
    # A hung piece holds nothing: whatever stood on it goes to the bag.
    carried = tree if body.surface in ('floor', 'top') else []
    others = [p for p in build.placed.values() if p['room'] == body.room and p['id'] != oid and p['id'] not in tree]
    if len(others) + 1 + len(carried) > ROOM_LIMIT:
        fail('room_full')
    skip = {oid, *tree, *([parent] + build.supports(parent) if parent else [])}
    if build.collides(body.room, x, z, y, rotation, size, skip):
        fail('placement_overlap')
    moves = []
    for child_id in carried:
        child = build.placed[child_id]
        dx, dz = turned(child['x'] - old['x'], child['z'] - old['z'], rotation - (old['rotation'] or 0))
        pose = {'id': child_id, 'x': round(x + dx, 3), 'z': round(z + dz, 3), 'y': round(child['y'] + y - old['y'], 3),
                'rotation': ((child['rotation'] or 0) + rotation - (old['rotation'] or 0)) % 360, 'room': body.room,
                'version': child['version'] + 1}
        if build.collides(body.room, pose['x'], pose['z'], pose['y'], pose['rotation'], build.size(child), skip):
            fail('placement_overlap')
        moves.append(pose)
    budget(conn, assets, owner_id, body.room, obj, [build.placed[c]['asset_id'] for c in carried if build.placed[c]['room'] != body.room])
    conn.execute("UPDATE objects SET state='placed',x=?,z=?,rotation=?,version=version+1 WHERE id=?", (x, z, rotation, oid))
    conn.execute('INSERT INTO furniture_locations VALUES (?,?) ON CONFLICT(object_id) DO UPDATE SET room=excluded.room', (oid, body.room))
    mount(conn, oid, body.surface, y, parent, wall)
    for pose in moves:
        conn.execute('UPDATE objects SET x=?,z=?,rotation=?,version=version+1 WHERE id=?', (pose['x'], pose['z'], pose['rotation'], pose['id']))
        conn.execute('INSERT INTO furniture_locations VALUES (?,?) ON CONFLICT(object_id) DO UPDATE SET room=excluded.room', (pose['id'], body.room))
        conn.execute('UPDATE object_mounts SET y=? WHERE object_id=?', (pose['y'], pose['id']))
    retrieved = release_children(conn, oid) if not carried and tree else []
    return {'x': x, 'z': z, 'y': y, 'rotation': rotation, 'surface': body.surface, 'parent': parent,
            'carried': moves, 'retrieved': retrieved}
