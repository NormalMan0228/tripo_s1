"""Currency balance and ledger writers. Callers own the surrounding transaction."""
import json
import logging
import uuid
from fastapi import HTTPException
from .security import ADMIN_DAILY_SHARD_LIMIT, record_event

log = logging.getLogger(__name__)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS economy_flags (
 user_id TEXT NOT NULL REFERENCES users(id), code TEXT NOT NULL,
 detail TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL,
 occurrences INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(user_id,code));
CREATE INDEX IF NOT EXISTS ledger_user_created ON ledger(user_id,created);
CREATE TABLE IF NOT EXISTS leaf_ledger (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), amount INTEGER NOT NULL,
 reason TEXT NOT NULL, reference TEXT NOT NULL, created REAL NOT NULL,
 UNIQUE(user_id,reason,reference));
CREATE INDEX IF NOT EXISTS leaf_ledger_user_created ON leaf_ledger(user_id,created);
'''


class EconomyRejected(HTTPException):
    def __init__(self, user_id, code, detail, status=409):
        super().__init__(status, code)
        self.user_id, self.evidence = user_id, detail


def flag(conn, user_id, code, detail, now):
    """Flags remain until operator review; security-event copies follow normal retention."""
    conn.execute('''INSERT INTO economy_flags(user_id,code,detail,first_seen,last_seen)
                    VALUES (?,?,?,?,?) ON CONFLICT(user_id,code) DO UPDATE SET
                    detail=excluded.detail,last_seen=excluded.last_seen,occurrences=occurrences+1''',
                 (user_id, code, json.dumps(detail, sort_keys=True), now, now))
    record_event(conn, 'economy_suspicious', user_id, {'code': code, **detail}, now)
    log.warning('economy_suspicious user=%s code=%s detail=%s', user_id, code, detail)


def change_shards(conn, user_id, amount, reason, reference, now, *, sell_daily=None, offset=540):
    """Balance + ledger are atomic even if a caller catches a constraint failure.

    Reject floats/bools rather than relying on SQLite's permissive integer affinity.
    Never commit the caller's transaction, including purchases with two counterparties.
    """
    if not conn.in_transaction:
        raise RuntimeError('currency_transaction_required')
    if type(amount) is not int or not -(2**63) <= amount < 2**63:
        raise EconomyRejected(user_id, 'invalid_shard_amount', {'reason': reason})
    row = conn.execute('SELECT shards FROM users WHERE id=?', (user_id,)).fetchone()
    if row is None:
        raise ValueError('currency_user_not_found')
    balance = row[0]
    if type(balance) is not int or balance < 0:
        raise EconomyRejected(user_id, 'invalid_shard_balance', {'balance': balance})
    if balance + amount < 0:
        raise HTTPException(409, 'insufficient_shards')
    if balance + amount >= 2**63:
        raise EconomyRejected(user_id, 'shard_balance_overflow', {'balance': balance, 'attempted': amount})
    if amount > 0 and reason in ('admin_grant', 'sell_reward'):
        if reason == 'sell_reward' and sell_daily is None:
            raise ValueError('sell_daily_required')
        shift = offset * 60 if reason == 'sell_reward' else 0
        start = ((now + shift) // 86400) * 86400 - shift
        cap = sell_daily if reason == 'sell_reward' else ADMIN_DAILY_SHARD_LIMIT
        paid = conn.execute('SELECT COALESCE(SUM(amount),0) FROM ledger WHERE user_id=? AND reason=? AND created>=? AND created<?',
                            (user_id, reason, start, start+86400)).fetchone()[0]
        if paid + amount > cap:
            raise EconomyRejected(user_id, 'admin_grant_limit' if reason == 'admin_grant' else 'sell_reward_limit',
                                  {'paid': paid, 'attempted': amount, 'cap': cap}, 429)
    conn.execute('SAVEPOINT shard_change')
    try:
        conn.execute('INSERT INTO ledger(id,user_id,amount,reason,reference,created) VALUES (?,?,?,?,?,?)',
                     (str(uuid.uuid4()), user_id, amount, reason, reference, now))
        conn.execute('UPDATE users SET shards=shards+? WHERE id=?', (amount, user_id))
    except BaseException:
        conn.execute('ROLLBACK TO shard_change')
        raise
    finally:
        conn.execute('RELEASE shard_change')
    if reason == 'sell_reward':
        recent = conn.execute("SELECT created FROM ledger WHERE user_id=? AND reason='sell_reward' AND created>=? AND created<=?",
                              (user_id, now-600, now)).fetchall()
        days = {int((r[0]+offset*60)//86400) for r in recent}
        if len(recent) >= 10 and len(days) > 1:
            flag(conn, user_id, 'boundary_sell_burst', {'sales': len(recent), 'window_seconds': 600}, now)


def change_coins(conn, user_id, state, amount, reason, reference, now):
    """Persist balance and leaf ledger together. Callers save later inventory/version edits.

    The first write records an old save's balance once, without giving additional money.
    """
    if not conn.in_transaction:
        raise RuntimeError('currency_transaction_required')
    if type(amount) is not int or not -(2**63) <= amount < 2**63:
        raise EconomyRejected(user_id, 'invalid_coin_amount', {'reason': reason})
    balance = state.get('coins', 0)
    if type(balance) is not int or balance < 0 or balance >= 2**63:
        raise EconomyRejected(user_id, 'invalid_coin_balance', {'balance': balance})
    if balance + amount < 0:
        raise HTTPException(409, 'life_not_enough_coins')
    if balance + amount >= 2**63:
        raise EconomyRejected(user_id, 'coin_balance_overflow', {'balance': balance, 'attempted': amount})
    updated = dict(state, coins=balance + amount)
    conn.execute('SAVEPOINT coin_change')
    try:
        if not conn.execute('SELECT 1 FROM leaf_ledger WHERE user_id=? LIMIT 1', (user_id,)).fetchone():
            conn.execute('INSERT INTO leaf_ledger VALUES (?,?,?,?,?,?)',
                         (str(uuid.uuid4()), user_id, balance, 'opening_balance', 'migration', now))
        conn.execute('INSERT INTO leaf_ledger VALUES (?,?,?,?,?,?)',
                     (str(uuid.uuid4()), user_id, amount, reason, reference, now))
        conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state',
                     (user_id, json.dumps(updated)))
    except BaseException:
        conn.execute('ROLLBACK TO coin_change')
        raise
    finally:
        conn.execute('RELEASE coin_change')
    state['coins'] = updated['coins']


def ledger_check(conn, now=None):
    """List discrepancies without repairing money. With now, persist review flags too."""
    rows = conn.execute('''SELECT u.id,u.username,u.shards,COALESCE(SUM(l.amount),0) AS ledger_sum
                           FROM users u LEFT JOIN ledger l ON l.user_id=u.id GROUP BY u.id
                           HAVING u.shards != COALESCE(SUM(l.amount),0) OR u.shards < 0
                           OR typeof(u.shards) != 'integer' ORDER BY u.username''').fetchall()
    result = [dict(zip(('user_id', 'username', 'shards', 'ledger_sum'), row)) for row in rows]
    if now is not None:
        for row in result:
            flag(conn, row['user_id'], 'ledger_mismatch', row, now)
    return result
