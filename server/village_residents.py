"""Per-player residency. Mutations run in the caller's write transaction."""
import json
import uuid

from fastapi import HTTPException, Request

from . import npc_homes

MOVERS = {'shopkeeper': {'name': '단비', 'plot': 'danbi_plot',
                         'home': 'danbi_house', 'old_home': '13_shop'}}
# Map centre (-23.5, 9) minus Town.SPAWN (-33, 37).
PLOTS = {'danbi_plot': {'x': 9.5, 'z': -28.0, 'radius': 5.0}}
RESCUE_EVENT = 'danbi_rescued'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS village_roster (
 host_id TEXT PRIMARY KEY REFERENCES users(id), version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS village_residents (
 host_id TEXT NOT NULL REFERENCES users(id), npc_id TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('away','arriving','home','leaving')),
 home TEXT NOT NULL, plot TEXT NOT NULL, since REAL NOT NULL, due_at REAL,
 moves INTEGER NOT NULL DEFAULT 0, legacy INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(host_id,npc_id), UNIQUE(host_id,plot));
CREATE INDEX IF NOT EXISTS village_residents_due ON village_residents(host_id,due_at);
CREATE TABLE IF NOT EXISTS village_news (
 id TEXT PRIMARY KEY, host_id TEXT NOT NULL REFERENCES users(id), npc_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('arriving','moved_in','returned','leaving','moved_out')),
 at REAL NOT NULL, reason TEXT NOT NULL, letter_id TEXT REFERENCES npc_letters(id),
 returned_to_bag TEXT NOT NULL DEFAULT '[]');
CREATE INDEX IF NOT EXISTS village_news_host ON village_news(host_id,at);
CREATE TABLE IF NOT EXISTS npc_conversation_memory (
 host_id TEXT NOT NULL REFERENCES users(id), npc_id TEXT NOT NULL,
 first_met REAL NOT NULL, last_met REAL NOT NULL,
 PRIMARY KEY(host_id,npc_id));
'''


def remember(conn, host, npc, now):
    conn.execute('INSERT INTO npc_conversation_memory VALUES (?,?,?,?) '
                 'ON CONFLICT(host_id,npc_id) DO UPDATE SET last_met=MAX(last_met,excluded.last_met)',
                 (host, npc, now, now))


def migrate_memory(conn, host):
    chapter = conn.execute('SELECT greeted,started,updated FROM story_progress WHERE user_id=?', (host,)).fetchone()
    if chapter:
        for npc in json.loads(chapter['greeted']):
            conn.execute('INSERT OR IGNORE INTO npc_conversation_memory VALUES (?,?,?,?)',
                         (host, npc, chapter['started'], chapter['updated']))


def initial_state(conn, host):
    chapter = conn.execute('SELECT step FROM story_progress WHERE user_id=?', (host,)).fetchone()
    rescued = conn.execute('SELECT 1 FROM story_events WHERE user_id=? AND event=?',
                           (host, RESCUE_EVENT)).fetchone()
    return 'home' if not rescued and (not chapter or chapter['step'] == 'done') else 'away'


def absent(conn, host, settings):
    if not settings.resident_moves:
        return set()
    rows = {r['npc_id']: r['state'] for r in conn.execute(
        'SELECT npc_id,state FROM village_residents WHERE host_id=?', (host,))}
    fallback = initial_state(conn, host) if any(n not in rows for n in MOVERS) else 'away'
    return {npc for npc in MOVERS if rows.get(npc, fallback) in ('away', 'arriving')}


def plot_reserved(x, z):
    if any((x - p['x']) ** 2 + (z - p['z']) ** 2 <= p['radius'] ** 2 for p in PLOTS.values()):
        return 'plot_reserved'
    return None


def _bump(conn, host):
    conn.execute('UPDATE village_roster SET version=version+1 WHERE host_id=?', (host,))


def _news(conn, host, npc, kind, at, reason, letter=None, returned=()):
    conn.execute('INSERT INTO village_news VALUES (?,?,?,?,?,?,?,?)',
                 (str(uuid.uuid4()), host, npc, kind, at, reason, letter, json.dumps(list(returned))))


def ensure(conn, host, now, settings):
    if not settings.resident_moves:
        return
    conn.execute('INSERT OR IGNORE INTO village_roster(host_id) VALUES (?)', (host,))
    for npc, spec in MOVERS.items():
        if conn.execute('SELECT 1 FROM village_residents WHERE host_id=? AND npc_id=?', (host, npc)).fetchone():
            continue
        state = initial_state(conn, host)
        conn.execute('INSERT INTO village_residents(host_id,npc_id,state,home,plot,since,legacy) VALUES (?,?,?,?,?,?,?)',
                     (host, npc, state, spec['home'], spec['plot'], now, int(state == 'home')))
        migrate_memory(conn, host)
        if state == 'home':
            _clear_plot(conn, host, spec['plot'])
            _items(conn, host, npc, spec['home'], now, settings, True)


def _clear_plot(conn, host, plot):
    p = PLOTS[plot]
    returned = []
    for row in conn.execute("SELECT o.id,o.x,o.z FROM objects o LEFT JOIN furniture_locations f ON f.object_id=o.id "
                            "WHERE o.owner_id=? AND o.state='placed' AND COALESCE(f.room,'village')='village'", (host,)).fetchall():
        if row['x'] is not None and row['z'] is not None and (row['x'] - p['x']) ** 2 + (row['z'] - p['z']) ** 2 <= p['radius'] ** 2:
            conn.execute("UPDATE objects SET state='inventory',x=NULL,z=NULL,version=version+1 WHERE id=?", (row['id'],))
            conn.execute('DELETE FROM furniture_locations WHERE object_id=?', (row['id'],))
            returned.append(row['id'])
    return returned


def _items(conn, host, npc, home, now, settings, returning):
    homes = {r[0] for r in conn.execute('SELECT DISTINCT home_id FROM npc_items WHERE host_id=? AND npc_id=?', (host, npc))}
    conn.execute("UPDATE npc_items SET state='stored',slot=NULL,fresh=1,home_id=? WHERE host_id=? AND npc_id=?",
                 (home, host, npc))
    for old in homes | {home}:
        conn.execute('UPDATE npc_homes SET version=version+1,updated=? WHERE host_id=? AND home_id=?', (now, host, old))
        if not conn.execute('SELECT 1 FROM npc_items WHERE host_id=? AND home_id=? AND npc_id!=?', (host, old, npc)).fetchone():
            conn.execute('UPDATE npc_homes SET next_change_at=NULL WHERE host_id=? AND home_id=?', (host, old))
    # Keep gifts stored until the map session supplies the new interior's slots.
    if returning and homes and npc_homes.SLOTS.get(home):
        conn.execute('INSERT OR IGNORE INTO npc_homes(host_id,home_id,seed,updated) VALUES (?,?,?,?)',
                     (host, home, settings.npc_seed or 1, now))
        conn.execute('UPDATE npc_homes SET next_change_at=? WHERE host_id=? AND home_id=?',
                     (now + settings.npc_place_min, host, home))


def settle(conn, host, now, settings):
    if not settings.resident_moves:
        return
    ensure(conn, host, now, settings)
    for row in conn.execute('SELECT * FROM village_residents WHERE host_id=? AND due_at<=? ORDER BY due_at,npc_id', (host, now)).fetchall():
        entering = row['state'] == 'arriving'
        at, npc = row['due_at'], row['npc_id']
        kind = ('returned' if row['moves'] or row['legacy'] else 'moved_in') if entering else 'moved_out'
        returned = _clear_plot(conn, host, row['plot']) if entering else []
        _items(conn, host, npc, row['home'], at, settings, entering)
        level = npc_homes.MOVE_LETTER_LEVEL + 2 * row['moves'] + (0 if entering else 1)
        letter = str(uuid.uuid4())
        conn.execute('INSERT INTO npc_letters(id,host_id,npc_id,level,created) VALUES (?,?,?,?,?)',
                     (letter, host, npc, level, at))
        _news(conn, host, npc, kind, at, 'settled', letter, returned)
        conn.execute('UPDATE village_residents SET state=?,since=?,due_at=NULL,moves=moves+? WHERE host_id=? AND npc_id=?',
                     ('home' if entering else 'away', at, int(not entering), host, npc))
        _bump(conn, host)


def move_in(conn, host, npc, now, settings, *, entering=True, reason='operator'):
    if npc not in MOVERS:
        raise HTTPException(404, 'unknown_resident')
    if not settings.resident_moves:
        raise HTTPException(409, 'resident_moves_disabled')
    settle(conn, host, now, settings)
    row = conn.execute('SELECT state FROM village_residents WHERE host_id=? AND npc_id=?', (host, npc)).fetchone()
    if row['state'] != ('away' if entering else 'home'):
        return False
    state = 'arriving' if entering else 'leaving'
    delay = settings.resident_arrive_seconds if entering else settings.resident_leave_seconds
    conn.execute('UPDATE village_residents SET state=?,since=?,due_at=? WHERE host_id=? AND npc_id=?',
                 (state, now, now + delay, host, npc))
    _news(conn, host, npc, state, now, reason)
    _bump(conn, host)
    settle(conn, host, now, settings)
    return True


def arrive(conn, host, npc, now, settings, reason='operator'):
    return move_in(conn, host, npc, now, settings, reason=reason)


def leave(conn, host, npc, now, settings, reason='operator'):
    return move_in(conn, host, npc, now, settings, entering=False, reason=reason)


def sync(conn, host, now, settings):
    """Apply a deferred rescue once, then finish any move that is due."""
    if not settings.resident_moves:
        return
    ensure(conn, host, now, settings)
    rescued = conn.execute('SELECT 1 FROM story_events WHERE user_id=? AND event=?', (host, RESCUE_EVENT)).fetchone()
    row = conn.execute("SELECT state,moves,legacy FROM village_residents WHERE host_id=? AND npc_id='shopkeeper'", (host,)).fetchone()
    if rescued and row['state'] == 'away' and not row['moves'] and not row['legacy']:
        arrive(conn, host, 'shopkeeper', now, settings, reason=RESCUE_EVENT)
    settle(conn, host, now, settings)


def brief(conn, host, now, settings):
    enabled = settings.resident_moves
    roster = conn.execute('SELECT version FROM village_roster WHERE host_id=?', (host,)).fetchone()
    residents, plots = [], {plot: 'empty' for plot in PLOTS}
    for npc, spec in MOVERS.items():
        row = conn.execute('SELECT * FROM village_residents WHERE host_id=? AND npc_id=?', (host, npc)).fetchone() if enabled else None
        bond = npc_homes.friendship(conn, host, npc, settings.npc_levels)
        memory = conn.execute('SELECT first_met,last_met FROM npc_conversation_memory WHERE host_id=? AND npc_id=?', (host, npc)).fetchone()
        state = row['state'] if row else 'home'
        residents.append({'npc': npc, 'state': state, 'home': row['home'] if row else spec['old_home'],
                          'plot': row['plot'] if row else spec['plot'], 'since': row['since'] if row else None,
                          'due_at': row['due_at'] if row else None, 'moves': row['moves'] if row else 0,
                          'legacy': bool(row and row['legacy']), 'back': bool(row and row['moves'] and state in ('home', 'leaving')),
                          'hearts': bond['level'], 'friendship': bond,
                          'memory': {'met': bool(memory or bond['gifts'] or bond['points']),
                                     'first_met': memory['first_met'] if memory else None,
                                     'last_met': memory['last_met'] if memory else None}})
        if row:
            plots[row['plot']] = 'built' if state in ('home', 'leaving') else 'building' if state == 'arriving' else 'empty'
    news = []
    if enabled:
        for r in conn.execute('SELECT * FROM village_news WHERE host_id=? AND at>=? ORDER BY at DESC,rowid DESC LIMIT 5', (host, now - 7 * 86400)):
            news.append({'id': r['id'], 'npc': r['npc_id'], 'kind': r['kind'], 'at': r['at'],
                         'letter_id': r['letter_id'], 'returned_to_bag': json.loads(r['returned_to_bag'])})
    return {'enabled': enabled, 'host_id': host, 'version': roster['version'] if enabled and roster else 0,
            'residents': residents, 'plots': plots, 'news': news}


class VillageResidents:
    def __init__(self, app, db, settings, clock, auth, host_for):
        self.db, self.settings, self.clock = db, settings, clock
        with db.read() as conn:
            conn.executescript(SCHEMA)

        @app.get('/v1/village/residency')
        @app.get('/v1/residents')
        def read(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                host = host_for(conn, user['id'])
            return self.residents_for(host)

    def sync_in(self, conn, host, now):
        sync(conn, host, now, self.settings)

    def residents_for(self, host):
        now = self.clock()
        if self.settings.resident_moves:
            with self.db.read() as conn:
                rows = conn.execute('SELECT * FROM village_residents WHERE host_id=?', (host,)).fetchall()
                pending = len(rows) < len(MOVERS) or any(r['due_at'] is not None and r['due_at'] <= now for r in rows)
                if not pending:
                    pending = any(r['state'] == 'away' and not r['moves'] and not r['legacy'] for r in rows) and conn.execute(
                        'SELECT 1 FROM story_events WHERE user_id=? AND event=?', (host, RESCUE_EVENT)).fetchone() is not None
            if pending:
                with self.db.transaction() as conn:
                    self.sync_in(conn, host, now)
        with self.db.read() as conn:
            return brief(conn, host, now, self.settings)
