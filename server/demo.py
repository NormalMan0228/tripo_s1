"""Demo accounts for presentations (admin_cli demo): one command readies an account for the
judges' run, so nothing in the first minutes can stall on an empty wallet or a missing piece.

  prep:  the opening chapter back at the letter on the desk (story.reset, nothing deleted), the
         starseed balance topped up to a floor (ledger 'demo_topup', never lowered), and
         optionally copies of finished pieces from another account into the bag (a nicer chair to
         hand 모카 if a live craft runs late, a clock or a lamp to show their interactions).
  list:  one account's pieces (id, name, state) to pick copies from.

A copy is a new object of the same model (assets are shared, never duplicated): its interaction
program, collision shape, runtime state and paint come along, and the creator stays the original
maker. The source keeps its piece. Copies land in the bag ('inventory').
"""
import shutil
import uuid
from pathlib import Path

from . import object_paint, story

# Per-object rows that travel with a copy (object_id is each table's primary key).
COPIED_TABLES = ('object_interactions', 'object_shape', 'studio_runtime', 'object_paint')


def tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def pieces(conn, user_id):
    """An account's pieces, newest first (gifted ones belong to a resident now)."""
    return [dict(r) for r in conn.execute(
        "SELECT id,name,state,created FROM objects WHERE owner_id=? AND state!='gifted' ORDER BY created DESC,rowid DESC", (user_id,))]


def pick(conn, user_id, wanted):
    """Pieces of an account by id (or its first 8+ characters) or by a word in the name; the newest
    match per word. Unknown words raise ValueError so a typo never copies the wrong thing."""
    own = pieces(conn, user_id)
    chosen = []
    for word in wanted:
        match = next((p for p in own if len(word) >= 8 and p['id'].startswith(word)), None) or \
            next((p for p in own if word in p['name']), None)
        if not match:
            raise ValueError('no piece matches %r' % word)
        if match['id'] not in [c['id'] for c in chosen]:
            chosen.append(match)
    return chosen


def copy_piece(conn, assets, object_id, owner_id, now):
    """A copy of one piece in owner_id's bag; returns the new id."""
    row = conn.execute('SELECT * FROM objects WHERE id=?', (object_id,)).fetchone()
    new_id = str(uuid.uuid4())
    conn.execute('INSERT INTO objects(id,owner_id,creator_id,asset_id,name,color,version,state,x,z,rotation,created) '
                 "VALUES (?,?,?,?,?,?,1,'inventory',NULL,NULL,0,?)",
                 (new_id, owner_id, row['creator_id'], row['asset_id'], row['name'], row['color'], now))
    present = tables(conn)
    for table in COPIED_TABLES:
        if table not in present:
            continue
        for extra in conn.execute('SELECT * FROM %s WHERE object_id=?' % table, (object_id,)).fetchall():
            values = dict(extra)
            values['object_id'] = new_id
            conn.execute('INSERT INTO %s (%s) VALUES (%s)' % (table, ','.join(values), ','.join('?' * len(values))), tuple(values.values()))
            if table == 'object_paint' and values.get('sha256'):
                source = object_paint.file_for(assets, object_id, values['sha256'])
                if source.is_file():
                    shutil.copyfile(source, object_paint.file_for(assets, new_id, values['sha256']))
    return new_id


def prep(conn, data_dir, user_id, now, stars=0, source_id=None, wanted=()):
    """Ready one account for a demo run (the caller holds a write transaction)."""
    chapter = story.reset(conn, user_id, now)
    balance = conn.execute('SELECT shards FROM users WHERE id=?', (user_id,)).fetchone()[0]
    topped = max(0, stars - balance)
    if topped:
        from .economy import change_shards
        change_shards(conn, user_id, topped, 'demo_topup', str(uuid.uuid4()), now)
    copied = []
    if source_id and wanted:
        assets = Path(data_dir) / 'assets'
        for piece in pick(conn, source_id, wanted):
            copied.append({'id': copy_piece(conn, assets, piece['id'], user_id, now), 'name': piece['name'], 'from': piece['id']})
    return {'story': chapter, 'shards': balance + topped, 'topped_up': topped, 'copied': copied}
