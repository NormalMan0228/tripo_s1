"""Durable tester reservations and shared generation counts; use write transactions."""
import math
from .provider import ProviderError


def daily_counts(conn, since, user_id=None):
    where = 'j.created>=?' + (' AND j.owner_id=?' if user_id else ' AND u.is_tester=0')
    args = (since, user_id) if user_id else (since,)
    return sum(conn.execute(f'SELECT count(*) FROM {table} j JOIN users u ON u.id=j.owner_id WHERE {where}', args).fetchone()[0]
               for table in ('jobs', 'studio_jobs'))


def tester_credits(conn, exclude=''):
    return conn.execute('SELECT COALESCE(SUM(credits),0) FROM tester_credit_spend WHERE reference!=?',
                        (exclude,)).fetchone()[0]


def check_tester_budget(conn, limits, credits, reference=''):
    if limits.is_tester and tester_credits(conn, reference) + credits > limits.tester_credit_budget:
        raise ProviderError('tester_credit_budget_exhausted')


def reserve_tester_credits(conn, limits, reference, credits):
    if not limits.is_tester:
        return
    old = conn.execute('SELECT credits FROM tester_credit_spend WHERE reference=?', (reference,)).fetchone()
    credits = max(credits, old[0] if old else 0)
    check_tester_budget(conn, limits, credits, reference)
    conn.execute('INSERT INTO tester_credit_spend VALUES (?,?) ON CONFLICT(reference) DO UPDATE SET credits=excluded.credits',
                 (reference, credits))


def record_tester_bill(conn, reference, credits):
    # Actual bills can exceed estimates. Record even an overrun, then block further submissions.
    # Never release reservations on failure, missing billing, account deletion or retry.
    if type(credits) in (int, float) and math.isfinite(credits) and credits >= 0:
        conn.execute('UPDATE tester_credit_spend SET credits=MAX(credits,?) WHERE reference=?', (credits, reference))
