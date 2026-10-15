"""Friends, blocks, privacy, reports, the people roster and knock/drop-in visits
(docs/design/SOCIAL_API.md). Module functions are shared with multiplayer.py and chat.py; the
Friends class adds the routes. Every mutation goes through mutate() (request_id idempotency).

rev (social_prefs.rev) grows on every friend, request, block, knock or privacy change that touches
a player; presence replies carry it as social.v, so clients refetch /v1/social/people only then
(or every few seconds while the social window is open).
"""
import json
import math
import threading
import uuid
from typing import Literal
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field, model_validator
from .models import Strict, Mutation, Avatar

SCHEMA = '''
CREATE TABLE IF NOT EXISTS social_friends (
 user_id TEXT NOT NULL REFERENCES users(id), friend_id TEXT NOT NULL REFERENCES users(id),
 created REAL NOT NULL, PRIMARY KEY(user_id,friend_id));
CREATE TABLE IF NOT EXISTS social_requests (
 id TEXT PRIMARY KEY, from_id TEXT NOT NULL REFERENCES users(id), to_id TEXT NOT NULL REFERENCES users(id),
 state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS social_requests_open ON social_requests(from_id,to_id) WHERE state IN ('pending','suppressed');
CREATE INDEX IF NOT EXISTS social_requests_to ON social_requests(to_id,state);
CREATE INDEX IF NOT EXISTS social_requests_from ON social_requests(from_id,created);
CREATE INDEX IF NOT EXISTS social_requests_updated ON social_requests(updated);
CREATE TABLE IF NOT EXISTS social_blocks (
 user_id TEXT NOT NULL REFERENCES users(id), blocked_id TEXT NOT NULL REFERENCES users(id),
 created REAL NOT NULL, PRIMARY KEY(user_id,blocked_id));
CREATE INDEX IF NOT EXISTS social_blocks_reverse ON social_blocks(blocked_id);
CREATE TABLE IF NOT EXISTS social_prefs (
 user_id TEXT PRIMARY KEY REFERENCES users(id),
 appear_offline INTEGER NOT NULL DEFAULT 0, roster TEXT NOT NULL DEFAULT 'everyone',
 requests TEXT NOT NULL DEFAULT 'everyone', drop_in TEXT NOT NULL DEFAULT 'off',
 rev INTEGER NOT NULL DEFAULT 0, last_seen REAL, chat_muted_until REAL);
CREATE TABLE IF NOT EXISTS social_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, to_id TEXT NOT NULL, message_id INTEGER,
 text TEXT, context TEXT, reason TEXT NOT NULL, note TEXT, state TEXT NOT NULL DEFAULT 'open',
 created REAL NOT NULL, updated REAL);
CREATE INDEX IF NOT EXISTS social_reports_state ON social_reports(state,created);
CREATE INDEX IF NOT EXISTS social_reports_user ON social_reports(user_id,created);
'''

ONLINE_SECONDS = 15          # seen this recently = online (village 4 Hz, rooms 1-3 s, survival 2 s)
ROSTER_SECONDS = 3           # the shared online list is rebuilt at most this often
ROSTER_LIMIT = 200           # online entries per reply (online_count is the full number)
FRIEND_LIMIT = 100
BLOCK_LIMIT = 200
REQUESTS_PER_DAY = 20
PENDING_LIMIT = 20
DECLINE_COOLDOWN_SECONDS = 86400
REQUEST_EXPIRY_SECONDS = 30 * 86400
REPORTS_PER_DAY = 10
KNOCK_SECONDS = 120
KNOCK_GAP_SECONDS = 60
KNOCKS_PENDING = 5
PEOPLE_PER_MINUTE = 60
GUEST_LIMIT = 2              # guests besides the host (multiplayer.py village_full)
DEFAULT_PREFS = {'appear_offline': False, 'roster': 'everyone', 'requests': 'everyone', 'drop_in': 'off'}
FEATURES = ['chat2', 'place', 'people', 'friends', 'visit', 'report']


def fail(code, status=409):
    raise HTTPException(status, code)


# --- shared helpers (multiplayer.py, chat.py) ------------------------------------------------
def ensure_schema(conn):
    conn.executescript(SCHEMA)


def prefs(conn, user_id):
    row = conn.execute('SELECT * FROM social_prefs WHERE user_id=?', (user_id,)).fetchone()
    if not row:
        return {**DEFAULT_PREFS, 'rev': 0, 'last_seen': None, 'chat_muted_until': None}
    return {'appear_offline': bool(row['appear_offline']), 'roster': row['roster'], 'requests': row['requests'],
            'drop_in': row['drop_in'], 'rev': row['rev'], 'last_seen': row['last_seen'], 'chat_muted_until': row['chat_muted_until']}


def bump(conn, *user_ids):
    for user_id in set(user_ids):
        conn.execute('INSERT INTO social_prefs(user_id,rev) VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET rev=rev+1', (user_id,))


def muted_until(conn, user_id):
    row = conn.execute('SELECT chat_muted_until FROM social_prefs WHERE user_id=?', (user_id,)).fetchone()
    return row[0] if row else None


def set_mute(conn, user_id, until):
    conn.execute('INSERT INTO social_prefs(user_id,chat_muted_until) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET chat_muted_until=excluded.chat_muted_until', (user_id, until))


def remember_seen(conn, user_id, seen):
    """last_seen for friends lists once the presence row is gone (logout, quit)."""
    conn.execute('INSERT INTO social_prefs(user_id,last_seen) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen', (user_id, seen))


def blocked_ids(conn, user_id):
    """Players this one blocked or was blocked by: never shown to each other anywhere."""
    return ({r[0] for r in conn.execute('SELECT blocked_id FROM social_blocks WHERE user_id=?', (user_id,))}
            | {r[0] for r in conn.execute('SELECT user_id FROM social_blocks WHERE blocked_id=?', (user_id,))})


def blocked_between(conn, a, b):
    return conn.execute('SELECT 1 FROM social_blocks WHERE (user_id=? AND blocked_id=?) OR (user_id=? AND blocked_id=?)', (a, b, b, a)).fetchone() is not None


def are_friends(conn, a, b):
    return conn.execute('SELECT 1 FROM social_friends WHERE user_id=? AND friend_id=?', (a, b)).fetchone() is not None


def friend_ids(conn, user_id):
    return [r[0] for r in conn.execute('SELECT friend_id FROM social_friends WHERE user_id=?', (user_id,))]


def visible_online(conn, user_id, now):
    row = conn.execute('SELECT p.seen,COALESCE(s.appear_offline,0) AS hidden FROM mp_presence p LEFT JOIN social_prefs s ON s.user_id=p.user_id WHERE p.user_id=?', (user_id,)).fetchone()
    return bool(row and now-row['seen'] < ONLINE_SECONDS and not row['hidden'])


def place_of(row):
    """village | home | workshop | room | expedition | away. Clients with the place feature say;
    older ones send only the scene (survival and the workshop both say 'away')."""
    if row['place']:
        return row['place']
    if row['scene'] in ('village', 'home'):
        return row['scene']
    return 'expedition' if row['expedition'] else 'away'


def where_of(row):
    place = place_of(row)
    where = {'place': place}
    if place in ('village', 'home'):
        where.update(host_id=row['host_id'], host_name=row['host_name'])
    if row['floor'] is not None:
        where['floor'] = row['floor']
    return where


def look(raw):
    try:
        return json.loads(raw) if raw else Avatar().model_dump()
    except ValueError:
        return Avatar().model_dump()


class Roster:
    """Everyone online, shared by every /people reply and presence social block, rebuilt at most
    every ROSTER_SECONDS. It lives in this process: the server runs one uvicorn worker
    (ops/compose.yaml --workers 1). More workers would each keep a copy that can differ by a few
    seconds; move it into SQLite before raising the worker count."""
    def __init__(self, clock):
        self.clock = clock
        self.lock = threading.Lock()
        self.built, self.rows, self.rebuilds = -math.inf, {}, 0

    def get(self, conn):
        now = self.clock()
        if now-self.built < ROSTER_SECONDS:
            return self.rows
        # One thread rebuilds; the others keep using the previous list meanwhile.
        if not self.lock.acquire(blocking=self.built == -math.inf):
            return self.rows
        try:
            if now-self.built >= ROSTER_SECONDS:
                rows = {}
                for r in conn.execute(
                        'SELECT p.user_id,p.host_id,p.scene,p.place,p.floor,p.seen,u.username,h.username AS host_name,'
                        'pr.avatar,COALESCE(pr.version,0) AS avatar_version,COALESCE(s.appear_offline,0) AS appear_offline,'
                        "COALESCE(s.roster,'everyone') AS roster,"
                        "CASE WHEN p.place IS NULL AND p.scene='away' THEN (EXISTS(SELECT 1 FROM runs WHERE owner_id=p.user_id AND status='active')"
                        " OR EXISTS(SELECT 1 FROM coop_members m JOIN coop_runs c ON c.id=m.run_id WHERE m.user_id=p.user_id AND m.withdrawn=0 AND c.status='active')) ELSE 0 END AS expedition "
                        'FROM mp_presence p JOIN users u ON u.id=p.user_id JOIN users h ON h.id=p.host_id '
                        'LEFT JOIN profiles pr ON pr.user_id=p.user_id LEFT JOIN social_prefs s ON s.user_id=p.user_id '
                        'WHERE p.seen>?', (now-ONLINE_SECONDS,)):
                    row = dict(r)
                    row['avatar'] = look(row['avatar'])
                    rows[row['user_id']] = row
                self.rows, self.built = rows, now
                self.rebuilds += 1
            return self.rows
        finally:
            self.lock.release()


class PollMeter:
    """Server-side backpressure for the presence poll. Every poll is counted; every
    METER_SECONDS the slow-down factor moves towards measured rate / budget (square root steps,
    so it settles instead of swinging), between 1 and MAX_SLOWDOWN. The advised intervals are
    the operator's (social_poll in /health) times the factor. In this process only (one worker)."""
    METER_SECONDS = 2.0
    MAX_SLOWDOWN = 4.0

    def __init__(self, clock, budget):
        self.clock, self.budget = clock, budget
        self.lock = threading.Lock()
        self.count, self.since, self.factor = 0, clock(), 1.0

    def tick(self):
        with self.lock:
            self.count += 1
            now = self.clock()
            elapsed = now-self.since
            if elapsed >= self.METER_SECONDS:
                rate = self.count/elapsed
                self.factor = min(self.MAX_SLOWDOWN, max(1.0, self.factor*math.sqrt(rate/self.budget)))
                self.count, self.since = 0, now
            return self.factor


class Lookup(Mutation):
    """A player by user id (lists) or by user name (typed)."""
    user_id: uuid.UUID | None = None
    username: str | None = Field(default=None, min_length=3, max_length=24, pattern=r'^[a-zA-Z0-9_]+$')

    @model_validator(mode='after')
    def one(self):
        if (self.user_id is None) == (self.username is None):
            raise ValueError('give user_id or username')
        return self


class Target(Mutation):
    user_id: uuid.UUID


class PrefsEdit(Mutation):
    appear_offline: bool | None = None
    roster: Literal['everyone', 'friends'] | None = None
    requests: Literal['everyone', 'nobody'] | None = None
    drop_in: Literal['off', 'friends'] | None = None


class Report(Mutation):
    user_id: uuid.UUID
    message_id: int | None = Field(default=None, ge=1, le=2**53)
    reason: Literal['spam', 'abuse', 'other']
    note: str = Field(default='', max_length=200)


class Mute(Mutation):
    user_id: uuid.UUID
    minutes: int = Field(ge=0, le=7*24*60)


class Removal(Mutation):
    message_ids: list[int] = Field(min_length=1, max_length=100)


class Friends:
    def __init__(self, app, db, settings, clock, auth, mutate, multiplayer):
        self.db, self.settings, self.clock = db, settings, clock
        self.roster = Roster(clock)
        self.meter = PollMeter(clock, settings.presence_budget)
        mp = multiplayer
        from .chat import Window, refuse
        people_window = Window(PEOPLE_PER_MINUTE, 60)
        with db.read() as conn:
            ensure_schema(conn)

        def user_by(conn, body):
            if body.user_id is not None:
                return conn.execute('SELECT id,username FROM users WHERE id=?', (str(body.user_id),)).fetchone()
            return conn.execute('SELECT id,username FROM users WHERE username=?', (body.username.lower(),)).fetchone()

        def target(conn, user, user_id, self_code):
            row = conn.execute('SELECT id,username FROM users WHERE id=?', (str(user_id),)).fetchone()
            if not row:
                fail('user_not_found', 404)
            if row['id'] == user['id']:
                fail(self_code, 422)
            return row

        def accept_into(conn, request_row):
            a, b = request_row['from_id'], request_row['to_id']
            for one in (a, b):
                if conn.execute('SELECT count(*) FROM social_friends WHERE user_id=?', (one,)).fetchone()[0] >= FRIEND_LIMIT:
                    fail('friend_list_full')
            now = clock()
            conn.execute('INSERT OR IGNORE INTO social_friends VALUES (?,?,?)', (a, b, now))
            conn.execute('INSERT OR IGNORE INTO social_friends VALUES (?,?,?)', (b, a, now))
            conn.execute("UPDATE social_requests SET state='accepted',updated=? WHERE state IN ('pending','suppressed') AND ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?))", (now, a, b, b, a))
            bump(conn, a, b)

        # --- the roster ---------------------------------------------------------------------
        def people(conn, user):
            now, me = clock(), user['id']
            rows = self.roster.get(conn)
            blocked = blocked_ids(conn, me)
            mine = prefs(conn, me)
            friend_rows = conn.execute(
                'SELECT f.friend_id AS id,f.created,u.username,pr.avatar,COALESCE(pr.version,0) AS avatar_version,'
                "COALESCE(s.appear_offline,0) AS appear_offline,COALESCE(s.drop_in,'off') AS drop_in,s.last_seen,p.seen "
                'FROM social_friends f JOIN users u ON u.id=f.friend_id LEFT JOIN profiles pr ON pr.user_id=f.friend_id '
                'LEFT JOIN social_prefs s ON s.user_id=f.friend_id LEFT JOIN mp_presence p ON p.user_id=f.friend_id '
                'WHERE f.user_id=? ORDER BY u.username', (me,)).fetchall()
            friend_set = {r['id'] for r in friend_rows}
            host = mp.host_for(conn, me)
            guests_of = {}
            for r in conn.execute('SELECT host_id,count(*) FROM mp_visits WHERE expires>? GROUP BY host_id', (now,)):
                guests_of[r[0]] = r[1]
            # Everyone online (privacy rules in docs/design/SOCIAL_API.md).
            online = []
            count = 0
            for r in rows.values():
                if r['appear_offline']:
                    continue
                count += 1
                if r['user_id'] == me or r['user_id'] in blocked:
                    continue
                friend = r['user_id'] in friend_set
                here = r['host_id'] == host and place_of(r) in ('village', 'home')
                if not friend and not here:
                    if self.settings.social_roster != 'all' or r['roster'] == 'friends':
                        continue
                elif self.settings.social_roster == 'off':
                    continue
                entry = {'id': r['user_id'], 'username': r['username'], 'avatar': r['avatar'], 'avatar_version': r['avatar_version'],
                         'friend': friend, 'place': place_of(r)}
                if friend or here:
                    entry['where'] = where_of(r)
                online.append(entry)
            online.sort(key=lambda e: (not e['friend'], 'where' not in e, e['username']))
            friends = []
            for f in friend_rows:
                if f['id'] in blocked:
                    continue
                live = rows.get(f['id'])
                hidden = bool(f['appear_offline'])
                is_online = bool(live) and not hidden
                entry = {'id': f['id'], 'username': f['username'], 'avatar': look(f['avatar']), 'avatar_version': f['avatar_version'],
                         'online': is_online, 'since': f['created'], 'drop_in': f['drop_in'] == 'friends',
                         'last_seen': None if hidden or is_online else (f['seen'] if f['seen'] is not None else f['last_seen'])}
                if is_online:
                    entry['where'] = where_of(live)
                entry['joinable'] = bool(is_online and place_of(live) in ('village', 'home') and live['host_id'] == f['id']
                                         and guests_of.get(f['id'], 0) < GUEST_LIMIT and host != f['id'])
                friends.append(entry)
            friends.sort(key=lambda e: (not e['online'], e['username']))
            incoming = [dict(r) for r in conn.execute(
                "SELECT r.id,r.from_id AS user_id,u.username,r.created FROM social_requests r JOIN users u ON u.id=r.from_id WHERE r.to_id=? AND r.state='pending' ORDER BY r.created DESC LIMIT 50", (me,))
                if r['user_id'] not in blocked]
            outgoing = [dict(r) for r in conn.execute(
                "SELECT r.id,r.to_id AS user_id,u.username,r.created FROM social_requests r JOIN users u ON u.id=r.to_id WHERE r.from_id=? AND r.state IN ('pending','suppressed') ORDER BY r.created DESC LIMIT 50", (me,))]
            blocked_list = [dict(r) for r in conn.execute('SELECT b.blocked_id AS id,u.username FROM social_blocks b JOIN users u ON u.id=b.blocked_id WHERE b.user_id=? ORDER BY u.username', (me,))]
            # My village now: the host and every guest, indoors too.
            host_name = conn.execute('SELECT username FROM users WHERE id=?', (host,)).fetchone()[0]
            host_live = rows.get(host)
            guests = []
            for g in conn.execute('SELECT v.user_id,u.username,p.scene,p.place,p.floor,p.seen,p.host_id,NULL AS host_name,0 AS expedition FROM mp_visits v JOIN users u ON u.id=v.user_id '
                                  'LEFT JOIN mp_presence p ON p.user_id=v.user_id WHERE v.host_id=? AND v.expires>? ORDER BY u.username', (host, now)):
                if g['user_id'] in blocked:
                    continue
                entry = {'id': g['user_id'], 'username': g['username'], 'online': bool(g['seen'] is not None and now-g['seen'] < ONLINE_SECONDS)}
                if g['scene'] is not None:
                    entry['place'] = place_of(g)
                    if g['floor'] is not None:
                        entry['floor'] = g['floor']
                guests.append(entry)
            village = {'host': {'id': host, 'username': host_name, 'online': bool(host_live) and (host == me or not host_live['appear_offline'])},
                       'visiting': host != me, 'guests': guests, 'guest_limit': GUEST_LIMIT}
            if host == me:
                village['invites_out'] = [dict(r) for r in conn.execute(
                    "SELECT i.id,i.recipient_id AS user_id,u.username,i.kind,i.expires FROM mp_invites i JOIN users u ON u.id=i.recipient_id WHERE i.sender_id=? AND i.state='pending' AND i.expires>? AND i.kind IN ('village','party') ORDER BY i.created DESC LIMIT 20", (me, now))]
                village['knocks'] = [dict(r) for r in conn.execute(
                    "SELECT i.id,i.sender_id AS user_id,u.username,i.expires FROM mp_invites i JOIN users u ON u.id=i.sender_id WHERE i.recipient_id=? AND i.kind='knock' AND i.state='pending' AND i.expires>? ORDER BY i.created DESC LIMIT 20", (me, now))
                    if r['user_id'] not in blocked]
            return {'v': mine['rev'], 'online_count': count, 'online': online[:ROSTER_LIMIT], 'roster': self.settings.social_roster,
                    'my_village': village, 'friends': friends, 'requests': {'incoming': incoming, 'outgoing': outgoing},
                    'blocked': blocked_list, 'prefs': {k: mine[k] for k in DEFAULT_PREFS},
                    'limits': {'friends': FRIEND_LIMIT, 'requests_per_day': REQUESTS_PER_DAY}}

        def presence_block(conn, user_id):
            """The social part of a chat2 presence reply: badges without fetching /people."""
            now = clock()
            rows = self.roster.get(conn)
            mine = prefs(conn, user_id)
            online = sum(1 for f in friend_ids(conn, user_id) if f in rows and not rows[f]['appear_offline'])
            requests = conn.execute("SELECT count(*) FROM social_requests WHERE to_id=? AND state='pending'", (user_id,)).fetchone()[0]
            knocks = conn.execute("SELECT count(*) FROM mp_invites WHERE recipient_id=? AND state='pending' AND expires>? AND kind='knock'", (user_id, now)).fetchone()[0]
            slow = self.meter.factor
            block = {'v': mine['rev'], 'requests': requests, 'knocks': knocks, 'friends_online': online,
                     'poll': {'together': round(self.settings.presence_together_seconds*slow, 2), 'alone': round(self.settings.presence_alone_seconds*slow, 2)}}
            if mine['chat_muted_until'] and mine['chat_muted_until'] > now:
                block['muted_until'] = mine['chat_muted_until']
            return block

        self.people = people
        self.presence_block = presence_block

        @app.get('/v1/social/people')
        def get_people(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                wait = people_window.take(user['id'], clock())
                if wait:
                    refuse('people_rate_limited', 429, wait)
                return JSONResponse(people(conn, user))

        # --- friend requests ----------------------------------------------------------------
        @app.post('/v1/friends/requests')
        def send_request(body: Lookup, request: Request):
            def apply(conn, user):
                now, me = clock(), user['id']
                other = user_by(conn, body)
                if not other:
                    fail('user_not_found', 404)
                them = other['id']
                if them == me:
                    fail('friend_self', 422)
                if conn.execute('SELECT 1 FROM social_blocks WHERE user_id=? AND blocked_id=?', (me, them)).fetchone():
                    fail('user_blocked')
                if are_friends(conn, me, them):
                    return {'state': 'friends'}
                open_row = conn.execute("SELECT id FROM social_requests WHERE from_id=? AND to_id=? AND state IN ('pending','suppressed')", (me, them)).fetchone()
                if open_row:
                    return {'state': 'sent', 'id': open_row['id']}
                if conn.execute('SELECT count(*) FROM social_requests WHERE from_id=? AND created>?', (me, now-86400)).fetchone()[0] >= REQUESTS_PER_DAY:
                    fail('friend_requests_limited', 429)
                if conn.execute("SELECT count(*) FROM social_requests WHERE from_id=? AND state IN ('pending','suppressed')", (me,)).fetchone()[0] >= PENDING_LIMIT:
                    fail('friend_requests_pending_full')
                if conn.execute('SELECT count(*) FROM social_friends WHERE user_id=?', (me,)).fetchone()[0] >= FRIEND_LIMIT:
                    fail('friend_list_full')
                reverse = conn.execute("SELECT * FROM social_requests WHERE from_id=? AND to_id=? AND state='pending'", (them, me)).fetchone()
                if reverse and not blocked_between(conn, me, them):
                    accept_into(conn, reverse)
                    return {'state': 'accepted'}
                # Never tells the sender why nothing reaches the other player.
                silent = (blocked_between(conn, me, them) or prefs(conn, them)['requests'] == 'nobody'
                          or conn.execute("SELECT 1 FROM social_requests WHERE from_id=? AND to_id=? AND state='declined' AND updated>?", (me, them, now-DECLINE_COOLDOWN_SECONDS)).fetchone())
                request_id = str(uuid.uuid4())
                conn.execute('INSERT INTO social_requests VALUES (?,?,?,?,?,?)', (request_id, me, them, 'suppressed' if silent else 'pending', now, now))
                bump(conn, me) if silent else bump(conn, me, them)
                return {'state': 'sent', 'id': request_id}
            return mutate(request, body, 'friend_request', apply)

        @app.post('/v1/friends/requests/{request_id}/{decision}')
        def answer_request(request_id: str, decision: Literal['accept', 'decline', 'cancel'], body: Mutation, request: Request):
            def apply(conn, user):
                now, me = clock(), user['id']
                if decision == 'cancel':
                    row = conn.execute("SELECT * FROM social_requests WHERE id=? AND from_id=? AND state IN ('pending','suppressed')", (request_id, me)).fetchone()
                else:
                    row = conn.execute("SELECT * FROM social_requests WHERE id=? AND to_id=? AND state='pending'", (request_id, me)).fetchone()
                if not row:
                    fail('request_unavailable', 404)
                if decision == 'accept':
                    accept_into(conn, row)
                    return {'ok': True, 'state': 'accepted'}
                state = 'declined' if decision == 'decline' else 'cancelled'
                conn.execute('UPDATE social_requests SET state=?,updated=? WHERE id=?', (state, now, request_id))
                bump(conn, row['from_id'], row['to_id']) if row['state'] == 'pending' else bump(conn, me)
                return {'ok': True, 'state': state}
            return mutate(request, body, 'friend_answer:'+request_id+':'+decision, apply)

        @app.post('/v1/friends/remove')
        def remove_friend(body: Target, request: Request):
            def apply(conn, user):
                them = str(body.user_id)
                removed = conn.execute('DELETE FROM social_friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)', (user['id'], them, them, user['id'])).rowcount
                if removed:
                    bump(conn, user['id'], them)
                return {'ok': True}
            return mutate(request, body, 'friend_remove', apply)

        # --- blocks, privacy, reports ---------------------------------------------------------
        @app.post('/v1/social/blocks')
        def block(body: Target, request: Request):
            def apply(conn, user):
                now, me = clock(), user['id']
                them = target(conn, user, body.user_id, 'block_self')['id']
                if not conn.execute('SELECT 1 FROM social_blocks WHERE user_id=? AND blocked_id=?', (me, them)).fetchone():
                    if conn.execute('SELECT count(*) FROM social_blocks WHERE user_id=?', (me,)).fetchone()[0] >= BLOCK_LIMIT:
                        fail('block_list_full')
                    conn.execute('INSERT INTO social_blocks VALUES (?,?,?)', (me, them, now))
                # Everything between the two ends: friendship, requests, invitations, knocks, visits.
                conn.execute('DELETE FROM social_friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)', (me, them, them, me))
                conn.execute("UPDATE social_requests SET state='cancelled',updated=? WHERE state IN ('pending','suppressed') AND ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?))", (now, me, them, them, me))
                conn.execute("UPDATE mp_invites SET state='revoked' WHERE state='pending' AND ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?))", (me, them, them, me))
                for guest, host in ((them, me), (me, them)):
                    if conn.execute('SELECT 1 FROM mp_visits WHERE user_id=? AND host_id=?', (guest, host)).fetchone():
                        mp.end_visit(conn, guest, host, 'ended')
                bump(conn, me, them)
                return {'ok': True}
            return mutate(request, body, 'social_block', apply)

        @app.post('/v1/social/blocks/remove')
        def unblock(body: Target, request: Request):
            def apply(conn, user):
                them = str(body.user_id)
                if conn.execute('DELETE FROM social_blocks WHERE user_id=? AND blocked_id=?', (user['id'], them)).rowcount:
                    bump(conn, user['id'], them)
                return {'ok': True}
            return mutate(request, body, 'social_unblock', apply)

        @app.post('/v1/social/prefs')
        def edit_prefs(body: PrefsEdit, request: Request):
            def apply(conn, user):
                changes = {k: v for k, v in body.model_dump().items() if k in DEFAULT_PREFS and v is not None}
                bump(conn, user['id'])
                for key, value in changes.items():
                    conn.execute(f'UPDATE social_prefs SET {key}=? WHERE user_id=?', (int(value) if isinstance(value, bool) else value, user['id']))
                return {k: v for k, v in prefs(conn, user['id']).items() if k in DEFAULT_PREFS}
            return mutate(request, body, 'social_prefs', apply)

        @app.post('/v1/social/report')
        def report(body: Report, request: Request):
            def apply(conn, user):
                now, me = clock(), user['id']
                them = target(conn, user, body.user_id, 'report_self')['id']
                if conn.execute('SELECT count(*) FROM social_reports WHERE user_id=? AND created>?', (me, now-86400)).fetchone()[0] >= REPORTS_PER_DAY:
                    fail('report_limited', 429)
                same = conn.execute('SELECT id FROM social_reports WHERE user_id=? AND to_id=? AND COALESCE(message_id,0)=? AND created>?', (me, them, body.message_id or 0, now-86400)).fetchone()
                if same:
                    return {'ok': True, 'id': same['id']}
                text = None
                if body.message_id:
                    line = conn.execute('SELECT text FROM mp_messages WHERE id=? AND user_id=?', (body.message_id, them)).fetchone()
                    text = line['text'] if line else None
                # What the reporter could have read from that player in the last hour, for the operator.
                party = mp.party_for(conn, me)
                rooms = ['village:'+mp.host_for(conn, me), 'global', 'dm:'+me] + (['party:'+party['id']] if party else [])
                context = [dict(r) for r in conn.execute(
                    f"SELECT id,channel,room,text,created FROM mp_messages WHERE user_id=? AND created>? AND room IN ({','.join('?'*len(rooms))}) ORDER BY id DESC LIMIT 10",
                    (them, now-3600, *rooms))]
                for line in context:
                    line['room'] = line['room'].split(':')[0]
                from .security import clean_text
                report_id = conn.execute('INSERT INTO social_reports(user_id,to_id,message_id,text,context,reason,note,state,created) VALUES (?,?,?,?,?,?,?,?,?)',
                                         (me, them, body.message_id, text, json.dumps(context[::-1], ensure_ascii=False), body.reason,
                                          clean_text(body.note)[:200], 'open', now)).lastrowid
                return {'ok': True, 'id': report_id}
            return mutate(request, body, 'social_report', apply)

        # --- visits from the lists ------------------------------------------------------------
        @app.post('/v1/social/visit')
        def visit(body: Target, request: Request):
            def apply(conn, user):
                now, me = clock(), user['id']
                host = target(conn, user, body.user_id, 'visit_self')['id']
                if mp.host_for(conn, me) == host:
                    return {'state': 'visiting'}
                friends = are_friends(conn, me, host)
                host_prefs = prefs(conn, host)
                asked = {'state': 'asked', 'expires': now+KNOCK_SECONDS}
                if blocked_between(conn, me, host) or (not friends and host_prefs['requests'] == 'nobody'):
                    return asked
                if not visible_online(conn, host, now) or mp.host_for(conn, host) != host:
                    fail('host_offline')
                if mp.active_coop(conn, me):
                    fail('party_expedition_active')
                spot = conn.execute('SELECT scene,seen FROM mp_presence WHERE user_id=?', (me,)).fetchone()
                # Straight in only from the village: the game follows a new host in its village poll.
                if friends and host_prefs['drop_in'] == 'friends' and spot and spot['scene'] == 'village' and now-spot['seen'] < mp.HOST_GONE_SECONDS:
                    mp.start_visit(conn, me, host)
                    bump(conn, host)
                    return {'state': 'visiting'}
                last = conn.execute("SELECT max(created) FROM mp_invites WHERE sender_id=? AND recipient_id=? AND kind='knock'", (me, host)).fetchone()[0]
                if last is not None and now-last < KNOCK_GAP_SECONDS:
                    refuse('knock_limited', 429, KNOCK_GAP_SECONDS-(now-last))
                if conn.execute("SELECT count(*) FROM mp_invites WHERE sender_id=? AND state='pending' AND kind='knock' AND expires>?", (me, now)).fetchone()[0] >= KNOCKS_PENDING:
                    refuse('knock_limited', 429, KNOCK_SECONDS)
                conn.execute("INSERT INTO mp_invites VALUES (?,?,?,'knock',NULL,'pending',?,?)", (str(uuid.uuid4()), me, host, now+KNOCK_SECONDS, now))
                bump(conn, host)
                return asked
            return mutate(request, body, 'social_visit', apply)

        # --- operators ------------------------------------------------------------------------
        def admin(conn, request):
            user = auth(conn, request)
            if user['role'] != 'admin':
                fail('admin_only', 403)
            return user

        @app.get('/v1/admin/reports')
        def reports(request: Request, state: Literal['open', 'closed', 'all'] = 'open', limit: int = 50):
            with db.read() as conn:
                admin(conn, request)
                limit = max(1, min(limit, 200))
                where = '' if state == 'all' else 'WHERE r.state=?'
                args = () if state == 'all' else (state,)
                rows = conn.execute('SELECT r.*,a.username AS reporter,b.username AS reported FROM social_reports r LEFT JOIN users a ON a.id=r.user_id '
                                    f'LEFT JOIN users b ON b.id=r.to_id {where} ORDER BY r.id DESC LIMIT ?', (*args, limit)).fetchall()
                return {'reports': [{**{k: r[k] for k in ('id', 'user_id', 'reporter', 'to_id', 'reported', 'message_id', 'text', 'reason', 'note', 'state', 'created')},
                                     'context': json.loads(r['context'] or '[]')} for r in rows]}

        @app.post('/v1/admin/reports/{report_id}/close')
        def close_report(report_id: int, body: Mutation, request: Request):
            def apply(conn, user):
                if user['role'] != 'admin':
                    fail('admin_only', 403)
                conn.execute("UPDATE social_reports SET state='closed',updated=? WHERE id=?", (clock(), report_id))
                return {'ok': True}
            return mutate(request, body, 'admin_report_close:'+str(report_id), apply)

        @app.post('/v1/admin/chat/mute')
        def mute(body: Mute, request: Request):
            def apply(conn, user):
                if user['role'] != 'admin':
                    fail('admin_only', 403)
                if not conn.execute('SELECT 1 FROM users WHERE id=?', (str(body.user_id),)).fetchone():
                    fail('user_not_found', 404)
                until = clock()+body.minutes*60 if body.minutes else None
                set_mute(conn, str(body.user_id), until)
                return {'ok': True, 'muted_until': until}
            return mutate(request, body, 'admin_chat_mute', apply)

        @app.post('/v1/admin/chat/delete')
        def delete_lines(body: Removal, request: Request):
            def apply(conn, user):
                if user['role'] != 'admin':
                    fail('admin_only', 403)
                return {'ok': True, 'removed': mp.chat.remove(conn, body.message_ids, clock())}
            return mutate(request, body, 'admin_chat_delete', apply)

    def health(self):
        """The one /health definition of the social layer (clients feature-detect from it)."""
        s = self.settings
        return {'social_features': list(FEATURES), 'global_chat': bool(s.global_chat), 'social_roster': s.social_roster,
                'interaction_sync': 1, 'chat_max_length': 160,
                'social_poll': {'presence_together': s.presence_together_seconds, 'presence_alone': s.presence_alone_seconds,
                                'people': s.people_seconds, 'presence_budget': s.presence_budget}}
