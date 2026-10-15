"""Persistent display-time overrides for operator-provisioned tester accounts.

These values are separate from presence, game clocks and reward/day boundaries.
The client applies the returned hour to its own sky and lighting.
"""
import json
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from pydantic import Field

from .models import Strict


PRESET_HOURS = {'morning': 8, 'noon': 12, 'evening': 18, 'night': 22}
TimeOverride = Literal['morning', 'noon', 'evening', 'night'] | Annotated[
    int, Field(strict=True, ge=0, le=23)] | None

SCHEMA = '''
CREATE TABLE IF NOT EXISTS account_time_overrides (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 value TEXT NOT NULL, updated REAL NOT NULL);
'''


class TimeOverrideUpdate(Strict):
    # Required even when clearing: an empty object must not erase a saved value.
    time_override: TimeOverride


def require_permission(user):
    if not user['is_tester'] and user['role'] != 'admin':
        raise HTTPException(403, 'time_override_forbidden')


def public(conn, user_id):
    row = conn.execute('SELECT value,updated FROM account_time_overrides WHERE user_id=?',
                       (user_id,)).fetchone()
    value = json.loads(row['value']) if row else None
    return {'time_override': value, 'hour': PRESET_HOURS.get(value, value),
            'updated': row['updated'] if row else None}


class DevTime:
    def __init__(self, app, db, clock, auth):
        with db.read() as conn:
            conn.executescript(SCHEMA)

        @app.get('/v1/dev/time_override')
        def read(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                require_permission(user)
                return public(conn, user['id'])

        @app.post('/v1/dev/time_override')
        def update(body: TimeOverrideUpdate, request: Request):
            with db.transaction() as conn:
                user = auth(conn, request)
                require_permission(user)
                # Assignments and clearing are naturally idempotent. Do not add an
                # audit entry or change the timestamp when the value is unchanged.
                previous = public(conn, user['id'])
                if previous['time_override'] == body.time_override:
                    return previous
                now = clock()
                if body.time_override is None:
                    conn.execute('DELETE FROM account_time_overrides WHERE user_id=?', (user['id'],))
                else:
                    conn.execute('INSERT INTO account_time_overrides(user_id,value,updated) VALUES (?,?,?) '
                                 'ON CONFLICT(user_id) DO UPDATE SET value=excluded.value,updated=excluded.updated',
                                 (user['id'], json.dumps(body.time_override), now))
                conn.execute('INSERT INTO audit(user_id,action,target,outcome,created) VALUES (?,?,?,?,?)',
                             (user['id'], 'dev_time_override', None,
                              json.dumps({'time_override': body.time_override}), now))
                return public(conn, user['id'])
