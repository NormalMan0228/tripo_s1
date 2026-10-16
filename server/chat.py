"""Chat v2 (docs/design/SOCIAL_API.md): channels, cursor delivery, history, rate limits, the word
filter, mutes, operator removals, and the retention that keeps every social table bounded.

Rooms in mp_messages.room: 'village:<host id>' (channel local), 'party:<party id>' (party),
'global' (everyone on the server), 'dm:<recipient id>' (whisper; to_id is the recipient).
Lines live chat_retention_hours (24 h) and are delivered for an hour at most.

Delivery (deliver) runs in the presence reply's read phase, after the poll's write committed
(Database.write_then_read): a UNION ALL of one index range per room, never the writer slot.
"""
import hashlib
import json
import uuid
from typing import Literal
import logging
import math
import re
import sqlite3
import threading
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from .models import Mutation
from .whisper_presence import nearby
from .chat_filter import ChatFilter
from .security import clean_text, record_event
from . import friends as social

CHANNELS = ('local', 'party', 'global', 'whisper')
HISTORY_LINES = 30            # since <= 0: the newest lines of the player's rooms
DELIVERY_LINES = 50           # at most per reply; 'more' asks the client to poll again soon
DELIVERY_SECONDS = 3600       # older lines are never delivered (history included)
GAP_SECONDS = 1               # between two lines of one player
BURST_LINES, BURST_SECONDS = 5, 10
REPEAT_LINES, REPEAT_SECONDS = 3, 30
GLOBAL_GAP_SECONDS = 5        # one player's lines in the everyone channel
GLOBAL_SERVER_LINES, GLOBAL_SERVER_SECONDS = 20, 10   # the whole server's everyone channel
MASK_MUTE_LINES, MASK_MUTE_SECONDS, AUTO_MUTE_SECONDS = 3, 300, 300
REMOVAL_SECONDS = 900         # an operator's removal is announced to clients this long
RUN_LIMIT = 12                # a character repeated longer than this is cut (ㅋㅋㅋ… floods)
PRUNE_SECONDS = 600           # retention runs at most this often, in batches
PRUNE_BATCH = 5000
REMOVALS_SHOWN = 200          # newest operator removals per reply
# The released games' (0.11.x) greeting chip always sends the same line: exempt from the repeat
# rule for sends without a channel (gap and burst limits still apply).
LEGACY_GREETINGS = frozenset({'안녕하세요! 👋', 'Hello! 👋', '你好！👋'})

log = logging.getLogger(__name__)

# Idempotency records (requests) and audit rows of social operations: a retried request comes
# within seconds, so two days is plenty; social audit rows stay 30 days, a legacy chat line's
# audit row (servers before chat v2 wrote one per line) a day. Money and crafting rows stay.
SOCIAL_OPERATIONS = ('social_message', 'social_invite', 'social_home', 'social_eject', 'social_visit',
                     'social_block', 'social_unblock', 'social_prefs', 'social_report',
                     'friend_request', 'friend_remove', 'whisper_request')
SOCIAL_PREFIXES = ('invite:', 'friend_answer:', 'whisper_answer:')
REQUEST_KEEP_SECONDS = 2 * 86400
AUDIT_KEEP_SECONDS = 30 * 86400

WHISPER_COOLDOWN = 600
WHISPER_PENDING_LIMIT = 5

SCHEMA = '''
CREATE TABLE IF NOT EXISTS whisper_requests (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), friend_id TEXT NOT NULL REFERENCES users(id),
 sender_id TEXT NOT NULL REFERENCES users(id), recipient_id TEXT NOT NULL REFERENCES users(id),
 state TEXT NOT NULL CHECK(state IN ('pending','accepted','declined')),
 created REAL NOT NULL, expires REAL NOT NULL, UNIQUE(user_id,friend_id));
CREATE INDEX IF NOT EXISTS whisper_requests_sender ON whisper_requests(sender_id,state,expires);
CREATE INDEX IF NOT EXISTS whisper_requests_recipient ON whisper_requests(recipient_id,state,expires);

CREATE INDEX IF NOT EXISTS mp_messages_user ON mp_messages(user_id,id);
CREATE INDEX IF NOT EXISTS mp_messages_created ON mp_messages(created);
CREATE UNIQUE INDEX IF NOT EXISTS mp_messages_request ON mp_messages(user_id,request_id) WHERE request_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS mp_message_removals (id INTEGER PRIMARY KEY, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS mp_message_removals_created ON mp_message_removals(created);
CREATE INDEX IF NOT EXISTS requests_operation ON requests(operation,created);
CREATE INDEX IF NOT EXISTS audit_action ON audit(action,created);
CREATE INDEX IF NOT EXISTS mp_invites_expires ON mp_invites(expires);
CREATE INDEX IF NOT EXISTS mp_invites_sender ON mp_invites(sender_id,state);
'''


def refuse(code, status, retry=None):
    raise HTTPException(status, code, headers={'Retry-After': str(max(1, math.ceil(retry)))} if retry else None)


def ensure_schema(conn):
    columns = [r[1] for r in conn.execute('PRAGMA table_info(mp_messages)')]
    for name in ('channel', 'to_id', 'request_id'):
        if name not in columns:
            conn.execute('ALTER TABLE mp_messages ADD COLUMN '+name+' TEXT')
    conn.executescript(SCHEMA)
    # Line ids start at 2, so the cursor of a server without any line yet is 1, not 0 (since 0
    # asks for history: the first lines ever would come as history and be seeded silently).
    row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='mp_messages'").fetchone()
    if row is None:
        conn.execute("INSERT INTO sqlite_sequence(name,seq) VALUES ('mp_messages',1)")
    elif not row[0] or row[0] < 1:
        conn.execute("UPDATE sqlite_sequence SET seq=1 WHERE name='mp_messages'")


class Window:
    """Sliding-window counters kept in this process (the server runs one uvicorn worker)."""
    def __init__(self, limit, seconds):
        self.limit, self.seconds = limit, seconds
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def take(self, key, now):
        """Records one use and returns 0, or returns the seconds until one is free."""
        with self.lock:
            if len(self.hits) > 4096:
                for old in [k for k, q in self.hits.items() if not q or q[-1] <= now-self.seconds]:
                    del self.hits[old]
            queue = self.hits[key]
            while queue and queue[0] <= now-self.seconds:
                queue.popleft()
            if len(queue) >= self.limit:
                return queue[0]+self.seconds-now
            queue.append(now)
            return 0


def channel_of(row):
    if row['channel']:
        return row['channel']
    return 'party' if row['room'].startswith('party:') else 'local'


def prepare(text):
    value = clean_text(text)
    return re.sub(r'(.)\1{%d,}' % RUN_LIMIT, lambda m: m.group(1)*RUN_LIMIT, value)


class Chat:
    def __init__(self, db, settings, clock):
        self.db, self.settings, self.clock = db, settings, clock
        extra = settings.chat_filter_extra
        if extra:
            from pathlib import Path
            extra = Path(extra) if Path(extra).is_absolute() else settings.data_dir/extra
        self.filter = ChatFilter(extra)
        self.per_ip = Window(settings.chat_ip_per_minute, 60)
        self.everyone = Window(GLOBAL_SERVER_LINES, GLOBAL_SERVER_SECONDS)
        self.prune_lock = threading.Lock()
        self.pruned_at = -math.inf
        with db.read() as conn:
            ensure_schema(conn)

    # --- sending ------------------------------------------------------------------------------
    def post(self, conn, user, body, ip, legacy_room, village_room, party_room):
        now, uid = self.clock(), user['id']
        value = prepare(body.text)
        if not value:
            refuse('message_empty', 422)
        checked = self.filter.check(value)
        previous = conn.execute('SELECT id,room,channel,text FROM mp_messages WHERE user_id=? AND request_id=?', (uid, str(body.request_id))).fetchone()
        if previous:
            # The same request again (a retry after a lost reply): the same answer, no second line.
            if previous['text'] != checked.text:
                refuse('request_id_reused', 409)
            return {'ok': True, 'id': previous['id'], 'channel': channel_of(previous), 'text': previous['text'], 'masked': checked.masked > 0}
        previous_request = conn.execute('SELECT operation,fingerprint,response FROM requests WHERE user_id=? AND request_id=?',
                                        (uid, str(body.request_id))).fetchone()
        if previous_request:
            fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
            if previous_request['operation'] != 'whisper_request' or previous_request['fingerprint'] != fingerprint:
                refuse('request_id_reused', 409)
            return json.loads(previous_request['response'])
        if checked.blocked:
            refuse('message_blocked', 422)
        muted = social.muted_until(conn, uid)
        if muted and muted > now:
            refuse('chat_muted', 403, muted-now)
        channel, to_id = body.channel, None
        if channel is None:
            room = legacy_room
            channel = 'party' if room.startswith('party:') else 'local'
        elif channel == 'local':
            room = village_room
        elif channel == 'party':
            if not party_room:
                refuse('not_in_party', 409)
            room = party_room
        elif channel == 'global':
            if not self.settings.global_chat:
                refuse('global_chat_off', 403)
            room = 'global'
        else:
            to_id = self.whisper_target(conn, uid, body.to, now)
            room = 'dm:'+to_id
        recent = conn.execute('SELECT room,text,created FROM mp_messages WHERE user_id=? ORDER BY id DESC LIMIT 8', (uid,)).fetchall()
        if recent and now-recent[0]['created'] < GAP_SECONDS:
            refuse('message_rate_limited', 429, GAP_SECONDS-(now-recent[0]['created']))
        if len(recent) >= BURST_LINES and now-recent[BURST_LINES-1]['created'] < BURST_SECONDS:
            refuse('message_rate_limited', 429, BURST_SECONDS-(now-recent[BURST_LINES-1]['created']))
        repeated = next((r for r in recent[:REPEAT_LINES] if r['text'] == checked.text and now-r['created'] < REPEAT_SECONDS), None)
        if repeated:
            if body.channel is not None:
                refuse('message_repeated', 429)
            # Released games know only message_rate_limited; their greeting chip is exempt.
            if checked.text not in LEGACY_GREETINGS:
                refuse('message_rate_limited', 429, REPEAT_SECONDS-(now-repeated['created']))
        if room == 'global':
            last = next((r['created'] for r in recent if r['room'] == 'global'), None)
            if last is not None and now-last < GLOBAL_GAP_SECONDS:
                refuse('global_chat_slow', 429, GLOBAL_GAP_SECONDS-(now-last))
        wait = self.per_ip.take(ip, now)
        if wait:
            refuse('chat_ip_limited', 429, wait)
        if room == 'global':
            wait = self.everyone.take('global', now)
            if wait:
                refuse('global_chat_busy', 429, wait)
        if channel == 'whisper':
            requested = self.request_whisper(conn, uid, to_id, body, now)
            if requested is not None:
                return requested
        line_id = conn.execute('INSERT INTO mp_messages(room,user_id,text,created,channel,to_id,request_id) VALUES (?,?,?,?,?,?,?)',
                               (room, uid, checked.text, now, channel, to_id, str(body.request_id))).lastrowid
        conn.execute('DELETE FROM mp_messages WHERE created<?', (now-self.settings.chat_retention_hours*3600,))
        reply = {'ok': True, 'id': line_id, 'channel': channel, 'text': checked.text, 'masked': checked.masked > 0}
        # Only matches not split by a space count towards the mute ("몇 시 발표" is not "시발",
        # but a spaced reading is masked anyway and never mutes on its own).
        if checked.masked > checked.split:
            record_event(conn, 'chat_masked', uid, {'words': checked.masked, 'message_id': line_id}, now)
            count = conn.execute("SELECT count(*) FROM security_events WHERE kind='chat_masked' AND created>? AND user_id=?", (now-MASK_MUTE_SECONDS, uid)).fetchone()[0]
            if count >= MASK_MUTE_LINES:
                social.set_mute(conn, uid, now+AUTO_MUTE_SECONDS)
                record_event(conn, 'chat_auto_mute', uid, {'seconds': AUTO_MUTE_SECONDS}, now)
                reply['muted_until'] = now+AUTO_MUTE_SECONDS
        return reply

    def whisper_target(self, conn, uid, name, now):
        """Friends retain unlimited range; strangers need fresh shared-space presence."""
        target = conn.execute('SELECT id FROM users WHERE username=?', ((name or '').lower(),)).fetchone() if name else None
        if (not target or target['id'] == uid or social.blocked_between(conn, uid, target['id'])
                or not social.visible_online(conn, target['id'], now)):
            refuse('whisper_target_unavailable', 404)
        if not social.are_friends(conn, uid, target['id']):
            if not social.visible_online(conn, uid, now) or not nearby(conn, uid, target['id'], now):
                refuse('whisper_target_unavailable', 404)
        return target['id']

    def request_whisper(self, conn, uid, target, body, now):
        if social.are_friends(conn, uid, target):
            return None
        pair = tuple(sorted((uid, target)))
        row = conn.execute('SELECT * FROM whisper_requests WHERE user_id=? AND friend_id=?', pair).fetchone()
        if row and row['state'] == 'accepted' and row['expires'] > now:
            return None
        if row and now-row['created'] < WHISPER_COOLDOWN:
            refuse('whisper_request_limited', 429, row['created']+WHISPER_COOLDOWN-now)
        pending = conn.execute("SELECT count(*) FROM whisper_requests WHERE sender_id=? AND state='pending' AND expires>?", (uid,now)).fetchone()[0]
        if pending >= WHISPER_PENDING_LIMIT:
            refuse('whisper_pending_limit', 429, WHISPER_COOLDOWN)
        ident, expires = str(uuid.uuid4()), now+WHISPER_COOLDOWN
        conn.execute('''INSERT INTO whisper_requests VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT(user_id,friend_id) DO UPDATE SET id=excluded.id,sender_id=excluded.sender_id,
                        recipient_id=excluded.recipient_id,state=excluded.state,created=excluded.created,expires=excluded.expires''',
                     (ident,*pair,uid,target,'pending',now,expires))
        # No text is queued: acceptance grants permission for a NEW send only.
        reply = {'ok': True, 'channel': 'whisper', 'state': 'requested', 'request': {'id': ident, 'to_id': target, 'expires': expires}}
        conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)',
                     (uid,str(body.request_id),'whisper_request',hashlib.sha256(body.model_dump_json().encode()).hexdigest(),json.dumps(reply),now))
        return reply

    def bind_routes(self, app, auth, mutate):
        @app.get('/v1/social/whispers/requests')
        def requests(request: Request):
            with self.db.read() as conn:
                user = auth(conn, request)
                now, uid = self.clock(), user['id']
                rows = conn.execute('''SELECT r.id,r.sender_id,r.recipient_id,r.state,r.created,r.expires,
                                       s.username AS from_name,t.username AS to_name,
                                       COALESCE(s.display_name,s.username) AS from_display_name,COALESCE(t.display_name,t.username) AS to_display_name
                                       FROM whisper_requests r JOIN users s ON s.id=r.sender_id
                                       JOIN users t ON t.id=r.recipient_id
                                       WHERE (r.sender_id=? OR r.recipient_id=?) AND r.expires>?
                                       ORDER BY r.created''', (uid,uid,now)).fetchall()
                return {'requests': [dict(r) for r in rows if not social.blocked_between(conn,r['sender_id'],r['recipient_id'])]}

        @app.post('/v1/social/whispers/requests/{whisper_id}/{decision}')
        def answer(whisper_id: str, decision: Literal['accept','decline'], body: Mutation, request: Request):
            def apply(conn, user):
                now = self.clock()
                row = conn.execute('SELECT * FROM whisper_requests WHERE id=? AND recipient_id=? AND expires>?',
                                   (whisper_id,user['id'],now)).fetchone()
                if not row or social.blocked_between(conn,row['sender_id'],row['recipient_id']):
                    refuse('whisper_request_unavailable', 404)
                state = 'accepted' if decision == 'accept' else 'declined'
                if row['state'] != 'pending':
                    if row['state'] == state:
                        return {'ok': True, 'state': state, 'expires': row['expires']}
                    refuse('whisper_request_closed', 409)
                expires = row['expires']
                if decision == 'accept':
                    sender = conn.execute('SELECT username FROM users WHERE id=?', (row['sender_id'],)).fetchone()[0]
                    self.whisper_target(conn,user['id'],sender,now)
                    expires = (int(now//86400)+1)*86400
                conn.execute('UPDATE whisper_requests SET state=?,expires=? WHERE id=?', (state,expires,whisper_id))
                return {'ok': True, 'state': state, 'expires': expires}
            return mutate(request,body,'whisper_answer:'+whisper_id+':'+decision,apply)

    # --- delivery -----------------------------------------------------------------------------
    def rooms_for(self, village_room, party_room):
        rooms = [village_room]
        if party_room:
            rooms.append(party_room)
        if self.settings.global_chat:
            rooms.append('global')
        return rooms

    def deliver(self, conn, user_id, since, rooms, blocked):
        """The chat block of a presence reply: lines after the client's cursor (or the newest
        HISTORY_LINES when since <= 0), from the player's rooms and own whispers, without
        blocked players. cursor = the newest line id the server has, so a later room change does
        not replay that room's past (send since=0 for its history)."""
        now = self.clock()
        row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='mp_messages'").fetchone()
        head = row[0] if row else 0
        history = since <= 0 or since > head
        # The oldest line still delivered (one seek in the created index): every branch scans
        # ids from there, never the rest of the 24 h retention.
        first = conn.execute('SELECT id FROM mp_messages WHERE created>? ORDER BY created LIMIT 1', (now-DELIVERY_SECONDS,)).fetchone()
        floor = first[0] if first else head+1
        columns = 'e.id,e.room,e.channel,e.user_id,e.to_id,e.text,e.created'
        branches, params = [], []
        wheres = [('e.room=?', (room,)) for room in rooms]
        wheres.append(('e.room=?', ('dm:'+user_id,)))
        wheres.append(("e.user_id=? AND e.room>='dm:' AND e.room<'dm;'", (user_id,)))
        for where, args in wheres:
            if history:
                branches.append(f'SELECT * FROM (SELECT {columns} FROM mp_messages e WHERE {where} AND e.id>=? AND e.created>? ORDER BY e.id DESC LIMIT {HISTORY_LINES})')
                params.extend((*args, floor, now-DELIVERY_SECONDS))
            else:
                branches.append(f'SELECT {columns} FROM mp_messages e WHERE {where} AND e.id>? AND e.created>?')
                params.extend((*args, max(since, floor-1), now-DELIVERY_SECONDS))
        if history:
            sql = ' UNION ALL '.join(branches)+f' ORDER BY 1 DESC LIMIT {HISTORY_LINES*2}'
        else:
            sql = ' UNION ALL '.join(branches)+f' ORDER BY 1 LIMIT {DELIVERY_LINES*2+1}'
        rows, seen = [], set()
        for r in conn.execute(sql, params):
            if r['id'] not in seen:
                seen.add(r['id'])
                rows.append(r)
        more = False
        if history:
            rows = rows[:HISTORY_LINES][::-1]
            cursor = head
        elif len(rows) > DELIVERY_LINES:
            rows, more = rows[:DELIVERY_LINES], True
            cursor = rows[-1]['id']
        else:
            cursor = head
        rows = [r for r in rows if r['user_id'] not in blocked and r['to_id'] not in blocked]
        names, shown = {}, {}
        wanted = {r['user_id'] for r in rows} | {r['to_id'] for r in rows if r['to_id']}
        if wanted:
            marks = ','.join('?'*len(wanted))
            names = dict(conn.execute(f'SELECT id,username FROM users WHERE id IN ({marks})', tuple(wanted)).fetchall())
            shown = dict(conn.execute(f'SELECT id,COALESCE(display_name,username) FROM users WHERE id IN ({marks})', tuple(wanted)).fetchall())
        lines = []
        for r in rows:
            line = {'id': r['id'], 'channel': channel_of(r), 'user_id': r['user_id'], 'username': names.get(r['user_id'], ''),
                    'display_name': shown.get(r['user_id'], ''), 'text': r['text'], 'created': r['created']}
            if r['to_id']:
                line['to_id'], line['to_name'] = r['to_id'], names.get(r['to_id'], '')
                line['to_display_name'] = shown.get(r['to_id'], '')
            lines.append(line)
        block = {'cursor': cursor, 'history': history, 'more': more, 'lines': lines}
        # The newest removed lines first: those are the ones most likely still on screen.
        removed = [r[0] for r in conn.execute(f'SELECT id FROM mp_message_removals WHERE created>? ORDER BY id DESC LIMIT {REMOVALS_SHOWN}', (now-REMOVAL_SECONDS,))]
        if removed:
            block['removed'] = removed
        return block

    def legacy(self, conn, room, blocked):
        """The 20 newest lines of one room for clients before chat v2 (overview 'messages')."""
        rows = conn.execute('SELECT e.id,e.user_id,u.username,COALESCE(u.display_name,u.username) AS display_name,e.text,e.created FROM mp_messages e JOIN users u ON u.id=e.user_id WHERE room=? AND e.created>? ORDER BY e.id DESC LIMIT 20',
                            (room, self.clock()-DELIVERY_SECONDS)).fetchall()
        return [{'id': r['id'], 'username': r['username'], 'display_name': r['display_name'], 'text': r['text'], 'created': r['created']} for r in rows[::-1] if r['user_id'] not in blocked]

    # --- moderation ---------------------------------------------------------------------------
    @staticmethod
    def remove(conn, message_ids, now):
        """Operator removal: the lines are deleted and clients drop them (chat 'removed')."""
        count = 0
        for message_id in message_ids:
            count += conn.execute('DELETE FROM mp_messages WHERE id=?', (message_id,)).rowcount
            conn.execute('INSERT INTO mp_message_removals VALUES (?,?) ON CONFLICT(id) DO UPDATE SET created=excluded.created', (message_id, now))
        return count

    # --- retention ----------------------------------------------------------------------------
    def maybe_prune(self):
        """Runs after the response was sent (a background task of the chat and presence routes):
        a failure (a long writer holding SQLite's writer slot) never changes a committed request's
        answer; the next run, PRUNE_SECONDS later, tries again."""
        now = self.clock()
        if now-self.pruned_at < PRUNE_SECONDS or not self.prune_lock.acquire(blocking=False):
            return None
        try:
            self.pruned_at = now
            with self.db.transaction() as conn:
                return prune(conn, now, self.settings.chat_retention_hours)
        except sqlite3.Error as error:
            log.warning('social retention prune failed: %s', error)
            return None
        finally:
            self.prune_lock.release()


def prune(conn, now, retention_hours=24):
    """Bounded social tables: deletes what no feature reads any more, at most PRUNE_BATCH rows
    per table and run. Returns the rows removed per table."""
    removed = defaultdict(int)

    def run(table, sql, args):
        removed[table] += conn.execute(sql, args).rowcount

    def operations(column):
        marks = ','.join('?'*len(SOCIAL_OPERATIONS))
        prefixes = ' OR '.join(f'{column} BETWEEN ? AND ?' for _ in SOCIAL_PREFIXES)
        args = list(SOCIAL_OPERATIONS)
        for prefix in SOCIAL_PREFIXES:
            args += [prefix, prefix+'￿']
        return f'({column} IN ({marks}) OR {prefixes})', args

    run('whisper_requests', f'DELETE FROM whisper_requests WHERE rowid IN (SELECT rowid FROM whisper_requests WHERE expires<? AND created<? LIMIT {PRUNE_BATCH})', (now,now-WHISPER_COOLDOWN))
    run('mp_messages', 'DELETE FROM mp_messages WHERE created<?', (now-retention_hours*3600,))
    run('mp_message_removals', 'DELETE FROM mp_message_removals WHERE created<?', (now-REMOVAL_SECONDS,))
    where, args = operations('operation')
    run('requests', f'DELETE FROM requests WHERE rowid IN (SELECT rowid FROM requests WHERE {where} AND created<? LIMIT {PRUNE_BATCH})', (*args, now-REQUEST_KEEP_SECONDS))
    run('audit', f"DELETE FROM audit WHERE rowid IN (SELECT rowid FROM audit WHERE action='social_message' AND created<? LIMIT {PRUNE_BATCH})", (now-86400,))
    where, args = operations('action')
    run('audit', f'DELETE FROM audit WHERE rowid IN (SELECT rowid FROM audit WHERE {where} AND created<? LIMIT {PRUNE_BATCH})', (*args, now-AUDIT_KEEP_SECONDS))
    run('mp_invites', f'DELETE FROM mp_invites WHERE rowid IN (SELECT rowid FROM mp_invites WHERE expires<? LIMIT {PRUNE_BATCH})', (now-7*86400,))
    run('mp_visit_notices', 'DELETE FROM mp_visit_notices WHERE created<?', (now-86400,))
    conn.execute("UPDATE social_requests SET state='expired',updated=? WHERE state IN ('pending','suppressed') AND created<?", (now, now-social.REQUEST_EXPIRY_SECONDS))
    run('social_requests', f"DELETE FROM social_requests WHERE rowid IN (SELECT rowid FROM social_requests WHERE state NOT IN ('pending','suppressed') AND updated<? LIMIT {PRUNE_BATCH})", (now-30*86400,))
    run('social_reports', "DELETE FROM social_reports WHERE (state!='open' AND created<?) OR created<?", (now-90*86400, now-180*86400))
    return dict(removed)
