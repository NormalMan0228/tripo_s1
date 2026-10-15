"""Where a player picks up after signing in again (docs/contracts/SERVER_CONTRACTS_KO.md, items 55-56).

The spot is the player's last presence: the live row while it lasts (a game that crashed never said
goodbye) or the copy kept when the game logged out or quit (multiplayer.leave). Only the player's own
village or home is offered as a place to start; a friend's village, an expedition or a home the
player was refused give no spot. The client still checks the spot is walkable and falls back to the
home door.

wake: start by getting up from the attic bed. True after WAKE_AFTER seconds away (the server's
clock, never the client's) or when the game ended inside the player's own home.
"""
from fastapi import Request

SCHEMA = '''
CREATE TABLE IF NOT EXISTS last_spots (
 user_id TEXT PRIMARY KEY REFERENCES users(id), host_id TEXT NOT NULL, scene TEXT NOT NULL, place TEXT, floor INTEGER,
 x REAL NOT NULL, z REAL NOT NULL, y REAL NOT NULL, yaw REAL NOT NULL, at REAL NOT NULL);
'''
# Away this long (seconds), the next sign-in starts in bed.
WAKE_AFTER = 3600
# Places inside the home where ending the game means waking up in bed next time.
HOME_PLACES = (None, 'home')
SPOT_FIELDS = ('scene', 'place', 'floor', 'x', 'z', 'y', 'yaw')


def ensure(conn):
    conn.executescript(SCHEMA)


def save_from_presence(conn, user_id):
    """Keep the player's last spot before the live presence row goes (logout, quit)."""
    conn.execute('INSERT INTO last_spots SELECT user_id,host_id,scene,place,floor,x,z,y,yaw,seen FROM mp_presence WHERE user_id=? '
                 'ON CONFLICT(user_id) DO UPDATE SET host_id=excluded.host_id,scene=excluded.scene,place=excluded.place,'
                 'floor=excluded.floor,x=excluded.x,z=excluded.z,y=excluded.y,yaw=excluded.yaw,at=excluded.at', (user_id,))


def latest(conn, user_id):
    live = conn.execute('SELECT host_id,scene,place,floor,x,z,y,yaw,seen AS at FROM mp_presence WHERE user_id=?', (user_id,)).fetchone()
    kept = conn.execute('SELECT host_id,scene,place,floor,x,z,y,yaw,at FROM last_spots WHERE user_id=?', (user_id,)).fetchone()
    rows = [r for r in (live, kept) if r is not None]
    return max(rows, key=lambda r: r['at']) if rows else None


def resume(conn, user_id, now) -> dict | None:
    """{spot, at, away_seconds, wake}, or None for a player never seen in the world (first sign-in:
    the story's opening takes over)."""
    row = latest(conn, user_id)
    if row is None:
        return None
    own = row['host_id'] == user_id and row['scene'] in ('village', 'home')
    away = max(0.0, now-row['at'])
    ended_at_home = own and row['scene'] == 'home' and row['place'] in HOME_PLACES
    return {'spot': {k: row[k] for k in SPOT_FIELDS} if own else None, 'at': row['at'], 'away_seconds': round(away, 1),
            'wake': away >= WAKE_AFTER or ended_at_home}


class LastSpot:
    """GET /v1/social/resume: the same block the sign-in reply carries ('resume'), for a game that
    needs it again without signing in."""

    def __init__(self, app, db, clock, auth):
        with db.read() as conn:
            ensure(conn)

        @app.get('/v1/social/resume')
        def get_resume(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                return {'resume': resume(conn, user['id'], clock())}
