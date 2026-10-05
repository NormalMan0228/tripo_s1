"""Invited village visits and durable three-member cooperative expeditions."""
import json
import secrets
import uuid
from typing import Literal
from fastapi import Request, HTTPException
from fastapi.responses import Response
from pydantic import Field
from .models import Strict, Mutation, Input, RunStart
from .stored_assets import read_glb
from . import coop, homestead

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
 scene TEXT NOT NULL, x REAL NOT NULL, z REAL NOT NULL, y REAL NOT NULL DEFAULT 0, yaw REAL NOT NULL, seen REAL NOT NULL);
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
'''


class Invite(Mutation):
    username: str = Field(min_length=3, max_length=24, pattern=r'^[a-zA-Z0-9_]+$')
    kind: Literal['village', 'party']


# Visitors may walk the host's village and the host's home interior.
VISIBLE_SCENES = ('village', 'home')


class Presence(Strict):
    scene: Literal['village', 'home', 'away'] = 'village'
    x: float = Field(default=0, ge=-100, le=100)
    z: float = Field(default=3, ge=-100, le=100)
    y: float = Field(default=0, ge=-20, le=40)
    yaw: float = Field(default=0, ge=-100, le=100)


class Message(Mutation):
    text: str = Field(min_length=1, max_length=160)


class Target(Mutation):
    user_id: uuid.UUID


def fail(code, status=409):
    raise HTTPException(status, code)


class Multiplayer:
    def __init__(self, app, db, settings, clock, auth, mutate, money, profile, assets):
        self.db, self.clock = db, clock
        with db.read() as conn:
            conn.executescript(SCHEMA)
            if 'y' not in [r[1] for r in conn.execute('PRAGMA table_info(mp_presence)')]:
                conn.execute('ALTER TABLE mp_presence ADD COLUMN y REAL NOT NULL DEFAULT 0')

        def party_for(conn, user_id):
            return conn.execute('SELECT p.* FROM mp_parties p JOIN mp_members m ON m.party_id=p.id WHERE m.user_id=?', (user_id,)).fetchone()

        def active_coop(conn, user_id):
            return conn.execute("SELECT r.id FROM coop_runs r JOIN coop_members m ON r.id=m.run_id WHERE m.user_id=? AND m.withdrawn=0 AND r.status='active'", (user_id,)).fetchone()

        def host_for(conn, user_id):
            visit = conn.execute('SELECT host_id FROM mp_visits WHERE user_id=? AND expires>?', (user_id, clock())).fetchone()
            return visit['host_id'] if visit else user_id

        def room_for(conn, user_id):
            party = party_for(conn, user_id)
            return 'party:'+party['id'] if party else 'village:'+host_for(conn, user_id)

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

        def overview(conn, user):
            host = host_for(conn, user['id'])
            host_name = conn.execute('SELECT username FROM users WHERE id=?', (host,)).fetchone()[0]
            invites = [dict(r) for r in conn.execute("SELECT i.id,i.kind,i.sender_id,u.username AS sender,i.expires FROM mp_invites i JOIN users u ON u.id=i.sender_id WHERE recipient_id=? AND state='pending' AND expires>? ORDER BY i.created DESC LIMIT 20", (user['id'], clock()))]
            pending = [dict(r) for r in conn.execute("SELECT r.id FROM coop_runs r JOIN coop_members m ON r.id=m.run_id WHERE m.user_id=? AND m.claimed=0 AND m.withdrawn=0 AND r.status='won' ORDER BY r.created LIMIT 20", (user['id'],))]
            room = room_for(conn, user['id'])
            messages = [dict(r) for r in conn.execute('SELECT e.id,u.username,e.text,e.created FROM mp_messages e JOIN users u ON u.id=e.user_id WHERE room=? AND e.created>? ORDER BY e.id DESC LIMIT 20', (room, clock()-3600))][::-1]
            return dict(self_id=user['id'], host_id=host, host_name=host_name, visiting=host != user['id'],
                        party=party_public(conn, user['id']), invites=invites, pending_rewards=pending, messages=messages)

        def village(conn, user, scene='village'):
            host = host_for(conn, user['id'])
            objects = [dict(r) for r in conn.execute("SELECT o.id,o.name,o.color,o.version,o.state,o.x,o.z,o.rotation,COALESCE(l.room,'village') AS room,EXISTS(SELECT 1 FROM studio_assets WHERE asset_id=o.asset_id) AS studio,(SELECT version FROM studio_runtime WHERE object_id=o.id) AS runtime_version FROM objects o LEFT JOIN furniture_locations l ON l.object_id=o.id WHERE o.owner_id=? AND o.state='placed' AND COALESCE(l.room,'village')=? ORDER BY o.id", (host, scene))]
            players = []
            for row in conn.execute("SELECT p.*,u.username FROM mp_presence p JOIN users u ON u.id=p.user_id WHERE p.host_id=? AND p.scene=? AND p.seen>? AND (p.user_id=? OR EXISTS(SELECT 1 FROM mp_visits v WHERE v.user_id=p.user_id AND v.host_id=? AND v.expires>?))", (host, scene, clock()-coop.PRESENCE_SECONDS, host, host, clock())):
                players.append(dict(id=row['user_id'], username=row['username'], x=row['x'], z=row['z'], y=row['y'], yaw=row['yaw'], avatar=profile(conn, row['user_id'])['avatar']))
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
            with db.transaction() as conn:
                user = auth(conn, request)
                host = host_for(conn, user['id'])
                conn.execute('INSERT INTO mp_presence(user_id,host_id,scene,x,z,y,yaw,seen) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET host_id=excluded.host_id,scene=excluded.scene,x=excluded.x,z=excluded.z,y=excluded.y,yaw=excluded.yaw,seen=excluded.seen', (user['id'], host, body.scene, body.x, body.z, body.y, body.yaw, clock()))
                space = village(conn, user, body.scene) if body.scene in VISIBLE_SCENES else None
                return {**overview(conn, user), 'village': space if body.scene == 'village' else None, 'space': space}

        @app.post('/v1/social/invites')
        def invite(body: Invite, request: Request):
            def create(conn, user):
                target = conn.execute('SELECT id FROM users WHERE username=?', (body.username.lower(),)).fetchone()
                if not target or target['id'] == user['id']:
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
                invite_id = str(uuid.uuid4())
                conn.execute("INSERT INTO mp_invites VALUES (?,?,?,?,?,'pending',?,?)", (invite_id, user['id'], target['id'], body.kind, party_id, clock()+600, clock()))
                return {'id': invite_id}
            return mutate(request, body, 'social_invite', create)

        @app.post('/v1/social/invites/{invite_id}/{decision}')
        def answer(invite_id: str, decision: Literal['accept', 'decline'], body: Mutation, request: Request):
            def apply(conn, user):
                row = conn.execute("SELECT * FROM mp_invites WHERE id=? AND recipient_id=? AND state='pending' AND expires>?", (invite_id, user['id'], clock())).fetchone()
                if not row:
                    fail('invitation_expired', 404)
                if decision == 'accept':
                    if active_coop(conn, user['id']):
                        fail('party_expedition_active')
                    if row['kind'] == 'party':
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
                        if conn.execute('SELECT count(*) FROM mp_visits WHERE host_id=? AND user_id!=? AND expires>?', (row['sender_id'], user['id'], clock())).fetchone()[0] >= 2:
                            fail('village_full')
                        conn.execute('INSERT INTO mp_visits VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET host_id=excluded.host_id,expires=excluded.expires', (user['id'], row['sender_id'], clock()+3600))
                        conn.execute('DELETE FROM mp_presence WHERE user_id=?', (user['id'],))
                conn.execute('UPDATE mp_invites SET state=? WHERE id=?', (decision, invite_id))
                return overview(conn, user)
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
                conn.execute('DELETE FROM mp_visits WHERE user_id=? AND host_id=?', (str(body.user_id), user['id']))
                return {'ok': True}
            return mutate(request, body, 'social_eject', apply)

        @app.post('/v1/social/messages')
        def message(body: Message, request: Request):
            def apply(conn, user):
                value = ''.join(c for c in body.text.strip() if c.isprintable())
                if not value:
                    fail('empty_message', 422)
                last = conn.execute('SELECT max(created) FROM mp_messages WHERE user_id=?', (user['id'],)).fetchone()[0]
                if last is not None and clock()-last < 1:
                    fail('message_rate_limited', 429)
                conn.execute('INSERT INTO mp_messages(room,user_id,text,created) VALUES (?,?,?,?)', (room_for(conn, user['id']), user['id'], value, clock()))
                conn.execute('DELETE FROM mp_messages WHERE created<?', (clock()-86400,))
                return {'ok': True}
            return mutate(request, body, 'social_message', apply)

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
                party = party_for(conn, user['id'])
                if not party:
                    return {'ok': True}
                if active_coop(conn, user['id']):
                    fail('leave_expedition_first')
                conn.execute('DELETE FROM mp_members WHERE user_id=?', (user['id'],))
                next_member = conn.execute('SELECT user_id FROM mp_members WHERE party_id=? ORDER BY joined,user_id LIMIT 1', (party['id'],)).fetchone()
                if next_member and party['leader_id'] == user['id']:
                    conn.execute('UPDATE mp_parties SET leader_id=? WHERE id=?', (next_member[0], party['id']))
                elif not next_member:
                    conn.execute('DELETE FROM mp_parties WHERE id=?', (party['id'],))
                conn.execute("UPDATE mp_invites SET state='revoked' WHERE party_id=? AND sender_id=? AND state='pending'", (party['id'], user['id']))
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
                return {**coop.public(state, user['id'], clock()), 'id': run_id, 'claimed': bool(row['claimed'])}

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
                return {**coop.public(state, user['id'], clock()), 'id': run_id, 'claimed': bool(row['claimed'])}

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
            row = conn.execute("SELECT o.* FROM objects o LEFT JOIN furniture_locations l ON l.object_id=o.id WHERE o.id=? AND o.owner_id=? AND o.state='placed' AND COALESCE(l.room,'village') IN ('village','home')", (object_id, host_for(conn, user_id))).fetchone()
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
                value = json.loads(row[0])
                runtime = conn.execute('SELECT * FROM studio_runtime WHERE object_id=?', (object_id,)).fetchone()
                bindings = json.loads(runtime['bindings'])
                for part in value['plan']['parts']:
                    part.update(bindings.get(part['id'], {}))
                return {'schema': value['schema'], 'plan': value['plan'], 'program': value['program'],
                        'provenance': {'geometry': value.get('provenance', {}).get('geometry')},
                        'runtime': dict(state=json.loads(runtime['state']), colors=json.loads(runtime['colors']), bindings=bindings, version=runtime['version']), 'object_version': obj['version']}

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

        self.active_coop = active_coop

