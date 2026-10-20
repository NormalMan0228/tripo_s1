"""Who has cleared the expedition tutorial (/v1/me tutorial_done).

The tutorial is a selectable expedition map; tutorial_done is progress, not a forced destination.
Clearing it once, alone or with a party, sets tutorial_done for good. Abandoning or leaving it does
not. Accounts that went on expeditions before the tutorial existed have had their first expedition:
when this table is first made they are recorded as done (run_id 'before_tutorial').
"""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS tutorial_progress (
 user_id TEXT PRIMARY KEY REFERENCES users(id), run_id TEXT NOT NULL, completed REAL NOT NULL);
'''
BEFORE = 'before_tutorial'


def ensure(db, now):
    """Create the table; on its first creation record the players with earlier expeditions."""
    with db.transaction() as conn:
        existed = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tutorial_progress'").fetchone()
        conn.execute(SCHEMA)
        if existed:
            return
        conn.execute('INSERT OR IGNORE INTO tutorial_progress SELECT DISTINCT owner_id,?,? FROM runs', (BEFORE, now))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='coop_members'").fetchone():
            conn.execute('INSERT OR IGNORE INTO tutorial_progress SELECT DISTINCT user_id,?,? FROM coop_members', (BEFORE, now))


def done(conn, user_id):
    return conn.execute('SELECT 1 FROM tutorial_progress WHERE user_id=?', (user_id,)).fetchone() is not None


def mark(conn, user_id, run_id, now):
    conn.execute('INSERT OR IGNORE INTO tutorial_progress VALUES (?,?,?)', (user_id, run_id, now))
