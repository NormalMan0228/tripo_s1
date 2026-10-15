"""Invited village visits and durable three-member cooperative expeditions."""
import json
import secrets
import uuid
from typing import Literal
from fastapi import Request, HTTPException
from fastapi.responses import Response, JSONResponse
from pydantic import Field
from .models import Strict, Mutation, Input, RunStart
from .stored_assets import read_glb
from . import coop, homestead, object_paint, object_shape, interactions
from . import friends as social_db
from .chat import Chat

SCHEMA = '''
CREATE TABLE IF NOT EXISTS mp_parties (
 id TEXT PRIMARY KEY, leader_id TEXT NOT NULL REFERENCES users(id), run_id TEXT, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mp_members (
 user_id TEXT PRIMARY KEY REFERENCES users(id), party_id TEXT NOT NULL REFERENCES mp_parties(id), joined REAL NOT NULL);
CREATE INDEX IF NOT EXISTS mp_members_party ON mp_members(party_id);
CREATE TABLE IF NOT EXISTS mp_invites (
 id TEXT PRIMARY KEY, sender_id TEXT NOT NULL REFERENCES users(id), recipient_id TEXT NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL, party_id TEXT, state TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS mp_invites_recipient ON mp_invites(recipient_id,state,expires);
CREATE TABLE IF NOT EXISTS mp_visits (
 user_id TEXT PRIMARY KEY REFERENCES users(id), host_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mp_presence (
 user_id TEXT PRIMARY KEY REFERENCES users(id), host_id TEXT NOT NULL REFERENCES users(id),
 scene TEXT NOT NULL, x REAL NOT NULL, z REAL NOT NULL, y REAL NOT NULL DEFAULT 0, yaw REAL NOT NULL, seen REAL NOT NULL,
 vx REAL NOT NULL DEFAULT 0, vz REAL NOT NULL DEFAULT 0, ct REAL);
CREATE TABLE IF NOT EXISTS mp_visit_notices (
 user_id TEXT PRIMARY KEY REFERENCES users(id), host_id TEXT NOT NULL REFERENCES users(id),
 reason TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mp_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id),
 text TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS mp_messages_room ON mp_messages(room,id);
CREATE TABLE IF NOT EXISTS coop_runs (
 id TEXT PRIMARY KEY, party_id TEXT NOT NULL, state TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS coop_members (
 run_id TEXT NOT NULL REFERENCES coop_runs(id), user_id TEXT NOT NULL REFERENCES users(id),
 claimed INTEGER NOT NULL DEFAULT 0, withdrawn INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(run_id,user_id));
CREATE INDEX IF NOT EXISTS coop_members_user ON coop_members(user_id);
'''
# Presence columns added after the first release, in order (guarded ALTERs, idempotent):
# y and the walk (0.11.4), then the social layer's place/floor and the interaction state ix.
PRESENCE_COLUMNS = (('y', 'REAL NOT NULL DEFAULT 0'), ('vx', 'REAL NOT NULL DEFAULT 0'), ('vz', 'REAL NOT NULL DEFAULT 0'), ('ct', 'REAL'),
                    ('place', 'TEXT'), ('floor', 'INTEGER'), ('ix', 'TEXT'))


class Invite(Mutation):
    username: str = Field(min_length=3, max_length=24, pattern=r'^[a-zA-Z0-9_]+$')
    # Knocks (kind 'knock', guest -> host) are made only by /v1/social/visit (server/friends.py).
    kind: Literal['village', 'party']


# Visitors may walk the host's village and the host's home interior.
VISIBLE_SCENES = ('village', 'home')

# A visit lasts while both sides keep polling; each guest poll moves its end this far ahead.
VISIT_SECONDS = 3600
# A host not heard from this long (crashed, connection lost; quitting and logging out end visits at
# once) has left: the guests' next poll sends them home. Longer than a slow screen change.
HOST_GONE_SECONDS = 20
# A guest not heard from this long has left the host's village: the place is free again and the
# guest's next sign-in starts at home.
GUEST_GONE_SECONDS = 60
# Other players are drawn in the village or home only this soon after their last poll.
VISIBLE_SECONDS = 6
# How long a guest's client is told why its visit ended (visit_ended).
NOTICE_SECONDS = 120


class IxState(Strict):
    """What the player's body is doing with an object (docs/design/INTERACTION_SOCKETS.md, WP17):
    stored and echoed to the other players in the same space, never interpreted here."""
    k: str = Field(min_length=1, max_length=24, pattern=r'^[a-z][a-z0-9_]*$')     # socket type
    p: Literal['enter', 'hold', 'act', 'exit']                                    # phase
    c: str = Field(default='', max_length=48, pattern=r'^[a-z0-9_]*$')            # clip set
    t0: float = Field(ge=0, le=1e10)                                              # sender clock at phase start
    o: str = Field(default='', max_length=64, pattern=r'^[A-Za-z0-9_:#.-]*$')     # object ref
    s: str = Field(default='', max_length=32, pattern=r'^[a-z0-9_]*$')            # socket id
    h: float = Field(default=0, ge=-.3, le=.3)                                    # height offset


class Presence(Strict):
    """Every field after t is optional and sent only when /health advertises it, so released
    clients (0.11.4/0.11.5) and older servers keep working: since with social_features 'chat2',
    place/floor with 'place', ix with interaction_sync 1. A 422 from this route lists the refused
    top-level fields ('fields'), so a client drops just that group."""
    scene: Literal['village', 'home', 'away'] = 'village'
    x: float = Field(default=0, ge=-100, le=100)
    z: float = Field(default=3, ge=-100, le=100)
    y: float = Field(default=0, ge=-20, le=40)
    yaw: float = Field(default=0, ge=-100, le=100)
    # The walker's velocity and the sender's own clock (seconds) when this spot was taken: other
    # clients draw the walk between spots at their true moments (remote_motion.gd).
    vx: float = Field(default=0, ge=-30, le=30)
    vz: float = Field(default=0, ge=-30, le=30)
    t: float | None = Field(default=None, ge=0, le=1e10)
    # Chat cursor (chat2): the newest line id this client has; 0 or -1 asks for history.
    since: int | None = Field(default=None, ge=-1, le=2**53)
    # Where the player is (place): finer than scene, shown in friends lists and rosters.
    place: Literal['village', 'home', 'workshop', 'room', 'expedition'] | None = None
    floor: int | None = Field(default=None, ge=0, le=9)
    ix: IxState | None = None


class Message(Mutation):
    text: str = Field(min_length=1, max_length=160)
    # No channel: the room before chat v2 (the party's, else the village's). whisper needs to.
    channel: Literal['local', 'party', 'global', 'whisper'] | None = None
    to: str | None = Field(default=None, min_length=3, max_length=24, pattern=r'^[a-zA-Z0-9_]+$')


class Target(Mutation):
    user_id: uuid.UUID


def fail(code, status=409):
    raise HTTPException(status, code)


class Multiplayer:
    def __init__(self, app, db, settings, clock, auth, mutate, money, profile, assets):
        self.db, self.clock = db, clock
        with db.read() as conn:
            conn.executescript(SCHEMA)
            columns = [r[1] for r in conn.execute('PRAGMA table_info(mp_presence)')]
            for name, kind in PRESENCE_COLUMNS:
                if name not in columns:
                    conn.execute('ALTER TABLE mp_presence ADD COLUMN '+name+' '+kind)
            social_db.ensure_schema(conn)
        self.chat = chat = Chat(db, settings, clock)

        def party_for(conn, user_id):
            return conn.execute('SELECT p.* FROM mp_parties p JOIN mp_members m ON m.party_id=p.id WHERE m.user_id=?', (user_id,)).fetchone()

        def active_coop(conn, user_id):
            return conn.execute("SELECT r.id FROM coop_runs r JOIN coop_members m ON r.id=m.run_id WHERE m.user_id=? AND m.withdrawn=0 AND r.status='active'", (user_id,)).fetchone()

        def visit_over(conn, visit, host_here=False):
            """Why a visit has ended without anyone ending it, or None while it goes on."""
            if visit['expires'] <= clock():
                return 'expired'
            host = None if host_here else conn.execute('SELECT seen FROM mp_presence WHERE user_id=?', (visit['host_id'],)).fetchone()
            if host and clock()-host['seen'] > HOST_GONE_SECONDS:
                return 'host_lost'
            if visit['expires'] < clock()+VISIT_SECONDS-GUEST_GONE_SECONDS:
                return 'lost'
            return None

        def host_for(conn, user_id):
            visit = conn.execute('SELECT host_id,expires FROM mp_visits WHERE user_id=?', (user_id,)).fetchone()
            return visit['host_id'] if visit and not visit_over(conn, visit) else user_id

        def end_visit(conn, guest_id, host_id, reason):
            # The guest's client hears why once (overview visit_ended) and goes home.
            conn.execute('DELETE FROM mp_visits WHERE user_id=?', (guest_id,))
            conn.execute('INSERT INTO mp_visit_notices VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET host_id=excluded.host_id,reason=excluded.reason,created=excluded.created', (guest_id, host_id, reason, clock()))

        def settle_visits(conn, user_id):
            """Ends this player's own visit, or the visits to this player's village, that are over."""
            visit = conn.execute('SELECT host_id,expires FROM mp_visits WHERE user_id=?', (user_id,)).fetchone()
            if visit:
                reason = visit_over(conn, visit)
                if reason:
                    end_visit(conn, user_id, visit['host_id'], reason)
                return
            # The host asking is here; only guests who went quiet leave.
            for guest in conn.execute('SELECT user_id,host_id,expires FROM mp_visits WHERE host_id=?', (user_id,)).fetchall():
                reason = visit_over(conn, guest, host_here=True)
                if reason:
                    end_visit(conn, guest['user_id'], user_id, reason)

        def drop_from_party(conn, user_id):
            party = party_for(conn, user_id)
            if not party:
                return
            conn.execute('DELETE FROM mp_members WHERE user_id=?', (user_id,))
            next_member = conn.execute('SELECT user_id FROM mp_members WHERE party_id=? ORDER BY joined,user_id LIMIT 1', (party['id'],)).fetchone()
            if next_member and party['leader_id'] == user_id:
                conn.execute('UPDATE mp_parties SET leader_id=? WHERE id=?', (next_member[0], party['id']))
            elif not next_member:
                conn.execute('DELETE FROM mp_parties WHERE id=?', (party['id'],))
            conn.execute("UPDATE mp_invites SET state='revoked' WHERE party_id=? AND sender_id=? AND state='pending'", (party['id'], user_id))

        def leave(conn, user_id):
            """The player logged out or quit the game: gone from every screen at once. Guests in this
            player's village go home (told why), this player's own visit ends, pending village
            invitations from this player lapse, and the party goes on without this player (an
            expedition under way keeps its place, to resume after the next sign-in)."""
            seen = conn.execute('SELECT seen FROM mp_presence WHERE user_id=?', (user_id,)).fetchone()
            if seen:
                social_db.remember_seen(conn, user_id, seen[0])
            conn.execute('DELETE FROM mp_presence WHERE user_id=?', (user_id,))
            conn.execute('DELETE FROM mp_visits WHERE user_id=?', (user_id,))
            for guest in conn.execute('SELECT user_id FROM mp_visits WHERE host_id=?', (user_id,)).fetchall():
                end_visit(conn, guest['user_id'], user_id, 'left')
            conn.execute("UPDATE mp_invites SET state='revoked' WHERE sender_id=? AND kind IN ('village','knock') AND state='pending'", (user_id,))
            if not active_coop(conn, user_id):
                drop_from_party(conn, user_id)

        def room_for(conn, user_id):
            party = party_for(conn, user_id)
            return 'party:'+party['id'] if party else 'village:'+host_for(conn, user_id)

        def chat_rooms(conn, user_id):
            """(room before chat v2, village room, party room or None)."""
            party = party_for(conn, user_id)
            village_room = 'village:'+host_for(conn, user_id)
            party_room = 'party:'+party['id'] if party else None
            return party_room or village_room, village_room, party_room

        def start_visit(conn, guest_id, host_id):
            """The guest walks into the host's village: an accepted invitation, a knock the host let
            in, or a friend's drop-in (server/friends.py). The host must still be here and at home
            (not gone, not off visiting); the guest's next village poll follows the new host."""
            host_seen = conn.execute('SELECT seen FROM mp_presence WHERE user_id=?', (host_id,)).fetchone()
            if host_seen and clock()-host_seen['seen'] > HOST_GONE_SECONDS or host_for(conn, host_id) != host_id:
                fail('host_offline')
            settle_visits(conn, host_id)
            if conn.execute('SELECT count(*) FROM mp_visits WHERE host_id=? AND user_id!=? AND expires>?', (host_id, guest_id, clock())).fetchone()[0] >= 2:
                fail('village_full')
            conn.execute('INSERT INTO mp_visits VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET host_id=excluded.host_id,expires=excluded.expires', (guest_id, host_id, clock()+VISIT_SECONDS))
            conn.execute('DELETE FROM mp_presence WHERE user_id=?', (guest_id,))
            conn.execute('DELETE FROM mp_visit_notices WHERE user_id=?', (guest_id,))

        def party_public(conn, user_id):
            party = party_for(conn, user_id)
            if not party:
                return None
            members = [dict(r) for r in conn.execute('SELECT u.id,u.username,m.joined FROM mp_members m JOIN users u ON u.id=m.user_id WHERE m.party_id=? ORDER BY m.joined,u.id', (party['id'],))]
            for member in members:
                presence = conn.execute('SELECT seen FROM mp_presence WHERE user_id=?', (member['id'],)).fetchone()
                member['online'] = bool(presence and clock()-presence['seen'] < coop.PRESENCE_SECONDS)
            run = conn.execute('SELECT status FROM coop_runs WHERE id=?', (party['run_id'],)).fetchone() if party['run_id'] else None
            participant = conn.execute('SELECT withdrawn FROM coop_members WHERE run_id=? AND user_id=?', (party['run_id'], user_id)).fetchone() if run else None
            return dict(id=party['id'], leader_id=party['leader_id'], members=members, max_members=3,
                        run_id=party['run_id'], run_status=run['status'] if run else None,
                        can_join_run=bool(participant and not participant['withdrawn']))

        def overview(conn, user, messages=True, blocked=None):
            host = host_for(conn, user['id'])
            host_name = conn.execute('SELECT username FROM users WHERE id=?', (host,)).fetchone()[0]
            blocked = social_db.blocked_ids(conn, user['id']) if blocked is None else blocked
            offers = [dict(r) for r in conn.execute("SELECT i.id,i.kind,i.sender_id,u.username AS sender,i.expires FROM mp_invites i JOIN users u ON u.id=i.sender_id WHERE recipient_id=? AND state='pending' AND expires>? ORDER BY i.created DESC LIMIT 40", (user['id'], clock()))]
            # Knocks are listed apart: a released game would show one as a party invitation.
            invites = [i for i in offers if i['kind'] != 'knock'][:20]
            knocks = [{k: i[k] for k in ('id', 'sender_id', 'sender', 'expires')} for i in offers if i['kind'] == 'knock' and i['sender_id'] not in blocked][:20]
            pending = [dict(r) for r in conn.execute("SELECT r.id FROM coop_runs r JOIN coop_members m ON r.id=m.run_id WHERE m.user_id=? AND m.claimed=0 AND m.withdrawn=0 AND r.status='won' ORDER BY r.created LIMIT 20", (user['id'],))]
            # chat2 clients read the chat block instead (chat.deliver).
            messages = chat.legacy(conn, room_for(conn, user['id']), blocked) if messages else []
            # Why the last visit ended (the host left, lost the connection or ended it), for a while.
            ended = None
            if host == user['id']:
                notice = conn.execute('SELECT n.host_id,n.reason,n.created,u.username FROM mp_visit_notices n JOIN users u ON u.id=n.host_id WHERE n.user_id=? AND n.created>?', (user['id'], clock()-NOTICE_SECONDS)).fetchone()
                if notice:
                    ended = dict(host_id=notice['host_id'], host_name=notice['username'], reason=notice['reason'], at=notice['created'])
            data = dict(self_id=user['id'], host_id=host, host_name=host_name, visiting=host != user['id'],
                        party=party_public(conn, user['id']), invites=invites, pending_rewards=pending, messages=messages,
                        visit_ended=ended)
            if knocks:
                data['knocks'] = knocks
            return data

        def look(conn, user_id):
            # Every place that draws another player reads the saved look and its version; clients
            # rebuild a body only when avatar_version changes.
            saved = profile(conn, user_id)
            return {'avatar': saved['avatar'], 'avatar_version': saved['version']}

        def live_looks(conn, data):
            # A co-op run stores each look as it was at the start; the answer shows the look saved now.
            for player in data['players']:
                player.update(look(conn, player['id']))
            return data

        def village(conn, user, scene='village', blocked=frozenset()):
            host = host_for(conn, user['id'])
            objects = [object_shape.listed(dict(r)) for r in conn.execute("SELECT o.id,o.name,o.color,o.version,o.state,o.x,o.z,o.rotation,COALESCE(l.room,'village') AS room,EXISTS(SELECT 1 FROM studio_assets WHERE asset_id=o.asset_id) AS studio,(SELECT version FROM studio_runtime WHERE object_id=o.id) AS runtime_version," + object_paint.version_column('o.id') + " AS paint_version," + object_shape.column('o.id') + " AS shape FROM objects o LEFT JOIN furniture_locations l ON l.object_id=o.id WHERE o.owner_id=? AND o.state='placed' AND COALESCE(l.room,'village')=? ORDER BY o.id", (host, scene))]
            players = []
            for row in conn.execute("SELECT p.*,u.username FROM mp_presence p JOIN users u ON u.id=p.user_id WHERE p.host_id=? AND p.scene=? AND p.seen>? AND (p.user_id=? OR EXISTS(SELECT 1 FROM mp_visits v WHERE v.user_id=p.user_id AND v.host_id=? AND v.expires>?))", (host, scene, clock()-VISIBLE_SECONDS, host, host, clock())):
                if row['user_id'] in blocked:
                    continue
                # t: the sender's clock when the spot was taken (older games send none: seen).
                player = dict(id=row['user_id'], username=row['username'], x=row['x'], z=row['z'], y=row['y'], yaw=row['yaw'],
                              vx=row['vx'], vz=row['vz'], t=row['ct'], seen=row['seen'], **look(conn, row['user_id']))
                # The interaction state only when that player sent one (older replies are unchanged).
                if row['ix']:
                    player['ix'] = json.loads(row['ix'])
                players.append(player)
            row = conn.execute('SELECT state FROM homesteads WHERE user_id=?', (host,)).fetchone()
            life = homestead.public(json.loads(row[0]) if row else homestead.initial(), clock())
            # Visitors can see crops, not the host's private inventory or fishing outcome.
            crops = {'version': life['version'], 'plots': life['plots'], 'server_time': clock()}
            return dict(host_id=host, scene=scene, objects=objects, players=players, crops=crops if scene == 'village' else None)

        @app.get('/v1/social')
        def social(request: Request):
            with db.read() as conn:
                return overview(conn, auth(conn, request))

        @app.post('/v1/social/presence')
        def presence(body: Presence, request: Request):
            # Positions, visit times and resident moves: the next poll writes them again (no disk wait).
            if hasattr(app.state, 'friends'):
                app.state.friends.meter.tick()
            with db.write_then_read(durable=False) as phase:
                conn = phase.conn
                user = auth(conn, request)
                # A visit whose host is gone (or whose guest was away too long) ends here; a guest
                # still here keeps the visit going.
                settle_visits(conn, user['id'])
                host = host_for(conn, user['id'])
                if host != user['id']:
                    conn.execute('UPDATE mp_visits SET expires=? WHERE user_id=?', (clock()+VISIT_SECONDS, user['id']))
                ix = body.ix.model_dump_json() if body.ix else None
                conn.execute('INSERT INTO mp_presence(user_id,host_id,scene,x,z,y,yaw,seen,vx,vz,ct,place,floor,ix) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET host_id=excluded.host_id,scene=excluded.scene,x=excluded.x,z=excluded.z,y=excluded.y,yaw=excluded.yaw,seen=excluded.seen,vx=excluded.vx,vz=excluded.vz,ct=excluded.ct,place=excluded.place,floor=excluded.floor,ix=excluded.ix',
                             (user['id'], host, body.scene, body.x, body.z, body.y, body.yaw, clock(), body.vx, body.vz, body.t, body.place, body.floor, ix))
                # The host's residents' home versions (npc_homes.py), so visitors follow their rooms too.
                homes = app.state.npc_homes.versions_in(conn, host) if hasattr(app.state, 'npc_homes') else {}
                # The rest is read after the commit: some 240 polls a second share SQLite's one writer slot.
                phase.commit()
                chat2 = body.since is not None
                blocked = social_db.blocked_ids(conn, user['id'])
                space = village(conn, user, body.scene, blocked) if body.scene in VISIBLE_SCENES else None
                reply = {**overview(conn, user, messages=not chat2, blocked=blocked), 'village': space if body.scene == 'village' else None, 'space': space, 'npc_homes': homes}
                if chat2:
                    _, village_room, party_room = chat_rooms(conn, user['id'])
                    del reply['messages']
                    reply['chat'] = chat.deliver(conn, user['id'], body.since, chat.rooms_for(village_room, party_room), blocked)
                    reply['social'] = app.state.friends.presence_block(conn, user['id']) if hasattr(app.state, 'friends') else None
            chat.maybe_prune()
            # Straight to JSON: FastAPI's generic encoder walks every value of this large reply first.
            return JSONResponse(reply)

        @app.post('/v1/social/offline')
        def offline(request: Request):
            # The game is closing (window closed, quit from the menu): to everyone else, it left.
            with db.transaction() as conn:
                leave(conn, auth(conn, request)['id'])
                return {'ok': True}

        @app.post('/v1/social/invites')
        def invite(body: Invite, request: Request):
            def create(conn, user):
                target = conn.execute('SELECT id FROM users WHERE username=?', (body.username.lower(),)).fetchone()
                # A block either way looks the same as an unknown name.
                if not target or target['id'] == user['id'] or social_db.blocked_between(conn, user['id'], target['id']):
                    fail('invite_target_unavailable', 404)
                party_id = None
                if body.kind == 'party':
                    party = party_for(conn, user['id'])
                    if not party or party['leader_id'] != user['id']:
                        fail('party_leader_required', 403)
                    if active_coop(conn, user['id']):
                        fail('party_expedition_active')
                    party_id = party['id']
                elif host_for(conn, user['id']) != user['id']:
                    fail('return_home_before_inviting')
                if conn.execute("SELECT count(*) FROM mp_invites WHERE sender_id=? AND state='pending' AND expires>?", (user['id'], clock())).fetchone()[0] >= 10:
                    fail('too_many_invitations', 429)
                conn.execute("UPDATE mp_invites SET state='replaced' WHERE sender_id=? AND recipient_id=? AND kind=? AND state='pending'", (user['id'], target['id'], body.kind))
                social_db.bump(conn, target['id'])
                invite_id = str(uuid.uuid4())
                conn.execute("INSERT INTO mp_invites VALUES (?,?,?,?,?,'pending',?,?)", (invite_id, user['id'], target['id'], body.kind, party_id, clock()+600, clock()))
                return {'id': invite_id}
            return mutate(request, body, 'social_invite', create)

        @app.post('/v1/social/invites/{invite_id}/{decision}')
        def answer(invite_id: str, decision: Literal['accept', 'decline'], body: Mutation, request: Request):
            def apply(conn, user):
                row = conn.execute("SELECT * FROM mp_invites WHERE id=? AND recipient_id=? AND state='pending' AND expires>?", (invite_id, user['id'], clock())).fetchone()
                if not row or social_db.blocked_between(conn, user['id'], row['sender_id']):
                    fail('invitation_expired', 404)
                knocked = None
                if decision == 'accept':
                    if active_coop(conn, user['id']):
                        fail('party_expedition_active')
                    if row['kind'] == 'knock':
                        # The host lets a knocking player in: straight in from the village, else an
                        # ordinary invitation, which the guest's game accepts once it is in the village.
                        guest = row['sender_id']
                        spot = conn.execute('SELECT scene,seen FROM mp_presence WHERE user_id=?', (guest,)).fetchone()
                        if spot and spot['scene'] == 'village' and clock()-spot['seen'] < HOST_GONE_SECONDS and not active_coop(conn, guest):
                            start_visit(conn, guest, user['id'])
                            knocked = 'visiting'
                        else:
                            if host_for(conn, user['id']) != user['id']:
                                fail('return_home_before_inviting')
                            conn.execute("UPDATE mp_invites SET state='replaced' WHERE sender_id=? AND recipient_id=? AND kind='village' AND state='pending'", (user['id'], guest))
                            conn.execute("INSERT INTO mp_invites VALUES (?,?,?,'village',NULL,'pending',?,?)", (str(uuid.uuid4()), user['id'], guest, clock()+600, clock()))
                            knocked = 'invited'
                        social_db.bump(conn, guest)
                    elif row['kind'] == 'party':
                        party = conn.execute('SELECT * FROM mp_parties WHERE id=? AND leader_id=?', (row['party_id'], row['sender_id'])).fetchone()
                        if not party:
                            fail('party_unavailable')
                        if party_for(conn, user['id']):
                            fail('already_in_party')
                        if active_coop(conn, row['sender_id']):
                            fail('party_expedition_active')
                        if conn.execute('SELECT count(*) FROM mp_members WHERE party_id=?', (party['id'],)).fetchone()[0] >= 3:
                            fail('party_full')
                        conn.execute('INSERT INTO mp_members VALUES (?,?,?)', (user['id'], party['id'], clock()))
                    else:
                        start_visit(conn, user['id'], row['sender_id'])
                conn.execute('UPDATE mp_invites SET state=? WHERE id=?', (decision, invite_id))
                data = overview(conn, user)
                if knocked:
                    data['knock'] = knocked
                return data
            return mutate(request, body, 'invite:'+invite_id+':'+decision, apply)

        @app.post('/v1/social/home')
        def home(body: Mutation, request: Request):
            def apply(conn, user):
                conn.execute('DELETE FROM mp_visits WHERE user_id=?', (user['id'],))
                conn.execute('DELETE FROM mp_presence WHERE user_id=?', (user['id'],))
                return {'ok': True}
            return mutate(request, body, 'social_home', apply)

        @app.post('/v1/social/eject')
        def eject(body: Target, request: Request):
            def apply(conn, user):
                if conn.execute('SELECT 1 FROM mp_visits WHERE user_id=? AND host_id=?', (str(body.user_id), user['id'])).fetchone():
                    end_visit(conn, str(body.user_id), user['id'], 'ended')
                return {'ok': True}
            return mutate(request, body, 'social_eject', apply)

        @app.post('/v1/social/messages')
        def message(body: Message, request: Request):
            # Not through mutate(): a chat line is its own idempotency record (mp_messages.request_id),
            # so always-on chat adds no requests or audit rows. Filter, limits, channels: server/chat.py.
            with db.transaction() as conn:
                user = auth(conn, request)
                legacy_room, village_room, party_room = chat_rooms(conn, user['id'])
                reply = chat.post(conn, user, body, request.client.host if request.client else 'unknown', legacy_room, village_room, party_room)
            chat.maybe_prune()
            return reply

        @app.post('/v1/party')
        def create_party(body: Mutation, request: Request):
            def create(conn, user):
                if party_for(conn, user['id']):
                    fail('already_in_party')
                if active_coop(conn, user['id']):
                    fail('party_expedition_active')
                party_id = str(uuid.uuid4())
                conn.execute('INSERT INTO mp_parties VALUES (?,?,NULL,?)', (party_id, user['id'], clock()))
                conn.execute('INSERT INTO mp_members VALUES (?,?,?)', (user['id'], party_id, clock()))
                return party_public(conn, user['id'])
            return mutate(request, body, 'party_create', create)

        @app.post('/v1/party/leave')
        def leave_party(body: Mutation, request: Request):
            def apply(conn, user):
                if party_for(conn, user['id']) and active_coop(conn, user['id']):
                    fail('leave_expedition_first')
                drop_from_party(conn, user['id'])
                return {'ok': True}
            return mutate(request, body, 'party_leave', apply)

        @app.post('/v1/party/runs')
        def start(body: RunStart, request: Request):
            def create(conn, user):
                party = party_for(conn, user['id'])
                if not party or party['leader_id'] != user['id']:
                    fail('party_leader_required', 403)
                if body.chapter_id:
                    fail('coop_story_not_available')
                if party['run_id']:
                    previous = conn.execute('SELECT status FROM coop_runs WHERE id=?', (party['run_id'],)).fetchone()
                    if previous and previous[0] == 'active':
                        fail('party_expedition_active')
                members = [dict(r) for r in conn.execute('SELECT u.id,u.username FROM mp_members m JOIN users u ON u.id=m.user_id WHERE m.party_id=? ORDER BY joined,u.id', (party['id'],))]
                if len(members) < 2:
                    fail('party_needs_two_players')
                for member in members:
                    if active_coop(conn, member['id']):
                        fail('party_expedition_active')
                    if conn.execute("SELECT 1 FROM runs WHERE owner_id=? AND status='active'", (member['id'],)).fetchone():
                        fail('member_has_solo_expedition')
                    presence = conn.execute("SELECT seen,scene FROM mp_presence WHERE user_id=?", (member['id'],)).fetchone()
                    if not presence or clock()-presence['seen'] >= coop.PRESENCE_SECONDS or presence['scene'] != 'village':
                        fail('party_members_not_in_village')
                    member['avatar'] = profile(conn, member['id'])['avatar']
                run_id = str(uuid.uuid4())
                state = coop.new_world(secrets.randbits(32), clock(), settings.day_seconds, members, body.map_id, body.difficulty)
                conn.execute("INSERT INTO coop_runs VALUES (?,?,?,'active',?)", (run_id, party['id'], json.dumps(state), clock()))
                for member in members:
                    conn.execute('INSERT INTO coop_members(run_id,user_id) VALUES (?,?)', (run_id, member['id']))
                conn.execute('UPDATE mp_parties SET run_id=? WHERE id=?', (run_id, party['id']))
                return {'id': run_id}
            return mutate(request, body, 'party_start', create)

        def owned_run(conn, user_id, run_id):
            row = conn.execute('SELECT r.*,m.claimed,m.withdrawn FROM coop_runs r JOIN coop_members m ON m.run_id=r.id WHERE r.id=? AND m.user_id=?', (run_id, user_id)).fetchone()
            if not row:
                fail('run_not_found', 404)
            return row, json.loads(row['state'])

        def save(conn, run_id, state):
            conn.execute('UPDATE coop_runs SET state=?,status=? WHERE id=?', (json.dumps(state), state['world']['status'], run_id))

        @app.get('/v1/coop/runs/{run_id}')
        def snapshot(run_id: str, request: Request):
            with db.transaction() as conn:
                user = auth(conn, request)
                row, state = owned_run(conn, user['id'], run_id)
                coop.advance(state, clock())
                save(conn, run_id, state)
                return {**live_looks(conn, coop.public(state, user['id'], clock())), 'id': run_id, 'claimed': bool(row['claimed'])}

        @app.post('/v1/coop/runs/{run_id}/input')
        def input_run(run_id: str, body: Input, request: Request):
            with db.transaction() as conn:
                user = auth(conn, request)
                row, state = owned_run(conn, user['id'], run_id)
                actor = state['players'][user['id']]
                if actor['withdrawn']:
                    fail('expedition_left')
                if body.sequence <= actor['sequence']:
                    fail('stale_input')
                coop.apply_input(state, user['id'], body, clock())
                save(conn, run_id, state)
                return {**live_looks(conn, coop.public(state, user['id'], clock())), 'id': run_id, 'claimed': bool(row['claimed'])}

        @app.post('/v1/coop/runs/{run_id}/abandon')
        def abandon(run_id: str, body: Mutation, request: Request):
            def apply(conn, user):
                row, state = owned_run(conn, user['id'], run_id)
                if state['world']['status'] == 'active':
                    state['players'][user['id']]['withdrawn'] = True
                    conn.execute('UPDATE coop_members SET withdrawn=1 WHERE run_id=? AND user_id=?', (run_id, user['id']))
                    coop.finish(state)
                    save(conn, run_id, state)
                return {'ok': True}
            return mutate(request, body, 'coop_abandon:'+run_id, apply)

        @app.post('/v1/coop/runs/{run_id}/claim')
        def claim(run_id: str, body: Mutation, request: Request):
            def apply(conn, user):
                row, state = owned_run(conn, user['id'], run_id)
                if row['withdrawn'] or row['status'] != 'won':
                    fail('run_not_won')
                if row['claimed']:
                    fail('reward_already_claimed')
                reward = state['world']['reward']
                money(conn, user['id'], reward, 'coop_reward', run_id)
                conn.execute('UPDATE coop_members SET claimed=1 WHERE run_id=? AND user_id=?', (run_id, user['id']))
                return {'reward': reward}
            return mutate(request, body, 'coop_claim:'+run_id, apply)

        def visible_object(conn, user_id, object_id):
            # Also the pieces the host's residents have put up in their homes (npc_homes.py), not the stored ones.
            row = conn.execute("SELECT o.* FROM objects o LEFT JOIN furniture_locations l ON l.object_id=o.id WHERE o.id=? AND o.owner_id=? AND (o.state='placed' AND COALESCE(l.room,'village') IN ('village','home') OR o.state='gifted' AND EXISTS(SELECT 1 FROM npc_items i WHERE i.object_id=o.id AND i.state='placed'))", (object_id, host_for(conn, user_id))).fetchone()
            if not row:
                fail('object_not_found', 404)
            return row

        @app.get('/v1/social/village/objects/{object_id}/model')
        def model(object_id: str, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                obj = visible_object(conn, user['id'], object_id)
                asset = conn.execute('SELECT * FROM assets WHERE id=?', (obj['asset_id'],)).fetchone()
                return Response(read_glb(assets, asset['relative_path'], asset['digest']), media_type='model/gltf-binary', headers={'Cache-Control': 'no-store'})

        @app.get('/v1/social/village/objects/{object_id}/assembly')
        def assembly(object_id: str, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                obj = visible_object(conn, user['id'], object_id)
                row = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
                if not row:
                    fail('not_studio_object', 404)
                value = interactions.apply(conn, object_id, json.loads(row[0]))
                runtime = conn.execute('SELECT * FROM studio_runtime WHERE object_id=?', (object_id,)).fetchone()
                bindings = json.loads(runtime['bindings'])
                for part in value['plan']['parts']:
                    part.update(bindings.get(part['id'], {}))
                # Visitors see the host's interaction too (only when one is set: older replies are unchanged).
                extra = {'interaction': value['interaction']} if 'interaction' in value else {}
                return interactions.for_client(request, {'schema': value['schema'], 'plan': value['plan'], 'program': interactions.compat(value),
                        'provenance': {'geometry': value.get('provenance', {}).get('geometry')},
                        'runtime': dict(state=json.loads(runtime['state']), colors=json.loads(runtime['colors']), bindings=bindings, version=runtime['version']), 'object_version': obj['version'], **extra})

        @app.get('/v1/social/village/objects/{object_id}/parts/{part_id}')
        def part(object_id: str, part_id: str, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                obj = visible_object(conn, user['id'], object_id)
                row = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
                value = json.loads(row[0]) if row else {}
                entry = next((p for p in value.get('plan', {}).get('parts', []) if p['id'] == part_id), None)
                if not entry:
                    fail('part_not_found', 404)
                return Response(read_glb(assets, entry['file'], entry['sha256']), media_type='model/gltf-binary', headers={'Cache-Control': 'no-store'})

        # The painted surface follows the same rule as the model: only furniture the host has
        # placed where guests can see it (village or home) is readable during a visit.
        @app.get('/v1/social/village/objects/{object_id}/paint')
        def paint(object_id: str, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                visible_object(conn, user['id'], object_id)
                return object_paint.response(conn, assets, object_id)

        self.active_coop = active_coop
        self.host_for = host_for
        self.leave = leave
        self.start_visit = start_visit
        self.end_visit = end_visit
        self.party_for = party_for
        self.overview = overview
        self.HOST_GONE_SECONDS = HOST_GONE_SECONDS

