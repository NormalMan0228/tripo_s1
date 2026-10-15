"""Who may be inside a player's home (docs/contracts/SERVER_CONTRACTS_KO.md, decided 2026-10-16).

The owner always. Anyone else (a guest visiting the owner's village) only while the owner is in the
home: nobody gets in while the owner is away, a guest inside follows the owner out within
OWNER_GRACE seconds, the owner may lock the door (off by default; a lock keeps new guests out but
not the ones already inside), and the owner may send one guest out of the home (the village visit
goes on, the home stays shut to that guest for EJECT_SECONDS). Leaving is always free.

The rules are enforced in /v1/social/presence (server/multiplayer.py): a guest refused the home is
stored as 'away' (drawn nowhere) and gets no home space, only the 'home' block saying why.
"""
from typing import Literal
from fastapi import Request, HTTPException
from .models import Mutation
import uuid

SCHEMA = '''
CREATE TABLE IF NOT EXISTS home_access (
 owner_id TEXT PRIMARY KEY REFERENCES users(id), locked INTEGER NOT NULL DEFAULT 0, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS home_ejections (
 owner_id TEXT NOT NULL REFERENCES users(id), user_id TEXT NOT NULL REFERENCES users(id), until REAL NOT NULL,
 PRIMARY KEY(owner_id,user_id));
'''
# The owner counts as in the home this soon after a home poll (mp_presence.seen; HOST_GONE_SECONDS).
OWNER_SEEN = 20
# A guest already inside may stay this long after the owner's last poll from inside the home
# (mp_presence.home_seen): time to walk out behind the owner.
OWNER_GRACE = 10
# A guest sent out of the home cannot come back in for this long (the village visit goes on).
EJECT_SECONDS = 600
# Why a guest is not let in: the client shows the matching line and keeps the door shut.
REASONS = ('owner_away', 'locked', 'ejected')


class HomeLock(Mutation):
    locked: bool


class HomeEject(Mutation):
    user_id: uuid.UUID


def ensure(conn):
    conn.executescript(SCHEMA)


def locked(conn, owner_id) -> bool:
    row = conn.execute('SELECT locked FROM home_access WHERE owner_id=?', (owner_id,)).fetchone()
    return bool(row and row['locked'])


def ejected_until(conn, owner_id, user_id, now) -> float:
    row = conn.execute('SELECT until FROM home_ejections WHERE owner_id=? AND user_id=? AND until>?', (owner_id, user_id, now)).fetchone()
    return float(row['until']) if row else 0.0


def owner_inside(conn, owner_id, now) -> bool:
    """The owner's latest poll was from inside their own home, recently."""
    row = conn.execute('SELECT scene,host_id,seen FROM mp_presence WHERE user_id=?', (owner_id,)).fetchone()
    return bool(row and row['scene'] == 'home' and row['host_id'] == owner_id and now-row['seen'] <= OWNER_SEEN)


def owner_was_inside(conn, owner_id, now) -> bool:
    """The owner polled from inside their home within OWNER_GRACE (they may just have walked out)."""
    row = conn.execute('SELECT home_seen FROM mp_presence WHERE user_id=?', (owner_id,)).fetchone()
    return bool(row and row['home_seen'] is not None and now-row['home_seen'] <= OWNER_GRACE)


def state(conn, user_id, host_id, now, inside=False) -> dict:
    """The 'home' block of a presence reply: may this player be in host_id's home now?
    inside: the player's last poll was already from that home (so a lock does not push them out)."""
    if user_id == host_id:
        return {'open': True, 'owner': True, 'locked': locked(conn, host_id)}
    is_locked = locked(conn, host_id)
    reason = None
    until = ejected_until(conn, host_id, user_id, now)
    if until:
        reason = 'ejected'
    elif inside:
        if not owner_was_inside(conn, host_id, now):
            reason = 'owner_away'
    elif not owner_inside(conn, host_id, now):
        reason = 'owner_away'
    elif is_locked:
        reason = 'locked'
    block = {'open': reason is None, 'owner': False, 'locked': is_locked, 'owner_in': owner_inside(conn, host_id, now)}
    if reason:
        block['reason'] = reason
    if until:
        block['until'] = until
    return block


class HomeAccess:
    """POST /v1/home/lock and /v1/home/eject (the owner's), GET /v1/home/access (anyone's, about the
    home of the village they are in)."""

    def __init__(self, app, db, clock, auth, mutate, host_for):
        with db.read() as conn:
            ensure(conn)

        def fail(code, status=409):
            raise HTTPException(status, code)

        @app.get('/v1/home/access')
        def access(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                host = host_for(conn, user['id'])
                row = conn.execute('SELECT scene,host_id,seen FROM mp_presence WHERE user_id=?', (user['id'],)).fetchone()
                inside = bool(row and row['scene'] == 'home' and row['host_id'] == host and clock()-row['seen'] <= OWNER_SEEN)
                return {'host_id': host, **state(conn, user['id'], host, clock(), inside)}

        @app.post('/v1/home/lock')
        def lock(body: HomeLock, request: Request):
            def apply(conn, user):
                conn.execute('INSERT INTO home_access VALUES (?,?,?) ON CONFLICT(owner_id) DO UPDATE SET locked=excluded.locked,updated=excluded.updated',
                             (user['id'], int(body.locked), clock()))
                return {'locked': body.locked}
            return mutate(request, body, 'home_lock', apply)

        @app.post('/v1/home/eject')
        def eject(body: HomeEject, request: Request):
            def apply(conn, user):
                guest = str(body.user_id)
                if guest == user['id']:
                    fail('cannot_eject_self')
                conn.execute('INSERT INTO home_ejections VALUES (?,?,?) ON CONFLICT(owner_id,user_id) DO UPDATE SET until=excluded.until',
                             (user['id'], guest, clock()+EJECT_SECONDS))
                # Out of the home at once for everyone else; the guest's own next poll is refused.
                moved = conn.execute("UPDATE mp_presence SET scene='village',ix=NULL WHERE user_id=? AND host_id=? AND scene='home'", (guest, user['id'])).rowcount
                return {'ok': True, 'was_inside': bool(moved), 'until': clock()+EJECT_SECONDS}
            return mutate(request, body, 'home_eject', apply)
