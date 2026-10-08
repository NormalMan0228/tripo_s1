"""Operator commands that run inside the server container.

    docker compose ... exec -T api python -m server.admin_cli delete-accounts --pattern '^qa_[0-9a-f]{6}$'
    docker compose ... exec -T api python -m server.admin_cli delete-accounts --pattern '^qa_[0-9a-f]{6}$' --yes

delete-accounts removes whole accounts (test or abuse accounts) with everything they own:
sessions, ledger, objects and their placement/runtime, studio jobs, parties, messages,
security events, and crafted model files nobody else uses. Without --yes it only lists
what it would remove. With --yes it first writes a verified backup to /backups.
Accounts are chosen by exact usernames and/or a regular expression (--pattern).
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    actions = parser.add_subparsers(dest='action', required=True)
    delete = actions.add_parser('delete-accounts', help='remove accounts and everything they own')
    delete.add_argument('usernames', nargs='*', help='exact usernames')
    delete.add_argument('--pattern', help='regular expression matched against the whole username')
    delete.add_argument('--yes', action='store_true', help='really remove (after a verified backup)')
    delete.add_argument('--data-dir', default='/data')
    delete.add_argument('--backups', default='/backups')
    args = parser.parse_args(argv)
    if not args.usernames and not args.pattern:
        parser.error('give usernames or --pattern')
    return delete_accounts(args)


if __name__ == '__main__':
    sys.exit(main())
