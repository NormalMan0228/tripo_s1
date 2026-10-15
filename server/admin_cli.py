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
piece, letter and return gift stays. Ask the player to sign in again afterwards.

    ... python -m server.admin_cli story show USERNAME
    ... python -m server.admin_cli story reset USERNAME

quests shows one player's residents' requests (server/quests.py): which are under way or done,
when, and the starseeds each paid (the ledger's quest_reward rows). Read-only.

    ... python -m server.admin_cli quests show USERNAME
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
                'friend_id', 'from_id', 'to_id', 'inviter_id', 'invitee_id'}


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
        conn.executescript(HOMES + chapter.SCHEMA)
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
    homes = actions.add_parser('npc-homes', help="show one player's residents' homes and gifts")
    homes.add_argument('username')
    homes.add_argument('--data-dir', default='/data')
    chapter = actions.add_parser('story', help='show or restart the opening story chapter of one player')
    chapter.add_argument('command', choices=('show', 'reset'))
    chapter.add_argument('username')
    chapter.add_argument('--data-dir', default='/data')
    asked = actions.add_parser('quests', help="show one player's residents' requests and their rewards")
    asked.add_argument('command', choices=('show',))
    asked.add_argument('username')
    asked.add_argument('--data-dir', default='/data')
    args = parser.parse_args(argv)
    if args.action == 'story':
        return story(args)
    if args.action == 'quests':
        return quests(args)
    if args.action == 'npc-homes':
        return npc_homes(args)
    if args.action == 'library':
        return library(args)
    if not args.usernames and not args.pattern:
        parser.error('give usernames or --pattern')
    return delete_accounts(args)


if __name__ == '__main__':
    sys.exit(main())
