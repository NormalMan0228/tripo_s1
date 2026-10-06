import sqlite3
from contextlib import contextmanager, closing

SCHEMA = '''
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 shards INTEGER NOT NULL DEFAULT 0 CHECK(shards>=0), created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS profiles (
 user_id TEXT PRIMARY KEY REFERENCES users(id), avatar TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version>=1));
CREATE TABLE IF NOT EXISTS homesteads (
 user_id TEXT PRIMARY KEY REFERENCES users(id), state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS campaign_progress (
 user_id TEXT NOT NULL REFERENCES users(id), chapter_id TEXT NOT NULL,
 completed_run TEXT NOT NULL REFERENCES runs(id), completed REAL NOT NULL,
 PRIMARY KEY(user_id,chapter_id));
CREATE TABLE IF NOT EXISTS objects (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), creator_id TEXT NOT NULL REFERENCES users(id),
 asset_id TEXT NOT NULL, name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#f6eee0',
 version INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL DEFAULT 'inventory' CHECK(state IN ('inventory','placed','listed')),
 x REAL, z REAL, rotation INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS assets (
 id TEXT PRIMARY KEY, relative_path TEXT NOT NULL, digest TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS asset_render_budgets (
 asset_id TEXT PRIMARY KEY REFERENCES assets(id), budget TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), state TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','won','lost','abandoned')), reward INTEGER NOT NULL DEFAULT 0,
 claimed INTEGER NOT NULL DEFAULT 0 CHECK(claimed IN(0,1)), created REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(owner_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS ledger (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), amount INTEGER NOT NULL,
 reason TEXT NOT NULL, reference TEXT NOT NULL, created REAL NOT NULL,
 UNIQUE(user_id, reason, reference));
CREATE TABLE IF NOT EXISTS requests (
 user_id TEXT NOT NULL, request_id TEXT NOT NULL, operation TEXT NOT NULL, fingerprint TEXT NOT NULL,
 response TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(user_id, request_id));
CREATE TABLE IF NOT EXISTS listings (
 id TEXT PRIMARY KEY, object_id TEXT NOT NULL REFERENCES objects(id), seller_id TEXT NOT NULL REFERENCES users(id),
 price INTEGER NOT NULL CHECK(price>0), state TEXT NOT NULL CHECK(state IN('open','sold','cancelled')),
 buyer_id TEXT REFERENCES users(id), created REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_listing ON listings(object_id) WHERE state='open';
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), prompt TEXT NOT NULL,
 state TEXT NOT NULL, provider_task TEXT, asset_id TEXT, object_id TEXT,
 error_code TEXT, cost INTEGER NOT NULL CHECK(cost>0), provider_reserve INTEGER NOT NULL,
 created REAL NOT NULL, updated REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_job ON jobs(owner_id)
 WHERE state IN ('queued','submitting','generating','downloading','unknown');
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, action TEXT NOT NULL, target TEXT,
 outcome TEXT NOT NULL, created REAL NOT NULL);
-- Per-username login attempts (also for names that do not exist, so lockout
-- never reveals which accounts are real). Cleared on a successful login.
CREATE TABLE IF NOT EXISTS login_attempts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS login_attempts_username ON login_attempts(username,created);
CREATE INDEX IF NOT EXISTS login_attempts_created ON login_attempts(created);
-- Append-only security log: login_failed, login_locked, register, admin_grant.
CREATE TABLE IF NOT EXISTS security_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, user_id TEXT, detail TEXT,
 created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS security_events_kind ON security_events(kind,created);
CREATE INDEX IF NOT EXISTS security_events_created ON security_events(created);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id,expires);
'''

class Database:
    def __init__(self, path, mode):
        self.path = str(path)
        with closing(self.connect()) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)
            # Accounts are players unless an operator promotes them (tools/admin_accounts.py).
            if 'role' not in [r[1] for r in db.execute('PRAGMA table_info(users)')]:
                db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'player'")
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('mode',?)", (mode,))
            if db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()[0] != mode:
                raise ValueError('Demo and live must use different database directories')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        return db

    @contextmanager
    def read(self):
        """Read-only work must not reserve SQLite's single writer slot."""
        db = self.connect()
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
