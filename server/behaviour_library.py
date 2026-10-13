"""The learned library: what the AI made once, kept so the next similar request needs no AI.

Two kinds of entry, both checked by the same gates as fresh results before they are kept:

  describe  a behaviour a player described in the interaction editor (글로 설명하기), keyed by the
            normalised sentence and the object's part ids. Crafts of a library type name their
            parts by role (server/archetype_library.py), so one entry serves every clock or chest;
            one-part crafts all share the signature 'whole'. A hit costs no starseeds and no AI.
  design    a text-only craft the LLM designer planned (plan + program), keyed by the normalised
            request, style, size and motion (and the wording those send to the designer). Kept
            when the planning finishes, served only after that craft became an object; Tripo
            still builds a fresh mesh, so only the design step is skipped.

Fixture (offline) results are not kept: they cost nothing to make again. Operators list, inspect,
disable and delete entries with `python -m server.admin_cli library ...`.
"""
import hashlib
import json
import re
import unicodedata

SCHEMA = '''
CREATE TABLE IF NOT EXISTS behaviour_library (
 key TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL, signature TEXT NOT NULL,
 category TEXT NOT NULL DEFAULT '', value TEXT NOT NULL, provider TEXT NOT NULL DEFAULT '',
 origin TEXT NOT NULL DEFAULT '', ready INTEGER NOT NULL DEFAULT 0, disabled INTEGER NOT NULL DEFAULT 0,
 uses INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, last_used REAL);
CREATE INDEX IF NOT EXISTS behaviour_library_kind ON behaviour_library(kind, created);
'''

# Words that do not change what is asked ("please make it spin" = "spin", "돌게 해줘" = "돌게").
FILLERS = {'please', 'make', 'it', 'a', 'an', 'the', 'can', 'you', 'pls', 'plz',
           '해줘', '해주세요', '해', '주세요', '줘', '좀', '줄래', '해줄래', '부탁해', '제발'}
POLITE = ('해주세요', '해줘요', '해줘', '주세요', '줘요', '줘')


def normalize(text):
    """Case, width, punctuation and filler words do not make a request different."""
    value = unicodedata.normalize('NFKC', str(text)).casefold()
    tokens = [t for t in re.sub(r'[^\w]+', ' ', value).split() if t not in FILLERS]
    out = []
    for token in tokens:
        for ending in POLITE:
            if token.endswith(ending) and len(token) > len(ending):
                token = token[:-len(ending)]
                break
        out.append(token)
    return ' '.join(out)[:200]


def signature(parts):
    return ','.join(sorted(str(p['id']) for p in parts))


def make_key(kind, *fields):
    return hashlib.sha256('\x1f'.join((kind,) + tuple(str(f) for f in fields)).encode()).hexdigest()[:32]


def find(conn, key):
    """A served entry (ready, not disabled) as {'key', 'value', ...} or None."""
    row = conn.execute('SELECT * FROM behaviour_library WHERE key=? AND ready=1 AND disabled=0', (key,)).fetchone()
    if not row:
        return None
    entry = dict(row)
    entry['value'] = json.loads(entry['value'])
    return entry


def remember(conn, key, kind, label, sig, value, now, provider='', origin='', category='', ready=True):
    """Keeps a validated result. The first served entry for a key stays; one not served yet (its
    craft did not finish) is replaced by the newer result."""
    conn.execute('INSERT INTO behaviour_library(key,kind,label,signature,category,value,provider,origin,ready,created) '
                 'VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,provider=excluded.provider,'
                 'origin=excluded.origin,category=excluded.category,ready=excluded.ready,created=excluded.created '
                 'WHERE behaviour_library.ready=0',
                 (key, kind, label[:200], sig[:400], category[:40], json.dumps(value, separators=(',', ':')), provider[:60],
                  origin[:80], int(bool(ready)), now))


def mark_ready(conn, key):
    conn.execute('UPDATE behaviour_library SET ready=1 WHERE key=?', (key,))


def used(conn, key, now):
    conn.execute('UPDATE behaviour_library SET uses=uses+1,last_used=? WHERE key=?', (now, key))


# ---------------------------------------------------------------- operator view (admin_cli)

def listing(conn, kind=None, limit=50):
    rows = conn.execute('SELECT key,kind,label,signature,category,provider,origin,ready,disabled,uses,created,last_used '
                        'FROM behaviour_library' + (' WHERE kind=?' if kind else '') + ' ORDER BY created DESC LIMIT ?',
                        ((kind, limit) if kind else (limit,))).fetchall()
    return [dict(zip(('key', 'kind', 'label', 'signature', 'category', 'provider', 'origin', 'ready', 'disabled',
                      'uses', 'created', 'last_used'), tuple(r))) for r in rows]


def resolve(conn, prefix):
    """The one entry whose key starts with prefix (at least 6 characters)."""
    if len(prefix) < 6:
        raise ValueError('give at least 6 characters of the key')
    rows = conn.execute('SELECT key FROM behaviour_library WHERE key LIKE ?', (prefix.replace('%', '') + '%',)).fetchall()
    if len(rows) != 1:
        raise ValueError('no entry' if not rows else 'several entries start with ' + prefix)
    return rows[0][0]


def show(conn, prefix):
    key = resolve(conn, prefix)
    row = conn.execute('SELECT * FROM behaviour_library WHERE key=?', (key,)).fetchone()
    names = [d[0] for d in conn.execute('SELECT * FROM behaviour_library LIMIT 0').description]
    entry = dict(zip(names, tuple(row)))
    entry['value'] = json.loads(entry['value'])
    return entry
