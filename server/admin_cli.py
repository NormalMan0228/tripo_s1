"""Operator commands that run inside the server container.

    docker compose ... exec -T api python -m server.admin_cli delete-accounts --pattern '^qa_[0-9a-f]{6}$'
    docker compose ... exec -T api python -m server.admin_cli delete-accounts --pattern '^qa_[0-9a-f]{6}$' --yes

delete-accounts removes whole accounts (test or abuse accounts) with everything they own:
sessions, ledger, objects and their placement/runtime, studio jobs, parties, messages,
security events, and crafted model files nobody else uses. Without --yes it only lists
what it would remove. With --yes it first writes a verified backup to /backups.
Accounts are chosen by exact usernames and/or a regular expression (--pattern).

library lists and manages the learned library (server/behaviour_library.py): behaviours players
described and designs the LLM made, reused for the next same request without the AI.

    ... python -m server.admin_cli library list [--kind describe|design] [--limit 50]
    ... python -m server.admin_cli library show KEY        (the first 6+ characters of a key)
    ... python -m server.admin_cli library disable KEY     (stop serving it; enable undoes)
    ... python -m server.admin_cli library delete KEY

npc-homes shows one player's village residents' homes (server/npc_homes.py): every gift, whether
it is in storage or at which slot, the next change time, and friendship. Read-only.

    ... python -m server.admin_cli npc-homes USERNAME

story shows or restarts one player's opening story chapter "마을의 첫 선물" (server/story.py).
reset puts the account back at the letter on the desk (rehearsals; an account made before the
chapter existed starts it this way): the piece on the café terrace goes back to the bag, every other
piece, letter and return gift stays. Treasure chests are not part of the chapter: opened ones
stay open (and paid). Ask the player to sign in again afterwards.

    ... python -m server.admin_cli story show USERNAME
    ... python -m server.admin_cli story reset USERNAME

chat and reports are the operator's moderation tools for the social layer (server/chat.py,
server/friends.py). Deleted lines also vanish from the screens that show them (chat 'removed');
a mute refuses that player's lines until it ends (0 minutes lifts it).

    ... python -m server.admin_cli chat list [--username NAME] [--grep TEXT] [--limit 50]
    ... python -m server.admin_cli chat delete MESSAGE_ID [MESSAGE_ID ...]
    ... python -m server.admin_cli chat mute USERNAME MINUTES
    ... python -m server.admin_cli reports list [--all] [--limit 50]
    ... python -m server.admin_cli reports close REPORT_ID [REPORT_ID ...]

knocks expire ends every open knock (visit requests, kind 'knock'). Run it right before rolling the
server back to a version before the social layer (6028e2c and older): those list every pending
invitation, so a 0.11.x host would see a knock as a party invitation, and accepting it would move
the host into the knocker's village.

    ... python -m server.admin_cli knocks expire
quests shows one player's residents' requests (server/quests.py): which are under way or done,
when, and the starseeds each paid (the ledger's quest_reward rows). Read-only.

    ... python -m server.admin_cli quests show USERNAME

chests shows one player's treasure chests (server/treasure.py): which are open, when, the starseeds
each paid (the ledger's chest_reward rows) and which are left. Read-only.

    ... python -m server.admin_cli chests show USERNAME
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from .backups import create_backup, verify_backup
from . import behaviour_library

# Columns that hold a user id and mean "this row belongs to that user". creator_id is left
# out on purpose: an object one of these accounts made may now belong to someone else.
USER_COLUMNS = {'user_id', 'owner_id', 'seller_id', 'buyer_id', 'author_id', 'host_id', 'guest_id',
                'sender_id', 'recipient_id', 'member_id', 'visitor_id', 'actor_id', 'leader_id',
                'friend_id', 'from_id', 'to_id', 'inviter_id', 'invitee_id', 'blocked_id'}


def tables(conn):
    return {name: [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')]
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def plan(conn, usernames, pattern):
    rows = conn.execute('SELECT id,username,shards,created FROM users').fetchall()
    chosen = [r for r in rows if r[1] in usernames or (pattern and re.fullmatch(pattern, r[1]))]
    users = {r[0] for r in chosen}
    schema = tables(conn)
    objects = {r[0] for r in conn.execute('SELECT id,owner_id FROM objects') if r[1] in users} if 'objects' in schema else set()
    jobs = set()
    for name in ('studio_jobs', 'jobs'):
        if name in schema:
            jobs |= {r[0] for r in conn.execute(f'SELECT id,owner_id FROM "{name}"') if r[1] in users}
    # Model files of the removed objects that no remaining object uses.
    assets = set()
    if 'objects' in schema:
        mine = {r[0] for r in conn.execute('SELECT asset_id,owner_id FROM objects') if r[1] in users and r[0]}
        others = {r[0] for r in conn.execute('SELECT asset_id,owner_id FROM objects') if r[1] not in users and r[0]}
        assets = {a for a in mine - others if a != 'starter'}
    removals = {}
    for name, columns in schema.items():
        conditions, values = [], []
        if name == 'users':
            conditions.append(('id', users))
        for column in columns:
            if column in USER_COLUMNS:
                conditions.append((column, users))
            elif column == 'object_id' or (name == 'objects' and column == 'id'):
                conditions.append((column, objects))
            elif column == 'job_id' or (name in ('studio_jobs', 'jobs') and column == 'id'):
                conditions.append((column, jobs))
            elif column == 'asset_id' or (name == 'assets' and column == 'id'):
                conditions.append((column, assets))
        conditions = [(c, ids) for c, ids in conditions if ids]
        if not conditions:
            continue
        where = ' OR '.join(f'"{c}" IN ({",".join("?" * len(ids))})' for c, ids in conditions)
        for _, ids in conditions:
            values.extend(sorted(ids))
        count = conn.execute(f'SELECT count(*) FROM "{name}" WHERE {where}', values).fetchone()[0]
        if count:
            removals[name] = (where, values, count)
    files = []
    if assets and 'assets' in schema and 'relative_path' in schema['assets']:
        files = [r[0] for r in conn.execute(f'SELECT relative_path FROM assets WHERE id IN ({",".join("?" * len(assets))})', sorted(assets))]
    return chosen, removals, files, sorted(objects)


def remove_paint(data, object_ids):
    """Painted textures (assets/paint/<object>.<sha>.png) of removed objects; their
    object_paint rows go with the other object_id rows."""
    from .object_paint import remove_object_files
    return sum(remove_object_files(data / 'assets', object_id) for object_id in object_ids)


def delete_accounts(args):
    data = Path(args.data_dir)
    database = data / 'world.sqlite3'
    with sqlite3.connect(database, timeout=30) as conn:
        chosen, removals, files, objects = plan(conn, set(args.usernames), args.pattern)
    print(json.dumps({'accounts': [{'username': r[1], 'stars': r[2],
                                    'created': time.strftime('%Y-%m-%d %H:%M', time.gmtime(r[3]))} for r in chosen],
                      'rows': {name: item[2] for name, item in removals.items()}, 'model_files': len(files)},
                     ensure_ascii=False, indent=1))
    if not chosen:
        print('No matching accounts.')
        return 0
    if not args.yes:
        print('Dry run: nothing was removed. Add --yes to remove these accounts.')
        return 0
    snapshot = Path(args.backups) / ('before-delete-accounts-' + time.strftime('%Y%m%d-%H%M%S'))
    create_backup(data, snapshot)
    verify_backup(snapshot)
    print(json.dumps({'backup': str(snapshot)}))
    with sqlite3.connect(database, timeout=30) as conn:
        conn.execute('PRAGMA foreign_keys=OFF')
        _, removals, files, objects = plan(conn, set(args.usernames), args.pattern)
        for name, (where, values, _) in removals.items():
            conn.execute(f'DELETE FROM "{name}" WHERE {where}', values)
        conn.commit()
    removed_files = 0
    for relative in files:
        target = (data / 'assets' / relative).resolve() if not relative.startswith('assets/') else (data / relative).resolve()
        if data.resolve() in target.parents and target.is_file():
            target.unlink()
            removed_files += 1
    removed_paint = remove_paint(data, objects)
    print(json.dumps({'ok': True, 'removed_accounts': len(chosen), 'removed_model_files': removed_files,
                      'removed_paint_files': removed_paint}))
    return 0


def library(args):
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    with sqlite3.connect(database, timeout=30) as conn:
        conn.executescript(behaviour_library.SCHEMA)
        if args.command == 'list':
            print(json.dumps(behaviour_library.listing(conn, args.kind, args.limit), ensure_ascii=False, indent=1))
            return 0
        try:
            key = behaviour_library.resolve(conn, args.key or '')
        except ValueError as error:
            print(str(error))
            return 1
        if args.command == 'show':
            print(json.dumps(behaviour_library.show(conn, key), ensure_ascii=False, indent=1))
        elif args.command == 'delete':
            conn.execute('DELETE FROM behaviour_library WHERE key=?', (key,))
            print(json.dumps({'ok': True, 'deleted': key}))
        else:
            conn.execute('UPDATE behaviour_library SET disabled=? WHERE key=?', (int(args.command == 'disable'), key))
            print(json.dumps({'ok': True, args.command + 'd': key}))
    return 0


def npc_homes(args):
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    from .npc_homes import describe, SCHEMA
    with sqlite3.connect(database, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT id FROM users WHERE username=?', (args.username.lower(),)).fetchone()
        if not user:
            print('No such account.')
            return 1
        # A world from before resident gifts has none of these tables yet (they start empty).
        conn.executescript(SCHEMA)
        print(json.dumps(describe(conn, user['id']), ensure_ascii=False, indent=1))
    return 0


def residents(args):
    """Local operator moves; no player mutation endpoint and no relationship reset."""
    from . import village_residents as residency, npc_homes as homes, story as chapter
    from .config import Settings
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    settings = Settings(data_dir=Path(args.data_dir))
    # Validate the relevant configuration without reading or writing another world.
    import math
    if any(not math.isfinite(t) or not 0 <= t <= 30 * 86400
           for t in (settings.resident_arrive_seconds, settings.resident_leave_seconds)):
        raise ValueError('Invalid resident move timing')
    if args.command != 'show' and not settings.resident_moves:
        print('TRIPOTHON_RESIDENT_MOVES is disabled.')
        return 1
    with sqlite3.connect(database, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        user = conn.execute('SELECT id FROM users WHERE username=?', (args.username.lower(),)).fetchone()
        if not user:
            print('No such account.')
            return 1
        conn.executescript(homes.SCHEMA + chapter.SCHEMA + residency.SCHEMA)
        conn.execute('BEGIN IMMEDIATE')
        now = time.time()
        residency.sync(conn, user['id'], now, settings)
        if args.command != 'show':
            action = residency.arrive if args.command == 'move-in' else residency.leave
            action(conn, user['id'], args.npc, now, settings)
        result = residency.brief(conn, user['id'], now, settings)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


def story(args):
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    from . import story as chapter
    with sqlite3.connect(database, timeout=30, isolation_level=None) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT id FROM users WHERE username=?', (args.username.lower(),)).fetchone()
        if not user:
            print('No such account.')
            return 1
        # A world from before the chapter (or resident gifts) gets the empty tables first.
        from .npc_homes import SCHEMA as HOMES
        from .village_residents import SCHEMA as RESIDENTS
        conn.executescript(HOMES + chapter.SCHEMA + RESIDENTS)
        if args.command == 'show':
            print(json.dumps(chapter.describe(conn, user['id']), ensure_ascii=False, indent=1))
            return 0
        conn.execute('BEGIN IMMEDIATE')
        try:
            result = chapter.reset(conn, user['id'], time.time())
            conn.execute('COMMIT')
        except BaseException:
            conn.execute('ROLLBACK')
            raise
        print(json.dumps({'ok': True, 'username': args.username.lower(), **result}, ensure_ascii=False))
    return 0


def social_db(args):
    """The world database with the social tables (an older world gets them empty first)."""
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return None
    from .friends import SCHEMA
    conn = sqlite3.connect(database, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA + 'CREATE TABLE IF NOT EXISTS mp_message_removals (id INTEGER PRIMARY KEY, created REAL NOT NULL);')
    return conn


def chat(args):
    conn = social_db(args)
    if conn is None:
        return 1
    try:
        columns = [r[1] for r in conn.execute('PRAGMA table_info(mp_messages)')]
        if not columns:
            print('No chat yet.')
            return 0
        if args.command == 'list':
            where, values = [], []
            if args.target:
                where.append('u.username=?')
                values.append(args.target.lower())
            if args.grep:
                where.append('e.text LIKE ?')
                values.append('%' + args.grep + '%')
            channel = 'e.channel' if 'channel' in columns else 'NULL'
            rows = conn.execute(f'SELECT e.id,e.room,{channel} AS channel,u.username,e.text,e.created FROM mp_messages e LEFT JOIN users u ON u.id=e.user_id '
                                + ('WHERE ' + ' AND '.join(where) if where else '') + ' ORDER BY e.id DESC LIMIT ?', (*values, args.limit)).fetchall()
            print(json.dumps([{'id': r['id'], 'channel': r['channel'] or ('party' if r['room'].startswith('party:') else 'local'),
                               'room': r['room'].split(':')[0], 'username': r['username'], 'text': r['text'],
                               'time': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(r['created']))} for r in rows[::-1]], ensure_ascii=False, indent=1))
            return 0
        if args.command == 'delete':
            ids = [int(v) for v in args.values]
            conn.execute('BEGIN IMMEDIATE')
            removed = 0
            for message_id in ids:
                removed += conn.execute('DELETE FROM mp_messages WHERE id=?', (message_id,)).rowcount
                conn.execute('INSERT INTO mp_message_removals VALUES (?,?) ON CONFLICT(id) DO UPDATE SET created=excluded.created', (message_id, time.time()))
            conn.execute('COMMIT')
            print(json.dumps({'ok': True, 'removed': removed}))
            return 0
        if len(args.values) != 2 or not args.values[1].isdigit():
            print('chat mute USERNAME MINUTES')
            return 1
        user = conn.execute('SELECT id FROM users WHERE username=?', (args.values[0].lower(),)).fetchone()
        if not user:
            print('No such account.')
            return 1
        minutes = int(args.values[1])
        until = time.time() + minutes * 60 if minutes else None
        conn.execute('INSERT INTO social_prefs(user_id,chat_muted_until) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET chat_muted_until=excluded.chat_muted_until', (user['id'], until))
        print(json.dumps({'ok': True, 'username': args.values[0].lower(), 'muted_until': until}))
        return 0
    finally:
        conn.close()


def reports(args):
    conn = social_db(args)
    if conn is None:
        return 1
    try:
        if args.command == 'list':
            rows = conn.execute('SELECT r.*,a.username AS reporter,b.username AS reported FROM social_reports r LEFT JOIN users a ON a.id=r.user_id '
                                'LEFT JOIN users b ON b.id=r.to_id ' + ('' if args.all else "WHERE r.state='open' ") + 'ORDER BY r.id DESC LIMIT ?', (args.limit,)).fetchall()
            print(json.dumps([{'id': r['id'], 'reporter': r['reporter'], 'reported': r['reported'], 'reason': r['reason'], 'note': r['note'],
                               'message': r['text'], 'context': json.loads(r['context'] or '[]'), 'state': r['state'],
                               'time': time.strftime('%Y-%m-%d %H:%M', time.gmtime(r['created']))} for r in rows], ensure_ascii=False, indent=1))
            return 0
        closed = sum(conn.execute("UPDATE social_reports SET state='closed',updated=? WHERE id=?", (time.time(), int(v))).rowcount for v in args.values)
        print(json.dumps({'ok': True, 'closed': closed}))
        return 0
    finally:
        conn.close()


def knocks(args):
    conn = social_db(args)
    if conn is None:
        return 1
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mp_invites'").fetchone():
            print(json.dumps({'ok': True, 'expired': 0}))
            return 0
        conn.execute('BEGIN IMMEDIATE')
        expired = conn.execute("UPDATE mp_invites SET state='revoked' WHERE kind='knock' AND state IN ('pending','suppressed')").rowcount
        conn.execute('COMMIT')
        print(json.dumps({'ok': True, 'expired': expired}))
        return 0
    finally:
        conn.close()
def demo(args):
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    if not 0 <= args.stars <= 10000:
        print('--stars must be 0-10000.')
        return 1
    from . import demo as staging, story as chapter
    with sqlite3.connect(database, timeout=30, isolation_level=None) as conn:
        conn.row_factory = sqlite3.Row
        named = {}
        for name in [args.username] + ([args.source] if args.source else []):
            row = conn.execute('SELECT id FROM users WHERE username=?', (name.lower(),)).fetchone()
            if not row:
                print('No such account: ' + name)
                return 1
            named[name] = row['id']
        if args.command == 'list':
            print(json.dumps(staging.pieces(conn, named[args.username]), ensure_ascii=False, indent=1))
            return 0
        from .npc_homes import SCHEMA as HOMES
        from .village_residents import SCHEMA as RESIDENTS
        conn.executescript(HOMES + chapter.SCHEMA + RESIDENTS)
        conn.execute('BEGIN IMMEDIATE')
        try:
            result = staging.prep(conn, args.data_dir, named[args.username], time.time(), args.stars,
                                  named.get(args.source), args.pick)
            conn.execute('COMMIT')
        except ValueError as error:
            conn.execute('ROLLBACK')
            print(str(error))
            return 1
        except BaseException:
            conn.execute('ROLLBACK')
            raise
        print(json.dumps({'ok': True, 'username': args.username.lower(), **result}, ensure_ascii=False))
    return 0


def quests(args):
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    from . import quests as requests
    with sqlite3.connect(database, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT id FROM users WHERE username=?', (args.username.lower(),)).fetchone()
        if not user:
            print('No such account.')
            return 1
        # A world from before the requests has no progress table yet (it starts empty).
        conn.executescript(requests.SCHEMA)
        print(json.dumps(requests.describe(conn, user['id']), ensure_ascii=False, indent=1))
    return 0


def chests(args):
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    from . import treasure
    with sqlite3.connect(database, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT id FROM users WHERE username=?', (args.username.lower(),)).fetchone()
        if not user:
            print('No such account.')
            return 1
        # A world from before the chests has no table yet (it starts empty).
        conn.executescript(treasure.SCHEMA)
        print(json.dumps(treasure.describe(conn, user['id']), ensure_ascii=False, indent=1))
    return 0


def ledger_check(args):
    from . import economy
    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    with sqlite3.connect(database, timeout=30) as conn:
        conn.executescript(economy.SCHEMA)
        conn.execute('BEGIN IMMEDIATE')
        mismatches = economy.ledger_check(conn, time.time())
        flags = [dict(zip(('user_id','code','detail','first_seen','last_seen','occurrences'), r))
                 for r in conn.execute('SELECT user_id,code,detail,first_seen,last_seen,occurrences FROM economy_flags ORDER BY last_seen DESC')]
    print(json.dumps({'ok': not mismatches, 'mismatches': mismatches, 'flags': flags}, ensure_ascii=False, indent=1))
    return 1 if mismatches else 0


def tester(args):
    """Local operator access only. No HTTP route can set this flag."""
    import getpass
    import os
    import uuid
    from contextlib import closing
    from argon2 import PasswordHasher
    from .config import Settings
    from .database import Database
    from .models import strong_password
    from .security import record_event
    from .account_limits import tester_credits

    database = Path(args.data_dir) / 'world.sqlite3'
    if not database.is_file():
        print('No world database at ' + str(database))
        return 1
    if args.command != 'list' and args.username not in ('tripo1', 'tripo2', 'tripo3', 'tripo4', 'tripo5'):
        print('Tester accounts must be named tripo1 through tripo5.')
        return 1
    # Read the existing mode; never create a second or mismatched world.
    with sqlite3.connect(database) as conn:
        mode = conn.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()[0]
    settings = Settings(data_dir=Path(args.data_dir), mode=mode)
    limits = settings.limits_for({'is_tester': 1})
    if not 0 <= limits.welcome_stars <= 10000 or not 1 <= limits.tester_credit_budget <= 10000000:
        print('Invalid tester limits.')
        return 1
    password_hash = None
    if args.command == 'create':
        password = os.environ.get('TRIPOTHON_TESTER_PASSWORD') or getpass.getpass('Tester password: ')
        if not 10 <= len(password) <= 128 or not strong_password(password):
            print('Password must have 10-128 characters, an uppercase letter and a special character.')
            return 1
        password_hash = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1).hash(password)
    with closing(Database(database, mode)) as db, db.transaction() as conn:
        if args.command == 'list':
            print(json.dumps({'accounts': [dict(r) for r in conn.execute(
                'SELECT username,shards AS stars FROM users WHERE is_tester=1 ORDER BY username')],
                'credits_committed': tester_credits(conn), 'credit_budget': limits.tester_credit_budget}))
            return 0
        user = conn.execute('SELECT * FROM users WHERE username=?', (args.username,)).fetchone()
        if args.command == 'create':
            if user:
                print('Account already exists; use tester grant after verifying its owner.')
                return 1
            user_id, now = str(uuid.uuid4()), time.time()
            conn.execute('INSERT INTO users(id,username,password_hash,shards,created,is_tester) VALUES (?,?,?,?,?,1)',
                         (user_id, args.username, password_hash, limits.welcome_stars, now))
            conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',
                         (str(uuid.uuid4()), user_id, limits.welcome_stars, 'tester_welcome', user_id, now))
            conn.execute('INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) VALUES (?,?,?,?,?,?)',
                         (str(uuid.uuid4()), user_id, user_id, 'starter', 'Welcome wooden chair', now))
            if settings.story_enabled:
                from . import story
                story.begin(conn, user_id, now)
        else:
            if not user:
                print('No such account.')
                return 1
            user_id = user['id']
            conn.execute('UPDATE users SET is_tester=1 WHERE id=?', (user_id,))
        record_event(conn, 'tester_' + args.command, user_id, {'username': args.username}, time.time())
        print(json.dumps({'ok': True, 'username': args.username, 'is_tester': True}))
    return 0



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    actions = parser.add_subparsers(dest='action', required=True)
    delete = actions.add_parser('delete-accounts', help='remove accounts and everything they own')
    delete.add_argument('usernames', nargs='*', help='exact usernames')
    delete.add_argument('--pattern', help='regular expression matched against the whole username')
    delete.add_argument('--yes', action='store_true', help='really remove (after a verified backup)')
    delete.add_argument('--data-dir', default='/data')
    delete.add_argument('--backups', default='/backups')
    learned = actions.add_parser('library', help='list and manage the learned library')
    learned.add_argument('command', choices=('list', 'show', 'disable', 'enable', 'delete'))
    learned.add_argument('key', nargs='?', help='a key or its first 6+ characters')
    learned.add_argument('--kind', choices=('describe', 'design'))
    learned.add_argument('--limit', type=int, default=50)
    learned.add_argument('--data-dir', default='/data')
    moving = actions.add_parser('residents', help='show residency or start an operator move')
    moving.add_argument('username')
    moving.add_argument('command', choices=('show', 'move-in', 'move-out'), nargs='?', default='show')
    moving.add_argument('npc', choices=('shopkeeper',), nargs='?', default='shopkeeper')
    moving.add_argument('--data-dir', default='/data')
    homes = actions.add_parser('npc-homes', help="show one player's residents' homes and gifts")
    homes.add_argument('username')
    homes.add_argument('--data-dir', default='/data')
    chapter = actions.add_parser('story', help='show or restart the opening story chapter of one player')
    chapter.add_argument('command', choices=('show', 'reset'))
    chapter.add_argument('username')
    chapter.add_argument('--data-dir', default='/data')
    staged = actions.add_parser('demo', help='ready an account for a demo run: story at the letter, starseeds, spare pieces')
    staged.add_argument('command', choices=('prep', 'list'))
    staged.add_argument('username')
    staged.add_argument('--stars', type=int, default=0, help='prep: top the starseed balance up to at least this')
    staged.add_argument('--copy-from', dest='source', help='prep: account to copy finished pieces from (see list)')
    staged.add_argument('--pick', action='append', default=[], help='prep: a piece id (8+ characters) or a word of its name; repeat')
    staged.add_argument('--data-dir', default='/data')
    talk = actions.add_parser('chat', help='list, delete or mute chat lines (moderation)')
    talk.add_argument('command', choices=('list', 'delete', 'mute'))
    talk.add_argument('values', nargs='*', help='delete: message ids; mute: USERNAME MINUTES')
    talk.add_argument('--username', dest='target', help='list: only this player')
    talk.add_argument('--grep', help='list: lines containing this text')
    talk.add_argument('--limit', type=int, default=50)
    talk.add_argument('--data-dir', default='/data')
    reported = actions.add_parser('reports', help="list or close players' reports")
    reported.add_argument('command', choices=('list', 'close'))
    reported.add_argument('values', nargs='*', help='close: report ids')
    reported.add_argument('--all', action='store_true', help='list: closed reports too')
    reported.add_argument('--limit', type=int, default=50)
    reported.add_argument('--data-dir', default='/data')
    knocked = actions.add_parser('knocks', help='end every open knock (before rolling the server back)')
    knocked.add_argument('command', choices=('expire',))
    knocked.add_argument('--data-dir', default='/data')
    asked = actions.add_parser('quests', help="show one player's residents' requests and their rewards")
    asked.add_argument('command', choices=('show',))
    asked.add_argument('username')
    asked.add_argument('--data-dir', default='/data')
    found = actions.add_parser('chests', help="show one player's treasure chests and their rewards")
    found.add_argument('command', choices=('show',))
    found.add_argument('username')
    found.add_argument('--data-dir', default='/data')
    ledger = actions.add_parser('ledger-check', help='compare starseed balances with the ledger and flag discrepancies')
    ledger.add_argument('--data-dir', default='/data')
    testing = actions.add_parser('tester', help='operator-only tester accounts and shared credit usage')
    testing.add_argument('command', choices=('create', 'grant', 'list'))
    testing.add_argument('username', nargs='?')
    testing.add_argument('--data-dir', default='/data')
    args = parser.parse_args(argv)
    if args.action == 'ledger-check':
        return ledger_check(args)
    if args.action == 'tester':
        return tester(args)
    if args.action == 'knocks':
        return knocks(args)
    if args.action == 'chat':
        return chat(args)
    if args.action == 'reports':
        return reports(args)
    if args.action == 'residents':
        return residents(args)
    if args.action == 'story':
        return story(args)
    if args.action == 'demo':
        return demo(args)
    if args.action == 'quests':
        return quests(args)
    if args.action == 'chests':
        return chests(args)
    if args.action == 'npc-homes':
        return npc_homes(args)
    if args.action == 'library':
        return library(args)
    if not args.usernames and not args.pattern:
        parser.error('give usernames or --pattern')
    return delete_accounts(args)


if __name__ == '__main__':
    sys.exit(main())
