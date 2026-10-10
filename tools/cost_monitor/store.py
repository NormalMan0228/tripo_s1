"""Settings and history of the cost monitor, kept on this PC only.

Folder: %LOCALAPPDATA%\\Villagen\\cost_monitor (VILLAGEN_COST_MONITOR_DIR overrides it, for tests).
  config.json       the user's changes on top of default_config.json (server usage keys live here)
  history.sqlite3   balance samples, hand-entered balances and the last reading of each source
  server.json       the running dashboard's port, process id and page token
Nothing here is inside the repository, and nothing is sent anywhere.
"""
import copy
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULTS_FILE = HERE / 'default_config.json'


def data_dir():
    override = os.environ.get('VILLAGEN_COST_MONITOR_DIR')
    if override:
        folder = Path(override)
    else:
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        folder = Path(base) / 'Villagen' / 'cost_monitor'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def write_json(path, value):
    """Atomic write, so a crash never leaves half a settings file."""
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class Config:
    """default_config.json from the repository, plus the user's overrides by source id.
    A source added to the defaults later shows up on its own; one the user added stays theirs."""

    def __init__(self, folder):
        self.path = Path(folder) / 'config.json'

    @staticmethod
    def defaults():
        return json.loads(DEFAULTS_FILE.read_text(encoding='utf-8'))

    def user(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(value, dict):
                value.setdefault('settings', {})
                value.setdefault('sources', [])
                return value
        except (OSError, ValueError):
            pass
        return {'version': 1, 'settings': {}, 'sources': []}

    def save(self, user):
        write_json(self.path, user)

    def merged(self):
        defaults, user = self.defaults(), self.user()
        settings = {**defaults['settings'], **user['settings']}
        overrides = {s.get('id'): s for s in user['sources'] if isinstance(s, dict)}
        sources = []
        for source in defaults['sources']:
            sources.append({**copy.deepcopy(source), **overrides.pop(source['id'], {}), 'builtin': True})
        for source in user['sources']:
            if isinstance(source, dict) and source.get('id') in overrides and source.get('type'):
                sources.append({**source, 'builtin': False})
        return {'settings': settings, 'sources': sources}

    def default_ids(self):
        return {s['id'] for s in self.defaults()['sources']}

    def change_source(self, source_id, changes, cleared=()):
        user = self.user()
        entry = next((s for s in user['sources'] if s.get('id') == source_id), None)
        if entry is None:
            entry = {'id': source_id}
            user['sources'].append(entry)
        entry.update(changes)
        for name in cleared:
            entry.pop(name, None)
        self.save(user)

    def add_source(self, source):
        user = self.user()
        user['sources'].append(source)
        self.save(user)

    def remove_source(self, source_id):
        user = self.user()
        user['sources'] = [s for s in user['sources'] if s.get('id') != source_id]
        self.save(user)

    def change_settings(self, changes):
        user = self.user()
        user['settings'].update(changes)
        self.save(user)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS samples (source TEXT NOT NULL, ts REAL NOT NULL, value REAL NOT NULL);
CREATE INDEX IF NOT EXISTS samples_source ON samples(source, ts);
CREATE TABLE IF NOT EXISTS manual_entries (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, balance REAL NOT NULL,
 checked_at REAL NOT NULL, recorded_at REAL NOT NULL, note TEXT NOT NULL DEFAULT '',
 origin TEXT NOT NULL DEFAULT 'dashboard');
CREATE INDEX IF NOT EXISTS manual_source ON manual_entries(source, checked_at);
CREATE TABLE IF NOT EXISTS latest (source TEXT PRIMARY KEY, fetched_at REAL NOT NULL, reading TEXT NOT NULL, raw TEXT);
'''

# A balance that did not change is stored again at most this often (keeps the file small).
SAMPLE_GAP = 15 * 60


class History:
    def __init__(self, path):
        self.path = str(path)
        with closing(self.connect()) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    def add_sample(self, source, value, ts):
        with closing(self.connect()) as db:
            last = db.execute('SELECT ts,value FROM samples WHERE source=? ORDER BY ts DESC LIMIT 1', (source,)).fetchone()
            if last and last['value'] == value and ts - last['ts'] < SAMPLE_GAP:
                return False
            db.execute('INSERT INTO samples VALUES (?,?,?)', (source, ts, float(value)))
            return True

    def series(self, source, since):
        """(ts, value) from the last sample before `since` onwards, oldest first."""
        with closing(self.connect()) as db:
            before = db.execute('SELECT ts,value FROM samples WHERE source=? AND ts<? ORDER BY ts DESC LIMIT 1',
                                (source, since)).fetchall()
            after = db.execute('SELECT ts,value FROM samples WHERE source=? AND ts>=? ORDER BY ts', (source, since)).fetchall()
        return [(r['ts'], r['value']) for r in list(before) + list(after)]

    def add_manual(self, source, balance, checked_at, note='', origin='dashboard', now=None):
        with closing(self.connect()) as db:
            cursor = db.execute('INSERT INTO manual_entries(source,balance,checked_at,recorded_at,note,origin) VALUES (?,?,?,?,?,?)',
                                (source, float(balance), float(checked_at), float(now or time.time()), note, origin))
            return cursor.lastrowid

    def manual(self, source):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT * FROM manual_entries WHERE source=? ORDER BY checked_at,id', (source,)).fetchall()
        return [dict(r) for r in rows]

    def delete_manual(self, source, entry_id):
        with closing(self.connect()) as db:
            return db.execute('DELETE FROM manual_entries WHERE source=? AND id=?', (source, entry_id)).rowcount == 1

    def save_latest(self, source, fetched_at, reading, raw=None):
        with closing(self.connect()) as db:
            db.execute('INSERT INTO latest VALUES (?,?,?,?) ON CONFLICT(source) DO UPDATE SET '
                       'fetched_at=excluded.fetched_at,reading=excluded.reading,raw=excluded.raw',
                       (source, fetched_at, json.dumps(reading, ensure_ascii=False),
                        None if raw is None else json.dumps(raw, ensure_ascii=False)))

    def latest(self):
        """{source: (fetched_at, reading, raw)} as last saved (raw is None for most sources)."""
        with closing(self.connect()) as db:
            rows = db.execute('SELECT * FROM latest').fetchall()
        out = {}
        for r in rows:
            try:
                out[r['source']] = (r['fetched_at'], json.loads(r['reading']), json.loads(r['raw']) if r['raw'] else None)
            except ValueError:
                continue
        return out


def spend(points, since):
    """Credits spent since `since`: the sum of every drop between consecutive balances.
    Rises (top-ups) are not spending and are skipped."""
    total, previous = 0.0, None
    for ts, value in points:
        if previous is not None and ts >= since and value < previous:
            total += previous - value
        previous = value
    return total


def topped_up(points, since):
    total, previous = 0.0, None
    for ts, value in points:
        if previous is not None and ts >= since and value > previous:
            total += value - previous
        previous = value
    return total


def day_start(now):
    """Local midnight of `now` (this PC's time zone)."""
    t = time.localtime(now)
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
