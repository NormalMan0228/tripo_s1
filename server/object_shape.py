"""Player shape edits of their objects (the client's 모양 바꾸기 panel).

Width, depth and height stretch and an overall size, each a whole percent from 50 to 200,
plus a left-right mirror. One row per object; its version only grows (a reset keeps the
row at the defaults), so clients can tell edits apart. Owners edit through
POST /v1/objects/{id}/shape; every object list (/v1/me, /v1/studio, the visitor and
home-visit spaces) carries the current shape, or null for an object never reshaped.
The client applies it to the model's scaled frame, so the object keeps its spot, turn
and footing; painted textures follow the surface (UV) and stay lined up.
"""
import json
from fastapi import HTTPException, Request
from pydantic import Field
from .models import Mutation

LOWEST = 50
HIGHEST = 200
DEFAULT = {'width': 100, 'depth': 100, 'height': 100, 'scale': 100, 'mirror': False}

SCHEMA = f'''CREATE TABLE IF NOT EXISTS object_shape (
 object_id TEXT PRIMARY KEY REFERENCES objects(id),
 width INTEGER NOT NULL DEFAULT 100 CHECK(width BETWEEN {LOWEST} AND {HIGHEST}),
 depth INTEGER NOT NULL DEFAULT 100 CHECK(depth BETWEEN {LOWEST} AND {HIGHEST}),
 height INTEGER NOT NULL DEFAULT 100 CHECK(height BETWEEN {LOWEST} AND {HIGHEST}),
 scale INTEGER NOT NULL DEFAULT 100 CHECK(scale BETWEEN {LOWEST} AND {HIGHEST}),
 mirror INTEGER NOT NULL DEFAULT 0 CHECK(mirror IN (0,1)),
 version INTEGER NOT NULL DEFAULT 1 CHECK(version>=1), updated REAL NOT NULL)'''

# The shape an object list shows (JSON text, NULL for an object never reshaped); listed() decodes it.
SHAPE_SQL = ("(SELECT json_object('width',width,'depth',depth,'height',height,'scale',scale,'mirror',mirror,'version',version) "
             "FROM object_shape WHERE object_shape.object_id={})")


def column(object_column):
    return SHAPE_SQL.format(object_column)


def public(text):
    if not text:
        return None
    value = json.loads(text)
    value['mirror'] = bool(value['mirror'])
    return value


def listed(row):
    """An object list row (dict) with its 'shape' column decoded."""
    row['shape'] = public(row.get('shape'))
    return row


def percent():
    return Field(default=100, ge=LOWEST, le=HIGHEST)


class ShapeEdit(Mutation):
    width: int = percent()
    depth: int = percent()
    height: int = percent()
    scale: int = percent()
    mirror: bool = False
    # Back to the made shape (the other values are ignored).
    reset: bool = False
    # The shape version the edit was made from (optional): a newer one refuses it.
    version: int | None = Field(default=None, ge=0, le=2147483647)


def fail(code, status=409):
    raise HTTPException(status, code)


class ObjectShape:
    def __init__(self, app, db, clock, mutate, own):
        with db.transaction() as conn:
            conn.execute(SCHEMA)

        @app.post('/v1/objects/{object_id}/shape')
        def edit(object_id: str, body: ShapeEdit, request: Request):
            def save(conn, user):
                row = own(conn, user['id'], object_id)
                if row['state'] == 'listed':
                    fail('object_is_listed')
                previous = conn.execute('SELECT version FROM object_shape WHERE object_id=?', (object_id,)).fetchone()
                current = previous['version'] if previous else 0
                if body.version is not None and body.version != current:
                    fail('stale_shape_version')
                value = dict(DEFAULT) if body.reset else {k: getattr(body, k) for k in DEFAULT}
                value['version'] = current + 1
                conn.execute('INSERT INTO object_shape(object_id,width,depth,height,scale,mirror,version,updated) VALUES (?,?,?,?,?,?,?,?) '
                             'ON CONFLICT(object_id) DO UPDATE SET width=excluded.width,depth=excluded.depth,height=excluded.height,'
                             'scale=excluded.scale,mirror=excluded.mirror,version=excluded.version,updated=excluded.updated',
                             (object_id, value['width'], value['depth'], value['height'], value['scale'], int(value['mirror']),
                              value['version'], clock()))
                return value
            return mutate(request, body, 'shape:' + object_id, save)
