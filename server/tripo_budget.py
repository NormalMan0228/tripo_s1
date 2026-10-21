"""Durable Tripo liabilities. All mutations require a BEGIN IMMEDIATE transaction.

An attempt is committed before the POST and starts unknown: even a process crash
cannot turn a possibly charged request into free budget. No user operation deletes
attempts. Unsubmitted build estimates are separate holds, not provider attempts.
"""
import json
import math
import uuid

from .provider import ProviderError


SCHEMA = '''
CREATE TABLE IF NOT EXISTS tripo_attempts (
 attempt_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, owner_id TEXT NOT NULL,
 is_tester INTEGER NOT NULL, kind TEXT NOT NULL, part_id TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('unknown','reserved','charged','released')),
 reserved_credits REAL NOT NULL CHECK(reserved_credits>=0),
 actual_credits REAL CHECK(actual_credits>=0), task_id TEXT, provider_key TEXT NOT NULL DEFAULT '',
 created REAL NOT NULL, updated REAL NOT NULL, release_reason TEXT, released_at REAL);
CREATE INDEX IF NOT EXISTS tripo_attempts_job ON tripo_attempts(job_id);
CREATE INDEX IF NOT EXISTS tripo_attempts_owner ON tripo_attempts(owner_id,created);
CREATE TABLE IF NOT EXISTS tripo_job_holds (
 job_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, is_tester INTEGER NOT NULL,
 credits REAL NOT NULL CHECK(credits>=0));
'''


def valid_credits(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def liability(row):
    return 0.0 if row['state'] == 'released' else max(row['reserved_credits'], row['actual_credits'] or 0)


def attempt_credits(conn, job_id=None, tester=False):
    where, args = ['state!=\'released\''], []
    if job_id is not None:
        where.append('job_id=?'); args.append(job_id)
    if tester:
        where.append('is_tester=1')
    return conn.execute('SELECT COALESCE(SUM(MAX(reserved_credits,COALESCE(actual_credits,0))),0) '
                        'FROM tripo_attempts WHERE ' + ' AND '.join(where), args).fetchone()[0]


def job_billing(conn, job_id):
    rows = conn.execute("SELECT state,actual_credits FROM tripo_attempts WHERE job_id=? AND state!='released'",
                        (job_id,)).fetchall()
    known = sum(row['actual_credits'] or 0 for row in rows)
    complete = all(row['actual_credits'] is not None and row['state']=='charged' for row in rows)
    return {'known_tripo_credits':known, 'tripo_credits_consumed':known if complete else None,
            'billing_complete':complete}


def legacy_bills(parts):
    """Every provider step stored before the durable attempt ledger existed."""
    for part in parts.values():
        for task, key in (('task','credits_consumed'), ('image_task','image_credits_consumed'),
                          ('concept_task','concept_credits_consumed'), ('multiview_task','multiview_credits_consumed')):
            yield part.get(task), part.get(key)
        for entry in [part.get('rig', {}), *part.get('anims', {}).values()]:
            yield entry.get('task'), entry.get('credits_consumed')


def legacy_credits(conn, exclude='', tester=False):
    # Worlds predating the ledger retain their old conservative accounting until
    # that craft is adopted. Tester references are job_id:build, job_id:legacy or
    # job_id:concept:attempt_id. Keep orphaned/deleted jobs too: the old ledger
    # proves a reservation existed even when no craft or account row survives.
    by_job = {}
    for row in conn.execute('SELECT reference,credits FROM tester_credit_spend'):
        job_id = row['reference'].split(':', 1)[0]
        if job_id != exclude:
            by_job[job_id] = by_job.get(job_id, 0) + row['credits']
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='studio_jobs'").fetchone():
        return sum(by_job.values())
    for row in conn.execute('SELECT id,state,parts,provenance FROM studio_jobs WHERE id!=? '
                            'AND id NOT IN (SELECT job_id FROM tripo_job_holds)', (exclude,)):
        # A legacy tester reference proves that this craft used the shared tester
        # budget, even if the account was deleted or its current role changed.
        # Apply known overruns before adoption too; ordinary crafts stay separate.
        if tester and row['id'] not in by_job:
            continue
        try:
            parts = json.loads(row['parts'] or '{}')
            quote = float(json.loads(row['provenance'] or '{}').get('estimated_tripo_credits') or 0)
        except (TypeError, ValueError):
            parts, quote = {}, 0
        known, missing = 0.0, False
        for task, amount in legacy_bills(parts):
            if not task:
                continue
            if valid_credits(amount):
                known += amount
            else:
                missing = True
        studio_credits = max(known, quote) if row['state'] in ('building','submitting','unknown') or missing else known
        # These are two records of the same old craft, not separate liabilities.
        # A failed concept can exist only in the tester ledger; a provider overrun
        # can instead be larger in parts. Preserve the larger known commitment.
        by_job[row['id']] = max(by_job.get(row['id'], 0), studio_credits)
    return sum(by_job.values())


def committed_credits(conn, exclude='', tester=False):
    filter_sql = ' AND is_tester=1' if tester else ''
    total = conn.execute('SELECT COALESCE(SUM(MAX(reserved_credits,COALESCE(actual_credits,0))),0) '
                         "FROM tripo_attempts WHERE state!='released' AND job_id!=?" + filter_sql,
                         (exclude,)).fetchone()[0]
    total += conn.execute('SELECT COALESCE(SUM(credits),0) FROM tripo_job_holds WHERE job_id!=?' + filter_sql,
                          (exclude,)).fetchone()[0]
    total += legacy_credits(conn, exclude, tester)
    return total


def manage_job(conn, job_id, owner_id, is_tester, now):
    if conn.execute('SELECT 1 FROM tripo_job_holds WHERE job_id=?', (job_id,)).fetchone():
        return
    # Adopt an older craft conservatively; retain every legacy tester reservation.
    old = conn.execute('SELECT reference,credits FROM tester_credit_spend WHERE substr(reference,1,?)=?',
                       (len(job_id)+1, job_id+':')).fetchall()
    previous = sum(row['credits'] for row in old)
    known = 0
    created = now
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='studio_jobs'").fetchone():
        row = conn.execute('SELECT state,parts,provenance,created FROM studio_jobs WHERE id=?', (job_id,)).fetchone()
        if row:
            created = row['created']
            parts = json.loads(row['parts'] or '{}')
            bills = list(legacy_bills(parts))
            bill = sum(amount for _, amount in bills if valid_credits(amount))
            known = bill
            submitted = any(task for task, _ in bills)
            if submitted or row['state'] in ('submitting','unknown'):
                previous = max(previous, bill, float(json.loads(row['provenance'] or '{}').get('estimated_tripo_credits') or 0))
    conn.execute('INSERT INTO tripo_job_holds VALUES (?,?,?,0)', (job_id,owner_id,int(is_tester)))
    if previous:
        conn.execute('INSERT INTO tripo_attempts(attempt_id,job_id,owner_id,is_tester,kind,part_id,state,'
                     'reserved_credits,actual_credits,created,updated) VALUES (?,?,?,?,?,?,\'unknown\',?,?,?,?)',
                     (str(uuid.uuid4()),job_id,owner_id,int(is_tester or bool(old)),'legacy_import','',previous,known or None,created,now))
    for row in old:
        conn.execute('DELETE FROM tester_credit_spend WHERE reference=?', (row['reference'],))


def check_budget(conn, limits, job_id, credits, craft_extra=0):
    # Tester check retains its established error code when several limits overlap.
    if limits.is_tester and committed_credits(conn, job_id, tester=True) + credits > limits.tester_credit_budget:
        raise ProviderError('tester_credit_budget_exhausted')
    if limits.max_credits_per_craft and credits + craft_extra > limits.max_credits_per_craft:
        raise ProviderError('craft_over_trial_limit')
    if limits.tripo_credit_budget and committed_credits(conn, job_id) + credits > limits.tripo_credit_budget:
        raise ProviderError('tripo_budget_exhausted')


def hold_build(conn, limits, job_id, owner_id, credits, now):
    manage_job(conn, job_id, owner_id, limits.is_tester, now)
    check_budget(conn, limits, job_id, attempt_credits(conn, job_id) + credits)
    conn.execute('UPDATE tripo_job_holds SET credits=?,is_tester=? WHERE job_id=?', (credits,int(limits.is_tester),job_id))


def reserve_attempt(conn, limits, job_id, owner_id, kind, part_id, credits, remaining_credits, now,
                    provider_key='', craft_extra=0):
    if not valid_credits(credits) or not valid_credits(remaining_credits):
        raise ValueError('Invalid Tripo reservation')
    manage_job(conn, job_id, owner_id, limits.is_tester, now)
    check_budget(conn, limits, job_id, attempt_credits(conn, job_id)+credits+remaining_credits, craft_extra)
    attempt_id = str(uuid.uuid4())
    conn.execute('UPDATE tripo_job_holds SET credits=?,is_tester=? WHERE job_id=?', (remaining_credits,int(limits.is_tester),job_id))
    conn.execute('INSERT INTO tripo_attempts(attempt_id,job_id,owner_id,is_tester,kind,part_id,state,'
                 'reserved_credits,provider_key,created,updated) VALUES (?,?,?,?,?,?,\'unknown\',?,?,?,?)',
                 (attempt_id,job_id,owner_id,int(limits.is_tester),kind,part_id,credits,provider_key,now,now))
    return attempt_id


def record_task(conn, attempt_id, task_id, now):
    conn.execute("UPDATE tripo_attempts SET task_id=?,state=CASE WHEN state='unknown' THEN 'reserved' ELSE state END,"
                 'updated=? WHERE attempt_id=?', (task_id,now,attempt_id))


def record_result(conn, attempt_id, result, now):
    actual = result.get('credits_consumed')
    if valid_credits(actual):
        conn.execute("UPDATE tripo_attempts SET actual_credits=MAX(COALESCE(actual_credits,0),?),"
                     "state=CASE WHEN state='released' AND ?=0 THEN 'released' ELSE 'charged' END,updated=? WHERE attempt_id=?",
                     (actual,actual,now,attempt_id))
    elif result.get('status') in ('failed','cancelled','banned','expired','success'):
        mark_unknown(conn, attempt_id, now)


def mark_unknown(conn, attempt_id, now):
    conn.execute("UPDATE tripo_attempts SET state='unknown',updated=? WHERE attempt_id=? "
                 "AND actual_credits IS NULL AND state!='released'", (now,attempt_id))


def clear_hold(conn, job_id):
    conn.execute('UPDATE tripo_job_holds SET credits=0 WHERE job_id=?', (job_id,))


def release_attempt(conn, attempt_id, reason, now):
    row = conn.execute('SELECT * FROM tripo_attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
    if not row:
        raise ValueError('attempt_not_found')
    if not reason or not reason.strip():
        raise ValueError('release_reason_required')
    if (row['actual_credits'] or 0) > 0:
        raise ValueError('charged_attempt_cannot_be_released')
    if row['state'] == 'released':
        return False
    conn.execute("UPDATE tripo_attempts SET state='released',release_reason=?,released_at=?,updated=? WHERE attempt_id=?",
                 (reason.strip(),now,now,attempt_id))
    return True
