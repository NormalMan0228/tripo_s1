"""Display names (the user's choice: banned words filtered, no duplicates). The login id (username)
stays the identifier (friend requests, sign-in); every place that shows a player to others also carries
`display_name`. Existing accounts start with their username as their display name.

Rules: 2..12 characters after trimming, letters/digits/spaces and a few marks; the craft request word
list and chat swears refuse (server/craft_moderation.py); names posing as staff are reserved; two names
are the same after NFKC, case folding and removing spaces (a UNIQUE index on users.display_key keeps
it); a name can change once a day.
"""
import re
import unicodedata

NAME_MIN, NAME_MAX = 2, 12
CHANGE_SECONDS = 86400
ALLOWED_MARKS = set(" _-.·'")
# Staff titles, refused anywhere in a name's Hangul and as a whole Latin word or a word's start.
RESERVED_KO = ('운영자', '관리자', '운영진', '운영팀', '개발자', '개발팀', '공식', '시스템', '지엠', '게임마스터')
RESERVED_EN_WORDS = ('gm', 'mod', 'staff', 'system', 'official', 'support')
RESERVED_EN_PREFIX = ('admin', 'moderator', 'gamemaster', 'operator', 'developer', 'villagen')


class NameError_(ValueError):
    """A refused display name; str() is the error code the game words."""


def key(name):
    """The duplicate key: NFKC, case folded, no spaces."""
    return ''.join(unicodedata.normalize('NFKC', name).casefold().split())


def clean(raw):
    """The display name as it is kept, or NameError_ with name_invalid / name_refused / name_reserved."""
    if not isinstance(raw, str):
        raise NameError_('name_invalid')
    name = ' '.join(unicodedata.normalize('NFKC', raw).split())
    if not NAME_MIN <= len(name) <= NAME_MAX:
        raise NameError_('name_invalid')
    for ch in name:
        if unicodedata.category(ch)[0] == 'C' or not (ch.isalnum() or ch in ALLOWED_MARKS):
            raise NameError_('name_invalid')
    folded = key(name)
    hangul = ''.join(ch for ch in folded if '가' <= ch <= '힣')
    words = re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKC', name).casefold())
    if (any(term in hangul for term in RESERVED_KO) or any(w in RESERVED_EN_WORDS for w in words)
            or any(w.startswith(RESERVED_EN_PREFIX) for w in words) or folded.startswith(RESERVED_EN_PREFIX)):
        raise NameError_('name_reserved')
    from .craft_moderation import check_text
    if check_text(name):
        raise NameError_('name_refused')
    return name


def migrate(db):
    """Once: display_name / display_key / name_changed columns, existing accounts named by their
    username, and the unique index. Usernames are lower-case [a-z0-9_], so their keys never collide."""
    columns = [r[1] for r in db.execute('PRAGMA table_info(users)')]
    if 'display_name' in columns and 'display_key' in columns and 'name_changed' in columns:
        return
    db.execute('BEGIN IMMEDIATE')
    try:
        columns = [r[1] for r in db.execute('PRAGMA table_info(users)')]
        if 'display_name' not in columns:
            db.execute('ALTER TABLE users ADD COLUMN display_name TEXT')
        if 'display_key' not in columns:
            db.execute('ALTER TABLE users ADD COLUMN display_key TEXT')
        if 'name_changed' not in columns:
            db.execute('ALTER TABLE users ADD COLUMN name_changed REAL NOT NULL DEFAULT 0')
        for row in db.execute('SELECT id,username FROM users WHERE display_name IS NULL').fetchall():
            db.execute('UPDATE users SET display_name=?,display_key=? WHERE id=?', (row[1], key(row[1]), row[0]))
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_display_key ON users(display_key)')
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


# Shown names in SQL: the display name, or the username for a row made before it was set.
SHOWN = "COALESCE({u}.display_name,{u}.username)"


def shown(alias='u'):
    return SHOWN.format(u=alias)
