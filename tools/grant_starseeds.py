"""One-time, audited operator grant of in-game starseeds to an existing account."""
import argparse
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path


def grant(database: Path, username: str, amount: int, reference: str):
    if not 1 <= amount <= 100000 or not reference or len(reference) > 120:
        raise ValueError('invalid_grant_request')
    with sqlite3.connect(database, timeout=15) as conn:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN IMMEDIATE')
        account = conn.execute('SELECT id,shards FROM users WHERE username=?', (username,)).fetchone()
        if account is None:
            raise ValueError('account_not_found')
        user_id, before = account
        previous = conn.execute(
            "SELECT user_id,amount FROM ledger WHERE reason='operator_grant' AND reference=?",
            (reference,),
        ).fetchone()
        if previous is not None:
            if previous != (user_id, amount):
                raise ValueError('grant_reference_conflict')
            return {'username': username, 'amount': amount, 'balance': before, 'already_applied': True}
        now = time.time()
        conn.execute(
            'INSERT INTO ledger(id,user_id,amount,reason,reference,created) VALUES (?,?,?,?,?,?)',
            (str(uuid.uuid4()), user_id, amount, 'operator_grant', reference, now),
        )
        conn.execute('UPDATE users SET shards=shards+? WHERE id=?', (amount, user_id))
        conn.execute(
            'INSERT INTO audit(user_id,action,target,outcome,created) VALUES (?,?,?,?,?)',
            (user_id, 'operator_grant', reference, f'credited_{amount}_starseeds', now),
        )
        after = conn.execute('SELECT shards FROM users WHERE id=?', (user_id,)).fetchone()[0]
        if after != before + amount:
            raise RuntimeError('balance_mismatch')
        return {'username': username, 'amount': amount, 'balance': after, 'already_applied': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--amount', type=int, required=True)
    parser.add_argument('--reference', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(grant(args.database, args.username, args.amount, args.reference)))
    except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
